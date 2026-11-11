#!/usr/bin/env python3
"""选词题库 JSON → 售前诊断上传 CSV（5 列：query,question_zh,topic,diagnosis_intent,tags）。

2026-11-11 起：删掉 question_types、purchase_intent、persona_name、scene_name 四列（研发要求先改 skill；
线上后端改为按意图类型决定统计什么，旧模板带这四列的照收、忽略）；替代题直接传 alternatives。

- 只认现行结构的题库：旧结构（validate_after_sales_set.legacy_markers 认出的）报「不支持的旧结构」，退出码 2，不导出。
- diagnosis_intent 用后端枚举：discovery、alternatives、competitor、evaluation。tags 写跨主题切片标签：按 config.tag_dimensions
  从矩阵行派生（口径在 tag_dimensions.py，落在不到 2 个主题、不到 5 道题、和主题重复的值不出，打印原因），
  不写 diagnosis_intent 已经表达的类型名。
  问题解决（Information）、验证（Trust）、交易（Transactional）、售后（Support）后端还没有枚举，不导出并打印题号。
- 每类统计什么以 shared/canonical-intent-mapping.md 和研发需求第 4 节的表为准，不在 CSV 里表达。
- 上传时市场在上传页另选，所以 CSV 不带市场；题库有几个 region 就出几份，每份一个市场。
- 主题名按 topic_id 去 config.topics 取；要换显示名时加 --topic-label。
- 不导出 status 为停测、需修改的题，打印题号。
- 写完用上传 CSV 检查（check_upload_rows）自检，不过就退出码 1。

用法：
    python3 -I export_upload_csv.py <题库.json> --out <目录> [--topic-label "<题库主题>=<显示名>"]
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HEADERS = ["query", "question_zh", "topic", "diagnosis_intent", "tags"]
INTENT = {"Discovery": "discovery", "Competitor": "competitor", "Alternatives": "alternatives",
          "Evaluation": "evaluation"}
TAGS_MAX = 200
SKIP_STATUS = {"停测", "需修改"}
# -I 不把脚本目录放进 sys.path，同目录的 tag_dimensions、validate_after_sales_set 要手动加
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from tag_dimensions import TYPE_ZH, tag_plan  # noqa: E402
from validate_after_sales_set import legacy_markers  # noqa: E402


def tags_cell(prompt_type, tags):
    """只写切片标签，不写 diagnosis_intent 已表达的类型名；超长就从后面丢，保证短于 200 字。"""
    out = [str(t).strip() for t in tags or [] if str(t).strip() and str(t).strip() not in TYPE_ZH.values()]
    while len(",".join(out)) >= TAGS_MAX and len(out) > 1:
        out.pop()
    return ",".join(out)


# 上传行检查（后端上传模板的约束；2026-11-06 从已退役的 geo-presales-prompt-builder 搬来）
UPLOAD_MAX_ROWS = 60
UPLOAD_INTENTS = {"discovery", "alternatives", "competitor", "evaluation"}
EVALUATION_META_TOPIC = re.compile(r"\btopic\b", re.IGNORECASE)


def _norm_query(value: str) -> str:
    """字母数字（任何文字）和组合符号保留，其余当分隔符；用来查重。"""
    kept = "".join(ch if ch.isalnum() or unicodedata.category(ch).startswith("M") else " " for ch in str(value).lower())
    return " ".join(kept.split())


def _parse_tags(value: object) -> list[str]:
    return [tag.strip() for tag in re.split(r"[，,;\n]+", str(value or "")) if tag.strip()]


def check_upload_rows(fieldnames: list[str] | None, rows: list[dict]) -> tuple[list[str], dict]:
    errors: list[str] = []
    if fieldnames != HEADERS:
        errors.append(f"CSV header must exactly equal {HEADERS}")
    if len(rows) > UPLOAD_MAX_ROWS:
        errors.append(f"CSV batch total must not exceed {UPLOAD_MAX_ROWS}")
    intents, topics, csv_tags, queries = Counter(), Counter(), Counter(), Counter()
    for index, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            errors.append(f"CSV row {index} must be an object")
            continue
        for field in ("query", "question_zh", "topic", "diagnosis_intent"):
            if not str(row.get(field) or "").strip():
                errors.append(f"CSV row {index} field {field!r} must be non-empty")
        query = str(row.get("query") or "").strip()
        if len(query) > 1000:
            errors.append(f"CSV row {index} query must not exceed 1000 characters")
        if len(str(row.get("question_zh") or "")) > 1000:
            errors.append(f"CSV row {index} question_zh must not exceed 1000 characters")
        if len(str(row.get("topic") or "")) > 255:
            errors.append(f"CSV row {index} topic must not exceed 255 characters")
        raw_tags = str(row.get("tags") or "").strip()
        if len(raw_tags) > TAGS_MAX:
            errors.append(f"CSV row {index} tags must not exceed {TAGS_MAX} characters")
        parsed = _parse_tags(raw_tags)
        if raw_tags and not parsed:
            errors.append(f"CSV row {index} tags must contain at least one non-empty tag")
        role = str(row.get("diagnosis_intent") or "").strip()
        if role not in UPLOAD_INTENTS:
            errors.append(f"CSV row {index} has unsupported diagnosis_intent {role!r}")
        if role == "evaluation" and EVALUATION_META_TOPIC.search(query):
            errors.append(f"CSV row {index} evaluation query must not contain the meta word 'topic'")
        intents[role] += 1
        topics[str(row.get("topic") or "").strip()] += 1
        queries[_norm_query(query)] += 1
        csv_tags.update(parsed)
    duplicates = sorted(q for q, n in queries.items() if q and n > 1)
    if duplicates:
        errors.append(f"CSV normalized query values must be unique {duplicates}")
    return errors, {"total": len(rows), "diagnosis_intent": dict(intents),
                    "topic": dict(topics), "tags": dict(csv_tags)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bank", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--topic-label", action="append", default=[],
                    help="题库主题名=上传用的中文主题名，可重复；不给就用题库里的主题名")
    a = ap.parse_args()
    labels = dict(x.split("=", 1) for x in a.topic_label)
    bank = json.loads(a.bank.read_text(encoding="utf-8"))
    markers = legacy_markers(bank)
    if markers:
        print(f"不支持的旧结构（{'; '.join(markers)}）：旧题库不迁移，不导出", file=sys.stderr)
        sys.exit(2)
    topic_names = {str(t.get("topic_id") or "").strip(): str(t.get("topic") or t.get("name") or "").strip()
                   for t in (bank.get("config") or {}).get("topics") or [] if isinstance(t, dict)}
    config = bank.get("config") or {}
    derived, tag_problems, _ = tag_plan(config, bank["questions"])
    # 60 条上限按市场 × 产品线算（Suda 2026-11-09）：产品线从题所在矩阵行读
    slice_line = {str(r.get("slice_id") or "").strip(): str(r.get("product_line") or "").strip()
                  for r in config.get("slices") or [] if isinstance(r, dict)}
    bank_line = str(bank.get("product_line") or "").strip()
    by_region, skipped, held = {}, [], []
    for q in bank["questions"]:
        status = str(q.get("status") or "").strip()
        if status in SKIP_STATUS:
            held.append(f"{q.get('question_id')}（{status}）")
            continue
        typ = str(q.get("prompt_type") or "").strip()
        if typ not in TYPE_ZH:
            sys.exit(f"{q.get('question_id')}：不认识的意图类型 {typ!r}")
        if typ not in INTENT:
            skipped.append(f"{q.get('question_id')}（{TYPE_ZH[typ]}）")
            continue
        intent = INTENT[typ]
        topic = topic_names.get(str(q.get("topic_id") or "").strip(), "")
        line = slice_line.get(str(q.get("slice_ref") or "").strip()) or bank_line
        by_region.setdefault((str(q.get("region") or "未填市场").strip(), line), []).append({
            "query": str(q.get("user_question") or "").strip(),
            "question_zh": str(q.get("zh_translation") or "").strip(),
            "topic": labels.get(topic, topic),
            "diagnosis_intent": intent,
            "tags": tags_cell(typ, derived[id(q)]),
        })
    check = check_upload_rows
    a.out.mkdir(parents=True, exist_ok=True)
    failed = False
    lines_per_region = Counter(region for region, _ in by_region)
    line_no: dict[tuple, int] = {}
    for region, line in by_region:
        line_no[(region, line)] = sum(1 for r, _ in line_no if r == region) + 1
    for (region, line), rows in by_region.items():
        # 一个市场只有一条产品线时文件名不变；多条时按产品线拆，文件名带序号
        suffix = f".{region}" if lines_per_region[region] == 1 else f".{region}.line{line_no[(region, line)]}"
        path = a.out / f"{a.bank.stem}{suffix}.upload.csv"
        if lines_per_region[region] > 1:
            print(f"{path.name} ← 产品线：{line or '未填产品线'}")
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, HEADERS)
            w.writeheader()
            w.writerows(rows)
        errors, summary = check(HEADERS, rows)
        print(f"{path}：{len(rows)} 行，diagnosis_intent {summary['diagnosis_intent']}")
        for e in errors:
            failed = True
            print("  问题：" + e)
    for p in tag_problems:
        print("  标签没出：" + p)
    if skipped:
        print(f"没导出 {len(skipped)} 道（后端未支持的类型）：{', '.join(skipped)}")
    if held:
        print(f"没导出 {len(held)} 道（停测或需修改）：{', '.join(held)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
