#!/usr/bin/env python3
"""A Prompt Attribute must reference the Topic's P1/P2/P3, never an excluded candidate.

Regression for the Trip.Biz finding: a question carried ``Attribute: 一站式网页与移动端差旅预订``
while that candidate sat in the Topic plan's ``excluded`` list as a catalog-only fact.
Before this gate the value was silently accepted, because "exists in attribute_plan" was
never told apart from "exists among the planning priorities".
"""

from __future__ import annotations

import unittest

from test_v8_tags import MODULE, valid_v8_bank


class ExcludedAttributeTests(unittest.TestCase):
    def test_control_bank_still_passes(self) -> None:
        data = valid_v8_bank()
        errors, _, _ = MODULE.validate(data)
        self.assertEqual([], errors)

    def test_discovery_attribute_may_not_reference_an_excluded_candidate(self) -> None:
        data = valid_v8_bank()
        plan = data["config"]["attribute_plan"][0]
        excluded_candidate = plan["excluded"][0]["candidate"]
        self.assertTrue(excluded_candidate)
        discovery = next(
            row
            for row in data["questions"]
            if "Intent: Discovery" in row["tags"]
            and any(tag.startswith("Attribute: ") for tag in row["tags"])
        )
        discovery["tags"] = [
            tag for tag in discovery["tags"] if not tag.startswith("Attribute: ")
        ] + [f"Attribute: {excluded_candidate}"]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("is an excluded candidate", joined)
        self.assertIn("never an excluded or accuracy_only candidate", joined)

    def test_competitor_attribute_may_not_reference_an_excluded_candidate(self) -> None:
        data = valid_v8_bank()
        plan = data["config"]["attribute_plan"][0]
        excluded_candidate = plan["excluded"][0]["candidate"]
        competitor = next(
            row for row in data["questions"] if "Intent: Competitor" in row["tags"]
        )
        competitor["tags"] = [
            tag for tag in competitor["tags"] if not tag.startswith("Attribute: ")
        ] + [f"Attribute: {excluded_candidate}"]
        errors, _, _ = MODULE.validate(data)
        self.assertIn("is an excluded candidate", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
