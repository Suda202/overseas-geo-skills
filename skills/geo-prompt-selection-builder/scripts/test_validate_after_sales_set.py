#!/usr/bin/env python3
"""Focused contract tests for the after-sales validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_after_sales_set.py")


def question(topic_id: str, number: int) -> dict[str, object]:
    text = f"Which category providers fit scenario {topic_id} {number}?"
    return {
        "question_id": f"{topic_id}-{number}",
        "topic_id": topic_id,
        "user_question": text,
        "zh_translation": f"问题 {number}",
        "monitoring_prompt": text,
        "region": "United States",
        "prompt_type": "Discovery",
        "tags": ["Scenario"],
    }


def inherited_question(topic_id: str, number: int) -> dict[str, object]:
    row = question(topic_id, number)
    row.pop("prompt_type")
    row["intent_key"] = f"{topic_id}-discovery-buyer-choice"
    row["tags"] = ["Prompt Type: Discovery", "BrandScope: Non-Branded", "Scenario"]
    return row


def staged_bank(topic_count: int, lifecycle: str) -> dict[str, object]:
    topics = [{"topic_id": "topic_1", "topic": "Example Topic"}]
    return {
        "mode": "after-sales-strategic-topics",
        "config": {
            "generation_stage": "discovery",
            "lifecycle_status": lifecycle,
            "evidence_status": "customer_confirmed",
            "customer_confirmation": {"status": "confirmed"},
            "prompt_version": "v1",
            "topics": topics,
            "expected_total": topic_count,
        },
        "questions": [
            {
                **question("topic_1", number),
                "journey_stage": "发现",
                "audience": "通用",
                "group_role": "core",
                "attribute_ref": "",
                "evidence_refs": [f"input-{number}"],
            }
            for number in range(topic_count)
        ],
    }


def validate(data: dict[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as handle:
        json.dump(data, handle)
        handle.flush()
        return subprocess.run(
            [sys.executable, str(SCRIPT), handle.name],
            text=True,
            capture_output=True,
            check=False,
        )


class ValidateAfterSalesSetTests(unittest.TestCase):
    def test_hypothesis_topic_can_remain_below_five(self) -> None:
        result = validate(staged_bank(2, "hypothesis"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_discovery_method_question_without_candidate_ask_fails(self) -> None:
        for text, ok in [
            ("How do I get rid of litter box smell in a home with multiple cats?", False),
            ("What's the best way to get my cat to drink more water?", False),
            ("Which automatic litter boxes seal in odor best between bag changes?", True),
            ("Where can I source custom light guide panels for thin light box signs?", True),
        ]:
            data = staged_bank(2, "hypothesis")
            data["questions"][0]["user_question"] = text
            data["questions"][0]["monitoring_prompt"] = text
            result = validate(data)
            with self.subTest(text=text):
                self.assertEqual(result.returncode == 0, ok, result.stdout)
                if not ok:
                    self.assertIn("asks no candidate question", result.stdout)
        # 显式不进可见度统计的问题意识题放行
        data = staged_bank(2, "hypothesis")
        data["questions"][0]["user_question"] = "How can I get my cat to drink more water?"
        data["questions"][0]["monitoring_prompt"] = "How can I get my cat to drink more water?"
        data["questions"][0]["formal_visibility_eligible"] = False
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)

    def test_formal_topic_requires_five_prompts(self) -> None:
        result = validate(staged_bank(4, "locked"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("at least 5 Prompts per Topic", result.stdout)

    def test_after_sales_signal_cannot_be_formal_ready(self) -> None:
        data = staged_bank(5, "locked")
        data["config"]["evidence_status"] = "after_sales_signal"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be marked formal-ready", result.stdout)

    def test_discovery_stage_rejects_later_intents(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["prompt_type"] = "Evaluation"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("discovery stage must contain Discovery or Information Prompts only", result.stdout)

    def test_inherited_intent_and_brand_scope_tags_are_normalized(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"] = [inherited_question("topic_1", number) for number in range(5)]
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_staged_inherited_long_topic_name_is_accepted(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["topics"][0]["topic"] = (
            "LED display manufacturers and commercial display solution providers"
        )
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_conflicting_explicit_and_inherited_intent_fails(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["tags"] = ["Prompt Type: Evaluation", "Scenario"]
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prompt_type conflicts with Prompt Type tag", result.stdout)

    def test_formal_baseline_metadata_cannot_bypass_lifecycle(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["baseline"] = {
            "status": "formal",
            "planned_runs": 5,
            "conditions_key": "us-en-v1",
            "valid_samples_only": True,
            "failures_as_zero": False,
        }
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires a locked or formal lifecycle", result.stdout)

    def test_required_question_fields_and_bad_stage_fail_cleanly(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["generation_stage"] = ["discovery"]
        data["questions"][0]["question_id"] = ""
        data["questions"][0]["user_question"] = ""
        data["questions"][0]["zh_translation"] = ""
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("question_id is required", result.stdout)
        self.assertIn("user_question is required", result.stdout)
        self.assertIn("zh_translation is required", result.stdout)
        self.assertIn("generation_stage must be one of", result.stdout)


    def test_trial_runs_fixed_at_five_with_valid_run_floor(self) -> None:
        for planned, valid in ((5, 3), (5, 5)):
            with self.subTest(planned_runs=planned, valid_runs=valid):
                data = staged_bank(5, "locked")
                data["config"]["customer_confirmation"] = {
                    "status": "confirmed",
                    "scope_status": "confirmed",
                    "prompt_set_status": "confirmed",
                }
                data["config"]["trial"] = {
                    "status": "passed",
                    "planned_runs": planned,
                    "valid_runs": valid,
                    "evidence_refs": ["trial/run-1.json"],
                }
                result = validate(data)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_trial_run_range_rejects_non_three_or_five_plans(self) -> None:
        # 2026-10-23: 候选基线取消，trial 改为 ChatGPT 3 次质量试跑；旧题库的 5 仍兼容。
        for planned, valid in ((2, 2), (7, 7)):
            with self.subTest(planned_runs=planned):
                data = staged_bank(5, "locked")
                data["config"]["customer_confirmation"] = {
                    "status": "confirmed",
                    "scope_status": "confirmed",
                    "prompt_set_status": "confirmed",
                }
                data["config"]["trial"] = {
                    "status": "passed",
                    "planned_runs": planned,
                    "valid_runs": valid,
                    "evidence_refs": ["trial/run-1.json"],
                }
                result = validate(data)
                self.assertEqual(result.returncode, 1)
                self.assertIn("trial.planned_runs must be 3", result.stdout)

    def test_trial_accepts_three_and_legacy_five(self) -> None:
        for planned in (3, 5):
            with self.subTest(planned_runs=planned):
                data = staged_bank(5, "locked")
                data["config"]["customer_confirmation"] = {
                    "status": "confirmed",
                    "scope_status": "confirmed",
                    "prompt_set_status": "confirmed",
                }
                data["config"]["trial"] = {
                    "status": "passed",
                    "planned_runs": planned,
                    "valid_runs": planned,
                    "evidence_refs": ["trial/run-1.json"],
                }
                result = validate(data)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_formal_set_caps_each_topic_at_ten(self) -> None:
        def locked(count: int, lifecycle: str = "locked") -> dict:
            data = staged_bank(count, lifecycle)
            data["config"]["customer_confirmation"] = {
                "status": "confirmed",
                "scope_status": "confirmed",
                "prompt_set_status": "confirmed",
            }
            data["config"]["trial"] = {
                "status": "passed",
                "planned_runs": 5,
                "valid_runs": 5,
                "evidence_refs": ["trial/run-1.json"],
            }
            return data

        self.assertEqual(validate(locked(10)).returncode, 0)
        result = validate(locked(11))
        self.assertEqual(result.returncode, 1)
        self.assertIn("at most 10 Prompts per purchased Topic", result.stdout)
        # 候选阶段可以多出题
        self.assertEqual(validate(locked(14, "customer_confirmed")).returncode, 0, validate(locked(14, "customer_confirmed")).stdout)

    def test_information_is_experimental(self) -> None:
        data = staged_bank(5, "hypothesis")
        q = data["questions"][0]
        q.update({"prompt_type": "Information", "journey_stage": "解决问题", "formal_visibility_eligible": False})
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Information Prompts belong to the experimental layer", result.stdout)
        q["group_role"] = "experimental"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)

    def test_competitor_is_never_core(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["generation_stage"] = "diagnostic"
        q = data["questions"][0]
        q.update({"prompt_type": "Competitor", "journey_stage": "对比", "user_question": "Hbrand vs RivalH1 for HDB rentals?"})
        q["monitoring_prompt"] = q["user_question"]
        self.assertIn("Competitor and Alternatives Prompts belong to the monitoring or experimental layer", validate(data).stdout)
        q["group_role"] = "monitoring"
        self.assertNotIn("Prompts belong to the monitoring", validate(data).stdout)

    def test_audience_may_list_several_groups(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["audience"] = ["公民购房者", "PR 购房者"]
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["questions"][0]["audience"] = []
        self.assertIn("missing audience", validate(data).stdout)

    def test_low_condition_anchor_warns_unless_leader_default(self) -> None:
        data = staged_bank(2, "hypothesis")
        for row in data["questions"]:
            row["constraint_type"] = "约束"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("all carry conditions", result.stdout)
        # 任一题低条件即消警
        data["questions"][0]["constraint_type"] = "无限定"
        self.assertNotIn("all carry conditions", validate(data).stdout)
        # 领导者即默认：带原因豁免，缺原因报错
        data["questions"][0]["constraint_type"] = "约束"
        data["config"]["leader_default"] = {"reason": "领头平台占九成，买家不问哪个平台好"}
        self.assertNotIn("all carry conditions", validate(data).stdout)
        data["config"]["leader_default"] = {}
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("leader_default must state the reason", result.stdout)
        # 不记录 constraint_type 的旧库不触发
        data = staged_bank(2, "hypothesis")
        self.assertNotIn("all carry conditions", validate(data).stdout)

    def test_topic_clustering_trace_gates(self) -> None:
        data = staged_bank(2, "hypothesis")
        result = validate(data)
        self.assertIn("missing covered_attributes/planned_prompts", result.stdout)
        data["config"]["topics"][0].update(
            {"covered_attributes": ["气味控制"], "planned_prompts": 2}
        )
        data["config"]["attribute_plan"] = [
            {"attribute": "气味控制", "priority": "P1"},
            {"attribute": "无家可归的属性", "priority": "P1"},
        ]
        for row in data["questions"]:
            row["attribute_ref"] = "气味控制"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("homed in no Topic's covered_attributes", result.stdout)
        self.assertNotIn("missing covered_attributes/planned_prompts", result.stdout)
        # P1 一律要安家；降级并写原因后放行（与「无题不许挂 P1」同一语义）
        data["config"]["attribute_plan"][1]["priority"] = "P2"
        data["config"]["attribute_plan"][1]["no_carrier_reason"] = "共识锁定，首期不开主题"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["config"]["topics"][0]["covered_attributes"].append("拼错的属性")
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("absent from attribute_plan", result.stdout)

    def test_alternatives_type_contract(self) -> None:
        data = staged_bank(2, "hypothesis")
        data["config"]["generation_stage"] = "diagnostic"
        row = data["questions"][0]
        row["prompt_type"] = "Alternatives"
        row["user_question"] = "What are the best alternatives to RivalBrand for small teams?"
        row["monitoring_prompt"] = row["user_question"]
        row["journey_stage"] = "替代方案"
        row["group_role"] = "monitoring"
        row["formal_visibility_eligible"] = False
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        # 替代型计不计入提及率考核未定（Suda 2026-10-23）：formal_visibility_eligible 两种值都接受
        row["formal_visibility_eligible"] = True
        self.assertNotIn("must set formal_visibility_eligible: false", validate(data).stdout)
        row["formal_visibility_eligible"] = False
        # 不许进核心层
        row["group_role"] = "core"
        self.assertIn("monitoring or experimental layer", validate(data).stdout)
        row["group_role"] = "monitoring"
        # 替代型只许挂替代方案阶段
        row["journey_stage"] = "对比"
        self.assertIn("does not fit journey_stage", validate(data).stdout)
        # 旧库的替代题标 Competitor 仍合法（不迁移）
        row["journey_stage"] = "替代方案"
        row["prompt_type"] = "Competitor"
        row["constraints"] = ["租房"]  # 选词阶段 Competitor 题须带用例
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)

    def test_legacy_intent_field_is_read_as_prompt_type(self) -> None:
        data = staged_bank(2, "hypothesis")
        for row in data["questions"]:
            row.pop("prompt_type")
            row["intent"] = "Discovery"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        # 旧库的问题形状标签占着 prompt_type 时，以 intent 为准
        data["questions"][0]["prompt_type"] = "品类"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        # 两边都是合法类型且不同 → 冲突
        data["questions"][0]["prompt_type"] = "Information"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("conflicts with the legacy intent field", result.stdout)


QUOTES = [
    {"输入编号": "Q01", "原话": "I want something that records continuously while parked.", "约束": "停车持续录像"},
    {"输入编号": "Q04", "原话": "true 4K with a Sony STARVIS 2 sensor for plates at night", "约束": "STARVIS 2、夜间车牌、100 美元以内"},
    {"输入编号": "Q08", "原话": "poor customer service despite good reviews", "约束": "客服、200 美元以内"},
    {"输入编号": "Q09", "原话": "4 channel dash cam with parking mode", "约束": "四路、停车模式"},
]


def scoped_bank(rows: list[tuple[str, str, list[str], list[str]]]) -> dict[str, object]:
    """rows: (query, attribute, constraints, evidence_refs) under one Topic."""
    questions = []
    for number, (text, attribute, constraints, refs) in enumerate(rows):
        questions.append({
            **question("topic_1", number),
            "user_question": text,
            "monitoring_prompt": text,
            "journey_stage": "发现",
            "audience": "通用",
            "group_role": "core",
            "attribute_ref": attribute,
            "evidence_refs": refs,
            "constraints": constraints,
        })
    return {
        "mode": "after-sales-strategic-topics",
        "config": {
            "generation_stage": "discovery",
            "lifecycle_status": "hypothesis",
            "topics": [{"topic_id": "topic_1", "topic": "Dash Cams"}],
            "expected_total": len(questions),
            "buyer_quotes": QUOTES,
            "base_conditions": ["私家车"],
        },
        "questions": questions,
    }


class ScopeGateTests(unittest.TestCase):
    """Gates 36–37 (output-contract.md). Each case is one failure mode written down
    before the gate was coded (80-代码/选词工具-harness-AB/runs/gates/FAILURE-MODES.md)."""

    def outside(self, rows) -> str:
        result = validate(scoped_bank(rows))
        return "\n".join(l for l in result.stdout.splitlines() if "outside the cited evidence" in l)

    def test_condition_backed_by_constraint_column_passes(self) -> None:
        # 「200 美元以内」 is in Q08's 约束 column though not in the quote text (Suda 2026-10-22)
        self.assertEqual(self.outside([("Which dash cams under $200 are worth buying?", "Price", ["200 美元以内"], ["Q08"])]), "")

    def test_undeclared_number_outside_evidence_fails(self) -> None:  # F1
        self.assertIn("数字 512", self.outside([("Which dash cams support a 512GB card?", "Storage", [], ["Q01"])]))

    def test_cjk_numeral_in_constraint_column_matches_digits(self) -> None:  # F2, F11
        self.assertEqual(self.outside([("Which 4-channel dash cams have parking mode?", "Coverage", ["四路"], ["Q09"])]), "")
        self.assertEqual(self.outside([("Which 4-channel dash cams have parking mode?", "Coverage", ["4 路"], ["Q09"])]), "")

    def test_numbers_that_are_not_conditions_pass(self) -> None:  # F4
        rows = [("Which dash cams use Sony STARVIS 2 sensors for 24/7 parking monitoring in 2026?", "Night", [], ["Q01"])]
        self.assertEqual(self.outside(rows), "")

    def test_declared_condition_outside_evidence_fails(self) -> None:  # F5, F10
        out = self.outside([("Which dash cams catch a hit-and-run on the street overnight?", "Parking", ["肇事逃逸", "街边过夜"], ["Q01"])])
        self.assertIn("肇事逃逸", out)
        self.assertIn("街边过夜", out)

    def test_base_condition_is_not_a_condition(self) -> None:
        self.assertEqual(self.outside([("What are the best dash cams for a private car?", "", ["私家车"], ["Q01"])]), "")

    def test_low_condition_prompt_passes(self) -> None:  # F9
        self.assertEqual(self.outside([("Which dash cams capture plates clearly at night?", "Night", [], ["Q04"])]), "")

    def test_unknown_evidence_ref_is_reported_not_passed(self) -> None:  # F6
        result = validate(scoped_bank([("Which dash cams under $200 are worth buying?", "Price", ["200 美元以内"], ["Q99"])]))
        self.assertIn("evidence_refs not in config.buyer_quotes", result.stdout)
        self.assertIn("outside the cited evidence", result.stdout)

    def test_bank_without_quote_table_skips_with_warning(self) -> None:  # F7
        data = scoped_bank([("Which dash cams support a 512GB card?", "Storage", [], ["Q01"])])
        data["config"].pop("buyer_quotes")
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("config.buyer_quotes missing", result.stdout)

    def test_scenery_variant_of_one_decision_is_a_repeat(self) -> None:  # F13, F15, F12
        result = validate(scoped_bank([
            ("Which dash cams keep recording while the car is parked?", "Parking mode", [], ["Q01"]),
            ("Which dash cams catch a hit-and-run in a parking lot?", "Parking mode", [], ["Q01"]),
            ("Which dash cams are best for a car parked in a shared garage?", "Parking mode", [], ["Q01"]),
        ]))
        repeats = [l for l in result.stdout.splitlines() if "asked 3 times" in l]
        self.assertEqual(len(repeats), 1, result.stdout)  # F18: one line per group

    def test_evidence_backed_condition_is_a_new_decision(self) -> None:  # F14
        result = validate(scoped_bank([
            ("Which 4-channel dash cams keep recording while parked?", "Parking mode", ["四路"], ["Q09"]),
            ("Which dash cams keep recording while the car is parked?", "Parking mode", [], ["Q01"]),
        ]))
        self.assertNotIn("asked 2 times", result.stdout)

    def test_slice_ref_keys_the_decision(self) -> None:  # F19
        data = scoped_bank([
            ("Which dash cams keep recording while the car is parked?", "Parking mode", [], ["Q01"]),
            ("Which 4-channel dash cams keep recording while parked?", "Coverage", [], ["Q09"]),
        ])
        for row in data["questions"]:
            row["slice_ref"] = "M-007"
        self.assertIn("asked 2 times", validate(data).stdout)


class CompetitorUseCaseGateTests(unittest.TestCase):
    """Selection-stage Competitor Prompts must name a use case (constraints non-empty)."""

    GATE = "Competitor Prompt has no use case"

    def bank(self, constraints, stage="diagnostic") -> dict[str, object]:
        data = scoped_bank([("Is Hbrand or RivalH1 better for HDB rentals?", "", constraints, ["Q01"])])
        row = data["questions"][0]
        row.update({"prompt_type": "Competitor", "journey_stage": "对比", "group_role": "monitoring"})
        if stage is None:
            data["config"].pop("generation_stage")
        else:
            data["config"]["generation_stage"] = stage
        return data

    def test_empty_constraints_fail_at_selection_stage(self) -> None:
        for constraints in ([], None):
            data = self.bank([])
            if constraints is None:
                data["questions"][0].pop("constraints")
            with self.subTest(constraints=constraints):
                result = validate(data)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(self.GATE, result.stdout)

    def test_gate_does_not_need_buyer_quotes(self) -> None:
        data = self.bank([])
        data["config"].pop("buyer_quotes")
        self.assertIn(self.GATE, validate(data).stdout)

    def test_non_empty_constraints_pass(self) -> None:
        self.assertNotIn(self.GATE, validate(self.bank(["停车持续录像"])).stdout)

    def test_missing_stage_skips_gate_for_legacy_banks(self) -> None:
        self.assertNotIn(self.GATE, validate(self.bank([], stage=None)).stdout)

    def test_alternatives_are_not_checked(self) -> None:
        data = self.bank([])
        data["questions"][0].update({"prompt_type": "Alternatives", "journey_stage": "替代方案"})
        self.assertNotIn(self.GATE, validate(data).stdout)


class CategoryAliasNearDuplicateTests(unittest.TestCase):
    """Prompts that differ only by the buyer's name for the category are not near-duplicates."""

    ALIASES = ["GEO tools", "AI visibility tools"]
    A = "Which GEO tools help brands track AI answers?"
    B = "Which AI visibility tools help brands track AI answers?"
    C = "Which AI visibility tools help brands track AI answers cheaply?"

    def bank(self, texts, aliases) -> dict[str, object]:
        data = scoped_bank([(t, "Tracking", [], ["Q01"]) for t in texts])
        if aliases is not None:
            data["config"]["category_aliases"] = aliases
        return data

    def warned(self, data) -> bool:
        return "near-duplicate wording" in validate(data).stdout

    def test_category_wording_only_difference_is_allowed(self) -> None:
        self.assertFalse(self.warned(self.bank([self.A, self.B], self.ALIASES)))

    def test_without_aliases_the_warning_stays(self) -> None:
        self.assertTrue(self.warned(self.bank([self.A, self.B], None)))

    def test_difference_beyond_category_wording_still_warns(self) -> None:
        self.assertTrue(self.warned(self.bank([self.A, self.C], self.ALIASES)))

    def test_same_slice_warning_is_also_skipped(self) -> None:
        # Overlap ~43%: below 0.6, so only the same-slice (0.35) warning can fire.
        a = "Which GEO software platform for small agencies tracking brand answers do you recommend?"
        b = "Which AI search visibility monitoring tools for small agencies tracking brand answers do you recommend?"
        aliases = ["GEO software platform", "AI search visibility monitoring tools"]
        self.assertIn("same Topic, intent and attribute", validate(self.bank([a, b], None)).stdout)
        self.assertNotIn("same Topic, intent and attribute", validate(self.bank([a, b], aliases)).stdout)


class ScopeGateRegressionTests(unittest.TestCase):
    """The six 2026-10-22 A/B banks with their blind-review verdicts.

    Floors are set just under the measured catch rates (outside-evidence 95%,
    either gate 84% of failed Prompts) so a change that weakens a gate fails
    here; raising them needs a fresh blind review, not a code tweak.
    """

    SAMPLES = Path(__file__).resolve().parents[1] / "evals" / "scope-gates-ab-20261022"

    def test_gates_catch_blind_review_failures(self) -> None:
        review = json.loads((self.SAMPLES / "_review.json").read_text(encoding="utf-8"))["blind_review_fail"]
        caught_fit = total_fit = caught_any = total_any = 0
        for path in sorted(self.SAMPLES.glob("X*.json")):
            label = path.name.split("-")[0]
            data = json.loads(path.read_text(encoding="utf-8"))
            seq = {str(q["question_id"]): i + 1 for i, q in enumerate(data["questions"])}
            stdout = validate(data).stdout
            fit = {seq[qid] for qid in seq if f"ERROR: {qid}: condition outside" in stdout}
            dup: set[int] = set()
            for line in stdout.splitlines():
                if "one purchase decision asked" in line:
                    ids = line.split(": same Topic", 1)[0].removeprefix("WARNING: ").split(" / ")
                    dup |= {seq[i] for i in ids[1:]}
            bad_fit = set(review[label]["fit"])
            bad_any = bad_fit | set(review[label]["dup"])
            caught_fit += len(fit & bad_fit)
            total_fit += len(bad_fit)
            caught_any += len((fit | dup) & bad_any)
            total_any += len(bad_any)
        self.assertGreaterEqual(caught_fit / total_fit, 0.90, f"outside-evidence {caught_fit}/{total_fit}")
        self.assertGreaterEqual(caught_any / total_any, 0.80, f"either gate {caught_any}/{total_any}")


if __name__ == "__main__":
    unittest.main()
