#!/usr/bin/env python3
"""把题库算出的切片标签写进对客确认 Base 提示词库的「标签」（多选，2026-11-03）。

标签和上传 CSV 用同一套口径（tag_dimensions.py，规则见 selection-rules.md → 6「切片标签」）：
按题库 config.tag_dimensions 从矩阵行和属性池派生，不合格的值不出并打印原因。
Base 一行对应题库里编号相同的题；多市场合并成一行的题，各市场题库算出的标签取并集。

- 多选字段不会自动建选项：先把缺的选项补进字段（全量 PUT，保留已有选项），等几秒生效再写记录。
- 题库里有、Base 里没有的编号打印出来；Base 里有、题库里没有的行不动。
- 默认只预览；--write 写入并回读核对。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I write_tags.py --base <token> --bank <bank.json> [--bank <另一市场.json>] [--write]
退出码：0 正常；1 回读对不上；2 读不到 Base 或缺「标签」字段。
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # -I 不把脚本目录放进 sys.path
    sys.path.insert(0, str(HERE))
from tag_dimensions import tag_plan  # noqa: E402
from validate_after_sales_set import legacy_markers  # noqa: E402
from write_prompt_reasons import Lark, text  # noqa: E402

TABLE, FIELD = "提示词库", "标签"


def names(value):
    items = value if isinstance(value, list) else ([value] if value else [])
    return [str(x.get("name") or x.get("text") or "") if isinstance(x, dict) else str(x) for x in items]


def field_def(lark):
    out = lark._json("+field-get", "--table-id", TABLE, "--field-id", FIELD)
    field = (out.get("data") or {}).get("field")
    if not field or field.get("type") != "select" or not field.get("multiple"):
        print(f"{TABLE}没有多选字段「{FIELD}」：从模板复制的 Base 才有；旧 Base 不支持", file=sys.stderr)
        sys.exit(2)
    return field


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--base", required=True, help="对客确认 Base 的 token")
    ap.add_argument("--bank", action="append", required=True, type=Path, help="题库 JSON，多个市场可重复")
    ap.add_argument("--write", action="store_true", help="写回 Base 并回读核对")
    a = ap.parse_args()

    wanted = {}
    for path in a.bank:
        bank = json.loads(path.read_text(encoding="utf-8"))
        markers = legacy_markers(bank)
        if markers:
            print(f"{path.name} 是不支持的旧结构（{'; '.join(markers)}）：旧题库不迁移", file=sys.stderr)
            sys.exit(2)
        derived, problems, _ = tag_plan(bank.get("config") or {}, bank["questions"])
        for p in problems:
            print(f"{path.name} 标签没出：{p}")
        for q in bank["questions"]:
            code = str(q.get("question_id") or "").strip()
            if code and id(q) in derived:
                wanted.setdefault(code, [])
                wanted[code] += [t for t in derived[id(q)] if t not in wanted[code]]

    lark = Lark(a.base)
    field = field_def(lark)
    rows = {text(r.get("编号")).strip(): r for r in lark.records(TABLE) if text(r.get("编号")).strip()}
    missing = sorted(set(wanted) - set(rows))
    if missing:
        print(f"Base 里没有这些编号（没写）：{', '.join(missing[:10])}{' …' if len(missing) > 10 else ''}")
    upd = {rows[c]["record_id"]: {FIELD: tags} for c, tags in wanted.items()
           if c in rows and names(rows[c].get(FIELD)) != tags}
    counts = {}
    for tags in wanted.values():
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    print(f"题库 {len(wanted)} 道；标签 {counts or '无'}；要改 {len(upd)} 行")
    if not a.write or not upd:
        return

    have = [o.get("name") for o in field.get("options") or []]
    new = [t for t in counts if t not in have]
    if new:
        body = {k: field[k] for k in ("name", "type", "multiple", "description") if k in field}
        body["options"] = [{"name": n} for n in have + new]
        lark._json("+field-update", "--table-id", TABLE, "--field-id", FIELD, "--yes", js=body)
        print(f"补了选项：{'、'.join(new)}")
        time.sleep(5)  # 新选项要几秒才能按名字写入
    lark.update(TABLE, upd)
    for _ in range(4):  # 刚写入要等几秒才读得回来
        time.sleep(5)
        back = {r["record_id"]: r for r in lark.records(TABLE)}
        ok = sum(1 for rid, f in upd.items() if names(back.get(rid, {}).get(FIELD)) == f[FIELD])
        if ok == len(upd):
            break
    print(f"写入并回读一致 {ok} / {len(upd)}")
    sys.exit(0 if ok == len(upd) else 1)


if __name__ == "__main__":
    main()
