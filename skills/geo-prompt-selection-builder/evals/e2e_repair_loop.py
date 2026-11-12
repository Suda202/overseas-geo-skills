#!/usr/bin/env python3
"""返修循环端到端校验（2026-11-05）。

用假 agent（--agent-cmd）走 run_selection_mode.py 的 run 子命令，验证线上一次性生词的
返修与保底行为（Suda 2026-11-05：门禁不放松，最终得能生词）：

  1. 修好：首轮题库违规（发现题带品牌名，validator 门禁 12），返修第 1 轮修好
     → success，repair_rounds=1，REPAIR-1.md 存在、没有第 2 轮
  2. 丢题保底：返修第 1 轮仍坏，第 2 轮按丢题授权删掉违规题（记 config.retired）
     → success，repair_rounds=2，题数回到夹具原量
  3. 关闭返修：--repair-rounds 0 → failed，报错指向 validator，不生成 REPAIR-1.md
  4. agent 没写出 bank.json → failed，不返修
  5. 补题（3.13.0）：通过检查但不到 30 道 → 写 TOPUP.md 补一轮；补了题 → top_up.status=added；
     补坏了（发现题带品牌名）→ 退回补题前的题库，top_up.status=reverted，照常 success；--repair-rounds 0 不补

产物：reports/repair-loop-e2e.md；工作目录建在系统临时目录，跑完删除。

    python3 evals/e2e_repair_loop.py
退出码 0 表示全部符合预期。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RUNNER = SKILL / "scripts" / "run_selection_mode.py"
FIXTURE = SKILL / "evals" / "fixtures" / "online-sample-bank.json"
CASE = SKILL / "references" / "input-examples" / "b2c-example.json"
FIXTURE_COUNT = len(json.loads(FIXTURE.read_text(encoding="utf-8"))["questions"])

FAKE_AGENT = '''
import json, os
from pathlib import Path

ws = Path(os.environ["WORKSPACE"])
task = Path(os.environ["TASK_FILE"]).name
mode = os.environ["FAKE_MODE"]
bank = json.loads(Path(os.environ["FIXTURE"]).read_text(encoding="utf-8"))
base_qs = list(bank["questions"])


def clone(bad: bool) -> dict:
    q = json.loads(json.dumps(next(x for x in base_qs if x["question_id"] == "US-001")))
    q["question_id"] = "US-902"
    text = ("Which BrandX robot vacuums are best for pet hair?" if bad
            else "Which robot vacuums pick up long dog hair from rugs?")
    q["user_question"] = q["monitoring_prompt"] = text
    q["zh_translation"] = "坏题：发现题带品牌名" if bad else "哪些扫地机器人能吸起地毯上的长狗毛？"
    return q


def write(questions: list) -> None:
    bank["questions"] = questions
    if "expected_total" in bank["config"]:
        bank["config"]["expected_total"] = len(questions)
    (ws / "out/bank.json").write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")


if task == "TOPUP.md":
    topup = os.environ.get("TOPUP_MODE", "none")
    current = json.loads((ws / "out/bank.json").read_text(encoding="utf-8"))
    bank = current
    if topup == "add":
        extra = clone(bad=False)
        extra["question_id"] = "US-903"
        extra["user_question"] = extra["monitoring_prompt"] = "Which robot vacuums keep cat litter from spreading on hard floors?"
        extra["zh_translation"] = "哪些扫地机器人能清理硬地板上散落的猫砂？"
        write(current["questions"] + [extra])
    elif topup == "break":
        write(current["questions"] + [clone(bad=True)])
elif mode == "none":
    pass  # 不写 bank.json
elif task == "TASK.md":
    write(base_qs + [clone(bad=mode != "good")])  # 首轮：带一道坏题（good 模式首轮就合格）
elif mode == "fix":
    write(base_qs + [clone(bad=False)])  # 返修第 1 轮：改好坏题
elif mode == "drop":
    if task == "REPAIR-1.md":
        write(base_qs + [clone(bad=True)])  # 第 1 轮：改不动
    else:  # 第 2 轮：按丢题授权删掉坏题
        bank["config"]["retired"] = list(bank["config"].get("retired") or []) + [
            {"question_id": "US-902", "reason": "返修改不好，按丢题授权删除"}]
        write(base_qs)
'''

rows: list[tuple[str, bool, str]] = []
WS_ROOT = Path(tempfile.mkdtemp(prefix="repair-loop-"))
fake = WS_ROOT / "fake_agent.py"
fake.write_text(FAKE_AGENT, encoding="utf-8")
dummy_task = WS_ROOT / "dummy-task.md"
dummy_task.write_text("测试任务：由假 agent 执行，内容不读。\n", encoding="utf-8")


def run_case(name: str, mode: str, repair_rounds: int = 2, topup: str = "none") -> tuple[int, dict, Path]:
    ws = WS_ROOT / f"ws-{name}"
    env = dict(os.environ, FAKE_MODE=mode, FIXTURE=str(FIXTURE), TOPUP_MODE=topup)
    cmd = [sys.executable, "-I", str(RUNNER), "run", "--case", str(CASE), "--market", "US",
           "--platforms", "chatgpt", "--out", str(ws), "--task-file", str(dummy_task),
           "--repair-rounds", str(repair_rounds),
           "--agent-cmd", f'"{sys.executable}" -I "{fake}"']
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    result_path = ws / "out/result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    return proc.returncode, result, ws


def check(name: str, ok: bool, detail: str) -> None:
    rows.append((name, ok, detail))


# 1. 修好路径
rc, res, ws = run_case("fix", "fix")
check("修好：返修第 1 轮通过 → success",
      rc == 0 and res.get("status") == "success" and res.get("repair_rounds") == 1
      and res.get("prompt_count") == FIXTURE_COUNT + 1
      and (ws / "REPAIR-1.md").exists() and not (ws / "REPAIR-2.md").exists(),
      f"exit={rc} status={res.get('status')} rounds={res.get('repair_rounds')} count={res.get('prompt_count')}")
check("修好：REPAIR-1.md 带报错原文和检查命令",
      "[validator]" in (ws / "REPAIR-1.md").read_text(encoding="utf-8")
      and "validate_after_sales_set.py" in (ws / "REPAIR-1.md").read_text(encoding="utf-8"), "")

# 2. 丢题保底路径
rc, res, ws = run_case("drop", "drop")
bank = json.loads((ws / "out/bank.json").read_text(encoding="utf-8"))
retired = [r.get("question_id") for r in bank["config"].get("retired") or []]
check("丢题保底：第 2 轮删坏题 → success，retired 记了题号",
      rc == 0 and res.get("status") == "success" and res.get("repair_rounds") == 2
      and res.get("prompt_count") == FIXTURE_COUNT and "US-902" in retired,
      f"exit={rc} status={res.get('status')} rounds={res.get('repair_rounds')} count={res.get('prompt_count')} retired={retired}")
check("丢题保底：最后一轮任务里有丢题授权",
      "丢题不丢库" in (ws / "REPAIR-2.md").read_text(encoding="utf-8")
      and "丢题不丢库" not in (ws / "REPAIR-1.md").read_text(encoding="utf-8"),
      "最后一轮才授权丢题")

# 3. 关闭返修（旧行为回归）
rc, res, ws = run_case("rounds0", "fix", repair_rounds=0)
stages = [e.get("stage") for e in res.get("errors", [])]
check("关闭返修：--repair-rounds 0 → failed，不返修",
      rc == 1 and res.get("status") == "failed" and "validator" in stages
      and not (ws / "REPAIR-1.md").exists(),
      f"exit={rc} status={res.get('status')} stages={stages}")

# 4. agent 没写 bank.json：不返修
rc, res, ws = run_case("none", "none")
check("没有 bank.json：failed，不返修",
      rc == 1 and res.get("status") == "failed" and not (ws / "REPAIR-1.md").exists()
      and any("bank.json" in (e.get("message") or "") for e in res.get("errors", [])),
      f"exit={rc} status={res.get('status')} errors={[e.get('message') for e in res.get('errors', [])]}")

# 5. 补题（夹具只有 5 道，通过检查后都会进补题轮）
rc, res, ws = run_case("topup-add", "fix", topup="add")
top = res.get("top_up") or {}
check("补题：不到 30 道补一轮，补了题 → added",
      rc == 0 and res.get("status") == "success" and (ws / "TOPUP.md").exists()
      and top.get("status") == "added" and top.get("after") == top.get("before", 0) + 1
      and any("[top_up]" in w for w in res.get("warnings", [])),
      f"exit={rc} status={res.get('status')} top_up={top}")
check("补题：TOPUP.md 写了补题顺序和不许凑数",
      "假设" in (ws / "TOPUP.md").read_text(encoding="utf-8")
      and "同义改写" in (ws / "TOPUP.md").read_text(encoding="utf-8"), "")
rc, res, ws = run_case("topup-break", "fix", topup="break")
top = res.get("top_up") or {}
bank = json.loads((ws / "out/bank.json").read_text(encoding="utf-8"))
check("补题：补坏了退回原题库 → reverted，照常 success",
      rc == 0 and res.get("status") == "success" and top.get("status") == "reverted"
      and top.get("after") == top.get("before") and len(bank["questions"]) == FIXTURE_COUNT + 1,
      f"exit={rc} status={res.get('status')} top_up={top} questions={len(bank['questions'])}")
rc, res, ws = run_case("topup-off", "good", repair_rounds=0)
check("补题：--repair-rounds 0 不补，首轮合格照常 success",
      rc == 0 and res.get("status") == "success" and not (ws / "TOPUP.md").exists() and "top_up" not in res,
      f"exit={rc} top_up={res.get('top_up')}")

# 6. 文档与默认值
runner_text = RUNNER.read_text(encoding="utf-8")
check("runner 文档写了返修与丢题授权", "--repair-rounds" in runner_text and "丢题不丢库" in runner_text, "")

passed = sum(1 for _, ok, _ in rows if ok)
lines = ["# 返修循环端到端校验", "", f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
         "- 命令：`python3 evals/e2e_repair_loop.py`", f"- 结果：{passed}/{len(rows)} 通过", "",
         "| 检查 | 结果 | 说明 |", "|---|---|---|"]
lines += [f"| {n} | {'通过' if ok else '失败'} | {d.replace('|', '/')} |" for n, ok, d in rows]
(SKILL / "reports").mkdir(exist_ok=True)
(SKILL / "reports" / "repair-loop-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
shutil.rmtree(WS_ROOT, ignore_errors=True)
sys.exit(0 if passed == len(rows) else 1)
