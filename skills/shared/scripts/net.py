#!/usr/bin/env python3
"""联网替代工具：WebSearch / WebFetch 经 360 网关报 400 时用（2026-10-20）。

原因：WebSearch 发 server tool `web_search_20250305`、WebFetch 发 `thinking: disabled`，
360 网关对 Claude 5 系列（opus/sonnet 槽）一律拒收（错误码 10137）。

  python3 net.py search "<query>" [--gl sg --hl en]    Google 搜索（Scrapeless，付费，每次 1 调用；同一查询有缓存）
  python3 net.py fetch <url> [--raw] [--country SG]     取页面正文；直连 403/挑战页时改走 Scrapeless 目标国代理（付费），再不行退到 Wayback

缓存目录 /tmp/hb_net_cache。Scrapeless key 读 macOS 钥匙串 SCRAPELESS_API_KEY。
"""
import hashlib, html, json, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CACHE = Path("/tmp/hb_net_cache"); CACHE.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
API = "https://api.scrapeless.com"


def key():
    return subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                          capture_output=True, text=True).stdout.strip()


def http(url, data=None, headers=None, timeout=60):
    h = {"User-Agent": UA, "Accept-Language": "en-SG,en;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=h,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read(), url
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode(), url


def search(q, gl="sg", hl="en"):
    f = CACHE / (hashlib.md5((q if gl == "sg" and hl == "en" else f"{q}|{gl}|{hl}").encode()).hexdigest() + ".json")
    if f.exists():
        data = json.loads(f.read_text())
    else:
        k = key(); hdr = {"x-api-token": k, "Content-Type": "application/json"}
        s, b, _ = http(API + "/api/v1/scraper/request", {"actor": "scraper.google.search",
                       "input": {"q": q, "gl": gl, "hl": hl, "google_domain": "google.com"}}, hdr)
        data = json.loads(b or b"{}")
        tid = data.get("taskId") or data.get("task_id")
        end = time.time() + 90
        while tid and not data.get("organic_results") and time.time() < end:
            time.sleep(3)
            s, b, _ = http(API + "/api/v1/scraper/result/" + tid, None, hdr)
            data = json.loads(b or b"{}")
        f.write_text(json.dumps(data, ensure_ascii=False))
    cites = {}
    raw = CACHE / (f.stem + ".html")
    if not raw.exists() and (data.get("metadata") or {}).get("rawUrl"):
        s, b, _ = http(data["metadata"]["rawUrl"], None, {"x-api-token": key()})
        raw.write_bytes(b if s == 200 else b"")
    page = raw.read_text("utf-8", "replace") if raw.exists() else ""
    for r in data.get("organic_results") or []:
        i = page.find(">" + html.escape(r.get("title") or "", quote=False) + "</h3>")
        m = re.search(r"<cite[^>]*>(.*?)</cite>", page[i:i + 4000]) if i >= 0 else None
        cites[r.get("position")] = re.sub(r"<[^>]+>", "", html.unescape(m.group(1))).replace(" › ", "/") if m else r.get("source")
    for i, r in enumerate(data.get("organic_results") or [], 1):
        print(f"{i}. {r.get('title')}\n   {cites.get(r.get('position'))}（Google 显示的网址路径，可能被截断；以打开后的页面为准）\n   {r.get('snippet') or ''}\n")
    if not data.get("organic_results"):
        print("无结果：", json.dumps(data, ensure_ascii=False)[:300])


def to_text(b):
    t = b.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<(br|p|div|li|h[1-6]|tr|option)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t)).strip()


def blocked(s, b):
    return s in (0, 403, 429, 503) or b"cf-chl" in b[:20000] or b"Just a moment" in b[:20000]


def fetch(url, raw=False, country="SG"):
    s, b, _ = http(url)
    src = f"直连 HTTP {s}"
    if blocked(s, b):
        hdr = {"x-api-token": key(), "Content-Type": "application/json"}
        for js in (False, True):
            s3, b3, _ = http(API + "/api/v1/unlocker/request", {"actor": "unlocker.webunlocker", "proxy": {"country": country},
                             "input": {"url": url, "method": "GET", "redirect": True, "js_render": js}}, hdr, timeout=150)
            try:
                body = json.loads(b3).get("data") or ""
            except Exception:  # noqa: BLE001
                body = ""
            if s3 == 200 and len(body) > 2000 and not blocked(200, body.encode()):
                print(f"[来源] {url} —— 直连被拦，经 Scrapeless {country} 代理取得（js_render={js}）\n")
                print(body if raw else to_text(body.encode())); return
        s2, b2, final = http("https://web.archive.org/web/2026id_/" + url, timeout=90)
        m = re.search(r"/web/(\d{8})", final)
        if s2 == 200 and not blocked(s2, b2):
            s, b, src = s2, b2, f"直连被拦，改用 Wayback 快照 {m.group(1) if m else '日期未知'}（{final}）"
        else:
            print(f"读不到：直连 HTTP {s}，Wayback HTTP {s2}"); return
    print(f"[来源] {url} —— {src}\n")
    print(b.decode("utf-8", "replace") if raw else to_text(b))


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "search":
        search(arg, opt("--gl", "sg"), opt("--hl", "en"))
    else:
        fetch(arg, "--raw" in sys.argv, opt("--country", "SG"))
