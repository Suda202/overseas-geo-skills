# 方法依据

诊断规则背后的研究记录留在项目内部，不随 skill 发布：综合结论加 A–G 分来源的原始记录（A 厂商公开方法论、B 从业者、C 实证、D 实体与检索派专家、E 查漏、F Citation Labs 精读、G Ahrefs 工作流与书籍）。下表只列直接决定规则的依据，2026-11-16 逐条回原文核过。

| 规则 | 依据 | 出处 |
|---|---|---|
| 七层分开读，不是漏斗；不把「没被引用」当「没被检索」 | Citation Labs 六区域（"These zones are not a funnel."、"Do not turn 'not cited' into 'not retrieved.'"） | citationlabs.com/operating-system/field-guides/ai-visibility/（2026-09-12），原文已存档 |
| 检索、引用、提及是三件事 | Dan Petrovic："every citation was a grounding source, but most grounding sources are never cited."；Ahrefs：ChatGPT 检索到的网址只有 49.98% 被引（140 万提示词） | dejan.ai/blog/grounding-citation-mention/（2026-07-07）；ahrefs.com/blog/why-chatgpt-cites-pages/（2026-04-15） |
| 第一断点、串行前置 | Citation Labs §11「first useful point of diagnosis」；Jason Barnard "U unlocks C. C unlocks D." | 同上；kalicube.pro/methodologies/the-kalicube-process |
| 引用不等于推荐，要单独标推荐 | Lily Ray：品牌自写榜单被引时 69%–83% 没被推荐（二手转述）；Citation Labs ARB 编码 D-REC / Q-FIT / X-WARN / Z-GAP | seohandbook.co.uk 转述；citationlabs.com/citation-optimization-framework/ |
| 「被认识」和「被推荐」分开 | Discovery Gap：112 家初创公司点名识别 99.4%，发现型查询 3.32% | arxiv.org/abs/2601.00912 |
| 强制联网会改变读数 | Graphite："For prompts that never trigger search naturally, visibility values differ by 20 points on average." 建议报告每题联网率 | graphite.io/five-percent/research/do-not-force-search-prompt-tracking（2026-08-20） |
| 不报单次排名，只报出现率和区间 | SparkToro：同一品牌名单重复 <1/100、同顺序约 1/1000；Graphite：每题 10 次可见度平均误差约 5.6 个点 | sparktoro.com（2026-01-27）；graphite.io/five-percent/research/demystifying-randomness-in-ai（2026-04-14） |
| 先修准确性 | Seer：先建品牌事实表，10 道测试题有一道答错就先修 | seerinteractive.com/insights/stop-chasing-ai-rankings-before-you-fix-how-llms-see-your-brand（2026-05-19） |
| 页面缺口 vs 答案缺口；第三方排序 | Ahrefs 工作流 page gap / answer gap；Peec gap score = 已提竞品数 × 被用次数（Forbes 9 × 3 = 27） | ahrefs.com/blog/ai-visibility-workflow/（2026-09-30）；peec.ai/blog/a-beginner-s-guide-to-brand-mention-gap-analysis-in-ai-search（2026-02-05） |
| 诊断可以以「不做」结束；五种决定；动作四要素；度量契约；五种结果 | Citation Labs §15–31 | 同第一行 |
| 相关度是被引主因，只改格式影响小 | SIGIR'26：25.2 万次受控对比，主题相关度和位置主导，"formatting-only edits have little impact"；Ahrefs：被引页面标题与提示词语义更接近（0.602 vs 0.484） | arxiv.org/abs/2605.25517；ahrefs.com/blog/why-chatgpt-cites-pages/ |

## 降级或不用的说法

| 说法 | 处理 | 依据 |
|---|---|---|
| 加 Schema 能提升已有页面引用 | 不作为提升动作 | Ahrefs 2026-05：1,885 页处理组对照 DiD，"no major uplift in citations on any platform" |
| llms.txt | 不用 | Ahrefs 2026-05：13.7 万域名，97% 的 llms.txt 零请求 |
| 多平台合成一个分 | 禁止 | Profound、Graphite、Go Fish、Citation Labs 一致 |
| 「Reddit 占 AI 引用 40%」 | 不用 | 该组数字合计 208%，不是引用份额；Ahrefs 测 ChatGPT 上 Reddit 被引率 1.93% |
| GEO 打分高就会被推荐 | 不用 | Discovery Gap：无相关 |
| 优化一次长期稳住 | 不用 | 引用集合同日重跑 Jaccard 0.32–0.43（C 文件 Schulte et al.） |

## 难度（第 8 节，2026-11-20 核验）

原文与核验记录在 `30-选Topic与生词/方案/优化难度-外部方法核验-20261120.md`。

| 规则 | 依据 | 出处 |
|---|---|---|
| 竞争难度看竞品强度和可得位置 | Semrush Topic Difficulty：Competitor strength（常被提及的品牌是否知名权威）+ Opportunity size（可得位置相对全站均值），只到主题层，公式不公开 | semrush.com/kb/1607-semrush-ai-visibility-data |
| 固定品牌与单一主导的门槛 | Kevin Indig（1,094 个主题、5 万多品牌的 ChatGPT 数据）：主导 = 5 道题里至少 4 道出现且份额领先第二名 ≥5 个点；主导者次月 90.4% 仍第一；换位时原领先中位数 1.3 点、保住时 2.9 点 | growth-memo.com/p/does-topical-authority-matter-in |
| 引用来源结构只解释怎么改，不定竞争难度 | Indig：最常被引的域名只有 20.8% 是最常被提及的品牌；Profound 按来源类型选站内或站外路径 | 同上；tryprofound.com/articles/ai-marketing-agents-outreach |
| 不合成一个难度分、不承诺涨幅 | Profound、Ahrefs、Writesonic、AirOps、Similarweb 都没有提示词或主题难度分；arXiv 2604.07585 把「稳定性指标能否反映优化效果」列为未来工作 | 核验文件 B 部分 |

第 8 节阈值（80%、50%、5 个点、轮换位 1 / 3、已进候选 20%、已达标 30%）里，80% 和 5 个点取自 Indig，30% 沿用诊断的 `mention_ok`，其余是 2026-11-20 用路拓（ChatGPT 7 次）、老虎 HK / SG（3 次试跑）三份数据定的起点。

## 第一版阈值的来历

`diagnose.py` 的 PARAMS 没有外部标准。`min_valid` 7 沿用正式基线每格 7 次；`hold_margin` 10 个点、`retr_low` 20%、`mention_ok` 30%、推荐占比 50% 是 2026-11-16 用路拓（ChatGPT 美国 7 次）和 Housebell（三平台新加坡 5 次）两份数据定的起点，积累客户后按诊断结果和人工复核的一致情况校准。
