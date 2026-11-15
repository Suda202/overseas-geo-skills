from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import all_objects
from .shopping import attribute_cards
from .util import (
    domain_matches,
    find_alias_spans,
    normalize_host,
    normalize_url,
    resolve_alias_spans,
    sha256_obj,
    write_text,
)


# 引用来源分类的类别表、内置域名表和判定函数在 sources.py（唯一实现），这里只转出旧名字，
# 供 `from geo_presales_core.deterministic import SOURCE_TYPES` 这类老调用继续可用。
from .sources import (  # noqa: E402,F401
    KNOWN_HOST_TYPES,
    RETIRED_SOURCE_TYPES,
    SOURCE_TYPES,
    _classify_official,
    _known_type,
    classify_source,
)


def choose_representative_samples(samples: list[dict], questions: list[dict]) -> tuple[dict[str, str | None], list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        grouped[sample["question_id"]].append(sample)
    selected: dict[str, str | None] = {}
    issues: list[dict] = []
    for question in questions:
        candidates = sorted(grouped.get(question["question_id"], []), key=lambda item: (item["repeat_index"], item["sample_id"]))
        valid = [item for item in candidates if item["analysis_eligible"]]
        chosen = valid[0] if valid else (candidates[0] if candidates else None)
        selected[question["question_id"]] = chosen["sample_id"] if chosen else None
        if len(valid) > 1:
            issues.append({
                "code": "MULTIPLE_VALID_REPEATS_FIRST_SELECTED",
                "question_id": question["question_id"],
                "selected_sample_id": chosen["sample_id"],
                "valid_sample_ids": [item["sample_id"] for item in valid],
            })
    return selected, issues


def prepare_answers(run_root: Path, config: dict, question_bank: dict, crawl: dict) -> dict:
    question_by_id = {item["question_id"]: item for item in question_bank["questions"]}
    selected, issues = choose_representative_samples(crawl["samples"], question_bank["questions"])
    answers: list[dict] = []
    unknown_hosts: dict[str, dict] = {}

    for sample in crawl["samples"]:
        question = question_by_id[sample["question_id"]]
        answer_text = sample.get("answer_text") or ""
        # 品牌匹配跑在去引用正文上（`ranking_text`，由上游剥离引用标记与商品卡商家列）；
        # 缺该字段时回落到原文以保持旧输入可用。理由见 build_report_data.py 的 de_cite
        # 注释：被引文章标题里的品牌不该算成回答提及。
        matching_text = sample.get("ranking_text") or answer_text
        evidence_path = run_root / "evidence/answers" / f"{sample['sample_id']}.txt"
        write_text(evidence_path, answer_text)
        objects = all_objects(config)
        # 品牌匹配按对象各跑一次会漏掉跨对象撞名：泰文无空格、别名又不带词边界，
        # 短别名会落进别的对象的长别名里（乙大学 vs 乙大学南校区）。先把所有对象的候选
        # 跨度汇总，做一次最长优先不重叠消解，再回填到各自对象。拉丁别名带词边界，
        # 跨对象消解对它是空操作，既有结果不变。
        resolved_spans: dict[str, list[dict]] = defaultdict(list)
        if sample["analysis_eligible"]:
            candidates = [
                {**span, "object_id": obj["object_id"]}
                for obj in objects
                for span in find_alias_spans(matching_text, obj["aliases"], obj.get("case_sensitive_aliases"))
            ]
            for span in resolve_alias_spans(candidates):
                resolved_spans[span["object_id"]].append({
                    "alias": span["alias"],
                    "matched_text": span["matched_text"],
                    "start": span["start"],
                    "end": span["end"],
                })
        object_records = []
        for obj in objects:
            spans = resolved_spans.get(obj["object_id"], [])
            object_records.append({
                "object_id": obj["object_id"],
                "canonical_name": obj["canonical_name"],
                "role": obj["role"],
                "mentioned": bool(spans),
                "matched_aliases": sorted({span["alias"] for span in spans}),
                "match_spans": spans,
                "first_position": spans[0]["start"] if spans else None,
                "mention_order": None,
                "recommendation_rank": None,
                "report_rank": None,
                "sentiment": "not_applicable" if not spans else None,
                "sentiment_score": None,
                "sentiment_confidence": None,
                "sentiment_evidence": [],
                "sentiment_status": "not_applicable" if not spans else "pending",
            })
        mentioned = sorted(
            [item for item in object_records if item["mentioned"]],
            key=lambda item: (item["first_position"], next(obj["display_order"] for obj in config["objects"] if obj["object_id"] == item["object_id"])),
        )
        for rank, item in enumerate(mentioned, 1):
            item["mention_order"] = rank
            item["report_rank"] = rank

        citations = []
        for raw in sample.get("citations") or []:
            normalized = normalize_url(raw.get("raw_url")) if raw.get("raw_url") else None
            row = dict(raw)
            row.update({
                "canonical_url": normalized.get("canonical_url") if normalized else None,
                "host": normalized.get("host") if normalized else normalize_host(raw.get("domain_hint")),
                "registrable_domain": normalized.get("registrable_domain") if normalized else None,
                "removed_query_params": normalized.get("removed_query_params") if normalized else [],
                "normalization_status": "normalized" if normalized else "failed",
                "source_type": "other",
                "source_type_name": SOURCE_TYPES["other"],
                "matched_official_object_id": None,
                "classification_source": "default_other",
                "classification_confidence": None,
            })
            if row["host"]:
                verdict = classify_source(row["host"], config)
                if verdict["basis"] != "unjudged":
                    row.update({
                        "source_type": verdict["source_type"],
                        "source_type_name": SOURCE_TYPES[verdict["source_type"]],
                        "matched_official_object_id": verdict["object_id"],
                        "classification_source": verdict["basis"],
                        "classification_confidence": verdict["confidence"],
                    })
                else:
                    if normalized and selected.get(sample["question_id"]) == sample["sample_id"]:
                        host_item = unknown_hosts.setdefault(row["host"], {
                            "host": row["host"],
                            "sample_urls": [],
                            "titles": [],
                            "snippets": [],
                            "citation_ids": [],
                        })
                        if row["canonical_url"] and row["canonical_url"] not in host_item["sample_urls"]:
                            host_item["sample_urls"].append(row["canonical_url"])
                        if row.get("title") and row["title"] not in host_item["titles"]:
                            host_item["titles"].append(row["title"])
                        if row.get("summary") and row["summary"] not in host_item["snippets"]:
                            host_item["snippets"].append(row["summary"])
                        host_item["citation_ids"].append(row["raw_citation_id"])
            citations.append(row)

        answers.append({
            "answer_id": sample["sample_id"],
            "sample_id": sample["sample_id"],
            "question_id": sample["question_id"],
            "question_text": question["question_text"],
            "question_zh": question.get("question_zh"),
            "question_type": question["question_type"],
            "funnel_intent": question["funnel_intent"],
            "diagnostic_intent": question.get("diagnostic_intent"),
            "analysis_type": question.get("analysis_type"),
            "metric_scopes": question.get("metric_scopes"),
            "topic_id": question.get("topic_id"),
            "attribute_ids": question.get("attribute_ids") or [],
            "generation_sequence": question["generation_sequence"],
            "repeat_index": sample["repeat_index"],
            "selected_for_report": selected.get(sample["question_id"]) == sample["sample_id"],
            "validity": "valid" if sample["analysis_eligible"] else "invalid",
            "validity_reason": None if sample["analysis_eligible"] else sample.get("error_code"),
            "answer_text": sample.get("answer_text"),
            "answer_zh": None,
            "translation_status": "not_requested",
            "evidence_ref": str(evidence_path.relative_to(run_root)),
            "objects": object_records,
            "citations": citations,
            # 购物层：平台不支持商品字段时为 None（不是空列表），见 shopping.py。
            "engine": sample.get("engine"),
            "product_cards": attribute_cards(sample.get("product_cards"), objects),
            "provenance": sample.get("provenance"),
        })

    unknown_items = {}
    for index, host in enumerate(sorted(unknown_hosts), 1):
        item = unknown_hosts[host]
        item["sample_urls"] = item["sample_urls"][:3]
        item["titles"] = item["titles"][:3]
        item["snippets"] = item["snippets"][:3]
        unknown_items[f"S-{index:03d}"] = item

    return {
        "schema_version": "geo-presales-answers/v1",
        "run_id": config["run_id"],
        "rank_policy": config["rank_policy"],
        "sample_policy": config["sample_policy"],
        "selected_samples": selected,
        "issues": issues,
        "answers": answers,
        "unknown_source_items": unknown_items,
        "answers_hash": sha256_obj(answers),
    }
