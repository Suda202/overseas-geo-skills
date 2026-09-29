# After-Sales GEO Prompt Rules

Source: the project's canonical rule document `售后生词规则` (Feishu, rev 100 as of 2026-09-24). This file expands it for skill execution; where the two differ, the rule document wins. It also adapts the representative-library guidance from Aleyda Solis for this project. An earlier document of the same name has been superseded and its body emptied — do not cite it. The client-facing intake spec is the separate 《AI 搜索监测问题确认说明》.

## Core Principle

`After-sales Prompt set = real signals + representative coverage + stable Topics + incremental Prompts + semantic maintenance`

**We are not a monitoring tool, and that changes the objective.** A tool's business is measurement coverage, so for it more Prompts is better. A brand's own instinct is "what do I look like to AI", and it leans to completeness for fear of missing. We sell delivery outcomes and must commit to results, so we prefer few and precise. When reading outside methodology, first separate which parts express the tool's stance from the parts that actually transfer to a service provider's stance.

售前做覆盖；售后找机会。新 Prompt should be justified by at least one of:

- an observed monitoring gap or low-visibility important business theme;
- a GSC/SEO query with relevant demand;
- repeated new language, attributes, scenarios, or buying standards in AI answers;
- a confirmed new product, market, USP, audience, or competitor;
- an industry trend or technology change.

Do not call a generated phrase “high frequency” without frequency evidence. For B2B brands, the strongest evidence is usually not public search volume alone: preserve anonymized sales, CRM, customer-success, support, review, and customer-interview language when available.

An Attribute is a buyer decision focus, not a product-attribute inventory. It
may describe a capability, scenario, customer pain, audience constraint,
procurement requirement, supply or service risk, or applicability boundary.
Treat a feature as an Attribute or Prompt condition only when the evidence
shows that buyers use it to decide, compare, manage risk, or determine fit.

Before naming individual Prompts, run the internal representative-coverage pass
described in [representative-library.md](representative-library.md). Check the
meaningful intersections of product/service line, buyer/persona, journey stage,
market/language, constraint, competitor/alternative set, and business
priority. Add local terminology, source ecosystem, regulation, currency, trust,
availability, and service expectations when they can change the answer. This
pass is for internal gap checking; it is not a customer-facing matrix or a
requirement to fill every combination.

Every new Prompt must pass three gates:

1. It has an evidence source or is explicitly marked as a hypothesis.
2. A recognizable buyer or user could naturally ask it.
3. It adds an independent candidate set, comparison dimension, preference,
   risk, or applicability judgment.

Failure of any gate means the idea stays in the evidence-gap or research log;
it is not added merely to equalize Topic counts.

Discovery-first handoff:

- Reuse public research and prior monitoring/history. Prepare researched context
  and a customer-confirmation document; presales may supply Discovery V1, and
  after-sales inherits and corrects it.
- Confirm current business priorities and factual/product/market boundaries with
  the customer before the after-sales trial. Approval of the final Prompt set
  comes separately, after trial and before version lock.
- Ask for real buyer intent and, when available, redacted sales, support,
  win/loss, CRM, and GSC evidence. Do not reduce this to checkboxes.
- Do not require a complete Attribute x Journey matrix before work starts. The
  customer confirms product scope, market/language, real scenarios, exclusions,
  and evidence gaps.
- Mark lifecycle explicitly as `hypothesis`, `customer_confirmed`, or `locked`.
  `after_sales_signal` can justify a hypothesis, but cannot make a set
  formal-ready without customer confirmation and a locked Prompt version.

## The Four Stages and What Each Can Conclude

The chain is continuous, but each stage answers exactly one question. **An earlier stage may only raise a hypothesis; it may not state a conclusion.** Moving a later conclusion forward is the most common error in this flow.

| Stage | The question it answers | What may be said here | What may NOT be said here |
|---|---|---|---|
| **Before the presales run** | What is worth monitoring? | Brand facts, demand signals, attribute pool, initial attribute priority, competitors, Topics, the first Prompt set | Whether AI has a cognitive gap — nothing has been collected yet |
| **Presales diagnostic run** | What might be wrong right now? | **Preliminary cognitive problem / opportunity hypothesis**: mentions, competitors, attribute cognition, accuracy, citations, recommendation reasons, content gaps | That a **stable** cognitive gap exists — AI answers fluctuate, so a single round only yields a suspicion |
| **After-sales 3-day baseline** | What is the initial before benchmark under the final locked set? | Three daily valid observations, initial differences between Topics and a provisional optimisation order | A claim that a gap is stable over time, or that optimisation worked |
| **Continuous monitoring** | Are the gaps persistent, and did optimisation improve them? | Same-question, same-condition, same-caliber window comparison; longitudinal evidence | A single-day comparison or immediate effect promises |

**One line: presales suggests the opportunity, the 3-day baseline fixes the initial benchmark, long-term comparable data tests persistence and improvement.**

### Priority is set in two passes, never fixed in one

| When | Basis | Nature of the result |
|---|---|---|
| **Before the presales run** | Does the customer care × does it affect purchase × does the brand truly have the capability × is it a strategic priority | **Theoretical priority** — demand and advantage only; no AI-gap data yet |
| **After the 3-day baseline** (or once a presales batch has measured the gap) | **Purchase impact × initial measured gap × optimisability** — three legs, multiplied | Operational priority for the next actions, explicitly provisional about persistence |

The second pass adds an **initial measured gap**, not a stable one. Presales cannot measure it before collection; three daily observations provide a reproducible starting point but still cannot separate short-term misses from a persistent gap. Confirm persistence through later comparable windows.

**The operational formula has three legs; `相对竞品` is not a fourth.** Attributes, and the monitoring Prompts that carry them, share it. Scale each leg: purchase impact 高 3 / 中 2 / 低 1; measured gap = 3 × (1 − the Topic's measured rate); optimisability 证据缺口 3.0 / 持平 or no gap 2.2 / 能力缺口 1.5. Set the tier cuts per engagement so P1 stays a short list, and **P1 always requires a Prompt that carries the Attribute** — an uncarried row cannot be P1 however it scores.

Why `相对竞品` is not multiplied in: the verdict is read off the public layer, so most `劣势` rows mean "the capability exists but is not published" — the same fact that makes optimisability high. Multiplying both counts it twice with opposite signs. In practice a four-leg formula ranks parity rows on top (the brand already matches competitors publicly yet still goes unmentioned, so the bottleneck is not content and the row is hard to move) and pushes evidence-gap rows down, although those are the fastest to move. **Competitive position enters inside optimisability instead**: ask whether publishing the missing material would actually bring the brand level with the leaders. If it would not — a competitor lists certifications per model while the brand can only publish a summary figure — score optimisability lower.

**Within one tier, order the work by how ready the material is.** Evidence-gap rows whose content already exists somewhere the answers read (a blog, a PDF, a sub-domain) and only needs moving onto the product page go first; rows that need new material from the brand party follow. This is an execution order inside the tier, not a further multiplier.

Therefore: **presales may rank candidate Topics; the after-sales baseline informs operational priority, but neither stage alone promises that an action will work.**

## Search-Demand Anchoring

Traditional Search Demand should anchor the parent Topic, while the brand’s differentiators become attributes and Query conditions:

`Search Demand -> Topic -> ICP / journey -> Attribute / USP -> AI Query`

For example, `corporate travel management`, `travel management company`, `business travel software`, and `travel policy` can validate parent demand. `APAC coverage`, `China Railway`, `local service`, `corporate rates`, `multi-market settlement`, and `policy automation` should normally be treated as attributes or scenarios under those Topics, not automatically promoted to independent Topics.

Search-volume tools may use different countries, databases, and keyword definitions. Use them to validate direction and relative demand only; never treat their figures as AI-monitoring volume or directly comparable exact numbers.

## Customer and Market Signals Before Product Features

**Signals are collected first; the Attribute Matrix is distilled from them.** Collecting Customer / Market Signals is the evidence stage — sales and CRM language, support and customer-success records, win/loss and churn reasons, review and community language, GSC/SEO queries, already-collected AI answers — and the attribute pass comes after, not before. Do not open by filling in an attribute list and then hunting for signals that confirm it.

The customer should help confirm what buyers actually ask, compare, worry about, and need to solve. The builder may organize and translate these inputs, but must not replace them with a feature-list-derived question bank.

**Weights follow the buyer type.** For B2B, first-party material — sales calls, support tickets, win/loss — is the highest-signal source, and public material is thin early; for consumer brands the inverse holds, and public material (reviews, community, prompt data) can nearly carry the analysis on its own. Public sources do double duty: the language is what buyers care about, and it is simultaneously how the web currently describes the brand, because AI reads the same corpus.

Keep these fields separate when available:

- customer role;
- customer problem or decision;
- customer wording;
- journey stage: problem recognition, solution discovery, supplier selection, capability verification, implementation, or ongoing use;
- scenario and constraints;
- importance/frequency;
- evidence source type.

GSC/SEO queries and AI answers are supporting signals. They are not automatically customer Prompts.

**Customer input is not "less is better" — swap the collection form, do not cut the information.** What shrinks is the customer's filling burden, never the context; cut the context and all that is left is generic `best X` questions. Sort requests into three tiers:

- **Must have (without it the work is wrong):** the target buyer's real intent, differentiators, what the business does not do, which scenarios are easier to win, and which unique assets the client holds.
- **Best to have:** finer buyer wording and scenario detail — the material that makes a Prompt sound natural instead of generic.
- **Collect ourselves:** official-site facts, who the competitors are and where they are strong, who currently owns the category in AI answers, and the category's naming variants.

Depth also varies by layer: business boundaries (product, market, ICP, competitors, differentiation) need the client to **confirm**; Attributes and Topics come from interviews; **Prompt generation depends on internal data** — that layer's real buyer language cannot be skipped. "We draft, the client ticks and deletes" solves the Topic layer, not the Prompt layer.

### The customer confirmation table

"Fill in whatever you like" is not a low bar — it is no bar, and clients freeze or free-associate. Give a fixed frame; lower the burden by choosing the right columns, not by removing them. For the actual customer-facing 属性池、监测主题与问题确认件, use [client-facing-attribute-pool.md](client-facing-attribute-pool.md) as the concrete document pattern: opening scope, 核对时从哪里判断, 品牌事实, 属性池, optional 监测主题与问题, optional 竞品名单, and 试跑与锁词流程. The canonical intake spec is the project's client-intake spec 《AI 搜索监测问题确认说明》 — follow it rather than re-inventing columns. Its settled shape is five client columns:

`目标客户 | 客户问题与场景 | 客户原话 | 客户旅程 | 业务重要程度`

**On the column name 客户问题与场景 (renamed 2026-09-22, was 客户意图).** The column holds the buyer's occasion and ask, which is a distilled **output** of the signal pass, not the signals themselves — the old name "客户意图" read as if it named the whole collection stage, and invited readers to treat it as a synonym for Customer / Market Signals. The column set in 《AI 搜索监测问题确认说明》 was renamed to match; that document is canonical for the client-facing frame.

**Delivered client documents are revised when the nomenclature changes** (decided 2026-09-22, superseding the earlier hold-and-reissue-only rule). A column name or a P-scale that a client has already read is a shared vocabulary, not a private one: leaving old documents on the old label while new ones use the new one splits that vocabulary and makes the client's own confirmation table disagree with what we send next. So when the canonical frame changes, sweep the delivered files too, and say what changed. Practical order: update the canonical document first, then the internal files, then the delivered client documents, so every artifact ends on one vocabulary.

- **业务重要程度 uses one ordered P-scale as defined in that document**, which already contains frequency — do not add a separate frequency column, and never use a middle grade as an "undecided" placeholder. The **attribute table carries its own P1–P3 with different semantics** (P1 = decides customer-set entry); the two scales must not be mixed.
- **客户旅程** is named exactly that (the purchase stages: 了解需求 / 比较方案 / 评估是否适合 / 准备购买 / 使用与续费); do not invent an alias like "提问场景" and then explain it means the journey.
- **客户原话 is best-effort, not a hard requirement** — in practice most clients cannot produce quotes, so a blank cell never blocks the intake. The column stays because of what a blank tells us: the intent is the induction, the quote is the evidence, and a row nobody can find a quote for drops to hypothesis grade and triggers our own verification (review mining, community language, support-log sampling) before it can back a formal Prompt. When the client does quote, it is "pick one representative sentence", not a transcript. Never fill this column ourselves with invented quotes.
- A scenario column was tried and removed — fold the situation into 客户问题与场景 instead; a standalone 限制条件 column was also dropped from the client table, since constraints are better elicited in conversation than as a form field.
- **The boundary: the client gives facts, we make judgements.** Any question that asks the client to reach our conclusion for us — why they lose deals, "how would buyers describe your advantage", "which advantages do buyers actually credit" — stays out of the client's list. But do not over-relieve either: frequency, priority, and constraints are the client's daily sales judgement, so those stay with the client.
- Keep the client's confirmation burden to what only they can answer. If a column has grown into a multi-part question, cut it to the one thing being confirmed — asking for more confirmation than "just the priority" is itself a failure.
- **Market does not follow the question**: market and language are fixed at project start, and a multi-market engagement gets one client table and monitoring snapshot per market. The internal coverage pass decides whether an intent is `shared_equivalent`, `localized`, `market_specific`, or `not_supported`; do not assume the same core intent, `intent_key`, competitor set, or answer ecosystem across countries. Localize question wording and record evidence for budget/currency, competitors, constraints, terminology, regulation, trust, availability, or service differences. Each market/language has its own version and baseline.
- Client-facing confirmation documents are written in Chinese, contain conclusions and answerable open items only, drop question numbering (the crawler uses the prompt text, not the number), and never include our intermediate process (methodology notes, word-frequency work, validation steps go to the internal archive file).

Rows we drafted from public research are marked as ours; the client corrects and supplements rather than filling from zero — and drafting first never makes the client's intent pass optional.

### The final deliverable table

The working output is one reconciled master table, not a separate attribute table plus a separate intent table. The customer-facing confirmation document may still show separate sections for readability (品牌事实, 属性池, 监测主题与问题) as specified in [client-facing-attribute-pool.md](client-facing-attribute-pool.md); before delivery, reconcile them back to the master relationship. Its reference shape:

`优先级 | 品牌属性 | 客户问题与场景 | Topic | Query | Query 类型 | 选择理由`

This shape is a reference, not a validation checklist — a deliverable is not wrong for arranging columns differently, only for violating the rules below. Do not add columns that carry the same information twice: attribute explanation and evidence live inside 选择理由 or the attribute pool's 备注/还缺什么 columns, so a separate 属性说明与证据 column is redundant. Column naming (Prompt vs Query, Chinese vs English headers) is free as long as one document uses one term consistently.

- **品牌事实 stays a separate table up front** (brand, domain, business model, category, ICP, target customer, geography, applicable boundary) — it is confirmed once for accuracy, then not revisited.
- **品牌属性 and 客户问题与场景 stay adjacent but are never merged.** The entire act of translation lives in the gap between them; merging them silently asserts "attribute = intent", which is the failure this section exists to prevent.
- **Reconcile the intent pass against the Prompt set in both directions before delivery.** Every P1/P2 intent must be carried by at least one Prompt, and every Prompt's intent must exist as a row in the client's intent table. The two drift apart easily — the intent table is usually drafted from impressions while the Prompts are derived from attributes, and nothing in the derivation catches the mismatch. Make the master table's intent column **quote the intent table verbatim** so an edit to one flows into the other, and run the reconciliation as an explicit step rather than by eye.
- **Every client-facing table carries a 客户确认 column, and its convention is write-what-to-change.** The client writes only in the rows that need a correction, a deletion, or an addition, and leaves every other cell blank — never an all-rows "confirmed" reply, and never a per-row 确认 that has to be filled in for the table to count as reviewed. Question numbering stays out of the client document entirely.
- **选择理由 carries answer-layer evidence only** — a fixed pattern such as "competitors are negatively mentioned on this theme (Stera 33%, Coway 0%), we are at zero" — never free-text reasoning, which gets pulled around by "the client says this matters".
- **P3 attributes stay visible in the attribute table but receive no Prompts.** Only P1/P2 attributes carry Prompts; verify this before delivery.
- A paraphrased row nobody can source is tagged **待验证** rather than quietly kept.
- Use empty cells rather than merged (rowspan) cells down a column, because the client edits the table in Feishu and merged cells misalign when rows are inserted or deleted.

### The consolidated master table

The end of the whole chain is one table. **The reference shape** — the reference shape only, per the note above:

`优先级 | 主题 | 主题类型 | 核心属性 | 限定属性 | 问题 | 来源依据 | 售前结果 | 3 天基线 | 是否正式优化`

**Keep the 售前结果 and 3 天基线 columns side by side.** They make the two-pass priority auditable: the latter supplies an initial reading rather than proof that a gap is stable.

**核心属性 and 限定属性 are two roles, not two trees.** The core attribute is the perception that makes the Topic worth watching on its own; the qualifiers are the pool attributes relevant to this Topic that change how a question is asked. Once an attribute is selected as a core attribute it stops also serving as a qualifier. Selecting the core attribute is the first layer; picking qualifiers is the second, and the second layer is a **filter, not a re-rank** — it asks only "is it relevant?" and "is it worth a share of the query budget?", and the same attribute may take different tiers in different Topics without the pool being re-sorted.

**限定属性 fall into four slots, named as in 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」**: 无限定条件 (no qualifier) / 目标用户 (target user) / 偏好标准 (preference criteria) / 约束 (constraint). Pain points belong under 偏好标准 — a dimension buyers weigh while comparing, not a fifth slot. Coverage and Depth Topics follow different combination rules and mixing them is an error: a Coverage Prompt carries no condition or at most one low-complexity main condition and must not combine slots, while a Depth Topic may compound two or more conditions that genuinely change the choice.

**「是否正式优化」 is filled by us after the baseline**, never by the client. The three-day result can justify an initial action with uncertainty recorded; it cannot certify a stable gap. Leave the column blank during presales rather than writing a placeholder.

**An attribute is promoted from qualifier to its own Depth Topic** when it would form an independent competitive situation: a materially different competitor set, a changed evaluation standard, or a wholly different content strategy. That is the same clustering test that governs Topic boundaries — competition set or evaluation standard differs, so split.

## Topic and Attribute Selection Criteria

Authoritative source for this section: the canonical rule document `售后生词规则` (§3 第三步, §4; Feishu rev 71 as of 2026-09-22). When this file and that rule document differ, the rule document wins.

Selection runs on one joint test, applied to Attributes and Topics alike: **demand × standing to win × deliverable, all three or nothing** (有需求 × 有资格赢 × 可交付，三者缺一即为废).

| Leg | Meaning | Who judges |
|---|---|---|
| Demand (有需求) | Buyers really ask it | The customer's buyer-intent work plus our own buyer evidence |
| Standing to win (有资格赢) | The direction is eligible to compete and we hold the corresponding assets | Us, from presales diagnostic data plus an asset inventory |
| Deliverable (可交付) | The corresponding action sits within 90-day control | Us |

Do not ask the customer to rank. **The resulting Attribute order becomes the candidate order for Topics.** A direction with demand but no standing to win cannot be promised; one that is winnable but not asked about is self-indulgent differentiation nobody queries.

**This joint test is the presales-stage form of the priority judgement, not the final result.** Before the presales run the basis is demand × standing to win × deliverable. **After the 3-day baseline the basis adds an initial measured gap and optimisability**; these observations may guide the next action but do not establish a stable cognitive gap. Compare later windows before claiming persistence or improvement. See *The Four Stages and What Each Can Conclude* above.

**How to judge "standing to win".** If a competitor's advantage in a direction rests on brand awareness or broad media consensus, it is not reversible in the short run. **Do not open a Topic for that direction.** A Topic carries Prompts, Prompts carry a measurement cost, and a direction nothing can move returns the same number every cycle — buying a baseline instrument that can never read differently is worse than not measuring it. Read the overall category position from the presales round instead. Directions whose competitor advantage does *not* rest on consensus are the battlefield that is movable within 90 days.

**Judge this per Attribute, not per Topic.** A Topic can be unmovable as a whole while individual Attributes inside it are fixable — an absent OEM page or an unpublished certification is an evidence gap that one page closes, even when the Topic's leaders are consensus-locked. When you drop a Topic, **re-home its Attributes one by one**: promote the movable ones into a surviving Topic, and for each one you leave behind record why. Deleting a Topic and letting its Attributes sit in the plan unmeasured is the failure this rule exists to prevent.

**Evidence hierarchy for that judgement — answer layer beats spec sheet.** Read the AI answers' sentiment matrix (which competitors are criticised on this theme, and whether we are clean) before comparing product specifications, and put market-convention web research last. A dimension where competitors have hardware parity can still be a battlefield if AI answers keep criticising them there; conversely, buyer-forum language that never enters AI answers is not monitoring evidence. Structural losses recorded in the answer layer do exclude a Prompt ("only structural evidence excludes; a single zero-mention never does"), and a dimension where we are the weaker party **does not get its own Topic** — let the category Prompts surface it.

**The answer layer may not exist — check before reading anything into its absence.** A sentiment matrix exists only if the presales run produced one *and* put the **discovery** questions into its sentiment sample scope. Two failure modes are both common, and neither is an anomaly: a rough presales pass runs visibility only and has no sentiment layer at all; and a run that marked only the branded evaluation question produces a self-portrait of the brand rather than a competitor matrix, so there are still no per-theme negatives to read. Verify which case you are in before treating the answer layer as evidence.

When the matrix is absent, do **not** report the emptiness as a finding that competitors are clean. Fall back to the next evidence layer — product specifications, our own asset inventory, external research on who leads the category — mark the standing-to-win judgement as **provisional**, and say so in the deliverable. Record the gap as a process fix for the next presales run rather than as a blocker for this one.

**When several brands must be judged, keep the theme boundaries fixed across the run** so a later matrix stays comparable to the first one.

**When no theme shows a competitor negative.** A first pass can come back with competitors clean on every theme — roundup-style AI answers praise rather than criticise, so this is common and is **not** proof that no opening exists. It does mean no theme has a *demonstrated* opening yet. Do not quietly keep the optimisation labels on the Themes while the evidence says nothing was found; state it in the deliverable, hold the labels as provisional, and plan a second run of the same matrix immediately after the baseline so the judgement is longitudinal rather than a single snapshot. Also note the counter-explanation in the deliverable: an absence of negatives may be a property of the answer format rather than of the market.

**When the client asks for the head term they cannot win** ("rank #1 on <broad category> recommendation"): do not drop the broad term and do not promise it. Keep exactly one broad category Topic as the baseline/diagnostic instrument, keep it light (roughly six Prompts), and put the real question budget into the narrow Topics where evidence shows the brand can win (eight to ten each). Explain the trade-off in the client's terms, not with our internal scoring.

**Differentiators are Attributes.** They are one row each in the decision-attribute table with their own priority — never a separate section, never a Topic, never a Tag. The "competitor cannot copy this" test decides **how a claim may be worded as a differentiator**, not whether a dimension earns a row: shared category requirements (compliance certification, integration, SLA) are legitimate Attributes and often decide the shortlist; they simply must not be sold as differentiators. A claim every major competitor can match — global inventory or price advantage, 24/7 multilingual support, "more advanced technology" — is either worded as the survivable part or recorded as parity. Trade-press or self-declared claims are labelled **品牌自述**, never asserted as fact, and gated on client confirmation. Attribute names must be legible in the client's own industry vocabulary — when the client says a name is unreadable, rename it rather than explaining it.

**Standing-to-win judgements are made against the actual category leaders, not only the frozen competitor list.** Treating the frozen list as the whole competitive set produces false confidence: the brand may look strong against the configured set while the real answer-layer winners are elsewhere. Use the frozen list for Prompt construction and reporting consistency, but judge winnability against whoever actually leads the category's AI answers.

**The per-attribute relative-competitor verdict is researched, not requested.** Every P1, and every P2 that carries Prompts, is judged by actually comparing our public position against that product line's leaders on that attribute — answer layer first, then the competitors' own public pages (spec sheets, certification pages, service terms), then third-party material. Run it product line by product line: the comparison set is not the same set across lines.

**Where the engagement already has collected answers, read the set off the answer layer** — whichever brands actually lead that product line's discovery answers. The presales competitor-research step exists for the **pre-data** case, before anything has been collected; once data exists it is superseded, and a frozen list carried forward from before the run is a hypothesis to re-check rather than a given. Where no answers exist yet, fall back to it. This is **not** `automatic competitor discovery` — here the set is given and making the comparison is ours.

`待确认` therefore means **we looked and the public layer genuinely cannot settle it** — a QC agreement, an internal test report, a privately held warranty clause — never "nobody handed us a number". Always name the material that would settle it. A column that comes back mostly `待确认` is a research gap, not a finding: before shipping it, check whether the comparison was actually run.

While judging, split the gap and state which applies: **evidence gap** (the capability exists but is not published — the fix is a page) versus **capability gap** (the capability is absent — the fix is investment). That split is the most actionable line in the document and it is invisible from the verdict alone.

**The category observation Topic doubles as a diagnostic.** Research suggests roughly 15% of categories already have a clear winner. Where one exists, put the effort into the depth Topics and keep the category Topic as the baseline instrument; where none exists, the category Topic is itself a winnable battlefield. It has to be measured either way, so the extra judgement costs almost nothing.

### How Attributes Are Derived

Topic and Prompt both grow out of Attributes, so the rule document §3 derives and ranks them **before** Topics and Prompts are named, in four steps. When running an after-sales engagement, follow that order rather than brainstorming Topic names first.

**Supply side and demand side are different objects — never generate the word list twice.** An Attribute is a **decision focus**: anything a buyer weights when choosing, on either side of the table. The rule document §3's twelve-category sweep is the class list, and it already spans both sides:

| Side | Classes |
|---|---|
| Brand side — how AI should perceive the brand | Category, Feature, Differentiator, Integration, Trust & Security |
| Buyer side — which buyer the brand is for, and in what situation | Industry & Vertical, Buyer Persona / ICP, Pain Point, Use Case, Evaluation Criteria, Geography & Market, Constraint |

**Customer intent is not a third class of Attribute.** An intent is the occasion on which a buyer asks ("we have offices in several Asian countries and do not want a supplier per country") — the demand side, organised by the journey labels — not a perception to own. Both degrade into "topic words" if written carelessly, which is where apparent duplication comes from (`Asian market coverage` as attribute vs `find a travel platform with good Asian coverage` as intent). Attributes decide **which perception to optimise**; intents decide **in which user question to fight for that perception**. Do not narrow the class list into a supply-side capability inventory, and do not merge the two objects into one column. The derivation stays stepwise — attribute pass, then intent pass, then cross-map — and each input pass stays light; what collapses into one artifact is the **deliverable**: the client sees and confirms a single joint table `journey → intent → linked attribute(s) → Topic → Query → priority`, because two heavyweight standalone tables are unreadable and unfillable for them.

**Step 1 — sweep twelve categories as a gap check, not a checklist.** Sweep Category / Industry & Vertical / Buyer Persona / Pain Point / Use Case / Evaluation Criteria / Differentiator / Feature / Integration / Constraint / Geography & Market / Trust & Security to find what is missing. Never fill them mechanically, and never let the skeleton stand in for the category-specific attributes that actually decide the choice — in B2B, Evaluation Criteria, Integration and Trust & Security are exactly the classes general knowledge cannot supply and the category must.

**Step 2 — collect the category-specific attributes from three sources.**

| Source | What to take | Who |
|---|---|---|
| The client's own procurement standard | RFP / tender scorecards received, the evaluation items sales is asked about most. B2B procurement already scores by domain, so this is the most accurate first-hand source. | Client provides |
| Competitor comparison and feature pages | Competitors have already summarised this category's evaluation dimensions for the market. | We research |
| Already-collected AI answers | Cluster the attribute words AI uses when describing brands in this category — "the attribute set AI is actually using". Only we can do this layer, and it is the cheapest. | Ours alone |

**Step 3 — B2B and B2C are not one attribute set.** The required categories, the wording, and the evidence lines all differ; mixing them yields a set that fits nobody — see the rule document §3 for the full comparison table (skeleton classes seen as required, how attributes are worded, data line, and when a single B2B/B2C set is acceptable).

**Step 3.5 — validate that someone actually asks it, before locking.** An attribute that hits the priority test is still only a hypothesis about the market until a first-party source says buyers raise it. Check each P1, and each P2 that will carry Prompts, against our available sources: GSC/SEO queries, sales and CRM language, support tickets, win/loss and churn reasons, review and community language, already-collected AI answers. Traditional search volume is a directional signal, never proof of AI-side demand, and a long-tail or regional Query may legitimately have little volume while inheriting demand from its parent Topic. Where no first-party source exists, the row is marked **hypothesis grade** — it may still ship in a Discovery-first set, but it cannot be described as frequent, commonly asked, or high-demand. We have no AI prompt-volume data source; do not invent one, and do not present a tool's keyword figure as AI-answer volume.

**On the AI-Gap leg of the priority test (fill it only when it has been measured).** Profound's third question — is there distance between what AI says and what we want it to say — is the leg we most often cannot answer at generation time, because a first set is designed before any answer exists. Do not fill it from intuition: an unfilled Gap is marked `待测`, never "AI doesn't know us". **But the engagement usually runs two rounds** — presales collects a first answer batch, so after-sales often *does* have measured Gap data. When it exists, fill it with the measured value and cite the sample ("APAC coverage mentioned in 33.3% of 15 valid discovery prompts, the other 7 topics at 0"), and keep it to the answer layer: a sales hunch or "the client says this matters" is not Gap evidence. **Where another company shares or nearly shares the brand's name, measure the gap on the brand's own-domain citation rate, not on name mentions**: a name appearing in the answer does not show the AI read the brand's content, and some of those answers cite the other company's pages under the brand's name.

**Step 4 — cross-map intents × attributes and filter by the joint test; the surviving order becomes the Topic candidate order.** Organise intents by the canonical five journey stages (`了解需求 / 比较方案 / 评估是否适合 / 准备购买 / 使用与续费` — the confirmation doc's labels; older namings like 了解产品/确认功能 are retired), map each to the attribute(s) that answer it, and keep only cells passing demand × standing to win × deliverable. An intent with no attribute behind it is low priority; an attribute no intent reaches is self-indulgent differentiation nobody queries. Demand is judged from the client's signal pass plus our own buyer evidence; the other two by us. Do not ask the customer to rank.

Attributes are also not kept as a separate library: they exist to build and explain Topics, so do not create one Topic per Attribute or promote a brand's self-described selling point into a buyer need. Keep generation-time attributes (which design and explain the Prompts) apart from post-analysis attributes clustered out of AI answers; the two can be linked but never share one meaning. We draft the attribute list by category and the client only adds, deletes, and corrects — a dimension the client did not raise but the procurement RFP plainly evaluates is raised by us for confirmation. If interviews are used, run When / Where / While / with What / Why / how-feeling / with-Whom and converge on the 5–8 attributes that genuinely affect the choice.

## Topic Rule

A Topic is a business theme worth tracking with an independent long-term metric.
The recommended first-stage shape is one category observation Topic plus two
same-product buying-scenario Topics; two Topics are acceptable when the product
line or evidence is genuinely narrow. Category observation is not a randomized
causal control and may be optimized when it is a real opportunity. It is also
not the `Category Awareness` intent.

For a customer-confirmed, locked, or formal Topic, require at least five
independent Prompts. Candidate/hypothesis Topics may temporarily have fewer,
but must be marked for evidence completion. Do not fill them with synonymous
rewrites: merge them, keep them as Tags, or report the evidence gap if five
independent intents cannot be supported. Prompt counts are deliberately
variable and Topic counts may differ. The project's first-stage shape is three
Topics — one category observation Topic plus two same-product buying-scenario
Topics — with a lower bound of five Prompts per Topic, normally 5–10, 8 as the
internal recommendation, and **no permanent upper cap**. Ten or more Prompts in
one Topic requires a stated reason (ten or more genuinely distinct important
intents; otherwise split the Topic). Weight the counts, do not equalise them: the
category observation Topic carries roughly six Prompts, while the
buying-scenario Topics the brand can win carry eight to ten each. A mature set
grows only when evidence supports independent long-term value.

A **broad Topic must be resolved into its facets**, and the facet mix written
down. A label like `APAC coverage` can hide five different buyer needs
(coverage breadth, cross-market itineraries, local content and low-cost
carriers, local-language service, multi-supplier data consolidation) — that is
one Topic name with five Prompts each serving a different need, so no facet is
actually covered. Name the facets, mark which facet each Prompt serves, and put
the Prompt weight on the facet where the brand's advantage meets buyer demand.
Do not spread Prompts evenly across facets for visual balance.

Topic names should be short and scannable, normally one to four English words. Examples:

- `Corporate Travel Management`
- `Airline Content`
- `Hotel Content`
- `Customer Service`
- `Booking Technology`
- `Expense & Payment`
- `Sustainability`

Do not encode a whole use case, audience, feature list, or region into the Topic name. Put those in the Prompt and Tags.

## Prompt Priorities

1. **Discovery:** natural non-branded candidate discovery and the main visibility opportunity.
2. **Evaluation:** a specific attribute, scenario, or decision standard that can guide content/action.
3. **Competitor:** one-to-one comparison only when a real competitive opportunity justifies it.
4. **Category Awareness:** low-frequency observation; refresh only for a new concept, trend, or changed buying standard.

The six intents are `Discovery`, `Competitor`, `Evaluation`, `Verification`,
`Category Awareness`, and `Accuracy`. Capability validation is an alias of
`Verification`, not a seventh intent. Verification and Accuracy are not default
after-sales Prompts: use them only with an explicit evidence contract.

**Which monitoring task each intent carries** — the intent list is ours, and it covers the same ground as the standard AEO prompt taxonomy. Read it as task coverage, not as a quota:

| Our intent | Task it carries | Success shape |
|---|---|---|
| Discovery | Does AI recommend the brand when a buyer explores the category | Returns a provider/platform list; needs a candidate-noun trigger |
| Competitor | Whom AI picks in a head-to-head | Returns a verdict, not a both-sides answer; needs a use case and a comparison ask |
| Evaluation | How AI appraises the brand or a competitor on a stated scope | Returns an appraisal; this is where sentiment is read per attribute |
| Verification | Whether AI even knows the brand holds a specific capability | Yes/No/Unknown per attribute; distinguishes a comprehension gap from a trust gap |
| Accuracy | Whether what AI says about the brand is factually correct | Needs official sources; not part of routine expansion |
| Category Awareness | How AI frames the category itself — table stakes and evaluation criteria | Category-level read; never carries target-brand visibility |

Verification and Profound's `Validation` are the same task under two names — keep our label, and do not read a "no" there as a visibility failure. Our Evaluation covers both Profound's `Sentiment` and its appraisal prompts; Category Awareness covers its `Market Perception`.

The first staged set is all `Discovery`: lock the Discovery group first, then add
Competitor, Evaluation, Verification, Category Awareness, or Accuracy as the
situation requires, each only when its separate business question and evidence
contract are present; none has a fixed quota. The Feishu rule's reference
distribution — six to eight Discovery Prompts out of about ten, with the
remaining two to four spread across the other intents by actual need — describes
that later allocation, not a first-set quota, and never justifies adding a type
to fill a slot.

## Discovery Quality

Discovery is the formal visibility population. It must be a natural commercial recommendation or selection question:

- no target brand or competitor names;
- category is recognizable;
- one main decision;
- enough buyer context to produce named providers or platforms;
- no pure methodology, trend, or educational question unless a separate problem-awareness track is explicitly requested;
- **match the real distribution of user wording, and do not default to "concise"**: a large share of delegated, long-form questions is expected (measured user prompts run to a ~20-word median, delegated questions about 37%, keyword-style only about 3%). Mix short direct questions with questions carrying a buyer, scenario, or constraint, in roughly the proportions real users produce;
- no redundant containment wording, such as a broad region plus a subregion that is already included;
- classify every qualified Prompt into one of the four condition slots used by 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」, and keep those names: **无限定条件** (no qualifier), **目标用户** (target user), **偏好标准** (preference criteria), **约束** (constraint). Pain points sit under 偏好标准 — they are a dimension buyers weigh while comparing, not a fifth slot. Retain a mix across the four whenever the condition changes the expected candidate set.

Topic-level rules:

- each candidate Topic has at least one natural no-qualifier (无限定条件) Discovery Prompt;
- **Coverage and Depth follow different combination rules, and mixing them is an error.** A Coverage (宽泛) Topic's Prompt carries no condition or at most ONE low-complexity main condition, and must NOT combine target user, preference criteria, and constraint. A Depth (细分) Topic's Prompt may carry one condition or several, and the group must systematically contain meaningful compound Prompts — the same question joined with two or more conditions that genuinely change the choice. Not every Prompt needs to compound, there is no fixed sub-quota, and stacking conditions to look thorough is prohibited;
- compound conditions are allowed for a genuinely narrow scenario, but must change the candidate set or recommendation;
- do not create near-duplicate Prompts by changing only adjectives, word order, or “best/top/recommended”.
- dedupe by **purchase decision**, not by wording. Two Prompts that resolve the
  same decision (same candidate set, same comparison dimension, same condition
  that changes the answer) are one Prompt, however differently they read; only a
  change of buyer, region, scenario, or decision stage makes a new one. Normalised
  text uniqueness only catches synonym and word-order rewrites, so near-equivalent
  phrasings must be merged on human review.
- stop expanding a Topic once its evidence-backed important decision focuses
  are covered; a longer list is not evidence of better monitoring.

**Natural visibility uses Discovery Prompts only.** Named-brand Evaluation,
Comparison, and Verification results are read separately and never enter the
natural-discovery statistic. Keep one identical wording when several brands must
be evaluated. A Discovery Prompt scoped to a specific attribute — "which
enterprise travel platforms have good customer support" — is still Discovery; a
specific attribute does not by itself make a Prompt an Evaluation.

## Trial, Baseline, and Optimization Groups

Run each candidate Prompt three to five times on each proposed platform before lock. Check the market coverage pass first, then category fit, answer-task fit,
ambiguity, leading wording, and semantic duplication. Do not select or reject a
Prompt because the target brand was or was not mentioned, and never retire an
existing Prompt on a single or zero mention — that corrupts the visibility
measurement. **"Can we win" is only one leg of the joint selection test — demand
× standing to win × deliverable — and must not be used alone** (see Topic and
Attribute Selection Criteria above). Judge it by the rule document's method: a
competitor advantage resting on brand awareness or broad media consensus is not
reversible in the short run, so treat that direction as baseline only; where the
advantage does not rest on consensus, expect to move it within 90 days. A single
or zero mention never enters this judgement.

When comparison is useful, a baseline observation group uses Discovery Prompts
sampled at the same cadence as its comparable group. It is not automatically a
causal control and does not need a fixed size. Do not confuse it with
low-frequency Category Awareness, and do not forbid optimizing the category
observation Topic.

Confirm the business scope before trial; after three valid trial runs per
Prompt/platform, the customer approves the final set and its version. Trial
answers do not count toward the formal baseline. Run that baseline on three
consecutive calendar days, once per Prompt/platform/day, under the same
questions, market, language, and collection configuration. Use only observed
valid samples; failures are not zeroes, and missing days cannot be glued into
a three-day window. Three days establishes an initial benchmark, not
statistical stability. This skill emits the plan; it does not execute crawling
unless explicitly requested.

An added, deleted, or reworded Prompt starts a new set version and a separate
three-day baseline for its affected market/group. Preserve IDs, evidence
references, and history, but do not concatenate old and new set-level windows.
Unchanged common Prompts remain comparable on their own. Select initial
optimization priorities using observed evidence plus confirmed advantage,
evidence availability, AI recommendation opportunity, and content
controllability; verify persistence in continued monitoring.

## Field Semantics

Every Prompt has:

- `Topic`: one stable business theme.
- `Region`: the market being monitored, such as `Global`, `United States`, or `Singapore`.
- `Intent`: one of the project’s six diagnostic intents: Discovery, Competitor, Evaluation, Verification, Category Awareness, or Accuracy.
- `Tags`: **optional, and kept short.** Leave it empty unless a tag carries a dimension the other fields do not — typically an attribute, a buyer role, or a use case. Do not repeat `Region`, `Intent`, or `Topic` in Tags, do not prefix a value with its field name (`属性:` / `Prompt Task:`), and use the bare name rather than a phrase.

## Maintenance

After-sales is a dynamic set:

- add when the Prompt introduces a new user need, competition context, decision dimension, product/region/USP, or useful analysis view;
- merge when two Prompts produce the same buyer need and expected candidate set;
- retire only when duplicated, obsolete, or no longer business-relevant. Do not
  retire only because of zero target-brand mentions or inconvenient outcomes.

Core and experimental groups are qualitative operating categories; do not set a
fixed percentage split. The goal is a smaller, more useful monitoring set, not
perpetual growth.

Use three operating roles:

- `core`: stable, high-priority Prompts used for recurring comparison;
- `experimental`: new market, audience, constraint, competitor or emerging
  intent under evaluation;
- `monitoring`: representation, reputation, risk, compliance or competitor
  change surveillance.

Keep the role and prompt group in the internal metadata. Do not mix an
experimental market hypothesis into the core baseline until its local evidence,
trial and customer confirmation are complete.

Review affected groups when a product, market, pricing model, regulation or
major competitor changes. Active commercial and representation groups may
need monthly review; market terminology, substitutes and source ecosystems
quarterly; the full attribute pool and library every 6-12 months. These
intervals trigger review, not automatic Prompt replacement or collection.
Retain unchanged core Prompts for comparability.
