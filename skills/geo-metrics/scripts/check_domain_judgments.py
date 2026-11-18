#!/usr/bin/env python3
"""域名判读自检：前 N 个被引域名必须判过，「其他」必须写理由，其他占比不能过高。

用法：
  python3 scripts/check_domain_judgments.py --collect <采集目录> \
    --cache assets/domain-categories.json --lexicon assets/brand_lexicon.<品类>.json \
    [--case <Case.json>] [--top 20] [--other-limit 0.15] [--reasons build/domain-judgments.json]

判读顺序（SKILL.md 第 3 步）：先过品牌词表和 Case（是不是某个品牌官网）→ 再开站核实
（产品站 / 评测媒体 / 机构站）→ 最后才落「其他」。判「其他」的域名要在这里写明理由。

退出码：0 通过；1 有必须处理的问题；2 输入读不了。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

BUCKETS = {"media_review", "ugc", "institutional", "press_release", "other"}
CORPORATE_PREFIX = re.compile(r"^(support|docs|doc|help|helpcenter|developer|press|newsroom|shop|store)\.")


CORE_SCRIPTS = Path(__file__).resolve().parent
if str(CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CORE_SCRIPTS))
from geo_presales_core.util import normalize_host  # noqa: E402

PLATFORMS = ("chatgpt", "perplexity", "copilot", "gemini", "aimode", "overview", "grok", "alexa")


def norm_host(url: str) -> str:
    return normalize_host(url)


def count_citations(collect_dir: Path) -> Counter:
    """和报告同口径数引用：只读有效回答，引用字段与正文引用标记按 core 的 _citation_entries 抽。

    2026-11-18 前这里递归扫 JSON 里所有带 url 的节点，把 search_result、web_source 这些
    「检索到但没引用」的结果也算进去（老虎 14374 次 vs 报告 9418 次），前 20 和「其他」占比都对不上。
    """
    from geo_presales_core.citations import _citation_entries
    from geo_presales_core.crawler import answer_body, answer_validity

    counts: Counter = Counter()
    for platform in PLATFORMS:
        pdir = collect_dir / f"scraper.{platform}"
        if not pdir.is_dir():
            continue
        for path in sorted(pdir.glob("*/*.json")):
            try:
                tr = (json.loads(path.read_text(encoding="utf-8")) or {}).get("task_result") or {}
            except (OSError, json.JSONDecodeError):
                continue
            text = answer_body(tr, platform)
            if not answer_validity(text)[0]:
                continue
            for entry in _citation_entries(platform, tr, text):
                host = normalize_host(entry.get("domain_hint") or entry.get("raw_url") or "")
                if host:
                    counts[host] += 1
    return counts


def brand_domains(lexicon_path: Path | None, case_path: Path | None) -> dict[str, str]:
    owned: dict[str, str] = {}
    if lexicon_path and lexicon_path.exists():
        data = json.loads(lexicon_path.read_text(encoding="utf-8"))
        brands = data.get("brands") if isinstance(data, dict) else None
        if isinstance(brands, list):
            for item in brands:
                name = item.get("name")
                for dom in (item.get("official_domains") or item.get("domains") or []):
                    owned[str(dom).lower()] = f"品牌 {name}"
        elif isinstance(data, dict):
            for name, aliases in data.items():
                if str(name).startswith("_"):
                    continue
                if isinstance(aliases, dict):
                    for dom in (aliases.get("official_domains") or aliases.get("domains") or []):
                        owned[str(dom).lower()] = f"品牌 {name}"
    if case_path and case_path.exists():
        case = json.loads(case_path.read_text(encoding="utf-8"))
        for index in range(1, 51):
            name = case.get(f"竞品 {index}")
            dom = case.get(f"竞品 {index} 官网域名")
            if isinstance(name, str) and isinstance(dom, str) and dom.strip():
                owned[norm_host(dom)] = f"配置竞品 {name}"
        brand = case.get("品牌") or case.get("品牌名称")
        dom = case.get("官方域名")
        if isinstance(brand, str) and isinstance(dom, str) and dom.strip():
            owned[norm_host(dom)] = f"目标品牌 {brand}"
    return owned


def main() -> int:
    parser = argparse.ArgumentParser(description="引用域名判读自检")
    parser.add_argument("--collect", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--lexicon")
    parser.add_argument("--case")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--other-limit", type=float, default=0.15)
    parser.add_argument("--reasons")
    parser.add_argument("--meta", help="判读记录 domain-categories-meta.json，默认与 --cache 同目录")
    args = parser.parse_args()

    collect_dir = Path(args.collect)
    cache_path = Path(args.cache)
    if not collect_dir.exists():
        print(f"采集目录不存在：{collect_dir}")
        return 2
    counts = count_citations(collect_dir)
    if not counts:
        print("采集目录里没有可识别的引用 URL")
        return 2
    from geo_presales_core.sources import (  # noqa: E402
        KNOWN_HOST_TYPES, _matched_key, classify_source, load_cache as core_load_cache, low_volume_threshold)
    from geo_presales_core.util import COMMON_MULTI_LABEL_SUFFIXES  # noqa: E402
    cache = core_load_cache(cache_path) if cache_path.exists() else {}
    config = {"domain_category_cache": cache}
    owned = brand_domains(Path(args.lexicon) if args.lexicon else None,
                          Path(args.case) if args.case else None)

    reasons_path = Path(args.reasons) if args.reasons else Path("build/domain-judgments.json")
    reasons = {}
    if reasons_path.exists():
        try:
            reasons = json.loads(reasons_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            reasons = {}

    total = sum(counts.values())
    ranked = counts.most_common()
    top = ranked[: args.top]
    problems: list[str] = []

    def lookup(host: str, table: dict) -> str | None:
        key = _matched_key(host, table)
        return table[key] if key else None

    def category(host: str) -> str | None:
        """和报告同一个判定：先看 Case/词表官网，再走 core 的 classify_source。"""
        if lookup(host, owned):
            return "brand"
        verdict = classify_source(host, config)
        if verdict["basis"] == "unjudged":
            return None
        return verdict["source_type"] if verdict["source_type"] in BUCKETS else "brand"

    unjudged_top, other_top = [], []
    for host, n in top:
        cat = category(host)
        if cat is None:
            unjudged_top.append((host, n))
        elif cat == "other":
            other_top.append((host, n))

    threshold = low_volume_threshold(total)
    tail_note = []
    for host, n in unjudged_top:
        if n >= threshold:
            problems.append(f"前 {args.top} 里未判读：{host}（{n} 次引用）")
        else:
            tail_note.append(f"{host}({n})")
    missing_reason = [(h, n) for h, n in other_top if not str(reasons.get(h) or "").strip()]
    for host, n in missing_reason:
        problems.append(f"判为「其他」但没有理由：{host}（{n} 次引用），写进 {reasons_path}")

    other_cites = sum(n for host, n in ranked if category(host) == "other")
    other_share = other_cites / total if total else 0.0
    if other_share > args.other_limit:
        problems.append(
            f"「其他」占引用 {other_share:.1%}，超过上限 {args.other_limit:.0%}；逐条复核是否漏了品牌官网或评测站"
        )

    # 待复核占比：判过但证据不足（confidence=pending）的域名，读数要用时先看这一项
    meta_path = args.meta if args.meta else cache_path.parent / "domain-categories-meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    pending_cites = 0
    pending_top: list[tuple[str, int]] = []
    if meta:
        for host, n in ranked:
            key = _matched_key(host, meta)
            if key and (meta.get(key) or {}).get("confidence") == "pending":
                pending_cites += n
                pending_top.append((host, n))
    pending_share = pending_cites / total if total else 0.0

    reasons_path.parent.mkdir(parents=True, exist_ok=True)
    template = {h: reasons.get(h, "") for h, _ in other_top}
    reasons_path.write_text(json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8")

    if tail_note:
        print(f"长尾未判（单个域名不足 {threshold} 次引用，归「其他」不强制判读）："
              + "、".join(tail_note[:8]) + ("…" if len(tail_note) > 8 else ""))
    print(f"引用 {total} 次，域名 {len(counts)} 个；前 {args.top} 未判读 {len(unjudged_top)} 个，"
          f"判「其他」{len(other_top)} 个，其他占比 {other_share:.1%}")
    # 缓存卫生：只判了子域、父域没判，同域其他页面会整片落未判读
    def parent_of(key: str) -> str:
        parts = key.split(".")
        return ".".join(parts[1:]) if len(parts) >= 3 else ""

    def is_suffix(value: str) -> bool:
        parts = value.split(".")
        return value in COMMON_MULTI_LABEL_SUFFIXES or (
            len(parts) == 2 and parts[0] in {"com", "net", "org", "gov", "edu", "ac", "co", "or", "ne", "go", "mil"})

    orphan_counts: dict[str, int] = {}
    for host, n in ranked:
        key = _matched_key(host, {**KNOWN_HOST_TYPES, **cache})
        parent = parent_of(key) if key else ""
        if (parent and parent not in cache and parent not in KNOWN_HOST_TYPES and parent.count(".") >= 1
                and not is_suffix(parent)):
            orphan_counts[parent] = orphan_counts.get(parent, 0) + n
    if orphan_counts:
        top_orphans = "、".join(f"{k}({v})" for k, v in sorted(orphan_counts.items(), key=lambda x: -x[1])[:5])
        print(f"父域未判（子域判过、父域没判）{len(orphan_counts)} 个，涉及 {sum(orphan_counts.values())} 条引用；"
              f"最多的：{top_orphans}。判父域，子域自动跟；只有 community./forum./club. 这类性质不同的子域才单独判。")

    if meta:
        legacy = [(h, n) for h, n in ranked
                  if (meta.get(_matched_key(h, meta) or "") or {}).get("confidence") == "legacy"]
        legacy_cites = sum(n for _, n in legacy)
        if legacy:
            top_legacy = "、".join(f"{h}({n})" for h, n in legacy[:5])
            print(f"历史判读无依据（confidence=legacy）{len(legacy)} 个域名，占引用 {legacy_cites / total:.1%}；"
                  f"引用最多的：{top_legacy}。高频的顺手补依据，写进 domain-categories-meta.json")
        top_pending = "、".join(f"{h}({n})" for h, n in sorted(pending_top, key=lambda x: -x[1])[:5])
        print(f"待复核（confidence=pending）{len(pending_top)} 个域名，占引用 {pending_share:.1%}"
              + (f"；最多的：{top_pending}" if top_pending else ""))
    # 只提示不拦截：企业的帮助中心、文档站、新闻室、商店判成机构或媒体，多半是判错（判据见 geo-metrics 合同「判读判据」）
    corporate = [(h, category(h)) for h, _ in ranked
                 if CORPORATE_PREFIX.match(h) and category(h) in ("institutional", "media_review")]
    if corporate:
        print("请复核（企业子站判成了机构或媒体）：" + "、".join(f"{h}={c}" for h, c in corporate[:10]))
    if problems:
        print("\n必须处理：")
        for item in problems:
            print("  -", item)
        print(f"\n理由文件：{reasons_path}")
        return 1
    print("域名判读通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
