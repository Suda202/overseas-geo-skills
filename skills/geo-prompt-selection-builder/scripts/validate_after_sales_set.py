#!/usr/bin/env python3
"""Validate an after-sales Prompt set without presales quota assumptions.

Historical v8 banks omit ``config.generation_stage`` and retain their legacy
shape checks. Staged banks (``selection``; older ``discovery`` / ``diagnostic``) get the selection
checks in references/output-contract.md.
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
}
# Verification and Accuracy are two distinct intents (Suda 2026-10-16): Verification
# covers a capability AI does not recognise, Accuracy a fact AI states wrongly. No aliasing.
# Information (问题解决, after-sales only, Suda 2026-10-19; client label renamed and scope narrowed on 2026-10-26):
# a buyer asking how to solve a problem or reach a goal; AI answers with advice, not a candidate
# list; only own-domain citation is read. Pure knowledge questions are not this type.
# New banks write "selection"; "discovery" / "diagnostic" from banks before 2026-11-02 are still accepted
# and no longer limit which Prompt types a bank may hold.
STAGES = {"selection", "discovery", "diagnostic"}
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
            counts_for_visibility = row.get("formal_visibility_eligible") is not False
            if english and counts_for_visibility and not _prompt_gates.requests_candidates(text):
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
    stage: str | None,
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
    if stage is None:
        return
    # A Competitor verdict hinges on a scenario; with no use case AI answers "it
    # depends". Independent of buyer_quotes, so it runs before the early return below.
    for row in questions:
        if (intents or {}).get(id(row)) == "Competitor" and not row.get("constraints"):
            fail(f"{row.get('question_id')}: Competitor Prompt has no use case (empty constraints); without one "
                 f"AI answers \"it depends\" instead of a verdict — name the scenario the verdict hinges on", errors)
    quote_constraints, quote_texts = _scope_gates.quote_index(config)
    common = common_constraints(config)
    if not quote_constraints and not common:
        warnings.append("[W36] neither attribute_plan common_constraints nor config.buyer_quotes (需求信号): gates 36–37 "
                        "(conditions without a basis, one decision asked twice) were skipped")
        return
    # A condition taken from the attribute's 常见约束 in 属性池 is backed (Suda 2026-11-01): Prompts no longer
    # cite buyer quotes one by one; the quotes back the attribute and its common constraints instead.
    rows = slice_index(config)
    questions = [with_common_basis(row, common, rows) for row in questions]
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


def common_constraints(config: dict) -> dict[str, list[str]]:
    """attribute_plan → {attribute: its 常见约束}, the buyer-side conditions a Prompt may draw from."""
    out: dict[str, list[str]] = {}
    for entry in config.get("attribute_plan") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("attribute") or "").strip()
        raw = entry.get("common_constraints", entry.get("常见约束"))
        items = raw if isinstance(raw, list) else re.split(r"[、，,;；/|]", str(raw or ""))
        values = [str(i).strip() for i in items if str(i).strip()]
        if name and values:
            out[name] = values
    return out


def with_common_basis(row: dict, common: dict[str, list[str]], rows: dict[str, dict] | None = None) -> dict:
    """The Prompt with the 常见约束 of its attribute and of every attribute on its matrix row added to
    condition_basis, for gates 36–37: a Prompt may combine conditions buyers raise in the same situation."""
    names = [str(row.get("attribute_ref") or row.get("attribute") or "").strip()]
    listed = ((rows or {}).get(str(row.get("slice_ref") or "").strip()) or {}).get("attributes") or []
    names += [str(a).strip() for a in ([listed] if isinstance(listed, str) else listed)]
    values = [v for n in dict.fromkeys(names) for v in common.get(n, [])]
    if not values:
        return row
    basis = row.get("condition_basis") or {}
    if not isinstance(basis, dict):
        basis = {str(e.get("condition")): e.get("basis") for e in basis if isinstance(e, dict)}
    return {**row, "condition_basis": {**{v: "属性池常见约束" for v in values}, **basis}}


def audience_values(row: dict) -> list[str]:
    value = row.get("audience")
    if value is None:
        value = row.get("persona") if row.get("persona") is not None else row.get("buyer")
    items = value if isinstance(value, (list, tuple)) else [value]
    return [str(item).strip() for item in items if str(item or "").strip()]


def audience_checks(
    config: dict,
    questions: list[dict],
    stage: str | None,
    warnings: list[str],
    intents: dict[int, str],
) -> None:
    """Gate 39: a Prompt filed under a non-base audience shows who is asking, stated or implied.

    A segment exists because it changes the candidates, the criteria or the
    answer; a Prompt that does not say who is asking is answered for the
    generic buyer, so its audience label measures nothing. Warning only:
    matching the buyer's own words is a heuristic.
    """
    if stage is None:
        return
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
    """Normalize the prompt_type field and inherited presales Prompt Type tags."""
    explicit = str(row.get("prompt_type") or "").strip()
    # 意图 was renamed 提示词类型 on 2026-10-22. Banks written before carry the
    # type under `intent`, and may use `prompt_type` for the retired
    # question-shape label (品类 / 属性 …). Old banks are not migrated: when
    # `intent` holds a valid type and `prompt_type` does not, `intent` wins and
    # the old shape label is ignored. New banks write `prompt_type` only.
    legacy = str(row.get("intent") or "").strip()
    if legacy in INTENTS:
        if explicit in INTENTS and explicit != legacy:
            fail(f"{row.get('question_id')}: prompt_type conflicts with the legacy intent field", errors)
        elif explicit not in INTENTS:
            explicit = legacy
    intent_key = str(row.get("intent_key") or "").strip()
    tag_intents = {
        str(tag).split(":", 1)[1].strip()
        for tag in row.get("tags") or []
        if str(tag).strip().startswith("Prompt Type:")
    }
    if len(tag_intents) > 1:
        fail(f"{row.get('question_id')}: conflicting Prompt Type tags", errors)
    tag_intent = next(iter(tag_intents), "")
    if explicit and explicit not in INTENTS:
        fail(f"{row.get('question_id')}: unsupported prompt_type {explicit!r}", errors)
    if explicit and tag_intent and explicit != tag_intent:
        fail(f"{row.get('question_id')}: prompt_type conflicts with Prompt Type tag", errors)
    if explicit:
        return explicit
    if tag_intent:
        if intent_key in INTENTS and intent_key != tag_intent:
            fail(f"{row.get('question_id')}: intent_key conflicts with Prompt Type tag", errors)
        return tag_intent
    if intent_key in INTENTS:
        return intent_key
    return ""


# ---------- per-Prompt metadata: one canonical field each, older names accepted ----------

# Three journey stages since 2026-11-02 (Suda): 需求认知 / 方案考虑 / 购买决策; no post-purchase stage.
JOURNEY_STAGES = ("需求认知", "方案考虑", "购买决策")
# Eight-stage labels (2026-10-15 → 11-01) are still accepted on older banks and read as three stages.
# 购后支持 has no three-stage home: post-purchase questions are outside selection.
LEGACY_EIGHT_STAGES = {"发现": "方案考虑", "替代方案": "方案考虑", "评估": "购买决策", "对比": "购买决策",
                       "验证": "购买决策", "交易": "购买决策", "解决问题": "需求认知", "购后支持": None}
# The five-stage labels do not map one-to-one (output contract: re-judge each Prompt
# by its content), so they are recognised but never converted.
OLD_JOURNEY_STAGES = {"了解需求", "比较方案", "评估是否适合", "准备购买", "使用与续费"}
GROUP_ROLES = {"core", "experimental", "monitoring"}
# Supported row types. Journey stages describe buyer context independently.
REGISTERED_TYPES = {"Discovery", "Alternatives", "Competitor", "Evaluation", "Information"}
# Prompt types that never count toward the mention-rate KPI. Only Discovery counts since 2026-11-03 (Suda); Alternatives is reported on its own under 竞争定位.
NON_VISIBILITY_INTENTS = {"Category Awareness", "Verification", "Accuracy", "Information"}
# The mention-rate KPI reads these types (Suda 2026-11-02).
KPI_INTENTS = {"Discovery"}
LAYER_TO_ROLE = {"核心": "core", "实验": "experimental", "监测": "monitoring",
                 "core": "core", "experimental": "experimental", "monitoring": "monitoring"}
FIELD_ALIASES = {
    "journey_stage": ("journey_stage_9", "journey"),
    "audience": ("persona", "buyer"),
    "group_role": ("library_layer",),
    "attribute_ref": ("attribute",),
    "evidence_refs": ("buyer_demand_evidence",),
    "constraint_type": ("condition_slot",),
}
# A Prompt states the attribute it tests. Journey stage and audience are read from its matrix row
# (config.slices) and are required on the Prompt only in banks without rows (Suda 2026-11-01).
REQUIRED_STAGED_FIELDS = ("attribute_ref",)
ROWLESS_REQUIRED_FIELDS = ("journey_stage", "audience")
# No-condition Discovery Prompts are not written by default (Suda 2026-10-29): a bare category
# question is owned by category leaders. Judged from constraint_type / condition_slot.
LOW_CONDITION_VALUES = {"无限定", "无限定条件", "低条件", "none", "unconstrained", "no_condition"}
FORMAL_LIFECYCLES = {"locked", "formal_baseline", "active"}
REVIEW_STATUSES = ("待审核", "已批准", "需修改")
REVIEW_ALIASES = {
    **{status: status for status in REVIEW_STATUSES},
    "pending": "待审核", "approved": "已批准", "needs_revision": "需修改",
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


def canonical_value(field: str, value: object) -> object:
    if field == "group_role":
        return LAYER_TO_ROLE.get(str(value).strip(), str(value).strip())
    if field == "evidence_refs":
        return value
    return str(value).strip()


def normalize_fields(row: dict, errors: list[str]) -> dict:
    """Read each canonical field, falling back to its older names.

    Two names holding different values for one Prompt is an error: a reader
    cannot tell which one the downstream metric used.
    """
    qid = row.get("question_id")
    out: dict = {}
    for field, aliases in FIELD_ALIASES.items():
        values = [(name, row[name]) for name in (field, *aliases) if name in row and not is_blank(row[name])]
        if field == "journey_stage":
            # A legacy five-stage label next to a newer one is the old
            # export shape, not a disagreement; the newer value wins.
            eight = [(n, v) for n, v in values if str(v).strip() not in OLD_JOURNEY_STAGES]
            values = eight or values
        if not values:
            out[field] = None if not any(name in row for name in (field, *aliases)) else ""
            continue
        canon = {(name, json.dumps(canonical_value(field, v), ensure_ascii=False, sort_keys=True)) for name, v in values}
        distinct = {c for _, c in canon}
        if len(distinct) > 1 and field != "evidence_refs":
            shown = ", ".join(f"{name}={row[name]!r}" for name, _ in values)
            fail(f"{qid}: {field} disagrees across its field names ({shown})", errors)
        out[field] = canonical_value(field, values[0][1])
    return out


def slice_index(config: dict) -> dict[str, dict]:
    """config.slices by slice_id; empty when the bank has no matrix rows."""
    slices = config.get("slices")
    if not isinstance(slices, list):
        return {}
    return {str(r.get("slice_id") or "").strip(): r for r in slices
            if isinstance(r, dict) and str(r.get("slice_id") or "").strip()}


def field_contract_checks(
    config: dict,
    questions: list[dict],
    intents: dict[int, str],
    stage: str | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if stage is None:
        return  # unstaged historical v8 banks keep their old shape
    formal = config.get("lifecycle_status") in FORMAL_LIFECYCLES
    fields = {id(row): normalize_fields(row, errors) for row in questions}
    qid = lambda row: str(row.get("question_id"))
    # Journey stage and audience live on the matrix row; a Prompt that leaves them out inherits its row's.
    rows = slice_index(config)
    for row in questions:
        source = rows.get(str(row.get("slice_ref") or "").strip())
        if source:
            for field in ROWLESS_REQUIRED_FIELDS:
                if is_blank(fields[id(row)].get(field)) and not is_blank(source.get(field)):
                    fields[id(row)][field] = canonical_value(field, source[field] if isinstance(source[field], str)
                                                             else (source[field][0] if source[field] else ""))

    def report(message: str, rows: list[dict], hard: bool, code: str = "W33") -> None:
        if not rows:
            return
        ids = ", ".join(qid(r) for r in rows[:6]) + (" …" if len(rows) > 6 else "")
        text = f"{message} ({len(rows)} of {len(questions)}: {ids})"
        if hard:
            errors.append(text)
        else:
            warnings.append(f"[{code}] {text}")

    required = REQUIRED_STAGED_FIELDS + (() if rows else ROWLESS_REQUIRED_FIELDS)
    for field in required:
        # attribute_ref may be empty on a category-baseline Prompt; it only has to be stated.
        missing = [r for r in questions if fields[id(r)][field] is None
                   or (field != "attribute_ref" and is_blank(fields[id(r)][field]))]
        report(f"missing {field} (required before lock)", missing, formal)

    stage_of = lambda r: fields[id(r)]["journey_stage"]
    old = [r for r in questions if stage_of(r) in OLD_JOURNEY_STAGES]
    report("journey_stage still uses the old five-stage labels; re-judge into the three stages", old, formal, "W7")
    odd = [r for r in questions if stage_of(r)
           and stage_of(r) not in OLD_JOURNEY_STAGES
           and stage_of(r) not in JOURNEY_STAGES and stage_of(r) not in LEGACY_EIGHT_STAGES]
    report(f"journey_stage is not one of {'/'.join(JOURNEY_STAGES)}", odd, formal, "W7")
    post = [r for r in questions if stage_of(r) == "购后支持"]
    report("journey_stage 购后支持: post-purchase questions are outside selection since 2026-11-02 "
           "(no three-stage home); keep them only on older banks", post, stage == "selection", "W7")
    bad_role = [r for r in questions if fields[id(r)]["group_role"] and fields[id(r)]["group_role"] not in GROUP_ROLES]
    report(f"group_role is not one of {sorted(GROUP_ROLES)}", bad_role, formal, "W58")

    leaking = [r for r in questions if intents.get(id(r)) in NON_VISIBILITY_INTENTS
               and r.get("formal_visibility_eligible") is True]
    report("Category Awareness, Verification, Accuracy and Information Prompts must set formal_visibility_eligible: false", leaking, True)
    # Information is an experimental-layer intent (Suda 2026-10-20): measured, but never in the formal set.
    info_layer = [r for r in questions if intents.get(id(r)) == "Information"
                  and fields[id(r)]["group_role"] and fields[id(r)]["group_role"] != "experimental"]
    report("Information Prompts belong to the experimental layer (group_role: experimental)", info_layer, True)
    # The three layers were dropped on 2026-11-02; banks that still carry group_role keep these two checks.
    comp_layer = [r for r in questions if intents.get(id(r)) == "Competitor"
                  and fields[id(r)]["group_role"] == "core"]
    report("Competitor Prompts belong to the monitoring or experimental layer, not core", comp_layer, True)

    # Balance checks only mean something on the shape they were written for.
    # A Discovery-stage set is mostly 发现 by construction, and a named-brand
    # set has no natural-visibility trend to keep stable.
    # Eight-stage banks only: three-stage banks sit mostly on 方案考虑 by design.
    counted = [r for r in questions if stage_of(r) in LEGACY_EIGHT_STAGES]
    if stage != "discovery" and len(counted) >= 8:
        top, n = Counter(fields[id(r)]["journey_stage"] for r in counted).most_common(1)[0]
        if n / len(counted) > 0.45:
            warnings.append(f"[W58] journey stage {top} holds {n / len(counted):.0%} of Prompts; "
                            "check whether evaluation, comparison and validation decisions are covered")
    discovery = [r for r in questions if intents.get(id(r)) == "Discovery" and fields[id(r)]["group_role"]]
    if len(discovery) >= 5:
        core = sum(fields[id(r)]["group_role"] == "core" for r in discovery)
        if core / len(discovery) < 0.5:
            warnings.append(f"[W58] only {core} of {len(discovery)} Discovery Prompts are core; "
                            "keep most in core so the trend stays comparable")

    # Bare category questions are written only when the brand party asks for the head term
    # (Suda 2026-10-29; the per-Topic low-condition anchor of 2026-10-22 is retired).
    if config.get("leader_default") is not None:
        warnings.append("[W58] config.leader_default is no longer read (2026-10-28)")
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


# Row tiers: 高 / 中 / 低 since 2026-11-01; banks written before use P1 / P2 / P3 (same order).
PRIORITIES = ("P1", "P2", "P3")
TIER_INDEX = {"P1": 0, "高": 0, "P2": 1, "中": 1, "P3": 2, "低": 2}
TOPIC_PRIORITIES = ("高", "中", "低")
CHANGEABILITY = ("高", "中", "低", "待试跑")
RELATIVE_VERDICTS = ("优势", "持平", "劣势", "待确认")


def plan_verdicts(config: dict) -> dict[str, str]:
    """attribute_plan → {attribute: 相对竞品}."""
    out: dict[str, str] = {}
    for entry in config.get("attribute_plan") or []:
        if isinstance(entry, dict) and str(entry.get("attribute") or "").strip():
            out[str(entry["attribute"]).strip()] = str(entry.get("relative_competitor") or entry.get("相对竞品") or "").strip()
    return out


def slice_checks(config: dict, questions: list[dict], topic_ids: set, errors: list[str], warnings: list[str]) -> None:
    """Matrix rows (config.slices) carry the one 业务重要性 judgement (Suda 2026-10-28 / 11-01 / 11-02).

    Each row: {slice_id, topic_id, product_line, audience, scene, journey_stage, attributes, priority,
    priority_basis}; priority is 业务优先级 (Aleyda: commercial value, strategic importance, current business
    focus; Suda 2026-11-05). 高 and 中 rows get Prompts; 低 rows get none by default (W64 when they carry some —
    allowed only to fill 高 / 中 coverage, with a recorded decision). Situations out of scope, without a
    reasonable demand basis, or the brand cannot serve are not opened as rows (they go to notes). Every Prompt sits on a row
    whose Topic it shares. Relative disadvantage is not an exclusion. Priority equals its row's
    unless a priority_change_reason records a business decision.
    Banks without config.slices skip these checks (legacy shape).
    """
    slices = config.get("slices")
    if slices is None:
        return
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
            fail(f"slice {sid}: priority must be 高 / 中 / 低 (legacy P1 / P2 / P3); a situation the brand cannot "
                 "use or serve is not opened as a row", errors)
        elif is_blank(row.get("priority_basis")):
            fail(f"slice {sid}: priority_basis is empty — a priority with no written basis is not made", errors)
        tid = row.get("topic_id")
        if not is_blank(tid) and tid not in topic_ids:
            fail(f"slice {sid}: topic_id {tid!r} is not in config.topics", errors)
        # Gate 60: a row registers which Prompt types it can carry (slices.prompt_types, Suda 2026-11-03).
        # Every non-default type needs a written basis (buyer evidence
        # or an explicit 假设). Rows without the key are older banks and are not checked.
        registered = row.get("prompt_types")
        if registered is not None:
            stage_label = str(row.get("journey_stage") or "").strip()
            stage3 = stage_label if stage_label in JOURNEY_STAGES else LEGACY_EIGHT_STAGES.get(stage_label)
            if not isinstance(registered, list) or not all(isinstance(x, dict) for x in registered):
                fail(f"slice {sid}: prompt_types must be a list of {{type, basis}} objects", errors)
            else:
                for entry in registered:
                    rtype = str(entry.get("type") or "").strip()
                    if rtype not in REGISTERED_TYPES:
                        fail(f"slice {sid}: prompt_types registers {rtype!r}; it must be one of "
                             f"{sorted(REGISTERED_TYPES)} (Verification is an external diagnostic, never registered)", errors)
                        continue
                    default_discovery = rtype == "Discovery" and stage3 == "方案考虑"
                    if not default_discovery and is_blank(entry.get("basis")):
                        fail(f"slice {sid}: prompt_types registers {rtype} with no basis — write the buyer evidence "
                             "or an explicit 「假设：……」; a type with neither is not registered", errors)
    # Category Awareness is the research pre-run before the attribute pool, never a bank Prompt (Suda 2026-10-29).
    ca = [str(q.get("question_id")) for q in questions
          if str(q.get("prompt_type") or q.get("intent") or "").strip() == "Category Awareness"]
    if ca:
        fail(f"Category Awareness Prompts in the bank ({len(ca)}): {', '.join(ca)}; it runs once per platform "
             "before the attribute pool as research and is not written into the bank", errors)
    verdicts = plan_verdicts(config)
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
        tier = str(row.get("priority") or "").strip()
        # Gate 61: a Prompt's type must be registered on its row (rows with prompt_types only).
        # Legacy diagnostic types are outside registered selection types.
        registered = row.get("prompt_types")
        if isinstance(registered, list) and all(isinstance(x, dict) for x in registered):
            qtype = str(q.get("prompt_type") or q.get("intent") or "").strip()
            allowed = {str(x.get("type") or "").strip() for x in registered}
            if qtype in REGISTERED_TYPES and qtype not in allowed:
                fail(f"{qid}: prompt_type {qtype} is not registered on row {ref} (registered: "
                     f"{', '.join(sorted(allowed)) or 'none'}); register it with its basis, or move the Prompt", errors)
        if TIER_INDEX.get(tier) == 2:
            low_carried.append(f"{qid}({ref})")
        if not is_blank(row.get("topic_id")) and q.get("topic_id") != row.get("topic_id"):
            fail(f"{qid}: topic_id {q.get('topic_id')!r} differs from its row {ref}'s {row.get('topic_id')!r}", errors)
        change = str(q.get("changeability") or "").strip()
        if change and change not in CHANGEABILITY:
            fail(f"{qid}: changeability must be one of {'/'.join(CHANGEABILITY)}", errors)
        own = str(q.get("priority") or "").strip()
        if own and tier in TIER_INDEX:
            expected = TIER_INDEX[tier]
            if TIER_INDEX.get(own) != expected and is_blank(q.get("priority_change_reason")):
                warnings.append(f"[W55] {qid}: priority {own} differs from the expected tier "
                                f"(row {ref} {tier}, 可改变性 {change or '待试跑'}) with no priority_change_reason")
    # Gate 48: 高 and 中 方案考虑 rows are the ones written this period; one with no Prompt is either an
    # omission or a deliberate skip that needs a warning decision. 需求认知 / 购买决策 rows are opened on
    # buyer evidence whatever the brand picked; their types follow the step-1 goals, so a row with no
    # Prompt there is the expected "本期不出" (Suda 2026-11-02).
    bare = [sid for sid, row in by_id.items()
            if TIER_INDEX.get(str(row.get("priority") or "").strip()) in (0, 1) and not per_row[sid]
            and str(row.get("journey_stage") or "").strip() not in ("需求认知", "购买决策")]
    if bare:
        warnings.append(f"[W48] 高 / 中 方案考虑 rows with no Prompt ({len(bare)}): {', '.join(bare[:8])}{' …' if len(bare) > 8 else ''}; "
                        "write their Prompts, or record why this row gets none")
    if low_carried:
        warnings.append(f"[W64] Prompts on 低 rows ({len(low_carried)}): {', '.join(low_carried[:8])}{' …' if len(low_carried) > 8 else ''}; "
                        "低 rows get no Prompts by default — keep them only to fill 高 / 中 coverage and record the decision")
    if unfiled:
        warnings.append(f"[W53] Prompts with no slice_ref ({len(unfiled)}): "
                        f"{', '.join(unfiled[:6])}{' …' if len(unfiled) > 6 else ''}; every Prompt sits on a matrix row")
    # attribute_plan is the 买方约束 list (the client Base has no attribute pool since 2026-11-04). A verdict, when
    # given, is one of 优势 / 持平 / 劣势 / 待确认 and 优势 / 持平 / 劣势 carry a written basis; banks written after
    # 2026-11-04 may leave it empty (judged after the baseline). A row lists plan names only.
    plan = config.get("attribute_plan")
    if not plan or not isinstance(plan, list) or not all(isinstance(e, dict) for e in plan):
        return
    for entry in plan:
        name = str(entry.get("attribute") or "").strip()
        if not name:
            continue
        verdict = verdicts.get(name, "")
        if not verdict:  # 2026-11-04 起相对竞品在基线后判，写题前可以不填
            continue
        if verdict not in RELATIVE_VERDICTS:
            fail(f"attribute_plan {name!r}: relative_competitor must be one of {'/'.join(RELATIVE_VERDICTS)}, "
                 f"got {verdict!r}", errors)
        elif verdict != "待确认" and is_blank(entry.get("relative_competitor_basis") or entry.get("相对竞品依据")):
            fail(f"attribute_plan {name!r}: relative_competitor_basis is empty — a verdict with no written basis "
                 "is not made", errors)
    for sid, row in by_id.items():
        listed = row.get("attributes") or []
        listed = [listed] if isinstance(listed, str) else listed
        absent = [str(a).strip() for a in listed if str(a).strip() and str(a).strip() not in verdicts]
        if absent:
            fail(f"slice {sid}: attributes absent from attribute_plan: {', '.join(absent)}", errors)


def topic_checks(config: dict, questions: list[dict], intents: dict[int, str],
                 errors: list[str], warnings: list[str], stage: str | None = None) -> None:
    """Topics are the unit the brand party buys (Suda 2026-10-31 / 11-01).

    Every Topic holds a Discovery Prompt. W59 is a coverage review prompt,
    not a statistical guarantee or an instruction to merge buyer tasks.
    """
    rows = slice_index(config)
    topics = [t for t in config.get("topics") or [] if isinstance(t, dict)]
    by_topic: dict[object, list[dict]] = {}
    for q in questions:
        by_topic.setdefault(q.get("topic_id"), []).append(q)
    empty = sorted(str(t.get("topic_id")) for t in topics if not by_topic.get(t.get("topic_id")))
    if empty and questions:
        fail(f"Topics with no Prompt ({len(empty)}): {', '.join(empty)}; drop them or file Prompts under them", errors)
    no_discovery = sorted(str(tid) for tid, items in by_topic.items()
                          if items and not any(intents.get(id(r)) == "Discovery" for r in items))
    if no_discovery:
        fail(f"Topics with no Discovery Prompt ({len(no_discovery)}): {', '.join(no_discovery)}; "
             "a purchased Topic needs a Discovery Prompt — add one or file these "
             "Prompts under the Topic of the same buyer need", errors)
    if stage == "selection":
        floor = []
        for tid, items in sorted(by_topic.items(), key=lambda kv: str(kv[0])):
            kpi = [q for q in items if intents.get(id(q)) in KPI_INTENTS
                   and str(q.get("status") or "").strip() != "停测"]
            decisions = {(str(q.get("attribute_ref") or "").strip(),
                          tuple(sorted(str(c).strip() for c in (q.get("constraints") or []))))
                         for q in kpi}
            if kpi and (len(kpi) < 5 or len(decisions) < 4):
                floor.append(f"{tid}: {len(kpi)} KPI Prompts / {len(decisions)} decision signatures")
        if floor:
            warnings.append(f"[W59] Topics below the default coverage target ({'; '.join(floor)}); "
                            "in order: (1) add missed buyer constraints, scenes, audiences or limits; (2) build compound "
                            "conditions with real purchase meaning — never pad with synonyms, reordering or mechanical "
                            "condition permutations; (3) check over-splitting — merge only adjacent Topics of the same "
                            "purchase decision with similar candidate solutions. Record the decision if still short.")
    # Topic priority is summarised, not judged again (Suda 2026-11-05): by default the tier most of its rows carry;
    # a tie has no default and needs a human call. Tier differences are never a reason to split a Topic.
    row_tiers: dict = {}
    for r in rows.values():
        idx = TIER_INDEX.get(str(r.get("priority") or "").strip())
        if idx is not None and r.get("topic_id"):
            row_tiers.setdefault(r.get("topic_id"), []).append(idx)
    for t in topics:
        tid, level = t.get("topic_id"), str(t.get("priority") or "").strip()
        if not level:
            continue  # banks written before topic priority came back (2026-11-01)
        if level not in TOPIC_PRIORITIES:
            fail(f"topic {tid}: priority must be one of {'/'.join(TOPIC_PRIORITIES)}", errors)
        elif is_blank(t.get("priority_basis")):
            fail(f"topic {tid}: priority_basis is empty — a priority with no written basis is not made", errors)
        elif row_tiers.get(tid):
            counts = Counter(row_tiers[tid])
            top = max(counts.values())
            leaders = [i for i, n in counts.items() if n == top]
            if len(leaders) > 1:
                warnings.append(f"[W46] topic {tid}: rows split evenly across tiers, no majority; decide 主题优先级 by hand "
                                "and record the reason")
            elif level != ("高", "中", "低")[leaders[0]]:
                warnings.append(f"[W46] topic {tid}: priority {level} but most of its rows are {('高', '中', '低')[leaders[0]]}; "
                                "主题优先级 defaults to the tier most of its rows carry — record the reason if overridden")


BUSINESS_GOALS = ("发现型可见度", "竞争定位", "品牌呈现", "声誉与信任")


def goal_checks(config: dict, questions: list[dict], intents: dict[int, str], warnings: list[str]) -> None:
    """Gates 49–52 (Suda 2026-11-02 审核清单 B2): the brand party's goals decide which Prompt types are written.

    config.business_goals = {selected: [goals in the brand party's order], information_named: bool}. Only
    generation_stage "selection" banks are checked; presales banks declare config.extra_prompt_types instead
    and are skipped. Alternatives belong to 竞争定位.
    Verification is outside selection banks and rejected by the main type check.
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
    rows = slice_index(config)
    decision_rows = sorted(sid for sid, r in rows.items()
                           if str(r.get("journey_stage") or "").strip() == "购买决策"
                           and TIER_INDEX.get(str(r.get("priority") or "").strip()) in (0, 1))
    if "竞争定位" in chosen and not by_type.get("Competitor"):
        shown = ", ".join(decision_rows[:8]) + (" …" if len(decision_rows) > 8 else "")
        warnings.append("[W50] business_goals selects 竞争定位 but the bank holds no Competitor Prompt "
                        f"(高 / 中 购买决策 rows: {shown or 'none opened'}); write the 对比 Prompts the step-1 "
                        "evidence supports, or record why none is written")
    if "声誉与信任" in chosen and not by_type.get("Evaluation"):
        warnings.append("[W51] business_goals selects 声誉与信任 but the bank holds no Evaluation Prompt; write the 评价 "
                        "Prompts the step-1 evidence supports, or record why none is written")
    unasked = [(t, label) for t, label, ok in (
        ("Competitor", "竞争定位", "竞争定位" in chosen),
        ("Alternatives", "竞争定位", "竞争定位" in chosen),
        ("Evaluation", "声誉与信任", "声誉与信任" in chosen),
        ("Information", "information_named", named_info),
    ) if not ok and by_type.get(t)]
    for t, label in unasked:
        ids = by_type[t]
        warnings.append(f"[W52] {t} Prompts written without the goal {label} in business_goals ({len(ids)}): "
                        f"{', '.join(ids[:8])}{' …' if len(ids) > 8 else ''}; drop them or record the goal")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("--previous", type=Path, help="Previous monitoring set for version checks")
    args = parser.parse_args()

    data = json.loads(args.bank.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config") or {}
    topics = config.get("topics") or []
    questions = data.get("questions") or []
    stage = config.get("generation_stage")
    legacy_full_bank = stage is None
    if stage is not None and (not isinstance(stage, str) or stage not in STAGES):
        fail(f"config.generation_stage must be one of {sorted(STAGES)}", errors)

    mode = data.get("mode")
    if mode != "after-sales-strategic-topics":
        fail("root mode must be after-sales-strategic-topics", errors)
    if not topics:
        fail("config.topics must contain at least one Topic", errors)
    if config.get("expected_total") is not None and len(questions) != config.get("expected_total"):
        fail("config.expected_total, when given, must equal question count", errors)

    topic_ids = {topic.get("topic_id") for topic in topics if topic.get("topic_id")}
    if len(topic_ids) != len(topics):
        fail("Topic IDs must be unique", errors)
    if any(not str(topic.get("topic") or "").strip() for topic in topics):
        fail("Topic names must be non-empty", errors)
    if legacy_full_bank and any(len(str(topic.get("topic") or "")) > 48 for topic in topics):
        fail("Topic names are too long", errors)

    if not legacy_full_bank:
        slice_checks(config, questions, topic_ids, errors, warnings)

    role_counts: Counter[str] = Counter()
    row_intents: dict[int, str] = {}
    topic_counts: Counter[str] = Counter()
    normalized_queries: set[str] = set()
    question_ids: set[str] = set()
    for row in questions:
        question_id = str(row.get("question_id") or "").strip()
        if not question_id:
            fail("question_id is required", errors)
        elif question_id in question_ids:
            fail(f"{question_id}: duplicate question_id", errors)
        question_ids.add(question_id)
        topic_id = row.get("topic_id")
        if topic_id not in topic_ids:
            fail(f"{question_id}: unknown topic_id", errors)
        topic_counts[topic_id] += 1
        intent = normalized_intent(row, errors)
        row_intents[id(row)] = intent
        role_counts[intent] += 1
        if stage == "selection" and intent == "Verification":
            fail(f"{question_id}: Verification is a temporary zero-mention diagnostic outside the question bank", errors)
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
        # monitoring_prompt is optional (Suda 2026-11-01); when an older bank carries it, it equals the query.
        if "monitoring_prompt" in row and row.get("monitoring_prompt") != row.get("user_question"):
            fail(f"{question_id}: monitoring_prompt mismatch", errors)
        # `tags` is optional. Empty means "nothing to add beyond the other
        # fields"; a `Prompt Type:` tag restating prompt_type is neither required
        # nor rejected, so inherited presales v8 rows still normalise through
        # `normalized_intent`.
        query_key = " ".join(user_question.casefold().split())
        if query_key in normalized_queries:
            fail(f"{row.get('question_id')}: duplicate query", errors)
        normalized_queries.add(query_key)

    # Gate 47 (Suda 2026-11-02): a candidate bank for one product line in one market holds about 30–60
    # Prompts. Outside that range something upstream is off (attributes too narrow or wide, too few or many
    # rows, splits not by decision). Warning only; never pad to reach 30. Verification Prompts take no slot.
    if stage is not None and config.get("lifecycle_status") not in FORMAL_LIFECYCLES:
        lines: Counter[str] = Counter()
        slice_rows = slice_index(config)
        for row in questions:
            if row_intents.get(id(row)) == "Verification" or str(row.get("status") or "").strip() == "停测":
                continue
            line = row.get("product_line") or (slice_rows.get(str(row.get("slice_ref") or "").strip()) or {}).get("product_line")
            lines[str(line or "").strip() or "—"] += 1
        off = [f"{line}: {n}" for line, n in sorted(lines.items()) if not 30 <= n <= 60]
        if off:
            warnings.append(f"[W47] candidate Prompt count outside 30–60 per product line ({'; '.join(off)}); check whether "
                            "attributes are too narrow or wide, too few or many rows are open, or splits follow "
                            "decision differences — never pad to reach 30")

    wording_checks(config, questions, row_intents, errors, warnings)
    field_contract_checks(config, questions, row_intents, stage, errors, warnings)
    if not legacy_full_bank:
        topic_checks(config, questions, row_intents, errors, warnings, stage)
    # Gates 49–52: selection banks only; presales banks carry extra_prompt_types instead.
    if stage == "selection" and "extra_prompt_types" not in config:
        goal_checks(config, questions, row_intents, warnings)
        # Gates W62/W63 (Suda 2026-11-03): slice tags cut data across Topics. A value inside one Topic,
        # or under 5 Prompts, duplicates the Topic filter or reads as noise; export drops it either way.
        _, tag_problems, unregistered = _tag_plan(config, questions)
        for problem in tag_problems:
            warnings.append(f"[W62] tag_dimensions: {problem}")
        if unregistered:
            listed = "; ".join(f"{qid}: {'、'.join(tags)}" for qid, tags in list(unregistered.items())[:6])
            warnings.append(f"[W63] hand-written tags not registered as a 自定义 value in config.tag_dimensions "
                            f"({listed}{' …' if len(unregistered) > 6 else ''}); export leaves them out")
    scope_checks(config, questions, stage, errors, warnings, row_intents)
    audience_checks(config, questions, stage, warnings, row_intents)

    # Attribute <-> Prompt alignment. Dropping a Topic takes its Prompts with it
    # but leaves the Attributes behind, so a plan row can silently end up with
    # nothing that measures it. Every row must either be carried by at least one
    # Prompt or state why it is not, and an uncarried row must never outrank the
    # rows we actually measure.
    plan = config.get("attribute_plan") or []
    if plan and (not isinstance(plan, list) or not all(isinstance(entry, dict) for entry in plan)):
        # 2026-09-28 前的旧写法是 {note, p1, p2, p3} 字典；对齐门禁只认逐行对象，不硬转换以免中英文名对不上被误报。
        fail(
            "attribute_plan must be a list of {attribute, priority, no_carrier_reason} rows; "
            "legacy {p1, p2, p3} plans must be migrated before the alignment gate can check them",
            errors,
        )
        plan = []
    # review_status mirrors the review values of the client Base 提示词库 状态 column. Once any Prompt carries it,
    # only 已批准 Prompts count as covering an attribute, the same rule as the
    # Base 覆盖情况 formula. Banks written before the column existed keep the
    # old any-Prompt rule.
    # 状态 (status) carries the same review values when review_status is absent (Suda 2026-11-01).
    review_of = lambda row: row.get("review_status") if "review_status" in row else (
        row.get("status") if str(row.get("status") or "").strip() in REVIEW_ALIASES else None)
    review_active = any(review_of(row) is not None for row in questions)
    review_counts: Counter[str] = Counter()
    approved_rows = questions
    if review_active:
        unstated: list[str] = []
        approved_rows = []
        for row in questions:
            raw = review_of(row)
            if is_blank(raw):
                unstated.append(str(row.get("question_id")))
                status = "待审核"
            else:
                status = REVIEW_ALIASES.get(str(raw).strip().casefold(), "")
                if not status:
                    fail(f"{row.get('question_id')}: review_status must be one of "
                         f"{'/'.join(REVIEW_STATUSES)} (状态 may also be 正式 / 停测), got {raw!r}", errors)
                    status = "待审核"
            review_counts[status] += 1
            if status == "已批准":
                approved_rows.append(row)
        if unstated:
            warnings.append(f"[W56] review_status missing on {len(unstated)} Prompts, counted as 待审核 "
                            f"({', '.join(unstated[:6])}{' …' if len(unstated) > 6 else ''})")

    def carried_by(rows: list[dict]) -> set[str]:
        names: set[str] = set()
        for row in rows:
            for tag in row.get("tags") or []:
                names.add(str(tag).strip())
            for field in ("attribute_ref", "attribute"):
                value = str(row.get(field) or "").strip()
                if value:
                    names.add(value)
        return names

    matrix_bank = not legacy_full_bank and bool(slice_index(config))
    if plan:
        carried_names = carried_by(approved_rows)
        written_names = carried_by(questions)
        review_done = lifecycle_after_review(config)
        pending: list[str] = []
        uncarried: list[str] = []
        for entry in plan:
            name = str(entry.get("attribute") or "").strip()
            if not name or name in carried_names:
                continue
            if name in written_names:
                pending.append(f"{name}({str(entry.get('priority') or '').strip() or '?'})")
                continue
            reason = str(
                entry.get("no_carrier_reason")
                or entry.get("demoted_reason")
                or ""
            ).strip()
            # 劣势 attributes get no Prompt (Suda 2026-10-28 / 10-31); the verdict is the reason.
            if not reason and str(entry.get("relative_competitor") or entry.get("相对竞品") or "").strip() == "劣势":
                continue
            # Matrix banks (Suda 2026-11-02): only an 优势 attribute with no Prompt needs a written reason.
            if not reason and matrix_bank and str(entry.get("relative_competitor") or entry.get("相对竞品") or "").strip() != "优势":
                continue
            if not reason:
                uncarried.append(name)
            elif str(entry.get("priority") or "").strip() == "P1":
                fail(
                    f"attribute {name!r} carries no Prompt but is ranked P1; "
                    "P1 requires a Prompt that measures it",
                    errors,
                )
        if uncarried:
            fail(
                "attributes with no carrying Prompt and no no_carrier_reason "
                f"({len(uncarried)}): " + ", ".join(sorted(uncarried)),
                errors,
            )
        if pending:
            message = ("attributes carried only by Prompts not yet 已批准, so not counted as covered "
                       f"({len(pending)}): " + ", ".join(sorted(pending)))
            (errors if review_done else warnings).append(message if review_done else f"[W57] {message}")

    # Topic ← P1 clustering consistency. covered_attributes must name real plan
    # rows, and every P1 must be homed in some Topic or state why it is not —
    # a Topic that no P1 opened, or a P1 that no Topic measures, is the
    # clustering drifting after the fact.
    declared_topics = [t for t in topics if isinstance(t, dict) and t.get("covered_attributes")]
    # Legacy banks only: since 2026-10-28 Topics are clustered from matrix rows (config.slices).
    if plan and declared_topics and config.get("slices") is None:
        plan_rows = {str(entry.get("attribute") or "").strip(): entry for entry in plan}
        homed: set[str] = set()
        for topic in declared_topics:
            for name in topic.get("covered_attributes") or []:
                name = str(name).strip()
                homed.add(name)
                if name and name not in plan_rows:
                    fail(f"topic {topic.get('topic_id')}: covered_attributes names {name!r}, "
                         "absent from attribute_plan", errors)
        unhomed = sorted(
            name for name, entry in plan_rows.items()
            if name and str(entry.get("priority") or "").strip() == "P1" and name not in homed
        )
        if unhomed:
            fail("P1 attributes homed in no Topic's covered_attributes "
                 f"({len(unhomed)}): " + ", ".join(unhomed)
                 + "; re-home each one or demote it with a reason — P1 requires a Topic that measures it",
                 errors)

    lifecycle = config.get("lifecycle_status")
    if lifecycle is not None and lifecycle not in LIFECYCLE_STATES:
        fail(f"config.lifecycle_status must be one of {sorted(LIFECYCLE_STATES)}", errors)

    # Evidence source diversity (warning only, from customer_confirmed on).
    # A formal set whose evidence all comes from one source family usually
    # means the signal pass skipped sources, not that buyers only speak there.
    if stage is not None and lifecycle_after_review(config):
        refs = [str(ref).strip() for row in approved_rows
                for ref in (row.get("evidence_refs") or []) if str(ref).strip()]
        if refs:
            families = Counter(evidence_source_family(ref) for ref in refs)
            unclassified = families.pop("未分类", 0)
            if unclassified <= len(refs) / 2 and len(families) < 3:
                found = "、".join(sorted(families)) or "none recognised"
                warnings.append(
                    f"[W34] evidence spans only {len(families)} source families ({found}); "
                    "the signal pass covers search data, sales records, reviews and "
                    "community — check whether the missing families were collected"
                )

    # Unused buyer-language inputs (warning only). When the bank carries the
    # collected 需求信号 index, every input should either back a Prompt or have
    # been consciously set aside; silently unused inputs are the cheapest
    # evidence for the next expansion round.
    audience_inputs = config.get("audience_inputs") or []
    if audience_inputs and isinstance(audience_inputs, list):
        # Quotes back Prompts or, since 2026-11-01, the attributes and their 常见约束 (Prompts no longer cite them).
        all_refs = " ".join(
            str(ref) for row in questions for ref in (row.get("evidence_refs") or [])
        ) + json.dumps([config.get("attribute_plan") or [], config.get("slices") or []], ensure_ascii=False)
        unused: list[str] = []
        for entry in audience_inputs:
            input_id = str(entry.get("input_id") if isinstance(entry, dict) else entry or "").strip()
            if input_id and input_id not in all_refs:
                unused.append(input_id)
        if unused:
            warnings.append(
                f"[W35] audience inputs referenced by no Prompt ({len(unused)}): "
                + ", ".join(unused[:8]) + (" …" if len(unused) > 8 else "")
                + "; cite each in an attribute's evidence or a Prompt, or record why it was set aside"
            )

    # Unstaged historical v8 remains compatible with the old complete-bank
    # validator. New staged artifacts do not inherit its fixed quotas.
    if legacy_full_bank:
        if not 3 <= len(topics) <= 10:
            fail(f"legacy first-stage Topic count must be 3-10, got {len(topics)}", errors)
        if any(count < 5 or count > 15 for count in topic_counts.values()):
            fail(f"legacy Topic counts must be 5-15: {dict(topic_counts)}", errors)
        if role_counts.get("Competitor", 0) > 0 and role_counts["Competitor"] != 1:
            fail("legacy starter set expects one Competitor Prompt", errors)
        if role_counts.get("Category Awareness", 0) > 1:
            fail("legacy Category Awareness must not be duplicated by default", errors)
    elif lifecycle in {"customer_confirmed", "locked", "formal_baseline", "active"}:
        # No Prompt floor per Topic (Suda 2026-10-30): a Topic holds as many Prompts as it has
        # distinct decision needs; the formal count is not a clustering concern.
        # 交付范围（Suda 2026-11-05）：正式题每条产品线 × 每个国家 × 每种语言合计最多 60 条，单个主题不设上限
        # （一个题库 = 一个国家 × 一种语言，所以在题库内按产品线数）；候选阶段（customer_confirmed）不设上限。
        if lifecycle in {"locked", "formal_baseline", "active"}:
            formal_slices = slice_index(config)
            per_line: Counter[str] = Counter()
            for row in questions:
                if row_intents.get(id(row)) == "Verification" or str(row.get("status") or "").strip() == "停测":
                    continue
                line = row.get("product_line") or (formal_slices.get(str(row.get("slice_ref") or "").strip()) or {}).get("product_line")
                per_line[str(line or "").strip() or "—"] += 1
            over = {line: n for line, n in sorted(per_line.items()) if n > 60}
            if over:
                fail(
                    "formal set allows at most 60 Prompts per product line × country × language; "
                    f"move the rest out of the deliverable set: {over}",
                    errors,
                )

    evidence_status = config.get("evidence_status")
    if evidence_status in {"hypothesis", "after_sales_signal"} and lifecycle in {
        "locked",
        "formal_baseline",
        "active",
    }:
        fail("hypothesis or after_sales_signal evidence cannot be marked formal-ready", errors)

    confirmation = config.get("customer_confirmation") or {}
    if lifecycle in {"customer_confirmed", "locked", "formal_baseline", "active"}:
        if confirmation.get("status") not in {"confirmed", "locked"}:
            fail("customer confirmation is required before formal-ready lifecycle states", errors)
        if confirmation.get("scope_status") != "confirmed":
            fail("customer_confirmation.scope_status must be confirmed before trial", errors)
    if lifecycle in {"locked", "formal_baseline", "active"}:
        if confirmation.get("prompt_set_status") != "confirmed":
            fail("customer_confirmation.prompt_set_status must be confirmed after trial", errors)

    prompt_version = config.get("prompt_version")
    if lifecycle in {"locked", "formal_baseline", "active"} and not str(prompt_version or "").strip():
        fail("prompt_version is required before formal baseline", errors)

    trial = config.get("trial") or {}
    if trial or lifecycle in {"locked", "formal_baseline", "active"}:
        # trial = 候选题质量试跑：每题在每个监测平台各 3 次（异常补到 5 次封顶）。候选基线已于 2026-10-23 取消，不再多平台 × 5 次。
        # 旧题库写的 5 仍接受，不迁移。
        planned = trial.get("planned_runs")
        if isinstance(planned, bool) or not isinstance(planned, int) or planned not in {3, 5}:
            fail("trial.planned_runs must be 3 (quality trial on each monitored platform; legacy 5 still accepted)", errors)
    if trial.get("status") in {"running", "passed"} and confirmation.get("scope_status") != "confirmed":
        fail("customer_confirmation.scope_status must be confirmed before trial", errors)
    if lifecycle in {"locked", "formal_baseline", "active"}:
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
        # 正式基线：每个 query × 平台 × 国家 × 语言跑 30 次（Suda 2026-10-23）。是否跨天由项目约定，写在 collection_config。
        # 旧题库的 5 与 window_days × runs_per_day（3–7）兼容，不迁移。
        runs = baseline.get("planned_runs")
        if runs is None and "window_days" in baseline:
            days, per_day = baseline.get("window_days"), baseline.get("runs_per_day", 1)
            legacy = days * per_day if all(isinstance(v, int) and not isinstance(v, bool) for v in (days, per_day)) else None
            if not isinstance(legacy, int) or not 3 <= legacy <= 7:
                fail("legacy baseline window_days x runs_per_day must total 3 to 7", errors)
        elif isinstance(runs, bool) or not isinstance(runs, int) or runs not in {5, 30}:
            fail("baseline.planned_runs must be 30 (per query x platform x country x language; legacy 5 still accepted)", errors)
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

    if args.previous:
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
        previous_collection = (previous.get("config") or {}).get("collection_config") or {}
        if any(
            collection.get(field) and previous_collection.get(field)
            and collection[field] != previous_collection[field]
            for field in ("market", "language")
        ):
            fail("previous bank must use the same market and language", errors)
        if monitored_set(data) != monitored_set(previous):
            old_version = (previous.get("config") or {}).get("prompt_version")
            if not prompt_version or old_version == prompt_version:
                fail("prompt_version must change when the monitored set changes", errors)

    # Warnings never change the exit code: each one needs a human decision, and
    # rewording a Prompt only to silence a heuristic is not a fix.
    # Each warning is handled by a written decision in config.warning_decisions:
    # [{"match": "<text in the warning>", "decision": "已改写 / 保留：理由"}] (Suda 2026-10-31), or, for a whole
    # class, [{"gate": "W39", "decision": "保留：理由"}] — every warning opens with its stable code "[Wnn]"
    # (Suda 2026-11-02 审核清单 D5).
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
                "topics": len(topics),
                "prompts": len(questions),
                "prompts_per_topic": dict(topic_counts),
                "prompt_types": dict(role_counts),
                "generation_stage": stage or "legacy_full_bank",
                **({"review_status": dict(review_counts)} if review_active else {}),
                "warnings": len(warnings),
                "warnings_handled": len(handled),
                "readiness": readiness,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
