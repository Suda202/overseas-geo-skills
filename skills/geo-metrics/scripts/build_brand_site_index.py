#!/usr/bin/env python3
"""把各项目的品牌官网汇成可复用的「品牌站索引」：域名 → 品牌、品类、行业、市场、来源项目。

用法：
  python3 scripts/build_brand_site_index.py --roots <评测数据目录> <本 skill 目录> \
    --out assets/domain-brand-sites.json

数据来源（.snapshots 下的不读）：
- `case.json`：品牌 / 品类 / 官方域名 / 竞品 N / 竞品 N 官网域名
- `bank*.json`：config 的 brand_name / official_domain / competitors / product_line / category_aliases / region
- `lexicon.json`：brands[] 的 name / official_domains（或 domains）/ type
- `assets/brand_lexicon.<品类>.json`：品类取顶层 category 或文件名后缀

品类按 `assets/category-taxonomy.json` 归一成英文品类键（与选词 skill 行业知识档案同一套词）。
同一项目里 lexicon.json 没写品类时，沿用该项目 case / bank 里归一出的品类。
归不进去的原文列在告警里，补进品类表的 aliases 后重跑。

索引只回答「这个域名是谁、做什么品类」，不回答「它是不是你的竞品」：
竞品关系由品牌方按项目确认，写在 Case 和词表里。每次全量重建，不在旧文件上累加。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo_presales_core.util import normalize_host  # noqa: E402

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "assets" / "category-taxonomy.json"
CASE_BRAND_KEYS = ("品牌", "品牌名称", "brand")
CASE_CATEGORY_KEYS = ("品类", "产品线", "垂直行业")
SKIP_PARTS = {".snapshots"}


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_categories(texts, taxonomy: dict) -> list[str]:
    """一组原文（品类、产品线、品类叫法）→ 品类键。按别名包含关系匹配，长别名先试。"""
    pairs = sorted(((alias.lower(), key) for key, item in taxonomy["categories"].items()
                    for alias in [key, *item.get("aliases", [])]), key=lambda p: -len(p[0]))
    found: list[str] = []
    for text in texts:
        low = str(text or "").lower()
        if not low:
            continue
        for alias, key in pairs:
            if alias in low and key not in found:
                found.append(key)
                break  # 一段原文只归一个品类，避免「快充充电器」同时撞上别的短词
    return found


def resolve_markets(texts, taxonomy: dict) -> list[str]:
    found: list[str] = []
    for text in texts:
        low = str(text or "").lower()
        for code, names in taxonomy.get("markets", {}).items():
            if (low == code.lower() or any(n in low for n in names)) and code not in found:
                found.append(code)
    return found


def _project(path: Path, root: Path) -> str:
    rel = path.relative_to(root).parts
    return rel[0] if len(rel) > 1 else path.name


def _case(case: dict) -> tuple[list[dict], list[str], list[str]]:
    """返回 (品牌站条目, 品类原文, 市场原文)。"""
    brand = next((str(case[k]).strip() for k in CASE_BRAND_KEYS if case.get(k)), "")
    raw_cats = [str(case[k]) for k in CASE_CATEGORY_KEYS if case.get(k)]
    entries = []
    own = case.get("官方域名") or case.get("official_domain") or case.get("品牌官网")
    for dom in own if isinstance(own, list) else [own]:
        if dom:
            entries.append({"domain": dom, "brand": brand, "role": "target"})
    for i in range(1, 51):
        if case.get(f"竞品 {i} 官网域名"):
            entries.append({"domain": case[f"竞品 {i} 官网域名"], "brand": str(case.get(f"竞品 {i}") or ""), "role": "competitor"})
    for item in case.get("competitors") or []:
        dom = item.get("domain") or item.get("official_domain")
        if dom:
            entries.append({"domain": dom, "brand": str(item.get("name") or ""), "role": "competitor"})
    return entries, raw_cats, raw_cats + [str(case.get("市场") or case.get("market") or "")]


def _bank(bank: dict) -> tuple[list[dict], list[str], list[str]]:
    cfg = bank.get("config") if isinstance(bank, dict) else None
    if not isinstance(cfg, dict) or not cfg.get("brand_name"):
        return [], [], []
    entries = []
    own = cfg.get("official_domain")
    for dom in own if isinstance(own, list) else [own]:
        if dom:
            entries.append({"domain": dom, "brand": cfg["brand_name"], "role": "target"})
    for item in cfg.get("competitors") or []:
        if isinstance(item, dict) and item.get("domain"):
            entries.append({"domain": item["domain"], "brand": str(item.get("name") or ""), "role": "competitor"})
    raw_cats = [str(cfg.get("product_line") or "")] + [str(a) for a in (cfg.get("category_aliases") or [])]
    return entries, raw_cats, [str(cfg.get("region") or cfg.get("market") or "")]


def _lexicon(lexicon: dict) -> list[dict]:
    entries = []
    for item in (lexicon.get("brands") if isinstance(lexicon, dict) else None) or []:
        # 只有显式标了 target / competitor 的才记角色；开放品牌（type 为空或 open、competitor_open）
        # 是开放挖掘进词表的，可能是内容方而不是竞品（Housebell 的 Stacked Homes 是媒体）
        t = str(item.get("type") or "").lower()
        role = "target" if t == "target" else "competitor" if t == "competitor" else "open"
        for dom in (item.get("official_domains") or item.get("domains") or []):
            entries.append({"domain": dom, "brand": str(item.get("name") or ""), "role": role})
    return entries


def _read(path: Path, warnings: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warnings.append(f"读不了：{path}")
        return None


def build(roots: list[Path], taxonomy: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    # 第一遍：每个项目的品类与市场（case / bank 里有，lexicon 里通常没有）
    project_cats: dict[str, list[str]] = {}
    project_markets: dict[str, list[str]] = {}
    unmapped: dict[str, set] = {}
    staged: list[tuple[str, str, list[dict], list[str] | None, list[str]]] = []

    for root in roots:
        if not root.exists():
            warnings.append(f"目录不存在：{root}")
            continue
        for path in sorted(root.rglob("*.json")):
            if SKIP_PARTS & set(path.parts) or path.name.startswith(".snap"):
                continue
            name = path.name
            if name == "case.json":
                kind = "case"
            elif name.startswith("bank") and name.endswith(".json"):
                kind = "bank"
            elif name == "lexicon.json":
                kind = "lexicon"
            elif name.startswith("brand_lexicon.") and path.parent.name == "assets":
                kind = "brand_lexicon"
            else:
                continue
            data = _read(path, warnings)
            if data is None:
                continue
            project = _project(path, root) if kind != "brand_lexicon" else name
            if kind == "case":
                entries, raw_cats, raw_mkts = _case(data)
            elif kind == "bank":
                entries, raw_cats, raw_mkts = _bank(data)
            elif kind == "lexicon":
                entries, raw_cats, raw_mkts = _lexicon(data), [], []
            else:
                suffix = name[len("brand_lexicon."):-len(".json")]
                entries = _lexicon(data)
                raw_cats = [str(data.get("category") or ""), suffix]
                raw_mkts = [str(r) for r in (data.get("regions") or [])]
            cats = resolve_categories(raw_cats, taxonomy) if raw_cats else []
            if raw_cats and not cats:
                unmapped.setdefault(project, set()).update(t for t in raw_cats[:2] if t)
            for key in cats:
                project_cats.setdefault(project, [])
                if key not in project_cats[project]:
                    project_cats[project].append(key)
            for code in resolve_markets(raw_mkts, taxonomy):
                project_markets.setdefault(project, [])
                if code not in project_markets[project]:
                    project_markets[project].append(code)
            if entries:
                staged.append((project, kind, entries, cats or None, raw_cats))

    # 第二遍：落到域名
    index: dict[str, dict] = {}
    today = date.today().isoformat()
    for project, kind, entries, cats, raw_cats in staged:
        cats = cats or project_cats.get(project, [])
        markets = project_markets.get(project, [])
        for entry in entries:
            host = normalize_host(entry["domain"])
            if not host or "." not in host:
                continue
            item = index.setdefault(host, {"brands": [], "categories": [], "industries": [], "markets": [],
                                           "roles": [], "sources": [], "verified_at": today})
            for field, values in (("brands", [entry["brand"]]), ("categories", cats), ("markets", markets),
                                  ("roles", [entry["role"]]), ("sources", [project])):
                for value in values:
                    if value and value not in item[field]:
                        item[field].append(value)
            for key in cats:
                industry = taxonomy["categories"][key]["industry"]
                if industry not in item["industries"]:
                    item["industries"].append(industry)

    for host, item in index.items():
        if len({b.lower() for b in item["brands"] if b}) > 1:
            warnings.append(f"{host} 挂了多个品牌：{'/'.join(item['brands'])}")
        if not item["categories"]:
            warnings.append(f"{host} 没有品类（来源 {'、'.join(item['sources'])}）")
    for project, texts in sorted(unmapped.items()):
        if not project_cats.get(project):
            warnings.append(f"品类表里没有：{project} 的「{' / '.join(sorted(texts))}」，补进 category-taxonomy.json 的 aliases")
    return dict(sorted(index.items())), warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="重建品牌站索引")
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH)
    args = parser.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)
    index, warnings = build(args.roots, taxonomy)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    with_cat = sum(1 for v in index.values() if v["categories"])
    print(f"品牌站 {len(index)} 个，带品类 {with_cat} 个；输出 {args.out}")
    for item in warnings[:25]:
        print("  告警：", item)
    if len(warnings) > 25:
        print(f"  还有 {len(warnings) - 25} 条告警未显示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
