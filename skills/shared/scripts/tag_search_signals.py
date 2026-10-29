"""给搜索词信号表（signals.csv）打「类型提示」，供人工筛买家原话时先看。

来源：借鉴 yao-geo-douyin 的行业画像（按顺序匹配、先排除后意图、每条带理由、实采误判写成回归用例），
标签换成我们的提示词类型（30-选Topic与生词/研究与方法/姚金刚GEO-Skills最新版对照-20261029.md）。
只加两列「类型提示」「提示理由」，不删行、不改原列；是否进买家原话表仍由人判。

标签（按下列顺序匹配，先命中的生效）：
  排除      求职招聘、账号客服、下载模板、词义查询，以及画像里的类目专属排除（服务方后台、同名异义）
  候选名单  best / top / which / vs / alternatives / recommend，或「找、选 + 服务方名词」→ 发现、对比、替代的线索
  品牌      含画像 brands 或 --brands 里的品牌名 → 只作评价/验证题证据（signal-sources.md：品牌词查询不剔除）
  交易      价格、费用、多少钱 → 实验层线索
  问题解决  how / why / can / steps / eligibility 这类 → 问题解决型线索（纯知识问题不算，人判）
  候选名单  只有服务方名词（website / app / agency …）
  交易      for sale / for rent / buy / near me / 价位 → 实验层线索；改写成题面时问去哪找、选哪家
  未判      都没命中；非拉丁字母的词也记未判（规则只覆盖英语，其他语言在画像里加规则）

画像（--profile，JSON）：类目专属规则默认排在通用规则之前，stage=after_brand 的排在品牌规则之后
（类目里改判交易词用，避免盖过品牌）；字段 id、category、version、brands、
rules[{tag, pattern, reason, unless?, stage?}]、regression_cases[{text, expect | not, why}]。
画像放 shared/keyword-profiles/，按类目建，不按客户建。
每次运行先跑通用与画像回归用例，任一不过就退出码 2、不写产物——改规则后旧误判不能复发。

可能出错的地方（规则与回归用例针对的就是这些）：
  1. 排除误杀真实需求：「How much salary to buy condo」是买房负担能力，不是求职 → salary 带 unless
  2. 品牌词与候选名单冲突：「rivalh1 alternative」应是候选名单 → 候选名单强规则排在品牌前
  3. 同名异义：property 指酒店物业（marriott property）→ 只能在类目画像里排除
  4. 非英语词被英语规则误判 → 无拉丁字母直接记未判
  5. 覆盖输入文件 → 默认另写 <输入名>.tagged.csv
  6. 画像正则失控 → 规则数 ≤ 80、单条 ≤ 200 字符，编译失败即退出
  7. App 类目（如 Ybrand）里 download / apk 是真实需求 → 通用规则会标排除，这类类目要在画像里先把它改判

    python3 -I tag_search_signals.py <signals.csv> [--profile <画像.json>] [--brands A B] [--out <tagged.csv>]
    python3 -I tag_search_signals.py <signals.csv> --profile <画像.json> --kept-from <题库.json> --report <核对.json>

--kept-from 读题库 config.buyer_quotes 的「原话」作人工最终留用集，输出各标签的留用/未留用数，
并列出被标「排除」的留用词；有一条就退出码 1（排除误杀必须为 0）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

TAG_COL, REASON_COL = "类型提示", "提示理由"
MAX_RULES, MAX_PATTERN = 80, 200

# (tag, pattern, reason, unless)；顺序即优先级，画像规则插在最前面
BASE_RULES = [
    ("排除", r"\b(jobs?|careers?|hiring|vacanc(y|ies)|internships?|recruit\w*|resume)\b", "求职招聘", None),
    ("排除", r"\b(salary|salaries)\b", "求职薪资",
     r"\b(salary|salaries|income)\s+(to|for|needed|required)\b|\bhow much (salary|income)\b"),
    ("排除", r"\b(log ?in|sign ?in|sign ?up|customer (service|care|support)|contact (number|no)|hotline|helpline|phone number)\b",
     "账号或客服入口", None),
    ("排除", r"\b(apk|download|templates?|wallpapers?|pdf)\b", "下载或模板", None),
    ("排除", r"\b(meaning|definition|synonyms?)\b", "词义查询", None),
    ("候选名单", r"\b(best|top(\s+\d+)?|which|recommend\w*|vs\.?|versus|compare|comparison|alternatives?|competitors?)\b",
     "选择或比较用语", None),
    ("候选名单", r"\b(find|choose|pick|hire|search|looking for)\b.*\b(agents?|agenc(y|ies)|compan(y|ies)|providers?|websites?|sites?|apps?|platforms?|portals?|services?|brands?)\b",
     "找、选服务方", None),
    ("品牌", None, "含品牌名：只作评价、验证题证据", None),
    ("交易", r"\b(price|prices|pricing|cost|costs|fees?|how much|afford\w*|cheap|cheapest|discount|deals?|coupon|promo)\b",
     "价格费用", None),
    ("问题解决", r"^(how|why|what|when|where|can|should|is|are|do|does|will)\b|\b(how to|steps?|process|procedure|eligib\w*|criteria|rules?|requirements?|guide|calculator|checklist|tips)\b",
     "怎么办、能不能", None),
    ("候选名单", r"\b(websites?|sites?|apps?|platforms?|portals?|agenc(y|ies)|agents?|compan(y|ies)|providers?|developers?|software|tools?)\b",
     "服务方名词", None),
    ("交易", r"\b(for sale|for rent|to rent|rent|rental|buy|buying|near me|under|below)\b|\$\s?\d|\b\d+\s?k\b",
     "购买或租赁：改写成题面时问去哪找、选哪家", None),
]

BASE_CASES = [
    {"text": "How much salary to buy condo in Singapore", "not": "排除", "why": "买房负担能力，不是求职"},
    {"text": "property valuer singapore salary", "expect": "排除", "why": "估价师薪资是求职"},
    {"text": "best property website singapore reddit", "expect": "候选名单", "why": "best 优先"},
    {"text": "How to check property ownership in Singapore online?", "expect": "问题解决", "why": "怎么办"},
    {"text": "ห้องเช่า ราคาถูก", "expect": "未判", "why": "规则只覆盖英语"},
    {"text": "ai translation earbuds", "not": "排除", "why": "Obrand：翻译是耳机功能，不是词义查询"},
    {"text": "gan charger meaning", "expect": "排除", "why": "Obrand：词义查询"},
]


def load_profile(path: Path | None) -> dict:
    if not path:
        return {"id": "base", "version": "", "brands": [], "rules": [], "regression_cases": []}
    p = json.loads(path.read_text(encoding="utf-8"))
    rules = p.get("rules", [])
    if len(rules) > MAX_RULES:
        sys.exit(f"画像规则 {len(rules)} 条，超过 {MAX_RULES}")
    for r in rules:
        for key in ("pattern", "unless"):
            if r.get(key) and len(r[key]) > MAX_PATTERN:
                sys.exit(f"画像规则过长（>{MAX_PATTERN} 字符）：{r[key][:60]}…")
        if r.get("tag") not in {"排除", "候选名单", "品牌", "交易", "问题解决"}:
            sys.exit(f"画像规则标签不认识：{r.get('tag')}")
        if r.get("stage", "first") not in {"first", "after_brand"}:
            sys.exit(f"画像规则 stage 只能是 first / after_brand：{r.get('stage')}")
    return p


def compile_rules(profile: dict, extra_brands: list[str]):
    brands = [b for b in profile.get("brands", []) + extra_brands if b.strip()]
    brand_re = re.compile(r"\b(" + "|".join(re.escape(b) for b in brands) + r")\b", re.I) if brands else None
    first = [(r["tag"], r["pattern"], r["reason"], r.get("unless"))
             for r in profile.get("rules", []) if r.get("stage", "first") == "first"]
    after_brand = [(r["tag"], r["pattern"], r["reason"], r.get("unless"))
                   for r in profile.get("rules", []) if r.get("stage") == "after_brand"]
    i = next(n for n, r in enumerate(BASE_RULES) if r[0] == "品牌") + 1
    raw = first + BASE_RULES[:i] + after_brand + BASE_RULES[i:]
    out = []
    for tag, pat, reason, unless in raw:
        try:
            if pat is None:  # 品牌占位
                if brand_re:
                    out.append((tag, brand_re, reason, None))
                continue
            out.append((tag, re.compile(pat, re.I), reason, re.compile(unless, re.I) if unless else None))
        except re.error as e:
            sys.exit(f"规则编译失败：{pat}（{e}）")
    return out


def classify(text: str, rules) -> tuple[str, str]:
    t = " ".join(text.split())
    if not re.search(r"[A-Za-z]", t):
        return "未判", "非英语：规则只覆盖英语"
    for tag, rx, reason, unless in rules:
        m = rx.search(t)
        if m and not (unless and unless.search(t)):
            return tag, f"{reason}（{m.group(0).strip()}）"
    return "未判", "没有命中规则"


def run_cases(cases, rules, label: str) -> list[str]:
    bad = []
    for c in cases:
        tag, _ = classify(c["text"], rules)
        if ("expect" in c and tag != c["expect"]) or ("not" in c and tag == c["not"]):
            want = c.get("expect") or f"不是{c['not']}"
            bad.append(f"[{label}] {c['text']!r} → {tag}，应为 {want}（{c.get('why', '')}）")
    return bad


def norm(s: str) -> str:
    return " ".join(s.lower().split()).rstrip("?？")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("signals", type=Path)
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--brands", nargs="*", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--kept-from", type=Path, help="题库 JSON，读 config.buyer_quotes 作人工留用集")
    ap.add_argument("--report", type=Path, help="--kept-from 的核对结果写到这里")
    a = ap.parse_args()

    profile = load_profile(a.profile)
    rules = compile_rules(profile, a.brands)
    bad = run_cases(BASE_CASES, rules, "通用") + run_cases(profile.get("regression_cases", []), rules, profile["id"])
    if bad:
        print("回归用例不过，未写产物：", *bad, sep="\n  ", file=sys.stderr)
        return 2

    with a.signals.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if "原话" not in fields:
        sys.exit("输入缺「原话」列：应是 collect_serp_signals.py / collect_keyword_data.py 的 signals.csv")
    for col in (TAG_COL, REASON_COL):
        if col not in fields:
            fields.append(col)
    for r in rows:
        r[TAG_COL], r[REASON_COL] = classify(r["原话"], rules)

    out = a.out or a.signals.with_name(a.signals.stem + ".tagged.csv")
    if out.resolve() == a.signals.resolve():
        sys.exit("--out 不能等于输入文件")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    counts = Counter(r[TAG_COL] for r in rows)
    print(f"{out}  画像 {profile['id']} {profile.get('version', '')}  " +
          "  ".join(f"{k} {v}" for k, v in counts.most_common()))

    if not a.kept_from:
        return 0
    bank = json.loads(a.kept_from.read_text(encoding="utf-8"))
    kept = {norm(q["原话"]) for q in bank.get("config", {}).get("buyer_quotes", [])}
    table = {}
    for r in rows:
        k = "留用" if norm(r["原话"]) in kept else "未留用"
        table.setdefault(r[TAG_COL], Counter())[k] += 1
    killed = [{"原话": r["原话"], "理由": r[REASON_COL]} for r in rows
              if r[TAG_COL] == "排除" and norm(r["原话"]) in kept]
    report = {
        "signals": str(a.signals), "kept_from": str(a.kept_from),
        "profile": f"{profile['id']} {profile.get('version', '')}".strip(),
        "rows": len(rows), "kept_rows": sum(c["留用"] for c in table.values()),
        "by_tag": {t: dict(c) for t, c in table.items()},
        "excluded_but_kept": killed,
        "excluded": [{"原话": r["原话"], "理由": r[REASON_COL]} for r in rows if r[TAG_COL] == "排除"],
    }
    print("标签\t留用\t未留用")
    for t, c in sorted(table.items(), key=lambda x: -sum(x[1].values())):
        print(f"{t}\t{c['留用']}\t{c['未留用']}")
    print(f"排除误杀（被标排除的留用词）：{len(killed)}")
    for k in killed:
        print("  ", k["原话"], "←", k["理由"])
    if a.report:
        a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if killed else 0


if __name__ == "__main__":
    sys.exit(main())
