#!/usr/bin/env python3
"""缺口诊断端到端校验（1.1.0，2026-11-17）。不联网、不花钱。

用假品牌（Veyra / Lumo / Nexo）和一份自造采集目录，跑通四个脚本的完整链路：
  R  layer_readings：归题、去重、强制联网判定、官网进检索与被引、同名回答去重、无解题登记
  G  diagnose：门 0/1/2、已领先守住、断点 1/3/5/7、约束明显劣势转产品、点名题靠标注
  L  label_batches：prepare 出的批次与 Z-GAP、merge 的校验与退回、sample 抽检与一致率
  P  page_gap：页面缺口 / 答案缺口 / 抓取失败（用预置缓存，不真联网）
  D  端到端产物：diagnosis.csv / .json / .md 三份都在，结论写进 md

产物：reports/gap-diagnosis-e2e.md；临时目录跑完删除。

    python3 evals/e2e_gap_diagnosis.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
LAYER = SKILL / "scripts/layer_readings.py"
LABELS = SKILL / "scripts/label_batches.py"
PAGE = SKILL / "scripts/page_gap.py"
DIAG = SKILL / "scripts/diagnose.py"
REPORT = SKILL / "reports/gap-diagnosis-e2e.md"

TARGET = "Veyra"
COMP_A, COMP_B = "Lumo", "Nexo"
THIRD = "reviewhub.example"
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" —— {detail[:300]}" if detail and not ok else ""))


def run(cmd, cwd=None):
    proc = subprocess.run([sys.executable, "-I", *map(str, cmd)], cwd=cwd, capture_output=True, text=True)
    return proc


# ------------------------------------------------------------------ 夹具

QUESTIONS = [
    {"question_id": "G-01", "topic_id": "t1", "topic": "portable solar chargers",
     "prompt_type": "Discovery", "priority": "高", "user_question": "best portable solar charger for camping"},
    {"question_id": "G-02", "topic_id": "t1", "topic": "portable solar chargers",
     "prompt_type": "Discovery", "priority": "高", "user_question": "best solar charger for backpacking"},
    {"question_id": "G-03", "topic_id": "t2", "topic": "brand reliability",
     "prompt_type": "Evaluation", "priority": "高", "user_question": "is Veyra solar charger reliable"},
    {"question_id": "G-04", "topic_id": "t1", "topic": "portable solar chargers",
     "prompt_type": "Discovery", "priority": "低", "user_question": "cheapest solar charger"},
    {"question_id": "G-05", "topic_id": "t1", "topic": "portable solar chargers",
     "prompt_type": "Discovery", "priority": "高", "user_question": "solar charger for RV trips"},
    {"question_id": "G-06", "topic_id": "t1", "topic": "portable solar chargers",
     "prompt_type": "Discovery", "priority": "高", "user_question": "best solar charger for van life"},
]

# 每题的正文与引用：8 条里 Q1 零提及、Q2 领先、Q6 低提及但官网常被引
BODIES = {
    "G-01": "For camping, reviewers usually point to Lumo and Nexo. Lumo folds flat; Nexo charges two devices.",
    "G-02": "Veyra is the top pick for backpacking. Lumo is a solid second option.",
    "G-03": "Veyra works outdoors, but buyers report it is not suitable for long trips.",
    "G-04": "For a cheap option, Lumo and Nexo are the usual suggestions.",
    "G-05": "Most guides recommend Lumo for RV trips.",
    "G-06": "Van lifers often choose Lumo. Nexo is occasionally mentioned; Veyra rarely comes up.",
}

ANSWER_SLUG = {qid: qid.lower().replace("-", "_") for qid in BODIES}


def write_bank(root: Path) -> Path:
    bank = {
        "config": {"brand_name": TARGET, "aliases": ["Veyra"], "official_domain": "veyra.com",
                   "competitors": [{"name": COMP_A, "domain": "lumo.com"}, {"name": COMP_B, "domain": "nexo.com"}],
                   "topics": [{"topic_id": "t1", "topic": "portable solar chargers", "priority": "高"},
                              {"topic_id": "t2", "topic": "brand reliability", "priority": "高"}]},
        "questions": QUESTIONS,
    }
    path = root / "bank.json"
    path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    return path


def write_lexicon(root: Path) -> Path:
    lex = {"brands": [
        {"name": TARGET, "type": "target", "aliases": ["Veyra"], "domains": ["veyra.com"]},
        {"name": COMP_A, "type": "competitor", "aliases": ["Lumo"], "domains": ["lumo.com"]},
        {"name": COMP_B, "type": "competitor", "aliases": ["Nexo"], "domains": ["nexo.com"]},
    ]}
    path = root / "lexicon.json"
    path.write_text(json.dumps(lex, ensure_ascii=False), encoding="utf-8")
    return path


def citations_for(qid, runs):
    if qid in ("G-02",):
        return [{"url": "https://www.veyra.com/backpacking", "title": "Backpacking kit", "cited_count": runs},
                {"url": f"https://{THIRD}/guides", "title": "Guide", "cited_count": 0}]
    if qid == "G-06":
        return [{"url": "https://www.veyra.com/van", "title": "Van kit", "cited_count": runs},
                {"url": f"https://{THIRD}/van", "title": "Van guide", "cited_count": runs},
                {"url": f"https://{THIRD}/guides", "title": "Guide", "cited_count": runs}]
    if qid == "G-03":
        return [{"url": f"https://{THIRD}/guides", "title": "Guide", "cited_count": runs},
                {"url": f"https://{THIRD}/reviews", "title": "Reviews", "cited_count": runs}]
    return [{"url": f"https://{THIRD}/guides", "title": "Guide", "cited_count": runs}]


def retrieval_for(qid):
    if qid in ("G-01", "G-04"):
        return [f"https://{THIRD}/guides", "https://www.lumo.com/products"]
    if qid == "G-02":
        return ["https://www.veyra.com/backpacking"]
    if qid == "G-06":
        return ["https://www.veyra.com/van", f"https://{THIRD}/van"]
    if qid == "G-03":
        return ["https://www.veyra.com/about", f"https://{THIRD}/reviews"]
    return []


def write_collect(root: Path):
    run = root / "collect" / "run-1"
    counts = {"G-05": 2}  # 门 0：只有 2 条
    for q in QUESTIONS:
        text = q["user_question"]
        qid = q["question_id"]
        runs = counts.get(qid, 7)
        folder = run / "scraper.chatgpt" / "US"
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, runs + 1):
            # 每次运行正文略有不同，避免被当成重复回答去重
            body = BODIES[qid] + f" Sources checked on day {i}."
            if qid == "G-06" and i > 2:  # 只在 2/7 条里提到本品，留出提及缺口
                body = "Van lifers often choose Lumo. Nexo is occasionally mentioned." + f" Sources checked on day {i}."
            payload = {"status": "success", "task_result": {
                "prompt": text,
                "result_text": body,
                "content_references": citations_for(qid, 1),
                "search_result": [{"url": u} for u in retrieval_for(qid)],
            }}
            (folder / f"{qid.replace('-', '')}{i:02d}.json").write_text(json.dumps(payload), encoding="utf-8")
    # 同名回答写两遍 → DUPLICATE_ANSWER
    dup_dir = run / "scraper.chatgpt" / "US"
    dup = {"status": "success", "task_result": {
        "prompt": QUESTIONS[0]["user_question"], "result_text": BODIES["G-01"] + " Sources checked on day 1.",
        "content_references": citations_for("G-01", 1),
        "search_result": [{"url": u} for u in retrieval_for("G-01")]}}
    (dup_dir / "G0199.json").write_text(json.dumps(dup), encoding="utf-8")
    # 不在题库的题 → UNRESOLVED
    odd = {"status": "success", "task_result": {"prompt": "some prompt not in the bank",
                                               "result_text": "An unrelated answer about something else entirely."}}
    (dup_dir / "G0000.json").write_text(json.dumps(odd), encoding="utf-8")
    (run / "collect-manifest.json").write_text(json.dumps({
        "questions_file": "bank.json", "web_search": True, "platforms": ["chatgpt"]}), encoding="utf-8")
    return run


def readings(root: Path):
    write_collect(root)
    out = root / "readings"
    proc = run([LAYER, "--bank", root / "bank.json", "--collect", root / "collect",
                "--lexicon", root / "lexicon.json", "--out", out])
    data = json.loads((out / "readings.json").read_text(encoding="utf-8"))
    issues = json.loads((out / "issues.json").read_text(encoding="utf-8"))
    return proc, out, data, issues


def q_of(data, qid):
    return next(q for q in data["questions"] if q["question_id"] == qid)


# ------------------------------------------------------------------ 用例

def case_layer(root: Path):
    proc, out, data, issues = readings(root)
    check("R1 layer_readings 输出四份文件",
          (out / "readings.json").exists() and (out / "answers.jsonl").exists()
          and (out / "readings.csv").exists() and (out / "issues.json").exists(),
          proc.stdout + proc.stderr)
    q1 = q_of(data, "G-01")
    merged = q1["platforms"]["合并"]
    check("R2 Q1 零提及、领先竞品识别为 Lumo", merged["target_mention"][0] == 0 and merged["leader"] == COMP_A,
          json.dumps(merged["leader_mention"]))
    check("R3 ChatGPT 强制联网口径记「强制」", merged["grounded"].get("强制") == 7, str(merged["grounded"]))
    check("R4 Q1 官网未进检索（search_result 只有第三方和竞品）",
          merged["official_retrieved"][0] == 0, str(merged["official_retrieved"]))
    q2 = q_of(data, "G-02")
    m2 = q2["platforms"]["合并"]
    check("R5 Q2 官网进检索与被引都 100%", m2["official_retrieved"][0] == 1 and m2["official_cited"][0] == 1,
          f"{m2['official_retrieved']} {m2['official_cited']}")
    q5 = q_of(data, "G-05")
    check("R6 Q5 只有 2 条有效回答（门 0 的依据）", q5["platforms"]["合并"]["n"] == 2,
          str(q5["platforms"]["合并"]["n"]))
    codes = {i["code"] for i in issues}
    check("R7 重复回答与无解题都登记进 issues", "DUPLICATE_ANSWER" in codes and len(codes) >= 2, str(sorted(codes)))
    check("R8 有未解题时退出码 1", proc.returncode == 1, f"rc={proc.returncode}")


def case_gates(root: Path, rd: Path):
    proc = run([DIAG, "--readings", rd, "--out", root / "diag-gates"])
    rows = list(csv.DictReader((root / "diag-gates" / "diagnosis.csv").open(encoding="utf-8-sig")))
    by_q = {r["题号"]: r for r in rows}
    check("G1 低优先级过不了门 1 → 暂不做", by_q["G-04"]["过门情况"] == "门 1 未过"
          and by_q["G-04"]["决定"] == "暂不做", by_q["G-04"]["过门情况"])
    check("G2 有效回答不足过不了门 0 → 观察", by_q["G-05"]["过门情况"] == "门 0 未过"
          and by_q["G-05"]["决定"] == "观察", by_q["G-05"]["过门情况"])
    check("G3 已领先的题 → 守住", by_q["G-02"]["决定"] == "守住", by_q["G-02"]["决定"])
    check("G4 Q1 定位到断点 3（官网没进检索层）", by_q["G-01"]["断点"].startswith("3 "),
          by_q["G-01"]["断点"] + " / " + by_q["G-01"]["证据"])
    check("G5 断点 3 的载体是官网、负责方内容团队",
          by_q["G-01"]["载体"] == "官网" and by_q["G-01"]["负责方"] == "内容团队",
          f"{by_q['G-01']['载体']} {by_q['G-01']['负责方']}")
    check("G6 无标注、无页面缺口时 Q3 退回观察", by_q["G-03"]["决定"] == "观察"
          or by_q["G-03"]["过门情况"] == "点名题", by_q["G-03"]["决定"] + " / " + by_q["G-03"]["过门情况"])


def case_constraints(root: Path, rd: Path):
    cons = root / "constraints.json"
    cons.write_text(json.dumps({"G-01": {"relative": "明显劣势", "basis": "容量只有竞品一半"}}), encoding="utf-8")
    site = root / "site.json"
    site.write_text(json.dumps({"crawlability": "低", "source": "官网诊断报告 2026-11"}), encoding="utf-8")
    proc = run([DIAG, "--readings", rd, "--constraints", cons, "--site-audit", site, "--out", root / "diag-cons"])
    rows = list(csv.DictReader((root / "diag-cons" / "diagnosis.csv").open(encoding="utf-8-sig")))
    by_q = {r["题号"]: r for r in rows}
    check("C1 主约束明显劣势过不了门 2 → 转产品", by_q["G-01"]["过门情况"] == "门 2 未过"
          and by_q["G-01"]["决定"] == "转产品", by_q["G-01"]["过门情况"])
    check("C2 其余题受站点可达性低影响改判断点 1", by_q["G-06"]["断点"].startswith("1 "), by_q["G-06"]["断点"])
    check("C3 断点 1 的负责方是官网技术", by_q["G-06"]["负责方"] == "官网技术", by_q["G-06"]["负责方"])


def prepare_and_merge(root: Path, rd: Path):
    out = root / "labels"
    proc = run([LABELS, "prepare", "--readings", rd, "--out", out])
    batches = sorted((out / "batches").glob("*.jsonl"))
    check("L1 prepare 产出批次文件与 auto-zgap", bool(batches) and (out / "auto-zgap.json").exists(),
          proc.stdout + proc.stderr)
    batch_rows = [json.loads(line) for b in batches for line in b.read_text(encoding="utf-8").splitlines() if line.strip()]
    q3_rows = [r for r in batch_rows if r.get("question_id") == "G-03"]
    check("L2 点名题 Q3 送模型标注，标注品牌含本品", bool(q3_rows) and TARGET in (q3_rows[0].get("label_brands") or []),
          json.dumps(q3_rows[:1])[:300])
    # 写回模型标注：合法一条 + 引文对不上一条 + 漏标一条 + Q-FIT 缺约束一条
    lab_dir = out / "labels"
    lab_dir.mkdir(parents=True, exist_ok=True)
    row = q3_rows[0]
    quote = "Veyra works outdoors"
    valid = [{"answer_id": r["answer_id"], "labels": {TARGET: {"code": "X-WARN", "quote": quote,
                                                              "reason": "只适合短途"}}} for r in q3_rows]
    bad_quote = {"answer_id": row["answer_id"], "labels": {TARGET: {"code": "X-WARN", "quote": "not in the text at all"}}}
    missing = {"answer_id": row["answer_id"], "labels": {}}
    no_constraint = {"answer_id": row["answer_id"], "labels": {TARGET: {"code": "Q-FIT", "quote": quote}}}
    (lab_dir / "m1.jsonl").write_text("\n".join(json.dumps(x) for x in valid + [bad_quote, missing, no_constraint]) + "\n",
                                      encoding="utf-8")
    proc = run([LABELS, "merge", "--readings", rd, "--out", out])
    labels = json.loads((out / "labels.json").read_text(encoding="utf-8"))
    rejected = [json.loads(line) for line in (out / "labels-rejected.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
    ok_label = (labels.get(row["answer_id"]) or {}).get(TARGET) or {}
    check("L3 引文逐字对上的标注被接受", ok_label.get("code") == "X-WARN", json.dumps(ok_label))
    check("L4 引文对不上、漏标、Q-FIT 缺约束都被退回", len(rejected) >= 3, f"rejected={len(rejected)}")
    check("L5 退回条目写了原因", all("reason" in r for r in rejected), json.dumps(rejected[:2])[:300])
    check("L6 merge 后 labels.json 带 _fact_errors 结构", "_fact_errors" in labels)
    return out


def case_labels(root: Path, rd: Path):
    out = prepare_and_merge(root, rd)
    proc = run([LABELS, "sample", "--out", out, "--n", "1"])
    csv_path = out / "sample-review.csv"
    check("L7 sample 产出人工抽检表", csv_path.exists(), proc.stdout + proc.stderr)
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig"))) if csv_path.exists() else []
    check("L8 抽检表有 agree 列", rows and "agree" in rows[0], str(list(rows[0].keys()) if rows else []))
    if rows:
        rows[0]["agree"] = "Y"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    proc = run([LABELS, "sample", "--out", out, "--score"])
    check("L9 --score 算出一致率", "一致率" in proc.stdout or "agreement" in proc.stdout.lower(), proc.stdout + proc.stderr)
    # 用这份标注跑诊断，验证第 7 断点
    proc = run([DIAG, "--readings", rd, "--labels", out / "labels.json", "--out", root / "diag-labels"])
    diag_rows = list(csv.DictReader((root / "diag-labels" / "diagnosis.csv").open(encoding="utf-8-sig")))
    q3 = next(r for r in diag_rows if r["题号"] == "G-03")
    check("L10 点名题有标注后定位到断点 7（被提及没被推荐）", q3["断点"].startswith("7 "),
          q3["断点"] + " / " + q3["证据"][:150])


def build_page_cache(pg_out: Path):
    cache = pg_out / "pages"
    cache.mkdir(parents=True, exist_ok=True)

    def seed(url, text, status="ok"):
        key = hashlib.sha1(url.encode()).hexdigest()
        (cache / f"{key}.txt").write_text(text, encoding="utf-8")
        (cache / f"{key}.status").write_text(status, encoding="utf-8")

    seed(f"https://{THIRD}/guides",
         "<html><body><h1>Portable solar charger guide</h1><p>Our picks: Lumo and Nexo. "
         "Lumo folds flat and Nexo charges two devices at once. Runners-up included several brands.</p></body></html>")
    seed(f"https://{THIRD}/van",
         "<html><body><h1>Van life chargers</h1><p>Veyra makes a compact kit. Lumo and Nexo are also "
         "popular picks among van lifers, with Lumo winning most comparisons.</p></body></html>")
    seed(f"https://{THIRD}/reviews", "<html><body>Access denied</body></html>", status="http_403")


def case_pages(root: Path, rd: Path):
    pg = root / "pagegap"
    build_page_cache(pg)
    proc = run([PAGE, "--readings", rd, "--out", pg])
    data = json.loads((pg / "page_gap.json").read_text(encoding="utf-8"))
    pages = data["pages"]
    rows = list(csv.DictReader((pg / "page_gap.csv").open(encoding="utf-8-sig")))
    check("P1 page_gap 输出 json 与 csv", (pg / "page_gap.json").exists() and (pg / "page_gap.csv").exists(),
          proc.stdout + proc.stderr)
    check("P2 没提本品、提了两家竞品的页面判页面缺口",
          any(r["gap"] == "页面缺口" and "/guides" in r["url"] for r in rows),
          json.dumps([{k: r[k] for k in ("url", "gap")} for r in rows])[:300])
    check("P3 提到本品但引用它的回答没提 → 答案缺口",
          any(r["gap"] == "答案缺口" and r["url"].endswith("/van") for r in rows),
          json.dumps([{k: r[k] for k in ("url", "gap")} for r in rows])[:300])
    check("P4 403 页面记抓取失败、不猜",
          any(str(r.get("fetch")) == "http_403" and r["gap"] == "未知" for r in rows),
          json.dumps([{k: r.get(k) for k in ("url", "fetch", "gap")} for r in rows])[:300])
    # 页面缺口接进诊断 → 断点 5
    proc = run([DIAG, "--readings", rd, "--pagegap", pg, "--out", root / "diag-pages"])
    rows = list(csv.DictReader((root / "diag-pages" / "diagnosis.csv").open(encoding="utf-8-sig")))
    q6 = next(r for r in rows if r["题号"] == "G-06")
    check("P5 官网已在检索层时，页面缺口接进诊断判断点 5", q6["断点"].startswith("5 "),
          q6["断点"] + " / " + q6["证据"][:150])


def case_outputs(root: Path, rd: Path):
    out = root / "diag-final"
    proc = run([DIAG, "--readings", rd, "--labels", root / "labels" / "labels.json",
                "--pagegap", root / "pagegap", "--out", out])
    check("D1 三份产物都在", all((out / f).exists() for f in ("diagnosis.csv", "diagnosis.json", "diagnosis.md")),
          proc.stdout + proc.stderr)
    md = (out / "diagnosis.md").read_text(encoding="utf-8")
    check("D2 md 里写断点与决定", "断点" in md and "决定" in md, md[:200])
    payload = json.loads((out / "diagnosis.json").read_text(encoding="utf-8"))
    check("D3 json 带每题行与元信息", "rows" in payload and "meta" in payload, str(list(payload)[:5]))
    check("D4 退出码 0", proc.returncode == 0, f"rc={proc.returncode}")


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="gap-e2e-"))
    try:
        write_bank(tmp)
        write_lexicon(tmp)
        case_layer(tmp)
        proc, rd, _data, _issues = readings(tmp)
        case_gates(tmp, rd)
        case_constraints(tmp, rd)
        case_labels(tmp, rd)
        case_pages(tmp, rd)
        case_outputs(tmp, rd)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    lines = [f"# 缺口诊断 e2e（{datetime.now():%Y-%m-%d %H:%M}）", "",
             f"{passed}/{total} 通过", "", "| 用例 | 结果 | 说明 |", "|---|---|---|"]
    for name, ok, detail in results:
        lines.append(f"| {name} | {'通过' if ok else '**失败**'} | {detail.replace('|', '\\|')[:200]} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} 通过，报告：{REPORT}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
