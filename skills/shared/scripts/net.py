#!/usr/bin/env python3
"""联网替代工具：WebSearch / WebFetch 经 360 网关报 400 时用（2026-10-20）。

原因：WebSearch 发 server tool `web_search_20250305`、WebFetch 发 `thinking: disabled`，
360 网关对 Claude 5 系列（opus/sonnet 槽）一律拒收（错误码 10137）。

  python3 net.py search "<query>" [--gl sg --hl en]    Google 搜索（Scrapeless，付费，每次 1 调用；同一查询有缓存）
  python3 net.py fetch <url> [--raw] [--country SG] [--proxy]
                                                        取页面正文；直连 403/挑战页时改走 Scrapeless 目标国代理（付费），再不行退到 Wayback；
                                                        --proxy 跳过直连直接走代理（Facebook 公开群帖子要这样取，直连返回 400 登录页）
  python3 net.py render <url> [--raw] [--wait 8000]     JS 渲染页：独立无头 Chrome（临时 profile，免费，不占 Suda 的浏览器）
  python3 net.py reddit <url|query> [--sub X] [--t all|year|month] [--limit 25]
                                                        Reddit 走 RSS 直连（免费）：版块/帖子 URL 取帖子与评论，否则当搜索词；
                                                        未登录约每分钟 1 次，按 x-ratelimit-reset 自动等待（.json/无头/Scrapeless 都被拦，2026-10-27 实测）

缓存目录 /tmp/hb_net_cache。Scrapeless key 读 macOS 钥匙串 SCRAPELESS_API_KEY。
"""
import hashlib, html, json, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CACHE = Path("/tmp/hb_net_cache"); CACHE.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
API = "https://api.scrapeless.com"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


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


def cacheable(data):
    """只有成功结果才可进缓存：限流/鉴权等失败（如 code 100429、100401）落盘后会把后续重试全部卡死。"""
    code = data.get("code")
    if isinstance(code, int) and code >= 400:
        return False
    return bool(data.get("organic_results"))


def search(q, gl="sg", hl="en"):
    f = CACHE / (hashlib.md5((q if gl == "sg" and hl == "en" else f"{q}|{gl}|{hl}").encode()).hexdigest() + ".json")
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            data = {}
        if not cacheable(data):
            f.unlink(missing_ok=True); data = {}  # 旧缓存里的失败结果视为未命中，重新请求
    if not cacheable(data):
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
        if cacheable(data):
            f.write_text(json.dumps(data, ensure_ascii=False))
    cites = {}
    raw = CACHE / (f.stem + ".html")
    if not raw.exists() and (data.get("metadata") or {}).get("rawUrl"):
        s, b, _ = http(data["metadata"]["rawUrl"], None, {"x-api-token": key()})
        if s == 200 and b:
            raw.write_bytes(b)
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


def fetch(url, raw=False, country="SG", proxy=False):
    s, b, _ = (0, b"", url) if proxy else http(url)
    src = f"直连 HTTP {s}"
    if proxy or blocked(s, b):
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


def render(url, raw=False, wait=8000):
    """JS 渲染页：起一个独立的无头 Chrome（临时 profile，不带登录态、不碰 Suda 的浏览器），跑完即退出。"""
    import shutil, tempfile
    prof = tempfile.mkdtemp(prefix="net-headless-")
    try:
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            f"--user-data-dir={prof}", f"--user-agent={UA}", f"--virtual-time-budget={wait}",
                            "--dump-dom", url], capture_output=True, timeout=wait / 1000 + 60)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    b = r.stdout
    if r.returncode or len(b) < 500 or blocked(200, b):
        print(f"读不到：无头 Chrome 退出码 {r.returncode}，DOM {len(b)} 字节{'，遇到挑战页' if blocked(200, b) else ''}"); return
    print(f"[来源] {url} —— 无头 Chrome 渲染（独立临时 profile）\n")
    print(b.decode("utf-8", "replace") if raw else to_text(b))


REDDIT_GATE = CACHE / "reddit_next_ok"  # 跨进程记录下一次可请求的时间，连续调用时先等再发，少撞 429


def reddit_rss_url(arg, sub=None, t="all", limit=25):
    if arg.startswith("http"):
        p = urllib.parse.urlsplit(arg)
        path = re.sub(r"/?(\.rss|\.json)?/?$", "", p.path)
        q = dict(urllib.parse.parse_qsl(p.query)); q.setdefault("limit", str(limit if "/comments/" not in path else max(limit, 100)))
        return f"https://www.reddit.com{path}/.rss?{urllib.parse.urlencode(q)}"
    q = {"q": arg, "sort": "relevance", "t": t, "limit": str(limit)}
    if sub:
        q["restrict_sr"] = "1"
        return f"https://www.reddit.com/r/{sub}/search.rss?{urllib.parse.urlencode(q)}"
    return f"https://www.reddit.com/search.rss?{urllib.parse.urlencode(q)}"


def reddit_get(url, tries=4):
    f = CACHE / ("reddit_" + hashlib.md5(url.encode()).hexdigest() + ".xml")
    if f.exists():
        return f.read_bytes()
    for _ in range(tries):
        if REDDIT_GATE.exists():
            wait = float(REDDIT_GATE.read_text() or 0) - time.time()
            if wait > 0:
                print(f"[限流] 等 {wait:.0f} 秒（x-ratelimit-reset）", file=sys.stderr); time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                s, b, hd = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            s, b, hd = e.code, e.read(), e.headers
        except Exception as e:  # noqa: BLE001
            s, b, hd = 0, str(e).encode(), {}
        reset = float(hd.get("x-ratelimit-reset") or 60)
        remaining = float(hd.get("x-ratelimit-remaining") or 0)
        REDDIT_GATE.write_text(str(time.time() + (reset + 2 if remaining < 1 else 0)))
        if s == 200 and b.lstrip().startswith(b"<?xml"):
            f.write_bytes(b); return b
        if s != 429:
            print(f"读不到：HTTP {s} {b[:200].decode('utf-8', 'replace')}"); return None
    print(f"读不到：连续 {tries} 次 429"); return None


def reddit(arg, sub=None, t="all", limit=25):
    import xml.etree.ElementTree as ET
    url = reddit_rss_url(arg, sub, t, limit)
    b = reddit_get(url)
    if not b:
        return
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = ET.fromstring(b).findall("a:entry", ns)
    thread = "/comments/" in url
    print(f"[来源] {url} —— Reddit RSS 直连，{len(entries)} 条{'（第 1 条是帖子，其余是评论，扁平无楼层/点赞）' if thread else ''}\n")
    for i, e in enumerate(entries, 1):
        get = lambda k: (e.findtext(k, "", ns) or "").strip()  # noqa: E731
        link = (e.find("a:link", ns).get("href") if e.find("a:link", ns) is not None else "")
        body = to_text(get("a:content").encode())
        body = re.sub(r"\s*(submitted by\s+/u/\S+)?\s*\[link\]\s*(\[comments\])?\s*$", "", body)
        kind = ("帖子" if i == 1 else "评论") if thread else ("帖子" if "/comments/" in link else "版块")
        print(f"{i}. [{kind}] {get('a:title') if kind != '评论' else ''}\n   {get('a:author/a:name')} · {get('a:updated')[:10]} · {link}\n   {body}\n")


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "search":
        search(arg, opt("--gl", "sg"), opt("--hl", "en"))
    elif cmd == "reddit":
        reddit(arg, opt("--sub", None), opt("--t", "all"), int(opt("--limit", "25")))
    elif cmd == "render":
        render(arg, "--raw" in sys.argv, int(opt("--wait", "8000")))
    else:
        fetch(arg, "--raw" in sys.argv, opt("--country", "SG"), "--proxy" in sys.argv)
