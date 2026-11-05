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
| `tags` | 第一个是提示词类型的中文名，后面接切片标签：题库写了 `config.tag_dimensions` 时按维度从矩阵行和题上的买方约束派生（规则见 `geo-prompt-selection-builder` selection-rules.md → 6「切片标签」），没写时接题目自带的 `tags`；总长不到 200 字 |
| `question_types` | 由 `diagnosis_intent` 定：发现 `visibility,sentiment`，对比和评价 `sentiment` |
| `purchase_intent`、`persona_name`、`scene_name` | 留空 |

每个市场单独出一份，一份不超过 60 条。

## 线上怎么跑

线上无人值守时，用一条命令跑完：

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

脚本先归一化 Case，建一个只含所需 skill 的独立工作目录，再让 agent 按下面的步骤调研、写 `out/bank.json`，最后跑第 9 步的检查，结果写进 `out/result.json`。检查没过而 `out/bank.json` 存在时，脚本把报错原文写成 `REPAIR-<n>.md` 回喂 agent 返修再查，默认最多 2 轮（`--repair-rounds`，0 关闭）；最后一轮授权 agent 丢题不丢库（改不好的题删掉、题号记 `config.retired`，每个主题仍要至少一道发现题），所以门禁不放松、一次性跑也能出词。宿主有自己的 harness 时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物清单见脚本开头说明。一次只跑一个市场。

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
| 2. 研究预跑 | 每个产品线 × 市场语言出一份只有 `query` 列的 CSV，只放 1 道品类认知题（`What should I look for when choosing [category]?`），用市场语言写，答案用作第 4 步买方约束查漏。不跑品牌和竞品评价题：它的答案用在相对竞品、品牌事实核查和声誉上，售前都不做；售后选词要用时按「未覆盖来源」补采。用 `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <目录> --regions <市场> --platforms <AI 平台>` 跑，平台只用表单「AI 平台」里客户选的，每个平台各跑 1 次，没选的平台不采。答案只当线索，打开它引用的页面核实后才能用 | 不进题库。答案目录路径和每个平台是否采到，写进 `out/notes.md` 的「预跑答案」 |
| 3. 公开信号 | 收集三类：搜索词（`shared/scripts/collect_serp_signals.py`、`collect_keyword_data.py`，逐条人工判断，无关词直接跳过）、评价（`collect_reviews.py`）、社区（`net.py reddit` 等）。各站点走哪个通道查选词 skill 的 `references/community-channels.md`。没有客户数据这一项 | 买家原话：`config.buyer_quotes`（`[{输入编号, 原话, 约束}]`，约束只写 2–3 个关键词）。品类本身的基础人群或用途：`config.base_conditions`。非基础受众的自述说法：`config.audience_terms`。品类的不同叫法：`config.category_aliases` |
| 4. 买方约束 | 按十二类查漏，B2B 和 B2C 分开，统一粒度（选词 `selection-rules.md` → 3. 买方约束）：一条 ＝ 买家比较选项的一个维度，买家任务写成矩阵行。写题前核实品牌是否满足需求的硬条件。不判重要性、可改变性、相对竞品，也不定优先级 | `config.attribute_plan`：`[{attribute, no_carrier_reason}]`，`attribute` 是买方约束名。品牌相对较弱的照常挂行出题，品牌不满足题面硬条件时才排除 |
| 5. 受众与购买任务 | 受众从 Case 的目标受众起步，按会不会改变候选来拆并。每类受众列出购买任务（在找什么、要定什么，换了任务候选或起作用的约束会变），只列有证据、品牌在竞争的，写依据；只多看一条约束的挂成买方约束，不算任务（选词 `selection-rules.md` → 4）。每个任务按常识推理 AI 会推荐哪一类解决方案（「杀毒软件」「企业终端安全平台」「专门的磁盘分析工具」「找房平台」），写到解决方案类型这一层，不写品牌名单：免费杀毒、轻量杀毒都是「杀毒软件」，企业场景换成终端安全平台才算换了一类。再判断两件事：品牌能不能合理满足这个任务（不要求和候选是同一种产品形态，Sbrand 的磁盘分析功能能满足「找磁盘分析工具」）；AI 的回答里会不会出现品牌这一类（问在售楼盘，回答列的是楼盘，平台品牌基本不会出现）。线上不试跑，这一步只靠推理，写明是推理。推理时注意：套件型品牌的单项功能，AI 常列专门的单功能工具（Sbrand 试跑：磁盘分析列 WizTree、TreeSize，重复文件列 AllDup，游戏加速列 Razer Cortex），不要默认它和套件的主功能是同一类候选 | 购买任务写在矩阵行的 `scene` 字段；受众的自述说法写进 `config.audience_terms`；每个任务的解决方案类型、品牌能否满足、回答里会不会出现品牌这一类，写进 `out/notes.md` 的「购买任务候选」 |
| 6. 矩阵行与业务优先级 | 一行 ＝ 产品线 × 市场 × 受众 × 购买任务 × 旅程阶段，列出这一行买家看重的买方约束。旅程阶段三段：需求认知 / 方案考虑 / 购买决策；核心受众 × 购买任务 × 三段只作查漏清单，只开真实存在、决策不同、有合理需求依据的行，有公开证据写证据、没有的标「假设」，不看 Case 点没点名对比、评价（选词 `selection-rules.md` → 5「用清单查漏，只开成立的行」）。题型按本期范围及需求证据登记，阶段按实际买家处境记录。售前不出问题解决题，对比、评价只在 `extra_prompt_types` 点名且有买家证据时出题；要出的对比、评价题另开行、在行上写 `prompt_type`，这样才能归进第 7 步的类型主题。不出题的行照样判业务优先级、写进 `config.slices`，不带 `topic_id`，`priority_basis` 末尾写「本期不出：……」。售前报告只按题统计，不展示矩阵；售后选词接手时，这些行随完整矩阵写进对客确认表（选词 2.3.1）。业务优先级判高 / 中 / 低：按一类买家需求对品牌的商业价值、战略重要性和当前业务重点的贡献判（选词 `selection-rules.md` → 5「业务优先级」），不打分、不看证据多少。线上没有业务目标字段，业务重点从 Case 的目标受众、差异化优势、补充内容和主题（Case 填了主题时）取，依据里写明出处；这几项都空时，主要受众的核心购买任务记高、其他记中，`priority_basis` 写明「Case 无业务重点，按主要受众的核心购买任务定」。高、中出题，题数按决策差异定；低默认不出；范围外、没依据、品牌做不到又没服务路径的处境不开行 | `config.slices`：`[{slice_id, topic_id, product_line, audience, scene, market, prompt_type, journey_stage, attributes, priority, priority_basis}]`（`prompt_type` 用英文类型名）。没开的行和原因写进 `out/notes.md` 的「没开的格子」 |
| 7. 主题与主题优先级 | 本期出题的行（业务优先级为高和中，写题时能问出本期题型）按选词 `selection-rules.md` → 6「怎么聚」聚成主题：在本期产品线范围内按核心意图和解决方案范围划分：买家想拿到同一类结果、AI 会推荐相近类型的产品服务或渠道的放一起（两条都必要），合并后读数能说清哪类需求要优化作为验证；同一购买任务里要平台和要具体标的的题归不同主题；产品类型、客群、场景要有需求证据才拆，Case 写明要独立监测时可单拆；只是属性、场景、购买条件不同的写成同一主题内不同的题；业务优先级不同不作为拆分依据。推理拿不准时按解决方案类别归类，在主题的 `priority_basis` 里写「解决方案类型为推理，待验证」。品牌不能合理满足的任务按第 6 步不开行；能满足、但回答里基本不会出现品牌这一类的，行照开、本期不出，`priority_basis` 写原因，不把题改写成问品牌那一类。题数不判断边界，也不为题数合并独立需求。一个主题只放一种提示词类型（门禁 66，原因见选词 `selection-rules.md` → 6「发现题和其他类型不放同一主题」）：发现题按上面的条件分主题；对比、评价题一个决策下够 5 题开「决策 + 类型」主题，不够 5 题就把多个决策下的同类型题合成一个类型主题（「品牌对比」「品牌评价」），主题名写出类型，类型主题不设题数下限。主题名用中文写，买家一看就懂是哪一类购买需求，不以单个买方约束或卖点命名、不带品牌，和同产品线其他主题分得开（「海外远程安全租房」），题库和上传 CSV 里都用这个中文名。主题优先级：默认取组内多数行的业务优先级，没有多数时人工判断并写理由；同档按父关键词月搜索量排先后（取哪家的量见选词 `selection-rules.md` → 6. 主题与主题优先级）；优先级差异不作为拆主题的依据。主题个数不受 3 个限制（研发放开前仍最多 3 个，类型主题也占名额）。Case 填了主题（`topic_source` 为 `case`）时，它只当第 6 步的业务重点线索 | `config.topics`：`[{topic_id, topic, priority, priority_basis}]`，并把 `topic_id` 回填到对应的 `config.slices` 行 |
| 8. 写题 | 规则看选词 `selection-rules.md` → 7. 写题。一道题承载一个完整购买决策，关联所属矩阵行和相关属性，类型按回答任务判断。品牌不满足硬条件时排除，相对劣势保留用于诊断。售前默认只出发现题，和选词统一；`case-normalized.json` 的 `extra_prompt_types`（由 Case「希望解决的问题」推出）列了 `Competitor` / `Evaluation` 才允许出对比题 / 评价题，并把这个列表写进 `config.extra_prompt_types`；允许不等于必须，对比题要有买家在比的证据，评价题要有买家在问可信度的信号（选词 `selection-rules.md` → 1 的证据表），没有就不出、在 notes.md 写原因。Case 的「希望解决的问题」排在前面的优先考虑，`补充内容` 里客户给的 AI 答错例子当作依据之一。对比题只比 Case 冻结的竞品；报告的竞品胜率只读对比题，没出就为空。情感从发现题的回答里照常统计。题面条件按选词 `selection-rules.md` → 7「题面怎么写」：默认 1 到 3 个、每个都要有依据（公开信号原话，或写在 `condition_basis` 的依据） | 每题的字段见下表 |
| 9. 校验与导出 | 依次跑三条，都退出码 0 才算完成：① `python3 -I ../geo-prompt-selection-builder/scripts/validate_after_sales_set.py <bank.json>`，错误全部改掉、告警逐条看过；② `python3 -I scripts/check_presales_bank.py <bank.json>`，查售前专属的几条：对比、评价题要 `extra_prompt_types` 点名才出且它只能列这两类、主题都有题、对比题点名冻结竞品、买方约束名单（`attribute_plan`）不为空；③ `python3 -I ../geo-prompt-selection-builder/scripts/export_upload_csv.py <bank.json> --out <目录>`。不跑本 skill 的 `validate_question_bank.py`：它查的是默认模式的 Tag 和配额结构 | — |

`config` 里另写固定值：`lifecycle_status: "hypothesis"`、`evidence_status: "hypothesis"`。`generation_stage` 写 `"selection"`（2026-11-02 前的 `"discovery"` / `"diagnostic"` 照认，不再按它限制题型）。根节点写 `schema_version: "overseas-geo-question-bank/v8"` 和 `mode: "after-sales-strategic-topics"`；后者是选词 validator 要求的固定值，不代表这是售后题库。

按本文字段造的一份 7 题样例（发现、对比、评价各一个主题，5 道发现、1 道对比、1 道评价）存在 `evals/fixtures/selection-mode-sample-bank.json`，三条检查都是退出码 0；`evals/e2e_presales_gates.py` 用它造违规样本，确认每条规则都拦得住（2026-10-29）。

## 每道题的字段

| 字段 | 填什么 |
|---|---|
| `question_id` | 题号 |
| `intent_key` | 同一意图在不同语言版本之间的配对键（多市场时） |
| `topic_id`、`slice_ref` | 所属主题和所属矩阵行，两者要对得上；受众、购买任务、旅程阶段从这一行读，题上不再写 |
| `user_question` | 题面 |
| `zh_translation` | 译文 |
| `prompt_type` | `Discovery`；Case 点名时加 `Competitor` / `Evaluation` |
| `region` | 市场，和 `collection_config.market` 一致 |
| `attribute_ref` | 这道题的主要属性，从所在行的 `attributes` 里选，其他相关属性和条件保留在题面及出题依据中 |
| `constraints` | 题面在属性之外附加的条件（关键词），每个都要有依据（公开信号原话或 `condition_basis`）；没有就写 `[]`；受众不算条件 |
| `priority` | 提示词优先级，照抄所在行的业务优先级 |
| `changeability` | 写 `待试跑`，售前不试跑 |
| `tags` | 选填，只放其他字段推不出来的短名 |

按需才写：`condition_basis`（条件不来自引用的需求信号时写依据）、`evidence_refs`（引用的需求信号编号）。旧样例里的 `monitoring_prompt`、`group_role`、`journey_stage`、`audience`、`analysis_type`、`formal_visibility_eligible`、`quality_checks` 仍能通过校验，新题库不用写。不写状态字段：售前没有审批这一步。

## 不做的事

- 不做客户数据收集、对客确认、试跑排序、锁定正式题。
- 不出品类认知题（它只用在第 2 步预跑）；不出问题解决、验证题；准确性题不进题库。
- 替代题等研发加上独立的 `diagnosis_intent` 之后再出（它要算可见度和情感）。在那之前它只能挂在 `competitor` 下，只算情感。上线后要同步改导出脚本的 `INTENT` / `QUESTION_TYPES`、本 skill validator 的 `V8_CSV_QUESTION_TYPES`，以及 `shared/canonical-intent-mapping.md`。
