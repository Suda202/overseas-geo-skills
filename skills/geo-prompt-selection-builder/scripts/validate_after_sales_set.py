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
# No lifecycle, trial, baseline or lock gates (3.14.1): locking happens in the client Base (check_client_base.py).


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
# Which language a Prompt is written in (Suda 2026-11-09): markets and languages follow the brand party
# and are not enumerable, so this uses the general detector lingua (75 languages, offline) instead of
# per-language word lists. A collection language lingua does not know, or a machine without lingua,
# skips this check with one warning; the script-share check above still runs.
try:
    from lingua import IsoCode639_1, Language, LanguageDetectorBuilder
except ImportError:  # pragma: no cover - depends on the machine
    LanguageDetectorBuilder = None
_LANGUAGE_DETECTOR = None
LANGUAGE_NAME_ALIASES = {
    "bahasa indonesia": "id", "bahasa melayu": "ms", "bahasa malaysia": "ms", "filipino": "tl",
    "fil": "tl", "norwegian": "nb", "no": "nb", "farsi": "fa", "persian": "fa", "chinese": "zh",
    "mandarin": "zh", "cantonese": "zh", "greek": "el", "hebrew": "he", "iw": "he",
}
# Closely related languages a short Prompt cannot tell apart; a hit inside the group counts as a match.
CLOSE_LANGUAGES = [{"id", "ms"}, {"nb", "nn", "da"}, {"hr", "sr", "bs"}, {"nl", "af"}, {"cs", "sk"}]
# When lingua tops a Prompt with another language, the expected language's own confidence decides:
# under 0.05 is an error, under 0.10 a warning. Prompts written in the wrong language score 0.00–0.04 for
# the expected one, with the detected language at 0.18 or more (evals/e2e_language_check.py). A line that
# is mostly product names and jargon gets no clear winner: real English Prompts lingua tops with German or
# Spanish, such as a client's "Best fast charger for a Samsung tablet", top out at 0.07–0.13, so a top
# language under 0.15 is not judged.
LANGUAGE_ERROR_CONFIDENCE, LANGUAGE_WARN_CONFIDENCE, LANGUAGE_MIN_TOP = 0.05, 0.10, 0.15
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


def lingua_code(value: object) -> str | None:
    """ISO 639-1 code lingua knows for a collection language ("id", "pt-BR", "Indonesian", "Bahasa Indonesia")."""
    if LanguageDetectorBuilder is None:
        return None
    raw = str(value or "").strip().casefold()
    if not raw:
        return None
    candidates = [raw, re.split(r"[-_ /(]", raw, maxsplit=1)[0]]
    for cand in candidates:
        cand = LANGUAGE_NAME_ALIASES.get(cand, cand)
        try:
            return Language.from_iso_code_639_1(getattr(IsoCode639_1, cand.upper())).iso_code_639_1.name.lower()
        except (AttributeError, ValueError):
            pass
        language = getattr(Language, cand.upper().replace(" ", "_"), None)
        if isinstance(language, Language):
            return language.iso_code_639_1.name.lower()
    return None


def close_languages(a: str, b: str) -> bool:
    return a == b or any(a in group and b in group for group in CLOSE_LANGUAGES)


def detect_language(text: str, ignore: list[str] = ()) -> tuple[str, float, dict[str, float]] | None:
    """(top language, its confidence, confidence by code); None when the text is too short to judge.
    Brand, competitor and category names are removed first: they are not written in the buyer's language."""
    global _LANGUAGE_DETECTOR
    if LanguageDetectorBuilder is None:
        return None
    cleaned = str(text)
    for term in sorted((t for t in ignore if t and len(t) >= 3), key=len, reverse=True):
        pattern = rf"(?<![^\W_]){re.escape(term)}(?![^\W_])" if term.isascii() else re.escape(term)
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    # Too short to judge: under 12 letters, or under 5 words where the language separates words with spaces
    # (real English "Best open-ear earbuds" reads 0.38 English vs Norwegian). Thai, Chinese and Japanese
    # run words together, so "words" there average far more than 12 letters and the word count is not used.
    words = cleaned.split()
    letters = sum(ch.isalpha() for ch in cleaned)
    spaced = bool(words) and letters / len(words) <= 12
    if letters < 12 or (spaced and len(words) < 5):
        return None
    if _LANGUAGE_DETECTOR is None:
        _LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()
    values = _LANGUAGE_DETECTOR.compute_language_confidence_values(cleaned)
    if not values:
        return None
    by_code = {v.language.iso_code_639_1.name.lower(): v.value for v in values}
    top = values[0]
    return top.language.iso_code_639_1.name.lower(), top.value, by_code


def similarity_units(text: str, script: str) -> set[str]:
    if script == "latin":
        stem = lambda w: re.sub(r"(est|ing|ed|er|es|s)$", "", w) if len(w) > 5 else w
        return {stem(w) for w in latin_words(text) if w not in CONTENT_STOPWORDS and len(w) > 1}
    compact = "".join(ch for ch in str(text).casefold() if ch.isalnum())
    return {compact[i:i + 3] for i in range(max(0, len(compact) - 2))}


def entity_terms(config: dict) -> list[str]:
    """Target brand, aliases and every competitor name in competitor_selection.

    Aliases come from config.brand_aliases (normalize_case output, 3.14.3), the older config.aliases, or the
    「品牌别名 n」 entries of config.case_fields.
    """
    case_fields = config.get("case_fields") if isinstance(config.get("case_fields"), dict) else {}
    aliases = [v for k, v in case_fields.items() if str(k).startswith("品牌别名") and str(v).strip() not in ("", "无")]
    terms = [config.get("brand_name"), *(config.get("brand_aliases") or []), *(config.get("aliases") or []),
             *aliases, *(config.get("competitors") or [])]

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
    raw_language = collection.get("language") or config.get("language")
    lang = language_key(raw_language)
    script = LANGUAGE_SCRIPTS.get(lang, "")
    expected = lingua_code(raw_language)
    terms = entity_terms(config)
    ignore = terms + [str(config.get("category_label") or ""), str(collection.get("market") or "")] + [
        str(a) for a in config.get("category_aliases") or [] if isinstance(a, str)]
    if raw_language and expected is None:
        reason = "lingua is not installed (pip install lingua-language-detector)" if LanguageDetectorBuilder is None \
            else f"collection language {raw_language!r} is not one of lingua's 75 languages"
        warnings.append(f"[W32] language check skipped: {reason}; check by hand that Prompts are in the market language")

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
        detected = detect_language(text, ignore)
        if intents.get(id(row)) == "Discovery":
            named = [term for term in terms if mentions_entity(text, term)]
            if named:
                fail(f"{qid}: Discovery Prompt names a brand or competitor {named}", errors)
            # A query written in another language (a wording slip the language check
            # reports separately) is not judged by the English candidate gate.
            reads_english = detected[0] == "en" if detected else None
            if raw_language:
                english = (expected == "en" or lang in ("en", "english")) and reads_english is not False
            else:
                english = reads_english is True
            if english and not _prompt_gates.requests_candidates(text):
                fail(f"{qid}: Discovery Prompt asks no candidate question (which / best / "
                     f"recommend / where to buy ...); AI answers it with advice, not a brand list", errors)
        if script:
            share = expected_script_share(text, script)
            if share is not None and share < 0.5:
                fail(f"{qid}: query is not written in the collection language {lang!r} "
                     f"({share:.0%} of letters in the expected script)", errors)
        if expected and detected and detected[1] >= LANGUAGE_MIN_TOP and not close_languages(detected[0], expected):
            top, top_conf, by_code = detected
            own = by_code.get(expected, 0.0)
            if own < LANGUAGE_ERROR_CONFIDENCE:
                fail(f"{qid}: query reads as {top!r}, not the collection language {expected!r} "
                     f"(confidence {top_conf:.2f} vs {own:.2f})", errors)
            elif own < LANGUAGE_WARN_CONFIDENCE:
                warnings.append(f"[W32] {qid}: reads more like {top!r} than the collection language {expected!r}; "
                                f"check it is in the buyer's language (mixed-language wording is fine if buyers ask that way)")
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
# Sales unit (Suda 2026-11-09): one Discovery Topic is sold as 10 Prompts, each a distinct purchase decision.
# 3.0.0 dropped the second threshold (8 distinct decision signatures): one number, 10. Other types have no floor
# (3.13.0): their counts come from type-branches.md (one per competitor, per product line …), which a floor of 5
# could never meet.
TOPIC_FLOOR = 10
# W47 / gate 47 (3.13.0): per product line × market, under 30 candidates is a coverage review (warning, never pad);
# over 60 is an error — the cost cap (Suda 2026-11-12): trial runs bill per candidate. Topics are not capped
# by count; within 60, ten-Prompt Topics fit six.
CANDIDATE_FLOOR, CANDIDATE_CAP = 30, 60
PROMPT_FIELDS = ("attribute_ref", "constraint_type")
# A Prompt states the constraint it tests (attribute_ref); target customer and use scenario are read from its
# matrix row (config.slices).
REQUIRED_STAGED_FIELDS = ("attribute_ref",)
# No-condition Discovery Prompts are not written by default (Suda 2026-10-29): a bare category
# question is owned by category leaders. Judged from constraint_type.
LOW_CONDITION_VALUES = {"无限定", "无限定条件", "低条件", "none", "unconstrained", "no_condition"}
REVIEW_STATUSES = ("待审核", "已批准", "需修改")
REVIEW_ALIASES = {
    **{status: status for status in REVIEW_STATUSES},
    # 提示词库 状态 also carries 正式 (locked) and 停测 (dropped); both were approved first.
    "正式": "已批准", "停测": "已批准",
}



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
    fields = {id(row): normalize_fields(row) for row in questions}
    for field in REQUIRED_STAGED_FIELDS:
        # attribute_ref may be empty on a category-baseline Prompt; it only has to be stated.
        missing = [r for r in questions if fields[id(r)][field] is None]
        report_rows(f"missing {field}", missing, len(questions), False, errors, warnings)

    # Bare category questions are written only when the brand party asks for the head term
    # (Suda 2026-10-29; the per-Topic low-condition anchor of 2026-10-22 is retired).
    # 3.13.0: judged from the contract field — a bare category Prompt leaves attribute_ref empty
    # and has no constraint keywords (output-contract.md); the old constraint_type marker is still read.
    constraint_of = lambda r: str(fields[id(r)].get("constraint_type") or "").strip().casefold()
    bare = [str(r.get("question_id")) for r in questions
            if intents.get(id(r)) == "Discovery"
            and (constraint_of(r) in LOW_CONDITION_VALUES
                 or (is_blank(r.get("attribute_ref")) and not r.get("constraints")))]
    if bare:
        warnings.append(
            f"[W54] no-condition Discovery Prompts ({len(bare)}): {', '.join(bare)}; a bare category question is "
            "written only when the brand party asks for that head term — say so in its reason (selection-rules.md → 5「宽泛品类题」)"
        )



# Row tiers: 高 / 中 / 低.
TIER_INDEX = {"高": 0, "中": 1, "低": 2}
TOPIC_PRIORITIES = ("高", "中", "低")
BUSINESS_GOALS = ("发现型可见度", "竞争定位", "品牌呈现", "声誉与信任")


# A bank that leaves business_goals out is read as this default (3.0.0): online runs write only Discovery. Local
# selection opens the types of the goals the brand party picked (3.10.0; selection-rules.md → 1).
DEFAULT_BUSINESS_GOALS = {"selected": ["发现型可见度"], "information_named": False}
# Which goal opens which Prompt type (type-branches.md「对应哪个目标」). Transactional and Support belong to no goal
# and stay registered-only (3.13.0).
GOAL_TYPES = {"竞争定位": ("Competitor", "Alternatives"), "声誉与信任": ("Evaluation", "Trust")}


def opened_types(config: dict) -> set[str]:
    """Prompt types written this period: Discovery, plus the types of the goals in config.business_goals."""
    goals = config.get("business_goals")
    goals = DEFAULT_BUSINESS_GOALS if goals is None else goals
    selected = goals.get("selected") if isinstance(goals, dict) else None
    opened = {"Discovery"}
    if isinstance(selected, list):
        for goal in selected:
            opened.update(GOAL_TYPES.get(str(goal).strip(), ()))
    if isinstance(goals, dict) and goals.get("information_named") is True:
        opened.add("Information")
    return opened
# 约束条件表 (3.11.0): what the brand has, and where it stands on public hard facts.
BRAND_STATUS = ("有", "没有", "待确认")
VS_COMPETITORS = ("明显优势", "明显劣势", "持平", "未知")


def goal_checks(config: dict, questions: list[dict], intents: dict[int, str], warnings: list[str]) -> None:
    """Gates 49 and 52 (Suda 2026-11-02 审核清单 B2): the brand party's goals decide which Prompt types are written.

    config.business_goals = {selected: [goals], information_named: bool}; missing means DEFAULT_BUSINESS_GOALS
    (3.0.0). Alternatives belong to 竞争定位. Verification and Accuracy are outside selection banks and rejected by
    the main type check. Transactional and Support belong to no goal yet (selection-rules.md → 1) and always warn
    when written. The dormant gates 50 / 51 (a selected goal with no Prompt of its type) were removed in 3.0.0.
    """
    goals = config.get("business_goals")
    if goals is None:
        goals = DEFAULT_BUSINESS_GOALS
    selected = goals.get("selected") if isinstance(goals, dict) else None
    if (not isinstance(goals, dict) or not isinstance(selected, list)
            or any(str(g).strip() not in BUSINESS_GOALS for g in selected)):
        warnings.append("[W49] config.business_goals malformed: leave it out (read as {selected: [\"发现型可见度\"], "
                        "information_named: false}) or write {selected: [goals from "
                        f"{' / '.join(BUSINESS_GOALS)}], information_named: true / false}} so gate 52 can run")
        return
    chosen = {str(g).strip() for g in selected}
    named_info = goals.get("information_named") is True
    by_type: dict[str, list[str]] = {}
    for q in questions:
        by_type.setdefault(intents.get(id(q)) or "", []).append(str(q.get("question_id")))
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

    def __init__(self, data: dict) -> None:
        self.data = data
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
        self.check_constraint_table()
        self.check_inputs()
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
            if not tier and not self.row_due(row):
                pass  # types whose goal is not selected are registered without a tier
            elif tier not in TIER_INDEX:
                fail(f"slice {sid}: priority must be 高 / 中 / 低 (Discovery rows and rows of a selected goal's type "
                     "are tiered); a situation the brand cannot use or serve is not opened as a row", errors)
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
        # Gate 48: 高 and 中 rows of an opened type with no Prompt are an omission or a deliberate skip that needs a
        # warning decision; rows of the other types wait for their goals to open.
        bare = [sid for sid, row in by_id.items()
                if TIER_INDEX.get(str(row.get("priority") or "").strip()) in (0, 1) and not per_row[sid]
                and self.row_due(row)]
        if bare:
            warnings.append(f"[W48] 高 / 中 rows with no Prompt ({len(bare)}): "
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
        """Rows judged and written this period: Discovery, plus the types of the selected goals (3.10.0 / 3.13.0)."""
        return str(row.get("prompt_type") or "").strip() in opened_types(self.config)

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
                 "zero-mention diagnosis checks crawlability and cited pages first (geo-monitoring/references/gap-cause-action-table.md)",
                 self.errors)
        if intent == "Accuracy":
            fail(f"{question_id}: Accuracy probes sit outside the bank (fix acceptance / 品牌呈现); record them in the "
                 "brand fact-check table", self.errors)

    def check_candidate_count(self) -> None:
        """Gate 47 (Suda 2026-11-02; 3.13.0): per product line × market, 30–60 candidate Prompts.

        Under 30 is a warning: something upstream may be off (rows not opened, constraints too narrow, splits not by
        decision); never pad to reach 30. Over 60 is an error: the cost cap (Suda 2026-11-12) — cut the weakest-evidence
        Prompts on 中 rows first. Verification and stopped Prompts take no slot.
        """
        cells: Counter[str] = Counter()
        slice_rows = slice_index(self.config)
        for row in self.questions:
            if self.intents.get(id(row)) == "Verification" or str(row.get("status") or "").strip() == "停测":
                continue
            slice_row = slice_rows.get(str(row.get("slice_ref") or "").strip()) or {}
            line = str(row.get("product_line") or slice_row.get("product_line") or "").strip() or "—"
            market = str(row.get("region") or slice_row.get("market") or "").strip() or "—"
            cells[f"{line} × {market}"] += 1
        over = [f"{cell}: {n}" for cell, n in sorted(cells.items()) if n > CANDIDATE_CAP]
        if over:
            fail(f"more than {CANDIDATE_CAP} candidate Prompts per product line × market ({'; '.join(over)}); the cap "
                 "controls cost — cut the weakest-evidence Prompts on 中 rows first (selection-rules.md → 7)", self.errors)
        short = [f"{cell}: {n}" for cell, n in sorted(cells.items()) if n < CANDIDATE_FLOOR]
        if short:
            self.warnings.append(f"[W47] fewer than {CANDIDATE_FLOOR} candidate Prompts per product line × market "
                                 f"({'; '.join(short)}); check whether rows were left unopened, constraints are too "
                                 "narrow, or splits follow decision differences — never pad to reach 30")

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
            if kpi and len(kpi) < TOPIC_FLOOR:
                floor.append(f"{tid}: {len(kpi)} KPI Prompts")
        if floor:
            self.warnings.append(f"[W59] Topics below the default coverage target ({'; '.join(floor)}); "
                                 "in order: (1) add missed buyer constraints, scenes, audiences or limits; (2) build compound "
                                 "conditions with real purchase meaning — never pad with synonyms, reordering or mechanical "
                                 "condition permutations; (3) check over-splitting — merge only adjacent Topics of the same "
                                 "purchase decision with similar candidate solutions. Still short: never pad with repeats — the brand party may fill the "
                                 "10-Prompt unit with Prompts from other Topics (mixed selection); record the decision.")

    def check_topic_priority(self, topics: list[dict]) -> None:
        """Topic priority is not judged again (Suda 2026-11-09, 2.62.0): it takes the highest 业务优先级 among its rows,
        since a 高 row means a buyer situation the brand party named. Tier differences are never a reason to split a Topic."""
        row_tiers: dict = {}
        for r in slice_index(self.config).values():
            idx = TIER_INDEX.get(str(r.get("priority") or "").strip())
            if idx is not None and r.get("topic_id"):
                row_tiers.setdefault(r.get("topic_id"), []).append(idx)
        for t in topics:
            tid, level = t.get("topic_id"), str(t.get("priority") or "").strip()
            if not level:
                fail(f"topic {tid}: priority is empty — take the highest 业务优先级 among its rows (gate 43)", self.errors)
                continue
            if level not in TOPIC_PRIORITIES:
                fail(f"topic {tid}: priority must be one of {'/'.join(TOPIC_PRIORITIES)}", self.errors)
            elif is_blank(t.get("priority_basis")):
                fail(f"topic {tid}: priority_basis is empty — a priority with no written basis is not made", self.errors)
            elif row_tiers.get(tid):
                best = ("高", "中", "低")[min(row_tiers[tid])]
                if level != best:
                    self.warnings.append(f"[W46] topic {tid}: priority {level} but its highest row is {best}; "
                                         "主题优先级 takes the highest 业务优先级 in the Topic (2.62.0) — change the rows, not the Topic")

    # ---------- goals and slice tags (W49, W52, W62, W63) ----------

    def check_goals_and_tags(self) -> None:
        goal_checks(self.config, self.questions, self.intents, self.warnings)
        # Gates W62/W63 (Suda 2026-11-03): slice tags cut data across Topics. A value inside one Topic,
        # or under 5 Prompts, duplicates the Topic filter or reads as noise; export drops it either way.
        _, tag_problems, unregistered = _tag_plan(self.config, self.questions)
        for problem in tag_problems:
            self.warnings.append(f"[W62] tag_dimensions: {problem}")
        if unregistered:
            listed = "; ".join(f"{qid}: {'、'.join(tags)}" for qid, tags in list(unregistered.items())[:6])
            self.warnings.append(f"[W63] hand-written tags not registered as a 自定义 value in config.tag_dimensions "
                                 f"({listed}{' …' if len(unregistered) > 6 else ''}); export leaves them out")

    # ---------- conditions and audiences (gate 38; W36, W37, W39) ----------

    # ---------- 约束条件表: brand status and position vs competitors (gates 67, 68; W67) ----------

    def check_constraint_table(self) -> None:
        """config.attribute_plan doubles as the client 约束条件 table (3.11.0; 3.11.2; 3.13.0).

        brand_status 有 / 没有 / 待确认 is required on every entry (a dimension every candidate has is 有; how good
        goes to vs_competitors), each with brand_status_basis (the evidence, or where we looked);
        vs_competitors 明显优势 / 明显劣势 / 持平 / 未知, judged only on public hard facts. An entry may carry
        product_line when the brand has the condition on some lines only; it then applies to that line's Prompts.
        A bank whose rows or Prompts name constraints must have the table (3.13.0: an empty table no longer skips
        gates 67 / 68). A Prompt must not carry a condition the brand does not have or that is still 待确认 (gate 68:
        its attribute_ref, and constraint keywords that equal an option name); a clear advantage nobody measures is
        a warning unless no_carrier_reason says why (W67).
        """
        plan = attribute_plan(self.config)
        rows = slice_index(self.config)
        named = [sid for sid, row in rows.items() if row.get("attributes")]
        refs = [str(q.get("question_id")) for q in self.questions if not is_blank(q.get("attribute_ref"))]
        if not plan:
            if named or refs:
                fail(f"config.attribute_plan (the 约束条件 table) is missing while matrix rows ({len(named)}) or "
                     f"Prompts ({len(refs)}) name constraints; write one entry per constraint with brand_status and "
                     "brand_status_basis (selection-rules.md → 3)", self.errors)
            return
        lacking: dict[str, list[tuple[str, str]]] = {}
        ahead: list[str] = []
        for entry in plan:
            name = str(entry.get("attribute") or "").strip()
            status = str(entry.get("brand_status") or "").strip()
            vs = str(entry.get("vs_competitors") or "").strip()
            line = str(entry.get("product_line") or "").strip()
            if not name:
                fail("config.attribute_plan: every entry needs attribute (the 约束条件 option name)", self.errors)
                continue
            if status not in BRAND_STATUS:
                fail(f"约束条件 {name}: brand_status {status!r} must be one of {' / '.join(BRAND_STATUS)}", self.errors)
            elif is_blank(entry.get("brand_status_basis")):
                fail(f"约束条件 {name}: brand_status {status} needs brand_status_basis (the evidence, or where we "
                     "looked and found nothing)", self.errors)
            if vs and vs not in VS_COMPETITORS:
                fail(f"约束条件 {name}: vs_competitors {vs!r} is not one of {' / '.join(VS_COMPETITORS)}", self.errors)
            if vs in ("明显优势", "明显劣势", "持平") and is_blank(entry.get("vs_competitors_basis")):
                fail(f"约束条件 {name}: vs_competitors {vs} needs vs_competitors_basis (the public figures and which "
                     "competitors)", self.errors)
            if status in ("没有", "待确认"):
                lacking.setdefault(name, []).append((line, status))
            if vs == "明显优势" and is_blank(entry.get("no_carrier_reason")):
                ahead.append(name)
        names = {str(entry.get("attribute") or "").strip() for entry in plan} - {""}
        unknown = [f"{q.get('question_id')}（{q.get('attribute_ref')}）" for q in self.questions
                   if not is_blank(q.get("attribute_ref")) and str(q.get("attribute_ref")).strip() not in names]
        if unknown:
            fail(f"Prompts whose attribute_ref is not in config.attribute_plan ({len(unknown)}): "
                 f"{', '.join(unknown[:8])}{' …' if len(unknown) > 8 else ''}", self.errors)
        carried: dict[str, set[str]] = {}
        bad: list[str] = []
        for q in self.questions:
            q_id = str(q.get("question_id") or "").strip()
            if not q_id:
                continue
            q_names = {str(c).strip() for c in (q.get("constraints") or [])} | {str(q.get("attribute_ref") or "").strip()}
            carried[q_id] = q_names
            q_line = str(q.get("product_line")
                         or (rows.get(str(q.get("slice_ref") or "").strip()) or {}).get("product_line") or "").strip()
            hits = [f"{n}:{status}" for n in sorted(q_names & lacking.keys())
                    for line, status in lacking[n] if not line or line == q_line]
            if hits:
                bad.append(f"{q_id}（{'、'.join(hits)}）")
        if bad:
            fail(f"Prompts carry a condition the brand does not have or has not confirmed (brand_status 没有 / 待确认): "
                 f"{', '.join(bad[:8])}{' …' if len(bad) > 8 else ''}; drop the condition or the Prompt", self.errors)
        idle = [name for name in ahead if not any(name in names for names in carried.values())]
        if idle:
            self.warnings.append(f"[W67] clear advantages no Prompt measures ({len(idle)}): {', '.join(idle)}; write a "
                                 "Prompt on it or say why in no_carrier_reason")

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
                self.warnings.append(f"[W56] status missing on {len(unstated)} Prompts, counted as 待审核 "
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
        pending = [name for entry in plan
                   if (name := str(entry.get("attribute") or "").strip())
                   and name not in self.carried_names and name in self.written_names]
        if pending:
            message = ("attributes carried only by Prompts not yet 已批准, so not counted as covered "
                       f"({len(pending)}): " + ", ".join(sorted(pending)))
            self.warnings.append(f"[W57] {message}")

    # ---------- unused buyer inputs (W35) ----------

    def check_inputs(self) -> None:
        config, questions = self.config, self.questions
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
        # Only public data (first_party_data not true), or a hypothesis-grade set, caps the verdict at Usable.
        capped = config.get("first_party_data") is not True or config.get("evidence_status") == "hypothesis"
        plural = lambda n, word: f"{n} {word}{'s' if n != 1 else ''}"
        if errors:
            readiness = f"Not ready: {plural(len(errors), 'error')} to fix"
        elif open_warnings:
            readiness = f"Usable: {plural(len(open_warnings), 'warning')} without a decision"
        elif capped:
            readiness = "Usable: public data only or hypothesis-grade evidence — list what the brand party still has to supply"
        else:
            readiness = "Ready"

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


def load_args(argv: list[str] | None, description: str | None) -> tuple[Path, dict]:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("bank", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.bank.read_text(encoding="utf-8"))
    return args.bank, data


def main(argv: list[str] | None = None) -> int:
    bank, data = load_args(argv, __doc__)
    markers = legacy_markers(data)
    if markers:
        print(f"ERROR: unsupported old structure in {bank.name}: {'; '.join(markers)}. Old banks are not migrated "
              "and not validated; a bank written now follows references/output-contract.md")
        print("READINESS: Not ready: unsupported old structure")
        return 2
    return BankValidator(data).run()


if __name__ == "__main__":
    raise SystemExit(main())
