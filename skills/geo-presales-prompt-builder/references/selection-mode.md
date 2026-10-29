# 售前生词步骤

售前诊断的流程很短：生词 → 爬一次 → 出 HTML 报告。没有客户确认，也没有试跑。本文件只写售前要做的步骤，以及每一步的判断记在题库 JSON 的哪个字段。题面怎么写、怎么去重、过哪些门禁，只在选词 skill 里定义一份，本文按章节引用，不另抄。

## 最终交给线上的是什么

最终只交 9 个字段，每道题一行：

`query, question_zh, topic, diagnosis_intent, tags, question_types, purchase_intent, persona_name, scene_name`

研发可以走上传 CSV，也可以走接口传入，两种方式字段相同。导出脚本输出的就是这 9 个字段：走 CSV 就直接上传文件，走接口就把每一行当作一条记录传过去。题库 JSON 是我们内部的工作底稿，不传给线上。

| 字段 | 从哪来（导出脚本自动填） |
|---|---|
| `query` | `user_question` |
| `question_zh` | `zh_translation` |
| `topic` | 题目的 `topic`；没有就按 `topic_id` 去 `config.topics` 查。写报告上要显示的主题名，需要换名时导出加 `--topic-label "题库主题=显示名"`。线上目前从表单「监测主题」取报告主题。已提给研发三项改动（2026-10-29）：线上生词改为运行本 skill、表单去掉监测主题、报告主题从题里取。研发改好之前，`topic` 必须和表单上填的监测主题逐字一致 |
| `diagnosis_intent` | 由 `prompt_type` 换成后端枚举：发现 `discovery`、对比 `competitor`、评价 `evaluation` |
| `tags` | 第一个是提示词类型的中文名，后面接题目自带的 `tags`，总长不到 200 字 |
| `question_types` | 由 `diagnosis_intent` 定：发现 `visibility,sentiment`，对比和评价 `sentiment` |
| `purchase_intent`、`persona_name`、`scene_name` | 留空 |

每个市场单独出一份，一份不超过 60 条。

## 线上怎么跑

线上无人值守时，用一条命令跑完：

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

脚本先归一化 Case，建一个只含所需 skill 的独立工作目录，再让 agent 按下面的步骤调研、写 `out/bank.json`，最后跑第 8 步的两个检查，结果写进 `out/result.json`。宿主有自己的 harness 时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物清单见脚本开头说明。一次只跑一个市场。

### 线上没有浏览器

选词 skill 有三处写了「用本地浏览器」：逐层点开 PAA、读要登录或反爬强的站、核对 AI 引用的帖子（`signal-sources.md`）。服务器上没有带登录态的浏览器，这三处按下面换：

| 原来用浏览器做的 | 线上怎么做 |
|---|---|
| 逐层点开 Google PAA 看更多问题 | 不做。`collect_serp_signals.py` 每个种子词取到的那一层 PAA 就够了，PAA 本来每次都会轮换，单次只是样本 |
| 读要登录或反爬强的社区、评价站 | 先查 `community-channels.md` 的通道表：评价站走 `collect_reviews.py`，Reddit 走 `net.py reddit`，Facebook 公开群帖子和 HardwareZone 走 `net.py fetch --proxy`，JS 页走 `net.py render`。表里标「不通」的站（Instagram、Quora、X、G2、Capterra、Dcard 等）跳过 |
| 打开 AI 引用的帖子核对原话 | 用同一套通道打开；打不开的帖子，原话不进 `config.buyer_quotes` |

跳过的站和打不开的帖子写进 `out/notes.md` 的「未覆盖来源」，不另找办法绕过登录。

## 步骤与记录位置

| 步骤 | 做什么 | 记在题库 JSON 哪里 |
|---|---|---|
| 1. 归一化 Case | 运行 `scripts/normalize_case.py`。线上那几个旧字段就够了，缺的业务字段不用找客户补 | `config.brand_name`、`config.official_domain`、`config.competitor_selection`；市场和语言写进 `config.collection_config.market` / `.language` |
| 2. 研究预跑 | 每个产品线 × 市场语言出一份只有 `query` 列的 CSV：1 道品类认知题（`What should I look for when choosing [category]?`），再给目标品牌和每个竞品各出 1 道（`Evaluate the [category] company [brand]`），都用市场语言。用 `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <目录> --regions <市场> --platforms <AI 平台>` 跑，平台只用表单「AI 平台」里客户选的，每个平台各跑 1 次，没选的平台不采。答案只当线索，打开它引用的页面核实后才能用 | 不进题库。答案目录路径写进交接文件 |
| 3. 公开信号 | 收集三类：搜索词（`shared/scripts/collect_serp_signals.py`、`collect_keyword_data.py`，再跑 `tag_search_signals.py` 打类型提示）、评价（`collect_reviews.py`）、社区（`net.py reddit` 等）。各站点走哪个通道查选词 skill 的 `references/community-channels.md`。没有客户数据这一项 | 买家原话：`config.buyer_quotes`（`[{输入编号, 原话, 约束}]`，约束只写 2–3 个关键词）。品类本身的基础人群或用途：`config.base_conditions`。非基础受众的自述说法：`config.audience_terms`。品类的不同叫法：`config.category_aliases` |
| 4. 属性与相对竞品 | 按十二类查漏，B2B 和 B2C 分开（选词 SKILL → *Attribute means…* Step 1–4）。每个属性只判相对竞品：优势 / 持平 / 劣势 / 待确认，并写依据（预跑答案加核实页面）。不判重要性、可改变性，也不定优先级 | `config.attribute_plan`：`[{attribute, relative_competitor, relative_competitor_basis}]`。劣势属性留在表里，但不挂到任何矩阵行上 |
| 5. 矩阵行与优先级 | 枚举产品线 × 受众 × 市场 × 旅程阶段，只开值得测的格子；每行列出在这个处境下真正影响取舍的属性。行优先级按「业务重点 × 买家证据」判 P1 / P2 / P3：线上没有业务目标字段，业务重点从 Case 的差异化优势和补充内容取，依据里写明出处；挂了待确认属性的行最高只能定 P2。`target_count` 按这一行里真正不同的决策需求数填，P3 行留空 | `config.slices`：`[{slice_id, topic_id, product_line, audience, market, journey_stage, attributes, priority, priority_basis, target_count}]`。没开的格子和不开的原因写进交接文件 |
| 6. 聚主题 | 把 P1 / P2 行按决策任务聚成主题：同一个要解决的问题、同一组竞品、同一套评价标准算一个主题。主题名用买家的说法，题库里写 1–4 个英文词。每个主题计划题数合计至少 5 条；P3 行不出题。主题个数不受 3 个限制（研发放开前仍最多 3 个） | `config.topics`：`[{topic_id, topic, source_slices, planned_prompts}]`，并把 `topic_id` 回填到对应的 `config.slices` 行 |
| 7. 写题 | 规则看选词 SKILL 第 7、9、10、11 步，以及 `after-sales-rules.md` → *Reference wording per prompt type*。售前只出发现、对比、评价三类，发现型至少占一半。题面附加的条件必须出现在所引买家原话的约束里 | 每题的字段见下表 |
| 8. 校验与导出 | 先跑 `python3 -I ../geo-prompt-selection-builder/scripts/validate_after_sales_set.py <bank.json>`，错误全部改掉、告警逐条看过；再跑 `python3 -I ../geo-prompt-selection-builder/scripts/export_upload_csv.py <bank.json> --out <目录>`，退出码 0 才算完成。不跑本 skill 的 `validate_question_bank.py`：它查的是默认模式的 Tag 和配额结构 | `config.expected_total` 等于题数 |

`config` 里另写固定值：`lifecycle_status: "hypothesis"`、`evidence_status: "hypothesis"`。`generation_stage` 看题型：只有发现型写 `"discovery"`，含对比或评价写 `"diagnostic"`，否则选词 validator 会报「discovery 阶段只能有发现题」。根节点写 `schema_version: "overseas-geo-question-bank/v8"` 和 `mode: "after-sales-strategic-topics"`；后者是选词 validator 要求的固定值，不代表这是售后题库。

按本文字段造的一份 7 题样例（5 道发现、1 道对比、1 道评价），选词 validator 和导出脚本都是退出码 0（2026-10-29）。

## 每道题的字段

| 字段 | 填什么 |
|---|---|
| `question_id`、`intent_key` | 题号；`intent_key` 是同一意图在不同语言版本之间的配对键 |
| `topic_id`、`slice_ref` | 所属主题和所属矩阵行。两者要对得上：这道题的 `topic_id` 必须等于它那一行的 `topic_id` |
| `user_question`、`monitoring_prompt` | 题面，两个字段写同一句 |
| `zh_translation` | 中文意思 |
| `prompt_type` | `Discovery` / `Competitor` / `Evaluation` |
| `region` | 市场，和 `collection_config.market` 一致 |
| `analysis_type`、`formal_visibility_eligible` | 发现：`visibility,sentiment`、`true`；对比和评价：`sentiment`、`false` |
| `group_role` | 发现填 `core`，对比填 `monitoring`，评价填 `experimental` |
| `journey_stage` | 八段之一：发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持 |
| `audience` | 受众；没有细分人群时填 `通用` |
| `attribute_ref` | 这道题测的那一个属性，从所在行的 `attributes` 里选 |
| `evidence_refs` | 所引买家原话的输入编号 |
| `constraints` | 题面在属性之外附加的条件（关键词），没有就写 `[]`；受众不算条件 |
| `priority` | 照抄所在行的优先级 |
| `changeability` | 写 `待试跑`，售前不试跑 |
| `quality_checks` | 照选词题库的写法 |
| `tags` | 选填，只放其他字段推不出来的短名（属性、角色、场景） |

不写 `review_status`。售前没有审批这一步，一旦写了，validator 会按「只有已批准的题才算覆盖属性」报告警。

## 不做的事

- 不做客户数据收集、对客确认、试跑排序、锁定正式题。
- 不出品类认知题（它只用在第 2 步预跑）；不出问题解决、验证、准确性题。
- 替代题等研发加上独立的 `diagnosis_intent` 之后再出（它要算可见度和情感）。在那之前它只能挂在 `competitor` 下，只算情感。上线后要同步改导出脚本的 `INTENT` / `QUESTION_TYPES`、本 skill validator 的 `V8_CSV_QUESTION_TYPES`，以及 `shared/canonical-intent-mapping.md`。
