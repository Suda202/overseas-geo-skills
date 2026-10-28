# Change: Add the GEO Orchestrator platform

## Why

`dify-agent-a-v2/workflow.dsl.yaml` proves the whole presales pipeline works: a
9-field case goes in, and a validated question-bank JSON comes out. But that
proof lives only inside Dify. Running it means opening a Dify workspace,
importing a DSL, clicking through a node graph, and hand-copying a JSON blob into
the start node. That is fine for the person who built it and unusable for anyone
else — presales cannot hand a Dify login to a colleague and expect a question
bank back.

The Dify workflow itself is done and stays done. What is missing is a front door:
a place where a non-Dify person types nine fields (or pastes the case JSON they
already have), presses run, and gets the question-bank JSON back.

## What Changes

A thin FastAPI platform that wraps the existing Dify workflow.

- **NEW** `platforms/geo-orchestrator/` — FastAPI service, the only entry point.
- **NEW** `DifyClient` — one small module calling
  `POST http://dify.ads.qihoo.net/v1/workflows/run` with
  `Authorization: Bearer {API_KEY}`. Blocking mode, `response_mode: blocking`.
- **NEW** dual input: a 9-field form and a paste-a-JSON box. Both validate into
  one `CaseInput` model, then become the Dify `inputs` object verbatim.
- **NEW** run records under `runs/<run_id>/` — input, Dify response, extracted
  artifact, error. So a run is inspectable without Dify's UI.
- **NEW** artifact endpoint serving `questions` + `bank_config` +
  `schema_version` + validation result as one JSON document.

**No pipeline engine.** The orchestration already exists in Dify and works. The
platform does not re-describe the 17 nodes, does not re-implement retries, and
does not know what a node is. It knows one thing: how to POST a case to a Dify
workflow and read the outputs back.

Existing code is untouched. `skills/`, `server.py`, `search_server.py` and
`dify-agent-a-v2/` keep working as they do today.

## Impact

- Affected specs: `orchestrator` (new capability)
- Affected code: new tree under `platforms/geo-orchestrator/` only
- Runtime deps: fastapi, uvicorn, pydantic v2, httpx — already present
- Config: `DIFY_API_KEY`, `DIFY_BASE_URL` (default
  `http://dify.ads.qihoo.net/v1`), `DIFY_WORKFLOW_ID` or the app's own key
- Network: the platform host must reach `dify.ads.qihoo.net`

## Non-goals

- Reimplementing or editing the Dify workflow. It is the engine.
- A provider abstraction. There is exactly one backend; if a second ever
  appears, that is when the seam gets cut, not before.
- Async/streaming runs, job queues, or a database. Blocking call, files on disk.
- Multi-tenant auth or billing.
- A build step or SPA. Server-rendered HTML plus a little vanilla JS.
