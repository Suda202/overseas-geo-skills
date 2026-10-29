#!/usr/bin/env python3
"""选词 skill 家族的退役说法扫描（Suda 2026-10-27）。只读，不改文件。

每次改口径后跑一遍，扫出 0 条才算改完。扫 SKILL.md 与 references/*.md，
覆盖选词、监测两个 skill 和 shared/canonical-intent-mapping.md。

一行里同时出现「历史标记」（退役、改名、取消、before 2026… 这类交代来历的词）
时不算命中：规则里保留旧名是为了说明沿革，不是在用旧口径。

用法：python3 -I check_skill_terms.py [--json out.json]
退出码：0 无命中；1 有命中。
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
TARGETS = [
    SKILLS / "geo-prompt-selection-builder" / "SKILL.md",
    *sorted((SKILLS / "geo-prompt-selection-builder" / "references").glob("*.md")),
    SKILLS / "geo-monitoring" / "SKILL.md",
    *sorted((SKILLS / "geo-monitoring" / "references").glob("*.md")),
    SKILLS / "shared" / "canonical-intent-mapping.md",
]

# 退役说法 → 现在的说法
RETIRED = [
    (r"候选基线|candidate baseline", "试跑（每平台 3 次）与正式基线（每格 30 次）"),
    (r"Every table in it carries a 客户确认", "Base 里直接改单元格，只有文档版带客户确认列"),
    (r"P1 = decides", "优先级只在提示词矩阵行上判：业务重点 × 买家证据强弱"),
    (r"ChatGPT quality trial", "各监测平台的质量试跑"),
    (r"用来分配题量|decides how many Prompts", "受众是否重点进矩阵行优先级的业务重点"),
    (r"context columns|information columns", "试跑读数放单独的试跑报告"),
    (r"enforced by structure", "防选择偏差靠推荐顺序不读试跑读数"),
    (r"formal set must carry", "验证题是正式基线后的诊断题，不占名额"),
    (r"Accuracy Prompts (are trialled|go through the same trial)|alongside Competitor and Accuracy", "准确性题不进试跑"),
    (r"brand-named Evaluation and Verification", "只写点名评价题，不写点名验证题"),
    (r"Four Stages", "The Stage Chain（六段）"),
    (r"of the 5 runs", "按实际次数写"),
    (r"P1 Attributes land|P1/P2 landing|from the P1 landings|重要性 高 Attributes? (with|land)|where the 重要性 高", "主题从矩阵的 P1、P2 行聚出（2026-10-28）"),
    (r"属性池 优先级|attribute tier|重要性 × 可改变性|importance × changeability", "属性池不出档位；优先级只在提示词矩阵行上判（2026-10-28）"),
    (r"建议优先级", "提示词库只有一列可编辑的优先级，脚本按矩阵行预填（2026-10-28）"),
    (r"信源壁垒|来源追不上 drop|来源追不上 barrier", "提示词库「可改变性」，按引用前 20 域名判（2026-10-28）"),
    (r"判断冲突", "属性池只判相对竞品，无判断冲突公式（2026-10-28）"),
    (r"「品类基线」|品类基线：|category-baseline row", "不带条件的品类题挂在属性为空的矩阵行（2026-10-28）"),
    (r"买家角色 row|买家角色 行|买家角色行", "受众是否重点只写在业务范围主要受众（优先）（2026-10-28）"),
    (r"category observation Topic|Depth (\(细分\) )?Topics?|Coverage (\(宽泛\) )?Topics?|Coverage and Depth", "主题不分类型（2026-10-28）"),
    (r"Default wording per prompt type|one opening for Discovery|one sentence form|the sentence form is fixed|默认句式", "提示词不限句式和开头，只看该类型题面必须做到什么（2026-10-29）"),
    (r"Default to the report wording", "评价题默认买家问法，Evaluate 命令式只作诊断（2026-10-29）"),
    (r"broad anchor Prompts|low-condition anchor|Every Topic keeps a broad|each candidate Topic has at least one natural no-qualifier", "不写宽泛品类题，品牌方点名大词才写（2026-10-29）"),
    (r"人群只判重要性", "受众是否重点进矩阵行优先级（2026-10-28）"),
    (r"领先 / 持平 / 劣势|领先 or 持平|领先 before 持平|领先 rows|领先 goes before", "相对竞品取值用 优势 / 持平 / 劣势 / 待确认"),
    (r"What is \[category\] and what should buyers consider", "What should I look for when choosing [category] for [condition]?"),
    (r"「竞品对比」|竞品对比题|点名品牌的竞品对比|类型[^。]{0,6}竞品对比", "提示词类型标签「对比」"),
    (r"购买影响", "属性池的「重要性」"),
    (r"必须给", "优先提供 / 有就提供"),
]
HISTORY = re.compile(
    r"retired|retiring|退役|取消|superseding|superseded|replac|renamed|改名|简化|formerly|former|"
    r"\bwas\b|before 20\d\d|pre-20\d\d|原「|原名|旧|never|removed|已删|删除|不再|legacy|old flow|"
    r"was called|called .+ before|reversing|推翻|拆出|split out|不写|there is no|\d\d-\d\d 前|之前|以前"
)


def scan():
    hits = []
    for path in TARGETS:
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, now in RETIRED:
                m = re.search(pattern, line)
                if m and not HISTORY.search(line):
                    hits.append({"file": str(path.relative_to(SKILLS)), "line": n, "term": m.group(0), "now": now})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    hits = scan()
    for h in hits:
        print(f"{h['file']}:{h['line']}  「{h['term']}」 → {h['now']}")
    print(f"共 {len(hits)} 处退役说法" if hits else "通过：没有退役说法")
    if a.json:
        Path(a.json).write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
