"""Pydantic models for the orchestrator.

Field names mirror the Dify workflow start-node variables exactly so there is
no translation table to go stale.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class Competitor(BaseModel):
    name: str
    official_domain: str = ""


class CaseInput(BaseModel):
    """The 9 fields the Dify workflow start node expects."""

    brand_name: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    business_mode: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    official_domain: str = Field(..., min_length=1)
    topics: str = Field(..., min_length=1)
    competitors: List[Competitor] = Field(default_factory=list, max_length=6)
    regions: str = Field(..., min_length=1)
    supplemental: str = ""

    @field_validator("competitors", mode="before")
    @classmethod
    def _coerce_competitors(cls, v: Any) -> Any:
        if v is None or v == "":
            return []
        # Accept a JSON array string (what people paste out of Dify).
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            try:
                v = json.loads(s)
            except json.JSONDecodeError:
                # Fall back to "Name: domain, Name2: domain2" or comma list.
                items = []
                for chunk in re.split(r"[,;]\s*|\n", s):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if ":" in chunk:
                        name, _, domain = chunk.partition(":")
                        items.append({"name": name.strip(), "official_domain": domain.strip()})
                    else:
                        items.append({"name": chunk, "official_domain": ""})
                return items
        out = []
        for item in v if isinstance(v, list) else []:
            if isinstance(item, dict):
                out.append({
                    "name": item.get("name") or item.get("名称") or "",
                    "official_domain": item.get("official_domain")
                    or item.get("官网域名")
                    or item.get("domain")
                    or "",
                })
            elif isinstance(item, str) and item.strip():
                out.append({"name": item.strip(), "official_domain": ""})
        return out

    def to_inputs(self) -> dict:
        """Serialize to the Dify workflow `inputs` object.

        Keys are exactly the workflow's start-node variable names. competitors
        becomes the JSON array string the workflow parses.
        """
        comps = [
            {"name": c.name, "official_domain": c.official_domain}
            for c in self.competitors
        ]
        return {
            "brand_name": self.brand_name,
            "company_name": self.company_name,
            "business_mode": self.business_mode,
            "category": self.category,
            "official_domain": self.official_domain,
            "topics": self.topics,
            "competitors": json.dumps(comps, ensure_ascii=False),
            "regions": self.regions,
            "supplemental": self.supplemental or "",
        }


class RunSubmit(BaseModel):
    case: CaseInput
    user: str = "orchestrator"


class PasteSubmit(BaseModel):
    raw: str


class Artifact(BaseModel):
    run_id: str
    questions: List[dict] = Field(default_factory=list)
    question_count: int = 0
    bank_config: Optional[Union[dict, str]] = None
    schema_version: str = ""
    validate_valid: bool = False
    validate_error_count: int = 0
    validate_first_errors: str = ""
    bank_path: str = ""
