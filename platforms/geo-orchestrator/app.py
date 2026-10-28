"""GEO Orchestrator — the front door to the Dify question-bank workflow.

Run:
    cd platforms/geo-orchestrator
    uvicorn app:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from artifact import ArtifactError, extract_artifact
from dify_client import DifyClient, DifyConfig, DifyError
from models import CaseInput, PasteSubmit, RunSubmit
from paste import parse_pasted_case
from runs import (
    count_runs,
    list_runs,
    load_artifact,
    load_error,
    load_input,
    new_run_id,
    save_artifact,
    save_error,
    save_input,
    save_response,
)

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from .env without clobbering real env vars."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'\"")
        if k:
            os.environ.setdefault(k, v)


_load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="GEO Orchestrator", version="0.1.0")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _fmt_ts(run_id: str) -> str:
    """20261027T101845Z-abc123 -> 2026-10-27 18:18:45（UTC 转本地）"""
    try:
        stamp = run_id.split("-")[0]
        dt = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return run_id


templates.env.filters["fmt_ts"] = _fmt_ts
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _client() -> DifyClient:
    return DifyClient(DifyConfig.from_env())


@app.get("/healthz")
def healthz():
    cfg = DifyConfig.from_env()
    auth = _client().check_auth() if cfg.api_key else {"auth_ok": False, "reason": "DIFY_API_KEY is not set"}
    return {
        "ok": True,
        "dify_base_url": cfg.base_url,
        "dify_reachable": "unreachable" not in str(auth.get("reason", "")),
        "auth_ok": auth.get("auth_ok", False),
        "auth_detail": auth.get("reason", ""),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str):
    inp = load_input(run_id)
    art = load_artifact(run_id)
    err = load_error(run_id)
    if inp is None and art is None and err is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return templates.TemplateResponse(
        request,
        "run.html",
        {
            "run_id": run_id,
            "case": (inp or {}).get("case") or {},
            "artifact": art,
            "error": err,
        },
    )


@app.get("/api/v1/runs")
def api_list_runs(page: int = 1, page_size: int = 10):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = count_runs()
    offset = (page - 1) * page_size
    return {
        "runs": list_runs(limit=page_size, offset=offset),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def _execute(case: CaseInput, user: str) -> str:
    """Run one case through Dify; persist records; return run_id."""
    run_id = new_run_id()
    save_input(run_id, {"case": case.model_dump(), "inputs": case.to_inputs()})

    client = _client()
    try:
        body = client.run_workflow(case.to_inputs(), user=user)
    except DifyError as e:
        save_error(run_id, {"kind": "dify", "message": str(e), "status": e.status, "body": e.body})
        raise HTTPException(status_code=502, detail=str(e)) from e
    save_response(run_id, body)

    try:
        artifact = extract_artifact(run_id, body)
    except ArtifactError as e:
        save_error(run_id, {"kind": e.kind, "message": str(e)})
        status = 422 if e.kind == "failed" else 409 if e.kind == "invalid" else 500
        raise HTTPException(status_code=status, detail=str(e)) from e

    save_artifact(run_id, artifact)
    return run_id


@app.post("/api/v1/runs")
def api_submit(sub: RunSubmit):
    run_id = _execute(sub.case, user=sub.user)
    return {"run_id": run_id, "artifact_url": f"/api/v1/runs/{run_id}/artifact"}


@app.post("/api/v1/runs/paste")
def api_submit_paste(sub: PasteSubmit):
    try:
        payload = parse_pasted_case(sub.raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        case = CaseInput.model_validate(payload)
    except ValidationError as e:
        # Surface the first human-readable error, naming the field.
        err = e.errors()[0]
        loc = ".".join(str(p) for p in err.get("loc", []))
        raise HTTPException(status_code=422, detail=f"field `{loc}`: {err.get('msg')}") from e
    run_id = _execute(case, user="paste")
    return {"run_id": run_id, "artifact_url": f"/api/v1/runs/{run_id}/artifact"}


@app.get("/api/v1/runs/{run_id}")
def api_get_run(run_id: str):
    rec = {
        "run_id": run_id,
        "input": load_input(run_id),
        "artifact": load_artifact(run_id),
        "error": load_error(run_id),
    }
    if rec["input"] is None and rec["artifact"] is None and rec["error"] is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return rec


@app.get("/api/v1/runs/{run_id}/artifact")
def api_get_artifact(run_id: str):
    art = load_artifact(run_id)
    if art is not None:
        return art
    err = load_error(run_id)
    if err is not None:
        status = 422 if err.get("kind") == "failed" else 409 if err.get("kind") == "invalid" else 500
        return JSONResponse(status_code=status, content={"run_id": run_id, "error": err})
    raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
