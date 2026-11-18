#!/usr/bin/env python3
"""试跑答案 → 每道题的可改变性预判。

脚本只做预判，档位由人复核后才算数。做法：

1. 读题库 bank.json 和一个或多个试跑采集目录（collect_answers.py 产出的
   ``scraper.<平台>/<市场>/<NNNN>.json``）。每个含 ``scraper.*`` 子目录的目录算一次试跑；
   给的是上层目录时，往下找出所有这样的目录（跳过 ``_collector``）。同平台正文与引用字段完全相同的
   回答只算一次（``html-report/collect`` 这类镜像目录会让次数翻倍）。
2. 文件归到题：NNNN 是采集用 CSV 的行号（manifest 里的 ``questions_file``）。CSV 采集后被改过
   （sha256 对不上）时，行数不变且本批所有回显题面都和 CSV 同行一致才继续用，否则这批不用 CSV。
   依次用：CSV 行的 ``question_id``（题面与题库一致时）→ 回答回显的题面 → CSV 行的题面 → 文件名就是题号。
   题面和当前题库对不上的文件不计：改过措辞的题重跑，不沿用旧读数。题库 region 能对成两位市场代码时，
   必须和采集目录的市场一致。
3. 取引用：只数正文引用，不数 search_result 这类检索候选。直接复用售前报告数据层
   ``geo-presales-report-builder/scripts/build_report_data.py`` 的 ``_citation_entries``：
   带 ``cited_count`` 的新格式按供应商次数计；字段里一条 ``cited_count`` 都没有的旧格式（10-10 及更早的
   ChatGPT、部分 AIO）回退数正文引用标记，Gemini / AIO 旧格式的伪拆分按同一套规则折叠；Alexa 数
   ``{ref cite_…}``。逐个回答判代数，不按日期。正文字段用同一模块的 ``ANSWER_FIELD``，
   失败页判定用 core 的 ``answer_validity``。
4. 每道题跨所有平台、所有试跑次数汇总，子域名归到注册域名（``blog.x.com`` 算 ``x.com``；
   ``hdb.gov.sg`` 这类国家二级后缀下的站保留到机构一级）。
5. 定档（Suda 2026-11-13 审核版，默认只优化官网，全自动）：规则在 ``summarize`` 的说明和
   geo-monitoring/references/baseline-report.md「可改变性」。要点：品类错位 → 低；主约束相对竞品明显劣势 → 低；
   有引用的回答不到 4 条 → 不判；同类竞品官网被引的回答比例领先本品 ≥40 个百分点且多 ≥3 条 → 高；
   引了厂商官网的有引用回答 <40% → 低（第三方主导）；其余 → 中。只用于发现、替代、问题解决；点名本品的类型不适用。
   同类品牌和竞品官网读 ``--lexicon`` 的 ``same_category``。不到 7 条有效回答只算预判。
6. 官网＋社区占全部被引的比例（``official_share_reference``）和前 20 域名照样输出，只作参考，不参与定档。

域名参数的写法：不带 ``/`` 按域名比（含子域名），带 ``/`` 按「主机+路径前缀」比，例如
``reddit.com/r/yourbrand``、``amazon.com/stores/YourBrand``——这样品牌自己的版块算社区，Reddit 其余帖子仍是难影响。
品牌官网 = ``config.official_domain`` ∪ ``--official``；竞品官网 = 题库 config 里竞品条目的 domain /
official_domain ∪ ``--competitor-domain``（只用于参考占比和前 20 标注）；定档比差距用的同类竞品官网另读词表（第 5 条）。

输出（``--out`` 目录）：``changeability.csv``（每题一行）、``changeability.json``（每题完整明细、
分平台回答数与引用格式、归题问题清单）。默认只预览；``--write`` 才把建议档和一句依据写回题库的
``changeability`` / ``changeability_basis``，打了需人工标记的题不写；题库里已有高/中/低的题默认不覆盖，
要覆盖加 ``--overwrite``。写回前把原题库复制一份到 ``--out/bank.before-write.json``。

用法：
    python3 -I changeability_domains.py --bank <bank.json> --collect <试跑目录> [<试跑目录> …] \\
        --out <输出目录> --lexicon <品牌词表.json> [--official brand.cn] [--competitor-domain rival.com …] \\
        [--community-domain reddit.com/r/yourbrand …] [--third-party] [--write [--overwrite]]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

SKILLS = Path(__file__).resolve().parents[2]
CORE = SKILLS / "geo-metrics" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

# 统计口径全部来自 geo-metrics core；2026-11-18 前经由售前报告的 build_report_data 绕进来
from geo_presales_core import citations as brd  # noqa: E402  （沿用 brd 名：_citation_entries 等都在这里）
from geo_presales_core.crawler import ANSWER_FIELD, answer_validity  # noqa: E402
from geo_presales_core.runs import (  # noqa: E402,F401  （下游脚本仍按 cd.Resolver 等名字用）
    REGION_CODE, Matcher, Resolver, competitor_domains, find_runs, load_bank, load_vendor_brands,
    q_region_code, q_text, run_questions_csv)
from geo_presales_core.util import normalize_host, normalize_text, registrable_domain  # noqa: E402

TOP_N = 20
PENDING = {"", "待试跑", None}



# ------------------------------------------------------------------ 域名

def reg_domain(host: str) -> str:
    """注册域名：统一走 core（含 x.co.th 这类国家二级后缀、多租户平台）。"""
    return registrable_domain(host)


def is_gov(domain: str) -> bool:
    from geo_presales_core.sources import is_government
    return is_government(normalize_host(domain))


def is_wiki(domain: str) -> bool:
    from geo_presales_core.sources import is_wiki as core_is_wiki
    return core_is_wiki(normalize_host(domain))


# ------------------------------------------------------------------ 题库

# ------------------------------------------------------------------ 采集目录

# ------------------------------------------------------------------ 主流程

def classify(host: str, url: str, official: Matcher, competitor: Matcher, community: Matcher):
    if official.match(host, url):
        return "官网", "品牌官网"
    if competitor.match(host, url):
        return "官网", "竞品官网"
    if community.match(host, url):
        return "社区", "品牌社区"
    return "难影响", ""


def collect(args, questions, official, competitor, community, vendors=None, brands=None, cache=None):
    resolver = Resolver(questions)
    runs = find_runs(args.collect)
    issues: list[dict] = []
    seen_hashes: dict[str, str] = {}
    per_q = {q["question_id"]: {"answers": Counter(), "valid": Counter(), "format": Counter(),
                                "domains": Counter(), "unresolved": 0, "files": [], "per_answer": []}
             for q in questions}
    for run in runs:
        rows, _csv = run_questions_csv(run, issues)
        for pdir in sorted(run.glob("scraper.*")):
            platform = pdir.name.split(".", 1)[1]
            if platform not in ANSWER_FIELD:
                issues.append({"code": "UNKNOWN_PLATFORM", "dir": str(pdir)})
                continue
            for rdir in sorted(p for p in pdir.iterdir() if p.is_dir()):
                region = rdir.name
                for path in sorted(rdir.glob("*.json")):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        issues.append({"code": "BAD_JSON", "file": str(path)})
                        continue
                    task = payload.get("task_result") or {}
                    # 去重按回答内容，不按文件字节：build_baseline_html 的 html-report/collect 是补了题面的
                    # 镜像副本，字节不同、回答相同。空正文（AIO 未触发）不参与去重，它本来就不计引用。
                    body = str(task.get(ANSWER_FIELD[platform]) or "")
                    digest = None
                    if body.strip():
                        digest = hashlib.sha256(json.dumps(
                            [platform, body, task.get(brd.CITATION_FIELD.get(platform))],
                            ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                        if digest in seen_hashes:
                            issues.append({"code": "DUPLICATE_ANSWER", "file": str(path),
                                           "same_as": seen_hashes[digest]})
                            continue
                    echo = str(task.get("prompt") or task.get("user_query") or task.get("user_text") or "").strip()
                    qid, method, code = resolver.resolve(echo, rows.get(path.stem), path.stem, region)
                    if not qid:
                        issues.append({"code": code, "file": str(path),
                                       "prompt": (echo or (rows.get(path.stem) or {}).get("query") or "")[:100]})
                        continue
                    if digest:
                        seen_hashes[digest] = str(path)  # 归上题才登记，免得没归上的原件挡掉能归上的镜像
                    if method == "filename":
                        issues.append({"code": "FILENAME_FALLBACK", "file": str(path), "question_id": qid})
                    slot = per_q[qid]
                    slot["answers"][platform] += 1
                    status = str(payload.get("status") or "success").lower()
                    text = body
                    valid, _ = answer_validity(text)
                    if status != "success" or not valid:
                        continue
                    slot["valid"][platform] += 1
                    slot["files"].append(str(path))
                    if platform == "alexa":
                        slot["format"]["alexa_ref"] += 1
                    elif brd._cited_count_entries(platform, task) is not None:
                        slot["format"]["cited_count"] += 1
                    else:
                        slot["format"]["body_marker"] += 1
                    rec = {"file": str(path), "platform": platform, "cited": False, "vendors": set(),
                           "pages": [], "third": Counter(), "same_category": None}
                    for entry in brd._citation_entries(platform, task, text):
                        host = entry.get("domain_hint") or ""
                        url = entry.get("raw_url") or ""
                        if not host:
                            slot["unresolved"] += 1
                            continue
                        rec["cited"] = True
                        cls, sub = classify(host, url, official, competitor, community)
                        dom = reg_domain(host)
                        slot["domains"][(dom, cls, sub)] += 1
                        owner = "本品" if (official.match(host, url) or community.match(host, url)) else None
                        if owner is None:
                            owner = next((name for name, m in (vendors or {}).items() if m.match(host, url)), None)
                        if owner:
                            rec["vendors"].add(owner)
                            if owner != "本品" and url:
                                rec["pages"].append((owner, url.split("?")[0]))
                        else:
                            rec["third"][third_party_type(host, cache)] += 1
                    if brands:  # 一个同类品牌都不认识时不判品类门槛（same_category 留 None）
                        rec["same_category"] = same_category_mentioned(text, task, brands)
                    slot["per_answer"].append(rec)
    return runs, per_q, issues


NAMED_TYPES = {"Evaluation", "Competitor", "Trust", "Transactional", "Support"}
BRAND_LIST_TYPES = {"Discovery", "Alternatives"}
THIRD_LABEL = {"media_review": "媒体评测", "ugc": "社区", "institutional": "机构与百科",
               "press_release": "新闻稿", "other": "其他网站"}


def third_party_type(host: str, cache) -> str:
    from geo_presales_core.sources import classify_source
    verdict = classify_source(normalize_host(host), {"domain_category_cache": cache or {}})
    t = verdict["source_type"]
    return t if t in THIRD_LABEL else "other"


def same_category_mentioned(text: str, task: dict, brands: list[dict]) -> bool:
    """去引用正文里有没有提到任何同类品牌（含本品）。识别口径同 trial_brand_count。"""
    from de_cite_crawl import blank_merchant_columns, strip_citations
    from geo_presales_core.util import find_alias_spans
    body = blank_merchant_columns(strip_citations(text, task.get("follow_up_form")))
    return any(find_alias_spans(body, b["aliases"], b["case_sensitive_aliases"]) for b in brands)


def summarize(q: dict, slot: dict, rules: dict, weak_attrs: dict) -> dict:
    """可改变性：默认只优化官网时，改官网能不能改变这道题（Suda 2026-11-13 审核版）。

    按顺序判，命中即定档：
    1 品类错位（只用于发现、替代题）：同类品牌（含本品）被提到的回答 < category_min → 低
    2 硬规格劣势：题目挂的约束条件在约束条件表里「相对竞品」= 明显劣势 → 低
    3 有引用的回答 < min_cited → 不判（引用样本不足）
    4 官网差距：有引用的回答里，某家同类竞品官网被引的比例 − 本品官网 ≥ gap，且多出的回答 ≥ gap_answers → 高
    5 第三方主导：有引用的回答里，引了任一同类厂商官网（含本品）的 < vendor_min → 低
      （--third-party 开时，媒体、社区为主的改判中；机构为主仍是低）
    6 其余 → 中
    点名本品的类型（评估、对比、信任、交易、售后）不适用。有效回答少于 formal_answers 时只算预判。
    """
    ranked = sorted(slot["domains"].items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
    top = ranked[:TOP_N]  # 只用于展示和人工复核
    total_all = sum(slot["domains"].values())
    oc_cites = sum(n for (d, cls, _), n in ranked if cls in ("官网", "社区"))
    share_c = oc_cites / total_all if total_all else None
    answers = slot["per_answer"]
    valid = len(answers)
    cited = [a for a in answers if a["cited"]]
    n_cited = len(cited)
    ptype = str(q.get("prompt_type") or q.get("intent") or "").strip()

    def rate(pred, pool):
        return sum(1 for a in pool if pred(a)) / len(pool) if pool else 0.0

    own_rate = rate(lambda a: "本品" in a["vendors"], cited)
    comp_rates = {}
    for a in cited:
        for v in a["vendors"] - {"本品"}:
            comp_rates[v] = comp_rates.get(v, 0) + 1
    comp_counts = dict(comp_rates)
    comp_rates = {k: v / n_cited for k, v in comp_rates.items()} if n_cited else {}
    # 并列时按名字取，结果可复现（2026-11-18 前用 max 取 set 遍历顺序里的第一个，同一份数据两次跑出不同竞品）
    top_comp, top_comp_rate = (min(comp_rates.items(), key=lambda kv: (-kv[1], kv[0]))
                               if comp_rates else ("", 0.0))
    own_count = sum(1 for a in cited if "本品" in a["vendors"])
    gap_answers = comp_counts.get(top_comp, 0) - own_count
    vendor_rate = rate(lambda a: bool(a["vendors"]), cited)
    same_known = [a for a in answers if a["same_category"] is not None]
    same_rate = rate(lambda a: a["same_category"], same_known) if same_known else None
    third = Counter()
    for a in cited:
        third.update(a["third"])
    third_main = min(third.items(), key=lambda kv: (-kv[1], kv[0]))[0] if third else ""
    pages = Counter(url for a in cited for owner, url in a["pages"] if owner == top_comp)
    attr = str(q.get("attribute_ref") or "").strip()
    # 次数门槛按 7 次基线定；试跑回答少时按比例缩（3 次试跑：有引用 ≥2 条、多 ≥2 条），结果只算预判
    scale = min(1.0, valid / rules["formal_answers"]) if valid else 1.0
    min_cited = max(2, round(rules["min_cited"] * scale))
    need_gap = max(2, round(rules["gap_answers"] * scale))

    tier, step, reason = None, "", ""
    if not valid:
        step, reason = "无数据", "没有有效回答"
    elif ptype in NAMED_TYPES:
        step, reason = "不适用", f"{ptype} 题题面点名本品，这套规则不适用"
    elif ptype in BRAND_LIST_TYPES and same_rate is not None and same_rate < rules["category_min"]:
        tier, step = "低", "品类错位"
        reason = f"同类品牌只在 {same_rate:.0%} 的回答里出现，AI 按另一类产品回答"
    elif attr and weak_attrs.get(attr):
        tier, step = "低", "硬规格劣势"
        reason = f"主约束「{attr}」相对竞品明显劣势：{weak_attrs[attr]}"
    elif n_cited < min_cited:
        step, reason = "引用样本不足", f"有引用的回答只有 {n_cited} 条（少于 {min_cited}）"
    elif top_comp_rate - own_rate >= rules["gap"] and gap_answers >= need_gap:
        tier, step = "高", "官网差距"
        reason = (f"{top_comp} 官网在 {top_comp_rate:.0%} 的有引用回答里被引，本品官网 {own_rate:.0%}"
                  f"（多 {gap_answers} 次回答）")
    elif vendor_rate < rules["vendor_min"]:
        main = THIRD_LABEL.get(third_main, "第三方")
        if rules["third_party"] and third_main in ("media_review", "ugc"):
            tier, step = "中", "第三方主导（已购第三方信源）"
        else:
            tier, step = "低", "第三方主导"
        reason = f"只有 {vendor_rate:.0%} 的有引用回答引了厂商官网，主要引{main}"
    else:
        tier, step = "中", "官网常被引"
        reason = (f"厂商官网在 {vendor_rate:.0%} 的有引用回答里被引；本品 {own_rate:.0%}"
                  + (f"，{top_comp} {top_comp_rate:.0%}" if top_comp else "") + "，差距不到门槛")
    stage = "正式" if valid >= rules["formal_answers"] else f"预判（{valid} 次回答）"

    domains = []
    for rank, ((d, cls, sub), n) in enumerate(top, 1):
        tag = "政府" if is_gov(d) else "百科" if is_wiki(d) else ""
        domains.append({"rank": rank, "domain": d, "class": cls, "detail": sub or tag, "citations": n})
    return {
        "question_id": q["question_id"], "user_question": q_text(q), "prompt_type": ptype,
        "region": q.get("region"),
        "answers_valid": valid, "answers_cited": n_cited, "answers_by_platform": dict(slot["valid"]),
        "citation_format": dict(slot["format"]),
        "citations_all": total_all, "citations_unresolved": slot["unresolved"],
        "domains_all": len(slot["domains"]),
        "same_category_rate": same_rate, "own_site_rate": own_rate, "top_competitor": top_comp,
        "top_competitor_rate": top_comp_rate, "vendor_site_rate": vendor_rate,
        "third_party_main": THIRD_LABEL.get(third_main, ""), "attribute_ref": attr,
        "official_share_reference": share_c,
        "suggested": tier, "step": step, "reason": reason, "stage": stage,
        "flag": "" if tier else step,
        "current": q.get("changeability"), "current_basis": q.get("changeability_basis"),
        "top_competitor_pages": [u for u, _ in sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
        "top20": domains,
        "answer_files": slot["files"],
    }


def label(item: dict) -> str:
    return item["domain"] + ("(品牌账号)" if item["class"] == "社区" else "")


def basis_sentence(r: dict) -> str:
    text = f"{r['suggested']}（{r['step']}）：{r['reason']}"
    if r["step"] == "官网差距" and r["top_competitor_pages"]:
        text += "；竞品被引页面：" + "、".join(r["top_competitor_pages"][:2])
    return text + f"。{r['stage']}，脚本判"


def pct(v):
    return "" if v is None else f"{v * 100:.0f}%"


def write_outputs(out: Path, results: list, meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    (out / "changeability.json").write_text(
        json.dumps({"meta": meta, "questions": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    headers = ["question_id", "prompt_type", "region", "answers_valid", "answers_cited", "answers_by_platform",
               "suggested", "step", "stage", "reason", "same_category_rate", "own_site_rate", "top_competitor",
               "top_competitor_rate", "vendor_site_rate", "third_party_main", "attribute_ref",
               "official_share_reference", "citations_all", "citation_format", "current", "basis_preview",
               "top_competitor_pages", "top20_domains", "user_question"]
    with (out / "changeability.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=headers)
        w.writeheader()
        for r in results:
            w.writerow({
                **{k: r.get(k) for k in headers if k in r},
                "answers_by_platform": " ".join(f"{k}={v}" for k, v in sorted(r["answers_by_platform"].items())),
                "citation_format": " ".join(f"{k}={v}" for k, v in sorted(r["citation_format"].items())),
                **{k: pct(r[k]) for k in ("same_category_rate", "own_site_rate", "top_competitor_rate",
                                          "vendor_site_rate", "official_share_reference")},
                "suggested": r["suggested"] or "",
                "top_competitor_pages": " ".join(r["top_competitor_pages"]),
                "basis_preview": basis_sentence(r) if r["suggested"] else "",
                "top20_domains": "; ".join(
                    f"{i['domain']}[{i['class']}{'/' + i['detail'] if i['detail'] else ''}] {i['citations']}"
                    for i in r["top20"]),
            })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bank", type=Path, required=True, help="题库 bank.json")
    ap.add_argument("--collect", type=Path, nargs="+", required=True, help="试跑采集目录（可多个，或其上层目录）")
    ap.add_argument("--out", type=Path, required=True, help="输出目录")
    ap.add_argument("--official", nargs="*", default=[], help="品牌官网 / 转化渠道页（与 config.official_domain 合并）")
    ap.add_argument("--competitor-domain", nargs="*", default=[], help="竞品官网（与题库 config 竞品域名合并）")
    ap.add_argument("--community-domain", nargs="*", default=[], help="品牌发帖的社区、另买的信源服务")
    ap.add_argument("--lexicon", type=Path, default=None,
                    help="品牌词表：同类品牌标 same_category: true（目标和配置竞品默认同类），用于品类门槛和竞品官网")
    ap.add_argument("--third-party", action="store_true", help="品牌方已购第三方信源：媒体、社区主导的题判中")
    ap.add_argument("--category-min", type=float, default=0.20, help="同类品牌提及率低于此值判品类错位（默认 0.20，7 次里最多 1 次）")
    ap.add_argument("--gap", type=float, default=0.40, help="竞品官网被引回答比例领先本品至少此值判高（默认 0.40，7 次里约多 3 次）")
    ap.add_argument("--gap-answers", type=int, default=3, help="官网差距还要求竞品多被引的回答数至少此值（默认 3，防止有引用回答少时 2 次就够）")
    ap.add_argument("--vendor-min", type=float, default=0.40, help="引了厂商官网的有引用回答低于此值判第三方主导（默认 0.40）")
    ap.add_argument("--min-cited", type=int, default=4, help="有引用的回答少于此数不判档（默认 4）")
    ap.add_argument("--formal-answers", type=int, default=7, help="有效回答少于此数只算预判（默认 7，即正式基线）")
    ap.add_argument("--write", action="store_true", help="把建议档和依据写回 bank.json")
    ap.add_argument("--overwrite", action="store_true", help="配合 --write：覆盖题库里已有的高/中/低")
    args = ap.parse_args(argv)

    raw, bank, questions = load_bank(args.bank)
    config = bank.get("config") or {}
    official_values = list(dict.fromkeys(
        [config.get("official_domain")] + list(config.get("official_domains") or []) + list(args.official)))
    if not any(official_values):
        raise SystemExit("题库 config.official_domain 为空，用 --official 给品牌官网域名")
    official = Matcher(official_values)
    competitor_values = competitor_domains(config) + list(args.competitor_domain)
    if args.lexicon:
        # 竞品与本品同口径：配置竞品在词表里登记的全部域名都算，不只 config 里那一个
        lex = json.loads(Path(args.lexicon).read_text(encoding="utf-8"))
        for b in lex.get("brands") or []:
            if str(b.get("type") or "").startswith("competitor"):
                competitor_values += [d for d in (b.get("domains") or b.get("official_domains") or []) if d]
    competitor = Matcher(list(dict.fromkeys(competitor_values)))
    community = Matcher(args.community_domain)

    vendors, brands, lex_note = load_vendor_brands(config, args.lexicon)
    from geo_presales_core.sources import load_cache
    runs, per_q, issues = collect(args, questions, official, competitor, community, vendors, brands, load_cache())
    rules = {"category_min": args.category_min, "gap": args.gap, "gap_answers": args.gap_answers, "vendor_min": args.vendor_min,
             "min_cited": args.min_cited, "formal_answers": args.formal_answers, "third_party": args.third_party}
    weak = {a.get("attribute"): (a.get("vs_competitors_basis") or "明显劣势")
            for a in config.get("attribute_plan") or [] if a.get("vs_competitors") == "明显劣势"}
    results = [summarize(q, per_q[q["question_id"]], rules, weak) for q in questions]
    meta = {
        "bank": str(args.bank), "runs": [str(r) for r in runs],
        "official": official.describe(), "competitor": competitor.describe(), "community": community.describe(),
        "rules": rules, "lexicon": str(args.lexicon or ""), "lexicon_note": lex_note,
        "same_category_brands": [b["name"] for b in brands], "vendor_sites": sorted(vendors),
        "issues": issues,
    }
    write_outputs(args.out, results, meta)

    print(f"试跑目录 {len(runs)} 个；官网 {', '.join(official.describe())}；竞品 {', '.join(competitor.describe()) or '无'}；"
          f"社区 {', '.join(community.describe()) or '无'}")
    print(f"规则：品类错位 <{args.category_min:.0%}、官网差距 ≥{args.gap:.0%}、厂商官网 <{args.vendor_min:.0%} 判第三方主导、"
          f"有引用回答 <{args.min_cited} 不判；第三方信源{'已购' if args.third_party else '未购（默认只优化官网）'}")
    if lex_note:
        print(lex_note)
    codes = Counter(i["code"] for i in issues)
    if codes:
        print("归题问题：" + "、".join(f"{k} {v}" for k, v in codes.most_common()))
    print()
    print(f"{'题号':<16}{'回答':>4}{'有引':>4}  建议  现值  依据")
    for r in results:
        print(f"{r['question_id']:<16}{r['answers_valid']:>4}{r['answers_cited']:>4}  {r['suggested'] or '—':<4}"
              f"{str(r['current'] or '—'):<5} {r['step']}：{r['reason']}（{r['stage']}）")
    print(f"\n（* = 官网；输出：{args.out / 'changeability.csv'}、{args.out / 'changeability.json'}）")

    if not args.write:
        print("预览模式，未改题库；加 --write 写回。")
        return 0

    backup = args.out / "bank.before-write.json"
    shutil.copy2(args.bank, backup)
    written, skipped = [], []
    by_id = {r["question_id"]: r for r in results}
    for q in questions:
        r = by_id[q["question_id"]]
        if not r["suggested"]:
            skipped.append((q["question_id"], r["flag"] or "无建议档"))
            continue
        if q.get("changeability") not in PENDING and not args.overwrite:
            skipped.append((q["question_id"], f"已有「{q.get('changeability')}」，未加 --overwrite"))
            continue
        q["changeability"] = r["suggested"]
        q["changeability_basis"] = basis_sentence(r)
        written.append(q["question_id"])
    indent = 2
    lines = raw.splitlines()
    if len(lines) > 1:
        stripped = lines[1].lstrip(" ")
        indent = (len(lines[1]) - len(stripped)) or None
    tail = "\n" if raw.endswith("\n") else ""
    args.bank.write_text(json.dumps(bank, ensure_ascii=False, indent=indent) + tail, encoding="utf-8")
    print(f"已写回 {len(written)} 题：{'、'.join(written) or '无'}；原题库备份 {backup}")
    for qid, why in skipped:
        print(f"  未写 {qid}：{why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
