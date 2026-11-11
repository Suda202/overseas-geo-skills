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
    "lifecycle_status": "hypothesis",
    "evidence_status": "hypothesis",
    "first_party_data": false,
    "customer_confirmation": {"status": "pending", "scope_status": "pending", "prompt_set_status": "pending"},
    "topics": [],
    "slices": [],
    "attribute_plan": [],
    "tag_dimensions": [],
    "buyer_quotes": [],
    "trial": {"status": "planned", "planned_runs": 3},
    "baseline": {"status": "planned", "planned_runs": 7},
    "warning_decisions": []
  },
  "questions": []
}
```

只支持这一种结构：`generation_stage: selection`，矩阵行都带 `prompt_type`。旧题库不迁移、不校验，validator 和导出脚本遇到直接报「不支持的旧结构」并退出（见文末）。

## config

| 字段 | 内容 |
|-|-|
| `lifecycle_status` | `hypothesis` / `customer_confirmed` / `locked` / `formal_baseline` / `active` |
| `evidence_status` | `hypothesis`：整份题集没有任何买家信号，不能锁版；`after_sales_signal`：有公开买家信号撑起，品牌方确认正式题即可锁版 |
| `first_party_data` | 有没有用到品牌方一手数据；`false` 时就绪结论最高 Usable，不挡锁版 |
| `customer_confirmation` | `scope_status`（试跑前确认业务范围）、`prompt_set_status`（试跑后确认正式题）、`status` |
| `business_goals` | `{selected: [...], information_named: true / false}`，`selected` 取 发现型可见度 / 竞争定位 / 品牌呈现 / 声誉与信任。目前只做发现，可以不写，validator 按 `{selected: ["发现型可见度"], information_named: false}` 填充；写了就要写对（W49）。开放其他目标时恢复必填（type-branches.md） |
| `shopping_cards` | 选填，每条产品线 `{product_line, status: 开 / 关 / 试跑后定, basis}`（selection-rules.md → 1）；没写按关 |
| `topics` | `{topic_id, topic, priority, priority_basis}`；`priority` 是主题优先级，高 / 中 / 低 |
| `slices` | 矩阵行 `{slice_id, topic_id, product_line, market, audience, scene, prompt_type, attributes, priority, priority_basis}`。`scene` 存使用场景；单市场可省 `market`；`prompt_type` 是这一行唯一的意图类型，英文键 Discovery / Information / Evaluation / Competitor / Alternatives / Trust / Transactional / Support；`priority` 是业务优先级，只有发现行写。本期不出题的行也写，不带 `topic_id`：非发现行不写 `priority`、依据写在 `priority_basis`；低档发现行在 `priority_basis` 末尾写「本期不出：……」 |
| `attribute_plan` | 约束条件名单 `{attribute, no_carrier_reason}`，`attribute` 是三张表「约束条件」的选项名 |
| `tag_dimensions` | 跨主题切片标签 `{dimension, basis, values}`：`dimension` 为目标客户 / 使用场景 / 属性（或约束条件）/ 自定义；属性维度和自定义必须列 `values`。不需要就写 `[]`（selection-rules.md → 6「切片标签」） |
| `buyer_quotes` | 需求信号 `{输入编号, 原话, 目标客户, 约束条件}`，约束那一列键名就是 `约束条件`（也认 `constraint`、旧键 `约束`），W36 按它核对题面条件。线上必填；不填时 W36、W37 跳过并告警一次 |
| `base_conditions` | 品类本身的基础人群或用途（「养猫家庭」），不算条件 |
| `audience_terms` | 选填，`{目标客户: [自我描述词和暗示词]}`，W39 用；没写时转人工检查 |
| `category_aliases` | 品类叫法变体，只差这些词的两道题不算重复 |
| `audience_inputs` | 收到的需求信号编号，查有没有没用上的 |
| `warning_decisions` | 告警处理记录（见下「告警」） |
| `trial`、`baseline` | 试跑 `planned_runs: 3`、基线 `planned_runs: 7`，其余字段由监测写（见下「试跑与基线元数据」） |
| `retired`、`purchase_selection`、`assessment_scope`、`collection_config`、`prompt_version` | 锁版和监测阶段由 `geo-monitoring` 写（trial-and-lock.md），选词不写 |

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
| `attribute_ref` | 主约束条件；宽泛品类题留空字符串 | 约束条件（第一个） |
| `constraints` | 题面条件关键词列表，没有写 `[]` | — |
| `status` | 待审核 / 需修改 / 已批准 / 正式 / 停测 | 状态 |

按需才写：`condition_basis`（条件不来自引用的信号时 `{条件: 依据}`）、`evidence_refs`（引用的信号编号）、`audience_implicit`（题面没写提问人、条件已隐含时的理由）、`intent_key` 和 `market_decision`（多市场，`shared_equivalent` / `localized` / `market_specific`）、`tags`（只写 `tag_dimensions` 自定义维度的值，其余标签导出时派生）、`brand_weakness`（「品牌在 X 上不如 Y（事实，出处）」，提示词优先级据此降一档）、`reason_note`（接在出题原因后的一句）。

不写：`priority`（提示词优先级由 `write_prompt_reasons.py` 从行档位和 `brand_weakness` 算出）、`journey_stage`、`group_role`、`monitoring_prompt`、`formal_visibility_eligible`、`ai_cognitive_gap` 等旧字段。`journey_stage`、`group_role` 和旧字段名 `intent`、`persona`、`attribute`、`review_status` 出现就按旧结构拒收，其余写了也不读。

## 上传 CSV

九列：`query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`。用 `python3 -I scripts/export_upload_csv.py <bank.json> --out <dir> [--topic-label "<主题>=<显示名>"]` 导出，导出后自动跑上传检查：

- 一个市场一个文件；`diagnosis_intent` 填后端枚举，`question_types` 脚本自动填（过渡字段，统计口径以 shared/canonical-intent-mapping.md 为准）。
- `tags` 写按 `tag_dimensions` 派生的标签，不合格的值不出并打印原因。替代题暂按 `competitor` 上传、`tags` 第一个写「替代」（后端还没有 `alternatives` 枚举）。
- 问题解决、验证、交易、售后没有后端枚举，不导出并打印题号；停测、需修改的不导出；旧结构题库退出码 2。
- 后三列留空（线上后端读不读未确认）。

交付说明要告诉品牌方：替代题和问题解决题的读数现在只在基线 HTML 报告里看得到。

## validator 门禁

```bash
python3 -I scripts/validate_after_sales_set.py BANK.json [--previous PRIOR-BANK.json]
```

最后一行是就绪结论：Not ready（有错误退出码 1，旧题库退出码 2）；Usable（没有错误，但有告警没写处理记录，或 `first_party_data: false`、证据级别是假设）；Ready（没有错误、告警都有记录、有一手数据）。带 `--previous` 时，题集变了而 `prompt_version` 没变、或市场语言不同，报错。锁版由 `geo-monitoring` 做，但锁版门禁（14、26）和试跑、基线元数据检查在本 validator。

### 报错（必须改）

| 编号 | 查什么 |
|-|-|
| 2 | 主题名不为空、编号唯一；每道题只归一个存在的主题 |
| 3 | 不能有没有题的主题 |
| 4 | 每道题有主题、市场、类型、中文含义 |
| 8 | 题面完全重复 |
| 12 | 发现题不出现品牌、别名、竞品名，要向 AI 要候选 |
| 14 | 锁版后每个题库（一个国家 × 一种语言）正式题最多 60 道，且不超过 10 × 有正式题的主题数（混合选择时单个主题可以超过 10）；候选阶段不设上限 |
| 26 | 试跑前业务范围已确认；锁版前正式题已确认、试跑完成、版本已定 |
| 32 | 题面用采集语言写：一半以上字符是该语言文字；语种识别（lingua）判为另一门语言且采集语言置信度低于 0.05 |
| 38 | 对比题必须带条件（`constraints` 不为空） |
| 42 | 硬条件需人工核实并记录 |
| 43 | 发现行的业务优先级和主题优先级取值合法、写了依据；题的主题和所在行一致 |
| 60 | 每一行的 `prompt_type` 是八类之一 |
| 61 | 题的类型和所在行一致；不接受 Verification、Accuracy |
| 66 | 一个主题只放一种意图类型 |
| — | 品类认知题不进题库 |

### 告警（每条都要写处理记录）

告警以编号开头（`WARNING: [W39] …`）。处理记录写在 `config.warning_decisions`：`{match: "告警里的一段文字", decision: "已改写" / "保留：理由"}` 按子串处理单条；`{gate: "W39", decision: "保留：理由"}` 处理这个编号下全部告警（适合题量、原话未用这类成片出现的）。

| 编号 | 查什么 |
|-|-|
| W8b | 两道题措辞高度相似（只差品类叫法变体的不算） |
| W32 | 题面像关键词串、太长、多个问号、货币和市场不符；疑似另一门语言（置信度 0.05–0.10）；语种检查跳过 |
| W33 | 锁版前缺必填字段（锁版后是报错） |
| W34 | 证据来源不到三类 |
| W35 | 收到的需求信号没被任何题或约束条件用上 |
| W36 | 题面带条件却没引用信号也没写 `condition_basis`；题面数字不在引用的原话或依据里；引用了不存在的编号 |
| W37 | 同一主题、类型、约束条件、同样依据的条件：同一个决策问了两次 |
| W39 | 非基础人群的题，题面看不出谁在问（只在写了 `audience_terms` 时查） |
| W46 | 主题优先级和组内最高的业务优先级对不上（改行的档位，不单改主题） |
| W47 | 单产品线 × 单市场的候选题不在 30–60 道 |
| W48 | 业务优先级为高、中的发现行没有题 |
| W49 | `business_goals` 写法不对 |
| W52 | 有发现以外的题，`business_goals` 里却没有对应目标 |
| W53 | 题没写 `slice_ref` |
| W54 | 无条件的发现题（只在品牌方点名大词时写） |
| W56 | 有题写了审核状态、有题没写（没写的按待审核） |
| W57 | 约束条件只被未批准的题承载（客户确认后是报错） |
| W59 | 发现主题不够 10 道（其他类型不够 5 道），处理顺序见 selection-rules.md → 6 硬要求 3 |
| W62 | 切片标签维度不合格：维度名不对、没写 `basis`、自定义没登记 `values`；值不到 2 个主题、不到 5 道题、和主题名相同；整个维度就是主题切分轴 |
| W63 | 题上手写的 `tags` 没登记在自定义维度里 |
| W64 | 业务优先级为低的行挂了题（从低档补题属正常，写理由保留） |

### 人工检查（交付前）

- 对比题一对一、只用确认过的竞品；条件里要有使用场景，光有预算不算（门禁 38 只查非空）。
- 没写 `audience_terms` 时，人工看非基础人群的题面能不能看出谁在问。
- 试跑复核：品类和任务对不对、有没有歧义、诱导、重复；品牌有没有被提到不是合格标准。
- 多市场：每个市场的差异有依据；平台差异是采集配置，不是题面变体。
- 矩阵和题双向对得上、题放对了主题；对客表写法符合 client-facing-base.md。

### 不支持的旧结构

按旧结构写的历史题库保持原样，不迁移、不校验、不导出。判法以 `validate_after_sales_set.legacy_markers` 为准，主要是：`generation_stage` 不是 `selection`、没有矩阵行、行没写 `prompt_type` 或档位写 P1 / P2 / P3、有旅程阶段或 `group_role`、用旧字段名、`attribute_plan` 是 `{p1, p2, p3}` 或带 `relative_competitor` 等旧键。

## 试跑与基线元数据

由 `geo-monitoring` 写，validator 只查声明的次数、引用和版本，不读答案：

- 试跑：每题每个监测平台 3 次（异常最多 5 次），读数只作探索；`trial.status: passed`、`valid_runs`、`evidence_refs`。
- 锁版（`locked` / `formal_baseline` / `active`）：两次确认、试跑完成、版本已定；`evidence_status: "hypothesis"` 不能锁版。
- 正式基线：每个 query × 平台 × 国家 × 语言 7 次；`conditions_key`、`valid_samples_only: true`、`baseline.prompt_version` 与 `config.prompt_version` 一致；只算有效样本，失败要重跑。
- 新增、删除、改写任何一道题都开新版本，受影响的市场重建基线，新旧曲线不拼接。
