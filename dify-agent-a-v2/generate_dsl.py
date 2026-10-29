#!/usr/bin/env python3
"""Generate complete Dify workflow DSL for GEO Presales Agent A (all-English)."""

import yaml
import json
import ast
import copy
import re
from pathlib import Path

DIFY_PUBLIC_ORIGIN = "http://123.57.162.4"
GEO_TOKEN_PLACEHOLDER = "CHANGE_ME_GEO_ACCESS_TOKEN"
CONFIG_NODE_ID = "1729000000015"
DSL_PATH = Path(__file__).with_name("workflow.dsl.yaml")

# Node IDs (timestamp-style strings)
NODES = {
    "start": "1729000000001",
    "config": "1729000000015",
    "read_skills": "1729000000002",
    "prepare": "1729000000003",
    "web_search": "1729000000004",
    "web_fetch": "1729000000005",
    "llm_research": "1729000000006",
    "write_research": "1729000000007",
    "finalize": "1729000000008",
    "normalize": "1729000000009",
    "llm_bank": "1729000000010",
    "fix_bank": "1729000000016",
    "write_input": "1729000000011",
    "build_bank": "1729000000012",
    "validate": "1729000000013",
    "read_bank": "1729000000017",
    "end": "1729000000014",
}

# Edges (connections between nodes)
EDGES = [
    ("start", "config", "start", "code"),
    ("config", "read_skills", "code", "code"),
    ("read_skills", "prepare", "code", "code"),
    ("prepare", "web_search", "code", "code"),
    ("web_search", "web_fetch", "code", "code"),
    ("web_fetch", "llm_research", "code", "llm"),
    ("llm_research", "write_research", "llm", "code"),
    ("write_research", "finalize", "code", "code"),
    ("finalize", "normalize", "code", "code"),
    ("normalize", "llm_bank", "code", "llm"),
    ("llm_bank", "fix_bank", "llm", "code"),
    ("fix_bank", "write_input", "code", "code"),
    ("write_input", "build_bank", "code", "code"),
    ("build_bank", "validate", "code", "code"),
    ("validate", "read_bank", "code", "code"),
    ("read_bank", "end", "code", "end"),
]

# Python code templates for code nodes
CODE_RETRY_TEMPLATE = '''
import requests
import time

def main({inputs}, geo_api_token):
    headers = {"Authorization": f"Bearer {geo_api_token}"}
    url = f"{{{base_var}}}/api/v1/tools/{tool_name}"
    {payload_setup}
    last_error = ""
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout={timeout})
            result = resp.json()
            if not result.get("ok"):
                return {{"ok": False, "error": result.get("error", "unknown"), {error_defaults}}}
            {success_extract}
            return {{"ok": True, {success_outputs}, "error": ""}}
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = f"attempt {{attempt+1}}/3: {{type(e).__name__}}: {{e}}"
            if attempt < 2:
                time.sleep(2 ** attempt)
        except Exception as e:
            return {{"ok": False, "error": f"{{type(e).__name__}}: {{e}}", {error_defaults}}}
    return {{"ok": False, "error": f"重试 3 次仍失败: {{last_error}}", {error_defaults}}}
'''

# LLM prompts
LLM_RESEARCH_SYSTEM = """你是竞品研究员。根据搜索结果和官网抓取内容，组装一份符合 research-contract 的 research 对象。

结构：
{
  "input_hash": "sha256:...",
  "researched_at": "YYYY-MM-DD",
  "evidence": [{"evidence_id": "EV-001", "url": "...", "title": "...", "source_type": "official" | "independent_review" | "market_report", "published_at": null, "accessed_at": "YYYY-MM-DD", "claims": [...]}],
  "candidates": [{"canonical_name": "...", "official_domain": "...", "aliases": [...], "source": "user_provided", "activity_status": "active", "direct_substitute": true, "same_purchase_set": true, "market_position": "peer" | "challenger" | "leader", "dimensions": {...1-5 scores}, "evidence_bindings": {...}, "evidence_ids": [...]}]
}

关键规则：
- 每个候选的 evidence_bindings.* 只能引用本候选 evidence_ids 里的 ID
- source_type 只能是 official / independent_review / market_report
- dimensions 各项 1-5 分整数

只输出 JSON 对象，不要任何其他文字。"""

LLM_RESEARCH_USER = """Brand: {{#start.brand_name#}}
Official domain: {{#start.official_domain#}}
Topics: {{#start.topics#}}
Market: {{#start.regions#}}
Competitors: {{#prepare.competitors_parsed#}}

Search results:
{{#web_search.search_results#}}

Fetch results:
{{#web_fetch.fetch_results#}}

Generate the research object, candidates array in the order of competitors_parsed."""

LLM_BANK_SYSTEM = """你是 GEO 题库生成专家。生成符合 overseas-geo-question-bank/v8 合同的题库输入对象。

## 12 条铁律（必须严格遵守）

1. **topic 必须是英文**（如 "family dietary supplements"）
2. **attribute 命名必须是英文短语**（如 "family suitability and use-case fit"）
3. **source_field 必须是 normalized.case_fields 里真实存在的英文字段名**（如 "pain_points 1"）
4. **source_value 必须逐字复制 case_fields 里的值**
5. **intent_key 必填、唯一、英文蛇形命名**（如 "family_supplement_brand_discovery"）
6. **每道题面必须包含 brands/options/platforms/providers/tools 等候选词**
7. **所有题的 Attribute 标签必须覆盖 attribute_plan 所有 P1**
8. **tags 恰好 3 个默认标签**（Intent: Discovery + Brand Scope: Non-Branded + Prompt Task: X）+ 0 或多个 Attribute 标签
9. **config_meta.quotas 必须包含全部 6 个 Intent**（discovery 阶段只有 Intent: Discovery 大于 0，其他全为 0）
10. **共 6 题**，topic_id 都是 "topic_1"
11. **quality_checks 8 个字段全 true**
12. **每题必填字段**：question_id / topic_id / tags / analysis_type / formal_visibility_eligible / intent_key / user_question / zh_translation / monitoring_prompt / quality_checks

## 输出结构

{
  "attribute_plan": [
    {
      "topic_id": "topic_1",
      "priorities": {
        "P1": [{"attribute": "...", "source_field": "...", "source_value": "...", "decision_reason": "..."}],
        "P2": [...],
        "P3": [...]
      },
      "excluded": []
    }
  ],
  "questions": [
    {
      "question_id": "kb-t1-q1",
      "topic_id": "topic_1",
      "tags": ["Intent: Discovery", "Brand Scope: Non-Branded", "Prompt Task: Discovery", "Attribute: ..."],
      "analysis_type": "visibility,sentiment",
      "formal_visibility_eligible": true,
      "intent_key": "family_supplement_brand_discovery",
      "user_question": "Which family dietary supplement brands ...?",
      "zh_translation": "哪些家庭营养补充剂品牌...？",
      "monitoring_prompt": "Which family dietary supplement brands ...?",
      "quality_checks": {
        "case_grounded": true,
        "buyer_realistic": true,
        "independent_decision": true,
        "single_primary_task": true,
        "category_clear": true,
        "neutral": true,
        "no_brand_leakage": true,
        "translation_equivalent": true
      }
    }
  ],
  "config_meta": {
    "expected_total": 6,
    "quotas": {
      "intent_tags": {"Intent: Discovery": 6, "Intent: Competitor": 0, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 0, "Intent: Category Awareness": 0},
      "per_topic": {"Intent: Discovery": 6, "Intent: Competitor": 0, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 0, "Intent: Category Awareness": 0},
      "topic_overrides": {}
    },
    "generation_stage": "discovery",
    "locale": "en"
  }
}

只输出 JSON 对象，不要任何其他文字。"""

LLM_BANK_USER = """Normalized Case:
{{#normalize.normalized#}}

Competitor selection:
{{#finalize.selection#}}

Brand: {{#start.brand_name#}}
Topics: {{#start.topics#}}
Market: {{#start.regions#}}

Generate the question bank input object. Requirements:
- 6 questions, all Discovery intent, topic_id = "topic_1"
- All user_question must contain candidate words like brands / options / platforms
- intent_key must be unique, use: family_supplement_brand_discovery / family_supplement_multi_member_fit / family_supplement_quality_safety / family_supplement_selection_guidance / family_supplement_daily_routine_value / family_supplement_broad_options
- attribute names in English
- source_field must reference existing English field names in normalized.case_fields
- source_value must be copied exactly from case_fields values

Output only JSON object, no other text."""

# Deployment constants and DSL transformation helpers
DIFY_PUBLIC_ORIGIN = "http://123.57.162.4"
GEO_TOKEN_PLACEHOLDER = "CHANGE_ME_GEO_ACCESS_TOKEN"
CONFIG_NODE_ID = "1729000000015"
DSL_PATH = Path(__file__).with_name("workflow.dsl.yaml")


def _is_request_post_call(node) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "requests"
        and node.func.attr == "post"
    )


def _request_post_calls(code: str):
    return [
        node for node in ast.walk(ast.parse(code))
        if _is_request_post_call(node)
    ]


def _validate_request_headers(code: str, title: str) -> None:
    calls = _request_post_calls(code)
    if not calls:
        raise ValueError(f"{title}: no requests.post call found")
    for call in calls:
        if not any(keyword.arg == "headers" for keyword in call.keywords):
            raise ValueError(f"{title}: requests.post is missing headers")


def _add_token_argument(code: str) -> str:
    if re.search(r"(?m)^def main\(.*\bgeo_api_token\b.*\):", code):
        return code
    return re.sub(
        r"(?m)^def main\(([^)]*)\):$",
        lambda match: (
            "def main(geo_api_token):"
            if not match.group(1).strip()
            else "def main({}, geo_api_token):".format(match.group(1))
        ),
        code,
        count=1,
    )


def _ensure_headers_variable(code: str) -> str:
    def move_header_after_docstring(match):
        return match.group(1) + match.group(3) + match.group(2)

    code = re.sub(
        r"(?s)^(def main\([^\n]*\):\n)(    headers = \{\"Authorization\": f\"Bearer \{geo_api_token\}\"\}\n)((?:[ \t]*(?:\"\"\"|''')(?:.|\n)*?(?:\"\"\"|''')[ \t]*\n)?)",
        move_header_after_docstring,
        code,
        count=1,
    )
    if 'headers = {"Authorization": f"Bearer {geo_api_token}"}' in code:
        return code
    return re.sub(
        r"(?s)^(def main\([^\n]*\):\n)((?:[ \t]*(?:\"\"\"|''')(?:.|\n)*?(?:\"\"\"|''')[ \t]*\n)?)",
        lambda match: (
            match.group(1)
            + match.group(2)
            + '    headers = {"Authorization": f"Bearer {geo_api_token}"}\n'
        ),
        code,
        count=1,
    )


def _add_headers_to_requests_post(code: str) -> str:
    calls = _request_post_calls(code)
    if calls and all(
        any(keyword.arg == "headers" for keyword in call.keywords)
        for call in calls
    ):
        return code
    code = re.sub(
        r"(requests\.post\([^)]*?json=payload,\s*)timeout=",
        r"\1headers=headers, timeout=",
        code,
    )
    def add_multiline_header(match):
        indentation = match.group(1).lstrip("\r\n")
        return f",\n{indentation}headers=headers,\n{indentation}timeout="

    code = re.sub(r",(\s*\n\s*)timeout=", add_multiline_header, code)
    return code


def _ensure_code_node_token_input(node: dict) -> None:
    data = node["data"]
    variables = data.setdefault("variables", [])
    if not any(variable.get("variable") == "geo_api_token" for variable in variables):
        variables.append({
            "value_selector": [CONFIG_NODE_ID, "geo_api_token"],
            "variable": "geo_api_token",
        })


def apply_deployment_updates(dsl: dict) -> dict:
    result = copy.deepcopy(dsl)
    workflow = result["workflow"]
    env_variables = workflow.setdefault("environment_variables", [])
    env_by_name = {item["name"]: item for item in env_variables}

    for name, value, description in (
        ("biz_api_base", DIFY_PUBLIC_ORIGIN, "GEO 业务工具服务端基础 URL"),
        ("search_api_base", DIFY_PUBLIC_ORIGIN, "GEO 联网工具服务端基础 URL"),
    ):
        if name in env_by_name:
            env_by_name[name]["value"] = value
            env_by_name[name]["description"] = description

    if "geo_api_token" not in env_by_name:
        env_variables.append({
            "description": "GEO API Bearer Token（请在 Dify 环境变量中填写真实值）",
            "id": "a1b2c3d4-0003-4000-8000-000000000003",
            "name": "geo_api_token",
            "selector": ["env", "geo_api_token"],
            "value": GEO_TOKEN_PLACEHOLDER,
            "value_type": "string",
        })
    else:
        token = env_by_name["geo_api_token"]
        token["description"] = "GEO API Bearer Token（请在 Dify 环境变量中填写真实值）"
        token["selector"] = ["env", "geo_api_token"]
        token["value_type"] = "string"
        token.setdefault("id", "a1b2c3d4-0003-4000-8000-000000000003")
        token.setdefault("value", GEO_TOKEN_PLACEHOLDER)

    nodes = workflow["graph"]["nodes"]
    config = next(node for node in nodes if node["id"] == CONFIG_NODE_ID)
    config_data = config["data"]
    config_data["code"] = (
        "def main(biz_api_base: str, search_api_base: str, geo_api_token: str):\n"
        "    return {\n"
        '        "biz_api_base": biz_api_base,\n'
        '        "search_api_base": search_api_base,\n'
        '        "geo_api_token": geo_api_token,\n'
        "    }"
    )
    config_data["outputs"]["geo_api_token"] = {"children": None, "type": "string"}
    config_data["variables"] = [
        {"value_selector": ["env", name], "variable": name}
        for name in ("biz_api_base", "search_api_base", "geo_api_token")
    ]

    for node in nodes:
        data = node.get("data") or {}
        code = data.get("code", "")
        if "requests.post" not in code:
            continue
        title = data.get("title", node["id"])
        code = _add_token_argument(code)
        code = _ensure_headers_variable(code)
        code = _add_headers_to_requests_post(code)
        compile(code, f"<{title}>", "exec")
        _validate_request_headers(code, title)
        data["code"] = code
        _ensure_code_node_token_input(node)

    return result


def build_dsl() -> dict:
    """Apply the canonical deployment contract to the maintained workflow template."""
    return apply_deployment_updates(yaml.safe_load(DSL_PATH.read_text(encoding="utf-8")))


# Build complete DSL
def _build_legacy_skeleton_dsl():
    dsl = {
        "app": {
            "description": "GEO Presales Agent A - Case building, competitor research, question bank generation (all-English)",
            "icon": "🔍",
            "icon_background": "#FFEAD5",
            "mode": "workflow",
            "name": "GEO Presales Agent A - English",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": "0.6.0",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [
                {
                    "description": "GEO business tools API base URL",
                    "id": "a1b2c3d4-0001-4000-8000-000000000001",
                    "name": "biz_api_base",
                    "selector": ["env", "biz_api_base"],
                    "value": "https://redhead-appliance-manchester-contracting.trycloudflare.com",
                    "value_type": "string",
                },
                {
                    "description": "GEO search tools API base URL",
                    "id": "a1b2c3d4-0002-4000-8000-000000000002",
                    "name": "search_api_base",
                    "selector": ["env", "search_api_base"],
                    "value": "https://soldiers-connected-naples-rebates.trycloudflare.com",
                    "value_type": "string",
                },
            ],
            "features": {
                "file_upload": {"enabled": False},
                "opening_statement": "",
                "retriever_resource": {"enabled": True},
                "sensitive_word_avoidance": {"enabled": False},
                "speech_to_text": {"enabled": False},
                "suggested_questions": [],
                "suggested_questions_after_answer": {"enabled": False},
                "text_to_speech": {"enabled": False},
            },
            "graph": {
                "edges": [],
                "nodes": [],
                "viewport": {"x": 0, "y": 0, "zoom": 0.5},
            },
            "rag_pipeline_variables": [],
        },
    }

    # Build edges
    for i, (src, tgt, src_type, tgt_type) in enumerate(EDGES):
        dsl["workflow"]["graph"]["edges"].append({
            "data": {"isInIteration": False, "isInLoop": False, "sourceType": src_type, "targetType": tgt_type},
            "id": f"edge-{src}-{tgt}",
            "source": NODES[src],
            "sourceHandle": "source",
            "target": NODES[tgt],
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
        })

    # Build nodes
    # ... (I'll generate all 16 nodes in the next step)

    return dsl

if __name__ == "__main__":
    dsl = build_dsl()
    DSL_PATH.write_text(
        yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Updated {DSL_PATH}")
