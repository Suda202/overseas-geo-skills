#!/usr/bin/env python3
"""对客确认 Base 发出前的检查（Suda 2026-10-23；2026-10-28 改为两种结构）。只读，不改表。

先按表结构认新旧：提示词矩阵有「业务重要性依据」（2026-11-02 前叫「优先级依据」）字段的是新结构
（2026-10-28 起），否则是旧结构（旧客户 Base 不迁移，照旧规则查）。三个优先级字段 2026-11-02 改名：
矩阵「业务重要性」、主题「主题优先级」、提示词库「提示词优先级」；旧名照认，--template 要求新名。

新结构查：
  1. 属性池：相对竞品为优势 / 持平 / 劣势的行，「相对竞品依据」不空（旧 Base 的「判据与证据」要有「相对竞品（值）：…」一行）；
     不该再有「重要性」「可改变性」「优先级」「判断冲突」字段。
  2. 提示词矩阵：每行有「业务重要性」（高 / 中 / 低；旧 Base 的 P1 / P2 / P3 同序）和依据；
     挂了题的行有「主题」；每行都有档位，品牌用不上、硬条件的处境不开行（2026-11-05）；劣势属性可以挂在行上；用新字段名的 Base，旅程阶段是
     需求认知 / 方案考虑 / 购买决策三段（2026-11-02）；有「提示词类型」（旧名可出题型）字段时（2026-11-03 起），
     值来自发现、替代、对比、评价、问题解决，阶段和题型分别判断，
     除方案考虑行的发现外，每个登记的类型在「提示词类型依据」里有一行「类型：依据」（证据或「假设：……」），
     行上挂的题的「提示词类型」都在登记范围内（验证题不查）；对客表放完整矩阵，需求认知、购买决策行没挂题的
     是品牌方没选的目标，业务重要性依据里要写「本期不出：……」（2026-11-02），不写在备注（2026-11-02 审核清单 D1）。
  3. 主题表：「状态」不空（单个主题不设题数上限，2026-11-05）；有「主题优先级」列时（2026-11-01 起），
     它是高 / 中 / 低且依据不空。候选主题不设题数底线（2026-10-30）。
  4. 提示词库：状态为正式的题每条产品线 × 每个市场 × 每种语言不超过 60 道（2026-11-05）；没有停测行；每道题有出题原因、提示词优先级；默认档位 = 所属切片的业务重要性，
     可改变性只作诊断观察；和默认不一致的，出题原因里有「改档：理由，定为 X」；
     相对弱势可保留；临时验证保存到独立诊断记录；不该有品类认知题（只在属性池前预跑）。
  5. 已移除的字段：属性池「重要性」「可改变性」「优先级」「判断冲突」「属性编号」，提示词矩阵「约束」
     「可改变性」「候选主题」「目标题数」「覆盖情况」，提示词库「建议优先级」「信源壁垒」「库分层」
     「看什么指标」「AI 认知差距」「优化顺序」，主题「来源属性」「计划题数」「可改变性低占比」。
  6. 使用说明和各表字段名里没有已退役的说法。
  7. 需求信号（2026-11-04 起）：受众叫法在提示词矩阵里有（问题）；另打印提示，不算问题：没有信号支撑的矩阵行
     （受众相同、买方约束也相同的信号为 0）、没有信号的受众、有信号却没挂在任何矩阵行上的买方约束。
  8. 买方约束（2026-11-04 起，属性池并进三张表的选项字段）：需求信号、提示词矩阵、提示词库三处选项一致。
     没有属性池表的 Base 不查属性池；旧 Base 有属性池的照查。

旧结构查（2026-10-27 及以前的规则）：属性池三项判断的依据行、属性池「优先级」不空、
提示词库停测行 / 出题原因 / 优先级与建议优先级的改档理由、退役说法。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I check_client_base.py --base <base_token> [--template] [--json out.json]
（--template：检查模板本身，【】占位是有意留的，不报）
退出码：0 通过；1 有问题；2 读不到 Base。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# 已退役的说法 → 现在的说法（2026-10-23 盘点）
RETIRED_TERMS = {
    "候选基线": "试跑（每平台 3 次）与正式基线（30 次）",
    "购买影响": "属性池的「重要性」",
    "审核状态": "「状态」",
    "竞争格局": "「信源壁垒」；竞争格局只在基线报告里算",
    "已批准题数": "「覆盖情况」公式内联计数",
    "优先级原因": "提示词库的「出题原因」",
    "必须项": "优先提供 / 有就提供",
    "计入情感": "不对客提供情感判断（2026-10-21）",
}
# 2026-10-28 起新结构里退役的说法（旧结构 Base 的使用说明里合法存在，只对新结构查）
RETIRED_TERMS_V2 = {
    "建议优先级": "提示词库只有一列可编辑的「优先级」，脚本按矩阵行预填",
    "信源壁垒": "提示词库「可改变性」，按试跑引用前 20 域名判",
    "判断冲突": "属性池只判相对竞品",
    "来源属性": "主题的买方约束从矩阵行的「买方约束」看",
}
RETIRED_FIELDS_V2 = {
    "属性池": ("重要性", "可改变性", "优先级", "判断冲突", "属性编号"),
    "提示词矩阵": ("约束", "可改变性", "候选主题", "目标题数", "覆盖情况", "依据信号", "依据信号条数", "备注"),
    "需求信号": ("约束", "证据可信度", "涉及品牌", "来源说明", "收集日期", "矩阵行关联", "旅程阶段"),
    "提示词库": ("建议优先级", "信源壁垒", "库分层", "看什么指标", "AI 认知差距", "优化顺序"),
    "主题": ("来源属性", "计划题数", "可改变性低占比"),
}
# 行档位：2026-11-01 起高 / 中 / 低；旧 Base 的 P1 / P2 / P3 同序
TIER = {"P1": 0, "高": 0, "P2": 1, "中": 1, "P3": 2, "低": 2}
STAGES = ("需求认知", "方案考虑", "购买决策")
# --template 要求的新字段名（2026-11-02）
NEW_NAMES = {"提示词矩阵": ("业务优先级", "业务优先级依据"), "主题": ("主题优先级", "主题优先级依据"),
             "提示词库": ("提示词优先级",)}
# 阶段独立标注，正式类型均可按买家证据登记；临时验证存题库之外。
STAGE_TYPES = {stage: {"发现", "替代", "对比", "评价", "问题解决"}
               for stage in ("需求认知", "方案考虑", "购买决策")}
# 方案考虑行的发现默认登记，不要求依据行
DEFAULT_TYPES = {("方案考虑", "发现")}
TIER_NAMES = (("P1", "P2", "P3"), ("高", "中", "低"))


LABELS = {
    "重要性": ("重要性", "买家关注度"),
    "可改变性": ("可改变性", "内容能不能改变"),
    "相对竞品": ("相对竞品",),
}
VALUE_ALIAS = {"领先": "优势"}


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


def has_basis(evidence: str, judgement: str, value: str) -> bool:
    """判据里有没有写明这个判断、而且档位和格子一致的一行。"""
    value = VALUE_ALIAS.get(value, value)
    for label in LABELS[judgement]:
        for m in re.finditer(rf"{label}[（(]?(高|中|低|优势|领先|持平|劣势|待确认)[)）]?[：:]", evidence):
            got = VALUE_ALIAS.get(m.group(1), m.group(1))
            if got == value and evidence[m.end():].split("\n", 1)[0].strip():
                return True
    return False


def check_pool(rows):
    problems = []
    for r in rows:
        name = text(r.get("属性")) or r.get("record_id")
        if not text(r.get("属性")):  # 空白占位行（模板里有）不判
            continue
        evidence = text(next((r[k] for k in ("相对竞品依据", "判据与证据", "判据") if k in r), ""))  # 2026-11-04 起叫相对竞品依据；旧名照认
        role = text(r.get("类别")) == "买家角色"
        judgements = ("重要性",) if role else ("重要性", "可改变性", "相对竞品")
        for j in judgements:
            value = text(r.get(j))
            if value and not has_basis(evidence, j, value):
                problems.append(f"属性池「{name}」：{j}填了「{value}」，判据里没有写明依据的「{j}（{value}）：…」一行")
        # 属性层优先级（2026-10-26 起在属性池）：非买家角色行必须有值
        if rows and "优先级" in rows[0] and not role and not text(r.get("优先级")):
            problems.append(f"属性池「{name}」：「优先级」是空的（属性档位 2026-10-26 起记在属性池）")
    if rows and "优先级" not in rows[0]:
        problems.append("属性池没有「优先级」列（2026-10-26 起属性档位在属性池，矩阵不再带优先级）")
    return problems


def check_prompts(rows):
    problems = []
    stopped = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("状态")) == "停测"]
    if stopped:
        problems.append(f"提示词库还留着 {len(stopped)} 条停测题（应删除，题号和原因记在题库 config.retired）：{', '.join(stopped[:8])}")
    if rows and "出题原因" in rows[0]:
        empty = [text(r.get("编号")) for r in rows if not text(r.get("出题原因")).strip()]
        if empty:
            problems.append(f"提示词库 {len(empty)} 道题没有出题原因：{', '.join(empty[:8])}")
    elif rows:
        problems.append("提示词库没有「出题原因」字段")
    # 优先级可手改（Suda 2026-10-26）：「优先级」单选由脚本按「建议优先级」公式预填；
    # 两者不一致时，出题原因里必须有「改档：理由，定为 Px」，Px 与「优先级」一致。
    if rows and "建议优先级" in rows[0]:
        blank = [text(r.get("编号")) for r in rows if not text(r.get("优先级"))]
        if blank:
            problems.append(f"提示词库 {len(blank)} 道题「优先级」是空的（应按建议优先级预填）：{', '.join(blank[:8])}")
        pending = [text(r.get("编号")) for r in rows if text(r.get("建议优先级")) == "待判"]
        if pending:
            problems.append(f"提示词库 {len(pending)} 道题建议优先级「待判」：所属切片没挂属性；宽泛题要挂属性池的「品类基线」行"
                            f"（2026-10-26 起不再固定 P1）：{', '.join(pending[:8])}")
        for r in rows:
            manual, sugg = text(r.get("优先级")), text(r.get("建议优先级"))
            if manual and sugg and manual != sugg:
                m = re.search(r"改档[：:](.+)", text(r.get("出题原因")), re.S)
                if not m or not m.group(1).strip() or f"定为 {manual}" not in m.group(1):
                    problems.append(f"提示词库「{text(r.get('编号'))}」：优先级手改为 {manual}（建议 {sugg}），"
                                    f"出题原因里没有写「改档：理由，定为 {manual}」")
    elif rows:
        problems.append("提示词库没有「建议优先级」列（优先级应可手改，建议档位写在「建议优先级」）")
    return problems


def ids(v):
    return [x.get("id") if isinstance(x, dict) else x for x in (v or [])]


def check_pool_v2(rows):
    problems = []
    for r in rows:
        name = text(r.get("属性"))
        if not name:
            continue
        evidence = text(next((r[k] for k in ("相对竞品依据", "判据与证据", "判据") if k in r), ""))  # 2026-11-04 起叫相对竞品依据；旧名照认
        value = text(r.get("相对竞品"))
        if "判据与证据" not in r and "判据" not in r:
            # 2026-11-04 起专列「相对竞品依据」，只写依据、不重复写结论：优势 / 持平 / 劣势不能空
            if value in ("优势", "持平", "劣势") and not evidence.strip():
                problems.append(f"属性池「{name}」：相对竞品填了「{value}」，相对竞品依据是空的")
        elif value and not has_basis(evidence, "相对竞品", value):
            problems.append(f"属性池「{name}」：相对竞品填了「{value}」，判据里没有「相对竞品（{value}）：…」一行")
    return problems


def first(row, *names):
    """按新名、旧名顺序取字段（2026-11-02 起矩阵「业务重要性」、主题「主题优先级」、提示词库「提示词优先级」，旧 Base 不改名）。"""
    for name in names:
        if name in row:
            return text(row.get(name))
    return ""


def check_matrix_v2(rows, prompt_rows, pool_rows=()):
    problems = []
    on_row = {}
    type_on_row = {}
    for p in prompt_rows:
        for i in ids(p.get("所属切片")):
            on_row.setdefault(i, []).append(text(p.get("编号")))
            type_on_row.setdefault(i, []).append((text(p.get("编号")), text(p.get("提示词类型"))))
    for r in rows:
        sid = text(r.get("切片编号")) or r.get("record_id")
        tier = first(r, "业务优先级", "业务重要性", "优先级")
        if tier not in TIER:
            problems.append(f"提示词矩阵 {sid}：「业务优先级」没填（高 / 中 / 低）；范围外、没有合理需求依据、品牌做不到又没服务路径的处境不开行，从矩阵里删掉、记进题库 notes")
            continue
        if not first(r, "业务优先级依据", "业务重要性依据", "优先级依据").strip():
            problems.append(f"提示词矩阵 {sid}：{tier} 没写「业务优先级依据」（这个需求对哪项业务目标起什么作用）")
        stage = text(r.get("旅程阶段"))
        if ("业务优先级" in r or "业务重要性" in r) and stage and stage not in STAGES:
            problems.append(f"提示词矩阵 {sid}：旅程阶段「{stage}」不是需求认知 / 方案考虑 / 购买决策（2026-11-02 起三段）")
        carried = on_row.get(r.get("record_id"), [])
        if carried and not ids(r.get("主题")):
            problems.append(f"提示词矩阵 {sid}：挂了题但没挂「主题」")
        # 低档行默认不出题（2026-11-05）：没挂题的要在依据末尾写「本期不出：业务优先级低，原因……」；为补高、中覆盖挂了题的不报
        if ("业务优先级" in r or "业务重要性" in r) and TIER[tier] == 2 and not carried and "本期不出" not in first(r, "业务优先级依据", "业务重要性依据"):
            problems.append(f"提示词矩阵 {sid}：业务优先级为低，依据末尾要写「本期不出：业务优先级低，原因……」")
        if (("业务优先级" in r or "业务重要性" in r) and stage in ("需求认知", "购买决策") and TIER[tier] < 2 and not carried
                and "本期不出" not in first(r, "业务优先级依据", "业务重要性依据")):
            problems.append(f"提示词矩阵 {sid}：{stage}行本期没出题，业务优先级依据末尾要写「本期不出：……」说明原因")
        # 本期不出的理由不能是试跑读数：品牌读数不进选题（Hbrand 2026-11-04 M-024、M-025）
        reason = first(r, "业务优先级依据", "业务重要性依据").split("本期不出", 1)
        if len(reason) == 2 and re.search(r"\d+\s*/\s*\d+|\d+\s*次|0 次|没提到|未提及", reason[1]):
            problems.append(f"提示词矩阵 {sid}：「本期不出」的理由写了试跑读数；品牌读数不进选题，改写题或重判这一行")
        # 行上的提示词类型（2026-11-03 起；2026-11-04 前字段叫「可出题型」）：有这个字段才查，没有的是旧 Base 不迁移
        type_field = next((k for k in ("提示词类型", "可出题型") if k in r), None)
        if type_field:
            basis_field = f"{type_field}依据"
            registered = {t for t in text(r.get(type_field)).split("/") if t}
            basis = text(r.get(basis_field))
            ceiling = STAGE_TYPES.get(stage, set())
            for rtype in sorted(registered - ceiling):
                problems.append(f"提示词矩阵 {sid}：{stage}行登记了「{rtype}」，超出该阶段允许的类型"
                                f"（{('、'.join(sorted(ceiling)) or '无')}）；核对证据该开哪一行，不放宽映射")
            for rtype in sorted(registered & ceiling):
                if (stage, rtype) not in DEFAULT_TYPES and f"{rtype}：" not in basis and f"{rtype}:" not in basis:
                    problems.append(f"提示词矩阵 {sid}：登记了「{rtype}」但「{basis_field}」里没有"
                                    f"「{rtype}：依据」一行（买家证据或「假设：……」）")
            for pid, ptype in type_on_row.get(r.get("record_id"), []):
                if ptype and ptype != "验证" and ptype in {t for s in STAGE_TYPES.values() for t in s} and ptype not in registered:
                    problems.append(f"提示词矩阵 {sid}：挂了{ptype}题 {pid}，但「{type_field}」没登记{ptype}")
    # 同一受众、同一购买任务只开一行（2026-11-04；2026-11-05 起字段叫购买任务，旧名场景、购买场景照认）
    seen = {}
    for r in rows:
        key = (text(r.get("购买任务")) or text(r.get("场景")) or text(r.get("购买场景")), text(r.get("受众")), "/".join(sorted(t for t in text(r.get("买方约束")).split("/") if t)))
        if key[0] and key[2]:
            seen.setdefault(key, []).append(text(r.get("切片编号")) or r.get("record_id"))
    for (scene, _, cons), sids in seen.items():
        if len(sids) > 1:
            problems.append(f"提示词矩阵 {'、'.join(sids)}：受众、购买任务「{scene}」、买方约束「{cons}」完全相同；同一任务只开一行，放在一个旅程阶段")
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
        status = text(r.get("状态"))
        if not status:
            problems.append(f"{label}没填「状态」")
        if "主题优先级" in r or "优先级" in r:  # 2026-11-01 起主题排优先级，11-02 改名「主题优先级」
            level = first(r, "主题优先级", "优先级")
            if level not in ("高", "中", "低"):
                problems.append(f"{label}「主题优先级」没填（高 / 中 / 低）")
            elif not first(r, "主题优先级依据", "优先级依据").strip():
                problems.append(f"{label}主题优先级 {level} 没写「主题优先级依据」")
    return problems


def check_prompts_v2(rows, matrix, pool_rows=()):
    problems = []
    stopped = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("状态")) == "停测"]
    if stopped:
        problems.append(f"提示词库还留着 {len(stopped)} 条停测题（应删除，题号和原因记在题库 config.retired）：{', '.join(stopped[:8])}")
    ca = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("提示词类型")) == "品类认知"]
    if ca:
        problems.append(f"提示词库有 {len(ca)} 道品类认知题：品类认知只在梳理属性池前预跑，不进提示词库（2026-10-29）：{', '.join(ca[:8])}")
    for r in rows:
        code = text(r.get("编号")) or text(r.get("提示词"))[:20]
        if text(r.get("提示词类型")) == "验证":
            problems.append(f"提示词库「{code}」为临时验证，须保存到独立诊断记录")
        reason = text(r.get("出题原因"))
        if not reason.strip():
            problems.append(f"提示词库「{code}」没有出题原因")
        manual = first(r, "提示词优先级", "优先级")
        if not manual:
            problems.append(f"提示词库「{code}」「提示词优先级」是空的（应按所属切片预填）")
            continue
        sl = next((matrix[i] for i in ids(r.get("所属切片")) if i in matrix), None)
        if sl is None:
            problems.append(f"提示词库「{code}」没有所属切片")
            continue
        tier = first(sl, "业务优先级", "业务重要性", "优先级")
        if tier not in TIER:
            continue
        default = tier
        if manual != default:
            m = re.search(r"改档[：:](.+)", reason, re.S)
            if not m or f"定为 {manual}" not in m.group(1):
                problems.append(f"提示词库「{code}」：提示词优先级为 {manual}，按规则是 {default}"
                                f"（切片 {tier}），出题原因里没有写「改档：理由，定为 {manual}」")
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


def buyer_constraints(r, pool_names=None):
    """一行的买方约束：2026-11-04 起是选项字段「买方约束」；更早的 Base 是链接属性池的「属性关联」「属性」。"""
    if "买方约束" in r:
        return {x for x in text(r.get("买方约束")).split("/") if x}
    for k in ("属性关联", "属性"):
        if k in r:
            return {(pool_names or {}).get(i, i) for i in ids(r.get(k))}
    return set()


HYPOTHESIS_SOURCES = {"query fan-outs", "AI 追问", "模型建议问题",  # 模型生成、背后没有真实用户（2026-11-04）
                      "品牌官网", "竞品官网"}  # 品牌自己写的内容（2026-11-05）


def check_signals_v2(sig_rows, matrix_rows, pool_names=None):
    """需求信号（2026-11-04 起）：受众叫法和矩阵一致（问题）；每行矩阵、每类受众有几条信号支撑（提示，不算问题）。
    一行的支撑信号 = 受众和这一行有交集、买方约束也和这一行有交集；来源类型是 query fan-outs、AI 追问、模型建议问题、品牌官网、竞品官网的不算支撑
    （模型生成、背后没有真实用户，只开假设级候选），受众叫法照查。"""
    def auds(r):
        return {x for x in text(r.get("受众")).split("/") if x}
    m_auds = set().union(*[auds(m) for m in matrix_rows]) if matrix_rows else set()
    problems = [f"需求信号「{text(r.get('输入编号'))}」的受众「{a}」不在提示词矩阵的受众里（三处叫法要一致）"
                for r in sig_rows for a in sorted(auds(r) - m_auds) if m_auds]
    sigs = [(auds(r), buyer_constraints(r, pool_names)) for r in sig_rows
            if not HYPOTHESIS_SOURCES & set(text(r.get("来源类型")).split("/"))]
    notes = []
    zero_rows = [text(m.get("切片编号")) or "（无编号）" for m in matrix_rows
                 if not any(sa & auds(m) and sc & buyer_constraints(m, pool_names) for sa, sc in sigs)]
    if zero_rows:
        notes.append(f"{len(zero_rows)} 行矩阵没有信号支撑（只有假设，依据写在提示词类型依据或业务优先级依据）：{'、'.join(zero_rows)}")
    zero_auds = sorted(a for a in m_auds if not any(a in sa for sa, _ in sigs))
    if zero_auds:
        notes.append(f"这些受众没有信号：{'、'.join(zero_auds)}")
    on_rows = set().union(*[buyer_constraints(m, pool_names) for m in matrix_rows]) if matrix_rows else set()
    cnt = {}
    for _, sc in sigs:
        for c in sc - on_rows:
            cnt[c] = cnt.get(c, 0) + 1
    if cnt:
        top = sorted(cnt.items(), key=lambda kv: -kv[1])
        notes.append(f"{len(top)} 条买方约束有信号却没挂在任何矩阵行上：" + "、".join(f"{c} {n}" for c, n in top))
    return problems, notes


def check_constraint_options(base, tables):
    """三张表的「买方约束」选项是同一份名单（2026-11-04 起）。"""
    opts = {}
    for t in ("需求信号", "提示词矩阵", "提示词库"):
        if t not in tables:
            continue
        fl = (lark("base", "+field-list", "--base-token", base, "--table-id", tables[t]).get("data") or {}).get("fields") or []
        f = next((x for x in fl if x.get("name") == "买方约束"), None)
        if f is not None:
            opts[t] = {o.get("name") for o in f.get("options") or []}
    problems = []
    if "提示词矩阵" in opts:
        for t, o in opts.items():
            for name in sorted(o - opts["提示词矩阵"]):
                problems.append(f"{t}「买方约束」有选项「{name}」，提示词矩阵里没有（三张表的选项要一致，改名、合并时一起改）")
            if t != "提示词矩阵":
                for name in sorted(opts["提示词矩阵"] - o):
                    problems.append(f"提示词矩阵「买方约束」有选项「{name}」，{t}里没有（三张表的选项要一致）")
    return problems


def field_names(base, tables):
    out = {}
    for name, tid in tables.items():
        fields = lark("base", "+field-list", "--base-token", base, "--table-id", tid)
        out[name] = [f.get("name", "") for f in (fields.get("data") or {}).get("fields") or []]
    return out


def check_fields_v2(fields):
    problems = []
    for table, retired in RETIRED_FIELDS_V2.items():
        for f in fields.get(table, []):
            if f in retired:
                problems.append(f"{table} 还有字段「{f}」：已移除（2026-10-28 / 11-01，见 client-facing-attribute-pool.md）")
    return problems


def table_ids(base):
    listing = lark("base", "+base-block-list", "--base-token", base)
    return {b["name"]: b["id"] for b in (listing.get("data") or {}).get("blocks") or [] if b.get("type") == "table"}


def check_terms(base, template=False, v2=False):
    problems = []
    terms = dict(RETIRED_TERMS, **(RETIRED_TERMS_V2 if v2 else {}))
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
    # 2026-10-26 前的旧矩阵也有「优先级」，按依据字段认；11-02 起叫「业务重要性依据」
    v2 = bool({"业务优先级依据", "业务重要性依据", "优先级依据"} & set(fields.get("提示词矩阵", [])))
    # 2026-11-04 起没有属性池（买方约束是三张表的选项字段）；旧 Base 有就照查
    pool_rows = records(a.base, "属性池") if "属性池" in tables else []
    prompt_rows = records(a.base, "提示词库")
    pool_names = {p["record_id"]: text(p.get("属性")) for p in pool_rows}
    if v2:
        matrix_rows = records(a.base, "提示词矩阵")
        matrix = {r["record_id"]: r for r in matrix_rows}
        topic_rows = records(a.base, "主题") if "主题" in tables else []
        problems = check_fields_v2(fields) + check_pool_v2(pool_rows) + check_constraint_options(a.base, tables)
        if a.template:
            problems += [f"{t} 缺字段「{n}」（2026-11-02 起的新名，旧名「{n.replace('业务优先级', '优先级').replace('主题优先级', '优先级').replace('提示词优先级', '优先级')}」要改名）"
                         for t, names in NEW_NAMES.items() for n in names if n not in fields.get(t, [])]
        notes = []
        if not a.template:
            problems += (check_matrix_v2(matrix_rows, prompt_rows, pool_rows) + check_topics_v2(topic_rows, matrix_rows, prompt_rows)
                         + check_prompts_v2(prompt_rows, matrix, pool_rows))
            if "需求信号" in tables and {"买方约束", "属性关联"} & set(fields.get("需求信号", [])):
                sig_problems, notes = check_signals_v2(records(a.base, "需求信号"), matrix_rows, pool_names)
                problems += sig_problems
        if "主题" not in tables:
            problems.append("没有「主题」表")
    else:
        problems = check_pool(pool_rows) + check_prompts(prompt_rows)
    problems += check_terms(a.base, a.template, v2)
    print(("新结构（2026-10-28 起）" if v2 else "旧结构（2026-10-27 及以前，按旧规则查）"))
    for p in problems:
        print("问题：" + p)
    for n in (notes if v2 else []):
        print("提示：" + n)
    print(f"共 {len(problems)} 个问题" if problems else "通过")
    if a.json:
        Path(a.json).write_text(json.dumps(problems, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
