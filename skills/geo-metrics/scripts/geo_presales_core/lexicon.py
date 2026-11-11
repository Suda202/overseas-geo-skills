"""品牌词表读取：报告、监测基线、试跑计数、情感抽取、词表挖掘都读这一份。

结构见 geo-metrics/SKILL.md「品牌词表」。顶层名单字段（case_sensitive_aliases、competitor_site_domains）
由 util.read_lexicon_list 读。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .util import normalize_host, normalize_text


def load_lexicon(path) -> tuple[list[dict], set[str], str]:
    """读取品牌词表，返回 ([{name, domains, aliases, type}], 排除名单, status)。

    词表结构容忍多种写法（``{"brands": [...]}`` / 裸列表 / name->info 映射）。
    ``uncertain`` 中的名字按词表约定排除在声量分母之外。
    """
    empty: tuple[list[dict], set[str], str] = ([], set(), "absent")
    if not path:
        return empty
    path = Path(path)
    if not path.exists():
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], set(), f"unreadable:{exc.__class__.__name__}"

    uncertain = set()
    if isinstance(raw, dict):
        for item in raw.get("uncertain") or []:
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                uncertain.add(normalize_text(str(name)))

    def as_list(value):
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    if isinstance(raw, dict) and isinstance(raw.get("brands"), (list, dict)):
        # 正式结构 {"brands": [...]}；也容忍 {"brands": {标准名: 别名 list}} 的嵌套 dict。
        # 顶层其余键（target / note / tiers 等元数据）一律不当作品牌——旧行为会把它们
        # 静默变成品牌，声量分母随之被污染（2026-09-22 实测：22 个品牌的词表只出了 8 个对象，
        # 还混进 target/note/tiers 三个假品牌）。
        brands_field = raw["brands"]
        if isinstance(brands_field, dict):
            source = [{"name": key, "aliases": [key, *[str(a).strip() for a in as_list(value)]]}
                      for key, value in brands_field.items()]
        else:
            source = brands_field
        ignored = sorted(key for key in raw
                         if key not in {"brands", "uncertain", "stopwords", "case_sensitive_aliases",
                                        "competitor_site_domains"} and not key.startswith("_"))
        if ignored:
            print(f"词表 {path}: 顶层 {ignored} 未识别为品牌，已忽略（只读 brands 分支）", file=sys.stderr)
    elif isinstance(raw, list):
        source = raw
    elif isinstance(raw, dict):
        # 兼容「标准名 → 别名 list」的 dict 型词表（report-audit / shared），别名必须保留；
        # 以 `_` 开头的键（_comment/_canonical 等）是元数据，不是品牌。
        source = []
        for key, value in raw.items():
            if key in {"uncertain", "stopwords"} or key.startswith("_"):
                continue
            if isinstance(value, dict):
                source.append(dict(value, name=key))
            elif isinstance(value, list):
                source.append({"name": key, "aliases": [key, *value]})
            else:
                source.append({"name": key})
    else:
        return [], set(), "unsupported-shape"

    entries = []
    for item in source:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("brand") or item.get("canonical_name") or "").strip()
        if not name or normalize_text(name) in uncertain:
            continue
        domains = [normalize_host(str(d)) for d in as_list(
            item.get("official_domains") or item.get("domains") or item.get("domain"))]
        aliases = [str(a).strip() for a in as_list(item.get("aliases")) if str(a).strip()]
        entry = {
            "name": name,
            "domains": [d for d in domains if d],
            "aliases": aliases or [name],
            "type": str(item.get("type") or "competitor_open").strip(),
            # 词表里实际写的类型；没写为 None（情感单元的 brand_type 照实记，不套默认值）
            "declared_type": str(item.get("type")).strip() if item.get("type") else None,
        }
        # 品牌名本身是普通英文词时（Nothing / One / Play），调用方可以要求不要把规范名当别名，
        # 只认词表里带型号的写法。透传这个开关，否则 build_config 拿不到。
        if item.get("exclude_canonical_alias"):
            entry["exclude_canonical_alias"] = True
        entries.append(entry)
    return entries, uncertain, "loaded"
