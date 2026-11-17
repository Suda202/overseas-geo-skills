#!/usr/bin/env python3
"""正式基线采集目录 → 每道题 × 平台的七层读数（可达、联网、检索、引用、提及，推荐与准确另由标注补）。

只做确定性计算，不判原因、不给动作（那是 diagnose.py）。规则见 references/diagnosis-rules.md 第 1 节。

1. 归题、去重、失败页判定、引用抽取、品牌识别全部复用现有实现，不另写口径：
   - 归题与去重：geo-monitoring/scripts/changeability_domains.py 的 Resolver、find_runs、run_questions_csv；
   - 正文字段、引用：geo-presales-report-builder 的 build_report_data（ANSWER_FIELD、_citation_entries）；
   - 去引用正文：geo-metrics/scripts/de_cite_crawl.py；品牌识别：trial_brand_count 的 build_brands / brands_in
     （core 的 find_alias_spans + resolve_alias_spans），同类品牌与竞品官网：changeability_domains.load_vendor_brands。
2. 检索层字段读 geo-monitoring 的平台字段合同（audit_crawl_integrity.load_platform_contract），
   ChatGPT 只取 search_result（links 里混着商品卡和图片地址）。没有检索字段的平台（Gemini、Perplexity）记不可观察。
3. 联网：ChatGPT 采集 manifest 里 web_search=true 时记「强制联网」——Scrapeless 文档写明这会让 ChatGPT 执行搜索，
   自然联网率不可观察。其余平台有检索字段时，检索结果非空记联网。
4. 比率都带分母和 Wilson 95% 区间；跨平台合并只用于判稳定性。

输入：
    --bank       题库 bank.json；或采集用的 questions.csv（列 query、question_id，可选 topic、intent、region），
                 此时用 --brand 给本品名
    --collect    一个或多个采集目录（含 scraper.<平台>/<市场>/NNNN.json，往下找）
    --lexicon    品牌词表（geo-metrics 格式），用来认品牌、同类竞品和官网域名
    --official   额外的本品官网域名（可多次）
    --priority   可选 JSON：{"<question_id 或 topic_id 或 topic 名>": "高|中|低"}，题库没写业务优先级时补
    --sku-map    可选 JSON 列表：[{"name", "pattern"（正文正则）, "url_pattern"（页面网址正则，可选）}]
    --sku-fit    可选 JSON：{"<question_id>": ["SKU 名", …]}，只在这些题上算 SKU 读数
    --out        输出目录

输出：answers.jsonl（每条有效回答一行）、readings.json、readings.csv（每题 × 平台一行，另有合并行）、
      cited_pages.csv（每题被引的第三方页面）、issues.json。

用法：
    python3 -I layer_readings.py --bank bank.json --collect <基线目录> --lexicon lexicon.json --out <输出目录>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for extra in (SKILLS / "geo-monitoring" / "scripts", SKILLS / "geo-metrics" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import changeability_domains as cd  # noqa: E402  （同时把报告数据层和 core 加进 sys.path）
from changeability_domains import brd  # noqa: E402
import trial_brand_count as tbc  # noqa: E402
from audit_crawl_integrity import load_platform_contract  # noqa: E402
from de_cite_crawl import blank_merchant_columns, strip_citations  # noqa: E402
from geo_presales_core.crawler import answer_validity  # noqa: E402
from geo_presales_core.shopping import extract_product_cards  # noqa: E402
from geo_presales_core.util import find_alias_spans, is_platform_internal, normalize_host, normalize_text  # noqa: E402

RETRIEVAL_OVERRIDE = {"chatgpt": ["search_result"]}
FORCED_SEARCH_PLATFORMS = {"chatgpt"}  # Scrapeless 文档：web_search=true 时 ChatGPT 执行搜索


def wilson(k: int, n: int, z: float = 1.96):
    if not n:
        return None, None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(p, 4), round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def urls_in(value) -> list[str]:
    out = []
    if isinstance(value, str):
        if value.startswith("http"):
            out.append(value)
    elif isinstance(value, dict):
        for key in ("url", "link", "href", "source_url"):
            v = value.get(key)
            if isinstance(v, str) and v.startswith("http"):
                out.append(v)
                break
    elif isinstance(value, list):
        for item in value:
            out.extend(urls_in(item))
    return out


def clean_url(url: str) -> str:
    return url.split("#")[0].split("?")[0].rstrip("/")


# ------------------------------------------------------------------ 题库

def load_questions(args):
    path = Path(args.bank)
    if path.suffix.lower() == ".csv":
        if not args.brand:
            raise SystemExit("用 questions.csv 当题库时要给 --brand（本品名）")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        questions = []
        for i, r in enumerate(rows, 1):
            qid = (r.get("question_id") or r.get("qid") or f"{i:04d}").strip()
            questions.append({"question_id": qid, "user_question": (r.get("query") or "").strip(),
                              "topic": (r.get("topic") or "").strip(), "topic_id": (r.get("topic") or "").strip(),
                              "prompt_type": (r.get("intent") or r.get("prompt_type") or "").strip(),
                              "region": (r.get("region") or "").strip()})
        config = {"brand_name": args.brand, "aliases": [], "competitors": []}
        return config, questions
    _raw, bank, questions = cd.load_bank(path)
    return bank.get("config") or {}, questions


def topic_meta(config: dict) -> dict:
    out = {}
    for t in config.get("topics") or []:
        if isinstance(t, dict):
            meta = {"topic": t.get("topic") or t.get("name") or "", "priority": t.get("priority") or ""}
            for key in (t.get("topic_id"), t.get("topic"), t.get("name")):
                if key:
                    out[str(key)] = meta
    return out


def priority_of(q: dict, topics: dict, override: dict) -> tuple[str, str]:
    for key in (q.get("question_id"), q.get("topic_id"), q.get("topic")):
        if key and str(key) in override:
            return str(override[str(key)]), "priority 文件"
    for field in ("priority", "prompt_priority", "提示词优先级", "business_priority"):
        if q.get(field):
            return str(q[field]), f"题库 {field}"
    meta = topics.get(str(q.get("topic_id") or "")) or topics.get(str(q.get("topic") or ""))
    if meta and meta.get("priority"):
        return str(meta["priority"]), "题库主题优先级"
    return "未定", ""


# ------------------------------------------------------------------ 主流程

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bank", required=True)
    ap.add_argument("--brand")
    ap.add_argument("--collect", required=True, nargs="+", type=Path)
    ap.add_argument("--lexicon", type=Path)
    ap.add_argument("--official", action="append", default=[])
    ap.add_argument("--priority", type=Path)
    ap.add_argument("--sku-map", type=Path)
    ap.add_argument("--sku-fit", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    config, questions = load_questions(args)
    topics = topic_meta(config)
    override = json.loads(args.priority.read_text(encoding="utf-8")) if args.priority else {}
    qmap = {q["question_id"]: q for q in questions}

    brands, lex_status = tbc.build_brands(config, args.lexicon)
    vendors, same_cat_brands, vendor_note = cd.load_vendor_brands(config, args.lexicon)
    same_cat = {normalize_text(b["name"]) for b in same_cat_brands}

    target_name = str(config.get("brand_name") or "").strip()
    official_domains = list(args.official)
    if config.get("official_domain"):
        official_domains.append(config["official_domain"])
    if args.lexicon:
        lex = json.loads(args.lexicon.read_text(encoding="utf-8"))
        for b in lex.get("brands") or []:
            if str(b.get("type") or "") == "target":
                target_name = target_name or b.get("name")
                official_domains.extend(b.get("domains") or b.get("official_domains") or [])
    if not target_name:
        raise SystemExit("认不出本品：题库 config.brand_name 和词表 type=target 都没有")
    target_key = normalize_text(target_name)
    target_brand = next((b for b in brands if normalize_text(b["name"]) == target_key), None)
    if not target_brand:
        raise SystemExit(f"品牌清单里没有本品 {target_name}")
    official = cd.Matcher(official_domains)
    vendor_matchers = {name: m for name, m in vendors.items() if normalize_text(name) != target_key}

    skus = json.loads(args.sku_map.read_text(encoding="utf-8")) if args.sku_map else []
    for s in skus:
        s["_re"] = re.compile(s["pattern"], re.I)
        s["_url_re"] = re.compile(s["url_pattern"], re.I) if s.get("url_pattern") else None
    sku_fit = json.loads(args.sku_fit.read_text(encoding="utf-8")) if args.sku_fit else {}

    contract = load_platform_contract()
    resolver = cd.Resolver(questions)
    runs = cd.find_runs(args.collect)
    issues: list[dict] = []
    seen: dict[str, str] = {}
    answers: list[dict] = []

    for run in runs:
        rows, _csv = cd.run_questions_csv(run, issues)
        manifest = {}
        if (run / "collect-manifest.json").exists():
            manifest = json.loads((run / "collect-manifest.json").read_text(encoding="utf-8"))
        web_search_flag = manifest.get("web_search")
        for pdir in sorted(run.glob("scraper.*")):
            platform = pdir.name.split(".", 1)[1]
            if platform not in brd.ANSWER_FIELD:
                issues.append({"code": "UNKNOWN_PLATFORM", "dir": str(pdir)})
                continue
            retrieval_fields = RETRIEVAL_OVERRIDE.get(platform, (contract.get(platform) or {}).get("retrieval") or [])
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
                    if raw.strip():
                        digest = hashlib.sha256(json.dumps(
                            [platform, raw, task.get(brd.CITATION_FIELD.get(platform))],
                            ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                        if digest in seen:
                            issues.append({"code": "DUPLICATE_ANSWER", "file": str(path), "same_as": seen[digest]})
                            continue
                        seen[digest] = str(path)
                    status = str(payload.get("status") or "success").lower()
                    body = blank_merchant_columns(strip_citations(raw, task.get("follow_up_form")))
                    valid, _ = answer_validity(body)
                    if status != "success" or not valid:
                        continue

                    order = tbc.brands_in(body, brands)
                    retrieval = []
                    for f in retrieval_fields:
                        retrieval.extend(urls_in(task.get(f)))
                    retrieval = [u for u in retrieval if not is_platform_internal(normalize_host(u))]
                    observable = bool(retrieval_fields)
                    cited = []
                    for entry in brd._citation_entries(platform, task, raw):
                        host = entry.get("domain_hint") or ""
                        url = entry.get("raw_url") or ""
                        if host:
                            cited.append((host, url))
                    if platform in FORCED_SEARCH_PLATFORMS and web_search_flag is True:
                        grounded = "强制"
                    elif observable:
                        grounded = "是" if retrieval else "否"
                    else:
                        grounded = "不可观察"

                    def split(urls_hosts):
                        off, comp, third = [], [], []
                        for host, url in urls_hosts:
                            if official.match(host, url):
                                off.append(clean_url(url) if url else host)
                            elif any(m.match(host, url) for m in vendor_matchers.values()):
                                comp.append(clean_url(url) if url else host)
                            else:
                                third.append(clean_url(url) if url else host)
                        return off, comp, third

                    r_off, r_comp, r_third = split([(normalize_host(u), u) for u in retrieval])
                    c_off, c_comp, c_third = split(cited)
                    rec = {
                        "answer_id": hashlib.sha1(str(path).encode()).hexdigest()[:12],
                        "file": str(path), "run": run.name, "platform": platform, "region": rdir.name,
                        "question_id": qid, "grounded": grounded, "retrieval_observable": observable,
                        "official_retrieved": bool(r_off), "official_retrieved_urls": sorted(set(r_off)),
                        "competitor_site_retrieved": bool(r_comp), "third_retrieved": bool(r_third),
                        "official_cited": bool(c_off), "official_cited_urls": sorted(set(c_off)),
                        "competitor_cited_urls": sorted(set(c_comp)), "third_cited_urls": sorted(set(c_third)),
                        "has_citation": bool(cited),
                        "brands": order, "target_mentioned": target_brand["name"] in order,
                        "target_position": (order.index(target_brand["name"]) + 1) if target_brand["name"] in order else None,
                    }
                    cards = extract_product_cards(platform, task)
                    rec["cards"] = None if cards is None else len(cards)
                    if skus:
                        card_text = " ".join(f"{c.get('title') or ''} {c.get('offer_product_name') or ''}" for c in cards or [])
                        rec["sku_mentions"] = [s["name"] for s in skus if s["_re"].search(body)]
                        rec["sku_cards"] = [s["name"] for s in skus if card_text and s["_re"].search(card_text)]
                        rec["sku_retrieved"] = sorted({s["name"] for s in skus if s["_url_re"]
                                                       for u in r_off if s["_url_re"].search(u)})
                        rec["sku_cited"] = sorted({s["name"] for s in skus if s["_url_re"]
                                                   for u in c_off if s["_url_re"].search(u)})
                    answers.append(rec)

    # ---------------------------------------------------------- 汇总
    by_q_p = defaultdict(list)
    for a in answers:
        by_q_p[(a["question_id"], a["platform"])].append(a)
        by_q_p[(a["question_id"], "合并")].append(a)

    def is_named(q):
        return bool(find_alias_spans(str(q.get("user_question") or ""), target_brand["aliases"],
                                     target_brand["case_sensitive_aliases"]))

    readings, csv_rows, page_rows = [], [], []
    for q in questions:
        qid = q["question_id"]
        prio, prio_src = priority_of(q, topics, override)
        item = {"question_id": qid, "question": cd.q_text(q), "topic": q.get("topic") or q.get("topic_id") or "",
                "topic_id": q.get("topic_id") or "", "prompt_type": q.get("prompt_type") or q.get("intent") or "",
                "named": is_named(q), "priority": prio, "priority_source": prio_src,
                "constraints": q.get("constraints") or [], "sku_fit": sku_fit.get(qid) or [], "platforms": {}}
        platforms = sorted({p for (qq, p) in by_q_p if qq == qid and p != "合并"}) + ["合并"]
        for p in platforms:
            group = by_q_p.get((qid, p)) or []
            n = len(group)
            if not n:
                continue
            obs = [a for a in group if a["retrieval_observable"]]
            g_known = [a for a in group if a["grounded"] in ("是", "否")]
            brand_counts = Counter(b for a in group for b in a["brands"])
            comp = [(name, c) for name, c in brand_counts.most_common()
                    if normalize_text(name) != target_key and normalize_text(name) in same_cat]
            leader = comp[0] if comp else (None, 0)
            positions = [a["target_position"] for a in group if a["target_position"]]
            off_urls = Counter(u for a in group for u in a["official_retrieved_urls"] + a["official_cited_urls"])
            third = Counter(u for a in group for u in set(a["third_cited_urls"]))
            r = {
                "n": n,
                "grounded": dict(Counter(a["grounded"] for a in group)),
                "grounded_rate": wilson(sum(a["grounded"] == "是" for a in g_known), len(g_known)),
                "retrieval_n": len(obs),
                "official_retrieved": wilson(sum(a["official_retrieved"] for a in obs), len(obs)),
                "official_cited": wilson(sum(a["official_cited"] for a in group), n),
                "with_citation": sum(a["has_citation"] for a in group),
                "target_mention": wilson(sum(a["target_mentioned"] for a in group), n),
                "target_positions": positions,
                "leader": leader[0], "leader_mention": wilson(leader[1], n) if leader[0] else (None, None, None),
                "competitors": [{"name": nm, "mention": wilson(c, n)} for nm, c in comp],
                "other_brands": [{"name": nm, "mention": wilson(c, n)} for nm, c in brand_counts.most_common(10)
                                 if normalize_text(nm) != target_key and normalize_text(nm) not in same_cat],
                "official_page_candidates": [{"url": u, "answers": c} for u, c in off_urls.most_common(5)],
                "top_third_cited": [{"url": u, "answers": c} for u, c in third.most_common(10)],
            }
            fit = sku_fit.get(qid) or []
            if skus and fit:
                with_cards = [a for a in group if a.get("cards")]
                r["sku"] = {s: {"mention": wilson(sum(s in a.get("sku_mentions", []) for a in group), n),
                                "card": wilson(sum(s in a.get("sku_cards", []) for a in with_cards), len(with_cards)),
                                "mention_or_card": wilson(sum(s in a.get("sku_mentions", []) or s in a.get("sku_cards", [])
                                                              for a in group), n),
                                "retrieved": wilson(sum(s in a.get("sku_retrieved", []) for a in obs), len(obs)),
                                "cited": wilson(sum(s in a.get("sku_cited", []) for a in group), n)} for s in fit}
            item["platforms"][p] = r
            csv_rows.append({
                "question_id": qid, "platform": p, "topic": item["topic"], "prompt_type": item["prompt_type"],
                "named": item["named"], "priority": prio, "n": n,
                "grounded": ";".join(f"{k}:{v}" for k, v in r["grounded"].items()),
                "official_retrieved": fmt(r["official_retrieved"], len(obs)),
                "official_cited": fmt(r["official_cited"], n),
                "target_mention": fmt(r["target_mention"], n),
                "leader": r["leader"] or "", "leader_mention": fmt(r["leader_mention"], n),
            })
            if p == "合并":
                for u, c in third.most_common():
                    page_rows.append({"question_id": qid, "topic": item["topic"], "url": u, "answers": c,
                                      "answers_target_mentioned": sum(1 for a in group if u in a["third_cited_urls"]
                                                                      and a["target_mentioned"])})
        readings.append(item)

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "answers.jsonl").open("w", encoding="utf-8") as handle:
        for a in answers:
            handle.write(json.dumps(a, ensure_ascii=False) + "\n")
    meta = {"target": target_brand["name"], "target_aliases": target_brand["aliases"],
            "brands": [{"name": b["name"], "aliases": b["aliases"], "case_sensitive_aliases": b["case_sensitive_aliases"],
                        "same_category": normalize_text(b["name"]) in same_cat} for b in brands],
            "sku_map": [{k: v for k, v in s.items() if not k.startswith("_")} for s in skus],
            "official_domains": official.describe(), "lexicon": lex_status, "vendor_note": vendor_note,
            "same_category_brands": sorted(b["name"] for b in same_cat_brands),
            "runs": [str(r) for r in runs], "answers": len(answers),
            "platforms": dict(Counter(a["platform"] for a in answers)),
            "forced_search": sorted({a["platform"] for a in answers if a["grounded"] == "强制"}),
            "skus": [s["name"] for s in skus], "sku_fit_questions": len(sku_fit),
            "sku_summary": sku_summary(answers, skus, questions, is_named)}
    (args.out / "readings.json").write_text(json.dumps({"meta": meta, "questions": readings}, ensure_ascii=False,
                                                       indent=1), encoding="utf-8")
    write_csv(args.out / "readings.csv", csv_rows)
    write_csv(args.out / "cited_pages.csv", page_rows)
    (args.out / "issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
    codes = Counter(i["code"] for i in issues)
    print(f"有效回答 {len(answers)}，平台 {meta['platforms']}，题 {len(readings)}；强制联网平台 {meta['forced_search']}")
    print(f"本品 {meta['target']}，官网 {meta['official_domains']}，同类品牌 {len(same_cat_brands)} 个；{vendor_note}")
    if codes:
        print(f"问题清单 {dict(codes)}（见 issues.json）")
    unresolved = sum(v for k, v in codes.items() if k not in ("DUPLICATE_ANSWER", "QUESTIONS_CSV_SHA_MISMATCH_VERIFIED"))
    return 1 if unresolved else 0


def sku_summary(answers, skus, questions, is_named) -> dict:
    """每个 SKU 在点名题、不点名题两组回答里的进检索率、被引率、正文或商品卡提及率（不限适配题）。"""
    named = {q["question_id"] for q in questions if is_named(q)}
    out = {}
    for s in skus:
        row = {}
        for label, pick in (("不点名题", lambda a: a["question_id"] not in named),
                            ("点名题", lambda a: a["question_id"] in named)):
            group = [a for a in answers if pick(a)]
            obs = [a for a in group if a["retrieval_observable"]]
            row[label] = {"n": len(group),
                          "retrieved": wilson(sum(s["name"] in a.get("sku_retrieved", []) for a in obs), len(obs)),
                          "cited": wilson(sum(s["name"] in a.get("sku_cited", []) for a in group), len(group)),
                          "mention_or_card": wilson(sum(s["name"] in a.get("sku_mentions", []) + a.get("sku_cards", [])
                                                        for a in group), len(group))}
        out[s["name"]] = row
    return out


def fmt(w, n) -> str:
    if not n or w[0] is None:
        return "—"
    return f"{w[0]:.0%}（{round(w[0] * n)}/{n}，{w[1]:.0%}–{w[2]:.0%}）"


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
