#!/usr/bin/env python3
"""对客确认 Base 发出前的检查（Suda 2026-10-23；2026-10-28 改为两种结构）。只读，不改表。

先按表结构认新旧：提示词矩阵有「业务重要性依据」（2026-11-02 前叫「优先级依据」）字段的是新结构
（2026-10-28 起），否则是旧结构（旧客户 Base 不迁移，照旧规则查）。三个优先级字段 2026-11-02 改名：
矩阵「业务重要性」、主题「主题优先级」、提示词库「提示词优先级」；旧名照认，--template 要求新名。

新结构查：
  1. 属性池：填了「相对竞品」的行，判据里有「相对竞品（值）：…」一行；
     不该再有「重要性」「可改变性」「优先级」「判断冲突」字段。
  2. 提示词矩阵：每行有「业务重要性」（高 / 中 / 低；旧 Base 的 P1 / P2 / P3 同序）和依据；
     挂了题的行有「主题」；低档行不挂题；劣势属性可以挂在行上；用新字段名的 Base，旅程阶段是
     需求认知 / 方案考虑 / 购买决策三段（2026-11-02）；对客表放完整矩阵，需求认知、购买决策行没挂题的
     是品牌方没选的目标，业务重要性依据里要写「本期不出：……」（2026-11-02）；业务重要性为低的行同样在
     依据里写「本期不出：业务重要性低，原因……」，不写在备注（2026-11-02 审核清单 D1）。
  3. 主题表：已采购主题不超过 10 道题，「状态」不空；有「主题优先级」列时（2026-11-01 起），
     它是高 / 中 / 低且依据不空。候选主题不设题数底线（2026-10-30）。
  4. 提示词库：没有停测行；每道题有出题原因、提示词优先级；默认档位 = 所属切片的业务重要性，
     「可改变性」为低再降一档；和默认不一致的，出题原因里有「改档：理由，定为 X」；
     不测劣势属性；不该有品类认知题（只在属性池前预跑）。
  5. 已移除的字段：属性池「重要性」「可改变性」「优先级」「判断冲突」「属性编号」，提示词矩阵「约束」
     「可改变性」「候选主题」「目标题数」「覆盖情况」，提示词库「建议优先级」「信源壁垒」「库分层」
     「看什么指标」「AI 认知差距」「优化顺序」，主题「来源属性」「计划题数」「可改变性低占比」。
  6. 使用说明和各表字段名里没有已退役的说法。

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
    "来源属性": "主题的属性从矩阵行的「属性关联」看",
}
RETIRED_FIELDS_V2 = {
    "属性池": ("重要性", "可改变性", "优先级", "判断冲突", "属性编号"),
    "提示词矩阵": ("约束", "可改变性", "候选主题", "目标题数", "覆盖情况"),
    "提示词库": ("建议优先级", "信源壁垒", "库分层", "看什么指标", "AI 认知差距", "优化顺序"),
    "主题": ("来源属性", "计划题数", "可改变性低占比"),
}
# 行档位：2026-11-01 起高 / 中 / 低；旧 Base 的 P1 / P2 / P3 同序
TIER = {"P1": 0, "高": 0, "P2": 1, "中": 1, "P3": 2, "低": 2}
STAGES = ("需求认知", "方案考虑", "购买决策")
# --template 要求的新字段名（2026-11-02）
NEW_NAMES = {"提示词矩阵": ("业务重要性", "业务重要性依据"), "主题": ("主题优先级", "主题优先级依据"),
             "提示词库": ("提示词优先级",)}
TIER_NAMES = (("P1", "P2", "P3"), ("高", "中", "低"))


def drop(tier):
    """可改变性低：降一档，用同一套档位名。"""
    names = next(n for n in TIER_NAMES if tier in n)
    return names[min(TIER[tier] + 1, 2)]
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
        evidence = text(r.get("判据与证据") if "判据与证据" in r else r.get("判据"))  # 字段名两种都认（Nbrand 10-26 改名为「判据」）
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
        evidence = text(r.get("判据与证据") if "判据与证据" in r else r.get("判据"))
        value = text(r.get("相对竞品"))
        if value and not has_basis(evidence, "相对竞品", value):
            problems.append(f"属性池「{name}」：相对竞品填了「{value}」，判据里没有写明依据的「相对竞品（{value}）：…」一行")
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
    for p in prompt_rows:
        for i in ids(p.get("所属切片")):
            on_row.setdefault(i, []).append(text(p.get("编号")))
    for r in rows:
        sid = text(r.get("切片编号")) or r.get("record_id")
        tier = first(r, "业务重要性", "优先级")
        if tier not in TIER:
            problems.append(f"提示词矩阵 {sid}：「业务重要性」没填（高 / 中 / 低）")
            continue
        if not first(r, "业务重要性依据", "优先级依据").strip():
            problems.append(f"提示词矩阵 {sid}：{tier} 没写「业务重要性依据」（这类受众在这个场景、阶段对业务多重要）")
        stage = text(r.get("旅程阶段"))
        if "业务重要性" in r and stage and stage not in STAGES:
            problems.append(f"提示词矩阵 {sid}：旅程阶段「{stage}」不是需求认知 / 方案考虑 / 购买决策（2026-11-02 起三段）")
        carried = on_row.get(r.get("record_id"), [])
        if carried and not ids(r.get("主题")):
            problems.append(f"提示词矩阵 {sid}：挂了题但没挂「主题」")
        if TIER[tier] == 2 and carried:
            problems.append(f"提示词矩阵 {sid}：低档行本期不出题（挂了：{', '.join(carried[:5])}）")
        # 低档行的原因也写在业务重要性依据末尾「本期不出：业务重要性低，原因……」，和没选目标的行同一个字段，
        # 一个筛选就能看到全部本期不出的行（Suda 2026-11-02 审核清单 D1）。只查新字段名的 Base。
        if "业务重要性" in r and TIER[tier] == 2 and "本期不出" not in first(r, "业务重要性依据"):
            problems.append(f"提示词矩阵 {sid}：业务重要性为低，依据末尾要写「本期不出：业务重要性低，原因……」")
        if ("业务重要性" in r and stage in ("需求认知", "购买决策") and TIER[tier] < 2 and not carried
                and "本期不出" not in first(r, "业务重要性依据")):
            problems.append(f"提示词矩阵 {sid}：{stage}行本期没出题，业务重要性依据末尾要写「本期不出：……」说明原因")
    return problems


def check_topics_v2(trows, matrix_rows, prompt_rows):
    problems = []
    counts = {}
    for p in prompt_rows:
        t = text(p.get("主题"))
        if t:
            counts[t] = counts.get(t, 0) + 1
    for r in trows:
        name = text(r.get("主题"))
        if not name:
            continue
        label = f"主题「{name}」（{text(r.get('市场')) or '未填市场'}）"
        status = text(r.get("状态"))
        n = counts.get(name, 0)
        if not status:
            problems.append(f"{label}没填「状态」")
        if status == "已采购" and n > 10:
            problems.append(f"{label}已采购，提示词库有 {n} 道题，超过 10 道")
        if "主题优先级" in r or "优先级" in r:  # 2026-11-01 起主题排优先级，11-02 改名「主题优先级」
            level = first(r, "主题优先级", "优先级")
            if level not in ("高", "中", "低"):
                problems.append(f"{label}「主题优先级」没填（高 / 中 / 低）")
            elif not first(r, "主题优先级依据", "优先级依据").strip():
                problems.append(f"{label}主题优先级 {level} 没写「主题优先级依据」")
    return problems


def check_prompts_v2(rows, matrix, pool_rows=()):
    problems = []
    weak = {r.get("record_id"): text(r.get("属性")) for r in pool_rows if text(r.get("相对竞品")) == "劣势"}
    stopped = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("状态")) == "停测"]
    if stopped:
        problems.append(f"提示词库还留着 {len(stopped)} 条停测题（应删除，题号和原因记在题库 config.retired）：{', '.join(stopped[:8])}")
    ca = [text(r.get("编号")) or text(r.get("提示词"))[:20] for r in rows if text(r.get("提示词类型")) == "品类认知"]
    if ca:
        problems.append(f"提示词库有 {len(ca)} 道品类认知题：品类认知只在梳理属性池前预跑，不进提示词库（2026-10-29）：{', '.join(ca[:8])}")
    for r in rows:
        code = text(r.get("编号")) or text(r.get("提示词"))[:20]
        reason = text(r.get("出题原因"))
        if not reason.strip():
            problems.append(f"提示词库「{code}」没有出题原因")
        tested_weak = [weak[i] for i in ids(r.get("属性")) if i in weak]
        if tested_weak:
            problems.append(f"提示词库「{code}」测的是劣势属性（{'、'.join(tested_weak)}），劣势属性写题时剔除")
        manual = first(r, "提示词优先级", "优先级")
        if not manual:
            problems.append(f"提示词库「{code}」「提示词优先级」是空的（应按所属切片预填）")
            continue
        sl = next((matrix[i] for i in ids(r.get("所属切片")) if i in matrix), None)
        if sl is None:
            problems.append(f"提示词库「{code}」没有所属切片")
            continue
        tier = first(sl, "业务重要性", "优先级")
        if tier not in TIER:
            continue
        if TIER[tier] == 2:
            problems.append(f"提示词库「{code}」挂在低档切片 {text(sl.get('切片编号'))} 上，低档本期不出题")
            continue
        default = drop(tier) if text(r.get("可改变性")) == "低" else tier
        if manual != default:
            m = re.search(r"改档[：:](.+)", reason, re.S)
            if not m or f"定为 {manual}" not in m.group(1):
                problems.append(f"提示词库「{code}」：提示词优先级为 {manual}，按规则是 {default}"
                                f"（切片 {tier}{'，可改变性低降一档' if default != tier else ''}），出题原因里没有写「改档：理由，定为 {manual}」")
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
    v2 = bool({"业务重要性依据", "优先级依据"} & set(fields.get("提示词矩阵", [])))
    pool_rows, prompt_rows = records(a.base, "属性池"), records(a.base, "提示词库")
    if v2:
        matrix_rows = records(a.base, "提示词矩阵")
        matrix = {r["record_id"]: r for r in matrix_rows}
        topic_rows = records(a.base, "主题") if "主题" in tables else []
        problems = check_fields_v2(fields) + check_pool_v2(pool_rows)
        if a.template:
            problems += [f"{t} 缺字段「{n}」（2026-11-02 起的新名，旧名「{n.replace('业务重要性', '优先级').replace('主题优先级', '优先级').replace('提示词优先级', '优先级')}」要改名）"
                         for t, names in NEW_NAMES.items() for n in names if n not in fields.get(t, [])]
        if not a.template:
            problems += (check_matrix_v2(matrix_rows, prompt_rows, pool_rows) + check_topics_v2(topic_rows, matrix_rows, prompt_rows)
                         + check_prompts_v2(prompt_rows, matrix, pool_rows))
        if "主题" not in tables:
            problems.append("没有「主题」表")
    else:
        problems = check_pool(pool_rows) + check_prompts(prompt_rows)
    problems += check_terms(a.base, a.template, v2)
    print(("新结构（2026-10-28 起）" if v2 else "旧结构（2026-10-27 及以前，按旧规则查）"))
    for p in problems:
        print("问题：" + p)
    print(f"共 {len(problems)} 个问题" if problems else "通过")
    if a.json:
        Path(a.json).write_text(json.dumps(problems, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
