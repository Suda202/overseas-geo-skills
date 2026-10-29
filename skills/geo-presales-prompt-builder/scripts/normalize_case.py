#!/usr/bin/env python3
"""Normalize a presales Case input into the v8 question-bank config fragments.

Two entry points share one set of rules:

* ``normalize(payload)`` takes the canonical API payload defined in
  ``references/input-contract.md`` (``input_version = presales-case-input/v1``).
* ``from_base_record(record)`` adapts a Feishu Base record (merged fields joined
  with "，", flat 竞品 n columns, markdown-wrapped URLs) into that payload first.

Output is deterministic: ``case_fields`` with numbered fields expanded, Topic
source mapping, frozen competitor selection, options and handoff. Fields that
need model judgment (English ``topic`` / ``category_label``, ``brand_object_type``,
``attribute_plan``) are left to the skill.

Exit codes: 0 valid, 1 input errors, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

INPUT_VERSION = "presales-case-input/v1"
LOCALE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "locale-templates.json"

BUSINESS_MODES = ("B2B", "B2C", "B2B / B2C")
# 与线上表单对齐：只有这几项必填，业务描述字段全部选填。
SCALAR_REQUIRED = ("公司名", "品牌名称", "业务模式", "品类", "官方域名")
SCALAR_OPTIONAL = ("业务 / 产品名称", "适用边界")
# 多值字段，按 `目标企业画像 n` 展开；B2B 选填，纯 B2C 必须省略。
B2B_LIST = "目标企业画像"
# B2B 选填：查不到就省略，不填「待人工确认」。
B2B_JOINABLE = ("购买标准", "集成与兼容", "信任与合规")
OPTIONAL_JOINABLE = ("差异化优势", "地理与市场")
NUMBERED_LISTS = ("目标客户", "痛点", "使用场景", "产品特性")
# Case Builder 合同的建议数量；超出只告警，不阻断。
SUGGESTED_COUNTS = {"目标企业画像": (1, 5), "目标客户": (1, 5), "痛点": (2, 5), "使用场景": (2, 5), "产品特性": (2, 5)}
TOPIC_KEY = "主题"
COMPETITOR_KEY = "竞品"
NOTE_KEY = "补充内容"
CASE_KEYS = set(
    SCALAR_REQUIRED + SCALAR_OPTIONAL + (B2B_LIST,) + B2B_JOINABLE + OPTIONAL_JOINABLE
    + NUMBERED_LISTS + (TOPIC_KEY, COMPETITOR_KEY, NOTE_KEY)
)
COMPETITOR_KEYS = {"名称", "官网域名"}
CONFIRMATION_STATUSES = ("none", "partial", "confirmed")
GENERATION_STAGES = ("discovery", "diagnostic")
JOIN_SEPARATOR = "，"

# Base 里不承载业务含义的管理列，适配时直接丢弃。
BASE_ADMIN_COLUMNS = {"record_id", "Case序号"}
BASE_RENAMED_COLUMNS = {"垂直行业": "目标企业画像"}
# 接口字段别名：线上表单叫「垂直行业」，直接映射，不要求调用方改名。
CASE_KEY_ALIASES = {"垂直行业": "目标企业画像"}
MARKDOWN_LINK = re.compile(r"^\[(?P<text>[^\]]*)\]\((?P<url>[^)\s]+)\)$")
BASE_COMPETITOR_NAME = re.compile(r"^竞品\s*(\d+)$")
BASE_COMPETITOR_DOMAIN = re.compile(r"^竞品\s*(\d+)\s*官网域名$")
BASE_NUMBERED = re.compile(r"^(目标企业画像|目标客户|痛点|使用场景|产品特性|主题)\s*(\d+)(?:（(?:宽泛|细分)）)?$")


class Report:
    def __init__(self) -> None:
        self.errors: list[dict] = []
        self.warnings: list[dict] = []

    def error(self, code: str, field: str, message: str) -> None:
        self.errors.append({"code": code, "field": field, "message": message})

    def warn(self, code: str, field: str, message: str) -> None:
        self.warnings.append({"code": code, "field": field, "message": message})


def _registered_locales() -> set[str]:
    try:
        registry = json.loads(LOCALE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"en"}
    return {key for key in registry if not key.startswith("_")}


def _clean(value) -> str:
    return str(value).replace("　", " ").strip()


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _check_url(value: str, field: str, report: Report) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        report.error("invalid_url", field, f"{field} 必须是 http(s) 开头的完整网址，收到 {value!r}")


def _scalar(case: dict, field: str, report: Report, required: bool) -> str | None:
    value = case.get(field)
    if _is_blank(value):
        if required:
            report.error("missing_field", field, f"缺少必填字段 {field}")
        return None
    if not isinstance(value, str):
        report.error("invalid_type", field, f"{field} 必须是字符串")
        return None
    return _clean(value)


def _joinable(case: dict, field: str, report: Report, required: bool) -> str | None:
    """字符串原样保留；数组按「，」合并，与 Base 的合并字段写法一致。"""
    value = case.get(field)
    if isinstance(value, list):
        items = [_clean(item) for item in value if isinstance(item, str) and item.strip()]
        if len(items) != len(value):
            report.error("invalid_item", field, f"{field} 的数组元素必须是非空字符串")
        value = JOIN_SEPARATOR.join(items)
    return _scalar({field: value}, field, report, required)


def _string_list(case: dict, field: str, report: Report, required: bool = False) -> list[str]:
    """数组逐项接收；字符串（线上表单的单个文本框）整段按一项接收，不按逗号拆，避免拆错。"""
    value = case.get(field)
    if _is_blank(value) or value == []:
        if required:
            report.error("missing_field", field, f"缺少必填字段 {field}，至少需要 1 项")
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        report.error("invalid_type", field, f"{field} 必须是字符串或字符串数组")
        return []
    items: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            report.error("invalid_item", f"{field}[{index}]", f"{field} 第 {index} 项必须是非空字符串")
            continue
        text = _clean(item)
        if text in items:
            report.error("duplicate_item", f"{field}[{index}]", f"{field} 第 {index} 项与前面重复：{text}")
            continue
        if "，" in text:
            report.warn(
                "comma_in_item", f"{field}[{index}]",
                f"{field} 第 {index} 项含中文逗号；写回飞书合并字段后再拆分会被拆成多项",
            )
        items.append(text)
    return items


def _competitors(case: dict, report: Report) -> list[dict]:
    value = case.get(COMPETITOR_KEY)
    if not isinstance(value, list):
        report.error("missing_field", COMPETITOR_KEY, "竞品必须是 1–3 项的数组")
        return []
    if not 1 <= len(value) <= 3:
        report.error("count_out_of_range", COMPETITOR_KEY, f"竞品必须 1–3 个，收到 {len(value)} 个")
    result: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        field = f"竞品[{index}]"
        if not isinstance(item, dict):
            report.error("invalid_type", field, f"{field} 必须是对象")
            continue
        unknown = sorted(set(item) - COMPETITOR_KEYS)
        if unknown:
            report.error("unknown_field", field, f"{field} 含未定义字段 {unknown}")
        name = _scalar(item, "名称", report, required=True)
        if name is None:
            report.errors[-1]["field"] = f"{field}.名称"
        domain = _scalar(item, "官网域名", report, required=True)
        if domain is None:
            report.errors[-1]["field"] = f"{field}.官网域名"
        if domain:
            _check_url(domain, f"{field}.官网域名", report)
        if name:
            key = name.casefold()
            if key in seen:
                report.error("duplicate_item", f"{field}.名称", f"竞品名称重复：{name}")
            seen.add(key)
        entry = {
            "name": name or "",
            "official_domain": domain or "",
            "source_fields": [f"竞品 {index}", f"竞品 {index} 官网域名"],
        }
        result.append(entry)
    return result


def _handoff(payload: dict, report: Report) -> dict:
    raw = payload.get("handoff")
    if raw is None:
        return {"confirmation_status": "none", "confirmed_fields": [], "sources": []}
    if not isinstance(raw, dict):
        report.error("invalid_type", "handoff", "handoff 必须是对象")
        return {"confirmation_status": "none", "confirmed_fields": [], "sources": []}
    unknown = sorted(set(raw) - {"confirmation_status", "confirmed_fields", "sources"})
    if unknown:
        report.error("unknown_field", "handoff", f"handoff 含未定义字段 {unknown}")
    status = raw.get("confirmation_status", "none")
    if status not in CONFIRMATION_STATUSES:
        report.error(
            "invalid_enum", "handoff.confirmation_status",
            f"confirmation_status 只接受 {list(CONFIRMATION_STATUSES)}",
        )
    confirmed = raw.get("confirmed_fields", [])
    if not isinstance(confirmed, list) or not all(isinstance(x, str) for x in confirmed):
        report.error("invalid_type", "handoff.confirmed_fields", "confirmed_fields 必须是字段名数组")
        confirmed = []
    for name in confirmed:
        if name not in CASE_KEYS:
            report.error("invalid_reference", "handoff.confirmed_fields", f"confirmed_fields 引用了不存在的字段 {name}")
    if status == "confirmed" and not confirmed:
        report.warn("confirmation_without_fields", "handoff", "状态为 confirmed 但未列出已确认字段，按全部字段已确认处理")
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        report.error("invalid_type", "handoff.sources", "sources 必须是数组")
        sources = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict) or _is_blank(source.get("url")):
            report.error("invalid_item", f"handoff.sources[{index}]", "每条来源必须是含 url 的对象")
        else:
            _check_url(_clean(source["url"]), f"handoff.sources[{index}].url", report)
    return {"confirmation_status": status, "confirmed_fields": confirmed, "sources": sources}


def normalize(payload: dict) -> dict:
    report = Report()
    if not isinstance(payload, dict):
        report.error("invalid_type", "$", "输入必须是 JSON 对象")
        return _result(report, None)
    unknown_root = sorted(set(payload) - {"input_version", "case", "options", "handoff"})
    if unknown_root:
        report.error("unknown_field", "$", f"顶层含未定义字段 {unknown_root}")
    if payload.get("input_version") != INPUT_VERSION:
        report.error("invalid_enum", "input_version", f"input_version 必须等于 {INPUT_VERSION}")
    case = payload.get("case")
    if not isinstance(case, dict):
        report.error("missing_field", "case", "缺少 case 对象")
        return _result(report, None)
    case = dict(case)
    for alias, target in CASE_KEY_ALIASES.items():
        if alias not in case:
            continue
        value = case.pop(alias)
        if _is_blank(case.get(target)) or case.get(target) == []:
            case[target] = value
        elif not (_is_blank(value) or value == []):
            report.warn("alias_ignored", alias, f"同时传了 {alias} 和 {target}，按 {target} 取值")
    unknown = sorted(set(case) - CASE_KEYS)
    if unknown:
        report.error("unknown_field", "case", f"case 含未定义字段 {unknown}")

    fields: dict[str, str] = {}
    for field in SCALAR_REQUIRED:
        value = _scalar(case, field, report, required=True)
        if value is not None:
            fields[field] = value
    mode = fields.get("业务模式")
    if mode is not None and mode not in BUSINESS_MODES:
        report.error("invalid_enum", "业务模式", f"业务模式只接受 {list(BUSINESS_MODES)}，收到 {mode!r}")
    if "官方域名" in fields:
        _check_url(fields["官方域名"], "官方域名", report)
    for field in SCALAR_OPTIONAL:
        value = _scalar(case, field, report, required=False)
        if value is not None:
            fields[field] = value

    is_b2c = mode == "B2C"
    for field in (B2B_LIST,) + B2B_JOINABLE:
        if is_b2c:
            if not _is_blank(case.get(field)) and case.get(field) != []:
                report.error("forbidden_for_b2c", field, f"纯 B2C Case 不填 {field}，请省略该字段")
            continue
        if field == B2B_LIST:
            items = _string_list(case, field, report)
            low, high = SUGGESTED_COUNTS[field]
            if items and not low <= len(items) <= high:
                report.warn("count_suggestion", field, f"{field} 建议 {low}–{high} 项，收到 {len(items)} 项")
            if "待人工确认" in items:
                report.warn("pending_value", field, f"{field} 仍为「待人工确认」，需上游补齐")
            for index, item in enumerate(items, start=1):
                fields[f"{field} {index}"] = item
            continue
        value = _joinable(case, field, report, required=False)
        if value is None:
            continue
        if value == "待人工确认":
            report.warn("pending_value", field, f"{field} 为「待人工确认」，已按未填写处理")
            continue
        fields[field] = value
    for field in OPTIONAL_JOINABLE:
        value = _joinable(case, field, report, required=False)
        if value is not None:
            fields[field] = value

    for field in NUMBERED_LISTS:
        items = _string_list(case, field, report)
        low, high = SUGGESTED_COUNTS[field]
        if items and not low <= len(items) <= high:
            report.warn("count_suggestion", field, f"{field} 建议 {low}–{high} 项，收到 {len(items)} 项")
        for index, item in enumerate(items, start=1):
            fields[f"{field} {index}"] = item

    # 主题选填（Suda 2026-10-29）：线上表单去掉了监测主题，生词时从矩阵行聚出主题。
    # 旧 Case 带着主题也收（1–3 个，第一个宽泛），结果里 topic_source 区分两种情况。
    topics = _string_list(case, TOPIC_KEY, report)
    if topics and not 1 <= len(topics) <= 3:
        report.error("count_out_of_range", TOPIC_KEY, f"主题必须 1–3 个，收到 {len(topics)} 个")
        topics = topics[:3]
    topic_entries = []
    for index, topic in enumerate(topics, start=1):
        # 第一个主题是核心品类 Coverage Topic，其余为同产品线的 Depth Topic（Case Builder 合同）。
        source_field = f"主题 {index}（{'宽泛' if index == 1 else '细分'}）"
        fields[source_field] = topic
        topic_entries.append({"topic_id": f"topic_{index}", "source_field": source_field, "source_value": topic})

    # 竞品不带主题边界（2026-10-29 删去「适用主题」：线上表单没有这一项）。
    competitors = _competitors(case, report)
    for index, competitor in enumerate(competitors, start=1):
        fields[f"竞品 {index}"] = competitor["name"]
        fields[f"竞品 {index} 官网域名"] = competitor["official_domain"]

    note = case.get(NOTE_KEY)
    if note is not None and not isinstance(note, str):
        report.error("invalid_type", NOTE_KEY, "补充内容必须是字符串")
        note = ""
    fields[NOTE_KEY] = _clean(note or "")

    options = payload.get("options") or {}
    if not isinstance(options, dict):
        report.error("invalid_type", "options", "options 必须是对象")
        options = {}
    unknown_options = sorted(set(options) - {"locale", "generation_stage"})
    if unknown_options:
        report.error("unknown_field", "options", f"options 含未定义字段 {unknown_options}")
    locale = str(options.get("locale") or "en").strip().casefold()
    locales = _registered_locales()
    if locale not in locales:
        report.error("invalid_enum", "options.locale", f"locale 只接受已登记语言 {sorted(locales)}")
    stage = options.get("generation_stage") or "discovery"
    if stage not in GENERATION_STAGES:
        report.error("invalid_enum", "options.generation_stage", f"generation_stage 只接受 {list(GENERATION_STAGES)}")
    elif stage == "diagnostic":
        report.warn("baseline_required", "options.generation_stage", "diagnostic 补题必须同时提供原 Discovery 题库作为 baseline")

    handoff = _handoff(payload, report)
    normalized = {
        "case_fields": fields,
        "brand_name": fields.get("品牌名称", ""),
        "official_domain": fields.get("官方域名", ""),
        "derived_field_sources": {"brand_name": "品牌名称", "category_label": "品类", "official_domain": "官方域名"},
        "topics": topic_entries,
        # case = 调用方填了主题；to_derive = 没填，生词时从矩阵行聚出
        "topic_source": "case" if topic_entries else "to_derive",
        "competitor_selection": {"status": "frozen", "selection_count": len(competitors), "formal_competitors": competitors},
        "locale": locale,
        "generation_stage": stage,
        "handoff": handoff,
    }
    return _result(report, normalized)


def _result(report: Report, normalized: dict | None) -> dict:
    ok = not report.errors
    result = {"ok": ok, "errors": report.errors, "warnings": report.warnings}
    if ok:
        result["normalized"] = normalized
    return result


def _base_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        # 富文本单元格可能是 [{"text": ...}] 片段数组。
        value = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    text = _clean(value)
    match = MARKDOWN_LINK.fullmatch(text)
    return match.group("url") if match else text


def from_base_record(record: dict) -> tuple[dict, list[dict]]:
    """Adapt one Feishu Base record into the canonical payload plus adapter warnings."""
    warnings: list[dict] = []
    case: dict = {}
    numbered: dict[str, dict[int, str]] = {}
    competitors: dict[int, dict] = {}
    for raw_key, raw_value in record.items():
        key = _clean(raw_key)
        if key in BASE_ADMIN_COLUMNS:
            continue
        value = _base_value(raw_value)
        if _is_blank(value):
            continue
        if key in BASE_RENAMED_COLUMNS:
            target = BASE_RENAMED_COLUMNS[key]
            if target not in record or _is_blank(record.get(target)):
                case[target] = (
                    [part.strip() for part in value.split(JOIN_SEPARATOR) if part.strip()]
                    if target == B2B_LIST else value
                )
                warnings.append({
                    "code": "renamed_column", "field": key,
                    "message": f"旧列 {key} 已按 {target} 读取",
                })
            continue
        if m := BASE_COMPETITOR_DOMAIN.fullmatch(key):
            competitors.setdefault(int(m.group(1)), {})["官网域名"] = value
        elif m := BASE_COMPETITOR_NAME.fullmatch(key):
            competitors.setdefault(int(m.group(1)), {})["名称"] = value
        elif m := BASE_NUMBERED.fullmatch(key):
            numbered.setdefault(m.group(1), {})[int(m.group(2))] = value
        elif key in NUMBERED_LISTS or key in (TOPIC_KEY, B2B_LIST):
            case[key] = [part.strip() for part in value.split(JOIN_SEPARATOR) if part.strip()]
        elif key in CASE_KEYS:
            case[key] = value
        else:
            warnings.append({"code": "ignored_column", "field": key, "message": f"未识别的 Base 列 {key} 已忽略"})
    for key, by_index in numbered.items():
        case[key] = [by_index[i] for i in sorted(by_index)]
    if competitors:
        case[COMPETITOR_KEY] = [competitors[i] for i in sorted(competitors)]
    return {"input_version": INPUT_VERSION, "case": case}, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="canonical payload JSON, or a Base record (JSON / single-line NDJSON)")
    parser.add_argument("--from-base-record", action="store_true", help="treat input as a Feishu Base record")
    parser.add_argument("-o", "--output", type=Path, help="write the result JSON here as well as stdout")
    args = parser.parse_args()
    try:
        text = args.input.read_text(encoding="utf-8").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if not args.from_base_record:
                raise
            # lark-cli 读回的是 NDJSON，一行一条 Record；只取第一条。
            data = json.loads(text.splitlines()[0])
    except (OSError, json.JSONDecodeError, IndexError) as exc:
        print(json.dumps({"ok": False, "errors": [{"code": "unreadable_input", "field": "$", "message": str(exc)}]}, ensure_ascii=False, indent=2))
        return 2
    adapter_warnings: list[dict] = []
    if args.from_base_record:
        if not isinstance(data, dict):
            print(json.dumps({"ok": False, "errors": [{"code": "invalid_type", "field": "$", "message": "Base record 必须是 JSON 对象"}]}, ensure_ascii=False, indent=2))
            return 2
        data, adapter_warnings = from_base_record(data)
    result = normalize(data)
    result["warnings"] = adapter_warnings + result["warnings"]
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
