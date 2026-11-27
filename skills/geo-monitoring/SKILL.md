---
name: geo-monitoring
description: Use when collecting GEO answers on a Prompt set — the 3-run quality trial per Prompt on each monitored platform, the formal Before baseline (7 runs per query × platform × country × language), daily or periodic collection and re-running failed cells — when checking whether a raw collection directory is trustworthy before any metric (field-layer mixing, lost reference definitions, empty citation fields, failed answers, unregistered platforms). Owns the single collector (scripts/collect_answers.py, also used by the presales pipeline and the selection research pre-run), the per-platform field contract and the crawl integrity check. Do not use for researching, writing, adding, merging, picking or locking Prompts (geo-prompt-selection-builder and the client Base), for the presales diagnosis report or the after-sales baseline HTML report (geo-presales-report-builder), for defining metric calibers or brand recognition (geo-metrics), or for diagnosing why the brand underperforms and deciding optimisation actions (geo-gap-diagnosis).
metadata:
  author: Overseas GEO Project
  version: "2.2.0"
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

- 采集：`scripts/collect_answers.py`，项目唯一采集实现，9 个平台（ChatGPT、Perplexity、Copilot、Gemini、Google AI Mode、Google AI Overview、Grok、Alexa、Bing AI Mode；`--platforms all`）；售前 pipeline 和选词研究预跑也调它。跑之前设 `no_proxy=api.scrapeless.com`（本机代理会掐断 Python 的 HTTPS 握手）；失败格加 `--retry-unrecoverable` 才会重采。各平台字段合同在 `references/platform-contract.json`，新增平台在这里登记。
- 采集完整性：`scripts/audit_crawl_integrity.py`，算任何指标前先过；退出码、缺陷怎么处理见 [crawl-integrity.md](references/crawl-integrity.md)。
- 试跑读数：每道题答案点了几个品牌用 geo-metrics 的 `scripts/trial_brand_count.py`（2026-11-18 迁走，统计归 geo-metrics）；`scripts/changeability_domains.py`（可改变性：默认只优化官网时改官网能不能改变这道题，规则见 [changeability-and-order.md](references/changeability-and-order.md)），用法见脚本开头说明。引用来源类别、域名榜、逐题官网引用份额和引用率用 geo-metrics 的 `scripts/citation_sources.py`，不要自己另写统计脚本：它带未判读门禁，未判读引用超过 5% 会停下列出待判域名。
- 基线报告：2026-11-20 起和售前报告是同一套 HTML，归 `geo-presales-report-builder`（`scripts/prepare_baseline.py`，见它的 references/baseline-report.md）。本 skill 只交出各轮采集目录和完整性检查结果。

## 交给内容团队

试跑或基线读数出来以后，缺口诊断、原因判断和优化动作归 `geo-gap-diagnosis`：它读本 skill 的采集目录和完整性检查结果，产出优化机会诊断表。本 skill 只负责把题按约定次数跑出来、查采集完整；query fan-out 和延伸问题的读法留在 [gap-cause-action-table.md](references/gap-cause-action-table.md)（**ChatGPT 的子查询形态随 `task_result.model` 变化：`gpt-6` 起只有一条关键词堆叠式宽查询、不带 `site:`，检索层域名榜要改从 `search_result` 算，两代读数不可比**）。

分工固定：我们根据监测数据定位缺口和原因，内容团队执行动作（写页面、第三方引用、发布到客户站点），监测和诊断都不产出内容本身。

**采集强制联网**：`collect_answers.py` 默认 `web_search=true`，Scrapeless 文档写明这会让 ChatGPT 执行搜索，2026-11-16 实测 Housebell、路拓两批 ChatGPT 回答 100% 带 `search_result`。所以 ChatGPT 读数是「强制联网」口径，测不到自然联网率；Graphite 2026-08 实测强制搜索会让从不自然联网的题可见度平均偏 20 个点。前后两期必须同一口径才能比。
