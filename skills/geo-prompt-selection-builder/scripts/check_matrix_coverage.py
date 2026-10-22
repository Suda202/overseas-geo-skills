#!/usr/bin/env python3
"""Top-down matrix coverage audit: list empty 受众 × 旅程阶段 (× 产品线) cells.

The matrix is enumerated top-down (Suda 2026-10-22, after Aleyda's step-5
matrix): the full grid is written out from the business scope first, signal
collection fills it, and every cell still empty when the matrix settles is
closed with an explicit reason in the internal handoff. This script lists the
empty cells so none can go missing silently. It does not judge whether an
empty cell is a gap — that stays a human call written next to each cell.

Input: a client-Base spec JSON ({表名: [行]}, as the generation script writes
it) or a staged bank JSON (reads each question's audience / journey_stage /
product line). The audience and product-line universes default to the values
observed in the matrix; pass --audience / --line to add expected values the
matrix never reached (e.g. 业务范围 lists an audience with no slice at all).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGES = ("发现", "解决问题", "评估", "对比", "替代方案", "验证", "交易", "购后支持")
NO_LINE = "（未分产品线）"


def as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def rows_from_spec(spec: dict) -> list[dict]:
    rows = []
    for row in spec.get("提示词矩阵") or []:
        rows.append({
            "key": str(row.get("切片编号") or row.get("_key") or ""),
            "audiences": as_list(row.get("受众")),
            "stages": as_list(row.get("旅程阶段")),
            "lines": as_list(row.get("产品线")) or [NO_LINE],
        })
    return rows


def rows_from_bank(bank: dict) -> list[dict]:
    rows = []
    for row in bank.get("questions") or []:
        stage = str(row.get("journey_stage") or row.get("journey_stage_9") or row.get("journey") or "").strip()
        rows.append({
            "key": str(row.get("question_id") or ""),
            "audiences": as_list(row.get("audience") or row.get("persona") or row.get("buyer")),
            "stages": [stage] if stage else [],
            "lines": as_list(row.get("product_line")) or [NO_LINE],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="base spec JSON ({表名: [行]}) or staged bank JSON")
    parser.add_argument("--audience", action="append", default=[],
                        help="expected audience absent from the matrix (repeatable)")
    parser.add_argument("--line", action="append", default=[],
                        help="expected product line absent from the matrix (repeatable)")
    args = parser.parse_args()

    data = json.loads(args.source.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "提示词矩阵" in data:
        rows, kind = rows_from_spec(data), "base spec"
    elif isinstance(data, dict) and "questions" in data:
        rows, kind = rows_from_bank(data), "bank"
    else:
        print("ERROR: source is neither a base spec ({表名: [行]}) nor a bank ({questions: [...]})")
        return 2
    if not rows:
        print(f"ERROR: no matrix rows found in the {kind}")
        return 2

    audiences = sorted({a for row in rows for a in row["audiences"]} | {a.strip() for a in args.audience if a.strip()})
    lines = sorted({l for row in rows for l in row["lines"]} | {l.strip() for l in args.line if l.strip()})
    filled: dict[tuple[str, str, str], int] = {}
    unknown_stage: list[str] = []
    for row in rows:
        if any(stage not in STAGES for stage in row["stages"]):
            unknown_stage.append(row["key"])
        for line in row["lines"]:
            for audience in row["audiences"]:
                for stage in row["stages"]:
                    filled[(line, audience, stage)] = filled.get((line, audience, stage), 0) + 1

    total = len(lines) * len(audiences) * len(STAGES)
    empty = [(line, audience, stage)
             for line in lines for audience in audiences for stage in STAGES
             if (line, audience, stage) not in filled]

    print(f"来源：{kind}，矩阵行 {len(rows)}；格子 = 产品线({len(lines)}) × 受众({len(audiences)}) × 旅程阶段(8) = {total}，"
          f"已覆盖 {total - len(empty)}，空 {len(empty)}")
    if unknown_stage:
        print(f"WARNING: {len(unknown_stage)} 行的旅程阶段不在八段里（{', '.join(unknown_stage[:6])}"
              f"{' …' if len(unknown_stage) > 6 else ''}），这些行未计入格子")
    if not empty:
        print("无空格子。")
        return 0
    print("\n空格子（逐格写一行原因进内部交接件：无买家证据 / 超出范围 / 留到后续周期）：\n")
    print("| 产品线 | 受众 | 空的旅程阶段 |")
    print("|---|---|---|")
    by_pair: dict[tuple[str, str], list[str]] = {}
    for line, audience, stage in empty:
        by_pair.setdefault((line, audience), []).append(stage)
    for (line, audience), stages in sorted(by_pair.items()):
        ordered = [s for s in STAGES if s in stages]
        print(f"| {line} | {audience} | {'、'.join(ordered)} |")
    return 1


if __name__ == "__main__":
    sys.exit(main())
