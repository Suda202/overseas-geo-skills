"""引用来源分类：唯一实现，报告数据层、监测基线和临时统计都调这里。

判定顺序（规则见 geo-metrics/references/metric-scope-and-copy-contract.md「引用来源分类」）：

1. 官网规则：纳入对象（目标、配置竞品、开放品牌）的官网域名，目标 → 自有网站，其余 → 竞品网站；
   都不中时，config 的 `competitor_site_domains` → 竞品网站。
2. 域名规则：内置 `KNOWN_HOST_TYPES` → 运行时缓存 `config["domain_category_cache"]`
   （`geo-presales-report-builder/assets/domain-categories.json`）→ .gov / .edu 后缀。
3. 以上都不中：「未判读」，展示时归「其他」。

「未判读」和缓存里判过的「其他」是两回事：后者有人看过、确认不属于任何一类；前者没人看过。
统计前必须把未判读的域名判完写回缓存，`unjudged_coverage` + `enforce_judged` 是门禁：
未判读引用超过 `UNJUDGED_SHARE_LIMIT` 就停下，并列出待判域名。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .config import all_objects
from .util import domain_matches

SOURCE_TYPES = {
    # 现行 7 类，以《引用来源分类》定义为准。旧版的 corporate_site（企业网站）已取消：
    # 未命中默认类别的企业网站归入 other；开放竞品官网也不进 competitor_official。
    "brand_official": "自有网站",
    "competitor_official": "竞品网站",
    "ugc": "社交平台",
    "media_review": "媒体网站",
    "press_release": "新闻稿平台",
    "institutional": "机构网站",
    "other": "其他",
}

# 已从 SOURCE_TYPES 退休的类别 → 现行类别，按《引用来源分类》的迁移口径。
# 百科类归「机构网站」（政府/非营利/教育/公共机构），企业网站归「其他」。
RETIRED_SOURCE_TYPES = {
    "encyclopedia_reference": "institutional",
    "corporate_site": "other",
}

# 缓存文件只允许这几类；品牌官网由 Case 和词表判，不写进缓存。
CACHE_CATEGORIES = ("media_review", "ugc", "institutional", "press_release", "other")

KNOWN_HOST_TYPES = {
    # 机构网站（Institutions）：政府、非营利组织、教育机构和公共机构的网站。
    # .gov / .edu 由 _known_type 的后缀规则兜住；这里放经确认的高频机构域名
    # （who.int、wikipedia.org、wikimedia.org 等）。
    "baike.baidu.com": "institutional",
    "who.int": "institutional",
    "reddit.com": "ugc",
    "youtube.com": "ugc",
    "facebook.com": "ugc",
    "instagram.com": "ugc",
    "tiktok.com": "ugc",
    "x.com": "ugc",
    "twitter.com": "ugc",
    "quora.com": "ugc",
    "wikipedia.org": "institutional",
    "wikimedia.org": "institutional",
    "wikidata.org": "institutional",
    "britannica.com": "institutional",
    "reuters.com": "media_review",
    "apnews.com": "media_review",
    "forbes.com": "media_review",
    "techcrunch.com": "media_review",
    "searchenginejournal.com": "media_review",
    "g2.com": "media_review",
    "capterra.com": "media_review",
    "trustpilot.com": "media_review",
    "bbb.org": "media_review",
    "github.com": "other",
    "linkedin.com": "other",
}

# 未判读引用占全部引用的上限。超过就停下补判（Suda 2026-11-13：「补判域名」老被跳过，改成门禁）。
UNJUDGED_SHARE_LIMIT = 0.05
# 门禁停下时的退出码：和「输入错误」区分开，流水线据此暂停等判读。
UNJUDGED_EXIT_CODE = 3

# 共享缓存的默认位置（报告 skill 的 assets）。
DEFAULT_CACHE_PATH = (Path(__file__).resolve().parents[3]
                      / "geo-presales-report-builder" / "assets" / "domain-categories.json")


def _known_type(host: str, cache: dict | None = None) -> str | None:
    """域名 → 来源类别；内置表、缓存、.gov/.edu 都不中时返回 None（未判读）。

    历史值兜底：`corporate_site`、`encyclopedia_reference` 等已从 `SOURCE_TYPES`
    退休的分类按迁移口径归并（见 `RETIRED_SOURCE_TYPES`），其余无法识别的值落到
    「其他」。内置表与运行时缓存两条路径都要过一遍——缓存里同样可能残留旧值，
    否则 `SOURCE_TYPES[known]` 会直接 KeyError 打断整条构建。
    """
    def _valid(source_type: str | None) -> str | None:
        if source_type is None:
            return None
        if source_type in SOURCE_TYPES:
            return source_type
        return RETIRED_SOURCE_TYPES.get(source_type, "other")

    for known, source_type in KNOWN_HOST_TYPES.items():
        if host == known or host.endswith("." + known):
            return _valid(source_type)
    if cache:
        for known, source_type in cache.items():
            if host == known or host.endswith("." + known):
                return _valid(source_type)
    if host.endswith(".gov") or ".gov." in host or host.endswith(".edu") or ".edu." in host:
        return "institutional"
    return None


def _classify_official(host: str, objects: list[dict], competitor_sites=()) -> tuple[str | None, str | None]:
    """官网规则：纳入对象的官网按顺序第一个命中的胜出；都不中时，config 的 competitor_site_domains
    （同类平台站点，词表顶层字段，因客户而异，不进共用的域名类别缓存）归「竞品网站」、不挂品牌。"""
    for obj in objects:
        for domain in obj.get("official_domains") or []:
            if domain_matches(host, domain):
                return ("brand_official" if obj.get("role") == "target" else "competitor_official",
                        obj.get("object_id"))
    if any(domain_matches(host, site) for site in competitor_sites):
        return "competitor_official", None
    return None, None


def classify_source(host: str, config: dict) -> dict:
    """一个引用域名的分类结论。

    返回 {source_type, object_id, basis, confidence}；basis 取 official_rule / domain_rule / unjudged。
    unjudged 时 source_type 为 other（展示口径），但它和缓存判过的 other 不同，门禁只数 unjudged。
    """
    objects = all_objects(config) if "objects" in config else []
    source_type, object_id = _classify_official(host, objects, config.get("competitor_site_domains") or ())
    if source_type is None:
        own = config.get("official_domain")
        own = own if isinstance(own, list) else [own]
        if any(d and domain_matches(host, d) for d in own):
            source_type, object_id = "brand_official", "target"
    if source_type:
        return {"source_type": source_type, "object_id": object_id, "basis": "official_rule", "confidence": 1.0}
    known = _known_type(host, config.get("domain_category_cache"))
    if known:
        return {"source_type": known, "object_id": None, "basis": "domain_rule", "confidence": 0.95}
    return {"source_type": "other", "object_id": None, "basis": "unjudged", "confidence": None}


def classify_source_host(host: str, config: dict) -> str:
    """只要类别（展示层用）。"""
    return classify_source(host, config)["source_type"] if host else "other"


def load_cache(path: Path | str | None = None) -> dict:
    """读共享缓存；文件不存在时返回空字典（之后所有域名都是未判读，门禁会拦）。"""
    cache_path = Path(path) if path else DEFAULT_CACHE_PATH
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"域名类别缓存格式应为扁平映射 {{域名: 类别}}，实际为 {type(payload).__name__}")
    bad = {k: v for k, v in payload.items() if v not in CACHE_CATEGORIES}
    if bad:
        sample = ", ".join(f"{k}={v}" for k, v in list(bad.items())[:3])
        raise SystemExit(f"域名类别缓存含未知类别（{sample}），允许值：{'/'.join(CACHE_CATEGORIES)}")
    return payload


def unjudged_coverage(citations) -> dict:
    """citations：可迭代的 {host, basis, title?, url?}。按引用次数（未去重）统计未判读占比。"""
    total = 0
    hosts: dict[str, dict] = {}
    for c in citations:
        if not c.get("host"):
            continue
        total += 1
        if c.get("basis") != "unjudged":
            continue
        item = hosts.setdefault(c["host"], {"domain": c["host"], "count": 0, "titles": [], "sample_urls": []})
        item["count"] += 1
        title = str(c.get("title") or "").strip()
        if title and title not in item["titles"] and len(item["titles"]) < 3:
            item["titles"].append(title[:90])
        url = c.get("url")
        if url and url not in item["sample_urls"] and len(item["sample_urls"]) < 2:
            item["sample_urls"].append(url)
    unjudged = sum(h["count"] for h in hosts.values())
    return {
        "total_citations": total,
        "unjudged_citations": unjudged,
        "unjudged_share": round(unjudged / total, 4) if total else 0.0,
        "limit": UNJUDGED_SHARE_LIMIT,
        "candidates": sorted(hosts.values(), key=lambda h: (-h["count"], h["domain"])),
    }


def enforce_judged(coverage: dict, candidates_path: Path, allow_reason: str = "", label: str = "") -> bool:
    """门禁：未判读超过上限时写待判清单并返回 False（调用方以 UNJUDGED_EXIT_CODE 退出）。

    给了 allow_reason（非空理由）时只告警、返回 True。未判读为 0 时不写文件。
    """
    share, n = coverage["unjudged_share"], len(coverage["candidates"])
    head = f"{label}：" if label else ""
    if n:
        candidates_path = Path(candidates_path)
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(json.dumps(coverage["candidates"], ensure_ascii=False, indent=1), encoding="utf-8")
    if share <= coverage["limit"]:
        if n:
            print(f"{head}引用来源未判读 {share:.1%}（{n} 个域名，上限 {coverage['limit']:.0%}），已列到 {candidates_path}")
        return True
    top = "、".join(f"{c['domain']}({c['count']})" for c in coverage["candidates"][:8])
    if allow_reason.strip():
        print(f"⚠ {head}引用来源未判读 {share:.1%}，超过上限 {coverage['limit']:.0%}，按理由放行：{allow_reason.strip()}。"
              f"待判清单 {candidates_path}")
        return True
    print(f"✗ {head}引用来源未判读 {share:.1%}（{coverage['unjudged_citations']}/{coverage['total_citations']} 次引用、"
          f"{n} 个域名），超过上限 {coverage['limit']:.0%}，停下补判。\n"
          f"  最多的：{top}\n"
          f"  待判清单：{candidates_path}\n"
          f"  做法：逐条读域名和页面标题，判成 {'/'.join(CACHE_CATEGORIES)}，写回 {DEFAULT_CACHE_PATH}，再重跑。\n"
          f"  品牌官网不写进缓存，改 Case 或词表的 official_domains；确实不判时加 --allow-unjudged-domains \"<理由>\"。")
    return False


def judged_counter(citations) -> Counter:
    """按类别数引用次数（unjudged 记成 other），临时统计用。"""
    return Counter(c.get("source_type") or "other" for c in citations if c.get("host"))
