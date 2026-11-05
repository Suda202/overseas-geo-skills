#!/usr/bin/env python3
"""Focused contract tests for the after-sales validator."""

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

    def test_topic_has_no_prompt_floor(self) -> None:  # Suda 2026-10-30
        result = validate(staged_bank(4, "locked"))
        self.assertNotIn("at least 5 Prompts per Topic", result.stdout)

    def test_after_sales_signal_cannot_be_formal_ready(self) -> None:
        data = staged_bank(5, "locked")
        data["config"]["evidence_status"] = "after_sales_signal"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be marked formal-ready", result.stdout)

    def test_generation_stage_no_longer_limits_types(self) -> None:
        # 2026-11-02 起 discovery / diagnostic 不再区分，新题库写 selection
        data = staged_bank(5, "hypothesis")
        data["questions"][0].update(prompt_type="Evaluation", journey_stage="评估",
                                    user_question="Is BrandX worth it for small apartments?")
        data["questions"][0]["monitoring_prompt"] = data["questions"][0]["user_question"]
        result = validate(data)
        self.assertNotIn("discovery stage must contain", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        data["config"]["generation_stage"] = "selection"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)

    def test_three_stage_journey_and_type_pairs(self) -> None:
        # 三段：需求认知只放问题解决；方案考虑放发现、替代；购买决策放对比、评价（Suda 2026-11-02）
        data = staged_bank(5, "hypothesis")
        data["config"]["generation_stage"] = "selection"
        for row in data["questions"]:
            row["journey_stage"] = "方案考虑"
            row.pop("group_role")
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        q = data["questions"][0]
        q.update(prompt_type="Competitor", user_question="BrandX vs RivalA for a small apartment?", constraints=["小户型"])
        q["monitoring_prompt"] = q["user_question"]
        self.assertNotIn("does not fit journey_stage", validate(data).stdout)
        q["journey_stage"] = "购买决策"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        # 发现题只在方案考虑：「在哪买、价格、库存」不进选词题库
        data["questions"][1]["journey_stage"] = "购买决策"
        self.assertNotIn("does not fit journey_stage", validate(data).stdout)
        data["questions"][1]["journey_stage"] = "方案考虑"
        # 问题解决只在需求认知
        r = data["questions"][2]
        r.update(prompt_type="Information", formal_visibility_eligible=False,
                 user_question="Why does my apartment still smell like cat litter?")
        r["monitoring_prompt"] = r["user_question"]
        self.assertNotIn("does not fit journey_stage", validate(data).stdout)
        r["journey_stage"] = "需求认知"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        # 验证题挂在触发它的发现题所在行，不查组合
        v = data["questions"][3]
        v.update(prompt_type="Verification", formal_visibility_eligible=False,
                 user_question="Does BrandX offer a self-cleaning mode?")
        v["monitoring_prompt"] = v["user_question"]
        self.assertNotIn("does not fit journey_stage", validate(data).stdout)
        # 购后支持不再是阶段：旧题库照认，只告警
        data["questions"][4]["journey_stage"] = "购后支持"
        data["questions"][4].update(prompt_type="Information", formal_visibility_eligible=False,
                                    user_question="Why did my BrandX pump stop working?")
        data["questions"][4]["monitoring_prompt"] = data["questions"][4]["user_question"]
        result = validate(data)
        self.assertIn("post-purchase questions are outside selection", result.stdout)

    def test_topic_discovery_can_follow_buyer_stage(self) -> None:
        # 门禁 41：发现题可以按买家处境放在购买决策行
        data = staged_bank(2, "hypothesis")
        data["config"]["generation_stage"] = "selection"
        data["config"]["slices"] = [
            {"slice_id": "M-001", "topic_id": "topic_1", "journey_stage": "购买决策", "priority": "高",
             "priority_basis": "品牌方要对比题"},
            {"slice_id": "M-002", "topic_id": "topic_1", "journey_stage": "方案考虑", "priority": "高",
             "priority_basis": "核心目标客户与购买场景（1）"},
        ]
        for row in data["questions"]:
            row.pop("journey_stage")
            row.pop("group_role")
            row["slice_ref"] = "M-001"
            row["priority"] = "高"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("no Discovery Prompt on a 方案考虑 row", result.stdout)
        data["questions"][0]["slice_ref"] = "M-002"
        self.assertNotIn("no Discovery Prompt on a 方案考虑 row", validate(data).stdout)

    def test_only_advantage_attributes_need_a_no_carrier_reason(self) -> None:
        # 门禁 31（Suda 2026-11-02）：矩阵题库里只有优势属性没题时要写原因
        data = staged_bank(2, "hypothesis")
        data["config"]["slices"] = [{"slice_id": "M-001", "topic_id": "topic_1", "priority": "高",
                                     "priority_basis": "核心目标客户与购买场景（1）", "attributes": ["除味"]}]
        data["config"]["attribute_plan"] = [
            {"attribute": "除味", "relative_competitor": "持平", "relative_competitor_basis": "三家都有"},
            {"attribute": "外观", "relative_competitor": "持平", "relative_competitor_basis": "差不多"},
        ]
        for row in data["questions"]:
            row.update(slice_ref="M-001", priority="高", attribute_ref="除味")
        self.assertNotIn("no_carrier_reason", validate(data).stdout)
        data["config"]["attribute_plan"][1]["relative_competitor"] = "优势"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no carrying Prompt and no no_carrier_reason", result.stdout)
        data["config"]["attribute_plan"][1]["no_carrier_reason"] = "所在行业务重要性为低"
        self.assertNotIn("no carrying Prompt and no no_carrier_reason", validate(data).stdout)

    def test_candidate_count_outside_30_to_60_warns(self) -> None:
        # 门禁 47：单产品线 × 单市场候选题 30–60 道，超出告警；锁版后不查
        data = staged_bank(5, "hypothesis")
        self.assertIn("candidate Prompt count outside 30–60", validate(data).stdout)
        data = staged_bank(30, "hypothesis")
        data["questions"] = [{**row, "user_question": f"Which cat litter box works best for setup number {i}?",
                              "monitoring_prompt": f"Which cat litter box works best for setup number {i}?"}
                             for i, row in enumerate(data["questions"])]
        self.assertNotIn("candidate Prompt count outside 30–60", validate(data).stdout)
        data = staged_bank(5, "locked")
        self.assertNotIn("candidate Prompt count outside 30–60", validate(data).stdout)

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

    def test_formal_set_caps_each_product_line_at_sixty(self) -> None:
        # 2026-11-05：单个主题不设上限；正式题每条产品线 × 国家 × 语言合计最多 60 道
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
        self.assertIn("Competitor Prompts belong to the monitoring or experimental layer", validate(data).stdout)
        q["group_role"] = "monitoring"
        self.assertNotIn("Prompts belong to the monitoring", validate(data).stdout)

    def test_audience_may_list_several_groups(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["audience"] = ["公民购房者", "PR 购房者"]
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["questions"][0]["audience"] = []
        self.assertIn("missing audience", validate(data).stdout)

    def test_bare_category_prompt_warns(self) -> None:
        # 2026-10-29 起不写宽泛品类题：全条件化不告警，无限定条件的发现题逐条告警
        data = staged_bank(2, "hypothesis")
        for row in data["questions"]:
            row["constraint_type"] = "约束"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("no-condition Discovery Prompts", result.stdout)
        data["questions"][0]["constraint_type"] = "无限定"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no-condition Discovery Prompts (1)", result.stdout)
        data["config"]["leader_default"] = {"reason": "领头平台占九成"}
        self.assertIn("leader_default is no longer read", validate(data).stdout)

    def test_topic_clustering_trace_gates(self) -> None:
        data = staged_bank(2, "hypothesis")
        result = validate(data)
        # source_slices / planned_prompts are no longer asked for (Suda 2026-11-01: 目标题数 retired)
        self.assertNotIn("missing source_slices/planned_prompts", result.stdout)
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
        self.assertNotIn("missing source_slices/planned_prompts", result.stdout)
        # P1 一律要安家；降级并写原因后放行（与「无题不许挂 P1」同一语义）
        data["config"]["attribute_plan"][1]["priority"] = "P2"
        data["config"]["attribute_plan"][1]["no_carrier_reason"] = "共识锁定，首期不开主题"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        data["config"]["topics"][0]["covered_attributes"].append("拼错的属性")
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("absent from attribute_plan", result.stdout)

    def test_matrix_rows_carry_the_priority(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["slices"] = [
            {"slice_id": "M-001", "topic_id": "topic_1", "priority": "高",
             "priority_basis": "品牌方点名：核心目标客户与购买场景（1）"},
            {"slice_id": "M-002", "topic_id": None, "priority": "低", "priority_basis": "品牌方未提，只有假设"},
        ]
        for row in data["questions"]:
            row["slice_ref"] = "M-001"
            row["priority"] = "高"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        # 可改变性低保留业务重要性
        data["questions"][0]["changeability"] = "低"
        data["questions"][0]["priority"] = "高"
        self.assertNotIn("differs from the expected", validate(data).stdout)
        # 手改档位没写原因：告警
        data["questions"][1]["priority"] = "低"
        self.assertIn("differs from the expected tier", validate(data).stdout)
        data["questions"][1]["priority_change_reason"] = "品牌方：本期不主推"
        self.assertNotIn("differs from the expected tier", validate(data).stdout)
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
        # 旧档位名 P1/P2/P3 仍认
        data["config"]["slices"][0]["priority"] = "P1"
        for row in data["questions"]:
            row["priority"] = "P1"
        data["questions"][0]["priority"] = "P2"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        # 中档行不再只限 1 道（Suda 2026-11-02）：题数按决策差异定
        data["config"]["slices"][0]["priority"] = "中"
        for row in data["questions"]:
            row["priority"] = "中"
        data["questions"][0]["priority"] = "低"
        self.assertNotIn("中 rows carrying more than one Prompt", validate(data).stdout)
        data["config"]["slices"][0]["priority"] = "高"
        for row in data["questions"]:
            row["priority"] = "高"
        data["questions"][0]["priority"] = "中"
        # 品类认知只在属性池前预跑，不进新结构题库（Suda 2026-10-29）
        data["questions"][4]["prompt_type"] = "Category Awareness"
        self.assertIn("Category Awareness Prompts in the bank", validate(data).stdout)

    def test_weak_attribute_can_carry_a_business_relevant_prompt(self) -> None:
        # 相对劣势允许作为业务需求进入题库
        data = staged_bank(2, "hypothesis")
        data["config"]["attribute_plan"] = [
            {"attribute": "除味", "relative_competitor": "持平", "relative_competitor_basis": "三家都有"},
            {"attribute": "噪音", "relative_competitor": "劣势", "relative_competitor_basis": "实测更吵"},
            {"attribute": "续航", "relative_competitor": "待确认"},
        ]
        data["config"]["slices"] = [{"slice_id": "M-001", "topic_id": "topic_1", "priority": "高",
                                     "priority_basis": "品牌方点名", "attributes": ["除味", "噪音"]},
                                    {"slice_id": "M-002", "topic_id": "topic_1", "priority": "中",
                                     "priority_basis": "有搜索需求", "attributes": ["续航"]}]
        for row in data["questions"]:
            row.update({"slice_ref": "M-001", "attribute_ref": "除味"})
        data["questions"][1]["user_question"] = "Which litter boxes keep odor down with three cats?"
        data["questions"][1].pop("monitoring_prompt", None)  # monitoring_prompt is optional since 2026-11-01
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        # 待确认不用写依据；中档行上的属性没题不算漏题
        self.assertNotIn("relative_competitor_basis is empty", result.stdout)
        self.assertNotIn("no carrying Prompt", result.stdout)
        data["questions"][1]["attribute_ref"] = "噪音"
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("tests 劣势 attribute", result.stdout)

    def test_topic_needs_prompts_and_a_discovery_prompt(self) -> None:
        data = staged_bank(2, "hypothesis")
        data["config"]["generation_stage"] = "diagnostic"
        data["config"]["topics"].append({"topic_id": "topic_2", "topic": "Brand check"})
        result = validate(data)
        self.assertIn("Topics with no Prompt", result.stdout)
        row = data["questions"][1]
        row.update({"topic_id": "topic_2", "prompt_type": "Evaluation", "journey_stage": "评估",
                    "group_role": "monitoring", "formal_visibility_eligible": False,
                    "user_question": "Is Brand good for odor control with three cats?"})
        row["monitoring_prompt"] = row["user_question"]
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Topics with no Discovery Prompt", result.stdout)
        self.assertIn("topic_2", result.stdout)

    def test_topic_priority_has_a_basis(self) -> None:
        data = staged_bank(2, "hypothesis")
        data["config"]["slices"] = [{"slice_id": "M-001", "topic_id": "topic_1", "priority": "高",
                                     "priority_basis": "品牌方点名"}]
        for row in data["questions"]:
            row["slice_ref"] = "M-001"
        topic = data["config"]["topics"][0]
        topic["priority"] = "高"
        self.assertIn("priority_basis is empty", validate(data).stdout)
        topic["priority_basis"] = "核心目标客户与购买场景（1）落在本主题"
        self.assertEqual(validate(data).returncode, 0, validate(data).stdout)
        topic["priority"] = "中"
        self.assertIn("most of its rows are 高", validate(data).stdout)
        topic["priority"] = "急"
        self.assertEqual(validate(data).returncode, 1)

    def test_warning_decisions_and_capped_readiness(self) -> None:
        data = staged_bank(2, "hypothesis")
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
        # 替代题计入提及率考核（Suda 2026-11-02）：可以算可见度，也可以进核心层
        row["formal_visibility_eligible"] = True
        self.assertNotIn("must set formal_visibility_eligible: false", validate(data).stdout)
        row["group_role"] = "core"
        self.assertNotIn("monitoring or experimental layer", validate(data).stdout)
        row["group_role"] = "monitoring"
        # 旅程与题型分别记录
        row["journey_stage"] = "对比"
        self.assertNotIn("does not fit journey_stage", validate(data).stdout)
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

    def test_common_constraint_backs_a_condition(self) -> None:
        # 题不逐条挂原话：条件取自属性池「常见约束」即算有依据（Suda 2026-11-01）
        data = scoped_bank([("Which dash cams under $300 record at night?", "Night vision", ["300美元以内"], [])])
        result = validate(data)
        self.assertIn("condition outside the cited evidence", result.stdout)
        data["config"]["attribute_plan"] = [{"attribute": "Night vision", "relative_competitor": "待确认",
                                             "common_constraints": ["300美元以内", "夜间"]}]
        result = validate(data)
        self.assertNotIn("condition outside the cited evidence", result.stdout)
        # 题库不带需求信号表时，有常见约束照样能查
        data["config"].pop("buyer_quotes")
        result = validate(data)
        self.assertNotIn("nor config.buyer_quotes", result.stdout)
        self.assertNotIn("condition outside the cited evidence", result.stdout)

    def test_bank_without_quote_table_skips_with_warning(self) -> None:  # F7
        data = scoped_bank([("Which dash cams support a 512GB card?", "Storage", [], ["Q01"])])
        data["config"].pop("buyer_quotes")
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("nor config.buyer_quotes", result.stdout)

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
    """A selection bank: five 方案考虑 Discovery Prompts, plus business_goals when selected is not None."""
    data = staged_bank(5, "hypothesis")
    data["config"]["generation_stage"] = "selection"
    data["config"].pop("expected_total")
    for row in data["questions"]:
        row["journey_stage"] = "方案考虑"
        row.pop("group_role")
        row.pop("tags")  # selection banks derive tags from config.tag_dimensions (W63)
    if selected is not None:
        data["config"]["business_goals"] = {"selected": selected, "information_named": information_named}
    return data


def add_typed(data: dict[str, object], prompt_type: str) -> None:
    text, stage = {
        "Competitor": ("BrandX vs RivalA for a small apartment with two cats?", "购买决策"),
        "Evaluation": ("Is BrandX worth it for a small apartment with two cats?", "购买决策"),
        "Information": ("Why does my apartment still smell like cat litter after scooping?", "需求认知"),
    }[prompt_type]
    row = {**question("topic_1", 90 + len(data["questions"])), "prompt_type": prompt_type, "user_question": text,
           "monitoring_prompt": text, "journey_stage": stage, "audience": "通用", "attribute_ref": "",
           "constraints": ["小户型"]}
    if prompt_type == "Information":
        row["formal_visibility_eligible"] = False
    data["questions"].append(row)


class BusinessGoalGateTests(unittest.TestCase):
    """Gates 49–52 (Suda 2026-11-02 审核清单 B2): business_goals decides which Prompt types are written."""

    def test_49_missing_business_goals(self) -> None:
        self.assertIn("config.business_goals missing or malformed", validate(goal_bank(None)).stdout)
        self.assertNotIn("config.business_goals missing", validate(goal_bank(["发现型可见度"])).stdout)
        # 旧题库（没有 generation_stage）和售前题库（带 extra_prompt_types）不查
        legacy = goal_bank(None)
        legacy["config"].pop("generation_stage")
        self.assertNotIn("business_goals", validate(legacy).stdout)
        presales = goal_bank(None)
        presales["config"]["extra_prompt_types"] = []
        self.assertNotIn("business_goals", validate(presales).stdout)
        # 写了但取值不在四个目标里，同样告警
        self.assertIn("config.business_goals missing or malformed", validate(goal_bank(["品牌曝光"])).stdout)

    def test_50_competitive_positioning_without_competitor_prompt(self) -> None:
        data = goal_bank(["发现型可见度", "竞争定位"])
        self.assertIn("selects 竞争定位 but the bank holds no Competitor Prompt", validate(data).stdout)
        add_typed(data, "Competitor")
        self.assertNotIn("selects 竞争定位", validate(data).stdout)

    def test_51_reputation_without_evaluation_prompt(self) -> None:
        data = goal_bank(["声誉与信任"])
        self.assertIn("selects 声誉与信任 but the bank holds no Evaluation Prompt", validate(data).stdout)
        add_typed(data, "Evaluation")
        self.assertNotIn("selects 声誉与信任", validate(data).stdout)

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
                data["questions"][0].update(prompt_type="Alternatives",
                                            user_question="What are the best alternatives to RivalA for two cats?")
                data["questions"][0]["monitoring_prompt"] = data["questions"][0]["user_question"]
                check = self.assertIn if warned else self.assertNotIn
                check("Alternatives Prompts written without the goal 竞争定位", validate(data).stdout)


class WarningCodeTests(unittest.TestCase):
    """D5 / D3 (Suda 2026-11-02 审核清单): stable warning codes, whole-class decisions, gate 39 without terms."""

    @staticmethod
    def short_bank() -> dict[str, object]:
        data = goal_bank(None)
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
    return data


class SliceTagTests(unittest.TestCase):
    """W62/W63 and export (Suda 2026-11-03): slice tags cut across Topics and never duplicate the Topic."""

    def test_62_value_in_one_topic_duplicates_topic(self) -> None:
        out = validate(tag_bank([{"dimension": "受众", "basis": "内容团队按人群补页面"}])).stdout
        self.assertIn("受众「购房者」只落在 1 个主题（topic_1）", out)
        self.assertIn("受众「外派家庭」只落在 1 个主题（topic_2）", out)
        self.assertNotIn("受众「租房者」", out)

    def test_62_topic_axis_dimension(self) -> None:
        data = tag_bank([{"dimension": "受众", "basis": "测试"}])
        for row in data["questions"]:
            row["audience"] = "租房者" if row["topic_id"] == "topic_1" else "购房者"
        self.assertIn("这个维度就是主题的切分轴", validate(data).stdout)

    def test_62_too_few_prompts_and_missing_basis(self) -> None:
        data = tag_bank([{"dimension": "受众"}])
        data["questions"][9]["audience"] = "购房者"  # 购房者: 3 in topic_1 + 1 in topic_2
        out = validate(data).stdout
        self.assertIn("受众：没写 basis", out)
        self.assertIn("受众「购房者」只有 4 道题", out)

    def test_63_handwritten_tag_must_be_registered(self) -> None:
        data = tag_bank([])
        data["questions"][0]["tags"] = ["黑五"]
        self.assertIn("[W63]", validate(data).stdout)
        data["config"]["tag_dimensions"] = [{"dimension": "自定义", "basis": "黑五活动", "values": ["黑五"]}]
        out = validate(data).stdout
        self.assertNotIn("[W63]", out)
        self.assertIn("自定义「黑五」只落在 1 个主题", out)

    def test_export_writes_only_passing_values(self) -> None:
        data = tag_bank([{"dimension": "受众", "basis": "内容团队按人群补页面"}])
        data["questions"][0]["tags"] = ["随手写的"]
        with tempfile.TemporaryDirectory() as tmp:
            bank = Path(tmp) / "bank.json"
            bank.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            run = subprocess.run([sys.executable, "-I", str(EXPORT), str(bank), "--out", tmp],
                                 text=True, capture_output=True, check=False)
            self.assertIn("标签没出：受众「购房者」", run.stdout, run.stdout + run.stderr)
            rows = list(csv.DictReader((Path(tmp) / "bank.United States.upload.csv").open(encoding="utf-8-sig")))
        tags = {r["tags"] for r in rows}
        self.assertEqual(tags, {"发现,租房者", "发现"}, tags)


if __name__ == "__main__":
    unittest.main()
