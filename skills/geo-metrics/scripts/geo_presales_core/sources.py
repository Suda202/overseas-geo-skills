"""引用来源分类：唯一实现，报告数据层、监测基线和临时统计都调这里。

判定顺序（规则见 geo-metrics/references/metric-scope-and-copy-contract.md「引用来源分类」）：

1. 官网规则：纳入对象（目标、配置竞品、开放品牌）的官网域名，目标 → 自有网站，其余 → 竞品网站；
   都不中时，config 的 `competitor_site_domains` → 竞品网站。
2. 域名规则（精确 hostname 优先，其次最长父域；有单独判读的子域覆盖父域）：
   内置 `KNOWN_HOST_TYPES` 与运行时缓存 `config["domain_category_cache"]`
   （`geo-metrics/assets/domain-categories.json`）按最长匹配查（子域单独判过就用子域的）
   → 机构后缀（.gov/.edu/.mil，gov.xx/edu.xx/ac.xx/go.xx/gouv.xx）。
3. 以上都不中：「未判读」，展示时归「其他」。

「未判读」和缓存里判过的「其他」是两回事：后者有人看过、确认不属于任何一类；前者没人看过。
统计前必须把未判读的域名判完写回缓存，`unjudged_coverage` + `enforce_judged` 是门禁：
未判读引用超过 `UNJUDGED_SHARE_LIMIT` 就停下，并列出待判域名。单个域名引用不足长尾阈值
（`low_volume_threshold`：min(100, 总引用 1%)，下限 5）的不强制判读，归「其他」并单列统计。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .config import all_objects
from .util import COMMON_MULTI_LABEL_SUFFIXES, domain_matches, normalize_host

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
    # .gov / .edu 等由 _institutional_suffix 兜住；这里放经确认的高频机构域名
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
    # 托管写作平台：每个子域是一个作者，按个人内容归社交平台（2026-11-18）。
    "medium.com": "ugc",
    "substack.com": "ugc",
    "blogspot.com": "ugc",
    "wikipedia.org": "institutional",
    "wikimedia.org": "institutional",
    "wikidata.org": "institutional",
    "britannica.com": "institutional",
    "reuters.com": "media_review",
    "apnews.com": "media_review",
    "forbes.com": "media_review",
    "techcrunch.com": "media_review",
    "searchenginejournal.com": "media_review",
    # 用户评论平台（G2、Capterra、Trustpilot）内容由用户生产，归社交平台（对齐 Profound 的 Social），
    # 放在共享缓存里而不是内置表：这条边界随时可能被推翻，缓存是覆盖表，改一行即可。
    # 多租户托管平台：根域不是单一站点，默认按「其他」；具体子域有证据时在缓存里单独覆盖
    # （如 2.zoppoz.workers.dev 实际是媒体镜像，单独判成媒体）。
    "github.io": "other",
    "pages.dev": "other",
    "workers.dev": "other",
    "netlify.app": "other",
    "vercel.app": "other",
    "web.app": "other",
    "firebaseapp.com": "other",
    "webflow.io": "other",
    "gitbook.io": "other",
    "readthedocs.io": "other",
    "myshopify.com": "other",
    # 代码与数据集开放发布平台：账号主人自己发布，按社交平台算（Suda 2026-11-24）
    "github.com": "ugc",
    "huggingface.co": "ugc",
    "linkedin.com": "ugc",
}

# 未判读引用占全部引用的上限。超过就停下补判（Suda 2026-11-13：「补判域名」老被跳过，改成门禁）。
UNJUDGED_SHARE_LIMIT = 0.05
# 门禁停下时的退出码：和「输入错误」区分开，流水线据此暂停等判读。
UNJUDGED_EXIT_CODE = 3

# 长尾阈值：单个域名在本次引用里不足这个次数，不强制判读，展示归「其他」并标「长尾未判」。
# 100 是 Profound 的口径；小项目按总引用的 1% 收，否则几百条引用的项目会把所有域名都判成长尾。
LOW_VOLUME_CAP = 100
LOW_VOLUME_SHARE = 0.01
LOW_VOLUME_FLOOR = 5


def low_volume_threshold(total_citations: int) -> int:
    return max(LOW_VOLUME_FLOOR, int(min(LOW_VOLUME_CAP, total_citations * LOW_VOLUME_SHARE)))

# 共享缓存的默认位置（报告 skill 的 assets）。
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "assets" / "domain-categories.json"


def _matched_key(host: str, table: dict) -> str:
    """先精确匹配，再从最长的父域往上找，返回命中的键；没命中返回空串。

    单独判过的子域优先于父域。2026-11-18 前按表的顺序取第一个后缀命中，缓存按字母排序，
    `apple.com` 排在 `support.apple.com` 前，子域自己的判读永远查不到。
    移动端子域（m./amp./mobile./wap.）查不到时按主域再查一次：缓存里常只判了 m.dealmoon.com，
    引用里出现 dealmoon.com 时不该落回未判读。
    """
    def lookup(value: str) -> str:
        if value in table:
            return value
        parts = value.split(".")
        for index in range(1, len(parts) - 1):
            parent = ".".join(parts[index:])
            if parent in table:
                return parent
        return ""

    key = lookup(host)
    if key:
        return key
    for prefix in ("m.", "amp.", "mobile.", "wap."):
        if host.startswith(prefix):
            return lookup(host[len(prefix):])
    return ""


# 公共机构后缀：gov/edu/mil 顶级域，或国家域名下的 gov/edu/ac/go/mil/gouv 二级（gov.sg、ac.uk、go.th、gouv.qc.ca）。
_INSTITUTIONAL_TLDS = {"gov", "edu", "mil", "int"}
# Profound 的机构 TLD：.gov/.edu/.mil/.int/.gov./.ac./.nhs./.gouv./.gob.；govt/gv 是新西兰等市场的政府二级
_INSTITUTIONAL_SLDS = {"gov", "edu", "ac", "go", "mil", "gouv", "gob", "nhs", "govt", "gv"}
# 不靠后缀能识别的政府与国际机构域
_INSTITUTIONAL_DOMAINS = {"europa.eu", "gc.ca", "canada.ca"}
# 百科：Profound 把 Wikipedia 归 Institution
WIKI_DOMAINS = {"wikipedia.org", "wikimedia.org", "wikidata.org", "wiktionary.org", "wikivoyage.org",
                "britannica.com", "namu.wiki", "baike.com", "baike.baidu.com"}


def is_government(host: str) -> bool:
    """政府与公共机构（后缀或已知政府域），不含学校、百科。可改变性和诊断要单独区分政府时用。"""
    labels = host.split(".")
    if labels[-1] in {"gov", "mil"}:
        return True
    if any(host == d or host.endswith("." + d) for d in _INSTITUTIONAL_DOMAINS):
        return True
    if len(labels[-1]) != 2:
        return False
    gov = {"gov", "go", "gob", "gouv", "govt", "gv", "mil", "nhs"}
    return (len(labels) >= 3 and labels[-2] in gov) or (len(labels) >= 4 and labels[-3] in gov) or \
        (len(labels) == 2 and labels[0] in gov)


def is_wiki(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in WIKI_DOMAINS)


def _institutional_suffix(host: str) -> bool:
    if any(host == d or host.endswith("." + d) for d in _INSTITUTIONAL_DOMAINS):
        return True
    labels = host.split(".")
    if labels[-1] in _INSTITUTIONAL_TLDS:
        return True
    if len(labels[-1]) != 2:
        return False                      # 机构二级后缀只出现在国家域名下，go.com 不算
    if len(labels) >= 3 and labels[-2] in _INSTITUTIONAL_SLDS:
        return True
    # 省州一级政府域：publicationsduquebec.gouv.qc.ca、xxx.gov.nsw.au
    if len(labels) >= 4 and len(labels[-2]) <= 3 and labels[-3] in _INSTITUTIONAL_SLDS:
        return True
    # 站点本身就落在机构二级后缀上（nhs.uk、gob.mx、gov.uk）
    return len(labels) == 2 and labels[0] in _INSTITUTIONAL_SLDS


def _known_type(host: str, cache: dict | None = None) -> str | None:
    """域名 → 来源类别；内置表、缓存、机构后缀都不中时返回 None（未判读）。

    内置表和缓存合成一张表按最长匹配查；同一个键两边都有时内置表优先。
    历史值兜底：`corporate_site`、`encyclopedia_reference` 等已从 `SOURCE_TYPES`
    退休的分类按迁移口径归并（见 `RETIRED_SOURCE_TYPES`），其余无法识别的值落到
    「其他」——缓存里同样可能残留旧值，否则 `SOURCE_TYPES[known]` 会直接 KeyError。
    """
    builtin_key = _matched_key(host, KNOWN_HOST_TYPES)
    cache_key = _matched_key(host, cache) if cache else ""
    # 缓存是覆盖表：命中一样具体时用缓存，人工纠错写进缓存即可推翻内置表；
    # 缓存命中得更具体时（内置只有父域、缓存单独判了子域）同样用缓存。
    if cache_key and len(cache_key) >= len(builtin_key):
        source_type = cache[cache_key]
    elif builtin_key:
        source_type = KNOWN_HOST_TYPES[builtin_key]
    else:
        source_type = None
    if source_type is not None:
        if source_type in SOURCE_TYPES:
            return source_type
        return RETIRED_SOURCE_TYPES.get(source_type, "other")
    if _institutional_suffix(host):
        return "institutional"
    return None


def _normalize_cache_keys(payload: dict) -> dict:
    """缓存键过一遍 normalize_host（去 www、小写），和查询时的 host 口径一致。

    2026-11-18 前缓存里的 `www.jeffgeerling.com` 永远查不到：查询的 host 已去掉 www。
    归一后同一个键出现两个不同类别，说明有人判了两次且不一致，停下让人定。
    """
    out: dict[str, str] = {}
    clash = []
    for raw_key, value in payload.items():
        key = normalize_host(raw_key)
        # 移动端子域和主域是同一个站：缓存里只判了 m.demo.com 时，主域也该命中
        for prefix in ("m.", "amp.", "mobile.", "wap."):
            if key.startswith(prefix):
                key = key[len(prefix):]
                break
        if not key or "." not in key:
            raise SystemExit(f"域名类别缓存的键不是域名：{raw_key!r}；后缀规则（.gov/.edu/.ac.xx 等）写在代码里，不写缓存")
        if key in COMMON_MULTI_LABEL_SUFFIXES:
            raise SystemExit(f"域名类别缓存里写了公共后缀 {key!r}（如 com.au / com.my），它不是一个站；改写成具体域名")
        if key in out and out[key] != value:
            clash.append(f"{key}={out[key]}/{value}")
        out[key] = value
    if clash:
        raise SystemExit(f"域名类别缓存去 www 后有键判得不一致：{', '.join(clash[:5])}")
    return out


def _is_same_category(obj: dict) -> bool:
    """目标品牌和配置竞品默认同类；开放品牌没写 same_category 也按同类算，只有显式 false 才排除。

    词表里的开放品牌本来就摘自同品类的回答，默认就是同类竞品；别的品类厂商（NVIDIA、CVAT、
    Microsoft、Voices.com 之类）要在词表里显式写 `same_category: false`，官网才不算「竞品网站」。
    难度与可改变性诊断另按显式标注取同类品牌，不走这里的默认值。
    """
    if obj.get("role") in ("target", "competitor"):
        return True
    return obj.get("same_category") is not False


def _classify_official(host: str, objects: list[dict], competitor_sites=()) -> tuple[str | None, str | None]:
    """官网规则：纳入对象的官网按顺序第一个命中的胜出；都不中时，config 的 competitor_site_domains
    （同类平台站点，词表顶层字段，因客户而异，不进共用的域名类别缓存）归「竞品网站」、不挂品牌。

    非同类开放品牌的官网不在这里归「竞品网站」，跳过它交给后面的域名缓存判类（_known_type）；
    缓存里没有就按原逻辑落 other/unjudged。

    2026-11-27 Suda 定：判「竞品网站」不看 role，看 same_category——open / 发现的同类品牌官网也计入
    竞品网站（FuninVR 报告里 42.5% 的竞品网站引用正是这批开放竞品）；只有别品类的品牌才落「其他」。
    """
    for obj in objects:
        for domain in obj.get("official_domains") or []:
            if domain_matches(host, domain):
                if obj.get("role") == "target":
                    return "brand_official", obj.get("object_id")
                if _is_same_category(obj):
                    return "competitor_official", obj.get("object_id")
                # 非同类开放品牌：不是竞品网站，继续找后面是否还有同类对象命中
                break
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
    return _normalize_cache_keys(payload)


def unjudged_coverage(citations) -> dict:
    """citations：可迭代的 {host, basis, title?, url?}。按引用次数（未去重）统计未判读占比。

    未判读分两档：引用次数达到长尾阈值的必须判（`candidates`，门禁按这部分算）；
    不足阈值的记「长尾未判」（`low_volume`），不强制判读，展示归「其他」。
    """
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
    threshold = low_volume_threshold(total)
    ordered = sorted(hosts.values(), key=lambda h: (-h["count"], h["domain"]))
    candidates = [h for h in ordered if h["count"] >= threshold]
    low_volume = [h for h in ordered if h["count"] < threshold]
    required = sum(h["count"] for h in candidates)
    tail = sum(h["count"] for h in low_volume)
    return {
        "total_citations": total,
        "unjudged_citations": required,
        "unjudged_share": round(required / total, 4) if total else 0.0,
        "low_volume_citations": tail,
        "low_volume_share": round(tail / total, 4) if total else 0.0,
        "low_volume_threshold": threshold,
        "low_volume_domains": len(low_volume),
        "limit": UNJUDGED_SHARE_LIMIT,
        "candidates": candidates,
        "low_volume": low_volume,
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
    tail_note = (f"；另有长尾未判 {coverage.get('low_volume_domains', 0)} 个域名、"
                 f"{coverage.get('low_volume_share', 0):.1%} 引用（单个域名不足 "
                 f"{coverage.get('low_volume_threshold', 0)} 次），归「其他」不强制判读")
    if share <= coverage["limit"]:
        if n:
            print(f"{head}引用来源未判读 {share:.1%}（{n} 个域名，上限 {coverage['limit']:.0%}），已列到 {candidates_path}{tail_note}")
        elif tail_note:
            print(head + tail_note.lstrip("；"))
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
