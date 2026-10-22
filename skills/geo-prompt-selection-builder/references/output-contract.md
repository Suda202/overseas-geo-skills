# After-Sales Output Contract

This is the practical after-sales extension contract. It is intentionally
separate from the presales v8 fixed-quota validator.

## Customer-Facing Confirmation Artifact

When the task includes client review of scope, attributes, Topics, or candidate Prompts, deliver a separate Chinese confirmation document in addition to JSON/CSV. Follow [client-facing-attribute-pool.md](client-facing-attribute-pool.md). Its minimum structure is:

- opening scope and monitoring object;
- `核对时从哪里判断` guidance adapted to B2B or B2C;
- a separate `品牌事实【请核对】` table (the Base's 业务范围);
- a `品牌事实核查` table (the Base's 品牌事实核查; document format: `事实项 | 官方值 | 来源页面 | 冲突说法 | 冲突来源 | 品牌方要做什么`) holding facts that are contradictory on the official site or asserted without external support, one row each, with full source URLs; 品牌方要做什么 is 改官网 or 提供材料 (see [client-facing-attribute-pool.md](client-facing-attribute-pool.md) → *品牌事实核查*);
- the attribute judgements — `重要性`, `相对竞品`, `可改变性`, `优先级`, evidence-gap fields, 约束 and 目标题数 — split between 属性池 (one row per attribute: `重要性`, `相对竞品`, `可改变性`, evidence and 还缺什么) and 提示词矩阵 rows (one row = coverage slice × attribute, primary field 切片编号, linked to 属性池 through 属性关联, carrying 约束, 目标题数 and the formula `优先级`; the per-slice `购买影响` column was removed 2026-10-22 — a situation that genuinely changes importance splits the pool row instead);
- optional candidate Prompts in 提示词库, each linked to one 提示词矩阵 row;
- optional competitor confirmation table;
- `需要品牌方提供的数据` while the attribute pool is still being built (client-only data, see [signal-sources.md](signal-sources.md));
- candidate-baseline / lock handoff.

In the Base there is no `客户确认` column: the brand party edits cells directly and marks 状态 (待审核 / 需修改 / 已批准, then 正式 / 停测 after the baseline) on 提示词库; only 已批准 Prompts enter the candidate baseline. Document-format pieces keep a `客户确认` column. Use write-what-to-change: the brand party writes only rows requiring correction, deletion, or addition; blank means reviewed without change. Do not put internal methodology, question numbering, or unstable evidence mappings in the customer document. Use `品牌方`, not `贵司`.

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
    "baseline": {"status": "planned", "planned_runs": 5}
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

Staged `config.topics` entries record the clustering that opened each Topic,
written **before** Prompts are drafted (Suda 2026-10-22): `{topic_id, topic,
covered_attributes, planned_prompts}` — `covered_attributes` names the
`attribute_plan` rows whose landing opened the Topic, `planned_prompts` is the
pre-writing count. The validator warns while a staged Topic lacks the two
fields, and fails when a `covered_attributes` name is absent from
`attribute_plan`, or a P1 attribute is homed in no Topic's
`covered_attributes` and carries no `no_carrier_reason` / `demoted_reason`.
`config.leader_default: {"reason": …}` records the leader-is-default decision
(after-sales-rules.md → *When the leader is the default*); it exempts the bank
from the per-Topic low-condition-anchor warning, and the flag without a reason
fails. Legacy banks keep their old shape; the legacy per-question `intent`
field is still read where `prompt_type` carries no valid type.

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

Staged banks (those with `config.generation_stage`) also carry, on every
question, the five fields the client Base 提示词库 and 提示词矩阵 read:

| Field | Value | Base column |
|---|---|---|
| `journey_stage` | eight-stage label: 发现 / 解决问题 / 评估 / 对比 / 替代方案 / 验证 / 交易 / 购后支持 | 旅程阶段 |
| `audience` | one or more real buyer groups (a string or a list; the Base 受众 is multi-select since Suda 2026-10-20), or 「通用」 as the internal placeholder for no group condition (rendered as the category's base audience, e.g. 「养猫家庭」, in the Base); never a journey state such as 「已在比较具体品牌」 | 受众 |
| `group_role` | `core` / `experimental` / `monitoring` | 库分层 (核心 / 实验 / 监测) |
| `attribute_ref` | the 提示词矩阵 attribute name; empty string on a category-baseline Prompt | 属性 (via 所属切片) |
| `evidence_refs` | list of 买家原话 输入编号 (or source notes) behind the Prompt | 证据 |

The validator warns while any of them is missing and fails once
`lifecycle_status` is `locked`, `formal_baseline` or `active`. Older banks
used other names; the validator reads them as aliases — `journey_stage_9` /
`journey` → `journey_stage`, `persona` / `buyer` → `audience`,
`library_layer` → `group_role`, `attribute` → `attribute_ref`,
`buyer_demand_evidence` → `evidence_refs`, `condition_slot` →
`constraint_type`. Write new banks with the canonical names only. Two names
holding different values on one Prompt fail validation (for example
`library_layer: 实验` beside `group_role: core`). Old five-stage labels
(了解需求 / 比较方案 / 评估是否适合 / 准备购买 / 使用与续费) are recognised but
never converted, because the mapping is not one-to-one: re-judge each Prompt.

`review_status` mirrors the review values of the 提示词库 状态 column: `待审核` / `已批准` /
`需修改` (正式 / 停测 count as already approved) (`pending` / `approved` / `needs_revision` are read as the same
values; anything else fails). Once any Prompt in a bank carries it, the
attribute-alignment gate counts only 已批准 Prompts as covering an
`attribute_plan` row, matching the count inside the Base 覆盖情况 formula; a Prompt without the
field is counted as 待审核 and listed in a warning. An attribute carried only
by unapproved Prompts warns while drafting and fails from `customer_confirmed`
on. Banks with no `review_status` anywhere keep the older rule that any Prompt
covers its attribute. The summary line reports the count per status.

**Conditions and the buyer-quote table (gates 36–37).** A staged bank carries
the 买家原话 rows its `evidence_refs` cite as `config.buyer_quotes`
(`[{"输入编号", "原话", "约束"}]`, the client Base 买家原话 columns), and
`config.base_conditions` for the category's base audience or use (「私家车」
「养猫家庭」), which is the category itself and never a condition. Each Prompt
carries `constraints`: the buyer conditions it adds beyond its attribute —
budget, car type or home size, parking place, weather, an event such as a
hit-and-run, bundled accessories, a named rival — as 约束-column keywords,
`[]` when it adds none. When the condition is the one a cited quote's 约束
already records, copy that wording (「200 美元以内」「四路」). A condition is
backed by the 约束 column of a quote the Prompt cites, not by the quote text
(Suda 2026-10-22): research writes there what the post states in its title or
thread. A missing `constraints` list is read as `[]`.

Recommended additional per-question metadata when useful:

- `region`
- `cadence`
- `evidence_status`
- `change_reason`
- `version`
- `lineage_id`
- `status` (`hypothesis`, `customer_confirmed`, `locked`, `retired`)
- `prompt_group`
- `constraint_type`
- `competitor_set`
- `business_priority`
- `market_decision` (`shared_equivalent`, `localized`, `market_specific`)

If the downstream uploader cannot accept these extra fields, keep them in a separate schedule or evidence file rather than dropping the information.

An alternatives question stays `Discovery` only when it is a non-branded
candidate-selection question that passes the Discovery contract. Named-brand
alternatives are `Alternatives` (替代, split out of `Competitor` 2026-10-22;
read as 列入率 + sentiment, `formal_visibility_eligible: false`; banks written
before keep them typed `Competitor`, no migration); transaction-only, post-purchase support, and
source research questions need their own evidence/collection contract; do not
force them into natural visibility metrics.

## Market Coverage and Localization

Before reusing or writing individual Prompts, retain an internal lightweight
coverage record for each priority market/language. It checks product/service
line, audience/persona, journey stage, market/language, buyer constraint,
competitor/alternative set and business priority, plus local terminology,
source ecosystem, regulation, currency, trust, availability and service
expectations when relevant. It is a gap check we draft — shown to the brand
party as the 提示词矩阵 table of the client Base — not a form the client fills or
a Cartesian-product quota.

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
  product/buyer/market scope, and factual/exclusion boundaries before the
  candidate baseline;
- `trial` (the candidate baseline): `planned_runs` 5; after the valid runs for each candidate Prompt
  on each proposed platform, `status: passed`, `valid_runs` equal to the runs
  actually completed, and raw
  `evidence_refs`. These counts are per Prompt/platform, not a total for the bank;
- `customer_confirmation.prompt_set_status`: formal set confirmed after the candidate baseline; retain the
  existing summary `status` separately;
- `prompt_version`: immutable market/language set version after final approval;
- `baseline`: `status`, `planned_runs` (5 per Prompt/platform; legacy
  `window_days` × `runs_per_day` is read as the total), `conditions_key`,
  `valid_samples_only`, and for a
  formal baseline `prompt_version` matching the locked set;
- `collection_config`: market, language, platforms, model/mode, cadence, and
  other conditions required for comparability.

`locked`/`formal_baseline`/`active` requires both confirmations, completed
trial evidence, and a locked Prompt version. `hypothesis` or
`after_sales_signal` evidence cannot be formal-ready. A locked set holds at most
10 Prompts per purchased Topic. Unchanged formal Prompts reuse their
candidate-baseline readings as the Before baseline; reworded ones are rerun. Any addition, deletion, or wording change requires a new
set version and a separate formal baseline for the affected market/group;
retain history but do not concatenate old and new set-level series.

The validator checks declared counts, references, cadence, and version linkage;
it does not read crawler answers or prove collection occurred. Before marking
trial or baseline collection complete, the collection workflow must audit the
raw results for each Prompt/platform run and retain their locations.

Compute only from observed valid runs (5 per Prompt/platform). Diagnose
failed or missing runs and rerun them rather than imputing zeroes. The baseline
runs establish an initial benchmark, not proof of a stable long-term gap.

Baseline analysis also reads the query fan-out from the same runs: ChatGPT
`task_result.search_model_queries.queries` and Gemini
`task_result.related_queries`; other platforms return none. Keep the raw
results whole so these fields survive, report the two platforms separately, and
treat an empty field as "no fan-out returned", not a failed run. How to read it
is in [gap-cause-action-table.md](../../geo-monitoring/references/gap-cause-action-table.md) → *Query fan-out*.

## Cadence

Cadence and re-run triggers are owned by `geo-monitoring` → 采集频率与重跑. This skill records only the client-specific cadence agreed with the brand party, in a separate schedule file or the CSV `cadence` column.

## Deterministic Quality Gates

Before delivery:

1. The chosen scope and stage are explicit. The recommended first-stage shape is one category observation Topic plus two same-product buying-scenario Topics; two Topics can be justified.
2. Topic names are short and each Prompt maps to exactly one Topic.
3. Every candidate (customer-confirmed), locked, or formal Topic has at least five Prompts; candidate Topic count is not limited. A shorter hypothesis Topic is marked for merge, Tag treatment, or evidence completion rather than padded with rewrites. Topic counts may differ; no equalization is required.
4. Every Prompt has Topic, Region, and prompt type, a query in the market's selected language, and a Chinese translation.
5. Tags, when used, do not repeat Topic, prompt type, or Region, and carry a dimension those fields do not.
6. Competitor Prompts are one-to-one, use only frozen applicable competitors, and do not enter the natural Discovery count.
7. Category Awareness is low-frequency and not duplicated across every Topic without a reason; it is not the category observation Topic.
8. Prompt text is unique after normalization and semantically reviewed for duplicates. The validator fails on exact duplicates and warns on near-duplicates (word overlap of 60% or more once words shared by most of the bank are removed) and on Prompts with the same Topic, intent and `attribute_ref` whose wording overlaps; each warning is resolved by keeping one or by recording what decision the second one adds. Wording overlap misses a decision re-asked in other scenery; gate 37 keys on the decision instead.
9. New Prompts have evidence or are clearly marked as hypotheses requiring confirmation. Each new Prompt also records why a recognizable buyer would ask it and what independent decision, risk, candidate set, or applicability judgment it adds.
10. No cross-topic competitor, product-line, or category leakage.
11. CSV rows match JSON rows and all upload length limits.
12. Discovery Prompts contain no brand names, ask a commercial recommendation/selection question, and test one primary intent. The validator fails on a Discovery Prompt naming `brand_name`, any `aliases`, or any name in `competitor_selection`; a brand written in a non-Latin script is caught only when that spelling is listed in `aliases`.
13. Trial review checks category/task fit, ambiguity, leading language, and duplication; target-brand mention is not a trial pass/fail criterion.
14. Formal baseline plans 5 runs per Prompt/platform. Audit observed valid
    samples separately; failures are not zeroes, and old/new Prompt versions are
    not concatenated.
15. Each Topic records a parent Search-Demand anchor or an explicit reason why no reliable Search-Demand signal is available.
16. A `discovery` generation stage contains Discovery Prompts only. Other
    intents are added later under their own evidence-backed purpose, not a fixed
    quota.
17. Attribute and Tag review covers scenarios, pains, procurement constraints,
    supply/service risks, and applicability boundaries when they affect buyer
    decisions; it is not limited to product features or technical parameters.
18. Attributes were derived in the rule document's four steps — twelve-category
    gap sweep, category-specific attributes from the three sources, one B2B/B2C
    line or an explicit split — and graded P1 / P2 / P3 by purchase-decision
    importance before Topics were named. The delivery states the resulting
    grades.
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
25. Customer-facing confirmation documents follow `client-facing-attribute-pool.md`: brand facts are separate from ranked attributes; the attribute pool includes `重要性` (购买影响 in documents before 2026-10-22), `相对竞品`, `优先级`, evidence gaps and `客户确认`; candidate monitoring questions, when included, carry buyer problem / scenario next to the query; every table uses the write-what-to-change `客户确认` convention; question numbering, internal methodology, unstable mappings, and `贵司` wording stay out of the document.
26. The attribute pool and business scope were confirmed before the candidate
    baseline (5 runs per Prompt/platform); the formal set (at most 10 per
    purchased Topic) was selected by attribute priority, confirmed and
    version-locked; reworded Prompts were rerun before reuse.
27. The customer-facing document contains the resulting brand facts, attribute
    pool and necessary market-specific Prompts, not the full internal coverage
    matrix or unresolved reasoning.
28. Library size is justified by independent decision coverage and business
    complexity, rather than multiplying all segmentation dimensions.
29. Direct competitors, substitutes and the status quo were distinguished
    where they change the buyer's candidate set, without changing the frozen
    competitor list in this skill.
30. Each group has a diagnostic business question, possible action and
    `core`/`experimental`/`monitoring` role; refresh decisions record a
    business or evidence trigger rather than an automatic expiry.
31. **Every plan Attribute is either carried by a Prompt or says why not.** The validator fails on an Attribute with no carrying Prompt and no `no_carrier_reason` (it also accepts a legacy `demoted_reason`), and it fails when such an Attribute is ranked P1 — P1 means "optimise this first", which is impossible for a dimension nothing measures. Record the reason on the row itself: `no_carrier_reason` is a short string a reader can act on ("its Topic was dropped as unmovable; the Attribute is product-selection shaped and has no home Topic"), never a placeholder. Dropping a Topic deletes its Prompts but leaves its Attributes in the plan, so run this check **after every Topic change**, not only before delivery.
32. **Wording matches the market.** The validator fails when fewer than half of a query's letters are in the script of `collection_config.language` (a Thai bank may still carry acronyms such as IELTS). It warns, without failing, on: a Latin-script query that reads as another Latin language; queries of four words or fewer, or short all-lowercase phrases without a question mark (keyword shape); more than one question mark; more than 40 words; a currency outside the market's. Warnings are reviewed one by one. Do not reword a Prompt only to silence one; a deliberate exception (for example a low-condition baseline kept next to its one-condition variant) is recorded in the internal diff.
33. **Metadata is complete and balanced.** Every Prompt in a staged bank carries the five fields in the table above, under their canonical names. The validator also warns when one journey stage holds more than 45% of a non-Discovery-stage set (a Discovery-stage set is mostly 发现 by construction, so it is not checked), and when fewer than half of the Discovery Prompts are `core` (the natural-visibility trend is read from the core set).
34. **Evidence comes from more than one kind of source.** From `customer_confirmed` on, the validator classifies every `evidence_refs` entry on 已批准 Prompts into a source family — 答案层, 搜索数据, 评价, 社区, 一手记录 (sales, CRM, support, interviews), 客户确认, 官网与竞品页 — by keywords in the ref text, and warns when the set spans fewer than three families. Refs that match no family (bare 输入编号 such as `input-3`) are 未分类; when they are more than half the refs the check is skipped, because diversity cannot be judged from IDs alone. A single-family set usually means the signal pass skipped sources (see SKILL.md → *Customer and Market Signals*); answer it by collecting the missing family or recording in the internal diff why that family has nothing for this category.
35. **Every collected buyer quote is either used or set aside on purpose.** When `config.audience_inputs` lists the 买家原话 输入编号 collected for this bank (plain strings or objects with `input_id`), the validator warns on each one that no Prompt's `evidence_refs` cites. Record a decision per unused input in the internal diff — drafted as a candidate, set aside (with reason), or not applicable — so the next expansion round starts from them instead of re-collecting.
36. **No condition outside the evidence.** The validator fails a Prompt whose `constraints` hold a keyword that no cited quote's 约束 backs, or whose market-language query states a number that neither the cited 约束 cells nor the cited quotes state (model names such as STARVIS 2, 24/7 and years are not conditions; Chinese numerals in 约束 are read as digits, so 「四路」 backs "4-channel"). Fix it by citing the quote whose 约束 carries the condition, by adding the condition to that quote's 约束 when research supports it, or by dropping it from the Prompt — never by leaving it undeclared, because gate 37 then folds the Prompt into its base decision. It warns on `evidence_refs` absent from `config.buyer_quotes`, and skips both gates with one warning when the bank carries no `config.buyer_quotes`.
37. **One purchase decision is asked once.** Prompts with the same Topic, prompt type, `attribute_ref` (or client-Base `slice_ref`) and evidence-backed constraints are one decision; the validator warns once per group. Only a condition a cited 约束 backs makes a new decision — a scenery change without evidence (parked on the street, a minivan, freezing weather) is the same decision reworded. Keep one, or give the others a condition their evidence carries. Two misses are known: the same need filed under two attribute names, and the same decision across Topics. The A/B replay (2026-10-22, six banks, blind review): gates 36–37 together flag 84% of the Prompts the review failed, and 23% of the ones it passed; `evals/scope-gates-ab-20261022/` holds the banks and verdicts the regression test reads.

The validator ends with a one-line verdict in three tiers: `Not ready: N errors to fix` (printed as `READINESS:` after the errors, exit 1), `Usable: N warnings to review`, or `Ready for the next lifecycle stage` (both in the summary JSON's `readiness` field). Quote this line in the validation summary handed over with the set.

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
  distinguishable from named-brand Evaluation, Competitor, and Accuracy;
- additions, revisions, merges, and retirements;
- evidence source and confidence gaps, marked against the customer-input tiers
  (must-have / best-to-have / collected by us);
- cadence decisions;
- validator/test result and any intentional incompatibility with presales fixed-quota tooling.
