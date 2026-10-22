# Peec、GEO Bubbles、Ahrefs 三篇选题文章 vs 我们的生词流程

对照源（2026-10-15 读）：

- Peec AI《How to choose the right prompts for LLM tracking》
  https://peec.ai/blog/how-to-choose-the-right-prompts-for-llm-tracking
- GEO Bubbles《Prompt generation: source selection》
  https://www.geobubbles.com/blog/prompt-generation-source-selection
- Ahrefs《How to choose prompts to track》
  https://ahrefs.com/aeo/choose-prompts-to-track

三篇里我们原本缺的集中在一件事：收来的材料各自能决定什么。其余大多已有，少数是刻意不同。

## 采纳并写进 skill

| 文章里的做法 | 落在哪 |
|---|---|
| 信源分层：只从 AI 真实提示词样本和买家语言来源取措辞；官网、竞品页、人设文档、内部访谈、关键词工具只管覆盖和查漏；各来源的偏差（评价偏极端、论坛偏年轻懂技术、客服记录偏投诉退货、竞品术语的镜像陷阱）（GEO Bubbles） | [signal-sources.md](signal-sources.md) →「每类信源能用来干什么」；共享原则第 16 条；SKILL Step 8 |
| GSC 筛法：先剔品牌词；排名 11–30 有展示低点击；问句正则与 6 词以上（GEO Bubbles、Ahrefs） | signal-sources.md →「客户提供什么」GSC 行 |
| 搜索词改写成题面：不改意图、原查询越长改得越少、年份改成当年（Ahrefs）；补进的条件要有原话依据（GEO Bubbles 的约束与人设扩展，按我们的证据门收紧） | signal-sources.md →「搜索词改写成题面」 |
| Perplexity 相关问题是模型按原查询和结果生成的，不是历史查询（Ahrefs）；让 ChatGPT 列顾虑（Peec） | signal-sources.md →「模型生成的联想不算买家信号」；SKILL Step 2，与 query fan-out 同一处理 |
| Google 搜索加 `&udm=18` 只看论坛讨论（Ahrefs） | signal-sources.md 开头 |
| 服务器日志里 ChatGPT-User 等用户触发型抓取，看 AI 实际在读哪些页（Ahrefs） | signal-sources.md →「客户提供什么」AI 来源流量行 |

## 原本就有

品牌题与发现题分开统计（Peec 的品牌评估单列、Ahrefs 的品牌与非品牌分组），对应自然可见度只算 Discovery；按市场分开追踪（Peec 地理定位），对应每个市场独立题库快照与基线；看一组题而非单条回答（Ahrefs），对应 Topic 为分析单元、每题每平台跑 5 次；核对 AI 对品牌的描述（Ahrefs 第 10 条），对应 Accuracy 题；竞品出现而我方没出现的查询（Ahrefs 第 8 条），对应候选基线后的缺口诊断；购买阶段「去哪买」（Peec），对应旅程「交易」段，B2B 可不设，与 Peec 一致。

## 刻意不采纳

1. **认知阶段的顾虑题**（Peec 的 "Will electric vehicles hold their value?"）。只问事实或顾虑的题，AI 通常不给候选名单，读不出可见度；UNI_A 有 8 题、Ebrand 有 2 题曾因此出错。仍按 SKILL Step 8：只有项目明确要做问题认知观察时才单列，不计入核心发现型。
2. **起步题量**（Peec 的 10–20 条认知题加 20–30 条考虑题、先跑 30 天）。我们按交付范围定题量：候选主题每个至少 5 条，正式题每个采购主题最多 10 条。
3. **Bing AI Performance 的 grounding 查询作为第一层来源**（GEO Bubbles）。它是 AI 检索时改写出的查询，我们只用它检验措辞和信源覆盖，不当题面。
4. **题面加 "in 2026" 逼 ChatGPT 联网**（Ahrefs）。加年份会改变 AI 是否检索，新旧读数不可比，规则里没写；改写规则只要求原查询本身带年份时改成当年。
5. **人设题模板**（Ahrefs 的「处境、约束、优先需求、痛点、问题」五段式）。条件只在改变候选集合时才加（SKILL Step 9），不按模板叠条件；Ahrefs 自己也把人设题放在低优先级。
