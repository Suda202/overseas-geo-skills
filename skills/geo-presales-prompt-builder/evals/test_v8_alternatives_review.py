#!/usr/bin/env python3
"""Named alternatives and buyer-phrased review as second formulations."""

from __future__ import annotations

import copy
import unittest

from test_v8_tags import MODULE, valid_v8_bank


def diagnostic_bank() -> dict:
    data = valid_v8_bank(1)
    data["config"]["generation_stage"] = "diagnostic"
    return data


def row_for(data: dict, role: str) -> dict:
    tag = MODULE.V8_PROMPT_TYPE_TAGS[role]
    return next(row for row in data["questions"] if tag in row["tags"])


class NamedAlternativesTests(unittest.TestCase):
    def test_competitor_may_name_one_competitor_without_the_target(self) -> None:
        data = diagnostic_bank()
        row = row_for(data, "competitor")
        config = data["config"]
        competitor = config["competitor_selection"]["formal_competitors"][0]["name"]
        target = config["brand_name"]
        row["user_question"] = f"What are the alternatives to {competitor}?"
        row["monitoring_prompt"] = row["user_question"]
        row["zh_translation"] = f"{competitor} 有哪些替代选择？"
        self.assertNotIn(target, row["user_question"])
        errors, _, _ = MODULE.validate(data)
        self.assertFalse(
            any("competitor must name target" in error for error in errors), errors
        )

    def test_competitor_without_any_brand_is_still_rejected(self) -> None:
        data = diagnostic_bank()
        row = row_for(data, "competitor")
        row["user_question"] = "What are the alternatives to a spreadsheet?"
        row["monitoring_prompt"] = row["user_question"]
        row["zh_translation"] = "电子表格有哪些替代选择？"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("competitor must name target" in error for error in errors), errors
        )


class ReviewPhrasingTests(unittest.TestCase):
    def test_evaluation_accepts_the_registered_review_template(self) -> None:
        data = diagnostic_bank()
        row = row_for(data, "evaluation")
        config = data["config"]
        expected = MODULE.build_v8_review_prompt(
            config["category_label"],
            config["brand_object_type"],
            config["brand_name"],
            next(
                topic["topic"]
                for topic in config["topics"]
                if topic["topic_id"] == row["topic_id"]
            ),
            config.get("locale", "en"),
        )
        self.assertTrue(expected, "review template must be registered for this locale")
        row["user_question"] = expected
        row["monitoring_prompt"] = expected
        row["zh_translation"] = "该品牌到底好不好？"
        errors, _, _ = MODULE.validate(data)
        self.assertFalse(
            any("fixed sentiment template" in error for error in errors), errors
        )

    def test_evaluation_still_rejects_unregistered_wording(self) -> None:
        data = diagnostic_bank()
        row = row_for(data, "evaluation")
        row["user_question"] = "Tell me about this brand please."
        row["monitoring_prompt"] = row["user_question"]
        row["zh_translation"] = "请介绍一下这个品牌。"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("fixed sentiment template" in error for error in errors), errors
        )


class BestPhrasingTests(unittest.TestCase):
    def test_superlative_with_plural_product_asks_for_candidates(self) -> None:
        for text in (
            "Best dash cams for rideshare drivers",
            "What are the best automatic litter boxes for multi-cat homes?",
        ):
            self.assertTrue(MODULE._v6_requests_concrete_candidates(text, "en"), text)

    def test_superlative_method_question_is_still_rejected(self) -> None:
        for text in (
            "Best ways to reduce litter box smell",
            "What are the best practices for corporate travel policy?",
        ):
            self.assertFalse(MODULE._v6_requests_concrete_candidates(text, "en"), text)


if __name__ == "__main__":
    unittest.main()
