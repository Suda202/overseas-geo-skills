#!/usr/bin/env python3
"""把竞争难度、优化难度接进 report-data.json，并写成品牌方看得懂的话。

难度怎么判归 geo-gap-diagnosis（scripts/difficulty.py，规则在它的 references/diagnosis-rules.md 第 8 节）；
这里只读它的 difficulty.json，把档位和读数换成对客说法，渲染层原样展示，不再计算。

对客说法的规则（Suda 2026-11-20）：
- 两个判断分开写：竞争难度（这道题的推荐名单被别家占得多牢）、优化难度（只改官网把本品做进回答有多难）。
- 不出内部参数名（轮换位、固定竞品、可改变性、阈值），用「AI 每次大约推荐几个品牌、哪几家几乎每次都在」这种话。
- 本品提及率已经 ≥30% 的题（内部档「已达标」）记优化难度「低」，说明写「已经出现在 X% 的回答里，是 AI 常推荐的
  品牌之一」，不写「达标 / 守住」，也不放进「建议先做」（Suda 2026-11-20：留空「—」客户看不懂）。
- 只评估不点名本品的题（发现、替代、问题解决），其余类型留「—」。
- 不写能涨多少。

题按题面对到报告里的题（meta.questions 的 en），对不上的列出来。主题名取报告里的主题名（difficulty.json 的主题可能是编号）。

写进 report-data.json 顶层 ``difficulty``：
    {"basis": "...", "preliminary": bool,
     "prompts": {"<qid>": {"comp": "高|中|低|", "comp_text": "...", "opt": "高|中|低|", "opt_text": "..."}},
     "topics": [{"topic", "comp", "comp_text", "opt", "opt_text", "first": [qid…]}]}

用法：
    python3 attach_difficulty.py --report report-data.json --difficulty <difficulty 目录或 difficulty.json> --out report-data.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

LEVELS = ("高", "中", "低")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def pct(x) -> str:
    if x is None:
        return "—"
    return "0%" if x == 0 else f"{x * 100:.0f}%"


def names(items: list) -> str:
    """品牌名两侧留空格（中英混排）：「PropertyGuru、99.co 和 Carousell」。"""
    items = [str(x) for x in items if x]
    return "、".join(items[:-1]) + " 和 " + items[-1] if len(items) > 1 else (items[0] if items else "")


def seen(brand: str, rate) -> str:
    return f"{brand} 目前没有出现在回答里" if not rate else f"{brand} 目前出现在 {pct(rate)} 的回答里"


def seats(x: float) -> str:
    if x < 1:
        return "几乎没有"
    return f"约 {int(x + 0.5)} 个"


def comp_text(level: str, d: dict) -> str:
    slots, fixed = d.get("slots") or 0, d.get("fixed") or []
    if level == "不判":
        return f"AI 回答这道题时很少推荐具体品牌（只有 {pct(d.get('named_any'))} 的回答提到了同类品牌），暂不评估。"
    if not slots:
        return "AI 回答这道题时多数不推荐具体品牌，推荐时也只列一两家。"
    head = f"AI 每次大约推荐 {slots:g} 个品牌"
    if fixed:
        return f"{head}，其中 {names(fixed)} 几乎每次都在，留给其他品牌的位置{seats(d.get('free') or 0)}。"
    if level == "高":
        return f"{head}，名额很少，虽然没有哪家每次都在，新品牌也很难挤进去。"
    return f"{head}，没有哪家每次都在，推荐名单轮换较多。"


def opt_reason(code: str, d: dict, brand: str) -> tuple[str, str]:
    """优化难度的原因（Suda 2026-11-23：要讲清为什么是高 / 中 / 低，档位只是结论）。

    返回 (原因, 说明)。原因是一句短话，主题层按它归类计数，所以不带品牌名、数字；说明是这道题的具体情况。"""
    now = seen(brand, d.get("target_rate"))
    rate = pct(d.get("target_rate"))
    fixed = d.get("fixed") or []
    if code == "change_low":
        step, attr = d.get("change_step") or "", d.get("change_attr") or ""
        if step == "品类错位":
            return ("AI 推荐的多是别的品类",
                    f"这道题 AI 推荐的多是别的品类，{brand} 这类产品很少被考虑；只改官网改变不了 AI 对品类的选择。")
        if step == "硬规格劣势":
            what = f"「{attr}」" if attr else "关键参数"
            return ("竞品的关键参数更强",
                    f"这道题看重{what}，竞品公开的参数比 {brand} 更强；官网写得再清楚，参数差距也还在。")
        if step == "第三方主导":
            return ("AI 主要引用第三方网站",
                    f"这道题 AI 主要引用媒体、论坛等第三方网站，很少引用品牌官网；只改官网，AI 不一定读到。")
        return ("只改官网影响不到这道题", "只改官网很难改变这道题的回答。")
    if code == "achieved":
        return ("AI 已经常推荐", f"{brand} 已经出现在 {rate} 的回答里，是 AI 常推荐的品牌之一。")
    if code == "in_pool":
        return ("已在 AI 的候选名单里",
                f"{brand} 已经出现在 {rate} 的回答里，AI 已经认识它、也会考虑它，提升起点好。")
    if code == "comp_high" and not fixed:
        # 没有每次都在的竞品，难在 AI 每次只给一两个名字
        return ("AI 每次只推荐一两家",
                f"这道题 AI 每次只推荐约 {d.get('slots') or 0:g} 个品牌，名额很少；{now}。")
    if code == "comp_high":
        who = f"{names(fixed)} "
        return ("推荐名单被固定的几家占满",
                f"AI 每次只推荐约 {d.get('slots') or 0:g} 个品牌，{who}几乎每次都在，留下的位置{seats(d.get('free') or 0)}；{now}。")
    if code == "comp_low":
        return ("推荐名单轮换多、还有位置",
                f"AI 每次推荐约 {d.get('slots') or 0:g} 个品牌，名单轮换较多，新品牌有机会进入；{now}。")
    if code == "change_high":
        return ("竞品官网被 AI 引用，可对照补内容",
                f"AI 回答这道题时常引用竞品官网，{brand} 官网补上同类内容就有机会被引用；{now}。")
    if not d.get("slots"):
        return ("AI 很少点名品牌", f"这道题的回答大多不推荐具体品牌，推荐时也只列一两家；{now}。")
    who = f"，{names(fixed)} 几乎每次都在" if fixed else ""
    return ("推荐名单还剩少量位置",
            f"AI 每次推荐约 {d.get('slots') or 0:g} 个品牌{who}，还剩{seats(d.get('free') or 0)}位置；{now}。")


def topic_comp_text(t: dict, comp: str, judged: int = 0) -> str:
    """主题的竞争说明：先说多数问题的情况（和档位一致），再说跨问题有没有固定被推荐的品牌。"""
    d = t.get("detail") or {}
    pat, fixed, leader = d.get("pattern"), d.get("fixed") or [], d.get("leader")
    if t.get("竞争难度") == "不判" or pat == "多数回答不点品牌":
        if judged:
            return f"这个主题的大多数问题 AI 很少推荐具体品牌，只有 {judged} 道会点名品牌，难度按这几道看（见问题明细）。"
        return "AI 回答这个主题的问题时很少推荐具体品牌，暂不评估。"
    lead = {
        "高": "多数问题里都有几家品牌每次都被推荐，留给其他品牌的位置很少。",
        "低": "多数问题的推荐名单轮换较多，还有位置。",
        "中": "多数问题还留有一些推荐位置。",
    }.get(comp, "")
    if pat == "单一主导":
        tail = f"其中 {fixed[0]} 在大多数问题里都被推荐，而且领先其他品牌较多。"
    elif pat == "一家固定":
        tail = f"其中 {fixed[0]} 在大多数问题里都被推荐。"
    elif pat == "多家固定":
        tail = f"其中 {names(fixed)} 在大多数问题里都被推荐。"
    elif pat == "有领先者" and leader:
        tail = f"{leader} 在一半以上的问题里被推荐。"
    else:
        tail = "不同问题推荐的品牌不太一样。"
    return lead + tail


def reason_summary(entries: list) -> str:
    """主题的优化难度原因：按原因归类、按题数从多到少；「推荐名单被占满」补上最常见的固定品牌。"""
    if not entries:
        return ""
    groups = {}
    for e in entries:
        groups.setdefault(e["opt_reason"], []).append(e)
    parts = []
    for reason, es in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        text = reason
        if reason == "推荐名单被固定的几家占满":
            common = [b for b, _ in Counter(b for e in es for b in e.get("fixed") or []).most_common(2)]
            if common:
                text = f"推荐名单被 {names(common)} 等固定占满"
        parts.append(f"{text}（{len(es)} 道）")
    return "；".join(parts) + "。"


def majority(levels: list) -> str:
    c = Counter(x for x in levels if x in LEVELS)
    n = sum(c.values())
    if not n:
        return ""
    if c["高"] * 2 > n:
        return "高"
    if c["低"] * 2 > n:
        return "低"
    return "中"


def dist_text(levels: list) -> str:
    c = Counter(x for x in levels if x in LEVELS)
    return "、".join(f"难度{k} {c[k]} 道" for k in ("低", "中", "高") if c[k])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--difficulty", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    src = args.difficulty / "difficulty.json" if args.difficulty.is_dir() else args.difficulty
    diff = json.loads(src.read_text(encoding="utf-8"))
    data = json.loads(args.report.read_text(encoding="utf-8"))
    meta = data["meta"]
    brand = meta.get("brand") or diff.get("target") or "本品"

    by_text = {norm(q.get("en")): q for q in meta.get("questions") or []}
    by_id = {str(q.get("question_id")): q for q in meta.get("questions") or [] if q.get("question_id")}
    qid_of, missing = {}, []
    for p in diff.get("prompts") or []:
        q = by_id.get(str(p["question_id"])) or by_text.get(norm(p.get("question")))
        if q:
            qid_of[p["question_id"]] = q
        else:
            if p.get("n"):  # 没有有效回答的题本来就不在报告里
                missing.append(p["question_id"])

    prompts = {}
    for p in diff.get("prompts") or []:
        q = qid_of.get(p["question_id"])
        if not q:
            continue
        d = p.get("detail") or {}
        comp, opt = p.get("竞争难度"), p.get("优化难度")
        if not p.get("n") or (comp not in LEVELS and comp != "不判"):
            continue  # 点名题、没有有效回答：不评估，问题明细里这一格是空的
        entry = {"comp": comp if comp in LEVELS else "", "comp_text": comp_text(comp, d), "opt": "", "opt_text": ""}
        if opt in LEVELS or opt == "已达标":
            entry["opt"] = opt if opt in LEVELS else "低"
            entry["opt_reason"], entry["opt_text"] = opt_reason(d.get("opt_code") or "", d, brand)
            entry["fixed"] = list(d.get("fixed") or [])
            entry["first"] = opt == "低"   # 已经常被推荐的题不进「建议先做」
        prompts[str(q["qid"])] = entry

    topics = []
    for t in diff.get("topics") or []:
        qs = [qid_of[x] for x in (t.get("detail") or {}).get("question_ids", []) if x in qid_of]
        if not qs:
            continue
        name = Counter(q.get("topic") for q in qs).most_common(1)[0][0]
        entries = [prompts.get(str(q["qid"])) for q in qs]
        opt_levels = [e["opt"] for e in entries if e]
        comp = t.get("竞争难度") if t.get("竞争难度") in LEVELS else ""
        ctext = topic_comp_text(t, comp, sum(1 for e in entries if e and e["comp"]))
        otext = reason_summary([e for e in entries if e and e.get("opt")])
        topics.append({
            "topic": name,
            "comp": comp, "comp_text": ctext,
            "opt": majority(opt_levels), "opt_text": otext,
            "first": [q["qid"] for q, e in zip(qs, entries) if e and e.get("first")],
        })

    preliminary = any(p.get("预判") for p in diff.get("prompts") or [])
    data["difficulty"] = {
        "basis": "按全部平台的回答合并判断，不随平台筛选变化；只评估不点名品牌的问题（发现、替代、问题解决）。",
        "preliminary": preliminary,
        "prompts": prompts,
        "topics": topics,
    }
    args.out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"难度接入：题 {len(prompts)}、主题 {len(topics)}；题面对不上 {len(missing)} 道"
          + (f"（{'、'.join(missing[:10])}）" if missing else "") + f" → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
