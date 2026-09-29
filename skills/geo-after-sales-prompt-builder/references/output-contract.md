# After-Sales Output Contract

This is the practical after-sales extension contract. It is intentionally
separate from the presales v8 fixed-quota validator.

## Customer-Facing Confirmation Artifact

When the task includes client review of scope, attributes, Topics, or candidate Prompts, deliver a separate Chinese confirmation document in addition to JSON/CSV. Follow [client-facing-attribute-pool.md](client-facing-attribute-pool.md). Its minimum structure is:

- opening scope and monitoring object;
- `核对时从哪里判断` guidance adapted to B2B or B2C;
- a separate `品牌事实【请核对】` table;
- `属性池【请核对】` with `购买影响`, `相对竞品`, `优先级`, evidence-gap fields, and `客户确认`;
- optional candidate `监测主题与问题【请核对】` table;
- optional competitor confirmation table;
- trial / lock / baseline handoff.

Every table has a `客户确认` column. Use write-what-to-change: the brand party writes only rows requiring correction, deletion, or addition; blank means reviewed without change. Do not put internal methodology, question numbering, or unstable evidence mappings in the customer document. Use `品牌方`, not `贵司`.

## JSON

Recommended root fields:

```json
{
  "schema_version": "overseas-geo-question-bank/v8",
  "mode": "after-sales-strategic-topics",
  "config": {
    "brand_name": "Example",
    "official_domain": "https://example.com",
    "generation_stage": "discovery",
    "lifecycle_status": "hypothesis",
    "evidence_status": "hypothesis",
    "customer_confirmation": {
      "status": "pending",
      "scope_status": "pending",
      "prompt_set_status": "pending"
    },
    "topics": [],
    "attribute_plan": [],
    "expected_total": 0,
    "competitor_selection": {},
    "trial": {"status": "planned", "planned_runs": 3},
    "baseline": {"status": "planned", "window_days": 3, "runs_per_day": 1}
  },
  "questions": []
}
```

`generation_stage` is optional for historical full v8 banks. When present, use
`discovery` or `diagnostic` for the dynamic handoff contract. The parent
presales builder may set `generation_stage: discovery` for new work while
leaving it absent for legacy full diagnostic banks. The extra fields in this
after-sales extension do not change the closed presales v8 schema. When a v8
uploader cannot accept them, emit them in sidecar schedule/evidence files
through an explicit adapter; never claim silent v8 compatibility.

Each question should contain:

- `question_id`
- `topic_id`
- `user_question`
- `zh_translation`
- `monitoring_prompt` equal to `user_question`
- `analysis_type`
- `formal_visibility_eligible`
- `intent_key`
- `quality_checks`

Recommended additional per-question metadata when useful:

- `region`
- `cadence`
- `evidence_refs`
- `evidence_status`
- `change_reason`
- `version`
- `lineage_id`
- `status` (`hypothesis`, `customer_confirmed`, `locked`, `retired`)
- `prompt_group`
- `group_role` (`core`, `experimental`, `monitoring`)
- `journey_stage`
- `audience`
- `constraint_type`
- `competitor_set`
- `business_priority`
- `market_decision` (`shared_equivalent`, `localized`, `market_specific`)
- `prompt_task` only for adapters that need a separate field; derive it from
  the single `Prompt Task: ...` tag rather than maintaining two values

If the downstream uploader cannot accept these extra fields, keep them in a separate schedule or evidence file rather than dropping the information.

The `Prompt Task: ...` tag describes the buyer's job, not the backend Intent.
A question may be `Prompt Task:
Alternatives` while its Intent remains `Discovery`, only when it is a
non-branded candidate-selection question that passes the Discovery contract.
Named-brand alternatives, transaction-only, post-purchase support, and source
research tasks need their own evidence/collection contract; do not force them
into natural visibility metrics.

## Market Coverage and Localization

Before reusing or writing individual Prompts, retain an internal lightweight
coverage record for each priority market/language. It checks product/service
line, audience/persona, journey stage, market/language, buyer constraint,
competitor/alternative set and business priority, plus local terminology,
source ecosystem, regulation, currency, trust, availability and service
expectations when relevant. It is a gap check, not a customer form or a
Cartesian-product quota.

Each candidate intent is classified per market as:

- `shared_equivalent`: local evidence supports the same buyer decision and
  expected answer set, so the intent may retain its lineage;
- `localized`: the decision is equivalent but wording, units, terminology or
  local context must change;
- `market_specific`: the market has a distinct buyer decision, competitor set,
  regulation, transaction model or expectation;
- `not_supported`: available evidence does not justify monitoring it in this
  market yet.

Record the evidence and reason for every local decision. Materialize one
versioned JSON/CSV set per market/language; its `region` and
`collection_config.market` must match, and each market has its own trial and
baseline. Identical queries in multiple markets do not become new intents.
Platform is a collection dimension, not a wording variant. The full coverage
record stays in the internal handoff/evidence artifact; the customer-facing
document shows only the resulting facts, attributes and necessary market
Prompts. `not_supported` belongs only in that internal record because there
is no Prompt row to tag.

In the existing internal input/evidence diff, record each priority market's
reviewed product line, audience, journey, constraint, competitor/substitute
set, business priority, dated evidence, and uncovered slice with its reason.
For each candidate intent record its market decision and destination or
omission reason. This is an internal handoff, not another Case schema or a
customer form.

Use one compact record per market/language rather than a complete matrix:

```json
{
  "market": "target market",
  "language": "target language",
  "product_lines": [],
  "audiences": [],
  "journey_tasks": [],
  "buyer_constraints": [],
  "formal_competitors": [],
  "substitutes_or_status_quo": [],
  "evidence_refs": [],
  "intent_decisions": [
    {
      "candidate_intent": "buyer decision",
      "decision": "shared_equivalent | localized | market_specific | not_supported",
      "reason": "local evidence or evidence gap",
      "destination": "Topic or pending"
    }
  ],
  "omitted_slices": []
}
```

## CSV

The project-compatible baseline is:

`query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`

For a new after-sales consumer, prefer an explicit adapter with:

`query,question_zh,topic,region,intent` — required.

`tags` and `cadence` may be appended when the receiving pipeline wants them, and
omitted when it does not. A delivered CSV that drops them is valid; the validator
only requires the five core columns and rejects columns it does not recognise.

Do not silently mix the two column contracts. State which adapter is being delivered.

## Trial and Baseline Metadata

When collection is ready, retain the following in the after-sales `config` for
validation. If a strict presales v8 uploader rejects these extension fields,
derive a separate schedule/evidence sidecar from the validated set rather than
silently dropping them:

- `customer_confirmation.scope_status`: customer confirmed business priority,
  product/buyer/market scope, and factual/exclusion boundaries before trial;
- `trial`: `planned_runs` 3–5; after 3–5 valid runs for each candidate Prompt
  on each proposed platform, `status: passed`, `valid_runs` equal to the runs
  actually completed, and raw
  `evidence_refs`. These counts are per Prompt/platform, not a total for the bank;
- `customer_confirmation.prompt_set_status`: confirmed after trial; retain the
  existing summary `status` separately;
- `prompt_version`: immutable market/language set version after final approval;
- `baseline`: `status`, `window_days: 3`, `runs_per_day: 1`,
  `calendar_days: true`, `conditions_key`, `valid_samples_only`, and for a
  formal baseline `prompt_version` matching the locked set;
- `collection_config`: market, language, platforms, model/mode, cadence, and
  other conditions required for comparability.

`locked`/`formal_baseline`/`active` requires both confirmations, completed
trial evidence, and a locked Prompt version. `hypothesis` or
`after_sales_signal` evidence cannot be formal-ready. Trial answers are never
part of the baseline. Any addition, deletion, or wording change requires a new
set version and a separate three-day baseline for the affected market/group;
retain history but do not concatenate old and new set-level series.

The validator checks declared counts, references, cadence, and version linkage;
it does not read crawler answers or prove collection occurred. Before marking
trial or baseline collection complete, the collection workflow must audit the
raw results for each Prompt/platform/day and retain their locations.

Compute only from three consecutive days of observed valid daily samples.
Diagnose failed or missing observations and restart the affected window rather
than imputing zeroes or concatenating non-consecutive days. Three observations
establish an initial benchmark, not proof of a stable long-term gap.

## Cadence

Cadence belongs in a separate schedule file or an explicit CSV column:

- Discovery: daily during a formal three-calendar-day baseline, then weekly or
  otherwise as agreed.
- Evaluation and Competitor: as agreed or event-triggered; no fixed default
  quota or cadence is implied.
- Category Awareness: one-time baseline or occasional refresh.
- Baseline Discovery observation: the same cadence as the comparable Discovery
  set.

These are defaults, not hardcoded quotas. Record any client-specific cadence decision.

## Deterministic Quality Gates

Before delivery:

1. The chosen scope and stage are explicit. The recommended first-stage shape is one category observation Topic plus two same-product buying-scenario Topics; two Topics can be justified.
2. Topic names are short and each Prompt maps to exactly one Topic.
3. A customer-confirmed, locked, or formal Topic has at least five Prompts. A shorter hypothesis Topic is marked for merge, Tag treatment, or evidence completion rather than padded with rewrites. Topic counts may differ; no equalization is required.
4. Every Prompt has Topic, Region, and Intent, a query in the market's selected language, and a Chinese translation.
5. Tags, when used, do not repeat Topic, Intent, or Region, and carry a dimension those fields do not.
6. Competitor Prompts are one-to-one, use only frozen applicable competitors, and do not enter the natural Discovery count.
7. Category Awareness is low-frequency and not duplicated across every Topic without a reason; it is not the category observation Topic.
8. Prompt text is unique after normalization and semantically reviewed for duplicates.
9. New Prompts have evidence or are clearly marked as hypotheses requiring confirmation. Each new Prompt also records why a recognizable buyer would ask it and what independent decision, risk, candidate set, or applicability judgment it adds.
10. No cross-topic competitor, product-line, or category leakage.
11. CSV rows match JSON rows and all upload length limits.
12. Discovery Prompts contain no brand names, ask a commercial recommendation/selection question, and test one primary intent.
13. Trial review checks category/task fit, ambiguity, leading language, and duplication; target-brand mention is not a trial pass/fail criterion.
14. Formal baseline plans three consecutive calendar days with one run per
    Prompt/platform/day. Audit observed valid samples separately; failures are
    not zeroes, missing days are not glued together, and old/new Prompt
    versions are not concatenated.
15. Each Topic records a parent Search-Demand anchor or an explicit reason why no reliable Search-Demand signal is available.
16. A `discovery` generation stage contains Discovery Prompts only. Other
    intents are added later under their own evidence-backed purpose, not a fixed
    quota.
17. Attribute and Tag review covers scenarios, pains, procurement constraints,
    supply/service risks, and applicability boundaries when they affect buyer
    decisions; it is not limited to product features or technical parameters.
18. Attributes were derived in the rule document's four steps — twelve-category
    gap sweep, category-specific attributes from the three sources, one B2B/B2C
    line or an explicit split — and ranked by demand × standing to win ×
    deliverable before Topics were named. The delivery states the resulting
    Attribute order.
19. The internal market coverage pass was completed before Prompt lock. Each
    retained market delta has evidence, each omitted slice has a reason, and
    reuse of an `intent_key` is justified by equivalent buyer decisions and
    expected answer sets. Platform differences are collection configuration,
    never Prompt variants.
20. Any prompt-count claim cites the source of demand. No Prompt is described as
    high-frequency without frequency evidence.
21. The intent pass and the Prompt set reconcile **in both directions**: every
    P1/P2 intent is carried by at least one Prompt, and every Prompt's intent
    exists as a row in the client's intent table. The master table's intent
    column quotes the intent table verbatim. Run this as an explicit step — the
    two are drafted from different inputs and drift silently.
22. The evidence layer was checked for existence before being read as a finding.
    Two common cases both leave it unusable: a rough presales pass ran visibility
    only and produced no sentiment layer at all, and a run that marked only the
    branded evaluation questions yields a brand self-portrait rather than a
    competitor matrix. In either case the emptiness is not reported as evidence
    that competitors are clean; the standing-to-win judgement is marked
    provisional, the next evidence layer is used instead, and the gap is recorded
    as a process fix for the next presales run.
23. Where no theme shows a competitor negative, the optimisation labels are held
    as provisional and the deliverable states that no theme has a demonstrated
    opening yet, together with the counter-explanation that roundup-style answers
    rarely criticise. A second run of the same matrix is planned after the
    baseline so the judgement is longitudinal.
24. Before a Topic is reported as short of the five-Prompt floor, attribution was
    re-checked: Prompts filed under the wrong Topic were moved to where their
    actual purchase decision belongs and the counts recomputed. A shortfall
    resolved this way is a correction, not padding.
25. Customer-facing confirmation documents follow `client-facing-attribute-pool.md`: brand facts are separate from ranked attributes; the attribute pool includes `购买影响`, `相对竞品`, `优先级`, evidence gaps and `客户确认`; candidate monitoring questions, when included, carry buyer problem / scenario next to the query; every table uses the write-what-to-change `客户确认` convention; question numbering, internal methodology, unstable mappings, and `贵司` wording stay out of the document.
26. Business scope was confirmed before three to five trial runs per candidate
    Prompt/platform; the final set was confirmed and version-locked after trial.
    Trial results do not count toward the three daily baseline observations.
27. The customer-facing document contains the resulting brand facts, attribute
    pool and necessary market-specific Prompts, not the full internal coverage
    matrix or unresolved reasoning.
28. Prompt Task coverage was reviewed separately from Intent routing. The task
    label does not change `analysis_type`, `formal_visibility_eligible`, or
    formal metric scope.
29. Library size is justified by independent decision coverage and business
    complexity, rather than multiplying all segmentation dimensions.
30. Direct competitors, substitutes and the status quo were distinguished
    where they change the buyer's candidate set, without changing the frozen
    competitor list in this skill.
31. Each group has a diagnostic business question, possible action and
    `core`/`experimental`/`monitoring` role; refresh decisions record a
    business or evidence trigger rather than an automatic expiry.
32. **Every plan Attribute is either carried by a Prompt or says why not.** The validator fails on an Attribute with no carrying Prompt and no `no_carrier_reason` (it also accepts a legacy `demoted_reason`), and it fails when such an Attribute is ranked P1 — P1 means "optimise this first", which is impossible for a dimension nothing measures. Record the reason on the row itself: `no_carrier_reason` is a short string a reader can act on ("its Topic was dropped as unmovable; the Attribute is product-selection shaped and has no home Topic"), never a placeholder. Dropping a Topic deletes its Prompts but leaves its Attributes in the plan, so run this check **after every Topic change**, not only before delivery.

Run the validator against the market's set and, for changes, its prior version:

```bash
python3 scripts/validate_after_sales_set.py BANK.json [MONITORING.csv]
python3 scripts/validate_after_sales_set.py BANK.json --previous PRIOR-BANK.json
python3 evals/verify_workflow.py --report reports/workflow-e2e.json
```

## Review Summary

The final delivery should state:

- active Topic count and Prompt count per Topic;
- the derived Attribute list and its ranking order;
- Prompt role counts, split so that Discovery (natural visibility) is
  distinguishable from named-brand Evaluation, Comparison, and Verification;
- additions, revisions, merges, and retirements;
- evidence source and confidence gaps, marked against the customer-input tiers
  (must-have / best-to-have / collected by us);
- cadence decisions;
- validator/test result and any intentional incompatibility with presales fixed-quota tooling.
