# Tasks

## 1. Scaffolding
- [x] 1.1 Initialize OpenSpec at repo root
- [x] 1.2 Create `platforms/geo-orchestrator/` package layout
- [x] 1.3 `requirements.txt` — fastapi, uvicorn, pydantic v2, httpx, jinja2
- [x] 1.4 `.env.example` — DIFY_BASE_URL, DIFY_API_KEY, DIFY_TIMEOUT

## 2. Dify client
- [x] 2.1 `dify_client.py` — `run_workflow(inputs) -> dict`, blocking mode
- [x] 2.2 Bearer auth, configurable base URL and timeout
- [x] 2.3 Map httpx/network failures to a single `DifyError` with the raw message
- [x] 2.4 `check_auth()` for /healthz — cheap call proving the key works

## 3. Input model
- [x] 3.1 `models.py` — `CaseInput` with the 9 Dify start-node field names
- [x] 3.2 `competitors` validation: accept JSON array string, list of objects, or `Name: domain` strings
- [x] 3.3 `to_inputs()` — serialize competitors back to the JSON-array-string Dify expects
- [x] 3.4 Tolerant parse helper: strip code fences, smart quotes, trailing commas, unwrap `case`

## 4. API
- [x] 4.1 `app.py` — FastAPI app, `GET /healthz`
- [x] 4.2 `POST /api/v1/runs` — `{"case": {...}}`
- [x] 4.3 `POST /api/v1/runs/paste` — `{"raw": "..."}`
- [x] 4.4 `GET /api/v1/runs/{run_id}` — run record
- [x] 4.5 `GET /api/v1/runs/{run_id}/artifact` — shaped question bank
- [x] 4.6 `runs.py` — persist `input/response/artifact/error.json` under `runs/<run_id>/`

## 5. Artifact shaping
- [x] 5.1 Extract `questions`, `question_count`, `bank_config`, `schema_version`,
      `validate_valid`, `validate_error_count`, `validate_first_errors`, `bank_path`
- [x] 5.2 Missing output key → explicit error naming the key
- [x] 5.3 `validate_valid: false` → artifact endpoint returns 409 with first errors

## 6. UI
- [x] 6.1 `templates/index.html` — tabbed form / paste
- [x] 6.2 Form: 9 fields, repeatable competitor rows (name + domain)
- [x] 6.3 Paste: textarea, live JSON validity hint, one-click "fill form from JSON"
- [x] 6.4 Run view: elapsed timer, rendered artifact + raw JSON toggle
- [x] 6.5 Copy / download artifact as `.json`

## 7. Verification
- [ ] 7.1 Run KeepBalance case end to end against the real Dify endpoint (needs DIFY_API_KEY)
- [ ] 7.2 Confirm artifact matches the Dify UI's outputs for the same run (needs key)
- [x] 7.3 Module smoke tests: paste parse, model validation, artifact extraction, /healthz, 400/422 paths
- [x] 7.4 README quickstart with the exact commands

## 8. Handoff
- [x] 8.1 `docs/architecture.md` — request path, run layout, where to add a second backend later
- [ ] 8.2 Real Dify API key configured in `.env` by the operator
