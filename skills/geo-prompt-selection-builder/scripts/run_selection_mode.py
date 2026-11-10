#!/usr/bin/env python3
"""选词的线上一条命令入口：Case（表单数据或文件）→ 每个市场一批 9 字段的题（Suda 2026-10-29；
2026-11-06 随售前生词并入选词 skill）。

规则见 references/online-runner.md 和 references/selection-rules.md。本脚本把
确定性的部分包起来，中间的调研和写题交给 agent：

    prepare   归一化 Case，建独立工作目录（skill 拷贝、inputs/、TASK.md）
    agent     在工作目录里让 agent 按 TASK.md 调研、写 out/bank.json
    finalize  跑选词 validator 和导出脚本，写 out/result.json
    返修      run 里检查没过而 out/bank.json 存在时，把报错原文写成 REPAIR-<n>.md 回喂 agent 再
              finalize，默认最多 2 轮（--repair-rounds，0 关闭）；最后一轮授权 agent 丢题不丢库
              （改不好的题删掉、题号进 config.retired，每个主题仍只放一种意图类型）

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
Reddit 限量：agent 里的 net.py reddit 每个工作目录最多 NET_REDDIT_MAX 次联网请求（默认 10，约 10 分钟），
计数在 logs/reddit_calls；宿主可用同名环境变量改。
DataForSEO 按人记账：宿主把发起这次选词的同事姓名放进 DATAFORSEO_WHO；没传时记成「线上选词（未传调用人）」。
DATAFORSEO_CASE 没传时自动填「品牌 市场」。流水在服务端 ~/.dataforseo/ledger.jsonl（DATAFORSEO_LEDGER 可改），
用 shared/scripts/collect_keyword_data.py ledger 汇总。

产物（都在工作目录里）：
  out/bank.json        题库 JSON（内部底稿）
  out/upload/*.csv     交给线上的 9 字段题（每个市场一份）
  out/result.json      {status, market, locale, upload_files, prompt_count, topics, repair_rounds, costs, errors…}
                       costs 是本轮记账（3.1.0）：LLM usage 加总、Scrapeless 请求数、DataForSEO 流水，只记数量
                       不乘单价；按客户算钱用 shared/scripts/cost_report.py（单价读本机 ~/.geo-cost/prices.json）
  logs/                agent 记录（返修轮带 -repair<n> 后缀；agent-run*.json 含 SDK 的 usage）、两个检查与导出的原始输出
  logs/net_cache/      本轮 net.py 缓存（NET_CACHE_DIR），代理页数和搜索次数从这里数
  REPAIR-<n>.md        每轮返修回喂 agent 的任务（报错原文在里面）

退出码：0 生词成功；1 生词失败（agent 出错、超时，或返修轮次用完检查仍没过，原因见 result.json）；
2 输入或环境有错（Case 归一化不过、参数错、缺 SCRAPELESS_API_KEY），不启动 agent，errors 原样在 result.json。

可能出错的地方（本脚本针对的就是这些）：
  1. Case 缺必填字段 → prepare 停下，不启动 agent，errors 原样交回
  2. agent 没写出 bank.json、超时或异常退出 → 没有 bank.json 就失败，不返修、不拿半成品导出
  3. 题库没过选词 validator（含主题都有题、一个主题一种类型）或导出检查（超 60 条、字段缺、类型不对） → 回喂报错返修（最多 --repair-rounds 轮），仍没过才失败，报错原文进 result.json
  4. 题库的市场和传入的 --market 不一致 → 同样走返修（agent 改 region），仍不一致才失败
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
# 整个拷贝的 skill：选词本身、shared 的联网与信号脚本。
# geo-monitoring 不拷（3.0.0）：选词文档里指向它的链接是锁版阶段规则，线上不读。
SKILL_DIRS = ("geo-prompt-selection-builder", "shared")
# 只拷一部分的 skill（3.0.0）：研究预跑只用 geo-presales-report-builder/scripts/collect_answers.py，
# 它在导入时还要 geo-presales-report-editor 的 geo_presales_core 包和 geo-presales-crawl-integrity 的
# audit_crawl_integrity.py（后者读同 skill 的 references/platform-contract.json 覆盖平台合同）。
# 这是让 collect_answers.py 能在工作目录里跑起来的最小集合。
PARTIAL_COPIES = (
    ("geo-presales-report-builder", "scripts"),
    ("geo-presales-report-editor", "scripts/geo_presales_core"),
    ("geo-presales-crawl-integrity", "scripts/audit_crawl_integrity.py"),
    ("geo-presales-crawl-integrity", "references/platform-contract.json"),
)
# legacy = 已归档的旧规则，不给 agent 看，免得混用两套口径
# client-facing-base.md = 只用来建对客确认表，线上不写这张表，不拷贝（省 ~31KB 上下文）
# demand-side-signals.md = signal-sources.md 里「客户提供什么」等品牌方数据小节，线上没有客户数据
IGNORE = shutil.ignore_patterns(".snapshots", "__pycache__", ".pytest_cache", "*.bak", "evals", "reports",
                                "*.local.json", "build", "legacy",
                                "client-facing-base.md", "demand-side-signals.md",
                                # lark-cli 在 skill 目录里落下的 Base 导出（客户数据），线上不需要
                                "tbl*.ndjson", "tbl*.manifest.json", "tpl_*.manifest.json")
DEFAULT_TIMEOUT = 120 * 60
# 与 geo-presales-report-builder/scripts/collect_answers.py 的 ALL_PLATFORMS 一致
KNOWN_PLATFORMS = {"chatgpt", "perplexity", "copilot", "gemini", "aimode", "overview", "grok", "alexa"}

TASK = """你在一个无人值守的流水线里，没有人会回答问题。遇到歧义按最合理的判断继续，把假设写进 `out/notes.md`。

任务：给这个品牌生成一批提示词。先读 `.agents/skills/geo-prompt-selection-builder/references/online-runner.md`（线上和本地不一样的地方），再按 `.agents/skills/geo-prompt-selection-builder/references/selection-rules.md` 第 1–8 步逐步做。只做到校验与导出，不试跑、不写对客确认表。

线上跳过不读：
- 文档里指向 `geo-monitoring` 的链接是锁版阶段规则（试跑、挑正式题、锁版、基线），线上不读，工作目录里也没有这个 skill。
- selection-rules.md 里这三类小节线上跳过：对客 Base 写法（第 8 步「写进对客表后回读行数」、「交付」里的对客确认表，以及所有指向 client-facing-base.md 的说明）；品牌方资料流程（第 1 步「品牌方先给，我们核对」「只要会改变选词判断的数据」，第 2 步「GSC 和搜索词报告分开用」）；售前主题重聚对账（第 6 步「报价与交付的先后」「品牌方售前点名的主题不重聚」）。

题量硬限（超了导出脚本直接报错、要返修）：
- 候选题一个市场 30–60 道（validator 对超出只告警，但导出对超 60 报错）；每个导出文件（市场 × 产品线）最多 60 条。写到 60 道就停，超出先砍业务优先级为中的行里证据最弱的题。

输入：
- `inputs/case-normalized.json`：归一化后的品牌信息（Case）。竞品用 Case 里客户填的，不自己增删。主题一律由你从矩阵行聚出，个数不限。品类名从「本期产品线」和官网推出，写进 `config.category_label`。
- 题型：只出发现题。Case 的「核心目标客户与购买场景」按业务优先级排先后，只当业务优先级的线索。
- 市场：`{market}`；语言：`{locale}`。所有题的 `region` 写 `{market}`，`config.collection_config` 写 `{{"market": "{market}", "language": "{locale}"}}`。

需求信号（必填）：
- 调研收到的买家原话（评价、社区）、搜索词和 AI 检索词里，**只登记撑起某道题的那几条**，写进 `config.buyer_quotes`，一条一个对象：`{{"输入编号": "<市场前缀>-R001", "原话": "<买家原话原文，不要翻译>", "目标客户": "<谁在问，看不出留空>", "约束条件": "<这条信号能证明题面哪些条件，关键词写法>"}}`。
- 约束那一列的键名就是 `约束条件`，和对客 Base 列名、`signals.csv` 一致。
- 题的 `evidence_refs` 填它引用的信号编号（如 `["US-R003"]`），不要填别的题的题号。题面带条件却挂不上任何原话时，在 `condition_basis` 里写 `{{"<条件>": "<依据>"}}`，不许留空。
- 一条原话可以撑多道题；撑不上的原话不要登记。没有条件、也没有标题面的题可以不引用。
- 线上没有品牌方提供的资料（销售、客服、GSC、关键词工具），只收公开层（评价、社区、搜索联想）。

联网：
- 不用 WebSearch / WebFetch。搜索和取网页用 `.agents/skills/shared/scripts/net.py`，取网页一律 `net.py fetch <url> [<url> ...] --country {market}`，要读的页面攒成一批一次传（脚本并发取），被拦的页面不要再试 `render`；Reddit 本次最多 {reddit_max} 次联网请求（`net.py reddit` 到上限会提示），先挑最相关的版块和帖子，读不到的记进未覆盖来源；搜索信号、关键词数据、评价用同目录的 `collect_serp_signals.py`、`collect_keyword_data.py`、`collect_reviews.py`。
- 研究预跑只在客户选的平台上跑：`python3 .agents/skills/geo-presales-report-builder/scripts/collect_answers.py --questions research/prerun.csv --out research/prerun --regions {market} --platforms {platforms}`。不要加别的平台。
- 没有带登录态的浏览器。要登录或通道表里标「不通」的站跳过，按 online-runner.md「线上没有浏览器」一节处理，写进 notes.md 的「未覆盖来源」。
- 调研过程文件都放 `research/`。只在本工作目录里读写，不要访问工作目录以外的路径。

交付（只写这两个路径）：
1. `out/bank.json`：题库 JSON，字段按 `.agents/skills/geo-prompt-selection-builder/references/output-contract.md` 和 online-runner.md。
2. `out/notes.md`：简短记录，分这几节：「预跑答案」（研究预跑的答案目录和每个平台是否采到）、「目标客户」、「使用场景候选」（每个场景推理的解决方案类型、品牌能否满足、回答里会不会出现品牌这一类）、「约束条件」、「需求信号」（`config.buyer_quotes` 登记了几条、各是什么来源类型、哪些题引用了它们、哪些题的条件只靠 `condition_basis`）、「没开的格子」（矩阵里没开的格子和原因）、「主题」（每个主题为什么成立）、「假设」、「未覆盖来源」、「validator 告警」。

结束前依次运行，两条都要退出码 0；有错就改题库再跑：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""

REPAIR_TASK = """你在无人值守流水线的返修环节（第 {round} / {max_rounds} 轮）。工作目录里已有 out/bank.json，但结束检查没过。

只做返修：按下面的报错改 `out/bank.json`（需要时更新 `out/notes.md`），不要重做调研（research/ 里已有材料），不要访问工作目录以外的路径。
{drop_clause}
报错原文：

{errors}

改完后依次运行，两条都要退出码 0；有错就继续改：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""

DROP_CLAUSE = """这是最后一轮返修，丢题不丢库：报错指向的题能改就改，改不好的直接删掉，不要为凑数新写题。删掉的题号和原因记进 `config.retired`，并写进 `out/notes.md`「删题」一节；空了的主题连主题登记一起删，删题后每个主题仍只放一种意图类型。宁可少交几道题，不要交整库失败。
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
    for sub in ("inputs", "research", "out", "logs", "logs/net_cache"):
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
    for name, rel in PARTIAL_COPIES:
        src = SKILLS / name / rel
        dst = ws / ".agents/skills" / name / rel
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True, ignore=IGNORE)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    task = task_file.read_text(encoding="utf-8") if task_file else TASK.format(market=market, locale=locale, platforms=",".join(names),
                                                                                  reddit_max=os.environ.get("NET_REDDIT_MAX", "10"))
    (ws / "TASK.md").write_text(task, encoding="utf-8")
    write_json(ws / "out/result.json", {"status": "prepared", "market": market, "locale": locale,
                                         "platforms": names, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                         "warnings": result["warnings"]})
    return 0


def net_env(ws: Path) -> dict:
    """net.py 的线上限量：Reddit RSS 约每分钟 1 次，是线上调研最慢的一环，默认每个工作目录最多 10 次联网请求。
    缓存目录按工作目录隔离（3.1.0），代理页数和搜索次数才能按轮归集；代价是不同 Case 之间不共享网页缓存。"""
    return {"NET_REDDIT_MAX": os.environ.get("NET_REDDIT_MAX", "10"),
            "NET_REDDIT_COUNTER": str(ws / "logs/reddit_calls"),
            "NET_CACHE_DIR": str(ws / "logs/net_cache")}


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _usage(raw) -> dict:
    """ResultMessage.usage 可能是 dict 也可能是对象；只取四个计费字段，缺的记 0。"""
    get = raw.get if isinstance(raw, dict) else (lambda k, d=None: getattr(raw, k, d))
    return {k: int(get(k, 0) or 0) for k in USAGE_KEYS}


async def _run_sdk(ws: Path, task: str, timeout: int, tag: str = "") -> dict:
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
           "CLAUDE_CONFIG_DIR": str(home), **net_env(ws)}
    opts = ClaudeAgentOptions(cwd=str(ws), model=model, env=env, permission_mode="bypassPermissions",
                              disallowed_tools=["WebSearch", "WebFetch"], setting_sources=["project"],
                              max_turns=600)
    record: dict = {"tool_calls": 0}
    with (ws / f"logs/agent{tag}.jsonl").open("w", encoding="utf-8") as log:
        async def consume():
            async for m in query(prompt=task, options=opts):
                if isinstance(m, AssistantMessage):
                    record["tool_calls"] += sum(1 for b in m.content if type(b).__name__ == "ToolUseBlock")
                if isinstance(m, ResultMessage):
                    record.update(finish=getattr(m, "subtype", None), turns=getattr(m, "num_turns", None),
                                  final=getattr(m, "result", None), model=model,
                                  duration_ms=getattr(m, "duration_ms", None),
                                  duration_api_ms=getattr(m, "duration_api_ms", None),
                                  # SDK 按 Anthropic 模型价算的；网关后面是别家模型（如 DeepSeek）时不可信，
                                  # 算钱用 usage × 网关单价（cost_report.py），这个数只原样留存
                                  total_cost_usd_anthropic_price_unreliable=getattr(m, "total_cost_usd", None))
                    if getattr(m, "usage", None) is not None:
                        record["usage"] = _usage(m.usage)
                log.write(json.dumps({"type": type(m).__name__, "repr": repr(m)[:2000]}, ensure_ascii=False) + "\n")
        await asyncio.wait_for(consume(), timeout)
    return record


def run_agent(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int,
              task_path: Path | None = None, tag: str = "") -> dict:
    task_path = task_path or ws / "TASK.md"
    task = task_path.read_text(encoding="utf-8")
    started = time.time()
    record: dict = {"agent": "sdk" if agent == "sdk" else "cmd", "task_file": task_path.name,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        if agent == "sdk":
            record.update(asyncio.run(_run_sdk(ws, task, timeout, tag)))
        else:
            env = dict(os.environ, WORKSPACE=str(ws), TASK_FILE=str(task_path), **net_env(ws))
            with (ws / f"logs/agent{tag}.log").open("w", encoding="utf-8") as log:
                proc = subprocess.run(agent_cmd, shell=True, cwd=ws, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=timeout)
            record["exit_code"] = proc.returncode
            if proc.returncode != 0:
                record["error"] = f"agent 命令退出码 {proc.returncode}，输出见 logs/agent{tag}.log"
    except (asyncio.TimeoutError, subprocess.TimeoutExpired):
        record["error"] = f"agent 超时（{timeout} 秒）"
    except Exception as exc:  # noqa: BLE001 - 任何 agent 异常都记成生词失败，不让流水线崩
        record["error"] = f"{type(exc).__name__}: {str(exc)[:2000]}"
    record["wall_secs"] = round(time.time() - started, 1)
    write_json(ws / f"logs/agent-run{tag}.json", record)
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


def finalize(ws: Path, agent_record: dict | None = None, repair_rounds: int | None = None) -> int:
    prior = json.loads((ws / "out/result.json").read_text(encoding="utf-8")) if (ws / "out/result.json").exists() else {}
    market, locale = prior.get("market", ""), prior.get("locale", "")
    result = {"status": "failed", "market": market, "locale": locale, "platforms": prior.get("platforms", []), "errors": [],
              "warnings": prior.get("warnings", []), "prepared_at": prior.get("prepared_at", "")}
    result["costs"] = collect_costs(ws, market, result["prepared_at"])
    if repair_rounds is not None:
        result["repair_rounds"] = repair_rounds
    if agent_record and agent_record.get("error"):
        result["errors"].append({"stage": "agent", "message": agent_record["error"]})
    bank = ws / "out/bank.json"
    if not bank.exists():
        result["errors"].append({"stage": "agent", "message": "agent 没有写出 out/bank.json"})
        write_json(ws / "out/result.json", result)
        return 1
    tools = ws / ".agents/skills/geo-prompt-selection-builder/scripts"
    upload = ws / "out/upload"
    if upload.exists():
        shutil.rmtree(upload)  # 只认这一次导出的文件
    checks = {
        "validator": [sys.executable, "-I", str(tools / "validate_after_sales_set.py"), str(bank)],
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


def _ledger_path() -> Path:
    """和 shared/scripts/collect_keyword_data.py 的 ledger_path 同一规则。"""
    return Path(os.environ.get("DATAFORSEO_LEDGER", "").strip() or Path.home() / ".dataforseo" / "ledger.jsonl")


def dataforseo_case(ws: Path, market: str) -> str:
    """run 给 agent 设的 DATAFORSEO_CASE；没设时同样按「品牌 市场」推。"""
    case = os.environ.get("DATAFORSEO_CASE", "").strip()
    if case:
        return case
    try:
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        brand = ""
    return f"{brand} {market}".strip()


def collect_costs(ws: Path, market: str, since: str) -> dict:
    """本轮记账：只记数量和 usage，不乘单价（单价在 cost_report.py 读本机配置）。

    每次 finalize 都从工作目录重新数一遍，所以返修轮之后的结果包含主跑和全部返修。
    """
    try:
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        brand = ""
    until = time.strftime("%Y-%m-%dT%H:%M:%S")
    # LLM：主跑 logs/agent-run.json，返修 logs/agent-run-repair<n>.json
    llm = {"runs": 0, "runs_with_usage": 0, "turns": 0, "duration_ms": 0, "model": "",
           **{k: 0 for k in USAGE_KEYS}, "total_cost_usd_anthropic_price_unreliable": 0.0, "files": []}
    starts: list[str] = []
    for path in sorted((ws / "logs").glob("agent-run*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        llm["runs"] += 1
        llm["files"].append(path.name)
        if rec.get("started_at"):
            starts.append(rec["started_at"])
        llm["turns"] += int(rec.get("turns") or 0)
        llm["duration_ms"] += int(rec.get("duration_ms") or 0)
        llm["model"] = llm["model"] or rec.get("model") or ""
        llm["total_cost_usd_anthropic_price_unreliable"] += float(rec.get("total_cost_usd_anthropic_price_unreliable") or 0)
        if isinstance(rec.get("usage"), dict):
            llm["runs_with_usage"] += 1
            for k in USAGE_KEYS:
                llm[k] += int(rec["usage"].get(k) or 0)
    if not since and starts:  # 3.1.0 之前 prepare 的目录没有 prepared_at，用最早一次 agent 启动时间
        since = min(starts)
    llm["total_cost_usd_anthropic_price_unreliable"] = round(llm["total_cost_usd_anthropic_price_unreliable"], 6)
    # Scrapeless：预跑尝试（失败重试也算一次）、SERP 原始返回、本轮 net.py 缓存里的代理页和搜索
    prerun = {"attempts": 0, "ok": 0, "files": []}
    for ev in sorted((ws / "research").glob("**/_collector/events.jsonl")):
        prerun["files"].append(str(ev.relative_to(ws)))
        for line in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "attempt":
                prerun["attempts"] += 1
                prerun["ok"] += 1 if e.get("ok") else 0
    serp = sum(1 for _ in (ws / "research").glob("**/serp*/raw/*.json"))
    cache = ws / "logs/net_cache"
    proxy = search = 0
    if cache.is_dir():
        for f in cache.glob("fetch_*.json"):
            try:
                proxy += 1 if "Scrapeless" in json.loads(f.read_text(encoding="utf-8")).get("src", "") else 0
            except (OSError, json.JSONDecodeError):
                continue
        search = sum(1 for f in cache.glob("*.json") if len(f.stem) == 32 and all(c in "0123456789abcdef" for c in f.stem))
    scrapeless = {"prerun_attempts": prerun["attempts"], "prerun_ok": prerun["ok"], "prerun_event_files": prerun["files"],
                  "serp_requests": serp, "net_search_requests": search, "proxy_pages": proxy,
                  "note": "proxy_pages 只数成功并写进缓存的代理页（Scrapeless 网页代理按成功请求计费）；"
                          "logs/net_cache 不在时记「不可归集」"}
    if not cache.is_dir():
        scrapeless["proxy_pages"] = scrapeless["net_search_requests"] = "不可归集"
    # DataForSEO：服务端流水按 case 与本轮时间窗过滤，不含沙盒
    case = dataforseo_case(ws, market)
    dfs = {"case": case, "since": since, "until": until, "calls": 0, "cost_usd": 0.0, "ledger": str(_ledger_path())}
    try:
        lines = _ledger_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
        dfs["note"] = "流水文件不存在"
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = str(e.get("time", ""))
        if e.get("sandbox") or (e.get("case") or "").strip() != case or (since and t < since) or t > until:
            continue
        dfs["calls"] += 1
        dfs["cost_usd"] += float(e.get("cost_usd") or 0)
    dfs["cost_usd"] = round(dfs["cost_usd"], 6)
    return {"brand": brand, "market": market, "since": since, "until": until,
            "llm": llm, "scrapeless_requests": scrapeless, "dataforseo": dfs}


def repair_task(ws: Path, round_no: int, max_rounds: int) -> Path:
    """把上一轮 result.json 的报错写成返修任务，返回任务文件路径。"""
    result = json.loads((ws / "out/result.json").read_text(encoding="utf-8"))
    errors = "\n\n".join(f"[{e.get('stage', '?')}] {e.get('output') or e.get('message', '')}".strip()
                         for e in result.get("errors", []))
    drop = DROP_CLAUSE if round_no >= max_rounds else ""
    path = ws / f"REPAIR-{round_no}.md"
    path.write_text(REPAIR_TASK.format(round=round_no, max_rounds=max_rounds, drop_clause=drop, errors=errors),
                    encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "prepare"):
        p = sub.add_parser(name)
        p.add_argument("--case", type=Path, required=True, help="presales-case-input/v2 JSON（见 references/input-contract.md）")
        p.add_argument("--market", required=True, help="市场代码，与采集的 --regions 一致，如 US")
        p.add_argument("--platforms", required=True,
                       help="表单「AI 平台」选中的平台，逗号分隔，如 chatgpt,gemini；研究预跑只跑这些")
        p.add_argument("--out", type=Path, required=True, help="新的工作目录，不能已存在")
        p.add_argument("--task-file", type=Path, help="替换默认任务说明（只用于测试）")
        if name == "run":
            p.add_argument("--agent", choices=["sdk"], help="内置 Claude Agent SDK 适配")
            p.add_argument("--agent-cmd", help="宿主 harness 的命令，在工作目录里执行")
            p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="agent 时间上限（秒），每轮返修同额")
            p.add_argument("--repair-rounds", type=int, default=2,
                           help="检查没过时回喂报错返修的最大轮数（默认 2，0 关闭；最后一轮授权丢题不丢库）")
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
    # DataForSEO 脚本没有调用人就不发调用；线上没传时给一个可见的占位，不让调研静默缺数据
    os.environ.setdefault("DATAFORSEO_WHO", "线上选词（未传调用人）")
    if not os.environ.get("DATAFORSEO_CASE", "").strip():
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
        os.environ["DATAFORSEO_CASE"] = f"{brand} {a.market.strip()}".strip()
    record = run_agent(ws, a.agent, a.agent_cmd, a.timeout)
    code = finalize(ws, record, repair_rounds=0)
    rounds = 0
    while code != 0 and rounds < max(a.repair_rounds, 0) and (ws / "out/bank.json").exists():
        rounds += 1
        task_path = repair_task(ws, rounds, a.repair_rounds)
        record = run_agent(ws, a.agent, a.agent_cmd, a.timeout, task_path=task_path, tag=f"-repair{rounds}")
        code = finalize(ws, record, repair_rounds=rounds)
    return code


if __name__ == "__main__":
    sys.exit(main())
