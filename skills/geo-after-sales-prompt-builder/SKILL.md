---
name: geo-after-sales-prompt-builder
description: Build or maintain evidence-backed after-sales GEO monitoring Topics and Prompts, including Discovery-first handoff, evidence correction, versioning, and collection plans. Use for ongoing monitoring-set expansion, refinement, deduplication, and retirement; do not use for presales coverage, crawler execution unless explicitly requested, metric calculation, report writing, or automatic competitor discovery.
metadata:
  author: Overseas GEO Project
  version: "1.10.0"
---

# GEO After-Sales Prompt Builder

## Purpose

售后生词不是重新生成一套售前题库，而是基于已有监测结果和真实业务变化，持续发现、补充、合并和淘汰高价值监测 Prompt。目标是发现新的可优化机会和细分分析视角，而不是把覆盖面机械做满。

Use this skill when the user asks to create, revise, expand, prune, organize, or schedule an after-sales GEO monitoring Prompt set. Read [after-sales-rules.md](references/after-sales-rules.md) before designing Topics or Prompt quotas. Read [representative-library.md](references/representative-library.md) when the task involves market/language coverage, attribute-pool gap checking, Prompt groups, localization, or sampling protocol. Read [client-facing-attribute-pool.md](references/client-facing-attribute-pool.md) when producing or updating an 属性池、对客确认件、客户确认表、监测主题与问题确认文档, or any customer-facing handoff. Read [output-contract.md](references/output-contract.md) when producing JSON, CSV, cadence, or audit artifacts.

## Operating Boundary

- **After-sales:** start from existing data, real queries, AI answers, business changes, and content opportunities; preserve valuable existing Prompts and explain additions/removals.
- **Presales:** use `geo-presales-prompt-builder` for initial diagnostic coverage, Case-derived Attribute x Topic planning, and its fixed contract.
- **Out of scope:** metric calculation, crawler collection, sentiment judging, report conclusions, and competitor discovery or freezing. This skill emits the trial/baseline collection plan; actual execution is delegated to the corresponding collection skill only when explicitly requested.
- A frozen competitor list may be consumed for comparison Prompts, but this skill must not silently select, replace, or verify competitors.

## Required Inputs

Accept the inputs available in the current task; do not invent a parallel business schema.

- Existing monitoring Prompt set and its Topics, if available.
- Brand/product Case and the official domain.
- At least one real signal: existing monitoring results, GSC/SEO query data, AI-answer gaps, sales/customer language, customer-review language, CRM/customer-success findings, a new product/market/USP/audience, or an industry change.
- Region and language for the monitoring run.
- Frozen competitors and their Topic boundaries when competitor Prompts are requested.
- Reusable researched context and a customer-confirmation document, when
  available; otherwise create a staged handoff artifact before formal lock.

Presales may leave the researched Case as a pending-confirmation V1. Before the
after-sales trial, the customer must confirm the current business priority,
product/buyer/market scope, and factual and exclusion boundaries. This is
separate from approving the final Prompt set after the trial; record both
decisions. If presales confirmation already exists, review changes rather than
asking the customer to start over.

If the user only provides a product brief with no after-sales signal, build a
clearly labelled first hypothesis set and list the evidence that still needs
confirmation. It may support Discovery/Diagnostic exploration, but is not
formal-baseline-ready. Do not present LLM-invented expansions as high-frequency
demand.

## Customer and Market Signals

After-sales Prompt work should start from **signal collection**, not from a product feature list and not from a finished attribute list. Signals are what we gather; the Attribute Matrix is what we distil out of them. Ask for or use, when available:

- sales and CRM language, including why customers bought, did not buy, switched, renewed, or churned;
- customer-support and customer-success questions, misunderstandings, adoption barriers, and recurring service concerns;
- customer-review and public-discussion language;
- GSC/SEO queries as demand clues, never as Prompts copied without interpretation;
- customer role, business scenario, decision stage, constraints, and the decision or risk the question is trying to resolve.

The customer must supply a **signal pass** of their own: based on their sales, support, win/loss, and churn records, what their target buyers actually ask, worry about, and want, in any framing they like (journey, persona, scenario, pain), plus the raw material behind it — FAQs, sales or support records, win/loss reasons, GSC/PPC/site-search data. This one is **must have**. Prefer queries that are newly appearing, already exposed but underperforming, or adjacent to existing content yet uncovered by the bank.

**Signals come first; attributes are the distilled result.** The order is collect signals → distil the Attribute Matrix (brand-side and buyer-side classes together) → then name Topics and Prompts. Do not start by filling in an attribute list and treating the signals as confirmation of it. **Weights follow the buyer type**: for B2B, first-party material (calls, tickets, win/loss) is the highest-signal source; for consumer brands the inverse holds and public material (reviews, Reddit, prompt data) can nearly carry the analysis on its own. Public sources do double duty — buyers' language and how the web currently describes the brand are the same corpus to AI.

**Customer input is not "less is better" — swap the collection form, do not cut the information.** What shrinks is the customer's filling burden, never the context; cut the context and all that remains is generic `best X` questions. Sort requests into three tiers:

- **Must have:** the target buyer's real intent, differentiators, what the business does not do, which scenarios are easier to win, and which unique assets the client holds.
- **Best to have:** finer buyer wording and scenario detail — the material that makes a Prompt sound natural instead of generic.
- **Collect ourselves:** official-site facts, who the competitors are and where they are strong, who currently owns the category in AI answers, and the category's naming variants.

Depth varies by layer: business boundaries (product, market, ICP, competitors, differentiation) need the client to **confirm**; Attributes and Topics come from interviews; **Prompt generation depends on internal data**. "We draft, the client ticks and deletes" relieves the Topic layer and does **not** relieve the Prompt layer — real buyer language for Prompt wording cannot be dropped, and drafting for the client never makes the intent pass optional.

The client-facing intake is a **fixed frame, not free-form**: "fill in whatever you like" is not a low bar but no bar, and clients freeze or free-associate. The canonical intake spec lives in the project's 《AI 搜索监测问题确认说明》 — follow it, do not re-invent columns. Its settled shape: five client columns `目标客户 | 客户问题与场景 | 客户原话 | 客户旅程 | 业务重要程度` (the scenario folds into 客户问题与场景; a 限制条件 column was tried and removed), importance on one ordered P-scale as defined there, which already contains frequency — never add a separate frequency column, and never use a middle P as an "undecided" placeholder. The attribute table carries its **own** P1–P3 with different semantics (P1 = decides candidate-set entry); the two scales must not be mixed. Two rules keep the intake honest: **the client gives facts and we make the judgements** (never ask them why they lose deals, how buyers would describe the advantage, or which advantages buyers credit), but do not over-relieve either — frequency, priority, and constraints are their daily sales judgement and stay with them; and **原话 is best-effort**, since most clients cannot produce quotes — a blank cell never blocks intake, it only drops that row to hypothesis grade and triggers our own verification (review mining, community language) before it can back a formal Prompt; never invent quotes to fill it. A client-facing confirmation document is written in Chinese, carries conclusions and answerable open items only, drops question numbering, and leaves our intermediate process to the internal archive file. **Every table in it carries a 客户确认 column, and its convention is write-what-to-change** — the client writes only in the rows needing a correction, deletion, or addition, and leaves every other cell blank; a blank column is a reviewed column, not an unanswered one. When producing the actual customer-facing 属性池 or 监测主题确认件, use [client-facing-attribute-pool.md](references/client-facing-attribute-pool.md): brand facts first, then the attribute pool, then candidate monitoring questions only when needed; use `品牌方`, not `贵司`.

Keep the original customer wording or a faithful summary as evidence. Separate:

- **observed customer intent**: supported by customer, sales, support, GSC, or monitoring evidence;
- **AI-answer opportunity**: a useful monitoring hypothesis derived from observed intent;
- **brand-advantage hypothesis**: a capability that still needs product or client confirmation.

Do not call a Prompt “high frequency” when it is only a plausible LLM expansion.

### Attribute means buyer decision focus

In after-sales work, an Attribute is not limited to a product feature or
technical parameter. It is the buyer decision focus being monitored under a
Topic and may be a capability, use case, customer pain, audience constraint,
procurement requirement, supply or service risk, or applicability boundary.
Product features become Prompts only when they matter in a real buyer context.

**The class list spans both sides of the table** — brand side (Category,
Feature, Differentiator, Integration, Trust & Security) and buyer side
(Industry & Vertical, Buyer Persona / ICP, Pain Point, Use Case, Evaluation
Criteria, Geography & Market, Constraint). Do not narrow it into a supply-side
capability inventory: ICP, persona, pain and use case are Attribute classes in
their own right, and this is where the apparent "attribute vs customer intent"
duplication usually comes from.

**Customer intent is a separate object, not a third Attribute class.**
Attributes decide **which perception to optimise**; intents decide **in which
user question to fight for that perception**. Keep both passes — attribute pass
first, intent pass second, cross-map third; do not jump straight to the joint
table, and do not merge the two into one column. What collapses into one table
is the **deliverable**: each input pass stays light (for attributes: the
twelve-class sweep from the rule document §3, covering product/service, ICP, differentiators,
and the capabilities buyers most need to verify; for intents: the
journey-organised signal pass from Customer and Market Signals), and the
client sees and confirms a single joint table because two heavyweight standalone
tables are unreadable and unfillable for them. The cross-map in Step 4 is that final
working artifact.

Topic and Prompt both grow out of Attributes, so they are derived and ranked **before** Topics and Prompts are named, in four steps.

**Step 1 — sweep the twelve categories as a gap check.** Sweep Category / Industry & Vertical / Buyer Persona / Pain Point / Use Case / Evaluation Criteria / Differentiator / Feature / Integration / Constraint / Geography & Market / Trust & Security to find what is missing. Never fill them mechanically and never treat the skeleton as a fixed list. The attributes that actually decide the choice are the category-specific ones the skeleton cannot supply — in B2B, Evaluation Criteria, Integration, and Trust & Security are exactly the classes general knowledge cannot fill.

**Step 2 — collect the category-specific attributes from three sources.**

| Source | What to take | Who |
|---|---|---|
| The client's own procurement standard | RFP / tender scorecards received, the evaluation items sales gets asked about most. B2B procurement already scores by domain, so this is the most accurate first-hand source. | Client provides |
| Competitor comparison and feature pages | Competitors have already summarised the category's evaluation dimensions for the market. | We research |
| Already-collected AI answers | Cluster the attribute words AI uses when describing brands in this category to get "the attribute set AI is actually using". Only we can do this layer, and it is the cheapest. | Ours alone |

**Step 3 — B2B and B2C are not one attribute set.** The required categories, the attribute wording, and the data lines all differ; mixing them yields a set that fits nobody.

| Aspect | B2B | B2C |
|---|---|---|
| Skeleton classes seen as required | Industry & Vertical (required); Buyer Persona written as decision / usage / payment / risk-control roles; Evaluation Criteria; Integration; Trust & Security | Industry & Vertical left empty; Buyer Persona as audience traits; Use Case; Pain Point; Evaluation Criteria |
| How attributes are worded | Procurement and risk terms: SLA, compliance certification, integration, total cost of ownership, implementation and migration | Consumption and experience terms: experience, ingredients or materials, price and value, word of mouth and repurchase |
| Data line | Procurement RFP / tender scorecards, sales and CRM records, support tickets, win/loss reasons | Product reviews and purchase enquiries, return reasons, community and social discussion, search terms |
| When one set is acceptable | Only when enterprise and individual buyers are both core and their criteria, scenarios, and competitors substantially overlap. Otherwise split into two cases with separate attributes and separate Prompt sets — never mixed into one. | Same |

**Step 4 — cross-map intents × attributes, filter by the joint test, and record the order.** Organise the demand side by the canonical five journey stages — `了解需求`(what solution should I look for) / `比较方案`(which fits me) / `评估是否适合`(can it meet my requirement) / `准备购买`(price, deployment, terms) / `使用与续费`(usage, service, renewal) — the same labels the client-facing confirmation doc uses; do not reintroduce older stage namings such as 了解产品/确认功能. Then map each intent to the attribute(s) that can answer it. Not every combination becomes a Query: keep only the cells that pass the joint test — **a real buyer asks it (demand) × the brand can carry it with evidence (standing to win) × there is a GEO action within the window (deliverable)**. An intent with no attribute behind it is low priority; an attribute no intent reaches is self-indulgent differentiation. Do not ask the customer to rank. The surviving cells, in order, become the Topic candidate order, and the deliverable is one working table: **journey → intent → linked attribute(s) → Topic → Query → priority** — not a separate attribute table plus a separate intent table.

**Boundaries for this section.**

- Attributes are not kept as a separate library, and no attribute requires its own Topic. Generation-time attributes (which design and explain the Prompts) stay apart from post-analysis attributes clustered out of AI answers: the two can be linked but never share one meaning.
- **Differentiators are Attributes** — one row each in the decision-attribute table with their own priority, never a separate section, never a Topic, never a Tag. The "competitor cannot copy this" test decides **how a claim may be worded as a differentiator**, not whether the dimension earns a row: shared category requirements (compliance certification, integration, SLA) are perfectly good Attributes and often decide the shortlist, they just must not be sold as differentiators. A claim every major competitor can match — global inventory or price advantage, 24/7 multilingual support, "more advanced technology" — is worded as the survivable part instead (not "全球 Content 最丰富" but "针对中国和亚太差旅，把全球内容与亚洲本地资源统一到一个平台") or recorded as parity. Trade-press or self-declared claims are labelled **品牌自述**, never asserted as fact, and gated on client confirmation.
- **Two blocks, not one.** Client-facing attribute sections separate a **品牌事实** table (brand, domain, business model, category, ICP, target customer, geography, applicable boundary — factual, unranked) from a **决策属性** table (ranked, with a client-confirmation column). The same split applies to the final deliverable: the master table's reference shape is `优先级 | 品牌属性 | 客户问题与场景 | Topic | Query | Query 类型 | 选择理由`, with 品牌事实 kept as a separate upfront table. Attribute evidence lives inside 选择理由 — do not add a separate 属性说明与证据 column, and drop any column that would carry the same information twice; the shape is a reference, not a validation checklist. Column naming (Prompt vs Query) is free as long as one document uses one term consistently. The one hard rule: keep 品牌属性 and 客户问题与场景 as adjacent but **never merged** columns — the whole act of translation lives between them, and merging them silently asserts "attribute = intent".
- **P3 attributes stay in the table but get no Prompts.** Keeping them visible lets the client disagree; writing Prompts for them wastes the budget. Only P1/P2 attributes carry Prompts — check this explicitly before delivery. The 选择理由 column carries **answer-layer evidence only** ("competitors are negatively mentioned on this theme at 33%, we are at zero"), never subjective reasoning, so it cannot be talked around by "the client says this matters". A paraphrased row we cannot source is tagged **待验证** rather than quietly kept.
- Attribute names must be legible to the client in their own industry vocabulary — if the client says "内容源覆盖是什么意思，看不懂", the name is wrong (the industry term was 库存, not 内容); rename it rather than explaining it.
- We draft the attribute list by category; the client only adds, deletes, and corrects, never fills from zero. A dimension the client did not raise but the procurement RFP plainly evaluates (integration, compliance certification, and the like) is raised by us for the client to confirm as fact. In a client-facing table, express such a row as whether it is a **selection gate** — never register certificate numbers or negative lists.
- Interview angles, if used, run When / Where / While / with What / Why / how-feeling / with-Whom, converging on the 5–8 attributes that genuinely affect the choice.

Before adding a new Prompt, require all three:

1. **Evidence:** it is supported by an observed query, answer gap, customer
   language, confirmed business change, or a clearly marked hypothesis source.
2. **Buyer reality:** a recognizable buyer, user, caregiver, service provider,
   or procurement role could naturally ask it.
3. **Incremental decision value:** it changes the candidate set, comparison
   dimension, preference, risk, or applicability judgment.

If any gate fails, keep the idea as a research/evidence-gap note, Tag, or
future hypothesis instead of adding a monitoring Prompt. Do not add a Prompt
just because a Topic has fewer rows than another Topic.

## Search-Demand Anchoring

Use traditional Search Demand to validate that a parent business need exists, not to copy SEO keywords into AI monitoring.

Apply this mapping:

`Search Demand -> parent Topic -> ICP / journey -> attributes and USP -> natural AI Discovery Query`

- Search Demand anchors parent Topics such as `Corporate Travel Management`, `TMC Selection`, `Travel Platform`, or `Travel Cost Management`.
- Product USPs such as APAC coverage, China content, rail, local service, corporate rates, policy, payment, or integration are usually attributes, scenarios, or constraints under a parent Topic.
- Do not create a standalone Topic from a feature or sales phrase unless buyers independently ask for that capability and it has enough distinct Prompts.
- Search-volume figures from different tools, countries, or databases are directional evidence only. Do not present them as comparable exact demand or as AI-answer volume.
- A long-tail regional or ICP Query may be valuable even when the exact keyword has little traditional volume, because it inherits demand from the parent Topic and can create a stronger brand-recommendation context.

## Workflow

0. **Confirm the monitoring scope.** Inherit the presales Case and confirmation record, correct changed business priorities and factual boundaries with the customer, and mark outstanding assumptions. A pending V1 can inform candidates but cannot enter the formal trial until the scope is confirmed. Keep this confirmation distinct from final Prompt approval after trial.
1. **Classify the change.** Decide whether this is a new Topic, a new Prompt under an existing Topic, a revision, a semantic merge, or retirement. Preserve the old Prompt IDs and evidence when modifying an existing set.
2. **Rank evidence.** Prefer, in order: observed monitoring gaps and repeated answer language; GSC/SEO queries; AI answers revealing new attributes or decision standards; confirmed product/market/USP/audience changes; industry changes. Record source and confidence for every new Prompt.
3. **Anchor parent demand before naming Topics.** Identify the parent Search Demand and customer journey stage first. Then decide whether the proposed Topic is a durable business need or only an attribute/USP cluster. **Apply the joint selection test before naming anything — demand × standing to win × deliverable, all three or nothing** (see [after-sales-rules.md](references/after-sales-rules.md) → *Topic and Attribute Selection Criteria*). "Standing to win" is judged by whether a competitor's advantage in that direction rests on brand awareness or broad media consensus: consensus-backed advantage is not reversible inside the window, so that direction stays a baseline topic rather than a battlefield.
4. **Design stable Topics.** The recommended first-stage shape is one category observation Topic plus two same-product buying-scenario Topics; use two Topics when product scope or evidence is genuinely narrow. This is guidance, not a quota. A Topic is a business opportunity worth observing independently over time, not a long sentence or one feature. Use short, scannable names, normally 1–4 English words. Put scenario and attributes in Prompts and Tags, not in the Topic name. A formal Topic needs at least five independent Prompts; if candidate evidence cannot support five, merge it, retain it as a Tag, or report the evidence gap rather than inventing filler. **A broad Topic must be resolved into its facets**: name the distinct buyer needs it contains — a label like `APAC coverage` may hide coverage breadth, cross-market itineraries, local content and low-cost carriers, local-language service, and multi-supplier data consolidation — and mark which facet each Prompt serves. Without that, one Topic name with N Prompts reads as coverage while every facet actually holds a single Prompt.
5. **Allocate Prompts by incremental value.** A formal Topic needs at least five independent Prompts, but counts do not need to be equal and there is no permanent after-sales total cap. Explain library size by independent decisions across priority product lines, buyers, markets, journey tasks, constraints and competitor/substitute sets; do not multiply every dimension. Start with the smallest set that covers the Topic's important buying situations and decision focuses. Stop when the meaningful decision coverage is complete. Put the weight on the facet where the brand's advantage meets buyer demand; do not spread Prompts evenly across facets for visual balance. Do not create a Prompt merely by changing “best” to “top”, reordering words, or balancing Topic counts.
6. **Prioritize Intent and Prompt Task separately.**
   - Prompt Task describes the buyer's job: `Discovery`, `Problem Solving`,
     `Evaluation`, `Comparison`, `Alternatives`, `Shortlist`, `Validation`,
     `Transaction`, `Post-purchase Support`, `Category Understanding`, or
     `Source Discovery`.
   - Intent describes the downstream analysis contract: `Discovery`,
     `Competitor`, `Evaluation`, `Verification`, `Accuracy`, or `Category
     Awareness`. Task labels never change routing.
   - Discovery: natural non-branded candidate questions; core visibility opportunity.
   - Evaluation: a concrete attribute, use case, or decision standard; useful for content/action planning.
   - Competitor: one-to-one comparison only when a new competitor, region, dimension, USP, or material gap justifies it.
   - Category Awareness: low-frequency observation; add only for a new category concept, trend, or changed buying standard.
   - Verification and Accuracy: only when the project already has an explicit evidence contract; do not create them by default. Capability validation is an alias for Verification.
   - For the first staged set, use Discovery only: draft the Discovery group
     first, then add the other intents as the situation requires, each for its
     own evidence-backed purpose — never to satisfy a role quota or fill a slot.
   - A reference distribution for a later stage (about ten Prompts) is six to
     eight Discovery plus two to four spread across Evaluation, Competitor,
     Verification, and the rest by actual need. It is a reference, not an
     industry standard or a quota, and it never justifies adding a type to fill
     a slot. Category Awareness is a low-frequency top-up; Accuracy is not part
     of routine expansion and needs a fact-check purpose plus complete official
     sources.
7. **Keep fields separate.** Every Prompt must have `topic`, `region`, `intent`, and `tags`; new Prompts should include exactly one `Prompt Task: ...` tag. Do not repeat `region` or `intent` inside Tags. When inheriting presales v8 rows, explicitly normalize `Intent`, `BrandScope`, and task tags into the after-sales fields; do not reject the inherited bank merely because it uses the older tag shape.
   - **Review the market, then decide reuse.** Build the lightweight internal coverage pass before writing or inheriting individual Prompts: product line, audience, journey stage, market/language, buyer constraint, competitor/alternative set and business priority, plus local terminology, source ecosystem, regulation, currency, trust, availability and service expectations when relevant. Only reuse a candidate intent and `intent_key` when local evidence supports equivalent buyer decisions and expected answer sets. Otherwise mark it `localized`, `market_specific`, or `not_supported`, and adapt, add, or omit the market Prompt with evidence. Translate and adapt approved wording to the market's language; same-language markets may reuse identical wording only after this review. Materialize and version a separate Prompt-set snapshot for each market/language so each has its own baseline. **Platform does not affect Prompt generation**: each market's set runs across its platforms unchanged. Never average market baselines or silently merge a market delta into another market's historical series. Keep the full coverage pass internal; show customers only the resulting facts, attributes, and necessary market-specific Prompts.
8. **Write buyer language.** The query must sound like a target buyer asking an AI, contain one main decision, avoid leading the answer, and include enough category context to prevent cross-category answers. Discovery Prompts must naturally ask for providers, platforms, or solutions to consider, choose, or recommend. Pure methodology, trend, education, or “how can I improve...” questions do not count as core Discovery unless the project explicitly wants a problem-awareness track.
9. **Validate Discovery quality.** Every Discovery Prompt must:
   - omit the target brand, frozen competitors, and other brand names;
   - expose a recognizable category and a commercial selection task;
   - test one primary buyer intent;
   - use no condition, one simple condition, or a meaningful compound condition that changes the candidate set;
   - avoid redundant containment questions such as “global coverage and APAC coverage” or “China and Asia” when one term already contains the other;
   - preserve at least one natural low-condition Prompt per Topic;
   - pass the evidence, buyer-reality, and incremental-decision gates above.
   - **Natural visibility is computed from Discovery Prompts only.** Named-brand Comparison, Evaluation, and Verification results are read on their own; they never enter the natural-discovery statistic.
   - When several brands must be evaluated, keep one identical wording across them. Compounds such as "customer support" as a Discovery sub-type stay Discovery — a specific attribute does not by itself make a Prompt an Evaluation.
10. **Deduplicate semantically.** Compare the new query with the whole active set. The unit of dedup is the **purchase decision**, not the wording: merge two Prompts that resolve the same decision (same candidate set, same comparison dimension, same condition that changes the answer) however differently they read. Normalised text uniqueness only catches synonym and word-order rewrites, so near-equivalent phrasings must be merged on human review. Keep both only when they change the buyer, region, use case, decision stage, competitor dimension, or expected answer set.
11. **Trial, approve, lock, baseline.** On each proposed platform run every candidate Prompt three to five times under the intended market/language and collection conditions; retain raw results. Check category/task fit, ambiguity, leading language, and duplication, never target-brand mention as a pass/fail criterion. **"Can we win" is only one leg of demand × standing to win × deliverable**, not a reason to remove a valid zero-mention Prompt. After the trial, the customer confirms the final set; save its immutable version and evidence. Then plan a formal baseline of three consecutive calendar days, once per Prompt per platform per day, under unchanged conditions. Trial answers are excluded from that baseline. Count only valid observations; a failed or missing day cannot be filled with zero or glued to nonconsecutive days. This three-day baseline is an initial benchmark, not proof of a stable long-term cognitive gap. Collection is delegated only when explicitly requested.
12. **Set cadence separately.** Discovery baseline uses daily collection for those three calendar days; ongoing cadence is weekly or otherwise as agreed. Competitor, Evaluation, and Verification follow the agreed or event-triggered cadence, not a fixed quota. Category Awareness is occasional. A baseline Discovery observation group uses the comparable cadence; it is not Category Awareness or automatically a causal control.
    Any addition, deletion, or wording change creates a new Prompt-set version and a fresh three-day baseline for the affected market/group. Preserve old IDs, results, and lineage; unchanged common Prompts can still be compared on their own, but new and old set-level series must not be spliced.
13. **Review and deliver.** Run the deterministic checks in [output-contract.md](references/output-contract.md), then perform a semantic review for evidence traceability, Topic fit, no cross-topic competitor use, no invented facts, no duplicates, useful incremental value, and clear lifecycle/lineage status. **Reconcile the intent pass against the Prompt set in both directions** — every P1/P2 intent carried by at least one Prompt, every Prompt's intent present as a row in the client's intent table — and make the master table's intent column quote the intent table verbatim so the two cannot drift. Before delivery, review the internal market coverage pass and confirm every retained market-specific delta has evidence and every omitted slice has a reason; distinguish official competitors from substitutes and the status quo without changing the frozen list. For each Prompt group state the diagnostic business question, possible action, role and next review trigger. Then check the evidence layer itself: does a sentiment matrix for this category actually exist, and did it cover the discovery questions?

## Topic and Prompt Sizing

The recommended first-stage shape is **one category observation Topic + two
same-product buying-scenario Topics** (two Topics can be justified), with
variable counts based on evidence-backed decision coverage. A customer-confirmed,
locked, or formal Topic requires at least five independent Prompts, normally
5–10 and with **8 as the internal recommendation and no permanent upper cap**;
ten or more requires a stated reason (ten or more genuinely distinct important
intents, otherwise split the Topic). Weight the counts rather than equalising
them — put the weight on the buying-scenario Topics the brand can win and leave
the category observation Topic lighter. Candidate Topics below five remain
explicitly pending merge, Tag treatment, or evidence completion. **Before concluding a Topic is short, re-check attribution**: a Prompt filed under the wrong Topic is a common cause of one Topic falling under the floor while another quietly carries a Prompt that does not serve it. Move it to where its actual purchase decision belongs, then count again — that is a correction, not padding. Do not add a
Prompt to fill a visual gap, or turn the presales `<=50` discovery-stage limit
into a permanent after-sales library cap.

## Output

Unless the user requests another format, deliver:

- A customer-facing attribute pool / confirmation document when the task involves scope confirmation, attribute priority, Topic approval, or Prompt wording approval. Follow [client-facing-attribute-pool.md](references/client-facing-attribute-pool.md): brand facts first, then 属性池, then candidate monitoring questions when needed; every table has a `客户确认` column using the write-what-to-change convention.
- A machine-readable JSON monitoring set.
- An upload CSV with `query,question_zh,topic,region,intent,tags` plus only the project-required compatibility columns.
- A cadence/schedule file.
- An input/evidence diff listing why each Topic or Prompt was added, changed, merged, or retained.
- In that same internal diff, a compact market-coverage section: reviewed slices, local evidence, retained/omitted intent decisions and reasons. Do not create a new customer-facing matrix.
- A short validation summary, including known incompatibilities when an older presales validator enforces fixed quotas.

For a single-product update such as Botslab NV900, keep the new product line isolated from unrelated product Topics. Reuse frozen Case boundaries, but do not carry unrelated competitors into the new Topic.
