#!/usr/bin/env python3
"""Validate an after-sales Prompt set without presales quota assumptions.

Historical v8 banks omit ``config.generation_stage`` and retain their legacy
shape checks. New Discovery/Diagnostic artifacts opt into stage-aware checks.
"""

from __future__ import annotations

import argparse
import csv
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
# Information (信息, after-sales only, Suda 2026-10-19): a buyer's own policy / process / cost /
# dispute question that AI answers with advice, not a candidate list; only own-domain citation is read.
STAGES = {"discovery", "diagnostic"}
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
                warnings.append(f"{qid}: reads as {detected}, but the collection language is {latin_name}")
        if script == "latin":
            words = latin_words(text)
            has_mark = "?" in text or "？" in text
            if len(words) <= 4:
                warnings.append(f"{qid}: too short to carry a buyer situation ({len(words)} words)")
            elif len(words) <= 6 and not has_mark and text == text.casefold():
                warnings.append(f"{qid}: reads like a search keyword, not a question asked to an AI")
            if len(words) > 40:
                warnings.append(f"{qid}: over-constrained ({len(words)} words); check it is not a one-off niche")
        if text.count("?") + text.count("？") > 1:
            warnings.append(f"{qid}: asks more than one question; split so each Prompt tests one decision")
        allowed = allowed_currencies(str(row.get("region") or collection.get("market") or ""))
        if allowed:
            used = {code for code, pattern in CURRENCY_PATTERNS if re.search(pattern, text)}
            if used - allowed:
                warnings.append(f"{qid}: uses currency {sorted(used - allowed)} outside the market's {sorted(allowed)}")

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
            warnings.append(f"{a.get('question_id')} / {b.get('question_id')}: near-duplicate wording "
                            f"({sim:.0%} overlap); keep both only if the purchase decision differs")
        elif same_slice and sim >= 0.35:
            warnings.append(f"{a.get('question_id')} / {b.get('question_id')}: same Topic, intent and attribute "
                            f"with overlapping wording ({sim:.0%}); check they test different decisions")


def scope_checks(
    config: dict,
    questions: list[dict],
    stage: str | None,
    errors: list[str],
    warnings: list[str],
    intents: dict[int, str] | None = None,
) -> None:
    """Gates 36–37: conditions outside the cited evidence; one decision asked twice.

    Both need the bank's buyer-quote table (`config.buyer_quotes`, the 买家原话
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
    if not quote_constraints:
        warnings.append("config.buyer_quotes missing: gates 36–37 (conditions outside the 约束 column, one "
                        "decision asked twice) were skipped; carry the 买家原话 rows (输入编号 / 原话 / 约束) in the bank")
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
            fail(f"{qid}: condition outside the cited evidence {outside}; cite the 买家原话 whose 约束 "
                 f"carries it, add it to that quote's 约束 if research supports it, or drop it from the Prompt",
                 errors)
    if unknown:
        shown = ", ".join(f"{q} {refs}" for q, refs in list(unknown.items())[:6])
        warnings.append(f"evidence_refs not in config.buyer_quotes ({len(unknown)} Prompts): {shown}"
                        f"{' …' if len(unknown) > 6 else ''}")
    for group in _scope_gates.repeated_decisions(questions, quote_constraints):
        warnings.append(f"{' / '.join(group)}: same Topic, attribute and evidence-backed constraints — one "
                        f"purchase decision asked {len(group)} times; keep one, or give the others a "
                        f"condition their evidence carries")


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
    for row in questions:
        audiences = [a for a in audience_values(row) if a not in base]
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
        warnings.append(f"config.audience_terms missing: gate 39 (wording names the non-base audience) was "
                        f"skipped for {len(used)} audiences; register each audience's own words from its 买家原话")
        return
    missing = sorted(a for a in used if not [t for t in terms.get(a) or [] if fold(t)])
    if missing:
        warnings.append(f"audiences with no entry in config.audience_terms ({len(missing)}): {', '.join(missing)}")
    if unnamed:
        warnings.append(f"Prompts filed under a non-base audience whose wording neither states nor implies it ({len(unnamed)}): "
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

JOURNEY_STAGES = ("发现", "解决问题", "评估", "对比", "替代方案", "验证", "交易", "购后支持")
# The five-stage labels do not map one-to-one (output contract: re-judge each Prompt
# by its content), so they are recognised but never converted.
OLD_JOURNEY_STAGES = {"了解需求", "比较方案", "评估是否适合", "准备购买", "使用与续费"}
GROUP_ROLES = {"core", "experimental", "monitoring"}
# Which journey stages each after-sales intent can sit on.
INTENT_STAGES = {
    "Discovery": {"发现", "解决问题", "交易"},
    "Category Awareness": {"发现", "解决问题"},
    # Competitor keeps 替代方案 for banks written before Alternatives split out
    # (2026-10-22); new banks type named-competitor alternatives as Alternatives.
    "Competitor": {"对比", "替代方案"},
    "Alternatives": {"替代方案"},
    "Evaluation": {"评估", "验证"},
    "Verification": {"验证", "购后支持"},
    "Accuracy": {"验证", "购后支持"},
    "Information": {"解决问题", "交易", "验证", "购后支持"},
}
NON_VISIBILITY_INTENTS = {"Category Awareness", "Verification", "Accuracy", "Information", "Alternatives"}
# Discovery-stage sets may also carry Information Prompts: both go into the candidate baseline.
DISCOVERY_STAGE_INTENTS = {"Discovery", "Information"}
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
REQUIRED_STAGED_FIELDS = ("journey_stage", "audience", "group_role", "attribute_ref", "evidence_refs")
# A low-condition Discovery Prompt anchors the Topic's category visibility
# (Aleyda step 6: deliberately mix unconstrained and constrained Prompts).
# Judged from constraint_type / condition_slot; exempt only via
# config.leader_default with a reason (after-sales-rules.md → When the leader
# is the default).
LOW_CONDITION_VALUES = {"无限定", "无限定条件", "低条件", "none", "unconstrained", "no_condition"}
FORMAL_LIFECYCLES = {"locked", "formal_baseline", "active"}
REVIEW_STATUSES = ("待审核", "已批准", "需修改")
REVIEW_ALIASES = {
    **{status: status for status in REVIEW_STATUSES},
    "pending": "待审核", "approved": "已批准", "needs_revision": "需修改",
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
            # A legacy five-stage label next to an eight-stage one is the old
            # export shape, not a disagreement; the eight-stage value wins.
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

    def report(message: str, rows: list[dict], hard: bool) -> None:
        if not rows:
            return
        ids = ", ".join(qid(r) for r in rows[:6]) + (" …" if len(rows) > 6 else "")
        text = f"{message} ({len(rows)} of {len(questions)}: {ids})"
        (errors if hard else warnings).append(text)

    for field in REQUIRED_STAGED_FIELDS:
        # attribute_ref may be empty on a category-baseline Prompt; it only has to be stated.
        missing = [r for r in questions if fields[id(r)][field] is None
                   or (field != "attribute_ref" and is_blank(fields[id(r)][field]))]
        report(f"missing {field} (required before lock)", missing, formal)

    old = [r for r in questions if fields[id(r)]["journey_stage"] in OLD_JOURNEY_STAGES]
    report("journey_stage still uses the old five-stage labels; re-judge into the eight stages", old, formal)
    odd = [r for r in questions if fields[id(r)]["journey_stage"]
           and fields[id(r)]["journey_stage"] not in OLD_JOURNEY_STAGES
           and fields[id(r)]["journey_stage"] not in JOURNEY_STAGES]
    report(f"journey_stage is not one of {'/'.join(JOURNEY_STAGES)}", odd, formal)
    bad_role = [r for r in questions if fields[id(r)]["group_role"] and fields[id(r)]["group_role"] not in GROUP_ROLES]
    report(f"group_role is not one of {sorted(GROUP_ROLES)}", bad_role, formal)

    bad_pair = [r for r in questions if intents.get(id(r)) in INTENT_STAGES
                and fields[id(r)]["journey_stage"] in JOURNEY_STAGES
                and fields[id(r)]["journey_stage"] not in INTENT_STAGES[intents[id(r)]]]
    report("prompt_type does not fit journey_stage (评估 asks for a judgement, 验证 for one checkable "
           "answer; see client-facing-attribute-pool.md → 旅程阶段)", bad_pair, True)
    # Alternatives stays out of this check: whether its mention rate counts toward the KPI is undecided
    # (Suda 2026-10-23), so formal_visibility_eligible may be either value until it is settled.
    leaking = [r for r in questions if intents.get(id(r)) in NON_VISIBILITY_INTENTS - {"Alternatives"}
               and r.get("formal_visibility_eligible") is True]
    report("Category Awareness, Verification, Accuracy and Information Prompts must set formal_visibility_eligible: false", leaking, True)
    # Information is an experimental-layer intent (Suda 2026-10-20): measured, but never in the formal set.
    info_layer = [r for r in questions if intents.get(id(r)) == "Information"
                  and fields[id(r)]["group_role"] and fields[id(r)]["group_role"] != "experimental"]
    report("Information Prompts belong to the experimental layer (group_role: experimental)", info_layer, True)
    # Competitor and Alternatives are named-brand research (Suda 2026-10-20/22): monitoring or experimental, never core.
    comp_layer = [r for r in questions if intents.get(id(r)) in {"Competitor", "Alternatives"}
                  and fields[id(r)]["group_role"] == "core"]
    report("Competitor and Alternatives Prompts belong to the monitoring or experimental layer, not core", comp_layer, True)

    # Balance checks only mean something on the shape they were written for.
    # A Discovery-stage set is mostly 发现 by construction, and a named-brand
    # set has no natural-visibility trend to keep stable.
    counted = [r for r in questions if fields[id(r)]["journey_stage"] in JOURNEY_STAGES]
    if stage != "discovery" and len(counted) >= 8:
        top, n = Counter(fields[id(r)]["journey_stage"] for r in counted).most_common(1)[0]
        if n / len(counted) > 0.45:
            warnings.append(f"journey stage {top} holds {n / len(counted):.0%} of Prompts; "
                            "check whether evaluation, comparison and validation decisions are covered")
    discovery = [r for r in questions if intents.get(id(r)) == "Discovery" and fields[id(r)]["group_role"]]
    if len(discovery) >= 5:
        core = sum(fields[id(r)]["group_role"] == "core" for r in discovery)
        if core / len(discovery) < 0.5:
            warnings.append(f"only {core} of {len(discovery)} Discovery Prompts are core; "
                            "keep most in core so the trend stays comparable")

    # Per-Topic low-condition anchor (SKILL step 10). Judged only when the bank
    # records constraint_type at all, so legacy banks without the field stay
    # quiet. config.leader_default (with a reason) is the explicit exemption
    # for categories where the leader is the default and bare category
    # questions were deliberately dropped (Hbrand, Suda 2026-10-19).
    leader = config.get("leader_default")
    leader_reason = str((leader or {}).get("reason", "") if isinstance(leader, dict) else leader or "").strip()
    if leader is not None and not leader_reason:
        errors.append("config.leader_default must state the reason bare category questions were dropped")
    constraint_of = lambda r: str(fields[id(r)].get("constraint_type") or "").strip().casefold()
    if not leader_reason and any(constraint_of(r) for r in questions):
        by_topic: dict[str, list[dict]] = {}
        for r in questions:
            if intents.get(id(r)) == "Discovery" and r.get("formal_visibility_eligible") is not False:
                by_topic.setdefault(str(r.get("topic_id")), []).append(r)
        missing = sorted(tid for tid, rows in by_topic.items()
                         if not any(constraint_of(r) in LOW_CONDITION_VALUES for r in rows))
        if missing:
            warnings.append(
                f"Topics whose Discovery Prompts all carry conditions ({len(missing)}): {', '.join(missing)}; "
                "keep at least one natural low-condition Prompt per Topic as the category-visibility anchor, "
                "or record the deliberate exception as config.leader_default with a reason "
                "(after-sales-rules.md → When the leader is the default)"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("monitoring_csv", type=Path, nargs="?")
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
    if len(questions) != config.get("expected_total"):
        fail("config.expected_total must equal question count", errors)

    topic_ids = {topic.get("topic_id") for topic in topics if topic.get("topic_id")}
    if len(topic_ids) != len(topics):
        fail("Topic IDs must be unique", errors)
    if any(not str(topic.get("topic") or "").strip() for topic in topics):
        fail("Topic names must be non-empty", errors)
    if legacy_full_bank and any(len(str(topic.get("topic") or "")) > 48 for topic in topics):
        fail("Topic names are too long", errors)

    # Topics are clustered from where the P1 Attributes land BEFORE Prompts are
    # written (SKILL step 5); each staged Topic records that clustering —
    # covered_attributes and planned_prompts — so "Topic first" is checkable
    # afterwards instead of the Topic shape being read back off whatever
    # Prompts happened to get written.
    if not legacy_full_bank:
        for topic in topics:
            planned = topic.get("planned_prompts") if isinstance(topic, dict) else None
            if planned is not None and (not isinstance(planned, int) or isinstance(planned, bool) or planned < 1):
                fail(f"topic {topic.get('topic_id')}: planned_prompts must be a positive integer", errors)
        undeclared = sorted(
            str(topic.get("topic_id"))
            for topic in topics
            if "covered_attributes" not in topic or "planned_prompts" not in topic
        )
        if undeclared:
            warnings.append(
                f"config.topics entries missing covered_attributes/planned_prompts ({len(undeclared)}): "
                + ", ".join(undeclared)
                + "; record the P1 clustering that opened each Topic before Prompts are written"
            )

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
        if "monitoring_prompt" not in row:
            fail(f"{question_id}: monitoring_prompt is required", errors)
        elif row.get("monitoring_prompt") != row.get("user_question"):
            fail(f"{question_id}: monitoring_prompt mismatch", errors)
        # `tags` is optional. Empty means "nothing to add beyond the other
        # fields"; a `Prompt Type:` tag restating prompt_type is neither required
        # nor rejected, so inherited presales v8 rows still normalise through
        # `normalized_intent`.
        query_key = " ".join(user_question.casefold().split())
        if query_key in normalized_queries:
            fail(f"{row.get('question_id')}: duplicate query", errors)
        normalized_queries.add(query_key)

    if stage == "discovery" and any(
        intent not in DISCOVERY_STAGE_INTENTS for intent in role_counts if intent
    ):
        fail("discovery stage must contain Discovery or Information Prompts only", errors)

    # Gate 40 (Suda 2026-10-23): Discovery is at least half of the set. It is
    # the only type that feeds the mention-rate KPI most clients buy. Warning
    # only: the share is a coverage target, never a reason to pad Discovery —
    # a leader-default category (Hbrand) is legitimately below it.
    if stage is not None and questions:
        share = role_counts.get("Discovery", 0) / len(questions)
        if share < 0.5:
            warnings.append(f"Discovery is {role_counts.get('Discovery', 0)} of {len(questions)} Prompts ({share:.0%}); "
                            "target is at least 50% — add evidence-backed Discovery Prompts or record why this "
                            "set sits below (never pad to reach it)")

    wording_checks(config, questions, row_intents, errors, warnings)
    field_contract_checks(config, questions, row_intents, stage, errors, warnings)
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
    review_active = any("review_status" in row for row in questions)
    review_counts: Counter[str] = Counter()
    approved_rows = questions
    if review_active:
        unstated: list[str] = []
        approved_rows = []
        for row in questions:
            raw = row.get("review_status")
            if is_blank(raw):
                unstated.append(str(row.get("question_id")))
                status = "待审核"
            else:
                status = REVIEW_ALIASES.get(str(raw).strip().casefold(), "")
                if not status:
                    fail(f"{row.get('question_id')}: review_status must be one of "
                         f"{'/'.join(REVIEW_STATUSES)}, got {raw!r}", errors)
                    status = "待审核"
            review_counts[status] += 1
            if status == "已批准":
                approved_rows.append(row)
        if unstated:
            warnings.append(f"review_status missing on {len(unstated)} Prompts, counted as 待审核 "
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
            (errors if review_done else warnings).append(message)

    # Topic ← P1 clustering consistency. covered_attributes must name real plan
    # rows, and every P1 must be homed in some Topic or state why it is not —
    # a Topic that no P1 opened, or a P1 that no Topic measures, is the
    # clustering drifting after the fact.
    declared_topics = [t for t in topics if isinstance(t, dict) and t.get("covered_attributes")]
    if plan and declared_topics:
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
                    f"evidence spans only {len(families)} source families ({found}); "
                    "the signal pass covers search data, sales records, reviews and "
                    "community — check whether the missing families were collected"
                )

    # Unused buyer-language inputs (warning only). When the bank carries the
    # collected 买家原话 index, every input should either back a Prompt or have
    # been consciously set aside; silently unused inputs are the cheapest
    # evidence for the next expansion round.
    audience_inputs = config.get("audience_inputs") or []
    if audience_inputs and isinstance(audience_inputs, list):
        all_refs = " ".join(
            str(ref) for row in questions for ref in (row.get("evidence_refs") or [])
        )
        unused: list[str] = []
        for entry in audience_inputs:
            input_id = str(entry.get("input_id") if isinstance(entry, dict) else entry or "").strip()
            if input_id and input_id not in all_refs:
                unused.append(input_id)
        if unused:
            warnings.append(
                f"audience inputs referenced by no Prompt ({len(unused)}): "
                + ", ".join(unused[:8]) + (" …" if len(unused) > 8 else "")
                + "; record a decision for each (draft candidate / set aside / not applicable) in the internal diff"
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
        short_topics = {
            topic_id: count
            for topic_id, count in topic_counts.items()
            if count < 5
        }
        missing_topics = topic_ids - topic_counts.keys()
        if missing_topics:
            short_topics.update({topic_id: 0 for topic_id in missing_topics})
        if short_topics:
            fail(
                "formal staged set requires at least 5 Prompts per Topic; "
                f"short Topics need merge, Tag treatment, or evidence-gap report: {short_topics}",
                errors,
            )
        # 交付范围：正式题每个采购主题最多 10 条；候选阶段（customer_confirmed）不设上限。
        if lifecycle in {"locked", "formal_baseline", "active"}:
            long_topics = {topic_id: count for topic_id, count in topic_counts.items() if count > 10}
            if long_topics:
                fail(
                    "formal set allows at most 10 Prompts per purchased Topic; "
                    f"move the rest out of the deliverable set: {long_topics}",
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
        # trial = 候选题质量试跑：ChatGPT 每题 3 次（异常补到 5 次封顶）。候选基线已于 2026-10-23 取消，不再多平台 × 5 次。
        # 旧题库写的 5 仍接受，不迁移。
        planned = trial.get("planned_runs")
        if isinstance(planned, bool) or not isinstance(planned, int) or planned not in {3, 5}:
            fail("trial.planned_runs must be 3 (ChatGPT quality trial; legacy 5 still accepted)", errors)
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

    if args.monitoring_csv:
        with args.monitoring_csv.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        required = {"query", "question_zh", "topic", "region", "prompt_type"}
        allowed = required | {"tags", "cadence"}
        actual = set(rows[0]) if rows else set()
        missing = required - actual
        unknown = actual - allowed
        if missing:
            fail(f"monitoring CSV is missing required columns {sorted(missing)}", errors)
        if unknown:
            fail(f"monitoring CSV has unsupported columns {sorted(unknown)}", errors)
        if len(rows) != len(questions):
            fail("monitoring CSV row count must equal JSON question count", errors)
        if any(len(str(row.get("tags") or "")) >= 200 for row in rows):
            fail("monitoring CSV tags must be shorter than 200 characters", errors)

    # Warnings never change the exit code: each one needs a human decision, and
    # rewording a Prompt only to silence a heuristic is not a fix.
    plural = lambda n, word: f"{n} {word}{'s' if n != 1 else ''}"
    if errors:
        readiness = f"Not ready: {plural(len(errors), 'error')} to fix"
    elif warnings:
        readiness = f"Usable: {plural(len(warnings), 'warning')} to review"
    else:
        readiness = "Ready for the next lifecycle stage"

    for warning in warnings:
        print(f"WARNING: {warning}")
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
                "readiness": readiness,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
