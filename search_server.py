#!/usr/bin/env python3
"""轻量 web_search / web_fetch 服务（Scrapeless 后端）。"""

# ============================================================
# from __future__ 必须放最顶部
# ============================================================
from __future__ import annotations

# ============================================================
# 启动时自动加载 .env
# ============================================================
import os
from pathlib import Path

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

# ============================================================
# 其他 import
# ============================================================
import argparse
import html as html_lib
import json
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote

import requests


# ============================================================
# 配置
# ============================================================
SCRAPELESS_API_KEY = os.environ.get("SCRAPELESS_API_KEY", "").strip()
SCRAPELESS_BASE = os.environ.get("SCRAPELESS_BASE_URL", "https://api.scrapeless.com")

# Scrapeless 各产品的 endpoint / actor（实测）：
#   - SERP（Google 搜索）：Scraping API  POST /api/v1/scraper/request   actor=scraper.google.search
#   - 抓取（任意 URL）：     Web Unlocker  POST /api/v2/unlocker/request  actor=unlocker.webunlocker
SERP_CREATE_PATH = "/api/v1/scraper/request"
SERP_RESULT_PATH = "/api/v1/scraper/result/"
UNLOCKER_PATH = "/api/v2/unlocker/request"
RESULT_PATH = "/api/v2/scraper/result/"

# actor 名：Scrapeless 按 actor 分能力。可用环境变量覆盖，无需改代码：
#   SCRAPELESS_SERP_ACTOR   默认 scraper.google.search
#   SCRAPELESS_FETCH_ACTOR  默认 unlocker.webunlocker
SERP_ACTOR = os.environ.get("SCRAPELESS_SERP_ACTOR", "scraper.google.search").strip()
FETCH_ACTOR = os.environ.get("SCRAPELESS_FETCH_ACTOR", "unlocker.webunlocker").strip()

# Web Unlocker 代理出口国家。留空=不用代理（默认，快：单站 1-13s）。
# 设成 US 等可治地理重定向，但会显著变慢（实测单站 21-46s），可能撞平台 30s 上限。
FETCH_COUNTRY = os.environ.get("SCRAPELESS_COUNTRY", "").strip()

# SERP 的 link 常是 Google 的 /goto?url=... 编码跳转，需跟随后才是真实 URL
RESOLVE_LINKS = os.environ.get("SCRAPELESS_RESOLVE_LINKS", "0").strip().lower() not in ("0", "false", "no")
# 单条 link 跟随的超时（秒）；解析并发执行，太慢的直接放弃保留原链接
LINK_RESOLVE_TIMEOUT = float(os.environ.get("SCRAPELESS_LINK_TIMEOUT", "12"))
# 并发度：link 解析、批量查询、批量抓取共用。
# SERP 打太猛会触发 Scrapeless 限流（100401），查询并发单独限得更低。
MAX_WORKERS = max(1, int(os.environ.get("SCRAPELESS_MAX_WORKERS", "8")))
SERP_WORKERS = max(1, int(os.environ.get("SCRAPELESS_SERP_WORKERS", "2")))
# 批量整体时间预算（秒）：超预算的剩余任务不再等待，直接标记失败
# 平台侧工具调用上限约 30s，这里留 ~2s 余量
BATCH_BUDGET = float(os.environ.get("SCRAPELESS_BATCH_BUDGET", "28"))
# 补跑门槛：剩余时间够跑完一次完整 SERP 才值得补跑，否则宁可保留部分成功结果
SERP_RETRY_MIN_BUDGET = float(os.environ.get("SCRAPELESS_RETRY_MIN_BUDGET", "18"))
# fetch 补跑门槛：单 URL 通常 1-20s，留 10s 就够再试一次
FETCH_RETRY_MIN_BUDGET = float(os.environ.get("SCRAPELESS_FETCH_RETRY_MIN_BUDGET", "10"))
# 单次抓取的超时（秒）：单个慢 URL 不拖垮整批（单站实测最慢 ~12s）
FETCH_TIMEOUT = float(os.environ.get("SCRAPELESS_FETCH_TIMEOUT", "25"))

# 瞬时故障重试（Scrapeless 偶发 520 网关错误、429 限流、100401 请求失败等）
# 100401 在并发下很常见，重试次数给足；退避基数也调大一点避开限流窗口
RETRY_ATTEMPTS = max(1, int(os.environ.get("SCRAPELESS_RETRY_ATTEMPTS", "5")))
RETRY_BACKOFF = float(os.environ.get("SCRAPELESS_RETRY_BACKOFF", "1.5"))  # 秒，指数退避基数
# 视为瞬时、值得重试的 HTTP 状态码（含 Cloudflare 5xx 系列）
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527}
# 视为瞬时的 Scrapeless 业务错误码（400 里夹带的“request failed”这类）
# 100400/100401 = 请求失败，100429 = 限流，20500 = 网关错误
TRANSIENT_CODES = {100400, 100401, 100429, 20500}
# 限流码特殊处理：重试只会让限额更紧，应快速失败让上层决定
RATE_LIMIT_CODES = {100429}

DEFAULT_TIMEOUT = 45          # 单次 actor 任务的总超时（含轮询）
POLL_INTERVAL = 2.0
MAX_FETCH_CHARS = 8000
MAX_SEARCH_RESULTS = 10
MAX_BATCH = 10

# 连接复用：线程池并发时显著降低握手开销
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})

# 常驻线程池：避免每次批量调用重建池；批量预算到点后放弃等待，不阻塞响应
_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="ss")


# ============================================================
# Scrapeless 后端（v2：create + poll）
# ============================================================

class TransientError(RuntimeError):
    """可重试的瞬时故障（网关 5xx、限流、请求失败）。"""


class RateLimitError(TransientError):
    """限流：立即重试只会让限额窗口更紧，交给批量层延迟补跑。"""


def _brief_body(text: str, limit: int = 300) -> str:
    """把响应体压成一行短摘要：HTML 错误页只留 title，JSON 原样截断。"""
    t = (text or "").strip()
    if t[:1] == "<" or "<html" in t[:200].lower():
        m = re.search(r"<title>(.*?)</title>", t, flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else "HTML error page"
        return f"<HTML> {title}"
    return re.sub(r"\s+", " ", t)[:limit]


def _http_json(method: str, path: str, payload=None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """统一调 Scrapeless HTTP API。

    - 非 2xx / 非 JSON：抛错并带上（截断后的）响应体，便于定位
    - 瞬时故障（网关 5xx、限流、100401）抛 TransientError，由上层重试
    """
    if not SCRAPELESS_API_KEY:
        raise RuntimeError("SCRAPELESS_API_KEY 未配置（检查 .env 文件或环境变量）")
    try:
        r = requests.request(
            method,
            f"{SCRAPELESS_BASE}{path}",
            json=payload,
            headers={
                "x-api-token": SCRAPELESS_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=max(1.0, timeout),
        )
    except requests.RequestException as e:
        raise TransientError(f"Scrapeless 网络错误：{type(e).__name__}: {e}")

    text = r.text
    if r.status_code >= 400:
        body = _brief_body(text)
        msg = f"Scrapeless HTTP {r.status_code} {method} {path}：{body}"
        if r.status_code in TRANSIENT_STATUS:
            raise TransientError(msg)
        # 400 里夹带的业务错误码（如 100401 request failed）也当瞬时
        if r.status_code == 400:
            try:
                code = int((r.json() or {}).get("code") or 0)
            except (ValueError, TypeError, AttributeError):
                code = 0
            if code in RATE_LIMIT_CODES:
                raise RateLimitError(msg)
            if code in TRANSIENT_CODES:
                raise TransientError(msg)
        raise RuntimeError(msg)
    try:
        return r.json()
    except ValueError:
        raise TransientError(f"Scrapeless 返回非 JSON（HTTP {r.status_code}）：{_brief_body(text)}")


def _http_json_retry(method: str, path: str, payload=None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """带指数退避的重试包装：只重试瞬时故障，其他错误立即抛出。

    - 限流（RateLimitError）最多重试一次，退避 8s。立即重试只会撞更紧的限额。
    - 其他瞬时故障最多 RETRY_ATTEMPTS 次，指数退避。
    - 受总时长上限约束：剩余时间不够一次完整尝试就提前抛出，保留批量里其他已完成项。
    """
    deadline = time.monotonic() + timeout
    last = None
    rate_limited_once = False
    # 单次尝试的保守耗时估计：取已观测到的最慢值的一半，避免预算被一次慢请求吃穿
    single_attempt_cost = max(3.0, timeout * 0.35)
    for attempt in range(RETRY_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= single_attempt_cost * 0.5:
            break  # 剩余时间连半次尝试都不够，不折腾了
        try:
            return _http_json(method, path, payload, min(timeout, remaining))
        except RateLimitError as e:
            last = e
            if rate_limited_once:
                break  # 已经给过一次机会，再撞就交给上层补跑
            rate_limited_once = True
            backoff = 8.0
            remaining = deadline - time.monotonic()
            if remaining - backoff < single_attempt_cost:
                break  # 退避+一次尝试都不够，不浪费预算
            time.sleep(backoff)
        except TransientError as e:
            last = e
            if attempt < RETRY_ATTEMPTS - 1:
                backoff = min(RETRY_BACKOFF * (2 ** attempt), 6.0)
                remaining = deadline - time.monotonic()
                # 退避后还要留够一次尝试的时间，否则不再重试
                if remaining - backoff < single_attempt_cost * 0.5:
                    break
                time.sleep(backoff)
    raise last


def _task_id_from(value) -> str:
    """从任意层级里取 task_id / taskId（与 collect_answers.py 一致）。"""
    if isinstance(value, dict):
        for name in ("task_id", "taskId"):
            v = value.get(name)
            if isinstance(v, str) and v:
                return v
        for child in value.values():
            found = _task_id_from(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _task_id_from(child)
            if found:
                return found
    return ""


def _run_actor(actor: str, input_payload: dict, timeout: float = DEFAULT_TIMEOUT,
               path: str = SERP_CREATE_PATH, result_path: str = SERP_RESULT_PATH,
               extra: dict | None = None) -> dict:
    """创建一次 actor 任务并轮询到终态，返回最终响应体。

    - path：创建任务的 endpoint（SERP 用 SERP_CREATE_PATH，抓取用 UNLOCKER_PATH）
    - result_path：轮询结果的 endpoint 前缀
    - extra：创建 body 里除 actor/input 外的附加字段（如 Web Unlocker 的 proxy）
    - 偶有同步直返（HTTP 200 / status=success/failed）→ 直接用
    - 否则取 task_id 后轮询 {result_path}{task_id}
    """
    body = {"actor": actor, "input": input_payload}
    if extra:
        body.update(extra)
    raw = _http_json_retry("POST", path, body, timeout)
    provider = str(raw.get("status") or "").lower() if isinstance(raw, dict) else ""
    if provider in ("success", "failed"):
        return raw  # 同步直返
    task_id = _task_id_from(raw)
    if not task_id:
        return raw  # 没 task_id：把原始返回透出（通常含错误信息）

    deadline = time.monotonic() + timeout
    interval = POLL_INTERVAL
    last = raw
    while time.monotonic() < deadline:
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
        try:
            last = _http_json("GET", result_path + quote(task_id, safe=""), None, timeout)
        except TransientError:
            # 轮询途中的瞬时故障不应中断：加长间隔继续，直到超时
            interval = min(interval + 2.0, 10.0)
            continue
        st = str(last.get("status") or "").lower() if isinstance(last, dict) else "invalid"
        if st in ("", "pending", "running", "processing", "queued", "created"):
            interval = min(interval + 1.0, 8.0)
            continue
        return last
    return last


def _extract_result(payload):
    """取任务结果主体：优先 task_result，否则原样。"""
    if isinstance(payload, dict) and isinstance(payload.get("task_result"), (dict, list)):
        return payload["task_result"]
    return payload


def _ensure_success(payload):
    """终态为 failed 时抛错，带上 message / 原始体，便于批量里定位。"""
    if not isinstance(payload, dict):
        return
    st = str(payload.get("status") or "").lower()
    if st == "failed":
        msg = payload.get("message") or payload.get("msg") or json.dumps(payload, ensure_ascii=False)[:500]
        raise RuntimeError(f"Scrapeless 任务失败：{msg}")


def _deep_find_str(obj, keys) -> str | None:
    """递归找第一个命中的非空字符串字段。"""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
        for v in obj.values():
            found = _deep_find_str(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _deep_find_str(v, keys)
            if found is not None:
                return found
    return None


def _deep_find_list(obj, keys) -> list:
    """递归找第一个命中的非空 list 字段。"""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, list) and v:
                return v
        for v in obj.values():
            found = _deep_find_list(v, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _deep_find_list(v, keys)
            if found:
                return found
    return []


def _resolve_google_link(link: str, timeout: float = LINK_RESOLVE_TIMEOUT) -> str:
    """Google SERP 的 link 常是 /goto?url=... 编码跳转，跟随后取真实 URL。"""
    if not link:
        return ""
    if link.startswith("http") and "google." not in link:
        return link
    target = link
    if link.startswith("/"):
        target = "https://www.google.com" + link
    try:
        r = _SESSION.get(target, allow_redirects=True, timeout=timeout)
        final = r.url
        # google.com/url? ... 但未真正跳出的情况：保持原样
        if final and "google." not in final.split("/")[2]:
            return final
        return final or link
    except requests.RequestException:
        return link


def _resolve_links_parallel(links: list) -> list:
    """并发解析一批 link，输入输出顺序一致；失败项保留原链接。"""
    if not links:
        return []
    results = list(links)
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(links))) as pool:
        futures = {pool.submit(_resolve_google_link, lk): i for i, lk in enumerate(links)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception:
                results[i] = links[i]
    return results


def _sanitize_query(query: str) -> str:
    """清洗查询词，去掉会让 Scrapeless / Google 直接 400 的字符。

    平台 agent 有时会给品牌名加英文双引号（"KeepBalance"），这类精确匹配语法
    会导致 Scrapeless 100400 request failed。统一剥掉双引号。
    """
    if not isinstance(query, str):
        return query
    return query.replace('"', "").strip()


# SERP 并发闸门：Scrapeless 的 Google Search 在并发 >3 时容易返回 100401，
# 用一个信号量把同时在飞的查询数压住，其余排队（总时间仍受 BATCH_BUDGET 约束）。
_SERP_SEM = threading.Semaphore(SERP_WORKERS)


def _serp_search(query: str, num: int = 10, gl: str = "us", hl: str = "en") -> list:
    """调 Scrapeless Google Search actor，返回 [{title, url, snippet}]。

    走 v1 Scraping API（POST /api/v1/scraper/request）；入参 q/hl/gl/num。
    link 若是 Google 编码跳转，并发跟随解析出真实 URL。
    """
    with _SERP_SEM:
        payload = _run_actor(
            SERP_ACTOR, {"q": _sanitize_query(query), "hl": hl, "gl": gl, "num": num},
            path=SERP_CREATE_PATH, result_path=SERP_RESULT_PATH,
        )
        _ensure_success(payload)
    data = _extract_result(payload)
    organic = _deep_find_list(data, (
        "organic_results", "organicResults", "organic", "results", "items", "result",
    ))
    items = [it for it in organic if isinstance(it, dict)][:num]
    raw_links = [(it.get("link") or it.get("url", "")) for it in items]
    if RESOLVE_LINKS:
        raw_links = _resolve_links_parallel(raw_links)
    out = []
    for item, url in zip(items, raw_links):
        out.append({
            "title": item.get("title", "") or item.get("name", ""),
            "url": url,
            "snippet": item.get("snippet") or item.get("description", "") or item.get("desc", ""),
        })
    return [o for o in out if o["url"]]


def _scrape_url(url: str) -> str:
    """调 Scrapeless Web Unlocker 抓取 URL，返回页面文本。

    Web Unlocker 是同步接口，成功响应形如 {"code":200,"data":"<正文或HTML>"}。
    走 v2 POST /api/v2/unlocker/request，actor=unlocker.webunlocker。
    """
    input_payload = {"url": url, "method": "GET", "redirect": False}
    extra = {"proxy": {"country": FETCH_COUNTRY}} if FETCH_COUNTRY else None

    payload = _run_actor(FETCH_ACTOR, input_payload, timeout=FETCH_TIMEOUT,
                         path=UNLOCKER_PATH, extra=extra)
    _ensure_success(payload)
    data = _extract_result(payload)
    # 常见字段：Web Unlocker 的正文在 data；静态抓取在 html/content
    text = _deep_find_str(data, ("data", "html", "content", "body", "markdown",
                                 "text", "pageContent", "result"))
    if text is not None:
        return text
    # 兜底：没有典型字段就把结果序列化，至少不丢信息
    return json.dumps(data, ensure_ascii=False)[:200000]


def _html_to_text(html: str) -> str:
    """HTML 转纯文本（去 script/style/标签/压缩空白）。"""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text)
    return ' '.join(text.split())


# ============================================================
# 工具实现
# ============================================================

def _run_batch(items, worker, make_error, budget: float = BATCH_BUDGET) -> list:
    """把 worker 并发跑在共享线程池上，按输入顺序返回槽位结果。

    - 到点（budget）后不再等待剩余任务，未完成的槽位用 make_error(item) 填充
    - 单个任务异常用 make_error(item, exc) 填充，不拖垮整批
    - 用共享池 + 绝对截止时间，避免 with 退出时同步 join 慢任务
    """
    slots = [None] * len(items)
    futures = {_POOL.submit(worker, i): i for i in range(len(items))}
    deadline = time.monotonic() + budget
    try:
        for fut in as_completed(futures, timeout=max(0.0, deadline - time.monotonic())):
            i = futures[fut]
            try:
                slots[i] = fut.result()
            except Exception as e:
                slots[i] = make_error(items[i], e)
    except FuturesTimeoutError:
        pass  # 预算到点：剩余未完成的槽位下面补失败占位
    for i, s in enumerate(slots):
        if s is None:
            slots[i] = make_error(items[i], None)  # 未完成
    return slots


def do_web_search(query: str, max_results: int = 8) -> dict:
    if not query or not isinstance(query, str):
        raise ValueError("query 必须是非空字符串")
    query = query.strip()
    if not query:
        raise ValueError("query 剥离空白后为空")
    max_results = max(1, min(int(max_results), MAX_SEARCH_RESULTS))
    items = _serp_search(query, num=max_results, gl="us", hl="en")
    return {"query": query, "count": len(items), "results": items[:max_results]}


def do_web_search_batch(queries, max_results_per_query: int = 5) -> dict:
    """批量搜索：并发执行多个查询，绕开平台调用次数限制。

    只对**失败的查询**做补跑（成功的不重跑），且补跑受剩余时间预算约束。
    """
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries 必须是非空 list")
    if len(queries) > MAX_BATCH:
        raise ValueError(f"queries 最多 {MAX_BATCH} 个，收到 {len(queries)} 个")
    max_results_per_query = max(1, min(int(max_results_per_query), MAX_SEARCH_RESULTS))

    def err(q, e):
        return {"query": q, "count": 0, "results": [],
                "error": f"{type(e).__name__}: {e}" if e else "TIMEOUT: 超出批量时间预算"}

    started = time.monotonic()
    slots = _run_batch(
        queries,
        lambda i: do_web_search(queries[i], max_results=max_results_per_query),
        err,
    )

    # 补跑轮：只针对失败项。SERP 单次实测 7-17s，所以必须有足够剩余预算才值得补跑，
    # 否则会把整批拖到平台 30s 超时，连已成功的结果都拿不到。
    # 限流失败的项延迟 5s 再补跑，避开限额窗口。
    failed_idx = [i for i, s in enumerate(slots) if s.get("error")]
    if failed_idx:
        remaining = BATCH_BUDGET - (time.monotonic() - started)
        if remaining >= SERP_RETRY_MIN_BUDGET:
            rate_limited = any("100429" in str(slots[i].get("error", "")) for i in failed_idx)
            if rate_limited:
                time.sleep(5.0)
                remaining = BATCH_BUDGET - (time.monotonic() - started)
                if remaining < SERP_RETRY_MIN_BUDGET:
                    succeeded = sum(1 for s in slots if not s.get("error"))
                    return {"total_queries": len(queries), "succeeded": succeeded,
                            "failed": len(queries) - succeeded, "retried": 0,
                            "failed_queries": [slots[i]["query"] for i in failed_idx],
                            "results": slots}
            retried = _run_batch(
                failed_idx,
                lambda j: do_web_search(queries[failed_idx[j]], max_results=max_results_per_query),
                lambda j, e: err(queries[failed_idx[j]], e),
                budget=remaining - 1.0,
            )
            for slot_pos, original_idx in enumerate(failed_idx):
                new = retried[slot_pos]
                # 只有补跑成功才覆盖（失败保留原始错误信息）
                if new and not new.get("error"):
                    slots[original_idx] = new

    succeeded = sum(1 for s in slots if not s.get("error"))
    failed_list = [s.get("query") for s in slots if s.get("error")]
    return {
        "total_queries": len(queries),
        "succeeded": succeeded,
        "failed": len(queries) - succeeded,
        "retried": len(failed_idx),
        "failed_queries": failed_list,
        "results": slots,
    }


def do_web_fetch(url: str, max_chars: int = MAX_FETCH_CHARS) -> dict:
    if not url or not isinstance(url, str):
        raise ValueError("url 必须是非空字符串")
    url = url.strip()
    if not url:
        raise ValueError("url 剥离空白后为空")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"url 必须以 http:// 或 https:// 开头: {url!r}")
    max_chars = max(500, min(int(max_chars), 50000))

    html_text = _scrape_url(url)
    text = _html_to_text(html_text)
    return {
        "url": url,
        "status_code": 200,
        "content_length": len(text),
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


def do_web_fetch_batch(urls, max_chars_per_url: int = 5000) -> dict:
    """批量抓取：并发抓多个 URL，绕开平台调用次数限制。

    只对**失败的 URL** 做补跑（成功的不重跑），且补跑受剩余时间预算约束。
    """
    if not isinstance(urls, list) or not urls:
        raise ValueError("urls 必须是非空 list")
    if len(urls) > MAX_BATCH:
        raise ValueError(f"urls 最多 {MAX_BATCH} 个，收到 {len(urls)} 个")
    max_chars_per_url = max(500, min(int(max_chars_per_url), MAX_FETCH_CHARS))

    def err(u, e):
        return {"url": u, "status_code": None, "content": "",
                "content_length": 0, "truncated": False,
                "error": f"{type(e).__name__}: {e}" if e else "TIMEOUT: 超出批量时间预算"}

    started = time.monotonic()
    slots = _run_batch(
        urls,
        lambda i: do_web_fetch(urls[i], max_chars=max_chars_per_url),
        err,
    )

    # 补跑轮：只针对失败项（fetch 单次 1-20s，门槛比 SERP 低一些）
    failed_idx = [i for i, s in enumerate(slots) if s.get("error")]
    if failed_idx:
        remaining = BATCH_BUDGET - (time.monotonic() - started)
        if remaining >= FETCH_RETRY_MIN_BUDGET:
            # _run_batch 的 make_error 收到的第一个参数是 items[i]（即 failed_idx[i]，已是原 urls 的索引）
            retried = _run_batch(
                failed_idx,
                lambda j: do_web_fetch(urls[failed_idx[j]], max_chars=max_chars_per_url),
                lambda original_idx, e: err(urls[original_idx], e),
                budget=remaining - 1.0,
            )
            for slot_pos, original_idx in enumerate(failed_idx):
                new = retried[slot_pos]
                if new and not new.get("error"):
                    slots[original_idx] = new

    succeeded = sum(1 for s in slots if not s.get("error"))
    failed_list = [s.get("url") for s in slots if s.get("error")]
    return {
        "total": len(urls),
        "succeeded": succeeded,
        "failed": len(urls) - succeeded,
        "retried": len(failed_idx),
        "failed_urls": failed_list,
        "results": slots,
    }


# ============================================================
# HTTP 服务
# ============================================================

def _parse_body_tolerant(raw: bytes) -> dict:
    """尽最大努力把平台发来的 body 解析成 dict。

    平台模板渲染常见的四种坏法：
      1. 字符串值里塞了裸 tab/换行/回车 → strict=False 能救
      2. body 尾部多了一段（如 `},{` 这种占位符替换残留）→ raw_decode 取第一个完整对象
      3. urls / queries 被二次序列化成 JSON 字符串 → 由 _deep_parse_list 解
      4. 字符串值里塞了**未转义的内层双引号**（如搜索词里的 "KeepBalance" 精确匹配语法）
         → 标准 JSON 解析全挂，用正则把 queries/urls 字段的原始字符串值抠出来
    """
    if not raw:
        return {}
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    # 尾部垃圾：raw_decode 取第一个完整 JSON 值，忽略后面
    try:
        obj, _ = json.JSONDecoder(strict=False).raw_decode(text.lstrip())
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # 内层未转义引号兜底：正则抠 queries / urls 的字符串值
    recovered = _recover_unescaped_quotes(text)
    if recovered:
        return recovered
    raise json.JSONDecodeError("body 无法解析为 JSON", text, 0)


def _recover_unescaped_quotes(text: str) -> dict:
    """从坏 JSON 里恢复 queries / urls 字段。

    覆盖三种形态：
      1. 内层引号未转义：{"queries": ""KeepBalance" alternatives..."}
      2. 值完全没引号：{"queries": KeepBalance alternatives...\n..., "max_results_per_query": 5}
      3. 值带引号但被截断：{"queries": "abc...

    策略：找到 "queries"/"urls" key 之后，取其值的**整个剩余字符串**直到下一个
    `"<key>":` 模式或文本结尾，再剥掉首尾的引号/逗号/花括号/空白。
    """
    out: dict = {}
    for key in ("queries", "urls"):
        # key 本身的引号是合法的；值可能带引号也可能不带
        m = re.search(r'"%s"\s*:\s*("?)' % key, text)
        if not m:
            continue
        value_start = m.end()
        tail = text[value_start:]
        # 值的结束：找下一个 `"<key>":` 模式（说明进入了下一个字段）
        next_key = re.search(r'(",|,)\s*"[a-zA-Z_]+"\s*:', tail)
        if next_key:
            value_end = value_start + next_key.start()
        else:
            value_end = len(text)
        value = text[value_start:value_end]
        # 剥掉尾部的 `"` `}` `,` 空白（可能叠多个）
        value = value.rstrip().rstrip('}').rstrip().rstrip('"').rstrip().rstrip(',').rstrip().rstrip('"').rstrip()
        # 剥掉开头可能的引号
        value = value.lstrip('"').lstrip()
        out[key] = value
    # 其他数值字段（max_results 等）用简单正则抓
    for num_key in ("max_results", "max_results_per_query", "max_chars", "max_chars_per_url"):
        m = re.search(r'"%s"\s*:\s*(\d+)' % num_key, text)
        if m:
            out[num_key] = int(m.group(1))
    return out if ("queries" in out or "urls" in out) else {}


def _deep_parse_list(value):
    """urls / queries 允许三种形态：
      1. list（直接返回）
      2. JSON 字符串化的 list（"[\\"a\\",\\"b\\"]" → 解开后递归）
      3. 换行或逗号分隔的字符串（"a\\nb" / "a,b" → ["a", "b"]）
      4. 单个字符串（"a" → ["a"]）
    另外容忍字面的 \\n（反斜杠+n 两字符）——平台把换行渲染进模板时常变成这样。
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("[", "{")):
            try:
                return _deep_parse_list(json.loads(stripped))
            except (json.JSONDecodeError, ValueError):
                pass
        # 平台把换行渲染成字面 \n（两字符）时，先还原成真换行再拆
        normalized = stripped.replace("\\n", "\n")
        if "\n" in normalized:
            parts = [p.strip() for p in normalized.split("\n")]
            return [p for p in parts if p]
        if "," in stripped:
            parts = [p.strip() for p in stripped.split(",")]
            return [p for p in parts if p]
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str) and item.strip().startswith(("[", "{")):
                out.extend(_deep_parse_list(item))
            else:
                out.append(item)
        return out
    return value


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        if self.path == "/api/v1/health":
            self._send(200, {
                "ok": True,
                "service": "search_server",
                "backend": "scrapeless",
                "base_url": SCRAPELESS_BASE,
                "api_key_configured": bool(SCRAPELESS_API_KEY),
                "serp_actor": SERP_ACTOR,
                "fetch_actor": FETCH_ACTOR,
                "fetch_country": FETCH_COUNTRY or None,
                "tools": ["web_search", "web_search_batch", "web_fetch", "web_fetch_batch"],
            })
        else:
            self._send(404, {"ok": False, "error": f"Unknown path: {self.path}"})

    def do_POST(self):
        raw = b""
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)

            body = _parse_body_tolerant(raw)

            if self.path == "/api/v1/web_search":
                result = do_web_search(body.get("query", ""), body.get("max_results", 8))
                self._send(200, {"ok": True, "data": result})

            elif self.path == "/api/v1/web_search_batch":
                # 参数名容错：query/queries、max_results/max_results_per_query 都认
                queries = body.get("queries") or body.get("query") or []
                queries = _deep_parse_list(queries)
                result = do_web_search_batch(
                    queries=queries,
                    max_results_per_query=body.get("max_results_per_query") or body.get("max_results") or 5,
                )
                self._send(200, {"ok": True, "data": result})

            elif self.path == "/api/v1/web_fetch":
                result = do_web_fetch(body.get("url", ""), body.get("max_chars", MAX_FETCH_CHARS))
                self._send(200, {"ok": True, "data": result})

            elif self.path == "/api/v1/web_fetch_batch":
                # 参数名容错：url/urls、max_chars/max_chars_per_url 都认
                urls = body.get("urls") or body.get("url") or []
                urls = _deep_parse_list(urls)
                result = do_web_fetch_batch(
                    urls=urls,
                    max_chars_per_url=body.get("max_chars_per_url") or body.get("max_chars") or 5000,
                )
                self._send(200, {"ok": True, "data": result})

            else:
                self._send(404, {"ok": False, "error": f"Unknown path: {self.path}"})

        except json.JSONDecodeError as e:
            # 把 raw body 前 200 字符回显，让调用方直接看到发了什么
            preview = ""
            try:
                raw_text = raw.decode("utf-8", errors="replace")
                preview = raw_text[:200].replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
                if len(raw_text) > 200:
                    preview += f"...(total {len(raw_text)} chars)"
            except Exception:
                preview = "<无法解码>"
            print(f"[BAD_JSON] path={self.path} err={e} body_preview={preview!r}", flush=True)
            self._send(400, {
                "ok": False,
                "error": f"Invalid JSON at char {e.pos}: {e.msg}",
                "body_preview": preview,
                "hint": "请求体不是合法 JSON。请检查工具管理里的 body 模板，确认 {{...}} 占位符被正确替换成了 JSON 值。",
            })
        except ValueError as e:
            self._send(400, {"ok": False, "error": str(e)})
        except requests.RequestException as e:
            self._send(502, {"ok": False, "error": f"Scrapeless API failed: {type(e).__name__}: {e}"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="web_search / web_fetch 微服务（Scrapeless 后端）")
    parser.add_argument("--port", type=int, default=9998)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    if not SCRAPELESS_API_KEY:
        print("WARNING: SCRAPELESS_API_KEY 未配置，所有调用都会失败", flush=True)
        print("请在 .env 文件中写入 SCRAPELESS_API_KEY=sk_xxx", flush=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"search_server (scrapeless) listening on {args.host}:{args.port}", flush=True)
    print(f"  base_url   : {SCRAPELESS_BASE}", flush=True)
    print(f"  serp_actor : {SERP_ACTOR}", flush=True)
    print(f"  fetch_actor: {FETCH_ACTOR}", flush=True)
    print(f"  POST /api/v1/web_search        {{query, max_results?}}", flush=True)
    print(f"  POST /api/v1/web_search_batch  {{queries[], max_results_per_query?}}", flush=True)
    print(f"  POST /api/v1/web_fetch         {{url, max_chars?}}", flush=True)
    print(f"  POST /api/v1/web_fetch_batch   {{urls[], max_chars_per_url?}}", flush=True)
    print(f"  GET  /api/v1/health", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()