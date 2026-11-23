"""把翻译好的检索词中文写回 report-data.json 的 `meta.fanout_zh`。

用法：
    python3 attach_fanout_translations.py --report report-data.json \
        --batches <输出>/fanout-translations --out report-data.json

批次文件为 `fanout-batch-NN-zh.json`，格式 {"<编号>": "<中文>"}；编号与
`export_fanout_translations.py` 一致（检索词在报告里第一次出现的顺序）。
缺译文的检索词照常显示原文，不阻断出报告；加 --strict 时缺一条就报错。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="回填 Query Fan-outs 检索词中文")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strict", action="store_true", help="有检索词缺译文时报错")
    return parser.parse_args(argv)


def collect_queries(report: dict) -> list[str]:
    seen: dict[str, None] = {}
    for entry in (report.get("details") or {}).values():
        for query in entry.get("fanout") or []:
            text = str(query).strip()
            if text and text not in seen:
                seen[text] = None
    return list(seen)


def main() -> int:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    queries = collect_queries(report)
    numbered = {str(index): query for index, query in enumerate(queries, 1)}

    translated: dict[str, str] = {}
    for path in sorted(args.batches.glob("fanout-batch-*-zh.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"{path.name} 应为 {{\"<编号>\": \"<中文>\"}} 映射")
        for key, value in payload.items():
            text = str(value).strip()
            if text:
                translated[str(key)] = text

    unknown = [key for key in translated if key not in numbered]
    if unknown:
        raise SystemExit(f"译文里有 {len(unknown)} 个编号不在报告里，例如 {unknown[:3]}")
    missing = [key for key in numbered if key not in translated]
    if missing:
        print(f"⚠ {len(missing)} 条检索词没有译文，报告里照常显示原文，例如 "
              f"{[numbered[key] for key in missing[:3]]}")
        if args.strict:
            raise SystemExit("有检索词缺译文（--strict）")

    fanout_zh = {numbered[key]: text for key, text in translated.items()}
    report.setdefault("meta", {})["fanout_zh"] = fanout_zh
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"回填 {len(fanout_zh)}/{len(queries)} 条检索词中文 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
