from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = SCRIPT_DIR.parent / "evals" / "fixtures"
sys.path.insert(0, str(SCRIPT_DIR))

from geo_presales_core.config import normalize_config
from geo_presales_core.crawler import answer_validity, import_crawl
from geo_presales_core.deterministic import prepare_answers
from geo_presales_core.metrics import _is_formal_visibility_answer, _is_sentiment_answer
from geo_presales_core.questions import normalize_question_bank
from geo_presales_core.util import (ContractError, domain_matches, find_alias_spans,
                                    normalize_url, read_json, resolve_alias_spans, write_json)


CLI = SCRIPT_DIR / "geo_presales.py"


class SourceTypeTableTests(unittest.TestCase):
    """来源类别表必须自洽：引用了已退休类别会直接 KeyError 打断整条构建。"""

    def test_known_host_types_use_live_source_types(self):
        from geo_presales_core.deterministic import (
            KNOWN_HOST_TYPES, RETIRED_SOURCE_TYPES, SOURCE_TYPES)
        allowed = set(SOURCE_TYPES) | set(RETIRED_SOURCE_TYPES)
        offenders = {host: kind for host, kind in KNOWN_HOST_TYPES.items()
                     if kind not in allowed}
        self.assertEqual({}, offenders)

    def test_retired_types_map_to_live_types(self):
        from geo_presales_core.deterministic import RETIRED_SOURCE_TYPES, SOURCE_TYPES
        for retired, live in RETIRED_SOURCE_TYPES.items():
            self.assertIn(live, SOURCE_TYPES, f"{retired} 映射到未定义的 {live}")

    def test_encyclopedia_and_institutions_classify_as_institutional(self):
        """机构网站 = 政府/非营利/教育/公共机构；百科类（维基）归这一类。"""
        from geo_presales_core.deterministic import _known_type
        for host in ("wikipedia.org", "zh.wikipedia.org", "wikimedia.org",
                     "who.int", "baike.baidu.com", "mit.edu", "nasa.gov"):
            self.assertEqual("institutional", _known_type(host), host)

    def test_retired_cache_values_do_not_crash_classification(self):
        """运行时缓存可能残留旧值，_known_type 必须按迁移口径归一而不是 KeyError。"""
        from geo_presales_core.deterministic import _known_type
        self.assertEqual("institutional", _known_type("some-museum.org",
                                                      {"some-museum.org": "encyclopedia_reference"}))
        self.assertEqual("other", _known_type("some-vendor.com",
                                              {"some-vendor.com": "corporate_site"}))
        self.assertEqual("other", _known_type("weird.example", {"weird.example": "brand_new_type"}))


class ContractTests(unittest.TestCase):
    def small_config(self):
        return normalize_config({
            "run_id": "R-test",
            "topic": "AI visibility software",
            "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
            "competitors": [{"name": "Beta", "aliases": ["Beta AI"], "domain": "beta.com"}],
            "quotas": {
                "total": 4,
                "question_type": {"generic": 2, "branded": 2},
                "funnel_intent": {"recommendation": 1, "comparison": 2, "decision": 1}
            }
        })

    def small_questions(self):
        return {
            "questions": [
                {"question_id": "q01", "question_type": "generic", "funnel_intent": "recommendation", "monitoring_prompt": "Which AI visibility tools track brand mentions?"},
                {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are best for small teams?"},
                {"question_id": "q03", "question_type": "branded", "funnel_intent": "comparison", "monitoring_prompt": "How does Acme AI compare with other visibility tools?"},
                {"question_id": "q04", "question_type": "branded", "funnel_intent": "decision", "monitoring_prompt": "Is Acme AI worth adopting for a small team?"},
            ]
        }

    def test_alias_boundary(self):
        self.assertEqual(find_alias_spans("A pineapple is not Apple.", ["Apple"])[0]["matched_text"], "Apple")
        self.assertEqual(len(find_alias_spans("pineapple", ["Apple"])), 0)

    def test_alias_conflict_blocks_config(self):
        with self.assertRaises(ContractError):
            normalize_config({
                "topic": "Test",
                "brand": {"name": "Acme", "domain": "acme.com", "aliases": ["Shared"]},
                "competitors": [{"name": "Beta", "domain": "beta.com", "aliases": ["Shared"]}],
            })

    def test_url_and_official_domain_boundaries(self):
        normalized = normalize_url("https://WWW.Acme.com:443/features/?utm_source=x&b=2&a=1#part")
        self.assertEqual(normalized["canonical_url"], "https://acme.com/features?a=1&b=2")
        self.assertEqual(normalized["removed_query_params"], ["utm_source"])
        self.assertTrue(domain_matches("docs.acme.com", "acme.com"))
        self.assertFalse(domain_matches("acme.com.evil.com", "acme.com"))

    def test_answer_validity_does_not_turn_failures_into_zero(self):
        self.assertEqual(answer_validity(""), (False, "EMPTY_ANSWER"))
        self.assertEqual(answer_validity("Something went wrong. Try again later."), (False, "ERROR_PAGE"))
        self.assertEqual(answer_validity("Acme is a valid option."), (True, None))

    def test_answer_validity_ignores_reference_definition_lines(self):
        # 引用定义行是采集交付的引用数据，不是助手正文。其实测中 URL 路径（one-login）、
        # 查询串（utm_source=chatgpt）与标题（"One Login"）会拼出跨词匹配，
        # 把正常回答判成 LOGIN_REQUIRED（trip-biz scraper.chatgpt/SG/0025.json、0026.json）。
        body = (
            "FCM covers the region well.\n\n"
            "[1]: https://www.fcmtravel.com/en-sg/one-login-technology/Singapore?utm_source=chatgpt.com "
            "\"FCM Travel - One Login - Singapore, Hong Kong, Malaysia | FCM Travel\""
        )
        self.assertEqual(answer_validity(body), (True, None))
        # 剔除引用行后，真正的失败页仍要被识别
        self.assertEqual(
            answer_validity("I encountered an error doing what you asked. Could you try again?\n"
                            "[1]: https://example.com \"Example\""),
            (False, "ERROR_PAGE"))
        self.assertEqual(answer_validity("Please log in to your ChatGPT account to continue."),
                         (False, "LOGIN_REQUIRED"))

    def test_task190_metric_scopes_are_independent(self):
        non_discovery_visibility = {
            "diagnostic_intents": ["competitor"],
            "metric_scopes": ["visibility"],
            "question_type": "branded",
        }
        overlapping_sentiment = {
            "diagnostic_intents": ["competitor", "sentiment"],
            "metric_scopes": ["visibility", "sentiment"],
            "question_type": "branded",
        }
        discovery = {
            "diagnostic_intents": ["discovery"],
            "metric_scopes": ["visibility", "citation"],
            "question_type": "generic",
        }

        self.assertFalse(_is_formal_visibility_answer(non_discovery_visibility))
        self.assertFalse(_is_sentiment_answer(non_discovery_visibility))
        self.assertFalse(_is_formal_visibility_answer(overlapping_sentiment))
        self.assertTrue(_is_sentiment_answer(overlapping_sentiment))
        self.assertTrue(_is_formal_visibility_answer(discovery))
        self.assertFalse(_is_sentiment_answer(discovery))

    def test_task190_sentiment_uses_analysis_type_without_intent_filter(self):
        for diagnostic_intent in ("competitor", "validation", "sentiment", "market_perception"):
            self.assertTrue(_is_sentiment_answer({
                "analysis_type": "sentiment",
                "diagnostic_intent": diagnostic_intent,
                "metric_scopes": ["visibility"],
                "question_type": "generic",
            }))
        self.assertFalse(_is_sentiment_answer({
            "analysis_type": "visibility",
            "diagnostic_intent": "sentiment",
            "metric_scopes": ["sentiment"],
            "question_type": "branded",
        }))

    def test_question_contract(self):
        config = self.small_config()
        self.assertNotIn("funnel_intent", config["quotas"])
        bank = normalize_question_bank(self.small_questions(), config)
        self.assertEqual(len(bank["questions"]), 4)
        different_distribution = self.small_questions()
        different_distribution["questions"][2]["funnel_intent"] = "recommendation"
        bank = normalize_question_bank(different_distribution, config)
        self.assertEqual(
            {"recommendation", "comparison", "decision"},
            {item["funnel_intent"] for item in bank["questions"]},
        )
        bad = self.small_questions()
        bad["questions"][0]["monitoring_prompt"] = "How does Acme work?"
        with self.assertRaises(ContractError):
            normalize_question_bank(bad, self.small_config())

    def test_legacy_awareness_is_migrated_to_recommendation(self):
        legacy = self.small_questions()
        legacy["questions"][0]["funnel_intent"] = "awareness"
        bank = normalize_question_bank(legacy, self.small_config())
        self.assertEqual("recommendation", bank["questions"][0]["funnel_intent"])
        self.assertTrue(
            any(item["code"] == "LEGACY_AWARENESS_MIGRATED" for item in bank["warnings"]),
            bank["warnings"],
        )

    def test_v3_geo_intent_is_ignored_by_report_consumer(self):
        v3 = self.small_questions()
        v3["questions"][0]["geo_intent"] = "pricing"
        bank = normalize_question_bank(v3, self.small_config())
        self.assertNotIn("geo_intent", bank["questions"][0])
        self.assertEqual("recommendation", bank["questions"][0]["funnel_intent"])

    def test_intent_miner_fixture_imports_without_translation_dependency(self):
        fixture = FIXTURES_DIR / "valid-prompt-bank.json"
        raw = read_json(fixture)
        config = normalize_config({
            "run_id": "R-intent-fixture",
            "topic": "AI search visibility platforms",
            "brand": {"name": "Peec AI", "domain": "peec.ai"},
            "competitors": [{"name": "Profound", "domain": "tryprofound.com"}],
            "quotas": raw["config"]["quotas"],
        })
        bank = normalize_question_bank(raw, config)
        self.assertEqual(len(bank["questions"]), 4)
        self.assertEqual(len(bank["warnings"]), 4)
        self.assertEqual("decision", bank["questions"][-1]["funnel_intent"])
        self.assertTrue(bank["questions"][-1]["question_text"].startswith("How well does "))

    def test_crawler_fixture_contract(self):
        fixture = FIXTURES_DIR / "sample-chatgpt-crawl.json"
        raw = read_json(fixture)
        question_bank = {
            "run_id": "R-crawler",
            "questions": [
                {"question_id": item["id"], "generation_sequence": item["index"], "question_text": item["question"]}
                for item in raw["input"]["questions"]
            ],
        }
        imported = import_crawl(raw, question_bank, fixture)
        self.assertEqual(imported["counts"]["valid_count"], 3)
        self.assertEqual(imported["counts"]["failed_count"], 1)
        self.assertEqual(sum(len(item["citations"]) for item in imported["samples"]), 8)
        failed = next(item for item in imported["samples"] if item["sample_id"] == "q02-r02")
        self.assertFalse(failed["analysis_eligible"])
        self.assertIsNone(failed["answer_text"])

    def test_crawler_plan_preserves_pending_samples(self):
        question_bank = {
            "run_id": "R-pending",
            "questions": [
                {"question_id": "q01", "generation_sequence": 1, "question_text": "What is an AI visibility platform?"},
                {"question_id": "q02", "generation_sequence": 2, "question_text": "Which AI visibility platform is best?"},
            ],
        }
        raw = {
            "run": {"engine": "chatgpt"},
            "plan": [
                {"sample_id": "q01-r01", "question_id": "q01", "question": question_bank["questions"][0]["question_text"], "repeat_index": 1},
                {"sample_id": "q02-r01", "question_id": "q02", "question": question_bank["questions"][1]["question_text"], "repeat_index": 1},
            ],
            "samples": [
                {
                    "sample_id": "q01-r01", "question_id": "q01", "question": question_bank["questions"][0]["question_text"],
                    "repeat_index": 1, "ok": True, "status": "done",
                    "result": {"ok": True, "answer": {"text": "A tool for measuring visibility."}, "references": {"items": []}},
                }
            ],
        }
        imported = import_crawl(raw, question_bank, "fixture.json")
        self.assertEqual(imported["counts"]["pending_count"], 1)
        pending = next(item for item in imported["samples"] if item["sample_id"] == "q02-r01")
        self.assertEqual(pending["error_code"], "PENDING")
        self.assertFalse(pending["analysis_eligible"])


class AliasMatchingTests(unittest.TestCase):
    """泰文/中文别名在连续文字里的匹配，以及跨对象撞名的最长优先消解。

    泰文无空格，品牌别名前后紧邻同文种字母也是 `\\w`；旧实现一律加词边界，
    导致泰语市场的别名永不命中、提及率被静默少算。见《CAU-中农大泰语称呼冻结》。
    """

    CAU = "มหาวิทยาลัยเกษตรจีน"
    SCAU = "มหาวิทยาลัยเกษตรจีนตอนใต้"

    def test_thai_alias_matches_inside_running_text(self):
        spans = find_alias_spans("แนะนำมหาวิทยาลัยเกษตรจีนตั้งอยู่ที่ปักกิ่ง", [self.CAU])
        self.assertEqual([item["matched_text"] for item in spans], [self.CAU])

    def test_cjk_alias_matches_inside_running_text(self):
        spans = find_alias_spans("我在看红果短剧很开心", ["红果短剧"])
        self.assertEqual([item["matched_text"] for item in spans], ["红果短剧"])

    def test_latin_boundary_still_requires_word_edges(self):
        # 拉丁别名仍不能落在更长单词里，也不能被更长的拉丁串命中。
        self.assertEqual(len(find_alias_spans("pineapple", ["Apple"])), 0)
        self.assertEqual(len(find_alias_spans("ShortMax", ["Max"])), 0)

    def test_cross_object_longest_alias_wins(self):
        # 中农大 `มหาวิทยาลัยเกษตรจีน` 是华南农大 `มหาวิทยาลัยเกษตรจีนตอนใต้` 的前缀，
        # 同一位置只算更长的那个对象。
        candidates = [
            {"alias": self.CAU, "matched_text": self.CAU, "start": 0, "end": len(self.CAU), "object_id": "target"},
            {"alias": self.SCAU, "matched_text": self.SCAU, "start": 0, "end": len(self.SCAU), "object_id": "competitor-01"},
        ]
        self.assertEqual(
            [item["object_id"] for item in resolve_alias_spans(candidates)],
            ["competitor-01"],
        )

    def test_same_object_overlapping_aliases_are_kept(self):
        # 只跨对象消解：同对象内部的重叠保持旧行为，拉丁结果不变。
        candidates = [
            {"alias": "YouTube", "matched_text": "YouTube", "start": 0, "end": 7, "object_id": "open-14"},
            {"alias": "YouTube Music", "matched_text": "YouTube Music", "start": 0, "end": 13, "object_id": "open-14"},
        ]
        self.assertEqual(len(resolve_alias_spans(candidates)), 2)

    def test_prepare_answers_does_not_credit_target_for_longer_competitor_alias(self):
        """端到端：答案只含华南农大长串时，中农大不得被记成提及。"""
        config = {
            "run_id": "R-thai",
            "rank_policy": "first_mention",
            "sample_policy": "first_valid",
            "objects": [
                {"object_id": "target", "canonical_name": "China Agricultural University",
                 "role": "target", "aliases": [self.CAU], "official_domains": ["cau.edu.cn"], "display_order": 1},
                {"object_id": "competitor-01", "canonical_name": "South China Agricultural University",
                 "role": "competitor", "aliases": [self.SCAU], "official_domains": ["scau.edu.cn"], "display_order": 2},
            ],
        }
        question_bank = {"questions": [{
            "question_id": "q01",
            "question_text": "Which Chinese agricultural universities are located in Guangzhou?",
            "question_type": "generic",
            "funnel_intent": "recommendation",
            "generation_sequence": 1,
        }]}
        answer = "มหาวิทยาลัยเกษตรจีนตอนใต้ตั้งอยู่ในกว่างโจว"
        crawl = {"samples": [{
            "sample_id": "q01-r01", "question_id": "q01", "repeat_index": 1,
            "analysis_eligible": True, "answer_text": answer, "ranking_text": answer,
            "citations": [], "provenance": None,
        }]}
        with tempfile.TemporaryDirectory() as temp:
            result = prepare_answers(Path(temp), config, question_bank, crawl)
        by_id = {obj["object_id"]: obj for obj in result["answers"][0]["objects"]}
        self.assertFalse(by_id["target"]["mentioned"])
        self.assertEqual(by_id["target"]["match_spans"], [])
        self.assertTrue(by_id["competitor-01"]["mentioned"])


class EndToEndTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != expected:
            self.fail(f"CLI failed ({completed.returncode}): {completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout)

    def task_result(self, task: dict, output: dict, status="completed"):
        return {
            "protocol_version": task["protocol_version"],
            "run_id": task["run_id"],
            "task_id": task["task_id"],
            "kind": task["kind"],
            "task_digest": task["task_digest"],
            "status": status,
            "output": output,
            "issues": [],
        }

    def test_low_confidence_creates_item_only_review(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            run_dir = temp / "run"
            config_path = temp / "config.json"
            questions_path = temp / "questions.json"
            crawl_path = temp / "crawl.json"
            write_json(config_path, {
                "run_id": "R-review",
                "topic": "AI visibility software",
                "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
                "competitors": [{"name": "Beta", "domain": "beta.com"}],
                "quotas": {
                    "total": 3,
                    "question_type": {"generic": 2, "branded": 1}
                }
            })
            question = "What should teams know about Acme AI?"
            answer = "Acme is capable, but the available evidence is limited."
            write_json(questions_path, {"questions": [
                {"question_id": "q01", "question_type": "branded", "funnel_intent": "recommendation", "monitoring_prompt": question},
                {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are easier for small teams?"},
                {"question_id": "q03", "question_type": "generic", "funnel_intent": "decision", "monitoring_prompt": "Which AI visibility tool should a small team choose?"},
            ]})
            write_json(crawl_path, {
                "run": {"engine": "chatgpt"},
                "samples": [{
                    "sample_id": "q01-r01", "question_id": "q01", "question_index": 1, "repeat_index": 1, "repeat_total": 1,
                    "question": question, "ok": True, "status": "done",
                    "result": {"ok": True, "answer": {"text": answer}, "references": {"items": []}},
                }]
            })
            self.run_cli("create-run", "--config", config_path, "--run-dir", run_dir)
            self.run_cli("import-questions", "--run-dir", run_dir, "--questions", questions_path)
            self.run_cli("import-crawl", "--run-dir", run_dir, "--crawl", crawl_path)
            self.run_cli("prepare", "--run-dir", run_dir)
            manifest = read_json(run_dir / "manifest.json")
            initial_id = next(iter(manifest["tasks"]))
            task = read_json(run_dir / manifest["tasks"][initial_id]["path"])
            result_path = temp / "low.json"
            write_json(result_path, self.task_result(task, {"items": {
                "q01-r01": {"label": "neutral", "score": 0.0, "confidence": 0.55, "evidence": [{"quote": answer}], "flags": ["AMBIGUOUS"]}
            }}))
            submitted = self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", initial_id, "--result", result_path)
            self.assertEqual(submitted["receipt"]["decision"], "accepted_with_review")
            manifest = read_json(run_dir / "manifest.json")
            review_tasks = [
                read_json(run_dir / meta["path"])
                for task_id, meta in manifest["tasks"].items()
                if task_id != initial_id
            ]
            self.assertEqual(len(review_tasks), 1)
            self.assertEqual(review_tasks[0]["mode"], "review")
            self.assertEqual(set(review_tasks[0]["input"]["items"]), {"q01-r01"})

    def test_full_cli_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            run_dir = temp / "run"
            config_path = temp / "config.json"
            questions_path = temp / "questions.json"
            crawl_path = temp / "crawl.json"
            write_json(config_path, {
                "run_id": "R-e2e",
                "topic": "AI visibility software",
                "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
                "competitors": [{"name": "Beta", "aliases": ["Beta AI"], "domain": "beta.com"}],
                "quotas": {
                    "total": 4,
                    "question_type": {"generic": 2, "branded": 2},
                    "funnel_intent": {"recommendation": 1, "comparison": 2, "decision": 1}
                }
            })
            write_json(questions_path, {
                "questions": [
                    {"question_id": "q01", "question_type": "generic", "funnel_intent": "recommendation", "monitoring_prompt": "Which AI visibility tools track brand mentions?"},
                    {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are best for small teams?"},
                    {"question_id": "q03", "question_type": "branded", "funnel_intent": "comparison", "monitoring_prompt": "How does Acme AI compare with other visibility tools?"},
                    {"question_id": "q04", "question_type": "branded", "funnel_intent": "decision", "monitoring_prompt": "Is Acme AI worth adopting for a small team?"},
                ]
            })
            answers = {
                "q01": "Beta is a commonly cited option for basic monitoring.",
                "q02": "Beta appears first, while Acme offers clearer workflows for small teams.",
                "q03": "Acme is easy to use and has clear onboarding.",
                "q04": "Acme is expensive for a small team and its reporting is limited.",
            }
            refs = {
                "q01": [{"url": "https://beta.com/overview", "title": "Beta"}],
                "q02": [{"url": "https://acme.com/features?utm_source=test", "title": "Acme features"}],
                "q03": [{"url": "https://www.acme.com/features#details", "title": "Acme features"}],
                "q04": [{"url": "https://reddit.com/r/tools/post", "title": "Discussion"}],
            }
            write_json(crawl_path, {
                "schema_version": "yao-chatgpt-crawler/v1",
                "run": {"engine": "chatgpt"},
                "samples": [
                    {
                        "sample_id": f"{qid}-r01", "question_id": qid, "question_index": index,
                        "repeat_index": 1, "repeat_total": 1,
                        "question": read_json(questions_path)["questions"][index-1]["monitoring_prompt"],
                        "ok": True, "status": "done", "error": "",
                        "result": {"ok": True, "answer": {"text": answers[qid]}, "references": {"count": 1, "items": refs[qid]}},
                    }
                    for index, qid in enumerate(("q01", "q02", "q03", "q04"), 1)
                ]
            })

            self.run_cli("create-run", "--config", config_path, "--run-dir", run_dir)
            self.run_cli("import-questions", "--run-dir", run_dir, "--questions", questions_path)
            self.run_cli("import-crawl", "--run-dir", run_dir, "--crawl", crawl_path)
            self.run_cli("prepare", "--run-dir", run_dir)

            manifest = read_json(run_dir / "manifest.json")
            sentiment_id = next(task_id for task_id, meta in manifest["tasks"].items() if meta["kind"] == "sentiment_batch")
            sentiment_task = read_json(run_dir / manifest["tasks"][sentiment_id]["path"])
            sentiment_output = {"items": {}}
            labels = {"q02-r01": ("positive", 0.5), "q03-r01": ("positive", 0.8), "q04-r01": ("negative", -0.7)}
            for answer_id, item in sentiment_task["input"]["items"].items():
                label, score = labels[answer_id]
                sentiment_output["items"][answer_id] = {
                    "label": label,
                    "score": score,
                    "confidence": 0.9,
                    "evidence": [{"quote": answers[answer_id.split("-r")[0]]}],
                    "flags": [],
                }
            result_path = temp / "sentiment.json"
            write_json(result_path, self.task_result(sentiment_task, sentiment_output))
            self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", sentiment_id, "--result", result_path)

            computed = self.run_cli("compute", "--run-dir", run_dir)
            self.assertEqual(computed["coverage"]["valid_answers"], 4)
            metrics = read_json(run_dir / "artifacts/metrics.json")
            self.assertEqual(metrics["opportunity"]["counts"], {"priority_improve": 1, "continue_optimize": 0, "stable": 1})
            self.assertEqual(metrics["sentiment"]["counts"], {"positive": 1, "neutral": 0, "negative": 1})

            while True:
                self.run_cli("prepare-report-tasks", "--run-dir", run_dir)
                manifest = read_json(run_dir / "manifest.json")
                pending = [
                    (task_id, meta, read_json(run_dir / meta["path"]))
                    for task_id, meta in manifest["tasks"].items()
                    if meta["status"] == "pending" and all(manifest["tasks"][dep]["status"] in {"accepted", "degraded"} for dep in meta.get("depends_on") or [])
                ]
                if not pending:
                    break
                for task_id, meta, task in pending:
                    if task["kind"] == "brand_expression_themes":
                        output = {
                            "positive": [{
                                "label": "Easy onboarding",
                                "summary": "Verified answers describe clear setup and workflows.",
                                "evidence_ids": ["E-q03-r01-01"],
                                "confidence": 0.9,
                            }],
                            "risk": [{
                                "label": "Cost and reporting limits",
                                "summary": "One verified answer raises cost and reporting concerns.",
                                "evidence_ids": ["E-q04-r01-01"],
                                "confidence": 0.9,
                            }],
                        }
                    elif task["kind"] == "report_module":
                        output = {
                            "module_id": task["input"]["module_id"],
                            "title": f"Module {task['input']['module_id']}",
                            "points": [{"text_template": "This module summarizes verified batch evidence.", "refs": []}],
                            "conclusion": None,
                        }
                    elif task["kind"] == "next_actions":
                        output = {
                            "summary": {"text_template": "Prioritize the verified gaps in this batch.", "refs": []},
                            "actions": [
                                {
                                    "direction_id": direction["direction_id"],
                                    "source_module": direction["source_module"],
                                    "title": "Act on verified evidence",
                                    "evidence_template": "The deterministic metrics support this direction.",
                                    "expected_impact_template": "Make the relevant evidence easier to understand and cite.",
                                    "action": "Review the verified gaps and improve the corresponding factual explanation and proof points.",
                                    "refs": [],
                                }
                                for direction in task["input"]["directions"]
                            ],
                        }
                    else:
                        self.fail(f"Unexpected task kind {task['kind']}")
                    task_result_path = temp / f"{task_id}.json"
                    write_json(task_result_path, self.task_result(task, output))
                    self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", task_id, "--result", task_result_path)

            finalized = self.run_cli("finalize", "--run-dir", run_dir)
            self.assertTrue(finalized["publishable"])
            report = read_json(run_dir / "artifacts/report-data.json")
            self.assertEqual(report["run_id"], "R-e2e")
            self.assertEqual(len(report["modules"]), 5)
            self.assertEqual(len(report["next_actions"]["actions"]), 3)


if __name__ == "__main__":
    unittest.main()
