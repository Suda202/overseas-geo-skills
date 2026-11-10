#!/usr/bin/env python3
"""End-to-end checks for the selection handoff and baseline configuration (current bank structure only)."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate_after_sales_set.py"


def bank(market: str = "United States", version: str = "us-v1") -> dict:
    questions = []
    query_templates = [
        "Which business travel providers should companies consider for scenario {number}?",
        "Which business travel providers should a company shortlist for scenario {number}?",
        "Which business travel management companies can help a company manage scenario {number}?",
        "Which business travel providers can a company use instead of booking travel in-house for scenario {number}?",
        "Which business travel providers should companies consider for scenario {number}?",
    ]
    for number in range(5):
        query = query_templates[number].format(number=number)
        questions.append(
            {
                "question_id": f"q{number}",
                "topic_id": "travel",
                "intent_key": f"travel-buyer-need-{number}",
                "user_question": query,
                "zh_translation": f"商务差旅服务商选择问题 {number}",
                "region": market,
                "prompt_type": "Discovery",
                "slice_ref": "M-000",
                "attribute_ref": "",
                "evidence_refs": [f"input-{number}"],
            }
        )
    return {
        "schema_version": "overseas-geo-question-bank/v8",
        "mode": "after-sales-strategic-topics",
        "config": {
            "brand_name": "Example",
            "topics": [{"topic_id": "travel", "topic": "Business Travel"}],
            "generation_stage": "selection",
            "business_goals": {"selected": ["发现型可见度"], "information_named": False},
            "slices": [{"slice_id": "M-000", "topic_id": "travel", "product_line": "差旅管理", "audience": "通用",
                        "prompt_type": "Discovery", "priority": "高", "priority_basis": "核心目标客户与使用场景（1）"}],
            # five Prompts that differ only by scenario number: W59 is expected and handled
            "warning_decisions": [{"gate": "W59", "decision": "测试造数：只验证生命周期与版本门禁"}],
            "lifecycle_status": "locked",
            "evidence_status": "customer_confirmed",
            "customer_confirmation": {
                "status": "locked",
                "scope_status": "confirmed",
                "prompt_set_status": "confirmed",
            },
            "prompt_version": version,
            "trial": {
                "status": "passed",
                "planned_runs": 3,
                "valid_runs": 3,
                "evidence_refs": ["trial-results.json"],
            },
            "baseline": {
                "status": "formal",
                "planned_runs": 7,
                "conditions_key": f"{market}-en-chatgpt",
                "valid_samples_only": True,
                "prompt_version": version,
            },
            "collection_config": {
                "market": market,
                "language": "en",
                "platforms": ["ChatGPT"],
            },
        },
        "questions": questions,
    }


def selection_bank() -> dict:
    """A locked bank with the full matrix: one row per Prompt type, business priority per row, Topic priority, one Prompt
    type per Topic, a 约束条件 list, Prompts on rows."""
    b = bank()
    config = b["config"]
    config.update(
        first_party_data=True,
        business_goals={"selected": ["发现型可见度", "竞争定位"], "information_named": False},
        topics=[{"topic_id": "travel", "topic": "中小企业差旅服务商选择", "priority": "高",
                 "priority_basis": "高：核心可见度问题（1）落在本主题"},
                {"topic_id": "travel_alt", "topic": "差旅平台替代", "priority": "高", "priority_basis": "高：组内 1 行，高"},
                {"topic_id": "travel_cmp", "topic": "差旅平台对比", "priority": "中", "priority_basis": "中：组内 1 行，中"}],
        slices=[
            {"slice_id": "M-001", "topic_id": "travel", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "控制差旅预算", "prompt_type": "Discovery", "attributes": ["预算控制", "账单合并", "全球覆盖"],
             "priority": "高", "priority_basis": "核心可见度问题（1）"},
            {"slice_id": "M-002", "topic_id": "travel_cmp", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "控制差旅预算", "prompt_type": "Competitor", "attributes": ["预算控制"],
             "priority": "中", "priority_basis": "买家常拿 Navan 来比（销售记录）"},
            {"slice_id": "M-009", "topic_id": "travel", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "合并差旅账单", "prompt_type": "Competitor", "attributes": ["账单合并"],
             "priority": "高", "priority_basis": "高：品牌方列出账单合并是本期主推。开行依据：销售记录里常拿 Navan 比账单"},
            {"slice_id": "M-003", "topic_id": None, "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "临时出差", "prompt_type": "Competitor", "attributes": ["账单合并"],
             "priority": "低", "priority_basis": "低：临时出差不是本期重点。开行依据：假设：临时出差会拿 Navan 比"},
            {"slice_id": "M-010", "topic_id": "travel_alt", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "控制差旅预算", "prompt_type": "Alternatives", "attributes": ["预算控制"], "priority": "高",
             "priority_basis": "高：跟同任务的发现行。开行依据：社区里有想换掉 SAP Concur 的帖子"},
        ],
        attribute_plan=[{"attribute": "预算控制"}, {"attribute": "账单合并"}, {"attribute": "全球覆盖"}],
        competitor_selection={"comparison_set": ["Navan", "SAP Concur"]},
        base_conditions=["企业差旅"],
        audience_terms={"中小企业财务": ["small business", "SME", "50-person"]},
        buyer_quotes=[
            {"输入编号": "S1", "原话": "we need travel to stay inside a fixed monthly budget", "约束": "每月预算"},
            {"输入编号": "S2", "原话": "we are a 50-person company", "约束": "50 人团队"},
            {"输入编号": "S3", "原话": "one invoice at the end of the month please", "约束": "月结"},
        ],
        # the Alternatives and Competitor Topics hold one Prompt each by construction
        warning_decisions=[{"match": "W59", "decision": "测试造数：类型主题各 1 道，只验证结构"}],
    )
    rows = [
        ("q0", "Discovery", "travel", "M-001", "预算控制", ["每月预算"],
         "Which business travel providers help a small business keep travel under a fixed monthly budget?"),
        ("q1", "Discovery", "travel", "M-001", "预算控制", ["50 人团队"],
         "Which business travel management companies suit a 50-person company that caps spending per department?"),
        ("q2", "Discovery", "travel", "M-001", "账单合并", ["月结"],
         "Which travel management providers give a small business one consolidated monthly invoice?"),
        ("q3", "Alternatives", "travel_alt", "M-010", "预算控制", [],
         "What are the best alternatives to SAP Concur for small business travel?"),
        ("q6", "Discovery", "travel", "M-001", "预算控制", ["每月预算", "50 人团队"],
         "Which corporate travel platforms help a 50-person company stay inside one monthly budget?"),
        ("q5", "Discovery", "travel", "M-001", "账单合并", [],
         "Which corporate travel platforms handle billing in one place for a small business?"),
        ("q4", "Competitor", "travel_cmp", "M-002", "预算控制", ["50 人团队"],
         "For a 50-person company watching its travel budget, is Example or Navan the better choice?"),
    ]
    b["questions"] = [
        {"question_id": qid, "topic_id": topic, "user_question": text, "zh_translation": f"差旅题 {qid}",
         "region": "United States", "prompt_type": prompt_type, "slice_ref": row, "attribute_ref": attribute,
         "constraints": constraints, "status": "正式",
         "evidence_refs": [{"每月预算": "S1", "50 人团队": "S2", "月结": "S3"}[c] for c in constraints]}
        for qid, prompt_type, topic, row, attribute, constraints, text in rows
    ]
    return b


def validate(data: dict, previous: dict | None = None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        current_path = Path(directory) / "current.json"
        current_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        command = [sys.executable, str(VALIDATOR), str(current_path)]
        if previous is not None:
            previous_path = Path(directory) / "previous.json"
            previous_path.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
            command += ["--previous", str(previous_path)]
        return subprocess.run(command, capture_output=True, text=True, check=False)


def run_checks() -> list[dict]:
    original = bank()
    cases: list[tuple[str, dict, dict | None, bool]] = [
        ("locked_bank", original, None, True),
    ]

    def changed(name: str, edit, expected: bool, previous: dict | None = None) -> None:
        candidate = copy.deepcopy(original)
        edit(candidate)
        cases.append((name, candidate, previous, expected))

    changed("two_trial_runs", lambda b: b["config"]["trial"].update(planned_runs=2), False)
    changed("seven_trial_runs", lambda b: b["config"]["trial"].update(planned_runs=7, valid_runs=7), False)
    changed("legacy_thirty_run_baseline", lambda b: b["config"]["baseline"].update(planned_runs=30), True)
    changed("eight_run_baseline", lambda b: b["config"]["baseline"].update(planned_runs=8), False)
    changed("two_run_baseline", lambda b: b["config"]["baseline"].update(planned_runs=2), False)

    changed(
        "missing_scope_confirmation",
        lambda b: b["config"]["customer_confirmation"].pop("scope_status"),
        False,
    )
    def trial_without_scope(b: dict) -> None:
        b["config"]["lifecycle_status"] = "hypothesis"
        b["config"]["customer_confirmation"]["scope_status"] = "pending"
        b["config"]["baseline"]["status"] = "planned"

    changed("trial_completed_without_scope", trial_without_scope, False)
    changed(
        "missing_final_set_confirmation",
        lambda b: b["config"]["customer_confirmation"].pop("prompt_set_status"),
        False,
    )
    changed(
        "stale_baseline_version",
        lambda b: b["config"]["baseline"].update(prompt_version="us-v0"),
        False,
    )
    changed("wrong_market", lambda b: b["questions"][0].update(region="Singapore"), False)

    def edit_query(b: dict) -> None:
        b["questions"][0]["user_question"] = "Which travel providers fit a fixed monthly budget?"

    changed("edited_query_same_version", edit_query, False, original)

    def add_query(b: dict) -> None:
        added = copy.deepcopy(b["questions"][0])
        added.update(
            question_id="q5",
            intent_key="travel-buyer-need-5",
            user_question="Which business travel providers support consolidated billing?",
        )
        b["questions"].append(added)

    changed("added_query_same_version", add_query, False, original)
    previous_six = copy.deepcopy(original)
    add_query(previous_six)
    changed("deleted_query_same_version", lambda b: None, False, previous_six)

    def rebaseline(b: dict) -> None:
        edit_query(b)
        b["config"]["prompt_version"] = "us-v2"
        b["config"]["baseline"]["prompt_version"] = "us-v2"

    changed("edited_query_new_version", rebaseline, True, original)
    singapore = bank("Singapore", "sg-v1")
    singapore["questions"][0]["user_question"] = (
        "Which business travel providers fit a monthly budget in SGD?"
    )
    singapore["questions"][0]["intent_key"] = "sg-business-travel-monthly-budget"
    cases.append(("market_specific_singapore_intent", singapore, None, True))
    cases.append(("cross_market_previous_bank", singapore, original, False))
    france = bank("France", "fr-v1")
    france["config"]["collection_config"]["language"] = "fr"
    for number, row in enumerate(france["questions"]):
        row["user_question"] = (
            f"Quels prestataires de voyages d'affaires conviennent au scénario {number} ?"
        )
    france["questions"][0]["intent_key"] = "fr-business-travel-local-choice"
    cases.append(("localized_french_with_distinct_intent", france, None, True))

    def set_query(b: dict, index: int, text: str) -> None:
        b["questions"][index]["user_question"] = text

    def competitor_in_discovery(b: dict) -> None:
        b["config"]["competitor_selection"] = {
            "status": "answer_layer_derived",
            "comparison_set": ["Navan", "SAP Concur"],
        }
        set_query(b, 1, "Which business travel tools are easier to roll out than SAP concur?")

    changed("competitor_named_in_discovery", competitor_in_discovery, False)
    changed(
        "target_brand_named_in_discovery",
        lambda b: set_query(b, 2, "Is Example or a local agency better for scenario 2 travel?"),
        False,
    )

    def thai_bank(b: dict) -> None:
        b["config"]["collection_config"]["language"] = "Thai"
        for number, row in enumerate(b["questions"]):
            set_query(b, number, f"บริษัทควรเลือกผู้ให้บริการจัดการการเดินทางเพื่อธุรกิจรายไหนสำหรับกรณีที่ {number}")
        set_query(b, 0, "บริษัทที่ต้องการรายงานค่าใช้จ่ายแบบ SAP หรือ Excel ควรเลือกผู้ให้บริการด้านการเดินทางรายไหน")

    changed("thai_bank_with_latin_acronyms", thai_bank, True)

    def english_in_thai_bank(b: dict) -> None:
        thai_bank(b)
        set_query(b, 3, "Which business travel providers should Thai companies consider?")

    changed("english_query_in_thai_bank", english_in_thai_bank, False)

    def wording_warnings(b: dict) -> None:
        set_query(b, 1, "business travel provider")
        set_query(b, 2, "Which business travel providers cost under £50 a trip? Which ones also book rail?")

    changed("wording_heuristics_warn_without_failing", wording_warnings, True)
    # A Prompt written wholly in another language is an error since lingua (2026-11-09), not a W32 warning.
    changed("spanish_query_in_english_bank",
            lambda b: set_query(b, 3, "¿Cuál es el top de proveedores de viajes de negocios para una empresa pequeña?"),
            False)

    def attribute_plan(b: dict, statuses: list[str | None], via_tag: bool = False) -> None:
        b["config"]["attribute_plan"] = [{"attribute": "预算控制"}, {"attribute": "账单合并"}]
        carrier = b["questions"][0]
        if via_tag:
            carrier["tags"] = [*carrier.get("tags", []), "预算控制"]
        else:
            carrier["attribute_ref"] = "预算控制"
        b["questions"][1]["attribute_ref"] = "账单合并"
        for row, status in zip(b["questions"], statuses):
            if status is not None:
                row["status"] = status

    def as_hypothesis(b: dict) -> None:
        b["config"]["lifecycle_status"] = "hypothesis"
        b["config"]["evidence_status"] = "hypothesis"
        b["config"]["baseline"]["status"] = "planned"

    approved = ["已批准"] * 5
    changed("attribute_plan_without_status_counts_any_prompt",
            lambda b: attribute_plan(b, [None] * 5), True)
    changed("review_all_approved_on_locked_set", lambda b: attribute_plan(b, approved), True)
    changed("review_unapproved_carrier_on_locked_set",
            lambda b: attribute_plan(b, ["待审核", *approved[1:]]), False)
    changed("review_needs_revision_carrier_via_tag_on_locked_set",
            lambda b: attribute_plan(b, ["需修改", *approved[1:]], via_tag=True), False)

    def drafting(b: dict) -> None:
        attribute_plan(b, ["待审核"] * 4 + [None])
        as_hypothesis(b)

    changed("review_pending_while_drafting_warns", drafting, True)
    def single_evidence_family(b: dict) -> None:
        for row in b["questions"]:
            row["evidence_refs"] = ["AI 答案层 distributor margin 22/70"]

    changed("evidence_single_family_warns", single_evidence_family, True)

    def three_evidence_families(b: dict) -> None:
        families = [
            "Reddit r/business 求推荐帖",
            "G2 评价高频条件",
            "GSC 搜索词 travel management",
            "销售通话流失原因",
            "AI 答案层当前差距",
        ]
        for row, ref in zip(b["questions"], families):
            row["evidence_refs"] = [ref]

    changed("evidence_three_families_no_warning", three_evidence_families, True)

    # Gate 36: a condition is backed by the 约束 column of a cited quote, not by the quote text.
    def quote_table(b: dict, budget_cell: str) -> None:
        # The synthetic queries say "scenario {n}"; each quote carries its own number so
        # only q1's budget is under test.
        b["config"]["buyer_quotes"] = [
            {"输入编号": f"input-{n}", "原话": f"we need a travel provider for scenario {n}",
             "约束": budget_cell if n == 1 else ""} for n in range(5)
        ]
        row = b["questions"][1]
        row["user_question"] = "Which business travel providers suit a team spending under $500 per trip?"
        row["constraints"] = ["500 美元以内"]

    changed("constraint_column_backs_condition", lambda b: quote_table(b, "500 美元以内"), True)
    # Warning since 2026-10-30: an unbacked condition no longer blocks the set.
    # Since 2026-11-04 quotes carry no 约束 cell: a cited quote backs the declared condition, but a number in
    # the query must still appear in the quote text or a written basis.
    changed("condition_outside_constraint_column", lambda b: quote_table(b, ""), True)

    def uncited_condition(b: dict) -> None:
        quote_table(b, "")
        b["questions"][1]["evidence_refs"] = []

    changed("condition_without_cited_signal", uncited_condition, True)
    changed("unused_audience_inputs_warn",
            lambda b: b["config"].update(audience_inputs=[f"input-{n}" for n in range(7)]), True)

    # Gate 8 exemption: a pair differing only by the category's registered naming variants.
    def category_alias_pair(b: dict) -> None:
        set_query(b, 1, "Which travel management companies suit a 50-person exporter with frequent regional bookings for scenario 9?")
        set_query(b, 2, "Which TMCs suit a 50-person exporter with frequent regional bookings for scenario 9?")
        b["config"]["category_aliases"] = ["travel management companies", "TMCs"]

    def category_pair_without_aliases(b: dict) -> None:
        category_alias_pair(b)
        b["config"].pop("category_aliases")

    changed("category_alias_pair_not_near_duplicate", category_alias_pair, True)
    changed("category_pair_without_aliases_warns", category_pair_without_aliases, True)

    # Gate 39: a Prompt filed under a non-base audience names that audience.
    def audience_prompt(b: dict, query: str, audience, terms: dict | None) -> None:
        row = b["questions"][1]
        row.update(user_question=query, audience=audience)
        if terms is not None:
            b["config"]["audience_terms"] = terms
    sme_query = "Which business travel providers suit a small-business finance team for scenario 1?"
    plain_query = "Which business travel management providers fit a growing company for scenario 1?"
    sme_terms = {"中小企业财务": ["small business", "SME"]}
    changed("audience_named_in_wording",
            lambda b: audience_prompt(b, sme_query, ["中小企业财务"], sme_terms), True)
    changed("audience_one_of_several_named",
            lambda b: audience_prompt(b, sme_query, ["差旅经理", "中小企业财务"],
                                      {**sme_terms, "差旅经理": ["travel manager"]}), True)
    changed("audience_not_named_warns",
            lambda b: audience_prompt(b, plain_query, "中小企业财务", sme_terms), True)

    def audience_implicit(b: dict) -> None:
        audience_prompt(b, plain_query, "中小企业财务", sme_terms)
        b["questions"][1]["audience_implicit"] = "growing company implies an SME buyer"
    changed("audience_implicit_exempt", audience_implicit, True)
    # D3 (Suda 2026-11-02): with no config.audience_terms, gate 39 is a manual check, not a warning.
    changed("audience_terms_missing_is_manual_check",
            lambda b: audience_prompt(b, plain_query, "中小企业财务", None), True)
    changed("audience_without_terms_entry_warns",
            lambda b: audience_prompt(b, plain_query, "中小企业财务", {"差旅经理": ["travel manager"]}), True)

    def base_audience(b: dict) -> None:
        audience_prompt(b, plain_query, "企业差旅", None)
        b["config"]["base_conditions"] = ["企业差旅"]
    changed("base_audience_not_checked", base_audience, True)

    # The full matrix: one row per type, business priority, Topic priority.
    selection = selection_bank()
    cases.append(("selection_locked_bank", selection, None, True))

    def selection_case(name: str, edit, expected: bool) -> None:
        candidate = copy.deepcopy(selection)
        edit(candidate)
        cases.append((name, candidate, None, expected))

    selection_case("selection_row_without_priority",
                   lambda b: b["config"]["slices"][0].update(priority=""), False)
    # 3.0.0: non-Discovery rows are registered without a tier this period
    selection_case("selection_non_discovery_row_without_priority_passes",
                   lambda b: b["config"]["slices"][3].update(priority="", priority_basis=""), True)
    selection_case("selection_prompt_on_weak_attribute",
                   lambda b: b["questions"][2].update(attribute_ref="全球覆盖"), True)
    selection_case("selection_topic_priority_mismatch_warns",
                   lambda b: b["config"]["topics"][0].update(priority="中", priority_basis="中：父关键词月搜索 4.4 万"),
                   True)
    # Gates 49 / 52 (Suda 2026-11-02 审核清单 B2): goals malformed, or a Competitor Prompt with 竞争定位 not picked.
    # 3.0.0: missing business_goals is read as {selected: ["发现型可见度"], information_named: false}.
    selection_case("selection_without_business_goals_defaults",
                   lambda b: b["config"].pop("business_goals"), True)
    selection_case("selection_malformed_business_goals_warns",
                   lambda b: b["config"].update(business_goals={"selected": ["品牌曝光"]}), True)
    selection_case("selection_competitor_without_goal_warns",
                   lambda b: b["config"]["business_goals"].update(selected=["发现型可见度"]), True)

    # W59 size floor (10 Prompts since 2026-11-09; the 8-decision threshold dropped in 3.0.0): with its decision
    # removed and one Prompt dropped, the 5-Prompt Topic reports 4 KPI Prompts.
    def selection_thin_topic(b: dict) -> None:
        b["questions"] = [q for q in b["questions"] if q["question_id"] != "q5"]
        b["config"].pop("warning_decisions")
    selection_case("selection_topic_below_size_floor_warns", selection_thin_topic, True)

    def selection_thin_topic_waived(b: dict) -> None:
        selection_thin_topic(b)
        b["config"]["warning_decisions"] = [{"match": "W59", "decision": "品牌方点名单买本主题，已告知读数波动风险（2026-11-03）"}]
    selection_case("selection_topic_below_size_floor_waived", selection_thin_topic_waived, True)

    def selection_verification(b: dict) -> None:
        b["questions"][4].update(prompt_type="Verification")
    selection_case("verification_rejected_from_selection_bank", selection_verification, False)
    # 3.0.0: changeability is judged on the monitoring side; selection no longer reads the field
    selection_case("changeability_field_not_read_by_selection",
                   lambda b: b["questions"][0].update(changeability="待试跑"), True)

    typed = selection

    def typed_case(name: str, edit, expected: bool) -> None:
        candidate = copy.deepcopy(typed)
        edit(candidate)
        cases.append((name, candidate, None, expected))

    def typed_slice(b: dict, sid: str) -> dict:
        return next(r for r in b["config"]["slices"] if r["slice_id"] == sid)

    typed_case("typed_prompt_on_wrong_type_row",
               lambda b: next(q for q in b["questions"] if q["question_id"] == "q4").update(slice_ref="M-001", priority="高"),
               False)

    # Gate 66: putting the Competitor row and Prompt back into the Discovery Topic mixes types.
    def typed_mixed_topic(b: dict) -> None:
        typed_slice(b, "M-002")["topic_id"] = "travel"
        next(q for q in b["questions"] if q["question_id"] == "q4")["topic_id"] = "travel"
        b["config"]["topics"] = [t for t in b["config"]["topics"] if t["topic_id"] != "travel_cmp"]
    typed_case("typed_mixed_type_topic_fails", typed_mixed_topic, False)
    typed_case("typed_row_invalid_type",
               lambda b: typed_slice(b, "M-009").update(prompt_type="Verification"), False)
    typed_case("typed_row_with_prompt_types_list_is_old_structure",
               lambda b: typed_slice(b, "M-001").update(prompt_types=[{"type": "Discovery"}, {"type": "Competitor"}]),
               False)

    def typed_bare_discovery(b: dict) -> None:
        b["config"]["slices"].append(
            {"slice_id": "M-004", "topic_id": "travel", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "临时出差", "prompt_type": "Discovery", "attributes": ["账单合并"],
             "priority": "高", "priority_basis": "营销活动（1）"})
    typed_case("typed_discovery_row_without_prompt_warns", typed_bare_discovery, True)

    def typed_bare_non_discovery(b: dict) -> None:
        b["config"]["slices"].append(
            {"slice_id": "M-005", "product_line": "差旅管理", "audience": "中小企业财务",
             "scene": "合并差旅账单", "prompt_type": "Evaluation",
             "attributes": ["账单合并"], "priority": "高", "priority_basis": "高：跟同任务的发现行。开行依据：社区问口碑"})
    typed_case("typed_non_discovery_row_stays_quiet", typed_bare_non_discovery, True)

    # Eight prompt types (2026-11-06).
    # 验证 / 交易 / 售后 rows (Trust / Transactional / Support) register without Prompts and stay quiet.
    def typed_eight_types_no_stage(b: dict) -> None:
        for i, (ptype, scene) in enumerate((("Trust", "核实差旅平台靠不靠谱"), ("Transactional", "开通差旅平台"),
                                            ("Support", "处理差旅平台报销故障")), start=6):
            b["config"]["slices"].append(
                {"slice_id": f"M-0{i:02d}", "product_line": "差旅管理", "audience": "中小企业财务", "scene": scene,
                 "prompt_type": ptype, "attributes": ["账单合并"], "priority": "中",
                 "priority_basis": "中：跟同任务的发现行。开行依据：假设：销售常被问到"})
    typed_case("typed_eight_types_without_journey_stage", typed_eight_types_no_stage, True)
    typed_case("typed_row_accuracy_type_rejected",
               lambda b: typed_slice(b, "M-009").update(prompt_type="Accuracy"), False)

    expected_errors = {
        "spanish_query_in_english_bank": "q3: query reads as 'es', not the collection language 'en'",
        "verification_rejected_from_selection_bank": "Verification is retired (2026-11-06)",

        "two_trial_runs": "READINESS: Not ready: 2 errors to fix",
        "seven_trial_runs": "trial.planned_runs must be 3",
        "eight_run_baseline": "baseline.planned_runs must be 7",
        "two_run_baseline": "baseline.planned_runs must be 7",
        "missing_scope_confirmation": "scope_status",
        "trial_completed_without_scope": "scope_status",
        "missing_final_set_confirmation": "prompt_set_status",
        "stale_baseline_version": "baseline.prompt_version",
        "wrong_market": "does not match collection_config.market",
        "edited_query_same_version": "prompt_version must change",
        "added_query_same_version": "prompt_version must change",
        "deleted_query_same_version": "prompt_version must change",
        "cross_market_previous_bank": "previous bank must use the same market and language",
        "competitor_named_in_discovery": "names a brand or competitor ['SAP Concur']",
        "target_brand_named_in_discovery": "names a brand or competitor ['Example']",
        "english_query_in_thai_bank": "q3: query is not written in the collection language 'thai'",
        "review_unapproved_carrier_on_locked_set":
            "ERROR: attributes carried only by Prompts not yet 已批准, so not counted as covered (1): 预算控制",
        "review_needs_revision_carrier_via_tag_on_locked_set":
            "ERROR: attributes carried only by Prompts not yet 已批准, so not counted as covered (1): 预算控制",
        "review_all_approved_on_locked_set": '"review_status": {"已批准": 5}',
        # 2 warnings: q0 / q4 share wording by construction, and the bank carries no
        # config.buyer_quotes, so gates 36–37 report that they were skipped.
        "locked_bank": '"readiness": "Usable: 2 warnings without a decision"',
        "evidence_three_families_no_warning": '"readiness": "Usable: 2 warnings without a decision"',
        "condition_outside_constraint_column":
            "WARNING: [W36] q1: condition outside the cited evidence ['数字 500']",
        "condition_without_cited_signal":
            "WARNING: [W36] q1: condition outside the cited evidence ['500美元以内', '数字 500']",
        # Gate 39 adds nothing on top of the two baseline warnings.
        "audience_named_in_wording": '"readiness": "Usable: 2 warnings without a decision"',
        "audience_one_of_several_named": '"readiness": "Usable: 2 warnings without a decision"',
        "audience_implicit_exempt": '"readiness": "Usable: 2 warnings without a decision"',
        "base_audience_not_checked": '"readiness": "Usable: 2 warnings without a decision"',
        "audience_terms_missing_is_manual_check": '"readiness": "Usable: 2 warnings without a decision"',
        "selection_locked_bank": '"readiness": "Ready for the next lifecycle stage"',
        "selection_row_without_priority": "ERROR: slice M-001: priority must be 高 / 中 / 低",
        "typed_prompt_on_wrong_type_row": "q4: prompt_type Competitor does not match row M-001 (Discovery)",
        "typed_mixed_type_topic_fails": "Gate 66: Topics mixing Prompt types (travel: Competitor + Discovery)",
        "typed_row_invalid_type": "slice M-009: prompt_type 'Verification' must be one of",
        "typed_row_with_prompt_types_list_is_old_structure":
            "unsupported old structure in current.json: matrix rows with the prompt_types list (1: M-001)",
    }
    expected_warnings = {
        "audience_not_named_warns": [
            "Prompts filed under a non-base audience whose wording neither states nor implies it (1): q1(中小企业财务)",
        ],
        "audience_without_terms_entry_warns": [
            "audiences with no entry in config.audience_terms (1): 中小企业财务",
        ],
        "category_pair_without_aliases_warns": [
            "q1 / q2: near-duplicate wording",
        ],
        "wording_heuristics_warn_without_failing": [
            "q1: too short to carry a buyer situation",
            "q2: asks more than one question",
            "q2: uses currency ['GBP'] outside the market's ['USD']",
        ],
        "review_pending_while_drafting_warns": [
            "review_status missing on 1 Prompts, counted as 待审核 (q4)",
            "attributes carried only by Prompts not yet 已批准, so not counted as covered (2): 账单合并, 预算控制",
        ],
        "evidence_single_family_warns": [
            "evidence spans only 1 source families (答案层)",
        ],
        "unused_audience_inputs_warn": [
            "audience inputs referenced by no Prompt (2): input-5, input-6",
        ],
        "constraint_column_backs_condition": [],
        "selection_topic_priority_mismatch_warns": ["topic travel: priority 中 but its highest row is 高"],
        "typed_discovery_row_without_prompt_warns": ["高 / 中 Discovery rows with no Prompt (1): M-004"],
        "selection_malformed_business_goals_warns": ["config.business_goals malformed"],
        "selection_competitor_without_goal_warns": ["Competitor Prompts written without the goal 竞争定位 in business_goals (1): q4",
                                                    "Alternatives Prompts written without the goal 竞争定位 in business_goals (1): q3"],
        "selection_topic_below_size_floor_warns": ["Topics below the default coverage target (travel: 4 KPI Prompts;"],
    }
    absent_warnings = {
        "changeability_field_not_read_by_selection": ["differs from the expected tier", "[W55]", "changeability"],
        "selection_without_business_goals_defaults": ["[W49]"],
        "selection_non_discovery_row_without_priority_passes": ["priority must be", "priority_basis is empty"],
        "typed_non_discovery_row_stays_quiet": ["rows with no Prompt"],
        "selection_locked_bank": ["Gate 66", "its rows sit in different Topics"],
        "audience_terms_missing_is_manual_check": ["audience_terms", "[W39]"],
        "selection_topic_below_size_floor_waived": ["without a decision"],
    }
    results = []
    for name, data, previous, expected in cases:
        result = validate(data, previous)
        output = (result.stdout + result.stderr).strip()
        passed = (result.returncode == 0) == expected
        # a fixture refused as old structure would pass every "expected invalid" case vacuously
        if "unsupported old structure" in output and name != "typed_row_with_prompt_types_list_is_old_structure":
            passed = False
        if name in expected_errors:
            passed = passed and expected_errors[name] in output
        for warning in expected_warnings.get(name, []):
            # every warning opens with its stable code "[Wnn]" (Suda 2026-11-02 审核清单 D5)
            passed = passed and re.search(r"WARNING: \[W\d+b?\] " + re.escape(warning), output) is not None
        for warning in absent_warnings.get(name, []):
            passed = passed and warning not in output
        results.append(
            {
                "case": name,
                "expected_valid": expected,
                "actual_valid": result.returncode == 0,
                "passed": passed,
                "output": output,
            }
        )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import check_client_base as ccb
    from validate_after_sales_set import legacy_markers
    # check_client_base, one row per Prompt type (2026-11-05): a 低 Discovery row with no Prompt needs 本期不出;
    # non-Discovery rows (对比, 替代) are reported — since 3.0.0 they stay in the bank JSON and out of the client
    # Base; two rows with the same audience, task, type and constraints, and a 对比 Prompt on a 发现 row are reported.
    typed_rows_base = [
        {"record_id": "t1", "切片编号": "M-201", "业务优先级": "低", "意图类型": "发现",
         "目标客户": "中小企业财务", "使用场景": "临时出差", "主题": [], "业务优先级依据": "低：不是本期重点"},
        {"record_id": "t2", "切片编号": "M-202", "业务优先级": "中", "意图类型": "对比",
         "目标客户": "中小企业财务", "使用场景": "临时出差", "主题": [], "业务优先级依据": "中：开行依据：销售记录里常拿 Navan 比"},
        {"record_id": "t3", "切片编号": "M-203", "业务优先级": "高", "意图类型": "发现",
         "目标客户": "中小企业财务", "使用场景": "控制差旅预算", "约束条件": ["预算控制"], "主题": ["T1"], "业务优先级依据": "高：核心可见度问题（1）"},
        {"record_id": "t4", "切片编号": "M-204", "业务优先级": "高", "意图类型": "发现",
         "目标客户": "中小企业财务", "使用场景": "控制差旅预算", "约束条件": ["预算控制"], "主题": ["T1"], "业务优先级依据": "高：核心可见度问题（1）"},
        {"record_id": "t5", "切片编号": "M-205", "业务优先级": "高", "意图类型": "替代",
         "目标客户": "中小企业财务", "使用场景": "控制差旅预算", "约束条件": ["预算控制"], "主题": ["T2"], "业务优先级依据": "高：开行依据：想换掉 SAP Concur"},
    ]
    typed_prompts = [{"编号": "Q1", "意图类型": "对比", "所属切片": ["t3"]}]
    got = ccb.check_matrix_v2(typed_rows_base, typed_prompts)
    want = [("M-201", "本期不出"), ("M-202", "非发现行只在题库 JSON 登记"), ("M-205", "非发现行只在题库 JSON 登记"),
            ("M-203", "另开一行对比行"), ("M-203、M-204", "意图类型「发现」、约束条件「预算控制」都相同")]
    ok = len(got) == len(want) and all(any(sid in g and needle in g for g in got) for sid, needle in want)
    results.append(
        {
            "case": "client_base_typed_rows",
            "expected_valid": True,
            "actual_valid": ok,
            "passed": ok,
            "output": json.dumps(got, ensure_ascii=False),
        }
    )
    # Old banks are not supported: one in the discovery-stage structure is refused, not skipped silently.
    old = copy.deepcopy(original)
    old["config"]["generation_stage"] = "discovery"
    for row in old["questions"]:
        row.update(journey_stage="发现", group_role="core")
    refused = validate(old)
    output = (refused.stdout + refused.stderr).strip()
    ok = (refused.returncode == 2 and "unsupported old structure" in output and "WARNING" not in output
          and not legacy_markers(original) and not legacy_markers(typed))
    results.append(
        {
            "case": "old_structure_bank_is_refused",
            "expected_valid": True,
            "actual_valid": ok,
            "passed": ok,
            "output": output,
        }
    )
    us_keys = {row["intent_key"] for row in original["questions"]}
    sg_keys = {row["intent_key"] for row in singapore["questions"]}
    fr_keys = {row["intent_key"] for row in france["questions"]}
    distinct = us_keys != sg_keys and us_keys != fr_keys and bool(us_keys & sg_keys & fr_keys)
    results.append(
        {
            "case": "market_review_can_retain_and_change_intents",
            "expected_valid": True,
            "actual_valid": distinct,
            "passed": distinct,
            "output": "Market banks retain some equivalent intents and allow distinct local intents; semantic evidence still needs human review.",
        }
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Write a reproducible JSON result artifact")
    args = parser.parse_args()
    results = run_checks()
    report = {
        "validator": str(VALIDATOR),
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"workflow e2e: {report['passed']}/{report['total']} passed")
    for result in results:
        if not result["passed"]:
            print(f"FAIL {result['case']}: {result['output']}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
