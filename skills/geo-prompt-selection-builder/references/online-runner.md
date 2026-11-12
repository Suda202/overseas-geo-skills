# 线上无人值守生成

线上（销售用的售前诊断、或任何没有人在旁边的场景）用一条命令把一份品牌资料（一个品牌 × 一个市场）跑成一批题。规则和本地选词完全一样，都在 [selection-rules.md](selection-rules.md)；本文只写线上和本地不一样的地方：输入换成品牌资料、没有品牌方数据、没有浏览器登录态、只交上传行。生成到导出为止，试跑和采集归 `geo-monitoring`。

2026-11-06 由已退役的 `geo-presales-prompt-builder` 并入。

接口和脚本里的 case 字样（`--case`、`normalize_case.py`、`inputs/case-normalized.json`、`case_fields`、`DATAFORSEO_CASE`、`presales-case-input/v2`）是历史命名，正文一律叫品牌资料。

## 输入与输出

- 输入：一份品牌资料 JSON，可以是线上表单收集的数据，也可以是本地文件，字段见 [input-contract.md](input-contract.md)。先过 `scripts/normalize_case.py`，`ok=false` 时把 `errors` 原样交回上游，不替上游补字段。
- 输出：每个市场一份 `bank.json`（内部底稿）、`notes.md`，和导出的 5 字段上传行：

`query, question_zh, topic, diagnosis_intent, tags`

研发可以走上传 CSV，也可以走接口传入，字段相同：走 CSV 就直接上传文件，走接口就把每一行当作一条记录。题库 JSON 不传给线上。

| 字段 | 从哪来（导出脚本自动填） |
|---|---|
| `query` | `user_question` |
| `question_zh` | `zh_translation` |
| `topic` | 题目的 `topic`；没有就按 `topic_id` 去 `config.topics` 查。需要换显示名时导出加 `--topic-label "题库主题=显示名"` |
| `diagnosis_intent` | 由 `prompt_type` 换成后端枚举（发现 `discovery`） |
| `tags` | 切片标签（selection-rules.md → 6「切片标签」），可以为空；不重复写 `diagnosis_intent` 已经表达的类型；总长不到 200 字 |

每个市场 × 产品线单独出一份，一份不超过 60 条（导出脚本查）。线上一份品牌资料只有一条产品线，所以就是每个市场一份；本地题库一个市场有几条产品线时，文件名带 `.line<n>`，导出时打印每份对应哪条产品线。

## 怎么跑

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

脚本先归一化品牌资料，建一个只含所需文件的独立工作目录（选词、shared 整个拷；`geo-presales-report-builder` 只拷 `scripts/`，外加 `collect_answers.py` 导入要的 `geo_presales_core` 包（geo-metrics）和 `audit_crawl_integrity.py`；不拷 `geo-monitoring`，线上不试跑、不采集），再让 agent 按本文和 selection-rules.md 调研、写 `out/bank.json`，最后跑校验和导出，结果写进 `out/result.json`。检查没过而 `out/bank.json` 存在时，脚本把报错原文写成 `REPAIR-<n>.md` 回喂 agent 返修再查，默认最多 2 轮（`--repair-rounds`，0 关闭）；最后一轮授权 agent 丢题不丢库（改不好的题删掉、题号记 `config.retired`），所以门禁不放松、一次性跑也能出词。宿主有自己的 harness 时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物清单见脚本开头说明。一次只跑一个市场。

部署、环境变量、境内服务器、接平台网关、审核环、每轮记账和验收见 [runner-ops.md](runner-ops.md)（给研发，agent 不用读）。

## 线上没有浏览器

signal-sources.md 和本地调研写了几种用浏览器的情况。服务器上没有带登录态的浏览器，按下面换：

| 原来用浏览器做的 | 线上怎么做 |
|---|---|
| 逐层点开 Google PAA 看更多问题 | 不做。`collect_serp_signals.py` 每个种子词取到的那一层 PAA 就够了，PAA 本来每次都会轮换，单次只是样本 |
| 读要登录或反爬强的社区、评价站 | 先查 community-channels.md 的通道表：评价站走 `collect_reviews.py`，Reddit 走 `net.py reddit`，Facebook 公开群帖子和 HardwareZone 走 `net.py fetch --proxy`，JS 页走 `net.py render`。表里标「不通」的站跳过 |
| 打开 AI 引用的帖子核对原话 | 用同一套通道打开；打不开的帖子，原话不进 `config.buyer_quotes` |

Reddit 的 RSS 返回 403 时（2026-11-11 本机就是），precollect 自动改读网页版：先用 `net.py search "reddit <词>"` 拿帖子链接（Reddit 自己的搜索页经代理被拦），再逐帖 `net.py reddit <帖子 URL> --proxy`，一个渠道最多 2 帖付费，拿到的只有顶层评论。你在补采时同样用这两步，别反复试 RSS。跳过的站和打不开的帖子写进 `out/notes.md` 的「未覆盖来源」，不另找办法绕过登录。

取网页一律 `net.py fetch <url> --country <市场代码>`：代理节点默认是 SG，和本次运行的市场不一致时常取不到（2026-11-09 topuniversities 用 SG 节点失败、US 节点 25 秒取到），一次失败要多花半分钟到一分钟。被拦的页面不要再试 `render`，它在被拦页面上基本超时；`render` 只在 `fetch` 提示「可能是 JS 渲染页」时用，服务器上要装 Chrome 并设 `CHROME_PATH`，没装就跳过、按未覆盖来源记。同一个 URL 成功取过一次有缓存，返修轮重复打开不再付费。要读的页面攒成一批一次传给 `fetch`（默认 5 路并发，按输入顺序输出）；Facebook、X、Instagram、Threads、HardwareZone 和 7 天内直连被拦过的域名脚本会自动跳过直连。Reddit 每个工作目录最多 10 次联网请求（环境变量 `NET_REDDIT_MAX`，runner 默认设好，约 10 分钟），先挑最相关的版块和帖子，到上限后读不到的写进「未覆盖来源」。Reddit 评论要给单帖 URL 才取得到，只给搜索词只返回主帖。

**runner 先判行业、再固定采一轮**：agent 启动前，runner 先跑一次短 agent（`PLAN.md`，约几分钟）：取品牌和竞品官网首页存到 `research/site/homepages.txt`（第 2 步官网调研从这份接着看），按 [precollect-channels.json](precollect-channels.json) 判出品牌属于哪个行业，填英文品类词、应用 ID、门店名这些参数，写 `research/precollect/plan.json`。runner 检查不过回喂一次，仍不过就退回默认渠道（竞品 Trustpilot + 市场社区）。要采哪些渠道由表定：行业那一行的评价站和社区，加上目标市场那一行的社区；agent 只能跳过缺应用或门店的渠道（Google Play、App Store、Google 地图），最多再补 3 个，不能删表里的渠道。然后脚本按计划采：搜索联想（`collect_serp_signals.py`）、评价（`collect_reviews.py` 的 Trustpilot / Google Shopping / 应用商店 / Google 地图，或 Capterra、Alibaba 这类评价站先用「站名 + 竞品名或品类词」搜出本站页面再取正文（Scrapeless 的 Google 搜索不认 `site:`，2026-11-11 实测））、社区（Reddit 搜索加最相关 3 帖评论，RSS 读不到时改读网页版、每类最多 2 帖付费；Hacker News 评论；Pantip 这类本地论坛的站内页；Pantip 只取帖子页，用 `net.py pantip` 取标题、主帖和评论）。原话合并在 `research/precollect/signals.csv`，页面正文在 `research/precollect/pages/`，计划和每个渠道成败在 `plan-checked.json`、`summary.json`。三类并行、同类渠道也并行，评价最多等 10 分钟、其余 6 分钟；DataForSEO 评价任务排队慢，超时的任务已提交，重跑 `research/precollect/reviews/<渠道>/rerun.txt` 里的命令能直接取结果、不重复付费。agent 先读这些，只对缺口补采，不重复采同样的来源；与本产品线相关的信号要登记进 `config.buyer_quotes`（页面里的买家原话由 agent 摘出来登记，出处写页面网址）。某一类采到了却一条没登记、`notes.md`「未覆盖来源」里也没说明这一类为什么全部无关，结束检查不通过、回喂返修。

B2B 软件评价站：G2 被 DataDome 拦，代理和无头 Chrome 都不通，不要试；Capterra、TrustRadius 用 `net.py fetch` 能取到完整评价，但要先用站内搜索确认产品有档案（2026-11-10 实测一家 GPU 云竞品两站都没有）。开发者和 AI 基础设施类品类，Hacker News 的 Algolia 接口直连可取评论全文（见 community-channels.md）。

## 和本地选词不一样的几步

| 步 | 线上怎么做 |
|---|---|
| 1. 业务范围 | 没有品牌方填的业务范围表，用归一化后的品牌资料代替：市场和语言写进 `config.collection_config.market` / `.language`，品牌（`brand_name`）、品牌别名（`brand_aliases`）、官网、竞品照抄 `normalize_case.py` 的结果。缺的业务字段不找客户补。`config.business_goals` 可以不写（validator 按 `{selected: ["发现型可见度"], information_named: false}` 填充）。品类名 `config.category_label` 从「产品线」和官网推出，写进 `notes.md`「假设」。`config.shopping_cards` 照选词推理，但售前没有试跑，工业、工程类直接写关 |
| 2. 调研 | 研究预跑每个产品线 × 市场语言只放 1 道品类认知题（`What should I look for when choosing [category]?`，用市场语言写），用 `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <目录> --regions <市场> --platforms <AI 平台>` 跑，平台只用表单「AI 平台」里客户选的，每个平台 1 次。品牌和竞品评估预跑题默认不跑，和本地一致（selection-rules.md → 2）。答案目录和每个平台是否采到写进 `notes.md`「预跑答案」。公开信号照 signal-sources.md 收不需要客户数据的三节；没有品牌方提供的资料，`demand-side-signals.md`（客户提供什么）不读，工作目录里也没有这个文件 |
| 3. 约束条件 | 照 selection-rules.md 第 3 步写 `config.attribute_plan`：每条判品牌情况（官网和公开资料判不出的填待确认，不出题）和公开硬事实上的相对竞品，三种取值都写 `brand_status_basis`。矩阵行或题挂了约束条件就必须有这张表（门禁 67），线上同样「宁可少出几道题」 |
| 4. 目标客户与使用场景 | 从品牌资料里的「核心目标客户与购买场景」拆出目标客户，不改写业务范围那几行；按会不会改变候选来拆并。每个使用场景按常识推理 AI 会推荐哪一类解决方案（「杀毒软件」「企业终端安全平台」「专门的磁盘分析工具」「找房平台」），写到解决方案类型这一层，不写品牌名单；再判断品牌能不能合理满足这个任务（不要求同一种产品形态），以及 AI 的回答里会不会出现品牌这一类（问在售楼盘，回答列的是楼盘，平台品牌基本不会出现）。线上没有试跑读数，这一步只靠推理，写明是推理。套件型品牌的单项功能，AI 常列专门的单功能工具（Sbrand 试跑：磁盘分析列 WizTree、TreeSize，重复文件列 AllDup，游戏加速列 Razer Cortex），不要默认它和套件的主功能是同一类候选。结果写进 `notes.md`「使用场景候选」 |
| 5. 业务优先级 | 品牌资料「核心目标客户与购买场景」里写了的条目就是品牌方点名，对应的行判高，我们补充的判中（同 selection-rules.md 第 5 步；填写顺序只用于主题同档排序）；差异化优势写进依据，写明出处；这几项都空时按官网主推判（同 selection-rules.md 第 5 步）：主推产品的主要目标客户的核心使用场景记高、其他记中，`priority_basis` 写明「推断：品牌资料无业务重点，按官网主推定」。没开的行和原因写进 `notes.md`「没开的格子」 |
| 6. 主题 | 和选词一样聚，个数不限。拿不准候选类别时按推理的候选类别归类，在主题的 `priority_basis` 里写「候选类别为推理，待验证」。能满足、但回答里基本不会出现品牌这一类的行照开、本期不出 |
| 7. 写题 | 和选词一样，本期只出发现题。题量按 selection-rules.md 第 7 步：超过 60 道 validator 和导出都报错；不到 30 道不凑题，检查通过后 runner 会写 `TOPUP.md` 让你补一轮（先开业务优先级为中的我方补充行和假设行，再用业务优先级为低的行，不许同义改写），补不到照常交付，`out/notes.md`「假设」里写一句为什么题少。补题在审核之前，审核删掉阻塞题后可能又不到 30 道，不再补；`--repair-rounds 0` 时不补题 |
| 8. 校验与导出 | 依次跑 `scripts/validate_after_sales_set.py <bank.json>`、`scripts/export_upload_csv.py <bank.json> --out <目录>`，都退出码 0 才算完成。不写对客确认表 |

`config` 另写固定值：`generation_stage: "selection"`；`evidence_status` 按 output-contract.md 的定义写：`config.buyer_quotes` 里有评价、社区或搜索数据的买家信号写 `after_sales_signal`，一条都没有写 `hypothesis`；根节点写 `schema_version: "overseas-geo-question-bank/v8"` 和 `mode: "after-sales-strategic-topics"`（`mode` 是 validator 要求的固定值，`schema_version` 照写备查）。题的字段按 output-contract.md。

`notes.md` 分这几节：「预跑答案」「目标客户」「使用场景候选」「约束条件」「需求信号」「没开的格子」「主题」「假设」「未覆盖来源」「validator 告警」，返修丢过题的再加「删题」。

## 需求信号必须填

线上没有品牌方提供的数据，但公开层收得到买家原话（评价、社区）、搜索词和 AI 检索词，这些要登记进 `config.buyer_quotes`，否则 W36（题面条件没有依据）、W37（同一决策问两遍）两道门禁会整段跳过，validator 只给一条 W36 告警，其实两道都没查。

- 登记哪些照 selection-rules.md 第 2 步「脚本产物按目录收齐再登记」：与本产品线、本期市场相关、会改变选词判断的都登记，不只登记撑起题的几条；带条件的题至少挂一条。一条一个对象：`{输入编号, 来源类型, 原话, 目标客户, 约束条件, 出处}`。来源类型 precollect 来的照抄 `signals.csv` 里的值（runner 按它查每类有没有登记），出处写完整网址；原话写原文不翻译，目标客户看不出留空。
- 约束那一列的键名就是 `约束条件`，和对客 Base 的列名、采集脚本的 `signals.csv` 一致。英文别名 `constraint` 也认；2.65.0 之前的旧键名 `约束` 仍兼容，但新写的题库一律用 `约束条件`。
- 题的 `evidence_refs` 填信号编号（`["US-R003"]`），不填别的题的题号。题面带条件却挂不上原话的，用 `condition_basis` 写清依据，不许留空。
- 输入编号带市场前缀（`US-R001`），线上一次运行只跑一个市场，不跑就别编号。

## 交给本地选词接着做

本地选词接手线上题库时：需求信号、约束条件、矩阵行、主题照收；用品牌方填的业务范围重判业务优先级，用品牌方数据复核约束条件；`notes.md`「预跑答案」里的答案直接用，不重跑；「未覆盖来源」补采。
