# 问题质量门（v8）

## 输入硬门

- 输入字段来自系统接口提交的同一评测 Case：公司与品牌、业务 / 产品、业务模式、品类、目标企业画像、目标客户、痛点、使用场景、产品特性、差异化优势、适用边界、购买标准、集成与兼容、信任与合规、地理与市场、1–3 个 Topic、官方域名、三组正式竞品及官网域名、补充内容。上游 Case Builder 通常产出 2–3 个 Topic，其中 1 个 Coverage Topic、1–2 个 Depth Topic；单 Topic 输入仍受支持。
- `补充内容`字段必须存在但允许为空；为空或未声明 Topic 局部竞品边界时，三组正式竞品均适用于全部 Topic。
- 纯 `B2C` Case 的 `目标企业画像`、`购买标准`、`集成与兼容`、`信任与合规` 必须整行省略；`B2B` 与 `B2B / B2C` 仍需非空。
- 不要求或读取旧 `target_attributes` 作为 v8 输入；不存在根据未采集回答预写的 `observed_associations`。
- `config` 只包含 v8 合同声明的字段；拒绝 `target_audiences / pain_points / use_cases` 等平行输入合同和未声明配置。
- `attribute_plan` 对每 Topic 恰好一项，新产物属性数不设配额；Attribute 可以是产品能力，也可以是场景、痛点、采购约束、供应风险、交付要求或适用边界。P1/P2/P3 可空但已有 P1 必须被 Discovery 覆盖。每项精确回指 Case 原字段，不要求客户交完整属性或旅程矩阵。历史未声明阶段的合同仍保留原属性数量检查。
- P3 仍必须影响购买认知；纯目录事实与无决策价值文案进入 `excluded.route=exclude`，非具体型号 Topic 下的单款 SKU 精确值进入 `excluded.route=accuracy_only`。
- Topic 标签中的“宽泛/细分”不成为 `topic_type`；Case 级正式竞品恰好三个且各有官网域名。存在 Topic 局部竞品边界时，每个竞品用 `topic_ids` 显式声明适用范围，每个 Topic 至少有一个适用竞品。
- Accuracy 默认配额为 0；输入不要求上游事实包，默认产物不包含 Accuracy 题或事实包字段。

## 逐题硬门

- `topic_id` 能回指当前 v8 配置；问题字段不依赖旧的逐题 `attribute_ids` 或单独 `attributes`。
- `tags` 是非空且归一后无重复的自由字符串数组；每题恰好一个默认 `Intent: …` 和一个 `Brand Scope: …`，允许增加其他自由 Tag。单个 Tag 不得包含 CSV 保留分隔符 `;`。
- `Brand Scope: Branded / Non-Branded` 与题面实际是否出现目标品牌或正式竞品一致。
- 每个 `Attribute: …` 都回指当前 Topic 的 `attribute_plan` **里 P1/P2/P3 的条目**，不得回指 `excluded` 条目（`route=exclude` 与 `accuracy_only` 都不行）——被排除的候选项没有资格作为任何题目的 Attribute，换个说法也不行。同名 Attribute 可跨 Topic，不能把其他 Topic 的属性串入当前题。该条已由 validator 确定性执行。
- 问题自然、独立、可回答、单一任务、品类可识别、前提中性；中英文等义。
- Discovery 的限制条件必须来自买家真实筛选逻辑。Attribute 先写买家会比较的能力、场景、痛点或约束，不以精确规格命名；精确规格只作 `source_value` 证据，单型号、型号参数、认证编号或需要独立真值的阈值进入 `accuracy_only`，不得改写成全市场硬门槛。
- Discovery 明确要求具体候选，不出现品牌；每题一个主要购买决策，可含真实场景必要的复合条件，但不能堆叠只让本品符合的 USP。
- 非 `en` locale 的 Discovery 题面必须写出本地化 `category_label`（归一化后逐字包含）。本地化时删掉反复出现的品类限定词，会让监测问题落到别的品类上，判定失败；英文题库不受此检查，品类称呼变体由人工语义复核把关。
- 补充 Competitor 时只比较目标品牌与当前 Topic 的一个适用竞品；新产物不强制每个竞品都出题。同组两题以上时，除竞品名称外题面完全相同。
- Verification 配额为 0，默认题库不生成 Verification 题；P1 的属性级正确性核查并入 Accuracy 合同。题库里出现 Verification 题即为失败——下游 `attribute_diagnostics` 只按配对 Discovery 与 Evaluation 派生，不依赖 Validation 样本。
- 默认产物不生成 Accuracy 题；如用户明确要求，先使用另行确认的事实核验合同，不临时复用默认 Builder 合同。
- 补充 Evaluation 时每题只评价一个目标品牌或当前 Topic 适用竞品；不强制逐品牌覆盖。Evaluation 和 Category Awareness 仍用固定模板，品类与 Topic 相同时省略范围从句，英文题面不出现元词 `topic`。
- `analysis_type` 与 `formal_visibility_eligible` 精确匹配 v8 分流表：Discovery 为 `visibility,sentiment`/`true`，Competitor 与 Evaluation 为 `sentiment`/`false`，Verification 与 Accuracy 只在独立合同下使用（售前配额 0，不产生题），Category Awareness 无 `analysis_type` 且 `formal_visibility_eligible=true`。自由 Tags 不改变路由。
- `monitoring_prompt` 等于 `user_question`；`intent_key` 唯一；不存在 `diagnosis_intent / attributes / topic_type / question_type / funnel_intent / decision_stage / metric_scopes / attribute_pool / attribute_id / attribute_ids / priority_attribute_ids / paired_discovery_ids`。

## 整批硬门

- Topic 数为 1–3；总题量不得超过 50。每 Topic 与聚合配额、`expected_total` 和最终题数必须一致。
- `diagnostic` 补充必须通过 `--baseline` 对照原始题库；原 Discovery 的 ID、题面、翻译、Tags、意图键和路由，以及 Case/Topic/语言保持不变。缺原件、缺题或改题即失败。提供 baseline 时，即使读历史题库也执行此对照。
- 新产物必须声明 `generation_stage`。`discovery` 只含 Discovery；`diagnostic` 按需补题，没有固定竞品、评价或品类认知配额。每 Topic 至少 5 条、整批最多 50；Verification / Accuracy 仍 0。省略阶段的历史题库继续按旧完整题库配额校验，不静默放宽。
- `quotas.per_topic` 是未被 override Topic 共用的默认实际配额；`quotas.topic_overrides` 必须声明所有不同 Topic 的实际配额；`quotas.intent_tags` 必须等于各 Topic 实际配额之和。
- Discovery 覆盖已有 P1，其余按独立购买价值选择；每 Topic 至少 5 条不是 5 个品类同义词，也不要求各 Topic 数量相等。先判断该 Topic 的重要决策关注点是否已覆盖，覆盖完成后停止扩题。无法满足时补证据或交上游调整 Topic。报告侧正式可见度指标只按 Discovery 计算，Category Awareness 不进分母。
- 每条 Discovery 题面归一后唯一，并明确要求具体品牌、制造商、供应商、产品或解决方案候选。
- 去重的单位是**购买决策**，不是措辞。两题若指向同一购买决策（同一候选集合、同一比较维度、同一改变答案的条件）即视为重复，只保留一题；只有买家、地区、场景或决策阶段发生变化才算新题。题面归一后唯一只能拦住「换同义词／换语序／换 best·top」，**语义相同但问法不同的两题必须人工复核后合并**——典型漏网是把「一次出差跑多个国家」和「同时订中国国内与区域行程」并列，两者是同一个决策。
- 补充的 Competitor 同组两题以上时通过控制变量检查，使用不适用竞品即失败；未补竞品题不构成失败。
- 补充的 Evaluation 单题出现多品牌、缺失被评价品牌或使用不适用竞品即失败；未覆盖所有品牌不构成失败。
- Discovery 的 Attribute Tags 覆盖每个 P1，其余单属性题优先覆盖 P2；Competitor 的维度与 Attribute Tags 来自双方可比的 P1 和高优先 P2。P3 只补余量。
- 不存在伪重复或输入外虚构条件，也不把 Case 品牌自述直接当成已核验真值。同一 Case 字段跨 Topic 重复使用是允许行为。每条新增 Discovery 都能说明：Case 来源、具体买家/场景，以及它如何改变候选集合、比较维度、采购偏好或适用判断；只因题量不足、属性看起来有趣或模型常识推断而新增，均不通过。
- Prompt Builder 全程不调用 `web-access`，不搜索、打开或重新核验目标品牌官网。

## 交接与试跑

- 交接记录真实来源、客户确认文档与状态、版本、待确认项；程序通过不等于客户批准或已经完成试跑。
- 售后采集流程在正式基线前对每道候选题于拟监测平台各试跑 3–5 次，只检查回答任务、歧义、诱导和跑题；本品未出现不是不合格，不依照提及结果挑题。试跑不进入正式基线。
- **「能不能赢」是选题三项联合判断（有需求 × 有资格赢 × 可交付，见《售后生词规则》§3–§4）里的一项，不能单独用。** 判断方法：**竞品优势若来自品牌知名度或广泛媒体共识，短期不可逆转，该方向只作基线；不来自共识的方向才是 90 天内可推进的战场**。可以把共识锁死的方向排为基线而不为它新配题；反向同样成立：**不能因为单次或零提及就删除既有题**，那会污染可见度测量。
- 修改与新增 Prompt 都重新 QA；售前历史样本保留，售后正式基线另锁版本。仅继承同题、同配置历史，不把新旧问题混成同一基线。

## 本地化专项复核

非英文题库在语义警告之外逐题确认：题面是否仍写明本地化 `category_label`。英文源题面反复出现品类限定是正常的；本地化为了简练把它删掉，题面会退化成光秃秃的"哪些平台 / which platform"，模型随即改答别的品类——泰语题库曾因此在 34 道 Discovery 中丢掉 32 道品类限定，采集回来的回答有 9 条完全答成语言学习 App 和线上外教。该检查已由 validator 确定性执行，不要只依赖人工阅读。

## 语义警告

确定性 validator 通过后仍需人工复核：Topic 是否确实为完整监测机会，跨 Topic 能力、场景或痛点是否正确进入 Attribute；P1 是否真正决定入围，P2 是否明显影响比较，P3 是否仍有购买参考价值，应排除事实是否被降级塞入 P3；中文源字段是否被英文扩写成新事实；每个 Topic 的重要决策关注点是否覆盖且没有为均衡数量凑题；每条新增题是否通过 Case 依据、真实买家问题、独立决策三门；Discovery 是否先覆盖 P1/P2；Discovery 是否包含候选触发名词而非操作建议问法，品类称呼变体是否全部来自 Case 字段；Competitor 是否同时具备使用场景、两个具名品牌和明确推荐要求，而不是软性 Compare；题面是否引导答案或预设目标品牌优点；缩写和跨品类歧义称呼是否已在题面内消解；Tags 是否准确且不过度标注；Topic 局部竞品是否跨界；竞品题是否保持控制变量；Verification 是否暗示正向答案；固定模板译文是否弱化限定。
