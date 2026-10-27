"""用 DataForSEO API 取 Google 关键词数据：月搜索量、长尾关键词建议、Google Trends、账户余额。

售前选词工具和售后选词共用；销售通过选词工具调用，不需要 Semrush / Ahrefs 账号。
四个子命令：
  balance   查账户余额（免费），也用来确认凭据可用。
  volume    给一批关键词查月搜索量（Google Ads 数据）。一次请求最多 1000 个词，按请求计费，
            不按词数计费；Google Ads 接口每分钟最多 12 次请求。
  suggest   给种子词取包含它的长尾关键词（DataForSEO Labs 关键词库），带月搜索量与搜索意图；
            每个种子词 1 次付费调用。
  trends    比较同一品类 2–5 种叫法在目标市场的 Google Trends 相对热度，并按日历月看季节性；
            一次请求最多 5 个词，按请求计费。只有同一次请求里的词能互相比较（Trends 按请求内最高值
            归一到 100），所以一组叫法必须一次给齐。--queries 另给每个词各取一次相关查询（热门与飙升），
            每个词多 1 次付费调用；飙升查询只是候选新叫法，要在评价或社区里确认买家也这么说才进题面。

    python3 -I collect_keyword_data.py balance
    python3 -I collect_keyword_data.py volume "automatic litter box" "self cleaning litter box" --country us --lang en --out <目录>
    python3 -I collect_keyword_data.py suggest --seeds-file seeds.txt --country us --lang en --limit 50 --out <目录>
    python3 -I collect_keyword_data.py trends "automatic litter box" "self cleaning litter box" --country us --lang en --queries --out <目录>

凭据依次读：环境变量 DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD；macOS 钥匙串（服务名同上）。
凭据不写进任何文件。--sandbox 走 DataForSEO 沙盒（免费，返回假数据），只用来验证流程。

花费控制：每次付费调用后读返回的 cost 累加，累计超过 --budget-usd（默认 1 美元）就停止后续调用。
<out>/raw/ 已有同一请求的返回时直接复用，不重复付费；--refresh 强制重采，--cache-only 不发付费调用。

产物（<out>/）：
  raw/<子命令>-<摘要>.json   原始请求与返回，作证据留存
  signals.csv               列与对客 Base「买家原话」表一致；来源类型「搜索数据」，月搜索量填分档
                            （>10,000 / >1000 / >100 / <100；确切数在 volumes.csv），中文意思、受众、旅程阶段等留空待人工判
  volumes.csv               内部用：关键词、月均搜索量、近 12 个月逐月量、竞争度、CPC、搜索意图
  summary.json              调用次数、累计花费、失败项
  trends 子命令的产物不进 signals.csv（Trends 只定用哪个品类词和避开哪几个月，不是买家原话）：
  trends.csv                每个叫法的平均热度、排名、热度最高的三个日历月、逐周序列
  trends_queries.csv        --queries 时：每个叫法的热门与飙升相关查询
  summary.json 的 note      可直接贴进买家原话表「来源说明」与任务记录的一句话（叫法对比 + 旺季月份）

读数口径（signal-sources.md → 关键词工具）：搜索量只作方向判断，不当 AI 提问量；说主题规模时
取同一需求几种说法里量最大的那个词，不相加。韩国谷歌量偏低，量级以 Naver 关键词工具为主。
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LIVE = "https://api.dataforseo.com/v3/"
SANDBOX = "https://sandbox.dataforseo.com/v3/"
VOLUME_PATH = "keywords_data/google_ads/search_volume/live"
SUGGEST_PATH = "dataforseo_labs/google/keyword_suggestions/live"
TRENDS_PATH = "keywords_data/google_trends/explore/live"
TRENDS_FIELDS = ["keyword", "average", "rank", "peak_months", "weeks", "series"]
TRENDS_QUERY_FIELDS = ["keyword", "kind", "query", "value"]
TRENDS_RANGES = ["past_30_days", "past_90_days", "past_12_months", "past_5_years"]
TRENDS_RANGE_LABEL = {"past_30_days": "近 30 天", "past_90_days": "近 90 天", "past_12_months": "近 12 个月",
                      "past_5_years": "近 5 年"}
USER_PATH = "appendix/user_data"
FIELDS = ["输入编号", "产品线", "涉及品牌", "来源类型", "月搜索量", "原话", "中文意思", "受众", "旅程阶段",
          "约束", "来源说明", "来源链接", "收集日期", "证据可信度", "引用它的问题"]
VOLUME_FIELDS = ["keyword", "search_volume", "tier", "monthly", "competition", "cpc", "main_intent", "seed", "source"]
# DataForSEO 国家 location_code = 2000 + ISO 3166 数字代码；表外市场用 --location-code。
COUNTRY = {"us": 2840, "gb": 2826, "uk": 2826, "sg": 2702, "my": 2458, "th": 2764, "tw": 2158, "kr": 2410,
           "jp": 2392, "hk": 2344, "au": 2036, "ca": 2124, "de": 2276, "fr": 2250, "id": 2360, "vn": 2704,
           "ph": 2608, "in": 2356, "ae": 2784, "sa": 2682, "br": 2076, "mx": 2484, "es": 2724, "it": 2380,
           "nl": 2528, "nz": 2554}
GOOGLE_ADS_LIMITS = (80, 10)  # 每个关键词最多 80 个字符、10 个词


class Fatal(Exception):
    pass


def credential(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    r = subprocess.run(["security", "find-generic-password", "-s", name, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def auth_header() -> str:
    login, password = credential("DATAFORSEO_LOGIN"), credential("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise Fatal("缺少 DataForSEO 凭据：设环境变量 DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD，或存进钥匙串（服务名同名）")
    return "Basic " + base64.b64encode(f"{login}:{password}".encode()).decode()


def call(base: str, path: str, auth: str, payload=None, timeout=120):
    req = urllib.request.Request(base + path, method="POST" if payload is not None else "GET",
                                 headers={"Authorization": auth, "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LookupError(f"网络错误：{e}")
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        raise LookupError(f"HTTP {status}：返回不是 JSON（{body[:200]!r}）")
    code = data.get("status_code")
    if status in (401, 402, 403) or code in FATAL_CODES:
        raise Fatal(f"HTTP {status} / {code}：鉴权、权限或余额错误，整批停止（{data.get('status_message')}）")
    if code != 20000:
        raise LookupError(f"HTTP {status} / {code}：{data.get('status_message')}")
    return data


FATAL_CODES = (40100, 40101, 40104, 40200, 40201, 40202, 40203, 40204)
# 40201「unusual activity…paused」2026-10-27 遇到两次，都是一两分钟内自行恢复，面板上不显示封禁
PAUSE_HINT = "；这类暂停实测是临时风控，隔一两分钟重跑即可，先别找客服"


def first_task(data) -> dict:
    tasks = data.get("tasks") or []
    if not tasks:
        raise Fatal("返回里没有 tasks")
    task = tasks[0]
    # 账户暂停、未验证、余额不足有时只出现在任务层（外层 status_code 仍是 20000），同样整批停止
    if task.get("status_code") in FATAL_CODES:
        raise Fatal(f"{task.get('status_code')}：账户或权限错误，整批停止（{task.get('status_message')}）"
                    + (PAUSE_HINT if task.get("status_code") == 40201 else ""))
    return task


def tier(volume) -> str:
    if not isinstance(volume, int):
        return ""
    if volume > 10000:
        return ">10,000"
    if volume > 1000:
        return ">1000"
    if volume > 100:
        return ">100"
    return "<100"


def monthly(items) -> str:
    rows = sorted((m["year"], m["month"], m.get("search_volume")) for m in (items or [])
                  if m and isinstance(m.get("year"), int) and isinstance(m.get("month"), int))
    return " ".join(f"{y}-{mo:02d}:{v}" for y, mo, v in rows)


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.raw = self.out / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.base = SANDBOX if args.sandbox else LIVE
        self.auth = None if args.cache_only else auth_header()
        self.paid_calls, self.cost, self.failed, self.stopped = 0, 0.0, [], ""

    def location(self) -> dict:
        if self.args.location_code:
            code = self.args.location_code
        else:
            code = COUNTRY.get(self.args.country.lower())
            if not code:
                raise Fatal(f"不认识的市场 {self.args.country}：用 --location-code 直接给 DataForSEO 的 location_code")
        return {"location_code": code, "language_code": self.args.lang}

    def request(self, kind: str, path: str, task: dict):
        key = hashlib.sha1(json.dumps([path, task, self.args.sandbox], sort_keys=True).encode()).hexdigest()[:12]
        f = self.raw / f"{kind}-{key}.json"
        if f.exists() and not self.args.refresh:
            return json.loads(f.read_text(encoding="utf-8"))["response"], True
        if self.args.cache_only:
            raise LookupError("无缓存，--cache-only 未采集")
        if self.stopped:
            raise LookupError(self.stopped)
        data = call(self.base, path, self.auth, [task])
        self.paid_calls += 1
        self.cost += float(data.get("cost") or 0)
        if ((data.get("tasks") or [{}])[0] or {}).get("status_code") == 20000:  # 失败的返回不缓存，下次重采
            f.write_text(json.dumps({"request": {"path": path, "task": task, "sandbox": self.args.sandbox},
                                     "collected": datetime.date.today().isoformat(), "response": data},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
        if self.cost >= self.args.budget_usd:
            self.stopped = f"累计花费 {self.cost:.4f} 美元已达预算 {self.args.budget_usd} 美元，后续调用停止"
        return data, False


def load_terms(args) -> list[str]:
    terms = list(args.terms)
    if args.file:
        for line in Path(args.file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    seen, out = set(), []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def run_volume(r: Runner, terms: list[str]):
    loc = r.location()
    ok, skipped = [], []
    for t in terms:
        (skipped if len(t) > GOOGLE_ADS_LIMITS[0] or len(t.split()) > GOOGLE_ADS_LIMITS[1] else ok).append(t)
    for t in skipped:
        r.failed.append({"term": t, "error": "超过 Google Ads 限制（80 字符或 10 个词），未查"})
    rows = []
    for i in range(0, len(ok), 1000):
        batch = ok[i:i + 1000]
        if i:
            time.sleep(5)  # Google Ads 接口每分钟最多 12 次
        try:
            data, cached = r.request("volume", VOLUME_PATH, {"keywords": batch, **loc})
        except LookupError as e:
            r.failed += [{"term": t, "error": str(e)} for t in batch]
            continue
        task = first_task(data)
        if task.get("status_code") != 20000:
            r.failed += [{"term": t, "error": f"{task.get('status_code')} {task.get('status_message')}"} for t in batch]
            continue
        found = {}
        for item in task.get("result") or []:
            found[str(item.get("keyword", "")).lower()] = item
        for t in batch:
            item = found.get(t.lower(), {})
            vol = item.get("search_volume")
            rows.append({"keyword": t, "search_volume": vol if vol is not None else "", "tier": tier(vol),
                         "monthly": monthly(item.get("monthly_searches")), "competition": item.get("competition") or "",
                         "cpc": item.get("cpc") if item.get("cpc") is not None else "", "main_intent": "",
                         "seed": "", "source": "Google Ads 月搜索量"})
    return rows


def run_suggest(r: Runner, seeds: list[str]):
    loc = r.location()
    rows = []
    for seed in seeds:
        task_in = {"keyword": seed, **loc, "limit": r.args.limit, "include_seed_keyword": True,
                   "filters": [["keyword_info.search_volume", ">=", r.args.min_volume]]}
        try:
            data, cached = r.request("suggest", SUGGEST_PATH, task_in)
        except LookupError as e:
            r.failed.append({"term": seed, "error": str(e)})
            continue
        task = first_task(data)
        if task.get("status_code") != 20000:
            r.failed.append({"term": seed, "error": f"{task.get('status_code')} {task.get('status_message')}"})
            continue
        result = (task.get("result") or [{}])[0] or {}
        items = list(result.get("items") or [])
        if result.get("seed_keyword_data"):
            items.insert(0, result["seed_keyword_data"])
        for item in items:
            info = item.get("keyword_info") or {}
            vol = info.get("search_volume")
            rows.append({"keyword": item.get("keyword") or seed, "search_volume": vol if vol is not None else "",
                         "tier": tier(vol), "monthly": monthly(info.get("monthly_searches")),
                         "competition": info.get("competition_level") or "",
                         "cpc": info.get("cpc") if info.get("cpc") is not None else "",
                         "main_intent": (item.get("search_intent_info") or {}).get("main_intent") or "",
                         "seed": seed, "source": "DataForSEO 关键词建议"})
        print(f"{seed}: {len(items)} 个关键词")
    return rows


def write_outputs(r: Runner, rows: list[dict], command: str):
    args, today = r.args, datetime.date.today().isoformat()
    seen, signal_rows = set(), []
    for row in rows:
        k = row["keyword"].lower()
        if k in seen:
            continue
        seen.add(k)
        note = f"{row['source']}｜{args.country or args.location_code} {args.lang}"
        if row["seed"]:
            note += f"｜种子词：{row['seed']}"
        if row["search_volume"] == "":
            note += "｜无数据"
        s = dict.fromkeys(FIELDS, "")
        s.update({"产品线": args.product_line, "来源类型": "搜索数据", "月搜索量": row["tier"], "原话": row["keyword"],
                  "来源说明": note + ("｜沙盒假数据" if args.sandbox else ""), "收集日期": today,
                  "证据可信度": "中" if row["search_volume"] != "" else "低"})
        signal_rows.append(s)
    for i, s in enumerate(signal_rows, 1):
        s["输入编号"] = f"{args.id_prefix}{i:03d}"
    with (r.out / "signals.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(signal_rows)
    with (r.out / "volumes.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=VOLUME_FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = {"command": command, "market": {"country": args.country, "location_code": args.location_code,
                                              "lang": args.lang},
               "sandbox": args.sandbox, "collected": today, "paid_calls": r.paid_calls,
               "cost_usd": round(r.cost, 4), "rows": len(signal_rows), "stopped": r.stopped, "failed": r.failed}
    (r.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n付费调用 {r.paid_calls} 次，花费 {r.cost:.4f} 美元；{len(signal_rows)} 个关键词"
          + ("（沙盒假数据）" if args.sandbox else ""))
    if r.failed:
        print(f"失败 {len(r.failed)} 项，见 summary.json")
    if r.stopped:
        print(r.stopped)
    print(f"产物：{r.out / 'signals.csv'}、{r.out / 'volumes.csv'}、{r.out / 'summary.json'}")


def trends_items(r: Runner, kind: str, task_in: dict, item_type: str):
    data, cached = r.request(kind, TRENDS_PATH, task_in)
    task = first_task(data)
    if task.get("status_code") != 20000:
        raise LookupError(f"{task.get('status_code')} {task.get('status_message')}")
    result = (task.get("result") or [{}])[0] or {}
    return [i for i in result.get("items") or [] if i.get("type") == item_type], result.get("check_url") or ""


def run_trends(r: Runner, terms: list[str]):
    base = {**r.location(), "type": "web", "time_range": r.args.time_range}
    rows, queries, check_url = [], [], ""
    try:
        graphs, check_url = trends_items(r, "trends", {"keywords": terms, **base,
                                                       "item_types": ["google_trends_graph"]}, "google_trends_graph")
    except LookupError as e:
        r.failed.append({"term": " / ".join(terms), "error": str(e)})
        r.graph_failed = True
        graphs = []
    points = (graphs[0].get("data") or []) if graphs else []
    for k, term in enumerate(terms):
        series, by_month = [], {}
        for p in points:
            vals = p.get("values") or []
            v = vals[k] if k < len(vals) else None
            if p.get("missing_data") or not isinstance(v, (int, float)):
                continue
            series.append((p.get("date_from", ""), v))
            by_month.setdefault(int(p.get("date_from", "0000-00")[5:7] or 0), []).append(v)
        avg = round(sum(v for _, v in series) / len(series), 1) if series else ""
        month_avg = sorted(((sum(vs) / len(vs), m) for m, vs in by_month.items() if m), reverse=True)
        rows.append({"keyword": term, "average": avg, "rank": "",
                     "peak_months": "、".join(f"{m} 月" for _, m in month_avg[:3]) if avg else "",
                     "weeks": len(series), "series": " ".join(f"{d}:{v}" for d, v in series)})
    ranked = sorted((row for row in rows if row["average"] != ""), key=lambda row: -row["average"])
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    if r.args.queries:
        for term in terms:
            try:
                lists, _ = trends_items(r, "trends-queries", {"keywords": [term], **base,
                                                               "item_types": ["google_trends_queries_list"]},
                                        "google_trends_queries_list")
            except LookupError as e:
                r.failed.append({"term": term, "error": f"相关查询：{e}"})
                continue
            data = (lists[0].get("data") or {}) if lists else {}
            for kind in ("top", "rising"):
                for q in data.get(kind) or []:
                    queries.append({"keyword": term, "kind": {"top": "热门", "rising": "飙升"}[kind],
                                    "query": q.get("query", ""), "value": q.get("value", "")})
            print(f"{term}: 相关查询 {sum(1 for q in queries if q['keyword'] == term)} 条")
    return rows, ranked, queries, check_url


def write_trends_outputs(r: Runner, rows, ranked, queries, check_url):
    args, today = r.args, datetime.date.today().isoformat()
    for name, fields, data in (("trends.csv", TRENDS_FIELDS, rows), ("trends_queries.csv", TRENDS_QUERY_FIELDS, queries)):
        if name == "trends_queries.csv" and not args.queries:
            continue
        with (r.out / name).open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)
    market = (args.country.upper() if args.country else f"location {args.location_code}")
    note = ""
    if ranked:
        note = f"Trends {market} {TRENDS_RANGE_LABEL[args.time_range]}，" + " 高于 ".join(
            f"{row['keyword']}（均值 {row['average']}）" for row in ranked)
        if args.time_range in ("past_12_months", "past_5_years"):
            note += f"；{ranked[0]['keyword']} 热度最高的月份：{ranked[0]['peak_months']}"
        if args.sandbox:
            note += "｜沙盒假数据"
    # 热度曲线没取到时不能说「没有足够数据」，原因看 failed
    no_data = [] if getattr(r, "graph_failed", False) else [row["keyword"] for row in rows if row["average"] == ""]
    summary = {"command": "trends", "market": {"country": args.country, "location_code": args.location_code,
                                               "lang": args.lang},
               "time_range": args.time_range, "sandbox": args.sandbox, "collected": today,
               "paid_calls": r.paid_calls, "cost_usd": round(r.cost, 4), "note": note, "check_url": check_url,
               "no_data": no_data, "stopped": r.stopped, "failed": r.failed}
    (r.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n付费调用 {r.paid_calls} 次，花费 {r.cost:.4f} 美元" + ("（沙盒假数据）" if args.sandbox else ""))
    if note:
        print(f"来源说明：{note}")
    if no_data:
        print(f"没有足够数据（小品类或小市场常见）：{'、'.join(no_data)}")
    if r.failed:
        print(f"失败 {len(r.failed)} 项，见 summary.json")
    if r.stopped:
        print(r.stopped)
    print(f"产物：{r.out / 'trends.csv'}" + (f"、{r.out / 'trends_queries.csv'}" if args.queries else "")
          + f"、{r.out / 'summary.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    bal = sub.add_parser("balance", help="查账户余额（免费）")
    bal.add_argument("--sandbox", action="store_true")
    for name, help_text in (("volume", "查关键词月搜索量"), ("suggest", "取种子词的长尾关键词"),
                            ("trends", "比较几种叫法的 Google Trends 相对热度与季节性")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("terms", nargs="*", help="关键词或种子词，可与 --file 合用")
        p.add_argument("--file", "--seeds-file", "--keywords-file", dest="file", help="每行一个词，# 开头为注释")
        p.add_argument("--country", default="", help="市场国家代码，如 us、sg、th、tw")
        p.add_argument("--location-code", type=int, help="直接给 DataForSEO location_code（覆盖 --country）")
        p.add_argument("--lang", required=True, help="语言代码，如 en、th、ko；繁体中文 Google Ads 用 zh_TW")
        p.add_argument("--out", required=True, help="产物目录")
        p.add_argument("--product-line", default="", help="写入 产品线 列")
        p.add_argument("--id-prefix", default="K", help="输入编号前缀，避免与已有买家原话撞号")
        p.add_argument("--budget-usd", type=float, default=1.0, help="本次累计花费上限，默认 1 美元")
        p.add_argument("--sandbox", action="store_true", help="走沙盒（免费，假数据），验证流程用")
        p.add_argument("--refresh", action="store_true", help="忽略缓存，重新付费采集")
        p.add_argument("--cache-only", action="store_true", help="只用 raw/ 缓存，不发付费调用")
        if name == "suggest":
            p.add_argument("--limit", type=int, default=50, help="每个种子词最多返回几个词，最大 1000")
            p.add_argument("--min-volume", type=int, default=10, help="只要月搜索量不低于这个值的词")
        if name == "trends":
            p.add_argument("--time-range", choices=TRENDS_RANGES, default="past_12_months",
                           help="时间范围，默认近 12 个月；看季节性更稳可用 past_5_years")
            p.add_argument("--queries", action="store_true", help="另取每个词的相关查询（每个词多 1 次付费调用）")
    args = ap.parse_args()

    try:
        if args.command == "balance":
            data = call(SANDBOX if args.sandbox else LIVE, USER_PATH, auth_header())
            result = (first_task(data).get("result") or [{}])[0] or {}
            money = result.get("money") or {}
            print(f"账户：{result.get('login', '')}  余额：{money.get('balance')} 美元"
                  + ("（沙盒）" if args.sandbox else ""))
            return 0
        if not args.country and not args.location_code:
            ap.error("要给 --country 或 --location-code")
        terms = load_terms(args)
        if not terms:
            ap.error("至少给一个关键词")
        r = Runner(args)
        if args.command == "trends":
            if len(terms) > 5:
                ap.error("trends 一次最多 5 个词：只有同一次请求里的词能互相比较，请分组后各跑一次")
            write_trends_outputs(r, *run_trends(r, terms))
            return 1 if r.stopped else 0
        rows = run_volume(r, terms) if args.command == "volume" else run_suggest(r, terms)
        write_outputs(r, rows, args.command)
        return 1 if r.stopped else 0
    except (Fatal, LookupError) as e:
        print(f"停止：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
