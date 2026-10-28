"""Extract the artifact from a raw Dify blocking-run response.

The workflow's end node emits 8 outputs; this pulls them out by key and
refuses to hand back a partial artifact for a failed run.
"""
from __future__ import annotations

import json

EXPECTED_KEYS = (
    "questions",
    "question_count",
    "bank_config",
    "schema_version",
    "validate_valid",
    "validate_error_count",
    "validate_first_errors",
    "bank_path",
)


class ArtifactError(Exception):
    def __init__(self, message: str, kind: str = "shape"):
        super().__init__(message)
        self.kind = kind  # "shape" | "failed" | "invalid"


def extract_artifact(run_id: str, body: dict) -> dict:
    """Return an artifact dict, or raise ArtifactError."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise ArtifactError("Dify response has no `data` object", kind="shape")

    status = data.get("status")
    if status != "succeeded":
        err = data.get("error") or f"workflow status is {status!r}"
        raise ArtifactError(f"Dify execution did not succeed: {err}", kind="failed")

    outputs = data.get("outputs")
    if not isinstance(outputs, dict):
        raise ArtifactError("Dify response has no `outputs` object", kind="shape")

    missing = [k for k in EXPECTED_KEYS if k not in outputs]
    if missing:
        raise ArtifactError(f"outputs missing keys: {', '.join(missing)}", kind="shape")

    validate_valid = bool(outputs.get("validate_valid"))
    if not validate_valid:
        first = outputs.get("validate_first_errors") or "no first_errors provided"
        raise ArtifactError(f"question bank failed validation: {first}", kind="invalid")

    # Node 13 stringifies config to avoid Dify's object-depth limit.
    bank_config = outputs.get("bank_config")
    if isinstance(bank_config, str):
        try:
            bank_config = json.loads(bank_config)
        except json.JSONDecodeError:
            pass  # leave it as the raw string; caller can show it verbatim

    return {
        "run_id": run_id,
        "questions": outputs.get("questions") or [],
        "question_count": outputs.get("question_count") or 0,
        "bank_config": bank_config,
        "schema_version": outputs.get("schema_version") or "",
        "validate_valid": True,
        "validate_error_count": outputs.get("validate_error_count") or 0,
        "validate_first_errors": outputs.get("validate_first_errors") or "",
        "bank_path": outputs.get("bank_path") or "",
    }
