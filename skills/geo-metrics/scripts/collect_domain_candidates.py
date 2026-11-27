"""收集引用来源里尚未登记的域名，供人工/模型判读类别。

引用来源分类不是封闭集合：`geo_presales_core` 的 `KNOWN_HOST_TYPES` 只放稳定的高频域名，
其余走 `assets/domain-categories.json` 缓存。本脚本负责找出缓存里还没有的域名，
连同页面标题一起输出，判读后写回缓存，下次运行即命中。

用法：
    python3 collect_domain_candidates.py --collect <采集目录> --case <Case.json> \
        --cache assets/domain-categories.json --out build/domain-candidates.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

REPO_SCRIPTS = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_SCRIPTS))
from geo_presales_core.platforms import CITATION_FIELDS  # noqa: E402

CITATION_FIELD = dict(CITATION_FIELDS)  # 平台登记表
PLATFORM_HOST_SUFFIXES = ("google.com", "gstatic.com", "googleusercontent.com")

# Case 字段（飞书表头）→ 归一化用
CASE_BRAND_KEYS = ("品牌名称", "brand", "品牌")
CASE_DOMAIN_KEYS = ("官方域名", "official_domain", "品牌官网")
CASE_COMPETITOR_KEYS = ("竞品 1", "竞品 2", "竞品 3", "competitors")
CASE_COMPETITOR_DOMAIN_KEYS = ("竞品 1 官网域名", "竞品 2 官网域名", "竞品 3 官网域名")


def normalize_host(value: str) -> str:
    host = str(value or "").strip().casefold()
    host = host.split("//")[-1].split("/")[0].split("?")[0]
    for prefix in ("www.", "m.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def load_case(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brand = next((raw[k] for k in CASE_BRAND_KEYS if raw.get(k)), "")

    domains = [normalize_host(raw[k]) for k in CASE_DOMAIN_KEYS if raw.get(k)]
    if isinstance(raw.get("official_domain"), list):
        domains = [normalize_host(d) for d in raw["official_domain"]]

    competitors = []
    for key in CASE_COMPETITOR_KEYS[:3]:
        name = str(raw.get(key) or "").strip()
        domain = normalize_host(raw.get(f"{key} 官网域名") or raw.get(f"{key.replace('竞品 ', 'competitor_')}_domain") or "")
        if name:
            competitors.append({"name": name, "domain": domain})
    for item in raw.get("competitors") or []:
        name = str(item.get("name") or "").strip()
        if name and not any(c["name"] == name for c in competitors):
            competitors.append({"name": name, "domain": normalize_host(item.get("domain") or "")})

    return {
        "brand": str(brand).strip(),
        "domains": [d for d in domains if d],
        "competitors": competitors,
    }


def load_cache(path: Path) -> dict:
    """与报告同一个读法（去 www、移动端前缀归一、校验类别），不另写一套。"""
    sys.path.insert(0, str(REPO_SCRIPTS))
    from geo_presales_core.sources import load_cache as core_load  # noqa: E402
    return core_load(path) if path.exists() else {}


def matches(host: str, domain: str) -> bool:
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def load_brand_index(path: Path | None) -> dict:
    """品牌站索引：域名 → 品牌、品类。只用来给候选加备注，不参与类别判定。"""
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def brand_hint(host: str, index: dict) -> dict | None:
    """按最长后缀找品牌站，返回 {brands, categories}；找不到返回 None。"""
    best = ""
    for known in index:
        if matches(host, known) and len(known) > len(best):
            best = known
    if not best:
        return None
    entry = index[best]
    return {"brands": entry.get("brands") or [], "categories": entry.get("categories") or [],
            "industries": entry.get("industries") or []}


def registrable_label(host: str) -> str:
    """取可注册域名的第一段：example-brand.com.sg → example-brand。"""
    parts = host.split(".")
    two = ".".join(parts[-2:])
    if two in {"com.sg", "com.hk", "com.my", "com.cn", "com.au", "co.uk", "co.nz", "co.ke", "com.tw"} and len(parts) >= 3:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else host


def same_label_hint(host: str, case: dict) -> str | None:
    """候选域名和本项目某个官网同标签、不同顶级域时给出提示（example-brand.com.sg ↔ example-brand.com）。
    只提示，不自动判成竞品：不同顶级域下可能是不同公司，要人确认。"""
    label = registrable_label(host)
    candidates = [(case.get("brand") or "", d) for d in case.get("domains") or []]
    candidates += [(c.get("name") or "", c.get("domain") or "") for c in case.get("competitors") or []]
    for name, domain in candidates:
        domain = normalize_host(domain)
        if name and domain and registrable_label(domain) == label:
            return name
    return None


def load_lexicon_domains(path: Path | None) -> list[str]:
    """词表里所有品牌的官网域名（official_domains 或 domains）与 competitor_site_domains。"""
    if not path or not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for item in (raw.get("brands") if isinstance(raw, dict) else raw) or []:
        for dom in (item.get("official_domains") or item.get("domains") or []):
            out.append(normalize_host(dom))
    if isinstance(raw, dict):
        out += [normalize_host(d) for d in raw.get("competitor_site_domains") or []]
    return [d for d in out if d]


def scan(collect_dir: Path, case: dict, cache: dict, brand_index: dict | None = None,
         lexicon_domains: list[str] | None = None) -> list[dict]:
    """只收「报告里会落成未判读」的域名：判定直接调 core 的 classify_source，和报告同一个口径
    （内置表、缓存最长匹配、机构后缀、多租户默认都算判过）。词表与 Case 的官网也排除。"""
    sys.path.insert(0, str(REPO_SCRIPTS))
    from geo_presales_core.sources import classify_source  # noqa: E402

    owned = (list(case["domains"]) + [c["domain"] for c in case["competitors"] if c["domain"]]
             + list(lexicon_domains or []))
    config = {"domain_category_cache": cache}

    found: dict[str, dict] = defaultdict(lambda: {"count": 0, "titles": []})
    for platform, field in CITATION_FIELD.items():
        platform_dir = collect_dir / f"scraper.{platform}"
        if not platform_dir.is_dir():
            continue
        for region_dir in sorted(p for p in platform_dir.iterdir() if p.is_dir()):
            for path in sorted(region_dir.glob("*.json")):
                result = (json.loads(path.read_text(encoding="utf-8")).get("task_result") or {})
                entries = result.get(field) or []
                if isinstance(entries, dict):  # Grok footnotes：以 card id 为键的对象
                    entries = list(entries.values())
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    raw_url = str(entry.get("url") or "").strip()
                    if not raw_url:
                        continue
                    host = normalize_host(urlsplit(raw_url).netloc)
                    if not host or any(host == s or host.endswith("." + s) for s in PLATFORM_HOST_SUFFIXES):
                        continue
                    if any(matches(host, d) for d in owned):
                        continue
                    if classify_source(host, config)["basis"] != "unjudged":
                        continue
                    found[host]["count"] += 1
                    title = str(entry.get("title") or entry.get("name") or entry.get("attribution") or "").strip()
                    if title and title not in found[host]["titles"] and len(found[host]["titles"]) < 2:
                        found[host]["titles"].append(title[:90])

    results = []
    for host, item in sorted(found.items(), key=lambda pair: (-pair[1]["count"], pair[0])):
        entry = {"domain": host, "count": item["count"], "titles": item["titles"]}
        hint = brand_hint(host, brand_index or {})
        if hint:
            # 已知品牌站：提醒判读时看它是不是同类品牌，判「其他」并补进本项目的 competitor_site_domains
            entry["known_brand"] = hint["brands"]
            entry["known_categories"] = hint["categories"]
            entry["known_industries"] = hint["industries"]
        same = same_label_hint(host, case)
        if same:
            entry["same_label_as"] = same
        results.append(entry)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="收集未登记的引用域名")
    parser.add_argument("--collect", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, help="品牌词表；词表里的品牌官网不进候选")
    parser.add_argument("--brand-index", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets" / "domain-brand-sites.json",
                        help="品牌站索引，默认 assets/domain-brand-sites.json；没有就不加备注")
    args = parser.parse_args()

    case = load_case(args.case)
    cache = load_cache(args.cache)
    candidates = scan(args.collect, case, cache, load_brand_index(args.brand_index),
                      load_lexicon_domains(args.lexicon))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidates, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    covered = sum(item["count"] for item in candidates)
    print(f"缓存已登记 {len(cache)} 个域名；本次新增候选 {len(candidates)} 个，涉及 {covered} 条引用")
    print(f"写出 {args.out}")
    if candidates:
        print("判读后写回 " + str(args.cache) + "，格式为扁平映射 {域名: 类别}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
