#!/usr/bin/env python3
"""推荐与准确性标注的三个步骤：prepare（出批次）、merge（收回并校验）、sample（抽检）。

判据见 references/recommendation-labels.md。模型按批次文件逐条标，交回 JSONL；本脚本只做确定性的事：
选标谁、切批、校验引文、记「应出现而缺席」、汇总、抽样。

prepare
    读 layer_readings.py 的 readings.json 与 answers.jsonl，对每条有效回答：
    - 标谁：本品 + 该题合并读数里被提及最多的 --top-competitors 家同类竞品（默认 3）；
    - 正文出现了的品牌送模型标；本品没出现、上述竞品出现了 → 直接记 Z-GAP，不送模型；
    - 每批 --batch-size 条（默认 25），写 batches/batch-NNN.jsonl，每行含 answer_id、题面、平台、
      要标的品牌、去引用正文（超过 --max-chars 截断并注明）。
    --types 只标这些提示词类型（默认全部）；--named-only / --unnamed-only 二选一可选。

merge
    读 labels/*.jsonl（模型交回，格式见 recommendation-labels.md），逐条校验：code 合法、quote 逐字出现在正文、
    事实错误带 quote / correct / basis。不合格的写 labels-rejected.jsonl 退回重标。合格的与 Z-GAP 合并成
    labels.json：{answer_id: {brand: {code, constraint, quote}}, "_fact_errors": [...]}。

sample
    从 labels.json 按 code 分层随机抽 --n 条（默认 50，种子固定），写 sample-review.csv 给人逐条判。
    人填好 agree 列（Y/N）后用 --score 读回，算一致率。

用法：
    python3 -I label_batches.py prepare --readings <readings目录> --out <标注目录>
    python3 -I label_batches.py merge   --readings <readings目录> --out <标注目录>
    python3 -I label_batches.py sample  --out <标注目录> [--n 50]
    python3 -I label_batches.py sample  --out <标注目录> --score
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for extra in (SKILLS / "geo-monitoring" / "scripts", SKILLS / "geo-metrics" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import changeability_domains as cd  # noqa: E402,F401  （把报告数据层和 core 加进 sys.path）
from changeability_domains import brd  # noqa: E402
from de_cite_crawl import blank_merchant_columns, strip_citations  # noqa: E402
from geo_presales_core.util import normalize_text  # noqa: E402

CODES = {"D-TOP", "D-REC", "R-LIST", "Q-FIT", "X-WARN", "UNSURE"}
REC = {"D-TOP", "D-REC"}


def load(readings_dir: Path):
    data = json.loads((readings_dir / "readings.json").read_text(encoding="utf-8"))
    answers = [json.loads(line) for line in (readings_dir / "answers.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    return data, answers


def body_of(answer: dict) -> str:
    payload = json.loads(Path(answer["file"]).read_text(encoding="utf-8"))
    task = payload.get("task_result") or {}
    raw = str(task.get(brd.ANSWER_FIELD[answer["platform"]]) or "")
    return blank_merchant_columns(strip_citations(raw, task.get("follow_up_form")))


def squash(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def label_targets(data: dict, top: int) -> dict:
    target = data["meta"]["target"]
    out = {}
    for q in data["questions"]:
        pooled = q["platforms"].get("合并") or {}
        comps = [c["name"] for c in pooled.get("competitors") or []][:top]
        out[q["question_id"]] = [target] + comps
    return out


def prepare(args):
    data, answers = load(args.readings)
    target = data["meta"]["target"]
    qinfo = {q["question_id"]: q for q in data["questions"]}
    targets = label_targets(data, args.top_competitors)
    types = set(args.types or [])
    out = args.out
    (out / "batches").mkdir(parents=True, exist_ok=True)
    auto, items = {}, []
    for a in answers:
        q = qinfo.get(a["question_id"]) or {}
        if types and q.get("prompt_type") not in types:
            continue
        if args.named_only and not q.get("named"):
            continue
        if args.unnamed_only and q.get("named"):
            continue
        want = targets.get(a["question_id"], [target])
        present = [b for b in want if b in a["brands"]]
        if target not in a["brands"] and any(b in a["brands"] for b in want[1:]) and not q.get("named"):
            auto[a["answer_id"]] = {target: {"code": "Z-GAP", "constraint": "", "quote": ""}}
        if not present:
            continue
        body = body_of(a)
        cut = len(body) > args.max_chars
        items.append({"answer_id": a["answer_id"], "question_id": a["question_id"], "question": q.get("question", ""),
                      "platform": a["platform"], "label_brands": present,
                      "body": body[:args.max_chars] + ("\n[……正文截断]" if cut else "")})
    for i in range(0, len(items), args.batch_size):
        path = out / "batches" / f"batch-{i // args.batch_size + 1:03d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for it in items[i:i + args.batch_size]:
                handle.write(json.dumps(it, ensure_ascii=False) + "\n")
    (out / "auto-zgap.json").write_text(json.dumps(auto, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"送模型标注 {len(items)} 条，{(len(items) + args.batch_size - 1) // args.batch_size} 批；"
          f"自动记 Z-GAP {len(auto)} 条。批次在 {out / 'batches'}")
    return 0


def merge(args):
    data, answers = load(args.readings)
    by_id = {a["answer_id"]: a for a in answers}
    batches = {}
    for path in sorted((args.out / "batches").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                it = json.loads(line)
                batches[it["answer_id"]] = it
    labels = json.loads((args.out / "auto-zgap.json").read_text(encoding="utf-8"))
    fact_errors, unverified, rejected, unsure, relabeled = [], [], [], [], []
    seen = set()
    for path in sorted((args.out / "labels").glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append({"file": path.name, "line": n, "reason": f"JSON 解析失败：{exc}"})
                continue
            aid = rec.get("answer_id")
            item = batches.get(aid)
            if not item:
                rejected.append({"file": path.name, "line": n, "answer_id": aid, "reason": "批次里没有这条回答"})
                continue
            body = squash(item["body"])
            problems = []
            out = {}
            for brand, lab in (rec.get("labels") or {}).items():
                code = str((lab or {}).get("code") or "")
                if brand not in item["label_brands"]:
                    problems.append(f"{brand} 不在要标的品牌里")
                    continue
                if code not in CODES:
                    problems.append(f"{brand} 的 code {code!r} 不合法")
                    continue
                quote = str(lab.get("quote") or "")
                if code != "UNSURE" and (not quote or squash(quote) not in body):
                    problems.append(f"{brand} 的 quote 在正文里找不到")
                    continue
                if code == "Q-FIT" and not str(lab.get("constraint") or "").strip():
                    problems.append(f"{brand} 记 Q-FIT 但没写约束")
                    continue
                out[brand] = {"code": code, "constraint": lab.get("constraint") or "", "quote": quote,
                              "reason": lab.get("reason") or ""}
                if code == "UNSURE":
                    unsure.append({"answer_id": aid, "brand": brand, "reason": lab.get("reason") or ""})
            missing = [b for b in item["label_brands"] if b not in out]
            if missing and not problems and not rec.get("partial"):  # partial：复核重标只交改动的品牌，覆盖前面的标注
                problems.append(f"漏标 {missing}")
            for fe in rec.get("fact_errors") or []:
                if not (fe.get("quote") and squash(fe["quote"]) in body and fe.get("correct") and fe.get("basis")):
                    problems.append("事实错误缺 quote / correct / basis，或 quote 对不上正文")
                    break
            if problems:
                rejected.append({"answer_id": aid, "file": path.name, "line": n, "reason": "；".join(problems)})
                continue
            if rec.get("partial"):
                for brand, lab in out.items():
                    old = (labels.get(aid) or {}).get(brand, {}).get("code")
                    if old != lab["code"]:
                        relabeled.append({"answer_id": aid, "brand": brand, "from": old, "to": lab["code"]})
            seen.add(aid)
            labels.setdefault(aid, {}).update(out)
            for fe in rec.get("fact_errors") or []:
                fact_errors.append(dict(fe, answer_id=aid, question_id=item["question_id"], platform=item["platform"]))
            unverified.extend({"answer_id": aid, "text": t} for t in rec.get("unverified_facts") or [])
    pending = sorted(set(batches) - seen)
    labels["_fact_errors"] = fact_errors
    labels["_unverified_facts"] = unverified
    labels["_unsure"] = unsure
    labels["_relabeled"] = relabeled
    (args.out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    with (args.out / "labels-rejected.jsonl").open("w", encoding="utf-8") as handle:
        for r in rejected:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    codes = Counter(v["code"] for k, d in labels.items() if not k.startswith("_") for v in d.values())
    print(f"合格 {len(seen)} 条，退回 {len(rejected)} 条，未交回 {len(pending)} 条；分布 {dict(codes)}；"
          f"事实错误 {len(fact_errors)} 条，待核事实 {len(unverified)} 条，拿不准 {len(unsure)} 条，复核改判 {len(relabeled)} 条")
    if pending:
        (args.out / "labels-pending.json").write_text(json.dumps(pending, indent=1), encoding="utf-8")
    return 1 if (rejected or pending) else 0


def relabel(args):
    """把 labels.json 里某个值的全部品牌标注抽出来，按原批次正文出复核批次 relabel/relabel-NNN.jsonl。"""
    labels = json.loads((args.out / "labels.json").read_text(encoding="utf-8"))
    batches = {}
    for p in sorted((args.out / "batches").glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                it = json.loads(line)
                batches[it["answer_id"]] = it
    items = []
    for aid, d in labels.items():
        if aid.startswith("_") or aid not in batches:
            continue
        brands = [b for b, lab in d.items() if lab["code"] == args.code]
        if brands:
            it = dict(batches[aid], label_brands=brands,
                      current={b: {"code": d[b]["code"], "quote": d[b]["quote"]} for b in brands})
            items.append(it)
    out = args.out / "relabel"
    out.mkdir(exist_ok=True)
    for i in range(0, len(items), args.batch_size):
        with (out / f"relabel-{i // args.batch_size + 1:03d}.jsonl").open("w", encoding="utf-8") as handle:
            for it in items[i:i + args.batch_size]:
                handle.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{args.code} 复核 {len(items)} 条回答、{sum(len(i['label_brands']) for i in items)} 个品牌标注，"
          f"{(len(items) + args.batch_size - 1) // args.batch_size} 批，在 {out}")
    return 0


def sample(args):
    path = args.out / "sample-review.csv"
    if args.score:
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        judged = [r for r in rows if r.get("agree", "").strip().upper() in ("Y", "N")]
        agree = sum(r["agree"].strip().upper() == "Y" for r in judged)
        by_code = defaultdict(lambda: [0, 0])
        for r in judged:
            by_code[r["code"]][0] += r["agree"].strip().upper() == "Y"
            by_code[r["code"]][1] += 1
        rate = agree / len(judged) if judged else 0
        print(f"已判 {len(judged)}/{len(rows)}，一致 {agree}，一致率 {rate:.0%}；按值 "
              + "，".join(f"{c} {a}/{n}" for c, (a, n) in sorted(by_code.items())))
        (args.out / "sample-score.json").write_text(json.dumps(
            {"judged": len(judged), "agree": agree, "rate": round(rate, 4),
             "by_code": {c: {"agree": a, "n": n} for c, (a, n) in by_code.items()}}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        return 0 if rate >= 0.85 else 1
    labels = json.loads((args.out / "labels.json").read_text(encoding="utf-8"))
    batches = {}
    for p in sorted((args.out / "batches").glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                it = json.loads(line)
                batches[it["answer_id"]] = it
    pool = defaultdict(list)
    for aid, d in labels.items():
        if aid.startswith("_") or aid not in batches:
            continue
        for brand, lab in d.items():
            if lab["code"] not in ("Z-GAP", "UNSURE"):
                pool[lab["code"]].append((aid, brand, lab))
    rng = random.Random(20261116)
    total = sum(len(v) for v in pool.values())
    picks = []
    for code, items in sorted(pool.items()):
        k = max(1, round(args.n * len(items) / total)) if total else 0
        picks.extend(rng.sample(items, min(k, len(items))))
    rng.shuffle(picks)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["answer_id", "question", "platform", "brand", "code", "constraint", "quote", "agree", "note"])
        for aid, brand, lab in picks[:args.n + 5]:
            it = batches[aid]
            w.writerow([aid, it["question"], it["platform"], brand, lab["code"], lab["constraint"], lab["quote"], "", ""])
    print(f"抽了 {min(len(picks), args.n + 5)} 条到 {path}（按值分层，种子 20261116）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--readings", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--top-competitors", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=25)
    p.add_argument("--max-chars", type=int, default=9000)
    p.add_argument("--types", nargs="*")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--named-only", action="store_true")
    g.add_argument("--unnamed-only", action="store_true")
    m = sub.add_parser("merge")
    m.add_argument("--readings", required=True, type=Path)
    m.add_argument("--out", required=True, type=Path)
    rl = sub.add_parser("relabel")
    rl.add_argument("--out", required=True, type=Path)
    rl.add_argument("--code", required=True)
    rl.add_argument("--batch-size", type=int, default=40)
    s = sub.add_parser("sample")
    s.add_argument("--out", required=True, type=Path)
    s.add_argument("--n", type=int, default=50)
    s.add_argument("--score", action="store_true")
    args = ap.parse_args(argv)
    return {"prepare": prepare, "merge": merge, "relabel": relabel, "sample": sample}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
