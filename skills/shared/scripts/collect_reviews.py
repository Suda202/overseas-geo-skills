"""用 DataForSEO Reviews API 取买家评价原文：Trustpilot、Google Play、App Store、Google Shopping、Google 地图。

售前选词工具和售后选词共用，异步任务可跑，不需要浏览器、不需要登录。评价原文直接来自接口返回，
本身就是可核对的原文；signals.csv 的每一行都能在 raw/ 里找到对应的原始返回。

五个子命令（DataForSEO 的评价接口都是先提交任务、再取结果，脚本自己轮询）：
  trustpilot      给 Trustpilot 上的商家域名（trustpilot.com/review/<域名> 里那一段）；每 20 条计一次费，最多 200 条
  google-play     给 Google Play 应用 ID（details?id= 后面那一段）；每 150 条计一次费
  app-store       给 App Store 应用 ID（URL 里 id 后面的数字）；每 25 条计一次费，最多 500 条
  google-shopping 给商品搜索词：先在 Google Shopping 搜商品，取前 --products 个有评价的商品，再取各自的评价；
                  每条评价带原始出处链接（零售站、评测站）。消费品替代 Amazon 评价用（DataForSEO 的 Amazon
                  评价接口 2026-10-27 文档写着暂不可用）
  google-maps     给 Google 地图商家：搜索词（店名 + 分店 + 城市），或 place_id:<ID>、cid:<ID>；每 10 条计一次费
                  （2026-10-27 实测 20 条 0.0015 美元）。会打印匹配到的商家名，连锁店用 --match 校验没搜到别的分店；
                  只打星没写字的评价不收（实测约四成）；外语评价取原文，不取 Google 的机器翻译

    python3 -I collect_reviews.py trustpilot www.example.com --depth 40 --sort newest --out <目录>
    python3 -I collect_reviews.py google-play com.ybrand.phone --country th --lang th --depth 150 --out <目录>
    python3 -I collect_reviews.py app-store 336141475 --country tw --lang zh-Hant --out <目录>
    python3 -I collect_reviews.py google-shopping "automatic litter box" --country us --lang en --products 3 --depth 20 --out <目录>
    python3 -I collect_reviews.py google-maps "Din Tai Fung Paragon Singapore" --country sg --lang en --match "Din Tai Fung" --sort lowest --out <目录>

凭据、预算、缓存与 collect_keyword_data.py 相同：钥匙串或环境变量 DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD；
累计花费超 --budget-usd（默认 1 美元）即停；<out>/raw/ 有同一请求的结果就复用；提交了任务但没等到结果时，
任务号存进 raw/*.pending.json，下次运行直接取结果，不重复付费。

产物（<out>/）：
  raw/                  每个任务的原始返回
  signals.csv           列与对客 Base「买家原话」表一致；来源类型「评价」，来源说明写平台、对象、星级、日期，
                        来源链接写该条评价（或商品、应用页）的地址；中文意思、受众、旅程阶段等留空待人工判
  reviews.csv           内部用：平台、对象、星级、日期、标题、正文、链接、有用数、应用版本；不存评价人姓名
  summary.json          调用次数、花费、每个对象取到几条、失败项

读数口径（signal-sources.md → 每类信源能用来干什么）：评价偏极端，差评多是投诉和退货，用来找决策摩擦，
不用来估多数买家的看法；--rating 可只取某几个星级。评价人姓名不进任何产物。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("collect_keyword_data", HERE / "collect_keyword_data.py")
kd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kd)

READY, PENDING = 20000, (40601, 40602)  # 40601 任务已提交、40602 排队中
REVIEW_FIELDS = ["platform", "target", "source_site", "rating", "date", "title", "text", "url", "helpful_count",
                 "version", "language", "review_id"]
PLATFORM = {
    "trustpilot": ("Trustpilot", "business_data/trustpilot/reviews/task_post",
                   "business_data/trustpilot/reviews/task_get/"),
    "google-play": ("Google Play", "app_data/google/app_reviews/task_post",
                    "app_data/google/app_reviews/task_get/advanced/"),
    "app-store": ("App Store", "app_data/apple/app_reviews/task_post",
                  "app_data/apple/app_reviews/task_get/advanced/"),
    "google-shopping": ("Google Shopping", "merchant/google/reviews/task_post",
                        "merchant/google/reviews/task_get/advanced/"),
    "google-maps": ("Google 地图", "business_data/google/reviews/task_post",
                    "business_data/google/reviews/task_get/"),
}
PRODUCTS = ("merchant/google/products/task_post", "merchant/google/products/task_get/advanced/")
SORT = {"trustpilot": {"newest": "recency", "relevant": "relevance"},
        "google-play": {"newest": "newest", "relevant": "most_relevant"},
        "app-store": {"newest": "most_recent", "relevant": "most_helpful"},
        "google-maps": {"newest": "newest", "relevant": "relevant", "lowest": "lowest_rating",
                        "highest": "highest_rating"}}


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.raw = self.out / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.auth = None if args.cache_only else kd.auth_header()
        self.paid_calls, self.cost, self.failed, self.stopped = 0, 0.0, [], ""

    def location(self) -> dict:
        code = self.args.location_code or kd.COUNTRY.get((self.args.country or "").lower())
        if not code:
            raise kd.Fatal(f"不认识的市场 {self.args.country}：用 --location-code 直接给 DataForSEO 的 location_code")
        return {"location_code": code, "language_code": self.args.lang}

    def task(self, kind: str, post_path: str, get_path: str, task: dict) -> dict:
        """提交任务并等结果；返回 task_get 的任务对象。成功结果与未取回的任务号都落盘。"""
        key = hashlib.sha1(json.dumps([post_path, task], sort_keys=True).encode()).hexdigest()[:12]
        done, pending = self.raw / f"{kind}-{key}.json", self.raw / f"{kind}-{key}.pending.json"
        if done.exists() and not self.args.refresh:
            return kd.first_task(json.loads(done.read_text(encoding="utf-8"))["response"])
        if self.args.cache_only:
            raise LookupError("无缓存，--cache-only 未采集")
        if pending.exists() and not self.args.refresh:
            task_id = json.loads(pending.read_text(encoding="utf-8"))["id"]
        else:
            if self.stopped:
                raise LookupError(self.stopped)
            posted = kd.first_task(kd.call(kd.LIVE, post_path, self.auth, [task]))
            if posted.get("status_code") not in (20100,) + PENDING:
                raise LookupError(f"提交失败 {posted.get('status_code')} {posted.get('status_message')}")
            self.paid_calls += 1
            self.cost += float(posted.get("cost") or 0)
            task_id = posted["id"]
            pending.write_text(json.dumps({"id": task_id, "post_path": post_path, "task": task,
                                           "posted": datetime.datetime.now().isoformat(timespec="seconds")},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
            if self.cost >= self.args.budget_usd:
                self.stopped = f"累计花费 {self.cost:.4f} 美元已达预算 {self.args.budget_usd} 美元，后续任务不再提交"
        deadline = time.time() + self.args.wait
        while True:
            data = kd.call(kd.LIVE, get_path + task_id, self.auth)
            got = kd.first_task(data)
            if got.get("status_code") == READY:
                done.write_text(json.dumps({"request": {"post_path": post_path, "task": task, "id": task_id},
                                            "collected": datetime.date.today().isoformat(), "response": data},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
                pending.unlink(missing_ok=True)
                return got
            if got.get("status_code") not in PENDING:
                pending.unlink(missing_ok=True)
                raise LookupError(f"{got.get('status_code')} {got.get('status_message')}")
            if time.time() > deadline:
                raise LookupError(f"等了 {self.args.wait} 秒任务还没完成（任务号 {task_id} 已存，重跑会直接取结果，不重复付费）")
            time.sleep(10)


def rating_of(item) -> str:
    v = (item.get("rating") or {}).get("value")
    return str(int(v)) if isinstance(v, (int, float)) else ""


def review_rows(platform: str, target: str, result: dict, fallback_url: str) -> list[dict]:
    rows = []
    for it in result.get("items") or []:
        text = (it.get("original_review_text") or it.get("review_text") or "").strip()  # 有原文取原文，不取机器翻译
        if not text:
            continue
        rows.append({"platform": PLATFORM[platform][0], "target": target, "rating": rating_of(it),
                     "date": (it.get("timestamp") or it.get("publication_date") or "")[:10],
                     "title": (it.get("title") or "").strip(), "text": text,
                     "url": (it.get("url") or it.get("review_url") or "").replace(".com//", ".com/") or fallback_url,
                     "source_site": it.get("provided_by") or "",
                     "helpful_count": it.get("helpful_count") if it.get("helpful_count") is not None else "",
                     "version": it.get("version") or "",
                     "language": it.get("original_language") or it.get("language") or "",
                     "review_id": it.get("id") or it.get("review_id") or ""})
    return rows


def collect(r: Runner, platform: str, target: str, base: dict) -> list[dict]:
    _, post_path, get_path = PLATFORM[platform]
    ratings = r.args.rating or [None]
    rows = []
    for rating in ratings:
        task = {**base, "depth": r.args.depth}
        if platform in SORT:
            task["sort_by"] = SORT[platform][r.args.sort]
        if rating is not None:
            task["rating"] = rating
        got = r.task(platform, post_path, get_path, task)
        result = (got.get("result") or [{}])[0] or {}
        label = maps_label(r, target, result) if platform == "google-maps" else target
        rows += review_rows(platform, label, result, result.get("check_url") or result.get("url") or "")
    return rows


def maps_target(target: str) -> dict:
    for prefix in ("place_id", "cid"):
        if target.startswith(prefix + ":"):
            return {prefix: target.split(":", 1)[1].strip()}
    return {"keyword": target}


def maps_label(r: Runner, target: str, result: dict) -> str:
    """搜索词可能落到别的分店或别的商家：打印匹配结果，给了 --match 就校验商家名。"""
    title = result.get("title") or ""
    if not title:
        raise LookupError("Google 地图没有匹配到商家")
    if r.args.match and r.args.match.lower() not in title.lower():
        raise LookupError(f"匹配到的商家是「{title}」，名字不含 {r.args.match}；换更具体的搜索词或给 place_id:")
    rating = (result.get("rating") or {}).get("value")
    print(f"  商家：{title}（{rating} 分，{result.get('reviews_count')} 条评价，place_id {result.get('place_id')}）")
    return f"{target} → {title}"


def run(r: Runner, platform: str, targets: list[str]) -> tuple[list[dict], dict]:
    rows, per_target = [], {}
    for target in targets:
        try:
            if platform == "trustpilot":
                got = collect(r, platform, target, {"domain": target})
            elif platform in ("google-play", "app-store"):
                got = collect(r, platform, target, {"app_id": target, **r.location()})
            elif platform == "google-maps":
                got = collect(r, platform, target, {**maps_target(target), **r.location()})
            else:
                got = []
                for product in shopping_products(r, target):
                    label = f"{target} → {product['title']}"
                    try:
                        got += collect(r, platform, label, {k: product[k] for k in ("gid", "product_id", "data_docid")
                                                             if product.get(k)} | r.location())
                    except LookupError as e:
                        r.failed.append({"target": label, "error": str(e)})
            rows += got
            per_target[target] = len(got)
            print(f"{target}: {len(got)} 条评价")
        except LookupError as e:
            r.failed.append({"target": target, "error": str(e)})
            per_target[target] = 0
    return rows, per_target


def shopping_products(r: Runner, keyword: str) -> list[dict]:
    got = r.task("shopping-products", *PRODUCTS, {"keyword": keyword, **r.location()})
    result = (got.get("result") or [{}])[0] or {}
    # 自然结果在前，再看轮播里的商品；评价数在 product_rating.votes_count（reviews_count 实测为空）
    candidates = [it for it in result.get("items") or [] if it.get("type") == "google_shopping_serp"]
    for it in result.get("items") or []:
        if it.get("type") == "google_shopping_carousel":
            candidates += [s for s in it.get("items") or [] if isinstance(s, dict)]
    picked, seen = [], set()
    for it in candidates:
        votes = it.get("reviews_count") or (it.get("product_rating") or {}).get("votes_count") or 0
        if not it.get("gid") or it["gid"] in seen or not votes:
            continue
        if r.args.match and r.args.match.lower() not in (it.get("title") or "").lower():
            continue
        seen.add(it["gid"])
        picked.append({"title": it.get("title") or "", "gid": it.get("gid"), "product_id": it.get("product_id"),
                       "data_docid": it.get("data_docid"), "reviews_count": votes})
        if len(picked) >= r.args.products:
            break
    if not picked:
        raise LookupError("Google Shopping 搜索结果里没有带评价的商品" + (f"（标题含 {r.args.match}）" if r.args.match else ""))
    for p in picked:
        print(f"  商品：{p['title']}（{p['reviews_count']} 条评价）")
    return picked


def write_outputs(r: Runner, platform: str, rows: list[dict], per_target: dict):
    args, today = r.args, datetime.date.today().isoformat()
    seen, signal_rows = set(), []
    for row in rows:
        k = (row["target"], row["review_id"] or row["text"])
        if k in seen:
            continue
        seen.add(k)
        note = "｜".join(x for x in (row["platform"], row["target"],
                                     f"原评价在 {row['source_site']}" if row["source_site"] else "",
                                     f"{row['rating']} 星" if row["rating"] else "",
                                     row["date"], f"版本 {row['version']}" if row["version"] else "") if x)
        s = dict.fromkeys(kd.FIELDS, "")
        s.update({"产品线": args.product_line, "涉及品牌": args.brand, "来源类型": "评价", "原话": row["text"],
                  "来源说明": note, "来源链接": row["url"], "收集日期": today, "证据可信度": "中"})
        signal_rows.append(s)
    for i, s in enumerate(signal_rows, 1):
        s["输入编号"] = f"{args.id_prefix}{i:03d}"
    with (r.out / "signals.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=kd.FIELDS)
        w.writeheader()
        w.writerows(signal_rows)
    with (r.out / "reviews.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = {"command": platform, "market": {"country": args.country, "location_code": args.location_code,
                                               "lang": args.lang},
               "collected": today, "paid_tasks": r.paid_calls, "cost_usd": round(r.cost, 4),
               "reviews": len(signal_rows), "per_target": per_target, "stopped": r.stopped, "failed": r.failed}
    (r.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n提交付费任务 {r.paid_calls} 个，花费 {r.cost:.4f} 美元；{len(signal_rows)} 条评价")
    if r.failed:
        print(f"失败 {len(r.failed)} 项，见 summary.json")
    if r.stopped:
        print(r.stopped)
    print(f"产物：{r.out / 'signals.csv'}、{r.out / 'reviews.csv'}、{r.out / 'summary.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    helps = {"trustpilot": "Trustpilot 商家域名", "google-play": "Google Play 应用 ID",
             "app-store": "App Store 应用 ID", "google-shopping": "Google Shopping 商品搜索词",
             "google-maps": "Google 地图商家搜索词或 place_id:/cid:"}
    for name, what in helps.items():
        p = sub.add_parser(name, help=f"按{what}取评价")
        p.add_argument("targets", nargs="+", help=what + "，可给多个")
        p.add_argument("--out", required=True, help="产物目录")
        p.add_argument("--depth", type=int, default={"trustpilot": 20, "google-play": 150, "app-store": 25,
                                                     "google-shopping": 20, "google-maps": 20}[name],
                       help="每个对象（每个星级）取几条；按平台的计费单位取整最省钱")
        if name == "google-maps":
            p.add_argument("--sort", choices=["newest", "relevant", "lowest", "highest"], default="relevant",
                           help="最新、最相关、最低分优先（找决策摩擦）或最高分优先")
        elif name != "google-shopping":
            p.add_argument("--sort", choices=["newest", "relevant"], default="relevant", help="最新或最相关")
        if name != "trustpilot":
            p.add_argument("--country", default="", help="市场国家代码，如 us、th、tw")
            p.add_argument("--location-code", type=int, help="直接给 DataForSEO location_code（覆盖 --country）")
            p.add_argument("--lang", required=True, help="语言代码，如 en、th")
        if name == "google-play":
            p.add_argument("--rating", type=int, nargs="+", choices=range(1, 6),
                           help="只取这几个星级（每个星级单独一个任务）")
        if name == "google-shopping":
            p.add_argument("--products", type=int, default=3, help="取搜索结果前几个有评价的商品")
        if name in ("google-shopping", "google-maps"):
            p.add_argument("--match", default="", help="商品标题或商家名必须含这个词，如品牌名")
        p.add_argument("--product-line", default="", help="写入 产品线 列")
        p.add_argument("--brand", default="", help="写入 涉及品牌 列（评价对象的品牌）")
        p.add_argument("--id-prefix", default="R", help="输入编号前缀，避免与已有买家原话撞号")
        p.add_argument("--budget-usd", type=float, default=1.0, help="本次累计花费上限，默认 1 美元")
        p.add_argument("--wait", type=int, default=600, help="每个任务最多等几秒")
        p.add_argument("--refresh", action="store_true", help="忽略缓存，重新付费采集")
        p.add_argument("--cache-only", action="store_true", help="只用 raw/ 缓存，不发付费调用")
    args = ap.parse_args()
    for attr, default in (("sort", "relevant"), ("country", ""), ("location_code", None), ("lang", ""),
                          ("rating", None), ("products", 0), ("match", "")):
        if not hasattr(args, attr):
            setattr(args, attr, default)
    if args.command != "trustpilot" and not args.country and not args.location_code:
        ap.error("要给 --country 或 --location-code")
    try:
        r = Runner(args)
        rows, per_target = run(r, args.command, args.targets)
        write_outputs(r, args.command, rows, per_target)
        return 1 if r.stopped else 0
    except (kd.Fatal, LookupError) as e:
        print(f"停止：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
