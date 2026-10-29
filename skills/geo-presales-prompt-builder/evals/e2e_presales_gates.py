#!/usr/bin/env python3
"""售前生词门禁端到端校验（2026-10-29）。

从 evals/fixtures/selection-mode-sample-bank.json（7 题合格样例）出发，逐条造违规题库，
跑真实的选词 validator、售前专属检查、导出脚本，再用 run_selection_mode.py 的 prepare + finalize
走一遍线上入口，确认：
  - 合格样例三条检查都退出码 0，入口给 success；
  - 每种违规都被指定的那个检查拦下（退出码 1，报错里有对应原文）；
  - 合法的边界（劣势属性不挂行、没题的属性写了原因）照常通过；
  - 违规题库走线上入口时 result.json 是 failed，并指出是哪一关。
产物：reports/presales-gates-e2e.md，以及 build/presales-gates-e2e/ 下每个样本的题库与检查输出；
线上入口的两个工作目录建在系统临时目录，跑完删除。

    python3 evals/e2e_presales_gates.py
退出码 0 表示全部符合预期。
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SKILLS = SKILL.parent
FIXTURE = SKILL / "evals" / "fixtures" / "selection-mode-sample-bank.json"
VALIDATOR = SKILLS / "geo-prompt-selection-builder" / "scripts" / "validate_after_sales_set.py"
PRESALES = SKILL / "scripts" / "check_presales_bank.py"
EXPORT = SKILLS / "geo-prompt-selection-builder" / "scripts" / "export_upload_csv.py"
RUNNER = SKILL / "scripts" / "run_selection_mode.py"
CASE = SKILL / "references" / "input-examples" / "b2c-example.json"
BUILD = SKILL / "build" / "presales-gates-e2e"

base = json.loads(FIXTURE.read_text(encoding="utf-8"))
rows: list[tuple[str, bool, str]] = []


def q(bank: dict, qid: str) -> dict:
    return next(x for x in bank["questions"] if x["question_id"] == qid)


def plan(bank: dict, name: str) -> dict:
    return next(x for x in bank["config"]["attribute_plan"] if x["attribute"] == name)


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-I", *cmd], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def checks(name: str, bank: dict) -> dict[str, tuple[int, str]]:
    d = BUILD / name
    d.mkdir(parents=True, exist_ok=True)
    path = d / "bank.json"
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    out = {
        "validator": run([str(VALIDATOR), str(path)]),
        "presales": run([str(PRESALES), str(path)]),
        "export": run([str(EXPORT), str(path), "--out", str(d / "upload")]),
    }
    for k, (code, text) in out.items():
        (d / f"{k}.txt").write_text(f"exit {code}\n{text}", encoding="utf-8")
    return out


# ---- 违规样本：(名字, 改法, 应该拦下它的检查, 报错里要出现的原文) ----
def split_topic(b):  # 第二个主题只有 3 道题
    b["config"]["slices"][1]["topic_id"] = "t_two"
    b["config"]["topics"][0].update(source_slices=["pet"], planned_prompts=4)
    b["config"]["topics"].append({"topic_id": "t_two", "topic": "Hands-free Cleaning",
                                  "source_slices": ["clean"], "planned_prompts": 3})
    for qid in ("US-003", "US-004", "US-005"):
        q(b, qid)["topic_id"] = "t_two"


def discovery_minority(b):  # 发现型 3/7
    for qid in ("US-003", "US-004"):
        row = q(b, qid)
        row.update(prompt_type="Evaluation", analysis_type="sentiment", formal_visibility_eligible=False,
                   group_role="experimental", journey_stage="评估")
        row["user_question"] = row["monitoring_prompt"] = f"Is BrandX good for {row['constraints'][0] if row['constraints'] else 'daily cleaning'}?"


def alternatives(b):
    row = q(b, "US-006")
    row.update(prompt_type="Alternatives", journey_stage="替代方案")
    row["user_question"] = row["monitoring_prompt"] = "What are good alternatives to RivalA for pet hair?"


def stray_competitor(b):
    row = q(b, "US-006")
    row["user_question"] = row["monitoring_prompt"] = "Is BrandX or Dyson better for pet hair on carpet?"


def empty_plan(b):
    b["config"]["attribute_plan"] = []


def weak_on_row(b):
    b["config"]["attribute_plan"].append({"attribute": "价格", "relative_competitor": "劣势",
                                          "relative_competitor_basis": "竞品同档便宜两成"})
    b["config"]["slices"][0]["attributes"].append("价格")


def row_attr_missing(b):
    b["config"]["slices"][0]["attributes"].append("续航")


def verdict_missing(b):
    plan(b, "避障").pop("relative_competitor")


def basis_missing(b):
    plan(b, "避障")["relative_competitor_basis"] = ""


def uncarried_no_reason(b):
    b["config"]["attribute_plan"].append({"attribute": "售后服务", "relative_competitor": "持平",
                                          "relative_competitor_basis": "评价站两边差不多"})


FAILS = [
    ("主题只有 3 道题", split_topic, "presales", "每个主题至少 5 道题"),
    ("发现型不到一半", discovery_minority, "presales", "不到一半"),
    ("出了替代题", alternatives, "presales", "这些题型不对"),
    ("对比题点名非冻结竞品", stray_competitor, "presales", "没点名冻结竞品"),
    ("属性池为空", empty_plan, "presales", "attribute_plan 为空"),
    ("劣势属性挂到矩阵行", weak_on_row, "validator", "lists 劣势 attributes"),
    ("行属性不在属性池", row_attr_missing, "validator", "absent from attribute_plan"),
    ("属性池缺相对竞品", verdict_missing, "validator", "relative_competitor must be one of"),
    ("属性池相对竞品没写依据", basis_missing, "validator", "relative_competitor_basis is empty"),
    ("没题的持平属性没写原因", uncarried_no_reason, "validator", "no_carrier_reason"),
]


def weak_in_pool_only(b):
    b["config"]["attribute_plan"].append({"attribute": "价格", "relative_competitor": "劣势",
                                          "relative_competitor_basis": "竞品同档便宜两成"})


def uncarried_with_reason(b):
    uncarried_no_reason(b)
    plan(b, "售后服务")["no_carrier_reason"] = "所在行是 P3，本期不出题"


PASSES = [
    ("合格样例", lambda b: None),
    ("劣势属性只留在属性池", weak_in_pool_only),
    ("没题的持平属性写了 no_carrier_reason", uncarried_with_reason),
]

if BUILD.exists():
    shutil.rmtree(BUILD)
WS_ROOT = Path(tempfile.mkdtemp(prefix="presales-gates-"))

for label, fn, _ in [(n, f, None) for n, f in PASSES]:
    bank = copy.deepcopy(base)
    fn(bank)
    out = checks(f"pass-{label}", bank)
    bad = {k: v[0] for k, v in out.items() if v[0] != 0}
    rows.append((f"通过：{label}", not bad, f"非 0 退出码：{bad}" if bad else "三条检查都退出码 0"))

for label, fn, gate, needle in FAILS:
    bank = copy.deepcopy(base)
    fn(bank)
    code, text = checks(f"fail-{label}", bank)[gate]
    ok = code == 1 and needle in text
    hit = next((line for line in text.splitlines() if needle in line), text.strip().splitlines()[-1] if text.strip() else "")
    rows.append((f"拦下：{label}（{gate}）", ok, f"exit {code}；{hit[:160]}"))

# ---- 线上入口：prepare + finalize ----
def entry(name: str, bank: dict) -> dict:
    ws = WS_ROOT / f"ws-{name}"  # 工作目录含 skill 拷贝，放临时目录，不留在 skill 树里
    code, text = run([str(RUNNER), "prepare", "--case", str(CASE), "--market", "US",
                      "--platforms", "chatgpt", "--out", str(ws)])
    if code != 0:
        return {"status": f"prepare 失败 exit {code}", "errors": [text[-300:]]}
    (ws / "out/bank.json").write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    run([str(RUNNER), "finalize", "--out", str(ws)])
    return json.loads((ws / "out/result.json").read_text(encoding="utf-8"))


good = entry("good", copy.deepcopy(base))
rows.append(("线上入口：合格样例 → success，readiness 有值",
             good.get("status") == "success" and good.get("prompt_count") == 7 and bool(good.get("validator_readiness")),
             f"status={good.get('status')} prompt_count={good.get('prompt_count')} readiness={good.get('validator_readiness')!r}"))
bad_bank = copy.deepcopy(base)
split_topic(bad_bank)
bad = entry("short-topic", bad_bank)
stages = [e.get("stage") for e in bad.get("errors", [])]
rows.append(("线上入口：主题只有 3 道 → failed，指出 presales_check",
             bad.get("status") == "failed" and "presales_check" in stages,
             f"status={bad.get('status')} stages={stages}"))

# ---- 文档与任务说明 ----
mode = (SKILL / "references" / "selection-mode.md").read_text(encoding="utf-8")
runner = RUNNER.read_text(encoding="utf-8")
rows.append(("selection-mode 不再提「交接文件」", "交接文件" not in mode, ""))
rows.append(("selection-mode 第 8 步列了售前专属检查", "check_presales_bank.py" in mode, ""))
rows.append(("selection-mode 写了 no_carrier_reason", "no_carrier_reason" in mode, ""))
rows.append(("TASK 结束检查含售前专属检查、notes.md 含预跑答案与没开的格子",
             "check_presales_bank.py out/bank.json" in runner and "「预跑答案」" in runner and "「没开的格子」" in runner, ""))

passed = sum(1 for _, ok, _ in rows if ok)
lines = ["# 售前生词门禁端到端校验", "", f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
         "- 命令：`python3 evals/e2e_presales_gates.py`", f"- 结果：{passed}/{len(rows)} 通过",
         f"- 每个样本的题库与检查原文：`build/presales-gates-e2e/`", "", "| 检查 | 结果 | 说明 |", "|---|---|---|"]
lines += [f"| {n} | {'通过' if ok else '失败'} | {d.replace('|', '/')} |" for n, ok, d in rows]
(SKILL / "reports").mkdir(exist_ok=True)
(SKILL / "reports" / "presales-gates-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
shutil.rmtree(WS_ROOT, ignore_errors=True)
sys.exit(0 if passed == len(rows) else 1)
