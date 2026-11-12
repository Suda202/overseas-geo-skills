# 统计范围与客户指标命名契约

## 目的

先按指标确定样本范围，再编辑客户文案。不得先用某个诊断意图筛掉记录，再从剩余记录计算其他指标。Task 190 已证明，单一筛选条件会同时制造“非 Discovery 混入可见度”和“情绪样本被误删”两类相反错误。

## 样本范围

| 指标或证据 | 正式样本范围 | 必须排除 | 交叉适用规则 |
|---|---|---|---|
| 正式可见度：品牌提及率、提及率排名、指定竞品内声量、平均提及位置、问题机会 | 后端确认的 Discovery 样本 | Competitor、Validation、Accuracy、Evaluation/Sentiment、Market Perception 等非 Discovery 样本 | 即使非 Discovery 记录也带 `visibility` 处理标记，仍不得进入正式可见度 |
| 主要引用生态与引用份额 | 后端确认的 Discovery 样本中的引用 | 所有非 Discovery 引用 | 其他意图的引用只能另列并明确范围，不得并入主要引用份额 |
| 评价/情绪 | 完整 `analysis_type=sentiment` 数据 | `analysis_type` 不是 `sentiment` 的记录 | 不再按 `diagnostic_intent`、Discovery/Evaluation、通用题/品牌题或其他意图二次筛选 |
| 竞品胜负 | 后端确认的 Competitor 样本 | 一般情绪、Discovery 提及率和品牌常识 | 只进入 M02 的决胜结果与正面对比证据，不进入正式可见度或情绪比例 |

**售前 HTML 报告与监测基线 HTML 的口径（2026-11-07 定，2026-11-10 基线统一到同一套）与上表不同，只用于我们自己出的 HTML 报告，不改上传 CSV 和后端：**

- 统计层默认原则（2026-11-10 Suda）：引用默认统计全部意图类型，各类型切片都算出来；展示哪一批由报告按需求决定。

- 提及类指标（提及率、提及率排名、声量份额、平均提及位置）只统计发现＋替代（11-06 前的旧类型「品类认知」题面不点名品牌，并入这一组）；问题解决不统计提及率（11-11 Suda 定），筛到只剩问题解决题时显示「当前筛选下不统计」；对比、评估、验证、交易、售后题面点名了品牌，提及率接近 100%，不统计（显示「—」）。
- 引用分两处：**核心洞察的引用份额、引用率和可见度矩阵的品牌引用份额只看发现＋替代**，与提及率同一批回答（2026-11-07 Suda：点名题会把被点名品牌的官网拉进引用，Bbrand H1 全部类型引用份额 13.1%、发现＋替代 0%，混在一起没法和提及率比）；**引用模块（来源类别、域名、页面、官网页面）和问题明细统计全部意图类型**，按数据筛选收窄。
- 实现：`build_report_data.build_config` 写 `visibility_intent_groups = [["discovery", "alternatives"]]`、`citation_scope = "visibility"`（核心洞察的引用与提及类同一批回答），core `compute_metrics` 读这两个键；不写 `citation_scope` 时 core 统计全部有效回答；`build_sources` 从全部有效回答算引用模块。编辑侧影子审计显式写 `citation_scope = "visibility"`，提及类不写分组时只看 Discovery，对齐上传 CSV。`verify_report_data.py` 按同口径独立复算，页面多选由 `report-engine.js` 现算、`check_engine_parity.js` 对账。
- 监测的基线 HTML（`geo-monitoring/scripts/build_baseline_html.py`）2026-11-10 起与售前同一套口径，不再打补丁：题库写真实意图类型，取代 10-22 的「所有题都计入提及率、全部类型引用只合并发现和品类认知」。

执行两条独立判定，不使用互斥的“先按意图选一类”逻辑：

1. 判断记录是否属于 Discovery；只有是，才允许进入正式可见度和主要引用生态。
2. 单独读取 `analysis_type`；只要等于 `sentiment`，就保留情绪结果，不要求它同时属于 Discovery 或某个特定 `diagnostic_intent`。

同一记录可以为不同模块提供彼此独立的证据，但每个指标必须使用自己的正式分母。报告编辑侧直接消费后端返回的完整 Sentiment 聚合；如果只有明细，仅依 `analysis_type=sentiment` 取数，不再叠加诊断意图筛选。

情绪标签必须反映回答对目标品牌的全文主导评价。“竞品在某方面更强”“某项信息仍需核验”“独立证据不足”等限定，不自动等于目标品牌负向；只有回答对目标品牌形成明确且占主导的否定、风险或不推荐判断时才标为负向。报告编辑侧不自行重判已确认标签，但发现标签与该原则冲突时应退回指标审计，不用错误标签生成客户结论。

## 客户指标命名

| 客户名称 | 含义 | 不得混淆为 |
|---|---|---|
| 品牌提及率 | 去引用正文里出现品牌名或它的任一识别名称的 Discovery 回答数 ÷ Discovery 有效回答数。识别名称包括不含品牌名的自有产品名和子品牌名（LG 的 PuriCare）：只提产品也计入母品牌，与 Profound 子资产向上汇总一致（2026-11-10 Suda 定）。AI 反问用户、让用户选的追问块里出现的品牌不计提及（2026-11-11 Suda 定）：ChatGPT 表单按 `follow_up_form` 字段定位、从第一个提问句删到提交按钮那一行（`strip_follow_up_form`）；没有表单的普通追问，向用户提问的句子（非 Markdown 标题）连同后面紧跟的 2 条以上短列表项一起删（`strip_choice_lists`）。正文里的自检清单（`- [ ] Confirm …`）照常计入。只看结构和版式，不看行业。一条回答提到多个名称只计一次，产品本身不另出提及率 | 推荐率、引用率、产品级提及率 |
| 提及率排名 | 在同一 Discovery 样本和冻结品牌集合中，按品牌提及率比较得到的相对名次 | 正文首次出现顺序、推荐顺序 |
| 平均提及位置 | 品牌在被提及的 Discovery 回答正文中的首次合格出现位置取平均；只在品牌被提及时成立 | 提及率排名、模型对品牌优劣的语义排序 |
| 引用份额 | 某来源、域名、页面或来源类型被引用的次数 ÷ 同一 Discovery 样本的全部引用次数。分子分母都按未去重次数计：同一回答多次引用同一来源计多次；去重只用于统计「有多少个不同来源」，不进份额。分母必须随数值一起确认 | 可见度、推荐率、流量占比、官网引用率 |
| 官网引用率 | 正文至少引用一次品牌官网的 Discovery 回答数 ÷ Discovery 有效回答数；按回答计票，一条回答引用多次只算一次。分母是全部有效回答，不是被提及的回答 | 引用份额、带官网的提及率 |
| 带官网的提及率 | 品牌被提及的 Discovery 回答中，正文同时引用了该品牌官网的回答占比；分母是「被提及的回答数」，必须随数值一起给出 | 引用份额、推荐率、点击率或流量 |

客户文案、CSV、任务说明、字段说明和校验统一使用“平均提及位置”和“引用份额”。“平均提及排名”“引用占比”“官网引用占比”是废弃名称，不得继续输出。

无品牌提及时，平均提及位置写 `-` 或 `—`，不得写第 0 位。平均提及位置更靠前，只能说明首次出现位置更靠前；不能单独推出推荐更强、评价更正面或提及率更高。提及率排名领先，也不能推出平均提及位置一定更靠前。

## 购物层指标（Shopping GEO）

对标 Profound Shopping Analysis（Shopping Mode Rate、Shopping Visibility Score）。实现只在 `scripts/geo_presales_core/shopping.py`（`metrics["shopping"]`）；不进入 `action_directions`、M01–M10 模块与上传 CSV。售前 HTML 有独立的「购物商品卡」模块（`geo-presales-report-builder/references/render-spec.md`「购物商品卡模块」），核心洞察另放一个商品卡提及率。和正文提及率分开报，不混算：正文提及率的分母是全部有效回答，商品卡提及率的分母是出现商品卡的回答，两个百分比不能直接比。目前是实验性监测模块，不进客户考核。

### 哪些产品线、哪些题统计

- **产品线开不开由我们推理决定，不让品牌方填**：消费类实体商品（3C、家电、个护、宠物用品、服饰等）开；软件、SaaS、服务、房地产关；工业、工程类实体商品先记「试跑后定」，试跑里这条产品线的回答出卡比例到 5% 就开，不到就关。售前没有试跑，工业类记关。判断和理由记在题库 `config.shopping_cards`（选词 output-contract.md）。关掉的产品线照常采集商品字段，但不汇总、不报，也不写 0%。
- **题的范围**：只统计发现、替代两类（2026-11-07 Suda 定，原为发现、替代、对比、交易四类）。这两类题面不点名本品，卡里是 AI 自己挑的候选，才能看出本品进没进、和竞品比；对比、交易题题面点名本品，出卡和进卡都是题面带出来的。其余类型照常采集商品卡字段，不进汇总。
- **原始数据都在采集目录里**：商品卡、商品名、品牌、位置、商家、购买链接都在各平台原始响应里，以后要加 SKU、商家、渠道分析不用重新采集。

### 来源字段

| 层 | 计数单位 | 来源字段 |
|---|---|---|
| 回答是否触发购物 | 回答 | 至少一张商品卡即算触发 |
| 商品卡（Product Card） | 卡 | ChatGPT / AI Mode / Gemini：`products[]`；AIO：`source[]` 中 `type=product` |

**ChatGPT 只认带商品目录的购物卡**（2026-11-11 Suda 定）：`products[]` 条目带 `id`、`cite`（如 `turn0product7`）、`offers`、`price` 之一才算商品卡，判断在 `shopping.chatgpt_catalog_backed`。不带的条目不计，包括两类：

- 没有商品目录的市场里，回答用卡片版式展示的商品推荐。肯尼亚、尼日利亚实测，回答页上的卡没有价格、商家、购买入口，图片是网页配图，`products` 只剩 `title` 和 `query`。OpenAI 原文 "Shopping is currently live for ChatGPT users in the U.S."（https://chatgpt.com/merchants/）。
- 非商品条目，如「RivalH1」「Facebook Marketplace」。

全项目实测：美国 1,333 条带目录证据、2 条不带；肯尼亚、尼日利亚 10,822 条全不带。一个市场全是这类条目时，该市场商品卡数为 0，报告按「本次采集没有商品卡」整块不出。

AIO 的 `task_result.products[]` 不计：Scrapeless 文档把 AI 概览内的商品定义在 `source[]`（「products inside ai overview」），`products` 定义为「Google wale sponsored products」；实测 `products` 379 项里 371 项不在同一回答的 AI 概览商品中，`section_title` 是 People also ask、Popular products、Deals 等页面区块名。空占位卡（无标题）和广告卡（`ads product`、`ads`）不计。

### 指标

都按平台分开算，「回答」都指有效回答，同一回答里本品有几张卡都只算一次。

| 中文名称 | 对标 | 公式 | 内部字段 |
|---|---|---|---|
| 商品卡触发率 | Profound Shopping Mode Rate | 出现商品卡的回答数 ÷ 有效回答数 | `shopping_mode_rate` |
| 商品卡提及率 | Profound Shopping Visibility Score | 至少有一张本品牌商品卡的回答数 ÷ 出现商品卡的回答数。只数商品卡里的品牌，不含正文提及 | `brands[].shopping_visibility` |
| 商品卡平均位置 | Average Position | 每条出现本品牌卡的回答里，本品牌最靠前那张卡的位置，取平均 | `brands[].average_card_position` |
| 官网购买链接覆盖率 | Writesonic Direct Purchase Link（按回答计） | 出现本品牌商品卡的回答里，这些卡至少带一个官网购买链接的回答占比。官网 = 链接域名是品牌官网，或商家名带品牌名（「Bbrand」「RivalB1 Official」） | `brands[].official_link_coverage` |

百分比一律保留 1 位小数，和报告其他指标同一精度（core 调用 `percent(n, d, 1)`，前端 `report-engine.js` 的 `corePercent` 同式）；整数时不写小数点（72% 不写 72.0%）。2026-11-09 Suda 发现核心洞察 8.5% 与模块表格 8% 对不上，就是这里原来取整到整数造成的。
例：100 条 ChatGPT 回答，60 条出了商品卡，其中 18 条有本品的卡、入选时平均在第 2.5 位：商品卡触发率 60%，商品卡提及率 30%（18 ÷ 60），商品卡平均位置 2.5。

**品牌级、SKU 级分开算**：上表是品牌级（本品任意一张卡都算）。SKU 级只看本品，同样三项——SKU 商品卡提及率（出现该 SKU 卡的回答 ÷ 出现商品卡的回答，分母和品牌级相同）、SKU 商品卡平均位置（该 SKU 在每条回答里最靠前那张卡的位置取平均）、SKU 官网购买链接覆盖率（出现该 SKU 卡的回答里带官网购买链接的占比），内部字段 `target_skus[]`。覆盖率用回答计，不用 offer 份额：份额会被第三方商家数量稀释（Bbrand ChatGPT 本品 offer 里官网只占 40%，但每条出现 Bbrand 卡的回答都带官网链接，覆盖率 100%）。同一款产品 AI 会写成好几种标题，所以先按归并表（`build_report_data.py --sku-map`，每条是「SKU 名 + 正则」，按顺序第一条命中卡标题的胜出）归到型号再数；配件单列；都不中的记「未识别型号」——Google 系（AIO、AI Mode）的卡标题常不带型号（「Bbrand Dash Cam Car Security Camera」），这一行会比较大。各 SKU 的提及率相加可以超过品牌级，因为一条回答可能同时出现两个 SKU。归并表按客户写，放在客户的评测目录（Bbrand：`10-售前诊断报告/评测数据/brand-b/售后/选词-20261106/report-h1/sku-map.json`）。

`brands[].shopping_exposure_rate`（有本品卡的回答 ÷ 有效回答，等于触发率 × 提及率）只留在数据里，不展示。

**不做（2026-11-07 Suda 定）**：商品卡份额（本品卡数 ÷ 全部卡数）、商品卡首位率、官网购买链接份额（按 offer 计）、商家份额，计算和展示都删了。理由：品牌是否进卡、排第几已经由提及率和平均位置回答，份额和首位率只是同一件事换个分母；官网入口用覆盖率看，不看份额。以后要用可以从原始响应补算。商品卡情感、属性准确率、价格准确率也不做。

- **按平台分开计算，不跨平台合并。** Gemini 每条回答 12–19 张卡，ChatGPT 1–6 张，卡位和排名合池没有意义；全部平台切片只给 `by_platform`。例外：核心洞察的商品卡提及率在「全部平台」时把返回了商品字段的平台合计（分子、分母各自相加），因为它按回答计。
- **接口未返回**：平台本身不返回商品字段（Perplexity），或本次采集里该平台一条回答都没带商品字段（`product_field_returned = false`；2026-10 中起 Scrapeless 的 Gemini 1,700 多条回答都没有 `products`，2026-11-07 用 3 道 ChatGPT 出卡的发现题复测仍没有），整列写「接口未返回」，不写 0%，也不进核心洞察的合计。AI Mode 只在出卡时才带 `products` 键，缺键按未触发处理。
- 实现：`shopping.py` 的 `SHOPPING_SCOPE_INTENTS` 定发现、替代两类；按意图类型筛选靠报告的意图类型 / 主题切片。产品线开关：`build_report_data.py --shopping-cards 开|关` 写进 `meta.shopping_cards`，没传时按数据判（任一平台触发率到 5%），见 render-spec.md。
- 卡片品牌归属顺序：平台 `brand` 字段 → 卡标题最早出现的别名 → offer 的 `product_name` → 商家名（全部可识别商家指向同一品牌时）。都不中的卡记为未归属，单独计数。
- 卡位按平台字段顺序编号。ChatGPT 实测与正文商品表顺序约 5% 不一致，平均位置是近似值。

### 客户指标命名

| 客户名称 | 内部字段 | 不得混淆为 |
|---|---|---|
| 商品卡触发率 | `shopping_mode_rate` | 商品卡提及率、品类适合度结论 |
| 商品卡提及率 | `brands[].shopping_visibility` | 正文提及率 |
| 商品卡平均位置 | `brands[].average_card_position` | 平均提及位置（正文） |
| 官网购买链接覆盖率 | `brands[].official_link_coverage` | 官网引用率（正文引用官网）、官网购买链接份额 |

## 引用来源分类（引用类别）

报告里的「引用类别」不是采回来的字段，是**我们自己判**的。采集结果只有 URL、host 和来源名（`content_references` / `citations` 里没有 `source_type`），不判就会全部落进「其他」——2026-11-11 某制氧机客户两份售前报告就是这样，305/373 条引用全是「其他」。

判定顺序固定，先命中先返回：

1. **自有网站**：host 等于或属于 `official_domain`（`example.com` 与 `*.example.com`）。
2. **竞品网站**：host 命中词表的 `competitor_site_domains`（配置竞品官网 + 开放品牌官网，后端规则同桶）。
3. **域名缓存**：`assets/domain-categories.json`，按 host 精确匹配，再按后缀匹配（`blog.example.com` 命中 `example.com`）。缓存值只允许 `media_review`（媒体网站）/ `ugc`（社区与论坛）/ `institutional`（机构与官方）/ `press_release`（新闻稿）/ `other`。
4. 以上都不命中 → `other`。

实现只有一处：`geo-presales-report-builder/scripts/build_report_data.py` 的 `classify_source_host()`，引用对象建好时就写入 `source_type`，报告端只读不重算。

- **缓存要用起来**：`--domain-cache` 传的那份文件必须真的参与判定。它写进 `config.domain_category_cache` 之后没有消费方，等于没接（2026-11-11 修）。缓存本身随每次运行生长，新域名判过一次就进表。
- **「其他」占比高先看两件事**：自有/竞品域名有没有传进来；缓存有没有命中。这两项都正常还有大量「其他」，才是真的判不出来，交付说明里要写清这一项的可信度。
- 分类是展示口径，不参与提及率、声量份额、引用份额的计算，改分类不改那些数。
