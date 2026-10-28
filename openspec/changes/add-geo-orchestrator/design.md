## Context

The Dify workflow at `dify-agent-a-v2/workflow.dsl.yaml` is complete and
verified: 17 nodes, 9 inputs, 8 outputs. It is reachable over HTTP at
`http://dify.ads.qihoo.net/v1` with a Bearer key, so the platform's whole job is
to be a well-behaved client of it plus a usable front door.

The interesting design work is therefore not orchestration — that exists — but
the edges: what the platform accepts, what it persists, and what it returns.

## Goals

1. A person who has never seen Dify can produce a question bank.
2. A script can produce the same question bank over HTTP.
3. A failed run is diagnosable from the platform's own records.
4. No reimplementation of anything the workflow already does.

## Decisions

### D1. No engine — Dify is the engine

The platform does not model nodes, does not sequence steps, does not implement
retries. It POSTs a case and reads outputs.

**Because:** a second description of the same pipeline is a second thing to keep
in sync, and the first one already works. Every hour spent on a pipeline engine
is an hour not spent on the front door, which is the actual gap.

**Trade-off:** the platform inherits Dify's failure modes — a 17-node run takes
minutes, and a blocking HTTP call has to survive that. Mitigated by a generous
configurable timeout (default 300s) and by surfacing Dify's own `error` field
verbatim rather than translating it.

### D2. Request shape is the workflow's shape

`CaseInput` field names are exactly the Dify start-node variable names:
`brand_name`, `company_name`, `business_mode`, `category`, `official_domain`,
`topics`, `competitors`, `regions`, `supplemental`.

The rendered `inputs` object is that model dumped, with `competitors`
serialized to the JSON-array-string the workflow expects.

**Because:** any mapping layer is a place for a rename to go wrong silently. The
workflow's variable names are the contract; the platform models the contract
directly. If the workflow gains a variable, one model field is added.

**Trade-off:** the platform's API is coupled to the workflow's naming. That is
acceptable — they are versioned together, and the alternative (a translation
table) trades a visible coupling for an invisible one.

### D3. Two input channels, one validation path

- `GET /` — form, 9 fields, `competitors` as repeatable rows.
- `POST /api/v1/runs` — `{"case": {...}}`, for scripts.
- `POST /api/v1/runs/paste` — `{"raw": "<json text>"}`, the paste path.

The paste path strips code fences, normalizes smart quotes, removes trailing
commas and retries once. It also accepts a bare flat object (no `case` wrapper)
because that is what people copy out of the Dify run history.

All three converge on `CaseInput`. Validation errors name the field and quote
the offending value.

**Because:** the most common real-world failure is a competitor list that is a
comma-separated string instead of a JSON array, or a whole case wrapped in
markdown. Tolerating formatting noise is cheap; telling someone their JSON is
bad without saying which field is expensive.

### D4. Runs are directories, not rows

`runs/<run_id>/` with `input.json`, `response.json` (Dify's raw body),
`artifact.json` (extracted, shaped), and `error.json` when it fails. `run_id` is
`<UTC stamp>-<6 hex>`.

**Because:** someone debugging a bad question bank needs the case that produced
it and Dify's raw response side by side. Files give that and survive restarts.
A database would add a migration problem for zero benefit at this scale.

### D5. Failure is loud

If Dify returns `status != "succeeded"`, or `validate_valid` is false, the run is
recorded as failed and the artifact endpoint returns 409 with the reason. No
partial or best-effort artifact is served as if it were good.

**Because:** a question bank with fabricated competitor evidence looks exactly
like a good one until someone uses it. The workflow already sets
`validate_valid`; the platform's job is to refuse to hide it.

## Risks

| Risk | Mitigation |
|---|---|
| 17-node run exceeds HTTP timeout | configurable `DIFY_TIMEOUT` (default 300s); on timeout the run record keeps the partial state and the error is explicit |
| Key rotation breaks everything | single env var; `/healthz` reports Dify auth reachability |
| Workflow variable renamed in Dify | `CaseInput` mirrors it; the failure is a pydantic validation error naming the field, not a silent empty input |
| Artifact shape differs from expectation | artifact extraction reads Dify `outputs` by key with explicit 404-style errors per missing key |
