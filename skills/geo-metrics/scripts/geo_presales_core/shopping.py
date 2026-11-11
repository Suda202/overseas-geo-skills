"""Shopping GEO：商品卡抽取、品牌归属与购物指标（2026-10-14，对标 Profound Shopping Analysis）。

三层数据，三个计数单位，不能混用：

| 层 | 单位 | 回答的问题 |
|---|---|---|
| 回答（是否触发购物） | 回答 | 品牌有没有进购物结果 |
| 商品卡（Product Card） | 卡 | 哪些具体商品被展示、排第几 |
| 购买选项（Offer） | offer | 商品展示后从哪个商家买 |

一张卡对应多个 offer，所以商品曝光与商家份额的分母不同。

**商品卡抽取只在这里实现一次**（`extract_product_cards`）。crawl-integrity 与
report-builder 都引用它，不各自解析平台字段——平台字段分层踩过的坑全记在下面的
`PLATFORM_PRODUCT_FIELDS` 注释里，复制一份就会有一份忘了。

口径（Suda 2026-10-14 裁定）：
- 四个平台（ChatGPT / AIO / AI Mode / Gemini）分开算，不跨平台合并——各平台每条回答的
  卡数量级不同（Gemini 12–19 张，ChatGPT 1–6 张），合池后排名没有意义。
- 发现、替代两类题（SHOPPING_SCOPE_INTENTS，2026-11-07 Suda 收窄）进汇总：商品卡触发率、商品卡提及率、
  卡位都只用这两类；按意图类型筛选靠报告切片，这里另给全部意图的触发率拆分
  （shopping_mode_rate_by_intent）作诊断。Suda 2026-11-06 定，口径见 metric-scope-and-copy-contract.md。
- 没有商品字段的平台（Perplexity）返回 None，显示「—」，不按 0% 计。
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from .config import all_objects
from .util import domain_matches, find_alias_spans, normalize_host, resolve_alias_spans


# 平台 → 商品卡在哪个字段。未登记的平台不支持购物指标（返回 None，不是空列表）。
#
# - chatgpt：`products[]`。实测 1761 张卡里 130 张是空占位（title/offers/id 全空），必须丢弃后再编位。
# - overview（AIO）：取 `source[]` 里 `type == "product"`，**不取 `products[]`**。
#   依据一（Scrapeless 文档 google-ai-overview「Data field」）：Source = "products inside ai overview"，
#   product_position 取 recommended / inline_link / reference，`type == "ads product"` 是广告（排除）；
#   Products = "Google wale sponsored products"。文档另一处又说 shopping=true 时 products 带
#   「每个商品簇背后的商家报价」，两处说法不一致，已列为待供应商确认。
#   依据二（2026-10-14 实测全量 AIO 数据）：products 379 项里 371 项的商品名不在同一回答的
#   AI 概览商品里，section_title 是 People also ask / Popular products / Videos / Deals 等页面区块名。
# - aimode / gemini：`products[]`，带 `brand` 与 `stores[]`。Gemini 未与页面 DOM 核验，按交付字段为准。
PLATFORM_PRODUCT_FIELDS = {
    "chatgpt": "products",
    "overview": "source[type=product]",
    "aimode": "products",
    "gemini": "products",
}


# 进商品卡汇总的意图类型（后端 diagnostic_intent 内部值）。评估、验证、问题解决、售后照常抽卡，不进汇总。
SHOPPING_SCOPE_INTENTS = ("discovery", "alternatives")


def product_field_returned(platform: str | None, task_result: dict | None) -> bool | None:
    """这条回答的平台响应里有没有商品字段（有字段、哪怕是空列表也算返回了）。

    用来区分「平台没出商品卡」和「采集接口没返回商品字段」：2026-10 中起 Scrapeless 的 Gemini
    1,700 多条回答一条都不带 ``products``，AI Mode 出卡时才带。整个平台在本次采集里一条都不带时，
    报告写「接口未返回」，不按 0% 计。平台不支持购物字段时返回 None。
    """
    name = str(platform or "").casefold()
    if name not in PLATFORM_PRODUCT_FIELDS:
        return None
    result = task_result if isinstance(task_result, dict) else {}
    return ("source" if name == "overview" else "products") in result


UNMATCHED_SKU = "未识别型号"


def sku_of(card: dict, sku_map: list[dict]) -> str:
    """本品商品卡归到哪个 SKU：按 ``config["sku_map"]`` 的顺序，第一条正则命中卡标题（或 offer 里的
    product_name）的胜出；都不中记「未识别型号」。同一款产品 AI 会写成好几种标题（「H1 4-Camera
    Multi-Channel」「H1 4-Channel Multi-Camera」），所以按型号 + 路数归并，不按标题原样数（2026-11-07）。"""
    text = " ".join(filter(None, [_text(card.get("title")), _text(card.get("offer_product_name"))]))
    for rule in sku_map or []:
        if re.search(rule["pattern"], text, re.I):
            return rule["name"]
    return UNMATCHED_SKU


def shopping_supported(platform: str | None) -> bool:
    return str(platform or "").casefold() in PLATFORM_PRODUCT_FIELDS


def _text(value) -> str:
    return str(value or "").strip()


def _offer(merchant, url, price, available=None) -> dict | None:
    merchant = _text(merchant)
    url = _text(url) or None
    if not merchant and not url:
        return None
    return {"merchant": merchant or None, "url": url, "price": _text(price) or None, "available": available}


def _google_store_offers(stores) -> list[dict]:
    offers = []
    for store in stores or []:
        if isinstance(store, dict):
            item = _offer(store.get("name"), store.get("link"), store.get("total_price") or store.get("price"))
            if item:
                offers.append(item)
    return offers


def chatgpt_catalog_backed(raw: dict) -> bool:
    """ChatGPT 的 ``products`` 条目是不是带商品目录的购物卡（2026-11-11 Suda 定：只有这种才算商品卡）。

    ChatGPT 购物卡来自商品目录，条目带 ``id``、``cite``（turn0productN）、``offers`` 或 ``price``。
    没有商品目录的市场（肯尼亚、尼日利亚实测）回答里也有带图的商品推荐，Scrapeless 照样放进
    ``products``，但只有 ``title`` 和 ``query``：回答页上没有价格、商家和购买入口，图片是网页配图。
    这类条目和「RivalH1」「Facebook Marketplace」这种非商品条目一样，不算商品卡。
    全项目实测：美国 1,333 条带目录证据、2 条不带；肯尼亚、尼日利亚 10,822 条全不带。
    """
    return bool(_text(raw.get("id")) or _text(raw.get("cite")) or raw.get("offers") or _text(raw.get("price")))


def extract_product_cards(platform: str | None, task_result: dict | None) -> list[dict] | None:
    """平台原始 `task_result` → 规范化商品卡列表；平台不支持购物字段时返回 None。

    `position` 是去掉占位与广告后、在平台字段中的 1 起顺序。ChatGPT 实测与正文商品表顺序
    约 5% 不一致，因此卡位只作内部字段。
    """
    name = str(platform or "").casefold()
    if name not in PLATFORM_PRODUCT_FIELDS:
        return None
    result = task_result if isinstance(task_result, dict) else {}
    cards: list[dict] = []

    if name == "chatgpt":
        for raw in result.get("products") or []:
            if not isinstance(raw, dict) or not _text(raw.get("title")):
                continue
            if not chatgpt_catalog_backed(raw):
                continue
            offers = [
                item for item in (
                    _offer(o.get("merchant_name"), o.get("url"), o.get("price"), o.get("available"))
                    for o in raw.get("offers") or [] if isinstance(o, dict)
                ) if item
            ]
            product_name = next((_text(o.get("product_name")) for o in raw.get("offers") or []
                                 if isinstance(o, dict) and _text(o.get("product_name"))), None)
            cards.append({
                "title": _text(raw.get("title")),
                "brand_hint": None,
                "offer_product_name": product_name,
                "price": _text(raw.get("price")) or None,
                "rating": raw.get("rating"),
                "review_count": raw.get("num_reviews"),
                "offers": offers,
            })
    elif name == "overview":
        for raw in result.get("source") or []:
            if not isinstance(raw, dict) or _text(raw.get("type")).casefold() != "product":
                continue
            if not _text(raw.get("title")):
                continue
            offers = _google_store_offers(raw.get("stores"))
            if not offers:
                fallback = _offer(raw.get("website_name"), None, None)
                offers = [fallback] if fallback else []
            cards.append({
                "title": _text(raw.get("title")),
                "brand_hint": None,
                "offer_product_name": None,
                "price": offers[0]["price"] if offers else None,
                "rating": None,
                "review_count": None,
                "offers": offers,
            })
    else:  # aimode / gemini
        for raw in result.get("products") or []:
            if not isinstance(raw, dict) or not _text(raw.get("title")):
                continue
            offers = _google_store_offers(raw.get("stores"))
            if not offers:
                fallback = _offer(raw.get("seller"), None, raw.get("price"))
                offers = [fallback] if fallback else []
            cards.append({
                "title": _text(raw.get("title")),
                "brand_hint": _text(raw.get("brand")) or None,
                "offer_product_name": None,
                "price": _text(raw.get("price") or raw.get("price_range")) or None,
                "rating": raw.get("rating"),
                "review_count": raw.get("reviews") if "reviews" in raw else raw.get("review_count"),
                "offers": offers,
            })

    for position, card in enumerate(cards, 1):
        card["position"] = position
        card["source_field"] = PLATFORM_PRODUCT_FIELDS[name]
    return cards


def _match_object(text: str | None, objects: list[dict]) -> str | None:
    if not text:
        return None
    candidates = [
        {**span, "object_id": obj["object_id"]}
        for obj in objects
        for span in find_alias_spans(text, obj["aliases"], obj.get("case_sensitive_aliases"))
    ]
    resolved = resolve_alias_spans(candidates)
    return resolved[0]["object_id"] if resolved else None


def attribute_cards(cards: list[dict] | None, objects: list[dict]) -> list[dict] | None:
    """给每张卡挂品牌对象，给每个 offer 判官方店 / 第三方。

    归属顺序：平台 `brand` 字段 → 卡标题里最早出现的别名 → offer 的 product_name →
    商家名（仅当全部可识别商家指向同一品牌）。都不中的卡保留，`object_id = None`，
    在指标里单独计数，不丢弃也不猜。

    官方店：offer 域名命中该品牌官网域名，或商家名命中该品牌别名（Google 的 stores
    链接常是 `/goto?url=…` 跳转串，域名对不上，只能看商家名，如「RivalB1 Official」）。
    """
    if cards is None:
        return None
    by_id = {obj["object_id"]: obj for obj in objects}
    out = []
    for card in cards:
        row = {**card, "offers": [dict(o) for o in card.get("offers") or []]}
        method = None
        object_id = _match_object(row.get("brand_hint"), objects)
        if object_id:
            method = "brand_field"
        else:
            object_id = _match_object(row.get("title"), objects)
            if object_id:
                method = "title"
            else:
                object_id = _match_object(row.get("offer_product_name"), objects)
                method = "offer_product_name" if object_id else None
        if not object_id:
            # AIO 的卡常只写型号（「G3」「G5」），卖家却是品牌官方店（「Abrand」）。
            # 只在全部可识别商家名指向同一个品牌时归属；指向多个品牌视为歧义，保持未归属。
            merchant_owners = {_match_object(o.get("merchant"), objects) for o in row["offers"]} - {None}
            if len(merchant_owners) == 1:
                object_id, method = merchant_owners.pop(), "merchant_name"
        row["object_id"] = object_id
        row["attribution_method"] = method
        owner = by_id.get(object_id)
        for offer in row["offers"]:
            if not owner:
                offer["channel"] = "unknown"
                continue
            host = normalize_host(offer["url"]) if offer.get("url", "") and "://" in offer["url"] else ""
            official = bool(host) and any(domain_matches(host, d) for d in owner["official_domains"])
            if not official and offer.get("merchant"):
                official = bool(find_alias_spans(offer["merchant"], owner["aliases"], owner.get("case_sensitive_aliases")))
            offer["channel"] = "official" if official else "third_party"
        out.append(row)
    return out


# ------------------------------------------------------------------ 指标

def _merchant_key(name: str | None) -> str | None:
    value = unicodedata.normalize("NFKC", _text(name))
    return re.sub(r"\s+", " ", value).casefold() or None


def _title_key(title: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", title)).strip().casefold()


def compute_shopping_metrics(config: dict, valid_answers: list[dict], percent, average,
                             is_discovery, top_n: int = 20) -> dict:
    """按平台分开计算购物指标。``percent`` / ``average`` / ``is_discovery`` 由 metrics.py 注入，
    保证舍入与 Discovery 判定和其他指标同一实现。"""
    objects = {obj["object_id"]: obj for obj in all_objects(config)}
    target_id = config["target_object_id"]
    by_platform_answers: dict[str, list[dict]] = defaultdict(list)
    unsupported = set()
    for answer in valid_answers:
        platform = str(answer.get("engine") or "").casefold() or "unknown"
        if answer.get("product_cards") is None:
            unsupported.add(platform)
            continue
        by_platform_answers[platform].append(answer)

    def obj_meta(object_id):
        obj = objects.get(object_id) or {}
        return {"object_id": object_id, "name": obj.get("canonical_name"), "role": obj.get("role")}

    result: dict[str, dict] = {}
    for platform, answers in sorted(by_platform_answers.items()):
        triggered = [a for a in answers if a["product_cards"]]
        intents: dict[str, list[dict]] = defaultdict(list)
        for answer in answers:
            intents[str(answer.get("diagnostic_intent") or "unknown")].append(answer)
        by_intent = {
            intent: percent(sum(1 for a in items if a["product_cards"]), len(items))
            for intent, items in sorted(intents.items())
        }

        scoped = [a for a in answers if is_discovery(a)
                  or str(a.get("diagnostic_intent") or "").casefold() in SHOPPING_SCOPE_INTENTS]
        shopping = [a for a in scoped if a["product_cards"]]
        flags = [(a.get("provenance") or {}).get("product_field_returned") for a in answers]
        # 旧数据没有这个标记（None）时按返回过处理，不误报
        field_returned = any(f is not False for f in flags)

        # ---- Brands：回答级去重
        present: dict[str, list[dict]] = defaultdict(list)   # object_id -> answers
        first_pos: dict[str, list[int]] = defaultdict(list)
        card_counts: Counter = Counter()
        unattributed = 0
        official_link: dict[str, int] = Counter()   # 本品牌的卡里带官网购买链接的回答数
        for answer in shopping:
            seen = {}
            linked = set()
            for card in answer["product_cards"]:
                oid = card.get("object_id")
                if not oid:
                    unattributed += 1
                    continue
                card_counts[oid] += 1
                seen.setdefault(oid, card["position"])
                if any(offer.get("channel") == "official" for offer in card.get("offers") or []):
                    linked.add(oid)
            for oid, pos in seen.items():
                present[oid].append(answer)
                first_pos[oid].append(pos)
            for oid in linked:
                official_link[oid] += 1
        brand_ids = [oid for oid, obj in objects.items() if obj["role"] in ("target", "competitor")]
        brand_ids += sorted((oid for oid in present if oid not in brand_ids),
                            key=lambda oid: (-len(present[oid]), objects[oid]["canonical_name"]))
        brands = []
        for oid in brand_ids:
            brands.append({
                **obj_meta(oid),
                "shopping_visibility": {**percent(len(present[oid]), len(shopping), 1),
                                        "included_answer_ids": [a["answer_id"] for a in present[oid]]},
                "shopping_exposure_rate": percent(len(present[oid]), len(scoped), 1),
                "average_card_position": average(first_pos[oid]),
                # 官网购买链接覆盖率：本品牌的卡里至少一张带官网购买链接的回答 ÷ 出现本品牌卡的回答
                "official_link_coverage": percent(official_link[oid], len(present[oid]), 1),
                "card_count": card_counts[oid],
            })
        brands.sort(key=lambda row: (-(row["shopping_visibility"]["raw"] or 0),
                                     row["role"] != "target", row["name"] or ""))

        # ---- SKU 级（只看本品）：分母同品牌级，是出现商品卡的回答；同一回答里同一 SKU 只算一次，
        # 位置取该 SKU 在这条回答里最靠前的那张卡。没配 sku_map 时只有「未识别型号」一行，不展示。
        sku_map = config.get("sku_map") or []
        sku_answers: dict[str, list[int]] = defaultdict(list)
        sku_linked: Counter = Counter()
        for answer in shopping:
            seen_sku: dict[str, int] = {}
            linked_sku = set()
            for card in answer["product_cards"]:
                if card.get("object_id") != target_id:
                    continue
                name = sku_of(card, sku_map)
                seen_sku.setdefault(name, card["position"])
                if any(offer.get("channel") == "official" for offer in card.get("offers") or []):
                    linked_sku.add(name)
            for name, pos in seen_sku.items():
                sku_answers[name].append(pos)
            for name in linked_sku:
                sku_linked[name] += 1
        order = [rule["name"] for rule in sku_map] + [UNMATCHED_SKU]
        target_skus = [
            {"name": name,
             "shopping_visibility": percent(len(sku_answers[name]), len(shopping), 1),
             "average_card_position": average(sku_answers[name]),
             "official_link_coverage": percent(sku_linked[name], len(sku_answers[name]), 1)}
            for name in dict.fromkeys(order) if name in sku_answers
        ] if sku_map else []

        # ---- Prompt 级下钻
        by_question: dict[str, dict] = {}
        for answer in scoped:
            row = by_question.setdefault(answer["question_id"], {
                "valid_answers": 0, "shopping_answers": 0, "target_present_answers": 0, "brands": Counter()})
            row["valid_answers"] += 1
            if answer["product_cards"]:
                row["shopping_answers"] += 1
                ids = {c.get("object_id") for c in answer["product_cards"] if c.get("object_id")}
                row["target_present_answers"] += target_id in ids
                row["brands"].update(objects[oid]["canonical_name"] for oid in ids)
        for row in by_question.values():
            row["shopping_mode_rate"] = percent(row["shopping_answers"], row["valid_answers"], 1)
            # ids 是 set，Counter 的插入顺序随哈希种子变，同数时 most_common 会每次跑出不同顺序；
            # 同数按品牌名排，保证同一份数据两次运行结果一致。
            row["brands"] = [name for name, _ in sorted(row["brands"].items(),
                                                        key=lambda kv: (-kv[1], kv[0].casefold()))[:5]]

        result[platform] = {
            "valid_answers": len(answers),
            "product_field_returned": field_returned,
            "scope_answers": len(scoped),
            "shopping_answers": len(shopping),
            "shopping_mode_rate": percent(len(shopping), len(scoped), 1),
            "shopping_mode_rate_by_intent": by_intent,
            "all_intent_shopping_answers": len(triggered),
            "card_count": sum(len(a["product_cards"]) for a in shopping),
            "unattributed_card_count": unattributed,
            "cards_without_offers": sum(1 for a in shopping for c in a["product_cards"] if not c["offers"]),
            "brands": brands,
            "target": next(row for row in brands if row["object_id"] == target_id),
            "target_skus": target_skus,
            "by_question": by_question,
        }

    return {
        "schema_version": "geo-presales-shopping/v1",
        "scope_intents": list(SHOPPING_SCOPE_INTENTS),
        "by_platform": result,
        "unsupported_platforms": sorted(unsupported - set(result)),
        "methodology": {
            "platform_scope": "按平台分开计算，不跨平台合并；无商品字段的平台不计（显示 —）",
            "card_source": {k: v for k, v in PLATFORM_PRODUCT_FIELDS.items()},
            "intent_scope": "发现、替代两类题进汇总；shopping_mode_rate_by_intent 另给全部意图的触发率",
            "shopping_mode_rate_denominator": "该平台发现、替代题的有效回答；分子为其中至少有一张商品卡的回答",
            "shopping_visibility_denominator": "该平台发现、替代题里出现商品卡的有效回答；分子为至少有一张该品牌商品卡的回答（回答级去重）",
            "shopping_exposure_rate_denominator": "该平台发现、替代题的有效回答（推导指标 = 商品卡提及率 × 商品卡触发率）",

            "average_card_position": "品牌/商品在回答内首张卡的位置（平台字段顺序，1 起）取平均",
            "product_field_returned": "本次采集里该平台有没有任何一条回答带商品字段；没有时报告写「接口未返回」",
            "official_link_coverage": "出现该品牌（或 SKU）商品卡的回答里，这些卡至少带一个官网购买链接的占比；官网 = 链接域名是品牌官网，或商家名带品牌名",
            "target_skus": "本品 SKU 级：按 config.sku_map 把卡标题归到型号；商品卡提及率分母同品牌级（出现商品卡的回答），位置取该 SKU 最靠前的卡",

            "card_attribution": "平台 brand 字段 → 卡标题最早别名 → offer product_name；都不中记未归属",
            "excluded": "空占位卡、广告卡、AIO products 字段（文档定义为 sponsored products，非 AI 概览内商品）、无效回答",
        },
    }
