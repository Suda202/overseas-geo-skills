# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 中国农业大学海外招生监测属性池, Bewinch 台式净饮机售后生词, Botslab NightVue NV900 售后监测主题与词表, and Piltwave 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Format: the Feishu Base template

The client confirmation piece is a Feishu Base copied from the template 《AI 搜索监测确认表（模板）》, kept in the same wiki space as 《售后生词规则》. Copy it once per client and per market/language, delete every 【示例】 row, and fill the 使用说明 doc's data-source placeholders with the sources actually used. Use the 需品牌方确认 checkbox where a document would use orange highlighting. The sections below still define what each table must contain.

**Settled table set (PETKIT, 2026-10-14/15).** Six tables plus the 使用说明 doc, in this order (the template had a seventh, 监测主题, removed 2026-10-15):

| 表 | 一行是什么 | 要点 |
|---|---|---|
| 业务范围 | 一个可以单独确认的事实 | Replaces 品牌事实. Multi-valued facts get one row each (产品线（1）（2）…, 主要受众（1）…). No 「已核对」 rows: a fact we verified ourselves is either written here as fact or folded into the matching attribute's 备注 |
| 买家原话 | 一条买家说法 | The evidence log; see *买家原话* below |
| 提示词矩阵 | 一种买家处境下要测的一条属性 | Carries the attribute pool — **no separate 属性池 table**; see *提示词矩阵* below |
| 提示词库 | 一道提示词 | Links its 所属切片 (one 提示词矩阵 row) and its 证据 (买家原话 rows) |
| 竞品名单 | 一个竞品 | `品牌 | 官网 | 适用产品线（多选） | 说明 | 客户确认`; 说明 gives mention-based reasons only |
| 需要品牌方提供的数据 | 一项只有品牌方能拿到的数据 | Unchanged |

**No separate 监测主题 table.** 监测主题 is a single-select column on both 提示词矩阵 and 提示词库 (same option set); a Topic's purchase status (已采购 / 候选) is written once in 业务范围 as 监测主题（n） rows, and the ≥5 candidate / ≤10 formal counts are checked by filtering 提示词库. A topic table would only duplicate the name and need links kept in sync. Competitors carry 适用产品线, not 适用主题.

Customer-facing names: call the Prompts **提示词** (tables 提示词矩阵 / 提示词库, field 提示词); keep **监测主题** for Topics. Suda reversed the 2026-08 ban on 「提示词」 on 2026-10-14. Use one term throughout the Base and the 使用说明.

### 提示词矩阵

One row is **one buyer situation × one tested attribute**. Aleyda's matrix row is a coverage slice and the attribute is one of the slice's dimensions; Prompts are written per slice, not per attribute. That is why the attribute pool is folded in rather than linked: a separate attribute table is many-to-many with the slices, and the brand party has to cross-read two tables to confirm one judgement.

Columns, in view order:

`买家处境（主字段） | 产品线 | 监测主题 | 受众 | 旅程阶段 | 属性 | 购买影响 | 相对竞品 | 可改变性 | 优先级 | 已有问题 | 已有题数 | 还缺什么 | 备注 | 需品牌方确认 | 客户确认`

- **买家处境** is the primary field and carries the information of the row: who, at which step, worried about what. Write it out in full (「听说水泵容易坏，下单前想确认保几年」), never a keyword like 「保几年」. Do not use a formula slice ID as the primary field.
- **Rows.** Every situation × attribute pair that has Prompts is a row. Every attribute with no first-stage Prompt also gets one row (受众 「通用」, a situation written from its buyer problem, a judged 旅程阶段), with the reason at the start of 备注 — 「首期不配提示词：购买影响低，不决定买家选谁」 or 「…：能力缺口，发布内容改变不了 AI 的说法」. Do not add a separate 去向/缺口说明 column. Category-baseline Prompts sit on rows with an empty 属性.
- **受众** is a single select with the same option set as 买家原话. Use only real buyer groups. A journey state is not an audience — 「已在比较具体品牌」 is the 对比 stage, not a persona — so named-brand Prompts are filed by the group their wording names, and Prompts with no group condition are 「通用」. Audiences beyond the brand party's listed 主要受众 are added to 业务范围 as 主要受众 rows with 需品牌方确认 ticked.
- **旅程阶段** uses the eight stages below; there is no separate 买家任务 column.
- **购买影响** is judged **per situation**: the same attribute may be 高 for one audience and 中 for another. Raise to 高 when the row's audience buys the product for exactly this attribute and drops any option that fails it (多猫家庭 × 每只猫分开记录; 预算敏感 × 耗材成本). Lower to 中 on post-purchase troubleshooting and returns rows, and on generic alternatives rows where the attribute is not what decides.
- **相对竞品 / 可改变性** are judgements about the attribute itself: identical on every row of that attribute, because the priority formula reads them. The brand party may correct any one row; we write the change back to all of its rows when collecting.
- **还缺什么 / 备注 / 需品牌方确认** are written **only on the first row of each attribute**, so the brand party meets each question once. When a named fact-check Prompt needs the brand's standard answer (does feature X need a subscription, how long does the battery last), write that request into the attribute's 还缺什么 with 「点名题要用：…」 — do not tick 需品牌方确认 on the Prompt itself.
- **优先级** is a formula; the brand party never fills it:
  - 购买影响 高 3 / 中 2 / 低 1 × 可改变性 证据缺口 3 / 持平或无缺口 2.2 / 能力缺口 1.5;
  - **P1 only at 9 (高 × 证据缺口)**, above 4.3 P2, otherwise P3;
  - rows with an empty 属性 (category baseline) are fixed at P1 — they measure which brands AI lists with no condition, the base of natural visibility.
  - Check the distribution after filling: P1 must stay a short list. At PETKIT a 6.5 cut put 52 of 105 rows in P1 because 高 × 持平或无缺口 scores 6.6; moving the cut to 9 left 26.
- Drop: 覆盖切片 formulas, 计划题数 / 覆盖情况 (always 「已覆盖」 once rows are generated from the bank), 市场与语言 (one Base is one market), 业务优先级 (half importance, half an echo of attribute priority), 买方约束 (now inside 买家处境), and any column whose every row holds the same value.

### 旅程阶段：八段，三张表同一套

`发现 | 解决问题 | 评估 | 对比 | 替代方案 | 验证 | 交易 | 购后支持`

Use one stage column in 提示词矩阵, 提示词库 and 买家原话. Aleyda's shortlist step folds into 发现; category understanding and source discovery are not used for after-sales banks. The older five-stage labels map as 了解需求→发现, 比较方案→对比, 评估是否适合→评估, 准备购买→交易, 使用与续费→购后支持, but re-judge each quote by its content when converting: a 「how do I get rid of the smell」 post is 解决问题, a filtering condition such as 「must be stainless steel」 is 发现, a 「does it have a hidden monthly fee」 check is 验证. A row with no Prompt still gets a judged stage — never leave it blank.

### 买家原话

`输入编号 | 产品线 | 涉及品牌 | 来源类型 | 原话 | 中文意思 | 受众 | 旅程阶段 | 约束或场景 | 来源说明 | 来源链接 | 收集日期 | 证据可信度 | 引用它的问题`

- **涉及品牌** (multi-select) names the brand the quote is about; generic buying posts and search terms are 「未指明品牌」. A subreddit name is not a brand mention.
- **来源类型** is the real source — 社区 / 评价 / 搜索数据 (later 销售记录、客服记录、GSC、站内搜索 when the brand party supplies them). Never 「竞品评价」: whose product it is goes in 涉及品牌.
- **受众** uses the same single-select set as 提示词矩阵; who the poster owns (「PETKIT 用户」「LR 用户」) is not an audience.
- Marketplace summary tags (Amazon 「Customers say」) keep only the tag text in 原话, the product name in 来源说明, and a 中文意思 that names the brand.

### 提示词库

`编号 | 提示词 | 中文含义 | 产品线 | 监测主题（单选） | 库分层 | 旅程阶段 | 所属切片 | 买家问题与场景 | 证据 | AI 认知差距 | 提及率 | 需品牌方确认 | 客户确认`

- Sort the view by 编号.
- **AI 认知差距 and 提及率 exist only after the candidate baseline.** Judge AI 认知差距 per Prompt from that Prompt's own answer text (有缺口 / 无人讨论 / 无缺口). Until then every row is 「待基线」 and both columns are hidden in the view. Never push an attribute-level judgement or presales answers onto individual Prompts — Prompts under one attribute would all read the same however their wording differs, which is not data.
- **监测主题 names describe what the Topic holds.** A category Topic that also carries condition Prompts (safety, large cats, one app) is 「××选购条件」, not 「××品类」; a Topic whose Prompts span cost, reliability and upkeep is named for all three.

### Facts we can verify ourselves

Settle what the public layer can settle before asking the brand party — for example whether a model is still sold: check the official site's product pages, redirects and search, then the main marketplace, and write the result into 业务范围 without ticking 需品牌方确认. Ask the brand party only for what only it knows.

## Canonical Shape

The sections below define the content. In the Base they live as: 品牌事实 → 业务范围, 属性池 → the attribute columns of 提示词矩阵, 监测主题与问题 → 提示词库. Where a section below conflicts with *Settled table set*, the table set wins. Use the sections that fit the task; do not force all of them into a small update.

1. **Opening scope paragraph**
   - State the monitoring object, product/category scope, market/language, and entry scenario.
   - Ask the brand party to confirm three things: the attribute list, the buying impact, and whether the brand is advantaged/at parity/weak versus competitors.
   - Explain the confirmation convention: every table's `客户确认` column is write-what-to-change; blank means reviewed with no change.
   - **State where our data came from**, in two or three plain sentences, so the brand party can judge the evidence instead of taking the table on trust: which public sources we collected (搜索需求与相关搜索、哪些评价平台、哪些社区——写实际用到的站点名，不写方法论), which of the brand party's own materials we used (销售/客服记录、GSC 等——只列用过的), and which AI answers were already collected (售前诊断或候选基线，带采集时间). Name only sources actually used in this engagement — the full menu stays internal in [signal-sources.md](signal-sources.md). One line of boundary: 公开来源查不到的，已在表中标为「待确认」或「需品牌方提供」，不会当成品牌方没有。

2. **核对时从哪里判断**

   The internal team may use a market-coverage pass to check whether the pool
   misses a product line, audience, journey stage, constraint, competitor,
   local terminology, regulation, currency, trust signal or source ecosystem.
   Show the filled slices in the 覆盖矩阵 table: we draft it, and the brand
   party only reviews whether an important buyer situation is missing. Never
   turn it into a questionnaire the client fills from scratch.

   | 要确认的 | 内部看什么 | 外部看什么 |
   |---|---|---|
   | 属性清单全不全 | 销售、客服、售后、win/loss、续费/退换货、GSC/站内搜索：是否有反复出现但表里缺失的问题 | 买家社区、评论、论坛、竞品页面、规格表、媒体评测、AI 回答里的高频属性 |
   | 购买影响高不高 | 这条不解决，买家会不会不入围、不购买、不续费、退货或要求补证据 | 买家公开选购理由、放弃理由、搜索规模、媒体评测维度、竞品主推方向 |
   | 相对竞品是优势还是持平 | 品牌自己的实测、交付记录、案例、服务条款、价格和可引用证据 | 竞品公开证据、第三方评测、榜单、社区口碑、AI 答案层同主题表现 |

   Adapt the wording by buyer type:
   - **B2B:** first-party sales/procurement/contract/renewal records usually outweigh public evidence.
   - **B2C hardware/consumer:** public reviews, community language, ecommerce Q&A and third-party reviews may carry the buyer-language layer; internal returns, service tickets, warranty terms and test data remain crucial for relative-competitor judgement.
   - Public absence is **not** `无优势` — but it is also **not** `待确认` until the external comparison has actually been run: the answer layer first, then the competitors' own public pages (spec sheets, certification pages, service terms), then third-party material. **Absence on both sides is likewise not `持平`** — that is exactly the case to put to the client, who knows where its own number sits in the industry. `待确认` is reserved for what stays undetermined *after* that pass and the client has not yet answered; name the material that would settle it, and ask the brand party for it. A verdict reached by comparison is ours to defend, and the client's internal records then either confirm it or upgrade it.

3. **品牌事实【请核对】**

   Keep factual scope separate from ranked attributes. Typical rows:
   - 品牌 / 业务模式 / 品类 / 产品或服务范围
   - 目标客户、目标企业画像或核心人群
   - 市场与语言、切入场景、适用边界
   - 官方域名
   - 竞品或替代方案（only if the comparison set itself needs confirmation）

   Use `项目 | 内容 | 为什么重要 | 需品牌方确认 | 客户确认` (the Base's 业务范围). One fact per row; split multi-valued facts into numbered rows. Do not rank brand facts. Wording rules for these rows: describe AI performance as 推荐 / 提及 — never 首推、排第一、排首位 or a rank percentage, which the client-facing caliber does not use; competitor reasons cite mention rates only.

4. **属性池【请核对】**

   In the Base these are the attribute columns of 提示词矩阵 (see *提示词矩阵* above); the lists below define what each column means. For a document-format pool, default columns:

   `类别 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 还缺什么 | 备注 | 客户确认`

   Use a compact variant when evidence is simple:

   `类型 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 品牌方补充与确认`

   Column semantics:
   - `类别/类型`: readable grouping such as 品类、目标客户画像、痛点、使用场景、购买标准、产品能力、差异化、信任与合规、申请门槛、地域与市场、约束.
   - `属性`: the buyer decision focus AI should associate with the brand. Differentiators are rows in this table, not a separate section, Topic, or Tag.
   - `解决的买家问题`: plain buyer problem or selection risk. Keep it close to customer language.
   - `购买影响`: buyer-side impact, normally 高 / 中 / 低. Judge by “if unresolved, does the buyer drop or downgrade the brand?”, not by frequency alone.
   - `相对竞品`: the attribute's **real position in the industry** — 优势 / 持平 / 劣势 / 待确认. Judge it on the facts, not on whether they happen to be published (publication is the **gap type**, a separate axis). Compare against the leaders publicly **first**; where the public layer cannot settle it — the brand's own spec or internal capability — put the question to the client rather than guessing. Add a short evidence note.
   - `优先级`: our initial action priority, not the customer's vote and not the final optimization priority after baseline.
   - `还缺什么`: specific material needed from the brand party; omit or leave blank when no material is needed.
   - `备注`: evidence and caveats we found. Keep it factual and short. For factual attributes, also note where public sources conflict or AI answers state the fact wrongly or outdatedly (quote the wrong claim and its platform), so the brand party can confirm the right answer.
   - `客户确认`: write-what-to-change only.

   For multi-market work, add the market only when it changes the buyer
   decision or evidence context. Use the existing `类别/类型` and
   `市场/语言` facts, attribute, constraint, competitor, or Prompt columns;
   do not create one duplicated attribute row for every country merely to
   demonstrate coverage.

5. **Priority Rules**

   In the Base the tier is a formula on 提示词矩阵 (cuts in *提示词矩阵* above). Before any answers are collected, set the initial priority from **importance × changeability**; current gap is `待测` until the baseline (the three conditions and their scales are in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*). `购买影响` is the importance reading; `业务重点` the brand party states counts as evidence for it. `相对竞品` and the gap type feed changeability: an `优势` or `持平` row whose facts are unpublished (证据缺口) is the cheapest win; a `劣势` row behind on the facts, or a consensus-locked direction, scores low.

   Important constraints:
   - P1 can coexist with `持平`: for a new product or category gate, the first-stage problem may be "AI does not know we have this," not differentiation.
   - P3 rows remain visible so the brand party can disagree, but P3 attributes do **not** get first-batch Prompts.
   - Only P1/P2 attributes normally carry first-stage Discovery Prompts.
   - `待确认` means the evidence is missing, not that the attribute is weak.
   - Once the baseline has measured the current gap, re-rank with importance × current gap × changeability; do not backfill the current gap before collection.

6. **监测主题与问题 / 提示词【请核对】**

   Include this section when the customer needs to confirm candidate Prompts, not when the current task is attribute-only.

   Recommended columns:

   `市场 | 监测主题 | 买家问题（或客户问题与场景） | 监测问题（英文或当地语言） | 中文含义 | 标签/属性 | 客户确认`

   Compact variant:

   `监测主题 | 买家问题 | 监测问题（英文或当地语言） | 中文含义 | 客户确认`

   Rules:
   - No question numbering in the customer document; crawler numbers are unstable.
   - Discovery-first: first staged set is normally all non-branded Discovery.
   - Keep the buyer problem / customer scenario adjacent to the Prompt, so the brand party can judge whether the wording matches real buying situations.
   - P3 attributes should not appear as first-stage Prompt coverage.
   - Each Prompt's buyer problem must exist in the intent/attribute table, and every P1/P2 buyer problem intended for first stage must have at least one Prompt.
   - Topic counts may differ; do not add filler for visual balance.
   - Keep `Prompt Task` in internal planning. The customer sees it only as the eight-stage 旅程阶段 column; do not add a separate 买家任务 column next to it.

7. **竞品名单（请确认）**

   Add a separate section when competitor scope is unstable or customer-submitted competitors were replaced.

   `品牌 | 说明 | 客户确认`

   Explain each inclusion/exclusion by “same buying comparison set,” not by brand fame alone.

8. **需要品牌方提供的数据**

   Include this section whenever the attribute pool is still being built. List only the data the brand party alone can access, using the table in [signal-sources.md](signal-sources.md) → 客户提供什么 (`数据 | 必要性与怎么给 | 品牌方补充与确认`). Mark 销售与 CRM 记录 and 客服记录 as 必须给 and the platform data as 最好给; do not ask for public search data, reviews or community language — we collect those. Say in one line that personal and customer-company details will be removed before use and raw records stay internal.

9. **候选基线与锁词流程**

   If the document hands off to monitoring, state the staged process in four lines:
   1. 品牌方确认业务重点、事实边界和属性池。
   2. Candidate Prompts run 5 times per proposed platform (the candidate baseline), in one sitting or over several days; the same runs check fit, ambiguity, leading wording and duplication.
   3. The formal set — at most 10 Prompts per purchased Topic — is chosen by attribute priority, confirmed by the brand party, and version-locked.
   4. Unchanged formal Prompts keep their candidate-baseline readings as the Before baseline; reworded ones are rerun 5 times.

## Wording Rules

- Use `品牌方`, not `贵司` / `贵校`.
- Write the final document directly; do not mention “上一版”, “补充更正”, or internal revision traces.
- Keep methodology, word-frequency work, validation steps, and evidence-position mappings out of the customer document. Archive them internally.
- Mark uncertain claims as `待核`, `待确认`, `待验证`, or `品牌自述`; do not turn trade-press/self-declared claims into facts.
- Avoid merged cells in Feishu tables. Empty cells are safer when rows are inserted or deleted.
- If a number is visible only through JavaScript or non-static page rendering, note the source limitation before treating it as AI-readable evidence.
- The brand party corrects facts and priorities; we make the judgement. Do not ask them to write our reasoning for us (for example, “why buyers credit this advantage”).
