# 海外 GEO 售前生题方法（v8）

## 1. 接收 Case 与研究交接

只消费系统接口提交的评测 Case 中文业务字段：公司与品牌、业务 / 产品、业务模式、品类、目标企业画像、目标客户、痛点、使用场景、产品特性、差异化优势、适用边界、购买标准、集成与兼容、信任与合规、地理与市场、1–3 个 Topic、官方域名、三组正式竞品及官网域名、补充内容。上游 Case Builder 通常产出 2–3 个 Topic，其中 1 个 Coverage Topic、1–2 个 Depth Topic；单 Topic 输入仍受支持。不再转写成另一套 Prompt Builder 输入。

把 `主题 1（宽泛）`、`主题 2（细分）` 一类标签解析为 Topic 顺序和文本；不要在 v8 配置或问题中保存 `topic_type`。Topic 只承载独立市场、场景或战略机会；跨 Topic 的能力、特征和评价标准进入 Attribute 规划。默认生成英文问题；中文源字段作为证据，不把翻译后的扩写当作新增事实。

复用 Case 研究来源和客户确认文档，标明公开证据、客户确认和待验证假设。客户尚未回复不阻止生成售前 V1，但不能标成正式锁词；把待确认的业务重点和事实边界明确交给售后复核。真实买家意图用于校准问法；没有频次证据时不称“高频”。多市场先做内部代表性覆盖查漏：产品线、买家、旅程、市场/语言、约束、竞品/替代方案和业务优先级。只有当地证据支持购买决策与答案集合等价时才复用候选意图；否则按当地术语、货币、法规、信任信号、来源生态和购买预期调整或增删。各市场/语言分别锁版本与建基线，同一市场的题可跨平台复用。新增业务事实交回 Case Builder，不直接在题面扩张事实。

## 2. 先建立 Attribute × Topic 规划

从下列来源逐项抽取可测试的买家关联，不要求 Case 提供 `target_attributes`：

| 来源字段 | 可用判断 | Edgelight 例子 |
|---|---|---|
| `品类` | product_category | LED display manufacturer and commercial display solutions provider |
| `目标客户 n` | audience | commercial AV integrators and LED display distributors |
| `痛点 n` | pain_point | matching pixel pitch, brightness, refresh rate and viewing distance to a venue |
| `使用场景 n` | use_case | fixed LED installations in corporate and commercial spaces |
| `产品特性 n` | capability / integration | structural customization and content-control integration |
| `差异化优势` | business_specific | project delivery capability backed by stated manufacturing scale and certifications |
| `适用边界` | business_specific | excludes buyers seeking only lighting, power supplies, controllers or full architectural AV services |

按 [Attribute × Topic 属性规划](attribute-planning.md) 合并同义候选，记录实际需要的 P1/P2/P3，不设数量配额或必填完整矩阵。Attribute 是买家决策关注点，不限于产品属性；场景、痛点、采购约束、供应风险和适用边界也可进入规划。无独立属性的品类题允许空规划，已选 P1 必须被 Discovery 覆盖。低信息量目录事实和需真值的精确参数分别进 `exclude / accuracy_only`。同一属性、源字段可跨 Topic 复用，不生成属性 ID 或预写未采集的 AI 认知差距。

## 3. 建立统一 Tags

每题使用一个自由字符串数组 `tags`。默认写入以下常用标签：

- 一个生成角色标签：`Intent: Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。
- 一个买家任务标签：`Prompt Task: Discovery / Problem Solving / Evaluation / Comparison / Alternatives / Shortlist / Validation / Transaction / Post-purchase Support / Category Understanding / Source Discovery`。它是任务层，不是后端 Intent 枚举。
- 一个品牌范围标签：题面出现目标品牌或任何正式竞品时写 `Brand Scope: Branded`，否则写 `Brand Scope: Non-Branded`。
- 零个或多个 Attribute 标签：`Attribute: {attribute_plan 中的人类可读名称}`。一题测试多个属性时可写多个；品类基线题不测试独立属性时允许为零。

允许增加 `Lifecycle: …`、`Region: …` 等自由 Tags。常用 Intent 标签用于 Builder 的实际数量汇总与模板质检，Prompt Task 用于覆盖查漏、分组和客户可读的题目用途，但两者都不携带固定配额；`tags` 字段本身没有封闭枚举，自定义 Tags 不改变 `analysis_type` 或 `formal_visibility_eligible`。

## Prompt Task 与 Intent

Prompt Task 回答“买家正在完成什么任务”，现有六类 Intent 回答“这道题按哪个分析合同处理”。先在内部覆盖规划中检查任务，再为实际生成的题写 `Prompt Task: …`。同一 Intent 可以承载多种任务；Task 不决定 `analysis_type` 或 `formal_visibility_eligible`，也不新增第七类 Intent。任务与合同的判定见 [代表性题库适配规则](../../geo-after-sales-prompt-builder/references/representative-library.md#prompt-task-and-intent)。

首批只生成现有 Discovery 合同可承接的任务，例如不点名品牌的候选发现、短名单选择，或不点名品牌且仍要求供应商候选的替代方案探索。纯“如何解决”方法题、具名竞品替代题、交易和购买后支持题不因为任务名称进入 Discovery；无合适合同的只留在内部候选，不伪装成售前正式题库。

## 4. 先发现型，后补诊断

新产物显式写 `config.generation_stage`：

| 阶段 | 产物 |
|---|---|
| `discovery`（默认生成） | 只生成 Discovery，其他五类配额 0；每 Topic 至少 5 条独立购买问题。 |
| `diagnostic`（用户要求补充） | 保留发现型问题，按需要补竞品、评价和品类认知；没有固定题型配额，每 Topic 合计至少 5 条。 |

两阶段整批均不得超过 50 条。Verification / Accuracy 继续走独立事实核验合同，不在此开启。省略阶段的历史题库仍按旧完整诊断规则校验，不能靠删掉字段绕过缺题检查。补题超限时先确认范围，不删除或重写已锁定 Discovery。Discovery 数量不要求均衡；如果已知后续有 diagnostic 题，先预留后补预算，不把首轮机械扩到 50 条。

补充 `diagnostic` 时保存原始题库，运行 validator 时用 `--baseline` 传入，实际比对原 Discovery ID/题面/路由等是否原样保留；只检查新题库的总数不够。

把生成前规划出的实际数量写入 `quotas`。`per_topic` 是未单列 Topic 共用的默认实际配额，不是固定模板或系统默认值；题量不同的 Topic 必须写入 `topic_overrides`。`intent_tags` 必须等于各 Topic 实际配额之和，并与最终问题数和 `expected_total` 一致。

Discovery 数量不要求各 Topic 对称。若某 Topic 无法形成 5 个独立购买意图，反馈给上游补证据、合并或调整 Topic；不要填同义题达到下限。

### Discovery：至少 5 条，优先覆盖购买入口

全部要求具体品牌、制造商、供应商、平台或产品候选，且不得出现目标品牌或正式竞品名称。题面必须包含候选触发名词（provider、manufacturer、supplier、tool、platform、solution、brand 等品类对应词）；缺少触发词的问句会得到操作建议而不是品牌清单，属于格式错误而非语义偏好。

Discovery 的规划顺序：

1. 每 Topic 先保留自然、无限定条件的购买入口，再从真实买家、场景、市场、约束和评价标准选出其余独立意图。品类叫法来自已收集证据，不自造，也不把每个同义叫法都算一条新需求。
2. 让已有 P1 至少各被一题覆盖；每题只承担一个主要购买决策，允许必要的复合条件。

**限定条件按四类归槽，槽名以 PRD「细分主题」为准，不要另造别名：无限定条件 / 目标用户 / 偏好标准 / 约束。** 痛点属于「偏好标准」，不是第五类。宽泛 Topic（Coverage）单条不带条件或最多 1 个低复杂度主要条件，**不得组合**；细分 Topic（Depth）可用 1 个或组合多个，整组要系统包含有意义的复合条件题——同一问题结合 2 个以上真正影响选择的条件，不设固定子配额，也不为显得深入机械堆叠。
3. 对每个候选新增题执行三门检查：Case 有明确来源、真实买家在具体角色或场景下会问、答案会改变独立决策。任一不满足就不生成。
4. 为能形成不同候选集合、比较边界或决策结果的 P2 增题；目标客户、场景和痛点只有在会改变答案时才单独成题。
5. 适用边界、交付限制或采购约束能改变候选结果时，可各形成一题；供应稳定性、交期、认证文件、备件和售后等采购关注点不因“不是产品参数”而排除。
6. 只有 P1/P2 已充分覆盖且仍有明确增量价值时才使用 P3。某个 Topic 已覆盖所有重要决策关注点后立即停止，即使其他 Topic 题量更多或更少。
7. 比较全量题库做语义去重。**去重的单位是购买决策，不是措辞**：两题若指向同一购买决策（同一候选集合、同一比较维度、同一改变答案的条件），只保留一题；只有买家、地区、场景或决策阶段变化才算新题。仅措辞或品类同义词变化，不增加购买意图时合并；需求不同的问题不能因一次回答相似就合并。若用户另要措辞实验，单独标记实验目的，不把变体算进独立意图覆盖。

宽泛 Topic 保留品类供应商发现视角；细分 Topic 锚定购买场景。问题可长可短，不强制 SEO 短词风格，不以假定的长短句比例凑题。不要只问定义、方法或标准清单。

**宽 Topic 必须落到切面，并标出配题重心。** 一个 Topic 下能识别出多个彼此不同的买家需求时，逐条写明它落在哪个切面（例如亚太覆盖下同时存在「区域覆盖广度」「跨市场行程」「本地内容与低价航司」「本地语言服务」「多供应商数据整合」），再标明这道题属于哪一面。配题重心放在**差异化优势与买家需求重合**的那个切面上，其余切面按次要处理。**不要用「一个宽标签下面每题讲一个不同需求」的方式把 Topic 撑开**——那样看着有 8 道题，实际每一面都只有 1 道，覆盖强度是假的。

### 按需补充 Competitor

选择有实际比较需求的当前 Topic 适用竞品，用中性一对一模板，包含具体场景、两个具名品牌和选择任务。同组两题以上时，除竞品名称外，题面及 Attribute Tags 同构，不预设胜者。没有“每个竞品必须一题”的配额，也不跨 Topic 借竞品补数。

### Verification × 0

默认不生成 Verification 题。保留 Verification 作为意图定义：批量验证 AI 是否正确认知目标品牌与当前 Topic 下多个关键 Attribute 的关联，逐项输出 `Yes / No / Unknown + 判断依据`，适用阶段为第二轮售前（高意向/定向验证）和售后。P1 的属性级正确性核查并入 Accuracy 合同。只有用户明确要求时，才在独立合同下单独确认产物，不得从 Case 或模型记忆临时补真值，也不在默认售前题库中生成 `validation_items`。

### Accuracy × 0

默认不生成 Accuracy 问题，不读取或要求 `fact_value / official_source_url / fact_checked_at`。如用户明确要求 Accuracy，先停止默认生题流程并确认独立的事实核验输入与产物合同；不得从 Case 声明、模型记忆或第三方页面临时补值。

### 按需补充 Evaluation

对选中的目标品牌或适用竞品使用同一固定模板：

`Evaluate the {category_label} {company|product} {brand_name} on {evaluation_scope}`

`company|product` 由 `brand_object_type` 决定。品类与 Topic 归一后相同时省略范围从句。实际句式来自 [语言注册表](locale-templates.json)；`evaluation_scope` 转为具体业务范围。每题只出现一个目标品牌或适用竞品；比较评价时保持同问法，不要求逐个补齐。英文题面不得出现元词 `topic`。

### 按需补充 Category Awareness

不出现任何品牌，使用品类优先固定模板：

`What is a {category_label}, and how should I evaluate one for {topic}?`

当 `category_label` 与 `topic` 归一后相同（忽略大小写、标点与复数）时，Topic 只是在复述核心品类，此时省略范围从句，改用短式：

`What is a {category_label}, and how should I evaluate one?`

先确认购买品类，再询问评价标准；它描述市场认知，不衡量目标品牌主动提及。句式同样取自语言注册表中 `locale` 对应的条目。

## 5. 逐题写作规则

按题面自查以下四条，任何一条不满足都属于写作错误，不是风格问题：

- **意图与格式匹配**：Discovery 缺候选触发词会得到建议清单；Competitor 缺场景或缺明确推荐要求会得到骑墙回答；Verification 写成开放题会得到清单而非逐项判断；Evaluation 缺明确评价任务会得到品牌罗列。发现格式漂移时按对应题型的修复动作改写：补触发词、补使用场景、改成逐项判断、改成明确评价。
- **不引导答案**：题面不得预设目标品牌的优点、期望结论或"为什么 X 很好"式前提。问题测量的是意图本身，不是希望看到的答案；带引导的题产生的读数没有诊断价值。
- **消除歧义**：缩写首次出现必须展开成 Case 字段支持的全称；跨品类歧义的称呼（同一词在不同行业指不同产品）必须补品类限定。监测 Prompt 没有第二轮澄清机会，歧义必须在题面内解决。生成非英文题库时，逐题确认本地化 `category_label` 仍写在题面里：英文源题面每题都重复品类限定，本地化为了简练把它删掉会让问题落到别的品类上，validator 会直接判失败。
- **买家语境具体化**：条件题的角色、企业类型和使用场景只能来自 `目标客户 n / 使用场景 n / 目标企业画像` 等 Case 字段；具体买家语境会显著改变候选集合，但不得从输入外补造行业、规模或地域。
- **关注点不只来自产品参数**：Attribute 可以是能力，也可以是场景、痛点、采购约束、供应风险或适用边界。不要为精确规格本身创建 Attribute，先把规格抽象成买家会比较的能力，如 flow range、oxygen purity、noise、certification；精确数值只作为 `source_value` 证据。只有买家真实会用该数值筛选时才写入 Discovery；单型号、认证编号或其他需要独立真值的精确事实进入 `accuracy_only`，不要把本品牌独有的 USP 参数改写成全市场硬门槛。

## 6. 二遍 review

第一遍检查业务边界、证据、独立买家意图和已有属性规划，逐 Topic 判断重要决策关注点是否覆盖，不以题量对称作为通过条件。第二遍逐题检查自然问法、单一任务、品类、无品牌泄漏、无引导、翻译和 Tags。整批确认阶段、每 Topic 至少 5 条、总量不超过 50、真实配额与题数一致；对每条新增题复核三门检查。只检验本次确实补充的题型，不因为尚未补竞品或评价而拒绝发现型产物。

交接保留版本、来源、客户确认状态和待试跑项。采集流程试跑后只校正歧义、跑题、重复和诱导；没有目标品牌不是题目失败。新增或修改题需要重新 QA，不以挑选有利回答的方式优化题库。选题用「有需求 × 有资格赢 × 可交付」三项联合判断，其中「能不能赢」的判法：竞品优势若来自品牌知名度或广泛媒体共识，短期不可逆转，该方向只作基线；不来自共识的方向才是 90 天内可推进的战场。不能因为单次或零提及删题。
