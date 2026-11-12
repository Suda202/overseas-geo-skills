# 题库 JSON 与 validator 门禁

本文件只写题库 JSON 的字段和 validator 查什么；怎么判、怎么写见 [selection-rules.md](selection-rules.md)，对客表见 [client-facing-base.md](client-facing-base.md)。售前固定配额的 v8 校验器是另一套，本文件的扩展字段不改变它。

## 根结构

```json
{
  "schema_version": "overseas-geo-question-bank/v8",
  "mode": "after-sales-strategic-topics",
  "config": {
    "brand_name": "Example",
    "official_domain": "https://example.com",
    "generation_stage": "selection",
    "evidence_status": "hypothesis",
    "first_party_data": false,
    "topics": [],
    "slices": [],
    "attribute_plan": [],
    "tag_dimensions": [],
    "buyer_quotes": [],
    "collection_config": {"market": "United States", "language": "en"},
    "warning_decisions": []
  },
  "questions": []
}
```

只支持这一种结构：`generation_stage: selection`，矩阵行都带 `prompt_type`。旧题库不迁移、不校验，validator 和导出脚本遇到直接报「不支持的旧结构」并退出（见文末）。

## config

| 字段 | 内容 |
|-|-|
| `evidence_status` | `hypothesis`：整份题集没有任何买家信号；`after_sales_signal`：有公开买家信号撑起。就绪结论按它封顶 |
| `first_party_data` | 有没有用到品牌方一手数据；不是 `true`（含没写）时就绪结论最高 Usable |
| `business_goals` | `{selected: [...], information_named: true / false}`，`selected` 取 发现型可见度 / 竞争定位 / 品牌呈现 / 声誉与信任。线上只出发现，可以不写，validator 按 `{selected: ["发现型可见度"], information_named: false}` 填充；本地品牌方选了其他目标就写全，写了就要写对（W49）。选了哪个目标，对应类型的行要判档（门禁 43） |
| `shopping_cards` | 选填，每条产品线 `{product_line, status: 开 / 关 / 试跑后定, basis}`（selection-rules.md → 1）；没写按关 |
| `topics` | `{topic_id, topic, priority, priority_basis}`；`priority` 是主题优先级，高 / 中 / 低 |
| `slices` | 矩阵行 `{slice_id, topic_id, product_line, market, audience, scene, prompt_type, attributes, priority, priority_basis}`。`scene` 存使用场景；单市场可省 `market`；`prompt_type` 是这一行唯一的意图类型，英文键 Discovery / Information / Evaluation / Competitor / Alternatives / Trust / Transactional / Support；`priority` 是业务优先级，发现行和已开放目标对应类型的行写。本期不出题的行也写，不带 `topic_id`：没开放的类型不写 `priority`、依据写在 `priority_basis`；低档发现行在 `priority_basis` 末尾写「本期不出：……」 |
| `attribute_plan` | 约束条件表 `{attribute, product_line, brand_status, brand_status_basis, vs_competitors, vs_competitors_basis, no_carrier_reason}`：矩阵行或题挂了约束条件就必须有（门禁 67）。`attribute` 是三张表「约束条件」的选项名；`product_line` 选填，品牌只在部分产品线有这项条件时按产品线各写一条，只管那条产品线的题；`brand_status` 有 / 没有 / 待确认，必填（判法见 selection-rules.md 第 3 步），`brand_status_basis` 是出处或查过哪里（只在 JSON，不进对客表；三种取值都必填）；`vs_competitors` 明显优势 / 明显劣势 / 持平 / 未知，不是未知的必须写 `vs_competitors_basis`（公开数字、对哪几家）。不用旧键 `relative_competitor`（旧结构会被拒收） |
| `tag_dimensions` | 跨主题切片标签 `{dimension, basis, values}`：`dimension` 为目标客户 / 使用场景 / 属性（或约束条件）/ 自定义；属性维度和自定义必须列 `values`。不需要就写 `[]`（selection-rules.md → 6「切片标签」） |
| `buyer_quotes` | 需求信号 `{输入编号, 来源类型, 原话, 目标客户, 约束条件, 出处}`：来源类型取 client-facing-base.md → 需求信号的选项（线上 runner 按它查每类采到的信号有没有登记），出处写完整网址或「文件名＋位置」；约束那一列键名就是 `约束条件`（也认 `constraint`、旧键 `约束`），W36 按它核对题面条件。线上必填；不填时 W36、W37 跳过并告警一次 |
| `base_conditions` | 品类本身的基础人群或用途（「养猫家庭」），不算条件 |
| `audience_terms` | 选填，`{目标客户: [自我描述词和暗示词]}`，W39 用；没写时转人工检查 |
| `category_aliases` | 品类叫法变体，只差这些词的两道题不算重复 |
| `audience_inputs` | 收到的需求信号编号，查有没有没用上的 |
| `warning_decisions` | 告警处理记录（见下「告警」） |
| `brand_aliases` | 品牌别名列表（照抄 `normalize_case.py` 的 `brand_aliases`），门禁 12 用它查发现题里有没有写品牌 |
| `collection_config` | `{market, language}`：题库的市场和采集语言，语种门禁（32）按它查 |
| `retired` | 删掉的题 `{question_id, reason}`；线上返修丢题时写，基线报告按它排除 |

## 每道题

| 字段 | 内容 | 对客表 |
|-|-|-|
| `question_id` | 题号 | 编号 |
| `user_question` | 题面，用市场语言写 | 提示词 |
| `zh_translation` | 中文含义 | 中文含义 |
| `topic_id` | 所属主题 | 主题 |
| `region` | 市场 | 市场 |
| `prompt_type` | 同所在行的 `prompt_type`；Verification、Accuracy 报错 | 意图类型 |
| `slice_ref` | 所在矩阵行；目标客户、场景、意图类型、产品线从这一行读 | 所属切片 |
| `attribute_ref` | 主约束条件，取 `attribute_plan` 的选项名（门禁 67）；宽泛品类题留空字符串 | 约束条件（第一个） |
| `constraints` | 题面条件关键词列表（买家说法，不是约束条件选项名），没有写 `[]`；W36、W37 用它核对依据 | — |
| `status` | 待审核 / 需修改 / 已批准 / 正式 | 状态 |

按需才写：`condition_basis`（条件不来自引用的信号时 `{条件: 依据}`）、`evidence_refs`（引用的信号编号）、`audience_implicit`（题面没写提问人、条件已隐含时的理由）、`tags`（只写 `tag_dimensions` 自定义维度的值，其余标签导出时派生）、`brand_weakness`（「品牌在 X 上不如 Y（事实，出处）」，提示词优先级据此降一档；挂的约束条件在 `attribute_plan` 里是明显劣势的不用写，脚本自动降，只有劣势落在约束条件表表达不了的说法上才手写）、`reason_note`（接在出题原因后的一句）。

不写：`priority`（提示词优先级由 `write_prompt_reasons.py` 从行档位、`brand_weakness` 和约束条件表算出）、`journey_stage`、`group_role`、`monitoring_prompt`、`formal_visibility_eligible`、`ai_cognitive_gap`、`lifecycle_status`、`customer_confirmation`、`trial`、`baseline`、`prompt_version`、`purchase_selection`、`assessment_scope`、`intent_key`、`market_decision` 等没有脚本读的字段（3.14.1 起不写）。`journey_stage`、`group_role` 和旧字段名 `persona`、`attribute`、`review_status` 出现就按旧结构拒收（`intent` 在没写 `prompt_type` 时拒收），其余写了也不读。

## 上传 CSV

五列：`query,question_zh,topic,diagnosis_intent,tags`（2026-11-11 起删掉 `question_types`、`purchase_intent`、`persona_name`、`scene_name` 四列，后端按意图类型决定统计什么）。用 `python3 -I scripts/export_upload_csv.py <bank.json> --out <dir> [--topic-label "<主题>=<显示名>"]` 导出，导出后自动跑上传检查：

- 一个市场 × 一条产品线一个文件，每个文件最多 60 条；`diagnosis_intent` 填后端枚举（`discovery`、`alternatives`、`competitor`、`evaluation`），统计口径以 shared/canonical-intent-mapping.md 为准。
- `tags` 写按 `tag_dimensions` 派生的标签，不合格的值不出并打印原因。替代题直接传 `alternatives`，`tags` 不写类型名。
- 问题解决、验证、交易、售后没有后端枚举，不导出并打印题号；停测、需修改的不导出；旧结构题库退出码 2。

交付说明要告诉品牌方：替代题和问题解决题的读数现在只在基线 HTML 报告里看得到。

## validator 门禁

```bash
python3 -I scripts/validate_after_sales_set.py BANK.json
```

最后一行是就绪结论：Not ready（有错误退出码 1，旧题库退出码 2）；Usable（没有错误，但有告警没写处理记录，或 `first_party_data` 不是 true、证据级别是假设）；Ready（没有错误、告警都有记录、有一手数据）。不查锁版、试跑、基线和改版（3.14.1 起）：锁版在对客表上做，正式题额度由 `check_client_base.py` 查。

### 报错（必须改）

| 编号 | 查什么 |
|-|-|
| 2 | 主题名不为空、编号唯一；每道题只归一个存在的主题；题号不重复 |
| 3 | 不能有没有题的主题 |
| 4 | 每道题有主题、市场、类型、中文含义 |
| 8 | 题面完全重复 |
| 12 | 发现题不出现品牌、别名、竞品名；英文市场的发现题还要向 AI 要候选（which / best / recommend 等，其他语言人工查） |
| 32 | 题面用采集语言写：一半以上字符是该语言文字；语种识别（lingua）判为另一门语言且采集语言置信度低于 0.05 |
| 38 | 对比题（Competitor）必须带条件（`constraints` 不为空）；替代题不查 |
| — | `config.slices` 是对象列表；每行有 `slice_id` 且不重复；题的 `slice_ref` 指向存在的行 |
| 43 | 发现行和已开放目标对应类型的行，业务优先级取值合法、写了依据；主题优先级同；题的主题和所在行一致 |
| 47 | 每条产品线 × 每个市场候选题超过 60 道（成本上限） |
| 60 | 每一行的 `prompt_type` 是八类之一 |
| 61 | 题的类型和所在行一致；不接受 Verification、Accuracy |
| 66 | 一个主题只放一种意图类型 |
| 67 | 矩阵行或题挂了约束条件时必须有约束条件表；每条 `brand_status` 必填、取 有 / 没有 / 待确认，写了 `brand_status_basis`；`vs_competitors` 明显优势 / 明显劣势 / 持平 / 未知，不是未知的写了 `vs_competitors_basis`；行的 `attributes` 和题的 `attribute_ref` 都在表里 |
| 68 | 题的主约束（`attribute_ref`）和与选项同名的条件关键词里，没有品牌情况为「没有」或「待确认」的（带 `product_line` 的条目只管那条产品线）；题面其他条件交付前人工核对 |
| — | 品类认知题不进题库 |

### 告警（每条都要写处理记录）

告警以编号开头（`WARNING: [W39] …`）。处理记录写在 `config.warning_decisions`：`{match: "告警里的一段文字", decision: "已改写" / "保留：理由"}` 按子串处理单条；`{gate: "W39", decision: "保留：理由"}` 处理这个编号下全部告警（适合题量、原话未用这类成片出现的）。

| 编号 | 查什么 |
|-|-|
| W8b | 两道题措辞高度相似（只差品类叫法变体的不算） |
| W32 | 题面像关键词串、太长、多个问号、货币和市场不符；疑似另一门语言（置信度 0.05–0.10）；语种检查跳过 |
| W33 | 题没写 `attribute_ref` 字段（宽泛品类题写空字符串） |
| W35 | 收到的需求信号没被任何题或约束条件用上 |
| W36 | 题面带条件却没引用信号也没写 `condition_basis`；题面数字不在引用的原话或依据里；引用了不存在的编号 |
| W37 | 同一主题、类型、约束条件、同样依据的条件：同一个决策问了两次 |
| W39 | 非基础人群的题，题面看不出谁在问（只在写了 `audience_terms` 时查） |
| W46 | 主题优先级和组内最高的业务优先级对不上（改行的档位，不单改主题） |
| W47 | 每条产品线 × 每个市场的候选题不到 30 道（超过 60 是门禁 47） |
| W48 | 业务优先级为高、中的发现行没有题 |
| W49 | `business_goals` 写法不对 |
| W52 | 有发现以外的题，`business_goals` 里却没有对应目标（交易、售后没有对应目标，写了就告警） |
| W53 | 题没写 `slice_ref` |
| W54 | 无条件的发现题：`attribute_ref` 留空且没有条件关键词（只在品牌方点名大词时写） |
| W56 | 有题写了审核状态、有题没写（没写的按待审核） |
| W57 | 约束条件只被未批准的题承载 |
| W59 | 发现主题不够 10 道，处理顺序见 selection-rules.md → 6 硬要求 3；其他类型不设主题下限 |
| W62 | 切片标签维度不合格：维度名不对、没写 `basis`、自定义没登记 `values`；值不到 2 个主题、不到 5 道题、和主题名相同；整个维度就是主题切分轴 |
| W63 | 题上手写的 `tags` 没登记在自定义维度里 |
| W64 | 业务优先级为低的行挂了题（从低档补题属正常，写理由保留） |
| W67 | 相对竞品为明显优势的约束条件没有题测，也没写 `no_carrier_reason` |

### 人工检查（交付前）

- 硬条件：品牌做不到、又没有服务路径的处境没开行，原因记进 notes「没开的格子」（selection-rules.md 第 3 步）。
- 对比题一对一、只用确认过的竞品；条件里要有使用场景，光有预算不算（门禁 38 只查非空）。
- 没写 `audience_terms` 时，人工看非基础人群的题面能不能看出谁在问。
- 题面除主约束外的条件，没用到品牌情况为没有或待确认的约束条件（门禁 68 只查主约束和同名关键词）。
- 试跑复核：品类和任务对不对、有没有歧义、诱导、重复；品牌有没有被提到不是合格标准。
- 多市场：每个市场的差异有依据；平台差异是采集配置，不是题面变体。
- 矩阵和题双向对得上、题放对了主题；对客表写法符合 client-facing-base.md。

### 不支持的旧结构

按旧结构写的历史题库保持原样，不迁移、不校验、不导出。判法以 `validate_after_sales_set.legacy_markers` 为准，主要是：`generation_stage` 不是 `selection`、没有矩阵行、行没写 `prompt_type` 或档位写 P1 / P2 / P3、有旅程阶段或 `group_role`、用旧字段名、`attribute_plan` 是 `{p1, p2, p3}` 或带 `relative_competitor` 等旧键。
