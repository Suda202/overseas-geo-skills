#!/usr/bin/env python3
"""The selection validator must judge the candidate ask exactly as the shared gate does."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "shared" / "scripts",
             ROOT / "geo-prompt-selection-builder" / "scripts"):
    sys.path.insert(0, str(path))

import prompt_gates  # noqa: E402
import validate_after_sales_set as selection  # noqa: E402


class SharedGateTests(unittest.TestCase):
    def test_regression_table(self) -> None:
        for text, expected in prompt_gates.REGRESSION_CASES:
            with self.subTest(text=text):
                self.assertEqual(expected, prompt_gates.requests_candidates(text))

    def test_selection_validator_uses_shared_gate(self) -> None:
        self.assertIs(selection._prompt_gates.requests_candidates, prompt_gates.requests_candidates)


if __name__ == "__main__":
    unittest.main()
