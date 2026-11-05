#!/usr/bin/env python3
"""选词题库 JSON → 售前诊断上传 CSV（《海外售前诊断关键词模板》的 9 列，Suda 2026-10-29）。

列：query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name

- diagnosis_intent 用后端枚举；它和 prompt_type 取值不完全一样，提示词类型的中文名写进 tags 第一个。
- tags 后面接跨主题切片标签：选词新题库（generation_stage: selection）和写了 config.tag_dimensions 的题库，
  按登记的维度从矩阵行和属性池派生（口径在 tag_dimensions.py，落在不到 2 个主题、不到 5 道题、
  和主题重复的值不出，打印原因）；售前题库和旧题库没写 tag_dimensions 时照旧带出题目自己的 tags。
  替代（Alternatives）后端还没有枚举，按映射表临时记 competitor，tags 里的「替代」区分；
  研发会加独立枚举、算可见度和情感（Suda 2026-10-29），上线后改 INTENT / QUESTION_TYPES；
  问题解决（Information）后端不支持，验证（Verification）只作临时诊断，两者不导出并打印题号。
- question_types 按 diagnosis_intent 固定填（发现 visibility,sentiment；对比、评价 sentiment；
  验证、准确性、品类认知 visibility），口径见 shared/canonical-intent-mapping.md。
- purchase_intent / persona_name / scene_name 留空：本地报告脚本（build_report_data.py）读上传 CSV 时不取这三列；
  线上后端是否读它们未确认，确认前留空（output-contract.md → 上传 CSV）。
- 上传时市场在上传页另选，所以 CSV 不带市场；题库有几个 region 就出几份，每份一个市场。
- 题目没写 topic 时按 topic_id 去 config.topics 取主题名（某制造业客户题库只有 topic_id）。
- 不导出 status 为 retired / 停测、review_status 为 需修改 的题，打印题号。
- 写完用售前 validator 的上传 CSV 检查（validate_v8_csv_rows）自检，不过就退出码 1。

用法：
    python3 -I export_upload_csv.py <题库.json> --out <目录> [--topic-label "TWS Earbuds=无线耳机"]
"""
import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

HEADERS = ["query", "question_zh", "topic", "diagnosis_intent", "tags", "question_types",
           "purchase_intent", "persona_name", "scene_name"]
INTENT = {"Discovery": "discovery", "Competitor": "competitor", "Alternatives": "competitor",
          "Evaluation": "evaluation", "Accuracy": "accuracy",
          "Category Awareness": "category_awareness"}
QUESTION_TYPES = {"discovery": "visibility,sentiment", "competitor": "sentiment", "evaluation": "sentiment",
                  "verification": "visibility", "accuracy": "visibility", "category_awareness": "visibility"}
TYPE_ZH = {"Discovery": "发现", "Competitor": "对比", "Alternatives": "替代", "Evaluation": "评价",
           "Verification": "验证", "Accuracy": "准确性", "Category Awareness": "品类认知", "Information": "问题解决"}
TAGS_MAX = 200
SKIP_STATUS = {"retired", "停测"}
SKIP_REVIEW = {"需修改", "needs_revision"}
PRESALES_VALIDATOR = (Path(__file__).resolve().parents[2]
                      / "geo-presales-prompt-builder" / "scripts" / "validate_question_bank.py")
# -I 不把脚本目录放进 sys.path，同目录的 tag_dimensions 要手动加
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from tag_dimensions import tag_plan  # noqa: E402


def tags_cell(prompt_type, tags):
    """类型中文名放第一个，再接切片标签；超长就从后面丢，保证短于 200 字。"""
    out = [TYPE_ZH[prompt_type]] + [str(t).strip() for t in tags or [] if str(t).strip() and str(t).strip() != TYPE_ZH[prompt_type]]
    while len(",".join(out)) >= TAGS_MAX and len(out) > 1:
        out.pop()
    return ",".join(out)


def presales_check():
    spec = importlib.util.spec_from_file_location("presales_validator", PRESALES_VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_v8_csv_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bank", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--topic-label", action="append", default=[],
                    help="题库主题名=上传用的中文主题名，可重复；不给就用题库里的主题名")
    a = ap.parse_args()
    labels = dict(x.split("=", 1) for x in a.topic_label)
    bank = json.loads(a.bank.read_text(encoding="utf-8"))
    topic_names = {str(t.get("topic_id") or "").strip(): str(t.get("topic") or t.get("name") or "").strip()
                   for t in (bank.get("config") or {}).get("topics") or [] if isinstance(t, dict)}
    config = bank.get("config") or {}
    derived, tag_problems, _ = tag_plan(config, bank["questions"])
    by_region, skipped, held = {}, [], []
    for q in bank["questions"]:
        status, review = str(q.get("status") or "").strip(), str(q.get("review_status") or "").strip()
        # 状态 merges review values since 2026-11-01: status 需修改 is held back like review_status 需修改.
        if status in SKIP_STATUS or review in SKIP_REVIEW or status in SKIP_REVIEW:
            held.append(f"{q.get('question_id')}（{status if status in SKIP_STATUS | SKIP_REVIEW else review}）")
            continue
        # 2026-10-22 前的旧题库里 prompt_type 存的是问法小类（「品类」「价格」），类型在 intent 里
        typ = next((str(q.get(k) or "").strip() for k in ("prompt_type", "intent")
                    if str(q.get(k) or "").strip() in TYPE_ZH), str(q.get("prompt_type") or "").strip())
        if typ not in TYPE_ZH:
            sys.exit(f"{q.get('question_id')}：不认识的提示词类型 {typ!r}")
        if typ not in INTENT:
            skipped.append(f"{q.get('question_id')}（{TYPE_ZH[typ]}）")
            continue
        intent = INTENT[typ]
        topic = str(q.get("topic") or "").strip() or topic_names.get(str(q.get("topic_id") or "").strip(), "")
        by_region.setdefault(str(q.get("region") or "未填市场").strip(), []).append({
            "query": str(q.get("user_question") or q.get("monitoring_prompt") or "").strip(),
            "question_zh": str(q.get("zh_translation") or "").strip(),
            "topic": labels.get(topic, topic),
            "diagnosis_intent": intent,
            "tags": tags_cell(typ, derived[id(q)] if derived else q.get("tags")),
            "question_types": QUESTION_TYPES[intent],
            "purchase_intent": "", "persona_name": "", "scene_name": "",
        })
    check = presales_check()
    a.out.mkdir(parents=True, exist_ok=True)
    failed = False
    for region, rows in by_region.items():
        path = a.out / f"{a.bank.stem}.{region}.upload.csv"
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
        print(f"没导出 {len(skipped)} 道（临时诊断或后端未支持的类型）：{', '.join(skipped)}")
    if held:
        print(f"没导出 {len(held)} 道（停测或需修改）：{', '.join(held)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
