# Representative Prompt Library Adaptation

This is the project's internal adaptation of Aleyda Solis's
`Representative AI Search Prompt Library` guidance. It governs how we check
attribute coverage and market representativeness before writing Prompts. It is
an internal working reference, not a customer-facing methodology note.

Source: https://www.aleydasolis.com/en/ai-search/ai-search-prompt-library/
(published June 8, 2026; updated June 17, 2026). Its sample prompt counts,
test runs and refresh cadences are illustrative, not this project's quotas or
collection protocol.

## Core Rule

Representative does not mean exhaustive. A useful library samples the
AI-assisted journeys that matter to the business and is:

- segmented rather than random;
- stable enough to compare over time;
- flexible enough to add emerging opportunities;
- tied to a business decision and a possible action.

Do not use a global prompt set as the default evidence for every market.
Reuse a candidate intent only after the local market review shows that the
buyer decision, category meaning, and expected answer set are materially
equivalent. Otherwise localize, split, add, or retire the market version.

## Start From Business Questions

Before the coverage pass, write down what decisions the library must support
(Aleyda step 1). This is the scope half of the attribute-pool work, not a
separate customer form; most answers already sit in the Case and the scope
confirmation, so record only what is missing:

- which products, service lines, categories or markets matter most right now,
  and whether lines need separate Cases or Prompt groups;
- which audiences must be represented, and whether they **ask differently,
  use different terms, or compare different alternatives** — if they do, that
  difference becomes Prompt wording or a split, not one shared phrasing;
- which journey stages matter most (discovery, evaluation, comparison,
  validation, transaction, post-purchase);
- which countries and languages are strategic;
- which competitors apply per product line, market or audience;
- **which conversion path the visibility should feed** — purchase, lead or
  enquiry, signup, demo, booking, subscription, store visit. It decides which
  journey stages and Topics carry weight;
- which visibility gaps would actually change what we optimise next. A slice
  whose result would change nothing is planning context, not a Prompt.

## Internal Coverage Pass

Before writing individual Prompts, build a lightweight internal coverage pass
for each priority market/language. It is a gap check we draft and the brand
party reviews (the 提示词矩阵 table of the client Base); it is not a form the
client fills from scratch, and not a Cartesian-product quota.

Review the intersections that can change the decision:

`product/service line × buyer/persona × journey stage × market/language × buyer constraint × competitor/alternative set × business priority`

**One matrix, not two.** Aleyda's prompt matrix (step 5) and our attribute
pool merge into one table — the client Base's 提示词矩阵. One row is **one
buyer situation × one tested attribute**: her columns describe the slice, ours
add the attribute and its priority judgement. The column set, per-row rules
and the priority formula are defined once in
[client-facing-attribute-pool.md](client-facing-attribute-pool.md) →
*提示词矩阵*; the internal handoff keeps only what the client does not see
(market decision and its evidence date, reuse reasoning).

Two properties make the table do its job. Every Prompt links one row
(`已有问题 / 已有题数`), so a P1 row with no Prompt is visible; and every
attribute without a Prompt still has a row whose 备注 says why, so an
attribute nobody tests cannot disappear silently. Fill only the slices that
change a decision; empty intersections are expected, and the row set is
generated from the bank, not planned as a Cartesian product.

Dimensions that sound separate but are not:
- **Audience vs journey state.** 「已在比较具体品牌」, 「准备下单」 and the like
  are stages, not audiences. Audience is who the buyer is; with no group
  condition it is 「通用」.
- **Buyer task vs journey stage.** One column, the eight stages
  `发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持`.
- **Business priority vs attribute priority.** Rating audiences 高/中 by
  whether the brand party listed them restates importance; rating them by
  where P1 attributes cluster restates attribute priority. Keep only the
  attribute priority, judged per row through 购买影响.

Adapt the uncertainty to the business model: ecommerce may hinge on
availability, delivery and returns; SaaS on integration, onboarding,
security and limits; B2B services on proof, process and service terms;
finance on eligibility, risk and local regulation; travel on itinerary,
booking and local supply. These are gap-check prompts, not required
Attributes or a fixed Prompt mix.

When checking the buyer-constraint dimension, walk this constraint-type
list instead of stopping at "budget": price/budget, buyer or team size,
industry/vertical, geography, language, use case, integration/compatibility,
trust/compliance, urgency, user profile (beginner/expert, family, agency),
and stated preference (e.g. sustainable, premium, low-risk). It is a
gap-check list, not a quota: a constraint type earns a Prompt or Attribute
only when evidence shows it changes the buyer decision; a plausible but
unevidenced type routes to customer confirmation or the research backlog,
never gets invented.

For each meaningful slice, record:

- the buyer decision or uncertainty;
- the relevant Attribute(s);
- local evidence and its date;
- whether the slice is shared-equivalent, localized, market-specific, or not
  supported;
- the candidate Topic/Prompt destination, or the reason it stays an evidence
  gap.

The coverage pass must consider, when relevant:

- local competitors and substitutes;
- local terminology, units, currency and price framing;
- local publishers, marketplaces, directories and source ecosystems;
- local regulation, eligibility and trust signals;
- local availability, delivery and service expectations;
- local audience, use case and purchase-stage differences.

**Test language follows the language the buyer decides in.** Ask which
language screened this buyer (admission, procurement or contract language),
then local English proficiency. Buyers who decide in the local language are
tested in it; where a Topic's buyers already passed an English threshold, a
local-language reading is a conservative floor and the report says so; where
both languages carry many real buyers, test both, each with its own version
and baseline.

**The market comes from collection settings; Prompts carry no place by
default.** Region, proxy and language are fixed in the collection config, so
a Prompt does not add a country or city unless the place is itself a buying
condition (import compliance for the US, returning to work in Thailand).
Keep one convention within a Prompt group.

The filled slices go into the 提示词矩阵 table of the client confirmation Base
(decided 2026-10-14; attribute pool folded in 2026-10-15), so the brand party sees which buyer situations are
covered and can point out missing ones. Show only slices that change a
decision — never pad empty intersections for completeness — and keep the
evidence notes behind reuse decisions (dates, shared/localized reasoning) in
the internal handoff. The customer confirms facts, priorities and missing
business context; we make the coverage and Prompt design judgement.

## Prompt Construction

Use real audience language from multiple evidence types:

- sales, CRM, support, renewal, win/loss and site-search language;
- search demand, GSC, PAA and AI traffic or grounding signals;
- reviews, communities, competitor comparisons and local source pages.

Treat these sources differently. Search data anchors demand; first-party
records reveal constraints and objections; reviews and communities reveal
alternative language; AI answers reveal the source and competitor ecosystem.
AI grounding/retrieval queries (e.g. Bing Webmaster Tools AI Performance)
are the machine's retrieval phrasing, not user prompts — use them to
stress-test Prompt wording and source coverage, never copy them in as
Prompts. Do not call a generated phrase high-frequency without frequency
evidence.

Log every piece of audience language as one row, so each Prompt can point
back to its evidence (Aleyda step 7, her workbook's 受众输入 sheet):

`输入编号 | 产品线 | 涉及品牌 | 来源类型 | 原话（保留原语言） | 中文意思 | 受众 | 旅程阶段 | 约束或场景 | 来源说明 | 来源链接 | 收集日期 | 证据可信度（高/中/低）`

(Market/language is fixed per Base; 受众 and 旅程阶段 use the 提示词矩阵 sets;
rules for 涉及品牌 and 来源类型 are in client-facing-attribute-pool.md →
*买家原话*.)

A Prompt's evidence field cites the 输入编号. Client records enter only after
anonymisation (see [signal-sources.md](signal-sources.md)). A Prompt whose
evidence row is missing a link or date is not evidence-complete.

Create Prompt groups before judging individual results. At minimum group by
market/language, product line, audience, journey, constraint, competitor set,
Prompt Task and business priority. Create variants only when they test a
meaningful difference in buyer, market, use case, competitor, constraint or
journey stage. Two framing contrasts are easy to miss and worth an explicit
check: generic vs constrained (the same need with a real buyer constraint
attached), and feature vs outcome (buyers often ask for the outcome —
"tools that alert me when X happens" — not the capability name; a pool
whose Prompts are all capability-phrased under-represents how buyers ask).

## Prompt Task and Intent

Prompt Task describes the buyer's job. Intent describes the downstream
analysis contract. They are separate dimensions; a Task label never changes
`analysis_type`, `formal_visibility_eligible`, or formal metric scope.

Use these task types when they add real coverage:

- `Discovery`: explore a category or provider set;
- `Problem Solving`: find a solution to a concrete problem;
- `Evaluation`: judge fit, quality, trust or suitability of a named option;
- `Comparison`: compare named options;
- `Alternatives`: look beyond a known option;
- `Shortlist`: narrow providers or products to consider;
- `Validation`: check credibility, proof, eligibility or risk;
- `Transaction`: price, availability, booking, purchase or signup;
- `Post-purchase Support`: setup, return, cancellation, renewal or troubleshooting;
- `Category Understanding`: understand a category and its decision criteria;
- `Source Discovery`: identify sources, reviews or evidence shaping the answer.

Common mappings are only defaults:

| Prompt Task | Common Intent | Boundary |
|---|---|---|
| Discovery / Shortlist | Discovery | Non-branded candidate selection |
| Alternatives | Discovery or separate exploration | Non-branded alternatives can be Discovery; "alternatives to [named brand]" does not fit the current default Discovery or one-to-one Competitor contract |
| Problem Solving | Discovery or Category Awareness | Only enter core visibility when the task asks for a solution/provider |
| Evaluation | Evaluation | Named-brand fit or quality judgement |
| Comparison | Competitor | One-to-one named comparison |
| Validation | Verification, Accuracy, or Evaluation | Depends on capability, fact, or trust question |
| Transaction | Separate transaction contract | Price/availability alone is not a provider-selection Discovery question |
| Post-purchase Support | Separate support contract | Does not enter default natural-discovery metrics |
| Category Understanding | Category Awareness | Category framing and decision criteria |
| Source Discovery | Separate research task | Studies source ecosystem, not brand visibility |

The first staged set may use several task labels while remaining
`Intent: Discovery`, but only when every question still meets the Discovery
contract. Do not create a question just to fill a task type.

## Library Sizing

Size the library by independent decision coverage, not a universal Prompt
quota. Explain growth using the number of priority product/service lines,
materially different buyers and markets, journey decisions, competitor or
substitute sets, and high-impact constraints. Do not multiply every dimension.
When a slice does not change the decision or expected answer set, retain it as
planning context, not a new Prompt. When evidence cannot support an
independent decision, record the gap instead of padding the bank. Presales
still obeys its separate Topic minimum and batch maximum.

## Alternatives and Action Link

Distinguish direct competitors from substitutes and the status quo in each
market: manual work, an internal team, an incumbent supplier, a marketplace
or retailer, or an adjacent category. Also check the options buyers really
weigh that are easy to miss: aggregators and review platforms, free or
open-source and do-it-yourself alternatives, local players, and the brands the
client's sales team hears most often (ask for that list with the sales
records). Compare against what buyers consider, not only the brands the client
wants to beat. Do not silently freeze a new official
competitor; use these alternatives to check the buyer's actual candidate set
and hand competitor changes to the owning research skill.

Each Prompt group should state the business question it tests and the
possible action its answer would inform, such as positioning, owned content,
third-party evidence, product proof or a market decision. This is a planning
purpose, not an observed finding or impact promise.

## Review Before the Candidate Baseline

Before running the candidate baseline (Aleyda step 18), check the set by hand,
not only through the validator:

- do the Prompts sound like real buyers, in local wording;
- do the Prompt groups follow business priority and the conversion path;
- are the priority product lines, audiences and markets all represented;
- are the constraints realistic rather than invented;
- does the competitor/alternative set reflect what buyers actually weigh;
- is the set over-weighted to one journey stage;
- is any Prompt only a meaningless micro-variant of another;
- would each group's result lead to an action someone can take.

If a sample produces no useful diagnostic pattern, adding more Prompts will
not fix it — fix the scope or the wording first.

## Roles and Refresh

Classify each Prompt group as one of:

- `core`: stable, high-priority Prompts used for recurring comparison;
- `experimental`: new market, audience, constraint, competitor or emerging
  intent under evaluation;
- `monitoring`: representation, reputation, risk, compliance or competitor
  change surveillance.

Keep the core stable for comparison. Review affected groups immediately when
products, markets, pricing models, regulation or major competitors change.
A major platform change (new model version, answer-format overhaul, a
platform added or dropped) is also a review trigger: re-baseline the
affected comparisons instead of reading the before/after difference as a
brand-visibility trend.
For active work, review commercial and representation groups about monthly;
review market terminology, competitor/alternative sets and source ecosystems
about quarterly; review the full attribute pool and library every 6-12 months.
These are review prompts, not automatic replacement deadlines. Add emerging
ideas to `experimental` first and move them to `core` only after local
evidence, customer confirmation and the project's trial/lock process. Retire
only for a documented business or evidence reason, not an inconvenient result.

This reference defines what to monitor and why. Session state, run logs,
platform model versions, raw answers, rates and citation measurement belong to
the collection and reporting skills; do not add their schema here.
