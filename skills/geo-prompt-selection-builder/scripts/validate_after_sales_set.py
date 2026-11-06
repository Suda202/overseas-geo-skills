#!/usr/bin/env python3
"""Validate a selection Prompt bank (选词题库) against the gates in references/output-contract.md.

Only the current structure is supported. A bank written in an older structure (see legacy_markers) is refused
with "unsupported old structure" and exit code 2; old banks are kept as they are and not validated.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from itertools import combinations
from pathlib import Path


INTENTS = {
    "Discovery",
    "Competitor",
    "Alternatives",
    "Evaluation",
    "Verification",
    "Category Awareness",
    "Accuracy",
    "Information",
    "Trust",
    "Transactional",
    "Support",
}
# Eight selection types since 2026-11-06 (Suda): Discovery (incl. shortlist), Information (问题解决), Evaluation (评估,
# incl. capability questions), Competitor, Alternatives, Trust (验证: reliability / complaints), Transactional (交易),
# Support (售后: names the brand / model). No journey stage on new banks.
# Verification and Accuracy are two distinct intents (Suda 2026-10-16): Verification
# covers a capability AI does not recognise, Accuracy a fact AI states wrongly. No aliasing.
# Information (问题解决, after-sales only, Suda 2026-10-19; client label renamed and scope narrowed on 2026-10-26):
# a buyer asking how to solve a problem or reach a goal; AI answers with advice, not a candidate
# list; only own-domain citation is read. Pure knowledge questions are not this type.
LIFECYCLE_STATES = {
    "hypothesis",
    "customer_confirmed",
    "locked",
    "formal_baseline",
    "active",
}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


# ---------- wording checks: brand leakage and language are errors, the rest are warnings ----------

LANGUAGE_SCRIPTS = {
    "en": "latin", "english": "latin", "es": "latin", "spanish": "latin",
    "fr": "latin", "french": "latin", "de": "latin", "german": "latin",
    "pt": "latin", "portuguese": "latin", "it": "latin", "italian": "latin",
    "nl": "latin", "dutch": "latin", "id": "latin", "indonesian": "latin",
    "ms": "latin", "malay": "latin", "vi": "latin", "vietnamese": "latin",
    "th": "thai", "thai": "thai",
    "zh": "han", "chinese": "han",
    "ja": "japanese", "japanese": "japanese",
    "ko": "hangul", "korean": "hangul",
    "ar": "arabic", "arabic": "arabic",
    "ru": "cyrillic", "russian": "cyrillic",
}
LATIN_LANGUAGE_NAMES = {
    "en": "English", "english": "English", "es": "Spanish", "spanish": "Spanish",
    "fr": "French", "french": "French", "de": "German", "german": "German",
    "pt": "Portuguese", "portuguese": "Portuguese", "it": "Italian", "italian": "Italian",
}
# Function words per language; two or more hits with a clear lead identify the language.
LATIN_STOPWORDS = {
    "English": set("the and for what which best how is to with of that are can my".split()),
    "Spanish": set("el la los las para que qué cual cuál mejor cómo como con de en y es una un mi".split()),
    "French": set("le la les pour quel quelle meilleur comment avec des et est une un mon du".split()),
    "German": set("der die das für welche beste wie mit und ist ein eine mein den".split()),
    "Portuguese": set("o os para qual melhor como com de e é uma um meu do da".split()),
    "Italian": set("il lo gli per quale migliore come con di e è una un mio del".split()),
}
CONTENT_STOPWORDS = set(
    "a an the of for to in on with and or is are be can i my me we our what which how do does "
    "should best good top who where when why vs versus that this it if at by from as any".split()
)
MARKET_CURRENCIES = [
    (r"\b(us|usa|united states|america)\b", {"USD"}),
    (r"\b(uk|united kingdom|britain|england|scotland|wales)\b", {"GBP"}),
    (r"\b(thailand)\b", {"THB"}),
    (r"\b(singapore)\b", {"SGD", "USD"}),
    (r"\b(malaysia)\b", {"MYR"}),
    (r"\b(japan)\b", {"JPY"}),
    (r"\b(india)\b", {"INR"}),
    (r"\b(australia)\b", {"AUD"}),
    (r"\b(canada)\b", {"CAD"}),
    (r"\b(germany|france|spain|italy|ireland|netherlands|portugal|austria|belgium|eu|europe)\b", {"EUR"}),
]
CURRENCY_PATTERNS = [
    ("SGD", r"S\$|\bSGD\b"), ("AUD", r"A\$|\bAUD\b"), ("CAD", r"C\$|\bCAD\b"),
    ("USD", r"(?<![SAC])\$|\bUSD\b"), ("GBP", r"£|\bGBP\b"), ("EUR", r"€|\bEUR\b"),
    ("THB", r"฿|บาท|\bTHB\b"), ("MYR", r"\bRM\s?\d|\bMYR\b"), ("JPY", r"¥|\bJPY\b"),
    ("INR", r"₹|\bINR\b"),
]
# A Discovery Prompt must ask for candidates. "How do I fix X" questions get
# advice back and no brand list (Pbrand 2026-10-15: 0 brands in 5 ChatGPT runs).
# The rule lives in shared/scripts/prompt_gates.py so both prompt validators agree.
_SHARED_SCRIPTS = Path(__file__).resolve().parents[2] / "shared" / "scripts"
if str(_SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SHARED_SCRIPTS))
import prompt_gates as _prompt_gates  # noqa: E402
import scope_gates as _scope_gates  # noqa: E402
# Cross-Topic slice tags (Suda 2026-11-03): one rule for export and the W62/W63 warnings.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from tag_dimensions import tag_plan as _tag_plan  # noqa: E402

# Evidence source families for the diversity warning. Classification is by
# keyword because evidence_refs are free strings; refs that match nothing are
# 未分类 and the check is skipped when they dominate (cannot judge diversity).
EVIDENCE_SOURCE_FAMILIES = [
    ("答案层", re.compile(r"答案层|已采集回答|AI 回答|AI 答案|fan-?out|search_model_queries|related_queries|候选基线|baseline answer", re.I)),
    ("搜索数据", re.compile(r"\bGSC\b|Search Console|\bPAA\b|People Also Ask|相关搜索|自动补全|autocomplete|搜索词|搜索数据|关键词|keyword|Google Trends|站内搜索|site.?search", re.I)),
    ("评价", re.compile(r"评价|评论|\breviews?\b|Trustpilot|G2\b|Capterra|TrustRadius|Amazon(?!.cn)|RTINGS|Wirecutter|App Store|Google Play", re.I)),
    ("社区", re.compile(r"社区|论坛|\bReddit\b|r/|Pantip|Dek-D|Quora|forum|Facebook 群|LinkedIn 讨论|MyDramaList|Naver", re.I)),
    ("一手记录", re.compile(r"销售|CRM|客服|工单|访谈|win.?loss|流失|成交|证言|案例|support ticket|sales call|churn", re.I)),
    ("客户确认", re.compile(r"客户确认|品牌方确认|客户提供|品牌方提供|client confirm", re.I)),
    ("官网与竞品页", re.compile(r"官网|official site|竞品.{0,6}(页|站)|对比页|alternatives page|spec sheet|vs page", re.I)),
]


def evidence_source_family(ref: str) -> str:
    for family, pattern in EVIDENCE_SOURCE_FAMILIES:
        if pattern.search(ref):
            return family
    return "未分类"


def language_key(value: object) -> str:
    raw = str(value or "").strip().casefold()
    if raw in LANGUAGE_SCRIPTS:
        return raw
    head = re.split(r"[-_ /(]", raw, maxsplit=1)[0]
    return head if head in LANGUAGE_SCRIPTS else ""


def char_script(ch: str) -> str:
    name = unicodedata.name(ch, "")
    for prefix, script in (
        ("LATIN", "latin"), ("THAI", "thai"), ("CJK", "han"), ("HIRAGANA", "kana"),
        ("KATAKANA", "kana"), ("HANGUL", "hangul"), ("ARABIC", "arabic"), ("CYRILLIC", "cyrillic"),
    ):
        if name.startswith(prefix):
            return script
    return "other"


def expected_script_share(text: str, script: str) -> float | None:
    counts = Counter(char_script(ch) for ch in text if ch.isalpha())
    total = sum(counts.values())
    if total < 4:
        return None
    hit = counts["han"] + counts["kana"] if script == "japanese" else counts[script]
    return hit / total


def latin_words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFD", str(text).casefold())
    folded = "".join(ch for ch in folded if not unicodedata.category(ch).startswith("M"))
    return re.findall(r"[a-z0-9£$€%]+", folded)


def detect_latin_language(text: str) -> str | None:
    tokens = re.findall(r"[a-zà-ÿ]+", str(text).casefold())
    if len(tokens) < 4:
        return None
    scores = sorted(
        ((name, sum(token in words for token in tokens)) for name, words in LATIN_STOPWORDS.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    (best, top), (_, second) = scores[0], scores[1]
    return best if top >= 2 and top - second >= 2 else None


def similarity_units(text: str, script: str) -> set[str]:
    if script == "latin":
        stem = lambda w: re.sub(r"(est|ing|ed|er|es|s)$", "", w) if len(w) > 5 else w
        return {stem(w) for w in latin_words(text) if w not in CONTENT_STOPWORDS and len(w) > 1}
    compact = "".join(ch for ch in str(text).casefold() if ch.isalnum())
    return {compact[i:i + 3] for i in range(max(0, len(compact) - 2))}


def entity_terms(config: dict) -> list[str]:
    """Target brand, aliases and every competitor name in competitor_selection."""
    terms = [config.get("brand_name"), *(config.get("aliases") or []), *(config.get("competitors") or [])]

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("name"), str):
                terms.append(node["name"])
            for value in node.values():
                if isinstance(value, (list, dict)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    terms.append(item)
                else:
                    walk(item)

    walk(config.get("competitor_selection") or {})
    variants: list[str] = []
    for term in terms:
        term = str(term or "").strip()
        if not term or len(term) > 60:
            continue
        variants.append(term)
        short = re.sub(r"\s*\([^)]*\)\s*", " ", term).strip()
        if short and short != term:
            variants.append(short)
        variants.extend(inner.strip() for inner in re.findall(r"\(([^()]*)\)", term) if inner.strip())
    return sorted({v for v in variants if len(v) >= 2}, key=str.casefold)


def mentions_entity(text: str, term: str) -> bool:
    if all(ch.isascii() for ch in term):
        tokens = re.findall(r"[a-z0-9]+", term.casefold())
        if not tokens:
            return False
        pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]{0,2}".join(map(re.escape, tokens)) + r"(?![a-z0-9])"
        return re.search(pattern, str(text).casefold()) is not None
    compact = lambda s: "".join(ch for ch in str(s).casefold() if ch.isalnum())
    return compact(term) in compact(text)


def wording_checks(
    config: dict,
    questions: list[dict],
    intents: dict[int, str],
    errors: list[str],
    warnings: list[str],
) -> None:
    collection = config.get("collection_config") or {}
    lang = language_key(collection.get("language") or config.get("language"))
    script = LANGUAGE_SCRIPTS.get(lang, "")
    latin_name = LATIN_LANGUAGE_NAMES.get(lang)
    terms = entity_terms(config)

    def allowed_currencies(region: str) -> set[str] | None:
        allowed: set[str] = set()
        for pattern, codes in MARKET_CURRENCIES:
            if re.search(pattern, region.casefold()):
                allowed |= codes
        return allowed or None

    for row in questions:
        qid = row.get("question_id")
        text = str(row.get("user_question") or "").strip()
        if not text:
            continue
        if intents.get(id(row)) == "Discovery":
            named = [term for term in terms if mentions_entity(text, term)]
            if named:
                fail(f"{qid}: Discovery Prompt names a brand or competitor {named}", errors)
            detected = detect_latin_language(text)
            # A query written in another language (a wording slip the language check
            # reports separately) is not judged by the English candidate gate.
            english = (latin_name == "English" and detected in (None, "English")) or (not lang and detected == "English")
            if english and not _prompt_gates.requests_candidates(text):
                fail(f"{qid}: Discovery Prompt asks no candidate question (which / best / "
                     f"recommend / where to buy ...); AI answers it with advice, not a brand list", errors)
        if script:
            share = expected_script_share(text, script)
            if share is not None and share < 0.5:
                fail(f"{qid}: query is not written in the collection language {lang!r} "
                     f"({share:.0%} of letters in the expected script)", errors)
        if latin_name:
            detected = detect_latin_language(text)
            if detected and detected != latin_name:
                warnings.append(f"[W32] {qid}: reads as {detected}, but the collection language is {latin_name}")
        if script == "latin":
            words = latin_words(text)
            has_mark = "?" in text or "？" in text
            if len(words) <= 4:
                warnings.append(f"[W32] {qid}: too short to carry a buyer situation ({len(words)} words)")
            elif len(words) <= 6 and not has_mark and text == text.casefold():
                warnings.append(f"[W32] {qid}: reads like a search keyword, not a question asked to an AI")
            if len(words) > 40:
                warnings.append(f"[W32] {qid}: over-constrained ({len(words)} words); check it is not a one-off niche")
        if text.count("?") + text.count("？") > 1:
            warnings.append(f"[W32] {qid}: asks more than one question; split so each Prompt tests one decision")
        allowed = allowed_currencies(str(row.get("region") or collection.get("market") or ""))
        if allowed:
            used = {code for code, pattern in CURRENCY_PATTERNS if re.search(pattern, text)}
            if used - allowed:
                warnings.append(f"[W32] {qid}: uses currency {sorted(used - allowed)} outside the market's {sorted(allowed)}")

    # Near-duplicates. Words shared by most of the bank (the category name) say
    # nothing about the decision, so they are dropped before comparing.
    units = {row.get("question_id"): similarity_units(row.get("user_question") or "", script or "latin")
             for row in questions}
    df = Counter(unit for unit_set in units.values() for unit in unit_set)
    common = {unit for unit, count in df.items() if count >= max(3, 0.4 * len(questions))}
    # Two Prompts that differ only by which name the buyer uses for the category
    # (config.category_aliases) test the same decision in different words on purpose.
    alias_units: set[str] = set()
    for alias in config.get("category_aliases") or []:
        if isinstance(alias, str):
            alias_units |= similarity_units(alias, script or "latin")
    for a, b in combinations(questions, 2):
        ua, ub = units[a.get("question_id")] - common, units[b.get("question_id")] - common
        if not ua or not ub:
            continue
        if alias_units and (ua ^ ub) and (ua ^ ub) <= alias_units:
            continue
        sim = len(ua & ub) / len(ua | ub)
        same_slice = (
            a.get("topic_id") == b.get("topic_id")
            and intents.get(id(a)) == intents.get(id(b))
            and str(a.get("attribute_ref") or "").strip()
            and a.get("attribute_ref") == b.get("attribute_ref")
        )
        if sim >= 0.6:
            warnings.append(f"[W8b] {a.get('question_id')} / {b.get('question_id')}: near-duplicate wording "
                            f"({sim:.0%} overlap); keep both only if the purchase decision differs")
        elif same_slice and sim >= 0.35:
            warnings.append(f"[W8b] {a.get('question_id')} / {b.get('question_id')}: same Topic, intent and attribute "
                            f"with overlapping wording ({sim:.0%}); check they test different decisions")


def scope_checks(
    config: dict,
    questions: list[dict],
    errors: list[str],
    warnings: list[str],
    intents: dict[int, str] | None = None,
) -> None:
    """Gates 36–37 (warnings): conditions with no quote and no written basis; one decision asked twice.

    Both need the bank's buyer-quote table (`config.buyer_quotes`, the 需求信号
    输入编号 / 原话 / 约束 columns); without it the scope gate cannot read the
    约束 column and says so. A Prompt's `constraints` list is what both gates
    compare; see shared/scripts/scope_gates.py.
    """
    # A Competitor verdict hinges on a scenario; with no use case AI answers "it
    # depends". Independent of buyer_quotes, so it runs before the early return below.
    for row in questions:
        if (intents or {}).get(id(row)) == "Competitor" and not row.get("constraints"):
            fail(f"{row.get('question_id')}: Competitor Prompt has no use case (empty constraints); without one "
                 f"AI answers \"it depends\" instead of a verdict — name the scenario the verdict hinges on", errors)
    quote_constraints, quote_texts = _scope_gates.quote_index(config)
    if not quote_constraints:
        warnings.append("[W36] no config.buyer_quotes (需求信号): gates 36–37 "
                        "(conditions without a basis, one decision asked twice) were skipped")
        return
    base = config.get("base_conditions") or []
    unknown: dict[str, list[str]] = {}
    for row in questions:
        qid = str(row.get("question_id"))
        result = _scope_gates.unsupported_conditions(row, quote_constraints, quote_texts, base)
        if result["unknown_refs"]:
            unknown[qid] = result["unknown_refs"]
        outside = result["keywords"] + [f"数字 {n}" for n in result["numbers"]]
        if outside:
            # Warning since 2026-10-30 (Suda): quote research is never complete, so a
            # condition may rest on other evidence — written in condition_basis.
            warnings.append(f"[W36] {qid}: condition outside the cited evidence {outside}; cite the 需求信号 it comes from in "
                            f"evidence_refs, write its basis in condition_basis "
                            f"(search data, pre-run answer, competitor filter, buyer common sense), or drop it from the Prompt")
    if unknown:
        shown = ", ".join(f"{q} {refs}" for q, refs in list(unknown.items())[:6])
        warnings.append(f"[W36] evidence_refs not in config.buyer_quotes ({len(unknown)} Prompts): {shown}"
                        f"{' …' if len(unknown) > 6 else ''}")
    for group in _scope_gates.repeated_decisions(questions, quote_constraints):
        warnings.append(f"[W37] {' / '.join(group)}: same Topic, attribute and evidence-backed constraints — one "
                        f"purchase decision asked {len(group)} times; keep one, or give the others a "
                        f"condition their evidence carries")


def audience_values(row: dict) -> list[str]:
    value = row.get("audience")
    items = value if isinstance(value, (list, tuple)) else [value]
    return [str(item).strip() for item in items if str(item or "").strip()]


def audience_checks(
    config: dict,
    questions: list[dict],
    warnings: list[str],
    intents: dict[int, str],
) -> None:
    """Gate 39: a Prompt filed under a non-base audience shows who is asking, stated or implied.

    A segment exists because it changes the candidates, the criteria or the
    answer; a Prompt that does not say who is asking is answered for the
    generic buyer, so its audience label measures nothing. Warning only:
    matching the buyer's own words is a heuristic.
    """
    base = {str(item).strip() for item in config.get("base_conditions") or []} | {"通用"}
    raw_terms = config.get("audience_terms")
    terms = raw_terms if isinstance(raw_terms, dict) else {}

    def fold(text: object) -> str:
        return " ".join(str(text or "").casefold().replace("-", " ").split())

    used: set[str] = set()
    unnamed: list[str] = []
    rows = slice_index(config)
    for row in questions:
        own = audience_values(row) or audience_values(rows.get(str(row.get("slice_ref") or "").strip()) or {})
        audiences = [a for a in own if a not in base]
        if not audiences:
            continue
        used.update(audiences)
        if intents.get(id(row)) in {"Verification", "Accuracy"} or str(row.get("audience_implicit") or "").strip():
            continue
        registered = [fold(term) for a in audiences for term in (terms.get(a) or []) if fold(term)]
        if not registered:
            continue  # reported once below as an audience with no terms
        query = fold(row.get("user_question"))
        if not any(term in query for term in registered):
            unnamed.append(f"{row.get('question_id')}({'/'.join(audiences)})")
    if not used:
        return
    if not terms:
        # No config.audience_terms: gate 39 becomes a manual check (output-contract.md → 人工检查),
        # not a warning (Suda 2026-11-02 审核清单 D3).
        return
    missing = sorted(a for a in used if not [t for t in terms.get(a) or [] if fold(t)])
    if missing:
        warnings.append(f"[W39] audiences with no entry in config.audience_terms ({len(missing)}): {', '.join(missing)}")
    if unnamed:
        warnings.append(f"[W39] Prompts filed under a non-base audience whose wording neither states nor implies it ({len(unnamed)}): "
                        f"{', '.join(unnamed[:8])}{' …' if len(unnamed) > 8 else ''}; register the implying term in "
                        f"config.audience_terms, state who is asking in the buyer's words, or record audience_implicit")


def normalized_intent(row: dict, errors: list[str]) -> str:
    """The Prompt's type: its prompt_type field (unknown values are reported by the caller)."""
    return str(row.get("prompt_type") or "").strip()


# ---------- per-Prompt metadata ----------

# Supported row types: the eight selection types (2026-11-06).
REGISTERED_TYPES = {"Discovery", "Information", "Evaluation", "Competitor", "Alternatives", "Trust", "Transactional", "Support"}
# The mention-rate KPI reads these types (Suda 2026-11-02).
KPI_INTENTS = {"Discovery"}
PROMPT_FIELDS = ("attribute_ref", "constraint_type")
# A Prompt states the constraint it tests (attribute_ref); target customer and use scenario are read from its
# matrix row (config.slices).
REQUIRED_STAGED_FIELDS = ("attribute_ref",)
# No-condition Discovery Prompts are not written by default (Suda 2026-10-29): a bare category
# question is owned by category leaders. Judged from constraint_type.
LOW_CONDITION_VALUES = {"无限定", "无限定条件", "低条件", "none", "unconstrained", "no_condition"}
FORMAL_LIFECYCLES = {"locked", "formal_baseline", "active"}
REVIEW_STATUSES = ("待审核", "已批准", "需修改")
REVIEW_ALIASES = {
    **{status: status for status in REVIEW_STATUSES},
    # 提示词库 状态 also carries 正式 (locked) and 停测 (dropped); both were approved first.
    "正式": "已批准", "停测": "已批准",
}


def lifecycle_after_review(config: dict) -> bool:
    """The brand party has reviewed 提示词库 once the scope is confirmed."""
    return config.get("lifecycle_status") in {"customer_confirmed", *FORMAL_LIFECYCLES}


def is_blank(value: object) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return not any(not is_blank(item) for item in (value.values() if isinstance(value, dict) else value))
    return not str(value or "").strip()


def normalize_fields(row: dict) -> dict:
    """The Prompt's metadata fields; a field absent from the Prompt is None, present but empty is ""."""
    return {field: (str(row[field]).strip() if not is_blank(row[field]) else "") if field in row else None
            for field in PROMPT_FIELDS}


def slice_index(config: dict) -> dict[str, dict]:
    """config.slices by slice_id; empty when the bank has no matrix rows."""
    slices = config.get("slices")
    if not isinstance(slices, list):
        return {}
    return {str(r.get("slice_id") or "").strip(): r for r in slices
            if isinstance(r, dict) and str(r.get("slice_id") or "").strip()}


def attribute_plan(config: dict) -> list[dict]:
    """config.attribute_plan (the 约束条件 list) as row objects; empty when absent or not a list of objects."""
    plan = config.get("attribute_plan") or []
    return plan if isinstance(plan, list) and all(isinstance(entry, dict) for entry in plan) else []


def report_rows(message: str, rows: list[dict], total: int, hard: bool,
                errors: list[str], warnings: list[str], code: str = "W33") -> None:
    """One line per check over Prompts: an error when hard, otherwise a warning under its code."""
    if not rows:
        return
    ids = ", ".join(str(r.get("question_id")) for r in rows[:6]) + (" …" if len(rows) > 6 else "")
    text = f"{message} ({len(rows)} of {total}: {ids})"
    if hard:
        errors.append(text)
    else:
        warnings.append(f"[{code}] {text}")


def field_contract_checks(
    config: dict,
    questions: list[dict],
    intents: dict[int, str],
    errors: list[str],
    warnings: list[str],
) -> None:
    formal = config.get("lifecycle_status") in FORMAL_LIFECYCLES
    fields = {id(row): normalize_fields(row) for row in questions}
    for field in REQUIRED_STAGED_FIELDS:
        # attribute_ref may be empty on a category-baseline Prompt; it only has to be stated.
        missing = [r for r in questions if fields[id(r)][field] is None]
        report_rows(f"missing {field} (required before lock)", missing, len(questions), formal, errors, warnings)

    # Bare category questions are written only when the brand party asks for the head term
    # (Suda 2026-10-29; the per-Topic low-condition anchor of 2026-10-22 is retired).
    constraint_of = lambda r: str(fields[id(r)].get("constraint_type") or "").strip().casefold()
    bare = [str(r.get("question_id")) for r in questions
            if intents.get(id(r)) == "Discovery" and constraint_of(r) in LOW_CONDITION_VALUES]
    if bare:
        warnings.append(
            f"[W54] no-condition Discovery Prompts ({len(bare)}): {', '.join(bare)}; a bare category question is "
            "written only when the brand party asks for that head term — say so in its reason (selection-rules.md → 5. 两类不写的题)"
        )


def monitored_set(data: dict) -> str:
    config = data.get("config") or {}
    topics = [
        (topic.get("topic_id"), topic.get("topic"))
        for topic in config.get("topics") or []
    ]
    fields = (
        "question_id",
        "topic_id",
        "user_question",
        "monitoring_prompt",
        "zh_translation",
        "region",
        "prompt_type",
        "intent_key",
        "tags",
        "analysis_type",
        "formal_visibility_eligible",
    )
    questions = []
    for row in data.get("questions") or []:
        selected = {field: row.get(field) for field in fields}
        if isinstance(selected["tags"], list):
            selected["tags"] = sorted(selected["tags"], key=str)
        questions.append(selected)
    return json.dumps(
        {
            "topics": sorted(topics, key=lambda topic: (str(topic[0]), str(topic[1]))),
            "questions": sorted(questions, key=lambda row: str(row["question_id"])),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


# Row tiers: 高 / 中 / 低.
TIER_INDEX = {"高": 0, "中": 1, "低": 2}
TOPIC_PRIORITIES = ("高", "中", "低")
CHANGEABILITY = ("高", "中", "低", "待试跑")
BUSINESS_GOALS = ("发现型可见度", "竞争定位", "品牌呈现", "声誉与信任")


def goal_checks(config: dict, questions: list[dict], intents: dict[int, str], warnings: list[str],
                decision_rows: list[str]) -> None:
    """Gates 49–52 (Suda 2026-11-02 审核清单 B2): the brand party's goals decide which Prompt types are written.

    config.business_goals = {selected: [goals in the brand party's order], information_named: bool}. Presales banks
    Alternatives belong to 竞争定位.
    Verification and Accuracy are outside selection banks and rejected by the main type check. Transactional and
    Support belong to no goal yet (selection-rules.md → 1) and always warn when written. decision_rows: the 高 / 中
    对比 rows, named by gate 50.
    """
    goals = config.get("business_goals")
    selected = goals.get("selected") if isinstance(goals, dict) else None
    if (not isinstance(goals, dict) or not isinstance(selected, list)
            or any(str(g).strip() not in BUSINESS_GOALS for g in selected)):
        warnings.append("[W49] config.business_goals missing or malformed: write {selected: [the goals the brand party "
                        f"picked, in its order, from {' / '.join(BUSINESS_GOALS)}], information_named: true / false}} "
                        "so the goal-to-type checks (gates 50–52) can run")
        return
    chosen = {str(g).strip() for g in selected}
    named_info = goals.get("information_named") is True
    by_type: dict[str, list[str]] = {}
    for q in questions:
        by_type.setdefault(intents.get(id(q)) or "", []).append(str(q.get("question_id")))
    if "竞争定位" in chosen and not by_type.get("Competitor"):
        shown = ", ".join(decision_rows[:8]) + (" …" if len(decision_rows) > 8 else "")
        warnings.append("[W50] business_goals selects 竞争定位 but the bank holds no Competitor Prompt "
                        f"(高 / 中 对比 rows: {shown or 'none opened'}); write the 对比 Prompts the step-1 "
                        "evidence supports, or record why none is written")
    if "声誉与信任" in chosen and not (by_type.get("Evaluation") or by_type.get("Trust")):
        warnings.append("[W51] business_goals selects 声誉与信任 but the bank holds no Evaluation or Trust Prompt; write the "
                        "评估 / 验证 Prompts the step-1 evidence supports, or record why none is written")
    unasked = [(t, label) for t, label, ok in (
        ("Competitor", "竞争定位", "竞争定位" in chosen),
        ("Alternatives", "竞争定位", "竞争定位" in chosen),
        ("Evaluation", "声誉与信任", "声誉与信任" in chosen),
        ("Trust", "声誉与信任", "声誉与信任" in chosen),
        ("Information", "information_named", named_info),
        ("Transactional", "交易（未开放）", False),
        ("Support", "售后（未开放）", False),
    ) if not ok and by_type.get(t)]
    for t, label in unasked:
        ids = by_type[t]
        warnings.append(f"[W52] {t} Prompts written without the goal {label} in business_goals ({len(ids)}): "
                        f"{', '.join(ids[:8])}{' …' if len(ids) > 8 else ''}; drop them or record the goal")


def legacy_markers(data: dict) -> list[str]:
    """Signs that a bank was written in an older structure (output-contract.md → 不支持的旧结构). Empty for a current bank.

    Old banks are kept as they are, not migrated and not validated.
    """
    config = data.get("config") or {}
    questions = [q for q in data.get("questions") or [] if isinstance(q, dict)]
    rows = slice_index(config)
    plan = attribute_plan(config)
    found: list[str] = []

    def note(label: str, ids: list[str]) -> None:
        if ids:
            found.append(f"{label} ({len(ids)}: {', '.join(ids[:4])}{' …' if len(ids) > 4 else ''})")

    def qids(test) -> list[str]:
        return [str(q.get("question_id")) for q in questions if test(q)]

    stage = config.get("generation_stage")
    if stage != "selection":
        found.append("no config.generation_stage" if stage is None else f"generation_stage {stage!r}")
    if not rows:
        found.append("no matrix rows in config.slices")
    if "extra_prompt_types" in config:
        found.append("config.extra_prompt_types (presales bank)")
    if config.get("leader_default") is not None:
        found.append("config.leader_default")
    note("matrix rows without prompt_type", [sid for sid, row in rows.items() if "prompt_type" not in row])
    note("matrix rows with the prompt_types list", [sid for sid, row in rows.items() if "prompt_types" in row])
    note("matrix rows tiered P1 / P2 / P3", [sid for sid, row in rows.items()
                                              if str(row.get("priority") or "").strip() in ("P1", "P2", "P3")])
    note("journey stages", [sid for sid, row in rows.items() if not is_blank(row.get("journey_stage"))]
         + qids(lambda q: any(not is_blank(q.get(k)) for k in ("journey_stage", "journey_stage_9", "journey"))))
    note("group_role", qids(lambda q: any(not is_blank(q.get(k)) for k in ("group_role", "library_layer"))))
    note("Prompt type in the intent field or a Prompt Type: tag",
         qids(lambda q: (not is_blank(q.get("intent")) and is_blank(q.get("prompt_type")))
              or any(str(t).strip().startswith("Prompt Type:") for t in q.get("tags") or [])))
    note("old field names persona / buyer / attribute / buyer_demand_evidence / condition_slot / review_status",
         qids(lambda q: any(k in q for k in ("persona", "buyer", "attribute", "buyer_demand_evidence",
                                               "condition_slot", "review_status"))))
    if config.get("attribute_plan") and not plan:
        found.append("attribute_plan in the {p1, p2, p3} shape")
    note("attribute_plan with relative_competitor, priority, common_constraints or brand_value",
         [str(e.get("attribute")) for e in plan
          if any(not is_blank(e.get(k)) for k in ("relative_competitor", "相对竞品", "priority",
                                                   "common_constraints", "常见约束", "brand_value"))])
    return found


class BankValidator:
    """The gates over one bank (output-contract.md → validator 门禁), in report order."""

    def __init__(self, data: dict, previous: dict | None = None) -> None:
        self.data = data
        self.previous = previous
        self.config: dict = data.get("config") or {}
        self.topics: list = self.config.get("topics") or []
        self.questions: list[dict] = data.get("questions") or []
        self.stage = self.config.get("generation_stage")
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.intents: dict[int, str] = {}
        self.topic_counts: Counter = Counter()
        self.role_counts: Counter = Counter()
        self.topic_ids: set = set()
        self.review_active = False
        self.review_counts: Counter = Counter()
        self.approved_rows: list[dict] = self.questions
        self.carried_names: set[str] = set()
        self.written_names: set[str] = set()

    def run(self) -> int:
        self.check_root()
        self.check_rows()
        self.check_prompts()
        self.check_candidate_count()
        wording_checks(self.config, self.questions, self.intents, self.errors, self.warnings)
        self.check_fields()
        self.check_topics()
        self.check_goals_and_tags()
        self.check_scope()
        self.check_attribute_coverage()
        self.check_lifecycle()
        return self.finish()

    # ---------- bank root and Topics ----------

    def check_root(self) -> None:
        config, topics, errors = self.config, self.topics, self.errors
        if self.data.get("mode") != "after-sales-strategic-topics":
            fail("root mode must be after-sales-strategic-topics", errors)
        if not topics:
            fail("config.topics must contain at least one Topic", errors)
        self.topic_ids = {topic.get("topic_id") for topic in topics if topic.get("topic_id")}
        if len(self.topic_ids) != len(topics):
            fail("Topic IDs must be unique", errors)
        if any(not str(topic.get("topic") or "").strip() for topic in topics):
            fail("Topic names must be non-empty", errors)

    # ---------- matrix rows (gates 43, 60, 61; W48, W53, W64) ----------

    def check_rows(self) -> None:
        """Matrix rows (config.slices) carry the one 业务优先级 judgement (Suda 2026-10-28 / 11-01 / 11-02 / 11-05).

        Each row: {slice_id, topic_id, product_line, audience, scene, prompt_type, attributes, priority,
        priority_basis}; priority is 业务优先级 (Aleyda: commercial value, strategic importance, current business
        focus). 高 and 中 Discovery rows get Prompts; 低 rows get none by default (W64 when they carry some —
        allowed only to fill 高 / 中 coverage, with a recorded decision). Situations out of scope, without a
        reasonable demand basis, or the brand cannot serve are not opened as rows (they go to notes). Every Prompt
        sits on a row whose Topic it shares and whose prompt_type it has. Relative disadvantage is not an exclusion.
        """
        config, questions, errors, warnings = self.config, self.questions, self.errors, self.warnings
        slices = config.get("slices")
        if not isinstance(slices, list) or not all(isinstance(x, dict) for x in slices):
            fail("config.slices must be a list of matrix-row objects", errors)
            return
        by_id: dict[str, dict] = {}
        for row in slices:
            sid = str(row.get("slice_id") or "").strip()
            if not sid:
                fail("config.slices: every row needs slice_id", errors)
                continue
            if sid in by_id:
                fail(f"config.slices: duplicate slice_id {sid}", errors)
            by_id[sid] = row
            tier = str(row.get("priority") or "").strip()
            if tier not in TIER_INDEX:
                fail(f"slice {sid}: priority must be 高 / 中 / 低; a situation the brand cannot "
                     "use or serve is not opened as a row", errors)
            elif is_blank(row.get("priority_basis")):
                fail(f"slice {sid}: priority_basis is empty — a priority with no written basis is not made", errors)
            tid = row.get("topic_id")
            if not is_blank(tid) and tid not in self.topic_ids:
                fail(f"slice {sid}: topic_id {tid!r} is not in config.topics", errors)
            self.check_row_type(sid, row)

        # Category Awareness is the research pre-run before the attribute pool, never a bank Prompt (Suda 2026-10-29).
        ca = [str(q.get("question_id")) for q in questions
              if str(q.get("prompt_type") or "").strip() == "Category Awareness"]
        if ca:
            fail(f"Category Awareness Prompts in the bank ({len(ca)}): {', '.join(ca)}; it runs once per platform "
                 "before the attribute pool as research and is not written into the bank", errors)
        unfiled: list[str] = []
        per_row: Counter[str] = Counter()
        low_carried: list[str] = []
        for q in questions:
            qid = str(q.get("question_id"))
            ref = str(q.get("slice_ref") or "").strip()
            if not ref:
                unfiled.append(qid)
                continue
            row = by_id.get(ref)
            if row is None:
                fail(f"{qid}: slice_ref {ref!r} is not in config.slices", errors)
                continue
            per_row[ref] += 1
            self.check_prompt_on_row(qid, q, ref, row)
            if TIER_INDEX.get(str(row.get("priority") or "").strip()) == 2:
                low_carried.append(f"{qid}({ref})")
            if not is_blank(row.get("topic_id")) and q.get("topic_id") != row.get("topic_id"):
                fail(f"{qid}: topic_id {q.get('topic_id')!r} differs from its row {ref}'s {row.get('topic_id')!r}", errors)
            change = str(q.get("changeability") or "").strip()
            if change and change not in CHANGEABILITY:
                fail(f"{qid}: changeability must be one of {'/'.join(CHANGEABILITY)}", errors)
        # Gate 48: 高 and 中 Discovery rows with no Prompt are an omission or a deliberate skip that needs a warning
        # decision; rows of the other types wait for their goals to open.
        bare = [sid for sid, row in by_id.items()
                if TIER_INDEX.get(str(row.get("priority") or "").strip()) in (0, 1) and not per_row[sid]
                and self.row_due(row)]
        if bare:
            warnings.append(f"[W48] 高 / 中 Discovery rows with no Prompt ({len(bare)}): "
                            f"{', '.join(bare[:8])}{' …' if len(bare) > 8 else ''}; "
                            "write their Prompts, or record why this row gets none (banks without prompt_type: 方案考虑 rows)")
        if low_carried:
            warnings.append(f"[W64] Prompts on 低 rows ({len(low_carried)}): {', '.join(low_carried[:8])}{' …' if len(low_carried) > 8 else ''}; "
                            "低 rows get no Prompts by default — keep them only to fill 高 / 中 coverage and record the decision")
        if unfiled:
            warnings.append(f"[W53] Prompts with no slice_ref ({len(unfiled)}): "
                            f"{', '.join(unfiled[:6])}{' …' if len(unfiled) > 6 else ''}; every Prompt sits on a matrix row")
        # attribute_plan is the 约束条件 list; a row lists plan names only.
        plan = attribute_plan(config)
        if not plan:
            return
        names = {str(entry.get("attribute") or "").strip() for entry in plan} - {""}
        for sid, row in by_id.items():
            listed = row.get("attributes") or []
            listed = [listed] if isinstance(listed, str) else listed
            absent = [str(a).strip() for a in listed if str(a).strip() and str(a).strip() not in names]
            if absent:
                fail(f"slice {sid}: attributes absent from attribute_plan: {', '.join(absent)}", errors)

    def check_row_type(self, sid: str, row: dict) -> None:
        """Gate 60: a row is one Prompt type (slices.prompt_type; Suda 2026-11-05: split the matrix by type)."""
        rtype = str(row.get("prompt_type") or "").strip()
        if rtype not in REGISTERED_TYPES:
            fail(f"slice {sid}: prompt_type {rtype!r} must be one of {sorted(REGISTERED_TYPES)} "
                 "(Verification is retired: capability questions are Evaluation; Accuracy probes sit outside the bank)",
                 self.errors)

    def check_prompt_on_row(self, qid: str, q: dict, ref: str, row: dict) -> None:
        """Gate 61: a Prompt's type is its row's type."""
        qtype = str(q.get("prompt_type") or "").strip()
        rtype = str(row.get("prompt_type") or "").strip()
        if qtype in REGISTERED_TYPES and qtype != rtype:
            fail(f"{qid}: prompt_type {qtype} does not match row {ref} ({rtype or 'none'}); "
                 "open a row of that type for the same purchase task and move the Prompt there", self.errors)

    def row_due(self, row: dict) -> bool:
        """Rows written this period: Discovery (only 发现型可见度 is open)."""
        return str(row.get("prompt_type") or "").strip() == "Discovery"

    # ---------- Prompts (gates 2, 4, 8; Verification / Accuracy) ----------

    def check_prompts(self) -> None:
        errors = self.errors
        normalized_queries: set[str] = set()
        question_ids: set[str] = set()
        for row in self.questions:
            question_id = str(row.get("question_id") or "").strip()
            if not question_id:
                fail("question_id is required", errors)
            elif question_id in question_ids:
                fail(f"{question_id}: duplicate question_id", errors)
            question_ids.add(question_id)
            topic_id = row.get("topic_id")
            if topic_id not in self.topic_ids:
                fail(f"{question_id}: unknown topic_id", errors)
            self.topic_counts[topic_id] += 1
            intent = normalized_intent(row, errors)
            self.intents[id(row)] = intent
            self.role_counts[intent] += 1
            self.check_retired_types(question_id, intent)
            if not intent:
                fail(f"{question_id}: missing prompt_type", errors)
            elif intent not in INTENTS:
                fail(f"{question_id}: unsupported prompt_type {intent!r}", errors)
            if not str(row.get("region") or "").strip():
                fail(f"{question_id}: missing region", errors)
            user_question = str(row.get("user_question") or "").strip()
            if not user_question:
                fail(f"{question_id}: user_question is required", errors)
            if not str(row.get("zh_translation") or "").strip():
                fail(f"{question_id}: zh_translation is required", errors)
            query_key = " ".join(user_question.casefold().split())
            if query_key in normalized_queries:
                fail(f"{row.get('question_id')}: duplicate query", errors)
            normalized_queries.add(query_key)

    def check_retired_types(self, question_id: str, intent: str) -> None:
        if intent == "Verification":
            fail(f"{question_id}: Verification is retired (2026-11-06): a capability question is prompt_type Evaluation; "
                 "zero-mention diagnosis checks crawlability and cited pages first (geo-monitoring/references/trial-and-lock.md)",
                 self.errors)
        if intent == "Accuracy":
            fail(f"{question_id}: Accuracy probes sit outside the bank (fix acceptance / 品牌呈现); record them in the "
                 "brand fact-check table (geo-monitoring/references/trial-and-lock.md)", self.errors)

    def check_candidate_count(self) -> None:
        """Gate 47 (Suda 2026-11-02): a candidate bank for one product line in one market holds about 30–60 Prompts.

        Outside that range something upstream is off (constraints too narrow or wide, too few or many rows, splits not
        by decision). Warning only; never pad to reach 30. Verification Prompts take no slot.
        """
        if self.config.get("lifecycle_status") in FORMAL_LIFECYCLES:
            return
        lines: Counter[str] = Counter()
        slice_rows = slice_index(self.config)
        for row in self.questions:
            if self.intents.get(id(row)) == "Verification" or str(row.get("status") or "").strip() == "停测":
                continue
            line = row.get("product_line") or (slice_rows.get(str(row.get("slice_ref") or "").strip()) or {}).get("product_line")
            lines[str(line or "").strip() or "—"] += 1
        off = [f"{line}: {n}" for line, n in sorted(lines.items()) if not 30 <= n <= 60]
        if off:
            self.warnings.append(f"[W47] candidate Prompt count outside 30–60 per product line ({'; '.join(off)}); check whether "
                                 "attributes are too narrow or wide, too few or many rows are open, or splits follow "
                                 "decision differences — never pad to reach 30")

    def check_fields(self) -> None:
        field_contract_checks(self.config, self.questions, self.intents, self.errors, self.warnings)

    # ---------- Topics (gates 3, 66; W59, W46) ----------

    def check_topics(self) -> None:
        """Topics are the unit the brand party buys (Suda 2026-10-31 / 11-01)."""
        topics = [t for t in self.topics if isinstance(t, dict)]
        by_topic: dict[object, list[dict]] = {}
        for q in self.questions:
            by_topic.setdefault(q.get("topic_id"), []).append(q)
        empty = sorted(str(t.get("topic_id")) for t in topics if not by_topic.get(t.get("topic_id")))
        if empty and self.questions:
            fail(f"Topics with no Prompt ({len(empty)}): {', '.join(empty)}; drop them or file Prompts under them", self.errors)
        self.check_topic_types(by_topic)
        self.check_topic_size(by_topic)
        self.check_topic_priority(topics)

    def check_topic_types(self, by_topic: dict) -> None:
        """Gate 66 (Suda 2026-11-05): the back-office dashboard reads by Topic, so a Topic holds one Prompt type."""
        mixed = []
        for tid, items in sorted(by_topic.items(), key=lambda kv: str(kv[0])):
            types = sorted({self.intents.get(id(q)) or "unknown" for q in items
                            if str(q.get("status") or "").strip() != "停测"})
            if len(types) > 1:
                mixed.append(f"{tid}: {' + '.join(types)}")
        if mixed:
            fail(f"Gate 66: Topics mixing Prompt types ({'; '.join(mixed)}); the dashboard has no type field, so "
                 "keep one type per Topic — a Topic is one core purchase decision × one Prompt type", self.errors)

    def check_topic_size(self, by_topic: dict) -> None:
        """W59: a coverage review prompt, not a statistical guarantee or an instruction to merge buyer tasks."""
        floor = []
        for tid, items in sorted(by_topic.items(), key=lambda kv: str(kv[0])):
            kpi = [q for q in items if self.intents.get(id(q)) in KPI_INTENTS
                   and str(q.get("status") or "").strip() != "停测"]
            decisions = {(str(q.get("attribute_ref") or "").strip(),
                          tuple(sorted(str(c).strip() for c in (q.get("constraints") or []))))
                         for q in kpi}
            if kpi and (len(kpi) < 5 or len(decisions) < 4):
                floor.append(f"{tid}: {len(kpi)} KPI Prompts / {len(decisions)} decision signatures")
            active = [q for q in items if str(q.get("status") or "").strip() != "停测"]
            if not kpi and active and len(active) < 5:
                floor.append(f"{tid}: {len(active)} non-Discovery Prompts")
        if floor:
            self.warnings.append(f"[W59] Topics below the default coverage target ({'; '.join(floor)}); "
                                 "in order: (1) add missed buyer constraints, scenes, audiences or limits; (2) build compound "
                                 "conditions with real purchase meaning — never pad with synonyms, reordering or mechanical "
                                 "condition permutations; (3) check over-splitting — merge only adjacent Topics of the same "
                                 "purchase decision with similar candidate solutions. Record the decision if still short.")

    def check_topic_priority(self, topics: list[dict]) -> None:
        """Topic priority is summarised, not judged again (Suda 2026-11-05): by default the tier most of its rows carry;
        a tie has no default and needs a human call. Tier differences are never a reason to split a Topic."""
        row_tiers: dict = {}
        for r in slice_index(self.config).values():
            idx = TIER_INDEX.get(str(r.get("priority") or "").strip())
            if idx is not None and r.get("topic_id"):
                row_tiers.setdefault(r.get("topic_id"), []).append(idx)
        for t in topics:
            tid, level = t.get("topic_id"), str(t.get("priority") or "").strip()
            if not level:
                continue  # banks written before topic priority came back (2026-11-01)
            if level not in TOPIC_PRIORITIES:
                fail(f"topic {tid}: priority must be one of {'/'.join(TOPIC_PRIORITIES)}", self.errors)
            elif is_blank(t.get("priority_basis")):
                fail(f"topic {tid}: priority_basis is empty — a priority with no written basis is not made", self.errors)
            elif row_tiers.get(tid):
                counts = Counter(row_tiers[tid])
                top = max(counts.values())
                leaders = [i for i, n in counts.items() if n == top]
                if len(leaders) > 1:
                    self.warnings.append(f"[W46] topic {tid}: rows split evenly across tiers, no majority; decide 主题优先级 by hand "
                                         "and record the reason")
                elif level != ("高", "中", "低")[leaders[0]]:
                    self.warnings.append(f"[W46] topic {tid}: priority {level} but most of its rows are {('高', '中', '低')[leaders[0]]}; "
                                         "主题优先级 defaults to the tier most of its rows carry — record the reason if overridden")

    # ---------- goals and slice tags (W49–W52, W62, W63) ----------

    def check_goals_and_tags(self) -> None:
        goal_checks(self.config, self.questions, self.intents, self.warnings, self.competitor_rows())
        # Gates W62/W63 (Suda 2026-11-03): slice tags cut data across Topics. A value inside one Topic,
        # or under 5 Prompts, duplicates the Topic filter or reads as noise; export drops it either way.
        _, tag_problems, unregistered = _tag_plan(self.config, self.questions)
        for problem in tag_problems:
            self.warnings.append(f"[W62] tag_dimensions: {problem}")
        if unregistered:
            listed = "; ".join(f"{qid}: {'、'.join(tags)}" for qid, tags in list(unregistered.items())[:6])
            self.warnings.append(f"[W63] hand-written tags not registered as a 自定义 value in config.tag_dimensions "
                                 f"({listed}{' …' if len(unregistered) > 6 else ''}); export leaves them out")

    def competitor_rows(self) -> list[str]:
        """高 / 中 对比 rows, named by gate 50."""
        return sorted(sid for sid, r in slice_index(self.config).items()
                      if str(r.get("prompt_type") or "").strip() == "Competitor"
                      and TIER_INDEX.get(str(r.get("priority") or "").strip()) in (0, 1))

    # ---------- conditions and audiences (gate 38; W36, W37, W39) ----------

    def check_scope(self) -> None:
        scope_checks(self.config, self.questions, self.errors, self.warnings, self.intents)
        audience_checks(self.config, self.questions, self.warnings, self.intents)

    # ---------- 约束条件 coverage (W56, W57) ----------

    def check_attribute_coverage(self) -> None:
        """Every 约束条件 a Prompt measures is counted as covered only once that Prompt is 已批准.

        status mirrors the 状态 column of the client Base 提示词库. Once any Prompt carries a review value, only
        已批准 Prompts count as covering a constraint, the same rule as the Base 覆盖情况 formula.
        """
        questions, errors = self.questions, self.errors
        review_of = lambda row: row.get("status") if str(row.get("status") or "").strip() in REVIEW_ALIASES else None
        self.review_active = any(review_of(row) is not None for row in questions)
        if self.review_active:
            unstated: list[str] = []
            self.approved_rows = []
            for row in questions:
                raw = review_of(row)
                if is_blank(raw):
                    unstated.append(str(row.get("question_id")))
                    status = "待审核"
                else:
                    status = REVIEW_ALIASES[str(raw).strip()]
                self.review_counts[status] += 1
                if status == "已批准":
                    self.approved_rows.append(row)
            if unstated:
                self.warnings.append(f"[W56] review_status missing on {len(unstated)} Prompts, counted as 待审核 "
                                     f"({', '.join(unstated[:6])}{' …' if len(unstated) > 6 else ''})")

        def carried_by(rows: list[dict]) -> set[str]:
            names: set[str] = set()
            for row in rows:
                for tag in row.get("tags") or []:
                    names.add(str(tag).strip())
                value = str(row.get("attribute_ref") or "").strip()
                if value:
                    names.add(value)
            return names

        plan = attribute_plan(self.config)
        if not plan:
            return
        self.carried_names = carried_by(self.approved_rows)
        self.written_names = carried_by(questions)
        pending = [f"{name}({str(entry.get('priority') or '').strip() or '?'})" for entry in plan
                   if (name := str(entry.get("attribute") or "").strip())
                   and name not in self.carried_names and name in self.written_names]
        if pending:
            message = ("attributes carried only by Prompts not yet 已批准, so not counted as covered "
                       f"({len(pending)}): " + ", ".join(sorted(pending)))
            if lifecycle_after_review(self.config):
                errors.append(message)
            else:
                self.warnings.append(f"[W57] {message}")

    # ---------- lifecycle, trial, baseline, version (gates 14, 26; W34, W35) ----------

    def check_lifecycle(self) -> None:
        config, questions, errors = self.config, self.questions, self.errors
        lifecycle = config.get("lifecycle_status")
        if lifecycle is not None and lifecycle not in LIFECYCLE_STATES:
            fail(f"config.lifecycle_status must be one of {sorted(LIFECYCLE_STATES)}", errors)
        self.check_evidence_diversity()

        # Unused buyer-language inputs (warning only). When the bank carries the
        # collected 需求信号 index, every input should either back a Prompt or have
        # been consciously set aside; silently unused inputs are the cheapest
        # evidence for the next expansion round.
        audience_inputs = config.get("audience_inputs") or []
        if audience_inputs and isinstance(audience_inputs, list):
            # Quotes back Prompts or the matrix rows.
            all_refs = " ".join(
                str(ref) for row in questions for ref in (row.get("evidence_refs") or [])
            ) + json.dumps([config.get("attribute_plan") or [], config.get("slices") or []], ensure_ascii=False)
            unused: list[str] = []
            for entry in audience_inputs:
                input_id = str(entry.get("input_id") if isinstance(entry, dict) else entry or "").strip()
                if input_id and input_id not in all_refs:
                    unused.append(input_id)
            if unused:
                self.warnings.append(
                    f"[W35] audience inputs referenced by no Prompt ({len(unused)}): "
                    + ", ".join(unused[:8]) + (" …" if len(unused) > 8 else "")
                    + "; cite each in an attribute's evidence or a Prompt, or record why it was set aside"
                )

        self.check_formal_cap()

        evidence_status = config.get("evidence_status")
        if evidence_status in {"hypothesis", "after_sales_signal"} and lifecycle in FORMAL_LIFECYCLES:
            fail("hypothesis or after_sales_signal evidence cannot be marked formal-ready", errors)

        confirmation = config.get("customer_confirmation") or {}
        if lifecycle in {"customer_confirmed", *FORMAL_LIFECYCLES}:
            if confirmation.get("status") not in {"confirmed", "locked"}:
                fail("customer confirmation is required before formal-ready lifecycle states", errors)
            if confirmation.get("scope_status") != "confirmed":
                fail("customer_confirmation.scope_status must be confirmed before trial", errors)
        if lifecycle in FORMAL_LIFECYCLES:
            if confirmation.get("prompt_set_status") != "confirmed":
                fail("customer_confirmation.prompt_set_status must be confirmed after trial", errors)

        prompt_version = config.get("prompt_version")
        if lifecycle in FORMAL_LIFECYCLES and not str(prompt_version or "").strip():
            fail("prompt_version is required before formal baseline", errors)

        trial = config.get("trial") or {}
        if trial or lifecycle in FORMAL_LIFECYCLES:
            # trial = 候选题质量试跑：每题在每个监测平台各 3 次（异常补到 5 次封顶）。
            planned = trial.get("planned_runs")
            if isinstance(planned, bool) or planned != 3:
                fail("trial.planned_runs must be 3 (quality trial on each monitored platform)", errors)
        if trial.get("status") in {"running", "passed"} and confirmation.get("scope_status") != "confirmed":
            fail("customer_confirmation.scope_status must be confirmed before trial", errors)
        if lifecycle in FORMAL_LIFECYCLES:
            valid = trial.get("valid_runs")
            ceiling = trial.get("planned_runs") if isinstance(trial.get("planned_runs"), int) else 5
            if trial.get("status") != "passed" or not isinstance(valid, int) or not 3 <= valid <= ceiling:
                fail("locked set requires 3 to 5 valid trial runs (planned 3; failures are not zeros)", errors)
            if not trial.get("evidence_refs"):
                fail("locked set requires trial.evidence_refs", errors)

        baseline = config.get("baseline") or {}
        formal_collection = baseline.get("status") in {"formal", "active"}
        if formal_collection and lifecycle not in {"locked", "formal_baseline", "active"}:
            fail("formal baseline metadata requires a locked or formal lifecycle", errors)
        if formal_collection and evidence_status in {"hypothesis", "after_sales_signal"}:
            fail("formal baseline metadata requires confirmed evidence", errors)
        if formal_collection and (confirmation.get("status") not in {"confirmed", "locked"}):
            fail("formal baseline metadata requires customer confirmation", errors)
        if formal_collection and not str(prompt_version or "").strip():
            fail("formal baseline metadata requires prompt_version", errors)
        if lifecycle == "formal_baseline" and baseline.get("status") not in {"formal", "active"}:
            fail("formal_baseline lifecycle requires baseline.status formal or active", errors)
        if baseline or lifecycle == "formal_baseline":
            # 正式基线：每个 query × 平台 × 国家 × 语言跑 7 次（Suda 2026-11-06）。是否跨天由项目约定，写在 collection_config。
            # 当天早些时候写的 30 次照认（某车载品牌、Bbrand 选词题库），锁版前改成 7。
            runs = baseline.get("planned_runs")
            if isinstance(runs, bool) or runs not in {7, 30}:
                fail("baseline.planned_runs must be 7 (per query x platform x country x language; 30 written before "
                     "2026-11-06 still accepted)", errors)
        if formal_collection:
            if not str(baseline.get("conditions_key") or "").strip():
                fail("formal baseline requires conditions_key", errors)
            if baseline.get("valid_samples_only") is not True:
                fail("formal baseline must compare valid samples only", errors)
            if baseline.get("failures_as_zero") is True:
                fail("collection failures must not be counted as zero", errors)
            if not prompt_version or baseline.get("prompt_version") != prompt_version:
                fail("baseline.prompt_version must match config.prompt_version", errors)

        collection = config.get("collection_config") or {}
        if baseline.get("status") in {"formal", "active"}:
            for field in ("market", "language"):
                if not str(collection.get(field) or "").strip():
                    fail(f"formal baseline requires collection_config.{field}", errors)
            if not collection.get("platforms"):
                fail("formal baseline requires collection_config.platforms", errors)
            for row in questions:
                if row.get("region") != collection.get("market"):
                    fail(
                        f"{row.get('question_id')}: region does not match collection_config.market",
                        errors,
                    )

        if self.previous is not None:
            previous = self.previous
            previous_collection = (previous.get("config") or {}).get("collection_config") or {}
            if any(
                collection.get(field) and previous_collection.get(field)
                and collection[field] != previous_collection[field]
                for field in ("market", "language")
            ):
                fail("previous bank must use the same market and language", errors)
            if monitored_set(self.data) != monitored_set(previous):
                old_version = (previous.get("config") or {}).get("prompt_version")
                if not prompt_version or old_version == prompt_version:
                    fail("prompt_version must change when the monitored set changes", errors)

    def check_evidence_diversity(self) -> None:
        """W34 (warning only, from customer_confirmed on): a formal set whose evidence all comes from one source family
        usually means the signal pass skipped sources, not that buyers only speak there."""
        if not lifecycle_after_review(self.config):
            return
        refs = [str(ref).strip() for row in self.approved_rows
                for ref in (row.get("evidence_refs") or []) if str(ref).strip()]
        if refs:
            families = Counter(evidence_source_family(ref) for ref in refs)
            unclassified = families.pop("未分类", 0)
            if unclassified <= len(refs) / 2 and len(families) < 3:
                found = "、".join(sorted(families)) or "none recognised"
                self.warnings.append(
                    f"[W34] evidence spans only {len(families)} source families ({found}); "
                    "the signal pass covers search data, sales records, reviews and "
                    "community — check whether the missing families were collected"
                )

    def check_formal_cap(self) -> None:
        """Gate 14 (交付范围, Suda 2026-11-05): a locked set holds at most 60 Prompts per product line × country ×
        language; one bank is one country × one language, so it counts per product line. No cap per Topic, and none
        while the set is still a candidate set."""
        if self.config.get("lifecycle_status") not in FORMAL_LIFECYCLES:
            return
        formal_slices = slice_index(self.config)
        per_line: Counter[str] = Counter()
        for row in self.questions:
            if self.intents.get(id(row)) == "Verification" or str(row.get("status") or "").strip() == "停测":
                continue
            line = row.get("product_line") or (formal_slices.get(str(row.get("slice_ref") or "").strip()) or {}).get("product_line")
            per_line[str(line or "").strip() or "—"] += 1
        over = {line: n for line, n in sorted(per_line.items()) if n > 60}
        if over:
            fail(
                "formal set allows at most 60 Prompts per product line × country × language; "
                f"move the rest out of the deliverable set: {over}",
                self.errors,
            )

    # ---------- readiness ----------

    def finish(self) -> int:
        """Print warnings, errors and the readiness verdict; return the exit code.

        Warnings never change the exit code: each one needs a human decision, and rewording a Prompt only to silence a
        heuristic is not a fix. Each warning is handled by a written decision in config.warning_decisions:
        [{"match": "<text in the warning>", "decision": "已改写 / 保留：理由"}] (Suda 2026-10-31), or, for a whole
        class, [{"gate": "W39", "decision": "保留：理由"}] — every warning opens with its stable code "[Wnn]"
        (Suda 2026-11-02 审核清单 D5).
        """
        config, errors, warnings = self.config, self.errors, self.warnings

        def gate_code(value: object) -> str:
            code = str(value or "").strip().strip("[]").strip()
            if not code:
                return ""
            code = code[1:] if code[:1] in "Ww" else code
            return f"[w{code.casefold()}]"  # compared case-insensitively with the warning's "[Wnn]" head

        decisions = [d for d in config.get("warning_decisions") or []
                     if isinstance(d, dict) and str(d.get("decision") or "").strip()
                     and (str(d.get("match") or "").strip() or gate_code(d.get("gate")))]

        def is_handled(warning: str) -> bool:
            head = warning.split(" ", 1)[0].casefold()
            for d in decisions:
                match = str(d.get("match") or "").strip()
                if match and match in warning:
                    return True
                if gate_code(d.get("gate")) and head == gate_code(d.get("gate")):
                    return True
            return False

        handled = [w for w in warnings if is_handled(w)]
        open_warnings = [w for w in warnings if w not in handled]
        # Only public data, or a hypothesis-grade set, caps the verdict at Usable whatever the warnings.
        capped = config.get("first_party_data") is False or config.get("evidence_status") == "hypothesis"
        plural = lambda n, word: f"{n} {word}{'s' if n != 1 else ''}"
        if errors:
            readiness = f"Not ready: {plural(len(errors), 'error')} to fix"
        elif open_warnings:
            readiness = f"Usable: {plural(len(open_warnings), 'warning')} without a decision"
        elif capped:
            readiness = "Usable: public data only or hypothesis-grade evidence — list what the brand party still has to supply"
        else:
            readiness = "Ready for the next lifecycle stage"

        for warning in warnings:
            print(f"WARNING{' (handled)' if warning in handled else ''}: {warning}")
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            print(f"READINESS: {readiness}")
            return 1

        print(
            json.dumps(
                {
                    "topics": len(self.topics),
                    "prompts": len(self.questions),
                    "prompts_per_topic": dict(self.topic_counts),
                    "prompt_types": dict(self.role_counts),
                    "generation_stage": self.stage,
                    **({"review_status": dict(self.review_counts)} if self.review_active else {}),
                    "warnings": len(warnings),
                    "warnings_handled": len(handled),
                    "readiness": readiness,
                },
                ensure_ascii=False,
            )
        )
        return 0


def load_args(argv: list[str] | None, description: str | None) -> tuple[Path, dict, dict | None]:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("bank", type=Path)
    parser.add_argument("--previous", type=Path, help="Previous monitoring set for version checks")
    args = parser.parse_args(argv)
    data = json.loads(args.bank.read_text(encoding="utf-8"))
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    return args.bank, data, previous


def main(argv: list[str] | None = None) -> int:
    bank, data, previous = load_args(argv, __doc__)
    markers = legacy_markers(data)
    if markers:
        print(f"ERROR: unsupported old structure in {bank.name}: {'; '.join(markers)}. Old banks are not migrated "
              "and not validated; a bank written now follows references/output-contract.md")
        print("READINESS: Not ready: unsupported old structure")
        return 2
    return BankValidator(data, previous).run()


if __name__ == "__main__":
    raise SystemExit(main())
