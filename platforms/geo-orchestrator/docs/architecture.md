# Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Browser                                                     │
│  GET /          form (9 fields, repeatable competitors)    │
│                 paste box (tolerant JSON)                  │
└────────────────────────┬───────────────────────────────────┘
                         │ POST /api/v1/runs | /runs/paste
┌────────────────────────▼───────────────────────────────────┐
│ FastAPI app.py                                              │
│   paste.parse_pasted_case  → CaseInput (models.py)         │
│   CaseInput.to_inputs()    → Dify start-node inputs        │
│   runs.py                  → runs/<run_id>/input.json      │
└────────────────────────┬───────────────────────────────────┘
                         │ POST {DIFY_BASE_URL}/workflows/run
                         │ Authorization: Bearer {DIFY_API_KEY}
┌────────────────────────▼───────────────────────────────────┐
│ Dify workflow (dify-agent-a-v2, 17 nodes)                   │
└────────────────────────┬───────────────────────────────────┘
                         │ blocking response body
┌────────────────────────▼───────────────────────────────────┐
│ artifact.extract_artifact                                   │
│   status != succeeded        → 422 (error.json)            │
│   validate_valid == false    → 409 (error.json)            │
│   missing output keys        → 500 (error.json)            │
│   else                       → runs/<run_id>/artifact.json │
└────────────────────────────────────────────────────────────┘
```

## Design intent

There is no orchestration here on purpose. The 17-node pipeline already lives in
Dify and works; this platform is a client of it. Everything the platform does is
at the edges: input tolerance, run persistence, artifact shaping, refusal to
serve an artifact for a failed run.

`CaseInput` field names match the workflow's start-node variables exactly. That
is deliberate: the Dify DSL is the contract, and a rename in Dify should surface
as a pydantic validation error naming the field, not as a silent empty input.

## Files

| File | Role |
|---|---|
| `app.py` | routes, healthz, run execution |
| `dify_client.py` | one POST to `/workflows/run`; `check_auth` for healthz |
| `models.py` | `CaseInput` + `to_inputs()` |
| `paste.py` | tolerant parse for the paste channel |
| `artifact.py` | Dify response → shaped artifact, with the three failure kinds |
| `runs.py` | `runs/<run_id>/{input,response,artifact,error}.json` |

## If a second backend ever appears

The seam is `dify_client.DifyClient.run_workflow(inputs, user) -> dict`. A new
backend would need to accept the same `inputs` dict and return something that
`artifact.extract_artifact` can read (a `data.outputs` object with the 8 keys).
That is the only change; routes, models, and the UI stay as they are. Do not
cut that seam until a second backend actually exists.

## Config

`DIFY_BASE_URL` (default `http://dify.ads.qihoo.net/v1`), `DIFY_API_KEY`,
`DIFY_TIMEOUT` (default 300s), `RUNS_DIR` (default `./runs`).
