"""Evidence-scope and repeated-decision gates for Prompt sets.

Found missing by the 2026-10-22 harness A/B: six Discovery sets that the
validator passed with 0 warnings had about half their Prompts failed by a
blind review, on two counts the validator never checked.

1. **A condition outside the evidence.** The Prompt adds a buyer condition —
   budget, car type, parking place, weather, an event such as a hit-and-run —
   that none of its cited buyer quotes carries. The evidence is the quote's
   约束 column, not the quote text (Suda 2026-10-22): research records there
   conditions such as 「200 美元以内」 that a post states in its title or
   thread rather than in the quoted line. Numbers in the quote itself also
   count, so "4 channel dash cam with parking mode" licenses a 4-channel
   Prompt.

2. **One purchase decision asked twice.** Two Prompts in one Topic test the
   same attribute under the same evidence-backed conditions and differ only in
   scenery or wording. Word overlap misses these ("keep recording while
   parked" vs "catch a hit-and-run in a parking lot"), so the decision is
   keyed on (Topic, prompt type, attribute or slice, evidence-backed
   constraints). A condition without evidence does not make a new decision.

Both read the per-Prompt `constraints` list — the buyer conditions the Prompt
carries beyond its attribute, written as 约束-column keywords — and the
bank's buyer-quote table `config.buyer_quotes` (输入编号 / 原话 / 约束, the
client Base 需求信号 columns). `config.base_conditions` lists the category's
base audience or use (「私家车」「日常驾驶」), which is the category itself
and never a condition.

Replay on the six A/B sets (80-代码/选词工具-harness-AB/runs/gates/replay.py):
the two gates together flag 85% of the Prompts the blind review failed.

Since 2026-10-30 (Suda) a condition no quote backs is a warning, not an error:
buyer-quote research is never complete, so a condition may also rest on search
data, the research pre-run, a competitor's filters or plain buyer common sense.
Such a basis is written per Prompt in `condition_basis` ({condition: basis}, or
a list of {"condition", "basis"}); a condition with a written basis is not
reported and counts as decision-changing in gate 2.

The column is called 约束条件 everywhere — the client Base 需求信号 sheet
(client-facing-base.md), the collectors' signals.csv and the bank. Older banks
written before 2.65.0 used the short key 约束 and are still read. When no quote
in the bank carries a 约束条件 cell, gate 1 checks that every declared condition
rests on at least one cited quote or a written `condition_basis`, and that every
number in the query appears in a cited quote or a basis; whether the quote
really says it is read by the reviewer, who sees the quote linked on the
Prompt. Banks whose quotes do carry 约束条件 keep the keyword check above.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

CJK_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}

# Digits that name a model, belong to the attribute itself, or date the
# question are not buyer conditions: 24/7 and 24 hours are what parking
# monitoring means, STARVIS 2 is a sensor, a four-digit year is a freshness
# marker.
_NOT_A_CONDITION = re.compile(
    r"24\s*/\s*7|24\s*-?\s*hours?|starvis\s*\d|\b(?:19|20)\d\d\b|\bv\d+\b|\bgen\s*\d\b",
    re.I,
)
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\$?\d+(?:[.,]\d+)?\s*(?:k|gb|tb|mp|p|%|°)?", re.I)
_SPLIT = re.compile(r"[、，,;；/|]")


# A bare CJK digit only states a quantity when a measure word follows it.
# 一般 / 一直 / 一起 / 一定有 / 一直留在自己錢包裡 are adverbs, not the number 1;
# without this list gate 36 reported 「数字 1」 against ordinary Taiwanese and
# Korean wording (Nbrand 2026-10-23: 4 false errors on 一般, 一直, 一有).
_UNITS = set("路个個支台款次倍年月天秒时時分条條张張部種种颗顆片件套档檔层層期轮輪人只手隻美元块塊米克斤升度折成笔筆家间間座门門")



def _cjk_numbers(text: str) -> str:
    """四路 -> 4路, 两百 -> 200, 二十四 -> 24; enough for short 约束 keywords."""
    def repl(m: re.Match) -> str:
        s = m.group(0)
        if not s:
            return ""
        if s == "十":
            return "10"
        if "百" in s:
            head, _, tail = s.partition("百")
            return str(CJK_DIGITS.get(head, 1) * 100 + (CJK_DIGITS.get(tail, 0) * 10 if tail else 0))
        if "十" in s:
            head, _, tail = s.partition("十")
            return str((CJK_DIGITS.get(head, 1) if head else 1) * 10 + (CJK_DIGITS.get(tail, 0) if tail else 0))
        # Bare digit: needs a following measure word, otherwise it is an adverb
        # or part of a word (一般, 一直, 一起), not a buyer condition.
        nxt = text[m.end():m.end() + 1]
        if s in CJK_DIGITS and nxt not in _UNITS:
            return s
        # A bare 「一」 is the indefinite article or an adverb (一般, 一直,
        # 一起, 一次找出, 一個工具), not a count; only 十/百 compounds and
        # 兩 / 三 / 四… still convert. A real "one X" condition is written 1 個
        # or 單一, and a miss only leaves a gate ungated while a false error
        # blocks delivery (Nbrand 2026-10-23: 6 false 「数字 1」 errors).
        if s == "一":
            return s
        return str(CJK_DIGITS.get(s, s))
    return re.sub(r"[零一二两兩三四五六七八九]?[百十]?[零一二两兩三四五六七八九]?", repl, text)


def _fold(text: object) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[\s、，,;；/|()（）\-–—·:：\"'“”]+", "", text)


def numbers_in(text: object) -> set[str]:
    """Integer values a text states, after dropping model names, 24/7 and years."""
    cleaned = _NOT_A_CONDITION.sub(" ", _cjk_numbers(unicodedata.normalize("NFKC", str(text or ""))))
    values: set[str] = set()
    for m in _NUMBER.finditer(cleaned):
        digits = re.sub(r"[^\d.,]", "", m.group(0)).replace(",", "").rstrip(".")
        if not digits:
            continue
        try:
            value = float(digits)
        except ValueError:
            continue
        if "$" in m.group(0) and re.search(r"k\b", m.group(0), re.I):
            value *= 1000
        values.add(str(int(value)) if value == int(value) else str(value))
    return values


def constraint_keywords(value: object) -> list[str]:
    """A 约束 cell or a declared list -> folded keywords (「四路、停车模式」 -> ['4路', '停车模式'])."""
    items = value if isinstance(value, list) else _SPLIT.split(str(value or ""))
    return [k for k in (_fold(_cjk_numbers(unicodedata.normalize("NFKC", str(i)))) for i in items) if k]


def keyword_supported(keyword: str, evidence: list[str]) -> bool:
    """A declared keyword is backed when it matches an evidence keyword, either containing the other."""
    return any(keyword == e or (len(keyword) >= 2 and keyword in e) or (len(e) >= 2 and e in keyword)
               for e in evidence)


def quote_index(config: dict) -> tuple[dict[str, str], dict[str, str]]:
    """config.buyer_quotes -> ({输入编号: 约束条件}, {输入编号: 原话}). Accepts Chinese or English keys.

    The column is 约束条件 everywhere — the client Base 需求信号 sheet, the
    collectors' signals.csv and the bank. `constraint` is the English alias;
    the old short key `约束` is still read for banks written before 2.65.0.
    """
    constraints: dict[str, str] = {}
    texts: dict[str, str] = {}
    for entry in config.get("buyer_quotes") or []:
        if not isinstance(entry, dict):
            continue
        qid = str(entry.get("输入编号") or entry.get("input_id") or "").strip()
        if not qid:
            continue
        constraints[qid] = str(entry.get("约束条件") or entry.get("constraint")
                                or entry.get("约束") or "")
        texts[qid] = str(entry.get("原话") or entry.get("quote") or "")
    return constraints, texts


def _resolve(ref: str, index: dict[str, str]) -> str | None:
    """evidence_refs may carry a note after the id (「KE-R019（社区）」); match on the id."""
    if ref in index:
        return ref
    head = re.split(r"[\s（(]", ref, maxsplit=1)[0]
    return head if head in index else None


def _cited(row: dict, index: dict[str, str]) -> tuple[list[str], list[str]]:
    refs = [str(r).strip() for r in (row.get("evidence_refs") or []) if str(r).strip()]
    hits = [_resolve(r, index) for r in refs]
    return [h for h in hits if h], [r for r, h in zip(refs, hits) if h is None]


def condition_basis(row: dict) -> dict[str, str]:
    """`condition_basis` -> {folded condition keyword: basis text}; empty bases are ignored."""
    raw = row.get("condition_basis") or {}
    pairs = raw.items() if isinstance(raw, dict) else (
        (e.get("condition"), e.get("basis")) for e in raw if isinstance(e, dict))
    out: dict[str, str] = {}
    for cond, basis in pairs:
        if str(basis or "").strip():
            for k in constraint_keywords(cond):
                out[k] = str(basis).strip()
    return out


def unsupported_conditions(row: dict, quote_constraints: dict[str, str],
                           quote_texts: dict[str, str] | None = None,
                           base_conditions: list[str] | None = None) -> dict:
    """Gate 1 for one Prompt.

    Returns {"unknown_refs", "keywords", "numbers"}: cited ids missing from the
    quote table, declared constraints that no cited 约束 cell backs, and numbers
    in the market-language query that neither the cited 约束 cells nor the
    cited quotes state. A condition (or a number inside one) with a written
    `condition_basis` is not reported. The Chinese gloss is not read for
    numbers — it renders "both sides" or "overnight" as 两侧 / 一整夜.
    """
    cited, unknown = _cited(row, quote_constraints)
    if not _has_cells(quote_constraints):
        texts = [(quote_texts or {}).get(h, "") for h in cited]
        base = set(constraint_keywords(base_conditions or []))
        declared = [k for k in constraint_keywords(row.get("constraints")) if k not in base]
        based = list(condition_basis(row))
        based_numbers = set().union(set(), *(numbers_in(k) for k in based))
        return {
            "unknown_refs": unknown,
            "keywords": [] if cited else [k for k in declared if not keyword_supported(k, based)],
            "numbers": sorted(numbers_in(row.get("user_question")) - set().union(set(), *(numbers_in(t) for t in texts))
                              - based_numbers),
        }
    cells = [quote_constraints[h] for h in cited]
    evidence_kw = [k for cell in cells for k in constraint_keywords(cell)]
    texts = [(quote_texts or {}).get(h, "") for h in cited]
    evidence_numbers: set[str] = set().union(set(), *(numbers_in(t) for t in cells + texts))
    base = set(constraint_keywords(base_conditions or []))
    declared = [k for k in constraint_keywords(row.get("constraints")) if k not in base]
    based = list(condition_basis(row))
    based_numbers: set[str] = set().union(set(), *(numbers_in(k) for k in based))
    return {
        "unknown_refs": unknown,
        "keywords": [k for k in declared
                     if not keyword_supported(k, evidence_kw) and not keyword_supported(k, based)],
        "numbers": sorted(numbers_in(row.get("user_question")) - evidence_numbers - based_numbers),
    }


def _has_cells(quote_constraints: dict[str, str]) -> bool:
    """Does any quote still carry a 约束 cell (banks before 2026-11-04)?"""
    return any(str(v or "").strip() for v in quote_constraints.values())


def supported_keywords(row: dict, quote_constraints: dict[str, str]) -> list[str]:
    """The declared constraints that a cited quote's 约束 column or a written `condition_basis` backs.
    Without 约束 cells (2026-11-04 on), a Prompt that cites a quote counts all its declared constraints as backed."""
    cited, _ = _cited(row, quote_constraints)
    if not _has_cells(quote_constraints):
        declared = constraint_keywords(row.get("constraints"))
        return declared if cited else [k for k in declared if keyword_supported(k, list(condition_basis(row)))]
    evidence_kw = [k for h in cited for k in constraint_keywords(quote_constraints[h])] + list(condition_basis(row))
    return [k for k in constraint_keywords(row.get("constraints")) if keyword_supported(k, evidence_kw)]


def decision_key(row: dict, quote_constraints: dict[str, str]) -> tuple:
    """Gate 2 key: Topic, prompt type, attribute (or client-Base slice) and the
    evidence-backed constraints. Category-baseline Prompts (no attribute) are
    keyed the same way, so two unconditioned baselines in one Topic collide."""
    topic = str(row.get("topic_id") or "")
    intent = str(row.get("prompt_type") or row.get("intent") or "")
    slice_ref = str(row.get("slice_ref") or "").strip()
    base = ("slice", slice_ref) if slice_ref else ("attr", _fold(row.get("attribute_ref") or row.get("attribute") or ""))
    return (topic, intent, *base, tuple(sorted(set(supported_keywords(row, quote_constraints)))))


def repeated_decisions(questions: list[dict], quote_constraints: dict[str, str]) -> list[list[str]]:
    """Groups (bank order) of question_ids sharing one decision key; each group has 2+ Prompts."""
    groups: dict[tuple, list[str]] = defaultdict(list)
    for row in questions:
        groups[decision_key(row, quote_constraints)].append(str(row.get("question_id")))
    return [ids for ids in groups.values() if len(ids) > 1]
