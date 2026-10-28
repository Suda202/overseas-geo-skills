#!/usr/bin/env python3
"""Generate complete Dify workflow DSL for GEO Presales Agent A (all-English)."""

import yaml
import json

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

def main({inputs}):
    url = f"{{{base_var}}}/api/v1/tools/{tool_name}"
    {payload_setup}
    last_error = ""
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout={timeout})
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

# Build complete DSL
def build_dsl():
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
    # Output will be completed in next iteration
    print("DSL structure ready, generating nodes...")
