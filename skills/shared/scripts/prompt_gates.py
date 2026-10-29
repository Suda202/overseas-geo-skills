"""Prompt writing gates shared by geo-prompt-selection-builder and geo-presales-prompt-builder.

One implementation so the two validators can never judge the same Prompt differently.
English only; non-Latin locales keep their registry-based checks in each validator.
"""

from __future__ import annotations

import re

_CANDIDATE_NOUNS = (
    r"brands?|companies|company|manufacturers?|providers?|products?|solutions?|suppliers?|"
    r"tools?|vendors?|options?|platforms?|models?|agenc(?:y|ies)|services?|apps?|software"
)
_CANDIDATE_NOUN = re.compile(rf"\b(?:{_CANDIDATE_NOUNS})\b")
# Asking for criteria or features returns a checklist, not a brand list.
_ABSTRACT_NOUN = re.compile(
    r"\b(?:factors?|criteria|features?|capabilities|attributes|requirements?|"
    r"considerations?|benefits?|risks?|differences?|tradeoffs?|look for)\b"
)
_METHOD_SUPERLATIVE = re.compile(
    r"\b(?:best|top)\s+(?:ways?|practices?|times?|tips?|steps?|methods?|strategies|"
    r"approach(?:es)?|settings?|temperatures?)\b"
)
# "Best dash cams for rideshare drivers", "What is the best dash cam for night
# driving?": a superlative before a product noun, singular or plural. Method nouns
# are rejected by _METHOD_SUPERLATIVE first; "best dash cam features" by _ABSTRACT_NOUN.
_SUPERLATIVE_PRODUCT = re.compile(
    r"^(?:what\s+(?:are|is)\s+the\s+)?(?:best|top)(?:[\s-]+rated)?\s+(?=[\w$-])"
)


def _superlative_product(lowered: str) -> bool:
    opener = _SUPERLATIVE_PRODUCT.match(lowered)
    if not opener:
        return False
    rest = lowered[opener.end():]
    # "Best for a finished kitchen", "Best if you want RO", "Best price": no product named.
    if re.match(r"^(?:for|if|in|to|with|of|when|at|overall|price)\b", rest):
        return False
    return not re.match(rf"^(?:[\w-]+\s+){{0,2}}?(?:{_ABSTRACT_NOUN.pattern})", rest)
# "What are the alternatives to managing X manually": AI answers with approaches,
# not providers (2026-10-22 test). The provider form "Which X providers can ...
# instead of ..." passes through the candidate-noun rule instead.
# "Can you recommend a dash cam for rideshare drivers?": recommend / suggest followed
# by an article asks for a product even when no generic noun ("brands", "tools")
# follows (Suda 2026-10-29: any natural opening works). A method or criteria ask
# ("recommend some ways to ...", "suggest a good setting") still returns advice.
_RECOMMEND_ASK = re.compile(
    r"\b(?:recommend|suggest)\s+(?:me\s+|us\s+)?(?:a|an|some|any|good|the\s+best)\s+"
)
_NOT_A_PRODUCT = re.compile(
    rf"^(?:[\w-]+\s+){{0,2}}?(?:{_ABSTRACT_NOUN.pattern}|ways?|tips?|steps?|methods?|"
    r"strateg(?:y|ies)|approach(?:es)?|settings?|temperatures?|practices?)"
)
_STATUS_QUO_APPROACH = re.compile(
    r"^what\s+(?:are|is)\s+(?:the\s+)?(?:alternatives?|options?)\s+(?:to|besides|other than)\s+"
    r"(?:\w+ing)\b"
)


def requests_candidates(text: str) -> bool:
    """True when an English Discovery Prompt asks AI for named candidates.

    Buyers often set the scene first ("I need a furnished place for three months.
    What are my options ..."), so every sentence and ", and ..." clause is checked.
    """
    lowered = " ".join(str(text).strip().casefold().split())
    clauses = [c.strip() for c in re.split(r"[.?!;]\s+|,\s+and\s+", lowered) if c.strip()]
    return any(_clause_requests_candidates(c) for c in clauses or [lowered])


def _clause_requests_candidates(lowered: str) -> bool:
    if not lowered:
        return False
    if re.match(r"^(?:how|why|when)\b", lowered):
        return False
    if re.match(r"^what\s+(?:is|does)\b", lowered) and not _superlative_product(lowered):
        return False
    if _STATUS_QUO_APPROACH.match(lowered):
        return False
    if _METHOD_SUPERLATIVE.search(lowered):
        return False
    if re.match(r"^what\s+should\s+(?:i|we|you)\s+look\s+for\b", lowered):
        return False
    if _superlative_product(lowered):
        return True
    if re.match(r"^who\b", lowered):
        return True
    if re.search(r"\bwhere\b.*\b(?:buy|source|order|get)\b", lowered):
        return True
    # "Which earbuds ...", "My counter is crowded — which ... brands ...": a Which
    # question anywhere in the Prompt asks AI to name products. Only a question for
    # criteria or features ("which factors ...") gets a checklist instead.
    which = re.search(r"(?:^|[\s,—–-])which\s+", lowered)
    if which:
        rest = lowered[which.end():]
        if re.match(rf"^(?:[\w-]+\s+){{0,3}}?(?:{_ABSTRACT_NOUN.pattern})", rest):
            return False
        return True
    opener = re.match(r"^what\s+", lowered)
    if opener:
        noun = _CANDIDATE_NOUN.search(lowered, opener.end())
        if not noun:
            return False
        prefix = lowered[opener.end():noun.start()]
        if _ABSTRACT_NOUN.search(prefix) or re.match(
            rf"^\s*(?:['’]s?)?\s*{_ABSTRACT_NOUN.pattern}", lowered[noun.end():]
        ):
            return False
        return len(prefix) <= 100
    recommend = _RECOMMEND_ASK.search(lowered)
    if recommend and not _NOT_A_PRODUCT.match(lowered[recommend.end():]):
        return True
    # A bare search keyword ("business travel provider", "dash cam brands") with no
    # verb or question returns a provider list on AI Overviews and AI Mode.
    if len(lowered.split()) <= 6 and not re.search(r"[?]|\b(?:how|why|is|are|do|does|can|should)\b", lowered) \
            and _CANDIDATE_NOUN.search(lowered):
        return True
    return bool(re.search(
        rf"\b(?:best|top|leading|recommend(?:ed)?|suggest|shortlist|list|name|find|compare)\b"
        rf".{{0,100}}\b(?:{_CANDIDATE_NOUNS})\b",
        lowered,
    ))


# Agreed judgements; both validators' tests assert against this table.
REGRESSION_CASES = (
    ("Which dash cam brands should rideshare drivers consider?", True),
    ("Best dash cams for rideshare drivers", True),
    ("Best dash cam for night driving", True),
    ("What is the best dash cam for night driving?", True),
    ("best robot vacuum for pet hair", True),
    ("Best time to buy a dash cam", False),
    ("What is the best temperature to store probiotics?", False),
    ("Best dash cam features for night driving", False),
    ("Best price for a portable oxygen concentrator", False),
    ("What are the best automatic litter boxes for multi-cat homes?", True),
    ("Which models of litter box handle multiple cats?", True),
    ("Where can I buy a portable oxygen concentrator in Singapore?", True),
    ("Recommend a corporate travel platform for a 50-person company", True),
    ("Which is better for a small team, a travel agency or a booking tool?", True),
    ("Top corporate travel management providers for mid-sized companies", True),
    ("Which corporate travel management providers can a company use instead of booking business travel in-house?", True),
    ("Which family nutrition supplement brands should a household shortlist?", True),
    ("What are the alternatives to managing expense reports manually?", False),
    ("What are the options besides handling corporate travel booking in-house?", False),
    ("What should I look for in a dash cam?", False),
    ("How do I reduce litter box smell?", False),
    ("Best ways to reduce litter box smell", False),
    ("What are the best practices for corporate travel policy?", False),
    ("What is the best way to store probiotics?", False),
    ("What factors matter when choosing brands?", False),
    ("Which factors matter most when choosing a dash cam?", False),
    ("Which features should a corporate travel platform have?", False),
    ("Which earbuds last the longest with the charging case included?", True),
    ("My kitchen counter is already crowded — which countertop water dispenser brands still fit?", True),
    ("I wear earbuds for eight hours a day at work, which ones stay comfortable?", True),
    ("I need a furnished place in Singapore for three months. What are my options for short-term rentals?", True),
    ("How can I avoid fake rental listings in Singapore, and which places are safest to find a room or flat?", True),
    ("business travel provider", True),
    ("how to choose a business travel provider", False),
    ("Can you recommend a dash cam for rideshare drivers?", True),
    ("Could you suggest a good robot vacuum for pet hair?", True),
    ("Can you recommend some ways to reduce litter box smell?", False),
    ("Can you suggest a good setting for night recording?", False),
    ("Can you recommend some features to look for in a dash cam?", False),
)
