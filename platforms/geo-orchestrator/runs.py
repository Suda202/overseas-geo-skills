"""Run persistence. One directory per run under RUNS_DIR."""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _runs_dir() -> Path:
    return Path(os.environ.get("RUNS_DIR", "runs")).resolve()


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(3)}"


def _safe(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError(f"bad run_id: {run_id!r}")
    return run_id


def run_dir(run_id: str) -> Path:
    d = _runs_dir() / _safe(run_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(run_id: str, name: str, data: Any) -> None:
    p = run_dir(run_id) / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read(run_id: str, name: str) -> Optional[Any]:
    p = _runs_dir() / _safe(run_id) / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_input(run_id: str, payload: dict) -> None:
    _write(run_id, "input.json", payload)


def save_response(run_id: str, payload: dict) -> None:
    _write(run_id, "response.json", payload)


def save_artifact(run_id: str, payload: dict) -> None:
    _write(run_id, "artifact.json", payload)


def save_error(run_id: str, payload: dict) -> None:
    _write(run_id, "error.json", payload)


def load_input(run_id: str) -> Optional[Any]:
    return _read(run_id, "input.json")


def load_response(run_id: str) -> Optional[Any]:
    return _read(run_id, "response.json")


def load_artifact(run_id: str) -> Optional[Any]:
    return _read(run_id, "artifact.json")


def load_error(run_id: str) -> Optional[Any]:
    return _read(run_id, "error.json")


def count_runs() -> int:
    root = _runs_dir()
    if not root.exists():
        return 0
    return sum(1 for p in root.iterdir() if p.is_dir())


def list_runs(limit: int = 50, offset: int = 0) -> list:
    root = _runs_dir()
    if not root.exists():
        return []
    runs = sorted((p for p in root.iterdir() if p.is_dir()), reverse=True)
    out = []
    for p in runs[offset:offset + limit]:
        rec = {
            "run_id": p.name,
            "has_artifact": (p / "artifact.json").exists(),
            "has_error": (p / "error.json").exists(),
        }
        inp = _read(p.name, "input.json")
        if isinstance(inp, dict):
            case = inp.get("case") or {}
            rec["brand_name"] = case.get("brand_name", "")
            rec["company_name"] = case.get("company_name", "")
            rec["category"] = case.get("category", "")
            rec["regions"] = case.get("regions", "")
        art = _read(p.name, "artifact.json")
        if isinstance(art, dict):
            rec["question_count"] = art.get("question_count", 0)
            rec["schema_version"] = art.get("schema_version", "")
            rec["validate_valid"] = art.get("validate_valid", False)
        err = _read(p.name, "error.json")
        if isinstance(err, dict):
            rec["error_kind"] = err.get("kind", "")
            rec["error_message"] = str(err.get("message", ""))[:200]
        out.append(rec)
    return out
