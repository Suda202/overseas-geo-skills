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

执行两条独立判定，不使用互斥的“先按意图选一类”逻辑：

1. 判断记录是否属于 Discovery；只有是，才允许进入正式可见度和主要引用生态。
2. 单独读取 `analysis_type`；只要等于 `sentiment`，就保留情绪结果，不要求它同时属于 Discovery 或某个特定 `diagnostic_intent`。

同一记录可以为不同模块提供彼此独立的证据，但每个指标必须使用自己的正式分母。报告编辑侧直接消费后端返回的完整 Sentiment 聚合；如果只有明细，仅依 `analysis_type=sentiment` 取数，不再叠加诊断意图筛选。

情绪标签必须反映回答对目标品牌的全文主导评价。“竞品在某方面更强”“某项信息仍需核验”“独立证据不足”等限定，不自动等于目标品牌负向；只有回答对目标品牌形成明确且占主导的否定、风险或不推荐判断时才标为负向。报告编辑侧不自行重判已确认标签，但发现标签与该原则冲突时应退回指标审计，不用错误标签生成客户结论。

## 客户指标命名

| 客户名称 | 含义 | 不得混淆为 |
|---|---|---|
| 提及率排名 | 在同一 Discovery 样本和冻结品牌集合中，按品牌提及率比较得到的相对名次 | 正文首次出现顺序、推荐顺序 |
| 平均提及位置 | 品牌在被提及的 Discovery 回答正文中的首次合格出现位置取平均；只在品牌被提及时成立 | 提及率排名、模型对品牌优劣的语义排序 |
| 引用份额 | 某来源、域名或来源类型的引用量占后端指定引用总量的份额；分母必须随数值一起确认 | 可见度、推荐率、流量占比 |
| 带官网的提及率 | 品牌被提及的 Discovery 回答中，正文同时引用了该品牌官网的回答占比；分母是「被提及的回答数」，必须随数值一起给出 | 引用份额、推荐率、点击率或流量 |

客户文案、CSV、任务说明、字段说明和校验统一使用“平均提及位置”和“引用份额”。“平均提及排名”“引用占比”“官网引用占比”是废弃名称，不得继续输出。

无品牌提及时，平均提及位置写 `-` 或 `—`，不得写第 0 位。平均提及位置更靠前，只能说明首次出现位置更靠前；不能单独推出推荐更强、评价更正面或提及率更高。提及率排名领先，也不能推出平均提及位置一定更靠前。

## 购物层指标（Shopping GEO）

对标 Profound Shopping Analysis 的 Brands / Products / Merchants 三层。实现只在 `scripts/geo_presales_core/shopping.py`（`metrics["shopping"]`）；当前只做统计输出，不进入 `action_directions`、M01–M10 模块与上传 CSV，售前 HTML 也不展示。客户文案要用这些数之前，先在本节补模块归属。

### 三层数据、三个计数单位

| 层 | 计数单位 | 来源字段 |
|---|---|---|
| 回答是否触发购物 | 回答 | 至少一张商品卡即算触发 |
| 商品卡（Product Card） | 卡 | ChatGPT / AI Mode / Gemini：`products[]`；AIO：`source[]` 中 `type=product` |
| 购买选项（Offer） | offer | ChatGPT：`offers[]`；Google 系：`stores[]` |

一张卡对应多个 offer，商品曝光和商家份额不能互相换算。AIO 的 `task_result.products[]` 不计：Scrapeless 文档把 AI 概览内的商品定义在 `source[]`（「products inside ai overview」），`products` 定义为「Google wale sponsored products」；实测 `products` 525 项里 513 项不在同一回答的 AI 概览商品中，`section_title` 是 People also ask、Popular products、Deals 等页面区块名。文档另一处说 `products` 带商品簇的商家报价，两处不一致，待供应商确认。空占位卡（无标题）和广告卡（`ads product`、`ads`）不计。

### 样本范围

| 指标 | 分子 | 分母 | 范围 |
|---|---|---|---|
| 购物触发率 | 至少有一张商品卡的回答 | 有效回答 | 全部诊断意图，另按诊断意图拆开报 |
| 购物可见度 | 至少有一张该品牌商品卡的回答（回答级去重） | 触发购物的有效回答 | 仅 Discovery |
| 购物曝光率 | 同上 | 有效回答 | 仅 Discovery；推导值 = 购物可见度 × Discovery 购物触发率 |
| 商品曝光率 | 出现该商品的回答（同一回答只计一次） | 触发购物的有效回答 | 仅 Discovery |
| 平均商品卡位置 | 品牌或商品在回答内首张卡的位置之和 | 出现该品牌或商品的回答数 | 仅 Discovery；内部字段 |
| 商家份额 | 该商家的 offer 数 | 全部 offer（同一回答内「商家 + 链接」相同只计一次） | 仅 Discovery 触发购物的回答 |
| 商家内品牌份额 | 该商家 offer 中属于目标品牌卡的 offer | 该商家的 offer | 同上 |
| 官方店入口占比 | 目标品牌卡中官方店 offer | 目标品牌卡的全部 offer | 同上 |

- **按平台分开计算，不跨平台合并。** Gemini 每条回答 12–19 张卡，ChatGPT 1–6 张，合池后的排名没有意义；全部平台切片只给 `by_platform`。
- 没有商品字段的平台（Perplexity）不计，显示 `—`，不写 0%。Gemini 与 AI Mode 只在有商品时才交付 `products` 键，缺键按未触发处理；供应商改版后需重新核验。
- 购物可见度必须和购物触发率一起出现：触发率 20% 时的 50% 可见度，只覆盖全部 Discovery 回答的 10%。
- 卡片品牌归属顺序：平台 `brand` 字段 → 卡标题最早出现的别名 → offer 的 `product_name` → 商家名（全部可识别商家指向同一品牌时）。都不中的卡记为未归属，单独计数。
- 官方店：offer 域名命中该品牌官网域名，或商家名命中该品牌别名。Google 系 `stores` 链接常是跳转串，只能靠商家名判断。判定依赖品牌词表的官网域名：词表没登记官网域名、商家名又是域名写法（如 `redtigercam.com`）时会记成第三方；平台店铺名带品牌名（如 `Walmart - Redtiger Official`）记为官方。
- 卡位按平台字段顺序编号。ChatGPT 实测与正文商品表顺序约 5% 不一致，平均商品卡位置只放内部字段，不进客户文案。

### 客户指标命名

| 客户名称 | 内部字段 | 不得混淆为 |
|---|---|---|
| 购物触发率 | `shopping_mode_rate` | 品牌购物可见度、品类适合度结论 |
| 购物可见度 | `brands[].shopping_visibility` | 正式可见度（提及率）、购物曝光率 |
| 购物曝光率 | `brands[].shopping_exposure_rate` | 购物可见度 |
| 商品曝光率 | `products[].exposure_rate` | 品牌购物可见度 |
| 商家份额 | `merchants[].merchant_share` | 销量份额、流量份额 |
