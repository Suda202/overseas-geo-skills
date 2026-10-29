#!/usr/bin/env python3
"""售前生词题库的专属检查（Suda 2026-10-29）。

选词 validator（validate_after_sales_set.py）管写题的通用规则；售前比售后候选阶段多几条硬要求，
放进选词 validator 会误伤售后题库，所以单独在这里查。售前题库要两边都退出码 0。

    python3 -I check_presales_bank.py <bank.json>

报错（退出码 1）：
  1. 题型只能是 Discovery / Competitor / Evaluation（替代题等研发加上独立 diagnosis_intent 再出）
  2. 发现型至少占一半（报告的可见度和引用只算发现题）
  3. 每个主题至少 5 道题；config.topics 里登记了却没有题的主题按 0 道算
  4. 对比题题面要点名至少一个冻结竞品（config.competitor_selection），报告只算这几个竞品
  5. config.attribute_plan 不能为空：矩阵行的属性要从这里来
退出码 2：文件读不了或不是题库。
每个市场不超过 60 道由导出脚本查，这里不重复。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ALLOWED_TYPES = ("Discovery", "Competitor", "Evaluation")
MIN_PER_TOPIC = 5
# 与 geo-prompt-selection-builder/scripts/export_upload_csv.py 一致：这些题不导出，也不计数
SKIP_STATUS = {"retired", "停测"}
SKIP_REVIEW = {"需修改", "needs_revision"}
# competitor_selection 里这些键下的字符串是来源说明，不是品牌名
NOT_NAMES = {"source_fields", "source_values", "notes", "evidence"}


def competitor_names(config: dict) -> list[str]:
    names: list[str] = [str(x) for x in config.get("competitors") or [] if isinstance(x, str)]

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, dict):
            if isinstance(node.get("name"), str):
                names.append(node["name"])
            for k, value in node.items():
                if isinstance(value, (list, dict)):
                    walk(value, k)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    if key not in NOT_NAMES:
                        names.append(item)
                else:
                    walk(item, key)

    walk(config.get("competitor_selection") or {})
    brand = str(config.get("brand_name") or "").strip().casefold()
    out = [n.strip() for n in names if n.strip() and n.strip().casefold() != brand]
    return list(dict.fromkeys(out))


def check(data: dict) -> list[str]:
    config = data.get("config") or {}
    questions = [q for q in data.get("questions") or [] if isinstance(q, dict)
                 and str(q.get("status") or "").strip() not in SKIP_STATUS
                 and str(q.get("review_status") or "").strip() not in SKIP_REVIEW]
    errors: list[str] = []
    if not questions:
        return ["题库没有题"]

    def ptype(q: dict) -> str:
        return str(q.get("prompt_type") or q.get("intent") or "").strip()

    wrong = [f"{q.get('question_id')}({ptype(q) or '空'})" for q in questions if ptype(q) not in ALLOWED_TYPES]
    if wrong:
        errors.append(f"售前只出 {'/'.join(ALLOWED_TYPES)}，这些题型不对（{len(wrong)}）：{', '.join(wrong)}")

    discovery = sum(1 for q in questions if ptype(q) == "Discovery")
    if discovery * 2 < len(questions):
        errors.append(f"发现型只有 {discovery}/{len(questions)} 道，不到一半；报告的可见度和引用只算发现题")

    counts = Counter(str(q.get("topic_id") or "").strip() for q in questions)
    for topic in config.get("topics") or []:
        if isinstance(topic, dict) and str(topic.get("topic_id") or "").strip():
            counts.setdefault(str(topic["topic_id"]).strip(), 0)
    short = {t or "（没写 topic_id）": n for t, n in counts.items() if n < MIN_PER_TOPIC}
    if short:
        errors.append(f"每个主题至少 {MIN_PER_TOPIC} 道题，这些不够：{short}；合并主题或补题")

    rivals = competitor_names(config)
    comp = [q for q in questions if ptype(q) == "Competitor"]
    if comp and not rivals:
        errors.append("有对比题，但 config.competitor_selection 里找不到竞品名")
    elif comp:
        lowered = [r.casefold() for r in rivals]
        stray = [str(q.get("question_id")) for q in comp
                 if not any(r in str(q.get("user_question") or "").casefold() for r in lowered)]
        if stray:
            errors.append(f"对比题没点名冻结竞品（{', '.join(rivals)}）：{', '.join(stray)}；竞品以 Case 为准，不换不加")

    plan = config.get("attribute_plan")
    if not isinstance(plan, list) or not plan:
        errors.append("config.attribute_plan 为空：先按第 4 步列属性并判相对竞品")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读不了题库：{exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        print("不是题库：缺 questions 列表", file=sys.stderr)
        return 2
    errors = check(data)
    for e in errors:
        print(f"ERROR: {e}")
    print(f"PRESALES: {'fail' if errors else 'pass'}（{len(errors)} 条错误）")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
