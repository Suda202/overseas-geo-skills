#!/usr/bin/env python3
"""读数 → 每道提示词、每个主题的「竞争难度」和「优化难度」，给品牌方挑主题、给我们判断能不能把效果做上去。

规则只有一份：references/diagnosis-rules.md 第 8 节；外部依据见 references/evidence-base.md「难度」。
售前、3 次试跑、正式基线都能跑；有效回答不到 ``min_valid`` 条的题只算预判。

输入：
- ``--readings``：layer_readings.py 的输出目录（readings.json 取题、主题、同类品牌；answers.jsonl 取逐条回答的品牌）。
- ``--changeability``（可选）：geo-monitoring/scripts/changeability_domains.py 的 changeability.csv。
  给了才判「只改官网能不能改变」，没给时优化难度只看竞争格局和本品现状，依据里写明。

两个判断分开出，不合成一个分：
- 竞争难度：别家把这道题占得多牢。看同类品牌里领先者出现得多稳、领先第二名多少（Semrush 竞品强度、
  Indig 主导品牌），以及一条回答一般列几家（Semrush 机会容量）。
- 优化难度：只改官网，把本品做进回答有多难。先看能不能改（可改变性），再看本品是否已在候选里、竞争难度。

只判不点名本品的题（发现、替代、问题解决）；评估、对比、验证、交易、售后题面点了名，写「不适用」。

输出（``--out``）：prompts.csv（每题一行）、topics.csv（每主题一行）、difficulty.md（给人看的两张表）、difficulty.json。

用法：
    python3 -I difficulty.py --readings <readings 目录> [--changeability changeability.csv] --out difficulty
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

PARAMS = {
    "min_valid": 7,          # 有效回答少于此数只算预判（正式基线每格 7 次）
    "min_judge": 3,          # 有效回答少于此数不判：1 次回答里出现的每家都算「每次都在」，轮换位恒为 0，全判成高（Zhiqinghe 2026-11-26）
    "no_brand": 0.20,        # 点了任一同类品牌的回答占比低于此值：答案不点品牌，不判
    "fixed_leader": 0.80,    # 领先竞品出现在 ≥80% 的回答里（Indig：5 道题里至少 4 道）……
    "sov_lead": 0.05,        # ……且声量份额领先第二名 ≥5 个百分点，算「头部固定」
    "has_leader": 0.50,      # 领先竞品出现在 ≥50% 的回答里，算「有领先者」
    "free_few": 1,           # 轮换位（每答列几家 − 固定出现的竞品家数）≤1：竞争难度高
    "free_many": 3,          # 轮换位 ≥3：竞争难度低
    "mention_ok": 0.30,      # 本品提及率 ≥30%：已达标（考核看提及率，不看排第几），任务是守住
    "in_pool": 0.20,         # 本品已在 ≥20% 的回答里出现：已进候选
    "topic_cover": 0.80,     # 主题：某竞品在 ≥80% 的题里「出现」（该题提及率 ≥50%）算固定；只有一家且份额领先 ≥5 点 → 单一主导
    "topic_emerging": 0.50,  # 主题：领先品牌在 ≥50% 的题里出现 → 有领先者
}
NAMED = {"evaluation", "sentiment", "competitor", "comparison", "verification", "validation", "trust",
         "transactional", "support", "accuracy"}
PLATFORM_ZH = {"chatgpt": "ChatGPT", "gemini": "Gemini", "overview": "AI 概览", "aimode": "AI 模式",
               "perplexity": "Perplexity", "copilot": "Copilot", "grok": "Grok", "alexa": "Alexa"}


def pct(x) -> str:
    if x is None:
        return "—"
    return "0%" if x == 0 else f"{x * 100:.0f}%"


def is_named(q: dict) -> bool:
    if q.get("named"):
        return True
    return str(q.get("prompt_type") or "").strip().casefold().replace(" ", "_") in NAMED


def load_changeability(path: Path | None) -> dict:
    if not path:
        return {}
    out = {}
    for row in csv.DictReader(open(path, encoding="utf-8-sig")):
        level = (row.get("suggested") or "").strip()
        out[row["question_id"]] = {"level": level, "step": (row.get("step") or "").strip(),
                                   "reason": (row.get("reason") or "").strip(),
                                   "attribute": (row.get("attribute_ref") or "").strip()}
    return out


def competition(answers: list, target: str, same: set) -> dict:
    """一组回答的竞争读数：领先竞品、出现率、声量份额、每答列几家。"""
    n = len(answers)
    per_answer = [[b for b in a["brands"] if b in same] for a in answers]
    named_any = sum(1 for bs in per_answer if bs)
    counts = [len(set(bs)) for bs in per_answer]
    mention = Counter(b for bs in per_answer for b in set(bs))
    total = sum(mention.values())
    rivals = [(b, c) for b, c in mention.most_common() if b != target]
    rate = lambda c: c / n if n else 0.0
    share = lambda c: c / total if total else 0.0
    lead = rivals[0] if rivals else (None, 0)
    second = rivals[1] if len(rivals) > 1 else (None, 0)
    return {
        "n": n,
        "named_any": rate(named_any),
        "slots": statistics.median(counts) if counts else 0,
        "target_rate": rate(mention.get(target, 0)),
        "leader": lead[0], "leader_rate": rate(lead[1]), "second": second[0], "second_rate": rate(second[1]),
        "leader_sov": share(lead[1]), "second_sov": share(second[1]),
        "top3_sov": share(sum(c for _, c in rivals[:3])),
        "rivals": len(rivals),
        # 固定出现的竞品：≥80% 的回答都有它（Indig「5 道里至少 4 道」用到单题的多次回答上）
        "fixed": [b for b, k in rivals if n and k / n >= PARAMS["fixed_leader"]],
    }


def pattern_of(c: dict) -> str:
    P = PARAMS
    if c["named_any"] < P["no_brand"]:
        return "答案不点品牌"
    if c["fixed"]:
        return "头部固定"
    if c["leader_rate"] >= P["has_leader"]:
        return "有领先者"
    return "分散"


def competition_level(c: dict, pattern: str) -> tuple[str, str]:
    """竞争难度看轮换位：每条回答列几家（含本品）减去每次都在的竞品家数。
    固定的几家把名额占满、剩下的位置很少，新品牌最难挤进来（Semrush：竞品强度 × 可得位置）。"""
    P = PARAMS
    slots = c["slots"]
    if c["n"] < P["min_judge"]:
        return "不判", f"每道题只有 {c['n']} 次回答，分不出哪些竞品每次都在；至少 {P['min_judge']} 次回答再判"
    if pattern == "答案不点品牌":
        return "不判", f"只有 {pct(c['named_any'])} 的回答点了同类品牌，答案在讲方法或规则，先复核题面"
    if slots == 0:
        return "中", f"多数回答不点品牌（只有 {pct(c['named_any'])} 点了同类品牌），点了的也只列一两家"
    fixed = c["fixed"]
    free = max(slots - len(fixed), 0)
    head = (f"{'、'.join(fixed)} 每次都在（≥80% 的回答）" if fixed
            else f"没有每次都在的竞品，提及最多的 {c['leader']} {pct(c['leader_rate'])}")
    txt = f"{head}；每条回答列 {slots:g} 家，轮换位 {free:g} 个"
    if free <= P["free_few"]:
        return "高", txt
    if free >= P["free_many"]:
        return "低", txt
    return "中", txt


def optimization_level(c: dict, comp: str, change: dict | None) -> tuple[str, str, str]:
    """只改官网，把本品做进回答有多难。按顺序判，命中即定档。"""
    P = PARAMS
    t, L = c["target_rate"], c["leader_rate"]
    if comp == "不判" and c["n"] < P["min_judge"]:
        return "不判", "too_few", f"回答次数不足 {P['min_judge']} 次，暂不判"
    if comp == "不判":
        return "不判", "not_judged", "答案不点品牌，提及率测不出东西；先复核题面是否在问候选"
    if t >= P["mention_ok"]:
        lead = f"，提及最多的竞品 {c['leader']} {pct(L)}" if c["leader"] else ""
        return "已达标", "achieved", f"本品出现在 {pct(t)} 的回答里{lead}，任务是守住"
    if change and change["level"] == "低":
        why = change["step"] or "可改变性低"
        return "高", "change_low", f"只改官网改不了（{why}）：{change['reason'][:80]}"
    if t >= P["in_pool"]:
        return "低", "in_pool", f"本品已在 {pct(t)} 的回答里出现，已进候选，离 {pct(P['mention_ok'])} 差 {pct(P['mention_ok'] - t)}"
    if comp == "高":
        return "高", "comp_high", f"竞争难度高，本品目前出现在 {pct(t)} 的回答里"
    if comp == "低":
        return "低", "comp_low", f"竞争分散、名额够；本品目前出现在 {pct(t)} 的回答里"
    if change and change["level"] == "高":
        return "低", "change_high", f"同类竞品官网被引明显领先本品，改官网有直接参照；本品目前 {pct(t)}"
    tail = "" if change else "（没给可改变性，未判只改官网能否改变）"
    return "中", "default", f"有领先者、本品目前出现在 {pct(t)} 的回答里{tail}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--readings", type=Path, required=True)
    ap.add_argument("--changeability", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    data = json.loads((args.readings / "readings.json").read_text(encoding="utf-8"))
    meta, questions = data["meta"], data["questions"]
    target = meta["target"]
    same = set(meta.get("same_category_brands") or []) | {target}
    answers = [json.loads(line) for line in (args.readings / "answers.jsonl").open(encoding="utf-8")]
    by_q = defaultdict(list)
    for a in answers:
        by_q[a["question_id"]].append(a)
    change = load_changeability(args.changeability)

    rows = []
    for q in questions:
        qid = q["question_id"]
        ans = by_q.get(qid, [])
        base = {"question_id": qid, "topic": q.get("topic") or "", "prompt_type": q.get("prompt_type") or "",
                "priority": q.get("priority") or "", "question": q.get("question") or "", "n": len(ans)}
        if is_named(q):
            rows.append(dict(base, 竞争格局="—", 竞争难度="不适用", 竞争依据="题面点名本品", 优化难度="不适用",
                             优化依据="题面点名本品", 预判=""))
            continue
        if not ans:
            rows.append(dict(base, 竞争格局="—", 竞争难度="不判", 竞争依据="没有有效回答", 优化难度="不判",
                             优化依据="没有有效回答", 预判=""))
            continue
        c = competition(ans, target, same)
        plats = defaultdict(list)
        for a in ans:
            plats[a["platform"]].append(a)
        slots_by = " · ".join(f"{PLATFORM_ZH.get(p, p)} {competition(v, target, same)['slots']:g}"
                              for p, v in sorted(plats.items()))
        pat = pattern_of(c)
        comp, comp_why = competition_level(c, pat)
        opt, opt_code, opt_why = optimization_level(c, comp, change.get(qid))
        rows.append(dict(base, 竞争格局=pat, 竞争难度=comp, 竞争依据=comp_why, 优化难度=opt, 优化依据=opt_why,
                         本品提及率=pct(c["target_rate"]), 领先竞品=c["leader"] or "—", 领先竞品提及率=pct(c["leader_rate"]),
                         领先份额差=pct(c["leader_sov"] - c["second_sov"]), 前三竞品份额=pct(c["top3_sov"]),
                         每答列几家=f"{c['slots']:g}", 分平台每答列几家=slots_by,
                         可改变性=(change.get(qid) or {}).get("level", "未给"),
                         预判="预判" if len(ans) < PARAMS["min_valid"] else "", _c=c,
                         # 结构化读数：基线报告用它写给品牌方看的说法（geo-presales-report-builder attach_difficulty.py）
                         detail={"opt_code": opt_code, "n": c["n"], "slots": c["slots"], "fixed": c["fixed"],
                                 "free": max(c["slots"] - len(c["fixed"]), 0), "named_any": c["named_any"],
                                 "target_rate": c["target_rate"], "leader": c["leader"],
                                 "change_level": (change.get(qid) or {}).get("level", ""),
                                 "change_step": (change.get(qid) or {}).get("step", ""),
                                 "change_attr": (change.get(qid) or {}).get("attribute", "")}))

    # ---- 主题 ----
    topics = []
    for topic in dict.fromkeys(r["topic"] for r in rows):
        rs = [r for r in rows if r["topic"] == topic and "_c" in r]
        if not rs:
            continue
        ans = [a for r in rs for a in by_q[r["question_id"]]]
        c = competition(ans, target, same)
        # Indig：某品牌在一道题里「出现」= 这道题里提及率 ≥50%；领先品牌按出现的题数排
        appear = Counter()
        for r in rs:
            qa = by_q[r["question_id"]]
            per = Counter(b for a in qa for b in set(a["brands"]) if b in same and b != target)
            for b, k in per.items():
                if k / len(qa) >= 0.5:
                    appear[b] += 1
        n_q = len(rs)
        fixed = [b for b, k in appear.most_common() if k / n_q >= PARAMS["topic_cover"]]
        leader, cover = (appear.most_common(1)[0] if appear else (None, 0))
        lead_gap = c["leader_sov"] - c["second_sov"]
        if c["named_any"] < PARAMS["no_brand"] or c["slots"] == 0:
            pat = "多数回答不点品牌"
        elif len(fixed) == 1 and lead_gap >= PARAMS["sov_lead"]:
            pat = "单一主导"            # Indig 的 clear owner
        elif len(fixed) == 1:
            pat = "一家固定"            # 每道题都在，但份额没拉开第二名
        elif fixed:
            pat = "多家固定"
        elif cover / n_q >= PARAMS["topic_emerging"]:
            pat = "有领先者"
        else:
            pat = "未定"
        if fixed:
            lead_txt = f"{'、'.join(fixed)} 在 ≥80% 的题里都出现；声量份额第一领先第二 {pct(lead_gap)}"
        elif leader:
            lead_txt = f"提及最多的 {leader} 在 {cover}/{n_q} 道题里出现；声量份额第一领先第二 {pct(lead_gap)}"
        else:
            lead_txt = "没有竞品在任何一道题里过半出现"

        def vote(col: str, done: str | None = None) -> tuple[str, str]:
            """主题档 = 题的多数档；不取平均。done 是「已达标」这类不参与比难易的档。"""
            d = Counter(r[col] for r in rs)
            judged = sum(d[k] for k in ("高", "中", "低"))
            if done and d[done] * 2 >= n_q:
                level = done
            elif not judged:
                level = "不判"
            elif d["高"] * 2 > judged:
                level = "高"
            elif d["低"] * 2 > judged:
                level = "低"
            else:
                level = "中"
            return level, " · ".join(f"{k} {d[k]}" for k in ("低", "中", "高", "已达标", "不判") if d[k])

        comp, comp_dist = vote("竞争难度")
        too_few = all(r["detail"].get("opt_code") == "too_few" for r in rs)
        opt, opt_dist = vote("优化难度", "已达标")
        if pat == "多数回答不点品牌":
            comp = "不判"
        topics.append({
            "topic": topic, "prompts": n_q, "竞争格局": pat, "竞争难度": comp, "竞争难度分布": comp_dist,
            "竞争依据": (f"每道题的回答不足 {PARAMS['min_judge']} 次，暂不判" if comp == "不判" and too_few
                       else f"只有 {pct(c['named_any'])} 的回答点了同类品牌，先复核题面" if comp == "不判" else lead_txt),
            "本品提及率": pct(c["target_rate"]), "每答列几家": f"{c['slots']:g}",
            "优化难度": opt, "优化难度分布": opt_dist,
            "可先做的题": "、".join(r["question_id"] for r in rs if r["优化难度"] == "低") or "—",
            "预判": "预判" if any(r["预判"] for r in rs) else "",
            "detail": {"pattern": pat, "fixed": fixed, "leader": leader, "cover": cover, "prompts": n_q,
                       "lead_gap": lead_gap, "named_any": c["named_any"], "slots": c["slots"],
                       "too_few": too_few, "question_ids": [r["question_id"] for r in rs]},
        })

    args.out.mkdir(parents=True, exist_ok=True)
    prompt_cols = ["question_id", "topic", "prompt_type", "priority", "n", "预判", "竞争格局", "竞争难度", "竞争依据",
                   "优化难度", "优化依据", "本品提及率", "领先竞品", "领先竞品提及率", "领先份额差", "前三竞品份额",
                   "每答列几家", "分平台每答列几家", "可改变性", "question"]
    with open(args.out / "prompts.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, prompt_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(args.out / "topics.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, [k for k in topics[0] if k != "detail"] if topics else ["topic"], extrasaction="ignore")
        w.writeheader()
        w.writerows(topics)
    clean = [{k: v for k, v in r.items() if k != "_c"} for r in rows]
    (args.out / "difficulty.json").write_text(json.dumps({"params": PARAMS, "target": target, "prompts": clean,
                                                          "topics": topics}, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    md = [f"# 竞争难度与优化难度 · {target}", "",
          "竞争难度＝别家把这道题占得多牢；优化难度＝只改官网把本品做进回答有多难。两个分开看，不合成分数；"
          "业务优先级另看。标「预判」的题有效回答不到 7 条。", "", "## 主题", "",
          "| 主题 | 题数 | 竞争格局 | 竞争难度 | 依据 | 每答列几家 | 本品提及率 | 优化难度 | 可先做的题 |",
          "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {t['topic']} | {t['prompts']} | {t['竞争格局']} | {t['竞争难度']}（{t['竞争难度分布']}） | {t['竞争依据']} | "
           f"{t['每答列几家']} | {t['本品提及率']} | {t['优化难度']}（{t['优化难度分布']}）{'，预判' if t['预判'] else ''} | "
           f"{t['可先做的题']} |"
           for t in topics]
    md += ["", "## 提示词", "", "| 题号 | 主题 | 竞争难度 | 竞争依据 | 优化难度 | 优化依据 | 分平台每答列几家 |",
           "|---|---|---|---|---|---|---|"]
    md += [f"| {r['question_id']}{'（预判）' if r['预判'] else ''} | {r['topic']} | {r['竞争难度']} | {r['竞争依据']} | "
           f"{r['优化难度']} | {r['优化依据']} | {r.get('分平台每答列几家', '—')} |" for r in rows]
    (args.out / "difficulty.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"题 {len(rows)}：竞争难度 {dict(Counter(r['竞争难度'] for r in rows))}；"
          f"优化难度 {dict(Counter(r['优化难度'] for r in rows))}；主题 {len(topics)} → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
