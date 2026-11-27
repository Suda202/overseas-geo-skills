#!/usr/bin/env python3
"""采集读数 → 诊断素材包（materials.json / materials.md）。

给分析师写报告的「诊断」与「行动」模块用：按主题汇总读数、竞品与第三方被引页面、页面缺口页、可改变性，
抓出回答正文里提到目标品牌的原句、检索词（fan-out）的年份 / 新增限定词 / 推荐类里的品牌 / 旧名命中。

只整理已有读数，不重新判品牌、不算指标口径（那是 geo-metrics / layer_readings 的事），也不下结论。

输入：
    --readings         layer_readings.py 的输出目录（readings.json + answers.jsonl）
    --target-pattern   目标品牌在正文里的识别正则（不区分大小写）
    --old-names        可选，品牌旧名，逗号分隔
    --pagegap          可选，page_gap.py 的输出目录（page_gap.csv）
    --changeability    可选，changeability_domains.py 的 changeability.csv
    --out              输出目录

输出：materials.json（机读）、materials.md（中文人读版，供写诊断用）。

用法：
    python3 scripts/diagnosis_materials.py --readings <readings目录> \\
        --target-pattern 'data\\s?ocean|speechocean' --old-names SpeechOcean \\
        --pagegap <pagegap目录> --changeability <changeability.csv> --out <输出目录>
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

STOPWORDS = {
    "the", "a", "for", "of", "to", "and", "or", "in", "with", "which", "what", "is", "are",
    "that", "best", "i", "we", "our", "can", "do", "does", "how", "who", "an", "on", "by",
    "from", "at", "as", "be", "it", "its", "my", "your", "their", "this", "these", "those",
    "you", "need", "want", "vs",
}
RECOMMEND_TYPES = {"discovery", "alternatives"}
WORD = re.compile(r"[a-z][a-z0-9]+")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
FOOTNOTE_LINE = re.compile(r"^\s*\[\d+\]:.*$", re.M)
IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
SENT_SPLIT = re.compile(r"[。！？!?\n]+")
YUPAN = re.compile(r"（预判[^）]*）|\(预判[^)]*\)")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def norm_url(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def get_queries(raw: dict) -> list[str]:
    """task_result.search_model_queries 三种结构：{"queries": [...]}、列表、缺失。"""
    task = raw.get("task_result") or {}
    value = task.get("search_model_queries")
    if isinstance(value, dict):
        value = value.get("queries")
    if not isinstance(value, list):
        return []
    return [q.strip() for q in value if isinstance(q, str) and q.strip()]


def brand_entries(meta: dict) -> list[tuple[str, list[str]]]:
    """meta.brands 优先，其次 meta.lexicon；都没有返回空。"""
    entries = []
    brands = meta.get("brands")
    if isinstance(brands, list):
        for item in brands:
            if isinstance(item, dict) and item.get("name"):
                aliases = [a for a in item.get("aliases") or [] if isinstance(a, str)]
                entries.append((str(item["name"]), aliases))
            elif isinstance(item, str):
                entries.append((item, []))
    if entries:
        return entries
    lexicon = meta.get("lexicon")
    if isinstance(lexicon, list):
        for item in lexicon:
            if isinstance(item, dict) and item.get("name"):
                aliases = [a for a in item.get("aliases") or [] if isinstance(a, str)]
                entries.append((str(item["name"]), aliases))
            elif isinstance(item, str):
                entries.append((item, []))
    elif isinstance(lexicon, dict):
        for name, value in lexicon.items():
            aliases = value.get("aliases") if isinstance(value, dict) else value
            entries.append((str(name), [a for a in aliases or [] if isinstance(a, str)]))
    return entries


def alias_regex(alias: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", re.I)


def clean_body(text: str) -> str:
    text = FOOTNOTE_LINE.sub("", text)
    text = IMG_TAG.sub(" ", text)
    text = MD_LINK.sub(r"\1", text)
    return text


def sentences_with_target(text: str, pattern: re.Pattern) -> list[str]:
    out = []
    for raw in SENT_SPLIT.split(clean_body(text)):
        sentence = " ".join(raw.split())
        if not sentence or not pattern.search(sentence):
            continue
        if 40 <= len(sentence) <= 400:
            out.append(sentence)
    return out


def reason_prefix(reason: str) -> str:
    reason = (reason or "").strip()
    for sep in ("：", ":"):
        if sep in reason:
            reason = reason.split(sep, 1)[0]
            break
    reason = YUPAN.sub("", reason).strip()
    return reason or "（未写原因）"


def load_page_gaps(directory: Path):
    rows = []
    with (directory / "page_gap.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    return rows


def load_changeability(path: Path) -> dict[str, dict]:
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            qid = (row.get("question_id") or "").strip()
            if qid:
                out[qid] = row
    return out


def to_int(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--readings", required=True, help="layer_readings.py 的输出目录")
    ap.add_argument("--target-pattern", required=True, help="目标品牌正文识别正则（不区分大小写）")
    ap.add_argument("--old-names", default="", help="品牌旧名，逗号分隔")
    ap.add_argument("--pagegap", help="page_gap.py 的输出目录")
    ap.add_argument("--changeability", help="changeability.csv 路径")
    ap.add_argument("--out", required=True, help="输出目录")
    args = ap.parse_args(argv)

    src = Path(args.readings)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    target = re.compile(args.target_pattern, re.I)
    old_names = [n.strip() for n in args.old_names.split(",") if n.strip()]
    old_res = [(n, alias_regex(n)) for n in old_names]

    data = json.loads((src / "readings.json").read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    questions = data.get("questions") or []
    answers = read_jsonl(src / "answers.jsonl")

    q_by_id = {q.get("question_id"): q for q in questions}
    topic_of = {qid: (q.get("topic") or "（未标主题）") for qid, q in q_by_id.items()}
    topic_order: list[str] = []
    for q in questions:
        topic = q.get("topic") or "（未标主题）"
        if topic not in topic_order:
            topic_order.append(topic)

    def topic_for(qid: str) -> str:
        topic = topic_of.get(qid)
        if topic is None:
            topic = "（未标主题）"
            topic_of[qid] = topic
            if topic not in topic_order:
                topic_order.append(topic)
        return topic

    # 主题里最常见的提示词类型
    type_counter = defaultdict(Counter)
    for q in questions:
        type_counter[q.get("topic") or "（未标主题）"][(q.get("prompt_type") or "").strip()] += 1

    stats = {}
    for topic in topic_order:
        types = type_counter.get(topic) or Counter()
        prompt_type = types.most_common(1)[0][0] if types else ""
        stats[topic] = {
            "prompt_type": prompt_type,
            "answers": 0,
            "target_mentioned": 0,
            "official_retrieved": 0,
            "official_cited": 0,
            "competitor_pages": Counter(),
            "third_pages": Counter(),
        }

    raw_cache: dict[str, dict] = {}

    def raw_of(path: str) -> dict:
        if path not in raw_cache:
            try:
                raw_cache[path] = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw_cache[path] = {}
        return raw_cache[path]

    target_sentences: list[dict] = []
    seen_sentences: set[str] = set()
    fanout_total = 0
    years = Counter()
    added_recommend = Counter()
    added_other = Counter()
    brand_counter = Counter()
    brands = brand_entries(meta)
    brand_res = [(name, [alias_regex(a) for a in aliases]) for name, aliases in brands]
    old_hits: list[dict] = []

    for row in answers:
        qid = (row.get("question_id") or "").strip()
        topic = topic_for(qid)
        bucket = stats[topic]
        bucket["answers"] += 1
        if row.get("target_mentioned"):
            bucket["target_mentioned"] += 1
        if row.get("official_retrieved"):
            bucket["official_retrieved"] += 1
        if row.get("official_cited"):
            bucket["official_cited"] += 1
        for url in row.get("competitor_cited_urls") or []:
            if isinstance(url, str):
                bucket["competitor_pages"][norm_url(url)] += 1
        for url in row.get("third_cited_urls") or []:
            if isinstance(url, str):
                bucket["third_pages"][norm_url(url)] += 1

        question = q_by_id.get(qid) or {}
        prompt_type = (question.get("prompt_type") or "").strip()
        q_text = (question.get("question") or "").lower()
        q_words = set(WORD.findall(q_text))
        recommend = prompt_type.lower() in RECOMMEND_TYPES

        file_path = row.get("file") or ""
        raw = raw_of(file_path) if file_path else {}
        queries = get_queries(raw)
        fanout_total += len(queries)

        for query in queries:
            for year in YEAR.findall(query):
                years[year] += 1
            added = {w for w in WORD.findall(query.lower())
                     if w not in STOPWORDS and w not in q_words}
            if recommend:
                added_recommend.update(added)
            else:
                added_other.update(added)
            for name, res in brand_res:
                if any(r.search(query) for r in res):
                    brand_counter[name] += 1
            matched_old = next((n for n, r in old_res if r.search(query)), None)
            if matched_old:
                old_hits.append({
                    "file": file_path,
                    "question_id": qid,
                    "query": query,
                    "target_in_answer": bool(row.get("target_mentioned")),
                })

        if file_path:
            body = ((raw.get("task_result") or {}).get("result_text") or "")
            for sentence in sentences_with_target(body, target):
                key = sentence.lower()
                if key in seen_sentences:
                    continue
                seen_sentences.add(key)
                target_sentences.append({
                    "file": file_path,
                    "question_id": qid,
                    "prompt_type": prompt_type,
                    "sentence": sentence,
                })

    page_rows = load_page_gaps(Path(args.pagegap)) if args.pagegap else None
    change_rows = load_changeability(Path(args.changeability)) if args.changeability else None

    page_gaps_by_topic = defaultdict(Counter)
    gap_pages_by_topic = defaultdict(dict)
    if page_rows is not None:
        for row in page_rows:
            topic = topic_for((row.get("question_id") or "").strip())
            gap = (row.get("gap") or "未知").strip() or "未知"
            page_gaps_by_topic[topic][gap] += 1
            if gap == "页面缺口":
                url = norm_url(row.get("url") or "")
                if not url:
                    continue
                entry = gap_pages_by_topic[topic].setdefault(
                    url, {"cited": 0, "competitors": 0})
                entry["cited"] += to_int(row.get("answers"))
                entry["competitors"] = max(entry["competitors"], to_int(row.get("competitors_on_page")))

    change_by_topic = defaultdict(Counter)
    reasons_by_topic = defaultdict(Counter)
    if change_rows is not None:
        for qid, row in change_rows.items():
            topic = topic_for(qid)
            suggested = (row.get("suggested") or "").strip() or "不适用"
            change_by_topic[topic][suggested] += 1
            if (row.get("reason") or "").strip():
                reasons_by_topic[topic][reason_prefix(row.get("reason") or "")] += 1

    by_topic = {}
    for topic in topic_order:
        bucket = stats[topic]
        item = {
            "prompt_type": bucket["prompt_type"],
            "answers": bucket["answers"],
            "target_mentioned": bucket["target_mentioned"],
            "official_retrieved": bucket["official_retrieved"],
            "official_cited": bucket["official_cited"],
            "top_competitor_pages": [[u, n] for u, n in bucket["competitor_pages"].most_common(8)],
            "top_third_pages": [[u, n] for u, n in bucket["third_pages"].most_common(8)],
        }
        if page_rows is not None:
            gaps = page_gaps_by_topic.get(topic) or Counter()
            item["page_gaps"] = {k: gaps.get(k, 0) for k in ("页面缺口", "答案缺口", "无", "未知")}
            pages = gap_pages_by_topic.get(topic) or {}
            ranked = sorted(pages.items(), key=lambda kv: (-kv[1]["cited"], -kv[1]["competitors"], kv[0]))
            item["gap_pages"] = [[u, v["cited"], v["competitors"]] for u, v in ranked[:8]]
        if change_rows is not None:
            changes = change_by_topic.get(topic) or Counter()
            item["changeability"] = {k: changes.get(k, 0) for k in ("高", "中", "低", "不适用")}
            item["changeability_reasons"] = [[r, n] for r, n in reasons_by_topic.get(topic, Counter()).most_common(5)]
        by_topic[topic] = item

    all_added = added_recommend + added_other
    fanout = {
        "total": fanout_total,
        "per_answer": round(fanout_total / len(answers), 2) if answers else 0.0,
        "years": dict(sorted(years.items())),
        "added_terms": [[w, n] for w, n in all_added.most_common(60)],
        "added_terms_recommend": [[w, n] for w, n in added_recommend.most_common(60)],
        "added_terms_other": [[w, n] for w, n in added_other.most_common(60)],
        "brands_in_recommend_fanouts": [[b, n] for b, n in brand_counter.most_common()],
        "old_name_hits": old_hits,
    }

    materials = {"by_topic": by_topic, "target_sentences": target_sentences, "fanout": fanout}
    (out_dir / "materials.json").write_text(
        json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "materials.md").write_text(render_md(materials), encoding="utf-8")
    return 0


def fmt_pages(rows, with_competitors=False) -> list[str]:
    lines = []
    for row in rows:
        if with_competitors:
            lines.append(f"- {row[0]}（被引 {row[1]} 次，竞品 {row[2]} 家）")
        else:
            lines.append(f"- {row[0]}（{row[1]} 次）")
    return lines or ["- 无"]


def render_md(materials: dict) -> str:
    lines = ["# 诊断素材包", "", "这是写诊断的素材，不是对客结论。", ""]
    for topic, item in materials["by_topic"].items():
        lines.append(f"## 主题：{topic}")
        lines.append("")
        lines.append(
            f"- 读数：回答 {item['answers']} 条，品牌被提及 {item['target_mentioned']} 条，"
            f"官网进检索 {item['official_retrieved']} 条，官网被引 {item['official_cited']} 条；"
            f"主要提示词类型 {item['prompt_type'] or '未标'}")
        lines.append("- 竞品被引页面：")
        lines.extend("  " + line for line in fmt_pages(item["top_competitor_pages"]))
        lines.append("- 第三方被引页面：")
        lines.extend("  " + line for line in fmt_pages(item["top_third_pages"]))
        if "page_gaps" in item:
            gaps = item["page_gaps"]
            lines.append(
                f"- 页面缺口分布：页面缺口 {gaps['页面缺口']} 页，答案缺口 {gaps['答案缺口']} 页，"
                f"无 {gaps['无']} 页，未知 {gaps['未知']} 页")
            lines.append("- 页面缺口页：")
            lines.extend("  " + line for line in fmt_pages(item["gap_pages"], with_competitors=True))
        if "changeability" in item:
            changes = item["changeability"]
            lines.append(
                f"- 可改变性：高 {changes['高']} / 中 {changes['中']} / 低 {changes['低']} / "
                f"不适用 {changes['不适用']}")
            if item["changeability_reasons"]:
                lines.append("- 原因：")
                lines.extend(f"  - {reason}（{n} 次）" for reason, n in item["changeability_reasons"])
        lines.append("")

    lines.append("## AI 对品牌的原话")
    lines.append("")
    grouped = defaultdict(list)
    for row in materials["target_sentences"]:
        grouped[row["prompt_type"] or "未标"].append(row)
    if not grouped:
        lines.append("- 无")
    for prompt_type, rows in grouped.items():
        lines.append(f"### {prompt_type}（{len(rows)} 句，列前 15）")
        for row in rows[:15]:
            lines.append(f"- [{row['question_id']}] {row['sentence']}")
        lines.append("")

    fan = materials["fanout"]
    lines.append("## 检索词（fan-out）")
    lines.append("")
    lines.append(f"- 检索词总数 {fan['total']} 条，每条回答平均 {fan['per_answer']} 条")
    years = "、".join(f"{y}×{n}" for y, n in fan["years"].items()) or "无"
    lines.append(f"- 年份：{years}")
    added = "、".join(f"{w}（{n}）" for w, n in fan["added_terms"][:30]) or "无"
    lines.append(f"- 新增限定词（前 30）：{added}")
    brands = "、".join(f"{b}（{n}）" for b, n in fan["brands_in_recommend_fanouts"]) or "无"
    lines.append(f"- 推荐类检索词里的品牌：{brands}")
    lines.append("- 旧名命中：")
    for hit in fan["old_name_hits"]:
        flag = "回答提到品牌" if hit["target_in_answer"] else "回答未提品牌"
        lines.append(f"  - [{hit['question_id']}] {hit['query']}（{flag}）")
    if not fan["old_name_hits"]:
        lines.append("  - 无")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
