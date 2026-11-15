#!/usr/bin/env python3
"""引用来源统计：采集目录 → 来源类别、域名榜、品牌官网、逐题官网引用份额与引用率。

临时统计（试跑读数、给客户的单次分析）用这一条命令，不再各自写脚本——自己写的脚本最容易漏掉
「补判未登记域名」，结果全落进「其他」（2026-11-13 某车载品牌第一版 36% 是「其他」）。

口径（geo-metrics/references/metric-scope-and-copy-contract.md）：
- 引用计次：core `_citation_entries`，新格式按平台 cited_count，未去重。
- 引用份额 = 某来源被引次数 ÷ 全部引用次数；引用率 = 至少引用一次该来源的有效回答 ÷ 有效回答。
- 分类：core `sources.classify_source`（自有 > 竞品 > 内置表与共享缓存 > 未判读）。
- 门禁：未判读引用超过 5% 时退出码 3，并在 --out 写 domain-candidates.json；判完写回
  geo-presales-report-builder/assets/domain-categories.json 后重跑，或用 --allow-unjudged-domains 写明理由放行。

用法：
    python3 -I citation_sources.py --collect <采集目录> [<采集目录> …] --questions <题库.csv> [<题库.csv> …] \\
        --lexicon <品牌词表.json> --out <输出目录> [--official rbrand.com] [--cache <缓存>] \\
        [--allow-unjudged-domains "<理由>"]

--questions 给一份时所有采集目录共用；给多份时和 --collect 一一对应（文件 NNNN 对题库第 N 行）。
题库有 question_id 列时按它标题号，没有时用 Q0001 这种行号。
词表 brands[].type 为 target 的域名算自有网站，其余品牌的 domains 和顶层 competitor_site_domains 算竞品网站。

输出：summary.json、report.md、per-prompt.csv、domain-candidates.json（有未判读域名时）。
退出码：0 通过；2 输入错误；3 未判读超过上限。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from geo_presales_core.citations import _citation_entries  # noqa: E402
from geo_presales_core.crawler import answer_body, answer_validity  # noqa: E402
from geo_presales_core.sources import (  # noqa: E402
    SOURCE_TYPES,
    UNJUDGED_EXIT_CODE,
    classify_source,
    enforce_judged,
    load_cache,
    unjudged_coverage,
)
from geo_presales_core.util import domain_matches, normalize_host  # noqa: E402

PLATFORMS = ("chatgpt", "perplexity", "copilot", "gemini", "aimode", "overview", "grok", "alexa")


def load_questions(path: Path) -> list[dict]:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or "query" not in rows[0]:
        raise SystemExit(f"题库没有 query 列：{path}")
    return [{"id": (r.get("question_id") or "").strip() or f"Q{i:04d}", "query": r["query"].strip(),
             "topic": (r.get("topic") or "").strip()} for i, r in enumerate(rows, 1)]


def build_config(lexicon: dict, official: list[str], cache: dict) -> tuple[dict, dict]:
    objects, brand_domains = [], {}
    for i, b in enumerate(lexicon.get("brands") or []):
        domains = [normalize_host(d) for d in (b.get("domains") or b.get("official_domains") or []) if d]
        role = "target" if b.get("type") == "target" else "competitor"
        oid = "target" if role == "target" else f"b{i}"
        objects.append({"object_id": oid, "role": role, "official_domains": domains, "canonical_name": b.get("name")})
        if domains:
            brand_domains[b.get("name")] = domains
    if official:
        doms = [normalize_host(d) for d in official]
        target = next((o for o in objects if o["role"] == "target"), None)
        if target:
            target["official_domains"] = list(dict.fromkeys(target["official_domains"] + doms))
        else:
            objects.insert(0, {"object_id": "target", "role": "target", "official_domains": doms, "canonical_name": "target"})
        brand_domains.setdefault(next((o["canonical_name"] for o in objects if o["role"] == "target"), "target"), doms)
    config = {"objects": objects, "competitor_site_domains": lexicon.get("competitor_site_domains") or [],
              "domain_category_cache": cache}
    return config, brand_domains


def iter_answers(collect: Path, questions: list[dict]):
    for platform in PLATFORMS:
        pdir = collect / f"scraper.{platform}"
        if not pdir.is_dir():
            continue
        for region in sorted(p for p in pdir.iterdir() if p.is_dir()):
            for f in sorted(region.glob("*.json")):
                try:
                    n = int(f.stem.split("-")[0])
                except ValueError:
                    continue
                if not 1 <= n <= len(questions):
                    continue
                tr = (json.loads(f.read_text(encoding="utf-8")) or {}).get("task_result") or {}
                text = answer_body(tr, platform)
                if not answer_validity(text)[0]:
                    continue
                yield questions[n - 1], platform, region.name, tr, text


def pct(a: int, b: int, digits: int = 0) -> str:
    return f"{a / b:.{digits}%}" if b else "—"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="引用来源统计（带未判读门禁）")
    ap.add_argument("--collect", type=Path, nargs="+", required=True)
    ap.add_argument("--questions", type=Path, nargs="+", required=True)
    ap.add_argument("--lexicon", type=Path, required=True)
    ap.add_argument("--official", nargs="*", default=[], help="补充自有官网域名（词表 target 已有时可省）")
    ap.add_argument("--cache", type=Path, default=None, help="域名类别缓存，默认共享缓存")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--top", type=int, default=30, help="域名榜条数")
    ap.add_argument("--allow-unjudged-domains", default="", metavar="理由")
    args = ap.parse_args(argv)

    if len(args.questions) not in (1, len(args.collect)):
        print("--questions 要么给一份，要么和 --collect 一一对应", file=sys.stderr)
        return 2
    lexicon = json.loads(args.lexicon.read_text(encoding="utf-8"))
    config, brand_domains = build_config(lexicon, args.official, load_cache(args.cache))

    answers = []  # (question, citations[{host,source_type,basis,title,url}])
    for i, collect in enumerate(args.collect):
        qs = load_questions(args.questions[0] if len(args.questions) == 1 else args.questions[i])
        for q, platform, region, tr, text in iter_answers(collect, qs):
            cites = []
            for e in _citation_entries(platform, tr, text):
                host = normalize_host(e.get("domain_hint") or e.get("raw_url") or "")
                if not host:
                    continue
                v = classify_source(host, config)
                cites.append({"host": host, "source_type": v["source_type"], "basis": v["basis"],
                              "title": e.get("title"), "url": e.get("raw_url")})
            answers.append((q, platform, cites))
    if not answers:
        print("没有有效回答", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    coverage = unjudged_coverage(c for _, _, cs in answers for c in cs)
    if not enforce_judged(coverage, args.out / "domain-candidates.json", args.allow_unjudged_domains, "引用来源门禁"):
        return UNJUDGED_EXIT_CODE

    n_ans = len(answers)
    all_c = [c for _, _, cs in answers for c in cs]
    total = len(all_c)
    cat = Counter(c["source_type"] for c in all_c)
    cat_ans = Counter(t for _, _, cs in answers for t in {c["source_type"] for c in cs})
    dom = Counter(c["host"] for c in all_c)
    dom_ans = Counter(h for _, _, cs in answers for h in {c["host"] for c in cs})
    dom_type = {c["host"]: c["source_type"] for c in all_c}

    def hits(host, doms):
        return any(domain_matches(host, d) for d in doms)

    brands = []
    for name, doms in brand_domains.items():
        n = sum(1 for c in all_c if hits(c["host"], doms))
        a = sum(1 for _, _, cs in answers if any(hits(c["host"], doms) for c in cs))
        brands.append({"brand": name, "citations": n, "share": round(n / total, 4) if total else 0,
                       "answers": a, "rate": round(a / n_ans, 4)})
    brands.sort(key=lambda b: -b["citations"])
    own = next((o["official_domains"] for o in config["objects"] if o["role"] == "target"), [])

    per = defaultdict(lambda: {"answers": 0, "citations": 0, "own": 0, "own_answers": 0, "query": "", "topic": ""})
    for q, _, cs in answers:
        p = per[q["id"]]
        p["query"], p["topic"] = q["query"], q["topic"]
        p["answers"] += 1
        p["citations"] += len(cs)
        o = sum(1 for c in cs if hits(c["host"], own))
        p["own"] += o
        p["own_answers"] += o > 0
    topics = defaultdict(lambda: [0, 0, 0, 0])
    for p in per.values():
        t = topics[p["topic"] or "—"]
        t[0] += p["answers"]; t[1] += p["citations"]; t[2] += p["own"]; t[3] += p["own_answers"]

    summary = {
        "answers": n_ans, "answers_with_citations": sum(1 for *_, cs in answers if cs), "citations": total,
        "source_classification": {k: coverage[k] for k in ("total_citations", "unjudged_citations", "unjudged_share", "limit")}
        | {"allowed_reason": args.allow_unjudged_domains.strip() if coverage["unjudged_share"] > coverage["limit"] else ""},
        "categories": [{"type": k, "label": SOURCE_TYPES[k], "citations": v, "share": round(v / total, 4),
                        "rate": round(cat_ans[k] / n_ans, 4)} for k, v in cat.most_common()],
        "domains": [{"domain": h, "type": SOURCE_TYPES[dom_type[h]], "citations": v, "share": round(v / total, 4),
                     "rate": round(dom_ans[h] / n_ans, 4)} for h, v in dom.most_common(args.top)],
        "brand_sites": brands,
        "topics": [{"topic": k, "answers": v[0], "citations": v[1], "own_share": round(v[2] / v[1], 4) if v[1] else None,
                    "own_rate": round(v[3] / v[0], 4)} for k, v in topics.items()],
        "per_prompt": [{"id": k, **v, "own_share": round(v["own"] / v["citations"], 4) if v["citations"] else None,
                        "own_rate": round(v["own_answers"] / v["answers"], 4)} for k, v in sorted(per.items())],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(args.out / "per-prompt.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["编号", "主题", "提示词", "回答数", "官网引用份额", "官网引用率"])
        for r in summary["per_prompt"]:
            w.writerow([r["id"], r["topic"], r["query"], r["answers"], pct(r["own"], r["citations"]),
                        pct(r["own_answers"], r["answers"])])

    L = [f"# 引用来源统计\n\n有效回答 {n_ans} 条，有引用的 {summary['answers_with_citations']} 条，引用 {total} 次（未去重）。"
         f"引用份额 = 次数 ÷ {total}；引用率 = 至少引用一次的回答 ÷ {n_ans}。"
         f"未判读引用 {coverage['unjudged_share']:.1%}（上限 {coverage['limit']:.0%}）。\n",
         "## 来源类别\n\n| 类别 | 引用份额 | 引用率 |\n|---|---|---|"]
    L += [f"| {c['label']} | {pct(c['citations'], total)} | {pct(cat_ans[c['type']], n_ans)} |" for c in summary["categories"]]
    L.append("\n## 品牌官网\n\n| 品牌 | 引用份额 | 引用率 |\n|---|---|---|")
    L += [f"| {b['brand']} | {pct(b['citations'], total, 1)} | {pct(b['answers'], n_ans)} |" for b in brands if b["citations"]]
    L.append(f"\n## 前 {args.top} 域名\n\n| 域名 | 类别 | 引用份额 | 引用率 |\n|---|---|---|---|")
    L += [f"| {d['domain']} | {d['type']} | {pct(d['citations'], total, 1)} | {pct(dom_ans[d['domain']], n_ans)} |"
          for d in summary["domains"]]
    L.append("\n## 按主题：自有官网\n\n| 主题 | 回答 | 官网引用份额 | 官网引用率 |\n|---|---|---|---|")
    L += [f"| {k} | {v[0]} | {pct(v[2], v[1])} | {pct(v[3], v[0])} |" for k, v in topics.items()]
    L.append("\n## 逐题：自有官网\n\n| 编号 | 回答 | 官网引用份额 | 官网引用率 |\n|---|---|---|---|")
    L += [f"| {r['id']} | {r['answers']} | {pct(r['own'], r['citations'])} | {pct(r['own_answers'], r['answers'])} |"
          for r in summary["per_prompt"]]
    (args.out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"有效回答 {n_ans}，引用 {total}；输出 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
