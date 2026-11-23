"""导出 Query Fan-outs 检索词，供翻译后回填报告抽屉。

采集数据里 AI 自己生成的检索词是原语言（多为英文），抽屉里要同时给中文。
本脚本从 report-data.json 的 details 里按固定顺序取全部唯一检索词，编号后按批导出；
翻译后由 `attach_fanout_translations.py` 按同一编号回填到 `meta.fanout_zh`。
编号 = 检索词在报告里第一次出现的顺序，导出与回填各算一次，结果一致。

用法：
    python3 export_fanout_translations.py --report report-data.json \
        --batch-size 60 --out-dir <输出>/fanout-translations
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="导出待翻译的 Query Fan-outs 检索词")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--out-dir", type=Path, required=True)
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
    if not queries:
        print("report-data.json 里没有 fanout 检索词")
        return 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    numbered = {str(index): query for index, query in enumerate(queries, 1)}
    ids = list(numbered)
    batches = [ids[i:i + args.batch_size] for i in range(0, len(ids), args.batch_size)]
    for index, batch in enumerate(batches, 1):
        path = args.out_dir / f"fanout-batch-{index:02d}.json"
        payload = {key: numbered[key] for key in batch}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"待翻译 {len(queries)} 条检索词，拆成 {len(batches)} 批 -> {args.out_dir}")
    print('每批翻译后写成 fanout-batch-NN-zh.json，格式 {"<编号>": "<中文>"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
