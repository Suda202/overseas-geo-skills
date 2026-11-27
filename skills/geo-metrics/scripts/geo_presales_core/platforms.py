"""平台登记表：项目里唯一的一张。

采集（geo-monitoring collect_answers）、正文与引用字段（crawler / citations）、报告展示名、
翻译导出、域名判读、词表挖掘都从这里取平台清单。新增平台只在这里加一行，
再到 geo-monitoring/references/platform-contract.json 登记字段合同。

字段：
- dir：采集目录名 scraper.<dir>，也是 Scrapeless actor 后缀
- label：报告里的英文展示名（report-data 的 meta.platforms 用它）
- label_zh：中文展示名（诊断、难度表用）
- answer_field：task_result 里的正文字段
- citation_field：task_result 里的引用字段；None 表示无独立引用字段
- aliases：别处写法（飞书表头、旧数据），只用于把展示名反查回目录名
"""
from __future__ import annotations

PLATFORM_REGISTRY: list[dict] = [
    {"dir": "chatgpt", "label": "ChatGPT", "label_zh": "ChatGPT",
     "answer_field": "result_text", "citation_field": "content_references", "aliases": []},
    {"dir": "perplexity", "label": "Perplexity", "label_zh": "Perplexity",
     "answer_field": "result_text", "citation_field": "web_results", "aliases": []},
    {"dir": "copilot", "label": "Copilot", "label_zh": "Copilot",
     "answer_field": "result_text", "citation_field": "citations", "aliases": ["Microsoft Copilot"]},
    {"dir": "gemini", "label": "Gemini", "label_zh": "Gemini",
     "answer_field": "result_text", "citation_field": "citations", "aliases": []},
    {"dir": "aimode", "label": "AI Mode", "label_zh": "AI 模式",
     "answer_field": "result_text", "citation_field": "citations", "aliases": ["Google AI Mode"]},
    {"dir": "overview", "label": "AIO", "label_zh": "AI 概览",
     "answer_field": "content", "citation_field": "source",
     "aliases": ["Google AI Overviews", "Google AI Overview", "AI Overview"]},
    {"dir": "grok", "label": "Grok", "label_zh": "Grok",
     "answer_field": "full_response", "citation_field": "footnotes", "aliases": []},
    {"dir": "alexa", "label": "Alexa", "label_zh": "Alexa",
     "answer_field": "md_text", "citation_field": "references", "aliases": []},
    {"dir": "bingaimode", "label": "Bing AI Mode", "label_zh": "Bing AI 模式",
     "answer_field": "content_md", "citation_field": "sources", "aliases": ["Bing"]},
]

# 只有展示名、不经 Scrapeless 采集的平台（国内数据），报告遇到这些目录时用
EXTRA_LABELS = {"doubao": "豆包", "deepseek": "DeepSeek"}

ALL_PLATFORM_DIRS: list[str] = [p["dir"] for p in PLATFORM_REGISTRY]
ANSWER_FIELDS: dict[str, str] = {p["dir"]: p["answer_field"] for p in PLATFORM_REGISTRY}
CITATION_FIELDS: dict[str, str] = {p["dir"]: p["citation_field"]
                                   for p in PLATFORM_REGISTRY if p["citation_field"]}
LABELS: dict[str, str] = {**{p["dir"]: p["label"] for p in PLATFORM_REGISTRY}, **EXTRA_LABELS}
LABELS_ZH: dict[str, str] = {p["dir"]: p["label_zh"] for p in PLATFORM_REGISTRY}
LABEL_TO_DIR: dict[str, str] = {}
for _p in PLATFORM_REGISTRY:
    for _name in [_p["label"], *_p["aliases"]]:
        LABEL_TO_DIR[_name] = _p["dir"]
