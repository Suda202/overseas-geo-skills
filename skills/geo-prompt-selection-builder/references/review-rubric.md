# 题库评审清单（review rubric）

给审核代理用：validator 通过后，新开会话读 `out/bank.json` 和 `out/notes.md`，按下面八条逐题核对。每条都有判据，只核对、不评论；不建议加题、不重判优先级、不改主题划分（那些是生成侧规则，见 selection-rules.md）。审核模型由宿主配置（`AGENT_REVIEW_MODEL`，默认同 `AGENT_MODEL`），清单写到换任何模型都能执行的程度。

## 输出格式

把发现写成一个 JSON 数组，存到工作目录的 `out/review.json`，没有问题写 `[]`。每条的键：`question_id`（题号；一条发现涉及几道题时写题号数组）、`check`（下表序号）、`problem`、`suggestion`、`blocking`（true / false，照下表）。除这个文件外不写任何文件，不改题库和 `notes.md`。

```json
[{"question_id": "US-001", "check": 2, "problem": "题面写 S$500k，引用的 US-R003 原话和 condition_basis 里都没有这个数", "suggestion": "换成原话里的 S$600k，或把取值依据补进 condition_basis", "blocking": true}]
```

## 八条核对

| # | 核对什么 | 判据 | blocking |
|-|-|-|-|
| 1 | 发现题在要候选 | 题面在向 AI 要一类候选（which / best / top / recommend / options 或市场语言的等价问法；本地服务和平台类的「找哪家 / 去哪找」也算）。how-to 问法不是发现题 | 是 |
| 2 | 条件和证据对得上 | 题面里的具体取值（预算、数字、房型、地区、型号）逐个出现在它挂的 `evidence_refs` 原话或 `condition_basis` 里；validator 只查结构（W36），这里查内容是否真的对应 | 是 |
| 3 | 同主题同一类候选 | 同一主题下通读全部题面：AI 回答这些题，推荐的是不是同一类东西（某类产品 / 平台 / 服务商）。混了类的指出哪几道 | 是 |
| 4 | 不诱导 | 没把品牌卖点写成前提、没把条件限定到只有本品符合、没写品牌规格数字（问长续航，不问 45 小时） | 是 |
| 5 | 像真人提问 | 按目标市场买家的说法读：有没有翻译腔、关键词堆砌、生硬的条件罗列。只报明显的，措辞风格拿不准的不报 | 否 |
| 6 | 语义层的市场一致 | 货币单位、地名、法规叫法和题库市场一致（语种本身 validator 已查）；地域影响供货、法规、服务范围的题面写了必要地点 | 是 |
| 7 | 一题一个决策 | 一个问号；没有用 and 连两个问题；没有互相包含的条件 | 是 |
| 8 | 看得出谁在问 | 目标客户不是品类基础人群的题，题面明写或用这类人的说法隐含了提问人 | 否 |

## 约束

- blocking 为 true 的发现由 runner 写成一轮返修回喂（`REVIEW-REPAIR-<n>.md`，报错格式同 validator，stage 记 `review`），返修后重跑 validator 和导出；false 的不触发返修，runner 记进 `out/result.json` 的 `review` 块，本来就要返修时顺带让返修 agent 写进 `out/notes.md`「评审意见」一节。
- 整轮审核只跑一次；返修后只复核上次报过的题（复核任务里列出题号），不重开全量。返修轮数见 online-runner.md「审核环」。
- `out/review.json` 缺失、不是合法 JSON 或结构不对时，runner 只记 warning、照常交付；validator 才是闸门。
- 发现为 0 不说明题库优秀，只说明这八条没查出问题；清单的增长方式是线下人工或强模型审出**新缺陷类别**后补条目（判据写得可核对才收，见选词 SKILL.md「维护本 skill」和定稿改动协议）。
