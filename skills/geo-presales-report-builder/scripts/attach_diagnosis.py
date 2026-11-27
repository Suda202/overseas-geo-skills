"""把分析师写的诊断内容接进 report-data.json 顶层 ``diagnosis`` 键。

诊断与行动的判断（主题优先级、冲突、缺的页面、行动清单）由分析师读报告后写成
diagnosis.json；本脚本只做接入，不改写内容，渲染层原样展示。缺字段照常写入，
由渲染层按空表处理，不在这里报错。

diagnosis.json 结构（字段都是可选的）：
    {"scope_note": "...",
     "module_insights": {"overview": {"headline": "...", "points": [...]}, ...},
     "topics": [{"topic", "priority", "status", "gap", "next"}],
     "conflicts": [{"item", "ai_says", "site_says", "impact", "fix"}],
     "missing_pages": [{"page", "for_topic", "evidence", "reference"}],
     "actions": [{"action", "owner", "priority", "topic", "measure"}]}

用法：
    python3 attach_diagnosis.py --report report-data.json --diagnosis diagnosis.json --out report-data.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="把诊断与行动写入 report-data.json")
    parser.add_argument("--report", type=Path, required=True, help="report-data.json 路径")
    parser.add_argument("--diagnosis", type=Path, required=True, help="分析师写的 diagnosis.json")
    parser.add_argument("--out", type=Path, required=True, help="输出路径（可与 --report 相同）")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    diagnosis = json.loads(args.diagnosis.read_text(encoding="utf-8"))
    report["diagnosis"] = diagnosis
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    topics = len((diagnosis.get("topics") or [])) if isinstance(diagnosis, dict) else 0
    conflicts = len((diagnosis.get("conflicts") or [])) if isinstance(diagnosis, dict) else 0
    pages = len((diagnosis.get("missing_pages") or [])) if isinstance(diagnosis, dict) else 0
    actions = len((diagnosis.get("actions") or [])) if isinstance(diagnosis, dict) else 0
    print(f"诊断接入：主题 {topics} / 冲突 {conflicts} / 缺页 {pages} / 行动 {actions} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
