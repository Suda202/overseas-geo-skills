#!/usr/bin/env python3
"""事实错误追出处：AI 写错的值，是官网自己写的、第三方页面写的，还是哪里都没有。

读 label_batches.py merge 后的 labels.json（`_fact_errors`），每条错误取「错误值」：标注时写了 `wrong_value` 就用它，
没写就从 quote 里抽价格、版本号、带单位的数字（旧标注没有这个字段），只留和「正确事实」同类的值
（正确事实是价格，就不追原句里顺带的分辨率）。然后去两处找这个值：
- 官网页面：facts_draft.py crawl 的缓存（--site-pages），加上 --official-pages 指定的目录；
- 这条回答引用的页面：answers.jsonl 里的官网和第三方引用 URL，正文借用 page_gap.py 的缓存（--pagegap），
  缓存里没有的直连抓一次（--no-fetch 关掉），抓不到记「未知」，不当成「没写」。

按找到的位置判原因（规则在 references/gap-cause-action-table.md 断点 8）：
- 官网自相矛盾：错误值出现在官网页面上（AI 照抄了官网某一页）；
- 第三方页面：只出现在被引的第三方页面上；
- 混淆型号：labels 里标了 `model_mixup`；或错误值正是事实表（--facts）里另一条事实的值、又不在被引第三方页上；
  或错误值在官网上出现，但命中片段里都没有被判错的那个型号（是官网别的产品的值，如 W901 Plus 套装价被安到 W702 Pro）；
- 混淆别家：labels 里标了 `other_entity`（同名或相似的另一家，标注时判）；
- 未找到出处：都没找到，被引页面和官网页面都抓全了；
- 未知：没找到，但有被引页面或官网页面没抓到（官网被限流时常见）；
- 泛值不可追：错误值太短（< 3 个字符），或在 ≥ --generic-pages（默认 5）个官网页面上都出现。
每个命中附前后 80 字的片段，语境可能相反（「not Android 14」），结论是候选，人核过再交出。

用法：
    python3 -I trace_errors.py --readings readings --labels labels/labels.json \
        --site-pages facts-draft [--pagegap pagegap] --out trace
输出：trace/trace.json（按 answer_id + quote 一条）、trace/trace.csv。diagnose.py --trace trace 读它。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from facts_draft import get, norm, page_text  # noqa: E402

VALUE_PATTERNS = [
    re.compile(r"[$€£¥]\s?\d[\d,]*(?:\.\d+)?"),                                  # 价格
    re.compile(r"\b(?:android|ios|windows|version|v)\s?\d+(?:\.\d+)*\b", re.I),   # 版本
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:nits|inch(?:es)?|in\.|\"|mah|wh|w|v|gb|tb|mm|cm|kg|lbs?|hz|fps|p|k|°c|°f|"
               r"hours?|days?|months?|years?|%)(?![a-z])", re.I),               # 带单位数字
    re.compile(r"\b\d{3,}(?:[.,]\d+)?\b"),                                       # 其他长数字（型号、邮编）
]
CAUSE_ACTION = {
    "官网自相矛盾": ("官网", "改掉官网上写错的那一页（见出处），统一成事实表的值；商品数据源、官方店一起改"),
    "第三方页面": ("第三方页面", "给出处页面的作者正确事实和官网依据，只请改事实"),
    "混淆型号": ("官网", "型号对比表、每个型号页写清规格与版本，避免相近型号互相串"),
    "混淆别家": ("官网", "关于页写清公司全称、所在地、品类，与同名或相似的公司区分开"),
    "未找到出处": ("官网", "在最接近的现有页面把这条事实写成静态正文，给 AI 一个正确来源"),
    "未知": ("待定", "先补抓没抓到的被引页面，再判出处"),
    "泛值不可追": ("待定", "错误值太泛，人工读回答原文定出处"),
}


def typed_values(text: str) -> list[tuple[int, str]]:
    out = []
    for kind, pat in enumerate(VALUE_PATTERNS):
        out += [(kind, m.group(0).strip()) for m in pat.finditer(text)]
    return out


def wrong_values(fe: dict) -> list[str]:
    if str(fe.get("wrong_value") or "").strip():
        return [str(fe["wrong_value"]).strip()]
    quote = str(fe.get("quote") or "")
    found = typed_values(quote)
    kinds = {k for k, _v in typed_values(str(fe.get("correct") or ""))}
    if kinds and any(k in kinds for k, _v in found):  # 只留和正确值同类的（正确值是价格，就不追原句里顺带的 1080p）
        found = [(k, v) for k, v in found if k in kinds]
    vals = [v for _k, v in found]
    if not vals and len(quote.strip()) <= 40:  # 短 quote 本身就是错误值（如 "$279.99"）
        vals = [quote.strip()]
    vals = list(dict.fromkeys(v for v in vals if v))
    return [v for v in vals if not any(v != o and v in o for o in vals)]  # 去掉被更长值包含的（129.99 ⊂ $129.99）


def variants(value: str) -> list[str]:
    out = [value]
    digits = re.sub(r"^[$€£¥]\s?", "", value)
    if digits != value:
        out.append(digits)
    return list(dict.fromkeys(norm(v) for v in out if v))


def find(text: str, needle: str) -> int:
    """在归一后的正文里找错误值；数字两侧不能紧挨数字、小数点或逗号（$99 不命中 $129.99）。"""
    pat = re.escape(needle)
    if needle[:1].isdigit():
        pat = r"(?<![\d.,])" + pat
    if needle[-1:].isdigit():
        pat += r"(?![\d]|[.,]\d)"
    m = re.search(pat, norm(text))
    return m.start() if m else -1


def snippet(text: str, needle: str, width: int = 80) -> str:
    t = norm(text)
    i = find(text, needle)
    if i < 0:
        return ""
    return ("…" if i > width else "") + t[max(0, i - width): i + len(needle) + width] + "…"


def fact_rows(path: Path | None) -> list[dict]:
    """facts.json（finalize 产出），或人工 facts.md 的表格行：编号 + 整行文字。"""
    if not path or not path.exists():
        return []
    js = path.with_suffix(".json")
    if js.exists():
        return [{"id": f["id"], "text": f"{f['subject']} {f['attribute']} {f['value']}", "subjects": [f["subject"]]}
                for f in json.loads(js.read_text(encoding="utf-8"))]
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(F-\d+)\s*\|([^|]*)\|(.*)", line)
        if m:  # 人工表第二列是型号，「W702 Pro / W502 Pro」「W712D、W603DS」拆开
            subjects = [x.strip() for x in re.split(r"[/、,]", m.group(2)) if x.strip()]
            rows.append({"id": m.group(1), "text": m.group(2) + m.group(3), "subjects": subjects})
    return rows


def about_subject(snip: str, subjects: list[str]) -> bool:
    """命中片段里有没有被判错的那个型号；品牌整体、空的当作有（不改判）。"""
    subs = [norm(x) for x in subjects if x and not re.search(r"品牌|brand", x, re.I)]
    return not subs or any(x in snip for x in subs)


def mixup_with(needles: list[str], basis: str, facts: list[dict]) -> list[str]:
    """错误值是事实表里另一条事实的值 → 返回那几条的编号。"""
    return [f["id"] for f in facts if f["id"] != basis and any(n and len(n) >= 3 and find(f["text"], n) >= 0
                                                              for n in needles)]


def site_failures(dirs: list[Path]) -> int:
    n = 0
    for d in dirs:
        idx = d / "pages.json"
        if idx.exists():
            n += sum(v.get("status") not in ("ok", "http_404", "http_410")  # 页面不存在不算没抓全
                     for v in json.loads(idx.read_text(encoding="utf-8")).values())
    return n


def load_dir_pages(root: Path) -> dict[str, str]:
    """facts_draft 的 pages.json + pages/，或任意目录下的 *.txt（文件名当 URL）。"""
    pages = {}
    idx = root / "pages.json"
    if idx.exists():
        for url, v in json.loads(idx.read_text(encoding="utf-8")).items():
            if v.get("status") == "ok":
                pages[url] = (root / "pages" / v["file"]).read_text(encoding="utf-8")
    else:
        for p in root.glob("*.txt"):
            pages[p.stem] = p.read_text(encoding="utf-8")
    return pages


def cited_text(url: str, pagegap: Path | None, cache: Path, fetch: bool) -> tuple[str, str]:
    sha = hashlib.sha1(url.encode()).hexdigest()
    for base in [pagegap / "pages"] if pagegap else []:
        f = base / f"{sha}.txt"
        st = base / f"{sha}.status"
        if f.exists():
            status = st.read_text(encoding="utf-8") if st.exists() else "ok"
            return status, f.read_text(encoding="utf-8")
    f, st = cache / f"{sha}.txt", cache / f"{sha}.status"
    if f.exists():
        return st.read_text(encoding="utf-8"), f.read_text(encoding="utf-8")
    if not fetch:
        return "not_fetched", ""
    status, raw = get(url)
    text = page_text(raw) if status == "ok" else ""
    if status == "ok" and len(text) < 200:
        status = "blocked_or_empty"
    f.write_text(text, encoding="utf-8")
    st.write_text(status, encoding="utf-8")
    return status, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readings", required=True, type=Path)
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--site-pages", type=Path, action="append", default=[],
                    help="facts_draft.py crawl 的输出目录，或放官网正文 *.txt 的目录；可给多个")
    ap.add_argument("--pagegap", type=Path)
    ap.add_argument("--facts", type=Path, help="facts.md（有同名 .json 时读 .json）；用来认出串了型号的错误值")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--generic-pages", type=int, default=5)
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args(argv)

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    errors = labels.get("_fact_errors") or []
    answers = {}
    for line in (args.readings / "answers.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            a = json.loads(line)
            answers[a["answer_id"]] = a
    site = {}
    for d in args.site_pages:
        site.update(load_dir_pages(d))
    facts = fact_rows(args.facts)
    site_failed = site_failures(args.site_pages)
    cache = args.out / "cited"
    cache.mkdir(parents=True, exist_ok=True)

    rows = []
    for fe in errors:
        a = answers.get(fe.get("answer_id")) or {}
        vals = wrong_values(fe)
        needles = [n for v in vals for n in variants(v)]
        kind = str(fe.get("error_type") or "")
        hits_site = {u: snippet(t, n) for u, t in site.items() for n in needles if n and find(t, n) >= 0}
        cited = list(dict.fromkeys((a.get("official_cited_urls") or []) + (a.get("third_cited_urls") or [])))
        hits_third, unfetched = {}, []
        for u in cited:
            if u in site:
                continue
            status, text = cited_text(u, args.pagegap, cache, not args.no_fetch)
            if status != "ok":
                unfetched.append(u)
                continue
            for n in needles:
                if n and find(text, n) >= 0:
                    hits_third[u] = snippet(text, n)
                    break
        official_hits = {u: s for u, s in hits_site.items()}
        official_cited = [u for u in (a.get("official_cited_urls") or []) if u in hits_third]
        for u in official_cited:
            official_hits[u] = hits_third.pop(u)
        mixed = mixup_with(needles, str(fe.get("basis") or ""), facts)
        basis_fact = next((f for f in facts if f["id"] == fe.get("basis")), None)
        other_product = bool(official_hits) and basis_fact is not None and not any(
            about_subject(snip, basis_fact["subjects"]) for snip in official_hits.values())
        if kind == "model_mixup" or (mixed and not hits_third) or other_product:
            cause = "混淆型号"
        elif kind == "other_entity":
            cause = "混淆别家"
        elif not needles or all(len(n) < 3 for n in needles) or len(hits_site) >= args.generic_pages:
            cause = "泛值不可追"
        elif official_hits:
            cause = "官网自相矛盾"
        elif hits_third:
            cause = "第三方页面"
        elif unfetched or site_failed:
            cause = "未知"
        else:
            cause = "未找到出处"
        carrier, action = CAUSE_ACTION[cause]
        rows.append({"answer_id": fe.get("answer_id"), "question_id": fe.get("question_id"),
                     "platform": fe.get("platform"), "basis": fe.get("basis"), "quote": fe.get("quote"),
                     "correct": fe.get("correct"), "wrong_values": " / ".join(vals), "cause": cause,
                     "carrier": carrier, "action": action,
                     "official_sources": list(official_hits), "third_sources": list(hits_third),
                     "snippets": {**official_hits, **hits_third}, "unfetched_cited": unfetched,
                     "same_value_facts": mixed, "site_pages_failed": site_failed,
                     "value_on_other_product": other_product,
                     "site_pages_searched": len(site)})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "trace.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with (args.out / "trace.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        cols = ["answer_id", "question_id", "platform", "basis", "quote", "correct", "wrong_values", "cause",
                "carrier", "action", "official_sources", "third_sources", "unfetched_cited"]
        w = csv.DictWriter(handle, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, **{k: " ".join(r[k]) for k in ("official_sources", "third_sources", "unfetched_cited")}})
    if not site:
        print("提醒：没给官网页面（--site-pages），「官网自相矛盾」只能从被引的官网页里判", file=sys.stderr)
    print(f"事实错误 {len(rows)} 条，官网页面 {len(site)} 个；出处 {dict(Counter(r['cause'] for r in rows))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
