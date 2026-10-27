#!/usr/bin/env python3
"""对客确认 Base 发出前的检查（Suda 2026-10-23）。只读，不改表。

查三件事：
  1. 属性池每个已填的判断都有写明依据的一行（判据与证据里）：
       普通属性：重要性 / 可改变性 / 相对竞品 各一行，形如「重要性（高）：……」；
       买家角色（受众）行：只要重要性那一行。
     兼容 2026-10-23 前的写法：「买家关注度高：」算重要性，「内容能不能改变（中）：」算可改变性。
     行里写的档位必须和格子里的值一致，否则算没有依据。
     属性池的「优先级」（2026-10-26 起属性层的档位在这里，矩阵不再带优先级）：
     非买家角色行不能为空。
  2. 提示词库只留在测的题：状态为「停测」的行要删掉（题号和原因在题库 config.retired）；
     每道题都有「出题原因」；「优先级」（可手改）不空，和「建议优先级」不一致时出题原因里写了
     「改档：理由，定为 Px」。「建议优先级」由 write_prompt_reasons.py 按属性池档位+信源壁垒写入（2026-10-26 起不按人群压档）。
  3. 使用说明和各表字段名里没有已退役的说法；提示词矩阵不能再有「优先级」字段（2026-10-26 移除）。

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


def check_terms(base, template=False):
    problems = []
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
            for term, now in RETIRED_TERMS.items():
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
    problems = check_pool(records(a.base, "属性池")) + check_prompts(records(a.base, "提示词库")) + check_terms(a.base, a.template)
    for p in problems:
        print("问题：" + p)
    print(f"共 {len(problems)} 个问题" if problems else "通过")
    if a.json:
        Path(a.json).write_text(json.dumps(problems, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
