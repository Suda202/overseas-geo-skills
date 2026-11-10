# 线上无人值守生成

线上（销售用的售前诊断、或任何没有人在旁边的场景）用一条命令把一份品牌资料（一个品牌 × 一个市场）跑成一批题。规则和本地选词完全一样，都在 [selection-rules.md](selection-rules.md)；本文只写线上和本地不一样的地方：输入换成品牌资料、没有品牌方数据、没有浏览器登录态、只交上传行。生成到导出为止，试跑、挑题、锁版都不在这里（归 `geo-monitoring`）。

2026-11-06 由已退役的 `geo-presales-prompt-builder` 并入。

接口和脚本里的 case 字样（`--case`、`normalize_case.py`、`inputs/case-normalized.json`、`case_fields`、`DATAFORSEO_CASE`、`presales-case-input/v2`）是历史命名，正文一律叫品牌资料。

## 输入与输出

- 输入：一份品牌资料 JSON，可以是线上表单收集的数据，也可以是本地文件，字段见 [input-contract.md](input-contract.md)。先过 `scripts/normalize_case.py`，`ok=false` 时把 `errors` 原样交回上游，不替上游补字段。
- 输出：每个市场一份 `bank.json`（内部底稿）、`notes.md`，和导出的 9 字段上传行：

`query, question_zh, topic, diagnosis_intent, tags, question_types, purchase_intent, persona_name, scene_name`

研发可以走上传 CSV，也可以走接口传入，字段相同：走 CSV 就直接上传文件，走接口就把每一行当作一条记录。题库 JSON 不传给线上。

| 字段 | 从哪来（导出脚本自动填） |
|---|---|
| `query` | `user_question` |
| `question_zh` | `zh_translation` |
| `topic` | 题目的 `topic`；没有就按 `topic_id` 去 `config.topics` 查。需要换显示名时导出加 `--topic-label "题库主题=显示名"` |
| `diagnosis_intent` | 由 `prompt_type` 换成后端枚举（发现 `discovery`） |
| `tags` | 切片标签（selection-rules.md → 6「切片标签」），可以为空；只有替代题在第一个写「替代」（后端没有 alternatives 枚举，临时按 competitor 上传），其他类型不重复写 `diagnosis_intent` 已经表达的类型；总长不到 200 字 |
| `question_types` | 由 `diagnosis_intent` 定：发现 `visibility,sentiment`。过渡字段，后端改为按意图类型决定统计什么之后删掉（shared/canonical-intent-mapping.md） |
| `purchase_intent`、`persona_name`、`scene_name` | 留空 |

每个市场 × 产品线单独出一份，一份不超过 60 条（导出脚本查）。线上一份品牌资料只有一条产品线，所以就是每个市场一份；本地题库一个市场有几条产品线时，文件名带 `.line<n>`，导出时打印每份对应哪条产品线。

## 怎么跑

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

脚本先归一化品牌资料，建一个只含所需文件的独立工作目录（选词、shared 整个拷；`geo-presales-report-builder` 只拷 `scripts/`，外加 `collect_answers.py` 导入要的 `geo_presales_core` 包和 `audit_crawl_integrity.py`；不拷 `geo-monitoring`，文档里指向它的链接是锁版阶段规则，线上不读），再让 agent 按本文和 selection-rules.md 调研、写 `out/bank.json`，最后跑校验和导出，结果写进 `out/result.json`。检查没过而 `out/bank.json` 存在时，脚本把报错原文写成 `REPAIR-<n>.md` 回喂 agent 返修再查，默认最多 2 轮（`--repair-rounds`，0 关闭）；最后一轮授权 agent 丢题不丢库（改不好的题删掉、题号记 `config.retired`），所以门禁不放松、一次性跑也能出词。宿主有自己的 harness 时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物清单见脚本开头说明。一次只跑一个市场。

### 审核环

校验和导出第一次都通过后，脚本再新开一个审核 agent（不带生成时的上下文），按 [review-rubric.md](review-rubric.md) 八条核对 `out/bank.json` 和 `out/notes.md`，发现写进 `out/review.json`，只写这一个文件。

- 审核模型：`--agent sdk` 时读环境变量 `AGENT_REVIEW_MODEL`，没设用 `AGENT_MODEL`；`--agent-cmd` 时照常执行宿主命令（`TASK_FILE` 指向 `REVIEW.md`），模型由宿主定。
- 阻塞发现（`blocking: true`）按返修的报错格式写成 `REVIEW-REPAIR-<n>.md`（stage 记 `review`）回喂 agent 返修，再跑校验和导出，然后 `REVIEW-<n>.md` 只复核上一轮报过的题号；复核仍有阻塞就继续返修，`--review-rounds` 轮（默认 1＝审一轮＋复核一轮，0 关闭审核）。最后一轮审核返修同样授权丢题不丢库；轮次用完仍有阻塞时，脚本自己把这些题删掉（删前题库存 `out/bank.before-drop.json`，题号和审核原文记进 `config.retired` 与 notes「删题（脚本兜底）」，删空的主题连登记一起删、挂在上面的矩阵行注明本期不出），再跑一遍校验和导出，通过就交付。删完仍没过，或阻塞发现没写题号删不了，才判生词失败。审核返修把校验改坏了，下一轮把校验报错和没修的阻塞发现一起回喂。审核轮次不占 `--repair-rounds` 的额度。
- 非阻塞发现不触发返修，记进 `out/result.json` 的 `review.nonblocking`；本来就要审核返修时，顺带让返修 agent 写进 `notes.md`「评审意见」一节。
- 审核是增强，validator 才是闸门：`review.json` 缺失、不是合法 JSON、结构不对，或审核 agent 超时、出错时，只在 `review.warnings` 记一条，照常交付已过校验的题库。审核 agent 改了 `bank.json` 时脚本恢复审核前的题库并记 warning。
- `out/result.json` 的 `review` 块：`rounds`（审核加复核跑了几轮）、`blocking_found` / `nonblocking_found`（各轮累计）、`status`（`passed` 无阻塞发现；`repaired` 返修后复核通过；`dropped` 轮次用完后脚本删题交付，删了哪些看 `dropped`；`skipped` 关闭审核；`review_failed` 审核没产出可用结果或阻塞没修完，看 `reason` 和总的 `status` 区分）、`review_repair_rounds`、`warnings`、`nonblocking`、`blocking_unresolved`。每轮原件存 `logs/review-<n>.json`；审核和审核返修的 agent 记录（`logs/agent-run-review*.json`）进 `costs.llm` 加总。

### 每轮记账

每轮自动记账，统计口径是每个客户平均花多少钱。脚本每次 finalize 都往 `out/result.json` 写一个 `costs` 块，只记数量和用量，不乘单价：

| 键 | 内容 | 从哪数 |
|-|-|-|
| `brand`、`market` | 客户和市场 | `inputs/case-normalized.json` |
| `llm` | 主跑和各返修轮的 token 用量加总（`input_tokens`、`output_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`）、轮次、turns、耗时；`total_cost_usd_anthropic_price_unreliable` 是 SDK 按 Anthropic 价算的，网关后面是别家模型时不可信，只留存不用 | `logs/agent-run*.json`（`--agent sdk` 才有 usage；`--agent-cmd` 记 `runs_with_usage: 0`） |
| `scrapeless_requests` | 研究预跑尝试次数（失败重试也算）和成功次数、SERP 请求数、网页代理页数、`net.py search` 次数 | `research/**/_collector/events.jsonl` 的 attempt 行、`research/**/serp*/raw/*.json`、`logs/net_cache/`（runner 设 `NET_CACHE_DIR`，每轮一份缓存） |
| `dataforseo` | 本轮时间窗内这个 case 的调用次数和花费 | `~/.dataforseo/ledger.jsonl`，按 `DATAFORSEO_CASE`（默认「品牌 市场」）过滤，不含沙盒 |

按客户汇总、算平均：`python3 -I .agents/skills/shared/scripts/cost_report.py <工作目录或评测数据目录> … [--since 2026-11-01]`。单价只读本机 `~/.geo-cost/prices.json`（`--write-example` 生成示例），不写进任何仓库文件。

## 线上没有浏览器

signal-sources.md 有三处写了「用本地浏览器」。服务器上没有带登录态的浏览器，这三处按下面换：

| 原来用浏览器做的 | 线上怎么做 |
|---|---|
| 逐层点开 Google PAA 看更多问题 | 不做。`collect_serp_signals.py` 每个种子词取到的那一层 PAA 就够了，PAA 本来每次都会轮换，单次只是样本 |
| 读要登录或反爬强的社区、评价站 | 先查 community-channels.md 的通道表：评价站走 `collect_reviews.py`，Reddit 走 `net.py reddit`，Facebook 公开群帖子和 HardwareZone 走 `net.py fetch --proxy`，JS 页走 `net.py render`。表里标「不通」的站跳过 |
| 打开 AI 引用的帖子核对原话 | 用同一套通道打开；打不开的帖子，原话不进 `config.buyer_quotes` |

跳过的站和打不开的帖子写进 `out/notes.md` 的「未覆盖来源」，不另找办法绕过登录。

取网页一律 `net.py fetch <url> --country <市场代码>`：代理节点默认是 SG，和本次运行的市场不一致时常取不到（2026-11-09 topuniversities 用 SG 节点失败、US 节点 25 秒取到），一次失败要多花半分钟到一分钟。被拦的页面不要再试 `render`，它在被拦页面上基本超时；`render` 只在 `fetch` 提示「可能是 JS 渲染页」时用，服务器上要装 Chrome 并设 `CHROME_PATH`，没装就跳过、按未覆盖来源记。同一个 URL 成功取过一次有缓存，返修轮重复打开不再付费。要读的页面攒成一批一次传给 `fetch`（默认 5 路并发，按输入顺序输出）；Facebook、X、Instagram、Threads、HardwareZone 和 7 天内直连被拦过的域名脚本会自动跳过直连。Reddit 每个工作目录最多 10 次联网请求（环境变量 `NET_REDDIT_MAX`，runner 默认设好，约 10 分钟），先挑最相关的版块和帖子，到上限后读不到的写进「未覆盖来源」。

## 和本地选词不一样的几步

| 步 | 线上怎么做 |
|---|---|
| 1. 业务范围 | 没有品牌方填的业务范围表，用归一化后的品牌资料代替：市场和语言写进 `config.collection_config.market` / `.language`，品牌、官网、竞品照抄 `normalize_case.py` 的结果。缺的业务字段不找客户补。`config.business_goals` 可以不写（validator 按 `{selected: ["发现型可见度"], information_named: false}` 填充）。品类名 `config.category_label` 从「产品线」和官网推出，写进 `notes.md`「假设」。`config.shopping_cards` 照选词推理，但售前没有试跑，工业、工程类直接写关 |
| 2. 调研 | 研究预跑每个产品线 × 市场语言只放 1 道品类认知题（`What should I look for when choosing [category]?`，用市场语言写），用 `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <目录> --regions <市场> --platforms <AI 平台>` 跑，平台只用表单「AI 平台」里客户选的，每个平台 1 次。品牌和竞品评估预跑题默认不跑，和本地一致（selection-rules.md → 2）。答案目录和每个平台是否采到写进 `notes.md`「预跑答案」。公开信号照 signal-sources.md 收不需要客户数据的三节；没有品牌方提供的资料，`demand-side-signals.md`（客户提供什么）不读，工作目录里也没有这个文件 |
| 4. 目标客户与使用场景 | 目标客户从品牌资料里的「核心目标客户与购买场景」起步（排在前面的业务优先级高），按会不会改变候选来拆并。每个使用场景按常识推理 AI 会推荐哪一类解决方案（「杀毒软件」「企业终端安全平台」「专门的磁盘分析工具」「找房平台」），写到解决方案类型这一层，不写品牌名单；再判断品牌能不能合理满足这个任务（不要求同一种产品形态），以及 AI 的回答里会不会出现品牌这一类（问在售楼盘，回答列的是楼盘，平台品牌基本不会出现）。线上没有试跑读数，这一步只靠推理，写明是推理。套件型品牌的单项功能，AI 常列专门的单功能工具（Sbrand 试跑：磁盘分析列 WizTree、TreeSize，重复文件列 AllDup，游戏加速列 Razer Cortex），不要默认它和套件的主功能是同一类候选。结果写进 `notes.md`「使用场景候选」 |
| 5. 业务优先级 | 业务重点从品牌资料里的核心目标客户与购买场景（按填写顺序）和差异化优势取，依据里写明出处；这几项都空时，主要目标客户的核心使用场景记高、其他记中，`priority_basis` 写明「品牌资料无业务重点，按主要目标客户的核心使用场景定」。没开的行和原因写进 `notes.md`「没开的格子」 |
| 6. 主题 | 和选词一样聚，个数不限。拿不准候选类别时按推理的候选类别归类，在主题的 `priority_basis` 里写「候选类别为推理，待验证」。能满足、但回答里基本不会出现品牌这一类的行照开、本期不出 |
| 7. 写题 | 和选词一样，本期只出发现题。候选题一个市场 30–60 道，每个导出文件最多 60 条（导出对超 60 报错） |
| 8. 校验与导出 | 依次跑 `scripts/validate_after_sales_set.py <bank.json>`、`scripts/export_upload_csv.py <bank.json> --out <目录>`，都退出码 0 才算完成。不写对客确认表 |

`config` 另写固定值：`generation_stage: "selection"`、`lifecycle_status: "hypothesis"`、`evidence_status: "hypothesis"`；根节点写 `schema_version: "overseas-geo-question-bank/v8"` 和 `mode: "after-sales-strategic-topics"`（validator 要求的固定值）。题的字段按 output-contract.md。

`notes.md` 分这几节：「预跑答案」「目标客户」「使用场景候选」「约束条件」「需求信号」「没开的格子」「主题」「假设」「未覆盖来源」「validator 告警」，返修丢过题的再加「删题」。

## 需求信号必须填

线上没有品牌方提供的数据，但公开层收得到买家原话（评价、社区）、搜索词和 AI 检索词，这些要登记进 `config.buyer_quotes`，否则 W36（题面条件没有依据）、W37（同一决策问两遍）两道门禁会整段跳过，validator 报「0 错误 0 告警」其实是没查。

- 只登记**撑起某道题**的那几条，一条一个对象：`{输入编号, 原话, 目标客户, 约束条件}`。原话写原文不翻译，目标客户看不出留空。
- 约束那一列的键名就是 `约束条件`，和对客 Base 的列名、采集脚本的 `signals.csv` 一致。英文别名 `constraint` 也认；2.65.0 之前的旧键名 `约束` 仍兼容，但新写的题库一律用 `约束条件`。
- 题的 `evidence_refs` 填信号编号（`["US-R003"]`），不填别的题的题号。题面带条件却挂不上原话的，用 `condition_basis` 写清依据，不许留空。
- 输入编号带市场前缀（`US-R001`），线上一次运行只跑一个市场，不跑就别编号。

## 交给本地选词接着做

本地选词接手线上题库时：需求信号、约束条件、矩阵行、主题照收；用品牌方填的业务范围重判业务优先级，用品牌方数据复核约束条件；`notes.md`「预跑答案」里的答案直接用，不重跑；「未覆盖来源」补采。

## 验收

- `python3 evals/e2e_input_contract.py`：品牌资料输入合同（示例 payload、飞书路径与接口路径一致、错误输入的错误码），结果写 `reports/input-contract-e2e.md`。
- `python3 evals/e2e_repair_loop.py`：返修循环四条路径（修好、丢题保底、关闭返修、无 bank），结果写 `reports/repair-loop-e2e.md`。
- `python3 evals/e2e_review_loop.py`：审核环七条路径（无发现、阻塞返修后复核通过、review.json 坏掉、结构不对、关闭审核、额度用完、审核超时），结果写 `reports/review-loop-e2e.md`。
