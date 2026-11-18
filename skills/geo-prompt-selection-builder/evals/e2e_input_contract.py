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
# 线上诊断表单的品牌资料字段（Suda 2026-11-13；国家/地区、语言、AI 平台走采集配置，不进 case）
INTAKE_FIELDS = {"公司名称", "品牌", "品牌别名", "官方域名", "产品线", "适用边界", "竞品",
                 "核心目标客户与购买场景", "差异化优势", "补充内容"}

rows: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    rows.append((name, passed, detail))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def codes(result: dict) -> list[str]:
    return [e["code"] for e in result["errors"]]


# 1. 合同字段与线上表单一致
check("合同字段 = 线上表单品牌资料字段", CASE_KEYS == INTAKE_FIELDS,
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

base = load(EXAMPLES / "youku-b2c.json")


def mutate(fn) -> dict:
    payload = copy.deepcopy(base)
    fn(payload)
    return payload


# 3. 只填必填项、1 个竞品也能通过
minimal = {"input_version": base["input_version"],
           "case": {k: base["case"][k] for k in ("品牌", "官方域名", "产品线")}}
minimal["case"]["竞品"] = base["case"]["竞品"][:1]
minimal["case"]["核心目标客户与购买场景"] = base["case"]["核心目标客户与购买场景"][:1]
minimal["case"]["差异化优势"] = base["case"]["差异化优势"][:1]
result = normalize(minimal)
check("只填必填项（品牌、官方域名、产品线、1 个竞品、1 条核心目标客户、1 条差异化优势）→ 通过",
      result["ok"] and result["normalized"]["locale"] == "en", json.dumps(result["errors"], ensure_ascii=False))

# 4. v1 输入：整份拒收，并说明改用 v2
v1 = mutate(lambda p: p.__setitem__("input_version", "presales-case-input/v1"))
result = normalize(v1)
check("v1 payload → unsupported_version", codes(result) == ["unsupported_version"], f"实际错误码={codes(result)}")
for field in ("业务模式", "品类", "痛点", "希望解决的问题", "主题", "品牌名称"):
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

# 4c. 公司名称是选填（2026-11-13）：照收进 case_fields；旧名「公司名」按「公司名称」收
result = normalize(mutate(lambda p: p["case"].update({"公司名称": "优酷信息技术（北京）有限公司"})))
check("公司名称 → 通过并进 case_fields",
      result["ok"] and not result["warnings"]
      and result["normalized"]["case_fields"].get("公司名称") == "优酷信息技术（北京）有限公司",
      json.dumps(result.get("errors") or result.get("warnings"), ensure_ascii=False))

# 4d. 补充内容是多文件上传（3.17.0）：表格取非品牌查询，文本按段落，PDF 和图片交给 agent 读
import tempfile  # noqa: E402
import zipfile  # noqa: E402

import read_supplement  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="supplement-e2e-"))
(tmp / "gsc-queries.csv").write_text("Top queries,Clicks,Impressions\nbest chinese drama app,12,340\n"
                                     "youku thai sub,40,900\nwhere to watch thai bl series free,3,120\n", encoding="utf-8")
with zipfile.ZipFile(tmp / "semrush-keywords.xlsx", "w") as z:
    z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
               '<sheet name="Organic" sheetId="1" r:id="rId1"/></sheets></workbook>')
    z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
    z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
               '<row r="1"><c r="A1" t="inlineStr"><is><t>Keyword</t></is></c><c r="B1" t="inlineStr"><is><t>Search Volume</t></is></c></row>'
               '<row r="2"><c r="A2" t="inlineStr"><is><t>asian drama streaming with english subtitles</t></is></c><c r="B2"><v>1900</v></c></row>'
               '</sheetData></worksheet>')
with zipfile.ZipFile(tmp / "sales-faq.docx", "w") as z:
    z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Can I download episodes to watch offline on a plane?</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Is there a family plan for 4 screens?</w:t></w:r></w:p></w:body></w:document>')
(tmp / "insights.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
(tmp / "bing-ai-performance.pdf").write_bytes(b"%PDF-1.4\n")
upload = ["gsc-queries.csv", "semrush-keywords.xlsx", "sales-faq.docx", "insights.png", "bing-ai-performance.pdf"]
result = normalize(mutate(lambda p: p["case"].__setitem__("补充内容", upload)), base_dir=tmp)
files = (result.get("normalized") or {}).get("supplement_files") or []
check("补充内容传 5 个文件（相对路径）→ 通过，按 JSON 所在目录解析成绝对路径，case_fields 记文件名",
      result["ok"] and files == [str((tmp / f).resolve()) for f in upload]
      and result["normalized"]["case_fields"].get("补充内容 2") == "semrush-keywords.xlsx",
      json.dumps(result.get("errors") or [Path(f).name for f in files], ensure_ascii=False))
sigs, summ = read_supplement.read_files([Path(f) for f in files], ["YOUKU", "优酷"])
by = {}
for sig in sigs:
    by.setdefault(sig["来源类型"], []).append(sig)
check("补充内容读文件：GSC 去掉品牌查询、展示写进出处；Semrush 量进月搜索量；docx 按段落；PNG、PDF 列给 agent",
      [x["原话"] for x in by.get("GSC", [])] == ["best chinese drama app", "where to watch thai bl series free"]
      and summ["brand_queries_dropped"] == 1 and "展示 340" in by["GSC"][0]["出处"]
      and by.get("Semrush", [{}])[0].get("月搜索量") == "1900"
      and len(by.get("品牌方资料", [])) == 2 and by["品牌方资料"][0]["出处"] == "补充内容：sales-faq.docx 第 1 段"
      and [Path(x).name for x in summ["to_read"]] == ["insights.png", "bing-ai-performance.pdf"] and not summ["failed"],
      json.dumps({"sources": {k: len(v) for k, v in by.items()}, "files": summ["files"],
                  "dropped": summ["brand_queries_dropped"]}, ensure_ascii=False))
big = tmp / "too-big.csv"
with big.open("wb") as f:
    f.truncate(21 * 1024 * 1024)
for name, value, want in (
        ("传字符串（旧文本框写法）", "泰国站今年主推独播剧", "invalid_type"),
        ("超 15 个文件", [upload[0]] * 16, "too_many_files"),
        ("格式不支持", ["setup.exe"], "unsupported_file_type"),
        ("文件不存在", ["missing.csv"], "file_not_found"),
        ("单个超 20 MB", ["too-big.csv"], "file_too_large")):
    result = normalize(mutate(lambda p, v=value: p["case"].__setitem__("补充内容", v)), base_dir=tmp)
    check(f"补充内容{name} → {want}", want in codes(result), f"实际错误码={codes(result)}")
result = normalize(mutate(lambda p: p["case"].__setitem__("公司名", "优酷")))
check("旧名「公司名」→ 按「公司名称」收，renamed_field 告警",
      result["ok"] and result["normalized"]["case_fields"].get("公司名称") == "优酷"
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
result = normalize(mutate(lambda p: p["case"].__setitem__("官方域名", ["https://youku.tv", "https://th.youku.tv"])))
check("官方域名传数组 → 第一个当主站，其余编号保留",
      result["ok"] and result["normalized"]["official_domain"] == "https://youku.tv"
      and result["normalized"]["case_fields"].get("官方域名 2") == "https://th.youku.tv",
      json.dumps(result.get("errors"), ensure_ascii=False))

# 6b. 同一个站的重复写法去重（PETKIT 的 petkit.com / www.petkit.com；协议、大小写、末尾斜杠）
result = normalize(mutate(lambda p: p["case"].__setitem__(
    "官方域名", ["https://petkit.com", "https://www.petkit.com/", "http://WWW.PETKIT.COM"])))
check("官方域名同一个站的重复写法 → 去重并告警",
      result["ok"] and result["normalized"]["official_domains"] == ["https://petkit.com"]
      and [w["code"] for w in result["warnings"]] == ["duplicate_item", "duplicate_item"],
      json.dumps(result.get("warnings") or result.get("errors"), ensure_ascii=False))
result = normalize(mutate(lambda p: p["case"].__setitem__(
    "官方域名", ["https://www.itiger.com", "https://itiger.com/hk", "https://www.itiger.com/hk/"])))
check("官方域名不同市场路径保留，只去掉同一路径的重复写法",
      result["ok"] and result["normalized"]["official_domains"] == ["https://www.itiger.com", "https://itiger.com/hk"],
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
    ("缺核心目标客户与购买场景", lambda p: p["case"].pop("核心目标客户与购买场景"), "missing_field"),
    ("缺差异化优势", lambda p: p["case"].pop("差异化优势"), "missing_field"),
    ("差异化优势只填「待补充」", lambda p: p["case"].__setitem__("差异化优势", ["待补充"]), "missing_field"),
    ("核心目标客户为空字符串", lambda p: p["case"].__setitem__("核心目标客户与购买场景", ""), "missing_field"),
    # 不依赖样例里竞品的个数和名字（公开仓库的脱敏样例只有 2 个竞品、名字也换了）
    ("竞品 4 个", lambda p: p["case"]["竞品"].extend(
        {"名称": f"Extra {i}", "官网域名": f"https://extra-{i}.example"} for i in range(4 - len(p["case"]["竞品"]))),
     "count_out_of_range"),
    ("竞品重名", lambda p: p["case"]["竞品"][1].__setitem__("名称", p["case"]["竞品"][0]["名称"]), "duplicate_item"),
    ("官网不是完整网址", lambda p: p["case"].__setitem__("官方域名", "youku.tv"), "invalid_url"),
    ("竞品带未定义字段", lambda p: p["case"]["竞品"][0].__setitem__("适用主题", [1]), "unknown_field"),
    ("字段名拼错", lambda p: p["case"].__setitem__("业务目的", "x"), "unknown_field"),
    ("options 带已停用的 generation_stage", lambda p: p["options"].__setitem__("generation_stage", "selection"), "unknown_field"),
    ("input_version 缺失", lambda p: p.pop("input_version"), "invalid_enum"),
    ("核心目标客户重复", lambda p: p["case"]["核心目标客户与购买场景"].append(p["case"]["核心目标客户与购买场景"][0]), "duplicate_item"),
]
# 语言以表单选的为准，不设白名单（2026-11-12）：法语、日语照收。
for loc in ("fr", "ja"):
    result = normalize(mutate(lambda p, loc=loc: p["options"].__setitem__("locale", loc)))
    check(f"任意语言照收：{loc}", result["ok"] and result["normalized"]["locale"] == loc, json.dumps(result["errors"], ensure_ascii=False))

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
report.parent.mkdir(exist_ok=True)  # 公开仓库不带 reports/，新克隆第一次跑时要建
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
sys.exit(0 if passed == len(rows) else 1)
