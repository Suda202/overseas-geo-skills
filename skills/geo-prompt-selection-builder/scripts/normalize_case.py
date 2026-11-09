#!/usr/bin/env python3
"""Normalize a presales Case input into the v8 question-bank config fragments.

``normalize(payload)`` takes the canonical payload defined in
``references/input-contract.md`` (``input_version = presales-case-input/v2``).
The Case fields are the first part of the Feishu doc《AI 搜索监测｜品牌资料收集》
(Suda 2026-11-09): the online diagnosis form and the after-sales intake collect
the same fields. v1 payloads (公司名 / 业务模式 / 品类 / 痛点 …) are rejected.

Output is deterministic: ``case_fields`` with numbered fields expanded, the
client's competitors (not frozen), locale and handoff. Things that need model
judgment (category name ``category_label``, Topics, matrix rows, Prompts) are
left to the skill; ``category_label`` is derived from 本期产品线 and the site.

Exit codes: 0 valid, 1 input errors, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

INPUT_VERSION = "presales-case-input/v2"
RETIRED_VERSIONS = ("presales-case-input/v1",)
LOCALE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "locale-templates.json"

# 与《品牌资料收集》第一部分一一对应（市场、语言是采集配置：市场走 --market，语言走 options.locale）。
SCALAR_REQUIRED = ("品牌", "本期产品线")
DOMAIN_KEY = "官方域名"
SCALAR_OPTIONAL = ("适用边界", "业务目标")
# 多值字段，按 `字段 n` 展开；顺序原样保留（核心目标客户与购买场景按业务优先级排，最优先的在前）。
NUMBERED_LISTS = ("品牌别名", "核心目标客户与购买场景", "差异化优势")
SUGGESTED_MAX = {"核心目标客户与购买场景": 5, "差异化优势": 5}
COMPETITOR_KEY = "竞品"
CASE_KEYS = set(SCALAR_REQUIRED + (DOMAIN_KEY,) + SCALAR_OPTIONAL + NUMBERED_LISTS + (COMPETITOR_KEY,))
# v1 字段（2026-11-09 退役）：报 retired_field，说明并到了哪里。
RETIRED_FIELDS = {
    "公司名": "删除；易混淆的公司或品牌名写进「品牌别名」",
    "品牌名称": "改名「品牌」",
    "业务 / 产品名称": "改用「本期产品线」",
    "业务模式": "删除；B2B / B2C 从「核心目标客户与购买场景」判断",
    "品类": "删除；品类由选词从「本期产品线」和官网推出",
    "目标企业画像": "并入「核心目标客户与购买场景」",
    "垂直行业": "并入「核心目标客户与购买场景」",
    "目标客户": "并入「核心目标客户与购买场景」",
    "痛点": "并入「核心目标客户与购买场景」",
    "使用场景": "并入「核心目标客户与购买场景」",
    "产品特性": "删除；选词调研时读官网",
    "补充内容": "删除",
    "希望解决的问题": "改用「业务目标」",
    "主题": "删除；主题由选词从矩阵行聚出",
    "购买标准": "删除",
    "集成与兼容": "删除",
    "信任与合规": "删除",
    "地理与市场": "删除；市场走 --market",
}
COMPETITOR_KEYS = {"名称", "官网域名"}
CONFIRMATION_STATUSES = ("none", "partial", "confirmed")
# 《品牌资料收集》：暂不确定的填「待补充」，按没填处理；不适用的填「无」，原样记录。
PENDING_VALUES = ("待补充", "待人工确认")


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
    return value is None or value == [] or (isinstance(value, str) and not value.strip())


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _check_url(value: str, field: str, report: Report) -> None:
    if not _is_url(value):
        report.error("invalid_url", field, f"{field} 必须是 http(s) 开头的完整网址，收到 {value!r}")


def _pending(value: str, field: str, report: Report) -> bool:
    if value in PENDING_VALUES:
        report.warn("pending_value", field, f"{field} 为「{value}」，已按未填写处理")
        return True
    return False


def _scalar(case: dict, field: str, report: Report, required: bool) -> str | None:
    value = case.get(field)
    if _is_blank(value):
        if required:
            report.error("missing_field", field, f"缺少必填字段 {field}")
        return None
    if not isinstance(value, str):
        report.error("invalid_type", field, f"{field} 必须是字符串")
        return None
    text = _clean(value)
    if _pending(text, field, report):
        if required:
            report.error("missing_field", field, f"必填字段 {field} 不能是「{text}」")
        return None
    return text


def _string_list(case: dict, field: str, report: Report, required: bool = False) -> list[str]:
    """数组逐项接收；字符串（单个文本框）整段按一项接收，不按逗号拆，避免拆错。"""
    value = case.get(field)
    if _is_blank(value):
        if required:
            report.error("missing_field", field, f"缺少必填字段 {field}，至少需要 1 项")
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        report.error("invalid_type", field, f"{field} 必须是字符串或字符串数组")
        return []
    items: list[str] = []
    errors_before = len(report.errors)
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            report.error("invalid_item", f"{field}[{index}]", f"{field} 第 {index} 项必须是非空字符串")
            continue
        text = _clean(item)
        if _pending(text, f"{field}[{index}]", report):
            continue
        if text in items:
            report.error("duplicate_item", f"{field}[{index}]", f"{field} 第 {index} 项与前面重复：{text}")
            continue
        items.append(text)
    if required and not items and len(report.errors) == errors_before:
        report.error("missing_field", field, f"缺少必填字段 {field}，至少需要 1 项")
    return items


def _domains(case: dict, report: Report) -> list[str]:
    """官方域名：一个网址或网址数组，第一个是品牌主站；子域名、市场独立站往后写。"""
    items = _string_list(case, DOMAIN_KEY, report, required=True)
    for index, item in enumerate(items, start=1):
        _check_url(item, DOMAIN_KEY if len(items) == 1 else f"{DOMAIN_KEY}[{index}]", report)
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
        result.append({
            "name": name or "",
            "official_domain": domain or "",
            "source_fields": [f"竞品 {index}", f"竞品 {index} 官网域名"],
        })
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
    version = payload.get("input_version")
    if version in RETIRED_VERSIONS:
        report.error(
            "unsupported_version", "input_version",
            f"{version} 已于 2026-11-09 停用，请按 {INPUT_VERSION} 传《品牌资料收集》第一部分的字段",
        )
        return _result(report, None)
    if version != INPUT_VERSION:
        report.error("invalid_enum", "input_version", f"input_version 必须等于 {INPUT_VERSION}")
    case = payload.get("case")
    if not isinstance(case, dict):
        report.error("missing_field", "case", "缺少 case 对象")
        return _result(report, None)
    for key in sorted(set(case) & set(RETIRED_FIELDS)):
        report.error("retired_field", key, f"{key} 已停用（2026-11-09）：{RETIRED_FIELDS[key]}")
    unknown = sorted(set(case) - CASE_KEYS - set(RETIRED_FIELDS))
    if unknown:
        report.error("unknown_field", "case", f"case 含未定义字段 {unknown}")

    fields: dict[str, str] = {}
    for field in SCALAR_REQUIRED:
        value = _scalar(case, field, report, required=True)
        if value is not None:
            fields[field] = value
    domains = _domains(case, report)
    if domains:
        fields[DOMAIN_KEY] = domains[0]
        for index, extra in enumerate(domains[1:], start=2):
            fields[f"{DOMAIN_KEY} {index}"] = extra
    for field in SCALAR_OPTIONAL:
        value = _scalar(case, field, report, required=False)
        if value is not None:
            fields[field] = value
    lists: dict[str, list[str]] = {}
    for field in NUMBERED_LISTS:
        items = _string_list(case, field, report)
        high = SUGGESTED_MAX.get(field)
        if high and len(items) > high:
            report.warn("count_suggestion", field, f"{field} 建议不超过 {high} 条，收到 {len(items)} 条")
        lists[field] = items
        for index, item in enumerate(items, start=1):
            fields[f"{field} {index}"] = item

    competitors = _competitors(case, report)
    for index, competitor in enumerate(competitors, start=1):
        fields[f"竞品 {index}"] = competitor["name"]
        fields[f"竞品 {index} 官网域名"] = competitor["official_domain"]

    options = payload.get("options") or {}
    if not isinstance(options, dict):
        report.error("invalid_type", "options", "options 必须是对象")
        options = {}
    unknown_options = sorted(set(options) - {"locale"})
    if unknown_options:
        report.error("unknown_field", "options", f"options 含未定义字段 {unknown_options}")
    locale = str(options.get("locale") or "en").strip().casefold()
    locales = _registered_locales()
    if locale not in locales:
        report.error("invalid_enum", "options.locale", f"locale 只接受已登记语言 {sorted(locales)}")

    handoff = _handoff(payload, report)
    normalized = {
        "case_fields": fields,
        "brand_name": fields.get("品牌", ""),
        "brand_aliases": [a for a in lists.get("品牌别名", []) if a != "无"],
        "official_domain": domains[0] if domains else "",
        "official_domains": domains,
        "product_line": fields.get("本期产品线", ""),
        # 品类名由选词从本期产品线和官网推出，写进题库 config.category_label
        "derived_field_sources": {"brand_name": "品牌", "official_domain": "官方域名", "category_label": "本期产品线（推断）"},
        # 竞品取客户填的，不冻结；报告侧按提及率补足归线上与监测（2026-11-06 / 11-09）
        "competitor_selection": {"status": "client_input", "selection_count": len(competitors), "formal_competitors": competitors},
        "locale": locale,
        "handoff": handoff,
    }
    return _result(report, normalized)


def _result(report: Report, normalized: dict | None) -> dict:
    ok = not report.errors
    result = {"ok": ok, "errors": report.errors, "warnings": report.warnings}
    if ok:
        result["normalized"] = normalized
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help=f"{INPUT_VERSION} payload JSON")
    parser.add_argument("-o", "--output", type=Path, help="write the result JSON here as well as stdout")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [{"code": "unreadable_input", "field": "$", "message": str(exc)}]}, ensure_ascii=False, indent=2))
        return 2
    result = normalize(data)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
