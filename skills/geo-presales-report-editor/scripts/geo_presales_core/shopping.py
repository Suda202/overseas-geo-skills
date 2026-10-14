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
- 购物触发率用全部有效回答，按诊断意图拆开报；购物可见度、商品、商家、卡位只用 Discovery，
  与正式可见度同口径（题面带品牌的题会必然抬高本品牌）。
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
        for span in find_alias_spans(text, obj["aliases"])
    ]
    resolved = resolve_alias_spans(candidates)
    return resolved[0]["object_id"] if resolved else None


def attribute_cards(cards: list[dict] | None, objects: list[dict]) -> list[dict] | None:
    """给每张卡挂品牌对象，给每个 offer 判官方店 / 第三方。

    归属顺序：平台 `brand` 字段 → 卡标题里最早出现的别名 → offer 的 product_name →
    商家名（仅当全部可识别商家指向同一品牌）。都不中的卡保留，`object_id = None`，
    在指标里单独计数，不丢弃也不猜。

    官方店：offer 域名命中该品牌官网域名，或商家名命中该品牌别名（Google 的 stores
    链接常是 `/goto?url=…` 跳转串，域名对不上，只能看商家名，如「70mai Official」）。
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
            # AIO 的卡常只写型号（「G3」「G5」），卖家却是品牌官方店（「Bewinch」）。
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
                official = bool(find_alias_spans(offer["merchant"], owner["aliases"]))
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

        discovery = [a for a in answers if is_discovery(a)]
        shopping = [a for a in discovery if a["product_cards"]]

        # ---- Brands：回答级去重
        present: dict[str, list[dict]] = defaultdict(list)   # object_id -> answers
        first_pos: dict[str, list[int]] = defaultdict(list)
        card_counts: Counter = Counter()
        unattributed = 0
        for answer in shopping:
            seen = {}
            for card in answer["product_cards"]:
                oid = card.get("object_id")
                if not oid:
                    unattributed += 1
                    continue
                card_counts[oid] += 1
                seen.setdefault(oid, card["position"])
            for oid, pos in seen.items():
                present[oid].append(answer)
                first_pos[oid].append(pos)
        brand_ids = [oid for oid, obj in objects.items() if obj["role"] in ("target", "competitor")]
        brand_ids += sorted((oid for oid in present if oid not in brand_ids),
                            key=lambda oid: (-len(present[oid]), objects[oid]["canonical_name"]))
        brands = []
        for oid in brand_ids:
            brands.append({
                **obj_meta(oid),
                "shopping_visibility": {**percent(len(present[oid]), len(shopping)),
                                        "included_answer_ids": [a["answer_id"] for a in present[oid]]},
                "shopping_exposure_rate": percent(len(present[oid]), len(discovery)),
                "average_card_position": average(first_pos[oid]),
                "card_count": card_counts[oid],
            })
        brands.sort(key=lambda row: (-(row["shopping_visibility"]["raw"] or 0),
                                     row["role"] != "target", row["name"] or ""))

        # ---- Products：卡级
        products: dict[tuple, dict] = {}
        for answer in shopping:
            target_absent = not any(c.get("object_id") == target_id for c in answer["product_cards"])
            for card in answer["product_cards"]:
                key = (card.get("object_id") or _text(card.get("brand_hint")).casefold() or None,
                       _title_key(card["title"]))
                item = products.setdefault(key, {
                    "title": card["title"], "object_id": card.get("object_id"),
                    "brand_hint": card.get("brand_hint"), "answers": {}, "merchants": Counter(),
                    "questions": set(), "target_absent_answers": set(),
                })
                item["answers"].setdefault(answer["answer_id"], card["position"])
                item["questions"].add(answer["question_id"])
                if target_absent:
                    item["target_absent_answers"].add(answer["answer_id"])
                for offer in card["offers"]:
                    if offer.get("merchant"):
                        item["merchants"][offer["merchant"]] += 1

        def product_row(item):
            meta = obj_meta(item["object_id"]) if item["object_id"] else {
                "object_id": None, "name": item["brand_hint"], "role": None}
            return {
                "title": item["title"], **meta,
                "answer_count": len(item["answers"]),
                "exposure_rate": percent(len(item["answers"]), len(shopping)),
                "average_card_position": average(list(item["answers"].values())),
                "question_ids": sorted(item["questions"]),
                "merchants": [name for name, _ in item["merchants"].most_common(5)],
            }

        ranked = sorted(products.values(), key=lambda it: (-len(it["answers"]), it["title"].casefold()))
        target_absent_ids = {a["answer_id"] for a in shopping
                             if not any(c.get("object_id") == target_id for c in a["product_cards"])}
        gap_items = sorted(
            (it for it in products.values()
             if it["target_absent_answers"] and (objects.get(it["object_id"]) or {}).get("role") == "competitor"),
            key=lambda it: (-len(it["target_absent_answers"]), it["title"].casefold()),
        )

        # ---- Merchants：offer 级。同一回答内「商家 + 链接」相同的 offer 只计一次——
        # Gemini 会把同一商品列成两张卡、卡内还重复同一变体链接（Botslab US 0001 实测），
        # 不去重会把该商家份额按重复次数放大。无链接时退回「商家 + 卡标题」。
        offers = []
        for answer in shopping:
            seen_offers = set()
            for card in answer["product_cards"]:
                for offer in card["offers"]:
                    key = (_merchant_key(offer.get("merchant")),
                           offer.get("url") or _title_key(card["title"]))
                    if key in seen_offers:
                        continue
                    seen_offers.add(key)
                    offers.append((card, offer))
        merchant_rows: dict[str, dict] = {}
        for card, offer in offers:
            key = _merchant_key(offer.get("merchant")) or f"(无商家名) {normalize_host(offer.get('url') or '')}"
            row = merchant_rows.setdefault(key, {"merchant": offer.get("merchant") or key,
                                                 "offers": 0, "target_offers": 0, "official_offers": 0})
            row["offers"] += 1
            row["target_offers"] += card.get("object_id") == target_id
            row["official_offers"] += offer.get("channel") == "official"
        merchants = [
            {
                "merchant": row["merchant"],
                "offer_count": row["offers"],
                "merchant_share": percent(row["offers"], len(offers)),
                "target_brand_share": percent(row["target_offers"], row["offers"]),
                "official_offer_count": row["official_offers"],
            }
            for row in sorted(merchant_rows.values(), key=lambda r: (-r["offers"], r["merchant"].casefold()))
        ]
        target_offers = [offer for card, offer in offers if card.get("object_id") == target_id]
        channel_counts = Counter(offer.get("channel") for offer in target_offers)

        # ---- Prompt 级下钻
        by_question: dict[str, dict] = {}
        for answer in discovery:
            row = by_question.setdefault(answer["question_id"], {
                "valid_answers": 0, "shopping_answers": 0, "target_present_answers": 0, "brands": Counter()})
            row["valid_answers"] += 1
            if answer["product_cards"]:
                row["shopping_answers"] += 1
                ids = {c.get("object_id") for c in answer["product_cards"] if c.get("object_id")}
                row["target_present_answers"] += target_id in ids
                row["brands"].update(objects[oid]["canonical_name"] for oid in ids)
        for row in by_question.values():
            row["shopping_mode_rate"] = percent(row["shopping_answers"], row["valid_answers"])
            row["brands"] = [name for name, _ in row["brands"].most_common(5)]

        result[platform] = {
            "valid_answers": len(answers),
            "shopping_answers": len(triggered),
            "shopping_mode_rate": percent(len(triggered), len(answers)),
            "shopping_mode_rate_by_intent": by_intent,
            "discovery_answers": len(discovery),
            "discovery_shopping_answers": len(shopping),
            "discovery_shopping_mode_rate": percent(len(shopping), len(discovery)),
            "card_count": sum(len(a["product_cards"]) for a in shopping),
            "unattributed_card_count": unattributed,
            "cards_without_offers": sum(1 for a in shopping for c in a["product_cards"] if not c["offers"]),
            "brands": brands,
            "target": next(row for row in brands if row["object_id"] == target_id),
            "products": [product_row(it) for it in ranked[:top_n]],
            "target_products": [product_row(it) for it in ranked if it["object_id"] == target_id],
            "target_absent_shopping_answers": len(target_absent_ids),
            "competitor_products_where_target_absent": [
                {**product_row(it), "target_absent_answer_count": len(it["target_absent_answers"])}
                for it in gap_items[:top_n]
            ],
            "offer_count": len(offers),
            "merchants": merchants[:top_n],
            "target_offer_channel": {
                "offer_count": len(target_offers),
                "official": percent(channel_counts["official"], len(target_offers)),
                "third_party": percent(channel_counts["third_party"], len(target_offers)),
            },
            "by_question": by_question,
        }

    return {
        "schema_version": "geo-presales-shopping/v1",
        "by_platform": result,
        "unsupported_platforms": sorted(unsupported - set(result)),
        "methodology": {
            "platform_scope": "按平台分开计算，不跨平台合并；无商品字段的平台不计（显示 —）",
            "card_source": {k: v for k, v in PLATFORM_PRODUCT_FIELDS.items()},
            "shopping_mode_rate_denominator": "该平台全部有效回答；分子为至少有一张商品卡的回答；按诊断意图另拆",
            "shopping_visibility_denominator": "该平台触发购物的有效 Discovery 回答；分子为至少有一张该品牌商品卡的回答（回答级去重）",
            "shopping_exposure_rate_denominator": "该平台全部有效 Discovery 回答（推导指标 = 购物可见度 × Discovery 触发率）",
            "product_exposure_denominator": "该平台触发购物的有效 Discovery 回答；同一商品在一条回答内只计一次",
            "average_card_position": "品牌/商品在回答内首张卡的位置（平台字段顺序，1 起）取平均；仅内部字段",
            "merchant_share_denominator": "该平台触发购物的 Discovery 回答中全部购买选项（offer）；同一回答内商家+链接相同只计一次",
            "target_brand_share_by_merchant": "某商家的 offer 中属于目标品牌商品卡的比例",
            "official_channel_rule": "offer 域名命中品牌官网域名，或商家名命中该品牌别名",
            "card_attribution": "平台 brand 字段 → 卡标题最早别名 → offer product_name；都不中记未归属",
            "excluded": "空占位卡、广告卡、AIO products 字段（文档定义为 sponsored products，非 AI 概览内商品）、无效回答",
        },
    }
