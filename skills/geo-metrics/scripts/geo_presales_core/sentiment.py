"""正向情感占比的唯一实现（Claim 信号口径，2026-09-20 定稿；2026-11-13 收成一份）。

claims-metrics（sentiment_sentences.py）、售前报告和监测基线的情感接入（attach_sentiment.py）
都调这里，不各写一份：

  * 最小单位 = 回答（地区 × 平台 × 题号 × 第几次） × 品牌 × claim × 方向；
  * 同一回答内同品牌、同 claim 文本、同方向只计 1 次（语义归一在抽取环节做，这里按文本兜底）；
    同一 Attribute 下不同 claim 各计一次；跨回答分别计数；
  * 只认正向、负向两种方向，不设中性；
  * 正向占比 = 正向信号 ÷（正向 + 负向）；
  * 跨平台先算各平台占比，再对有信号的平台等权平均，无信号平台不补 0。

报告页面里的多选筛选在浏览器里现算（report-engine.js），用同一套规则，由 check_engine_parity.js 对账。
"""
from __future__ import annotations

DIRECTIONS = ("positive", "negative")


def norm_claim_text(text) -> str:
    """去重用的 claim 文本归一：压空白 + casefold。"""
    return " ".join(str(text or "").split()).casefold()


def answer_key(claim: dict) -> tuple:
    return (claim.get("region", ""), claim.get("platform", ""), claim.get("idx"), claim.get("repeat"))


def claim_signals(claims: list[dict], brands=None) -> list[dict]:
    """去重后的 Claim 信号（保留每个信号第一次出现的那条 claim）。brands 给了就只留这些品牌。"""
    wanted = set(brands) if brands is not None else None
    seen: set[tuple] = set()
    out = []
    for c in claims:
        brand = c.get("brand")
        direction = c.get("sentiment")
        if direction not in DIRECTIONS or (wanted is not None and brand not in wanted):
            continue
        key = (brand, answer_key(c), norm_claim_text(c.get("claim")), direction)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def positive_share(pos: int, neg: int) -> str:
    total = pos + neg
    return f"{pos / total * 100:.1f}%" if total else "—"


def brand_signal_stats(signals: list[dict], brands: list[str]) -> dict:
    """按品牌汇总信号：总数、正负、正向占比、跨平台等权、分平台、分 Attribute、分 Theme。"""
    per_platform: dict[tuple, dict] = {}
    per_attr: dict[tuple, int] = {}
    per_theme: dict[tuple, int] = {}
    for c in signals:
        brand, direction = c.get("brand"), c.get("sentiment")
        bucket = per_platform.setdefault((brand, c.get("platform", "")), {"pos": 0, "neg": 0})
        bucket["pos" if direction == "positive" else "neg"] += 1
        attr_key = (brand, c.get("attribute") or "", direction)
        per_attr[attr_key] = per_attr.get(attr_key, 0) + 1
        theme_key = (brand, c.get("theme") or "", direction)
        per_theme[theme_key] = per_theme.get(theme_key, 0) + 1

    stats = {}
    for brand in brands:
        pos = sum(v for (b, _a, s), v in per_attr.items() if b == brand and s == "positive")
        neg = sum(v for (b, _a, s), v in per_attr.items() if b == brand and s == "negative")
        platform_rates = [v["pos"] / (v["pos"] + v["neg"])
                          for (b, _p), v in sorted(per_platform.items()) if b == brand and v["pos"] + v["neg"]]
        stats[brand] = {
            "signal_total": pos + neg,
            "positive_signals": pos,
            "negative_signals": neg,
            "pos_rate": positive_share(pos, neg),
            "platforms_with_signal": len(platform_rates),
            "pos_rate_cross_platform": (f"{sum(platform_rates) / len(platform_rates) * 100:.1f}%"
                                        if platform_rates else "—"),
            "by_platform": {
                plat: {"positive": v["pos"], "negative": v["neg"], "pos_rate": positive_share(v["pos"], v["neg"])}
                for (b, plat), v in sorted(per_platform.items()) if b == brand
            },
            "by_attribute": sorted(
                ({"attribute": a, "sentiment": s, "occurrence": v}
                 for (b, a, s), v in per_attr.items() if b == brand),
                key=lambda x: (-x["occurrence"], x["attribute"])),
            "by_theme": sorted(
                ({"theme": t, "sentiment": s, "occurrence": v}
                 for (b, t, s), v in per_theme.items() if b == brand),
                key=lambda x: (x["theme"], x["sentiment"])),
        }
    return stats
