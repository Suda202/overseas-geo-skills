---
name: geo-monitoring
description: Use when running or reporting GEO answer monitoring on a locked Prompt set or its candidate trial — the quality trial (3 runs per Prompt on each monitored platform), the formal Before baseline (30 runs per query × platform × country × language), periodic collection, collection cadence and re-run triggers, the baseline HTML report, and handing located gaps to the content team. Do not use for choosing, writing or retiring Prompts (geo-prompt-selection-builder), for the early presales diagnosis report (geo-presales-report-builder), or for defining metric calibers (geo-presales-report-editor core).
metadata:
  author: Overseas GEO Project
  version: "1.4.0"
---

# GEO Monitoring（监测）

## 管什么

监测把题跑出来、算出来、做成报告：试跑采集、正式基线、按期采集、统计、基线 HTML 报告和周期报告，以及采集频率和重跑触发。2026-10-22 从选词 skill 拆出：选词决定测哪些题、读数后留哪些题；监测负责跑和算，不改题、不选题。

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

## 质量试跑

每道候选题在每个监测平台各跑 3 次（某平台异常时该平台补到 5 次封顶），每次独立会话，市场、语言、模式和采集方式固定（Suda 2026-10-23：候选基线取消，试跑从只跑 ChatGPT 改为各平台都跑）。读数只用来查题目质量（品类与任务是否对得上、歧义、引导、重复、同一题各次结果是否一致、各平台是否都答对题）和初判信源壁垒（推荐是否依赖品牌进不去的来源），并作为探索性语境展示给客户；不进任何统计，不填 AI 认知差距，不驱动选词顺序。改过措辞的题重跑，不沿用旧读数。本品没被提到不是题目不合格的理由。某平台在该市场采不了（如香港的 ChatGPT），试跑和正式基线都不含这个平台。

## 正式基线与版本

客户选定正式题并锁版（选中的题在这时置「正式」，其余「停测」，不等基线跑完）后跑正式基线：**每个 query × 平台 × 国家 × 语言 30 次独立运行**（Suda 2026-10-23）。这一轮就是 Before 基线，没有候选读数可沿用。30 次是否分几天跑按项目约定，写进 `collection_config`；没定之前一次跑完，并在报告里写明。只计有效观测，失败的一次不算 0。基线只是初始起点，不能证明长期稳定的认知缺口。

正式基线发现平台异常时，只有语义、品类或平台适配错误才改题：旧题停测、开新题号、生成新版本、记录原因，实质变更请客户重新确认，受影响部分重采。品牌没被推荐、AI Overviews 没触发，都不是题目不合格。

**正式监测开始 2–4 周后复查一次题库**（Suda 2026-10-23，参照 Momentic Atlas）：监测侧把这段时间各题的读数交给选词侧，选词侧只看题目本身——是否切题、各平台是否都答对题、同一题各次结果是否稳定、有无重复、业务上是否仍相关；不合格的按下面的版本规则改或停测。品牌没被提到不是删题或改题的理由。复查之后只在有触发时再动题库。

任何新增、删除或改词都是新版本，受影响的市场与题组重建正式基线（每格 30 次）；保留旧 ID、结果和沿革，新旧题集的汇总序列不拼接，没变的公共题可以单独对比。没进正式题的候选题不采集，不属于交付范围。2026-10-23 前按候选基线采集的旧项目保留原数据和原口径，不迁移。

## 采集频率与重跑

- 发现型：正式基线跑 30 次后，周期采集每周一次或按约定（Suda 2026-10-23）。
- 竞品、品类认知、准确性：在属性池调研阶段采集（各监测平台 3 次试跑，用来判相对竞品和可改变性），不进正式基线（Suda 2026-10-15）。品类认知、准确性不占正式题名额。竞品题默认在监测层，品牌方选进正式题后每期跑、计入情感、不计月均提及率；选进正式题后同样跑 30 次正式基线作 Before 基线（2026-10-23 起不再沿用调研那轮读数）。
- 评价、信息、价格库存类实验发现题：进试跑（各平台 3 次，探索是否值得跑 30 次）；选进正式题后跑 30 次正式基线。信息型归实验层，不进月均提及率。
- 以上各类首轮之后只在有触发时重跑：对应属性的优化上线、底层事实变了、点名竞品有大动作、季度复查。不每期跑。
- 品类有明显季节性时（看 Google Trends），基线和重跑避开旺季：节日促销和礼品指南会改变 AI 引用的信源，旺季基线会把季节性和优化效果混在一起；避不开时在报告里写明。
- 对照组发现题用同样的频率；它不是品类认知题，也不自动构成因果对照。

以上是默认值，不是写死的配额。客户另有约定的，记录下来按约定执行。

## 交给内容团队

只在有基线读数之后做：用 [gap-cause-action-table.md](references/gap-cause-action-table.md)，从读数里定位缺口（零提及或低提及、无引用或引用质量低、负面情感或属性认知偏差、答案列表位置靠后、品类认知错位），读提及、引用和同一批采集的 query fan-out（ChatGPT `search_model_queries`、Gemini `related_queries`），从表里「可能原因」列挑最可能的原因并写明证据，再列出对应的「对应动作」作为优化方向。

分工固定：我们根据监测数据填缺口和原因两列，内容团队执行动作（写页面、结构化数据、第三方引用、发布到客户站点），本 skill 不产出内容本身。只凭 Case 调研、没有基线读数时不出这份说明：那时只有机会假设，还没有定位到的缺口。方向按选词侧的最终属性优先级排序（重要性 × 当前差距 × 可改变性，差距逐题读成 AI 认知差距）；共识锁死的方向只留基线，不作为可执行方向交出。
