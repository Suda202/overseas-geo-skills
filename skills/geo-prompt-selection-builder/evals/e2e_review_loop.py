#!/usr/bin/env python3
"""审核环端到端校验（3.2.0，2026-11-10）。

用假 agent（--agent-cmd）走 run_selection_mode.py 的 run 子命令。假 agent 按 TASK_FILE 的文件名
决定做什么：TASK.md 写题库，REVIEW*.md 写 out/review.json，REVIEW-REPAIR-<n>.md 改题库。验证：

  1. 审核无发现 → success，review.status=passed，rounds=1，没有审核返修
  2. 审核有阻塞 → REVIEW-REPAIR-1.md（[review] 报错、非阻塞意见搭车进 notes.md「评审意见」）
     → 返修 → finalize → REVIEW-2.md 只复核报过的题号 → 通过 → success，status=repaired
  3. review.json 坏掉（不是 JSON）且审核 agent 违规改了 bank.json → success，status=review_failed，
     warning 两条，题库恢复成审核前
  4. review.json 结构不对（对象不是数组） → success，status=review_failed
  5. --review-rounds 0 → success，status=skipped，不生成 REVIEW.md
  6. 复核仍有阻塞、额度用完 → 退出码 1，status=failed，review.status=review_failed
  7. 审核 agent 超时 → success，status=review_failed

产物：reports/review-loop-e2e.md；工作目录建在系统临时目录，跑完删除。

    python3 evals/e2e_review_loop.py
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
import json, os, time
from pathlib import Path

ws = Path(os.environ["WORKSPACE"])
task_path = Path(os.environ["TASK_FILE"])
task = task_path.name
mode = os.environ["FAKE_MODE"]
bank_path = ws / "out/bank.json"
fixture = json.loads(Path(os.environ["FIXTURE"]).read_text(encoding="utf-8"))
BLOCK = {"question_id": "US-902", "check": 4, "problem": "题面把品牌卖点写成前提", "suggestion": "去掉卖点前提", "blocking": True}
NOTE = {"question_id": "US-003", "check": 5, "problem": "措辞略像关键词堆砌", "suggestion": "改成口语问法", "blocking": False}


def write_bank(extra_text):
    bank = json.loads(json.dumps(fixture))
    q = json.loads(json.dumps(next(x for x in bank["questions"] if x["question_id"] == "US-001")))
    q["question_id"] = "US-902"
    q["user_question"] = q["monitoring_prompt"] = extra_text
    q["zh_translation"] = "哪些扫地机器人能吸起地毯上的长狗毛？"
    bank["questions"].append(q)
    if "expected_total" in bank["config"]:
        bank["config"]["expected_total"] = len(bank["questions"])
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")


def review(data):
    out = ws / "out/review.json"
    out.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")


if task == "TASK.md":
    write_bank("Which robot vacuums pick up long dog hair from rugs?")
elif task.startswith("REVIEW-REPAIR-"):
    write_bank("Which robot vacuums handle long dog hair on thick rugs?")
    text = task_path.read_text(encoding="utf-8")
    if "评审意见" in text:
        with (ws / "out/notes.md").open("a", encoding="utf-8") as f:
            f.write("\\n## 评审意见\\n\\n- US-003 第 5 条：措辞略像关键词堆砌\\n")
elif task.startswith("REVIEW"):
    if mode == "clean":
        review([])
    elif mode == "blocking":
        review([BLOCK, NOTE] if task == "REVIEW.md" else [])
    elif mode == "stuck":
        review([BLOCK])
    elif mode == "broken":
        bank_path.write_text("{}", encoding="utf-8")  # 违规改题库，runner 应恢复
        review("not json {")
    elif mode == "shape":
        review({"question_id": "US-001", "blocking": True})
    elif mode == "timeout":
        time.sleep(30)
'''

rows: list[tuple[str, bool, str]] = []
WS_ROOT = Path(tempfile.mkdtemp(prefix="review-loop-"))
fake = WS_ROOT / "fake_agent.py"
fake.write_text(FAKE_AGENT, encoding="utf-8")
dummy_task = WS_ROOT / "dummy-task.md"
dummy_task.write_text("测试任务：由假 agent 执行，内容不读。\n", encoding="utf-8")


def run_case(name: str, mode: str, review_rounds: int = 1, timeout: int = 120) -> tuple[int, dict, Path]:
    ws = WS_ROOT / f"ws-{name}"
    env = dict(os.environ, FAKE_MODE=mode, FIXTURE=str(FIXTURE))
    cmd = [sys.executable, "-I", str(RUNNER), "run", "--case", str(CASE), "--market", "US",
           "--platforms", "chatgpt", "--out", str(ws), "--task-file", str(dummy_task),
           "--review-rounds", str(review_rounds), "--timeout", str(timeout),
           "--agent-cmd", f'"{sys.executable}" -I "{fake}"']
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    result_path = ws / "out/result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    return proc.returncode, result, ws


def check(name: str, ok: bool, detail: str) -> None:
    rows.append((name, ok, detail))


def brief(rc: int, res: dict) -> str:
    rv = res.get("review") or {}
    return (f"exit={rc} status={res.get('status')} count={res.get('prompt_count')} review.status={rv.get('status')} "
            f"rounds={rv.get('rounds')} blocking={rv.get('blocking_found')} nonblocking={rv.get('nonblocking_found')} "
            f"warnings={len(rv.get('warnings') or [])}")


# 1. 审核无发现
rc, res, ws = run_case("clean", "clean")
rv = res.get("review") or {}
check("审核无发现 → success，review passed",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "passed" and rv.get("rounds") == 1
      and rv.get("blocking_found") == 0 and rv.get("nonblocking_found") == 0
      and (ws / "REVIEW.md").exists() and not (ws / "REVIEW-REPAIR-1.md").exists(), brief(rc, res))
check("审核轮进 costs 的 LLM 加总",
      "agent-run-review.json" in ((res.get("costs") or {}).get("llm") or {}).get("files", []),
      str(((res.get("costs") or {}).get("llm") or {}).get("files")))
review_md = (ws / "REVIEW.md").read_text(encoding="utf-8") if (ws / "REVIEW.md").exists() else ""
check("REVIEW.md 指向三份文件、只许写 review.json",
      all(s in review_md for s in ("out/bank.json", "out/notes.md", "review-rubric.md", "out/review.json", "全部题目")), "")

# 2. 有阻塞 → 返修 → 复核通过
rc, res, ws = run_case("blocking", "blocking")
rv = res.get("review") or {}
check("有阻塞 → 返修 → 复核通过 → success，review repaired",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "repaired" and rv.get("rounds") == 2
      and rv.get("blocking_found") == 1 and rv.get("nonblocking_found") == 1 and rv.get("review_repair_rounds") == 1
      and res.get("repair_rounds") == 0 and res.get("prompt_count") == FIXTURE_COUNT + 1, brief(rc, res))
rr = (ws / "REVIEW-REPAIR-1.md").read_text(encoding="utf-8") if (ws / "REVIEW-REPAIR-1.md").exists() else ""
check("REVIEW-REPAIR-1.md：[review] 报错、检查命令、非阻塞意见搭车、最后一轮丢题授权",
      "[review] US-902 第 4 条" in rr and "validate_after_sales_set.py" in rr and "评审意见" in rr
      and "US-003 第 5 条" in rr and "丢题不丢库" in rr, "")
re2 = (ws / "REVIEW-2.md").read_text(encoding="utf-8") if (ws / "REVIEW-2.md").exists() else ""
check("REVIEW-2.md 只复核报过的题号",
      "复核" in re2 and "US-902" in re2 and "US-003" not in re2 and "全部题目" not in re2, "")
notes = (ws / "out/notes.md").read_text(encoding="utf-8") if (ws / "out/notes.md").exists() else ""
check("非阻塞意见进 result.json 和 notes.md「评审意见」",
      any(f.get("question_id") == "US-003" for f in rv.get("nonblocking") or []) and "评审意见" in notes, "")
check("审核返修轮进 costs",
      {"agent-run-review.json", "agent-run-review2.json", "agent-run-review-repair1.json"}
      <= set(((res.get("costs") or {}).get("llm") or {}).get("files", [])), "")

# 3. review.json 坏掉 + 审核 agent 改了题库
rc, res, ws = run_case("broken", "broken")
rv = res.get("review") or {}
bank_ok = len(json.loads((ws / "out/bank.json").read_text(encoding="utf-8")).get("questions") or []) == FIXTURE_COUNT + 1
check("review.json 不是 JSON → 不阻塞交付，review_failed + warning，题库恢复",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "review_failed"
      and len(rv.get("warnings") or []) == 2 and bank_ok, brief(rc, res) + f" bank_restored={bank_ok}")

# 4. 结构不对
rc, res, ws = run_case("shape", "shape")
rv = res.get("review") or {}
check("review.json 结构不对 → 不阻塞交付，review_failed",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "review_failed"
      and any("数组" in w for w in rv.get("warnings") or []), brief(rc, res))

# 5. 关闭审核
rc, res, ws = run_case("off", "clean", review_rounds=0)
rv = res.get("review") or {}
check("--review-rounds 0 → 跳过审核",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "skipped" and rv.get("rounds") == 0
      and not (ws / "REVIEW.md").exists(), brief(rc, res))

# 6. 额度用完仍有阻塞
rc, res, ws = run_case("stuck", "stuck")
rv = res.get("review") or {}
check("复核仍有阻塞、额度用完 → failed",
      rc == 1 and res.get("status") == "failed" and rv.get("status") == "review_failed"
      and any(e.get("stage") == "review" for e in res.get("errors", [])) and rv.get("blocking_unresolved")
      and not (ws / "REVIEW-REPAIR-2.md").exists(), brief(rc, res))

# 7. 审核 agent 超时
rc, res, ws = run_case("timeout", "timeout", timeout=5)
rv = res.get("review") or {}
check("审核 agent 超时 → 不阻塞交付，review_failed",
      rc == 0 and res.get("status") == "success" and rv.get("status") == "review_failed"
      and any("超时" in w for w in rv.get("warnings") or []), brief(rc, res))

passed = sum(1 for _, ok, _ in rows if ok)
lines = ["# 审核环端到端校验", "", f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
         "- 命令：`python3 evals/e2e_review_loop.py`", f"- 结果：{passed}/{len(rows)} 通过", "",
         "| 检查 | 结果 | 说明 |", "|---|---|---|"]
lines += [f"| {n} | {'通过' if ok else '失败'} | {d.replace('|', '/')} |" for n, ok, d in rows]
(SKILL / "reports").mkdir(exist_ok=True)
(SKILL / "reports" / "review-loop-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
shutil.rmtree(WS_ROOT, ignore_errors=True)
sys.exit(0 if passed == len(rows) else 1)
