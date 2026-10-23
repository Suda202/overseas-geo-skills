# After-Sales GEO Prompt Rules

This file is the canonical rule text for after-sales Prompt work (Suda 2026-10-19: the Feishu copy 《售后生词规则》 is retired and no longer the authority; do not edit it). Read it as the rule document itself; the SKILL.md workflow restates the parts execution depends on. It also adapts the representative-library guidance from Aleyda Solis for this project. An earlier document of the same name has been superseded and its body emptied — do not cite it. The client-facing intake spec is the separate 《AI 搜索监测问题确认说明》.

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
availability, and service expectations when they can change the answer. We
draft this pass and the brand party reviews its filled slices in the client
Base's 提示词矩阵 table (one row = buyer situation × attribute, which also carries
the attribute pool); it is not a form to fill every combination.

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

## The Stage Chain and What Each Can Conclude

Six stages (Suda 2026-10-23, superseding the four-stage table): 需求研究与属性池 → Topic 规划与出题（覆盖矩阵） → 试跑（各监测平台 × 3 次） → 机会排序与客户选词 → 正式 Baseline → 优化与持续监测. The chain is continuous, but each stage answers exactly one question. **An earlier stage may only raise a hypothesis; it may not state a conclusion.** Moving a later conclusion forward is the most common error in this flow.

| Stage | The question it answers | What may be said here | What may NOT be said here |
|---|---|---|---|
| **1 需求研究 → 属性池** | What is worth monitoring? | Brand facts, demand signals, attribute pool (重要性, 相对竞品, 初步可改变性), competitors, candidate Topic directions | Whether AI has a cognitive gap — nothing has been collected yet |
| **2 Topic 规划与出题** | Which needs become questions, and how many? | Formal Topics (clustered from the pool, checked against the coverage matrix), candidate Prompts, type and tier defaults | Any AI-side reading |
| **3 试跑（每题 × 每个监测平台 × 3 次）** | Is each question asked right, and what does AI answer today? | `prompt_validity` (合格/修改/淘汰); **exploratory** readings — brand and competitor mentions, positions, cited sources, a 来源追不上 lead | A stable mention rate; any selection decision driven by the brand's own reading |
| **4 机会排序与客户选词** | Which Prompts should the client pick? | A recommendation order from buyer importance (slice tier), adjusted once only by a **confirmed** 来源追不上 barrier; trial readings shown as context columns | A promise that optimisation will work; a tier dropped because the brand already leads |
| **5 正式 Baseline（选定题 × 每平台 × 每国家 × 每语言 × 30 次）** | What is the initial Before benchmark under the locked set? | Formal per-platform visibility and citation diagnosis; re-judged changeability; provisional optimisation order; feasibility assessment for the commitment | A claim that a gap is stable over time, or that optimisation worked |
| **6 持续监测** | Are the gaps persistent, and did optimisation improve them? | Same-question, same-condition, same-caliber window comparison; longitudinal evidence | A single-day comparison or immediate effect promises |

**One line: 选词评估需求价值与可争取性，试跑提供探索证据，正式 Baseline 验证实际表现与承诺可行性，长期可比数据检验持续性与改善。**

**The candidate baseline is retired** (Suda 2026-10-23, superseding the 2026-10-13 全候选 × 全平台 × 5 次 rule). Multi-platform collection runs only for the client-selected formal set, and that run **is** the Before baseline. Candidates the client does not select are never collected beyond the trial. What this buys: no collection spent on unselected Prompts, and the client cannot pick Prompts by multi-platform readings — the anti-selection-bias rule is enforced by structure, not only by text. Because the trial runs on every monitored platform (Suda 2026-10-23), a platform-specific wording problem (one platform answers a different category, AI Overviews never triggers) surfaces at the trial; what still slips through is handled by the rule in *Versioning and baseline anomalies*, never by quietly dropping the Prompt. Banks collected under the old flow keep their data and calibers; do not migrate or delete them. A platform that cannot be collected in a market (ChatGPT in Hong Kong) is left out of both the trial and the formal baseline for that market.

## Stage 1: Demand Research and the Attribute Pool

**Settled sequence** (Suda 2026-10-23). Attributes are distilled from two parallel research passes — buyer signals (reviews, community, search data) and official-site research (the brand's own pages, spec sheets, competitor comparison, certification) — plus the twelve-class skeleton sweep. Both passes feed the pool; neither is skipped.

**The coverage matrix grid is enumerated before the pool is filled** (Suda 2026-10-22 top-down rule). From 业务范围, write out the complete 产品线 × 主要受众 × 旅程阶段 Cartesian product first, as a gap-check skeleton. Then collect signals and research the official layer; the evidence fills the skeleton. A cell that remains empty when the matrix settles is closed with a reason in the internal handoff — 无买家证据 (our research gap) / 低业务优先，留到后续周期 (the brand party's confirmed trade-off, read off the 业务范围 主要受众 priority marks) / 超出范围; `scripts/check_matrix_coverage.py` lists the open cells. Do not open by filling in an attribute list and then hunting for signals that confirm it, and do not write a Prompt into an empty cell just to close it. This prevents silent coverage holes: an audience quiet in buyer signals but business-critical (a new market, a B-end buyer, a niche but hard-constraint segment) stays as an empty row with 「无买家证据」 written, not an invisible omission. Enumerate the skeleton only; do not mechanically fill every cell — use the three-tier distinction Suda stated (候选组合 / 有效切片 / 排除组合+原因) to separate the real buying situations from the mechanical grid fill.

**Audiences beyond the business scope's listed 主要受众 are added to 业务范围 as 主要受众 rows, never as hypothetical池 rows or undocumented options.** An audience split that changes eligibility, dominant criteria, or the expected answer set is a real segmentation; one that does not is a 约束. Freeze the list before Prompts are written (Suda 2026-10-20), validate it against first-party sources (sales records, support tickets, the site's own audience selectors), and judge it once: each non-base audience becomes an 属性池 买家角色 row carrying 重要性 only (高 when the brand party marked it 主要受众（优先） or a 业务目标 names it, 中 for other confirmed 主要受众, 低 for hypothesis-grade or 后续 audiences); that 重要性 caps every slice serving the audience (see *Priority is set in two passes*). The base audience (the category's own buyer group) gets no row — it is the category itself, caps nothing, and every Prompt without a narrower buyer condition serves it.

Attribute priority (重要性 × 可改变性 → tier, capped by the audience) is set in this stage; the rules are in *Priority is set in two passes* at the end of this stage. Topics are clustered from the P1 landings in Stage 2.

### Customer and Market Signals Before Product Features

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

- **Must have (without it the work is wrong):** the target buyer's real intent, differentiators, what the business does not do, which scenarios are easier to win, which unique assets the client holds, **the business goal for this service period, and the marketing campaigns inside it** (Suda 2026-10-23; collected as 业务目标（n） / 营销活动（n） rows in 业务范围 — what they may and may not decide is in client-facing-attribute-pool.md → *Settled table set*).
- **Best to have:** finer buyer wording and scenario detail — the material that makes a Prompt sound natural instead of generic.
- **Collect ourselves:** official-site facts, who the competitors are and where they are strong, who currently owns the category in AI answers, and the category's naming variants.

Depth also varies by layer: business boundaries (product, market, ICP, competitors, differentiation) need the client to **confirm**; Attributes and Topics come from interviews; **Prompt generation depends on internal data** — that layer's real buyer language cannot be skipped. "We draft, the client ticks and deletes" solves the Topic layer, not the Prompt layer.

### The customer confirmation table

"Fill in whatever you like" is not a low bar — it is no bar, and clients freeze or free-associate. Give a fixed frame; lower the burden by choosing the right columns, not by removing them. For the actual customer-facing 属性池、主题与问题确认件, use [client-facing-attribute-pool.md](client-facing-attribute-pool.md) as the concrete document pattern: opening scope, 核对时从哪里判断, 品牌事实, 属性池, optional 主题与问题, optional 竞品 (in the Base: 竞品（n） rows of 业务范围), 需要品牌方提供的数据, and 试跑、选词与正式基线流程. The canonical intake spec is the project's client-intake spec 《AI 搜索监测问题确认说明》 — follow it rather than re-inventing columns. Its settled shape is five client columns:

`目标客户 | 客户问题与场景 | 客户原话 | 客户旅程 | 业务重要程度`

**On the column name 客户问题与场景 (renamed 2026-09-22, was 客户意图).** The column holds the buyer's occasion and ask, which is a distilled **output** of the signal pass, not the signals themselves — the old name "客户意图" read as if it named the whole collection stage, and invited readers to treat it as a synonym for Customer / Market Signals. The column set in 《AI 搜索监测问题确认说明》 was renamed to match; that document is canonical for the client-facing frame.

**Delivered client documents are revised when the nomenclature changes** (decided 2026-09-22, superseding the earlier hold-and-reissue-only rule). A column name or a P-scale that a client has already read is a shared vocabulary, not a private one: leaving old documents on the old label while new ones use the new one splits that vocabulary and makes the client's own confirmation table disagree with what we send next. So when the canonical frame changes, sweep the delivered files too, and say what changed. Practical order: update the canonical document first, then the internal files, then the delivered client documents, so every artifact ends on one vocabulary.

- **业务重要程度 uses one ordered P-scale as defined in that document**, which already contains frequency — do not add a separate frequency column, and never use a middle grade as an "undecided" placeholder. The **attribute table carries its own P1–P3 with different semantics** (P1 = decides customer-set entry); the two scales must not be mixed.
- **客户旅程** is named exactly that; in the client Base the column is 旅程阶段 with the eight stages 发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持 (2026-10-15, replacing 了解需求 / 比较方案 / 评估是否适合 / 准备购买 / 使用与续费). Do not invent an alias like "提问场景" and then explain it means the journey.
- **客户原话 is best-effort, not a hard requirement** — in practice most clients cannot produce quotes, so a blank cell never blocks the intake. The column stays because of what a blank tells us: the intent is the induction, the quote is the evidence, and a row nobody can find a quote for drops to hypothesis grade and triggers our own verification (review mining, community language, support-log sampling) before it can back a formal Prompt. When the client does quote, it is "pick one representative sentence", not a transcript. Never fill this column ourselves with invented quotes.
- A scenario column was tried and removed — fold the situation into 客户问题与场景 instead; a standalone 限制条件 column was also dropped from the client table, since constraints are better elicited in conversation than as a form field.
- **The boundary: the client gives facts, we make judgements.** Any question that asks the client to reach our conclusion for us — why they lose deals, "how would buyers describe your advantage", "which advantages do buyers actually credit" — stays out of the client's list. But do not over-relieve either: frequency, priority, and constraints are the client's daily sales judgement, so those stay with the client.
- Keep the client's confirmation burden to what only they can answer. If a column has grown into a multi-part question, cut it to the one thing being confirmed — asking for more confirmation than "just the priority" is itself a failure.
- **Market does not follow the question**: market and language are fixed at project start, and a multi-market engagement gets one monitoring snapshot per market, while the client Base is shared and split by its 市场 field (2026-10-19, see client-facing-attribute-pool.md → *Several markets in one Base*). The internal coverage pass decides whether an intent is `shared_equivalent`, `localized`, `market_specific`, or `not_supported`; do not assume the same core intent, `intent_key`, competitor set, or answer ecosystem across countries. Localize question wording and record evidence for budget/currency, competitors, constraints, terminology, regulation, trust, availability, or service differences. Each market/language has its own version and baseline.
- Client-facing confirmation documents are written in Chinese, contain conclusions and answerable open items only, drop question numbering (the crawler uses the prompt text, not the number), and never include our intermediate process (methodology notes, word-frequency work, validation steps go to the internal archive file).

Rows we drafted from public research are marked as ours; the client corrects and supplements rather than filling from zero — and drafting first never makes the client's intent pass optional.

### Search-Demand Anchoring

Traditional Search Demand should anchor the parent Topic, while the brand’s differentiators become attributes and Query conditions:

`Search Demand -> Topic -> ICP / journey -> Attribute / USP -> AI Query`

For example, `corporate travel management`, `travel management company`, `business travel software`, and `travel policy` can validate parent demand. `APAC coverage`, `China Railway`, `local service`, `corporate rates`, `multi-market settlement`, and `policy automation` should normally be treated as attributes or scenarios under those Topics, not automatically promoted to independent Topics.

Search-volume tools may use different countries, databases, and keyword definitions. Use them to validate direction and relative demand only; never treat their figures as AI-monitoring volume or directly comparable exact numbers.

### Topic and Attribute Selection Criteria

Authority for this section is this file itself (the retired Feishu 《售后生词规则》 was folded in here on 2026-10-19).

Attributes are tiered by importance × changeability before any collection and re-judged after the formal baseline (see *Priority is set in two passes* below); Topics are then clustered from where the P1 Attributes land.

| Condition | Meaning | Who judges |
|---|---|---|
| Importance | How much the Attribute matters to the purchase decision | From the user-language sources: the client supplies sales and support records; we collect search data, reviews, and community language |
| Changeability | Whether the brand can move it within its own control | Us, from gap type, `相对竞品`, and the asset inventory |
| Current gap | Distance between what AI says and what we want | The formal baseline data; `待测` before collection |

Do not ask the customer to rank. **Topics are clustered from where the P1 Attributes land** — the core category as one Topic, and the buyers or scenarios where P1s concentrate and change the purchase judgement as Depth Topics. A differentiator no buyer asks about does not become P1 and does not get its own Topic.

**Selection runs in two passes.** Before the presales run, Topics follow the P1 Attributes from importance × changeability. **After the formal baseline, current gap is added and the priority re-ranked**; these observations may guide the next action but do not establish a stable cognitive gap. Compare later windows before claiming persistence or improvement. See *The Four Stages and What Each Can Conclude* above.

**Consensus-locked directions do not get a Topic.** If a competitor's advantage in a direction rests on brand awareness or broad media consensus, it is not reversible in the short run. Its changeability scores as a capability gap, and **do not open a Topic for that direction.** A Topic carries Prompts, Prompts carry a measurement cost, and a direction nothing can move returns the same number every cycle — buying a baseline instrument that can never read differently is worse than not measuring it. Read the overall category position from the presales round instead. Directions whose competitor advantage does *not* rest on consensus are the battlefield that is movable within 90 days.

**Judge this per Attribute, not per Topic.** A Topic can be unmovable as a whole while individual Attributes inside it are fixable — an absent OEM page or an unpublished certification is an evidence gap that one page closes, even when the Topic's leaders are consensus-locked. When you drop a Topic, **re-home its Attributes one by one**: promote the movable ones into a surviving Topic, and for each one you leave behind record why. Deleting a Topic and letting its Attributes sit in the plan unmeasured is the failure this rule exists to prevent.

**Evidence hierarchy for the consensus and optimisation judgement — answer layer beats spec sheet.** Read the AI answers' sentiment matrix (which competitors are criticised on this theme, and whether we are clean) before comparing product specifications, and put market-convention web research last. A dimension where competitors have hardware parity can still be a battlefield if AI answers keep criticising them there; conversely, buyer-forum language that never enters AI answers is not monitoring evidence. Structural losses recorded in the answer layer do exclude a Prompt ("only structural evidence excludes; a single zero-mention never does"), and a dimension where we are the weaker party **does not get its own Topic** — let the category Prompts surface it.

**The answer layer may not exist — check before reading anything into its absence.** A sentiment matrix exists only if the presales run produced one *and* put the **discovery** questions into its sentiment sample scope. Two failure modes are both common, and neither is an anomaly: a rough presales pass runs visibility only and has no sentiment layer at all; and a run that marked only the branded evaluation question produces a self-portrait of the brand rather than a competitor matrix, so there are still no per-theme negatives to read. Verify which case you are in before treating the answer layer as evidence.

When the matrix is absent, do **not** report the emptiness as a finding that competitors are clean. Fall back to the next evidence layer — product specifications, our own asset inventory, external research on who leads the category — mark the consensus judgement as **provisional**, and say so in the deliverable. Record the gap as a process fix for the next presales run rather than as a blocker for this one.

**When several brands must be judged, keep the theme boundaries fixed across the run** so a later matrix stays comparable to the first one.

**When no theme shows a competitor negative.** A first pass can come back with competitors clean on every theme — roundup-style AI answers praise rather than criticise, so this is common and is **not** proof that no opening exists. It does mean no theme has a *demonstrated* opening yet. Do not quietly keep the optimisation labels on the Themes while the evidence says nothing was found; state it in the deliverable, hold the labels as provisional, and plan a second run of the same matrix immediately after the baseline so the judgement is longitudinal rather than a single snapshot. Also note the counter-explanation in the deliverable: an absence of negatives may be a property of the answer format rather than of the market.

**When the client asks for the head term they cannot win** ("rank #1 on <broad category> recommendation"): do not drop the broad term and do not promise it. Keep exactly one broad category Topic as the baseline/diagnostic instrument, keep it light (roughly six Prompts), and put the real question budget into the narrow Topics where evidence shows the brand can win (eight to ten each). Explain the trade-off in the client's terms, not with our internal scoring.

**Differentiators are Attributes.** They are one row each in the decision-attribute table with their own priority — never a separate section, never a Topic, never a Tag. The "competitor cannot copy this" test decides **how a claim may be worded as a differentiator**, not whether a dimension earns a row: shared category requirements (compliance certification, integration, SLA) are legitimate Attributes and often decide the shortlist; they simply must not be sold as differentiators. A claim every major competitor can match — global inventory or price advantage, 24/7 multilingual support, "more advanced technology" — is either worded as the survivable part or recorded as parity. Trade-press or self-declared claims are labelled **品牌自述**, never asserted as fact, and gated on client confirmation. Attribute names must be legible in the client's own industry vocabulary — when the client says a name is unreadable, rename it rather than explaining it.

**Consensus and `相对竞品` judgements are made against the actual category leaders, not only the frozen competitor list.** Treating the frozen list as the whole competitive set produces false confidence: the brand may look strong against the configured set while the real answer-layer winners are elsewhere. Use the frozen list for Prompt construction and reporting consistency, but judge them against whoever actually leads the category's AI answers.

**The per-attribute relative-competitor verdict is researched, not requested.** Every P1, and every P2 that carries Prompts, is judged by actually comparing our public position against that product line's leaders on that attribute — answer layer first, then the competitors' own public pages (spec sheets, certification pages, service terms), then third-party material. Run it product line by product line: the comparison set is not the same set across lines.

**Where the engagement already has collected answers, read the set off the answer layer** — whichever brands actually lead that product line's discovery answers, **computed separately for each market**: count mentions only in unbranded discovery answers from that market's run and take the top three per product line × market. A multi-market engagement (e.g. SG + MY) therefore carries one comparison set per cell, not one for the whole Case; a brand that leads in one market can be absent from another. Presales is unchanged — its Case keeps a single frozen set. The presales competitor-research step exists for the **pre-data** case, before anything has been collected; once data exists it is superseded, and a frozen list carried forward from before the run is a hypothesis to re-check rather than a given. Where no answers exist yet, fall back to it. This is **not** `automatic competitor discovery` — here the set is given and making the comparison is ours.

`待确认` therefore means **we looked and the public layer genuinely cannot settle it** — a QC agreement, an internal test report, a privately held warranty clause — never "nobody handed us a number". Always name the material that would settle it. A column that comes back mostly `待确认` is a research gap, not a finding: before shipping it, check whether the comparison was actually run.

While judging, split the gap and state which applies: **evidence gap** (the capability exists but is not published — the fix is a page) versus **capability gap** (the capability is absent — the fix is investment). That split is the most actionable line in the document and it is invisible from the verdict alone.

**Check factual accuracy during the same research pass — do not wait for Verification or Accuracy Prompts to find errors.** For every factual P1 (and every factual P2 that carries Prompts) — attributes with one checkable right answer, such as installation requirement, dimensions, availability in a market, price band, certification, warranty, eligibility, or corporate ownership — run two checks while filling `相对竞品`:

1. **Public-layer consistency.** Do the official site, marketplace and retailer listings, reviews, and third-party profiles state the same fact (model names, specs, prices, scope)? Conflicting public sources are the main reason AI gets a fact wrong.
2. **Answer-layer statement.** In the collected answers, what does AI actually say about this fact for the brand — correct, wrong, outdated, conflated with another entity (Ebrand vs Ebrand), or missing a remedy the brand does offer (UNI_A's foundation pathway)?

Write what you find into the client Base's **品牌事实核查** table (Suda 2026-10-16) — one row per contradictory or unsupported fact, with the official value, the source-page URL, the conflicting statement and its source, and whether the brand party should 改官网 or 提供材料 — and, for the attribute it belongs to, into that row's `备注` / `还缺什么` as evidence for the client to confirm; do not report it as an accuracy percentage — presales samples are too small, and the ground truth is the client's to settle. Subjective appraisals ("easy to use", "good value") are not facts; they belong to sentiment and recommendation, not here. See [client-facing-attribute-pool.md](client-facing-attribute-pool.md) → *品牌事实核查*.

**Only a few of those rows become Verification or Accuracy Prompts.** Research finds what is wrong and why; monitoring only tracks known risk points and whether fixes land. The two intents split by what AI gets wrong. One fact gets one Prompt, classed by what AI does with it during research; when that changes (AI learns the capability but then states a detail wrongly), reclassify the Prompt rather than add a second one. Different facts under the same attribute may carry one Verification and one Accuracy Prompt:

- **Verification** — AI does not know the brand holds the capability. The row becomes a Verification Prompt when the brand really offers the capability, a wrong answer would change shortlisting or purchase (typically a P1 or gating fact), and the discovery answers cannot show whether AI knows it (the brand is rarely or never mentioned on that attribute). Read it against the Discovery Prompts on the same attribute (trust gap vs comprehension gap, above).
- **Accuracy** — AI can state the fact but states it wrongly. The row becomes an Accuracy Prompt when a wrong answer would change shortlisting or purchase, and the answer layer already states it wrongly or outdatedly, **or** the fact recently changed (new model, rename, repricing) so AI is likely stale.

Either intent requires the client to have confirmed the right answer and an official source page — without that, keep it on the pending-confirmation list, not in the Prompt set. Facts that already appear correctly and frequently in discovery answers need neither. Expect roughly two to five per market across both intents; ask one checkable answer and name the brand (e.g. "Does Abrand G3 require plumbing installation?"). The client-confirmed answer is the scoring truth for that Prompt.

**The category observation Topic doubles as a diagnostic.** Research suggests roughly 15% of categories already have a clear winner. Where one exists, put the effort into the depth Topics and keep the category Topic as the baseline instrument; where none exists, the category Topic is itself a winnable battlefield. It has to be measured either way, so the extra judgement costs almost nothing.

**When the leader is the default, skip the bare category question** (Suda 2026-10-19, Hbrand). Where one brand holds roughly nine-tenths of the market and the brand party's own query data shows buyers do not ask "which platform / brand is best" (Singapore property portals: RivalH1; the brand's GSC was dominated by need queries such as "hdb for rent"), do not write bare "which X is best", "which sites should I use" or "alternatives to [leader]" Prompts — the brand cannot enter those lists within the service period, and buyers rarely ask them. Write the buyer's underlying need with its real conditions (area, unit type, budget, life stage, timing) instead; AI names the platforms or brands it would use as channels in passing, and that is what is measured. A "which platform" Prompt stays only when it carries a concrete capability condition the brand genuinely leads on (Hbrand: previewing new launches in 3D or VR). The category observation Topic is then dropped, and the first-stage shape is the buying-scenario Topics alone. **Record the exception as `config.leader_default` with the reason**: this rule is the explicit exemption from the per-Topic low-condition anchor (SKILL step 10), and the validator keeps warning about all-conditioned Topics until the field states why.

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

**Step 2.5 — merge and name before ranking.** The sweep and the three sources produce candidates, and candidates come back under several names for one thing — Pbrand's matrix carried 52 attributes of which 25 were repeats; Hbrand kept 43 after merging and still had 「平台收费透明」 beside 「中介佣金透明」. Merge by what would change the action, the same test 受众 uses:

| Question | If yes |
|---|---|
| Would one content action close both? (one fee page, one spec paragraph, one warranty note) | Merge into one attribute — 「平台与中介费用透明」, not two |
| Do both sit in the same twelve-class, and would a buyer ever choose between them as separate considerations? | Merge |
| Are they the same thing under a long and a short name? (「购房资格与流程指引」 vs 「购房资格与流程」) | Keep one name, and use it in the pool, the matrix link and the bank |
| Does AI judge them separately in its answers, or do they need different optimisation actions? | Keep them apart even when the names look alike — Hbrand's 「3D 楼盘模型」 and 「视频看房」 carry different 相对竞品 and changeability verdicts |

One attribute takes one row in 属性池 and one name everywhere; a name that only appears inside the matrix's linked cell and nowhere in the pool is a merge that was never done. Do this before priority is ranked, because merging after ranking means re-ranking.

**Step 3 — B2B and B2C are not one attribute set.** The required categories, the wording, and the evidence lines all differ; mixing them yields a set that fits nobody — see the rule document §3 for the full comparison table (skeleton classes seen as required, how attributes are worded, data line, and when a single B2B/B2C set is acceptable).

**Step 3.5 — validate that someone actually asks it, before locking.** An attribute graded P1 or P2 is still only a hypothesis about the market until a first-party source says buyers raise it. Check each P1, and each P2 that will carry Prompts, against our available sources: GSC/SEO queries, sales and CRM language, support tickets, win/loss and churn reasons, review and community language, already-collected AI answers. Traditional search volume is a directional signal, never proof of AI-side demand, and a long-tail or regional Query may legitimately have little volume while inheriting demand from its parent Topic. Where no first-party source exists, the row is marked **hypothesis grade** — it may still ship in a Discovery-first set, but it cannot be described as frequent, commonly asked, or high-demand. We have no AI prompt-volume data source; do not invent one, and do not present a tool's keyword figure as AI-answer volume.

**Inclusion follows buyer demand, not brand content** (Suda 2026-10-19). Whether to write a Prompt depends only on evidence that buyers ask it — buyer quotes, search signals, the brand's own GSC — and a niche audience counts (divorcing couples, retirees selling a short-lease flat, a citizen married to a foreigner). Whether the brand's site already has an article on it is not a reason to include a Prompt, and its absence is not a reason to leave one out; that only feeds changeability and, after the baseline, the content plan. Whether a direction can be won is read from the baseline, not pre-judged — except the bare category question above, where the leader's dominance already settles it.

**On the current-gap condition (fill it only when it has been measured).** Profound's third question — is there distance between what AI says and what we want it to say — is the leg we most often cannot answer at generation time, because a first set is designed before any answer exists. Do not fill it from intuition: an unfilled Gap is marked `待测`, never "AI doesn't know us". **But the engagement usually runs two rounds** — presales collects a first answer batch, so after-sales often *does* have measured Gap data. When it exists, fill it with the measured value and cite the sample ("APAC coverage mentioned in 33.3% of 15 valid discovery prompts, the other 7 topics at 0"), and keep it to the answer layer: a sales hunch or "the client says this matters" is not Gap evidence. **Where another company shares or nearly shares the brand's name, measure the gap on the brand's own-domain citation rate, not on name mentions**: a name appearing in the answer does not show the AI read the brand's content, and some of those answers cite the other company's pages under the brand's name.

**Step 4 — cross-map intents × attributes; the P1 Attributes and where they land become the Topic candidates.** Organise intents by the eight journey stages (`发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持` — the client Base's labels since 2026-10-15; the five-stage set and older namings like 了解产品/确认功能 are retired), map each to the attribute(s) that answer it, and keep the cells carrying P1 and P2 Attributes. An intent with no attribute behind it is low priority; an attribute no intent reaches is self-indulgent differentiation nobody queries. Importance is judged from the client's signal pass plus our own buyer evidence. Do not ask the customer to rank.

Attributes are also not kept as a separate library: they exist to build and explain Topics, so do not create one Topic per Attribute or promote a brand's self-described selling point into a buyer need. Keep generation-time attributes (which design and explain the Prompts) apart from post-analysis attributes clustered out of AI answers; the two can be linked but never share one meaning. We draft the attribute list by category and the client only adds, deletes, and corrects — a dimension the client did not raise but the procurement RFP plainly evaluates is raised by us for confirmation. If interviews are used, run When / Where / While / with What / Why / how-feeling / with-Whom and converge on the 5–8 attributes that genuinely affect the choice.

### Audience Segments

Audience is a dimension of the attribute pool, not a free list of labels. Segment it the same way attributes are derived: reason out the likely classes first, then correct them with evidence. Hbrand went seven → five (2026-10-20) because citizens and PRs, and buyers and renters, were split before anyone checked whether the split changed anything.

**Step 1 — write the parties in the purchase, not a demographic list.** Who decides, who uses, who pays, who owns or manages the thing after the purchase, and who carries the constraint. For a property portal that is: the buyer, the renter, the seller, the landlord, plus the family situation that decides eligibility. A demographic cut (age, gender, income) belongs here only when it changes one of Step 3's tests.

**Step 2 — cut by the things that change the decision, not by who the people are.**

| Cut | Ask | Merge when |
|---|---|---|
| Eligibility or legal status | Do different statuses admit different candidates at all? (citizenship, PR, work pass, licence, age) | The rules, the candidate list and the query wording are the same → one segment |
| Money source or payment form | Does the money come from somewhere that imposes its own rules? (self-funded, employer, insurer, government subsidy, loan type) | Same shortlist and same criteria → one segment |
| Relationship to the thing | Buy, rent, own and resell, or manage for someone else — each has a different job and different proof needed | Same stage, same candidate set → one segment |
| Hard constraint | A condition that removes options outright (family structure, pets, mobility, relocation date, online-only) | It only changes the wording of a question → a 约束, not a segment |

**Step 3 — apply the three tests.** A segment earns its place only when it changes at least one of: **which candidates are eligible**, **which criteria dominate**, or **how the question is phrased in a way that changes the answer**. If it changes only the phrasing, it is a 约束 on a slice; if it changes nothing, merge it into the nearest segment. B2C usually lands at five or fewer; B2B adds the buyer role (decision, use, payment, risk control) as separate rows, because there the roles really do buy differently.

**Step 4 — validate against first-party evidence, then freeze.** Check each proposed segment against sales and CRM segment labels, support-ticket categories, GSC and site-search terms, community and review language, the competitor sites' own filters, and already-collected AI answers. A segment no first-party source names is hypothesis grade: keep it only if a named buyer situation demands it, and say so. The brand party confirms the list as 主要受众（1）…（n） rows in 业务范围; we do not ask them to design the split. Freeze the list before writing Prompts — changing segments later moves every slice's audience, the per-audience dashboard and any audience-level reading.

**Step 5 — rank the audiences in 属性池** (Suda 2026-10-23). Each frozen segment except the base audience becomes a 买家角色 row named exactly as its 受众 option. Only its 重要性 is judged — the engagement's business weight (高 = marked 优先 or named by a 业务目标; 中 = other 主要受众 with first-party demand; 低 = 后续 or hypothesis grade); 相对竞品 and 可改变性 stay blank. That 重要性 caps every slice of the audience inside the 优先级 formula: 中 → at most P2, 低 → P3. Row semantics and the matrix formula: [client-facing-attribute-pool.md](client-facing-attribute-pool.md) → *属性池* and *提示词矩阵*.

**Step 6 — the wording must show who is asking, stated or implied** (Suda 2026-10-23). A segment exists because it changes the candidates, the criteria or the answer; a Prompt filed under it that a generic buyer could just as well be asking gets answered for the generic buyer, so the slice's audience label measures nothing. Most Prompts already carry the identity through what they ask — 「HDB resale flat」 implies a citizen or PR buyer, 「rent a room near NTU」 a student renter, 「my HDB flat is worth」 an owner — and need nothing added. Only where neither the wording nor its condition gives the asker away, add the audience in the buyer's own words (「with three cats」, 「as a foreigner」, 「for a 50-person sales team」). Register both kinds of words — the self-descriptions and the implying terms — from that audience's 买家原话 in `config.audience_terms` (output-contract gate 39). The audience is not a 约束: it is not listed in `constraints` and does not count toward gate 36. Exempt are Verification and Accuracy Prompts (one checkable fact, same answer for every asker) and the per-Topic low-condition anchor (base audience by definition); an implied identity the term list cannot catch is recorded as `audience_implicit` with the reason. This is not the first-person rewrite *Discovery Quality* warns against: that adds a situation which leaves the candidate set unchanged; this states the condition that made the segment a segment.

**Two things this rules out.** One segment per phrasing (citizens vs PRs when both buy the same flats under the same rules), and a "general" or catch-all segment: rows with no narrower condition take the category's base audience. A journey state (「已在比较具体品牌」) is never a segment; it is a stage.

### Priority is set in two passes, never fixed in one

| When | Basis | Nature of the result |
|---|---|---|
| **Before the presales run** | **Importance × changeability**; current gap marked `待测` | **Initial priority** — no current-gap data yet |
| **After the formal baseline** (or once a presales batch has measured the gap) | **Importance × current gap × changeability** — lookup tier, re-judged changeability; the optimisation order is computed in the baseline report from the five competition patterns | Operational priority for the next actions, explicitly provisional about persistence |

The second pass adds an **initial measured gap**, not a stable one. Presales cannot measure it before collection; the baseline runs provide a reproducible starting point but still cannot separate short-term misses from a persistent gap. Confirm persistence through later comparable windows.

**The three conditions follow Profound's attribute prioritisation: importance, current gap, changeability.** Attributes, and the monitoring Prompts that carry them, share them.
- **Importance** (重要性): how much the Attribute matters to the purchase decision — 高 (decides whether the brand gets onto the buyer's shortlist) / 中 (clearly matters to some buyers or specific situations) / 低 (relevant, but does not usually decide the choice). Grade it from the user-language sources in *Customer and Market Signals* (search data, sales records, reviews, community).
- **Current gap** (当前差距, recorded per Prompt as **AI 认知差距**): distance between what AI says now and what we want it to say, judged from each Prompt's own answer text — 知道但不推荐 (AI knows the brand holds the capability but omits or disfavours it; fix off-site signals) / 不知道该能力 (AI does not know the brand holds it; fix on-site description first — the paired Verification Prompt on the same attribute tells the two apart, see *Prompt Priorities*) / 无人讨论 (AI does not discuss this dimension) / 无缺口 (AI already describes it correctly and favourably). The pre-2026-10-22 single value 有缺口 covered the first two. Mention rate alone is not the gap: a brand mentioned in every answer can still be described wrongly. Before that Prompt's own formal-baseline answers exist, mark it `待基线` (the 3-run trial does not fill it); never copy an attribute-level judgement or presales answers onto individual Prompts. Where another company shares or nearly shares the brand's name, measure by the share of answers citing the brand's own domain, not by name occurrences.
- **Changeability** (可改变性): whether what the brand can do itself — publish content, fix the site, supply material, earn third-party reviews — can move what AI says on this Attribute within the service window. Graded 高 / 中 / 低 by the two questions under *How to grade changeability*.

Before collection, read the tier from importance × changeability in the table below; after the formal baseline, re-judge changeability (the selection tier in the Base is not re-opened by it — the optimisation order is computed in the baseline report). **P1 always requires a Prompt that carries the Attribute** — an uncarried row cannot be P1 whatever its cell.

| Importance \ Changeability | 高 | 中 | 低 |
|---|---|---|---|
| 高 | P1 | P2 | P2 |
| 中 | P2 | P2 | P3 |
| 低 | P3 | P3 | P3 |

Only 高 × 高 is P1, so P1 stays a short list; the category-baseline row (empty attribute) is fixed at P1 because it measures which brands AI lists with no condition. **The slice's audience then caps the tier**: an audience whose 重要性 in 属性池 is 中 holds its slices to P2 at most, 低 to P3 (see *Audience Segments* → Step 5). Do not reintroduce numeric weights: only the cell decides the tier, and decimals imply a precision the judgement does not have.

**P1/P2/P3 are this project's tiers, not Profound's.** Profound's AEO Guide also uses Priority 1–3 (chapter 4), but grades them only by how central the Attribute is to the buying decision; and for a gap that cannot realistically be closed it says "park it lower on the list", not drop it. Setting tiers by a lookup on the three conditions, and giving a confirmed capability gap no Prompt, are our own choices — do not cite Profound for either. Sources: https://www.tryprofound.com/aeo-guide/chapter-2 and https://www.tryprofound.com/aeo-guide/chapter-4 .

**How to grade changeability.** Ask in order; the first "yes" sets the grade; two "no"s give 中.

| # | Question | If yes |
|---|---|---|
| 1 | Can the brand not catch up even with material? The product truly lacks the capability or trails on the spec, or the competitor's lead rests on brand awareness or broad media consensus with no concrete fact the brand could match. | 低 (能力缺口 or consensus lead). A capability gap the client confirms has no remedy gets no candidate Prompt; a consensus lead still gets one in round one |
| 2 | Does the brand have the capability (`相对竞品` 领先 or 持平) but it is not written anywhere AI can read? | 高 (证据缺口) — one page or one template fix can move it |
| — | Otherwise: already written where AI reads; 劣势 with a small gap that material can close; `相对竞品` 待确认 | 中 |

Changeability answers one question only — can content move what AI says. Whether the attribute decides the purchase lives in 重要性 (judged once per attribute in 属性池 since 2026-10-22; its 高 already means the buyer drops options that fail it — the former per-slice 购买影响 column restated it and was removed), and how the win ranks against parity lives in the within-tier ordering below; a 2026-10-22 attempt to split this question by 领先/持平 double-counted both and was reverted the same day.

**"Somewhere AI can read" is judged from the site diagnosis report** — the HTML report a colleague produces with the site GEO-readiness skill (a score per dimension: crawler access, technical base, brand recognition and Schema, content quality, content citability; then a P0–P3 fix list). It means statically fetchable text or images on the brand site or on third-party pages AI cites. Numbers that exist only in JS-rendered elements, pages blocked by robots or behind a login, and pages the report marks as blocked or unreadable count as not written; parameters inside images count as written (ChatGPT read them in the 2026-10-10 test). The report samples only a few pages: when the Attribute's landing page is not in the sample, check its static source instead of borrowing the homepage score.

**`相对竞品` is not scored separately; it answers question 1.** It records the **real industry position** (领先 / 持平 / 劣势 / 待确认), judged on the facts from the public layer wherever that can settle it, and **from the client wherever it cannot** — a client knows where its own spec sits in the industry, so never infer `持平` from the mere fact that neither side published. Scoring it again would double-count. 待确认 holds at 中 until the evidence arrives; never downgrade by default.

**Round one excludes only confirmed capability gaps.** Round-one changeability rests on public facts such as official sites and specs and can be wrong, so the initial priority mainly orders the work and allocates Prompts. Low changeability has two sources, handled differently:
- **Confirmed capability gap**: the product really lacks the capability or really trails on the spec, and the client confirms there is no remedy (no bridging course, alternative model or roadmap date). Content cannot move it, so a candidate Prompt would only measure a known loss: give it none, and record the reason in `no_carrier_reason`. Until the client confirms, treat the row as 待确认 and give it a Prompt. Revisit the row when the product changes.
- **Competitor leads on brand awareness or media consensus**: the low grade is a guess about how AI answers, and the answers may not follow the consensus. This is where high-importance directions that look hard turn out to be open, so give every high-importance one at least one candidate Prompt.

Low-importance Attributes may go without a Prompt.

**After the formal baseline, re-judge changeability, then adjust per Prompt for optimisation.** Do not carry the round-one grades forward. Re-judge from the answer layer: if AI cites the brand's own site or third-party pages the brand can influence (review sites, communities, trade media) on this Attribute, changeability is at least 中; if AI rests on awareness or a vague "industry leader" and cites only sources the brand cannot influence, grade it 低; if AI criticises competitors on the theme, raise it one grade. The optimisation order is then computed in the baseline report (below).

**What decides priority, and where each factor acts** (Suda 2026-10-23). The Base 优先级 column is the **selection** priority. The optimisation order after the formal baseline is a separate result, computed in the baseline report (`geo-monitoring` → baseline-report.md → *优化顺序*), never written back into the Base.

| Factor | Who judges, when | Selecting the formal set | Ordering optimisation |
|---|---|---|---|
| Business value (业务目标, audience 优先 marks) | Brand party, at scope confirmation | Yes — through the audience cap on the slice tier | Yes |
| Buyer-demand importance | Us, from buyer evidence, at attribute grading | Yes — slice tier | Yes |
| Changeability | Us, at attribute grading; re-judged after the baseline | Yes — slice tier | Yes |
| 信源壁垒 (来源追不上) | Us, read from the 3-run trial answers; re-checked at the formal baseline | Yes — the only reading that drops a tier | Yes |
| 相对竞品 (real industry position) | Us, attribute research | Yes — within a tier, 领先 before 持平 | Yes |
| The brand's own mention reading (the five competition patterns) | Computed in the baseline report from the 30 runs per cell | **No** | Yes |
| Prompt type | Us | Yes — order in which formal slots are filled | No |
| Question quality and coverage | Us, trial; platform-specific problems at the formal baseline | Yes | No |

**Why the brand's own reading stays out of selection.** Picking the Prompts that happened to read low, then counting their regression to the mean as optimisation, is the failure Peec, Aleyda and Ahrefs all warn about; dropping Prompts the brand already wins would also stop the mention rate from showing what it holds. 信源壁垒 may enter selection because it reads where the recommendation comes from, not whether the brand is mentioned.

**Prompt type orders the formal slots: Discovery, then Alternatives, then Competitor, then the rest** (Suda 2026-10-23). Discovery is the mention-rate KPI and keeps at least half the set (gate 40); Alternatives also returns a candidate list and is read for mention; Competitor names brands and is read for win rate. Prompt type fills slots in this order but never lowers a Prompt's tier. Two exceptions within 其他: an Accuracy Prompt on a fact whose wrong answer changes the purchase, and the paired Verification Prompt step 12 requires, are placed on their own merits. B2B and high-trust categories may move Competitor, Evaluation and Verification up.

**信源壁垒** (Base field; replaced the seven-value 竞争格局 on 2026-10-23, Suda) has three values: 待判 / 来源追不上 / 无. It is filled for Discovery and Alternatives Prompts only; every other type is 无. Mark 来源追不上 when the **recommendation itself** rests on sources the brand has no path into: the leading candidate is such a source (a government portal such as the national housing portal), or the answer's candidate list is built from those pages. Judge it by reading the trial answers, and re-check it on the formal baseline. Competitor official pages, third-party review sites, communities and trade media never count — the brand can get into them. 来源追不上 drops the slice tier by one (P1 → P2, P2 → P3) once (SE Ranking rule, adopted).

**The overall citation share is a flag, not the verdict.** When government sites and encyclopedias make up ≥50% of a Prompt's citations, read its answers before marking 来源追不上: in regulated categories (property, finance, health) AI cites government pages for rules and facts while naming platforms from elsewhere, and the overall share would drop the brand's best Prompts. Hbrand replay: 9 of 23 Discovery Prompts crossed 50% (cea.gov.sg cited for the agent register, hdb.gov.sg for eligibility rules), including four of the five top-tier Prompts on the brand's strongest advantage, Chinese-language support; in only two (T2-D21, T6-D03) does a government portal, the national housing portal, lead the candidate list. Nbrand: no Prompt crossed 20%.

**Within one tier, selection orders 领先 rows before 持平 rows** (Suda 2026-10-22: an advantage AI cannot see moves recommendation once closed; parity only restores mention and a competitor neutralises it with one page) — `相对竞品` is the real industry position from research, not the brand's AI reading. Nothing else orders a tier at selection; Prompts left equal are equal. A weighted 1–3 product (importance × gap × changeability) is deliberately not used, and content effort is not an ordering key (Suda 2026-10-23): whether content can move the answer is already changeability, which sits in the tier.

**The five competition patterns live in the baseline report** (Suda 2026-10-23). 竞品领先 / 部分出现仍落后 / 已打平或领先 / 无品牌点名 / 来源追不上 are computed per Prompt from the formal baseline's 30 runs per cell and used only to order optimisation work; thresholds and ordering are in `geo-monitoring` → baseline-report.md → *优化顺序*. They are not filled by hand in the Base and never change the selection priority.

Therefore: **presales may rank candidate Topics; the after-sales baseline informs operational priority, but neither stage alone promises that an action will work.**

## Stage 2: Topic Planning, Coverage Matrix, and Prompt Generation

**Topics are clustered from where the P1 attributes land** (cross-map at SKILL.md Workflow Step 4). The attribute pool carries `重要性 × 可改变性 → tier` per attribute; that clustering is recorded in `config.topics` before Prompts are written, with `covered_attributes` naming the P1/P2 rows whose landing opened this Topic and `planned_prompts` carrying the count. The validator checks that each P1 attribute is homed in at least one Topic or has a `no_carrier_reason`.

**Coverage matrix slices combine the enumerated skeleton with the attribute pool's tier.** Each 提示词矩阵 row reads 产品线, 受众, 旅程阶段, 约束 (the coverage dimensions), 属性关联 (links to 属性池), and 可改变性 (formula from the linked row); its 优先级 is the lookup on 重要性 × 可改变性, then capped by the audience's 重要性 from 属性池 (see *Priority is set in two passes*). Slices that share every other dimension must still differ in 约束. 目标题数 is filled **before Prompts are written** — default 1, add one per additional buyer constraint wording where the candidate list would change. A slice whose coverage cell stayed empty gets the reason at the start of 备注 (首期不配提示词：重要性低 / 能力缺口 / 低业务优先). **Every 优先级 is published with its reason** — 优先级原因 on 提示词矩阵和 提示词库, a sentence the brand party can read: which attribute, what its importance and changeability mean for the buyer and for content, the 相对竞品 verdict, the audience cap where it applies, and the 信源壁垒 drop on the Prompt. A tier the client cannot explain is a tier they will not accept (Suda 2026-10-23; expressions and the row-by-row consistency check in client-facing-attribute-pool.md → *提示词矩阵*).

**Prompt type decides the analysis contract and is filled per Prompt, never per Topic or slice.** The eight types — Discovery, Competitor, Alternatives, Evaluation, Verification, Accuracy, Category Awareness, Information — have distinct analysis rules and tier defaults recorded in shared/canonical-intent-mapping.md, enforced by the validator. Discovery keeps at least 50% of the candidate bank (gate 40). Alternatives split out of Competitor 2026-10-22; Information added 2026-10-19. Each type's default tier (core / experimental / monitoring) is a **can-override default**, not a lock: the monitoring purpose stated in the generation rules or the brand party's purchase may move a Prompt to a different tier with a recorded reason.

### Topic Rule

A Topic is a business theme worth tracking with an independent long-term metric.
The formal Topic count follows what the customer purchases; the recommended
first-stage shape is one category observation Topic plus two same-product
buying-scenario Topics, and two are acceptable when the product line or
evidence is genuinely narrow. Candidate Topics are not limited in number. Category observation is not a randomized
causal control and may be optimized when it is a real opportunity. It is also
not the `Category Awareness` intent.

#### When to split a Topic: three tests, three checkpoints

**Split when the two halves are two independent competitive situations** — the same test that promotes a qualifier to a Depth Topic (see *An attribute is promoted* below). Three questions; any one hit means split, none means keep:

| 测试 | 问什么 | 例（Mbrand 家用 vs 医用制氧机） |
|---|---|---|
| 竞品集合 | 两半的买家在拿不同的对手比吗？ | 家用对手是 Inogen 这类消费品牌，医用是医院采购渠道的器械商，名单几乎不重叠 → 拆 |
| 评估标准 | 决定选谁的属性清单换了吗？ | 家用看噪音、便携、价格；医用看 FDA 510(k)、流量精度、保险覆盖 → 拆 |
| 优化方向 | 要发的内容、要挣的信源是两套吗？ | 一半上患者社区和 Amazon 评价，一半上行业采购指南 → 拆 |

Counter-example: Hbrand's rental Topic carried 20 candidate Prompts and stayed one Topic — budget, district, school zone and short-lease are constraint variants inside one competitive situation (same platforms, same criteria, same content landing). Many Prompts is not many situations.

Run the tests at three checkpoints:

1. **At clustering** (P1 landings → candidate Topics): the pool's 判据与证据 and `相对竞品` already name each P1's competitor set and evaluation standard — check whether the P1s inside one candidate Topic are homogeneous on those two columns. An obvious two-situation cluster (Mbrand above) is split here.
2. **At formal-set selection** (after the trial, the decisive checkpoint): the brand party picks at most 10 formal Prompts per purchased Topic by attribute priority — that pick is the test of whether one Topic holds the coverage. We do not pre-split at quoting time on an intent count: candidate Topics carry **no cap on Prompts or intents**, and predicting "your coverage won't fit" for the client is our inference overriding their call (Suda 2026-10-22). Only when the brand party cannot get under 10 without dropping intents it genuinely needs — or says so — propose splitting into a second purchased Topic; the units are the **independent purchase decisions** left over (the dedup yardstick: same candidate set, same comparison dimension, same answer-changing condition = one intent), not the Prompt count.
3. **From the answers — the trial first, confirmed on the formal baseline**: the answer layer shows it — when two groups of Prompts under one Topic surface two clearly different competitor lists (per-cell top3), that is test 1 showing up in data; split so each half's mention rate means something. This evidence also feeds checkpoint 2's conversation.

Signals that do **not** justify a split: a difference that is only a constraint (budget tier, household size) stays in the slice's 约束 column; only an audience, with competitors and criteria unchanged — multi-select 受众; only language or market — the 市场 field.

Every candidate Topic needs at least five independent Prompts before it
enters the trial; a hypothesis draft may temporarily have fewer,
but must be marked for evidence completion. Do not fill them with synonymous
rewrites: merge them, keep them as Tags, or report the evidence gap if five
independent intents cannot be supported. Prompt counts are deliberately
variable and Topic counts may differ. Candidate Topics are open-ended in
number, each carrying at least five Prompts; formal Topics follow the
purchased count, with a lower bound of five Prompts per Topic and **at most 10
formal Prompts per purchased Topic** (the deliverable); the candidate set may
be larger.
Ten or more genuinely distinct important intents in one Topic is a split
**signal**, acted on only when the brand party cannot pick its 10 formal
Prompts without dropping intents it needs — never a candidate-stage cap and
never a pre-quote auto-split (see *When to split a Topic* above).
Weight the counts, do not equalise them: the
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

### Prompt Priorities

1. **Discovery:** natural non-branded candidate discovery and the main visibility opportunity.
2. **Evaluation:** a specific attribute, scenario, or decision standard that can guide content/action.
3. **Competitor (客户标签 对比; 2026-10-23 从「竞品对比」简化, 2026-10-22 从「竞品」改出 — 列里没有第二种对比, 「竞品」二字不供区分; 本品必须一方的边界由定义守, 不由标签名守):** one-to-one comparison only when a real competitive opportunity justifies it. The target brand is always one side; a comparison between two competitors that leaves the brand out says nothing about it and is never written (Suda 2026-10-19). Read for win/loss and sentiment. **A Competitor Prompt must carry a concrete use case** — its `constraints` list is non-empty and names the scenario the verdict hinges on; without one AI answers "it depends" instead of picking a side (Profound ch3, adopted 2026-10-22). The validator fails a selection-stage Competitor Prompt with no constraints. Win rate is reported as two numbers — over all answers, and with ties stripped (Profound's worked example: 58% overall, 74.4% once answers where neither brand is clearly favored are removed); the tie-stripped number is the one to watch.
4. **Alternatives (客户标签 替代, split out of Competitor 2026-10-22, after-sales only):** asks for alternatives to a named competitor (「best alternatives to [leader]」), where the brand can appear in the answer list. Its natural reading is **提及率 within the alternatives list** (called 列入率 before 2026-10-23) — in how many of the 5 runs the brand is listed among the alternatives, and where — plus sentiment; win/loss framing does not apply because the brand is not one side of a comparison. 列入≠推荐: the listing feeds the mention layer only, the recommendation caliber stays separate. This 提及率 is reported on its own line; whether it counts toward the mention-rate KPI is undecided (Suda 2026-10-23): banks default to `formal_visibility_eligible: false` until it is settled, and the validator accepts either value. The case against counting it: the wording plants a competitor name and conditions the answer set. Non-branded alternatives questions stay Discovery as before. Evidence-gated like everything else, and the leader-default rule still bars 「alternatives to [leader]」 where buyers do not ask it. Same layer and cadence as Competitor (monitoring/experimental, never core; trialled during attribute research; may be bought into the formal set). Banks written before 2026-10-22 keep such Prompts typed Competitor — do not migrate; the validator accepts both on the 替代方案 stage.
5. **Category Awareness:** low-frequency observation; refresh only for a new concept, trend, or changed buying standard.

After-sales uses the six presales intents — `Discovery`, `Competitor`,
`Evaluation`, `Verification`, `Accuracy`, and `Category Awareness` — plus two
after-sales-only additions: `Alternatives` (替代, split out of Competitor on
2026-10-22, see item 4 above) and `Information` (信息, Suda 2026-10-19): a buyer's own
policy, process, cost, rights or dispute question that AI answers with advice
rather than a candidate list ("Should I take an HDB loan or a bank loan for a
resale flat?"). Its answers are read for one thing: whether the brand's domain is cited
(Suda 2026-10-23; mention rate is not read for this type). Set
`analysis_type: visibility` and `formal_visibility_eligible: false`; no
sentiment. In the formal baseline every selected Prompt, Information and named-brand ones included, is counted in the baseline report (HTML, built by geo-monitoring; see its baseline-report.md) with no split by intent (Suda 2026-10-20). The formal-set mention-rate KPI still counts Discovery only, and `formal_visibility_eligible` stays `false` — the field governs the formal stage only. It differs from Category Awareness (how to choose a product or provider)
and from Verification / Accuracy (facts about the brand). Like any Prompt it
needs real buyer demand evidence, a niche audience included; whether the brand
already has content on it does not decide inclusion. Only an Information
question whose answer leaves the buyer a next step the brand's product serves
(finding, buying, selling or renting a home through a platform or agent, for a
property portal) goes into the Prompt bank; one the answer fully settles, or
whose next step belongs to a bank, lawyer or government body, is not written as
a Prompt at all — record it with its reason in `config.parked` (Suda
2026-10-19). It belongs to the `experimental` layer (Suda 2026-10-20). Information
Prompts in the bank go into the trial; once selected, one whose formal-baseline answers neither cite the brand's domain
nor name any platform across its formal-baseline runs stops being monitored. By default they
stay out of the formal set; the brand party may buy them in, and the
mention-rate KPI counts Discovery only either way. Outside the formal set they
are re-run only on a trigger after the formal baseline. An Information answer that names the brand
or points the buyer to a platform is a real optimisation opportunity — it shows
where an advice page can carry the buyer into the product — even though the
number itself never joins the visibility rate.
`Verification` and `Accuracy` are **two distinct intents**, divided by what AI
gets wrong (Suda 2026-10-16). Verification asks whether AI recognises that the
brand holds a specific capability — the failure is that AI does not know the
brand has it. Accuracy asks whether a fact AI can already state is right — the
failure is that AI states it wrongly. A capability check ("Does Pbrand offer
X?") is a Verification Prompt, not an Accuracy Prompt. Neither is a default
after-sales Prompt: use them only through the gates in *Topic and Attribute
Selection Criteria*.

**Pair a Verification Prompt with every low-reading P1 Discovery direction
(Profound AEO Guide ch3, adopted 2026-10-22).** When a P1 attribute's Discovery
Prompts read low mention at the trial, the formal set must carry
one Verification Prompt on that same attribute ("Does {brand} offer
{capability}?"). Its answer splits the gap into two diseases with different
prescriptions — AI knows the brand holds the capability but does not recommend
it (build off-site signals: third-party citations, reviews, authority), or AI
does not know the brand holds it at all (fix on-site description and
documentation first): "These are completely different programs of work, and
without validation prompts, you can't tell which one you need." Record which in
提示词库 AI 认知差距 — the old single 有缺口 value is split into 知道但不推荐
and 不知道该能力 (2026-10-22); 待基线 / 无人讨论 / 无缺口 are unchanged.

**After the split, a Verification Prompt stays in periodic monitoring only if
AI does not yet confirm the capability** (Suda 2026-10-23). Its first job — telling
知道但不推荐 from 不知道该能力 — is done once the formal baseline (or a
supplementary run) has read it; re-asking every period adds cost without a new
decision. Read each answer (confirmed / partly / denied / unsure):

- AI confirms the capability in at least 80% of answers (e.g. 12/15): the gap is
  知道但不推荐. The Prompt leaves periodic collection and is re-run only on a
  trigger — the brand changes or launches the capability, the official page is
  rewritten, a same-name brand surfaces, or the quarterly review.
- AI confirms it in fewer than 80%: keep it in the monitoring layer. It is the
  reading that shows whether the on-site fix (a clear official page AI can
  actually crawl) reached the AI, so it runs every period alongside the paired
  Discovery Prompts.

Either way it never enters the mention-rate KPI. Hbrand 2026-10-23: CEA-only
listings 12/15, whole HDB and landed rentals 15/15, new launches 12/15 → trigger
only; fake-listing checks 7/15, area guides 9/15, resale eligibility guides 2/15
→ monitoring layer.

**Which monitoring task each intent carries, and which statistic it feeds.**
The analysis type follows from the intent; there is no separate field for it.
The Chinese name is the client Base 提示词库 提示词类型 value.

| Prompt type (提示词类型) | Task it carries | Success shape | Feeds |
|---|---|---|---|
| Discovery (发现) | Does AI recommend the brand when a buyer explores the category | Returns a provider/platform list; needs a candidate-noun trigger | visibility, sentiment |
| Competitor (对比) | Whom AI picks in a head-to-head, or what it offers instead of a named option | Returns a verdict, not a both-sides answer; needs a use case and a comparison ask | sentiment (win rate reported with and without ties) |
| Alternatives (替代) | Whether AI lists the brand among alternatives to a named competitor | Returns an alternatives list the brand can appear in | 提及率 within the alternatives list (own line; KPI inclusion undecided), sentiment |
| Evaluation (评价) | How AI appraises the brand or a competitor on a stated scope | Returns an appraisal; this is where sentiment is read per attribute | sentiment |
| Verification (验证) | Whether AI knows the brand holds a specific capability | Returns a yes/no with grounds; pairs with same-attribute Discovery to split the gap | AI 认知差距 (知道但不推荐 / 不知道该能力) |
| Accuracy (准确性) | Whether a brand fact AI states is right | Returns the fact; checked against the confirmed official source | 事实准确（复测表） |
| Category Awareness (品类认知) | What criteria AI tells buyers to choose by | Returns a criteria list; calibrates the attribute matrix | reference only |
| Information (信息) | Whether advice answers cite the brand's domain | Returns advice, not a candidate list | 引用 only (no mention rate), never the mention-rate KPI |

**Evaluation wording.** Two wordings test the same decision; pick one per Prompt, never both: the buyer's wording `Is {brand} a good {category} for {scope}?` and the report wording `Evaluate the {category} company {brand} on {scope}`. Default to the report wording (Suda 2026-10-22): it reads how AI appraises the brand in full, including regulator and recall records. Use the buyer wording only when the task is explicitly to read the short answer a buyer would see. They return different answers (2026-10-22, ChatGPT + Gemini US, 4 brands × 3 runs): the report wording averages 1072 words, cites more sources and surfaces regulator and recall records (Swisse recall in 3/3 ChatGPT answers); the buyer wording averages 599 words, gives a direct verdict, compares against other brands more often (1.6 vs 0.6 named) and did not raise the Swisse recall (0/3).

**Named-competitor alternatives.** A Competitor Prompt may ask for alternatives to one named competitor without naming the target brand (`What are the alternatives to [competitor] for [scope]?`), at most one per Topic and only when evidence shows buyers hold that competitor as a current option. It reads the buyer's real candidate set rather than a head-to-head verdict.
| Verification (验证) | Whether AI even knows the brand holds a specific capability | One checkable answer per capability, scored against the client-confirmed answer; distinguishes a comprehension gap from a trust gap | neither visibility nor sentiment |
| Accuracy (准确性) | Whether a fact AI can already state about the brand is right | One checkable answer, scored against the client-confirmed answer; only for rows that pass the accuracy gate | accuracy |
| Category Awareness (品类认知) | How AI frames the category — what to look for, which criteria decide | Buying criteria, category framing and comparison dimensions; read whether our P1 attributes appear among the criteria and which guides AI cites | neither visibility nor sentiment |
| Information (信息) | Whether AI cites the brand's pages when a buyer asks a policy, process, cost or dispute question | Advice rather than a candidate list; read whether the brand's domain is cited | citation only; runs in the trial with every other Prompt; once selected, in the formal baseline, outside the formal-set KPI |

Sentiment is read only on Prompts whose intent feeds it; it is never inferred
from Verification, Accuracy, Category Awareness or Information answers.

**Reading a capability Verification Prompt against its Discovery Prompts.** When
the capability is tied to an attribute that Discovery Prompts also test, read
the two together (Profound's validation diagnostic):

| Discovery on that attribute | Verification answer | Diagnosis | Action |
|---|---|---|---|
| brand absent | AI confirms the capability | trust gap — AI knows but does not recommend | third-party reviews, citations, off-page descriptions |
| brand absent | AI denies or does not know it | comprehension gap — AI has not linked brand and capability | own pages and structured documentation stating it |
| brand present | AI confirms | goal state | no fix |
| brand present | AI denies | inconsistent signals | investigate before acting |

Ask one capability per Prompt in yes/no or single-answer form ("Does [brand] [capability]?"); an open "what can [brand] do" question cannot be scored. Write the diagnosis into the gap-cause-action table.

Our Evaluation covers both Profound's `Sentiment` and its appraisal prompts; Verification covers Profound's `Validation`; Accuracy covers its `Accuracy`; Category Awareness covers its `Market Perception`.

**Category Awareness in after-sales.** Add one or two per product line, on the
journey stage 发现, in the `experimental` layer, with `formal_visibility_eligible:
false`. Ask how to choose ("What should I look for when choosing an automatic
litter box for multiple cats?"), never how to fix or use something — how-to and
troubleshooting questions return advice without criteria or brands. When such a
question carries real buyer demand and the brand wants its pages cited, write it
as an Information Prompt instead; otherwise its content-topic value is already
captured by fan-out sub-queries and People Also Ask at no collection cost. They go through the same trial as every other Prompt, run while the attribute pool
is still being judged, alongside Competitor and Accuracy Prompts (see
representative-library.md → *Roles and Refresh*).

The first staged set is `Discovery`, plus any demand-backed `Information` Prompts: lock the Discovery group first, then add
Competitor, Evaluation, Category Awareness, Verification, or Accuracy as the
situation requires, each only when its separate business question and evidence
contract are present; none has a fixed quota. The reference
distribution — six to eight Discovery Prompts out of about ten, with the
remaining two to four spread across the other intents by actual need — describes
that later allocation, not a first-set quota, and never justifies adding a type
to fill a slot.

### Discovery Quality

Discovery is the formal visibility population. It must be a natural commercial recommendation or selection question:

- no target brand or competitor names;
- category is recognizable;
- one main decision;
- enough buyer context to produce named providers or platforms;
- no pure methodology, trend, or educational question unless a separate problem-awareness track is explicitly requested;
- **the wording must ask for candidates** — which / best / top / recommend / options / alternatives / where to buy or source. A "How do I fix X" question gets advice back and no brand list: Pbrand's "How do I get rid of litter box smell in a home with multiple cats?" returned zero brands in 5 of 5 ChatGPT US runs (2026-10-15), while the same need asked as "Which automatic litter boxes seal in odor best between bag changes?" listed brands every run. The validator fails English Discovery Prompts without a candidate ask. A problem-awareness Prompt kept on purpose is set `formal_visibility_eligible: false` so it stays out of the visibility statistic and passes the gate;
- **match the real distribution of user wording, and do not default to "concise"**: a large share of delegated, long-form questions is expected (measured user prompts run to a ~20-word median, delegated questions about 37%, keyword-style only about 3%). Mix short direct questions with questions carrying a buyer, scenario, or constraint, in roughly the proportions real users produce;
- **do not rewrite an existing "Which …" Prompt only to make it sound more personal.** Adding a first-person situation that carries the same decision ("I travel a lot for work. Which automatic litter box lets me check…") did not move target-brand mention in a 2026-10-15 ChatGPT US test (Pbrand, 6 pairs × 5 runs: 63% → 50%, Fisher p=0.44), but the answers named fewer brands (one pair 4.2 → 2.2 on average), so long-tail competitors drop out of the competitor reading. Add a buyer situation when it changes the expected candidate set (a condition slot below), not for tone — which is exactly why a Prompt filed under a non-base audience must name that audience (*Audience Segments* → Step 6). Tested on ChatGPT only; re-test on Gemini and AI Mode before applying the same conclusion there;
- **mix the question openings; do not default to "Which …".** "What are the best …" is how much of the category is searched and how Profound and Aleyda write their discovery examples, and it does not shorten the answer: in a 2026-10-16 ChatGPT US test (Pbrand, 6 pairs × 5 runs, same conditions, only the opening changed) answers named 3.70 → 3.67 brands on average (paired t=-0.15) and target mention went 83% → 87% (Fisher p=1.00). When drafting new Discovery Prompts, use "Which …", "What are the best …" and "… recommend" side by side; this is not a reason to rewrite locked Prompts, and a "best" variant of an existing Prompt is a near-duplicate (see Topic-level rules). Tested on ChatGPT and one category only;
- **status-quo alternatives, service categories only.** When the business model is B2B or the category is delivered as a project, subscription or labour service, a Topic may carry at most one Prompt for buyers leaving the status quo (in-house, manual, current setup). Write the status quo as a condition and still ask for providers: `Which [category] providers can a company use instead of [current way]?`. Do not write `What are the options besides handling [X] in-house?` — AI answers with a list of approaches and names brands only in passing (2026-10-22 ChatGPT US: the marketing pair named 0 brands that way and 6 the provider way). It is a different decision from choosing among providers, so it is not a near-duplicate of the category entry Prompt. Physical goods and hardware do not get one; their buyers do not face a build-or-buy choice.
- **a superlative opening needs no generic noun.** `Best dash cams for rideshare drivers` asks for candidates; both validators accept best/top followed by a plural product noun and still reject `best ways / practices / tips`.
- no redundant containment wording, such as a broad region plus a subregion that is already included;
- classify every qualified Prompt into one of the four condition slots used by 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」, and keep those names: **无限定条件** (no qualifier), **目标用户** (target user), **偏好标准** (preference criteria), **约束** (constraint). Pain points sit under 偏好标准 — they are a dimension buyers weigh while comparing, not a fifth slot. Retain a mix across the four whenever the condition changes the expected candidate set.

Topic-level rules:

- each candidate Topic has at least one natural no-qualifier (无限定条件) Discovery Prompt;
- **Coverage and Depth follow different combination rules, and mixing them is an error.** A Coverage (宽泛) Topic's Prompt carries no condition or at most ONE low-complexity main condition, and must NOT combine target user, preference criteria, and constraint. A Depth (细分) Topic's Prompt may carry one condition or several, and the group must systematically contain meaningful compound Prompts — the same question joined with two or more conditions that genuinely change the choice. Not every Prompt needs to compound, there is no fixed sub-quota, and stacking conditions to look thorough is prohibited;
- compound conditions are allowed for a genuinely narrow scenario, but must change the candidate set or recommendation;
- do not create near-duplicate Prompts by changing only adjectives, word order, or “best/top/recommended”.
- **changing only the category's name is a legitimate variant, not a near-duplicate** (Profound, adopted 2026-10-22: synonymous category phrasings moved visibility by 25–50 pp in its measurements). When evidence shows buyers search the same category under several names, keep one Prompt per name and register the synonyms in `config.category_aliases` (a flat list of phrases); the validator exempts a Prompt pair whose only wording difference is tokens from that list. Every other rewording-only pair still merges.
- dedupe by **purchase decision**, not by wording. Two Prompts that resolve the
  same decision (same candidate set, same comparison dimension, same condition
  that changes the answer) are one Prompt, however differently they read; only a
  change of buyer, region, scenario, or decision stage makes a new one. Normalised
  text uniqueness only catches synonym and word-order rewrites, so near-equivalent
  phrasings must be merged on human review.
- stop expanding a Topic once its evidence-backed important decision focuses
  are covered; a longer list is not evidence of better monitoring.

**Natural visibility uses Discovery Prompts only.** Named-brand Evaluation,
Competitor, Verification, and Accuracy results are read separately and never enter the
natural-discovery statistic. Keep one identical wording when several brands must
be evaluated. A Discovery Prompt scoped to a specific attribute — "which
enterprise travel platforms have good customer support" — is still Discovery; a
specific attribute does not by itself make a Prompt an Evaluation.

### Field Semantics

Every Prompt has:

- `Topic`: one stable business theme.
- `Region`: the market being monitored, such as `Global`, `United States`, or `Singapore`.
- `Prompt type`: one of the after-sales prompt types: Discovery, Competitor, Evaluation, Verification, Accuracy, Category Awareness, or Information.
- `Tags`: **optional, and kept short.** Leave it empty unless a tag carries a dimension the other fields do not — typically an attribute, a buyer role, or a use case. Do not repeat `Region`, `Prompt type`, or `Topic` in Tags, do not prefix a value with its field name (`属性:`), and use the bare name rather than a phrase.

## Stage 3: Trial (Each Candidate Prompt × Each Monitored Platform × 3 Runs)

**The trial is quality validation plus exploratory diagnosis, never an early baseline** (Suda 2026-10-22 / 2026-10-23, adopting Profound's pre-tracking answer check, Aleyda's small-batch validation and Momentic Atlas's 3 platforms × 3). Every candidate Prompt runs 3 times on **each platform the engagement will monitor**, 5 at most per platform; each run is a separate, history-free session with the market, language, platform mode and collection method fixed — never the same conversation asked three times. A platform that cannot be collected in the market is left out. Competitor, Category Awareness and Accuracy Prompts go through the same trial, run while the attribute pool is still being judged, because their answers settle `相对竞品` and changeability; an Accuracy Prompt is scored only after the brand party confirms the right answer. These types take no formal-set slot unless the brand party buys them in.

Check the market coverage pass first. Then read each answer for five things: whether AI understood the category and intent; whether the answer task matches the prompt type (Discovery returns named candidates, Competitor returns a verdict rather than "it depends", Verification recognises or denies the capability, Information gives advice); whether the answer reaches the target segment rather than the broad category; whether it is substantively identical to another Prompt's answer with no new decision inside; and whether repeated runs and platforms agree. Judge per platform:

| What the three runs show | Action |
|---|---|
| All pass the checks | Keep; done |
| Two or three fail the same way (a Discovery Prompt turns into an explainer, AI answers a different category) | Reword or cull — the failure is the wording |
| Only one fails, or the runs disagree on intent, category or answer type | Run two more on that platform (five in total); reword only if at least three of five fail, otherwise keep and mark 高波动 — no further runs |
| Category and intent right, but the brand list changes a lot between runs | Keep without rewording; mark 高波动 |
| Only one platform fails (answers a different category, never triggers an AI Overview, refuses) while the others pass | If the wording causes it, reword and rerun on every platform; if it is the platform's behaviour, keep the Prompt and record that platform as excluded for it, with the reason |

A misread or mismatch is reworded or culled; an unsegmented answer is reworded first; a same-answer pair goes back through the dedup rule. A 高波动 mark goes in the internal diff; it tells the formal baseline to read that Prompt's runs with care, and it is never a reason to cull. Record reworded and culled Prompts with reasons in the internal diff.

**Brand mention — present, absent, competitor-only — is never a trial verdict.** An answer recommending competitors but not the brand is kept (that is the opportunity), and a stable brand presence is not a reason to cut. Do not let trial answers pick the Prompts most likely to show improvement — the selection input stays attribute priority and buyer evidence (sample-selection bias poisons every later delta; Peec's 2026-09 finding: representative Prompt coverage beats more runs of the same questions). **Whether a direction can be moved is the changeability condition, not a reason to drop a Prompt**: a competitor advantage resting on brand awareness or broad media consensus gets no Topic of its own and no promise of improvement (see *Topic and Attribute Selection Criteria*); a single or zero mention never enters that judgement.

**What the trial produces:**

1. **`prompt_validity` per Prompt** — 合格 (wording fits the intent and category, answer on-task, no ambiguity or duplication) / 修改 (reword and rerun) / 淘汰 (merge or drop). Two or three runs failing the same way means reword or cull; one failure or disagreeing runs adds two runs (five at most — reword only at three of five, otherwise keep and mark 高波动). **Target-brand mention is never a pass/fail criterion** — a valid 0/3 Discovery Prompt is kept.
2. **`信源壁垒` per Discovery and Alternatives Prompt** (待判 / 来源追不上 / 无), read from the three runs' answers and cited sources; every other type is 无. Re-checked on the formal baseline. The brand's own mention position is not recorded in the Base.
3. **Exploratory readings as transparent context**: brand and competitor mention counts, positions in the answer, cited sources, query fan-out. These readings are shown to the client as diagnosis columns; they never enter a statistic, never drive selection, and are never treated as a stable mention rate.

**A reworded Prompt is rerun; its new readings replace the old.** Trials where the Prompt text changed are not concatenated. After the trial, each candidate Prompt has `prompt_validity`, a 信源壁垒 value, and exploratory readings retained in `trial.evidence_refs`.

## Stage 4: Opportunity Ranking and Client Selection

**Selection reads buyer importance (the slice tier), adjusted once only by a confirmed 来源追不上 barrier** (Suda 2026-10-23). Trial readings are shown as transparent information columns for the client to see; they do not drive the recommendation order. The rule this enforces: picking Prompts that happened to read low, then crediting their regression to the mean as optimisation, is the failure Peec, Aleyda and Ahrefs all warn about; and a brand's own trial mention rate is exactly that reading.

**What may adjust the tier in selection:**

- **信源壁垒 = 来源追不上** (down one tier): a Prompt whose recommendation itself rests on sources the brand has no path into — the leading candidate is such a source (a government portal), or the candidate list is built from those pages. Judged by reading the trial answers; a ≥50% government/encyclopedia citation share only flags the Prompt for that read, since in regulated categories AI cites government pages for rules while naming platforms from elsewhere. SE Ranking rule, adopted. Competitor official pages and third-party review sites never count — they are reachable.
- An answer that names no brand at all is a wording check in stage 3 (does the Prompt really ask for candidates?), not a tier adjustment.

**What does NOT adjust the tier in selection** (Suda 2026-10-23):

- The brand's own mention rate — neither 0/3 nor 3/3 changes whether the Prompt is recommended.
- How far the brand trails or leads — that reading is computed in the baseline report and used only for optimisation ordering.
- AI 认知差距 (知道但不推荐 / 不知道该能力 / 无人讨论 / 无缺口) — judged per Prompt from its own answer text, marked `待基线` until the formal baseline, never used to drop a Prompt.

**Formal slot filling order: Discovery (at least half), Alternatives, Competitor, then the rest** (Suda 2026-10-23). Prompt type orders slots but never lowers a tier. Within one tier, 领先 rows go before 持平 rows (相对竞品); trial readings do not order a tier (Suda 2026-10-23).

**At most 10 Prompts per purchased Topic enter the formal set.** The brand party picks among 已批准 Prompts. When it confirms, lock the set: the selected Prompts move to 状态 **正式** and every other candidate to **停测** (Suda 2026-10-23 — 正式 means "in the formal set" and is set at lock, not after the baseline, so monitoring knows exactly which Prompts to collect). Save the immutable version, lock the assessment scope (Stage 5), and hand both to `geo-monitoring` for the formal baseline and periodic collection.

### The final deliverable table

The working output is one reconciled master table, not a separate attribute table plus a separate intent table. The customer-facing confirmation document may still show separate sections for readability (品牌事实, 属性池, 主题与问题) as specified in [client-facing-attribute-pool.md](client-facing-attribute-pool.md); before delivery, reconcile them back to the master relationship. Its reference shape:

`优先级 | 品牌属性 | 客户问题与场景 | Topic | Query | Query 类型 | 选择理由`

This shape is a reference, not a validation checklist — a deliverable is not wrong for arranging columns differently, only for violating the rules below. Do not add columns that carry the same information twice: attribute explanation and evidence live inside 选择理由 or the attribute pool's 备注/还缺什么 columns, so a separate 属性说明与证据 column is redundant. Column naming (Prompt vs Query, Chinese vs English headers) is free as long as one document uses one term consistently.

- **品牌事实 stays a separate table up front** (brand, domain, business model, category, ICP, target customer, geography, applicable boundary) — it is confirmed once for accuracy, then not revisited.
- **品牌属性 and 客户问题与场景 stay adjacent but are never merged.** The entire act of translation lives in the gap between them; merging them silently asserts "attribute = intent", which is the failure this section exists to prevent.
- **Reconcile the intent pass against the Prompt set in both directions before delivery.** Every P1/P2 intent must be carried by at least one Prompt, and every Prompt's intent must exist as a row in the client's intent table. The two drift apart easily — the intent table is usually drafted from impressions while the Prompts are derived from attributes, and nothing in the derivation catches the mismatch. Make the master table's intent column **quote the intent table verbatim** so an edit to one flows into the other, and run the reconciliation as an explicit step rather than by eye.
- **In the Base the brand party edits cells directly and marks 状态 on 提示词库; there is no 客户确认 column** (Suda 2026-10-15; we snapshot before sending and diff on collection). **Document-format pieces carry a 客户确认 column, and its convention is write-what-to-change.** The client writes only in the rows that need a correction, a deletion, or an addition, and leaves every other cell blank — never an all-rows "confirmed" reply, and never a per-row 确认 that has to be filled in for the table to count as reviewed. Question numbering stays out of the client document entirely.
- **选择理由 carries answer-layer evidence only** — a fixed pattern such as "competitors are negatively mentioned on this theme (Stera 33%, RivalA1 0%), we are at zero" — never free-text reasoning, which gets pulled around by "the client says this matters".
- **P3 attributes stay visible in the attribute table but receive no Prompts.** Only P1/P2 attributes carry Prompts; verify this before delivery.
- A paraphrased row nobody can source is tagged **待验证** rather than quietly kept.
- Use empty cells rather than merged (rowspan) cells down a column, because the client edits the table in Feishu and merged cells misalign when rows are inserted or deleted.

### The consolidated master table

The end of the whole chain is one table. **The reference shape** — the reference shape only, per the note above:

`优先级 | 主题 | 主题类型 | 核心属性 | 限定属性 | 问题 | 来源依据 | 售前结果 | 正式基线 | 是否正式优化`

**Keep the 售前结果 and 正式基线 columns side by side.** They make the two-pass priority auditable: the latter supplies an initial reading rather than proof that a gap is stable.

**核心属性 and 限定属性 are two roles, not two trees.** The core attribute is the perception that makes the Topic worth watching on its own; the qualifiers are the pool attributes relevant to this Topic that change how a question is asked. Once an attribute is selected as a core attribute it stops also serving as a qualifier. Selecting the core attribute is the first layer; picking qualifiers is the second, and the second layer is a **filter, not a re-rank** — it asks only "is it relevant?" and "is it worth a share of the query budget?", and the same attribute may take different tiers in different Topics without the pool being re-sorted.

**限定属性 fall into four slots, named as in 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」**: 无限定条件 (no qualifier) / 目标用户 (target user) / 偏好标准 (preference criteria) / 约束 (constraint). Pain points belong under 偏好标准 — a dimension buyers weigh while comparing, not a fifth slot. Coverage and Depth Topics follow different combination rules and mixing them is an error: a Coverage Prompt carries no condition or at most one low-complexity main condition and must not combine slots, while a Depth Topic may compound two or more conditions that genuinely change the choice.

**「是否正式优化」 is filled by us after the baseline**, never by the client. The baseline result can justify an initial action with uncertainty recorded; it cannot certify a stable gap. Leave the column blank during presales rather than writing a placeholder.

**An attribute is promoted from qualifier to its own Depth Topic** when it would form an independent competitive situation: a materially different competitor set, a changed evaluation standard, or a wholly different content strategy. That is the same clustering test that governs Topic boundaries — competition set or evaluation standard differs, so split.

## Stage 5: Formal Baseline (Each Query × Each Platform × Each Country × Each Language × 30 Runs)

**The formal baseline is the Before benchmark** (Suda 2026-10-23). Multi-platform collection runs only after the client confirms the formal set, at **30 runs per query per platform per country per language** (Suda 2026-10-23, raising the earlier 5–10). The sampling unit is stated in full so no N-round multiplier is implied: query × platform × country × language = one cell, 30 independent runs in it. Whether those 30 are split across days is undecided (Suda 2026-10-23) — decide per engagement and record it in `collection_config`, because a spread window measures a different thing from one sitting; until decided, run in one sitting and say so in the report. This is the reproducible initial measurement against which later windows are compared. It produces:

- Formal per-platform visibility and citation readings.
- Re-judged changeability from the answer layer (if AI cites the brand’s own site or influenceable third-party pages on this Attribute, changeability is at least 中; if AI rests on awareness or cites only sources the brand cannot influence, 低; if AI criticises competitors on the theme, raise it one grade).
- 信源壁垒 re-checked on the pooled baseline answers.
- Each Prompt's competition pattern (five values) computed from the 30 runs per cell, and the optimisation order derived from it (baseline-report.md → *优化顺序*); the Base 优先级 stays the selection priority.
- AI 认知差距 per Prompt (知道但不推荐 / 不知道该能力 / 无人讨论 / 无缺口), judged from each Prompt’s own answer text.
- Provisional optimisation order and a feasibility assessment for the delivery commitment.

**Where a P1 attribute’s Discovery Prompts read low mention, the formal set must carry one Verification Prompt on the same attribute** (Profound ch3, adopted 2026-10-22) — its answer splits the gap into 知道但不推荐 (off-site work) vs 不知道该能力 (on-site work). Once it has split the gap it stays in periodic monitoring only while AI confirms the capability in fewer than 80% of answers; at 80% or more it is re-run only on a trigger.

**The baseline establishes an initial Before benchmark, not proof that a gap is stable** — stability is confirmed through later comparable windows in stage 6.

### Assessment scope lock (考核口径锁定)

Before the formal baseline runs, lock four things and record them in `config.assessment_scope` (Suda 2026-10-23; a contract measure must not move after the Before reading exists):

- **the KPI Prompts** — the Discovery Prompts in the formal set; Alternatives stay out until their KPI inclusion is decided, and no other type is ever in;
- **where and how often** — platforms × markets × languages, 30 runs per cell, and whether the runs span days;
- **the denominator** — the brand lexicon mentions are counted against (target brand, configured competitors and the open lexicon, as the report builder defines it);
- **the calculation** — mention read from the answer body without citation labels or image captions, valid runs only, failures never zero, and whether platforms are pooled or reported separately.

The brand party confirms the scope together with the formal set. A later change to any of the four starts a new version, is reconfirmed by the brand party, and its series is never joined to the old one; a commitment is measured within one version.

### Versioning and baseline anomalies

**Baseline anomalies.** When the formal baseline shows a Prompt is wrong for a
platform, only a semantic, category or platform-fit error justifies changing
it: set the old Prompt 停测, open a new question_id in a new set version, record
the reason, get the brand party to reconfirm a substantive change, and re-collect
the affected cells. The brand not being recommended, or Google AI Overviews not
triggering, is never a question-quality failure. Use only observed valid samples; failures are not zeroes. The
baseline establishes an initial benchmark, not statistical stability. This skill emits the plan; it does not execute crawling
unless explicitly requested.

An added, deleted, or reworded Prompt starts a new set version and a separate
formal baseline for its affected market/group. Preserve IDs, evidence
references, and history, but do not concatenate old and new set-level windows.
Unchanged common Prompts remain comparable on their own.

When comparison is useful, a baseline observation group uses Discovery Prompts
sampled at the same cadence as its comparable group. It is not automatically a
causal control and does not need a fixed size. Do not confuse it with
low-frequency Category Awareness, and do not forbid optimizing the category
observation Topic.

## Stage 6: Optimisation and Continuous Monitoring

Content and page optimisation based on the baseline diagnosis. Prompts in 状态 = 正式 run each period under the contracted cadence; the formal set’s mention rate is the KPI. Same-question, same-condition, same-caliber window comparison establishes whether gaps are persistent and whether optimisation improved them. Single-day comparisons and immediate-effect promises are not supported by the data.

Optimisation work follows the order computed in the baseline report (tier, then competition pattern, then 领先 before 持平; geo-monitoring baseline-report.md → *优化顺序*); actions are handed to the content team as a gap-cause-action table. `geo-monitoring` owns the cadence, re-run triggers, and the ongoing analysis.

### Maintenance

After-sales is a dynamic set:

- add when the Prompt introduces a new user need, competition context, decision dimension, product/region/USP, or useful analysis view;
- merge when two Prompts produce the same buyer need and expected candidate set;
- retire only when duplicated, obsolete, or no longer business-relevant. Do not
  retire only because of zero target-brand mentions or inconvenient outcomes.
- **review the formal set once, 2–4 weeks after periodic monitoring starts**
  (Suda 2026-10-23, after Momentic's Atlas method). Check the Prompts
  themselves only: do the answers stay on the category and task, does every
  platform answer the question that was asked, are repeated runs consistent,
  is any Prompt a duplicate of another, is it still business-relevant. A
  Prompt that fails is reworded or retired through the versioning rule below
  (old Prompt 停测 with its history kept, new question_id, the affected cells
  re-baselined, a substantive change reconfirmed by the brand party). **The
  brand not being mentioned is never a reason to retire or reword** — finding
  where the brand is absent is what the set is for, and dropping those Prompts
  would bias every later reading. After this review the set changes only on a
  trigger (product, market, pricing, regulation or a major competitor change)
  or at the periodic reviews below. **Hold the review before optimisation
  content goes live where the schedule allows.** A Prompt the review opens is
  baselined after the review; if content for its attribute has already
  shipped, its Before already carries part of the effect. Mark such Prompts
  复查新增 in the report and keep them out of the commitment's before/after
  comparison for the current version (Suda 2026-10-23).
- **a formal Prompt's wording is immutable** (Scrunch archives-and-recreates,
  Peec keeps history the same way; adopted 2026-10-22). To reword one, set the
  old Prompt 停测 — keeping its question_id, readings and history — create a new
  question_id with the new wording, and start a new set version per the
  versioning rule in *Versioning and baseline anomalies*. Never edit the
  text in place: the old readings would silently describe a question that no
  longer exists.

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
