#!/usr/bin/env python3
"""对客确认 Base 发出前的检查（Suda 2026-10-23）。只读，不改表。

只查现行结构的 Base：没有属性池表，提示词矩阵有「目标客户」「使用场景」「意图类型」「约束条件」「业务优先级」
「业务优先级依据」字段。不符合的是旧 Base，不迁移、不检查，脚本报「不支持的旧结构」并以退出码 2 结束。

查什么：
  1. 提示词矩阵：每行有「业务优先级」（高 / 中 / 低）和依据；挂了题的行有「主题」；品牌用不上、硬条件的处境不开行；
     劣势约束条件可以挂在行上。一行一种意图类型，值来自八类：发现、问题解决、评估、对比、替代、验证、交易、售后；
     行上挂的题的意图类型和这一行一致。同一目标客户、使用场景、意图类型、约束条件只开一行；低档没挂题的发现行
     依据末尾写「本期不出：……」，非发现行本期不出题不用写；「本期不出」的理由不能是试跑读数。
     一个主题只放一种意图类型。
  2. 主题表：「主题优先级」是高 / 中 / 低且依据不空；不再有「状态」「主题范围」「信号条数」「GSC 展示」。
  3. 提示词库：状态为正式的题每条产品线 × 每个市场 × 每种语言不超过 60 道；没有停测行；每道题有出题原因、
     有所属切片（档位只读切片）；不该有品类认知题。
  4. 已移除的字段（见 RETIRED_FIELDS）不再出现。
  5. 使用说明和各表字段名里没有已退役的说法。
  6. 需求信号：目标客户叫法在提示词矩阵里有（问题）；另打印提示，不算问题：没有信号支撑的矩阵行
     （目标客户相同、约束条件也相同的信号为 0）、没有信号的目标客户、有信号却没挂在任何矩阵行上的约束条件。
  7. 约束条件：需求信号、提示词矩阵、提示词库三处选项一致。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I check_client_base.py --base <base_token> [--template] [--json out.json]
（--template：检查模板本身，【】占位是有意留的，不报）
退出码：0 通过；1 有问题；2 读不到 Base，或是不支持的旧结构 Base。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# 已退役的说法 → 现在的说法
RETIRED_TERMS = {
    "候选基线": "试跑（每平台 3 次）与正式基线（7 次）",
    "购买影响": "属性池的「重要性」",
    "审核状态": "「状态」",
    "竞争格局": "「信源壁垒」；竞争格局只在基线报告里算",
    "已批准题数": "「覆盖情况」公式内联计数",
    "优先级原因": "提示词库的「出题原因」",
    "必须项": "优先提供 / 有就提供",
    "计入情感": "不对客提供情感判断（2026-10-21）",
    "建议优先级": "提示词库没有优先级列，档位只读所属切片",
    "信源壁垒": "提示词库「可改变性」，按试跑引用前 20 域名判",
    "判断冲突": "不设属性池，不判相对竞品",
    "来源属性": "主题的约束条件从矩阵行的「约束条件」看",
}
RETIRED_FIELDS = {
    "提示词矩阵": ("约束", "可改变性", "候选主题", "目标题数", "覆盖情况", "依据信号", "依据信号条数", "备注", "旅程阶段"),
    "需求信号": ("约束", "证据可信度", "涉及品牌", "来源说明", "收集日期", "矩阵行关联", "旅程阶段"),
    "提示词库": ("建议优先级", "信源壁垒", "库分层", "看什么指标", "AI 认知差距", "优化顺序", "优先级", "提示词优先级"),
    "主题": ("来源属性", "计划题数", "可改变性低占比", "GSC 展示", "信号条数", "买家原话条数", "主题范围", "状态"),
}
# 现行结构的提示词矩阵必须有的字段；缺任何一个就是旧 Base
CURRENT_MATRIX_FIELDS = ("目标客户", "使用场景", "意图类型", "约束条件", "业务优先级", "业务优先级依据")
TIER = {"高": 0, "中": 1, "低": 2}
# --template 另要求的字段（提示词库「意图类型」从所属切片带出，导出时换成线上的诊断意图）
NEW_NAMES = {"主题": ("主题优先级", "主题优先级依据"), "提示词库": ("意图类型",)}
# 八类意图类型（2026-11-06）
ALL_TYPES = {"发现", "问题解决", "评估", "对比", "替代", "验证", "交易", "售后"}


def lark(*args):
    p = subprocess.run(["lark-cli", *args], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"lark-cli 输出无法解析：{' '.join(args[:3])} {p.stdout[:200]} {p.stderr[:200]}")


def records(base, table):
    with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix=".check_tmp_") as d:
        out = Path(d) / "rows.ndjson"
        subprocess.run(["lark-cli", "base", "+record-list", "--base-token", base, "--table-id", table,
                        "--format", "ndjson", "--output", str(out), "--overwrite"], capture_output=True, text=True)
        if not out.exists():
            print(f"读不到表：{table}", file=sys.stderr)
            sys.exit(2)
        return [json.loads(line) for line in out.read_text().splitlines() if line.strip()]


def text(v):
    if isinstance(v, list):
        return "/".join(str(x.get("text", x.get("name", "")) if isinstance(x, dict) else x) for x in v)
    return "" if v is None else str(v)


def ids(v):
    return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]


def check_matrix_v2(rows, prompt_rows):
    problems = []
    on_row = {}
    type_on_row = {}
    for p in prompt_rows:
        for i in ids(p.get("所属切片")):
            on_row.setdefault(i, []).append(text(p.get("编号")))
            type_on_row.setdefault(i, []).append((text(p.get("编号")), text(p.get("意图类型"))))
    # 看板没有类型字段，一个主题只放一种意图类型（2026-11-05）
    topic_types = {}
    for r in rows:
        rtype = text(r.get("意图类型"))
        if rtype and on_row.get(r.get("record_id")):
            for tid in ids(r.get("主题")):
                topic_types.setdefault(tid, set()).add(rtype)
    for tid, types in topic_types.items():
        if len(types) > 1:
            problems.append(f"主题 {tid}：挂了{'、'.join(sorted(types))}几种意图类型的题；一个主题只放一种类型（selection-rules.md → 6）")
    for r in rows:
        sid = text(r.get("切片编号")) or r.get("record_id")
        tier = text(r.get("业务优先级"))
        if tier not in TIER:
            problems.append(f"提示词矩阵 {sid}：「业务优先级」没填（高 / 中 / 低）；范围外、没有合理需求依据、品牌做不到又没服务路径的处境不开行，从矩阵里删掉、记进题库 notes")
            continue
        basis = text(r.get("业务优先级依据"))
        if not basis.strip():
            problems.append(f"提示词矩阵 {sid}：{tier} 没写「业务优先级依据」（这个需求对哪项业务目标起什么作用）")
        carried = on_row.get(r.get("record_id"), [])
        rtype = text(r.get("意图类型"))
        if carried and not ids(r.get("主题")):
            problems.append(f"提示词矩阵 {sid}：挂了题但没挂「主题」")
        # 低档行默认不出题（2026-11-05）：没挂题的发现行要在依据末尾写「本期不出：业务优先级低，原因……」；为补高、中覆盖挂了题的不报
        if TIER[tier] == 2 and not carried and rtype == "发现" and "本期不出" not in basis:
            problems.append(f"提示词矩阵 {sid}：业务优先级为低，依据末尾要写「本期不出：业务优先级低，原因……」")
        # 本期不出的理由不能是试跑读数：品牌读数不进选题（Hbrand 2026-11-04 M-024、M-025）
        reason = basis.split("本期不出", 1)
        if len(reason) == 2 and re.search(r"\d+\s*/\s*\d+|\d+\s*次|0 次|没提到|未提及", reason[1]):
            problems.append(f"提示词矩阵 {sid}：「本期不出」的理由写了试跑读数；品牌读数不进选题，改写题或重判这一行")
        if rtype not in ALL_TYPES:
            problems.append(f"提示词矩阵 {sid}：「意图类型」写了「{rtype or '空'}」，不是八类之一"
                            f"（发现、问题解决、评估、对比、替代、验证、交易、售后，selection-rules.md → 5）")
        for pid, ptype in type_on_row.get(r.get("record_id"), []):
            if ptype and ptype in ALL_TYPES and ptype != rtype:
                problems.append(f"提示词矩阵 {sid}：挂了{ptype}题 {pid}，但这一行的「意图类型」是"
                                f"{rtype or '空'}；同一使用场景另开一行{ptype}行，把题挂过去")
    # 同一目标客户、同一使用场景、同一意图类型、同一约束条件只开一行（2026-11-05 起按类型分行）
    seen = {}
    for r in rows:
        scene = text(r.get("使用场景"))
        cons = "/".join(sorted(t for t in text(r.get("约束条件")).split("/") if t))
        if scene and cons:
            label = text(r.get("切片编号")) or r.get("record_id")
            seen.setdefault((scene, text(r.get("目标客户")), text(r.get("意图类型")), cons), []).append(label)
    for (scene, _, rtype, cons), sids in seen.items():
        if len(sids) > 1:
            problems.append(f"提示词矩阵 {'、'.join(sids)}：目标客户、使用场景「{scene}」、意图类型「{rtype}」、约束条件「{cons}」都相同；同一任务的同一类型只开一行")
    for r in rows:
        if not text(r.get("切片编号")):
            problems.append(f"提示词矩阵 {r.get('record_id')}：没有切片编号；空行删掉，有内容的补编号")
    return problems


def check_topics_v2(trows, matrix_rows, prompt_rows):
    problems = []
    for r in trows:
        name = text(r.get("主题"))
        if not name:
            continue
        label = f"主题「{name}」（{text(r.get('市场')) or '未填市场'}）"
        level = text(r.get("主题优先级"))
        if level not in ("高", "中", "低"):
            problems.append(f"{label}「主题优先级」没填（高 / 中 / 低）")
        elif not text(r.get("主题优先级依据")).strip():
            problems.append(f"{label}主题优先级 {level} 没写「主题优先级依据」")
    return problems


def check_prompts_v2(rows, matrix):
    problems = []
    stopped = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("状态")) == "停测"]
    if stopped:
        problems.append(f"提示词库还留着 {len(stopped)} 条停测题（应删除，题号和原因记在题库 config.retired）：{', '.join(stopped[:8])}")
    ca = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("意图类型")) == "品类认知"]
    if ca:
        problems.append(f"提示词库有 {len(ca)} 道品类认知题：品类认知只在调研预跑里跑，不进提示词库（2026-10-29）：{', '.join(ca[:8])}")
    for r in rows:
        code = text(r.get("编号")) or text(r.get("提示词"))[:20]
        reason = text(r.get("出题原因"))
        if not reason.strip():
            problems.append(f"提示词库「{code}」没有出题原因")
        sl = next((matrix[i] for i in ids(r.get("所属切片")) if i in matrix), None)
        if sl is None:
            problems.append(f"提示词库「{code}」没有所属切片")
            continue
    # 正式题总额度（2026-11-05）：每条产品线 × 每个国家 × 每种语言合计最多 60 道，单个主题不设上限。
    # 市场多选的题每个市场各算一次；Base 没有「语言」字段时按产品线 × 市场数（同一市场两种语言会合并计数，偏严）。
    quota = {}
    for r in rows:
        if text(r.get("状态")) != "正式":
            continue
        markets = [m for m in text(r.get("市场")).split("/") if m] or ["未填市场"]
        for m in markets:
            key = (text(r.get("产品线")) or "未填产品线", m, text(r.get("语言")) if "语言" in r else "")
            quota[key] = quota.get(key, 0) + 1
    for (line, market, lang), n in sorted(quota.items()):
        if n > 60:
            where = " × ".join(x for x in (line, market, lang) if x)
            problems.append(f"正式题 {where} 有 {n} 道，超过 60 道（每条产品线 × 每个国家 × 每种语言合计最多 60 道）")
    return problems


def buyer_constraints(r):
    """一行的约束条件（三张表共用的选项字段「约束条件」）。"""
    return {x for x in text(r.get("约束条件")).split("/") if x}


HYPOTHESIS_SOURCES = {"query fan-outs", "AI 追问", "模型建议问题",  # 模型生成、背后没有真实用户（2026-11-04）
                      "品牌官网", "竞品官网"}  # 品牌自己写的内容（2026-11-05）


def check_signals_v2(sig_rows, matrix_rows):
    """需求信号（2026-11-04 起）：目标客户叫法和矩阵一致（问题）；每行矩阵、每类目标客户有几条信号支撑（提示，不算问题）。
    一行的支撑信号 = 目标客户和这一行有交集、约束条件也和这一行有交集；来源类型是 query fan-outs、AI 追问、模型建议问题、品牌官网、竞品官网的不算支撑
    （模型生成、背后没有真实用户，只开假设级候选），目标客户叫法照查。"""
    def auds(r):
        return {x for x in text(r.get("目标客户")).split("/") if x}
    m_auds = set().union(*[auds(m) for m in matrix_rows]) if matrix_rows else set()
    problems = [f"需求信号「{text(r.get('输入编号'))}」的目标客户「{a}」不在提示词矩阵的目标客户里（三处叫法要一致）"
                for r in sig_rows for a in sorted(auds(r) - m_auds) if m_auds]
    sigs = [(auds(r), buyer_constraints(r)) for r in sig_rows
            if not HYPOTHESIS_SOURCES & set(text(r.get("来源类型")).split("/"))]
    notes = []
    zero_rows = [text(m.get("切片编号")) or "（无编号）" for m in matrix_rows
                 if not any(sa & auds(m) and sc & buyer_constraints(m) for sa, sc in sigs)]
    if zero_rows:
        notes.append(f"{len(zero_rows)} 行矩阵没有信号支撑（只有假设，依据写在业务优先级依据）：{'、'.join(zero_rows)}")
    zero_auds = sorted(a for a in m_auds if not any(a in sa for sa, _ in sigs))
    if zero_auds:
        notes.append(f"这些目标客户没有信号：{'、'.join(zero_auds)}")
    on_rows = set().union(*[buyer_constraints(m) for m in matrix_rows]) if matrix_rows else set()
    cnt = {}
    for _, sc in sigs:
        for c in sc - on_rows:
            cnt[c] = cnt.get(c, 0) + 1
    if cnt:
        top = sorted(cnt.items(), key=lambda kv: -kv[1])
        notes.append(f"{len(top)} 条约束条件有信号却没挂在任何矩阵行上：" + "、".join(f"{c} {n}" for c, n in top))
    return problems, notes


def check_constraint_options(base, tables):
    """三张表的「约束条件」选项是同一份名单（2026-11-04 起）。"""
    opts = {}
    for t in ("需求信号", "提示词矩阵", "提示词库"):
        if t not in tables:
            continue
        fl = (lark("base", "+field-list", "--base-token", base, "--table-id", tables[t]).get("data") or {}).get("fields") or []
        f = next((x for x in fl if x.get("name") == "约束条件"), None)
        if f is not None:
            opts[t] = {o.get("name") for o in f.get("options") or []}
    problems = []
    if "提示词矩阵" in opts:
        for t, o in opts.items():
            for name in sorted(o - opts["提示词矩阵"]):
                problems.append(f"{t}「约束条件」有选项「{name}」，提示词矩阵里没有（三张表的选项要一致，改名、合并时一起改）")
            if t != "提示词矩阵":
                for name in sorted(opts["提示词矩阵"] - o):
                    problems.append(f"提示词矩阵「约束条件」有选项「{name}」，{t}里没有（三张表的选项要一致）")
    return problems


def field_names(base, tables):
    out = {}
    for name, tid in tables.items():
        fields = lark("base", "+field-list", "--base-token", base, "--table-id", tid)
        names = [f.get("name", "") for f in (fields.get("data") or {}).get("fields") or []]
        out[name] = names
    return out


def check_fields_v2(fields):
    problems = []
    for table, retired in RETIRED_FIELDS.items():
        for f in fields.get(table, []):
            if f in retired:
                problems.append(f"{table} 还有字段「{f}」：已移除（2026-10-28 / 11-01，见 client-facing-base.md）")
    return problems


def table_ids(base):
    listing = lark("base", "+base-block-list", "--base-token", base)
    return {b["name"]: b["id"] for b in (listing.get("data") or {}).get("blocks") or [] if b.get("type") == "table"}


def check_terms(base, template=False):
    problems = []
    terms = RETIRED_TERMS
    listing = lark("base", "+base-block-list", "--base-token", base)
    blocks = (listing.get("data") or {}).get("blocks") or []
    for b in blocks:
        if b.get("type") == "table":
            fields = lark("base", "+field-list", "--base-token", base, "--table-id", b["id"])
            for f in (fields.get("data") or {}).get("fields") or []:
                for term, now in RETIRED_TERMS.items():
                    if term in f.get("name", ""):
                        problems.append(f"{b['name']} 还有字段「{f['name']}」：已退役，现在用{now}")
        if b.get("docx_token"):
            doc = lark("docs", "+fetch", "--doc", b["docx_token"], "--doc-format", "markdown", "--scope", "full")
            content = ((doc.get("data") or {}).get("document") or {}).get("content") or ""
            for term, now in terms.items():
                n = content.count(term)
                if n:
                    problems.append(f"{b['name']} 里「{term}」出现 {n} 次：已退役，现在用{now}")
            n = 0 if template else content.count("【")
            if n:
                problems.append(f"{b['name']} 里还有 {n} 处【】占位没填")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--json")
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    tables = table_ids(a.base)
    fields = field_names(a.base, tables)
    missing = [n for n in CURRENT_MATRIX_FIELDS if n not in fields.get("提示词矩阵", [])]
    if "属性池" in tables or missing:
        why = "；".join(x for x in ("有属性池表" if "属性池" in tables else "",
                                   f"提示词矩阵缺字段 {'、'.join(missing)}" if missing else "") if x)
        print(f"不支持的旧结构 Base（{why}）：旧 Base 不迁移，不检查")
        sys.exit(2)
    prompt_rows = records(a.base, "提示词库")
    matrix_rows = records(a.base, "提示词矩阵")
    matrix = {r["record_id"]: r for r in matrix_rows}
    topic_rows = records(a.base, "主题") if "主题" in tables else []
    problems = check_fields_v2(fields) + check_constraint_options(a.base, tables)
    if a.template:
        problems += [f"{t} 缺字段「{n}」" for t, names in NEW_NAMES.items() for n in names if n not in fields.get(t, [])]
    notes = []
    if not a.template:
        problems += (check_matrix_v2(matrix_rows, prompt_rows) + check_topics_v2(topic_rows, matrix_rows, prompt_rows)
                     + check_prompts_v2(prompt_rows, matrix))
        if "需求信号" in tables and "约束条件" in fields.get("需求信号", []):
            sig_problems, notes = check_signals_v2(records(a.base, "需求信号"), matrix_rows)
            problems += sig_problems
    if "主题" not in tables:
        problems.append("没有「主题」表")
    problems += check_terms(a.base, a.template)
    for p in problems:
        print("问题：" + p)
    for n in notes:
        print("提示：" + n)
    print(f"共 {len(problems)} 个问题" if problems else "通过")
    if a.json:
        Path(a.json).write_text(json.dumps(problems, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
