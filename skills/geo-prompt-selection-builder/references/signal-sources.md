# 需求信号去哪收、怎么用

选词第 2 步「收需求信号」的来源和用法，规则总纲见 [selection-rules.md](selection-rules.md) → 2。本文件只写我方自己收的公开数据（搜索数据、评价、社区、官网、AI 答案）；品牌方提供的数据（销售、客服、GSC、Bing、Google Ads 等）见 [demand-side-signals.md](demand-side-signals.md)。每个站走哪个通道抓，见 [community-channels.md](community-channels.md)。脚本用法看各脚本的 `--help`。

先做所有行业都要做的，再按行业收评价和社区，最后按目标市场加当地平台。下面的表是起点：每个品牌 × 市场先确认站上确实有本品类的讨论再收，没有的跳过并记一句；表里没有、但买家确实在那里讨论的站，按规则外推理补上（selection-rules.md 总纲第四条）。每条原话在「出处」记网址。

## 所有行业都做

| 类别 | 去哪收 | 用来判断什么 |
|---|---|---|
| 搜索数据 | `shared/scripts/collect_serp_signals.py` 取 People Also Ask、相关搜索、自动补全（每个种子词 1 次付费调用）。种子词：品类词，加 2–3 个相邻词（场景词、竞品品类词，核心词下的 PAA 常很少）；每个竞品加 `<竞品名> alternative`，本品加 `<本品名>`（品牌词下有用的是「alternative to X」「Is X legit」这类相关搜索和补全）。月搜索量、长尾词、Trends 用 `collect_keyword_data.py` | 需求是否存在、买家怎么问 |
| 品牌官网 | 卖什么、卖给谁、在哪卖、能做到什么 | 见 selection-rules.md → 2「品牌官网」 |
| 竞品官网 | 服务谁、强调哪些选择条件、FAQ 里的买家问题 | 见 selection-rules.md → 2「竞品官网」；只开假设级候选 |
| 已采集的 AI 回答 | 预跑、试跑、基线的答案 | 选购标准、AI 追问的条件、品牌事实 |

Google 搜索默认跑脚本，不用本地浏览器：本机 IP 不在目标市场、浏览器带登录和搜索历史，结果会变，PAA 也不一定渲染。本地浏览器只在三种情况用：逐层点开 PAA、要登录或反爬强的站、脚本对某个种子词失败时人工核对（线上没有浏览器，替代做法见 online-runner.md）。搜索词逐条判断，求职、登录、下载、词义查询这类无关词跳过。

## 按行业收评价和社区

| 行业 | 评价 | 社区 |
|---|---|---|
| B2B 软件与 SaaS | G2、Capterra、TrustRadius、Gartner Peer Insights | Reddit 相关版块（r/sysadmin、r/SaaS）、LinkedIn |
| B2B 服务与代理 | Clutch、G2 服务类目、Sortlist、DesignRush | Reddit r/marketing、r/ecommerce，LinkedIn |
| 工业品与零部件 | Alibaba、Made-in-China、Global Sources 的买家评价与询盘问答；美国加 ThomasNet | 行业协会与展会资料、行业媒体、Reddit 行业版块 |
| 医疗器械 | Amazon 和医疗器械零售商的商品评价；FDA MAUDE 不良事件 | 患者社区（COPD360social、r/COPD） |
| 消费电子与智能家居 | Amazon 评价与问答、Best Buy；RTINGS、Wirecutter；YouTube 评测评论 | Reddit 品类版块（r/dashcam、r/smarthome） |
| 美妆与保健品 | Amazon、iHerb、Sephora、Trustpilot | r/SkincareAddiction、r/Supplements；TikTok、Instagram 评论 |
| 教育与留学 | QS、THE 等排名与院校页 | 目标市场学生论坛（泰国 Pantip、Dek-D）、Facebook 群组 |
| 内容与流媒体 | Google Play、App Store | MyDramaList、r/CDrama；泰国 Pantip |
| 开发者工具与云基础设施 | Trustpilot、Capterra、TrustRadius | Hacker News、Reddit 相关版块（r/LocalLLaMA、r/devops） |
| 消费级软件与在线服务（安全软件、VPN、在线订票等） | Trustpilot、Google Play、App Store | Reddit 品类版块 |
| 本地生活与门店 | Google 地图 | 本地论坛、Reddit 城市版块 |
| 其他实体消费品（家居、宠物、母婴、服饰、运动户外、汽车用品、食品等网上零售的实物） | Google Shopping 汇总的零售站评价、Trustpilot | Reddit 品类版块 |

线上 runner 按 [precollect-channels.json](precollect-channels.json) 的行业行和市场行固定采一轮；改上表或下表时同步改那份 JSON（不通的站不进 JSON）。

Trustpilot、Google Play、App Store、Google Shopping、Google 地图的评价跑 `shared/scripts/collect_reviews.py`（DataForSEO，不用浏览器；每次约 0.001 美元量级）。消费品要 Amazon 评价时跑 `google-shopping`：取商品下汇总的零售站评价，出处写原评价在哪个站。门店类品牌用 Google 地图，连锁店加 `--match` 防止搜到别家。

## 按目标市场换成当地平台

| 市场 | 优先看 |
|---|---|
| 泰国 | Pantip、Shopee、Lazada、Facebook 群组 |
| 日本 | Kakaku.com、Amazon JP |
| 韩国 | Naver 博客与 Naver Cafe |
| 东南亚其他市场 | Shopee、Lazada |

community-channels.md 标「不通」的站（Shopee、Lazada、G2、Dcard、Quora 等）不派脚本收，本地可改用深度调研或人工，线上记进「未覆盖来源」。

## 每类数据怎么用

| 数据 | 进需求信号表吗（来源类型） | 用在哪 | 月搜索量 |
|-|-|-|-|
| PAA、相关搜索、自动补全 | 是，搜索联想 | 需求和问法线索、竞品替代说法 | 不填 |
| 关键词工具（DataForSEO、Keyword Planner、Naver） | 是，按工具选 | 主题父关键词的量、长尾词 | 填 |
| Google Trends | 否 | 相对热度和季节性，写进主题优先级依据和任务记录 | — |
| 评价 | 是，评价 | 约束条件、题面具体条件 | 不填 |
| 社区（Reddit 等） | 是，社区 | 约束条件、目标客户和使用场景依据、题面措辞和具体条件 | 不填 |
| 品牌官网、竞品官网上品牌写的内容 | 是，品牌官网 / 竞品官网 | 目标客户、场景、约束条件候选；只开假设级候选 | 不填 |
| 预跑答案 | 否 | 约束条件候选（AI 的选购标准）、品牌事实核查 | — |
| 试跑和基线答案的子查询（ChatGPT `search_model_queries`、Grok `tool_usages`） | 是，query fan-outs | 提示漏掉的约束条件和场景，只开假设级候选（子查询由我们的题生成，不是买家原话） | 不填 |
| 答案末尾 AI 反问的条件（ChatGPT `follow_up_form`，其他平台读正文末段） | 是，AI 追问 | 查约束条件有没有漏，只开假设级候选 | 不填 |
| 平台推荐的延伸问题（Gemini `related_queries`、Grok `follow_up_suggestions`、Perplexity 相关问题）、让模型列的顾虑和搜索词 | 是，模型建议问题 | 提示漏掉的约束条件和候选题，只开假设级候选 | 不填 |

官网上买家自己写的评价、问答按评价、社区登记（判法见 selection-rules.md → 2「品牌官网」）。

**模型生成的都不是买家原话**：query fan-out、AI 追问、延伸问题、让模型列的顾虑，都是模型根据题面生成的，可以提示漏掉的条件、开假设级候选，不说明需求高频。AI 追问常问而信号里没人提的条件，找到买家依据才登记成信号或补题；信号里有而 AI 从不追问的条件不删。

### 月搜索量取哪家的

- **取量方法**：品牌方给了 Semrush / Ahrefs / Similarweb 数据的直接用；没给的跑 `collect_keyword_data.py volume`（DataForSEO）；Keyword Planner 没投放只给区间，只作参考；韩国用 Naver（PC 与移动相加）。来源类型按工具选，主题优先级依据里写明量取自哪家（只作参考，不参与排序，selection-rules.md → 6）。
- **填法**：需求信号表「月搜索量」分四档（超过 1 万 / 超过 1000 / 超过 100 / 低于 100），只填真实搜索量。同一需求的几种说法搜的是同一批人，不相加，取量最大那个词的档位。
- **展示量不算搜索量**（全书只在这里定义）：GSC、Bing、Google Ads 的展示量和站内搜索次数都不填进「月搜索量」，要量拿关键词工具补查。

## 每类信源能用来干什么

| 信源 | 可以用来 | 不能用来 | 偏差 |
|---|---|---|---|
| 评价 | 买家自己的用词、约束和场景；中差评找决策摩擦 | 按话题次数判断需求大小 | 极满意和极不满的人写得多 |
| 论坛与社区 | 求推荐帖原句可直接作发现题素材；互动多的帖子里反复出现的硬条件 | — | 发帖人偏年轻、偏懂技术；对小众企业软件参考价值低 |
| 自动补全、PAA、相关搜索 | 需求存在的证据、新问法、改写成题面的种子 | 估主题规模；不改写直接当题面 | 反映搜索习惯，对 AI 提问方式是滞后信号 |
| Google Trends | 品类有两种以上常见叫法或季节性明显时才查：比较叫法定发现题用哪个品类词；看季节性，基线避开旺季；「飙升」相关查询作候选新叫法，在评价或社区确认后才进题面。选定的叫法和对比写进主题优先级依据，旺季写进任务记录 | 估绝对需求；决定措辞 | 只有相对值，一组叫法要一次给齐才能比；小品类、B2B 软件常没数据 |
| 关键词工具 | 估主题搜索量（取父关键词）、长尾词 | 生成题面；估 AI 提问量（多数 AI 提问对不上任何搜索词）；查竞品域名的排名词（多是竞品博客和型号词） | 一个词背后可能是几种不同的提问 |
| 品牌官网 | 列产品线、人群、价格档位和市场范围，决定覆盖什么；判硬条件和品牌明显劣势 | 决定措辞；当买家需求证据 | 用品牌的说法，买家说法常不同 |
| 竞品官网 | 补漏掉的人群、场景和决策条件 | 决定措辞；当开行的买家证据 | 强调的是竞品卖点，买家在不在意要另核 |

题面措辞优先取评价、社区原话（有品牌方数据时还有销售、客服、AI 平台真实提示词样本，见 demand-side-signals.md），或按下节改写的搜索词。出不出一道题、加不加一个条件综合所有信息判断：买家原话不可能收全，搜索数据、预跑、买家常识都可以作依据，没有对应原话的条件写进 `condition_basis`。

## 搜索词改写成题面

搜索词（PAA、自动补全、GSC、Google Ads 等）改写成买家问 AI 的样子才能进题库：

- **先分簇，一簇最多一道代表题**：同一场景、带同样会改变答案的条件算一簇，只是词序、单复数、同义词、年份不同的归一簇；条件不同、候选或标准跟着变的分簇。没带来新需求、没改善问法的簇不出题，簇里的查询仍可作已有题的证据。
- **只改措辞不改意图**：候选集合和决策任务不变；按意图类型写成买家会问的话，不照搬关键词堆叠；年份改成当年。
- **补的条件要有依据**：挂需求信号原话，或写进 `condition_basis`；条件个数照 selection-rules.md → 7。
- 簇里用上的每条查询各登记一条需求信号，代表题的「证据」挂这些编号。

## 本地调研补充

- **派子代理调研**：取数统一走 `shared/scripts/net.py`（`search` 跑 Google，`fetch` 直连→目标国代理→Wayback，`render` 只给 JS 空壳页），不先试 WebSearch / WebFetch（经公司网关会报 400）。brief 写明页面数和请求数上限、每完成一条就写文件、写入前用脚本校验原话是页面原文的子串。
- **用大模型深度调研查漏**（选做）：四类信号收完后，让 ChatGPT、Claude、Gemini 按目标客户 × 场景列买家意图、每条附原帖链接。结果按「模型建议问题」登记，只查漏；要改记成社区、评价的那几条先打开原帖核对原话（深度调研会挂错帖子）。用干净会话问（带账号记忆会把正在研究的品牌塞进答案）；政策和费率以官方页为准；它给的「最常问 Top 10」不是搜索量。
