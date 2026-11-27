#!/usr/bin/env python3
"""品牌事实表草拟：读官网 → 模型抽事实 → 逐字校验 → 品牌方确认 → facts.md。

标注事实错误要一份「只认这些」的事实表（recommendation-labels.md）。以前靠人整理，或者干脆没有。这个脚本把
能确定的步骤做掉：抓页面、切段、校验原文、去重、标冲突、生成确认表、只用确认过的行出 facts.md。抽事实本身由模型做
（按 references/facts-extraction.md），脚本不信任模型交回的任何一句原文，逐字对不上就退回。

crawl
    从 --site 找页面：Shopify 等有 sitemap.xml 的读 sitemap（跳过 /fr/、/de-de/ 这类语言副本，--keep-locale 关掉），
    没有就读首页同域链接。按 关于/联系/政策/FAQ → 商品 → 其他页面 → 品类页 的顺序取前 --max-pages 个（默认 50），
    博客文章默认不取（--include-blogs 打开）。--url 可以追加指定页面。
    直连抓取（桌面 UA，20 秒超时，间隔 --delay 秒），按块保留换行。429 按 Retry-After 等一次再试；仍然 429、403、
    验证页、空壳的，最后统一经 shared/scripts/net.py 的 Scrapeless 代理补抓（付费，每页 1 次，--country 选节点，
    --no-proxy 关掉）。代理也拿不到的记状态，不猜。
    输出 pages.json（每页状态、字数）和 pages/<sha1>.txt（正文）。同一个目录重跑不重抓（--refetch 强制）。

prepare
    把抓到的页面按行切成 ≤ --chunk-chars（默认 6000）的段，整页不截断；写 batches/batch-NNN.jsonl，
    每行一段：chunk_id、url、text。模型按 references/facts-extraction.md 抽，交回 extracted/*.jsonl。

merge
    逐条校验模型交回的事实：quote 逐字出现在这一段里（只归一空白、大小写、弯引号）、value 出现在 quote 里、
    对象和属性非空。不合格的写 facts-rejected.jsonl。合格的按（对象、属性、值）去重、合并页面；同一对象同一属性
    有不同值的标「冲突」。输出 facts-draft.csv 交品牌方确认：确认列填 通过 / 改 / 删 / 新增，改要填改正值。

finalize
    读确认后的 facts-draft.csv，确认列有空或填错就报错退出（不默认通过）。只用确认过的行生成 facts.md（F-01 起）
    和 facts.json（trace_errors.py 用）。已有 facts.md 不覆盖，除非 --force。

用法：
    python3 -I facts_draft.py crawl    --site https://brand.com --out facts-draft [--max-pages 50] [--url …]
    python3 -I facts_draft.py prepare  --out facts-draft --brand Brand
    python3 -I facts_draft.py merge    --out facts-draft
    python3 -I facts_draft.py finalize --out facts-draft --facts <诊断目录>/facts.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
BLOCK_SIGNS = ("just a moment", "attention required", "verify you are human", "access denied", "captcha")
DROP = re.compile(r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", re.S | re.I)
BLOCK = re.compile(r"<(?:/?(?:p|div|li|ul|ol|h[1-6]|tr|td|th|table|section|article|header|footer|dt|dd|dl|"
                   r"blockquote|summary|details|figcaption|main|nav|aside|address)|br)\b[^>]*>", re.I)
TAG = re.compile(r"<[^>]+>")
LOCALE = re.compile(r"^/[a-z]{2}(?:-[a-z]{2,4})?(?:/|$)", re.I)
FIRST = re.compile(r"about|contact|faq|shipping|warranty|return|refund|terms|privacy|support|policy|policies|"
                   r"company|story|spec", re.I)
SHOPIFY_POLICIES = ("/policies/terms-of-service", "/policies/refund-policy", "/policies/shipping-policy",
                    "/policies/privacy-policy", "/pages/contact", "/pages/about-us", "/pages/faq")
CONFIRM = {"通过", "改", "删", "新增"}
COLS = ["草稿编号", "对象", "属性", "值", "原文", "页面", "可变", "冲突", "确认", "改正值", "备注"]


# ------------------------------------------------------------------ 归一与校验（merge 和 trace_errors 共用）

def norm(text: str) -> str:
    t = str(text).replace(" ", " ").replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return " ".join(t.split()).casefold()


def page_text(raw: str) -> str:
    text = DROP.sub(" ", raw)
    text = BLOCK.sub("\n", text)
    text = html.unescape(TAG.sub(" ", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


# ------------------------------------------------------------------ crawl

def get(url: str, timeout: int = 20, tries: int = 2) -> tuple[str, str]:
    """直连取页面。429 按 Retry-After 等一次（最多 60 秒）再试；还不行交给 crawl 的代理补抓，不在这里死等。"""
    for n in range(tries):
        status, raw, wait = _get_once(url, timeout)
        if status != "http_429" or n == tries - 1:
            return status, raw
        time.sleep(min(wait or 10, 60))
    return status, raw


def proxy_get(urls: list[str], country: str) -> dict[str, tuple[str, str]]:
    """直连拿不到的页面经 shared/scripts/net.py 的 Scrapeless 代理取（付费，每页 1 次，不开 JS，5 路并发）。"""
    shared = Path(__file__).resolve().parents[2] / "shared" / "scripts"
    sys.path.insert(0, str(shared))
    try:
        import net  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return {u: (f"proxy_unavailable_{exc.__class__.__name__}", "") for u in urls}
    from concurrent.futures import ThreadPoolExecutor

    def one(u):
        try:
            head, body = net.get(u, country=country, proxy=True)
        except Exception as exc:  # noqa: BLE001
            return u, (f"proxy_error_{exc.__class__.__name__}", "")
        return u, ("ok", body.decode("utf-8", "replace")) if body else (f"proxy_failed：{head[:120]}", "")

    with ThreadPoolExecutor(5) as ex:
        return dict(ex.map(one, urls))


def _get_once(url: str, timeout: int) -> tuple[str, str, float]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4_000_000).decode(resp.headers.get_content_charset() or "utf-8", errors="ignore")
        return "ok", raw, 0
    except urllib.error.HTTPError as exc:
        retry = exc.headers.get("Retry-After") if exc.headers else None
        return f"http_{exc.code}", "", float(retry) if retry and retry.isdigit() else 0
    except Exception as exc:  # noqa: BLE001  网络错误记状态，不中断
        return f"error_{exc.__class__.__name__}", "", 0


def locs(xml: str) -> list[str]:
    return [html.unescape(u.strip()) for u in re.findall(r"<loc>(.*?)</loc>", xml, re.S)]


def discover(site: str, keep_locale: bool, include_blogs: bool) -> tuple[list[str], str]:
    base = site.rstrip("/")
    host = urllib.parse.urlparse(base).netloc
    status, xml = get(base + "/sitemap.xml")
    urls, how = [], ""
    if status == "ok" and "<loc>" in xml:
        how = "sitemap"
        seen = set()
        children = locs(xml)
        if "<sitemapindex" in xml:
            for child in children:
                path = urllib.parse.urlparse(child).path
                if not keep_locale and LOCALE.match(path):
                    continue
                if not include_blogs and re.search(r"blogs|articles", path):
                    continue
                if child in seen:
                    continue
                seen.add(child)
                st, sub = get(child)
                if st == "ok":
                    urls.extend(locs(sub))
        else:
            urls = children
    else:
        status, raw = get(base + "/")
        how = "首页链接"
        for href in re.findall(r'href="([^"#]+)"', raw):
            u = urllib.parse.urljoin(base + "/", html.unescape(href))
            if urllib.parse.urlparse(u).netloc == host:
                urls.append(u.split("?")[0])
    clean = []
    for u in urls:
        p = urllib.parse.urlparse(u)
        if p.netloc != host or re.search(r"\.(jpe?g|png|gif|webp|pdf|svg|css|js|xml)$", p.path, re.I):
            continue
        if not keep_locale and LOCALE.match(p.path):
            continue
        if not include_blogs and re.search(r"/blogs?/|/articles?/|/news/", p.path):
            continue
        clean.append(u)
    if "sitemap_products" in xml:  # Shopify：政策页不在 sitemap 里
        clean.extend(base + p for p in SHOPIFY_POLICIES)
    return list(dict.fromkeys([base + "/"] + clean)), how


def rank(url: str) -> int:
    path = urllib.parse.urlparse(url).path
    if path in ("", "/"):
        return 0
    if FIRST.search(path):
        return 1
    if "/products/" in path:
        return 2
    if "/collections/" in path:
        return 4
    return 3


def cmd_crawl(args) -> int:
    out = args.out
    cache = out / "pages"
    cache.mkdir(parents=True, exist_ok=True)
    found, how = discover(args.site, args.keep_locale, args.include_blogs) if args.site else ([], "只用 --url")
    found = sorted(found, key=lambda u: (rank(u), found.index(u)))[:args.max_pages]
    urls = list(dict.fromkeys(found + list(args.url)))
    index_path = out / "pages.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    for i, url in enumerate(urls, 1):
        path = cache / (key(url) + ".txt")
        if (index.get(url, {}).get("status") == "ok" and path.exists() and not args.refetch) \
                or index.get(url, {}).get("status", "").startswith("proxy_"):  # 直连已被拦过，直接留给代理
            continue
        if i > 1:
            time.sleep(args.delay)
        status, raw = get(url)
        text = page_text(raw) if status == "ok" else ""
        if status == "ok" and (len(text) < 200 or any(s in text[:2000].casefold() for s in BLOCK_SIGNS)):
            status = "blocked_or_empty"
        path.write_text(text, encoding="utf-8")
        index[url] = {"status": status, "chars": len(text), "file": path.name}
        print(f"[{i}/{len(urls)}] {status} {len(text)} {url[:100]}", file=sys.stderr)
    retry = [u for u in urls if index[u]["status"] in ("http_429", "http_403", "blocked_or_empty")
             or index[u]["status"].startswith(("error_", "proxy_"))]  # 上次代理也失败的，重跑时再试代理
    if retry and not args.no_proxy:
        print(f"直连没拿到 {len(retry)} 页（限流、403、验证页、空壳），改走 Scrapeless {args.country} 代理补抓（付费，每页 1 次）",
              file=sys.stderr)
        for url, (status, raw) in proxy_get(retry, args.country).items():
            text = page_text(raw) if status == "ok" else ""
            if status == "ok" and (len(text) < 200 or any(s in text[:2000].casefold() for s in BLOCK_SIGNS)):
                status = "blocked_or_empty"
            path = cache / (key(url) + ".txt")
            path.write_text(text, encoding="utf-8")
            index[url] = {"status": status, "chars": len(text), "file": path.name,
                          "via": "proxy", "direct": index[url]["status"]}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(v["status"] == "ok" for v in index.values())
    via = sum(v.get("via") == "proxy" and v["status"] == "ok" for v in index.values())
    print(f"找页面：{how}；共 {len(index)} 页，抓到 {ok} 页（其中代理补抓 {via} 页），仍失败 {len(index) - ok} 页（不猜）")
    return 0


# ------------------------------------------------------------------ prepare

def load_pages(out: Path) -> dict:
    index = json.loads((out / "pages.json").read_text(encoding="utf-8"))
    return {u: (out / "pages" / v["file"]).read_text(encoding="utf-8") for u, v in index.items() if v["status"] == "ok"}


def chunks_of(text: str, limit: int) -> list[str]:
    parts, cur = [], ""
    for line in text.splitlines():
        while len(line) > limit:  # 单行超长才硬切，整页不截断
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts


def cmd_prepare(args) -> int:
    pages = load_pages(args.out)
    bdir = args.out / "batches"
    bdir.mkdir(parents=True, exist_ok=True)
    for old in bdir.glob("batch-*.jsonl"):
        old.unlink()
    rows = []
    for url, text in pages.items():
        for n, part in enumerate(chunks_of(text, args.chunk_chars), 1):
            rows.append({"chunk_id": f"{key(url)[:10]}-{n:02d}", "url": url, "brand": args.brand, "text": part})
    for b in range(0, len(rows), args.batch_size):
        path = bdir / f"batch-{b // args.batch_size + 1:03d}.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows[b:b + args.batch_size]) + "\n",
                        encoding="utf-8")
    (args.out / "extracted").mkdir(exist_ok=True)
    print(f"{len(pages)} 页切成 {len(rows)} 段，{-(-len(rows) // args.batch_size)} 个批次；"
          f"按 references/facts-extraction.md 抽，交回 {args.out / 'extracted'}/*.jsonl")
    return 0


# ------------------------------------------------------------------ merge

def cmd_merge(args) -> int:
    chunks = {}
    for path in sorted((args.out / "batches").glob("batch-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                chunks[r["chunk_id"]] = r
    facts, rejected = {}, []
    for path in sorted((args.out / "extracted").glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append({"file": path.name, "line": n, "reason": f"JSON 解析失败：{exc}"})
                continue
            chunk = chunks.get(rec.get("chunk_id"))
            if not chunk:
                rejected.append({"file": path.name, "line": n, "reason": "批次里没有这个 chunk_id"})
                continue
            body = norm(chunk["text"])
            for fact in rec.get("facts") or []:
                subject, attr = str(fact.get("subject") or "").strip(), str(fact.get("attribute") or "").strip()
                value, quote = str(fact.get("value") or "").strip(), str(fact.get("quote") or "").strip()
                why = ("对象、属性、值或原文有空" if not (subject and attr and value and quote)
                       else "原文在这一段里找不到（逐字）" if norm(quote) not in body
                       else "值不在原文里" if norm(value) not in norm(quote) else "")
                if why:
                    rejected.append({"file": path.name, "line": n, "chunk_id": chunk["chunk_id"], "url": chunk["url"],
                                     "fact": fact, "reason": why})
                    continue
                k = (subject.casefold(), attr.casefold(), norm(value))
                slot = facts.setdefault(k, {"对象": subject, "属性": attr, "值": value, "原文": quote, "页面": [],
                                            "可变": bool(fact.get("volatile"))})
                slot["页面"].append(chunk["url"])
                slot["可变"] = slot["可变"] or bool(fact.get("volatile"))
    by_attr = defaultdict(set)
    for (s, a, v), f in facts.items():
        by_attr[(s, a)].add(f["值"])
    rows = []
    for i, ((s, a, _v), f) in enumerate(sorted(facts.items()), 1):
        others = sorted(by_attr[(s, a)] - {f["值"]})
        rows.append({"草稿编号": f"D-{i:03d}", "对象": f["对象"], "属性": f["属性"], "值": f["值"], "原文": f["原文"],
                     "页面": " ".join(dict.fromkeys(f["页面"])), "可变": "是" if f["可变"] else "",
                     "冲突": ("官网另有写法：" + " / ".join(others)) if others else "", "确认": "", "改正值": "", "备注": ""})
    with (args.out / "facts-draft.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    with (args.out / "facts-rejected.jsonl").open("w", encoding="utf-8") as handle:
        for r in rejected:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    pending = sorted(set(chunks) - {json.loads(x).get("chunk_id") for p in (args.out / "extracted").glob("*.jsonl")
                                    for x in p.read_text(encoding="utf-8").splitlines() if x.strip().startswith("{")})
    conflicts = sum(bool(r["冲突"]) for r in rows)
    print(f"事实 {len(rows)} 条（冲突 {conflicts} 条），退回 {len(rejected)} 条，未交回的段 {len(pending)} 个；"
          f"确认表：{args.out / 'facts-draft.csv'}")
    return 0


# ------------------------------------------------------------------ finalize

def cmd_finalize(args) -> int:
    rows = list(csv.DictReader((args.out / "facts-draft.csv").open(encoding="utf-8-sig")))
    bad = [r.get("草稿编号") or f"第 {i} 行" for i, r in enumerate(rows, 2) if r.get("确认", "").strip() not in CONFIRM]
    bad += [r["草稿编号"] for r in rows if r.get("确认", "").strip() == "改" and not r.get("改正值", "").strip()]
    bad += [r.get("草稿编号") or "新增行" for r in rows
            if r.get("确认", "").strip() == "新增" and not all(r.get(c, "").strip() for c in ("对象", "属性", "值"))]
    if bad:
        print(f"确认表没填完，不生成：{len(bad)} 行确认列为空、填错，或「改」没写改正值、「新增」缺对象属性值："
              f"{'、'.join(bad[:20])}{'…' if len(bad) > 20 else ''}", file=sys.stderr)
        return 2
    if args.facts.exists() and not args.force:
        print(f"{args.facts} 已存在，不覆盖；确认要替换加 --force", file=sys.stderr)
        return 2
    kept = []
    for r in rows:
        c = r["确认"].strip()
        if c == "删":
            continue
        value = r["改正值"].strip() if c == "改" else r["值"].strip()
        basis = ("品牌方提供：" + (r.get("备注") or "").strip()) if c == "新增" else \
            f"{r['页面'].split()[0]}「{r['原文']}」" + ("（品牌方改正）" if c == "改" else "")
        kept.append({"subject": r["对象"].strip(), "attribute": r["属性"].strip(), "value": value,
                     "volatile": r.get("可变", "").strip() == "是", "urls": (r.get("页面") or "").split(),
                     "quote": r.get("原文", ""), "basis": basis, "confirm": c, "draft_id": r.get("草稿编号", "")})
    for i, f in enumerate(kept, 1):
        f["id"] = f"F-{i:02d}"
    lines = [f"# 品牌事实表（标注用，{len(kept)} 条）", "",
             f"由 `facts_draft.py` 从官网抽取、逐字校验，经品牌方逐条确认（{args.out / 'facts-draft.csv'}）。只有本表的"
             "事实能用来判 AI 写错；表里没有的记「待核事实」。可变的事实（价格、库存、数量）按 recommendation-labels.md "
             "的时间规则判。", "", "| 编号 | 对象 | 属性 | 事实 | 可变 | 依据 |", "|---|---|---|---|---|---|"]
    lines += [f"| {f['id']} | {f['subject']} | {f['attribute']} | {f['value']} | {'是' if f['volatile'] else ''} | "
              f"{f['basis'].replace('|', '/')} |" for f in kept]
    args.facts.parent.mkdir(parents=True, exist_ok=True)
    args.facts.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.facts.with_suffix(".json").write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"facts.md {len(kept)} 条（删 {sum(r['确认'].strip() == '删' for r in rows)} 条）→ {args.facts}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("crawl")
    p.add_argument("--site")
    p.add_argument("--url", action="append", default=[])
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-pages", type=int, default=50)
    p.add_argument("--keep-locale", action="store_true")
    p.add_argument("--include-blogs", action="store_true")
    p.add_argument("--refetch", action="store_true")
    p.add_argument("--delay", type=float, default=2.0, help="两次直连请求间隔秒数")
    p.add_argument("--country", default="US", help="代理补抓用的节点国家，填目标市场")
    p.add_argument("--no-proxy", action="store_true", help="直连拿不到的不走付费代理补抓")
    p = sub.add_parser("prepare")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--brand", required=True)
    p.add_argument("--chunk-chars", type=int, default=6000)
    p.add_argument("--batch-size", type=int, default=8)
    p = sub.add_parser("merge")
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("finalize")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--facts", required=True, type=Path)
    p.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "crawl" and not (args.site or args.url):
        ap.error("crawl 要 --site 或 --url")
    return {"crawl": cmd_crawl, "prepare": cmd_prepare, "merge": cmd_merge, "finalize": cmd_finalize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
