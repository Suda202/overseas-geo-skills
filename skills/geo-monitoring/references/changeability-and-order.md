# 可改变性与优化顺序

这两条是判断规则，原写在基线报告文档里（2026-11-20 基线报告并进 geo-presales-report-builder 后单独成文）。基线 HTML 不展示它们；脚本是 `scripts/changeability_domains.py`，缺口诊断（`geo-gap-diagnosis`）沿用这里的优化顺序。

## 可改变性（默认只优化官网，Suda 2026-11-13）

回答的是「只改官网，能不能改变这道题的答案」。第三方信源要另外加钱、社区也不好做，所以默认按只优化官网判。`scripts/changeability_domains.py` 全自动判，不用人工打开页面；只用于不点名本品的题（发现、替代、问题解决），评估、对比、验证、交易、售后输出「不适用」。按顺序判，命中即定档：

| 顺序 | 判什么 | 结果 |
|---|---|---|
| 1 | 品类错位（只用于发现、替代）：同类品牌（含本品）被提到的回答不到 20%，7 次里最多 1 次 | 低 |
| 2 | 硬规格劣势：题目的主约束在约束条件表里「相对竞品」是明显劣势 | 低 |
| 3 | 有引用的回答不到 4 条 | 不判，标「引用样本不足」 |
| 4 | 官网差距：有引用的回答里，某家同类竞品官网被引的比例比本品高 40 个百分点以上，且多出至少 3 条回答 | 高 |
| 5 | 第三方主导：有引用的回答里，引了任一同类厂商官网（含本品）的不到 40% | 低；品牌方已购第三方信源时（`--third-party`）媒体、社区为主的改判中，机构为主仍是低 |
| 6 | 其余：厂商官网常被引，本品和竞品差距不到门槛 | 中 |

- 分母只算有引用的回答：ChatGPT 有不少回答不联网、不带引用，算进去会把题误判成第三方主导。
- 「同类品牌」在品牌词表里标：目标品牌和配置竞品默认同类，开放品牌要写 `same_category: true` 才算；别的品类厂商（导航仪之于 CarPlay 屏）写 `false`。同类品牌的官网域名就是比差距用的竞品官网。
- 有效回答不到 7 条（3 次试跑）只算预判：「有引用的回答 4 条」「多出 3 条」两个次数门槛按回答数等比例缩，最少 2 条（3 次试跑就是 2 条、2 条）；7 次基线跑完再定正式档。
- 可改变性只回答能不能改，不回答值不值得做：提及率已经很高的题也可能判高。
- 每题输出被引最多的竞品页面网址，作为改官网的参照；不参与定档。
- 阈值（20%、40 个百分点、3 条、40%、4 条）都是参数，按路拓一个客户定的，多积累客户后再校准。

## 优化顺序 (Suda 2026-10-23)

The five competition patterns moved here from the client Base, where the seven-value 竞争格局 field was replaced by 信源壁垒 and, on 2026-10-28, by the per-Prompt 可改变性 (高 / 中 / 低; rules in「可改变性」above). They are computed per formal Prompt from the formal baseline (7 runs per query × platform × country × language), pooled across platforms, and used to order optimisation work. They never change the selection 优先级 (提示词库 优先级, prefilled from the matrix row).

Applies to Discovery and Alternatives Prompts only; named-brand types put the brand in the question and would always read as mentioned. Let t = the brand's mention rate on the Prompt and L = the highest rate among the other brands named as candidates:

| Pattern | How to tell | Place in the optimisation order |
|---|---|---|
| 部分出现仍落后 | t > 20% and L − t ≥ 30 points | First within the tier — closest to winning |
| 竞品领先（引用以竞品官网为主） | t ≤ 20%, L − t ≥ 30 points, citations mostly competitor official pages | Next — write the equivalent on the brand's own site |
| 竞品领先（引用以第三方为主） | Same, citations mostly review sites, communities, trade media | Next — reachable, but off-site work takes longer |
| 无品牌点名 | t ≤ 20% and L − t < 30 points | Next — an open slot; first confirm the wording asks for candidates |
| 已打平或领先 | t > 20% and L − t < 30 points | Last — the job is to hold; monitoring continues unchanged |
| 来源追不上 | No executable source intervention has been identified after reviewing pages, evidence and available resources | Record the source constraints and feasible actions for manual review; no automatic tier change |

Order: tier (提示词库 提示词优先级 — 高 / 中 / 低; 优先级 or P1 / P2 / P3 in older Bases — inherited from business importance) → pattern as above → 相对竞品 (优势 before 持平; judged after the baseline for Prompts with a gap — the client Base has no attribute pool since 2026-11-04; leave it out of the order where not yet judged). Source structure describes possible interventions and evidence gaps. Citation shares alone do not establish changeability or alter the selection tier. The thresholds (20%, 30 points) were set on Housebell's 15 answers per Prompt; with 7 runs per cell a 50% reading carries roughly ±37 points on a single platform and about ±19 pooled over four platforms (1.96 × √(p(1−p)/n)), so patterns are assigned on the pooled reading only — never per platform — and a Prompt within the pooled margin of a threshold is reported with both neighbouring patterns rather than forced into one. Write the pattern and the order into the optimisation work list (geo-gap-diagnosis), one value per Prompt, 「第 N 档（提示词优先级 · pattern · 相对竞品）」, one line per market. The baseline HTML does not show it, the client Base has no 优化顺序 column (removed 2026-11-01), and the selection 提示词优先级 is never rewritten.

