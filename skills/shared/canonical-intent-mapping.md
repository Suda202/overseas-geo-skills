# 跨 Skill 共享：提示词类型规范映射表

本文件是售前 skill 家族的唯一权威词表。消费方共六个：geo-presales-eval-case-builder / geo-presales-prompt-builder / geo-presales-report-editor / geo-presales-report-audit / geo-presales-report-builder / geo-presales-sentiment-judge，各自的"开始前读取"均指向本文件。各 skill 内部不得另行定义同概念的别名。

**命名（2026-10-22 Suda 定）**：这个维度统一叫「提示词类型」（Prompt Type），原名「诊断意图 / 意图 / Intent」停用。售前题库标签 `Prompt Type: …`，售后题库 JSON 字段 `prompt_type`，对客多维表格字段「提示词类型」。原「Prompt Task」买家任务标签层已删除，不再写。只有两处仍保留旧名，因为它们是与后端的接口约定：上传 CSV 列 `diagnosis_intent` 和后端字段 `diagnostic_intent`。旧题库不迁移。

## 完整映射

下表包含历史数据兼容映射。Verification 和 Accuracy 的旧值仅用于读取历史数据。当前选词的临时验证单独记在内部诊断记录中，不生成题库记录或上传行。

| 题库标签 | 后端 diagnostic_intent | 中文客户标签 | analysis_type | formal_visibility_eligible | 报告模块归属 |
|---|---|---|---|---|---|
| `Prompt Type: Discovery` | `discovery` | 发现（发现类问题） | `visibility,sentiment` | `true` | M01 数据总览、M02 竞品表现、M03 引用来源、M05 品牌进入、M07 平台一致 |
| `Prompt Type: Competitor` | `competitor` | 对比（原「竞品」→「竞品对比」，2026-10-23 简化为「对比」） | `sentiment` | `false` | M02 竞品表现（决胜与情感） |
| `Prompt Type: Alternatives` | `alternatives`（后端尚未支持，接入前需后端加枚举；临时上传按 `competitor` 适配） | 替代（替代类问题） | `sentiment` | `false` | **仅售后**（2026-10-22 从 Competitor 拆出）：点名竞品问替代方案（「[领头竞品] 最好的替代方案」），品牌不是对比的一边、答案是名单，读数是**提及率**（替代方案名单里的提及：5 次里几次被列入、列第几；Suda 2026-10-23 起不再另叫列入率）+ 情感，单独成行报；2026-11-02 起计入提及率考核（Suda 定，推翻 10-23「未定」），formal_visibility_eligible 两种值 validator 都接受；后端加 `alternatives` 枚举并计入可见度之前，线上报告看不到替代题的提及率，我们自己的基线报告照算；列入≠推荐。不点名的替代问法仍是 Discovery。2026-10-22 前的题库维持 Competitor 不迁移 |
| `Prompt Type: Verification` | `validation` | 验证（验证类问题） | —（空） | `false` | 历史数据兼容；当前临时验证只存内部诊断记录 |
| `Prompt Type: Accuracy` | `accuracy` | 准确性（准确性类问题） | `accuracy` | `false` | 无独立模块；作为准确性输入 M05 品牌进入 |
| `Prompt Type: Evaluation` | `sentiment` | 评价（评价类问题） | `sentiment` | `false` | M04 品牌表达 |
| `Prompt Type: Category Awareness` | `market_perception` | 品类认知（品类认知类问题） | —（空） | `true` | M08 购买框架（品类认知 / Market Perception） |
| `Prompt Type: Information` | `information`（后端尚未支持，接入前需后端加枚举） | 问题解决 | `citation` | `false` | **仅售后**（Suda 2026-10-19; client label renamed from 信息 and scope narrowed to problem-solving on 2026-10-26）：买家的问题解决型问题，AI 给建议不列候选，只统计品牌官网是否被引用；售前不使用 |

**上传值和后端内部值是两层，别混用（2026-10-29）。** 上表「后端 diagnostic_intent」列是后端统计包里存的值；我们上传 CSV 或走接口传入时，`diagnosis_intent` 填的是上传值，由后端自己换成内部值（报告侧的对照在 `geo-presales-report-builder/scripts/build_report_data.py` 的 `CSV_INTENT_MAP`）。两层不同的只有三个：评价传 `evaluation`（内部存 `sentiment`），历史验证记录用 `verification`（内部存 `validation`，当前临时验证不上传），品类认知传 `category_awareness`（内部存 `market_perception`）；发现、对比、准确性两层同名。上传值的全集以售前 validator 的 `V8_CSV_QUESTION_TYPES` 为准。评价题的 `analysis_type` / `question_types` 是 `sentiment`，和内部值同名，但它是另一个字段。

**历史验证与准确性映射**。旧数据保留 Verification 和 Accuracy 两个值及其独立含义。当前选词仅在有效发现题零提及时按需做临时点名验证，记录在题库之外。事实错误进入品牌事实核查表。触发、记录与判读要求见选词 selection-rules.md 第 8 步。

**报告模块按事实来源划分，不按提示词类型划分，两者不是一一对应。** 一个模块可以消费多种提示词类型的样本（M02 同时用 Discovery 的竞争位置与 Competitor 的决胜结果），一种意图也可能不进任何模块（验证与准确性只作为诊断输入）。下表的模块归属只说明「该意图的样本最终进入哪些模块」，不要把它读成「该意图等于某个模块」。

*重要：`formal_visibility_eligible = true` 表示进入后端可见度处理管线，**不等于**进入正式 Visibility 指标（品牌进入率、平均提及位置、声量、问题机会）。报告侧正式 Visibility 指标和主要引用生态**只使用 Discovery（`Prompt Type: Discovery`）**；Competitor 只统计情感并进入独立的 M02 竞品表现，不再进入可见度题集；Category Awareness 进入独立的 M08 购买框架。

情绪适用范围与 Discovery 独立判断：后端已标记为 Sentiment 的样本必须进入 M04 品牌表达聚合，不得因为该记录不属于 Discovery 或同时带有其他提示词类型而删除；它仍不得进入正式 Visibility。

购物层（Shopping GEO）同样两条独立判定：购物触发率用全部有效回答、按提示词类型拆开报；购物可见度、商品曝光、商家份额只用 Discovery。口径见 `geo-presales-report-editor/references/metric-scope-and-copy-contract.md`「购物层指标」。

> **迁移说明**：`Prompt Type: Discovery`、`Prompt Type: Competitor` 等提示词类型 Tag 当前作为默认枚举使用，计划迁移为项目自定义 Tags（不再是固定枚举）。迁移完成前，仍以本表为默认对照；迁移后，`analysis_type` 和 `formal_visibility_eligible` 的推导规则须在自定义 Tag 的定义文件中重新声明，不得依赖本表题库标签列自动推导。

## 提示词类型与旅程阶段

旅程阶段按买家处境判断，使用需求认知、方案考虑、购买决策三段。提示词类型按回答任务和读数口径判断。选词矩阵一行只有一种提示词类型，同一购买任务几种问法开几行；阶段按类型取默认值、可以改，validator 检查题的类型和所在行一致，不强制一一映射。

发现题通常出现在方案考虑，比较、评价通常出现在购买决策。具体买家证据优先于这种常见分布。题型是否进入本期范围按业务目标和需求证据判断。

Verification、Accuracy 和 Category Awareness 均不进入当前选词题库。旧题库的阶段和值保留兼容读取，不迁移历史数据。规则正文见选词 selection-rules.md 第 5、7、8 步。

## 问题类型（后端枚举）

后端问题类型只有两个值：`visibility`、`sentiment`。
- `accuracy` 是 diagnostic_intent 值，不是问题类型。
- 任何 intent 的 `analysis_type` 如为 `accuracy`，对应后端问题类型仍按分析处理（当前售前默认配额为 0）。

## `target_attributes` 来源

Report Editor 的后端输入字段 `target_attributes` 由**后端摄入层**从 v8 Prompt Bank 的 `attribute_plan` 字段和逐题 `Attribute: {attribute}` Tags 自动派生，并补充 `attribute_id`。Prompt Builder 不直接产出 `target_attributes`、`attribute_id` 或独立的逐题 `attributes` 字段。这一派生步骤由后端完成，不属于任何单个 skill 的职责范围。

## 字段名称互查

| 概念 | Case Builder（飞书 Base 字段） | Prompt Builder（输入合同） | Report Editor（后端字段） |
|---|---|---|---|
| 多值痛点 | `痛点`（单字段合并，`，`分隔） | `痛点 1…n`（编号兼容，合并单字段也接受） | — |
| 多值使用场景 | `使用场景`（单字段合并） | `使用场景 1…n`（编号兼容） | — |
| 多值产品特性 | `产品特性`（单字段合并） | `产品特性 1…n`（编号兼容） | — |
| 主题 | `主题`（单字段合并，`，`分隔，不标注类型） | `主题 1…n`（编号兼容，括号仅理解提示，不输出） | `topic_id`（英文 slug） |

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

模块编号按事实来源分配，与提示词类型编号无关。**M09 是未使用的编号**（后端从未定义过该模块，编号从 M08 直接跳到 M10），不是本表遗漏。旧数据的验证、准确性没有对应模块，其历史诊断输入分别进入 M04 与 M01、M05。当前临时验证保存在内部诊断记录中。完整职责与依赖见 `geo-presales-report-editor/references/backend-report-task-contract.md`。
