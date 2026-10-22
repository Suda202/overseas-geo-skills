---
name: geo-monitoring
description: Use when running or reporting GEO answer monitoring on a locked or candidate Prompt set — candidate baseline, formal Before baseline, periodic collection, collection cadence and re-run triggers, the candidate-baseline HTML report, and handing located gaps to the content team. Do not use for choosing, writing or retiring Prompts (geo-prompt-selection-builder), for the early presales diagnosis report (geo-presales-report-builder), or for defining metric calibers (geo-presales-report-editor core).
metadata:
  author: Overseas GEO Project
  version: "1.0.0"
---

# GEO Monitoring（监测）

## 管什么

监测把题跑出来、算出来、做成报告：候选基线、正式基线、按期采集、统计、基线 HTML 报告和周期报告，以及采集频率和重跑触发。2026-10-22 从选词 skill 拆出：选词决定测哪些题、读数后留哪些题；监测负责跑和算，不改题、不选题。

| 交接 | 内容 |
|---|---|
| 选词 → 监测 | 一份题集（题库 JSON，带 `prompt_type`、`group_role`、市场与语言）＋要跑的平台、次数、频率约定 |
| 监测 → 选词 | 每题每平台的有效读数、基线 HTML 报告；选词据此筛正式题、重排属性优先级、加题并题停题 |
| 监测 → 内容团队 | 缺口诊断与优化方向（见「交给内容团队」） |

不在范围：选题、改题、停题（`geo-prompt-selection-builder`）；指标口径定义（`geo-presales-report-editor` core）；情感规则（`geo-presales-sentiment-judge`）；前置售前诊断报告（`geo-presales-report-builder`）。

## 工具

- 采集：`../geo-presales-report-builder/scripts/collect_answers.py`，项目唯一采集实现，8 个平台。跑之前设 `no_proxy=api.scrapeless.com`（本机代理会掐断 Python 的 HTTPS 握手）；失败格要加 `--retry-unrecoverable` 才会重采。
- 采集完整性：`geo-presales-crawl-integrity`，算任何指标前先过。
- 基线报告：`scripts/build_baseline_html.py`，流程见 [baseline-report.md](references/baseline-report.md)。读数只出 HTML，不写进多维表格（Suda 2026-10-21）。
- 缺口转动作：[gap-cause-action-table.md](references/gap-cause-action-table.md)。

## 候选基线

每道候选题在每个拟监测平台跑 5 次，按目标市场、语言和采集条件，一次跑完或分几天跑都可以；保留原始结果。同一批读数同时检查题目质量（品类与任务是否对得上、歧义、引导、重复）和每个属性的当前差距。改过措辞的题必须重跑，不能沿用旧读数。只计有效观测，失败的一次不算 0。

候选基线结果里，所有题都计入基线读数、主题汇总和被引来源，不分提示词类型（Suda 2026-10-20）。正式题阶段的月均提及率只算发现型。

本品没被提到不是题目不合格的理由，也不是删题的理由；能不能推动是选词侧的可改变性判断。基线只是初始起点，不能证明长期稳定的认知缺口。

## 正式基线与版本

正式题由选词侧选定、客户确认后锁版。措辞没改的正式题沿用候选基线读数作 Before 基线；改过措辞的重跑 5 次。任何新增、删除或改词都是新版本，受影响的市场与题组重建正式基线；保留旧 ID、结果和沿革，新旧题集的汇总序列不拼接，没变的公共题可以单独对比。

没进正式题的候选题停测，不属于交付范围；需要时按月或按季度抽跑。

## 采集频率与重跑

- 发现型：正式基线用候选基线的 5 次读数，之后每周一次或按约定。
- 竞品、品类认知、准确性：在属性池调研阶段采集（每平台 5 次，用来判相对竞品和可改变性），不进候选基线（Suda 2026-10-15）。品类认知、准确性不占正式题名额。竞品题默认在监测层，品牌方选进正式题后每期跑、计入情感、不计月均提及率；措辞没改的沿用调研那轮读数作 Before 基线（Suda 2026-10-20）。
- 评价、信息、价格库存类实验发现题：进候选基线。信息型归实验层，不进月均提及率。
- 以上各类首轮之后只在有触发时重跑：对应属性的优化上线、底层事实变了、点名竞品有大动作、季度复查。不每期跑。
- 品类有明显季节性时（看 Google Trends），基线和重跑避开旺季：节日促销和礼品指南会改变 AI 引用的信源，旺季基线会把季节性和优化效果混在一起；避不开时在报告里写明。
- 对照组发现题用同样的频率；它不是品类认知题，也不自动构成因果对照。

以上是默认值，不是写死的配额。客户另有约定的，记录下来按约定执行。

## 交给内容团队

只在有基线读数之后做：用 [gap-cause-action-table.md](references/gap-cause-action-table.md)，从读数里定位缺口（零提及或低提及、无引用或引用质量低、负面情感或属性认知偏差、答案列表位置靠后、品类认知错位），读提及、引用和同一批采集的 query fan-out（ChatGPT `search_model_queries`、Gemini `related_queries`），从表里「可能原因」列挑最可能的原因并写明证据，再列出对应的「对应动作」作为优化方向。

分工固定：我们根据监测数据填缺口和原因两列，内容团队执行动作（写页面、结构化数据、第三方引用、发布到客户站点），本 skill 不产出内容本身。只凭 Case 调研、没有基线读数时不出这份说明：那时只有机会假设，还没有定位到的缺口。方向按选词侧的最终属性优先级排序（重要性 × 当前差距 × 可改变性，差距逐题读成 AI 认知差距）；共识锁死的方向只留基线，不作为可执行方向交出。
