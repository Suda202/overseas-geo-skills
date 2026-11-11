#!/usr/bin/env python3
"""试跑答案 → 发现题、替代题每个平台答案里点了几个品牌（geo-monitoring/references/trial-and-lock.md「试跑」「判题是否合格」）。

用来找「答案进了解释模式」的题：问的是候选，AI 却只讲方法、规则或区域，正文里几乎不点品牌。
只数答案里出现了几个不同的品牌，任何品牌都算，不看本品有没有被提到，所以不违反「品牌读数不进选题」。
点名品牌少还有两种原因，都不算题不合格：题面是单数（Which tool …），AI 只推一个；词表里没有答案点的品牌。

1. 归题、去重、判失败页和 ``changeability_domains.py`` 用同一套（同一个 Resolver、同一套镜像目录去重）。
2. 正文：取平台正文字段，用 ``geo-metrics/scripts/de_cite_crawl.py`` 去引用标记、
   清空商品卡的销售渠道列（渠道不是候选）。
3. 品牌：题库 config 的本品和竞品（``brand_name`` / ``aliases`` / ``competitors`` /
   ``competitor_selection.formal_competitors``）∪ ``--lexicon`` 品牌词表（售前报告同一格式，
   ``uncertain`` 里的名字不算）。别名匹配用 core 的 ``find_alias_spans`` + ``resolve_alias_spans``，
   泰文、中文这类无空格文字不加词边界。
4. 每道题 × 平台：每次回答数一次不同品牌数，取中位数；中位数 ≤ ``--max-brands``（默认 1）标
   「点名品牌少」。只是提示：人工打开答案分三种原因——解释模式（按「两三次同样失败」改写）、
   单选答案、词表缺品牌（补进词表重跑）。

没有词表时只认题库 config 里的几家，计数会偏低、误标变多：先跑
``geo-metrics/scripts/mine_brand_lexicon.py --collect-dir <试跑目录>`` 挖候选，
人工收成词表再给 ``--lexicon``。

输出（``--out`` 目录）：``brand_count.csv``（每题 × 平台一行）、``brand_count.json``（含每次回答的品牌名单）。

用法：
    python3 -I trial_brand_count.py --bank <bank.json> --collect <试跑目录> [<试跑目录> …] \\
        --out <输出目录> [--lexicon <品牌词表.json>] [--max-brands 1] [--types Discovery Alternatives]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for extra in (HERE, SKILLS / "geo-metrics" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import changeability_domains as cd  # noqa: E402  （同时把售前报告数据层和 core 加进 sys.path）
from changeability_domains import brd  # noqa: E402
from de_cite_crawl import blank_merchant_columns, strip_citations  # noqa: E402
from geo_presales_core.crawler import answer_validity  # noqa: E402
import geo_presales_core.util as core_util  # noqa: E402
from geo_presales_core.util import find_alias_spans, normalize_text, resolve_alias_spans  # noqa: E402

DEFAULT_TYPES = ("Discovery", "Alternatives")
DEFAULT_MAX = 1


def q_type(q: dict) -> str:
    return str(q.get("prompt_type") or q.get("intent") or "").strip()


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def build_brands(config: dict, lexicon_path: Path | None):
    """[{name, aliases}]，按归一化名字合并别名。"""
    merged: dict[str, dict] = {}

    def add(name, aliases=()):
        name = str(name or "").strip()
        if not name:
            return
        key = normalize_text(name)
        slot = merged.setdefault(key, {"name": name, "aliases": set()})
        slot["aliases"].update(a for a in [name, *(str(x).strip() for x in aliases)] if a)

    add(config.get("brand_name"), as_list(config.get("aliases")))
    pools = [config.get("competitors") or []]
    selection = config.get("competitor_selection") or {}
    if isinstance(selection, dict):
        pools.append(selection.get("formal_competitors") or [])
    for pool in pools:
        for item in pool if isinstance(pool, list) else []:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                add(item.get("name") or item.get("brand"), as_list(item.get("aliases")))
    status = "无词表"
    if lexicon_path:
        entries, _uncertain, status = brd.load_lexicon(lexicon_path)
        if status != "loaded":
            raise SystemExit(f"词表读不了（{status}）：{lexicon_path}")
        for entry in entries:
            add(entry["name"], entry["aliases"])
    case_sensitive = core_util.read_case_sensitive_aliases(lexicon_path)
    brands = [{"object_id": f"b{i}", "name": v["name"], "aliases": sorted(v["aliases"]),
               "case_sensitive_aliases": core_util.case_sensitive_for(v["aliases"], case_sensitive)}
              for i, v in enumerate(merged.values())]
    return brands, status


def brands_in(text: str, brands: list[dict]) -> list[str]:
    spans = []
    for b in brands:
        for span in find_alias_spans(text, b["aliases"], b["case_sensitive_aliases"]):
            spans.append(dict(span, object_id=b["object_id"]))
    first: dict[str, int] = {}
    for span in resolve_alias_spans(spans):
        first.setdefault(span["object_id"], span["start"])
    names = {b["object_id"]: b["name"] for b in brands}
    return [names[oid] for oid in sorted(first, key=first.get)]


def collect(collect_dirs, questions, brands, types):
    resolver = cd.Resolver(questions)
    wanted = {q["question_id"] for q in questions if q_type(q) in types}
    runs = cd.find_runs(collect_dirs)
    issues: list[dict] = []
    seen: dict[str, str] = {}
    per = defaultdict(list)  # (qid, platform) -> [{file, brands}]
    for run in runs:
        rows, _csv = cd.run_questions_csv(run, issues)
        for pdir in sorted(run.glob("scraper.*")):
            platform = pdir.name.split(".", 1)[1]
            if platform not in brd.ANSWER_FIELD:
                issues.append({"code": "UNKNOWN_PLATFORM", "dir": str(pdir)})
                continue
            for rdir in sorted(p for p in pdir.iterdir() if p.is_dir()):
                for path in sorted(rdir.glob("*.json")):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        issues.append({"code": "BAD_JSON", "file": str(path)})
                        continue
                    task = payload.get("task_result") or {}
                    raw = str(task.get(brd.ANSWER_FIELD[platform]) or "")
                    echo = str(task.get("prompt") or task.get("user_query") or task.get("user_text") or "").strip()
                    qid, _method, code = resolver.resolve(echo, rows.get(path.stem), path.stem, rdir.name)
                    if not qid:
                        issues.append({"code": code, "file": str(path)})
                        continue
                    if qid not in wanted:
                        continue
                    if raw.strip():
                        digest = hashlib.sha256(json.dumps([platform, raw], ensure_ascii=False).encode()).hexdigest()
                        if digest in seen:
                            continue
                        seen[digest] = str(path)
                    status = str(payload.get("status") or "success").lower()
                    body = blank_merchant_columns(strip_citations(raw, task.get("follow_up_form")))
                    valid, _ = answer_validity(body)
                    if status != "success" or not valid:
                        continue
                    per[(qid, platform)].append({"file": str(path), "brands": brands_in(body, brands)})
    return runs, per, issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bank", type=Path, required=True)
    ap.add_argument("--collect", type=Path, nargs="+", required=True, help="试跑采集目录（可多个，或其上层目录）")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lexicon", type=Path, default=None, help="品牌词表 JSON（售前报告同一格式）")
    ap.add_argument("--max-brands", type=float, default=DEFAULT_MAX, help="中位数 ≤ 此值标点名品牌少（默认 1）")
    ap.add_argument("--types", nargs="+", default=list(DEFAULT_TYPES), help="查哪些类型（默认 Discovery Alternatives）")
    args = ap.parse_args(argv)

    _raw, bank, questions = cd.load_bank(args.bank)
    brands, lex_status = build_brands(bank.get("config") or {}, args.lexicon)
    runs, per, issues = collect(args.collect, questions, brands, set(args.types))

    results = []
    for q in questions:
        if q_type(q) not in args.types:
            continue
        platforms = sorted(p for (qid, p) in per if qid == q["question_id"])
        if not platforms:
            results.append({"question_id": q["question_id"], "prompt_type": q_type(q), "platform": "",
                            "answers": 0, "counts": [], "median": None, "flag": "无试跑答案",
                            "brands": [], "user_question": cd.q_text(q)})
            continue
        for platform in platforms:
            answers = per[(q["question_id"], platform)]
            counts = [len(a["brands"]) for a in answers]
            median = statistics.median(counts)
            flag = "点名品牌少" if median <= args.max_brands else ""
            union = Counter(b for a in answers for b in a["brands"])
            results.append({"question_id": q["question_id"], "prompt_type": q_type(q), "platform": platform,
                            "answers": len(answers), "counts": counts, "median": median, "flag": flag,
                            "brands": [b for b, _ in union.most_common()], "runs": answers,
                            "user_question": cd.q_text(q)})

    args.out.mkdir(parents=True, exist_ok=True)
    meta = {"bank": str(args.bank), "runs": [str(r) for r in runs], "lexicon": str(args.lexicon or ""),
            "lexicon_status": lex_status, "brand_count": len(brands), "max_brands": args.max_brands,
            "types": args.types, "issues": issues}
    (args.out / "brand_count.json").write_text(
        json.dumps({"meta": meta, "rows": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    headers = ["question_id", "prompt_type", "platform", "answers", "counts", "median", "flag", "brands", "user_question"]
    with (args.out / "brand_count.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=headers)
        w.writeheader()
        for r in results:
            w.writerow({**{k: r.get(k) for k in headers}, "counts": " ".join(map(str, r["counts"])),
                        "median": "" if r["median"] is None else r["median"],
                        "brands": "、".join(r["brands"][:8])})

    print(f"试跑目录 {len(runs)} 个；品牌 {len(brands)} 个（{lex_status}）；类型 {' '.join(args.types)}；"
          f"中位数 ≤{args.max_brands:g} 标点名品牌少")
    if not args.lexicon:
        print("没给 --lexicon：只认题库 config 里的品牌，计数偏低、误标会多。")
    codes = Counter(i["code"] for i in issues)
    if codes:
        print("归题问题：" + "、".join(f"{k} {v}" for k, v in codes.most_common()))
    print(f"\n{'题号':<14}{'平台':<10}{'回答':>4}  每次品牌数   中位  标记 / 出现的品牌")
    for r in results:
        print(f"{r['question_id']:<14}{r['platform'] or '—':<10}{r['answers']:>4}  "
              f"{' '.join(map(str, r['counts'])) or '—':<12}{'' if r['median'] is None else r['median']:>4}  "
              f"{r['flag'] + ' ' if r['flag'] else ''}{'、'.join(r['brands'][:6])}")
    flagged = sorted({r["question_id"] for r in results if r["flag"] == "点名品牌少"})
    print(f"\n点名品牌少 {len(flagged)} 题：{'、'.join(flagged) or '无'}（人工打开答案判原因：解释模式才改写）")
    print(f"输出：{args.out / 'brand_count.csv'}、{args.out / 'brand_count.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
