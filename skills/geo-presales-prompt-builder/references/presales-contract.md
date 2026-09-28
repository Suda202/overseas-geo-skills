# 海外 GEO 售前问题库契约（v8）

## 输入字段合同

v8 直接接受系统接口提交的评测 Case 中文业务字段，不要求 `target_attributes`，也不把输入改造成另一套 Builder 字段：

| 基础字段 | 可编号字段 | 主题与竞品字段 | 补充字段 |
|---|---|---|---|
| `公司名`、`业务 / 产品名称`、`品牌名称`、`业务模式`、`品类`、`目标企业画像` | `目标客户 1…n`、`痛点 1…n`、`使用场景 1…n`、`产品特性 1…n` | `主题 1…n（宽泛/细分）`（1–3 个）、`官方域名`、三组 `竞品 n` 与 `竞品 n 官网域名` | `差异化优势`、`适用边界`、`购买标准`、`集成与兼容`、`信任与合规`、`地理与市场`、`补充内容` |

**格式兼容说明**：Prompt Builder 同时接受以下两种接口输入格式：
- **单字段合并格式**：`痛点`、`使用场景`、`产品特性`、`目标客户` 各为一个字段，多个值用 `，` 分隔；`主题` 为一个字段，1–3 个主题用 `，` 分隔，不带类型标注。
- **编号字段格式**（历史兼容）：`痛点 1…n`、`使用场景 1…n` 等分字段；`主题 1…n（宽泛/细分）`，括号标注仅作理解提示，不输出到 v8 字段。
若两种格式混合出现，以实际内容语义为准。构建 JSON 时将合并多值展开为上述编号格式写入 `config.case_fields`，并让 `source_field/source_value` 回指展开后的值；在交接记录保留原 Record 与合并字段。validator 校验的是该规范化产物，不直接接受未展开的 Base Record。此为序列化适配，不是要求客户另填一套业务字段。

括号中的“宽泛/细分”只帮助理解 Topic，不输出 `topic_type`。上游通常产出 1 个 Coverage + 2 个 Depth，证据不足时保留 1 + 1；单 Topic 输入仍受支持。品牌、品类、至少一个 Topic、官方域名以及三组竞品名称和官网域名为硬必填；`目标企业画像`、`购买标准`、`集成与兼容`、`信任与合规` 只服务 B2B，纯 `B2C` 必须整行省略。`补充内容`必须保留但允许为空；为空时三组正式竞品适用于全部 Topic。业务字段与研究证据应支持每 Topic 至少 5 个独立发现型意图，不要求凑 3–5 个属性或完整客户旅程。

Accuracy 默认配额为 0，不需要上游事实包，也不产生 `fact_value / official_source_url / fact_checked_at`。如用户明确要求 Accuracy，先单独确认事实核验输入和产物合同，不把 Case 声明直接当成已核验真值。

## Topic、Attribute 与 Tags

- Topic 是 Prompt 集合的主组织单元，代表可长期独立监测的市场、场景或战略机会。每题只回指一个 `topic_id`。
- Attribute 是希望 AI 形成的战略认知、能力、特征或评价标准。Builder 在 `attribute_plan` 中按 Topic 规划优先级，逐题使用 `Attribute: …` Tag 建立关联；同名 Attribute 可以跨 Topic 聚合。
- Tags 是统一的自由字符串数组，承接诊断意图、品牌范围、Attribute 和其他横向分类。默认使用命名空间以避免同名冲突，不另建逐题 `attributes` 字段。

## 固定结构

- `schema_version=overseas-geo-question-bank/v8`
- 1–3 个 Topic，总题量不得超过 50。
- 新产物显式写 `config.generation_stage`：默认 `discovery` 只含 Discovery，其他五类配额为 0；按需补题时用 `diagnostic`，竞品、评价和品类认知数量按实际需求填写，无固定配额。Verification / Accuracy 仍为 0，单独走已确认的验证合同。
- 每 Topic 至少 5 条、整批（含后补题）不超过 50。先确定独立发现型意图，不靠同义改写、品牌名替换或复制字段凑数。6/8/8 只是首轮分配示例。
- 补充题不改变已有 Discovery 的 ID、题面或来源；若需修改，必须留变更记录，不能把前后题当同一监测样本。
- `quotas.per_topic` 保存未被 `topic_overrides` 单列 Topic 共用的默认实际配额；`topic_overrides` 表达不同 Topic 的实际差异，不只用于适用竞品数不同的情形。`quotas.intent_tags` 必须等于各 Topic 实际配额之和。`expected_total` 必须等于最终题数。
- 正式可见度指标只统计 Discovery；后端管线 eligibility 与指标分母不是一回事，见共享映射。
- v8 不包含 `diagnosis_intent`、逐题 `attributes`、`topic_type`、`question_type`、`funnel_intent`、`decision_stage`、`metric_scopes`、`attribute_pool`、`attribute_id`、`attribute_ids` 或 `priority_attribute_ids`。
- v8 必须包含 Builder 派生的 `attribute_plan`；每 Topic 恰好一项，同一 Attribute 和源字段允许被多个 Topic 使用，不做唯一归属。

v8 的 `config` 是闭合合同，只允许 `case_fields / brand_name / brand_object_type / category_label / official_domain / derived_field_sources / topics / attribute_plan / expected_total / quotas / competitor_selection / locale / generation_stage`。拒绝平行业务字段。客户确认文档、市场、研究证据、版本和 QA 状态放独立交接文件，不塞入该配置。

`generation_stage` 只接受 `discovery / diagnostic`，不能从实际题型猜测阶段。历史 v8 未声明阶段时仍沿用原规则：Discovery 至少 5，Competitor `n`，Evaluation `1+n`，Category Awareness `1`，Verification / Accuracy `0`；保持旧缺题检查。新产物必须显式声明阶段，不能仅删字段伪造历史合同。

显式 `diagnostic` 是对原题库的补充，验证时必须通过 `--baseline` 提供原始 Discovery 或未声明阶段的历史 v8。Python 调用使用 `validate(data, baseline)`。原 Case、Topic、语言与所有原 Discovery 的 ID、题面、翻译、Tags、意图键和分析路由必须保留；缺失或改写均失败。若需要实质校正，走新版本 Discovery/售后维护流程，而不是伪装成纯补题。

`locale` 可选，默认 `en`，取值必须是 [语言注册表](locale-templates.json) 中已登记的键。它只决定**题面语言**：`user_question / monitoring_prompt` 使用该语言的文字，Evaluation 与 Category Awareness 由注册表里该语言的固定模板生成；因为 `category_label` 与 Topic 文本会嵌入这两类题面，非 `en` 题库应把这两个显示名改写成该语言。Case 字段、Tags 与翻译保持原有写法。非 `en` 题库应在每题保留 `en_translation`，便于与英文基线对照。

新增一门语言只需在 `locale-templates.json` 增加一个条目（四个模板、company/product 标签、候选名词与疑问词），不改 validator 代码；未登记的语言会被 validator 拒绝，构建期回落英文模板。

## `attribute_plan` 合同

- 每个 Topic 恰好一项，只包含 `topic_id / priorities / excluded`。
- `priorities` 恰好包含 `P1 / P2 / P3`，新分阶段产物按实际需要填写且均可为空，不设数量配额。未声明阶段的历史合同保留 P1 3–5、P2 建议 5–10、P3 0–10。
- P1 / P2 / P3 表示 Attribute 在当前 Topic 下的优先级，不是 Attribute 类型或 Prompt 优先级；这些分档属于本项目的生成合同，不是 Profound 原始分类。
- 各项含 `attribute / source_field / source_value / decision_reason`；P1 的 `verification_statement` 在新阶段可省略，继承时若保留须非空；历史合同必须有该字段。P2/P3 不包含它。
- `excluded` 可为空；每项包含 `candidate / source_field / source_value / reason / route`，`route` 只允许 `exclude` 或 `accuracy_only`。
- 当前 Topic 的 `validation_items` 和 Verification 的 Attribute Tags 与 P1 的强绑定已随 Verification 配额归 0 暂停使用；完整示例见 [属性规划](attribute-planning.md)。
- **下游后果**：后端 `attribute_diagnostics` 原本依赖 Validation 样本，配额归 0 后 `validation_question_ids` 为空，只能从配对 Discovery（「是否被主动推荐」）与 Evaluation（「是否知道」）派生；派生不出时后端须提交全 `unknown`。这是采集端与后端的事实来源，本 Skill 只负责让题库如实反映「没有 Verification 题」，不补题、不在题库里预留 Validation 字段。

## Case / Topic 示例骨架

下列是未声明阶段的历史完整诊断片段，只供旧数据读取；省略了必填的 `attribute_plan`。新发现型的配额示例见下文，不照抄该片段的题型数量。

```json
{
  "schema_version": "overseas-geo-question-bank/v8",
  "config": {
    "case_fields": {
      "公司名": "Shanghai Edgelight Industry Co., Ltd.",
      "业务 / 产品名称": "LED Display and Commercial Display Solutions",
      "品牌名称": "Edgelight",
      "业务模式": "B2B",
      "品类": "LED 显示屏制造商与商业显示解决方案提供商",
      "目标企业画像": "商业 AV 零售与商业地产 企业设施 舞台与体育场馆",
      "购买标准": "像素间距与画质 结构与安装适配 认证与文件 交付与售后能力",
      "集成与兼容": "与内容控制 播放与控制系统对接",
      "信任与合规": "国际认证与合规文件 项目验收要求",
      "目标客户 1": "商业 AV 集成商与 LED 显示屏分销商——关注参数 集成与服务",
      "目标客户 2": "零售 商业地产与品牌体验团队——关注视觉效果 可靠性与项目成本",
      "目标客户 3": "企业 政企园区与会议设施团队——关注清晰度 文件与维护",
      "目标客户 4": "舞台制作 体育场馆与活动技术团队——关注亮度 刷新率与结构灵活性",
      "痛点 1": "项目团队难以让像素间距 亮度 刷新率 观看距离与结构适配具体场馆",
      "痛点 2": "安装调试 文件 认证与售后缺口会延误交付并提高项目总成本",
      "使用场景 1": "在企业与商业空间安装固定式 LED 显示屏",
      "使用场景 2": "为裸眼 3D 舞台与场馆打造创意沉浸式 LED 体验",
      "产品特性 1": "室内外 固装 租赁与创意 LED 显示产品组合",
      "产品特性 2": "像素间距 亮度 刷新率 色彩与画质能力",
      "产品特性 3": "结构定制与内容控制集成",
      "产品特性 4": "项目设计 安装调试 文件 认证与售后服务",
      "差异化优势": "具备 20 多年 LED 领域经验 同时覆盖 LED 显示屏 电源 控制器 广告照明产品与项目解决方案 官网声明拥有五座全球生产基地 产品销往 50 多个国家并获得 100 多项国际认证",
      "适用边界": "只采购 LED 照明 驱动电源 控制器 广告照明配件或不需要 LED 显示屏的完整建筑 AV 与媒体制作服务的客户",
      "主题 1（宽泛）": "LED 显示屏制造商与商业显示解决方案提供商",
      "主题 2（细分）": "面向企业与商业空间的固定安装 LED 显示解决方案",
      "主题 3（细分）": "面向裸眼 3D 舞台与场馆体验的创意沉浸式 LED 显示屏",
      "官方域名": "https://edgelight.com",
      "竞品 1": "SANSI LED (Shanghai Sansi)",
      "竞品 1 官网域名": "https://www.sansi.com",
      "竞品 2": "Unilumin",
      "竞品 2 官网域名": "https://en.unilumin.com",
      "竞品 3": "LianTronics",
      "竞品 3 官网域名": "https://www.liantronics.com",
      "补充内容": "本次只在 LED 显示屏制造与商业显示解决方案范围内评测边光 不把 LED 电源 控制器 装饰照明 广告灯箱和物联网产品混入同一主题。官网列出室内外全彩屏 租赁屏 创意显示 玻璃相关显示与 LED 地砖屏等产品 并展示政企园区 商业环境和裸眼 3D 解决方案 项目案例覆盖商业项目 舞台剧场 会议显示 体育场馆和标识标牌。买家主要比较像素间距 亮度 刷新率 观看距离 色彩与画质 室内外耐候 结构定制 内容与控制集成 安装调试 服务 文件 认证 交期和项目总成本。SANSI LED Unilumin 与 LianTronics 作为可比的 LED 显示与解决方案提供商保留 仅照明或通用 AV 供应商不纳入本 Case。"
    },
    "brand_name": "Edgelight",
    "brand_object_type": "company",
    "category_label": "LED display manufacturer and commercial display solution provider",
    "official_domain": "https://edgelight.com",
    "derived_field_sources": {
      "brand_name": "品牌名称",
      "category_label": "品类",
      "official_domain": "官方域名"
    },
    "topics": [
      {
        "topic_id": "topic_1",
        "topic": "LED display manufacturers and commercial display solution providers",
        "source_field": "主题 1（宽泛）",
        "source_value": "LED 显示屏制造商与商业显示解决方案提供商"
      },
      {
        "topic_id": "topic_2",
        "topic": "fixed-installation LED display solutions for corporate and commercial spaces",
        "source_field": "主题 2（细分）",
        "source_value": "面向企业与商业空间的固定安装 LED 显示解决方案"
      },
      {
        "topic_id": "topic_3",
        "topic": "creative immersive LED displays for naked-eye 3D, stage and venue experiences",
        "source_field": "主题 3（细分）",
        "source_value": "面向裸眼 3D 舞台与场馆体验的创意沉浸式 LED 显示屏"
      }
    ],
    "expected_total": 41,
    "quotas": {
      "intent_tags": {"Intent: Discovery": 17, "Intent: Competitor": 9, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 12, "Intent: Category Awareness": 3},
      "per_topic": {"Intent: Discovery": 5, "Intent: Competitor": 3, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 4, "Intent: Category Awareness": 1},
      "topic_overrides": {
        "topic_1": {"Intent: Discovery": 7, "Intent: Competitor": 3, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 4, "Intent: Category Awareness": 1}
      }
    },
    "competitor_selection": {
      "status": "frozen",
      "selection_count": 3,
      "formal_competitors": [
        {"name": "SANSI LED (Shanghai Sansi)", "official_domain": "https://www.sansi.com", "source_fields": ["竞品 1", "竞品 1 官网域名"]},
        {"name": "Unilumin", "official_domain": "https://en.unilumin.com", "source_fields": ["竞品 2", "竞品 2 官网域名"]},
        {"name": "LianTronics", "official_domain": "https://www.liantronics.com", "source_fields": ["竞品 3", "竞品 3 官网域名"]}
      ]
    }
  },
  "questions": []
}
```

`formal_competitors[].topic_ids` 为可选字段。省略时表示该竞品适用于全部 Topic；Case 的补充内容声明局部边界时必须填写非空 Topic ID 数组。例如 Botslab 使用 `70mai → [topic_1]`、`Reolink → [topic_2]`、`aosu → [topic_2]`。三组竞品仍是 Case 级正式集合，但 Competitor 题按 Topic 子集生成。

新发现型配置片段（其余 Case、Topic、规划字段沿用已有合同）：

```json
{
  "generation_stage": "discovery",
  "expected_total": 22,
  "quotas": {
    "intent_tags": {"Intent: Discovery": 22, "Intent: Competitor": 0, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 0, "Intent: Category Awareness": 0},
    "per_topic": {"Intent: Discovery": 8, "Intent: Competitor": 0, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 0, "Intent: Category Awareness": 0},
    "topic_overrides": {
      "topic_1": {"Intent: Discovery": 6, "Intent: Competitor": 0, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 0, "Intent: Category Awareness": 0}
    }
  }
}
```

生成 Builder 派生的 `attribute_plan`，但不生成 Attribute ID 或单独的逐题属性字段。同一 Attribute 与 `source_field / source_value` 可以出现在多个 Topic 中；逐题通过 Attribute Tag 关联，默认不读取 Accuracy 事实包。

## 每题字段

所有问题必填：

- `question_id`：全批唯一。
- `topic_id`：回指 1–3 个正式 Topic；不附带 `topic_type`。
- `tags`：非空字符串数组；新题默认至少包含一个 `Intent: …`、一个 `Brand Scope: …` 和一个 `Prompt Task: …`，按题面需要包含零个或多个 `Attribute: …`，也允许增加其他自由 Tag。历史题库缺少 Task 标签不因此失效；`Prompt Task` 只描述买家任务，不改变分析路由。
- `analysis_type`：按 v8 的 Prompt 生成角色填写。
- `formal_visibility_eligible`：按 v8 的 Prompt 生成角色填写，决定是否进入正式可见度题集。
- `intent_key`：全批唯一，不能只换措辞伪造新意图。
- `user_question / zh_translation / monitoring_prompt`：英文根问题、等义中文和采集字段；`monitoring_prompt` 必须等于 `user_question`。
- `quality_checks`：已执行的检查全部为 `true`。

默认题库不包含 Verification 题与 `validation_items`、Accuracy 题或事实包字段。如用户明确要求 Verification 或 Accuracy，先单独确认产物合同，不临时复用默认 Builder 合同。

## Tags 合同

`tags` 字段接受任意非空字符串，不设全局封闭枚举。单个 Tag 不得包含分号 `;`，以便 JSON 被其他兼容适配器安全序列化；当前上传 CSV 本身不输出 Tags。Builder 默认使用以下常用命名：

| 命名空间 | 默认值与规则 |
|---|---|
| `Intent: …` | 每题恰好一个常用生成角色：`Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。六类数量必须符合每 Topic 写入的实际配额；仍可添加其他非默认自定义 Intent Tag。 |
| `Brand Scope: …` | 每题恰好一个。题面出现目标品牌或正式竞品时为 `Branded`，否则为 `Non-Branded`；以实际题面为准。 |
| `Attribute: …` | 零个或多个；名称必须来自当前 Topic 的 `attribute_plan`。Discovery 的 Attribute Tags 整批覆盖全部 P1；同名 Attribute 可跨 Topic。 |

其他自由 Tags 建议继续使用 `Namespace: Value`，例如 `Lifecycle: Consideration`、`Region: North America`。增删这些 Tags 不得改变分析路由。

## 分流合同

| 默认诊断 Tag | analysis_type | formal_visibility_eligible |
|---|---|---|
| `Intent: Discovery` | `visibility,sentiment` | `true` |
| `Intent: Competitor` | `sentiment` | `false` |
| `Intent: Verification` | 空 | `false` |
| `Intent: Accuracy` | `accuracy` | `false` |
| `Intent: Evaluation` | `sentiment` | `false` |
| `Intent: Category Awareness` | 空 | `true` |

报告侧正式可见度与聚合引用指标只统计 Discovery；Category Awareness 仅有后端管线 eligibility，不进入这些指标。Competitor 只统计情感。v8 不要求 `metric_scopes`；Tags 只是聚合维度，不改变核心路由。

品牌边界：Discovery 与 Category Awareness 不出现品牌；Competitor 出现目标品牌和恰好一个当前 Topic 适用竞品；Evaluation 每题只出现一个目标品牌或适用竞品，没有新产物的逐品牌覆盖配额。Evaluation 使用具体业务范围，英文题面不出现元词 `topic`；中文翻译和元数据不受此限制。

## CSV 固定字段导出

字段顺序固定为：

| CSV 列 | 来源 |
|-|-|
| `query` | `user_question` |
| `question_zh` | `zh_translation` |
| `topic` | 对应评测集 `主题 n（宽泛/细分）` 的原始中文值 |
| `diagnosis_intent` | 从 JSON 唯一默认 Intent Tag 转写：`discovery / competitor / verification / accuracy / evaluation / category_awareness` |
| `tags` | 上传适配列：允许留空；若填写必须短于 200 字符，并使用英文逗号、中文逗号或换行分隔，且优先保留可上传的最小化摘要，不把 JSON 里的完整 Attribute 列表直接搬进来 |
| `question_types` | `visibility,sentiment / sentiment / visibility`；Discovery 填 `visibility,sentiment`，Competitor 与 Evaluation 填 `sentiment`，Verification、Accuracy 与 Category Awareness 填 `visibility`（不得带 `sentiment`，否则会被下游情绪判读错误纳入样本） |
| `purchase_intent` | 可空或 `0 / 1 / 2 / 3`，分别表示无、推荐、比较、决策 |
| `persona_name` | 可空，最多 200 字符 |
| `scene_name` | 可空，最多 200 字符 |

CSV 上传模板现在包含 `tags` 列，但它只用于补充上传侧的自由标签；JSON 仍保留完整 `tags` 数组作为唯一权威来源。上传 CSV 不应承载 JSON 里完整的 Attribute 列表或过长的标签串。JSON 仍不生成独立 `diagnosis_intent` 或 `question_type` 字段；这两个 CSV 字段只由上传适配器导出。

## 旧版兼容

validator 允许只读旧 v7/v6/v5 题库，但新生成默认为 v8。旧 `diagnosis_intent` 只能作为 v7/v6 的兼容字段，不得出现在 v8。不得用 v5 的三个固定 Topic、`target_attributes`、`topic_type`、`metric_scopes`、单属性 Verification 或 `paired_discovery_ids` 作为新题库生成规则；不得只改 `schema_version` 伪造迁移。
