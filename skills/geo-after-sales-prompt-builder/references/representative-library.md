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

## Internal Coverage Pass

Before writing individual Prompts, build a lightweight internal coverage pass
for each priority market/language. It is a gap check, not a customer form and
not a Cartesian-product quota.

Review the intersections that can change the decision:

`product/service line × buyer/persona × journey stage × market/language × buyer constraint × competitor/alternative set × business priority`

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

Do not expose the full matrix to the customer. Fold meaningful findings into
the existing customer-facing `品牌事实`, `属性池`, and `监测主题与问题`
sections. The customer confirms facts, priorities and missing business
context; we make the coverage and Prompt design judgement.

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
or retailer, or an adjacent category. Do not silently freeze a new official
competitor; use these alternatives to check the buyer's actual candidate set
and hand competitor changes to the owning research skill.

Each Prompt group should state the business question it tests and the
possible action its answer would inform, such as positioning, owned content,
third-party evidence, product proof or a market decision. This is a planning
purpose, not an observed finding or impact promise.

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
