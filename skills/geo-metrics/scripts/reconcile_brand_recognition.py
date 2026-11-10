#!/usr/bin/env python3
"""品牌识别对账：用报告同一套识别跑一遍，列出漏判候选和误判候选，给人复核。

识别路径与报告完全一致：strip_citations + blank_merchant_columns 清正文，answer_validity 判有效，
build_report_data.load_lexicon 读词表，find_alias_spans + resolve_alias_spans 匹配。对账只在这之上加两条
确定性规则，不改识别结果：

  漏判候选  正文里的大写词（或相邻两个词连写）与某品牌别名首字母相同、拼写近似（5–8 字母差 1、9 字母以上差 2，
            或只差空格/连字符），且未被识别成任何品牌；词典里的普通单词不算。该回答没认出这个品牌时记「影响提及」，
            否则「无影响」。
  误判候选  品牌标准名带大写，但这条回答里它的命中全是小写（filter ring、outer ring 被算成 Ring）。
            「常用词只在句首出现」试过，Bbrand 数据 6 条全是加粗列表项或标题里的真品牌，已弃用。

只看拉丁字母；泰文、中日文别名不参与近似拼写，计入 skipped_non_latin_aliases。
词表外的新品牌不归这里，用 mine_brand_lexicon.py。

用法
    python3 reconcile_brand_recognition.py --collect <采集目录> [<采集目录> ...] \
        --lexicon <品牌词表.json> --out-dir <输出目录>
产出 summary.json、candidates.csv、report.md。
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for extra in (HERE, SKILLS / "geo-presales-report-builder" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import build_report_data as brd  # noqa: E402
import geo_presales_core.util as core_util  # noqa: E402
from de_cite_crawl import blank_merchant_columns, strip_citations  # noqa: E402
from geo_presales_core.crawler import answer_validity  # noqa: E402
from geo_presales_core.util import find_alias_spans, normalize_text, resolve_alias_spans  # noqa: E402

LATIN_ALIAS = re.compile(r"^[A-Za-z0-9 .'&+\-]+$")
WORD_RE = re.compile(r"(?<![\w])[A-Za-z][A-Za-z0-9]*(?:['’.&+\-][A-Za-z0-9]+)*")
DICT_PATH = Path("/usr/share/dict/words")


def squash(text: str) -> str:
    return re.sub(r"[\s.\-_'’]+", "", text.casefold())


def strip_possessive(token: str) -> str:
    return re.sub(r"['’]s$", "", token)


def edit_distance(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def allowed_distance(alias_len: int) -> int:
    return 1 if alias_len <= 8 else 2


def load_dictionary() -> set[str]:
    if not DICT_PATH.exists():
        return set()
    return {w.strip() for w in DICT_PATH.read_text(errors="ignore").splitlines() if w.strip().islower()}


def build_brands(lexicon_path: Path) -> tuple[list[dict], dict]:
    entries, uncertain, status = brd.load_lexicon(lexicon_path)
    if status != "loaded":
        raise SystemExit(f"词表读不了：{lexicon_path}（{status}）")
    case_sensitive = core_util.read_case_sensitive_aliases(lexicon_path)
    owner: dict[str, str] = {}
    brands, dropped = [], []
    for entry in entries:
        aliases = []
        for alias in [entry["name"], *entry["aliases"]]:
            key = normalize_text(alias)
            if owner.get(key, entry["name"]) != entry["name"]:
                dropped.append({"alias": alias, "brand": entry["name"], "kept_by": owner[key]})
                continue
            owner[key] = entry["name"]
            if alias not in aliases:
                aliases.append(alias)
        brands.append({
            "object_id": entry["name"],
            "aliases": aliases,
            "case_sensitive_aliases": core_util.case_sensitive_for(aliases, case_sensitive),
            "near": [(a, squash(a)) for a in aliases if LATIN_ALIAS.match(a) and len(squash(a)) >= 5],
            "has_upper": any(c.isupper() for c in entry["name"]),
        })
    meta = {"brands": len(brands), "uncertain": sorted(uncertain), "dropped_duplicate_aliases": dropped,
            "skipped_non_latin_aliases": sum(1 for b in brands for a in b["aliases"] if not LATIN_ALIAS.match(a))}
    return brands, meta


def parse_task(payload: dict, stats: dict):
    task = payload.get("task_result") or {}
    if isinstance(task, str):
        try:
            task = json.loads(task)
        except json.JSONDecodeError:
            try:
                task = ast.literal_eval(task)
            except (ValueError, SyntaxError):
                return None
        stats["legacy_string_task_result"] += 1
    return task if isinstance(task, dict) else None


def iter_answers(collect_dirs: list[Path], stats: dict):
    seen: set[str] = set()
    for root in collect_dirs:
        for path in sorted(root.rglob("*.json")):
            platform_dir = next((p for p in path.parents if p.name.startswith("scraper.")), None)
            if platform_dir is None or not path.stem.isdigit():
                continue
            platform = platform_dir.name.split(".", 1)[1]
            stats["files"] += 1
            if platform not in brd.ANSWER_FIELD:
                stats["unknown_platform"] += 1
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                stats["bad_json"] += 1
                continue
            task = parse_task(payload, stats)
            if task is None:
                stats["bad_task_result"] += 1
                continue
            raw = str(task.get(brd.ANSWER_FIELD[platform]) or "")
            digest = hashlib.sha256(json.dumps([platform, raw], ensure_ascii=False).encode()).hexdigest()
            if digest in seen:
                stats["duplicates"] += 1
                continue
            seen.add(digest)
            body = blank_merchant_columns(strip_citations(raw))
            valid, _ = answer_validity(body)
            if str(payload.get("status") or "success").lower() != "success" or not valid:
                stats["invalid"] += 1
                continue
            stats["answers"] += 1
            yield platform, path, body


def recognize(body: str, brands: list[dict]) -> dict[str, list[dict]]:
    spans = [dict(span, object_id=b["object_id"])
             for b in brands
             for span in find_alias_spans(body, b["aliases"], b["case_sensitive_aliases"])]
    found: dict[str, list[dict]] = defaultdict(list)
    for span in resolve_alias_spans(spans):
        found[span["object_id"]].append(span)
    return found


def snippet(body: str, start: int, end: int, width: int) -> str:
    return re.sub(r"\s+", " ", body[max(0, start - width):end + width]).strip()


def token_forms(body: str):
    words = [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(body)]
    for i, (word, start, end) in enumerate(words):
        yield word, start, end
        if i + 1 < len(words):
            nxt, nstart, nend = words[i + 1]
            if body[end:nstart].strip() == "":
                yield body[start:nend], start, nend


def near_misses(body: str, brands: list[dict], found: dict, dictionary: set[str], width: int) -> list[dict]:
    covered = [(s["start"], s["end"]) for spans in found.values() for s in spans]
    out, seen = [], set()
    for token, start, end in token_forms(body):
        token = strip_possessive(token)
        if not any(c.isupper() for c in token):
            continue
        if any(s < end and start < e for s, e in covered):
            continue
        if " " not in token and token.casefold() in dictionary:
            continue
        key = squash(token)
        for b in brands:
            for alias, alias_key in b["near"]:
                if key[:1] != alias_key[:1]:
                    continue
                cap = allowed_distance(len(alias_key))
                dist = edit_distance(key, alias_key, cap)
                if dist > cap or (dist == 0 and token.casefold() == alias.casefold()):
                    continue
                if (b["object_id"], token) in seen:
                    continue
                seen.add((b["object_id"], token))
                out.append({"kind": "漏判", "rule": "近似拼写" if dist else "只差空格或连字符",
                            "brand": b["object_id"], "text": token, "alias": alias, "distance": dist,
                            "affects_mention": b["object_id"] not in found,
                            "context": snippet(body, start, end, width)})
    return out


def false_positives(body: str, brands_by_id: dict, found: dict, width: int) -> list[dict]:
    out = []
    for object_id, spans in found.items():
        if not brands_by_id[object_id]["has_upper"]:
            continue
        if any(c.isupper() for s in spans for c in s["matched_text"]):
            continue
        first = spans[0]
        out.append({"kind": "误判", "rule": "命中全是小写", "brand": object_id, "text": first["matched_text"],
                    "alias": first["alias"], "distance": "", "affects_mention": True,
                    "context": snippet(body, first["start"], first["end"], width)})
    return out


def write_outputs(out_dir: Path, args, stats, meta, per_brand, rows) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    for brand, c in per_brand.items():
        if not (c["recognized"] or c["miss_affecting"] or c["fp"]):
            continue
        denominator_miss = c["recognized"] + c["miss_affecting"]
        summary_rows.append({
            "brand": brand, "recognized_answers": c["recognized"],
            "miss_candidates_affecting": c["miss_affecting"], "miss_candidates_no_effect": c["miss_no_effect"],
            "fp_candidates": c["fp"],
            "miss_rate_upper_bound": round(c["miss_affecting"] / denominator_miss, 4) if denominator_miss else 0,
            "fp_rate_upper_bound": round(c["fp"] / c["recognized"], 4) if c["recognized"] else 0,
        })
    summary_rows.sort(key=lambda r: (-(r["miss_candidates_affecting"] + r["fp_candidates"]), -r["recognized_answers"]))
    summary = {"inputs": {"collect": [str(p) for p in args.collect], "lexicon": str(args.lexicon)},
               "stats": stats, "lexicon": meta, "brands": summary_rows}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["kind", "rule", "brand", "text", "alias", "distance", "affects_mention", "platform", "file", "context"]
    with (out_dir / "candidates.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    def pct(value):
        return f"{value:.1%}"

    lines = ["# 品牌识别对账", "",
             f"- 采集目录：{', '.join(str(p) for p in args.collect)}",
             f"- 词表：{args.lexicon}（{meta['brands']} 个品牌；跳过非拉丁别名 {meta['skipped_non_latin_aliases']} 个；"
             f"跨品牌重名丢弃 {len(meta['dropped_duplicate_aliases'])} 个）",
             f"- 文件 {stats['files']}，重复 {stats['duplicates']}，无效 {stats['invalid']}，"
             f"旧格式字符串 {stats['legacy_string_task_result']}，坏文件 {stats['bad_json'] + stats['bad_task_result']}，"
             f"未知平台 {stats['unknown_platform']}；**有效回答 {stats['answers']}**", "",
             "漏判率、误判率都是上限：候选需人工复核，确认后才算数。", "",
             "| 品牌 | 识别为提及的回答 | 漏判候选（影响提及） | 漏判候选（无影响） | 误判候选 | 漏判率上限 | 误判率上限 |",
             "|---|---|---|---|---|---|---|"]
    for r in summary_rows:
        if r["miss_candidates_affecting"] or r["miss_candidates_no_effect"] or r["fp_candidates"]:
            lines.append(f"| {r['brand']} | {r['recognized_answers']} | {r['miss_candidates_affecting']} | "
                         f"{r['miss_candidates_no_effect']} | {r['fp_candidates']} | "
                         f"{pct(r['miss_rate_upper_bound'])} | {pct(r['fp_rate_upper_bound'])} |")
    for kind in ("漏判", "误判"):
        picked = [r for r in rows if r["kind"] == kind and r["affects_mention"]]
        lines += ["", f"## {kind}候选（影响提及，共 {len(picked)} 条，列前 {args.show}）", ""]
        for r in picked[:args.show]:
            lines.append(f"- **{r['brand']}** ← `{r['text']}`（{r['rule']}，{r['platform']}，{Path(r['file']).name}）："
                         f"{r['context']}")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect", nargs="+", type=Path, required=True, help="采集目录，可多个；按正文哈希去重")
    ap.add_argument("--lexicon", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--context", type=int, default=80, help="上下文前后各取多少字符")
    ap.add_argument("--show", type=int, default=30, help="report.md 每类最多列几条")
    args = ap.parse_args(argv)

    brands, meta = build_brands(args.lexicon)
    brands_by_id = {b["object_id"]: b for b in brands}
    dictionary = load_dictionary()
    meta["dictionary_words"] = len(dictionary)
    stats = defaultdict(int)
    per_brand = defaultdict(lambda: defaultdict(int))
    rows = []
    for platform, path, body in iter_answers(args.collect, stats):
        found = recognize(body, brands)
        for object_id in found:
            per_brand[object_id]["recognized"] += 1
        misses = near_misses(body, brands, found, dictionary, args.context)
        fps = false_positives(body, brands_by_id, found, args.context)
        for brand in {r["brand"] for r in misses if r["affects_mention"]}:
            per_brand[brand]["miss_affecting"] += 1
        for brand in {r["brand"] for r in misses if not r["affects_mention"]}:
            per_brand[brand]["miss_no_effect"] += 1
        for r in fps:
            per_brand[r["brand"]]["fp"] += 1
        rows += [dict(r, platform=platform, file=str(path)) for r in misses + fps]
    for key in ("files", "duplicates", "invalid", "legacy_string_task_result", "bad_json", "bad_task_result",
                "unknown_platform", "answers"):
        stats.setdefault(key, 0)
    summary = write_outputs(args.out_dir, args, dict(stats), meta, per_brand, rows)
    print(json.dumps({"answers": stats["answers"], "candidates": len(rows), "out": str(args.out_dir),
                      "top": summary["brands"][:5]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
