---
name: geo-monitoring
description: Use when collecting GEO answers on a Prompt set — the 3-run quality trial per Prompt on each monitored platform, the formal Before baseline (7 runs per query × platform × country × language), daily or periodic collection and re-running failed cells — when checking whether a raw collection directory is trustworthy before any metric (field-layer mixing, lost reference definitions, empty citation fields, failed answers, unregistered platforms), and when building the baseline HTML report or handing located gaps to the content team. Owns the single collector (scripts/collect_answers.py, also used by the presales pipeline and the selection research pre-run), the per-platform field contract and the crawl integrity check. Do not use for researching, writing, adding, merging, picking or locking Prompts (geo-prompt-selection-builder and the client Base), for the early presales diagnosis report (geo-presales-report-builder), or for defining metric calibers or brand recognition (geo-metrics).
metadata:
  author: Overseas GEO Project
  version: "2.1.0"
---

# GEO Monitoring（监测）

监测只做爬虫的活：把题按约定次数跑出来，查采集完整，再出基线报告、把缺口交给内容团队。写题、改题、挑正式题、锁版都不在这里（选词 `geo-prompt-selection-builder` 和对客确认表）。

## 跑几次

| 场景 | 次数 |
|---|---|
| 试跑 | 每道候选题在每个监测平台 3 次，每次独立会话 |
| 正式基线 | 每个 query × 平台 × 国家 × 语言 7 次 |
| 日常监测 | 发现题每个 query × 平台 × 国家 × 语言每天 1 次；其他类型每月 1 次 |

客户另有约定的按约定跑。某平台在该市场采不到的，不跑这个平台。只计有效观测，失败的一次重跑，不记 0。

## 工具

- 采集：`scripts/collect_answers.py`，项目唯一采集实现，8 个平台；售前 pipeline 和选词研究预跑也调它。跑之前设 `no_proxy=api.scrapeless.com`（本机代理会掐断 Python 的 HTTPS 握手）；失败格加 `--retry-unrecoverable` 才会重采。各平台字段合同在 `references/platform-contract.json`，新增平台在这里登记。
- 采集完整性：`scripts/audit_crawl_integrity.py`，算任何指标前先过；退出码、缺陷怎么处理见 [crawl-integrity.md](references/crawl-integrity.md)。
- 试跑读数：`scripts/trial_brand_count.py`（每道题答案点了几个品牌）、`scripts/changeability_domains.py`（引用前 20 域名的来源结构），用法见脚本开头说明。
- 基线报告：`scripts/build_baseline_html.py`，流程见 [baseline-report.md](references/baseline-report.md)。读数只出 HTML，不写进多维表格。

## 交给内容团队

只在有基线读数之后做：用 [gap-cause-action-table.md](references/gap-cause-action-table.md)，从读数里定位缺口（零提及或低提及、无引用或引用质量低、负面情感或属性认知偏差、答案列表位置靠后、品类认知错位），读提及、引用和同一批采集的 query fan-out（ChatGPT `search_model_queries`、Grok `tool_usages` 的检索词）与延伸问题（Gemini `related_queries`、Grok `follow_up_suggestions`），从表里「可能原因」列挑最可能的原因并写明证据，再列出对应的「对应动作」作为优化方向。**ChatGPT 的子查询形态随 `task_result.model` 变化：`gpt-6` 起只有一条关键词堆叠式宽查询、不带 `site:`，检索层域名榜要改从 `search_result` 算，两代读数不可比**（判据见该表 *ChatGPT 两代形态不同*）。定动作前先找站内最接近的现有页面，有就优先改它；动作也可以是合并重叠页面，或在缺口还说不准时标「继续观察」（规则见该表使用说明第 3 步）。

分工固定：我们根据监测数据填缺口和原因两列，内容团队执行动作（写页面、结构化数据、第三方引用、发布到客户站点），本 skill 不产出内容本身。方向按基线报告的优化顺序排（[baseline-report.md](references/baseline-report.md) → *优化顺序*）。
