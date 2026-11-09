# 题库 JSON 与 validator 门禁

本文件只写题库 JSON 的字段和 validator 查什么。选词规则见 [selection-rules.md](selection-rules.md)，对客表见 [client-facing-base.md](client-facing-base.md)。售前固定配额的 v8 校验器是另一套，本文件的扩展字段不改变它；售前上传器不收扩展字段时，用适配脚本另出文件，不要说成「兼容 v8」。

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
    "business_goals": {"selected": ["发现型可见度"], "information_named": false},
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

题库写 `generation_stage: selection`，矩阵行都带 `prompt_type`。只支持这一种结构：旧题库不迁移、不校验，validator 和导出脚本遇到旧结构直接报「不支持的旧结构」并退出（判法见下「不支持的旧结构」）。

## config

| 字段 | 内容 |
|-|-|
| `lifecycle_status` | `hypothesis` / `customer_confirmed` / `locked` / `formal_baseline` / `active` |
| `evidence_status` | 题库整体的证据级别；`hypothesis` 或 `after_sales_signal` 不能锁版，就绪结论最高 Usable |
| `first_party_data` | 有没有用到品牌方一手数据；`false` 时就绪结论最高 Usable |
| `customer_confirmation` | `scope_status`（试跑前确认业务范围）、`prompt_set_status`（试跑后确认正式题）、`status` |
| `business_goals` | 本期做的目标：`{selected: [...], information_named: true / false}`。`selected` 取值：发现型可见度 / 竞争定位 / 品牌呈现 / 声誉与信任；目前只做发现型可见度，一律写 `{selected: ["发现型可见度"], information_named: false}`（selection-rules.md → 1；其他目标的启用方式待定）；`information_named` 是品牌方是否点名问题解决（口径见 selection-rules.md → 7. 写题「什么算品牌方点名问题解决」）。必须写 |
| `shopping_cards` | 每条产品线统计不统计商品卡：`{product_line, status, basis}`，`status` 为 开 / 关 / 试跑后定，`basis` 写按什么商品属性判的（selection-rules.md → 1）；试跑后由监测改成开或关并写上出卡比例。选填，没写时按关处理 |
| `topics` | `{topic_id, topic, priority, priority_basis}`；`priority` 即主题优先级，高 / 中 / 低 |
| `slices` | 矩阵行：`{slice_id, topic_id, product_line, market, audience, scene, prompt_type, attributes, priority, priority_basis}`；一行 ＝ 产品线 × 市场 × 目标客户 × 场景 × 意图类型，`market` 在单市场题库里可以省略；`scene` 存这一行的使用场景（键名沿用）；不写 `journey_stage`；`priority` 即业务优先级，高 / 中 / 低；`prompt_type` 是这一行唯一的意图类型，用英文键（Discovery / Information / Evaluation / Competitor / Alternatives / Trust / Transactional / Support，对应发现 / 问题解决 / 评估 / 对比 / 替代 / 验证 / 交易 / 售后），同一任务几种问法开几行（selection-rules.md → 5「意图类型：八类」）；每一行都要写。本期不出题的行也写在这里，不带 `topic_id`：非发现行看类型就知道本期不出；低档发现行在 `priority_basis` 末尾写「本期不出：……」（写法见 selection-rules.md → 5；品牌用不上、硬条件的处境不开行，记在 notes「没开的格子」）；它们和其他行一样写进对客确认表 |
| `attribute_plan` | 约束条件名单（键名沿用）：`{attribute, no_carrier_reason}`；`attribute` 就是三张表「约束条件」的选项名（约束条件不单设表）。不写 `relative_competitor`、`priority`、`common_constraints`、`brand_value` |
| `tag_dimensions` | 跨主题切片标签的维度：`{dimension, basis, values}`；`dimension` 为目标客户 / 使用场景 / 属性（也可写约束条件，值是约束条件）/ 自定义，`basis` 写跨哪些主题、切完谁拿去做什么，`values`：属性维度写业务范围「差异化优势」对应的约束条件，必须列出；自定义必填；其余维度选填。什么时候登记、怎么避开和主题重复见 selection-rules.md → 6「切片标签」；不需要横切就写 `[]` |
| `buyer_quotes` | 需求信号（对客 Base 的需求信号表；键名沿用）：`{输入编号, 原话, 目标客户, 约束条件}`（整项选填，题引用信号时用来查条件依据；条件关键词写在「约束」列） |
| `base_conditions` | 品类本身的基础人群或用途（「养猫家庭」「私家车」），不算条件 |
| `audience_terms` | `{目标客户: [自我描述词和暗示词]}`，查题面能不能看出谁在问（告警 W39）；选填，没写时这一项改为人工检查 |
| `category_aliases` | 品类叫法变体，只差这些词的两道题不算重复 |
| `audience_inputs` | 收到的需求信号编号，查有没有没用上的 |
| `retired` | 停测的题号和原因（Base 里已删除） |
| `assessment_scope` | 锁版时的考核口径：考核题、平台市场语言和次数、品牌分母、计算方式 |
| `warning_decisions` | 每条告警的处理记录：`{match: 告警里的一段文字, decision: "已改写" / "保留：理由"}`，或按编号整类处理 `{gate: "W39", decision: "保留：理由"}`（见下「告警」） |
| `trial` | `planned_runs: 3`、`status`、`valid_runs`、`evidence_refs`（原始答案位置） |
| `baseline` | `planned_runs: 7`（2026-11-06 当天早些时候写的 30 照认）、`status`、`conditions_key`、`valid_samples_only: true`、`prompt_version` |
| `collection_config` | 市场、语言、平台、模型模式、7 次是否跨天 |
| `prompt_version` | 锁版后不可改的题集版本 |

## 每道题

| 字段 | 内容 | 对客表 |
|-|-|-|
| `question_id` | 题号 | 编号 |
| `user_question` | 题面，用市场语言写 | 提示词 |
| `zh_translation` | 中文含义 | 中文含义 |
| `topic_id` | 所属主题 | 主题 |
| `region` | 市场 | 市场 |
| `prompt_type` | 八类英文键之一，同 `slices.prompt_type`；Verification、Accuracy 报错：能力核查归 Evaluation，准确性题在题库之外 | 意图类型 |
| `slice_ref` | 所在矩阵行；目标客户、使用场景、意图类型、产品线从这一行读 | 所属切片 |
| `attribute_ref` | 测的主约束条件（键名沿用）；宽泛品类题留空字符串 | 约束条件（第一个；默认视图隐藏） |
| `constraints` | 题面条件（关键词列表），没有写 `[]` | — |
| `changeability` / `changeability_basis` | 可改变性（高 / 中 / 低 / 待试跑）及信源结构与可执行动作依据，仅作探索，不改档 | 可改变性 |
| `status` | 待审核 / 需修改 / 已批准 / 正式 / 停测 | 状态 |

按需才写：`condition_basis`（条件不来自引用的需求信号时，写 `{条件: 依据}`）、`audience_implicit`（题面没写提问人、但条件已经隐含时的理由）、`intent_key` 和 `market_decision`（多市场，`shared_equivalent` / `localized` / `market_specific`）、`evidence_refs`（引用的买家原话编号，选填）、`tags`（只写登记在 `tag_dimensions` 自定义维度里的值；目标客户、约束条件这些标签导出时派生，不写在题上）。

目标客户、使用场景、意图类型都从所在矩阵行读，题上不写旅程阶段。

以下字段不再写：`monitoring_prompt`、`journey_stage`、`group_role`（核心 / 实验 / 监测三层已取消，考核按类型认）、`formal_visibility_eligible`（算不算提及率考核按类型认：只有发现算）、`constraint_type`、`ai_cognitive_gap`（基线结果进报告）、`target_count`、`planned_prompts`、`source_slices`、`expected_total`、`priority`（题上的提示词优先级，2026-11-05 撤）、`priority_change_reason`，以及 cadence、version、lineage_id、prompt_group、competitor_set、business_priority、change_reason。其中 `journey_stage`、`group_role` 和旧字段名 `intent`、`persona`、`attribute`、`review_status` 出现就按旧结构拒收；其余写了也不读。

## 上传 CSV

线上诊断上传只认九列模板：`query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`。用 `python3 -I scripts/export_upload_csv.py <bank.json> --out <dir> [--topic-label "<题库主题>=<显示名>"]` 导出（主题名本来就用中文写，要换显示名时用 `--topic-label`；旧结构题库不导出，退出码 2）：一个市场一个文件；`diagnosis_intent` 填后端枚举；`tags` 写按 `config.tag_dimensions` 派生的切片标签，不重复写 `diagnosis_intent` 已经表达的类型，没有标签就留空（不到 2 个主题、不到 5 道题、和主题重复的值不出，打印原因）；替代题暂按 `competitor` 上传、在 `tags` 第一个写「替代」区分（只有替代题写类型名）（后端还没有 `alternatives` 枚举，上线前线上报告看不到替代题的提及率）；问题解决、验证、交易、售后没有后端枚举，不导出并打印题号；状态为停测或需修改的不导出；`question_types` 由脚本按 `diagnosis_intent` 自动填，是过渡字段，每类统计什么以 shared/canonical-intent-mapping.md 的「统计指标」列为准；导出后自动跑上传检查。后三列（`purchase_intent`、`persona_name`、`scene_name`）留空：本地的报告脚本不读它们（`geo-presales-report-builder/scripts/build_report_data.py` 读上传 CSV 时只取 query、question_zh、topic、diagnosis_intent、tags、question_types；`geo-presales-report-editor` core 的 `questions.py` 只在旧格式题库 JSON 里读这三个键，不读上传 CSV）；线上后端是否读这三列未确认，确认前留空。

交付说明要告诉品牌方：替代题的读数现阶段只在基线 HTML 报告里看得到，线上报告看不到（后端没有 `alternatives` 枚举）；问题解决题不导出，读数同样只在基线 HTML 报告里。

## validator 门禁

```bash
python3 -I scripts/validate_after_sales_set.py BANK.json [--previous PRIOR-BANK.json]
```

只查现行结构。遇到旧题库，报「unsupported old structure」并列出命中的旧结构标记，退出码 2，不往下查。

最后一行是就绪结论：

| 结论 | 条件 |
|-|-|
| Not ready | 有错误（退出码 1）；旧题库（退出码 2） |
| Usable | 没有错误，但有没写处理记录的告警；或只用公开数据（`first_party_data: false`）、证据级别是假设 |
| Ready | 没有错误，告警都有处理记录，有一手数据 |

带 `--previous` 时，题集变了而 `prompt_version` 没变报错，市场语言不同报错。

锁版由 `geo-monitoring` 做，锁版门禁（14、26）和试跑、基线元数据检查仍在本 validator：它们读的是题库 JSON 上的 `lifecycle_status`、`trial`、`baseline`，题库锁版时要查，`geo-monitoring` 没有自己的 validator。

### 报错（必须改）

| 编号 | 查什么 |
|-|-|
| 2 | 主题名不为空、主题编号唯一；每道题只归一个主题，主题编号存在 |
| 3 | 不能有没有题的主题 |
| 4 | 每道题有主题、市场、类型、中文含义，题面用市场语言写 |
| 8 | 题面完全重复 |
| 12 | 发现题不出现品牌、别名、竞品名，要向 AI 要候选 |
| 14 | 锁版后每条产品线（一个题库 = 一个国家 × 一种语言）正式题最多 60 道；单个主题不设上限 |
| 26 | 试跑前业务范围已确认；锁版前正式题已确认、试跑完成、版本已定 |
| 32 | 题面用采集语言写：一半以上的字符是该语言的文字；语种识别（lingua，75 种语言）判定题面是另一门语言、且采集语言自身的置信度低于 0.05 |
| 38 | 对比题必须带使用场景（`constraints` 不为空） |
| 42 | 相对弱势可保留，是否满足硬条件需人工核实并记录 |
| 43 | 业务优先级和主题优先级取值合法、写了依据；题的主题和所在行一致 |
| 60 | 每一行的 `prompt_type` 是八类之一 |
| 61 | 题的类型和所属行的 `prompt_type` 一致；不接受 Verification、Accuracy |
| 66 | 一个主题只放一种意图类型 |
| — | 品类认知题不进题库 |

### 告警（每条都要写处理记录）

每条告警都以稳定编号开头，如 `WARNING: [W39] …`。处理记录写在 `config.warning_decisions`，两种写法都认：

- `{match: "告警里的一段文字", decision: "已改写" / "保留：理由"}`：按子串匹配，只处理含这段文字的告警；
- `{gate: "W39", decision: "保留：理由"}`：一条覆盖这个编号下的全部告警（写 `W39`、`[W39]`、`39` 都认，大小写不论），适合题量、原话未用这类必然成片出现的告警。

| 编号 | 查什么 |
|-|-|
| W8b | 两道题措辞高度相似（只差品类叫法变体的不算；和报错 8 的题面完全重复不是一回事） |
| W32 | 题面像关键词串、太长、有多个问号、货币和市场不符；语种识别疑似另一门语言（采集语言置信度 0.05–0.10）；采集语言不在 lingua 支持范围或本机没装 lingua，语种检查跳过 |
| W33 | 锁版前缺必填字段（锁版后是报错） |
| W34 | 证据来源不到三类 |
| W35 | 收到的需求信号没被任何题或属性用上 |
| W36 | 题面带了条件，却既没引用需求信号（`evidence_refs`）也没写 `condition_basis`；题面里的数字不在引用的原话或依据里；引用了不存在的信号编号。信号带「约束」列时，按约束关键词逐条核对。题库没有需求信号时，36、37 跳过并告警一次 |
| W37 | 同一主题、同一类型、同一属性、同样有依据的条件：同一个决策问了两次 |
| W39 | 目标客户不是基础人群的题，题面看不出是谁在问（只在写了 `config.audience_terms` 时查；没写时转人工检查） |
| W46 | 主题优先级和组内多数行的业务优先级对不上，或各档行数一样多、没有多数（人工判断后写进 `warning_decisions`） |
| W47 | 单产品线 × 单市场的候选题不在 30–60 道 |
| W48 | 业务优先级为高、中的发现行没有题；非发现行本期不出，不告警 |
| W49 | 没写 `config.business_goals`，或写法不对（`selected` 不是四个目标里的值） |
| W50 | （休眠：目前 `selected` 只会是发现型可见度）`business_goals` 含竞争定位，但题库里没有任何对比题（高、中对比行也就都没有题） |
| W51 | （休眠，同上）`business_goals` 含声誉与信任，但题库里没有评估题或验证题 |
| W52 | 题库里有发现以外的题，但 `business_goals` 里没有对应目标：对比、替代对应竞争定位，评估、验证对应声誉与信任，问题解决对应 `information_named`；交易、售后本期没有对应目标，写了就告警 |
| W53 | 题没有所在行（没写 `slice_ref`） |
| W54 | 无条件的发现题（只在品牌方点名大词时写） |
| W56 | 有题写了审核状态、有题没写，没写的按待审核算 |
| W57 | 属性只被还没批准的题承载，不算覆盖（客户确认后是报错） |
| W59 | 主题不够 5 道考核题（发现题）或不够 4 个不同购买决策，其他类型的主题不够 5 道（停测题不计）；按 selection-rules 第 6 步硬要求 3 的顺序处理（补遗漏需求与条件 → 有意义的复合条件 → 查是否拆得过细），仍不足的写处理记录，品牌方点名单买的注明读数波动风险 |
| W62 | 切片标签维度不合格：维度名不对、没写 `basis`、自定义没登记 `values`；某个值不到 2 个主题、不到 5 道题、和主题名相同；整个维度每个值都只落在一个主题（这个维度就是主题的切分轴）（停测、需修改、问题解决不计） |
| W63 | 题上手写的 `tags` 没登记在 `tag_dimensions` 的自定义维度里，导出时不带 |
| W64 | 业务优先级为低的行挂了题：低档默认不出题（selection-rules.md → 5）；高、中档覆盖不够时从低档补的题属正常，写处理记录保留理由 |

### 不支持的旧结构

Abrand、Bbrand 9 月版、UNI_A、Ebrand、Hbrand 选词 2.1、360 选词等按旧结构写的题库保持历史版本，不迁移、不校验、不导出。validator（`validate_after_sales_set.legacy_markers`）见到下面任一项就判为旧结构：`generation_stage` 不是 `selection`；没有矩阵行；有 `config.extra_prompt_types`（旧售前题库）或 `config.leader_default`；有行没写 `prompt_type`、写了 `prompt_types` 列表或档位写 P1 / P2 / P3；行或题上有旅程阶段；题上有 `group_role`、旧字段名（`intent` 代替 `prompt_type`、`Prompt Type:` 标签、`persona`、`buyer`、`attribute`、`buyer_demand_evidence`、`condition_slot`、`review_status`）；`attribute_plan` 是旧的 `{p1, p2, p3}` 写法，或带 `relative_competitor`、`priority`、`common_constraints`、`brand_value`。

### 人工检查（交付前）

- 对比题一对一，只用确认过的竞品。
- 对比题的条件里要有使用场景，光有预算这类约束不算（门禁 38 只能查 `constraints` 非空）。
- 题库没写 `audience_terms` 时，人工看非基础人群的题面能不能看出谁在问。
- 新题有证据，否则标「假设」。
- 试跑复核：品类和任务对不对、有没有歧义、诱导、重复；品牌有没有被提到不是合格标准。
- 多市场：每个市场的差异有依据，借用另一个市场的意图有理由；平台差异是采集配置，不是题面变体。
- 矩阵和题双向对得上：业务优先级为高、中的发现行都有题（没题的写处理记录）；低档发现行依据里写「本期不出：……」；非发现行本期没有题；每道题都在一行上，类型和行一致。
- 题放对了主题。
- 对客表写法符合 client-facing-base.md → 写法。

## 试跑与基线元数据

- 试跑：每道候选题在每个监测平台 3 次（异常时最多 5 次）；读数只作探索，不进统计；`trial.status: passed`、`valid_runs`、`evidence_refs`。
- 锁版：`locked` / `formal_baseline` / `active` 要两次确认、试跑完成、版本已定；假设级证据不能锁版。
- 正式基线：每个 query × 平台 × 国家 × 语言 7 次（2026-11-06 起，原 30 次）；`conditions_key`、`valid_samples_only: true`、`baseline.prompt_version` 与 `config.prompt_version` 一致；7 次是否跨天写在 `collection_config`。只算有效样本，失败不记 0，失败要重跑。2026-11-06 当天早些时候写的 30 次照认，锁版前改成 7 次。
- 新增、删除、改写任何一道题都开新版本，受影响的市场重建基线，新旧曲线不拼接。
- validator 只查声明的次数、引用和版本，不读爬虫答案；采集是否真的完成，由监测在标记完成前逐题逐平台核对原始结果。
- 基线还读 query fan-out（ChatGPT `task_result.search_model_queries.queries`、Grok `tool_usages` 里 web_search 的检索词）和延伸问题（Gemini `task_result.related_queries`、Grok `follow_up_suggestions`，平台推荐用户下一步问的问题，不是检索词），两类分开报；字段为空表示没返回，不是失败。读法见 `geo-monitoring` → gap-cause-action-table.md → *Query fan-out*。
