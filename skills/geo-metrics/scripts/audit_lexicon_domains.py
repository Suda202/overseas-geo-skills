#!/usr/bin/env python3
"""词表域名自检：同一域名被两个品牌占用、域名与品牌名对不上。

用法：
  python3 scripts/audit_lexicon_domains.py --lexicon <词表.json> [<词表2.json> ...]

三类问题：
1. 同一域名挂在两个品牌下：
   - 两个品牌同名、互为别名或别名有交集 → 同一家公司的多个条目，建议合并，不算错。
   - 其余 → 必须确认，错挂会把 A 家的引用算成 B 家的官网。
     实例（2026-11-18）：一份词表里，品牌 A 的域名清单里挂着品牌 B 的交易平台域名，
     那批引用就全算到了 A 的官网名下。
2. 域名标签是**别家品牌**的名字：牌子 A 名下挂着 `platform-b.example`，而同一份词表里
   `platform-b` 是牌子 B 的别名 → 归属可能挂错，必须确认。只报这种有证据的，不按
   「域名和品牌名对不上」泛泛提示（母公司、产品名、缩写都会误报）。
3. 域名写法不规范：带协议、路径、大写或 www.，会绕开精确匹配。
4. 疑似同一品牌拆成两条（2026-11-20）：两条品牌的别名有交集、一条的别名整词出现在另一条的名字或别名里
   （Webull ⊂ Webull Hong Kong、Futu ⊂ Futu Securities）、中文别名互相包含（致富 ⊂ 致富證券），
   或官网域名主标签相同（webull.com 与 webull.hk）。同一品牌拆开会把它的提及分给两家、两家都偏低。
   确实是两家公司（中銀香港与中銀國際）就写进词表顶层 ``distinct_brands: [["A", "B"], …]``，不再报。

退出码：0 没有问题；1 有必须确认的问题；2 输入读不了。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo_presales_core.util import normalize_host, registrable_domain  # noqa: E402


def norm_name(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(text or "").lower())


def brands_of(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brands = raw.get("brands") if isinstance(raw, dict) else raw
    if not isinstance(brands, list):
        raise SystemExit(f"{path} 缺少 brands 数组")
    return brands


def same_company(a: dict, b: dict) -> bool:
    """两个品牌条目是不是同一家：同名、名字互相包含，或别名集合有交集。"""
    na, nb = norm_name(a.get("name")), norm_name(b.get("name"))
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    aliases_a = {norm_name(x) for x in a.get("aliases") or [] if norm_name(x)}
    aliases_b = {norm_name(x) for x in b.get("aliases") or [] if norm_name(x)}
    return bool(aliases_a & aliases_b)


_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0e00-\u0e7f]")


def _names(brand: dict) -> set[str]:
    return {str(x).strip() for x in [brand.get("name"), *(brand.get("aliases") or [])] if str(x or "").strip()}


def _labels(brand: dict) -> set[str]:
    out = set()
    for key in ("official_domains", "domains"):
        for dom in brand.get(key) or []:
            label = (registrable_domain(normalize_host(dom)) or "").split(".")[0]
            if len(label) >= 3:
                out.add(label)
    return out


def _word_in(short: str, long: str) -> bool:
    if len(norm_name(short)) < 3 or short.casefold() == long.casefold():
        return False
    return re.search(r"(?<![0-9a-z])" + re.escape(short.casefold()) + r"(?![0-9a-z])", long.casefold()) is not None


def split_suspects(raw: dict) -> list[str]:
    """疑似同一品牌被拆成两条的品牌对（见文件开头第 4 类）。``raw`` 是整份词表 JSON。"""
    brands = raw.get("brands") if isinstance(raw, dict) else raw
    if not isinstance(brands, list):
        return []
    allowed = {frozenset(map(str, pair)) for pair in (raw.get("distinct_brands") or [])
               if isinstance(raw, dict) and isinstance(pair, (list, tuple)) and len(pair) == 2}
    out = []
    for i, a in enumerate(brands):
        for b in brands[i + 1:]:
            na, nb = str(a.get("name")), str(b.get("name"))
            if na == nb or frozenset((na, nb)) in allowed:
                continue
            A, B = _names(a), _names(b)
            why = None
            shared = {x.casefold() for x in A} & {x.casefold() for x in B}
            if shared:
                why = f"别名重复：{sorted(shared)[0]}"
            if not why:
                for s, l, ls in ((A, B, nb), (B, A, na)):
                    hit = next(((x, y) for x in s for y in l
                                if (_CJK.search(x) and len(x) >= 2 and x in y and x != y)
                                or (not _CJK.search(x) and _word_in(x, y))), None)
                    if hit:
                        why = f"「{hit[0]}」包含在「{hit[1]}」里"
                        break
            if not why:
                common = _labels(a) & _labels(b)
                if common:
                    why = f"官网域名主标签相同：{sorted(common)[0]}"
            if why:
                out.append(f"{na} ↔ {nb}（{why}）")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="词表域名自检")
    parser.add_argument("--lexicon", nargs="+", type=Path, required=True)
    args = parser.parse_args()

    hard: list[str] = []
    soft: list[str] = []
    for path in args.lexicon:
        if not path.exists():
            print(f"读不了：{path}")
            return 2
        brands = brands_of(path)
        owners: dict[str, list[dict]] = defaultdict(list)
        for brand in brands:
            for key in ("official_domains", "domains"):
                for dom in brand.get(key) or []:
                    raw = str(dom).strip()
                    if not raw:
                        continue
                    if raw != normalize_host(raw) or "://" in raw or "/" in raw:
                        soft.append(f"{path.name}：{brand.get('name')} 的域名写法不规范 {raw!r}，应为 {normalize_host(raw)!r}")
                    owners[normalize_host(raw)].append(brand)

        for host, holders in owners.items():
            names = [str(b.get("name") or "").strip() for b in holders]
            if len({norm_name(n) for n in names}) <= 1:
                continue
            related = all(same_company(holders[0], b) for b in holders[1:])
            message = f"{path.name}：{host} 挂在 {'、'.join(names)} 下"
            if related:
                soft.append(message + "（疑似同一品牌的多个条目，建议合并）")
            else:
                hard.append(message + "（不是同一家公司；若其中一个是另一个的国际品牌，合并成一条并补别名）")

        # 域名标签撞上别家品牌名：牌子 A 挂着 B 的域名（真实案例里有过这种错挂）
        for brand in brands:
            own = {norm_name(brand.get("name"))} | {norm_name(a) for a in brand.get("aliases") or []}
            own.discard("")
            for key in ("official_domains", "domains"):
                for dom in brand.get(key) or []:
                    label = (registrable_domain(normalize_host(dom)) or "").split(".")[0]
                    if not label:
                        continue
                    for other in brands:
                        if other is brand:
                            continue
                        keys = {norm_name(other.get("name"))} | {norm_name(a) for a in other.get("aliases") or []}
                        keys.discard("")
                        if same_company(brand, other):   # 同一家（含名字互相包含），跳过
                            continue
                        if label in keys and label not in own:
                            hard.append(f"{path.name}：{brand.get('name')} 的域名 {dom} 标签是「{other.get('name')}」的名字，归属可能挂错")

        for item in split_suspects(json.loads(path.read_text(encoding="utf-8"))):
            hard.append(f"{path.parent.name}/{path.name}：疑似同一品牌拆成两条 {item}；是同一家就合并成一条，确是两家写进 distinct_brands")

    print(f"检查 {len(args.lexicon)} 份词表；必须确认 {len(hard)} 条，提示 {len(soft)} 条")
    for item in hard:
        print("  ✗", item)
    for item in soft:
        print("  ·", item)
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
