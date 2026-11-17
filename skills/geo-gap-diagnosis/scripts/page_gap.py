#!/usr/bin/env python3
"""被引第三方页面 → 页面缺口 / 答案缺口（诊断规则断点 5、6）。

读 layer_readings.py 的输出，挑出每道题被引 ≥ --min-cites 条回答的第三方页面，抓取正文，用同一套品牌识别
（core find_alias_spans + resolve_alias_spans，品牌清单取 readings.json 的 meta.brands）看页面上有没有本品、
有几家同类竞品、有没有目标 SKU。

判定（每道题 × 页面）：
- 抓取失败 → 未知；
- 页面没提本品、提了 ≥ --min-competitors 家同类竞品 → 页面缺口；
- 页面提了本品，但引用它的回答里有没提本品的 → 答案缺口；
- 其余 → 无。

抓取：urllib，桌面浏览器 UA，超时 20 秒，正文缓存到 <out>/pages/<sha1>.txt，重跑不重抓（--refetch 强制）。
被 403、验证页拦下的页面记失败，不猜。只为页面缺口判定抓取，不入库、不转载。

用法：
    python3 -I page_gap.py --readings <readings目录> --out <输出目录> [--min-cites 2] [--min-competitors 2] [--max-pages 150]
输出：page_gap.json（每个页面的抓取状态和识别结果）、page_gap.csv（每题 × 页面一行）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for extra in (SKILLS / "geo-monitoring" / "scripts", SKILLS / "geo-metrics" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import changeability_domains as cd  # noqa: E402,F401  （把 core 加进 sys.path）
import trial_brand_count as tbc  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
BLOCK_SIGNS = ("just a moment", "attention required", "verify you are human", "access denied", "captcha")
SCRIPT = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def page_text(raw: str) -> str:
    text = SCRIPT.sub(" ", raw)
    text = TAG.sub(" ", text)
    return " ".join(html.unescape(text).split())


def fetch(url: str, cache: Path, refetch: bool) -> tuple[str, str]:
    path = cache / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
    meta = path.with_suffix(".status")
    if path.exists() and not refetch:
        return meta.read_text(encoding="utf-8") if meta.exists() else "ok", path.read_text(encoding="utf-8")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(3_000_000).decode(resp.headers.get_content_charset() or "utf-8", errors="ignore")
        text = page_text(raw)
        status = "ok"
        if len(text) < 400 or any(s in text[:2000].casefold() for s in BLOCK_SIGNS):
            status = "blocked_or_empty"
    except urllib.error.HTTPError as exc:
        status, text = f"http_{exc.code}", ""
    except Exception as exc:  # noqa: BLE001  网络错误全部记失败，不中断
        status, text = f"error_{exc.__class__.__name__}", ""
    path.write_text(text, encoding="utf-8")
    meta.write_text(status, encoding="utf-8")
    return status, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readings", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--min-cites", type=int, default=2)
    ap.add_argument("--min-competitors", type=int, default=2)
    ap.add_argument("--max-pages", type=int, default=150)
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads((args.readings / "readings.json").read_text(encoding="utf-8"))
    meta = data["meta"]
    target = meta["target"]
    brands = [dict(b, object_id=f"b{i}") for i, b in enumerate(meta["brands"])]
    same_cat = {b["name"] for b in brands if b.get("same_category")}
    skus = [dict(s, _re=re.compile(s["pattern"], re.I)) for s in meta.get("sku_map") or []]
    answers = [json.loads(line) for line in (args.readings / "answers.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]

    per_q_url = defaultdict(lambda: {"answers": 0, "target_absent": 0})
    for a in answers:
        for u in set(a["third_cited_urls"]):
            slot = per_q_url[(a["question_id"], u)]
            slot["answers"] += 1
            slot["target_absent"] += not a["target_mentioned"]
    wanted = {k: v for k, v in per_q_url.items() if v["answers"] >= args.min_cites and k[1].startswith("http")}
    urls = sorted({u for _q, u in wanted}, key=lambda u: -sum(v["answers"] for (q, uu), v in wanted.items() if uu == u))
    urls = urls[:args.max_pages]

    cache = args.out / "pages"
    cache.mkdir(parents=True, exist_ok=True)
    pages = {}
    for i, url in enumerate(urls, 1):
        status, text = fetch(url, cache, args.refetch)
        found = tbc.brands_in(text, brands) if status == "ok" else []
        pages[url] = {"status": status, "chars": len(text), "target_on_page": target in found,
                      "competitors_on_page": [b for b in found if b in same_cat and b != target],
                      "other_brands_on_page": [b for b in found if b not in same_cat and b != target],
                      "skus_on_page": [s["name"] for s in skus if status == "ok" and s["_re"].search(text)]}
        print(f"[{i}/{len(urls)}] {status} {url[:100]}", file=sys.stderr)

    rows = []
    for (qid, url), v in sorted(wanted.items()):
        p = pages.get(url)
        if not p:
            continue
        if p["status"] != "ok":
            gap = "未知"
        elif not p["target_on_page"] and len(p["competitors_on_page"]) >= args.min_competitors:
            gap = "页面缺口"
        elif p["target_on_page"] and v["target_absent"]:
            gap = "答案缺口"
        else:
            gap = "无"
        rows.append({"question_id": qid, "url": url, "answers": v["answers"],
                     "answers_target_absent": v["target_absent"], "fetch": p["status"], "gap": gap,
                     "target_on_page": p["target_on_page"], "competitors_on_page": len(p["competitors_on_page"]),
                     "gap_score": v["answers"] * len(p["competitors_on_page"]) if gap == "页面缺口" else 0,
                     "competitors": "、".join(p["competitors_on_page"]), "skus_on_page": "、".join(p["skus_on_page"])})
    (args.out / "page_gap.json").write_text(json.dumps({"params": vars(args) | {"readings": str(args.readings),
                                                                              "out": str(args.out)},
                                                         "pages": pages}, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
    with (args.out / "page_gap.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        if rows:
            w = csv.DictWriter(handle, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    ok = sum(p["status"] == "ok" for p in pages.values())
    gaps = defaultdict(int)
    for r in rows:
        gaps[r["gap"]] += 1
    print(f"页面 {len(pages)} 个，抓到 {ok} 个；题×页面 {len(rows)} 行，{dict(gaps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
