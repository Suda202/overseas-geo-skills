# 跨 Skill 共享：意图类型规范映射表

本文件是售前 skill 家族的唯一权威词表。消费方共五个：geo-prompt-selection-builder / geo-presales-report-editor / geo-presales-report-audit / geo-presales-report-builder / geo-presales-sentiment-judge，各自的"开始前读取"均指向本文件。各 skill 内部不得另行定义同概念的别名。

**命名**：这个维度对客叫「意图类型」（2026-11-06 Suda 定；2026-10-22 至 11-06 叫「提示词类型」，更早叫「诊断意图 / 意图」）。英文仍叫 Prompt Type：售前题库标签 `Prompt Type: …`，售后题库 JSON 字段 `prompt_type`，都不改；对客多维表格字段「意图类型」（旧 Base 的「提示词类型」照认）。上传 CSV 列 `diagnosis_intent` 和后端字段 `diagnostic_intent` 是与后端的接口约定，不改。原「Prompt Task」买家任务标签层已删除。旧题库不迁移。

## 完整映射

选词的意图类型共八类：发现、问题解决、评估、对比、替代、验证、交易、售后，定义见选词 selection-rules.md → 5「意图类型：八类」。八类售前、售后都能用：线上售前诊断目前默认只出发现题，线下跑售前诊断或做售后时按需出其他类型（2026-11-09）。下表另含历史数据兼容映射：Verification（旧的 yes/no 能力核查）和 Accuracy 的旧值仅用于读取历史数据；能力核查现归评估，准确性题在题库之外，不生成上传行。

| 题库标签 | 后端 diagnostic_intent | 中文客户标签 | 统计指标 | formal_visibility_eligible | 报告模块归属 |
|---|---|---|---|---|---|
| `Prompt Type: Discovery` | `discovery` | 发现 | 提及率、情感 | `true` | M01 数据总览、M02 竞品表现、M03 引用来源、M05 品牌进入、M07 平台一致 |
| `Prompt Type: Alternatives` | `alternatives`（导出直接传此值；后端枚举上线前线上读不到替代题） | 替代 | 提及率、情感 | `false` | 点名一个竞品问替代方案，品牌不是对比的一边、答案是名单；提及率读替代名单里的提及。后端加 `alternatives` 枚举之前，线上报告看不到替代题的提及率，我们自己的基线报告照算。不点名的替代问法仍是 Discovery |
| `Prompt Type: Competitor` | `competitor` | 对比 | 胜负、情感（线上目前没有统计胜率，本地基线照算） | `false` | M02 竞品表现（决胜与情感） |
| `Prompt Type: Evaluation` | `sentiment` | 评估（问本品适不适合、有没有某能力） | 情感 | `false` | M04 品牌表达 |
| `Prompt Type: Trust` | `trust`（后端尚未支持） | 验证（问本品靠不靠谱、口碑、投诉） | 情感 | `false` | 本期不出，不导出上传 CSV |
| `Prompt Type: Information` | `information`（后端尚未支持） | 问题解决 | 引用 | `false` | AI 多给步骤和建议，多数回答不提品牌，提及率基数小，不统计提及率（2026-11-11 Suda 定，推翻 11-06 改看提及率）；看 AI 引用了哪些来源，用来给内容计划找方向 |
| `Prompt Type: Transactional` | `transactional`（后端尚未支持） | 交易（点名本品问哪里买、价格、库存） | 准确性 | `false` | 本期不出，不导出上传 CSV；判什么见下方「准确性怎么判」 |
| `Prompt Type: Support` | `support`（后端尚未支持） | 售后（点名本品问安装、使用、故障、维修、退换） | 准确性 | `false` | 本期不出，不导出上传 CSV；判什么见下方「准确性怎么判」 |
| `Prompt Type: Category Awareness` | `market_perception` | 品类认知 | —（M08 自有读法） | `true` | M08 购买框架（品类认知 / Market Perception）；只用于调研预跑，不进选词题库 |
| `Prompt Type: Accuracy` | `accuracy` | 准确性 | 准确性 | `false` | 无独立模块；作为准确性输入 M05 品牌进入。默认不出，有必要时才出，在题库之外，不上传 |
| `Prompt Type: Verification` | `validation` | 能力核查（旧） | — | `false` | 历史数据兼容；现在问「有没有某能力」归 Evaluation。不要和新的验证类型 Trust 混用 |

**统计指标由意图类型决定，不另设字段。** 每道题统计什么只看上表「统计指标」列，提示词库和题库都不另设分析维度字段。另有两条对所有类型都适用：

- **引用所有类型都统计**（引用份额、引用率、引用来源；线上目前只有引用份额，没有引用率，这次不加，我们本地基线和售前 HTML 照算），按意图类型分开看。售前 HTML 报告的引用模块默认合并全部意图类型，核心洞察的引用份额、引用率只看发现＋替代、和提及率同一批题（2026-11-07）；监测基线 HTML 的「全部类型」仍只合并题面不点名品牌的类型（2026-10-22，`geo-monitoring/scripts/build_baseline_html.py`）。两处口径见 `geo-metrics/references/metric-scope-and-copy-contract.md`「样本范围」。
- **提及只数正文里的品牌**：先去掉引用标记（「([RivalH1][5])」这类脚注、引用卡片标题）再识别，口径同 `geo-metrics/scripts/de_cite_crawl.py` 的 `strip_citations`。正文里写出来的品牌都算提及，包括被当作数据来源点名的（「Source: SRX Property Index」「According to rival-h2.example」）；提及不等于推荐。

**上传列 `question_types` 是过渡字段。** 后端现在按 `question_types` 决定统计什么，只有 `visibility`、`sentiment` 两个值；导出脚本 2026-11-11 起不再导出这一列。目标是后端直接按 `diagnostic_intent` 决定统计哪些指标，上传模板已删掉这一列和 `purchase_intent`、`persona_name`、`scene_name` 三个留空列（旧模板带的照收、忽略）。线上目前没有统计胜率和准确性，这次都不加；引用对所有类型都算，历史数据不回算（研发需求第 4 节，2026-11-11）。在那之前，上表里后端还没有的枚举（替代、验证、问题解决、交易、售后）和准确性指标都要后端先支持。这五个英文值（`alternatives`、`trust`、`information`、`transactional`、`support`）和售后数据看板的「意图类型」筛选已写进研发需求《售前诊断：线上生词改用选词 skill，研发需要改的地方》第 4 节（2026-11-09）。

**准确性怎么判。** 交易、售后和准确性题读的是 AI 说的事实对不对。

- 有品牌方资料（品牌事实核查表）时，对照事实表判对、错。
- 没有品牌方资料时，只能对照官网、官方帮助页、官方店铺页这些公开页面，记 AI 说法和官方公开信息冲突的地方；官方页面没写的记「无法核对」，不进分母。这时报的是「和官方公开信息冲突的回答占比」，不叫准确率。
- 不同平台说法互相矛盾，只当提示，说明这条事实在公开层不清楚，不直接判错。

**上传值和后端内部值是两层，别混用。** 上表「后端 diagnostic_intent」列是后端统计包里存的值；我们上传 CSV 或走接口传入时，`diagnosis_intent` 填的是上传值，由后端自己换成内部值（报告侧的对照在 `geo-presales-report-builder/scripts/build_report_data.py` 的 `CSV_INTENT_MAP`）。两层不同的只有三个：评估传 `evaluation`（内部存 `sentiment`），历史能力核查记录用 `verification`（内部存 `validation`，已不再出），品类认知传 `category_awareness`（内部存 `market_perception`）；发现、对比、准确性两层同名。上传值的全集以售前 validator 的 `V8_CSV_QUESTION_TYPES` 为准。

**历史验证与准确性映射**。旧数据保留 Verification 和 Accuracy 两个值及其独立含义。现在：问「有没有某能力」是评估（Evaluation）；新的「验证」类型（Trust）只问可信度，和旧 Verification 是两回事；零提及不再专门出点名题，按 geo-monitoring/references/trial-and-lock.md「零提及怎么诊断」找原因；准确性题默认不出，我们判断有必要时才出，在题库之外，问句和判定记进品牌事实核查表。

**报告模块按事实来源划分，不按意图类型划分，两者不是一一对应。** 一个模块可以消费多种意图类型的样本（M02 同时用 Discovery 的竞争位置与 Competitor 的决胜结果），一种意图也可能不进任何模块（验证与准确性只作为诊断输入）。上表的模块归属只说明「该意图的样本最终进入哪些模块」，不要把它读成「该意图等于某个模块」。

*重要：`formal_visibility_eligible = true` 表示进入后端可见度处理管线，**不等于**进入正式 Visibility 指标（品牌进入率、平均提及位置、声量、问题机会）。正式 Visibility 指标**只使用 Discovery**；替代的提及率按类型单独看；问题解决不统计提及率。售前报告的主要引用生态只用 Discovery（售前只出发现题）；Competitor 只统计情感并进入独立的 M02 竞品表现；Category Awareness 进入独立的 M08 购买框架。

情绪适用范围与 Discovery 独立判断：后端已标记为 Sentiment 的样本必须进入 M04 品牌表达聚合，不得因为该记录不属于 Discovery 或同时带有其他意图类型而删除；它仍不得进入正式 Visibility。

购物层（Shopping GEO）只在有商品卡展示机会的产品线上统计（开不开由我们按商品属性推理，消费类实体商品开、软件和服务关、工业类试跑后定），和正文提及率分开报：只统计发现、替代两类题；其他类型照常采集、不进汇总。指标是商品卡触发率、商品卡提及率、商品卡平均位置，口径见 `geo-metrics/references/metric-scope-and-copy-contract.md`「购物层指标」。

> **迁移说明**：`Prompt Type: Discovery`、`Prompt Type: Competitor` 等意图类型 Tag 当前作为默认枚举使用，计划迁移为项目自定义 Tags（不再是固定枚举）。迁移完成前，仍以本表为默认对照；迁移后，统计指标和 `formal_visibility_eligible` 的推导规则须在自定义 Tag 的定义文件中重新声明，不得依赖本表题库标签列自动推导。

## 意图类型与旅程阶段

2026-11-06 起选词不设旅程阶段：八类意图类型按买家想完成什么任务判断，已经覆盖旅程阶段要表达的信息。选词矩阵一行只有一种意图类型，同一使用场景几种问法开几行；validator 检查题的类型和所在行一致。题型是否进入本期范围按业务目标和需求证据判断。

Verification、Accuracy 和 Category Awareness 均不进入当前选词题库。旧题库的旅程阶段（三段或八段）和旧类型值保留兼容读取，不迁移历史数据。规则正文见选词 selection-rules.md 第 5、7、8 步。

## 问题类型（后端枚举）

后端问题类型（上传列 `question_types`）现在只有两个值：`visibility`、`sentiment`，是过渡字段，见上文「上传列 `question_types` 是过渡字段」。
- `accuracy` 现在只是 diagnostic_intent 值，不是问题类型；交易、售后要统计准确性，需后端先加这项指标。

## `target_attributes` 来源

Report Editor 的后端输入字段 `target_attributes` 由**后端摄入层**从 v8 Prompt Bank 的 `attribute_plan` 字段和逐题 `Attribute: {attribute}` Tags 自动派生，并补充 `attribute_id`。Prompt Builder 不直接产出 `target_attributes`、`attribute_id` 或独立的逐题 `attributes` 字段。这一派生步骤由后端完成，不属于任何单个 skill 的职责范围。

## 字段名称互查

| 概念 | 收集来源 | Prompt Builder（输入合同） | Report Editor（后端字段） |
|---|---|---|---|
| 多值目标客户 | 《品牌资料收集》「核心目标客户与购买场景」 | `核心目标客户与购买场景 1…n`（按填写顺序） | — |
| 多值差异化优势 | 《品牌资料收集》「差异化优势」 | `差异化优势 1…n` | — |
| 主题 | 不收（Case 输入合同 v2 起） | 选词从矩阵行聚出，写 `config.topics` | `topic_id`（英文 slug） |

## 报告模块代码

| 代码 | 含义 | 事实来源 |
|---|---|---|
| M01 | 数据总览（综合主诊断、跨模块关系与优先级） | M02–M05、M07–M08 |
| M02 | 竞品表现 | `competitor`、`competitor_comparison_summary` |
| M03 | 引用来源 | `citation`、`page_opportunities` |
| M04 | 品牌表达（品牌被认可与被质疑的表达证据） | `brand_expression` |
| M05 | 品牌进入（后端已分档的缺口覆盖哪些需求与阶段） | `category_actions` |
| M06 | 下一步行动 | `action_context` |
| M07 | 平台一致 | `platform_consistency` |
| M08 | 购买框架（品类认知 / Market Perception） | `market_perception_diagnostics` |
| M10 | 最终摘要 | M01–M08 |

模块编号按事实来源分配，与意图类型编号无关。**M09 是未使用的编号**（后端从未定义过该模块，编号从 M08 直接跳到 M10），不是本表遗漏。旧数据的验证、准确性没有对应模块，其历史诊断输入分别进入 M04 与 M01、M05。当前临时验证保存在内部诊断记录中。完整职责与依赖见 `geo-presales-report-editor/references/backend-report-task-contract.md`。
