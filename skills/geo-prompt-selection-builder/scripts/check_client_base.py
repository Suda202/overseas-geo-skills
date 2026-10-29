#!/usr/bin/env python3
"""对客确认 Base 发出前的检查（Suda 2026-10-23；2026-10-28 改为两种结构）。只读，不改表。

先按表结构认新旧：提示词矩阵有「优先级依据」字段的是新结构（2026-10-28 起），否则是旧结构
（旧客户 Base 不迁移，照旧规则查）。

新结构查：
  1. 属性池：填了「相对竞品」的行，判据里有「相对竞品（值）：…」一行；
     不该再有「重要性」「可改变性」「优先级」「判断冲突」字段。
  2. 提示词矩阵：每行有「优先级」（P1/P2/P3）和「优先级依据」；P1 行挂了「主题」；不挂劣势属性；
     P3 行不配题（目标题数留空、没有挂题）；不该再有「约束」「可改变性」「候选主题」字段。
  3. 主题表：候选主题题数不少于 5，已采购主题不超过 10，「状态」不空；
     主题里没有 P1 行的，依据与说明要写明是业务目标或核心可见度问题点名的。
  4. 提示词库：没有停测行；每道题有出题原因、优先级；默认档位 = 所属切片的优先级，
     「可改变性」为低再降一档；和默认不一致的，出题原因里有「改档：理由，定为 Px」；
     不该再有「建议优先级」「信源壁垒」字段；不该有品类认知题（只在属性池前预跑）。
  5. 使用说明和各表字段名里没有已退役的说法。

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
    "属性池": ("重要性", "可改变性", "优先级", "判断冲突"),
    "提示词矩阵": ("约束", "可改变性", "候选主题"),
    "提示词库": ("建议优先级", "信源壁垒"),
    "主题": ("来源属性",),
}
DROP = {"P1": "P2", "P2": "P3", "P3": "P3"}
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


def check_matrix_v2(rows, prompt_rows, pool_rows=()):
    problems = []
    weak = {r.get("record_id"): text(r.get("属性")) for r in pool_rows if text(r.get("相对竞品")) == "劣势"}
    on_row = {}
    for p in prompt_rows:
        for i in ids(p.get("所属切片")):
            on_row.setdefault(i, []).append(text(p.get("编号")))
    for r in rows:
        sid = text(r.get("切片编号")) or r.get("record_id")
        tier = text(r.get("优先级"))
        if tier not in ("P1", "P2", "P3"):
            problems.append(f"提示词矩阵 {sid}：「优先级」没填（P1/P2/P3）")
            continue
        if not text(r.get("优先级依据")).strip():
            problems.append(f"提示词矩阵 {sid}：{tier} 没写「优先级依据」（业务重点、买家证据强弱各怎么判的）")
        listed_weak = [weak[i] for i in ids(r.get("属性关联")) if i in weak]
        if listed_weak:
            problems.append(f"提示词矩阵 {sid}：挂了相对竞品为劣势的属性（{'、'.join(listed_weak)}），劣势不挂")
        if tier == "P1" and not ids(r.get("主题")):
            problems.append(f"提示词矩阵 {sid}：P1 行没挂「主题」")
        if tier == "P3" and (text(r.get("目标题数")) or on_row.get(r.get("record_id"))):
            problems.append(f"提示词矩阵 {sid}：P3 行本期不配题，目标题数应留空、不挂题"
                            f"（挂了：{', '.join(on_row.get(r.get('record_id'), [])[:5])}）")
    return problems


def check_topics_v2(trows, matrix_rows, prompt_rows):
    problems = []
    p1_topics = {i for r in matrix_rows if text(r.get("优先级")) == "P1" for i in ids(r.get("主题"))}
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
        if status == "候选" and n < 5:
            problems.append(f"{label}是候选主题，提示词库只有 {n} 道题，少于 5 道")
        if status == "已采购" and n > 10:
            problems.append(f"{label}已采购，提示词库有 {n} 道题，超过 10 道")
        note = text(r.get("依据与说明"))
        if r.get("record_id") not in p1_topics and not re.search("业务目标|核心可见度问题|营销活动", note):
            problems.append(f"{label}下没有 P1 行；只有业务目标、核心可见度问题或营销活动点名时才保留，并在依据与说明里写明")
    return problems


def check_prompts_v2(rows, matrix):
    problems = []
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
        manual = text(r.get("优先级"))
        if not manual:
            problems.append(f"提示词库「{code}」「优先级」是空的（应按所属切片预填）")
            continue
        sl = next((matrix[i] for i in ids(r.get("所属切片")) if i in matrix), None)
        if sl is None:
            problems.append(f"提示词库「{code}」没有所属切片")
            continue
        tier = text(sl.get("优先级"))
        if tier == "P3":
            problems.append(f"提示词库「{code}」挂在 P3 切片 {text(sl.get('切片编号'))} 上，P3 本期不配题")
            continue
        if tier not in ("P1", "P2"):
            continue
        default = DROP[tier] if text(r.get("可改变性")) == "低" else tier
        if manual != default:
            m = re.search(r"改档[：:](.+)", reason, re.S)
            if not m or f"定为 {manual}" not in m.group(1):
                problems.append(f"提示词库「{code}」：优先级为 {manual}，按规则是 {default}"
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
                problems.append(f"{table} 还有字段「{f}」：2026-10-28 起已移除（见 client-facing-attribute-pool.md）")
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
    v2 = "优先级依据" in fields.get("提示词矩阵", [])  # 2026-10-26 前的旧矩阵也有「优先级」，按新字段认
    pool_rows, prompt_rows = records(a.base, "属性池"), records(a.base, "提示词库")
    if v2:
        matrix_rows = records(a.base, "提示词矩阵")
        matrix = {r["record_id"]: r for r in matrix_rows}
        topic_rows = records(a.base, "主题") if "主题" in tables else []
        problems = check_fields_v2(fields) + check_pool_v2(pool_rows)
        if not a.template:
            problems += (check_matrix_v2(matrix_rows, prompt_rows, pool_rows) + check_topics_v2(topic_rows, matrix_rows, prompt_rows)
                         + check_prompts_v2(prompt_rows, matrix))
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
