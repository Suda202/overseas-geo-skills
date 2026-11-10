#!/usr/bin/env python3
"""Shadow-audit CLI only; production reports use backend_report.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "geo-metrics" / "scripts"))

from geo_presales_editor.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
