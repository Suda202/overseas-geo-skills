#!/usr/bin/env python3
"""读数 + 标注 + 页面缺口 → 优化机会诊断表。规则全部在 references/diagnosis-rules.md，本脚本只是它的实现。

输入：
    --readings    layer_readings.py 的输出目录（readings.json、answers.jsonl）
    --labels      label_batches.py merge 产出的 labels.json（可选；没有时第 7、8 断点记未知）
    --pagegap     page_gap.py 的输出目录（可选；没有时第 5、6 断点记未知）
    --constraints 可选 JSON：{"<question_id>": {"relative": "明显优势|优势|持平|劣势|明显劣势|未知", "basis": "…"}}
    --site-audit  可选 JSON：{"crawlability": "高|中|低", "source": "报告路径或日期"}
    --out         输出目录：diagnosis.csv、diagnosis.json、diagnosis.md

阈值在 PARAMS，可用 --param key=value 覆盖。

用法：
    python3 -I diagnose.py --readings readings --labels labels/labels.json --pagegap pagegap --out diagnosis
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PARAMS = {
    "min_valid": 7,          # 门 0：合并有效回答下限
    "min_fact_errors": 2,    # 事实错误成立的回答数
    "hold_margin": 0.10,     # 守住：本品提及率 ≥ 领先竞品 − 10 个点
    "ground_low": 0.50,      # 断点 2
    "retr_low": 0.20,        # 断点 3 / 4 的分界：官网进检索率低于它判断点 3，不低于它再看是否被引
    "mention_ok": 0.30,      # 断点 7
    "rec_ok": 0.50,          # 推荐占比
    "min_labelled": 3,       # 推荐占比至少要几条标注
    "min_retrieval_n": 5,    # 检索层读数至少几条可观察回答
    "no_brand": 0.20,        # 发现题里领先品牌提及率低于它 = 答案基本不点名品牌
    "seat_min": 0.40,        # 信息类题：引用了门户、攻略、媒体这类非机构来源的回答占比低于它才判「机构来源占满」
}
LIST_TYPES = {"Discovery", "Alternatives"}      # 判提及缺口的类型（答案是候选名单）
NAMED_REC_TYPES = {"Competitor", "Evaluation"}  # 点名题里判推荐的类型；其余点名类型只看劝退和事实
PRIO_RANK = {"高": 0, "P1": 0, "中": 1, "P2": 1, "未定": 2, "": 2, "低": 3, "P3": 3}
REC = {"D-TOP", "D-REC"}

BP_TEXT = {
    1: ("抓取不可达", "官网技术", "交官网修复爬虫可达性（robots、CDN、渲染），修好前不派内容动作", "官网诊断报告可达性；官网进检索率", "修复后 14 天"),
    2: ("不联网", "第三方或分布式资料", "在行业媒体、评测、百科类资料里建立「品牌 + 品类 + 场景」的稳定表述", "本品提及率", "60–90 天"),
    3: ("官网没进检索层", "官网", "写或改一页以买家问法为标题、首段直接回答本题需求的页面；先改最接近的现有页面", "官网进检索率", "上线后 14 天"),
    4: ("进了检索层没被引用", "官网", "首段直接回答题面问题，把关键事实（数字、条件、限制）写成正文", "官网被引率", "30 天"),
    5: ("页面缺口", "第三方页面", "争取被引第三方页面收录本品，按「被引次数 × 已提竞品数」排序", "目标页面是否已提到本品；本品提及率", "页面更新后 30–60 天"),
    6: ("答案缺口", "第三方页面", "请被引页面补可核实的本品段落（只请改事实，不请改观点）", "本品提及率", "30–60 天"),
    7: ("被提及但没被推荐", "官网或第三方（按 AI 说出的推荐标准定）", "对照 AI 说出的推荐标准，补本品「适合谁、为什么」的可核实证据", "被提及回答里的推荐占比", "30–60 天"),
    8: ("被推荐但说错", "错误来源所在载体", "按错误来源改正事实（官网旧页、官方店、第三方页面）", "同类事实错误条数", "改正后 30 天"),
}


def wilson(k, n, z=1.96):
    import math
    if not n:
        return [None, None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(w):
    return None if not w or w[0] is None else w[0]


def pct(w, n=None):
    if not w or w[0] is None:
        return "—"
    s = f"{w[0]:.0%}"
    if n:
        s += f"（{round(w[0] * n)}/{n}）"
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readings", required=True, type=Path)
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--pagegap", type=Path)
    ap.add_argument("--constraints", type=Path)
    ap.add_argument("--site-audit", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--param", action="append", default=[])
    args = ap.parse_args(argv)
    P = dict(PARAMS)
    for kv in args.param:
        k, v = kv.split("=", 1)
        P[k] = type(PARAMS[k])(v)

    data = json.loads((args.readings / "readings.json").read_text(encoding="utf-8"))
    meta = data["meta"]
    target = meta["target"]
    answers = [json.loads(line) for line in (args.readings / "answers.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    by_q = defaultdict(list)
    for a in answers:
        by_q[a["question_id"]].append(a)
    official_seen = any(a["official_retrieved"] or a["official_cited"] for a in answers)

    labels = json.loads(args.labels.read_text(encoding="utf-8")) if args.labels and args.labels.exists() else None
    fact_errors = [fe for fe in (labels or {}).get("_fact_errors", []) if fe.get("brand", target) == target]
    pg_rows, pg_pages = [], {}
    if args.pagegap and (args.pagegap / "page_gap.csv").exists():
        pg_rows = list(csv.DictReader((args.pagegap / "page_gap.csv").open(encoding="utf-8-sig")))
        pg_pages = json.loads((args.pagegap / "page_gap.json").read_text(encoding="utf-8"))["pages"]
    pg_by_q = defaultdict(list)
    for r in pg_rows:
        pg_by_q[r["question_id"]].append(r)
    constraints = json.loads(args.constraints.read_text(encoding="utf-8")) if args.constraints else {}
    site = json.loads(args.site_audit.read_text(encoding="utf-8")) if args.site_audit else {}
    crawl = str(site.get("crawlability") or "未知")

    rows = []
    for q in data["questions"]:
        pooled = q["platforms"].get("合并")
        if not pooled:
            continue
        rows.extend(diagnose_question(q, pooled, by_q[q["question_id"]], labels, fact_errors, pg_by_q[q["question_id"]],
                                      pg_pages, constraints.get(q["question_id"]) or {}, crawl, official_seen, target, P))
    rows.extend(accuracy_rows(fact_errors, data, P))
    rows.extend(sku_rows(data, by_q, pg_rows, pg_pages, P))

    # 对照题组：同主题里本期没有「测试」的题
    tested = {r["题号"] for r in rows if r["决定"] == "测试"}
    topic_qs = defaultdict(list)
    for q in data["questions"]:
        if not q["named"]:
            topic_qs[(q["topic"], q["prompt_type"])].append(q["question_id"])
    for r in rows:
        if r["决定"] == "测试" and r["对象"] == "品牌":
            ctrl = [x for x in topic_qs.get((r["主题"], r["类型"]), []) if x not in tested and x != r["题号"]]
            r["对照题组"] = ("、".join(ctrl[:5]) + ("…" if len(ctrl) > 5 else "")) if ctrl \
                else "无可比对照（结论按方向性写）"
    order = {"测试": 0, "先补研究": 1, "观察": 2, "守住": 3, "转产品": 4, "暂不做": 5, "不适用": 6}
    rows.sort(key=lambda r: (order.get(r["决定"], 9), PRIO_RANK.get(r["业务优先级"], 2), r["_pattern"], r["题号"]))
    for i, r in enumerate(rows, 1):
        r["机会编号"] = f"O-{i:03d}"

    args.out.mkdir(parents=True, exist_ok=True)
    cols = ["机会编号", "对象", "题号", "题面", "主题", "类型", "业务优先级", "有效回答", "本品提及率", "领先竞品",
            "领先竞品提及率", "官网进检索率", "官网被引率", "推荐分布", "过门情况", "断点", "主原因（假设）", "证据",
            "证据强度", "次要发现", "分平台读数", "决定", "载体", "缺口", "信息怎么变好（候选）", "最接近的现有页面（候选，需人确认）",
            "主指标", "对照题组", "最早复测", "负责方"]
    with (args.out / "diagnosis.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (args.out / "diagnosis.json").write_text(json.dumps({"params": P, "meta": {k: v for k, v in meta.items()
                                                                               if k not in ("brands",)},
                                                         "crawlability": crawl, "rows": rows},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "diagnosis.md").write_text(render_md(rows, meta, P, crawl, labels, pg_pages, args), encoding="utf-8")
    print(f"机会 {len(rows)} 行：{dict(Counter(r['决定'] for r in rows))}；断点 "
          f"{dict(Counter(r['断点'] for r in rows if r['决定'] in ('测试', '先补研究')))}")
    return 0


def label_stats(group, labels, brand):
    codes = Counter()
    quotes = defaultdict(list)
    if labels is None:
        return None, codes, quotes
    for a in group:
        lab = (labels.get(a["answer_id"]) or {}).get(brand)
        if lab and lab["code"] not in ("Z-GAP", "UNSURE"):
            codes[lab["code"]] += 1
            if lab.get("constraint") or lab.get("quote"):
                quotes[lab["code"]].append(lab.get("constraint") or lab.get("quote"))
    n = sum(codes.values())
    share = (codes["D-TOP"] + codes["D-REC"]) / n if n else None
    return share, codes, quotes


def base_row(q, pooled, share, codes):
    return {
        "对象": "品牌", "题号": q["question_id"], "题面": q["question"], "主题": q["topic"], "类型": q["prompt_type"],
        "业务优先级": q["priority"], "有效回答": pooled["n"],
        "本品提及率": pct(pooled["target_mention"], pooled["n"]),
        "领先竞品": pooled.get("leader") or "", "领先竞品提及率": pct(pooled.get("leader_mention"), pooled["n"]),
        "官网进检索率": pct(pooled["official_retrieved"], pooled["retrieval_n"]) if pooled["retrieval_n"] else "不可观察",
        "官网被引率": pct(pooled["official_cited"], pooled["n"]),
        "推荐分布": "、".join(f"{c} {n}" for c, n in codes.most_common()) if codes else "未标注",
        "过门情况": "", "断点": "", "主原因（假设）": "", "证据": "", "证据强度": "", "次要发现": "", "决定": "",
        "载体": "", "缺口": "", "信息怎么变好（候选）": "", "最接近的现有页面（候选，需人确认）": "",
        "主指标": "", "对照题组": "", "最早复测": "", "负责方": "", "_pattern": 9,
        "分平台读数": "；".join(f"{p} 提及 {pct(v['target_mention'])}、官网被引 {pct(v['official_cited'])}（{v['n']} 条）"
                            for p, v in q["platforms"].items() if p != "合并"),
    }


def pattern_rank(t, lead):
    """沿用 geo-monitoring baseline-report 的优化顺序：部分出现仍落后 → 竞品领先 → 无品牌点名 → 已打平。"""
    if t is None or lead is None:
        return 5
    if t > 0.2 and lead - t >= 0.3:
        return 0
    if t <= 0.2 and lead - t >= 0.3:
        return 1
    if t <= 0.2:
        return 2
    return 3


def diagnose_question(q, pooled, group, labels, fact_errors, pg, pg_pages, cons, crawl, official_seen, target, P):
    out = []
    share, codes, quotes = label_stats(group, labels, target)
    r = base_row(q, pooled, share, codes)
    n = pooled["n"]
    t = rate(pooled["target_mention"])
    lead = rate(pooled.get("leader_mention"))
    r["_pattern"] = pattern_rank(t, lead)
    q_fe = [fe for fe in fact_errors if fe.get("question_id") == q["question_id"]]
    fe_answers = len({fe["answer_id"] for fe in q_fe})
    secondary = []
    if pooled.get("grounded", {}).get("强制"):
        secondary.append("ChatGPT 强制联网，联网层不可观察")

    ptype = q["prompt_type"]
    if not q["named"] and ptype not in LIST_TYPES:
        return [citation_row(r, q, pooled, group, crawl, official_seen, P)]
    other = max((rate(o["mention"]) or 0 for o in pooled.get("other_brands") or []), default=0)
    if not q["named"] and (lead or 0) < P["no_brand"] and (t or 0) < P["no_brand"] and other >= P["rec_ok"]:
        return [category_row(r, q, pooled, pg, P)]
    if not q["named"] and (lead or 0) < P["no_brand"] and (t or 0) < P["no_brand"]:
        # 发现题答案基本不点名任何同类品牌（解释模式），提及率测不出东西，改按引用缺口判
        row = citation_row(r, q, pooled, group, crawl, official_seen, P)
        row["次要发现"] = ("答案基本不点名同类品牌（领先者 " + pct(pooled.get("leader_mention"), n)
                       + "），提及率测不出，按引用缺口判；题面是否在问候选，回选词复核") + (
            "；" + row["次要发现"] if row.get("次要发现") else "")
        return [row]
    # 门 0
    if n < P["min_valid"]:
        return [dict(r, 过门情况="门 0 未过", 决定="观察", 主原因="", 证据=f"有效回答 {n} 条 < {P['min_valid']}")]
    # 门 1
    prio = q["priority"]
    if prio in ("低", "P3"):
        return [dict(r, 过门情况="门 1 未过", 决定="暂不做", 证据="业务优先级低")]
    # 门 2
    if str(cons.get("relative")) == "明显劣势":
        return [dict(r, 过门情况="门 2 未过", 决定="转产品", 证据=f"主约束相对竞品明显劣势：{cons.get('basis', '')}")]
    # 对比题：看谁被首推（胜负），不看推荐占比
    if q["named"] and ptype == "Competitor" and labels is not None:
        win, lose, rivals = 0, 0, Counter()
        for a in group:
            labs = labels.get(a["answer_id"]) or {}
            if (labs.get(target) or {}).get("code") == "D-TOP":
                win += 1
            else:
                tops = [b for b, lab in labs.items() if b != target and lab.get("code") == "D-TOP"]
                if tops:
                    lose += 1
                    rivals.update(tops)
        r["推荐分布"] = f"对比：本品首推 {win}/{n}，竞品首推 {lose}/{n}（{'、'.join(f'{k} {v}' for k, v in rivals.most_common())}）"
        if lose <= win or lose < n * (1 - P["rec_ok"]):
            r.update(过门情况="点名题", 决定="守住", 证据=f"对比题本品首推 {win}/{n}，竞品首推 {lose}/{n}")
            return [r]
        rival = rivals.most_common(1)[0][0]
        reasons = [lab.get("quote") for a in group for b, lab in (labels.get(a["answer_id"]) or {}).items()
                   if b == rival and lab.get("code") == "D-TOP"]
        steer = codes.get("Q-FIT", 0) + codes.get("X-WARN", 0)
        strength = "模型标注（需核对竞品胜出理由是否是硬规格差距）"
        r.update(过门情况="通过", 断点="7 对比输", **{"主原因（假设）": f"AI 在对比里首推 {rival}；先读胜出理由，硬规格差距转产品，证据缺口补对比页"},
                 证据=f"本品首推 {win}/{n}，{rival} 等首推 {lose}/{n}；胜出理由：" + "；".join(dict.fromkeys(reasons))[:300],
                 证据强度=strength, 决定="先补研究", 载体="官网对比页或第三方评测", 缺口=f"{q['question_id']} 对比题：本品首推 {win}/{n}，竞品首推 {lose}/{n}",
                 **{"信息怎么变好（候选）": "写如实的对比页：列出 AI 说的胜出理由逐项对照，本品真实的赢点配可核实证据；硬规格输的项不回避"},
                 主指标="对比题本品首推率", 最早复测="30–60 天", 负责方="内容团队", 次要发现=f"本品有条件不推荐或劝退 {steer} 条" if steer else "")
        return [r]
    # 守住
    if not q["named"] and t is not None and lead is not None and t >= lead - P["hold_margin"] \
            and (share is None or share >= P["rec_ok"]):
        r.update(过门情况="已领先", 决定="守住",
                 证据=f"本品 {pct(pooled['target_mention'], n)}，领先竞品 {r['领先竞品']} {r['领先竞品提及率']}"
                      + (f"，推荐占比 {share:.0%}" if share is not None else ""))
        out.append(r)
    elif q["named"] and ptype not in NAMED_REC_TYPES and codes.get("X-WARN", 0) < max(1, sum(codes.values()) * 0.3):
        r.update(过门情况="不适用", 决定="不适用", 证据=f"{ptype} 点名题只判劝退和事实错误；劝退 {codes.get('X-WARN', 0)} 条")
        out.append(r)
    elif q["named"] and (share is None or share >= P["rec_ok"]):
        r.update(过门情况="点名题", 决定="守住", 证据=f"点名题推荐占比 {share:.0%}" if share is not None else "点名题，未标注")
        out.append(r)
    else:
        # 门 3
        stable = False
        if q["named"]:
            steer = codes.get("Q-FIT", 0) + codes.get("X-WARN", 0)
            stable = sum(codes.values()) >= P["min_labelled"] and steer >= sum(codes.values()) * (1 - P["rec_ok"])
        else:
            lw, tw = pooled.get("leader_mention") or [None] * 3, pooled["target_mention"]
            stable = (lw[1] is not None and tw[2] is not None and lw[1] > tw[2]) \
                or (t is not None and t >= P["mention_ok"] and share is not None and share < P["rec_ok"]
                    and sum(codes.values()) >= P["min_labelled"])
        if not stable:
            ev = (f"点名题推荐占比 {share:.0%}，但有条件不推荐和劝退不到一半，只是事实陈述，不算缺口" if q["named"] and share is not None
                  else f"本品 {r['本品提及率']} 与领先竞品 {r['领先竞品']} {r['领先竞品提及率']} 的区间重叠")
            r.update(过门情况="门 3 未过", 决定="观察", 证据=ev)
            out.append(r)
        else:
            r["过门情况"] = "通过"
            lw, tw = pooled.get("leader_mention") or [None] * 3, pooled["target_mention"]
            r["_mention_gap"] = q["named"] is False and lw[1] is not None and tw[2] is not None and lw[1] > tw[2]
            out.append(find_breakpoint(r, q, pooled, share, codes, quotes, q_fe, fe_answers, pg, crawl,
                                       official_seen, secondary, P))
    return out


def find_breakpoint(r, q, pooled, share, codes, quotes, q_fe, fe_answers, pg, crawl, official_seen, secondary, P):
    n = pooled["n"]
    hits = []
    if r.get("_mention_gap"):  # 提及落后才查 1–6；提及不落后、只是没被推荐的，直接从第 7 断点判
        if crawl == "低":
            hits.append((1, "官网诊断报告爬虫可达性低", "实测"))
        g = pooled.get("grounded_rate") or [None] * 3
        if g[0] is not None and g[0] < P["ground_low"]:
            hits.append((2, f"联网率 {g[0]:.0%}", "实测"))
        rn = pooled["retrieval_n"]
        orr = rate(pooled["official_retrieved"])
        if rn >= P["min_retrieval_n"] and orr is not None:
            if orr < P["retr_low"]:
                strength = "实测" if (official_seen or crawl in ("高", "中")) else "推断：可达性未核"
                hits.append((3, f"有检索字段的 {rn} 条回答里官网进检索 {pct(pooled['official_retrieved'], rn)}", strength))
            elif (rate(pooled["official_cited"]) or 0) < orr * 0.5:
                hits.append((4, f"官网进检索 {pct(pooled['official_retrieved'], rn)}，被引 {pct(pooled['official_cited'], n)}", "实测"))
        page_gaps = sorted([x for x in pg if x["gap"] == "页面缺口"], key=lambda x: -int(x["gap_score"]))
        if page_gaps:
            hits.append((5, "；".join(f"{x['url']}（被引 {x['answers']} 条，提了 {x['competitors']}）" for x in page_gaps[:3]), "实测"))
        ans_gaps = [x for x in pg if x["gap"] == "答案缺口"]
        if ans_gaps:
            hits.append((6, "；".join(f"{x['url']}（页面提了本品，引用它的 {x['answers_target_absent']}/{x['answers']} 条回答没提）"
                                     for x in ans_gaps[:3]), "实测"))
    t = rate(pooled["target_mention"])
    labelled = sum(codes.values())
    steer = codes.get("Q-FIT", 0) + codes.get("X-WARN", 0)
    named_ok = q["named"] and steer >= labelled * (1 - P["rec_ok"])  # 点名题只在 AI 把人劝走时算，纯事实陈述不算
    if share is not None and labelled >= P["min_labelled"] and share < P["rec_ok"] and (named_ok or (not q["named"] and (t or 0) >= P["mention_ok"])):
        top = codes.most_common(1)[0][0]
        ex = "；".join(dict.fromkeys(quotes.get(top, [])))[:300]
        hits.append((7, f"被提及 {labelled} 条里推荐占比 {share:.0%}，最多的是 {top}：{ex}",
                     "模型标注" if top != "Q-FIT" else "模型标注（Q-FIT 需核对约束是否属实）"))
    if q_fe:
        secondary.append(f"本题有 {fe_answers} 条回答写错事实（{'、'.join(sorted({fe['basis'] for fe in q_fe}))}），见事实行")
    if q.get("sku_fit") and codes.get("Q-FIT"):
        secondary.append(f"本题有适配 SKU（{'、'.join(q['sku_fit'])}）：Q-FIT 指向的若是别的型号，问题在 SKU 没出现，见 SKU 行")
    if pooled.get("retrieval_n", 0) == 0 and not q["named"]:
        secondary.append("这道题的平台不暴露检索层，断点 3、4 不可观察")
    if not pg:
        secondary.append("没跑页面缺口或本题没有被引 ≥2 次的第三方页面")
    if not hits:
        r.update(断点="未定位", 决定="先补研究", 证据="八个断点都没有成立的证据", 次要发现="；".join(secondary),
                 缺口=gap_sentence(r, q))
        return r
    bp, evidence, strength = hits[0]
    name, carrier, action, metric, retest = BP_TEXT[bp]
    secondary += [f"断点 {h[0]} {BP_TEXT[h[0]][0]}：{h[1][:160]}" for h in hits[1:]]
    decision = "测试"
    if strength.startswith("推断") or "Q-FIT" in strength:
        decision = "先补研究"
    cands = "；".join(f"{c['url']}（{c['answers']} 条）" for c in pooled.get("official_page_candidates") or []) or "无（检索和引用里没出现过官网页面）"
    r.update(断点=f"{bp} {name}", 主原因=name, **{"主原因（假设）": hypothesis(bp, codes)}, 证据=evidence, 证据强度=strength,
             次要发现="；".join(secondary), 决定=decision, 载体=carrier, 缺口=gap_sentence(r, q),
             **{"信息怎么变好（候选）": action, "最接近的现有页面（候选，需人确认）": cands if bp in (3, 4, 7) else ""},
             主指标=metric, 最早复测=retest, 负责方="内容团队" if bp in (3, 4, 7) else ("渠道 / PR" if bp in (5, 6) else
                                                                           "官网技术" if bp == 1 else "内容团队 + 品牌方"))
    return r


def hypothesis(bp, codes):
    return {
        1: "AI 爬虫拿不到官网正文",
        2: "这道题 AI 主要靠模型记忆作答",
        3: "站内没有以需求为题的页面，或相关页面标题、首段只写品牌型号",
        4: "页面和题面命题不契合，或关键事实不在正文",
        5: "高频被引的第三方页面没收录本品",
        6: "第三方页面提了本品但位置、篇幅或描述不支撑本题需求",
        7: {"Q-FIT": "AI 认为本品在本题场景有约束（见证据）；先核对约束是否属实",
            "X-WARN": "AI 依据负面评价或劣势劝退",
            "R-LIST": "差异化和适用场景证据不足，AI 只把本品当名单成员"}.get(codes.most_common(1)[0][0] if codes else "", "推荐证据不足"),
        8: "官网、官方店或第三方页面的事实写法冲突或过时",
    }[bp]


def gap_sentence(r, q):
    if q["named"]:
        return f"{q['question_id']} 点名题：推荐分布 {r['推荐分布']}"
    return (f"{q['question_id']}：本品提及率 {r['本品提及率']}，领先竞品 {r['领先竞品']} {r['领先竞品提及率']}，"
            f"官网进检索 {r['官网进检索率']}、被引 {r['官网被引率']}")


def category_row(r, q, pooled, pg, P):
    """品类错位：答案推的是别的品类。不改题面（题是真实买家问法）；先判本品能不能替代这个品类，
    被引页面里已经有提到本品的，直接按答案缺口做品类替代内容。"""
    n = pooled["n"]
    top_other = (pooled.get("other_brands") or [{}])[0]
    head = (f"答案推的是别的品类：{top_other.get('name')} {pct(top_other.get('mention'), n)}，同类品牌都不到 "
            f"{P['no_brand']:.0%}")
    if q["priority"] in ("低", "P3"):
        return dict(r, 过门情况="门 1 未过", 决定="暂不做", 证据="业务优先级低；" + head)
    seats = [x for x in pg if x["fetch"] == "ok" and str(x.get("target_on_page")) == "True"]
    r["过门情况"] = "品类错位"
    if seats:
        return dict(r, 断点="6 答案缺口（品类替代）",
                    **{"主原因（假设）": "AI 按别的品类作答；被引页面已经把本品列为替代选项，答案没提"},
                    证据=head + "；被引页面提到了本品：" + "；".join(f"{x['url']}（被引 {x['answers']} 条）" for x in seats[:3]),
                    证据强度="实测（替代是否成立需人确认）", 决定="测试", 载体="官网对照页 + 已被引的第三方页面",
                    缺口=f"{q['question_id']}：{top_other.get('name')} {pct(top_other.get('mention'), n)}，本品 {r['本品提及率']}",
                    **{"信息怎么变好（候选）": "官网写如实的品类对照页（本品和该品类各适合谁、能替代到什么程度）；"
                                         "请已提到本品的被引页面补可核实的替代说明"},
                    主指标="本品作为替代选项的提及率", 最早复测="30–60 天", 负责方="内容团队 + 渠道 / PR",
                    次要发现="预期放低：目标是作为替代选项被提到，不是赢过该品类的领先品牌", _pattern=3)
    return dict(r, 断点="品类错位", 决定="先补研究",
                **{"主原因（假设）": "AI 按别的品类作答"},
                证据=head + "；被引页面里没有提到本品的",
                证据强度="待人确认替代路径",
                次要发现="先判本品能不能真的替代这个品类（服务路径，见选词 selection-rules 第 3 步）："
                        "能替代 → 转测试，做官网品类对照页并争取进入被引的对照或榜单页；不能替代 → 回选词，改为只监测或删题。"
                        "不改题面：题是真实买家问法", _pattern=5)


def source_kind(host: str) -> str:
    """inst（政府、百科）/ ugc（社区、视频、社媒）/ other（门户、媒体、攻略、厂商）。"""
    import sys as _s
    from pathlib import Path as _P
    skills = _P(__file__).resolve().parents[2]
    for extra in (skills / "geo-monitoring" / "scripts", skills / "geo-metrics" / "scripts"):
        if str(extra) not in _s.path:
            _s.path.insert(0, str(extra))
    import changeability_domains as cd
    from geo_presales_core.sources import load_cache
    global _SRC_CACHE
    if "_SRC_CACHE" not in globals():
        _SRC_CACHE = load_cache()
    dom = cd.reg_domain(host)
    if cd.is_gov(dom) or cd.is_wiki(dom):
        return "inst"
    return "ugc" if cd.third_party_type(dom, _SRC_CACHE) == "ugc" else "other"


def citation_row(r, q, pooled, group, crawl, official_seen, P):
    """问题解决、信息类不点名题：答案通常不列品牌，目标是官网成为被引来源。只判引用缺口，断点只看 3、4。"""
    from urllib.parse import urlsplit
    n = pooled["n"]
    r["对象"] = "品牌（引用）"
    if n < P["min_valid"]:
        return dict(r, 过门情况="门 0 未过", 决定="观察", 证据=f"有效回答 {n} 条")
    if q["priority"] in ("低", "P3"):
        return dict(r, 过门情况="门 1 未过", 决定="暂不做", 证据="业务优先级低")
    hosts, kinds, seat, inst_any = Counter(), {}, 0, 0
    for a in group:
        hs = {urlsplit(u).netloc.lower().removeprefix("www.") for u in a["third_cited_urls"] + a["competitor_cited_urls"]
              if u.startswith("http")}
        for h in hs:
            kinds.setdefault(h, source_kind(h))
        hosts.update(h for h in hs if kinds[h] == "other")
        seat += any(kinds[h] == "other" for h in hs)
        inst_any += any(kinds[h] == "inst" for h in hs)
    if not kinds:
        return dict(r, 过门情况="不适用", 决定="观察", 证据="回答几乎不带引用")
    seat_w = wilson(seat, n)
    inst_note = f"机构站（政府、百科）出现在 {pct(wilson(inst_any, n), n)} 的回答，非机构席位 {pct(seat_w, n)}"
    ow = pooled["official_cited"]
    # 门 2：引用位几乎都被政府、百科占满，攻略、门户类页面进不去（Profound 101 第 13 课：前十名大多是机构来源时公司内容难进入）
    if (seat_w[0] or 0) < P["seat_min"]:
        return dict(r, 过门情况="门 2 未过", 决定="暂不做", 证据=inst_note + f"，低于 {P['seat_min']:.0%}：引用位基本被机构来源占满")
    top, k = hosts.most_common(1)[0]
    lw = wilson(k, n)
    r["领先竞品"], r["领先竞品提及率"] = f"被引最多的非机构来源 {top}", pct(lw, n)
    r["次要发现"] = inst_note
    if ow[0] is not None and lw[0] is not None and ow[0] >= lw[0] - P["hold_margin"]:
        return dict(r, 过门情况="已领先", 决定="守住", 证据=f"官网被引 {pct(ow, n)}，{top} {pct(lw, n)}")
    # 门 3：和「非机构席位」比（攻略、门户这类位置有多少回答在用），不和单个站比——席位常分散在多个攻略站
    if not (seat_w[1] is not None and ow[2] is not None and seat_w[1] > ow[2]):
        return dict(r, 过门情况="门 3 未过", 决定="观察", 证据=f"官网被引 {pct(ow, n)} 与非机构席位 {pct(seat_w, n)} 区间重叠")
    r["过门情况"] = "通过"
    rn, orr = pooled["retrieval_n"], rate(pooled["official_retrieved"])
    if crawl == "低":
        bp, ev, strength = 1, "官网诊断报告爬虫可达性低", "实测"
    elif rn >= P["min_retrieval_n"] and orr is not None and orr < P["retr_low"]:
        bp, ev = 3, f"有检索字段的 {rn} 条回答里官网进检索 {pct(pooled['official_retrieved'], rn)}；{top} 被引 {pct(lw, n)}"
        strength = "实测" if (official_seen or crawl in ("高", "中")) else "推断：可达性未核"
    elif rn >= P["min_retrieval_n"] and orr is not None:
        bp, ev, strength = 4, f"官网进检索 {pct(pooled['official_retrieved'], rn)}，被引 {pct(ow, n)}；{top} 被引 {pct(lw, n)}", "实测"
    else:
        return dict(r, 断点="未定位", 决定="先补研究", 证据=f"检索层不可观察；官网被引 {pct(ow, n)}，{top} {pct(lw, n)}")
    name, carrier, action, metric, retest = BP_TEXT[bp]
    cands = "；".join(f"{c['url']}（{c['answers']} 条）" for c in pooled.get("official_page_candidates") or []) \
        or "无（检索和引用里没出现过官网页面）"
    return dict(r, 断点=f"{bp} {name}", **{"主原因（假设）": "官网没有直接回答这个问题的页面，或有页面但不是被选中的来源"},
                证据=ev, 证据强度=strength, 决定="测试" if strength == "实测" else "先补研究", 载体=carrier,
                缺口=f"{q['question_id']}（{q['prompt_type']}）：官网被引 {pct(ow, n)}，被引最多的非机构来源 {top} {pct(lw, n)}",
                次要发现=r.get("次要发现", ""),
                **{"信息怎么变好（候选）": action + f"；对照 {top} 被引页面的结构和事实写", "最接近的现有页面（候选，需人确认）": cands},
                主指标="官网被引率" if bp == 4 else metric, 最早复测=retest, 负责方="内容团队", _pattern=4)


def sku_rows(data, by_q, pg_rows, pg_pages, P):
    """每个 SKU 一行：跨该 SKU 的全部适配题合并判（单题 7 次区间太宽，SKU 问题本来就是跨题的）。"""
    fit = defaultdict(list)
    for q in data["questions"]:
        for sku in (q["platforms"].get("合并") or {}).get("sku") or {}:
            fit[sku].append(q)
    summary = data["meta"].get("sku_summary") or {}
    rows = []
    for sku, qs in fit.items():
        group = [a for q in qs for a in by_q[q["question_id"]]]
        n = len(group)
        obs = [a for a in group if a["retrieval_observable"]]
        brand = wilson(sum(a["target_mentioned"] for a in group), n)
        seen = wilson(sum(sku in a.get("sku_mentions", []) or sku in a.get("sku_cards", []) for a in group), n)
        retr = wilson(sum(sku in a.get("sku_retrieved", []) for a in obs), len(obs))
        cited = wilson(sum(sku in a.get("sku_cited", []) for a in group), n)
        qids = [q["question_id"] for q in qs]
        detail = "；".join(f"{q['question_id']} 品牌 {pct(q['platforms']['合并']['target_mention'])}、SKU "
                           f"{pct(q['platforms']['合并']['sku'][sku]['mention_or_card'])}" for q in qs)
        prio = min((q["priority"] for q in qs), key=lambda p: PRIO_RANK.get(p, 2))
        r = {"对象": f"SKU：{sku}", "题号": "、".join(qids), "题面": "", "主题": "", "类型": "SKU", "业务优先级": prio,
             "有效回答": n, "本品提及率": pct(brand, n), "领先竞品": "", "领先竞品提及率": "",
             "官网进检索率": f"SKU 页 {pct(retr, len(obs))}" if obs else "不可观察",
             "官网被引率": f"SKU 页 {pct(cited, n)}", "推荐分布": f"SKU 正文或商品卡 {pct(seen, n)}",
             "过门情况": "", "断点": "", "主原因（假设）": "", "证据": "", "证据强度": "", "次要发现": detail, "决定": "",
             "载体": "", "缺口": f"{len(qs)} 道适配题合并：品牌 {pct(brand, n)}，{sku} {pct(seen, n)}",
             "信息怎么变好（候选）": "", "最接近的现有页面（候选，需人确认）": "", "主指标": "", "对照题组": "",
             "最早复测": "", "负责方": "", "_pattern": 0}
        allq = summary.get(sku) or {}
        if allq:
            un = allq.get("不点名题", {})
            nm = allq.get("点名题", {})
            r["次要发现"] += (f"；全部不点名题 SKU 页进检索 {pct(un.get('retrieved'), un.get('n'))}、"
                          f"点名题 {pct(nm.get('retrieved'), nm.get('n'))}")
        if n < P["min_valid"]:
            rows.append(dict(r, 过门情况="门 0 未过", 决定="观察"))
            continue
        if not (brand[1] is not None and seen[2] is not None and brand[1] > seen[2]):
            rows.append(dict(r, 过门情况="门 3 未过" if (seen[0] or 0) < 0.5 else "已领先",
                             决定="观察" if (seen[0] or 0) < 0.5 else "守住",
                             证据=f"品牌 {pct(brand, n)} 与 SKU {pct(seen, n)} 区间重叠"))
            continue
        pages_wo = sorted({x["url"] for x in pg_rows if x["question_id"] in qids and x["fetch"] == "ok"
                           and pg_pages.get(x["url"], {}).get("target_on_page")
                           and sku not in (pg_pages.get(x["url"], {}).get("skus_on_page") or [])})
        if len(obs) >= P["min_retrieval_n"] and (retr[0] or 0) < P["retr_low"]:
            bp, ev, why = 3, f"适配题 {len(obs)} 条可观察回答里 SKU 页进检索 {pct(retr, len(obs))}", \
                "品牌在、型号不在：SKU 页标题和正文以品牌加型号为主，只有检索词带品牌时才命中"
            action = "写以需求为标题、正文讲清该 SKU 适配哪些场景的页面，再从 SKU 产品页互链；SKU 页首屏写清它和投屏款等相邻型号的区别"
            metric = "适配题 SKU 页进检索率；SKU 出现率"
        elif len(obs) >= P["min_retrieval_n"] and (cited[0] or 0) < (retr[0] or 0) * 0.5:
            bp, ev, why = 4, f"SKU 页进检索 {pct(retr, len(obs))}，被引 {pct(cited, n)}", "SKU 页被检索到但关键事实不好提取"
            action, metric = BP_TEXT[4][2], "SKU 页被引率"
        elif pages_wo:
            bp, ev, why = 5, f"被引第三方页面提了品牌、没提 {sku}：" + "；".join(pages_wo[:3]), "第三方评测只收录了品牌的其他型号"
            action, metric = BP_TEXT[5][2], "目标页面是否已提到该 SKU；SKU 出现率"
        else:
            rows.append(dict(r, 过门情况="通过", 断点="未定位", 决定="先补研究", 证据="检索层与页面缺口都不成立"))
            continue
        rows.append(dict(r, 过门情况="通过", 断点=f"{bp} {BP_TEXT[bp][0]}（SKU）", **{"主原因（假设）": why}, 证据=ev,
                         证据强度="实测", 决定="测试", 载体=BP_TEXT[bp][1], **{"信息怎么变好（候选）": action},
                         主指标=metric, 最早复测=BP_TEXT[bp][4], 负责方="内容团队" if bp != 5 else "渠道 / PR",
                         对照题组="同主题不适配该 SKU 的题"))
        if pages_wo and bp != 5:
            rows[-1]["次要发现"] += f"；被引第三方页面里提了品牌、没提该 SKU 的 {len(pages_wo)} 个"
    return rows


def accuracy_rows(fact_errors, data, P):
    by_basis = defaultdict(list)
    for fe in fact_errors:
        by_basis[fe.get("basis") or "未注明"].append(fe)
    qinfo = {q["question_id"]: q for q in data["questions"]}
    rows = []
    for basis, items in sorted(by_basis.items()):
        answers = {fe["answer_id"] for fe in items}
        qs = sorted({fe["question_id"] for fe in items})
        prio = min((qinfo[x]["priority"] for x in qs if x in qinfo), key=lambda p: PRIO_RANK.get(p, 2), default="未定")
        ok = len(answers) >= P["min_fact_errors"]
        rows.append({
            "对象": f"事实：{basis}", "题号": "、".join(qs), "题面": "", "主题": "", "类型": "准确性", "业务优先级": prio,
            "有效回答": len(answers), "本品提及率": "", "领先竞品": "", "领先竞品提及率": "", "官网进检索率": "", "官网被引率": "",
            "推荐分布": "", "过门情况": "通过" if ok else "门 3 未过", "断点": "8 被推荐但说错" if ok else "",
            "主原因（假设）": "官网、官方店或第三方页面的事实写法冲突或过时",
            "证据": "；".join(dict.fromkeys(f"「{fe['quote'][:90]}」→ {fe['correct']}" for fe in items))[:600],
            "证据强度": "模型标注，需人工逐条核", "次要发现": "", "决定": "测试" if ok else "观察", "载体": "错误来源所在载体",
            "缺口": f"{len(answers)} 条回答在 {len(qs)} 道题里写错 {basis}", "信息怎么变好（候选）": BP_TEXT[8][2],
            "最接近的现有页面（候选，需人确认）": "", "主指标": BP_TEXT[8][3], "对照题组": "", "最早复测": BP_TEXT[8][4],
            "负责方": "内容团队 + 品牌方", "_pattern": -1,
        })
    return rows


def render_md(rows, meta, P, crawl, labels, pg_pages, args):
    c = Counter(r["决定"] for r in rows)
    lines = [f"# {meta['target']} 优化机会诊断（自动初稿）", "",
             "本文件由 `diagnose.py` 生成，是分析师的初稿：每条「测试」的原因假设、候选页面都要按 "
             "gap-cause-action-table.md 的三项核对（回答原文、被引来源、官网与产品事实）确认后再交内容团队。", "",
             "## 数据与口径", "",
             f"- 有效回答 {meta['answers']} 条，平台 {meta['platforms']}；采集目录 {len(meta['runs'])} 个。",
             f"- 强制联网的平台：{'、'.join(meta['forced_search']) or '无'}（这些平台联网层不可观察）。",
             f"- 官网可达性：{crawl}；推荐标注：{'有' if labels else '无（断点 7、8 未判）'}；"
             f"页面缺口：{'抓取 %d 个页面，成功 %d 个' % (len(pg_pages), sum(p['status'] == 'ok' for p in pg_pages.values())) if pg_pages else '未跑（断点 5、6 未判）'}。",
             f"- 阈值：{json.dumps(P, ensure_ascii=False)}", "",
             "## 结论分布", "", "| 决定 | 行数 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in c.most_common()] + [""]
    by_topic = defaultdict(Counter)
    for r in rows:
        if r["决定"] in ("测试", "先补研究") and r["主题"]:
            by_topic[r["主题"]][r["断点"]] += 1
    if by_topic:
        lines += ["## 按主题汇总（测试与先补研究）", "", "同一主题、同一断点的题，动作通常可以合成一页或一组页面来做，交内容团队时按主题派。", "",
                  "| 主题 | 断点与题数 |", "|---|---|"]
        lines += [f"| {tp} | {'；'.join(f'{k} × {v}' for k, v in cnt.most_common())} |"
                  for tp, cnt in sorted(by_topic.items(), key=lambda x: -sum(x[1].values()))]
        lines.append("")
    for decision in ("测试", "先补研究", "观察", "守住", "转产品", "暂不做", "不适用"):
        part = [r for r in rows if r["决定"] == decision]
        if not part:
            continue
        lines += [f"## {decision}（{len(part)}）", ""]
        if decision in ("测试", "先补研究"):
            for r in part:
                lines += [f"### {r['机会编号']} {r['对象']} · {r['题号']} · {r['断点']}", "",
                          f"- 题面：{r['题面']}（{r['主题']}，{r['类型']}，优先级 {r['业务优先级']}）" if r["题面"] else f"- 涉及题：{r['题号']}",
                          f"- 缺口：{r['缺口']}", f"- 原因假设：{r['主原因（假设）']}（证据强度：{r['证据强度']}）",
                          f"- 证据：{r['证据']}"]
                if r.get("分平台读数"):
                    lines.append(f"- 分平台：{r['分平台读数']}")
                if r["次要发现"]:
                    lines.append(f"- 次要发现：{r['次要发现']}")
                if decision == "测试":
                    lines += [f"- 载体：{r['载体']}；动作候选：{r['信息怎么变好（候选）']}"]
                    if r["最接近的现有页面（候选，需人确认）"]:
                        lines.append(f"- 最接近的现有页面（候选）：{r['最接近的现有页面（候选，需人确认）']}")
                    lines.append(f"- 度量契约：主指标 {r['主指标']}；最早复测 {r['最早复测']}；对照题组 {r['对照题组'] or '—'}")
                lines.append("")
        else:
            lines += ["| 编号 | 对象 | 题号 | 优先级 | 本品 | 领先竞品 | 依据 |", "|---|---|---|---|---|---|---|"]
            lines += [f"| {r['机会编号']} | {r['对象']} | {r['题号']} | {r['业务优先级']} | {r['本品提及率']} | "
                      f"{r['领先竞品']} {r['领先竞品提及率']} | {r['证据'][:120]} |" for r in part]
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
