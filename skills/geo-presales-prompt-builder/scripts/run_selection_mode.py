#!/usr/bin/env python3
"""售前选词模式的一条命令入口：表单 Case → 每个市场一批 9 字段的题（Suda 2026-10-29）。

线上生词改为在服务器上跑本 skill 的选词模式（references/selection-mode.md）。本脚本把
确定性的部分包起来，中间的调研和写题交给 agent：

    prepare   归一化 Case，建独立工作目录（skill 拷贝、inputs/、TASK.md）
    agent     在工作目录里让 agent 按 TASK.md 调研、写 out/bank.json
    finalize  跑选词 validator、售前专属检查和导出脚本，写 out/result.json

    python3 run_selection_mode.py run --case payload.json --market US --platforms chatgpt,gemini --out <工作目录> --agent sdk
    python3 run_selection_mode.py run --case payload.json --market US --platforms chatgpt --out <工作目录> --agent-cmd "<命令>"
    python3 run_selection_mode.py prepare  --case payload.json --market US --platforms chatgpt --out <工作目录>
    python3 run_selection_mode.py finalize --out <工作目录>

一次只跑一个市场；选了几个国家/地区就调几次，每次一个新工作目录。
--platforms 传表单「AI 平台」选中的平台（collect_answers.py 的平台名，逗号分隔）：研究预跑只在
这些平台上各跑 1 次，客户没选的平台不采。

agent 两种接法：
  --agent sdk       内置 Claude Agent SDK 适配（pip 包 claude-agent-sdk）。环境变量：
                    ANTHROPIC_BASE_URL、ANTHROPIC_API_KEY（模型网关）、AGENT_MODEL（模型名）。
  --agent-cmd "…"   宿主自己的 harness：在工作目录里用 shell 执行，环境变量 WORKSPACE、
                    TASK_FILE 指向工作目录和任务说明；命令结束后应已写出 out/bank.json。
调研要用的密钥照常放环境变量：SCRAPELESS_API_KEY、DATAFORSEO_LOGIN、DATAFORSEO_PASSWORD。

产物（都在工作目录里）：
  out/bank.json        题库 JSON（内部底稿）
  out/upload/*.csv     交给线上的 9 字段题（每个市场一份）
  out/result.json      {status, market, locale, upload_files, prompt_count, topics, errors…}
  logs/                agent 记录、两个检查与导出的原始输出

退出码：0 生词成功；1 生词失败（agent 出错、超时或检查没过，原因见 result.json）；
2 输入或环境有错（Case 归一化不过、参数错、缺 SCRAPELESS_API_KEY），不启动 agent，errors 原样在 result.json。

可能出错的地方（本脚本针对的就是这些）：
  1. Case 缺必填字段 → prepare 停下，不启动 agent，errors 原样交回
  2. agent 没写出 bank.json、超时或异常退出 → 失败，不拿半成品导出
  3. 题库没过选词 validator、售前专属检查（check_presales_bank.py：题型、发现型过半、每主题≥5、对比题点名冻结竞品）
     或导出检查（超 60 条、字段缺、类型不对） → 失败，报错原文进 result.json
  4. 题库的市场和传入的 --market 不一致 → 失败，避免把别的市场的题交上去
  4b. --platforms 里有采集器不认识的平台名 → 输入错误，不启动 agent
  5. 工作目录已存在 → 拒绝覆盖，避免两个 Case 共用一个目录
  6. 没有 SCRAPELESS_API_KEY → agent 采不了研究预跑会凭空写题，启动前就停下
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS = SKILL.parent
# 选词模式会用到的 skill；geo-monitoring 要带上，选词 skill 里有指向它的软链。
SKILL_DIRS = ("geo-presales-prompt-builder", "geo-prompt-selection-builder", "shared",
              "geo-presales-report-builder", "geo-monitoring")
# legacy = 已归档的默认模式规则，不给 agent 看，免得混用两套口径
IGNORE = shutil.ignore_patterns(".snapshots", "__pycache__", ".pytest_cache", "*.bak", "evals", "reports",
                                "*.local.json", "build", "legacy")
DEFAULT_TIMEOUT = 120 * 60
# 与 geo-presales-report-builder/scripts/collect_answers.py 的 ALL_PLATFORMS 一致
KNOWN_PLATFORMS = {"chatgpt", "perplexity", "copilot", "gemini", "aimode", "overview", "grok", "alexa"}

TASK = """你在一个无人值守的流水线里，没有人会回答问题。遇到歧义按最合理的判断继续，把假设写进 `out/notes.md`。

任务：给这个品牌生成售前诊断题。按 `.agents/skills/geo-presales-prompt-builder/references/selection-mode.md`（售前生词步骤）逐步做；它引用的选词规则在 `.agents/skills/geo-prompt-selection-builder/`。

输入：
- `inputs/case-normalized.json`：归一化后的品牌信息（Case）。竞品已冻结，不增删、不替换。主题一律由你从矩阵行聚出；Case 填了主题（`topic_source` 为 `case`）时，它只当业务重点线索。
- 市场：`{market}`；语言：`{locale}`。所有题的 `region` 写 `{market}`，`config.collection_config` 写 `{{"market": "{market}", "language": "{locale}"}}`。

联网：
- 不用 WebSearch / WebFetch。搜索和取网页用 `.agents/skills/shared/scripts/net.py`；搜索信号、关键词数据、评价用同目录的 `collect_serp_signals.py`、`collect_keyword_data.py`、`collect_reviews.py`。
- 研究预跑只在客户选的平台上跑：`python3 .agents/skills/geo-presales-report-builder/scripts/collect_answers.py --questions research/prerun.csv --out research/prerun --regions {market} --platforms {platforms}`。不要加别的平台。
- 没有带登录态的浏览器。要登录或通道表里标「不通」的站跳过，按 selection-mode.md「线上没有浏览器」一节处理，写进 notes.md 的「未覆盖来源」。
- 调研过程文件都放 `research/`。只在本工作目录里读写，不要访问工作目录以外的路径。

交付（只写这两个路径）：
1. `out/bank.json`：题库 JSON，字段按 selection-mode.md。
2. `out/notes.md`：简短记录，分这几节：「预跑答案」（研究预跑的答案目录和每个平台是否采到）、「受众」、「属性与相对竞品」、「没开的格子」（矩阵里没开的格子和原因）、「主题」（每个主题为什么成立）、「假设」、「未覆盖来源」、「validator 告警」。

结束前依次运行，三条都要退出码 0；有错就改题库再跑：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-presales-prompt-builder/scripts/check_presales_bank.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def scrapeless_key_present() -> bool:
    """和 shared/scripts/net.py 同一顺序：先环境变量，再 macOS 钥匙串。"""
    if os.environ.get("SCRAPELESS_API_KEY", "").strip():
        return True
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def load_normalizer():
    sys.path.insert(0, str(HERE))
    import normalize_case  # noqa: PLC0415
    return normalize_case


def parse_platforms(raw: str) -> tuple[list[str], list[str]]:
    names = [p.strip().removeprefix("scraper.").casefold() for p in raw.split(",") if p.strip()]
    names = list(dict.fromkeys(names))
    return names, [n for n in names if n not in KNOWN_PLATFORMS]


def prepare(case_path: Path, market: str, platforms: str, ws: Path, task_file: Path | None) -> int:
    if ws.exists():
        print(f"工作目录已存在：{ws}（每个 Case × 市场用一个新目录）", file=sys.stderr)
        return 2
    market = market.strip()
    if not market:
        print("--market 不能为空", file=sys.stderr)
        return 2
    names, unknown = parse_platforms(platforms)
    if not names or unknown:
        print(f"--platforms 要填采集器认识的平台名 {sorted(KNOWN_PLATFORMS)}，收到 {platforms!r}", file=sys.stderr)
        return 2
    ws.mkdir(parents=True)
    for sub in ("inputs", "research", "out", "logs"):
        (ws / sub).mkdir()
    try:
        payload = json.loads(case_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        write_json(ws / "out/result.json", {"status": "input_error", "market": market,
                                             "errors": [{"code": "unreadable_input", "message": str(exc)}]})
        return 2
    result = load_normalizer().normalize(payload)
    write_json(ws / "inputs/case-normalized.json", result)
    if not result["ok"]:
        write_json(ws / "out/result.json", {"status": "input_error", "market": market,
                                             "errors": result["errors"], "warnings": result["warnings"]})
        return 2
    locale = result["normalized"]["locale"]
    for name in SKILL_DIRS:
        src = SKILLS / name
        if src.is_dir():
            shutil.copytree(src, ws / ".agents/skills" / name, symlinks=True, ignore=IGNORE)
    task = task_file.read_text(encoding="utf-8") if task_file else TASK.format(market=market, locale=locale, platforms=",".join(names))
    (ws / "TASK.md").write_text(task, encoding="utf-8")
    write_json(ws / "out/result.json", {"status": "prepared", "market": market, "locale": locale,
                                         "platforms": names,
                                         "warnings": result["warnings"]})
    return 0


async def _run_sdk(ws: Path, task: str, timeout: int) -> dict:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query  # noqa: PLC0415
    model = os.environ.get("AGENT_MODEL", "").strip()
    if not os.environ.get("ANTHROPIC_BASE_URL") or not os.environ.get("ANTHROPIC_API_KEY") or not model:
        raise RuntimeError("--agent sdk 需要环境变量 ANTHROPIC_BASE_URL、ANTHROPIC_API_KEY、AGENT_MODEL")
    home = ws / "logs/agent-home"
    home.mkdir(parents=True, exist_ok=True)
    env = {"ANTHROPIC_MODEL": model, "ANTHROPIC_SMALL_FAST_MODEL": model,
           "ANTHROPIC_DEFAULT_HAIKU_MODEL": model, "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
           "ANTHROPIC_DEFAULT_OPUS_MODEL": model, "CLAUDE_CODE_SUBAGENT_MODEL": model,
           "ANTHROPIC_AUTH_TOKEN": "", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
           "CLAUDE_CONFIG_DIR": str(home)}
    opts = ClaudeAgentOptions(cwd=str(ws), model=model, env=env, permission_mode="bypassPermissions",
                              disallowed_tools=["WebSearch", "WebFetch"], setting_sources=["project"],
                              max_turns=600)
    record: dict = {"tool_calls": 0}
    with (ws / "logs/agent.jsonl").open("w", encoding="utf-8") as log:
        async def consume():
            async for m in query(prompt=task, options=opts):
                if isinstance(m, AssistantMessage):
                    record["tool_calls"] += sum(1 for b in m.content if type(b).__name__ == "ToolUseBlock")
                if isinstance(m, ResultMessage):
                    record.update(finish=getattr(m, "subtype", None), turns=getattr(m, "num_turns", None),
                                  final=getattr(m, "result", None))
                log.write(json.dumps({"type": type(m).__name__, "repr": repr(m)[:2000]}, ensure_ascii=False) + "\n")
        await asyncio.wait_for(consume(), timeout)
    return record


def run_agent(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int) -> dict:
    task = (ws / "TASK.md").read_text(encoding="utf-8")
    started = time.time()
    record: dict = {"agent": "sdk" if agent == "sdk" else "cmd"}
    try:
        if agent == "sdk":
            record.update(asyncio.run(_run_sdk(ws, task, timeout)))
        else:
            env = dict(os.environ, WORKSPACE=str(ws), TASK_FILE=str(ws / "TASK.md"))
            with (ws / "logs/agent.log").open("w", encoding="utf-8") as log:
                proc = subprocess.run(agent_cmd, shell=True, cwd=ws, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=timeout)
            record["exit_code"] = proc.returncode
            if proc.returncode != 0:
                record["error"] = f"agent 命令退出码 {proc.returncode}，输出见 logs/agent.log"
    except (asyncio.TimeoutError, subprocess.TimeoutExpired):
        record["error"] = f"agent 超时（{timeout} 秒）"
    except Exception as exc:  # noqa: BLE001 - 任何 agent 异常都记成生词失败，不让流水线崩
        record["error"] = f"{type(exc).__name__}: {str(exc)[:2000]}"
    record["wall_secs"] = round(time.time() - started, 1)
    write_json(ws / "logs/agent-run.json", record)
    return record


def validator_readiness(stdout: str) -> str:
    """有错时 validator 打印 `READINESS: …` 一行；通过时只打印一段 JSON，readiness 在里面。"""
    for line in stdout.splitlines():
        if line.startswith("READINESS:"):
            return line.split(":", 1)[1].strip()
    for line in reversed(stdout.strip().splitlines()):
        try:
            return str(json.loads(line).get("readiness") or "")
        except (json.JSONDecodeError, AttributeError):
            continue
    return ""


def _tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def finalize(ws: Path, agent_record: dict | None = None) -> int:
    prior = json.loads((ws / "out/result.json").read_text(encoding="utf-8")) if (ws / "out/result.json").exists() else {}
    market, locale = prior.get("market", ""), prior.get("locale", "")
    result = {"status": "failed", "market": market, "locale": locale, "platforms": prior.get("platforms", []), "errors": [],
              "warnings": prior.get("warnings", [])}
    if agent_record and agent_record.get("error"):
        result["errors"].append({"stage": "agent", "message": agent_record["error"]})
    bank = ws / "out/bank.json"
    if not bank.exists():
        result["errors"].append({"stage": "agent", "message": "agent 没有写出 out/bank.json"})
        write_json(ws / "out/result.json", result)
        return 1
    tools = ws / ".agents/skills/geo-prompt-selection-builder/scripts"
    presales_tools = ws / ".agents/skills/geo-presales-prompt-builder/scripts"
    upload = ws / "out/upload"
    if upload.exists():
        shutil.rmtree(upload)  # 只认这一次导出的文件
    checks = {
        "validator": [sys.executable, "-I", str(tools / "validate_after_sales_set.py"), str(bank)],
        "presales_check": [sys.executable, "-I", str(presales_tools / "check_presales_bank.py"), str(bank)],
        "export": [sys.executable, "-I", str(tools / "export_upload_csv.py"), str(bank), "--out", str(upload)],
    }
    exits = {}
    for name, cmd in checks.items():
        proc = subprocess.run(cmd, capture_output=True, text=True)
        output = proc.stdout + proc.stderr
        (ws / f"logs/{name}.txt").write_text(output, encoding="utf-8")
        exits[name] = proc.returncode
        if name == "validator":
            result["validator_readiness"] = validator_readiness(proc.stdout)
        if proc.returncode != 0:
            result["errors"].append({"stage": name, "exit_code": proc.returncode, "output": _tail(output)})
    files = sorted(upload.glob("*.upload.csv")) if upload.exists() else []
    result["upload_files"] = [str(p.relative_to(ws)) for p in files]
    try:
        data = json.loads(bank.read_text(encoding="utf-8"))
        regions = sorted({str(q.get("region") or "").strip() for q in data.get("questions") or []})
    except (OSError, json.JSONDecodeError) as exc:
        result["errors"].append({"stage": "bank", "message": f"bank.json 读不了：{exc}"})
        regions = []
    if market and regions and regions != [market]:
        result["errors"].append({"stage": "market", "message": f"题库市场 {regions} 与传入的 --market {market!r} 不一致"})
    rows = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows += list(csv.DictReader(f))
    result["prompt_count"] = len(rows)
    result["topics"] = list(dict.fromkeys(r["topic"] for r in rows))
    if not result["errors"] and all(code == 0 for code in exits.values()) and files:
        result["status"] = "success"
    elif not files and not any(e["stage"] == "export" for e in result["errors"]):
        result["errors"].append({"stage": "export", "message": "没有导出任何文件"})
    write_json(ws / "out/result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "market", "prompt_count", "topics", "upload_files")},
                     ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "prepare"):
        p = sub.add_parser(name)
        p.add_argument("--case", type=Path, required=True, help="presales-case-input/v1 JSON（见 references/input-contract.md）")
        p.add_argument("--market", required=True, help="市场代码，与采集的 --regions 一致，如 US")
        p.add_argument("--platforms", required=True,
                       help="表单「AI 平台」选中的平台，逗号分隔，如 chatgpt,gemini；研究预跑只跑这些")
        p.add_argument("--out", type=Path, required=True, help="新的工作目录，不能已存在")
        p.add_argument("--task-file", type=Path, help="替换默认任务说明（只用于测试）")
        if name == "run":
            p.add_argument("--agent", choices=["sdk"], help="内置 Claude Agent SDK 适配")
            p.add_argument("--agent-cmd", help="宿主 harness 的命令，在工作目录里执行")
            p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="agent 时间上限（秒）")
    p = sub.add_parser("finalize")
    p.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ws = a.out.resolve()
    if a.cmd == "finalize":
        return finalize(ws)
    if a.cmd == "run" and bool(a.agent) == bool(a.agent_cmd):
        print("run 需要 --agent sdk 或 --agent-cmd 二选一", file=sys.stderr)
        return 2
    code = prepare(a.case.resolve(), a.market, a.platforms, ws, a.task_file.resolve() if a.task_file else None)
    if code != 0 or a.cmd == "prepare":
        if code != 0 and (ws / "out/result.json").exists():
            print((ws / "out/result.json").read_text(encoding="utf-8"))
        return code
    if not a.task_file and not scrapeless_key_present():
        # 没有 key 时 agent 采不了研究预跑，会凭空写题；在启动 agent 前就停下
        write_json(ws / "out/result.json", {"status": "env_error", "market": a.market.strip(),
                                             "errors": [{"code": "missing_env", "message": "缺少 SCRAPELESS_API_KEY"}]})
        print("缺少 SCRAPELESS_API_KEY，未启动 agent", file=sys.stderr)
        return 2
    record = run_agent(ws, a.agent, a.agent_cmd, a.timeout)
    return finalize(ws, record)


if __name__ == "__main__":
    sys.exit(main())
