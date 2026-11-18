#!/usr/bin/env python3
"""给待判域名补证据：按引用次数取前 N 个，抓首页标题与 meta 描述。

用法：
  python3 scripts/enrich_domain_candidates.py --candidates build/domain-candidates.json \
    --out build/domain-candidates.enriched.json [--top 50] [--timeout 12]

只抓 `domain` 和 `count` 字段，不判类别。判读仍按 SKILL.md 第 3 步的顺序做；
抓不到的站点保留 `fetch_error`，标成待复核，不要强行归类。
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import html
import json
import re
import ssl
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
DESC = re.compile(r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']*)', re.I)
DESC_REV = re.compile(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\'](?:og:)?description', re.I)


def _clean(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()[:limit]


def fetch(host: str, timeout: int) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    error = ""
    for scheme in ("https://", "http://"):
        try:
            req = urllib.request.Request(f"{scheme}{host}", headers={"User-Agent": UA, "Accept-Language": "en,zh;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read(300_000).decode(resp.headers.get_content_charset() or "utf-8", "ignore")
                final = resp.geturl()
            title = TITLE.search(raw)
            desc = DESC.search(raw) or DESC_REV.search(raw)
            return {"title": _clean(title.group(1) if title else "", 110),
                    "description": _clean(desc.group(1) if desc else "", 160),
                    "final_url": final}
        except Exception as exc:  # 403/超时都只是拿不到证据
            error = str(exc)[:80]
    return {"fetch_error": error}


def main() -> int:
    parser = argparse.ArgumentParser(description="待判域名补证据")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        raise SystemExit("候选清单应为列表（collect_domain_candidates.py 的输出）")
    picked = candidates[: args.top]
    results: list[dict] = []
    with futures.ThreadPoolExecutor(16) as pool:
        for item, evidence in zip(picked, pool.map(lambda c: fetch(c.get("domain", ""), args.timeout), picked)):
            results.append({**item, "evidence": evidence})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = sum(1 for r in results if "fetch_error" in r["evidence"])
    print(f"抓取 {len(results)} 个（引用次数前 {args.top}），失败 {failed} 个；输出 {args.out}")
    print("抓不到的标待复核；标题不足以判断时再打开首页或 About 页，判完写回共享缓存与 domain-categories-meta.json。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
