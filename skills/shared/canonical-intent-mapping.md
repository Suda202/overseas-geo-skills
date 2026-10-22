# 跨 Skill 共享：提示词类型规范映射表

本文件是售前 skill 家族的唯一权威词表。消费方共六个：geo-presales-eval-case-builder / geo-presales-prompt-builder / geo-presales-report-editor / geo-presales-report-audit / geo-presales-report-builder / geo-presales-sentiment-judge，各自的"开始前读取"均指向本文件。各 skill 内部不得另行定义同概念的别名。

**命名（2026-10-22 Suda 定）**：这个维度统一叫「提示词类型」（Prompt Type），原名「诊断意图 / 意图 / Intent」停用。售前题库标签 `Prompt Type: …`，售后题库 JSON 字段 `prompt_type`，对客多维表格字段「提示词类型」。原「Prompt Task」买家任务标签层已删除，不再写。只有两处仍保留旧名，因为它们是与后端的接口约定：上传 CSV 列 `diagnosis_intent` 和后端字段 `diagnostic_intent`。旧题库不迁移。

## 完整映射

（下列 Prompt Type: … 标签为当前默认值，后续将迁移为自定义 Tags，枚举不固定）

| 题库标签 | 后端 diagnostic_intent | 中文客户标签 | analysis_type | formal_visibility_eligible | 报告模块归属 |
|---|---|---|---|---|---|
| `Prompt Type: Discovery` | `discovery` | 发现（发现类问题） | `visibility,sentiment` | `true` | M01 数据总览、M02 竞品表现、M03 引用来源、M05 品牌进入、M07 平台一致 |
| `Prompt Type: Competitor` | `competitor` | 竞品（竞品类问题） | `sentiment` | `false` | M02 竞品表现 |
| `Prompt Type: Verification` | `validation` | 验证（验证类问题） | —（空） | `false` | 无独立模块；作为属性诊断输入 M04 品牌表达与 M01 数据总览 |
| `Prompt Type: Accuracy` | `accuracy` | 准确性（准确性类问题） | `accuracy` | `false` | 无独立模块；作为准确性输入 M05 品牌进入 |
| `Prompt Type: Evaluation` | `sentiment` | 评价（评价类问题） | `sentiment` | `false` | M04 品牌表达 |
| `Prompt Type: Category Awareness` | `market_perception` | 品类认知（品类认知类问题） | —（空） | `true` | M08 购买框架（品类认知 / Market Perception） |
| `Prompt Type: Information` | `information`（后端尚未支持，接入前需后端加枚举） | 信息（信息类问题） | `citation` | `false` | **仅售后**（Suda 2026-10-19）：买家自己的政策、流程、费用、纠纷问题，AI 给建议不列候选，只统计品牌官网是否被引用；售前不使用 |

**验证与准确性是两种独立的提示词类型（2026-10-16 起，售前售后一致）。** 分界按 AI 错在哪：AI 不知道品牌有这个能力 → 验证；AI 能说出这个事实但说错了 → 准确性。两者都不进可见度指标，都只作诊断输入。Prompt Builder 不做别名转换，题库里写哪个就是哪个。

**报告模块按事实来源划分，不按提示词类型划分，两者不是一一对应。** 一个模块可以消费多种提示词类型的样本（M02 同时用 Discovery 的竞争位置与 Competitor 的决胜结果），一种意图也可能不进任何模块（验证与准确性只作为诊断输入）。下表的模块归属只说明「该意图的样本最终进入哪些模块」，不要把它读成「该意图等于某个模块」。

*重要：`formal_visibility_eligible = true` 表示进入后端可见度处理管线，**不等于**进入正式 Visibility 指标（品牌进入率、平均提及位置、声量、问题机会）。报告侧正式 Visibility 指标和主要引用生态**只使用 Discovery（`Prompt Type: Discovery`）**；Competitor 只统计情感并进入独立的 M02 竞品表现，不再进入可见度题集；Category Awareness 进入独立的 M08 购买框架。

情绪适用范围与 Discovery 独立判断：后端已标记为 Sentiment 的样本必须进入 M04 品牌表达聚合，不得因为该记录不属于 Discovery 或同时带有其他提示词类型而删除；它仍不得进入正式 Visibility。

购物层（Shopping GEO）同样两条独立判定：购物触发率用全部有效回答、按提示词类型拆开报；购物可见度、商品曝光、商家份额只用 Discovery。口径见 `geo-presales-report-editor/references/metric-scope-and-copy-contract.md`「购物层指标」。

> **迁移说明**：`Prompt Type: Discovery`、`Prompt Type: Competitor` 等提示词类型 Tag 当前作为默认枚举使用，计划迁移为项目自定义 Tags（不再是固定枚举）。迁移完成前，仍以本表为默认对照；迁移后，`analysis_type` 和 `formal_visibility_eligible` 的推导规则须在自定义 Tag 的定义文件中重新声明，不得依赖本表题库标签列自动推导。

## 提示词类型 × 旅程阶段：允许组合（售后）

旅程阶段和提示词类型是两条独立的轴，不合并（Suda 2026-10-22，用 Hbrand 76 题交叉验证过：同是「解决问题」阶段，答案是候选名单的为发现、是建议的为信息，这条分界决定指标路由；同是「信息」类型，又横跨解决问题/交易/验证/购后四个阶段，这条展开决定旅程覆盖读数——两个方向都推不出来）。旅程阶段按**买家处境**判，挂在切片和买家原话上；提示词类型按**答案怎么读**判，挂在提示词库上。

**同词不同义，注意「验证」「评估」两处重名**：提示词类型的「验证」＝AI 认不认品牌有这个能力、「评价」＝要 AI 对具名品牌下判断；旅程阶段的「验证」＝买家在查可信度与事实、「评估」＝买家在判断某个具名选项合不合适。对客解释在确认表《使用说明》里写一句即可。

售后 validator 按下表硬校验（源码是 `geo-prompt-selection-builder/scripts/validate_after_sales_set.py` 的 `INTENT_STAGES`；本表只是它的文档镜像，两处必须同步改）：

| 提示词类型 | 允许的旅程阶段 |
|---|---|
| Discovery（发现） | 发现 / 解决问题 / 交易 |
| Category Awareness（品类认知） | 发现 / 解决问题 |
| Competitor（竞品） | 对比 / 替代方案 |
| Evaluation（评价） | 评估 / 验证 |
| Verification（验证） | 验证 / 购后支持 |
| Accuracy（准确性） | 验证 / 购后支持 |
| Information（信息） | 解决问题 / 交易 / 验证 / 购后支持 |

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

模块编号按事实来源分配，与提示词类型编号无关。**M09 是未使用的编号**（后端从未定义过该模块，编号从 M08 直接跳到 M10），不是本表遗漏。验证、准确性没有对应模块：它们只作为诊断输入进入上表模块（验证 → M04 与 M01，准确性 → M05）。完整职责与依赖见 `geo-presales-report-editor/references/backend-report-task-contract.md`。
