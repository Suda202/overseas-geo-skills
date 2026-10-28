"""Tolerant parse for the paste-a-JSON channel.

Handles the common noise people copy in: markdown fences, smart quotes,
trailing commas, and either a bare flat object or a {"case": {...}} wrapper.
"""
from __future__ import annotations

import json
import re
from typing import Any

_SMART_QUOTES = {
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "’": "'",
    "‘": "'",
    "′": "'",
}


def _strip_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json|JSON)?\s*\n(.*?)\n?```\s*$", s, re.DOTALL)
    return m.group(1).strip() if m else s


def _normalize_quotes(s: str) -> str:
    for a, b in _SMART_QUOTES.items():
        s = s.replace(a, b)
    return s


def _strip_trailing_commas(s: str) -> str:
    # Remove ",}" and ",]" left by hand-edited JSON. Only safe because we
    # operate on a paste buffer, not a trusted stream.
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _unwrap_case(obj: Any) -> Any:
    if isinstance(obj, dict):
        # {"case": {...}} or {"case": "..."}
        if "case" in obj and isinstance(obj.get("case"), (dict, str)):
            inner = obj["case"]
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except json.JSONDecodeError:
                    return inner
            return inner
        # Dify "inputs" wrapper from a run-history copy.
        if "inputs" in obj and isinstance(obj["inputs"], dict):
            return obj["inputs"]
    return obj


def parse_pasted_case(raw: str) -> Any:
    """Return a dict ready for CaseInput, or raise ValueError with a readable msg."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("paste body is empty")
    s = _strip_fences(raw)
    s = _normalize_quotes(s)
    s = _strip_trailing_commas(s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON after tolerant parse: {e}") from e
    obj = _unwrap_case(obj)
    if not isinstance(obj, dict):
        raise ValueError(f"expected a JSON object, got {type(obj).__name__}")
    return obj
