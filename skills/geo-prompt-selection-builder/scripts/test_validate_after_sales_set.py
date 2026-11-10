#!/usr/bin/env python3
"""Focused contract tests for the selection validator."""

from __future__ import annotations

import csv
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


def current_bank(count: int, lifecycle: str) -> dict[str, object]:
    """A bank in the current structure: selection stage, one Discovery matrix row, every Prompt on it."""
    return {
        "mode": "after-sales-strategic-topics",
        "config": {
            "generation_stage": "selection",
            "lifecycle_status": lifecycle,
            "evidence_status": "customer_confirmed",
            "customer_confirmation": {"status": "confirmed"},
            "prompt_version": "v1",
            "topics": [{"topic_id": "topic_1", "topic": "Example Topic"}],
            "slices": [{"slice_id": "M-001", "topic_id": "topic_1", "prompt_type": "Discovery", "priority": "高",
                        "priority_basis": "核心目标客户与使用场景（1）"}],
            "expected_total": count,
        },
        "questions": [
            {**question("topic_1", number), "slice_ref": "M-001", "attribute_ref": "", "evidence_refs": [f"input-{number}"]}
            for number in range(count)
        ],
    }


def spread_topics(data: dict, sizes: list[int] | None = None) -> dict:
    """Re-file the Prompts of current_bank into Topics of the given sizes (default: 10 each), one Discovery row each."""
    questions = data["questions"]
    sizes = sizes or [10] * ((len(questions) + 9) // 10)
    topics, slices, start = [], [], 0
    for index, size in enumerate(sizes, 1):
        topic_id, slice_id = f"topic_{index}", f"M-{index:03d}"
        topics.append({"topic_id": topic_id, "topic": f"Example Topic {index}"})
        slices.append({"slice_id": slice_id, "topic_id": topic_id, "prompt_type": "Discovery", "priority": "高",
                       "priority_basis": "核心目标客户与使用场景（1）"})
        for row in questions[start:start + size]:
            row.update(topic_id=topic_id, slice_ref=slice_id)
        start += size
    data["config"]["topics"], data["config"]["slices"] = topics, slices
    return data


def validate(data: dict[str, object], old_structure: bool = False) -> subprocess.CompletedProcess[str]:
    """Run the validator. A fixture refused as old structure would make every assertNotIn pass vacuously, so that
    fails here unless the test is about old structure."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as handle:
        json.dump(data, handle)
        handle.flush()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), handle.name],
            text=True,
            capture_output=True,
            check=False,
        )
    if not old_structure and "unsupported old structure" in result.stdout:
        raise AssertionError(f"fixture is an old-structure bank: {result.stdout}")
    return result


class ValidateAfterSalesSetTests(unittest.TestCase):
    def test_hypothesis_topic_can_remain_below_five(self) -> None:
        result = validate(current_bank(2, "hypothesis"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_discovery_method_question_without_candidate_ask_fails(self) -> None:
        for text, ok in [
            ("How do I get rid of litter box smell in a home with multiple cats?", False),
            ("What's the best way to get my cat to drink more water?", False),
            ("Which automatic litter boxes seal in odor best between bag changes?", True),
            ("Where can I source custom light guide panels for thin light box signs?", True),
        ]:
            data = current_bank(2, "hypothesis")
            data["questions"][0]["user_question"] = text
            data["questions"][0]["monitoring_prompt"] = text
            result = validate(data)
            with self.subTest(text=text):
                self.assertEqual(result.returncode == 0, ok, result.stdout)
                if not ok:
                    self.assertIn("asks no candidate question", result.stdout)

    def test_topic_has_no_prompt_floor(self) -> None:  # Suda 2026-10-30
        result = validate(current_bank(4, "locked"))
        self.assertNotIn("at least 5 Prompts per Topic", result.stdout)

    def test_after_sales_signal_cannot_be_formal_ready(self) -> None:
        data = current_bank(5, "locked")
        data["config"]["evidence_status"] = "after_sales_signal"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be marked formal-ready", result.stdout)

    def test_candidate_count_outside_30_to_60_warns(self) -> None:
        # 门禁 47：单产品线 × 单市场候选题 30–60 道，超出告警；锁版后不查
        data = current_bank(5, "hypothesis")
        self.assertIn("candidate Prompt count outside 30–60", validate(data).stdout)
        data = current_bank(30, "hypothesis")
        data["questions"] = [{**row, "user_question": f"Which cat litter box works best for setup number {i}?",
                              "monitoring_prompt": f"Which cat litter box works best for setup number {i}?"}
                             for i, row in enumerate(data["questions"])]
        self.assertNotIn("candidate Prompt count outside 30–60", validate(data).stdout)
        data = current_bank(5, "locked")
        self.assertNotIn("candidate Prompt count outside 30–60", validate(data).stdout)

    def test_formal_baseline_metadata_cannot_bypass_lifecycle(self) -> None:
        data = current_bank(5, "hypothesis")
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
        data = current_bank(5, "hypothesis")
        data["questions"][0]["question_id"] = ""
        data["questions"][0]["user_question"] = ""
        data["questions"][0]["zh_translation"] = ""
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("question_id is required", result.stdout)
        self.assertIn("user_question is required", result.stdout)
        self.assertIn("zh_translation is required", result.stdout)


    def test_trial_run_range_rejects_plans_other_than_three(self) -> None:
        for planned, valid in ((2, 2), (5, 5), (7, 7)):
            with self.subTest(planned_runs=planned):
                data = current_bank(5, "locked")
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

    def test_trial_accepts_three(self) -> None:
        for planned, valid in ((3, 3),):
            with self.subTest(valid_runs=valid):
                data = current_bank(5, "locked")
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

    def test_formal_set_caps_each_product_line_at_sixty(self) -> None:
        # 正式题每条产品线 × 国家 × 语言合计最多 60 道；每 10 道放一个主题，不碰售卖上限（2026-11-09）
        def locked(count: int, lifecycle: str = "locked") -> dict:
            data = spread_topics(current_bank(count, lifecycle))
            data["config"]["customer_confirmation"] = {
                "status": "confirmed",
                "scope_status": "confirmed",
                "prompt_set_status": "confirmed",
            }
            data["config"]["trial"] = {
                "status": "passed",
                "planned_runs": 3,
                "valid_runs": 3,
                "evidence_refs": ["trial/run-1.json"],
            }
            return data

        self.assertEqual(validate(locked(11)).returncode, 0, validate(locked(11)).stdout)
        self.assertEqual(validate(locked(60)).returncode, 0, validate(locked(60)).stdout)
        result = validate(locked(61))
        self.assertEqual(result.returncode, 1)
        self.assertIn("at most 60 Prompts per product line", result.stdout)
        # 停测题不占额度
        stopped = locked(61)
        stopped["questions"][0]["status"] = "停测"
        self.assertNotIn("at most 60 Prompts per product line", validate(stopped).stdout)
        # 候选阶段不设上限
        self.assertEqual(validate(locked(61, "customer_confirmed")).returncode, 0, validate(locked(61, "customer_confirmed")).stdout)

    def test_formal_set_caps_each_topic_at_ten(self) -> None:
        # 2026-11-09：售卖以一个主题 10 道为上限；混合选择时单个主题可以超过 10 道，合计不超过 10 × 主题数
        def locked(sizes: list[int], lifecycle: str = "locked") -> dict:
            data = spread_topics(current_bank(sum(sizes), lifecycle), sizes)
            data["config"]["customer_confirmation"] = {
                "status": "confirmed", "scope_status": "confirmed", "prompt_set_status": "confirmed"}
            data["config"]["trial"] = {"status": "passed", "planned_runs": 3, "valid_runs": 3,
                                       "evidence_refs": ["trial/run-1.json"]}
            return data

        message = "sold as at most 10 Prompts per Topic"
        self.assertNotIn(message, validate(locked([10])).stdout)
        result = validate(locked([11]))
        self.assertEqual(result.returncode, 1)
        self.assertIn(message, result.stdout)
        self.assertNotIn(message, validate(locked([4, 16])).stdout)  # 混合选择
        self.assertIn(message, validate(locked([4, 17])).stdout)
        stopped = locked([11])
        stopped["questions"][0]["status"] = "停测"
        self.assertNotIn(message, validate(stopped).stdout)
        self.assertNotIn(message, validate(locked([11], "customer_confirmed")).stdout)  # 候选阶段不设上限

    def test_bare_category_prompt_warns(self) -> None:
        # 2026-10-29 起不写宽泛品类题：全条件化不告警，无限定条件的发现题逐条告警
        data = current_bank(2, "hypothesis")
        for row in data["questions"]:
            row["constraint_type"] = "约束"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("no-condition Discovery Prompts", result.stdout)
        data["questions"][0]["constraint_type"] = "无限定"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no-condition Discovery Prompts (1)", result.stdout)

    def test_matrix_rows_carry_the_priority(self) -> None:
        data = current_bank(5, "hypothesis")
        data["config"]["slices"] = [
            {"slice_id": "M-001", "topic_id": "topic_1", "prompt_type": "Discovery", "priority": "高",
             "priority_basis": "品牌方点名：核心目标客户与购买场景（1）"},
            {"slice_id": "M-002", "topic_id": None, "prompt_type": "Discovery", "priority": "低",
             "priority_basis": "品牌方未提，只有假设"},
        ]
        for row in data["questions"]:
            row["slice_ref"] = "M-001"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        # 可改变性归监测侧（3.0.0）：选词不读 changeability，写了什么都不查
        data["questions"][0]["changeability"] = "待试跑"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("changeability", result.stdout)
        data["questions"][0].pop("changeability")
        # 低档行可以出题（Suda 2026-11-05）；行没定档、行优先级没写依据、主题对不上：报错
        data["questions"][2]["slice_ref"] = "M-002"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["config"]["slices"][1]["priority"] = ""
        self.assertIn("is not opened as a row", validate(data).stdout)
        data["config"]["slices"][1]["priority"] = "低"
        data["questions"][2]["slice_ref"] = "M-001"
        # 无高档行不再要求归入主题（Suda 2026-10-31：只要每题归一个主题、没有空主题）
        self.assertNotIn("homed in no Topic", validate(data).stdout)
        data["config"]["slices"][1]["priority_basis"] = ""
        self.assertIn("priority_basis is empty", validate(data).stdout)
        data["config"]["slices"][1]["priority_basis"] = "品牌方未提，只有假设"
        data["questions"][3]["topic_id"] = "topic_x"
        self.assertIn("differs from its row", validate(data).stdout)
        data["questions"][3]["topic_id"] = "topic_1"
        # 中档行不再只限 1 道（Suda 2026-11-02）：题数按决策差异定
        data["config"]["slices"][0]["priority"] = "中"
        self.assertNotIn("中 rows carrying more than one Prompt", validate(data).stdout)
        data["config"]["slices"][0]["priority"] = "高"
        # 品类认知只在属性池前预跑，不进新结构题库（Suda 2026-10-29）
        data["questions"][4]["prompt_type"] = "Category Awareness"
        self.assertIn("Category Awareness Prompts in the bank", validate(data).stdout)

    def test_non_discovery_row_needs_no_priority(self) -> None:
        # 3.0.0：非发现行只登记、不判档；发现行没定档仍报错
        data = current_bank(5, "hypothesis")
        data["config"]["slices"].append({"slice_id": "M-002", "prompt_type": "Competitor", "scene": "对比"})
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("slice M-002", result.stdout)
        data["config"]["slices"][1]["prompt_type"] = "Discovery"
        self.assertIn("slice M-002: priority must be", validate(data).stdout)

    def test_topic_floor_is_ten_prompts_only(self) -> None:
        # 3.0.0：W59 只剩「每发现主题至少 10 道」一个数，不再按 8 个不同决策签名告警
        data = current_bank(10, "hypothesis")
        for i, row in enumerate(data["questions"]):
            text = f"Which cat litter box works best for setup number {i}?"
            row.update(user_question=text, monitoring_prompt=text, attribute_ref="", constraints=[])
        result = validate(data)
        self.assertNotIn("[W59]", result.stdout)
        data["questions"] = data["questions"][:9]
        self.assertIn("[W59] Topics below the default coverage target (topic_1: 9 KPI Prompts)", validate(data).stdout)

    def test_topic_needs_prompts(self) -> None:
        data = current_bank(2, "hypothesis")
        data["config"]["topics"].append({"topic_id": "topic_2", "topic": "Brand check"})
        self.assertIn("Topics with no Prompt", validate(data).stdout)

    def test_selection_topic_holds_one_prompt_type(self) -> None:
        data = current_bank(6, "hypothesis")
        data["config"]["slices"] = [
            {"slice_id": "M-001", "topic_id": "topic_1", "prompt_type": "Discovery", "priority": "高", "priority_basis": "x"},
            {"slice_id": "M-002", "topic_id": "topic_1", "prompt_type": "Competitor", "priority": "高", "priority_basis": "x"},
        ]
        for row in data["questions"]:
            row["slice_ref"] = "M-001"
        data["questions"][0].update({"slice_ref": "M-002", "prompt_type": "Competitor"})
        self.assertIn("Gate 66", validate(data).stdout)
        # the same Topic is fine once it holds a single type, and needs no Discovery Prompt then
        data["config"]["slices"][0]["prompt_type"] = "Competitor"
        for row in data["questions"]:
            row.update({"slice_ref": "M-002", "prompt_type": "Competitor"})
        stdout = validate(data).stdout
        self.assertNotIn("Gate 66", stdout)
        self.assertNotIn("Topics with no Discovery Prompt", stdout)

    def test_topic_priority_has_a_basis(self) -> None:
        data = current_bank(2, "hypothesis")
        topic = data["config"]["topics"][0]
        topic["priority"] = "高"
        self.assertIn("priority_basis is empty", validate(data).stdout)
        topic["priority_basis"] = "核心目标客户与购买场景（1）落在本主题"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        topic["priority"] = "中"
        self.assertIn("its highest row is 高", validate(data).stdout)
        topic["priority"] = "急"
        self.assertEqual(validate(data).returncode, 1)

    def test_warning_decisions_and_capped_readiness(self) -> None:
        data = current_bank(2, "hypothesis")
        result = validate(data)
        self.assertIn("Usable", result.stdout)
        warnings = [line for line in result.stdout.splitlines() if line.startswith("WARNING")]
        self.assertTrue(warnings)
        data["config"]["warning_decisions"] = [{"match": w.split(": ", 1)[1][:40], "decision": "保留：测试"} for w in warnings]
        result = validate(data)
        self.assertIn("Ready for the next lifecycle stage", result.stdout)
        self.assertIn("WARNING (handled)", result.stdout)
        data["config"]["first_party_data"] = False
        self.assertIn("public data only", validate(data).stdout)

class OldStructureTests(unittest.TestCase):
    """Old banks are not supported: the validator names each old-structure marker and exits 2."""

    @staticmethod
    def old_shapes() -> list[tuple[str, dict[str, object]]]:
        shapes: list[tuple[str, dict[str, object]]] = []

        def shape(marker: str, edit) -> None:
            data = current_bank(5, "hypothesis")
            edit(data)
            shapes.append((marker, data))

        shape("no config.generation_stage", lambda b: b["config"].pop("generation_stage"))
        shape("generation_stage 'discovery'", lambda b: b["config"].update(generation_stage="discovery"))
        shape("generation_stage 'diagnostic'", lambda b: b["config"].update(generation_stage="diagnostic"))
        shape("config.extra_prompt_types", lambda b: b["config"].update(extra_prompt_types=["Competitor"]))
        shape("matrix rows tiered P1 / P2 / P3", lambda b: b["config"]["slices"][0].update(priority="P1"))
        shape("Prompt type in the intent field", lambda b: (b["questions"][0].pop("prompt_type"),
                                                             b["questions"][0].update(intent="Discovery")))
        shape("Prompt type in the intent field",
              lambda b: b["questions"][0].update(tags=["Prompt Type: Discovery"]))
        shape("old field names", lambda b: b["questions"][0].update(persona="通用"))
        shape("old field names", lambda b: b["questions"][0].update(review_status="已批准"))
        shape("no matrix rows", lambda b: b["config"].pop("slices"))
        shape("no matrix rows", lambda b: b["config"].update(slices=[]))
        shape("matrix rows without prompt_type", lambda b: b["config"]["slices"][0].pop("prompt_type"))
        shape("matrix rows with the prompt_types list",
              lambda b: b["config"]["slices"][0].update(prompt_types=[{"type": "Discovery"}]))
        shape("journey stages", lambda b: b["config"]["slices"][0].update(journey_stage="方案考虑"))
        shape("journey stages", lambda b: b["questions"][0].update(journey_stage="发现"))
        shape("journey stages", lambda b: b["questions"][0].update(journey_stage_9="发现"))
        shape("group_role", lambda b: b["questions"][0].update(group_role="core"))
        shape("group_role", lambda b: b["questions"][0].update(library_layer="核心"))
        shape("attribute_plan in the {p1, p2, p3} shape", lambda b: b["config"].update(attribute_plan={"p1": ["除味"]}))
        shape("attribute_plan with relative_competitor",
              lambda b: b["config"].update(attribute_plan=[{"attribute": "除味", "relative_competitor": "持平"}]))
        shape("attribute_plan with relative_competitor",
              lambda b: b["config"].update(attribute_plan=[{"attribute": "除味", "priority": "P1"}]))
        shape("attribute_plan with relative_competitor",
              lambda b: b["config"].update(attribute_plan=[{"attribute": "除味", "common_constraints": ["小户型"]}]))
        shape("config.leader_default", lambda b: b["config"].update(leader_default={"reason": "x"}))
        return shapes

    def test_each_old_shape_is_refused_as_unsupported(self) -> None:
        for marker, data in self.old_shapes():
            with self.subTest(marker=marker):
                result = validate(data, old_structure=True)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("unsupported old structure", result.stdout)
                self.assertIn(marker, result.stdout)
                self.assertIn("READINESS: Not ready", result.stdout)
                self.assertNotIn("WARNING", result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_current_bank_is_not_refused_and_blank_old_keys_do_not_count(self) -> None:
        data = current_bank(5, "hypothesis")
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["config"]["slices"][0]["journey_stage"] = ""
        data["questions"][0]["group_role"] = ""
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)

QUOTES = [
    {"输入编号": "Q01", "原话": "I want something that records continuously while parked.", "约束条件": "停车持续录像"},
    {"输入编号": "Q04", "原话": "true 4K with a Sony STARVIS 2 sensor for plates at night", "约束条件": "STARVIS 2、夜间车牌、100 美元以内"},
    {"输入编号": "Q08", "原话": "poor customer service despite good reviews", "约束条件": "客服、200 美元以内"},
    {"输入编号": "Q09", "原话": "4 channel dash cam with parking mode", "约束条件": "四路、停车模式"},
]

# 2.65.0 之前写的题库用旧短键名 `约束`，scope_gates.quote_index 仍读，别删这条。
QUOTES_LEGACY_KEY = [
    {"输入编号": "Q01", "原话": "I want something that records continuously while parked.", "约束": "停车持续录像"},
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
            "audience": "通用",
            "attribute_ref": attribute,
            "evidence_refs": refs,
            "constraints": constraints,
        })
    return {
        "mode": "after-sales-strategic-topics",
        "config": {
            "generation_stage": "selection",
            "lifecycle_status": "hypothesis",
            "topics": [{"topic_id": "topic_1", "topic": "Dash Cams"}],
            "slices": [{"slice_id": "M-001", "topic_id": "topic_1", "prompt_type": "Discovery", "priority": "高",
                        "priority_basis": "核心目标客户与使用场景（1）"}],
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

    def test_bare_cjk_one_is_not_a_number_without_a_measure_word(self) -> None:  # Nbrand 2026-10-23
        # 一般 / 一直 / 一起 / 一有 are adverbs, not the quantity 1; gate 36 used to
        # fail all four as 「数字 1」 on ordinary Traditional-Chinese prompts.
        for query in ("除了一般聊天機器人，有哪些 AI 會接即時行情？",
                      "有哪些非託管的加密貨幣 AI 助手，資產一直留在自己錢包裡？",
                      "有沒有巨鯨追蹤助手，大戶一有動作就通知我？",
                      "有沒有 AI 能把賠率和新聞放在一起分析？"):
            self.assertEqual(self.outside([(query, "Condition", [], ["Q01"])]), "", query)

    def test_numbers_that_are_not_conditions_pass(self) -> None:  # F4
        rows = [("Which dash cams use Sony STARVIS 2 sensors for 24/7 parking monitoring in 2026?", "Night", [], ["Q01"])]
        self.assertEqual(self.outside(rows), "")

    def test_declared_condition_outside_evidence_fails(self) -> None:  # F5, F10
        out = self.outside([("Which dash cams catch a hit-and-run on the street overnight?", "Parking", ["肇事逃逸", "街边过夜"], ["Q01"])])
        self.assertIn("肇事逃逸", out)
        self.assertIn("街边过夜", out)

    def test_unbacked_condition_is_a_warning_not_an_error(self) -> None:  # Suda 2026-10-30
        result = validate(scoped_bank([("Which dash cams catch a hit-and-run on the street overnight?", "Parking", ["肇事逃逸"], ["Q01"])]))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARNING: [W36] topic_1-0: condition outside the cited evidence", result.stdout)

    def test_written_basis_covers_condition_and_its_number(self) -> None:  # Suda 2026-10-30
        data = scoped_bank([("Which dash cams under $150 catch a hit-and-run overnight?", "Parking", ["肇事逃逸", "150 美元以内"], ["Q01"])])
        data["questions"][0]["condition_basis"] = {"肇事逃逸": "预跑答案：AI 选购标准列了肇事取证", "150 美元以内": "搜索词 dash cam under 150"}
        self.assertEqual(self.outside_data(data), "")
        data["questions"][0]["condition_basis"] = {"肇事逃逸": ""}
        self.assertIn("肇事逃逸", self.outside_data(data))

    def outside_data(self, data) -> str:
        return "\n".join(l for l in validate(data).stdout.splitlines() if "outside the cited evidence" in l)

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
        self.assertIn("no config.buyer_quotes", result.stdout)

    def test_legacy_quote_key_is_still_read(self) -> None:
        """2.65.0 把列名统一成 约束条件；旧题库的 约束 键仍要能读，否则 W36 静默失效。"""
        data = scoped_bank([("Which dash cams keep recording while parked?", "Parking", ["停车持续录像"], ["Q01"])])
        data["config"]["buyer_quotes"] = QUOTES_LEGACY_KEY
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("condition outside the cited evidence", result.stdout)

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
            row["slice_ref"] = "M-001"
        self.assertIn("asked 2 times", validate(data).stdout)


class CompetitorUseCaseGateTests(unittest.TestCase):
    """Selection-stage Competitor Prompts must name a use case (constraints non-empty)."""

    GATE = "Competitor Prompt has no use case"

    def bank(self, constraints) -> dict[str, object]:
        data = scoped_bank([("Is Hbrand or RivalH1 better for HDB rentals?", "", constraints, ["Q01"])])
        data["questions"][0]["prompt_type"] = "Competitor"
        data["config"]["slices"][0]["prompt_type"] = "Competitor"
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

    def test_alternatives_are_not_checked(self) -> None:
        data = self.bank([])
        data["questions"][0]["prompt_type"] = "Alternatives"
        data["config"]["slices"][0]["prompt_type"] = "Alternatives"
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


def as_current_structure(data: dict) -> dict:
    """The 2026-10-22 A/B samples were written in the old structure; gates 36–37 only read Topic, type, attribute_ref,
    constraints, evidence_refs and the quote table, so the samples are carried over in memory: drop the old keys and
    add one unreferenced matrix row. Prompts keep no slice_ref, so the decision key stays the attribute, as before."""
    config = data["config"]
    config["generation_stage"] = "selection"
    config["slices"] = [{"slice_id": "M-000", "prompt_type": "Discovery", "priority": "低", "priority_basis": "样本"}]
    for entry in config.get("attribute_plan") or []:
        for key in ("priority", "relative_competitor", "relative_competitor_basis", "common_constraints", "brand_value"):
            entry.pop(key, None)
    for q in data["questions"]:
        for key in ("journey_stage", "journey_stage_9", "journey", "group_role", "library_layer"):
            q.pop(key, None)
    return data


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
            data = as_current_structure(json.loads(path.read_text(encoding="utf-8")))
            seq = {str(q["question_id"]): i + 1 for i, q in enumerate(data["questions"])}
            stdout = validate(data).stdout
            self.assertNotIn("unsupported old structure", stdout)
            fit = {seq[qid] for qid in seq if f"WARNING: [W36] {qid}: condition outside" in stdout}
            dup: set[int] = set()
            for line in stdout.splitlines():
                if "one purchase decision asked" in line:
                    ids = line.split(": same Topic", 1)[0].removeprefix("WARNING: ").removeprefix("[W37] ").split(" / ")
                    dup |= {seq[i] for i in ids[1:]}
            bad_fit = set(review[label]["fit"])
            bad_any = bad_fit | set(review[label]["dup"])
            caught_fit += len(fit & bad_fit)
            total_fit += len(bad_fit)
            caught_any += len((fit | dup) & bad_any)
            total_any += len(bad_any)
        self.assertGreaterEqual(caught_fit / total_fit, 0.90, f"outside-evidence {caught_fit}/{total_fit}")
        self.assertGreaterEqual(caught_any / total_any, 0.80, f"either gate {caught_any}/{total_any}")


def goal_bank(selected: list[str] | None, information_named: bool = False) -> dict[str, object]:
    """A selection bank: five Discovery Prompts, plus business_goals when selected is not None."""
    data = current_bank(5, "hypothesis")
    data["config"].pop("expected_total")
    for row in data["questions"]:
        row.pop("tags")  # selection banks derive tags from config.tag_dimensions (W63)
    if selected is not None:
        data["config"]["business_goals"] = {"selected": selected, "information_named": information_named}
    return data


def add_typed(data: dict[str, object], prompt_type: str) -> None:
    """One Prompt of this type on its own row and Topic; Accuracy has no row (it sits outside the bank)."""
    text = {
        "Competitor": "BrandX vs RivalA for a small apartment with two cats?",
        "Evaluation": "Is BrandX worth it for a small apartment with two cats?",
        "Information": "Why does my apartment still smell like cat litter after scooping?",
        "Trust": "Are there common complaints about BrandX litter boxes?",
        "Transactional": "Where can I buy the BrandX litter box in Singapore?",
        "Support": "How do I reset the BrandX litter box after a sensor error?",
        "Accuracy": "What warranty does BrandX offer on its litter box in Singapore?",
    }[prompt_type]
    topic = f"topic_{prompt_type.casefold()}"
    row = {**question(topic, 90 + len(data["questions"])), "prompt_type": prompt_type, "user_question": text,
           "monitoring_prompt": text, "audience": "通用", "attribute_ref": "", "constraints": ["小户型"]}
    row.pop("tags")
    data["config"]["topics"].append({"topic_id": topic, "topic": prompt_type})
    if prompt_type != "Accuracy":
        data["config"]["slices"].append({"slice_id": f"M-{prompt_type}", "topic_id": topic, "prompt_type": prompt_type,
                                         "priority": "中", "priority_basis": "测试造数"})
        row["slice_ref"] = f"M-{prompt_type}"
    data["questions"].append(row)


class BusinessGoalGateTests(unittest.TestCase):
    """Gates 49 and 52 (Suda 2026-11-02 审核清单 B2; W50 / W51 removed in 3.0.0): business_goals decides which Prompt
    types are written."""

    def test_49_missing_business_goals_defaults_to_discovery(self) -> None:
        # 3.0.0：只做发现期间 business_goals 是常量，没写按 {selected: [发现型可见度], information_named: false} 填
        self.assertNotIn("[W49]", validate(goal_bank(None)).stdout)
        self.assertNotIn("[W49]", validate(goal_bank(["发现型可见度"])).stdout)
        # 写了但取值不在四个目标里，仍告警
        self.assertIn("[W49] config.business_goals malformed", validate(goal_bank(["品牌曝光"])).stdout)

    def test_default_goals_still_drive_gate_52(self) -> None:
        # 默认填充后 W52 照查：没写 business_goals 的题库出了对比题、问题解决题照样告警
        for prompt_type, label in (("Competitor", "竞争定位"), ("Information", "information_named")):
            with self.subTest(prompt_type=prompt_type):
                data = goal_bank(None)
                add_typed(data, prompt_type)
                self.assertIn(f"{prompt_type} Prompts written without the goal {label}", validate(data).stdout)

    def test_dormant_gates_50_51_removed(self) -> None:
        # 3.0.0：选了目标却没有对应题型的休眠门禁 W50 / W51 已删
        out = validate(goal_bank(["发现型可见度", "竞争定位", "声誉与信任"])).stdout
        self.assertNotIn("[W50]", out)
        self.assertNotIn("[W51]", out)

    def test_52_type_written_without_its_goal(self) -> None:
        for prompt_type, label in (("Competitor", "竞争定位"), ("Evaluation", "声誉与信任"),
                                   ("Information", "information_named")):
            with self.subTest(prompt_type=prompt_type):
                data = goal_bank(["发现型可见度"])
                add_typed(data, prompt_type)
                self.assertIn(f"{prompt_type} Prompts written without the goal {label}", validate(data).stdout)
                ok = goal_bank(["发现型可见度", label] if label != "information_named" else ["发现型可见度"],
                               information_named=label == "information_named")
                add_typed(ok, prompt_type)
                self.assertNotIn("written without the goal", validate(ok).stdout)
        # 替代题归竞争定位
        for goals, warned in ((["发现型可见度"], True), (["发现型可见度", "竞争定位"], False)):
            with self.subTest(goals=goals):
                data = goal_bank(goals)
                for row in data["questions"][1:]:
                    row["status"] = "停测"
                data["config"]["slices"][0]["prompt_type"] = "Alternatives"
                data["questions"][0].update(prompt_type="Alternatives",
                                            user_question="What are the best alternatives to RivalA for two cats?")
                data["questions"][0]["monitoring_prompt"] = data["questions"][0]["user_question"]
                check = self.assertIn if warned else self.assertNotIn
                check("Alternatives Prompts written without the goal 竞争定位", validate(data).stdout)


class EightTypeTests(unittest.TestCase):
    """2.42.0 (Suda 2026-11-06): eight prompt types; capability checks are Evaluation, Accuracy sits outside the bank."""

    def test_trust_belongs_to_reputation_goal(self) -> None:
        data = goal_bank(["发现型可见度"])
        add_typed(data, "Trust")
        self.assertIn("Trust Prompts written without the goal 声誉与信任", validate(data).stdout)
        ok = goal_bank(["发现型可见度", "声誉与信任"])
        add_typed(ok, "Trust")
        out = validate(ok).stdout
        self.assertNotIn("written without the goal", out)

    def test_transactional_and_support_have_no_goal_yet(self) -> None:
        for prompt_type, label in (("Transactional", "交易（未开放）"), ("Support", "售后（未开放）")):
            with self.subTest(prompt_type=prompt_type):
                data = goal_bank(["发现型可见度", "竞争定位", "声誉与信任"])
                add_typed(data, prompt_type)
                result = validate(data)
                self.assertIn(f"{prompt_type} Prompts written without the goal {label}", result.stdout)
                self.assertNotIn("unsupported prompt_type", result.stdout)

    def test_accuracy_rejected_from_selection_bank(self) -> None:
        data = goal_bank(["发现型可见度"])
        add_typed(data, "Accuracy")
        self.assertIn("Accuracy probes sit outside the bank", validate(data).stdout)


class WarningCodeTests(unittest.TestCase):
    """D5 / D3 (Suda 2026-11-02 审核清单): stable warning codes, whole-class decisions, gate 39 without terms."""

    @staticmethod
    def short_bank() -> dict[str, object]:
        data = goal_bank(["品牌曝光"])  # malformed goals keep one [W49] open (missing goals default since 3.0.0)
        data["config"]["collection_config"] = {"market": "United States", "language": "en"}
        for i, text in ((0, "best litter box"), (1, "best cat litter box")):
            data["questions"][i]["user_question"] = text  # [W32] too short, twice
            data["questions"][i].pop("monitoring_prompt")
        return data

    def test_every_warning_carries_a_code(self) -> None:
        lines = [l for l in validate(self.short_bank()).stdout.splitlines() if l.startswith("WARNING")]
        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, r"^WARNING(?: \(handled\))?: \[W\d+b?\] ")

    def test_gate_decision_covers_the_whole_class(self) -> None:
        data = self.short_bank()
        out = validate(data).stdout
        self.assertEqual(validate(data).returncode, 0, out)
        self.assertGreaterEqual(len([l for l in out.splitlines() if l.startswith("WARNING: [W32]")]), 2, out)
        # one {gate} decision handles every [W32] warning; [W49] stays open
        data["config"]["warning_decisions"] = [{"gate": "W32", "decision": "保留：测试"}]
        out = validate(data).stdout
        self.assertNotIn("WARNING: [W32]", out)
        self.assertGreaterEqual(out.count("WARNING (handled): [W32]"), 2, out)
        self.assertIn("WARNING: [W49]", out)
        # gate codes may be written "W49", "[W8b]" or "36"; the old match-substring form still works
        data["config"]["warning_decisions"] += [
            {"gate": "W49", "decision": "保留：测试"}, {"gate": "[W8b]", "decision": "保留：测试"},
            {"gate": "36", "decision": "保留：测试"},
            {"gate": "W59", "decision": "任务覆盖已复核"},
            {"match": "candidate Prompt count outside 30–60", "decision": "保留：测试"}]
        out = validate(data).stdout
        self.assertNotIn("WARNING: [W", out)
        self.assertNotIn("without a decision", out)

    def test_gate_39_is_a_manual_check_without_audience_terms(self) -> None:
        data = goal_bank(["发现型可见度"])
        for row in data["questions"]:
            row["audience"] = "多猫家庭"
        self.assertNotIn("[W39]", validate(data).stdout)
        self.assertNotIn("audience_terms", validate(data).stdout)
        data["config"]["audience_terms"] = {"多猫家庭": ["multiple cats", "multi-cat"]}
        self.assertIn("[W39] Prompts filed under a non-base audience", validate(data).stdout)


EXPORT = Path(__file__).with_name("export_upload_csv.py")


def tag_bank(dimensions: list[dict]) -> dict[str, object]:
    """Two Topics, 12 Discovery Prompts: 租房者 spans both Topics (6), 购房者 only topic_1, 外派家庭 only topic_2."""
    data = goal_bank(["发现型可见度"])
    data["config"]["topics"].append({"topic_id": "topic_2", "topic": "Second Topic"})
    rows = []
    for topic in ("topic_1", "topic_2"):
        for n in range(6):
            row = {**data["questions"][0], **question(topic, 10 + n)}
            row.pop("tags")
            row["audience"] = "租房者" if n < 3 else ("购房者" if topic == "topic_1" else "外派家庭")
            rows.append(row)
    data["questions"] = rows
    data["config"]["tag_dimensions"] = dimensions
    return file_on_audience_rows(data)


def file_on_audience_rows(data: dict[str, object]) -> dict[str, object]:
    """One Discovery row per Topic × audience: slice tags read the target customer from the Prompt's row."""
    rows: dict[tuple, dict] = {}
    for q in data["questions"]:
        key = (q["topic_id"], q["audience"])
        row = rows.setdefault(key, {"slice_id": f"M-{len(rows) + 1:03d}", "topic_id": q["topic_id"], "audience": q["audience"],
                                    "prompt_type": "Discovery", "priority": "高", "priority_basis": "测试造数"})
        q["slice_ref"] = row["slice_id"]
    data["config"]["slices"] = list(rows.values())
    return data


class SliceTagTests(unittest.TestCase):
    """W62/W63 and export (Suda 2026-11-03): slice tags cut across Topics and never duplicate the Topic."""

    def test_62_value_in_one_topic_duplicates_topic(self) -> None:
        out = validate(tag_bank([{"dimension": "目标客户", "basis": "内容团队按人群补页面"}])).stdout
        self.assertIn("目标客户「购房者」只落在 1 个主题（topic_1）", out)
        self.assertIn("目标客户「外派家庭」只落在 1 个主题（topic_2）", out)
        self.assertNotIn("目标客户「租房者」", out)

    def test_62_topic_axis_dimension(self) -> None:
        data = tag_bank([{"dimension": "目标客户", "basis": "测试"}])
        for row in data["questions"]:
            row["audience"] = "租房者" if row["topic_id"] == "topic_1" else "购房者"
        self.assertIn("这个维度就是主题的切分轴", validate(file_on_audience_rows(data)).stdout)

    def test_62_too_few_prompts_and_missing_basis(self) -> None:
        data = tag_bank([{"dimension": "目标客户"}])
        data["questions"][9]["audience"] = "购房者"  # 购房者: 3 in topic_1 + 1 in topic_2
        out = validate(file_on_audience_rows(data)).stdout
        self.assertIn("目标客户：没写 basis", out)
        self.assertIn("目标客户「购房者」只有 4 道题", out)

    def test_63_handwritten_tag_must_be_registered(self) -> None:
        data = tag_bank([])
        data["questions"][0]["tags"] = ["黑五"]
        self.assertIn("[W63]", validate(data).stdout)
        data["config"]["tag_dimensions"] = [{"dimension": "自定义", "basis": "黑五活动", "values": ["黑五"]}]
        out = validate(data).stdout
        self.assertNotIn("[W63]", out)
        self.assertIn("自定义「黑五」只落在 1 个主题", out)

    def test_export_writes_only_passing_values(self) -> None:
        data = tag_bank([{"dimension": "目标客户", "basis": "内容团队按人群补页面"}])
        data["questions"][0]["tags"] = ["随手写的"]
        with tempfile.TemporaryDirectory() as tmp:
            bank = Path(tmp) / "bank.json"
            bank.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            run = subprocess.run([sys.executable, "-I", str(EXPORT), str(bank), "--out", tmp],
                                 text=True, capture_output=True, check=False)
            self.assertIn("标签没出：目标客户「购房者」", run.stdout, run.stdout + run.stderr)
            rows = list(csv.DictReader((Path(tmp) / "bank.United States.upload.csv").open(encoding="utf-8-sig")))
        tags = {r["tags"] for r in rows}
        self.assertEqual(tags, {"租房者", ""}, tags)  # 发现和 diagnosis_intent 重复，不写进 tags

    def test_export_type_in_tags_only_for_alternatives(self) -> None:
        """Suda 2026-11-07: only 替代 (uploaded as competitor) carries its type name in tags."""
        data = tag_bank([])
        data["questions"][0]["prompt_type"] = "Alternatives"
        data["questions"][1]["prompt_type"] = "Competitor"
        with tempfile.TemporaryDirectory() as tmp:
            bank = Path(tmp) / "bank.json"
            bank.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, "-I", str(EXPORT), str(bank), "--out", tmp],
                           text=True, capture_output=True, check=False)
            rows = list(csv.DictReader((Path(tmp) / "bank.United States.upload.csv").open(encoding="utf-8-sig")))
        by = {r["query"]: (r["diagnosis_intent"], r["tags"]) for r in rows}
        self.assertEqual(by[data["questions"][0]["user_question"]], ("competitor", "替代"))
        self.assertEqual(by[data["questions"][1]["user_question"]], ("competitor", ""))
        self.assertEqual(by[data["questions"][2]["user_question"]], ("discovery", ""))


if __name__ == "__main__":
    unittest.main()
