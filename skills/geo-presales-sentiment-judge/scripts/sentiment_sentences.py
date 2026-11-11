#!/usr/bin/env python3
"""Deterministic helpers for sentence-level brand sentiment in GEO presales.

This tool does NOT judge sentiment. It makes the brittle parts deterministic:
sample-scope selection (analysis_type / question_types contains "sentiment"),
prompt-to-question integrity checks, citation/UI stripping, sentence/table-cell
unit splitting, brand-alias matching, label validation, and metric aggregation.
The semantic judgment (which units are positive/negative) remains a reviewed
decision that is recorded as an explicit labels file and replayed by `compute`.

Subcommands:
  extract  crawler answers + v8 bank + brand lexicon -> brand-mention units JSON
  compute  units JSON + labels JSON                 -> per-sentence CSV + metrics

Brand sources (extract takes exactly one):
  --aliases 'A,B,C'   single-brand mode, kept for backward compatibility
  --lexicon <json>    multi-brand mode; reads brands[].name/aliases/type so
                      every unit carries the brand it is judged for (competitor
                      sentiment matrix). Brand recognition and citation
                      stripping are geo-metrics' (core find_alias_spans +
                      de_cite_crawl), the same as the visibility metrics.
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

# 品牌识别与去引用只有一份实现，在 geo-metrics（与提及率同口径）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "geo-metrics" / "scripts"))
import de_cite_crawl as de_cite  # noqa: E402
from geo_presales_core.crawler import answer_body  # noqa: E402
from geo_presales_core.lexicon import load_lexicon as core_load_lexicon  # noqa: E402
from geo_presales_core.util import (  # noqa: E402
    case_sensitive_for,
    find_alias_spans,
    read_case_sensitive_aliases,
    resolve_alias_spans,
)



# ---------- de-cite / UI strip (markdown crawler exports) ----------

def strip_answer_text(text: str) -> str:
    """去引用标记、平台组件与商品卡渠道列，和提及率读同一份正文；再去掉残留的 ``[N]`` 角标。"""
    t = de_cite.blank_merchant_columns(de_cite.strip_citations(text))
    return re.sub(r"\[\s*\d+\s*\]", "", t)


def split_units(text: str) -> list[str]:
    """Split cleaned text into judgment units: lines, and table rows into cells."""
    out: list[str] = []
    for line in strip_answer_text(text).split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("|") and line.count("|") >= 2:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # header separator row
            out.extend(c for c in cells if c)
        else:
            out.append(line)
    return out


# ---------- brand alias matching ----------

def brands_in_unit(unit: str, brands: list[dict]) -> list[dict]:
    """单元里认出的品牌（core 匹配 + 跨品牌最长优先消解），按词表顺序返回。"""
    candidates = [
        {**span, "object_id": index}
        for index, brand in enumerate(brands)
        for span in find_alias_spans(unit, brand["aliases"], brand["case_sensitive_aliases"])
    ]
    hit = {span["object_id"] for span in resolve_alias_spans(candidates)}
    return [brand for index, brand in enumerate(brands) if index in hit]


def load_lexicon(path: str) -> list[dict]:
    """品牌词表 → [{name, type, aliases, case_sensitive_aliases}]。读取规则与报告同一份（geo-metrics core lexicon）；
    顶层 case_sensitive_aliases 对所有品牌生效。"""
    entries, _uncertain, status = core_load_lexicon(path)
    if status != "loaded" or not entries:
        raise SystemExit(f"词表 {path} 读不出品牌（{status}）")
    seen: set[str] = set()
    for entry in entries:
        if entry["name"] in seen:
            raise SystemExit(f"词表 {path} 出现重复品牌名：{entry['name']}")
        seen.add(entry["name"])
    case_sensitive = read_case_sensitive_aliases(path)
    return [{"name": e["name"], "type": e["declared_type"], "aliases": e["aliases"],
             "case_sensitive_aliases": case_sensitive_for(e["aliases"], case_sensitive)}
            for e in entries]


# ---------- extract ----------

def load_bank(path: str) -> list[dict]:
    """Load the question bank from JSON (v8 bank) or the flat upload CSV.

    Both forms are normalised to the same record shape: ``user_question``,
    ``analysis_type``, ``tags`` (list), ``question_id``. The CSV has no id
    column, so ids are the 1-based row number padded to 4 digits — the same
    scheme the batch stats engine uses, keeping idx/question_id aligned across
    the two pipelines.
    """
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise SystemExit(f"题库 CSV {path} 没有数据行")
        questions = []
        for i, row in enumerate(rows, start=1):
            tags = [t.strip() for t in str(row.get("tags") or "").split(",") if t.strip()]
            questions.append({
                "question_id": (row.get("question_id") or f"{i:04d}").strip(),
                "user_question": (row.get("query") or row.get("user_question") or "").strip(),
                "analysis_type": row.get("question_types") or row.get("analysis_type") or "",
                "tags": tags,
            })
    else:
        bank = json.load(open(path))
        questions = bank["questions"]
    if not isinstance(questions, list) or not questions:
        raise SystemExit("题库 questions 为空或非数组")
    return questions



# Scrapeless 锚点残留文案（`RivalA5 CarafeGo to product viewer dialog for this item.`），
# 常量与报告渲染、词表挖掘共用 geo-metrics 的 de_cite_crawl。
PRODUCT_VIEWER_NOISE = de_cite.PRODUCT_VIEWER_NOISE


def answer_text(task: dict, platform: str) -> str:
    # 正文字段与报告数据层同一张表（geo-metrics core crawler.answer_body）。
    # 换成空格而非直接删：它粘在商品名后，删掉会把两个名字拼成一个词。
    # ChatGPT 追问表单那一段与提及率同口径删掉（geo-metrics de_cite_crawl.strip_follow_up_form）。
    body = de_cite.strip_follow_up_form(answer_body(task, platform), task.get("follow_up_form"))
    return body.replace(PRODUCT_VIEWER_NOISE, " ")


def answer_prompt(task: dict) -> str:
    """Best-available prompt text for the integrity check, or "" if unknown.

    Some exports omit ``prompt`` entirely (every AIO/overview record, part of
    ChatGPT). The AIO export carries the same question verbatim in the ``q=``
    parameter of ``metadata.rawUrl``, so recover it there. Returning "" means
    "cannot verify", which is reported separately from a genuine mismatch.
    """
    prompt = str(task.get("prompt") or task.get("user_query") or task.get("user_text") or "").strip()
    if prompt:
        return prompt
    meta = task.get("metadata")
    # AI Mode 把同一题面放在顶层 raw_url 的 q= 参数里
    if not isinstance(meta, dict) and task.get("raw_url"):
        meta = {"rawUrl": task.get("raw_url")}
    if isinstance(meta, dict):
        url = str(meta.get("rawUrl") or meta.get("url") or "")
        if url:
            values = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("q") or []
            if values and values[0].strip():
                return values[0].strip()
    return ""



def question_intent(question: dict) -> str:
    tags = [t for t in question.get("tags", []) if t.startswith("Prompt Type: ")]
    return tags[0][len("Prompt Type: "):] if tags else ""


def in_sentiment_scope(question: dict) -> bool:
    analysis = question.get("analysis_type")
    return isinstance(analysis, str) and "sentiment" in analysis


CRAWL_STEM_RE = re.compile(r"^(\d{4})(?:-r(\d+))?$")


def parse_crawl_stem(path: str) -> tuple[int, int | None]:
    """Parse <NNNN>.json or <NNNN>-r<RR>.json into (question idx, repeat)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    match = CRAWL_STEM_RE.fullmatch(stem)
    if not match:
        raise SystemExit(
            f"采集文件名无法解析题号/重复序号：{path}；"
            "期望 <NNNN>.json 或 <NNNN>-r<RR>.json"
        )
    return int(match.group(1)), int(match.group(2)) if match.group(2) is not None else None


def iter_crawl_files(crawl_dir: str):
    """Yield (platform, region, idx, repeat, path) in deterministic path order.

    ``region`` is the ``<REGION>`` directory in ``scraper.<platform>/<REGION>/
    <NNNN>.json`` (e.g. MY / SG). Layouts without a region directory yield None.
    ``repeat`` is None for legacy <NNNN>.json files, or the integer RR from
    <NNNN>-r<RR>.json repeat-sampling files.
    """
    files = sorted(
        glob.glob(os.path.join(crawl_dir, "scraper.*", "*", "*.json"))
        + glob.glob(os.path.join(crawl_dir, "scraper.*", "*.json"))
    )
    if not files:
        raise SystemExit(f"在 {crawl_dir} 下未找到 scraper.*/ 采集文件")
    for path in files:
        rel = os.path.relpath(path, crawl_dir)
        parts = rel.split(os.sep)
        platform = parts[0].split(".", 1)[1]
        region = parts[1] if len(parts) >= 3 else None
        idx, repeat = parse_crawl_stem(path)
        yield platform, region, idx, repeat, path


def resolve_brands(args: argparse.Namespace) -> list[dict]:
    """Build the [{name, type, aliases, case_sensitive_aliases}] brand list from --lexicon or --aliases."""
    if args.lexicon and args.aliases:
        raise SystemExit("--lexicon 与 --aliases 互斥，请只提供其一")
    if args.lexicon:
        return load_lexicon(args.lexicon)
    if not args.aliases:
        raise SystemExit("必须提供 --aliases（单品牌）或 --lexicon（多品牌词表）")
    aliases = [a.strip() for a in args.aliases.split(",") if a.strip()]
    if not aliases:
        raise SystemExit("必须提供至少一个品牌别名（--aliases）")
    name = (args.brand or "").strip() or aliases[0]
    return [{"name": name, "type": args.brand_type or None,
             "aliases": aliases, "case_sensitive_aliases": []}]


def cmd_extract(args: argparse.Namespace) -> None:
    questions = load_bank(args.bank)
    brands = resolve_brands(args)

    units: list[dict] = []
    mismatches: list[str] = []
    unverified: list[str] = []
    scope_answers = 0
    mentioned_answers = 0
    distinct_units = 0
    brand_answers: collections.Counter = collections.Counter()
    for platform, region, idx, repeat, path in iter_crawl_files(args.crawl_dir):
        if not 1 <= idx <= len(questions):
            mismatches.append(f"{platform} {idx:04d}: 编号超出题库范围 1..{len(questions)}")
            continue
        question = questions[idx - 1]
        data = json.load(open(path))
        task = data.get("task_result") or {}
        expected = str(question.get("user_question") or "").strip()
        prompt = answer_prompt(task)
        if prompt:
            if prompt != expected:
                mismatches.append(f"{platform} {idx:04d}: 采集题面与题库不一致")
                continue
        else:
            unverified.append(f"{platform} {idx:04d}")
        if not in_sentiment_scope(question):
            continue
        scope_answers += 1
        matched_here: set[str] = set()
        for unit in split_units(answer_text(task, platform)):
            matched = brands_in_unit(unit, brands)
            if not matched:
                continue
            distinct_units += 1
            for brand in matched:
                matched_here.add(brand["name"])
                units.append({
                    "platform": platform,
                    "region": region,
                    "idx": idx,
                    "repeat": repeat,
                    "question_id": question.get("question_id"),
                    "intent": question_intent(question),
                    "brand": brand["name"],
                    "brand_type": brand["type"],
                    "unit": unit,
                })
        if matched_here:
            mentioned_answers += 1
            for name in matched_here:
                brand_answers[name] += 1

    if mismatches:
        for m in mismatches:
            print("题面完整性失败:", m, file=sys.stderr)
        raise SystemExit("采集数据与题库映射不一致，停止抽取；请先核对题库版本")
    if unverified:
        print(f"警告：{len(unverified)} 条回答缺题面字段且无法从 metadata.rawUrl 还原，"
              f"已按编号映射抽取但未做题面校验（如 {', '.join(unverified[:5])}）",
              file=sys.stderr)

    by_brand = collections.Counter(u["brand"] for u in units)
    by_brand_type = collections.Counter(u["brand_type"] for u in units)

    payload = {
        "meta": {
            "bank": os.path.abspath(args.bank),
            "crawl_dir": os.path.abspath(args.crawl_dir),
            "brand_mode": "lexicon" if args.lexicon else "aliases",
            "lexicon": os.path.abspath(args.lexicon) if args.lexicon else None,
            "aliases": args.aliases,
            "brand_count": len(brands),
            "scope_answers": scope_answers,
            "mentioned_answers": mentioned_answers,
            "unit_count": len(units),
            "distinct_unit_count": distinct_units,
            "unverified_prompt_answers": len(unverified),
            "by_brand_type": dict(by_brand_type),
            "by_brand": dict(by_brand),
            "by_brand_answers": dict(brand_answers),
        },
        "units": units,
    }
    json.dump(payload, open(args.output, "w"), ensure_ascii=False, indent=1)

    print(f"情绪样本回答 {scope_answers} 条 | 提到任一品牌 {mentioned_answers} 条 | "
          f"判读单元 {len(units)} 个（去重句 {distinct_units}）")
    if args.lexicon:
        print(f"待判读品牌 {len(brands)} 个；按品牌分层单元数：")
        for btype, count in sorted(by_brand_type.items(), key=lambda kv: -kv[1]):
            print(f"  {btype or '(未标注类型)':<22} 单元 {count}")
        ranked = sorted(by_brand.items(), key=lambda kv: (-kv[1], kv[0]))
        print("  各品牌明细（单元数降序）：")
        for name, count in ranked:
            print(f"    {name:<22} {count}")
    print(f"写入 {args.output}")


# ---------- compute ----------

def cmd_compute(args: argparse.Namespace) -> None:
    payload = json.load(open(args.units))
    units = payload["units"]
    meta = payload.get("meta", {})
    labels = json.load(open(args.labels))
    positive = set(labels.get("positive", []))
    negative = set(labels.get("negative", []))
    all_brands = {u.get("brand") for u in units if u.get("brand")}
    if len(all_brands) > 1 and not args.brand:
        print(f"警告：本单元集含 {len(all_brands)} 个品牌，正向率将把各品牌混算；"
              f"分品牌指标请用 --brand 逐个运行", file=sys.stderr)

    overlap = positive & negative
    if overlap:
        raise SystemExit(f"同一单元不能既正又负：{sorted(overlap)}")
    out_of_range = [i for i in positive | negative if not 0 <= i < len(units)]
    if out_of_range:
        raise SystemExit(f"标签索引越界：{sorted(out_of_range)}（单元数 {len(units)}）")
    if args.brand:
        wrong_brand = [i for i in positive | negative if units[i].get("brand") != args.brand]
        if wrong_brand:
            raise SystemExit(f"标签含不属于品牌 {args.brand} 的单元：{sorted(wrong_brand)}")

    extracted = []
    for i, unit in enumerate(units):
        if i in positive:
            extracted.append({**unit, "sentiment": "P"})
        elif i in negative:
            extracted.append({**unit, "sentiment": "G"})

    p, g = len(positive), len(negative)
    denom = p + g
    if denom == 0:
        raise SystemExit("没有任何正负句；无法计算正向率（0/0 属于无样本，须如实报告）")

    # 键必须含 region 与 repeat：采集按 scraper.<platform>/<REGION>/NNNN.json 分层，
    # idx 是区域内编号，同一平台的港/新同题回答 idx 相同；重复采样还需区分 repeat。
    docs_with_pg = {(u.get("region", ""), u["platform"], u["idx"], u.get("repeat"))
                    for u in extracted}
    print(f"情绪样本回答 {meta.get('scope_answers', '?')} 条")
    print(f"  提到品牌的回答 {meta.get('mentioned_answers', '?')} 条")
    print(f"  含正负句的回答 {len(docs_with_pg)} 条")
    print(f"提取出的正负句 {denom} 句（正 {p} / 负 {g}）")
    print(f"\n正向率 = {p}/{denom} = {p / denom * 100:.1f}%")
    print(f"负面率 = {g}/{denom} = {g / denom * 100:.1f}%")

    def breakdown(key: str, title: str) -> dict:
        grouped: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for u in extracted:
            grouped[u[key]][u["sentiment"]] += 1
        print(f"\n=== {title} ===")
        result = {}
        for name, counter in sorted(grouped.items()):
            d = counter["P"] + counter["G"]
            rate = counter["P"] / d if d else None
            result[name] = {"P": counter["P"], "G": counter["G"], "positive_rate": rate}
            print(f"  {name:<12} 正={counter['P']:<3} 负={counter['G']:<3} 正向率={rate * 100:.1f}%")
        return result

    by_intent = breakdown("intent", "按 Intent")
    by_platform = breakdown("platform", "按平台")

    with open(args.out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["platform", "region", "idx", "question_id", "intent", "brand",
                         "sentiment", "sentence"])
        for u in extracted:
            writer.writerow([u["platform"], u.get("region", ""), u["idx"], u["question_id"],
                             u["intent"], u.get("brand", ""), u["sentiment"], u["unit"]])
    print(f"\n写入 {args.out_csv}（{denom} 行正负句）")

    if args.out_metrics:
        metrics = {
            "funnel": {
                "scope_answers": meta.get("scope_answers"),
                "mentioned_answers": meta.get("mentioned_answers"),
                "answers_with_pg": len(docs_with_pg),
                "unit_count": len(units),
            },
            "positive": p, "negative": g,
            "positive_rate": p / denom,
            "by_intent": by_intent, "by_platform": by_platform,
        }
        if args.brand:
            metrics["brand"] = args.brand
        json.dump(metrics, open(args.out_metrics, "w"), ensure_ascii=False, indent=1)
        print(f"写入 {args.out_metrics}")


def _load_claims(path: str) -> list[dict]:
    payload = json.load(open(path))
    claims = payload.get("claims") if isinstance(payload, dict) else payload
    if not isinstance(claims, list):
        raise SystemExit(f"{path} 应为 claims 数组，或 {{\"claims\": [...]}}")
    return claims


def _load_mapping(path, key_field: str, value_field: str) -> dict:
    """读聚类映射（claim→attribute 或 attribute→theme）。

    支持两种写法：`{"键": "值"}` 或 `[{"<key_field>": ..., "<value_field>": ...}]`。
    同一键映射到不同值时直接报错——聚类是函数，不允许一对多。
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = list(payload.items())
    elif isinstance(payload, list):
        items = []
        for i, rec in enumerate(payload):
            if not isinstance(rec, dict) or key_field not in rec or value_field not in rec:
                raise SystemExit(f"{path} 第 {i} 条应为 {{{key_field!r}: ..., {value_field!r}: ...}}")
            items.append((rec[key_field], rec[value_field]))
    else:
        raise SystemExit(f"{path} 应为 dict 或 list")
    out: dict[str, str] = {}
    for k, v in items:
        k, v = str(k or "").strip(), str(v or "").strip()
        if not k:
            continue
        if k in out and out[k] != v:
            raise SystemExit(f"{path}: {k!r} 同时映射到 {out[k]!r} 与 {v!r}，聚类结果必须一对一")
        out[k] = v
    return out


def cmd_claims_assemble(args: argparse.Namespace) -> None:
    """把抽取出的 Claim 与两趟聚类结果回装成带完整上下文的记录。

    输入：units.json（extract 产出，提供 evidence_text 与平台/地区/题号/意图上下文）
        + claims-raw.json（抽取环节产出，每条只给 unit_index / brand / claim / sentiment）
        + --claim-attributes（聚类 1：claim → attribute）
        + --attribute-themes（聚类 2：attribute → theme）
    输出：claims.json —— 每条补齐 evidence_text、attribute、theme 与上下文。

    三层各司其职：claim 是标准化语义判断（「价格高」），attribute 是相近 claim 的聚类
    （「Pricing > Expensive」），theme 是 attribute 的再聚类。抽取环节不产出 attribute/theme。
    """
    units = json.load(open(args.units))["units"]
    raw = _load_claims(args.claims)
    claim_attr = _load_mapping(args.claim_attributes, "claim", "attribute")
    attr_theme = _load_mapping(args.attribute_themes, "attribute", "theme")

    out = []
    problems = []
    for i, item in enumerate(raw):
        # 注意：unit_index 可以是 0，不能用 `or ""` 判空（会把 0 当缺失）。
        missing = [f for f in ("brand", "claim", "sentiment")
                   if not str(item.get(f) or "").strip()]
        if item.get("unit_index") is None:
            missing.insert(0, "unit_index")
        if missing:
            problems.append(f"第 {i} 条缺字段:{'、'.join(missing)}")
            continue
        unit_index = item["unit_index"]
        if not isinstance(unit_index, int) or not 0 <= unit_index < len(units):
            problems.append(f"第 {i} 条 unit_index 越界:{unit_index}")
            continue
        unit = units[unit_index]
        if item["brand"] != unit.get("brand"):
            problems.append(
                f"第 {i} 条品牌不符:claim 写 {item['brand']!r}，unit {unit_index} 属于 {unit.get('brand')!r}")
            continue
        direction = str(item["sentiment"]).strip()
        if direction not in ("positive", "negative", "正向", "负向"):
            problems.append(f"第 {i} 条 sentiment 只允许 positive/negative:{direction!r}")
            continue
        claim = str(item["claim"]).strip()
        attribute = claim_attr.get(claim)
        theme = attr_theme.get(attribute) if attribute else None
        if not attribute or not theme:
            continue  # 缺口在下面按「未映射清单」汇总报告，比逐条报更可读
        out.append({
            "unit_index": unit_index,
            "idx": unit.get("idx"),
            "repeat": unit.get("repeat"),
            "region": unit.get("region"),
            "platform": unit.get("platform"),
            "question_id": unit.get("question_id"),
            "intent": unit.get("intent"),
            "brand": item["brand"],
            "brand_type": unit.get("brand_type"),
            "claim": claim,
            "attribute": attribute,
            "theme": theme,
            "sentiment": "positive" if direction in ("positive", "正向") else "negative",
            "evidence_text": unit.get("unit", ""),
        })

    unmapped_claims = sorted({str(it.get("claim") or "").strip() for it in raw
                              if str(it.get("claim") or "").strip()
                              and str(it.get("claim") or "").strip() not in claim_attr})
    if unmapped_claims:
        problems.append(f"{len(unmapped_claims)} 个 claim 没有 attribute 映射：{unmapped_claims[:10]}")
    unmapped_attrs = sorted({v for v in claim_attr.values() if v and v not in attr_theme})
    if unmapped_attrs:
        problems.append(f"{len(unmapped_attrs)} 个 attribute 没有 theme 映射：{unmapped_attrs[:10]}")

    if problems:
        for p in problems[:20]:
            print("校验失败:", p, file=sys.stderr)
        if len(problems) > 20:
            print(f"... 另有 {len(problems) - 20} 条", file=sys.stderr)
        raise SystemExit(f"claims 校验未通过（{len(problems)} 条问题）")
    json.dump({"meta": {"unit_source": args.units, "claim_count": len(out),
                        "claim_attributes_source": args.claim_attributes,
                        "attribute_themes_source": args.attribute_themes},
               "claims": out}, open(args.output, "w"), ensure_ascii=False, indent=1)
    by_dir = collections.Counter(c["sentiment"] for c in out)
    print(f"回装 {len(out)} 条 claim（正向 {by_dir.get('positive', 0)} / 负向 {by_dir.get('negative', 0)}），"
          f"覆盖 {len({c['claim'] for c in out})} 个 claim / {len({c['attribute'] for c in out})} 个 attribute"
          f" / {len({c['theme'] for c in out})} 个 theme")
    print(f"写入 {args.output}")


def _common_substrings(a: str, b: str, min_len: int = 2) -> set[str]:
    """两个主题名共有的 ≥min_len 字片段，用来发现语义重叠（如「智能与安全功能」与「数据隐私与安全」都含「安全」）。"""
    hits: set[str] = set()
    for i in range(len(a)):
        for j in range(i + min_len, len(a) + 1):
            piece = a[i:j]
            if piece in b and not piece.isspace():
                hits.add(piece)
    # 只留最长的片段，短的重叠都是它的子串
    return {h for h in hits if not any(h != other and h in other for other in hits)}


def cmd_claims_theme_audit(args: argparse.Namespace) -> None:
    """检查主题层是否语义独立：一个主题只回答一个买家会横向比较的问题，主题之间不重复、不重叠。

    三条判据见 claim-layer-contract.md「Theme 是什么」第 4 条。这个命令只报问题，
    不替人判断该并到哪一行——语义归并仍由人做。

    报错（退出码 1）：
      * 同一个 attribute 挂在两个主题下（聚类 2 不是一对一）；
      * 两个主题名完全相同，或一个是另一个的子串（后者是前者的子集）。
    提示（不阻断）：
      * 两个主题名共享 ≥2 字的片段，可能语义重叠，例如都含「安全」「画质」；
      * 某个 attribute 的措辞里出现另一个主题的全名（说法串到了别的维度）；
      * 主题里全部 attribute 都是「整体 / 综合 / 总体」这类不成维度的说法。
    """
    payload = json.loads(Path(args.claims).read_text(encoding="utf-8"))
    records = payload.get("claims") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit(f"{args.claims} 应为数组或 {{\"claims\": [...]}}")

    attr_themes: dict[str, set[str]] = collections.defaultdict(set)
    theme_attrs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for rec in records:
        if not isinstance(rec, dict):
            continue
        attribute = str(rec.get("attribute") or "").strip()
        theme = str(rec.get("theme") or "").strip()
        if not attribute or not theme:
            continue
        attr_themes[attribute].add(theme)
        theme_attrs[theme][attribute] += 1

    errors: list[str] = []
    reviews: list[str] = []
    themes = sorted(theme_attrs)

    for attribute, owners in sorted(attr_themes.items()):
        if len(owners) > 1:
            errors.append(f"attribute「{attribute}」同时挂在 {len(owners)} 个主题下：{'、'.join(sorted(owners))}")

    for i, a in enumerate(themes):
        for b in themes[i + 1:]:
            if a == b:
                errors.append(f"主题名重复：{a}")
            elif a in b or b in a:
                big, small = (b, a) if a in b else (a, b)
                errors.append(f"主题「{small}」是「{big}」的子集，两者应并为一行")
            else:
                shared = _common_substrings(a, b)
                if shared:
                    reviews.append(f"主题「{a}」与「{b}」共享「{'」「'.join(sorted(shared))}」，确认不是同一维度")

    for theme in themes:
        for attribute in theme_attrs[theme]:
            for other in themes:
                if other == theme:
                    continue
                if other in attribute:
                    reviews.append(f"attribute「{attribute}」（主题「{theme}」）里出现另一个主题名「{other}」，确认归属")
        if all(any(w in a for w in ("整体", "综合", "总体")) for a in theme_attrs[theme]):
            reviews.append(f"主题「{theme}」下的 attribute 全是「整体 / 综合」这类说法，不成比较维度")

    summary = {
        "themes": len(themes),
        "attributes": len(attr_themes),
        "errors": errors,
        "reviews": reviews,
        "theme_attributes": {t: [a for a, _n in theme_attrs[t].most_common()] for t in themes},
    }
    if args.out:
        Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for line in errors:
        print("不合规:", line, file=sys.stderr)
    for line in reviews:
        print("请复核:", line)
    print(f"{len(themes)} 个主题 / {len(attr_themes)} 个 attribute：不合规 {len(errors)} 项，待复核 {len(reviews)} 项")
    if errors:
        raise SystemExit(f"主题语义检查未通过（{len(errors)} 项）")


def cmd_claims_cluster_list(args: argparse.Namespace) -> None:
    """产出待聚类的去重清单，供两趟聚类用。

    第一趟：`--input claims-raw.json --key claim` → 去重后的 claim 清单（写 claim→attribute）
    第二趟：`--input claim-attributes.json --key attribute` → 去重后的 attribute 清单（写 attribute→theme）

    先把重复项收敛成一份 distinct 清单，聚类才对每个值判一次、并天然自洽。
    """
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    field = args.key
    records = payload.get("claims") if isinstance(payload, dict) else payload
    if isinstance(payload, dict) and records is None:
        # 输入是映射表（如 claim→attribute 的聚类 1 产物）：待聚类的值就是它的 values
        records = [{"value": v} for v in payload.values()]
        field = "value"
    if not isinstance(records, list):
        raise SystemExit(f"{args.input} 应为数组、{{\"claims\": [...]}} 或映射表 {{键: 值}}")
    counter: collections.Counter = collections.Counter()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        value = str(rec.get(field) or "").strip()
        if value:
            counter[value] += 1
    rows = [{"value": k, "count": v}
            for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]
    json.dump({"key": args.key, "distinct": len(rows), "items": rows},
              open(args.output, "w"), ensure_ascii=False, indent=1)
    print(f"{args.key} 去重后 {len(rows)} 项（共 {sum(counter.values())} 条），写入 {args.output}")


def _norm_claim_text(text) -> str:
    """去重用的 claim 文本归一：压空白 + casefold。语义级归一是抽取环节的职责。"""
    return " ".join(str(text or "").split()).casefold()


def cmd_claims_metrics(args: argparse.Namespace) -> None:
    """按设计的统计口径计算 Claim / Attribute / Theme 三层指标。

    口径（2026-09-20 设计定稿）：
      * 最小结构化单位 = Prompt × 平台 × 回答 × Brand × Claim；
      * 同一回答内、同一品牌 × 同一 semantic claim 只计 1 次
        （语义归一由抽取环节完成，这里按 claim 文本兜底去重）；
        同一 Attribute 下不同 Claim 各计一次；**跨回答分别计数**；
      * 正向占比 = 正向 Claim 信号数 ÷ 正负向 Claim 信号数合计；
      * 跨平台先算各平台占比，再对**有有效信号的平台等权平均**，无信号平台不补 0。
    """
    claims = _load_claims(args.claims)
    brands = [b.strip() for b in args.brands.split(",") if b.strip()] if args.brands else \
        sorted({c["brand"] for c in claims})
    if args.brand:
        claims = [c for c in claims if c["brand"] == args.brand]
        brands = [args.brand]

    def answer_key(c: dict) -> tuple:
        return (c.get("region", ""), c.get("platform", ""), c.get("idx"), c.get("repeat"))

    # 回答内去重：同品牌 × 同 semantic claim 在一条回答里只算一次（按 claim 文本兜底）
    signal_keys: set[tuple] = set()
    per_brand_attr: dict[tuple, dict] = {}
    per_theme: dict[tuple, dict] = {}
    per_platform: dict[tuple, dict] = {}
    for c in claims:
        key = (c["brand"], answer_key(c), _norm_claim_text(c.get("claim")), c["sentiment"])
        if key in signal_keys:
            continue
        signal_keys.add(key)
        pk = (c["brand"], c.get("platform", ""))
        bucket = per_platform.setdefault(pk, {"pos": 0, "neg": 0})
        bucket["pos" if c["sentiment"] == "positive" else "neg"] += 1
        attr_key = (c["brand"], c["attribute"], c["sentiment"])
        per_brand_attr[attr_key] = per_brand_attr.get(attr_key, 0) + 1
        theme_key = (c["brand"], c["theme"], c["sentiment"])
        per_theme[theme_key] = per_theme.get(theme_key, 0) + 1

    def rate(pos: int, neg: int) -> str:
        total = pos + neg
        return f"{pos / total * 100:.1f}%" if total else "—"

    by_brand = {}
    for brand in brands:
        pos = sum(v for (b, _t, s), v in per_theme.items() if b == brand and s == "positive")
        neg = sum(v for (b, _t, s), v in per_theme.items() if b == brand and s == "negative")
        platform_rates = []
        for (b, plat), bucket in sorted(per_platform.items()):
            if b != brand or bucket["pos"] + bucket["neg"] == 0:
                continue
            platform_rates.append(bucket["pos"] / (bucket["pos"] + bucket["neg"]))
        by_brand[brand] = {
            "signal_total": pos + neg,
            "positive_signals": pos,
            "negative_signals": neg,
            "pos_rate": rate(pos, neg),
            "platforms_with_signal": len(platform_rates),
            "pos_rate_cross_platform": (
                f"{sum(platform_rates) / len(platform_rates) * 100:.1f}%" if platform_rates else "—"),
            "by_platform": {
                plat: {"positive": b["pos"], "negative": b["neg"], "pos_rate": rate(b["pos"], b["neg"])}
                for (brand_name, plat), b in sorted(per_platform.items()) if brand_name == brand
            },
            "by_attribute": sorted(
                ({"attribute": a, "sentiment": s, "occurrence": v}
                 for (b, a, s), v in per_brand_attr.items() if b == brand),
                key=lambda x: (-x["occurrence"], x["attribute"])),
            "by_theme": sorted(
                ({"theme": t, "sentiment": s, "occurrence": v}
                 for (b, t, s), v in per_theme.items() if b == brand),
                key=lambda x: x["theme"]),
        }

    metrics = {
        "brands": brands,
        "claim_total": len(claims),
        "deduped_signal_total": len(signal_keys),
        "by_brand": by_brand,
    }
    json.dump(metrics, open(args.out_metrics, "w"), ensure_ascii=False, indent=1)
    for brand in brands:
        s = by_brand[brand]
        print(f"{brand}: 信号 {s['signal_total']}（正 {s['positive_signals']} / 负 {s['negative_signals']}）"
              f" 正向占比 {s['pos_rate']}，跨平台等权 {s['pos_rate_cross_platform']}"
              f"（有信号平台 {s['platforms_with_signal']} 个）")
    print(f"写入 {args.out_metrics}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="抽取各品牌的判读单元（单品牌或词表多品牌）")
    p_extract.add_argument("--bank", required=True, help="题库：v8 JSON 或 upload CSV（query/question_types/tags）")
    p_extract.add_argument("--crawl-dir", required=True, help="采集目录（含 scraper.*/<区域>/NNNN.json）")
    p_extract.add_argument("--aliases", default=None,
                           help="单品牌模式：逗号分隔别名，须含当地文字转写，如 'Ybrand,某平台,บียู,บียู'")
    p_extract.add_argument("--lexicon", default=None,
                           help="多品牌模式：品牌词表 JSON（brands[].name/aliases/type），每条单元带 brand")
    p_extract.add_argument("--brand", default=None, help="单品牌模式下写入 brand 字段的品牌名（默认取首个别名）")
    p_extract.add_argument("--brand-type", default=None, dest="brand_type",
                           help="单品牌模式下写入 brand_type 字段的类型（可选）")
    p_extract.add_argument("--output", required=True)

    p_compute = sub.add_parser("compute", help="按人工标签计算正负指标")
    p_compute.add_argument("--units", required=True, help="extract 产出的单元 JSON")
    p_compute.add_argument("--labels", required=True,
                           help='标签 JSON：{"positive": [索引...], "negative": [索引...]}')
    p_compute.add_argument("--brand", default=None,
                           help="只计算该品牌的单元（多品牌单元集分品牌出指标时使用）")
    p_compute.add_argument("--out-csv", required=True)
    p_compute.add_argument("--out-metrics", default=None)

    # Claim 层（四层结构：evidence_text → Claim → Attribute → Theme，后两层各由一趟聚类产出）
    p_assemble = sub.add_parser("claims-assemble",
                                help="把抽取的 Claim 与两趟聚类结果回装成带证据与上下文的记录")
    p_assemble.add_argument("--units", required=True, help="extract 产出的单元 JSON")
    p_assemble.add_argument("--claims", required=True,
                            help="抽取环节产出的 claims-raw JSON（unit_index/brand/claim/sentiment）")
    p_assemble.add_argument("--claim-attributes", required=True,
                            help="聚类 1 产出：claim → attribute 映射（dict 或 [{claim, attribute}]）")
    p_assemble.add_argument("--attribute-themes", required=True,
                            help="聚类 2 产出：attribute → theme 映射（dict 或 [{attribute, theme}]）")
    p_assemble.add_argument("--output", required=True)

    p_cl = sub.add_parser("claims-cluster-list",
                          help="产出待聚类的去重清单（聚类 1 出 claim 清单，聚类 2 出 attribute 清单）")
    p_cl.add_argument("--input", required=True, help="claims-raw.json 或 claim-attributes.json")
    p_cl.add_argument("--key", required=True, help="取值字段：第一趟 claim，第二趟 attribute")
    p_cl.add_argument("--output", required=True)

    p_ta = sub.add_parser("claims-theme-audit",
                          help="检查主题是否语义独立（一对一、不重复、不互为子集），只报不改")
    p_ta.add_argument("--claims", required=True, help="claims-assemble 产出的 claims JSON")
    p_ta.add_argument("--out", default=None, help="把主题与 attribute 对照写进 JSON")

    p_cm = sub.add_parser("claims-metrics", help="按 Claim 信号口径统计正负与跨平台等权占比")
    p_cm.add_argument("--claims", required=True, help="claims-assemble 产出的 claims JSON")
    p_cm.add_argument("--brands", default=None, help="逗号分隔的品牌；缺省取 claim 里出现的全部品牌")
    p_cm.add_argument("--brand", default=None, help="只统计该品牌")
    p_cm.add_argument("--out-metrics", required=True)

    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "compute":
        cmd_compute(args)
    elif args.command == "claims-assemble":
        cmd_claims_assemble(args)
    elif args.command == "claims-cluster-list":
        cmd_claims_cluster_list(args)
    elif args.command == "claims-theme-audit":
        cmd_claims_theme_audit(args)
    else:
        cmd_claims_metrics(args)


if __name__ == "__main__":
    main()
