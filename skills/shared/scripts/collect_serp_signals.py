"""采集 Google 搜索侧的买家问法：People Also Ask、相关搜索、自动补全。

售前 Case 调研与售后生词共用。三类信号的来源：
  * PAA：每个种子词调用 1 次 Scrapeless scraper.google.search（付费），从同一次调用附带的
    原始页面 HTML 解析。Scrapeless 解析好的 JSON 不含 PAA（2026-10-15 实测）。
  * 相关搜索：同一次调用 JSON 的 related_searches。
  * 自动补全：Google 公开建议接口，不计费；从本机 IP 发出，只靠 hl/gl 指定市场，可信度记低。

默认走本脚本，不用本地浏览器：本机 IP 不在目标市场、浏览器带登录与历史会被个性化、
PAA 模块不一定渲染。本地浏览器只用于逐层展开 PAA、需登录或强反爬的社区与评价站、
以及本脚本对某个种子词失败或为空时的人工核对。

    python3 -I collect_serp_signals.py --seeds-file seeds.txt --gl us --hl en --out <目录>
    python3 -I collect_serp_signals.py "portable oxygen concentrator" --gl us --hl en --out <目录>

Key 依次读环境变量 SCRAPELESS_API_KEY、macOS 钥匙串（服务名 SCRAPELESS_API_KEY）。
<out>/raw/ 里已有某种子词的原始返回时直接复用，不重复付费；--refresh 强制重采，
--cache-only 只用缓存、不发任何付费调用。

产物（<out>/）：
  raw/<种子词>.json / .html   原始返回，作证据留存
  signals.csv                列与对客 Base「买家原话」表一致；中文意思、受众、旅程阶段、涉及品牌、月搜索量留空待人工判
                             （PAA、相关搜索、自动补全都不带搜索量；月搜索量只对 Ahrefs 等关键词工具的词填）
  summary.json               每个种子词各类信号条数与失败原因；PAA 为 0 的种子词单独列出
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://api.scrapeless.com"
CREATE_PATH = "/api/v1/scraper/request"
RESULT_PATH = "/api/v1/scraper/result/"
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
PAA_TAG = re.compile(r"<div[^>]*\brelated-question-pair\b[^>]*>")
DATA_Q = re.compile(r'\bdata-q="([^"]+)"')
FIELDS = ["输入编号", "产品线", "涉及品牌", "来源类型", "月搜索量", "原话", "中文意思", "受众", "旅程阶段",
          "约束", "来源说明", "来源链接", "收集日期", "证据可信度", "引用它的问题"]
KINDS = {"paa": ("Google People Also Ask", "中"),
         "related": ("Google 相关搜索", "中"),
         "autocomplete": ("Google 自动补全", "低")}


class Fatal(Exception):
    pass


def api_key() -> str:
    key = os.environ.get("SCRAPELESS_API_KEY", "").strip()
    if key:
        return key
    r = subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def http(method, url, payload=None, headers=None, timeout=60):
    req = urllib.request.Request(url, method=method, headers=headers or {},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, str(e).encode()


def as_json(body: bytes):
    text = body.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return {"_raw_text": text[:2000]}


def task_id(obj) -> str:
    if isinstance(obj, dict):
        for k in ("taskId", "task_id"):
            if isinstance(obj.get(k), str) and obj[k]:
                return obj[k]
        for v in obj.values():
            found = task_id(v)
            if found:
                return found
    return ""


def is_result(obj) -> bool:
    return isinstance(obj, dict) and any(k in obj for k in ("organic_results", "search_information", "metadata"))


def check_auth(status, data):
    msg = json.dumps(data, ensure_ascii=False).lower()
    if status in (401, 402, 403) or "insufficient" in msg or "invalid access token" in msg:
        raise Fatal(f"HTTP {status}：鉴权、权限或余额错误，整批停止（{msg[:160]}）")


def fetch_serp(seed, gl, hl, key, timeout):
    hdr = {"x-api-token": key, "Content-Type": "application/json"}
    body = {"actor": "scraper.google.search",
            "input": {"q": seed, "gl": gl, "hl": hl, "google_domain": "google.com"}}
    status, raw = http("POST", BASE_URL + CREATE_PATH, body, hdr)
    data = as_json(raw)
    check_auth(status, data)
    tid, deadline = task_id(data), time.monotonic() + timeout
    while status in (200, 201, 202) and not is_result(data) and tid and time.monotonic() < deadline:
        time.sleep(3)
        status, raw = http("GET", BASE_URL + RESULT_PATH + urllib.parse.quote(tid, safe=""), None, hdr)
        data = as_json(raw)
        check_auth(status, data)
    if not is_result(data):
        return None, None, f"HTTP {status}：{json.dumps(data, ensure_ascii=False)[:200]}"
    page = None
    raw_url = (data.get("metadata") or {}).get("rawUrl")
    if raw_url:
        s, b = http("GET", raw_url, None, {"x-api-token": key})
        if s == 200:
            page = b.decode("utf-8", "replace")
    return data, page, "" if page else "原始 HTML 未取到，PAA 无法解析"


def parse_paa(page) -> list[str]:
    out = []
    for tag in PAA_TAG.findall(page or ""):
        m = DATA_Q.search(tag)
        if m:
            out.append(html.unescape(m.group(1)).strip())
    return list(dict.fromkeys(q for q in out if q))


def parse_related(data) -> list[str]:
    items = (data or {}).get("related_searches") or []
    return list(dict.fromkeys(str(r.get("query")).strip() for r in items if isinstance(r, dict) and r.get("query")))


def autocomplete(seed, gl, hl):
    url = SUGGEST_URL + "?" + urllib.parse.urlencode({"client": "firefox", "hl": hl, "gl": gl, "q": seed})
    status, body = http("GET", url, timeout=20)
    if status != 200:
        return None
    try:
        arr = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None
    norm = seed.strip().lower()
    return [s for s in dict.fromkeys(arr[1]) if s.strip().lower() != norm]


def file_stem(seed: str) -> str:
    slug = re.sub(r"[^\w]+", "_", seed, flags=re.UNICODE).strip("_")[:50] or "seed"
    return f"{slug}.{hashlib.sha1(seed.encode()).hexdigest()[:8]}"


def search_link(seed, gl, hl):
    return "https://www.google.com/search?" + urllib.parse.urlencode({"q": seed, "gl": gl, "hl": hl})


def load_seeds(args) -> list[str]:
    seeds = list(args.seeds)
    if args.seeds_file:
        for line in Path(args.seeds_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                seeds.append(line)
    return list(dict.fromkeys(seeds))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seeds", nargs="*", help="种子词，可与 --seeds-file 合用")
    ap.add_argument("--seeds-file", help="每行一个种子词，# 开头为注释")
    ap.add_argument("--gl", required=True, help="市场国家代码，如 us、th")
    ap.add_argument("--hl", required=True, help="语言代码，如 en、th")
    ap.add_argument("--out", required=True, help="产物目录")
    ap.add_argument("--product-line", default="", help="写入 产品线 列")
    ap.add_argument("--id-prefix", default="S", help="输入编号前缀，避免与已有买家原话撞号")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--refresh", action="store_true", help="忽略缓存，重新付费采集")
    ap.add_argument("--cache-only", action="store_true", help="只用 raw/ 缓存，不发付费调用")
    ap.add_argument("--no-autocomplete", action="store_true")
    args = ap.parse_args()

    seeds = load_seeds(args)
    if not seeds:
        ap.error("至少给一个种子词")
    out, raw_dir = Path(args.out), Path(args.out) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    key = "" if args.cache_only else api_key()
    if not args.cache_only and not key:
        print("缺少 SCRAPELESS_API_KEY：环境变量和钥匙串里都没有", file=sys.stderr)
        return 2

    today = datetime.date.today().isoformat()
    rows, seen, per_seed, paid_calls, fatal = [], {}, [], 0, ""
    for seed in seeds:
        stem = file_stem(seed)
        jf, hf = raw_dir / f"{stem}.json", raw_dir / f"{stem}.html"
        rec = {"seed": seed, "raw": stem, "cached": False, "error": ""}
        data = page = None
        if jf.exists() and not args.refresh:
            data = json.loads(jf.read_text(encoding="utf-8")).get("response")
            page = hf.read_text(encoding="utf-8", errors="replace") if hf.exists() else None
            rec["cached"] = True
        elif args.cache_only:
            rec["error"] = "无缓存，--cache-only 未采集"
        elif not fatal:
            try:
                paid_calls += 1
                data, page, rec["error"] = fetch_serp(seed, args.gl, args.hl, key, args.timeout)
            except Fatal as e:
                fatal = rec["error"] = str(e)
            if data is not None:
                jf.write_text(json.dumps({"request": {"q": seed, "gl": args.gl, "hl": args.hl},
                                          "collected": today, "response": data}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
                if page:
                    hf.write_text(page, encoding="utf-8")
        else:
            rec["error"] = "前序鉴权或余额错误，未采集"

        found = {"paa": parse_paa(page) if data is not None else [],
                 "related": parse_related(data)}
        ac = None if args.no_autocomplete else autocomplete(seed, args.gl, args.hl)
        found["autocomplete"] = ac or []
        if ac is None and not args.no_autocomplete:
            rec["error"] = (rec["error"] + "；" if rec["error"] else "") + "自动补全接口失败"
        for kind, items in found.items():
            rec[kind] = len(items)
            label, grade = KINDS[kind]
            for text in items:
                k = (kind, text.lower())
                if k in seen:
                    seen[k]["来源说明"] += f"；另见种子词：{seed}"
                    continue
                row = dict.fromkeys(FIELDS, "")
                row.update({"产品线": args.product_line, "来源类型": "搜索数据", "原话": text,
                            "来源说明": f"{label}｜种子词：{seed}｜gl={args.gl} hl={args.hl}",
                            "来源链接": search_link(seed, args.gl, args.hl), "收集日期": today,
                            "证据可信度": grade})
                seen[k] = row
                rows.append(row)
        per_seed.append(rec)
        print(f"{seed}: PAA {rec['paa']} / 相关搜索 {rec['related']} / 自动补全 {rec['autocomplete']}"
              f"{'（缓存）' if rec['cached'] else ''}{'  ⚠ ' + rec['error'] if rec['error'] else ''}")

    for i, row in enumerate(rows, 1):
        row["输入编号"] = f"{args.id_prefix}{i:03d}"
    with (out / "signals.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = {
        "market": {"gl": args.gl, "hl": args.hl}, "collected": today, "paid_calls": paid_calls,
        "totals": {k: sum(1 for r in rows if r["来源说明"].startswith(KINDS[k][0])) for k in KINDS},
        "zero_paa_seeds": [r["seed"] for r in per_seed if not r["error"] and r["paa"] == 0],
        "failed_seeds": [{"seed": r["seed"], "error": r["error"]} for r in per_seed if r["error"]],
        "per_seed": per_seed,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n付费调用 {paid_calls} 次；去重后 {len(rows)} 条信号：{summary['totals']}")
    print(f"PAA 为 0 的种子词 {len(summary['zero_paa_seeds'])} 个：{summary['zero_paa_seeds']}")
    print(f"产物：{out / 'signals.csv'}、{out / 'summary.json'}")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
