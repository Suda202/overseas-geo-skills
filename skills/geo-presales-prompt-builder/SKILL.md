---
name: geo-presales-prompt-builder
description: Generate or validate Discovery-first GEO Prompts from an evaluation Case, and supplement competitor or evaluation questions when requested. Use evidence-backed buyer intent, Topic-scoped Attribute planning, and free Tags; do not create Topics, research competitors, collect answers, or calculate metrics.
metadata:
  author: Overseas GEO Project
  version: "4.13.0"
---

# GEO Presales Prompt Builder

## 目标

直接读取评测 Case 业务字段，先生成可被售后继承的 `overseas-geo-question-bank/v8` 发现型问题 V1。重点是选择真实、独立、值得监测的购买意图，不是凑完整题型。新题库显式写 `config.generation_stage=discovery`；只在用户要求补充竞品、评价或完整诊断时改为 `diagnostic`，保留原 Discovery 的 ID、题面和来源。

Topic 是主组织单元；Attribute 不是产品参数清单，而是当前 Topic 下的买家决策关注点。类目跨越两侧：品牌侧（品类、产品特性、差异化优势、集成、信任与合规）与买家侧（垂直行业、目标企业画像与买家角色、痛点、使用场景、购买标准、地理与市场、限制与边界）；**ICP、画像、痛点、场景本身就是 Attribute，不需要先转写成“客户意图”再映射回来**。对客确认表的「客户问题与场景」列是需求侧的另一对象（买家在哪个场合发问），不是属性的一类：属性决定优化哪项认知，意图决定在哪个问句里争这项认知。轻量派生 `attribute_plan`，P1/P2/P3 仅代表属性在当前 Topic 下的优先级，不设属性数量配额，不要求客户先交完整属性库或 Journey Matrix。无独立属性的品类基线允许空规划。诊断意图、品牌范围和实际测试的 Attribute 使用逐题 `tags`，不另造 Case 手工字段或属性 ID。

接口中的原始 Case 业务字段就是 Builder 的直接输入。不要另造 `target_audiences / pain_points / use_cases` 等平行输入合同。

题量硬门槛：每个 Topic 至少 5 条，整批（含后补题）不超过 50 条；这是下限和总量上限，不是均衡配额。不同 Topic 可以有不同数量，只有在重要买家关注点尚未覆盖时才增加问题。若已知后续要补 diagnostic 题，先为后补题预留总量，不把 Discovery 机械扩到 50 条。发现型阶段全部为 Discovery；其他阶段没有固定竞品、评价或品类认知配额。旧题库省略 `generation_stage` 时仍按历史完整诊断合同校验，不能通过漏题自动降级为发现型。

## 开始前读取

1. 读取 [售前与售后共用的监测问题生成原则](../shared/prompt-generation-principles.md)。
2. 读取 [属性规划](references/attribute-planning.md)。
3. 读取 [生成方法](references/generation-method.md)。
4. 读取 [v8 产物契约](references/presales-contract.md)；生成非英文语言题库时读取 [语言注册表](references/locale-templates.json)。
5. 质检时读取 [质量门](references/quality-gates.md)。
6. 需要正反例时读取 [Edgelight 示例](references/examples.md)。
7. 读取 [跨 skill 规范映射](../shared/canonical-intent-mapping.md)；意图 Tag、问题类型与字段名以本文件为准。
8. 需要多市场或多语言题库时，读取售后 skill 的 [代表性题库适配规则](../geo-after-sales-prompt-builder/references/representative-library.md)；内部做市场覆盖查漏，不把完整矩阵交给客户填写。

## 唯一输入合同

从系统接口提交的目标评测 Case 读取以下中文业务字段；编号字段支持 `1…n`，合并字段也按相同语义解析：

- `公司名`、`业务 / 产品名称`、`品牌名称`、`业务模式`、`品类`、`目标企业画像`
- `目标客户 1…n`、`痛点 1…n`、`使用场景 1…n`、`产品特性 1…n`
- `差异化优势`、`适用边界`
- `主题 1…n（宽泛/细分）`：接受 1–3 个 Case 候选 Topic；上游 Case Builder 通常产出 2–3 个，其中 1 个 Coverage Topic、1–2 个 Depth Topic。括号标签是输入提示，但 v8 不输出 `topic_type`
- `官方域名`
- 恰好三组 `竞品 n` 与 `竞品 n 官网域名`
- `补充内容`，字段必须保留但允许为空；非空时可包括 Topic 局部竞品边界，例如“竞品 1 仅用于主题 1，竞品 2–3 仅用于主题 2”

Accuracy 默认配额为 0，不读取或要求上游事实包。不得从旧评测集复制 `target_attributes`，不得新增 `attribute_pool / attribute_id / priority_attribute_ids`。`attribute_plan` 只能由 Builder 从当前 Case 字段派生。缺少品牌、品类、至少一个 Topic、官方域名、三组竞品名称及官网域名，或证据不足以支撑每 Topic 5 个独立购买意图时，停止并列出缺项；建议上游补证据或合并 Topic，不制造伪重复。对新增问题还必须逐条通过“Case 有依据、真实买家会问、会改变独立决策”三门；只因某个 Topic 题少、某项能力看起来有趣或模型能推测出来，不足以新增问题。

同时复用上游已交付的来源、客户确认文档和确认状态，见共享原则中的“阶段交接”。这些是研究证据，不是第二套业务字段；新增或更正业务事实先由 Case Builder 回写原字段。售前负责初步核对诊断用业务重点与事实边界；客户尚未回复时可用公开证据形成明确标为待客户确认的 V1，不能把公开资料或 AI 推测当成客户原话。交接时列出已确认与待确认的范围，不把预填文档当成批准；售后试跑前负责复核最终监测范围。多市场题库先按市场证据核对产品线、买家、旅程、约束、竞品与当地信源，再决定哪些意图共享、当地化、增删或不生成；完整查漏表留内部，客户只确认整理后的属性池和市场相关事实。

## Topic、Attribute 与 Tags

- Topic 回答“这批 Prompts 属于哪个长期独立监测的市场、场景或战略机会”，每题只回指一个 `topic_id`。
- Attribute 回答“这题在测试 AI 如何认识品牌的哪项能力、特征或评价标准”。同名 Attribute 可跨 Topic 复用，但在每个 Topic 内可有不同优先级。
- Prompt Task 回答“买家正在完成什么任务”，常用值包括 `Discovery`、`Problem Solving`、`Evaluation`、`Comparison`、`Alternatives`、`Shortlist`、`Validation`、`Transaction`、`Post-purchase Support`、`Category Understanding`、`Source Discovery`。它不是第七类 Intent；必须先按题面和业务合同决定现有 Intent，再写 Task 标签。
- Tags 是 JSON 内部的统一自由字符串数组。默认使用 `Intent: …`、`Brand Scope: …`、`Prompt Task: …`、`Attribute: …` 四个命名空间；可以增加阶段、区域或项目自定义 Tag。Prompt Task 描述买家任务，不改变后端 Intent 路由。Tags 不决定 `analysis_type` 或 `formal_visibility_eligible`。JSON 保留完整 Tags；上传 CSV 也带 `tags` 列，但它只用于上传适配，允许留空，且单元格必须短于 200 字符；若填写，使用英文逗号、中文逗号或换行分隔的简短标签，不把完整 Attribute 列表塞进 CSV。品牌范围、Attribute 与其他自由 Tags 仍保留在 JSON 中。

## 执行流程

1. 归一化中英文名称、品类、业务边界、1–3 个 Topic 和三组正式竞品；只把输入中的“宽泛/细分”当作理解提示，不保存为字段。读取补充内容中的 Topic 局部竞品边界，为每个正式竞品写入适用的 `topic_ids`；未提供局部边界时，三者默认适用于全部 Topic。不得把 Case 中可跨 Topic 的能力重新升级为 Topic。
2. 从证据支持的买家决策关注点完成轻量 `attribute_plan`，P1/P2/P3 与 `excluded` 均按实际内容填写，不凑数量；P1 必须被 Discovery 覆盖。生成前只根据购买决策影响和 Case 证据分级，不虚构尚未采集的 AI 认知差距。纯目录事实进入 `exclude`，需要真值的精确数值进入 `accuracy_only`。**进入 `excluded` 的候选项不得再作为任何题目的 `Attribute:` 标签**——被排除意味着它不改变购买决策，以它命名的题同样不改变决策。研究中已识别的属性直接复用，勿要求客户重复填写。优先级判断覆盖产品能力、场景、痛点、采购约束和边界，不把“属性数量”当作完整度。
3. 先选择阶段再记录实际配额。`discovery`：其他五类为 0，每 Topic 至少 5 条独立 Discovery；题量按该 Topic 的重要决策覆盖情况决定，允许明显不对称，不为凑齐或平均分配新增问题。`diagnostic`：在已有发现型集合上按需补竞品、评价或品类认知题，不要求每个竞品都出题或各 Topic 对称。先计算 Discovery 与计划中的后补题合计是否不超过 50；若后补后超限，先由用户决定范围，不静默删除已锁定的发现型问题。保存 `quotas` 的真实数量，不用配额驱动虚构需求。
4. 按生成方法编写自然英文根问题及等义中文。每题先确定一个 `Prompt Task`，再确定后端 `Intent`；两者分别记录。Discovery 和 Category Awareness 不出现具体品牌；Competitor、Evaluation 遵守各自品牌边界。按题面实际品牌提及写入唯一品牌范围 Tag。逐题检查任务匹配、不引导、消除缩写/跨品类歧义、买家语境有来源。Case 中多个既有品类称呼可帮助校准语言，但单纯更换称呼不计为新增独立意图。
5. Discovery 先覆盖当前 Topic 的所有重要 P1，再按独立购买价值选择 P2/P3；完成覆盖后立即停止，不因为其他 Topic 题更多或更少而平衡数量。每道新增题都要能指出 Case 来源、具体买家/场景和独立决策结果。每题只承担一个主要决策，允许真实场景所需的复合条件，不堆叠仅本品符合的 USP；保留低条件自然问法，长短取决于语境而非固定词数。实际测试的属性写为 `Attribute: …`，无独立属性的品类题可不写。**去重的单位是购买决策，不是措辞**：两题指向同一决策（同一候选集合、同一比较维度）只保留一题，只有买家、地区、场景或决策阶段变化才算新题；不把 best/top、品类同义称呼或同一能力的换说法计为新增覆盖。**宽 Topic 要落到切面**：一个 Topic 下有多个不同买家需求时，逐条标出所属切面，并把配题重心放在差异化优势与买家需求重合的切面上，不平均分配。补充 Competitor 时只选当前 Topic 适用且有比较价值的竞品，同组题面和 Attribute Tags 保持同构。
6. 不生成 Verification 与 Accuracy 问题。保留 Verification 作为意图定义（批量验证 AI 是否正确认知目标品牌与多个关键 Attribute 的关联，适用阶段为售后），P1 的属性级正确性核查并入 Accuracy 合同；只有用户明确要求售后验证或事实核验时，才在独立合同下单独确认产物，不得从 Case 或模型记忆临时补真值，也不在默认售前题库中生成 `validation_items` 或 `fact_value / official_source_url / fact_checked_at`。
7. 仅在补充诊断时读取生成方法的对应模板，按需要生成 Evaluation 或 Category Awareness，不为补全类型强制生成。Evaluation 每题一个目标品牌或当前 Topic 适用竞品；品牌间评价保持同模板。两类固定模板在品类与 Topic 相同时省略范围从句，非英文使用语言注册表。英文题面不出现元词 `topic`。品类 Topic 下的 Discovery 不是 Category Awareness，不互相替代。
8. 写入题型、品牌范围和实际属性 Tags，按真实产物核对配额。二遍语义 review 检查证据、意图覆盖、重复、题面和翻译；保存 JSON/CSV 并运行 validator。将题库版本、证据索引和客户确认状态交给售后。售后采集流程负责每道候选题在拟监测平台各试跑 3 次；售前未试跑就如实标记，不以本品是否出现作为合格条件。**阶段边界：售前这一轮只能产出「初步认知问题 / 机会假设」，不能认定为稳定认知缺口**——AI 回答有波动，单轮结果区分不了偶发未提及与长期提及率低；售后连续 3 天每天 1 次的正式基线只建立初始基准，长期稳定性仍由后续同口径监测验证。售前按「有需求 × 有资格赢 × 可交付」排理论优先级，基线后可结合初始读数安排验证与优化，不把三次读数称为稳定缺口或效果承诺。详见 `geo-after-sales-prompt-builder` → after-sales-rules.md 的 *The Four Stages and What Each Can Conclude*。**选题用「有需求 × 有资格赢 × 可交付」三项联合判断，其中「能不能赢」不能单独用**：判法是竞品优势若来自品牌知名度或广泛媒体共识，短期不可逆转、该方向只作基线；不来自共识的方向才是 90 天内可推进的战场。可以把共识锁死的方向排为基线而不为它新配题；**不能因为单次或零提及删题**，那会污染可见度测量。

## 分析与指标边界

> **注意**：下表中的 `Intent: …` Tag 为当前默认枚举。诊断意图后续将迁移为自定义 Tags，迁移后需在自定义 Tag 定义中重新声明 `analysis_type` 与 `formal_visibility_eligible` 的推导规则。

| 默认诊断 Tag | analysis_type | formal_visibility_eligible |
|---|---|---|
| `Intent: Discovery` | `visibility,sentiment` | `true` |
| `Intent: Competitor` | `sentiment` | `false` |
| `Intent: Verification` | 空 | `false` |
| `Intent: Accuracy` | `accuracy` | `false` |
| `Intent: Evaluation` | `sentiment` | `false` |
| `Intent: Category Awareness` | 空 | `true` |

把 `analysis_type` 用于分析模块分流，把 `formal_visibility_eligible` 用于标记进入后端可见度处理管线的题集。两者由 Prompt 生成角色确定，不从可自由修改的 Tags 自动推导；增删自定义 Tag 不得改变路由。Discovery 同时承担可见度与情感分析；Competitor 与 Evaluation 只进入情感模块；Verification 与 Accuracy 只在独立合同下使用，不进入默认售前题库的可见度或情感指标；Category Awareness 不分流进任何标准分析模块，由售前报告作为认知标准与品牌属性对比输入直接消费。**报告侧正式 Visibility、声量、排名、Share of Voice 与聚合引用指标的分子与分母只统计 `Intent: Discovery` 题**；Category Awareness 与 Competitor 均不计入，Competitor 进 M02 竞品模块，Category Awareness 进 M08 品类认知模块。`formal_visibility_eligible = true` 只表示进入后端可见度处理管线，不等于进入正式可见度指标。旧 `metric_scopes` 只可由兼容适配器生成，不是 v8 核心字段，也不得覆盖上述两个字段。

不生成或保留 `topic_type`、`question_type`、`funnel_intent`、`decision_stage`。旧 `overseas-geo-question-bank/v5` 仅允许只读验证或迁移，不得作为新题库默认输出。

## 输出与验证

- 新产物显式写 `generation_stage`；每 Topic 至少 5 条、整批不超过 50。默认只输出 Discovery；补充题型没有固定数量。保留 `attribute_plan`、实际配额、Tags 和失败/重写原因。按独立购买决策解释题量，不用产品线、市场和任务类型的笛卡尔积凑题。客户文档、来源、版本、市场任务查漏和待确认状态写入独立交接文件，不塞进闭合 `config` 或上传 CSV。
- 每题包含 `question_id / topic_id / tags / analysis_type / formal_visibility_eligible / intent_key / user_question / zh_translation / monitoring_prompt / quality_checks`；不包含 `diagnosis_intent` 或单独的 `attributes`。
- 默认题库不含 Verification 题与 `validation_items`、Accuracy 题或事实包字段；上传 CSV 固定字段顺序为 `query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`。`diagnosis_intent` 从 JSON 唯一默认 Intent Tag 转写为 `discovery / competitor / verification / accuracy / evaluation / category_awareness`。`tags` 为上传适配列：允许留空；如果填写，必须是短于 200 字符的字符串，并使用英文逗号、中文逗号或换行分隔，优先保留可上传的最小化摘要，不要把 JSON 里的完整 Attribute 列表直接搬进来。`question_types` 按上传合同填写：Discovery 为 `visibility,sentiment`，Competitor 与 Evaluation 为 `sentiment`，Verification、Accuracy 与 Category Awareness 为 `visibility`——这三类不得带 `sentiment`，否则下游 `geo-presales-sentiment-judge` 会把它们错误纳入情绪样本（样本口径见 `../shared/canonical-intent-mapping.md`）。`purchase_intent / persona_name / scene_name` 没有可靠来源时留空，不臆造。JSON 仍不生成独立 `diagnosis_intent` 或 `question_type` 字段；这两个 CSV 字段只由上传适配器导出。

```bash
python3 scripts/validate_question_bank.py /absolute/path/question-bank.json
python3 scripts/validate_question_bank.py /absolute/path/diagnostic-bank.json --baseline /absolute/path/discovery-v1.json
python3 -m unittest discover -s evals -p 'test_*.py'
```

`diagnostic` 补充阶段必须提供原始 Discovery（或原历史 v8）题库对照，检查 Case、Topic、语言与原 Discovery 的 ID、题面和路由未变；没有原件就不能声称“保留了原题”。市场和采集条件继续在交接文件核对，单文件 validator 不替代该核对。

新题库默认生成 v8；validator 仍可只读旧 v7/v6/v5。不创建 Topic，不选择或补齐竞品，不重新核验官网事实，不采集回答，不生成 `observed_associations`，不计算任何诊断指标，不直接写售前报告。
