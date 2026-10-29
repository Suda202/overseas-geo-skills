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

Six stages (Suda 2026-10-23, superseding the four-stage table; stage 2 reworked 2026-10-28): 需求研究与属性池 → 提示词矩阵、主题与出题 → 试跑（各监测平台 × 3 次） → 机会排序与客户选词 → 正式 Baseline → 优化与持续监测. The chain is continuous, but each stage answers exactly one question. **An earlier stage may only raise a hypothesis; it may not state a conclusion.** Moving a later conclusion forward is the most common error in this flow.

| Stage | The question it answers | What may be said here | What may NOT be said here |
|---|---|---|---|
| **1 需求研究 → 属性池** | What is worth monitoring? | Brand facts, demand signals, attribute pool (相对竞品 only), competitors; AI's buying criteria and its appraisal of the brand and competitors from the research pre-run, as leads to check | Whether AI has a cognitive gap, or a 相对竞品 taken from AI's appraisal without opening the page behind it — the pre-run is one run per platform |
| **2 矩阵、主题与出题** | Which buying situations matter, which needs become questions, and how many? | Matrix rows with their priority, candidate Topics clustered from the rows, candidate Prompts and their default tiers | Any AI-side reading |
| **3 试跑（每题 × 每个监测平台 × 3 次）** | Is each question asked right, and what does AI answer today? | `prompt_validity` (合格/修改/淘汰); 可改变性 per Prompt from the top 20 cited domains; an initial AI 认知差距 (试跑初判); **exploratory** readings — brand and competitor mentions, positions, cited sources | A stable mention rate; any selection decision driven by the brand's own reading |
| **4 机会排序与客户选词** | Which Prompts should the client pick? | A recommendation order from the matrix-row tier, dropped once only by 可改变性 低; trial readings shown in the separate trial report | A promise that optimisation will work; a tier dropped because the brand already leads |
| **5 正式 Baseline（选定题 × 每平台 × 每国家 × 每语言 × 30 次）** | What is the initial Before benchmark under the locked set? | Formal per-platform visibility and citation diagnosis; 可改变性 and AI 认知差距 confirmed on the pooled answers; provisional optimisation order; feasibility assessment for the commitment | A claim that a gap is stable over time, or that optimisation worked |
| **6 持续监测** | Are the gaps persistent, and did optimisation improve them? | Same-question, same-condition, same-caliber window comparison; longitudinal evidence | A single-day comparison or immediate effect promises |

**One line: 选词评估需求价值与可争取性，试跑提供探索证据，正式 Baseline 验证实际表现与承诺可行性，长期可比数据检验持续性与改善。**

**The candidate baseline is retired** (Suda 2026-10-23, superseding the 2026-10-13 全候选 × 全平台 × 5 次 rule). Multi-platform collection runs only for the client-selected formal set, and that run **is** the Before baseline. Candidates the client does not select are never collected beyond the trial. What this buys: no collection spent on unselected Prompts. The brand party does see the trial readings — they go to it as a separate trial report marked 供参考、不作统计 (Suda 2026-10-27) — so the anti-selection-bias rule is held by our recommendation order, which never reads them. Because the trial runs on every monitored platform (Suda 2026-10-23), a platform-specific wording problem (one platform answers a different category, AI Overviews never triggers) surfaces at the trial; what still slips through is handled by the rule in *Versioning and baseline anomalies*, never by quietly dropping the Prompt. Banks collected under the old flow keep their data and calibers; do not migrate or delete them. A platform that cannot be collected in a market (ChatGPT in Hong Kong) is left out of both the trial and the formal baseline for that market.

## Stage 1: Demand Research and the Attribute Pool

**Settled sequence** (Suda 2026-10-23). Attributes are distilled from two parallel research passes — buyer signals (reviews, community, search data) and official-site research (the brand's own pages, spec sheets, competitor comparison, certification) — plus the twelve-class skeleton sweep. Both passes feed the pool; neither is skipped.

**The coverage matrix grid is enumerated before the pool is filled** (Suda 2026-10-22 top-down rule). From 业务范围, write out 产品线 × 主要受众 × 市场 × 旅程阶段 first, as a gap-check skeleton; only the cells worth testing become matrix rows (Stage 2). Then collect signals and research the official layer; the evidence fills the skeleton. A cell that remains empty when the matrix settles is closed with a reason in the internal handoff — 无买家证据 (our research gap) / 低业务优先，留到后续周期 (the brand party's confirmed trade-off, read off the 业务范围 主要受众 priority marks) / 超出范围; `scripts/check_matrix_coverage.py` lists the open cells. Do not open by filling in an attribute list and then hunting for signals that confirm it, and do not write a Prompt into an empty cell just to close it. This prevents silent coverage holes: an audience quiet in buyer signals but business-critical (a new market, a B-end buyer, a niche but hard-constraint segment) stays as an empty row with 「无买家证据」 written, not an invisible omission. Enumerate the skeleton only; do not mechanically fill every cell — use the three-tier distinction Suda stated (候选组合 / 有效切片 / 排除组合+原因) to separate the real buying situations from the mechanical grid fill.

**Audiences beyond the business scope's listed 主要受众 are added to 业务范围 as 主要受众 rows, never as hypothetical options.** An audience split that changes eligibility, dominant criteria, or the expected answer set is a real segmentation; one that does not is a 约束. Freeze the list before Prompts are written (Suda 2026-10-20) and validate it against first-party sources (sales records, support tickets, the site's own audience selectors). Which audiences are a business priority is the 主要受众（优先） mark (or a 业务目标 naming one); it feeds matrix-row priority. There are no audience rows in 属性池 (Suda 2026-10-28).

**The pool judges only 相对竞品** (Suda 2026-10-28). Priority is judged once, on matrix rows (Stage 2 → *Priority*); whether content can move AI's answer is judged per Prompt from the trial (Stage 3). The attribute tier (重要性 × 可改变性) and the audience rows are retired.

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

- **业务重要程度 uses one ordered P-scale as defined in that document**, which already contains frequency — do not add a separate frequency column, and never use a middle grade as an "undecided" placeholder. The **matrix carries its own P1–P3 with different semantics** (business focus × buyer-evidence strength); the two scales must not be mixed.
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

Attributes are gathered and judged on 相对竞品 only; buying situations (matrix rows) are prioritised; Topics are clustered from the prioritised rows (Stage 2); changeability is read per Prompt from the trial (Suda 2026-10-28). Do not ask the customer to rank.

| What | Where it is judged | When |
|---|---|---|
| 相对竞品 — the brand's real industry position on the attribute | 属性池 | Before Prompts |
| Whether the attribute matters in a situation | Matrix row — listed or not | Before Prompts |
| Priority — business focus × buyer-evidence strength | Matrix row | Before Prompts |
| 可改变性 — can content change this Prompt's answer | 提示词库, from the top 20 cited domains | Trial |
| Current gap (AI 认知差距) | 提示词库 | Trial (initial), formal baseline (final) |

A differentiator no buyer asks about lands on no row and gets no Prompt.

**A direction the brand cannot move gets no Topic of its own.** If the brand genuinely lacks the capability, the attribute is 劣势 and is never listed. If a competitor's lead rests on brand awareness or broad media consensus, that shows in the trial: the Prompts' cited domains are mostly rankings and media, 可改变性 reads 低, the Prompts drop a tier, and the Topic's 可改变性低占比 moves it back in the recommended order. Do not pre-judge it before the trial — a consensus that holds in the media may not hold in the answers.

**Judge this per Prompt, not per Topic.** A Topic can be hard to move as a whole while single Prompts inside it are open — an unpublished certification is closed by one page even when the Topic's leaders hold the media. When a Topic is dropped, re-home its open Prompts' needs into a surviving Topic, and record why for any left unmeasured.

**Evidence hierarchy for the consensus and optimisation judgement — answer layer beats spec sheet.** Read the AI answers' sentiment matrix (which competitors are criticised on this theme, and whether we are clean) before comparing product specifications, and put market-convention web research last. A dimension where competitors have hardware parity can still be a battlefield if AI answers keep criticising them there; conversely, buyer-forum language that never enters AI answers is not monitoring evidence. Structural losses recorded in the answer layer do exclude a Prompt ("only structural evidence excludes; a single zero-mention never does"), and an attribute where the brand is the weaker party (劣势) is not listed on any row.

**The answer layer may not exist — check before reading anything into its absence.** A sentiment matrix exists only if the presales run produced one *and* put the **discovery** questions into its sentiment sample scope. Two failure modes are both common, and neither is an anomaly: a rough presales pass runs visibility only and has no sentiment layer at all; and a run that marked only the branded evaluation question produces a self-portrait of the brand rather than a competitor matrix, so there are still no per-theme negatives to read. Verify which case you are in before treating the answer layer as evidence.

When the matrix is absent, do **not** report the emptiness as a finding that competitors are clean. Fall back to the next evidence layer — product specifications, our own asset inventory, external research on who leads the category — mark the consensus judgement as **provisional**, and say so in the deliverable. Record the gap as a process fix for the next presales run rather than as a blocker for this one.

**When several brands must be judged, keep the theme boundaries fixed across the run** so a later matrix stays comparable to the first one.

**When no theme shows a competitor negative.** A first pass can come back with competitors clean on every theme — roundup-style AI answers praise rather than criticise, so this is common and is **not** proof that no opening exists. It does mean no theme has a *demonstrated* opening yet. Do not quietly keep the optimisation labels on the Themes while the evidence says nothing was found; state it in the deliverable, hold the labels as provisional, and plan a second run of the same matrix immediately after the baseline so the judgement is longitudinal rather than a single snapshot. Also note the counter-explanation in the deliverable: an absence of negatives may be a property of the answer format rather than of the market.

**When the client asks for the head term they cannot win** ("rank #1 on <broad category> recommendation"): write that one bare category Prompt, since they asked, and do not promise it. Its tier comes from its row and the trial's 可改变性 like any Prompt's; the question budget goes to the rows where evidence shows the brand can win. Explain the trade-off in the client's terms, not with our internal scoring. Without such a request no bare category Prompt is written (Suda 2026-10-29).

**Differentiators are Attributes.** They are one row each in 属性池 — never a separate section, never a Topic, never a Tag. The "competitor cannot copy this" test decides **how a claim may be worded as a differentiator**, not whether a dimension earns a row: shared category requirements (compliance certification, integration, SLA) are legitimate Attributes and often decide the shortlist; they simply must not be sold as differentiators. A claim every major competitor can match — global inventory or price advantage, 24/7 multilingual support, "more advanced technology" — is either worded as the survivable part or recorded as parity. Trade-press or self-declared claims are labelled **品牌自述**, never asserted as fact, and gated on client confirmation. **A category threshold is not a differentiator either**: what every legitimate option already meets (no return promises, basic compliance, a free tier) is listed on no row and gets no Prompt, and the buyer worry behind it goes to the attribute that decides (Suda 2026-10-23, client-facing-attribute-pool.md → *属性池*). Attribute names must be legible in the client's own industry vocabulary — when the client says a name is unreadable, rename it rather than explaining it.

**Consensus and `相对竞品` judgements are made against the actual category leaders, not only the frozen competitor list.** Treating the frozen list as the whole competitive set produces false confidence: the brand may look strong against the configured set while the real answer-layer winners are elsewhere. Use the frozen list for Prompt construction and reporting consistency, but judge them against whoever actually leads the category's AI answers.

**The per-attribute relative-competitor verdict is researched, not requested.** Every attribute listed on a matrix row is judged by actually comparing our public position against that product line's leaders on that attribute — answer layer first, then the competitors' own public pages (spec sheets, certification pages, service terms), then third-party material. Run it product line by product line: the comparison set is not the same set across lines.

**Where the engagement already has collected answers, read the set off the answer layer** — whichever brands actually lead that product line's discovery answers, **computed separately for each market**: count mentions only in unbranded discovery answers from that market's run and take the top three per product line × market. A multi-market engagement (e.g. SG + MY) therefore carries one comparison set per cell, not one for the whole Case; a brand that leads in one market can be absent from another. Presales is unchanged — its Case keeps a single frozen set. The presales competitor-research step exists for the **pre-data** case, before anything has been collected; once data exists it is superseded, and a frozen list carried forward from before the run is a hypothesis to re-check rather than a given. Where no answers exist yet, fall back to it. This is **not** `automatic competitor discovery` — here the set is given and making the comparison is ours.

`待确认` therefore means **we looked and the public layer genuinely cannot settle it** — a QC agreement, an internal test report, a privately held warranty clause — never "nobody handed us a number". Always name the material that would settle it. A column that comes back mostly `待确认` is a research gap, not a finding: before shipping it, check whether the comparison was actually run.

While judging, split the gap and state which applies: **evidence gap** (the capability exists but is not published — the fix is a page) versus **capability gap** (the capability is absent — the fix is investment). That split is the most actionable line in the document and it is invisible from the verdict alone.

**Check factual accuracy during the same research pass — do not wait for Verification or Accuracy Prompts to find errors.** For every factual attribute listed on a P1 or P2 row — attributes with one checkable right answer, such as installation requirement, dimensions, availability in a market, price band, certification, warranty, eligibility, or corporate ownership — run two checks while filling `相对竞品`:

1. **Public-layer consistency.** Do the official site, marketplace and retailer listings, reviews, and third-party profiles state the same fact (model names, specs, prices, scope)? Conflicting public sources are the main reason AI gets a fact wrong.
2. **Answer-layer statement.** In the collected answers, what does AI actually say about this fact for the brand — correct, wrong, outdated, conflated with another entity (Ebrand vs Ebrand), or missing a remedy the brand does offer (UNI_A's foundation pathway)?

Write what you find into the client Base's **品牌事实核查** table (Suda 2026-10-16) — one row per contradictory or unsupported fact, with the official value, the source-page URL, the conflicting statement and its source, and whether the brand party should 改官网 or 提供材料 — and, for the attribute it belongs to, into that row's `备注` / `还缺什么` as evidence for the client to confirm; do not report it as an accuracy percentage — presales samples are too small, and the ground truth is the client's to settle. Subjective appraisals ("easy to use", "good value") are not facts; they belong to sentiment and recommendation, not here. See [client-facing-attribute-pool.md](client-facing-attribute-pool.md) → *品牌事实核查*.

**Only a few of those rows become Verification or Accuracy Prompts.** Research finds what is wrong and why; monitoring only tracks known risk points and whether fixes land. The two intents split by what AI gets wrong. One fact gets one Prompt, classed by what AI does with it during research; when that changes (AI learns the capability but then states a detail wrongly), reclassify the Prompt rather than add a second one. Different facts under the same attribute may carry one Verification and one Accuracy Prompt:

- **Verification** — AI does not know the brand holds the capability. After the formal baseline, the row becomes a Verification Prompt when the brand really offers the capability, a wrong answer would change shortlisting or purchase (an attribute on a P1 row, a gating fact, or an attribute on a P2 row whose 相对竞品 is 优势), and the discovery answers cannot show whether AI knows it (the brand is rarely or never mentioned on that attribute). Read it against the Discovery Prompts on the same attribute (trust gap vs comprehension gap, above).
- **Accuracy** — AI can state the fact but states it wrongly. The row becomes an Accuracy Prompt when a wrong answer would change shortlisting or purchase, and the answer layer already states it wrongly or outdatedly, **or** the fact recently changed (new model, rename, repricing) so AI is likely stale.

Either intent requires the client to have confirmed the right answer and an official source page — without that, keep it on the pending-confirmation list, not in the Prompt set. Facts that already appear correctly and frequently in discovery answers need neither. Most markets need none and rarely more than five across both intents; ask one checkable answer and name the brand (e.g. "Does Abrand G3 require plumbing installation?"). The client-confirmed answer is the scoring truth for that Prompt.

**No broad anchor** (Suda 2026-10-29, retiring the 2026-10-22 per-Topic low-condition anchor). Research suggests roughly 15% of categories already have a clear winner; a bare category question there rests on rankings and media and rarely moves, and elsewhere it still takes a formal slot from a buyer situation. Every Discovery Prompt therefore carries at least one buyer condition from its row, except a head term the brand party asks for.

**When the leader is the default** (Suda 2026-10-19, Hbrand; revised 2026-10-28). Where one brand holds roughly nine-tenths of the market and the brand party's own query data shows buyers rarely ask "which platform / brand is best" (Singapore property portals: RivalH1), write no bare "which platform" Prompt (no Topic carries one by default since 2026-10-29; `config.leader_default` is no longer read). Put the Topic into the buyer's underlying needs with their real conditions (area, unit type, budget, life stage, timing); AI names the platforms it would use in passing, and that is what is measured. A "which platform" Prompt stays only when it carries a concrete capability condition the brand genuinely leads on (Hbrand: previewing new launches in 3D or VR).

### How Attributes Are Derived

Matrix rows list Attributes and Topics are clustered from the rows, so Attributes are gathered **before** the matrix is drawn, in four steps. When running an after-sales engagement, follow that order rather than brainstorming Topic names first.

**Supply side and demand side are different objects — never generate the word list twice.** An Attribute is a **decision focus**: anything a buyer weights when choosing, on either side of the table. The rule document §3's twelve-category sweep is the class list, and it already spans both sides:

| Side | Classes |
|---|---|
| Brand side — how AI should perceive the brand | Category, Feature, Differentiator, Integration, Trust & Security |
| Buyer side — which buyer the brand is for, and in what situation | Industry & Vertical, Buyer Persona / ICP, Pain Point, Use Case, Evaluation Criteria, Geography & Market, Constraint |

**Customer intent is not a third class of Attribute.** An intent is the occasion on which a buyer asks ("we have offices in several Asian countries and do not want a supplier per country") — the demand side, organised by the journey labels — not a perception to own. Both degrade into "topic words" if written carelessly, which is where apparent duplication comes from (`Asian market coverage` as attribute vs `find a travel platform with good Asian coverage` as intent). Attributes decide **which perception to optimise**; intents decide **in which user question to fight for that perception**. Do not narrow the class list into a supply-side capability inventory, and do not merge the two objects into one column. The derivation stays stepwise — attribute pass, then intent pass, then cross-map — and each input pass stays light; what collapses into one place is the **deliverable**: the brand party reads 提示词库, whose 出题原因 carries the chain situation → attribute → Topic → Prompt → tier, because two heavyweight standalone tables are unreadable and unfillable for them.

**Step 1 — sweep twelve categories as a gap check, not a checklist.** Sweep Category / Industry & Vertical / Buyer Persona / Pain Point / Use Case / Evaluation Criteria / Differentiator / Feature / Integration / Constraint / Geography & Market / Trust & Security to find what is missing. Never fill them mechanically, and never let the skeleton stand in for the category-specific attributes that actually decide the choice — in B2B, Evaluation Criteria, Integration and Trust & Security are exactly the classes general knowledge cannot supply and the category must.

**Step 2 — collect the category-specific attributes from three sources.**

| Source | What to take | Who |
|---|---|---|
| The client's own procurement standard | RFP / tender scorecards received, the evaluation items sales is asked about most. B2B procurement already scores by domain, so this is the most accurate first-hand source. | Client provides |
| Competitor comparison and feature pages | Competitors have already summarised this category's evaluation dimensions for the market. | We research |
| Already-collected AI answers and the research pre-run | Cluster the attribute words AI uses when describing brands in this category — "the attribute set AI is actually using". Only we can do this layer, and it is the cheapest. | Ours alone |

**Research pre-run — crawl first, then research** (Suda 2026-10-29). Before the public research and before 相对竞品 is judged, collect what AI says today about the category and the brands, then research to fill and check it. Per product line × market language, write a CSV with a `query` column holding: one Category Awareness Prompt asking how to choose (`What should I look for when choosing [category]?`); and one report-wording Evaluation Prompt for the brand and for each 竞品 row in 业务范围 for that line and market (`Evaluate the [category] company [brand]`, the same wording for every brand), all in the market language. Keep that wording; do not switch to or add pros and cons (Suda 2026-10-29): in an brand-o Kenya test (4 brands × 4 platforms × 1 run) both wordings listed weaknesses in all 16 answers, and the Evaluate wording returned more citations (9.8 vs 7.1 per answer), named more other brands (4.7 vs 2.6) and carried the risk records (counterfeit, after-sales, warranty) that pros and cons mostly missed, whose weaknesses read the same across brands (`10-售前诊断报告/评测数据/brand-o/售前/_trial/prerun-wording-20261029/结论.md`). Run it once on each platform the engagement will monitor with `geo-presales-report-builder/scripts/collect_answers.py --questions <csv> --out <dir> --regions <market>` (one run per cell is the collector's default; 1 + 4 brands on 4 platforms is about 20 calls). Read the answers as leads, never as verdicts: buying criteria the pool lacks, each brand's strengths and weaknesses as AI states them, regulator, recall and complaint records, brand facts AI states wrongly, and the pages AI cites. Then research: open the cited pages and the official layer, and fill what the answers did not reach. A criterion becomes an attribute, a strength or weakness a 相对竞品 basis, and a wrong fact a 品牌事实核查 row only after it is checked; 判据与证据 cites the pre-run answer and the page that confirmed it. One run per platform is enough because nothing here is a statistic. Asking a model directly does not replace it: the monitored platforms answer from web retrieval and cite their sources, which is what the research follows. These Prompts are research, not monitoring — they never enter the bank or 提示词库, the trial, the formal set or any baseline — and the pre-run is repeated only when a product line or market is added, the competitor set changes, or the category's buying standard visibly shifts. The buyer-wording Evaluation Prompts in the bank are a separate thing: they need a use case from a matrix row and are written after the matrix.

**Step 2.5 — merge and name before ranking.** The sweep and the three sources produce candidates, and candidates come back under several names for one thing — Pbrand's matrix carried 52 attributes of which 25 were repeats; Hbrand kept 43 after merging and still had 「平台收费透明」 beside 「中介佣金透明」. Merge by what would change the action, the same test 受众 uses:

| Question | If yes |
|---|---|
| Would one content action close both? (one fee page, one spec paragraph, one warranty note) | Merge into one attribute — 「平台与中介费用透明」, not two |
| Do both sit in the same twelve-class, and would a buyer ever choose between them as separate considerations? | Merge |
| Are they the same thing under a long and a short name? (「购房资格与流程指引」 vs 「购房资格与流程」) | Keep one name, and use it in the pool, the matrix link and the bank |
| Does AI judge them separately in its answers, or do they need different optimisation actions? | Keep them apart even when the names look alike — Hbrand's 「3D 楼盘模型」 and 「视频看房」 carry different 相对竞品 verdicts and different content actions |

One attribute takes one row in 属性池 and one name everywhere; a name that only appears inside the matrix's linked cell and nowhere in the pool is a merge that was never done. Do this before the matrix is drawn, because merging afterwards means re-listing rows.

**Step 3 — B2B and B2C are not one attribute set.** The required categories, the wording, and the evidence lines all differ; mixing them yields a set that fits nobody — see the rule document §3 for the full comparison table (skeleton classes seen as required, how attributes are worded, data line, and when a single B2B/B2C set is acceptable).

**Step 3.5 — validate that someone actually asks it, before locking.** An attribute listed on a P1 or P2 row is still only a hypothesis about the market until a first-party source says buyers raise it. Check each one against our available sources: GSC/SEO queries, sales and CRM language, support tickets, win/loss and churn reasons, review and community language, already-collected AI answers. Traditional search volume is a directional signal, never proof of AI-side demand, and a long-tail or regional Query may legitimately have little volume while inheriting demand from its parent Topic. Where no first-party source exists, the row is marked **hypothesis grade** — it may still ship in a Discovery-first set, but it cannot be described as frequent, commonly asked, or high-demand. We have no AI prompt-volume data source; do not invent one, and do not present a tool's keyword figure as AI-answer volume.

**Inclusion follows buyer demand, not brand content** (Suda 2026-10-19). Whether to write a Prompt depends only on evidence that buyers ask it — buyer quotes, search signals, the brand's own GSC — and a niche audience counts (divorcing couples, retirees selling a short-lease flat, a citizen married to a foreigner). Whether the brand's site already has an article on it is not a reason to include a Prompt, and its absence is not a reason to leave one out; that only feeds the content plan after the baseline. Whether a direction can be won is read from the trial and the baseline, not pre-judged.

**On the current-gap condition (fill it only when it has been measured).** Profound's third question — is there distance between what AI says and what we want it to say — is the leg we most often cannot answer at generation time, because a first set is designed before any answer exists. Do not fill it from intuition: an unfilled Gap is marked `待测`, never "AI doesn't know us". **But the engagement usually runs two rounds** — presales collects a first answer batch, so after-sales often *does* have measured Gap data. When it exists, fill it with the measured value and cite the sample ("APAC coverage mentioned in 33.3% of 15 valid discovery prompts, the other 7 topics at 0"), and keep it to the answer layer: a sales hunch or "the client says this matters" is not Gap evidence. **Where another company shares or nearly shares the brand's name, measure the gap on the brand's own-domain citation rate, not on name mentions**: a name appearing in the answer does not show the AI read the brand's content, and some of those answers cite the other company's pages under the brand's name.

**Step 4 — sweep the journey stages and judge 相对竞品.** Check each of the eight stages (`发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持`) for an attribute buyers weigh there that the pool still misses — transaction and post-purchase are the usual holes — then judge each attribute's 相对竞品 with its basis line. The situations, their priority and the Topics come next, in Stage 2. Do not ask the customer to rank.

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

**Step 3 — apply the three tests.** A segment earns its place only when it changes at least one of: **which candidates are eligible**, **which criteria dominate**, or **how the question is phrased in a way that changes the answer**. If it changes only the phrasing, it is a 约束 on a slice; if it changes nothing, merge it into the nearest segment. **A group that only follows a Topic is not a segment** (Suda 2026-10-26): when the different candidates come from what is asked, not from who asks, the Topic and the slice's 约束 already separate the reading, and the same base buyer asking the same question gets the same answer. Nbrand 台湾: the wallet-check Prompts (MetaMask 授权、钓鱼代币) pull Revoke.cash and GoPlus, but that is the 钱包安全体检 Topic speaking — a 美股加密 investor who holds a self-custody wallet asks the same; the grid Prompts (「網格機器人手續費太高」「跑出網格區間」) carry 网格 in their 约束. So 「DeFi 与链上用户」 and 「自动化交易用户」 were not split out in Taiwan and those 9 Prompts stay under the base audience. B2C usually lands at five or fewer; B2B adds the buyer role (decision, use, payment, risk control) as separate rows, because there the roles really do buy differently.

**Step 4 — validate against first-party evidence, then freeze.** Check each proposed segment against sales and CRM segment labels, support-ticket categories, GSC and site-search terms, community and review language, the competitor sites' own filters, and already-collected AI answers. A segment no first-party source names is hypothesis grade: keep it only if a named buyer situation demands it, and say so. The brand party confirms the list as 主要受众（1）…（n） rows in 业务范围; we do not ask them to design the split. Freeze the list before writing Prompts — changing segments later moves every slice's audience, the per-audience dashboard and any audience-level reading.

**Step 5 — mark the priority audiences in 业务范围** (Suda 2026-10-23; audience rows in 属性池 retired 2026-10-28). The brand party marks 主要受众（优先）; when it has not but its own written inputs settle it (template answers, priority product line, 核心可见度问题), we fill the mark ourselves, labelled 「我方按品牌方已填内容推断，品牌方可改」. The mark feeds the business-focus test of every matrix row with that audience (Stage 2 → *Priority*). A non-priority audience's rows are not dropped by default: they reach P2 on strong evidence and P3 (no Prompts this period) on weak. Row semantics: [client-facing-attribute-pool.md](client-facing-attribute-pool.md) → *提示词矩阵*.

**Step 6 — the wording must show who is asking, stated or implied** (Suda 2026-10-23). A segment exists because it changes the candidates, the criteria or the answer; a Prompt filed under it that a generic buyer could just as well be asking gets answered for the generic buyer, so the slice's audience label measures nothing. Most Prompts already carry the identity through what they ask — 「HDB resale flat」 implies a citizen or PR buyer, 「rent a room near NTU」 a student renter, 「my HDB flat is worth」 an owner — and need nothing added. Only where neither the wording nor its condition gives the asker away, add the audience in the buyer's own words (「with three cats」, 「as a foreigner」, 「for a 50-person sales team」). Register both kinds of words — the self-descriptions and the implying terms — from that audience's 买家原话 in `config.audience_terms` (output-contract gate 39). The audience is not a 约束: it is not listed in `constraints` and does not count toward gate 36. Exempt are Verification and Accuracy Prompts (one checkable fact, same answer for every asker) and a head-term Prompt the brand party asked for (base audience by definition); an implied identity the term list cannot catch is recorded as `audience_implicit` with the reason. This is not the first-person rewrite *Discovery Quality* warns against: that adds a situation which leaves the candidate set unchanged; this states the condition that made the segment a segment.

**Two things this rules out.** One segment per phrasing (citizens vs PRs when both buy the same flats under the same rules), and a "general" or catch-all segment: rows with no narrower condition take the category's base audience. A journey state (「已在比较具体品牌」) is never a segment; it is a stage.

### Priority: judged once on the matrix row

**Priority is judged once, on the 提示词矩阵 row** (Suda 2026-10-28, after Aleyda's per-row business priority, "based on commercial value, strategic importance or current business focus"). A Prompt takes its row's tier; the only per-Prompt adjustment is one drop when the trial reads its 可改变性 as 低. 属性池 carries no tier.

**Row priority = business focus × buyer-evidence strength.**

1. **Business focus**: the row's product line is the priority line, and any of — its audience is a priority (主要受众（优先） or named by a 业务目标); the row matches one of the brand party's 核心可见度问题; it matches a situation a 业务目标 or 营销活动 names. The conversion path is not read here.
2. **Buyer-evidence strength**: 强 when at least two independent source types recur (buyer quotes from community or reviews, search data, brand first-party data); 弱 with one. A 核心可见度问题 is business focus, never buyer evidence.

| | 证据强 | 证据弱 |
|---|---|---|
| 业务重点 | P1 | P2 |
| 非重点 | P2 | P3 |

- **Journey-stage cap**: 发现 / 评估 / 对比 / 替代方案 / 验证 may reach P1; 交易, 购后支持 and 解决问题 cap at P2 unless the row matches a 核心可见度问题.
- A row resting mainly on 待确认 attributes caps at P2.
- **P3 rows get no Prompts this period**; a P3 on 提示词库 only comes from a 可改变性 drop.
- Self-check: the P1 rows' 目标题数 should roughly match the formal slots (at most 10 per purchased Topic); far more means P1 was judged too wide.
- **Every judgement carries its written basis** (Suda 2026-10-23): row priority in 优先级依据, 相对竞品 in 属性池 判据与证据, a Prompt's 可改变性 in `changeability_basis`. A value with no basis stays blank.
- Do not reintroduce numeric weights or a lookup on attribute grades: the two tests and the caps decide the tier.

**P1/P2/P3 are this project's tiers.** Profound's AEO Guide grades attributes Priority 1–3 by how central they are to the buying decision and filters them by three questions (impact, distance, influence; https://www.tryprofound.com/aeo-guide/chapter-2 ); we judge priority on the buying situation instead, read "influence" per Prompt from the trial, and read "distance" as AI 认知差距. Do not cite Profound for the row tests.

**可改变性 per Prompt** (renamed from 信源壁垒 2026-10-28; the only changeability judgement in the flow). Take the top 20 domains by citation count in the Prompt's trial answers (正文引用 only, undeduplicated counts) and place each in a tier: **官网** — the brand's site, subdomains and blog, the pages it edits on its 转化路径 channel (Amazon store, App Store page, own store), and competitor official sites (AI citing them shows it takes vendor pages for this question); **社区** — text communities the brand party posts in from its own account with our content (Reddit, LinkedIn); **难影响** — third-party reviews, media, rankings, review platforms, government, communities the brand party does not post in, video platforms such as YouTube (outside our service unless the client buys a source service, which moves that class to 社区). No fixed threshold: mostly 官网 + 社区 → 高, mostly 难影响 → 低, about even → 中. A fact the brand publishes but AI cannot read (JS-rendered numbers, image-only specs) → 高, recorded as a content to-do. 低 drops the Prompt one tier, once. Re-checked on the formal baseline. Not judged here: whether the brand has the capability (劣势 is never listed), retrieval vs memory, or whether sources already hold a consensus — that shows only after content is published.

**When government or encyclopedia pages dominate, read whose pages the candidate list rests on.** In regulated categories (property, finance, health) AI cites government pages for rules while naming platforms from elsewhere; counting the rule citations would drop the brand's best Prompts. Hbrand replay: 9 of 23 Discovery Prompts had ≥50% government citations (cea.gov.sg for the agent register, hdb.gov.sg for eligibility), yet only two (T2-D21, T6-D03) had a government portal leading the candidate list. Judge those Prompts on the domains behind the candidates.

**What decides priority, and where each factor acts** (Suda 2026-10-23 / 2026-10-28). The 提示词库 优先级 is the **selection** priority. The optimisation order after the formal baseline is a separate result, computed in the baseline report (`geo-monitoring` → baseline-report.md → *优化顺序*) and written back per Prompt into 提示词库 优化顺序; it never rewrites the selection 优先级.

| Factor | Who judges, when | Selecting the formal set | Ordering optimisation |
|---|---|---|---|
| Business focus (业务目标, 营销活动, 核心可见度问题, audience and product-line 优先 marks) | Brand party marks, we judge the row | Yes — row tier | Yes |
| Buyer-evidence strength | Us, from buyer evidence | Yes — row tier | Yes |
| Journey stage | Fixed cap | Yes — caps the row tier | No |
| 可改变性 (top 20 cited domains) | Us, from the trial; re-checked at the formal baseline | Yes — the only reading that drops a Prompt's tier | Yes |
| 相对竞品 (real industry position) | Us, attribute research | 劣势 is never listed; within a tier and type, 优势 before 持平 | Yes |
| The brand's own mention reading (the five competition patterns) | Computed in the baseline report from the 30 runs per cell | **No** | Yes |
| AI 认知差距 | Trial (initial), formal baseline (final) | **No** | Yes — on-site vs off-site work |
| Prompt type | Us | Yes — order of formal slots within a tier | No |
| Question quality and coverage | Us, trial; platform-specific problems at the formal baseline | Yes | No |

**Why the brand's own reading stays out of selection.** Picking the Prompts that happened to read low, then counting their regression to the mean as optimisation, is the failure Peec, Aleyda and Ahrefs all warn about; dropping Prompts the brand already wins would also stop the mention rate from showing what it holds. 可改变性 may enter selection because it reads where the answer's sources come from, not whether the brand is mentioned.

**Within a tier, prompt type orders the formal slots: Discovery, then Alternatives, then Competitor, then Information (问题解决), then the rest; within one type, 优势 before 持平** (Suda 2026-10-23 / 2026-10-26 / 2026-10-28). Discovery is the mention-rate KPI and keeps at least half the set (gate 40); Alternatives also returns a candidate list and is read for mention; Competitor is read for win rate; Information is read for citations of the brand's pages. Prompt type never crosses tiers. Verification and Accuracy Prompts take no formal slot (see *Prompt Priorities*). B2B and high-trust categories may move Competitor, Evaluation and Verification up. Nothing else orders a tier at selection.

**A hand change is an exception, not a second judgement.** 提示词库 优先级 is an editable single-select prefilled by `write_prompt_reasons.py`; anyone may change it, and a changed Prompt's 出题原因 ends 「改档：理由，定为 Px」 (`check_client_base.py` fails a change without it).

**The five competition patterns live in the baseline report** (Suda 2026-10-23). 竞品领先 / 部分出现仍落后 / 已打平或领先 / 无品牌点名 / 来源追不上 are computed per Prompt from the formal baseline's 30 runs per cell and used only to order optimisation work; thresholds and ordering are in `geo-monitoring` → baseline-report.md → *优化顺序*. They are not filled by hand in the Base and never change the selection priority.

Therefore: **presales may rank candidate Topics; the after-sales baseline informs operational priority, but neither stage alone promises that an action will work.**

## Stage 2: Matrix, Topics, and Prompt Generation

**The matrix comes first, Topics are clustered from it** (Suda 2026-10-28). Draw the skeleton 产品线 × 受众 × 市场 × 旅程阶段, open only the situations worth testing, list on each row the attributes that matter there, and judge each row's priority (*Priority* above). Then cluster the P1 and P2 rows into Topics by the decision task — same competitor set, same evaluation standard, same optimisation direction — and file each row under one Topic (SKILL.md Workflow steps 4–5). The bank records it in `config.slices` (each row with its `topic_id`, `priority`, `priority_basis`, `target_count`) and `config.topics` (`source_slices`, `planned_prompts`); the validator checks that every P1 row is homed and that every Prompt sits on a row.

**目标题数 is the number of clearly different decision needs on the row**, filled before Prompts are written — decision difference, not phrasing count: blank outside this period, 1 for one independent decision, 2 or more only when the needs would change the candidate list (client-facing-attribute-pool.md → *提示词矩阵*). **Every Prompt is published with its reason** — 出题原因 on 提示词库, written per Prompt by script: what the Prompt tests (buyer, stage, decision need), the evidence behind it (quote counts by source, one representative quote), and why its tier (the row's business focus and evidence strength, then the 可改变性 drop where it applies). The brand party asks three questions — why this Prompt, why this tier, why this Topic first — and reads the first two here and the third in the 主题 table's 推荐顺序 (see *Topic recommendation order*). A tier the client cannot explain is a tier they will not accept (Suda 2026-10-23).

**Prompt type decides the analysis contract and is filled per Prompt, never per Topic or slice.** The eight types — Discovery, Competitor, Alternatives, Evaluation, Verification, Accuracy, Category Awareness, Information — have distinct analysis rules and tier defaults recorded in shared/canonical-intent-mapping.md, enforced by the validator. Discovery keeps at least 50% of the candidate bank (gate 40). Alternatives split out of Competitor 2026-10-22; Information added 2026-10-19. Each type's default tier (core / experimental / monitoring) is a **can-override default**, not a lock: the monitoring purpose stated in the generation rules or the brand party's purchase may move a Prompt to a different tier with a recorded reason — except two the validator fixes: Information is always `experimental`, and Competitor and Alternatives are never `core`.

### Topic Rule

A Topic is a set of intents around one shared buyer need or purchase decision, each intent represented by a Prompt — a business theme worth tracking with an independent long-term metric. It is clustered from matrix rows, can span several attributes, audiences and stages, and each Prompt belongs to exactly one Topic. There are no Topic types and no fixed first-stage shape (Suda 2026-10-28). It is not the `Category Awareness` intent.

#### Topic recommendation order

The formal Topic count follows the purchase, so the brand party has to choose which candidate Topics to buy; give it an order and a reason (Suda 2026-10-23, Nbrand: seven candidate Topics in Taiwan, five in Korea). The order is **derived from what is already judged**, written as 推荐顺序 in the 主题 table (Suda 2026-10-28):

1. **Business focus first** — Topics holding rows that match a 核心可见度问题, 业务目标, 营销活动 or priority audience. This is the brand party's call when it disagrees.
2. **Then the number of P1 Prompts** in the Topic.
3. **After the trial**, a Topic whose 可改变性低占比 is high moves back.

A Topic whose Prompts are all P2 can still be bought when a business goal names it (Nbrand: Polymarket); buying it does not raise its tiers. The reason goes in the 主题 table's 依据与说明; the 按主题 × 优先级 chart follows the order through 提示词库's hidden 主题排序 column. Candidate Topics are not limited in number.

#### When to split a Topic: three tests, three checkpoints

**Split when the two halves are two independent competitive situations** — the same test used when clustering rows into Topics. Three questions; any one hit means split, none means keep:

| 测试 | 问什么 | 例（Mbrand 家用 vs 医用制氧机） |
|---|---|---|
| 竞品集合 | 两半的买家在拿不同的对手比吗？ | 家用对手是 Inogen 这类消费品牌，医用是医院采购渠道的器械商，名单几乎不重叠 → 拆 |
| 评估标准 | 决定选谁的属性清单换了吗？ | 家用看噪音、便携、价格；医用看 FDA 510(k)、流量精度、保险覆盖 → 拆 |
| 优化方向 | 要发的内容、要挣的信源是两套吗？ | 一半上患者社区和 Amazon 评价，一半上行业采购指南 → 拆 |

Counter-example: Hbrand's rental Topic carried 20 candidate Prompts and stayed one Topic — budget, district, school zone and short-lease are constraint variants inside one competitive situation (same platforms, same criteria, same content landing). Many Prompts is not many situations.

Run the tests at three checkpoints:

1. **At clustering** (matrix rows → candidate Topics): the rows' audiences and listed attributes, with the attributes' 判据与证据, already show each row's competitor set and evaluation standard — check whether the rows inside one candidate Topic are homogeneous on those. An obvious two-situation cluster (Mbrand above) is split here.
2. **At formal-set selection** (after the trial, the decisive checkpoint): the brand party picks at most 10 formal Prompts per purchased Topic by tier — that pick is the test of whether one Topic holds the coverage. We do not pre-split at quoting time on an intent count: candidate Topics carry **no cap on Prompts or intents**, and predicting "your coverage won't fit" for the client is our inference overriding their call (Suda 2026-10-22). Only when the brand party cannot get under 10 without dropping intents it genuinely needs — or says so — propose splitting into a second purchased Topic; the units are the **independent purchase decisions** left over (the dedup yardstick: same candidate set, same comparison dimension, same answer-changing condition = one intent), not the Prompt count.
3. **From the answers — the trial first, confirmed on the formal baseline**: the answer layer shows it — when two groups of Prompts under one Topic surface two clearly different competitor lists (per-cell top3), that is test 1 showing up in data; split so each half's mention rate means something. This evidence also feeds checkpoint 2's conversation.

Signals that do **not** justify a split: a difference that is only a constraint (budget tier, household size) stays a decision need on the row, carried by the Prompts' wording; only an audience, with competitors and criteria unchanged — multi-select 受众; only language or market — the 市场 field.

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
Weight the counts, do not equalise them: the weight follows the P1 rows. A mature set
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
4. **Alternatives (客户标签 替代, split out of Competitor 2026-10-22, after-sales only):** asks for alternatives to a named competitor (「best alternatives to [leader]」), where the brand can appear in the answer list. Its natural reading is **提及率 within the alternatives list** (called 列入率 before 2026-10-23) — in how many runs the brand is listed among the alternatives, and where — plus sentiment; win/loss framing does not apply because the brand is not one side of a comparison. 列入≠推荐: the listing feeds the mention layer only, the recommendation caliber stays separate. This 提及率 is reported on its own line; whether it counts toward the mention-rate KPI is undecided (Suda 2026-10-23): banks default to `formal_visibility_eligible: false` until it is settled, and the validator accepts either value. The case against counting it: the wording plants a competitor name and conditions the answer set. Non-branded alternatives questions stay Discovery as before. Evidence-gated like everything else, and the leader-default rule still bars 「alternatives to [leader]」 where buyers do not ask it. Same layer and cadence as Competitor (monitoring/experimental, never core; trialled during attribute research; may be bought into the formal set). Banks written before 2026-10-22 keep such Prompts typed Competitor — do not migrate; the validator accepts both on the 替代方案 stage.
5. **Category Awareness:** research only — the pre-run before the attribute pool (*How Attributes Are Derived* → Step 2), never in the bank; repeated only for a new product line or market, or a changed buying standard.

After-sales uses the six presales intents — `Discovery`, `Competitor`,
`Evaluation`, `Verification`, `Accuracy`, and `Category Awareness` — plus two
after-sales-only additions: `Alternatives` (替代, split out of Competitor on
2026-10-22, see item 4 above) and `Information` (问题解决, Suda 2026-10-19; client label renamed from 信息 and scope narrowed to problem-solving on 2026-10-26, English value unchanged): a buyer asking how to solve a problem or reach a goal, which AI answers with advice rather than a candidate list ("How can I sell my HDB flat quickly?"). Pure knowledge questions — policy, rules, cost, rights or dispute questions asked for their own sake — are not this type. Its answers are read for one thing: whether the brand's domain is cited (Suda 2026-10-23; mention rate is not read for this type). Set `analysis_type: citation` (shared/canonical-intent-mapping.md) and `formal_visibility_eligible: false`; no sentiment. In the formal baseline every selected Prompt, Information and named-brand ones included, is counted in the baseline report (HTML, built by geo-monitoring; see its baseline-report.md) with no split by intent (Suda 2026-10-20). The formal-set mention-rate KPI still counts Discovery only, and `formal_visibility_eligible` stays `false` — the field governs the formal stage only. It differs from Category Awareness (how to choose a product or provider) and from Verification / Accuracy (facts about the brand). Like any Prompt it needs real buyer demand evidence, a niche audience included; whether the brand already has content on it does not decide inclusion. Only a problem-solving question whose solution runs through what the brand serves goes into the Prompt bank — the brand's product, tool or official content is a fitting citation for the answer (a property portal on selling, buying or renting a home; a travel platform on rebooking or a refund; a SaaS tool on setup or troubleshooting). One the answer fully settles with general advice, or whose next step belongs to a bank, lawyer or government body, is not written as a Prompt at all — record it with its reason in `config.parked` (Suda
2026-10-19). **Not written by default** (Suda 2026-10-29): it reads only whether the brand's pages are cited, which is not the KPI, and before the brand has content for the problem the reading is almost always zero. Write it in the first round only when the brand party's 业务目标 or 核心可见度问题 names that problem-solving need; it then runs in the trial as below. Otherwise write it after the formal baseline, when the content plan targets that problem: run it once before the content goes live and once after, as a diagnostic outside the formal set and the KPI. When written in the first round it belongs to the `experimental` layer (Suda 2026-10-20). Those Information
Prompts go into the trial; once selected, one whose formal-baseline answers neither cite the brand's domain
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
(Profound AEO Guide ch3, adopted 2026-10-22).** When an attribute on a P1 row reads
low mention in its Discovery Prompts in the formal baseline, add
one Verification Prompt on that same attribute ("Does {brand} offer
{capability}?"). P1 is the floor, not the limit (Suda 2026-10-26): an attribute on a P2
row may also get one when its 相对竞品 is 优势 — the brand really holds
the capability — and its Discovery Prompts read low. Never pair a 劣势 or
待确认 attribute; there the gap is the product, not AI's knowledge. One
Verification Prompt per attribute is enough; it is a diagnostic, not a monitored Prompt (Suda 2026-10-27) — not trialled, no formal-set slot, outside the KPI and outside the formal set, so adding it changes neither the set version nor the assessment scope. Its answer splits the gap into two diseases with different
prescriptions — AI knows the brand holds the capability but does not recommend
it (build off-site signals: third-party citations, reviews, authority), or AI
does not know the brand holds it at all (fix on-site description and
documentation first): "These are completely different programs of work, and
without validation prompts, you can't tell which one you need." Record which in
提示词库 AI 认知差距 — the old single 有缺口 value is split into 知道但不推荐
and 不知道该能力 (2026-10-22); 无人讨论 / 无缺口 are unchanged, and 待基线 became 待试跑 when the trial began giving an initial reading (2026-10-28).

**After the split, Verification Prompts are re-run only on an event trigger** (Suda 2026-10-26; cadence table in `geo-monitoring` → 采集频率与重跑). Its first job — telling
知道但不推荐 from 不知道该能力 — is done once the formal baseline (or a
supplementary run) has read it; re-asking every period adds cost without a new
decision. Read each answer (confirmed / partly / denied / unsure):

- AI confirms the capability in at least 80% of answers (e.g. 12/15): the gap is
  知道但不推荐. Re-run it only when the brand changes or launches the capability,
  the official page is rewritten, or a same-name brand surfaces.
- AI confirms it in fewer than 80%: keep it in the monitoring layer. It is the
  reading that shows whether the on-site fix (a clear official page AI can
  actually crawl) reached the AI, so re-run it once the fix is live, alongside
  the paired Discovery Prompts' daily readings, and again on any important
  product-information change.

Either way it never enters the mention-rate KPI. Hbrand 2026-10-23: CEA-only
listings 12/15, whole HDB and landed rentals 15/15, new launches 12/15 → 知道但不推荐;
fake-listing checks 7/15, area guides 9/15, resale eligibility guides 2/15
→ monitoring layer, re-run after the fix.

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
| Category Awareness (品类认知) | What criteria AI tells buyers to choose by | Returns a criteria list; read whether the attributes on our P1 rows appear among the criteria and which guides AI cites; feeds the attribute pool; research pre-run, not in the bank | reference only |
| Information (问题解决) | Whether advice answers cite the brand's domain | Returns advice, not a candidate list | 引用 only (no mention rate), never the mention-rate KPI |

**Reference wording per prompt type** (Suda 2026-10-29, replacing the 2026-10-26 one-form-per-type rule). No prompt type has a mandatory sentence form or opening: `Best …`, `What are the best …`, `Which …`, `… recommend` and other natural phrasings all work for Discovery, and the same holds for every other type. Write the way the market's buyers ask; buyer quotes and search queries supply the category name, the conditions (约束), the audience and the problem words. What is fixed is what each type's wording must do; the forms in the last column are examples to start from, not templates.

| Prompt type | The wording must | Reference form |
|---|---|---|
| Discovery (发现) | Ask for candidates (products, providers, platforms); every condition backed by a cited quote | `Best [category] for [condition]`, `Which [category] is best for [condition]?`; a buyer with no category name asks about `[tools / products] for [problem]`. The status-quo Prompt keeps its tested provider form (*Discovery Quality* → status-quo alternatives) |
| Competitor (对比) | Ask for a verdict, with the use case (gate 38) | `[brand] vs [competitor]: which is better for [use case]?` |
| Alternatives (替代) | Name one competitor, not the target brand | `What are the alternatives to [competitor] for [scope]?` |
| Evaluation (评价) | Name one brand and the use case or scope; see *Evaluation wording* below | `Is [brand] worth it for [use case]?`, `Is [brand] a good [category] for [use case]?` |
| Verification (验证) | Ask about one capability | `Does [brand] offer [capability]?` |
| Accuracy (准确性) | Ask about one fact | `What is the [fact] of [brand / product]?` |
| Category Awareness (品类认知) | Ask what to weigh when choosing | `What should I look for when choosing [category] for [condition]?` |
| Information (问题解决) | Ask how to solve a problem or reach a goal; AI answers with advice, read for citation only | `How can I [solve problem / reach goal]?` |

The wording is chosen once, when the Prompt is written, and never changed afterwards: on some platforms the phrasing moves the answer (*Discovery Quality* → any natural opening), so readings are compared over time on the same Prompt, never across two wordings. For a non-English market, write in the local buyers' own phrasing rather than translating an English form. Locked Prompts and existing banks are not rewritten (*Maintenance*: a formal Prompt's wording is immutable). The validator does not check the form. A very short no-condition anchor such as `Best dash cams` trips the four-words-or-fewer warning; record it as deliberate.

**Evaluation wording** (Suda 2026-10-29, replacing the 2026-10-22 report-wording default). Write an Evaluation Prompt the way a buyer asks about one named brand, with the use case or scope it hinges on — `Is {brand} worth it for {use case}?`, `Is {brand} a good {category} for {use case}?` — because the monitored reading is what a buyer sees when they ask. Without a use case AI picks its own dimensions and the answer maps onto no attribute. The report wording `Evaluate the {category} company {brand} on {scope}` stays out of monitoring. It is used in the research pre-run before the attribute pool (*How Attributes Are Derived* → Step 2), for the brand and each competitor, and as a **diagnostic** in the bank only when the task is to read AI's full appraisal of the brand, regulator and recall records included; say so in 出题原因. Never both wordings for one decision. They return different answers (2026-10-22, ChatGPT + Gemini US, 4 brands × 3 runs — a small sample, read as direction): the buyer wording averages 599 words, gives a direct verdict, compares against other brands more often (1.6 vs 0.6 named — more useful when Evaluation answers re-check 相对竞品) and did not raise the Swisse recall (0/3); the report wording averages 1072 words, cites more sources and surfaces regulator and recall records (Swisse recall in 3/3 ChatGPT answers). That the buyer wording missed the recall is itself the reading: a buyer asking does not see it. Locked Prompts and existing banks keep their wording.

**Named-competitor alternatives.** An Alternatives Prompt asks for alternatives to one named competitor without naming the target brand (`What are the alternatives to [competitor] for [scope]?`), at most one per Topic and only when evidence shows buyers hold that competitor as a current option. It reads the buyer's real candidate set rather than a head-to-head verdict (banks written before 2026-10-22 type it Competitor).

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

**Category Awareness in after-sales** runs only in the research pre-run (Suda 2026-10-29; *How Attributes Are Derived* → Step 2): one per product line and market language, one run per monitored platform, before the pool is judged. Ask how to choose ("What should I look for when choosing an automatic litter box?"), never how to fix or use something — how-to and troubleshooting questions return advice without criteria. When such a question carries real buyer demand and the brand wants its pages cited, write it as an Information Prompt instead. It is not written into the bank, not trialled and not monitored.

The first staged set is `Discovery`, plus `Information` only where the brand party's 业务目标 or 核心可见度问题 names the need: lock the Discovery group first, then add
Competitor, Alternatives or Evaluation as the
situation requires, each only when its separate business question and evidence
contract are present; none has a fixed quota. Verification and Accuracy come
later, as diagnostics. The reference mix (Discovery at least half; SKILL.md
Workflow step 7) describes that allocation, not a first-set quota, and never
justifies adding a type to fill a slot.

### Discovery Quality

Discovery is the formal visibility population. It must be a natural commercial recommendation or selection question:

- no target brand or competitor names;
- category is recognizable;
- one main decision;
- enough buyer context to produce named providers or platforms;
- no pure methodology, trend, or educational question unless a separate problem-awareness track is explicitly requested;
- **the wording must ask for candidates** — which / best / top / recommend / options / alternatives / where to buy or source. A "How do I fix X" question gets advice back and no brand list: Pbrand's "How do I get rid of litter box smell in a home with multiple cats?" returned zero brands in 5 of 5 ChatGPT US runs (2026-10-15), while the same need asked as "Which automatic litter boxes seal in odor best between bag changes?" listed brands every run. The validator fails English Discovery Prompts without a candidate ask. A problem-awareness Prompt kept on purpose is set `formal_visibility_eligible: false` so it stays out of the visibility statistic and passes the gate;
- **conditions follow real demand**: real user prompts carry a lot of situation (measured user prompts run to a ~20-word median, delegated questions about 37%, keyword-style only about 3%), so mix no-condition Prompts with Prompts carrying a buyer, scenario, or constraint in roughly the proportions the cited quotes show. The sentence around those conditions reads like a buyer in that market asking; it need not reproduce one user's phrasing, and it meets the type's requirements in *Reference wording per prompt type*;
- **do not rewrite an existing "Which …" Prompt only to make it sound more personal.** Adding a first-person situation that carries the same decision ("I travel a lot for work. Which automatic litter box lets me check…") did not move target-brand mention in a 2026-10-15 ChatGPT US test (Pbrand, 6 pairs × 5 runs: 63% → 50%, Fisher p=0.44), but the answers named fewer brands (one pair 4.2 → 2.2 on average), so long-tail competitors drop out of the competitor reading. Add a buyer situation when it changes the expected candidate set (a condition slot below), not for tone — which is exactly why a Prompt filed under a non-base audience must name that audience (*Audience Segments* → Step 6). Tested on ChatGPT only; re-test on Gemini and AI Mode before applying the same conclusion there;
- **any natural opening works for Discovery** (Suda 2026-10-29, replacing the 2026-10-26 `Best …`-only rule): `Best …`, `What are the best …`, `Which …` and `… recommend` are all fine. On ChatGPT the opening alone barely moves the answer: in a 2026-10-16 US test (Pbrand, 6 pairs × 5 runs, same conditions, only the opening changed) answers named 3.70 → 3.67 brands on average (paired t=-0.15) and target mention went 83% → 87% (Fisher p=1.00). On AI Overviews it does: a short form and a question form for the same need shared only 43% of their brands, against 65% for the same wording run twice (2026-10-22, 6 pairs × 3 runs, US). So the opening is chosen once when the Prompt is written, an AIO reading is compared only with readings of the same Prompt, and a variant of an existing Prompt that changes only the opening is a near-duplicate (see Topic-level rules);
- **status-quo alternatives, service categories only.** When the business model is B2B or the category is delivered as a project, subscription or labour service, a Topic may carry at most one Prompt for buyers leaving the status quo (in-house, manual, current setup). Write the status quo as a condition and still ask for providers: `Which [category] providers can a company use instead of [current way]?`. Do not write `What are the options besides handling [X] in-house?` — AI answers with a list of approaches and names brands only in passing (2026-10-22 ChatGPT US: the marketing pair named 0 brands that way and 6 the provider way). It is a different decision from choosing among providers, so it is not a near-duplicate of the category entry Prompt. Physical goods and hardware do not get one; their buyers do not face a build-or-buy choice.
- **a superlative opening needs no generic noun and no question word.** `Best dash cams for rideshare drivers`, `Best dash cam for night driving` and `What is the best dash cam for night driving?` all ask for candidates; both validators accept best/top followed by a product noun, singular or plural (Suda 2026-10-26), and still reject method or attribute asks (`best ways / practices / tips / time / temperature`, `best dash cam features`) and a superlative with no product (`Best for …`, `Best price`). The validator gates nothing beyond that; a short `Best …` and a full question for the same decision are near-duplicates — keep one.
- no redundant containment wording, such as a broad region plus a subregion that is already included;
- classify every qualified Prompt into one of the four condition slots used by 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」, and keep those names: **无限定条件** (no qualifier), **目标用户** (target user), **偏好标准** (preference criteria), **约束** (constraint). Pain points sit under 偏好标准 — they are a dimension buyers weigh while comparing, not a fifth slot. Retain a mix across the four whenever the condition changes the expected candidate set.

Topic-level rules:

- no candidate Topic needs a no-qualifier (无限定条件) Discovery Prompt; a bare category Prompt is written only when the brand party asks for the head term (Suda 2026-10-29);
- **Compound conditions: up to three conditions by default; four or more go through a reality review** (Suda 2026-10-28; revised 2026-10-29). The market and the product category are not counted as conditions. Every condition in a Prompt has buyer evidence of its own (gate 36 — different cited quotes may carry different conditions; a single quote stating them together is not required). **One to three conditions** need nothing more: write them the way buyers ask — Kenyan forum posts and the 2026-10-29 Obrand experiment's natural task Prompts carried up to three. **Four or more conditions** must pass a reality review before the trial: a buyer quote that states them together, or a written reason in 出题原因 that this combination is a real, frequent purchase task — a named business scenario or audience, or a common-sense reason buyers in that situation weigh them together. A combination that buyers rarely weigh together, or that no product on sale satisfies (premium ANC under the cheapest budget tier), fails the review. **Brand advantage decides which buyer needs get Prompts and which go first within a tier (优势 before 持平); it is never the reason a combination is real** — that buyers weigh two needs together is shown by quotes or a buyer-side reason, not by the brand having both. At any count, write the buyer's wording for each need, never the brand's spec value (ask for long battery life, not 45 hours; gate 36 fails a number no cited quote states). At any count the trial decides whether a condition stays: a Prompt whose candidate set does not differ from the Prompt without that condition (brand-set overlap between the two Prompts' runs not below the paired Prompt's own run-to-run overlap) merges back — in the Obrand experiment a third condition (battery life after budget plus sound or ANC) changed nothing and often did not even reach ChatGPT's search query. Stacking conditions to look thorough is prohibited. Each compound Prompt counts as one decision need in the row's 目标题数;
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

**The trial is quality validation plus exploratory diagnosis, never an early baseline** (Suda 2026-10-22 / 2026-10-23 / 2026-10-27, adopting Profound's pre-tracking answer check, Aleyda's small-batch validation and Momentic Atlas's 3 platforms × 3). Every candidate Prompt that can be written before collection runs 3 times on **each platform the engagement will monitor**, 5 at most per platform; each run is a separate, history-free session with the market, language, platform mode and collection method fixed — never the same conversation asked three times. A platform that cannot be collected in the market is left out.

**Which Prompts enter the trial** (Suda 2026-10-27, unifying the collection pass; Category Awareness moved to the pre-run 2026-10-29): Discovery, Alternatives, Competitor, Evaluation, and any first-round Information (问题解决) the brand party named, **plus** any named-brand Evaluation Prompt that has brand-search demand backing (GSC or GA4 top queries). Verification and Accuracy Prompts are not in the trial: Verification is written after the formal baseline reads low on its attribute, Accuracy once the brand party has confirmed the right answer; each is read once, then re-run only on an event trigger (see *Prompt Priorities*).

**One write-back pass after every trial run is collected** (Suda 2026-10-27):
1. Judge `prompt_validity` per Prompt (合格 / 修改 / 淘汰); reword and cull following the table below.
2. Mark `可改变性` (高 / 中 / 低) on every trialled Prompt from the top 20 cited domains (*Priority* → 可改变性 per Prompt, with the government-citation caution); mark an initial AI 认知差距 as 试跑初判 where the answers show it. Re-checked on the formal baseline.
3. Read every trial answer for a buying criterion the pool still lacks (the pre-run should have caught most); add it only after the same research as any attribute. New attributes added this way that carry Prompts need one 3-run pass for those Prompts.
4. Where Competitor or Evaluation answers contradict a `相对竞品` judgement (the research pre-run did the main check; Suda 2026-10-29), **re-check** it: open every link the answer cites and verify that the claimed capability, price, or spec is present on that page — do not rely on AI's summary. When the trial reading contradicts a pool judgement, write the finding in the attribute's 判据与证据, labelled 「试跑发现：…」; the 相对竞品 cell may be changed only after the brand party reviews it.
5. Mark any brand fact the answers state wrongly in that attribute's 判据与证据, labelled 「AI 错误：…」, and add it to 品牌事实核查. It becomes an Accuracy Prompt only if it passes the three conditions (SKILL.md Workflow step 7 → Accuracy); it is never trialled.
6. **Re-run the reason script and check the Topics**: `write_prompt_reasons.py` re-reads the rows and the 可改变性 values and rewrites 优先级 (where not hand-changed) and 出题原因 per Prompt. When two groups of Prompts in one Topic surfaced clearly different competitor lists, split the Topic — the one case after writing that moves a Topic. An attribute whose 相对竞品 turned 劣势 (accepted by the brand party) is taken off its rows.

**Brand readings — mention, position, competitor-only — never enter a verdict and never drive selection.** An answer recommending competitors but not the brand is kept (that is the opportunity); a stable brand presence is not a reason to cut. **The brand's own readings are transparent context, not selection input** — mention counts, positions in the answer, cited sources, and query fan-out go to the client as a separate trial report (a single HTML file, built by `geo-monitoring` → 质量试跑), marked 「供参考，不作统计」; they never enter the Base, never enter a statistic, never drive selection, and are never treated as a stable mention rate (Suda 2026-10-23 / 2026-10-27).

Check the market coverage pass first. Then read each answer for five things: whether AI understood the category and intent; whether the answer task matches the prompt type (Discovery returns named candidates, Competitor returns a verdict rather than "it depends", Verification recognises or denies the capability, Information gives advice); whether the answer reaches the target segment rather than the broad category; whether it is substantively identical to another Prompt's answer with no new decision inside; and whether repeated runs and platforms agree. Judge per platform:

| What the three runs show | Action |
|---|---|
| All pass the checks | Keep; done |
| Two or three fail the same way (a Discovery Prompt turns into an explainer, AI answers a different category) | Reword or cull — the failure is the wording |
| Only one fails, or the runs disagree on intent, category or answer type | Run two more on that platform (five in total); reword only if at least three of five fail, otherwise keep and mark 高波动 — no further runs |
| Category and intent right, but the brand list changes a lot between runs | Keep without rewording; mark 高波动 |
| Only one platform fails (answers a different category, never triggers an AI Overview, refuses) while the others pass | If the wording causes it, reword and rerun on every platform; if it is the platform's behaviour, keep the Prompt and record that platform as excluded for it, with the reason |

A misread or mismatch is reworded or culled; an unsegmented answer is reworded first; a same-answer pair goes back through the dedup rule. A 高波动 mark goes in the internal diff; it tells the formal baseline to read that Prompt's runs with care, and it is never a reason to cull. Record reworded and culled Prompts with reasons in the internal diff.

Do not let trial answers pick the Prompts most likely to show improvement — the selection input stays row priority and buyer evidence (sample-selection bias poisons every later delta; Peec's 2026-09 finding: representative Prompt coverage beats more runs of the same questions). **Whether a direction can be moved is the 可改变性 reading, not a reason to drop a Prompt**: a Prompt resting on sources the brand cannot reach drops a tier and gets no promise of improvement (see *Topic and Attribute Selection Criteria*); a single or zero mention never enters that judgement.

**What the trial produces:**

1. **`prompt_validity` per Prompt** — 合格 (wording fits the intent and category, answer on-task, no ambiguity or duplication) / 修改 (reword and rerun) / 淘汰 (merge or drop). Two or three runs failing the same way means reword or cull; one failure or disagreeing runs adds two runs (five at most — reword only at three of five, otherwise keep and mark 高波动). **Target-brand mention is never a pass/fail criterion** — a valid 0/3 Discovery Prompt is kept.
2. **`可改变性` per trialled Prompt** (高 / 中 / 低), from the top 20 cited domains of its runs, with its basis; and an initial **AI 认知差距** (试跑初判). Re-checked on the formal baseline. The brand's own mention position is not recorded in the Base.
3. **Exploratory readings as transparent context**: brand and competitor mention counts, positions in the answer, cited sources, query fan-out. These readings go to the client as a separate trial report (a single HTML file), never as columns in the Base (Suda 2026-10-23, matching the template's 使用说明); they never enter a statistic, never drive selection, and are never treated as a stable mention rate.

**A reworded Prompt is rerun; its new readings replace the old.** Trials where the Prompt text changed are not concatenated. After the trial, each candidate Prompt has `prompt_validity`, a 可改变性 value, and exploratory readings retained in `trial.evidence_refs`.

## Stage 4: Opportunity Ranking and Client Selection

**Selection reads the matrix-row tier, dropped once only by 可改变性 低** (Suda 2026-10-23 / 2026-10-28). Trial readings go to the client in the separate trial report; they do not drive the recommendation order. The rule this enforces: picking Prompts that happened to read low, then crediting their regression to the mean as optimisation, is the failure Peec, Aleyda and Ahrefs all warn about; and a brand's own trial mention rate is exactly that reading.

**What may adjust the tier in selection:**

- **可改变性 = 低** (down one tier, once): the Prompt's top 20 cited domains are mostly sources the brand cannot reach (*Priority* → 可改变性 per Prompt).
- A hand change on 提示词库 优先级 with its 「改档」 line.
- An answer that names no brand at all is a wording check in stage 3 (does the Prompt really ask for candidates?), not a tier adjustment.

**What does NOT adjust the tier in selection** (Suda 2026-10-23):

- The brand's own mention rate — neither 0/3 nor 3/3 changes whether the Prompt is recommended.
- How far the brand trails or leads — that reading is computed in the baseline report and used only for optimisation ordering.
- AI 认知差距 — an initial trial reading and a final baseline reading, never used to drop a Prompt.

**Formal slot filling: tier first; within a tier Discovery (at least half), Alternatives, Competitor, Information (问题解决), then the rest; within one type, 优势 before 持平** (Suda 2026-10-23 / 2026-10-26 / 2026-10-28). Trial readings do not order a tier.

**At most 10 Prompts per purchased Topic enter the formal set.** The brand party picks among 已批准 Prompts. When it confirms, lock the set: the selected Prompts move to 状态 **正式** and every other candidate is deleted from the Base, its question_id and reason kept in the bank's `config.retired` with bank status 停测 (Suda 2026-10-23 — 正式 means "in the formal set" and is set at lock, not after the baseline, so monitoring knows exactly which Prompts to collect; the Base holds only Prompts under test, client-facing-attribute-pool.md → *The Base holds only Prompts under test*). Save the immutable version, lock the assessment scope (Stage 5), and hand both to `geo-monitoring` for the formal baseline and periodic collection.

### The final deliverable table

The working output is one reconciled master table, not a separate attribute table plus a separate intent table. The customer-facing confirmation document may still show separate sections for readability (品牌事实, 属性池, 主题与问题) as specified in [client-facing-attribute-pool.md](client-facing-attribute-pool.md); before delivery, reconcile them back to the master relationship. Its reference shape:

`优先级 | 品牌属性 | 客户问题与场景 | Topic | Query | Query 类型 | 选择理由`

This shape is a reference, not a validation checklist — a deliverable is not wrong for arranging columns differently, only for violating the rules below. Do not add columns that carry the same information twice: attribute explanation and evidence live inside 选择理由 or the attribute pool's 备注/还缺什么 columns, so a separate 属性说明与证据 column is redundant. Column naming (Prompt vs Query, Chinese vs English headers) is free as long as one document uses one term consistently.

- **品牌事实 stays a separate table up front** (brand, domain, business model, category, ICP, target customer, geography, applicable boundary) — it is confirmed once for accuracy, then not revisited.
- **品牌属性 and 客户问题与场景 stay adjacent but are never merged.** The entire act of translation lives in the gap between them; merging them silently asserts "attribute = intent", which is the failure this section exists to prevent.
- **Reconcile the matrix against the Prompt set in both directions before delivery.** Every P1/P2 row's planned needs must be carried by Prompts, and every Prompt must sit on a row. Run it as an explicit step (`check_client_base.py`), not by eye.
- **In the Base the brand party edits cells directly and marks 状态 on 提示词库; there is no 客户确认 column** (Suda 2026-10-15; we snapshot before sending and diff on collection). **Document-format pieces carry a 客户确认 column, and its convention is write-what-to-change.** The client writes only in the rows that need a correction, a deletion, or an addition, and leaves every other cell blank — never an all-rows "confirmed" reply, and never a per-row 确认 that has to be filled in for the table to count as reviewed. Question numbering stays out of the client document entirely.
- **选择理由 carries answer-layer evidence only** — a fixed pattern such as "competitors are negatively mentioned on this theme (Stera 33%, RivalA1 0%), we are at zero" — never free-text reasoning, which gets pulled around by "the client says this matters".
- **P3 rows stay visible on the matrix but receive no Prompts.** Only P1/P2 rows carry Prompts; verify this before delivery.
- A paraphrased row nobody can source is tagged **待验证** rather than quietly kept.
- Use empty cells rather than merged (rowspan) cells down a column, because the client edits the table in Feishu and merged cells misalign when rows are inserted or deleted.

### The consolidated master table

The end of the whole chain is one table. **The reference shape** — the reference shape only, per the note above:

`优先级 | 主题 | 核心属性 | 限定属性 | 问题 | 来源依据 | 售前结果 | 正式基线 | 是否正式优化`

**Keep the 售前结果 and 正式基线 columns side by side.** They make the two-pass priority auditable: the latter supplies an initial reading rather than proof that a gap is stable.

**核心属性 and 限定属性 are two roles, not two trees.** The core attribute is the perception that makes the Topic worth watching on its own; the qualifiers are the pool attributes relevant to this Topic that change how a question is asked. Once an attribute is selected as a core attribute it stops also serving as a qualifier. Selecting the core attribute is the first layer; picking qualifiers is the second, and the second layer is a **filter, not a re-rank** — it asks only "is it relevant?" and "is it worth a share of the query budget?", and the same attribute may take different tiers in different Topics without the pool being re-sorted.

**限定属性 fall into four slots, named as in 《海外 GEO 售前诊断报告 V2 PRD》 → 「细分主题」**: 无限定条件 (no qualifier) / 目标用户 (target user) / 偏好标准 (preference criteria) / 约束 (constraint). Pain points belong under 偏好标准 — a dimension buyers weigh while comparing, not a fifth slot. No Prompt sits in 无限定条件 unless the brand party asked for the head term; Prompts carry one to three conditions by default, and four or more only after the reality review under *Compound conditions* in the Topic-level rules.

**「是否正式优化」 is filled by us after the baseline**, never by the client. The baseline result can justify an initial action with uncertainty recorded; it cannot certify a stable gap. Leave the column blank during presales rather than writing a placeholder.

**An attribute earns rows that cluster into a Topic of their own** only when they form an independent competitive situation: a materially different competitor set, a changed evaluation standard, or a wholly different content strategy. That is the same clustering test that governs Topic boundaries — competition set or evaluation standard differs, so split.

## Stage 5: Formal Baseline (Each Query × Each Platform × Each Country × Each Language × 30 Runs)

**The formal baseline is the Before benchmark** (Suda 2026-10-23). Multi-platform collection runs only after the client confirms the formal set, at **30 runs per query per platform per country per language** (Suda 2026-10-23, raising the earlier 5–10). The sampling unit is stated in full so no N-round multiplier is implied: query × platform × country × language = one cell, 30 independent runs in it. Whether those 30 are split across days is undecided (Suda 2026-10-23) — decide per engagement and record it in `collection_config`, because a spread window measures a different thing from one sitting; until decided, run in one sitting and say so in the report. This is the reproducible initial measurement against which later windows are compared. It produces:

- Formal per-platform visibility and citation readings.
- 可改变性 re-checked per Prompt on the pooled baseline answers' top 20 cited domains.
- Each Prompt's competition pattern (five values) computed from the 30 runs per cell, and the optimisation order derived from it (baseline-report.md → *优化顺序*) and written back per Prompt into 提示词库 优化顺序; the selection 优先级 on 提示词库 is never rewritten by it.
- AI 认知差距 per Prompt (知道但不推荐 / 不知道该能力 / 无人讨论 / 无缺口), judged from each Prompt’s own answer text — the final reading replacing the trial's 试跑初判.
- Provisional optimisation order and a feasibility assessment for the delivery commitment.

**Where an attribute on a P1 row reads low mention in its Discovery Prompts, add one Verification Prompt on the same attribute** (Profound ch3, adopted 2026-10-22) — a diagnostic outside the formal set, with no slot, version or KPI effect (Suda 2026-10-27); an attribute on a P2 row whose 相对竞品 is 优势 may get one too (Suda 2026-10-26) — its answer splits the gap into 知道但不推荐 (off-site work) vs 不知道该能力 (on-site work). Once it has split the gap it is re-run only on an event trigger (Suda 2026-10-26): while AI confirms the capability in fewer than 80% of answers, after the on-site fix goes live; at 80% or more, when the capability or its official page changes.

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
the research pre-run, and do not forbid optimizing the category
observation Topic.

## Stage 6: Optimisation and Continuous Monitoring

Content and page optimisation based on the baseline diagnosis. Prompts in 状态 = 正式 run each period under the contracted cadence; the formal set’s mention rate is the KPI. Same-question, same-condition, same-caliber window comparison establishes whether gaps are persistent and whether optimisation improved them. Single-day comparisons and immediate-effect promises are not supported by the data.

Optimisation work follows the order computed in the baseline report (tier, then competition pattern, then 优势 before 持平; geo-monitoring baseline-report.md → *优化顺序*); actions are handed to the content team as a gap-cause-action table. `geo-monitoring` owns the cadence, re-run triggers, and the ongoing analysis.

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
