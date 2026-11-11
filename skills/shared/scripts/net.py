#!/usr/bin/env python3
"""联网替代工具：WebSearch / WebFetch 经 360 网关报 400 时用（2026-10-20）。

原因：WebSearch 发 server tool `web_search_20250305`、WebFetch 发 `thinking: disabled`，
360 网关对 Claude 5 系列（opus/sonnet 槽）一律拒收（错误码 10137）。

  python3 net.py search "<query>" [--gl sg --hl en]    Google 搜索（Scrapeless，付费，每次 1 调用；同一查询有缓存）
  python3 net.py fetch <url> [<url> ...] [--urls-file F] [--jobs 5] [--raw] [--country SG] [--proxy] [--fresh]
                                                        取页面正文；直连（15 秒超时）403/挑战页时改走 Scrapeless 目标国代理（付费，不开 JS，1 次），
                                                        再不行退到 Wayback；--country 填目标市场（默认 SG，节点不对常取不到）；
                                                        --proxy 跳过直连直接走代理（Facebook 公开群帖子要这样取，直连返回 400 登录页）；
                                                        Facebook、X、Instagram、Threads、HardwareZone 和 7 天内直连被拦过的域名自动跳过直连；
                                                        多个 URL 并发取（--jobs，默认 5），按输入顺序输出；
                                                        成功结果按 URL 缓存，--fresh 跳过缓存并重新试直连
  python3 net.py pantip <帖子 URL> [--country TH]          Pantip 帖子的标题、主帖和评论（含前 5 条回复）：本机能直连时调评论接口（免费），
                                                        境内模式或直连失败时经 Scrapeless 网页代理 v2 的 JS 渲染取（每帖 1 次付费，约 17 秒）；
                                                        不需要本机 Chrome。帖子链接先用 net.py search "pantip <词>" 搜
  python3 net.py render <url> [--raw] [--wait 8000] [--country US]  JS 渲染页（本机没有 Chrome 或境内模式时改经 Scrapeless 代理取）：独立无头 Chrome（临时 profile，免费，不占 Suda 的浏览器）
  python3 net.py reddit <url|query> [--sub X] [--t all|year|month] [--limit 25] [--proxy]
                                                        Reddit 走 RSS 直连（免费）：版块/帖子 URL 取帖子与评论，否则当搜索词；
                                                        未登录约每分钟 1 次，按 x-ratelimit-reset 自动等待（.json/无头/Scrapeless 都被拦，2026-10-27 实测）；
                                                        设了环境变量 NET_REDDIT_MAX 时联网请求到上限就停（线上选词默认 10 次）
                                                        --proxy：RSS 读不到（403）时改取帖子网页版（Scrapeless 代理，每帖 1 次付费），
                                                        从 <shreddit-comment> 解析作者、点赞、日期、正文；只给帖子 URL 有用，搜索词不支持
                                                        （Reddit 搜索页经代理也被拦，搜索走 net.py search ''reddit <词>'' 拿帖子链接）

缓存目录 /tmp/hb_net_cache，环境变量 NET_CACHE_DIR 可改（线上 runner 设成工作目录的 logs/net_cache，按轮数付费请求）。Scrapeless key 先读环境变量 SCRAPELESS_API_KEY（服务器上用），没有再读 macOS 钥匙串同名项。
render 用的 Chrome 默认是 macOS 路径，服务器上用环境变量 CHROME_PATH 指定。

境内模式（环境变量 GEO_NET_DOMESTIC=1，境内服务器没有海外直连时用）：只连 api.scrapeless.com。
fetch 不试直连、不试 Wayback，直接走 Scrapeless 代理；reddit 的 RSS 不发请求，打印「读不到」由调用方记进未覆盖来源；render 改经代理不开 JS 取；
reddit --proxy 的帖子网页版照常经 Scrapeless 代理取。不设就是原来的行为。
"""
import hashlib, html, json, os, re, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("NET_CACHE_DIR", "").strip() or "/tmp/hb_net_cache"); CACHE.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
# 厂商接口地址可改（3.6.4）：平台有自己的网关时把 SCRAPELESS_BASE_URL 指过去，网关注入密钥，本机可以不放 key
API_DEFAULT = "https://api.scrapeless.com"
API = (os.environ.get("SCRAPELESS_BASE_URL", "").strip() or API_DEFAULT).rstrip("/")
CHROME = os.environ.get("CHROME_PATH") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DOMESTIC = os.environ.get("GEO_NET_DOMESTIC", "").strip().lower() in ("1", "true", "yes", "on")

def gateway_headers() :
    """研发网关要求的额外请求头（环境变量 GEO_GATEWAY_HEADERS，JSON 对象），只加在发给厂商接口的请求上。"""
    try:
        h = json.loads(os.environ.get("GEO_GATEWAY_HEADERS", "") or "{}")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in h.items()} if isinstance(h, dict) else {}


def vendor(h):
    """发给 Scrapeless 的请求头：本机 key（有就带）+ 网关额外头。"""
    return {**h, **gateway_headers()}


def key():
    value = os.environ.get("SCRAPELESS_API_KEY", "").strip()
    if value:
        return value
    try:
        return subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                              capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:  # 非 macOS 没有 security 命令
        return ""


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


def search_cache_file(q, gl="sg", hl="en"):
    return CACHE / (hashlib.md5((q if gl == "sg" and hl == "en" else f"{q}|{gl}|{hl}").encode()).hexdigest() + ".json")


def search_text(q, gl="sg", hl="en"):
    """Google 搜索（Scrapeless），返回 (打印文本, 原始返回)。"""
    f = search_cache_file(q, gl, hl)
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            data = {}
        if not cacheable(data):
            f.unlink(missing_ok=True); data = {}  # 旧缓存里的失败结果视为未命中，重新请求
    if not cacheable(data):
        k = key(); hdr = vendor({"x-api-token": k, "Content-Type": "application/json"})
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
        s, b, _ = http(data["metadata"]["rawUrl"].replace(API_DEFAULT, API, 1), None, vendor({"x-api-token": key()}))
        if s == 200 and b:
            raw.write_bytes(b)
    page = raw.read_text("utf-8", "replace") if raw.exists() else ""
    for r in data.get("organic_results") or []:
        i = page.find(">" + html.escape(r.get("title") or "", quote=False) + "</h3>")
        m = re.search(r"<cite[^>]*>(.*?)</cite>", page[i:i + 4000]) if i >= 0 else None
        cites[r.get("position")] = re.sub(r"<[^>]+>", "", html.unescape(m.group(1))).replace(" › ", "/") if m else r.get("source")
    out = []
    for i, r in enumerate(data.get("organic_results") or [], 1):
        link = f"\n   链接：{r['link']}" if r.get("link") else ""  # 完整网址（线上 precollect 按这一行取站内页）
        out.append(f"{i}. {r.get('title')}\n   {cites.get(r.get('position'))}（Google 显示的网址路径，可能被截断；以打开后的页面为准）{link}\n   {r.get('snippet') or ''}\n")
    if not data.get("organic_results"):
        out.append("无结果：" + json.dumps(data, ensure_ascii=False)[:300])
    return "\n".join(out) + "\n", data


def search(q, gl="sg", hl="en"):
    text, _ = search_text(q, gl, hl)
    print(text, end="")


def to_text(b):
    t = b.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<(br|p|div|li|h[1-6]|tr|option)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t)).strip()


def blocked(s, b):
    return s in (0, 403, 429, 503) or b"cf-chl" in b[:20000] or b"Just a moment" in b[:20000]


DENIED = re.compile(r"(?i)access denied|attention required|are you a robot|captcha|request blocked|403 forbidden")


def usable_proxy_body(body):
    """代理取回的正文能不能用。短正文多半是拦截页，所以原来只收 2000 字符以上；接口返回的 JSON（HN、自动补全）
    本来就短，按开头的 { [ 放行。境内模式所有页面都走代理，正常的短页面（example.com 577 字符）也要放行，
    只拦开头写着拒绝或人机验证的。"""
    if not body or blocked(200, body.encode()):
        return False
    if body.lstrip()[:1] in ("{", "[") or len(body) > 2000:
        return True
    return DOMESTIC and len(to_text(body.encode())) >= 50 and not DENIED.search(body[:3000])


DIRECT_TIMEOUT = 15  # 直连超时的站不必等满 60 秒再进代理
BLOCK_FILE = CACHE / "blocked_domains.json"  # 直连被拦过的域名 → 时间戳；BLOCK_DAYS 天内同域名跳过直连
BLOCK_DAYS = 7
# 本机直连必然不通的站（community-channels.md 2026-10-27 实测：直连超时或返回登录页），直接走代理
KNOWN_BLOCKED = ("facebook.com", "x.com", "twitter.com", "instagram.com", "threads.net", "threads.com",
                 "hardwarezone.com.sg")
_block_lock = threading.Lock()


def host(url):
    h = (urllib.parse.urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def known_blocked(h):
    """命中默认名单或 BLOCK_DAYS 天内直连被拦过时，返回原因；否则 None。"""
    if any(h == d or h.endswith("." + d) for d in KNOWN_BLOCKED):
        return "默认名单"
    try:
        t = json.loads(BLOCK_FILE.read_text()).get(h)
    except Exception:  # noqa: BLE001
        t = None
    if t and time.time() - t < BLOCK_DAYS * 86400:
        return f"{time.strftime('%m-%d', time.localtime(t))} 直连被拦过"
    return None


def remember_blocked(h):
    with _block_lock:
        try:
            d = json.loads(BLOCK_FILE.read_text())
        except Exception:  # noqa: BLE001
            d = {}
        d[h] = time.time()
        tmp = BLOCK_FILE.with_name(f"{BLOCK_FILE.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(d)); os.replace(tmp, BLOCK_FILE)


def get(url, country="SG", proxy=False, fresh=False):
    """取一个页面，返回 (说明行, 正文字节或 None)，不打印，便于并发。

    顺序：缓存 → 直连（15 秒；默认名单和 7 天内被拦过的域名跳过）→ Scrapeless 代理（不开 JS，1 次付费）→ Wayback。
    2026-11-09 实测被拦页面：直连约 1 秒；代理不开 JS 13–46 秒能取到；代理开 JS 没有一次比不开好，已去掉；
    无头渲染在被拦页面上 3/3 超时（68 秒），所以不在这条链里，只用于直连 200 但正文是 JS 空壳的页面。
    --fresh 跳过缓存，也不看被拦域名记录、重新试直连。
    """
    f = CACHE / ("fetch_" + hashlib.md5(url.encode()).hexdigest() + ".json")
    if not fresh and f.exists():
        try:
            c = json.loads(f.read_text())
            return f"[来源] {url} —— {c['src']}（缓存 {c['at']}）", c["body"].encode()
        except Exception:  # noqa: BLE001
            f.unlink(missing_ok=True)
    h = host(url)
    skip = "境内模式" if DOMESTIC else None if (proxy or fresh) else known_blocked(h)
    if proxy or skip:
        s, b = 0, b""
        direct = "按 --proxy 跳过直连" if proxy else f"跳过直连（{skip}）"
    else:
        s, b, _ = http(url, timeout=DIRECT_TIMEOUT)
        direct = f"直连 HTTP {s}"
    src = direct
    if proxy or skip or blocked(s, b):
        if not (proxy or skip):
            remember_blocked(h)
        hdr = vendor({"x-api-token": key(), "Content-Type": "application/json"})
        # 境内模式代理是唯一通道，偶发失败（2026-11-11 实测 HN 接口一次失败、重取即成）多试一次
        for _ in range(2 if DOMESTIC else 1):
            s3, b3, _ = http(API + "/api/v1/unlocker/request", {"actor": "unlocker.webunlocker", "proxy": {"country": country},
                             "input": {"url": url, "method": "GET", "redirect": True, "js_render": False}}, hdr, timeout=150)
            try:
                body = json.loads(b3).get("data") or ""
            except Exception:  # noqa: BLE001
                body = ""
            if s3 == 200 and usable_proxy_body(body):
                break
        if s3 == 200 and usable_proxy_body(body):
            s, b, src = 200, body.encode(), f"{direct}，经 Scrapeless {country} 代理取得"
        elif DOMESTIC:
            return f"读不到：{url} —— {direct}，Scrapeless {country} 代理 HTTP {s3}（正文 {len(body)} 字符），境内模式不试 Wayback", None
        else:
            s2, b2, final = http("https://web.archive.org/web/2026id_/" + url, timeout=90)
            m = re.search(r"/web/(\d{8})", final)
            if s2 == 200 and not blocked(s2, b2):
                s, b, src = s2, b2, f"{direct}，改用 Wayback 快照 {m.group(1) if m else '日期未知'}（{final}）"
            else:
                return (f"读不到：{url} —— {direct}，Scrapeless {country} 代理 HTTP {s3}（正文 {len(body)} 字符），"
                        f"Wayback HTTP {s2}"), None
    if s == 200 and src.startswith("直连") and len(to_text(b)) < 500:
        return (f"[提示] 直连只取到 {len(to_text(b))} 字符，可能是 JS 渲染页，改用 net.py render {url}\n"
                f"[来源] {url} —— {src}"), b
    if s == 200:
        f.write_text(json.dumps({"src": src, "at": time.strftime("%Y-%m-%d %H:%M"), "body": b.decode("utf-8", "replace")},
                                ensure_ascii=False))
    return f"[来源] {url} —— {src}", b


def fetch(urls, raw=False, country="SG", proxy=False, fresh=False, jobs=5):
    """一个或多个 URL；多个时并发取（默认 5 路），按输入顺序输出。"""
    from concurrent.futures import ThreadPoolExecutor

    def one(u):
        try:
            return get(u, country, proxy, fresh)
        except Exception as e:  # noqa: BLE001
            return f"读不到：{u} —— {type(e).__name__}: {e}", None

    with ThreadPoolExecutor(max(1, min(jobs, len(urls)))) as ex:
        results = list(ex.map(one, urls))
    for i, (u, (head, b)) in enumerate(zip(urls, results), 1):
        if len(urls) > 1:
            print(f"\n===== {i}/{len(urls)} {u}")
        print(head)
        if b is not None:
            print()
            print(b.decode("utf-8", "replace") if raw else to_text(b))
    if len(urls) > 1:
        print(f"\n===== 共 {len(urls)} 个，取到 {sum(b is not None for _, b in results)} 个")


def render(url, raw=False, wait=8000, country="US"):
    """JS 渲染页：起一个独立的无头 Chrome（临时 profile，不带登录态、不碰 Suda 的浏览器），跑完即退出。
    本机没有 Chrome（平台服务器）或境内模式时（3.6.4），改经 Scrapeless 网页代理不开 JS 取：2026-11-11 实测 RTINGS
    这样能取到正文（开 JS 渲染反而报 frame detached），GlobalSources 两种都被 AWS WAF 拦。"""
    import shutil, tempfile
    if DOMESTIC or not Path(CHROME).exists():
        why = "境内模式" if DOMESTIC else "本机没有 Chrome"
        head, b = get(url, country, True)
        if b is None or len(to_text(b)) < 500:
            print(f"读不到：{url} —— {why}，改走 Scrapeless 代理也没取到正文（{head[:120]}）"); return
        print(f"[来源] {url} —— {why}不用无头 Chrome，改经 Scrapeless {country} 代理取得（不开 JS）\n")
        print(b.decode("utf-8", "replace") if raw else to_text(b)); return
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


def reddit_budget_ok():
    """线上限量：设了 NET_REDDIT_MAX 时，计数文件 NET_REDDIT_COUNTER（默认缓存目录下）里的联网请求数到上限就不再发。
    缓存命中不计数。本地不设就不限。"""
    mx = os.environ.get("NET_REDDIT_MAX", "").strip()
    if not mx:
        return True
    cf = Path(os.environ.get("NET_REDDIT_COUNTER") or CACHE / "reddit_calls")
    try:
        n = int(cf.read_text() or 0)
    except Exception:  # noqa: BLE001
        n = 0
    if n >= int(mx):
        return False
    cf.write_text(str(n + 1)); return True


def reddit_get(url, tries=4):
    f = CACHE / ("reddit_" + hashlib.md5(url.encode()).hexdigest() + ".xml")
    if f.exists():
        return f.read_bytes()
    if not reddit_budget_ok():
        print(f"读不到：本次 Reddit 请求已达上限 {os.environ['NET_REDDIT_MAX']} 次（NET_REDDIT_MAX），"
              f"不再请求，这个来源记进未覆盖来源"); return None
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


REDDIT_COMMENT = re.compile(r'<shreddit-comment\s([^>]*)>(.*?)(?=<shreddit-comment\s|</shreddit-comment-tree>|$)', re.S)


def reddit_html_items(body):
    """从 Reddit 网页版 HTML 里取评论：返回 [(作者, 点赞, 日期, 链接, 正文)]，按页面顺序（顶层评论在前）。

    2026-11-11 实测：网页版经 Scrapeless 代理能取到（RSS 当天 403），每条评论的 <shreddit-comment> 带
    author / score / created / permalink，正文在 slot="comment" 里。页面上折叠的「N more replies」取不到，
    一个帖子大约拿到 20–25 条顶层评论。"""
    out = []
    for m in REDDIT_COMMENT.finditer(body):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        b = re.search(r'slot="comment">(.*?)</div>\s*</div>', m.group(2), re.S)
        if not b:
            continue
        t = re.sub(r"(?i)</p>|</li>|<br\s*/?>", "\n", b.group(1))
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        if not t or t in ("[deleted]", "[removed]"):
            continue
        link = a.get("permalink", "")
        out.append((a.get("author", ""), a.get("score", ""), a.get("created", "")[:10],
                    f"https://www.reddit.com{link}" if link.startswith("/") else link, t))
    return out


def reddit_proxy(url, country="US"):
    """帖子网页版：RSS 读不到时用。每帖 1 次 Scrapeless 付费请求。"""
    head, b = get(url, country, True)
    if b is None:
        print(head); return
    items = reddit_html_items(b.decode("utf-8", "replace"))
    if not items:
        print(f"读不到：{url} —— 网页版没有评论（可能整帖被删）"); return
    print(f"[来源] {url} —— Reddit 网页版，{len(items)} 条评论（经 Scrapeless {country} 代理，每帖 1 次付费请求；"
          f"折叠的回复和主帖正文取不到，主帖标题看 URL，正文用 --proxy 之外的通道或直接读原帖）\n")
    for i, (author, score, date, link, body) in enumerate(items, 1):
        print(f"{i}. [评论] \n   /u/{author} · {score} 赞 · {date} · {link}\n   {body}\n")


def reddit(arg, sub=None, t="all", limit=25, proxy=False):
    import xml.etree.ElementTree as ET
    if proxy:
        if not arg.startswith("http"):
            print("读不到：--proxy 只支持帖子 URL（Reddit 搜索页经代理也被拦，先用 net.py search 'reddit <词>' 拿帖子链接）"); return
        reddit_proxy(arg); return
    if DOMESTIC:
        print("读不到：境内模式不取 Reddit RSS（本机连不上 reddit.com）；给帖子 URL 加 --proxy 走 Scrapeless 代理"); return
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


PANTIP_TOPIC = re.compile(r"pantip\.com/topic/(\d+)")


def _pantip_render_js(tid):
    """在 Pantip 帖子页里请求评论接口（要带 X-Requested-With，代理不转发自定义请求头，只能在页面里发），
    把标题、主帖和评论 JSON 写进页面，渲染结果以纯文本取回。"""
    return ("(()=>{const o={title:document.title,story:''};const s=document.querySelector('.display-post-story');"
            "if(s)o.story=s.innerText;"
            f"fetch('/forum/topic/render_comments?tid={tid}&param=&type=3',{{headers:{{'X-Requested-With':'XMLHttpRequest'}}}})"
            ".then(r=>r.text()).then(t=>{o.comments=t}).catch(e=>{o.error=String(e)}).finally(()=>{"
            "document.body.innerHTML='';const p=document.createElement('pre');p.id='geo-out';"
            "p.textContent=JSON.stringify(o);document.body.appendChild(p);});})()")


def _pantip_direct(url, tid):
    """本机能直连时免费取：评论接口带 X-Requested-With 直接返回 JSON（2026-11-11 实测），标题和主帖从静态页取。"""
    s, b, _ = http(f"https://pantip.com/forum/topic/render_comments?tid={tid}&param=&type=3",
                   headers={"X-Requested-With": "XMLHttpRequest"}, timeout=DIRECT_TIMEOUT)
    if s != 200 or not b.lstrip().startswith(b"{"):
        return None
    s2, b2, _ = http(url, timeout=DIRECT_TIMEOUT)
    page = b2.decode("utf-8", "replace") if s2 == 200 else ""
    t = re.search(r"(?is)<title>(.*?)</title>", page)
    st = re.search(r'(?is)class="display-post-story"[^>]*>(.*?)</div>', page)
    return {"title": html.unescape(t.group(1)).strip() if t else "", "story": to_text(st.group(1).encode()) if st else "",
            "comments": b.decode("utf-8", "replace")}


def _pantip_scrapeless(url, tid, country):
    """经 Scrapeless 网页代理 v2 的 JS 渲染取（境内模式和直连失败时用，每帖 1 次付费请求，实测约 17 秒）。"""
    body = {"actor": "unlocker.webunlocker", "proxy": {"country": country},
            "input": {"url": url, "jsRender": {"enabled": True, "instructions": [
                {"evaluate": _pantip_render_js(tid)}, {"waitFor": ["#geo-out", 25000]}],
                "response": {"type": "plaintext"}}}}
    last = ""
    for _ in range(2):
        s, b, _ = http(API + "/api/v2/unlocker/request", body, vendor({"x-api-token": key(), "Content-Type": "application/json"}),
                       timeout=180)
        try:
            data = json.loads(b).get("data")
            text = data if isinstance(data, str) else ""
            o = json.loads(text[text.find("{"):]) if "{" in text else None
        except Exception:  # noqa: BLE001
            o = None
        if s == 200 and isinstance(o, dict) and str(o.get("comments") or "").lstrip().startswith("{"):
            return o, ""
        last = f"HTTP {s}，{(o or {}).get('error') or b[:160].decode('utf-8', 'replace')}"
    return None, last


def pantip_text(url, country="TH"):
    """Pantip 帖子的标题、主帖和评论，返回 (说明行, 正文或 None)。顺序：缓存 → 直连（境内模式跳过）→ Scrapeless 渲染。"""
    m = PANTIP_TOPIC.search(url)
    if not m:
        return f"读不到：{url} —— 不是 Pantip 帖子网址（要 https://pantip.com/topic/<数字>）", None
    tid = m.group(1)
    f = CACHE / f"pantip_{tid}.json"
    o, src = None, ""
    if f.exists():
        try:
            c = json.loads(f.read_text())
            o, src = c["data"], f"{c['src']}（缓存 {c['at']}）"
        except Exception:  # noqa: BLE001
            f.unlink(missing_ok=True)
    if o is None and not DOMESTIC:
        o = _pantip_direct(url, tid)
        src = "评论接口直连" if o else ""
    if o is None:
        o, why = _pantip_scrapeless(url, tid, country)
        if o is None:
            return f"读不到：{url} —— {'' if DOMESTIC else '直连没取到，'}Scrapeless {country} 渲染 {why}", None
        src = f"经 Scrapeless {country} 渲染取得"
    if "缓存" not in src:
        f.write_text(json.dumps({"src": src, "at": time.strftime("%Y-%m-%d %H:%M"), "data": o}, ensure_ascii=False))
    return f"[来源] {url} —— Pantip {src}", format_pantip(url, o)


def format_pantip(url, o):
    import datetime as _dt

    def day(v):
        try:
            return _dt.datetime.strptime(v, "%m/%d/%Y %H:%M:%S").date().isoformat()
        except Exception:  # noqa: BLE001
            return v or ""

    try:
        comments = json.loads(o.get("comments") or "{}").get("comments") or []
    except ValueError:
        comments = []
    title = re.sub(r"\s*-\s*Pantip\s*$", "", o.get("title") or "")
    out = [f"标题：{title}", f"主帖：{(o.get('story') or '').strip()}", f"评论 {len(comments)} 条（每条最多带 5 条回复）", ""]
    for i, c in enumerate(comments, 1):
        user = (c.get("user") or {}).get("name") or ""
        out.append(f"{i}. [评论] \n   {user} · {day(c.get('data_utime'))} · {url}#comment{c.get('comment_no')}\n"
                   f"   {to_text((c.get('message') or '').encode()).replace(chr(10), chr(10) + '   ')}")
        for r in c.get("replies") or []:
            ru = (r.get("user") or {}).get("name") or ""
            out.append(f"   - 回复 {ru} · {day(r.get('data_utime'))}：{to_text((r.get('message') or '').encode()).replace(chr(10), ' ')}")
        out.append("")
    return "\n".join(out)


def pantip(url, country="TH"):
    head, text = pantip_text(url, country)
    print(head)
    if text:
        print(); print(text)


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "search":
        search(arg, opt("--gl", "sg"), opt("--hl", "en"))
    elif cmd == "reddit":
        reddit(arg, opt("--sub", None), opt("--t", "all"), int(opt("--limit", "25")), "--proxy" in sys.argv)
    elif cmd == "pantip":
        pantip(arg, opt("--country", "TH").upper())
    elif cmd == "render":
        render(arg, "--raw" in sys.argv, int(opt("--wait", "8000")), opt("--country", "US").upper())
    else:
        valued = {"--country", "--jobs", "--urls-file"}
        urls, rest = [], sys.argv[2:]
        for i, x in enumerate(rest):
            if not x.startswith("--") and (i == 0 or rest[i - 1] not in valued):
                urls.append(x)
        if "--urls-file" in sys.argv:
            urls += [ln.strip() for ln in Path(opt("--urls-file", "")).read_text().splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
        urls = list(dict.fromkeys(urls))
        fetch(urls, "--raw" in sys.argv, opt("--country", "SG"), "--proxy" in sys.argv, "--fresh" in sys.argv,
              int(opt("--jobs", "5")))
