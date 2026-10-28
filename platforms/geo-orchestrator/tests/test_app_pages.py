from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_index_page_renders():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "GEO Orchestrator" in response.text


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_run_detail_page_renders(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "testrun0001"
    run_dir.mkdir(parents=True)
    (run_dir / "input.json").write_text(
        json.dumps(
            {
                "case": {
                    "brand_name": "KeepBalance",
                    "company_name": "KeepBalance",
                    "category": "family dietary supplements",
                    "regions": "US",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNS_DIR", str(runs_dir))

    with TestClient(app) as client:
        response = client.get("/runs/testrun0001")
    assert response.status_code == 200
    assert "KeepBalance" in response.text
