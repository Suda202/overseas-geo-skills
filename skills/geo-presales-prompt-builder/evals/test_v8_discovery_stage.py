#!/usr/bin/env python3
"""Discovery-first acceptance without relaxing legacy diagnostic contracts."""

from __future__ import annotations

import copy
import unittest

from test_v8_tags import MODULE, valid_v8_bank


def discovery_bank(counts: tuple[int, ...] = (6, 8, 8)) -> dict:
    data = valid_v8_bank(len(counts))
    config = data["config"]
    config["generation_stage"] = "discovery"
    topic_counts = {
        topic["topic_id"]: count
        for topic, count in zip(config["topics"], counts)
    }
    rows = []
    for topic_id, count in topic_counts.items():
        rows.extend([
            row for row in data["questions"]
            if row["topic_id"] == topic_id and "Intent: Discovery" in row["tags"]
        ][:count])
    data["questions"] = rows
    for plan in config["attribute_plan"]:
        count = topic_counts[plan["topic_id"]]
        plan["priorities"]["P1"] = plan["priorities"]["P1"][:count]
    quotas = {
        topic_id: {
            tag: count if role == "discovery" else 0
            for role, tag in MODULE.V8_INTENT_TAGS.items()
        }
        for topic_id, count in topic_counts.items()
    }
    config["expected_total"] = sum(counts)
    config["quotas"] = {
        "per_topic": quotas["topic_1"],
        "topic_overrides": {
            topic_id: quota for topic_id, quota in quotas.items()
            if topic_id != "topic_1"
        },
        "intent_tags": {
            tag: sum(quota[tag] for quota in quotas.values())
            for tag in MODULE.V8_INTENT_TAGS.values()
        },
    }
    return data


class DiscoveryStageTests(unittest.TestCase):
    def test_discovery_only_passes_for_one_to_three_topics(self) -> None:
        for counts in ((5,), (5, 6), (6, 8, 8)):
            with self.subTest(counts=counts):
                errors, warnings, summary = MODULE.validate(discovery_bank(counts))
                self.assertEqual([], errors)
                self.assertEqual([], warnings)
                self.assertEqual("discovery", summary["generation_stage"])
                self.assertEqual(sum(counts), summary["total"])
                self.assertEqual(
                    {"Intent: Discovery": sum(counts)},
                    summary["default_intent_tags"],
                )

    def test_discovery_accepts_lightweight_evidence_backed_attribute_plan(self) -> None:
        data = discovery_bank((5,))
        plan = data["config"]["attribute_plan"][0]
        plan["priorities"]["P1"] = plan["priorities"]["P1"][:1]
        plan["priorities"]["P2"] = []
        plan["priorities"]["P1"][0].pop("verification_statement")
        kept = f"Attribute: {plan['priorities']['P1'][0]['attribute']}"
        for row in data["questions"]:
            row["tags"] = [
                tag for tag in row["tags"]
                if not tag.startswith("Attribute: ") or tag == kept
            ]
        errors, warnings, _ = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_omitted_stage_keeps_legacy_full_diagnostic_requirements(self) -> None:
        data = discovery_bank((5,))
        del data["config"]["generation_stage"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any(".competitor must remain 3" in err for err in errors), errors)
        errors, warnings, summary = MODULE.validate(valid_v8_bank(2))
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual("diagnostic", summary["generation_stage"])

    def test_explicit_diagnostic_stage_accepts_existing_full_bank(self) -> None:
        data = valid_v8_bank()
        data["config"]["generation_stage"] = "diagnostic"
        errors, warnings, _ = MODULE.validate(data, discovery_bank((5,)))
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_unknown_or_malformed_stage_cannot_bypass_validation(self) -> None:
        for value in ("draft", "", None, True, [], {}):
            with self.subTest(value=value):
                data = discovery_bank((5,))
                data["config"]["generation_stage"] = value
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(any("generation_stage" in err for err in errors), errors)

    def test_non_discovery_quotas_are_rejected_even_if_totals_match(self) -> None:
        for role in ("competitor", "evaluation", "category_awareness"):
            with self.subTest(role=role):
                data = discovery_bank((5,))
                quota_tag = MODULE.V8_INTENT_TAGS[role]
                data["config"]["quotas"]["per_topic"][quota_tag] = 1
                data["config"]["quotas"]["intent_tags"][quota_tag] = 1
                data["config"]["expected_total"] += 1
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(any(f".{role} must remain 0" in err for err in errors), errors)

    def test_non_discovery_rows_are_rejected(self) -> None:
        data = discovery_bank((5,))
        full = valid_v8_bank()
        data["questions"].append(next(
            row for row in full["questions"] if "Intent: Evaluation" in row["tags"]
        ))
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(errors)

    def test_per_topic_minimum_and_existing_p1_coverage(self) -> None:
        errors, warnings, _ = MODULE.validate(discovery_bank((4,)))
        self.assertTrue(any("at least 5 Prompts per Topic" in err for err in errors), errors)
        self.assertEqual([], warnings)
        data = discovery_bank((5,))
        for row in data["questions"]:
            row["tags"] = [tag for tag in row["tags"] if not tag.startswith("Attribute: ")]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("cover every P1" in err for err in errors), errors)

    def test_discovery_still_rejects_fabricated_attribute_evidence(self) -> None:
        data = discovery_bank((5,))
        data["config"]["attribute_plan"][0]["priorities"]["P1"][0]["source_value"] = "invented"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("source_value must equal" in err for err in errors), errors)

    def test_discovery_still_rejects_brands_duplicates_and_wrong_routing(self) -> None:
        original = discovery_bank((5,))
        cases = []
        branded = copy.deepcopy(original)
        branded["questions"][0]["user_question"] = "Which LED display providers including Edgelight should I choose?"
        branded["questions"][0]["monitoring_prompt"] = branded["questions"][0]["user_question"]
        cases.append((branded, "must not name configured brands"))
        duplicate = copy.deepcopy(original)
        duplicate["questions"][1]["user_question"] = duplicate["questions"][0]["user_question"]
        duplicate["questions"][1]["monitoring_prompt"] = duplicate["questions"][0]["user_question"]
        cases.append((duplicate, "DUPLICATE"))
        routing = copy.deepcopy(original)
        routing["questions"][0]["analysis_type"] = "sentiment"
        cases.append((routing, "analysis_type must equal visibility,sentiment"))
        for data, message in cases:
            with self.subTest(message=message):
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(any(message in err for err in errors), errors)

    def test_negative_quota_and_missing_topic_override_fail(self) -> None:
        data = discovery_bank()
        data["config"]["quotas"]["topic_overrides"]["topic_2"]["Intent: Evaluation"] = -1
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("counts must be non-negative" in err for err in errors), errors)
        data = discovery_bank()
        del data["config"]["quotas"]["topic_overrides"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("quota" in err.lower() or "expected_total" in err for err in errors), errors)

    def test_fifty_is_the_batch_ceiling(self) -> None:
        errors, warnings, summary = MODULE.validate(discovery_bank((17, 17, 16)))
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(50, summary["total"])
        errors, _, _ = MODULE.validate(discovery_bank((17, 17, 17)))
        self.assertTrue(any("must not exceed 50" in err for err in errors), errors)

    def test_explicit_diagnostic_can_add_only_one_evaluation(self) -> None:
        data = discovery_bank((5,))
        baseline = copy.deepcopy(data)
        data["config"]["generation_stage"] = "diagnostic"
        full = valid_v8_bank()
        data["questions"].append(next(
            row for row in full["questions"] if "Intent: Evaluation" in row["tags"]
        ))
        data["config"]["quotas"]["per_topic"]["Intent: Evaluation"] = 1
        data["config"]["quotas"]["intent_tags"]["Intent: Evaluation"] = 1
        data["config"]["expected_total"] += 1
        errors, warnings, _ = MODULE.validate(data, baseline)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_diagnostic_requires_original_bank_and_preserves_discovery(self) -> None:
        baseline = discovery_bank((6,))
        data = copy.deepcopy(baseline)
        data["config"]["generation_stage"] = "diagnostic"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("--baseline" in err for err in errors), errors)
        errors, _, _ = MODULE.validate(data, baseline)
        self.assertEqual([], errors)
        dropped = copy.deepcopy(data)
        dropped["questions"].pop()
        dropped["config"]["quotas"]["per_topic"]["Intent: Discovery"] -= 1
        dropped["config"]["quotas"]["intent_tags"]["Intent: Discovery"] -= 1
        dropped["config"]["expected_total"] -= 1
        errors, _, _ = MODULE.validate(dropped, baseline)
        self.assertTrue(any("missing original Discovery" in err for err in errors), errors)
        rewritten = copy.deepcopy(data)
        rewritten["questions"][0]["user_question"] += " Please recommend candidates."
        rewritten["questions"][0]["monitoring_prompt"] = rewritten["questions"][0]["user_question"]
        errors, _, _ = MODULE.validate(rewritten, baseline)
        self.assertTrue(any("changed fields" in err for err in errors), errors)

    def test_baseline_cannot_be_another_language_or_invalid_snapshot(self) -> None:
        baseline = discovery_bank((5,))
        data = copy.deepcopy(baseline)
        data["config"]["generation_stage"] = "diagnostic"
        data["config"]["locale"] = "fr"
        errors, _, _ = MODULE.validate(data, baseline)
        self.assertTrue(any("preserve locale" in err for err in errors), errors)
        baseline["questions"] = []
        errors, _, _ = MODULE.validate(data, baseline)
        self.assertTrue(any("BASELINE invalid" in err for err in errors), errors)

    def test_supplied_baseline_is_not_ignored_for_a_historical_bank(self) -> None:
        data = valid_v8_bank()
        baseline = copy.deepcopy(data)
        data["questions"][0]["user_question"] += " Please recommend candidates."
        data["questions"][0]["monitoring_prompt"] = data["questions"][0]["user_question"]
        errors, _, _ = MODULE.validate(data, baseline)
        self.assertTrue(any("changed fields" in err for err in errors), errors)

    def test_broad_questions_do_not_require_invented_attributes(self) -> None:
        data = discovery_bank((5,))
        plan = data["config"]["attribute_plan"][0]
        plan["priorities"] = {"P1": [], "P2": [], "P3": []}
        for row in data["questions"]:
            row["tags"] = [tag for tag in row["tags"] if not tag.startswith("Attribute: ")]
        errors, warnings, _ = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)


if __name__ == "__main__":
    unittest.main()
