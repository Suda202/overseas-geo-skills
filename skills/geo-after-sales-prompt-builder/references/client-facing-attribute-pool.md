# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 中国农业大学海外招生监测属性池, Bewinch 台式净饮机售后生词, Botslab NightVue NV900 售后监测主题与词表, and Piltwave 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Format: the Feishu Base template

The client confirmation piece is a Feishu Base copied from the template 《AI 搜索监测确认表（模板）》, kept in the same wiki space as 《售后生词规则》. Copy it once per client and per market/language, delete every 【示例】 row, and fill the 使用说明 doc's data-source placeholders with the sources actually used. Its tables carry the sections below: 品牌事实, 属性池, 买家原话 (the evidence log), 覆盖矩阵, 监测主题与问题, 竞品名单, 需要品牌方提供的数据. Links do the reconciliation: each Prompt links the Attributes it tests, its 覆盖切片 and its 买家原话 evidence; 承载题数 / 覆盖检查 on 属性池 and 已有题数 / 覆盖情况 on 覆盖矩阵 are formulas, so an uncarried P1/P2 or an under-covered slice shows up without manual checking. Use the 需品牌方确认 checkbox where a document would use orange highlighting. The sections below still define what each table must contain.

## Canonical Shape

Use the sections that fit the task; do not force all of them into a small update.

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

   Use `项目 | 内容 | 客户确认` or `项目 | 内容 | 品牌方补充与确认`. Do not rank brand facts.

4. **属性池【请核对】**

   Default columns:

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

   Before any answers are collected, set the initial priority from **importance × changeability**; current gap is `待测` until the baseline (the three conditions and their scales are in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*). `购买影响` is the importance reading; `业务重点` the brand party states counts as evidence for it. `相对竞品` and the gap type feed changeability: an `优势` or `持平` row whose facts are unpublished (证据缺口) is the cheapest win; a `劣势` row behind on the facts, or a consensus-locked direction, scores low.

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
   - Keep `Prompt Task` in internal planning. Show an optional `买家任务` column only if the customer needs to distinguish why candidate question groups exist; use plain labels such as 发现、比较、替代方案或验证可信度, never backend routing terminology.

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
