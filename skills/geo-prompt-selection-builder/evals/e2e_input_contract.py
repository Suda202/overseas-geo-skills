#!/usr/bin/env python3
"""End-to-end check for the Case input contract v2 (references/input-contract.md).

Runs the example payloads, a required-only payload, retired v1 inputs and a set
of broken inputs through scripts/normalize_case.py and checks the result codes.
Writes reports/input-contract-e2e.md.

    python3 evals/e2e_input_contract.py
Exit code 0 means every check passed.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from normalize_case import CASE_KEYS, normalize  # noqa: E402

EXAMPLES = SKILL / "references" / "input-examples"
TEMPLATES = SKILL.parent / "shared" / "publish-templates"
# 《AI 搜索监测｜品牌资料收集》第一部分的字段（市场、语言走采集配置，不进 case）
INTAKE_FIELDS = {"品牌", "品牌别名", "官方域名", "产品线", "适用边界", "竞品",
                 "核心目标客户与购买场景", "差异化优势"}

rows: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    rows.append((name, passed, detail))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def codes(result: dict) -> list[str]:
    return [e["code"] for e in result["errors"]]


# 1. 合同字段与《品牌资料收集》第一部分一致
check("合同字段 = 《品牌资料收集》第一部分字段", CASE_KEYS == INTAKE_FIELDS,
      f"多 {sorted(CASE_KEYS - INTAKE_FIELDS)} 少 {sorted(INTAKE_FIELDS - CASE_KEYS)}")

# 2. 示例与公开模板都能通过，编号字段按顺序展开
for path in sorted(EXAMPLES.glob("*.json")) + sorted(TEMPLATES.glob("b2?-example.json")):
    payload = load(path)
    result = normalize(payload)
    check(f"示例 {path.name} 归一化无错误无告警", result["ok"] and not result["warnings"],
          json.dumps(result["errors"] + result["warnings"], ensure_ascii=False))
    if not result["ok"]:
        continue
    cf = result["normalized"]["case_fields"]
    targets = payload["case"]["核心目标客户与购买场景"]
    check(f"{path.name} 核心目标客户按原顺序展开为编号字段",
          [cf.get(f"核心目标客户与购买场景 {i}") for i in range(1, len(targets) + 1)] == targets)
    check(f"{path.name} 竞品取客户填的、不冻结",
          result["normalized"]["competitor_selection"]["status"] == "client_input"
          and result["normalized"]["competitor_selection"]["selection_count"] == len(payload["case"]["竞品"]))

base = load(EXAMPLES / "b2c-example.json")


def mutate(fn) -> dict:
    payload = copy.deepcopy(base)
    fn(payload)
    return payload


# 3. 只填必填项、1 个竞品也能通过
minimal = {"input_version": base["input_version"],
           "case": {k: base["case"][k] for k in ("品牌", "官方域名", "产品线")}}
minimal["case"]["竞品"] = base["case"]["竞品"][:1]
result = normalize(minimal)
check("只填必填项（品牌、官方域名、产品线、1 个竞品）→ 通过",
      result["ok"] and result["normalized"]["locale"] == "en", json.dumps(result["errors"], ensure_ascii=False))

# 4. v1 输入：整份拒收，并说明改用 v2
v1 = mutate(lambda p: p.__setitem__("input_version", "presales-case-input/v1"))
result = normalize(v1)
check("v1 payload → unsupported_version", codes(result) == ["unsupported_version"], f"实际错误码={codes(result)}")
for field in ("公司名", "业务模式", "品类", "痛点", "希望解决的问题", "主题", "补充内容", "品牌名称"):
    result = normalize(mutate(lambda p, f=field: p["case"].__setitem__(f, "x")))
    check(f"v2 里带了已停用字段 {field} → retired_field", "retired_field" in codes(result), f"实际错误码={codes(result)}")

# 4b. 旧字段名「本期产品线」（2026-11-10 改名「产品线」）照收并提醒
renamed = mutate(lambda p: p["case"].__setitem__("本期产品线", p["case"].pop("产品线")))
result = normalize(renamed)
check("旧名「本期产品线」→ 按「产品线」收，renamed_field 告警",
      result["ok"] and result["normalized"]["case_fields"].get("产品线") == base["case"]["产品线"]
      and "本期产品线" not in result["normalized"]["case_fields"]
      and [w["code"] for w in result["warnings"]] == ["renamed_field"],
      json.dumps(result.get("errors") or result.get("warnings"), ensure_ascii=False))

# 5. 「待补充」按没填处理；「无」原样记录、不算别名
result = normalize(mutate(lambda p: p["case"].__setitem__("适用边界", "待补充")))
check("选填项填「待补充」→ 通过并告警，不进 case_fields",
      result["ok"] and "适用边界" not in result["normalized"]["case_fields"]
      and [w["code"] for w in result["warnings"]] == ["pending_value"])
result = normalize(mutate(lambda p: p["case"].__setitem__("产品线", "待补充")))
check("必填项填「待补充」→ missing_field", "missing_field" in codes(result), f"实际错误码={codes(result)}")
result = normalize(mutate(lambda p: p["case"].__setitem__("品牌别名", "无")))
check("品牌别名填「无」→ 通过，brand_aliases 为空",
      result["ok"] and result["normalized"]["brand_aliases"] == [] and result["normalized"]["case_fields"]["品牌别名 1"] == "无")

# 6. 官方域名可填多个，第一个是主站
result = normalize(mutate(lambda p: p["case"].__setitem__("官方域名", ["https://brandy.example", "https://th.brandy.example"])))
check("官方域名传数组 → 第一个当主站，其余编号保留",
      result["ok"] and result["normalized"]["official_domain"] == "https://brandy.example"
      and result["normalized"]["case_fields"].get("官方域名 2") == "https://th.brandy.example",
      json.dumps(result.get("errors"), ensure_ascii=False))

# 7. 文本框字符串整段按一项接收，不按逗号拆
result = normalize(mutate(lambda p: p["case"].__setitem__("核心目标客户与购买场景", "多猫家庭：白天无人照看，关注异味，和清理频次")))
cf = result["normalized"]["case_fields"] if result["ok"] else {}
check("文本框字符串整段按一项接收，不按逗号拆",
      cf.get("核心目标客户与购买场景 1", "").endswith("清理频次") and "核心目标客户与购买场景 2" not in cf)

# 8. 失败输入：每种都必须返回对应错误码，而不是静默放行
FAILURES = [
    ("缺品牌", lambda p: p["case"].pop("品牌"), "missing_field"),
    ("缺产品线", lambda p: p["case"].pop("产品线"), "missing_field"),
    ("缺官方域名", lambda p: p["case"].pop("官方域名"), "missing_field"),
    ("竞品 4 个", lambda p: p["case"]["竞品"].append({"名称": "Extra", "官网域名": "https://extra.example"}), "count_out_of_range"),
    ("竞品重名", lambda p: p["case"]["竞品"][1].__setitem__("名称", "RivalY1"), "duplicate_item"),
    ("官网不是完整网址", lambda p: p["case"].__setitem__("官方域名", "brandy.example"), "invalid_url"),
    ("竞品带未定义字段", lambda p: p["case"]["竞品"][0].__setitem__("适用主题", [1]), "unknown_field"),
    ("字段名拼错", lambda p: p["case"].__setitem__("业务目的", "x"), "unknown_field"),
    ("未登记语言", lambda p: p["options"].__setitem__("locale", "fr"), "invalid_enum"),
    ("options 带已停用的 generation_stage", lambda p: p["options"].__setitem__("generation_stage", "selection"), "unknown_field"),
    ("input_version 缺失", lambda p: p.pop("input_version"), "invalid_enum"),
    ("核心目标客户重复", lambda p: p["case"]["核心目标客户与购买场景"].append(p["case"]["核心目标客户与购买场景"][0]), "duplicate_item"),
]
for label, fn, code in FAILURES:
    result = normalize(mutate(fn))
    check(f"失败输入：{label} → {code}", not result["ok"] and code in codes(result), f"实际错误码={codes(result)}")


passed = sum(1 for _, ok, _ in rows if ok)
lines = [
    "# Case 输入合同端到端校验（presales-case-input/v2）",
    "",
    f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
    "- 命令：`python3 evals/e2e_input_contract.py`",
    f"- 结果：{passed}/{len(rows)} 通过",
    "",
    "| 检查 | 结果 | 说明 |",
    "|---|---|---|",
]
for name, ok, detail in rows:
    lines.append(f"| {name} | {'通过' if ok else '失败'} | {detail.replace('|', '/') if detail else ''} |")
report = SKILL / "reports" / "input-contract-e2e.md"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
sys.exit(0 if passed == len(rows) else 1)
