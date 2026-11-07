# 线上无人值守生成

线上（销售用的售前诊断、或任何没有人在旁边的场景）用一条命令把一个 Case 跑成一批题。规则和本地选词完全一样，都在 [selection-rules.md](selection-rules.md)；本文只写线上和本地不一样的地方：输入换成 Case、没有品牌方数据、没有浏览器登录态、只交上传行。生成到导出为止，试跑、挑题、锁版都不在这里（归 `geo-monitoring`）。

2026-11-06 由已退役的 `geo-presales-prompt-builder` 并入。

## 输入与输出

- 输入：一个 Case JSON，可以是线上表单收集的数据，也可以是本地文件，字段见 [input-contract.md](input-contract.md)。先过 `scripts/normalize_case.py`，`ok=false` 时把 `errors` 原样交回上游，不替上游补字段。
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

每个市场单独出一份，一份不超过 60 条（导出脚本查）。

## 怎么跑

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

脚本先归一化 Case，建一个只含所需 skill 的独立工作目录，再让 agent 按本文和 selection-rules.md 调研、写 `out/bank.json`，最后跑校验和导出，结果写进 `out/result.json`。检查没过而 `out/bank.json` 存在时，脚本把报错原文写成 `REPAIR-<n>.md` 回喂 agent 返修再查，默认最多 2 轮（`--repair-rounds`，0 关闭）；最后一轮授权 agent 丢题不丢库（改不好的题删掉、题号记 `config.retired`），所以门禁不放松、一次性跑也能出词。宿主有自己的 harness 时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物清单见脚本开头说明。一次只跑一个市场。

## 线上没有浏览器

signal-sources.md 有三处写了「用本地浏览器」。服务器上没有带登录态的浏览器，这三处按下面换：

| 原来用浏览器做的 | 线上怎么做 |
|---|---|
| 逐层点开 Google PAA 看更多问题 | 不做。`collect_serp_signals.py` 每个种子词取到的那一层 PAA 就够了，PAA 本来每次都会轮换，单次只是样本 |
| 读要登录或反爬强的社区、评价站 | 先查 community-channels.md 的通道表：评价站走 `collect_reviews.py`，Reddit 走 `net.py reddit`，Facebook 公开群帖子和 HardwareZone 走 `net.py fetch --proxy`，JS 页走 `net.py render`。表里标「不通」的站跳过 |
| 打开 AI 引用的帖子核对原话 | 用同一套通道打开；打不开的帖子，原话不进 `config.buyer_quotes` |

跳过的站和打不开的帖子写进 `out/notes.md` 的「未覆盖来源」，不另找办法绕过登录。

## 和本地选词不一样的几步

| 步 | 线上怎么做 |
|---|---|
| 1. 业务范围 | 没有品牌方填的业务范围表，用归一化后的 Case 代替：市场和语言写进 `config.collection_config.market` / `.language`，品牌、官网、竞品照抄 `normalize_case.py` 的结果。缺的业务字段不找客户补。`config.business_goals` 照选词写 `{selected: ["发现型可见度"], information_named: false}`；Case 的「希望解决的问题」只当第 5 步的业务重点线索。`config.shopping_cards` 照选词推理，但售前没有试跑，工业、工程类直接写关 |
| 2. 调研 | 研究预跑每个产品线 × 市场语言只放 1 道品类认知题（`What should I look for when choosing [category]?`，用市场语言写），用 `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <目录> --regions <市场> --platforms <AI 平台>` 跑，平台只用表单「AI 平台」里客户选的，每个平台 1 次。品牌和竞品评估预跑题不跑，本地选词接手时要用再补。答案目录和每个平台是否采到写进 `notes.md`「预跑答案」。公开信号照 signal-sources.md 收不需要客户数据的三节，没有「客户提供什么」这一节 |
| 4. 目标客户与使用场景 | 目标客户从 Case 的目标客户起步，按会不会改变候选来拆并。每个使用场景按常识推理 AI 会推荐哪一类解决方案（「杀毒软件」「企业终端安全平台」「专门的磁盘分析工具」「找房平台」），写到解决方案类型这一层，不写品牌名单；再判断品牌能不能合理满足这个任务（不要求同一种产品形态），以及 AI 的回答里会不会出现品牌这一类（问在售楼盘，回答列的是楼盘，平台品牌基本不会出现）。线上没有试跑读数，这一步只靠推理，写明是推理。套件型品牌的单项功能，AI 常列专门的单功能工具（Sbrand 试跑：磁盘分析列 WizTree、TreeSize，重复文件列 AllDup，游戏加速列 Razer Cortex），不要默认它和套件的主功能是同一类候选。结果写进 `notes.md`「使用场景候选」 |
| 5. 业务优先级 | 线上没有业务目标字段，业务重点从 Case 的目标客户、差异化优势、希望解决的问题、补充内容和主题（Case 填了主题时）取，依据里写明出处；这几项都空时，主要目标客户的核心使用场景记高、其他记中，`priority_basis` 写明「Case 无业务重点，按主要目标客户的核心使用场景定」。没开的行和原因写进 `notes.md`「没开的格子」 |
| 6. 主题 | 和选词一样聚，个数不限。拿不准候选类别时按推理的候选类别归类，在主题的 `priority_basis` 里写「候选类别为推理，待验证」。能满足、但回答里基本不会出现品牌这一类的行照开、本期不出 |
| 7. 写题 | 和选词一样，本期只出发现题；`补充内容` 里客户给的 AI 答错例子当作依据之一。`changeability` 写 `待试跑` |
| 8. 校验与导出 | 依次跑 `scripts/validate_after_sales_set.py <bank.json>`、`scripts/export_upload_csv.py <bank.json> --out <目录>`，都退出码 0 才算完成。不写对客确认表 |

`config` 另写固定值：`generation_stage: "selection"`、`lifecycle_status: "hypothesis"`、`evidence_status: "hypothesis"`；根节点写 `schema_version: "overseas-geo-question-bank/v8"` 和 `mode: "after-sales-strategic-topics"`（validator 要求的固定值）。题的字段按 output-contract.md。

`notes.md` 分这几节：「预跑答案」「目标客户」「使用场景候选」「约束条件」「没开的格子」「主题」「假设」「未覆盖来源」「validator 告警」，返修丢过题的再加「删题」。

## 交给本地选词接着做

本地选词接手线上题库时：需求信号、约束条件、矩阵行、主题照收；用品牌方填的业务范围重判业务优先级，用品牌方数据复核约束条件；`notes.md`「预跑答案」里的答案直接用，不重跑，品牌和竞品评估预跑题要用时补跑；「未覆盖来源」补采。

## 验收

- `python3 evals/e2e_input_contract.py`：Case 输入合同（示例 payload、飞书路径与接口路径一致、错误输入的错误码），结果写 `reports/input-contract-e2e.md`。
- `python3 evals/e2e_repair_loop.py`：返修循环四条路径（修好、丢题保底、关闭返修、无 bank），结果写 `reports/repair-loop-e2e.md`。
