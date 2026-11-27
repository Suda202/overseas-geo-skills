#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mine an open-brand candidate table from Scrapeless GEO answer JSON.

Why this exists
---------------
The presales report computes share-of-voice with a denominator of *every brand
named in an AI answer*, not just the three pre-configured competitors. That is
only possible if brand names can be recovered from free-form English prose and
separated from the technical abbreviations, media names, place names and
product-model fragments that share the same capitalisation.

This script does the mechanical half of that job:

  1. Walk a collection directory laid out as
     ``<collect_dir>/scraper.<platform>/<REGION>/<NNNN>.json``.
  2. Pull the answer body (``task_result.content`` for ``overview``,
     ``task_result.result_text`` for the other platforms).
  3. Clean the body (see CLEANING below).
  4. Extract capitalised candidates: single tokens and 1-2 word runs.
  5. Classify each candidate against a brand lexicon and emit the rest as
     ``unknown`` so a human can rule on them.

It is re-runnable: point ``--collect-dir`` at a fresh collection and rerun to
re-mine, or pass ``--lexicon`` to check a curation against new data.

不漏开放竞品（2026-11-20）
--------------------------
只按出现次数排序时，出现两三次的长尾厂商会被几百个大写普通词压在后面，人只看前 40 个就漏了
（路拓 7 次 231 条回答漏了 MotoOptix、Podofo 等 12 家同类厂商，平均每答品牌数 2.81→3.03）。
现在每个候选另外记三类「像品牌」的结构证据，出现一次就够：

  * ``list_docs``：在答案的推荐位上当名字出现——加粗列表项开头（``**3. Podofo**``）、
    标题开头（``### Podofo``）、表格第一列（``| Podofo |``）。只取开头的名字，型号和后面的常用词截掉。
  * ``card_docs``：商品卡（``geo_presales_core.shopping.extract_product_cards``）的平台品牌字段，
    或卡标题开头的名字。商品卡不算正文提及，但卡里的品牌一样要进词表。
  * ``domain``：答案引用或链接里有同名域名（Podofo ↔ podofo.com）。

``tier``：词表没收、有任一结构证据、且不是单个英文常用词（常用词要有商品卡或域名证据）的记 A，
必须逐个过；其余没收的大写词记 B（按次数排，抽看即可）；单个常用词且无结构证据记 C。
型号样的（C3、AIO-5、R1250GS；Bike2Play 这种不算）、4 个字母以内全大写的缩写（GPS、TPMS；要有商品卡或域名证据才进 A）、只有域名证据的
（多是媒体和零售站）不进 A；域名一列只作人工判断参考。普通词包括英文常用词表里的词（含简单屈折变化）、修饰性复合词（Built-in、BMW-specific）、
这批答案里小写写法达到大写写法一半的词；普通词只有平台品牌字段（AI 模式、Gemini 商品卡的 brand）能把它拉进 A。
A 档不受 ``--min-count`` 限制。人工过 A 档时：同类厂商收进 ``brands``（写 ``same_category``），
别的品类品牌也收（写 ``same_category: false``），不是品牌的写进 ``stopwords``，下次不再出现。
``--check`` 时还有出现在 ≥ ``--check-min-docs`` 条回答里的 A 档候选，或词表里有疑似同一品牌拆成两条的
条目（规则在 ``audit_lexicon_domains.split_suspects``：别名重复、别名整词包含、中文别名互相包含、官网域名
主标签相同；确是两家写进词表顶层 ``distinct_brands``），退出码为 1。
中文（含繁体）品牌名另走一条（2026-11-20，老虎香港繁中回答漏了耀才、華盛、華泰）：推荐位或加粗片段开头的
中文名，以机构后缀结尾（證券、銀行、金融、集團、國際、資本、財富、理財、控股）、去掉后缀剩 2–4 个字的，
同样按推荐位证据进 A 档；「傳統銀行」「哪間香港銀行」这类泛称按前缀表和虚词表排除。繁简写法不同算没收
（词表有「恒生银行」、答案写「恆生銀行」认不出），所以照样列出，补上答案里的写法。泰文、日文、
韩文等其他无大小写文字的品牌这里仍挖不出来，要另外人工看。

CLEANING
--------
Markdown/Scrapeless artefacts are removed *without* discarding brand evidence:

  * ``<EntityCard ... title="X"/>`` -> the ``title`` text is kept, the tag goes.
  * markdown link targets ``[text](url)`` -> ``text`` is kept.
  * reference definition lines ``[N]: url "title"`` -> dropped entirely.
  * bare URLs / ``www.`` hosts -> dropped.
  * the Scrapeless anchor artefact ``Go to product viewer dialog for this
    item.`` -> dropped (it is glued onto product names and would otherwise
    create junk tokens such as ``DispenserGo``).

Usage
-----
    python3 mine_brand_lexicon.py                       # mine with defaults
    python3 mine_brand_lexicon.py --min-count 2 --top 300
    python3 mine_brand_lexicon.py --collect-dir /path/to/collect --out /tmp/x.csv
    python3 mine_brand_lexicon.py --lexicon assets/brand_lexicon.water-purifier-sea.json
    python3 mine_brand_lexicon.py --collect-dir run-1 run-2 run-3 --lexicon <词表> --bank <bank.json> --check
    （本品和配置竞品不在开放品牌词表里时，用 --case 或 --bank 带上，免得被列成没收）
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import html
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# Defaults (override on the command line)
# --------------------------------------------------------------------------

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "build", "brand_candidates.csv")

# 平台清单取 geo-metrics 平台登记表（下方 import 后赋值）
PLATFORMS: list[str] = []


def discover_regions(collect_dir: str) -> list[str]:
    """从采集目录发现市场代码，按首次出现顺序；不写死市场。

    与 build_report_data.discover_regions、collect_domain_candidates 保持一致：
    市场由 scraper.<platform>/<REGION>/ 目录结构推断，否则非 MY/SG 的采集
    （如泰国 TH）会一条文件都读不到。
    """
    regions: list[str] = []
    for platform in PLATFORMS:
        platform_dir = os.path.join(collect_dir, f"scraper.{platform}")
        if not os.path.isdir(platform_dir):
            continue
        for child in sorted(os.listdir(platform_dir)):
            if os.path.isdir(os.path.join(platform_dir, child)) and child not in regions:
                regions.append(child)
    return regions


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

# 与报告渲染共用同一定义（同目录 de_cite_crawl），避免两处漂移。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 不加脚本目录
from de_cite_crawl import PRODUCT_VIEWER_NOISE  # noqa: E402
from geo_presales_core.crawler import answer_body  # noqa: E402
from geo_presales_core.platforms import ALL_PLATFORM_DIRS  # noqa: E402
PLATFORMS[:] = ALL_PLATFORM_DIRS
from geo_presales_core.lexicon import load_lexicon as core_load_lexicon  # noqa: E402
from geo_presales_core.shopping import extract_product_cards  # noqa: E402
from geo_presales_core.util import extract_urls, is_common_word, normalize_host, registrable_domain  # noqa: E402


def clean_text(raw: str) -> str:
    """Strip Scrapeless/markdown wrapping while preserving brand-bearing text."""
    if not raw:
        return ""
    t = html.unescape(raw)

    # Keep the EntityCard title, discard the tag.
    t = re.sub(r'<EntityCard\b[^>]*?\btitle="([^"]*)"[^>]*?/>', r" \1 ", t)
    t = re.sub(r"<EntityCard\b[^>]*?/>", " ", t)
    t = re.sub(r"<EntityCard\b[^>]*?>", " ", t)
    # Any other HTML/XML-ish tag (img, br, span, ...).
    t = re.sub(r"<[^>]{0,400}>", " ", t)

    # Scrapeless anchor artefact glued onto product names.
    t = t.replace(PRODUCT_VIEWER_NOISE, " ")

    # Reference definition lines: [1]: https://... "Title"  (whole line goes).
    t = re.sub(r'^[ \t]*\[\d+\]:[ \t]*\S+.*$', "", t, flags=re.M)
    t = re.sub(r'^[ \t]*\[\d+\]:[ \t]*$', "", t, flags=re.M)

    # Markdown links -> keep the visible text. Handles nested brackets too.
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\[([^\[\]]*)\]\((?:[^()]*)\)", r"\1", t)
        t = re.sub(r"\[([^\[\]]*)\]\[[^\[\]]*\]", r"\1", t)

    # Bare URLs and www hosts.
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\bwww\.\S+", " ", t)

    # Collapse whitespace.
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


# --------------------------------------------------------------------------
# Candidate extraction
# --------------------------------------------------------------------------

# A capitalised word: leading capital, then letters/digits; allows the usual
# brand-joiners found in this corpus ( - & . ' + ).
WORD = r"[A-Z][A-Za-z0-9]*(?:[&.'+\-][A-Za-z0-9]+)*"
TOKEN_RE = re.compile(r"\b" + WORD + r"\b")
# 2- and 3-word runs of capitalised words (e.g. "Coway Malaysia",
# "Water Filter Guru", "British Berkefeld").
NGRAM_RE = re.compile(r"\b" + WORD + r"(?:\s+" + WORD + r"){1,2}\b")


def usable(cand: str) -> bool:
    """Drop single stray capitals ('A', 'I') that are never brand evidence.

    All-caps tokens (RO, TDS, LG, PUR) are kept on purpose: they are exactly
    what the stopword layer exists to absorb, and keeping them in the table
    lets a reviewer see that they were classified rather than silently lost.
    """
    return len(cand) >= 2


def iter_docs(collect_dir: str):
    """Yield (platform, region, path, body_text, raw_body, task) for every collected answer."""
    for platform in PLATFORMS:
        for region in discover_regions(collect_dir):
            pattern = os.path.join(collect_dir, f"scraper.{platform}",
                                   region, "*.json")
            for path in sorted(glob.glob(pattern)):
                try:
                    with open(path, encoding="utf-8") as fh:
                        payload = json.load(fh)
                except (OSError, ValueError):
                    continue
                task = payload.get("task_result") or {}
                body = answer_body(task, platform)
                yield platform, region, path, clean_text(body), body or "", task


# 推荐位：加粗列表项、编号列表项、标题、表格第一列的开头。
_LIST_HEAD_RES = [
    re.compile(r"^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?(?:\*\*|__)[ \t]*(?:\d+[.)][ \t]*)?(?P<rest>.+)$", re.M),
    re.compile(r"^[ \t]*\d+[.)][ \t]+(?P<rest>.+)$", re.M),
    re.compile(r"^[ \t]*#{1,6}[ \t]*(?:\d+[.)][ \t]*)?(?:\*\*)?[ \t]*(?P<rest>.+)$", re.M),
    re.compile(r"^[ \t]*\|[ \t]*(?:\*\*)?(?P<rest>[^|\n]+)\|", re.M),
]
_LEAD_WORDS = re.compile(r"^\s*(" + WORD + r"(?:[ \t]+" + WORD + r")*)")
_TABLE_RULE = re.compile(r"^[\s|:\-]+$")


_CJK_RUN = re.compile(r"^[ \t]*([\u3400-\u9fff·・]{2,12})")
_CJK_SUFFIX = re.compile(r"(證券|证券|証券|銀行|银行|金融|集團|集团|國際|国际|資本|资本|財富|财富|理財|理财|控股)+$")
# 泛称里常见、品牌名里少见的字：疑问、连接、动词（「哪間香港銀行」「出入金銀行」「證券或銀行」）
_CJK_FUNCTION = set("哪邊边間间或的與与及和之在是有為为个個些揀拣選选配常見见出入持適适虛虚擬拟傳传統统各該该此其他你我")
_CJK_GENERIC = ("傳統", "传统", "網上", "网上", "網絡", "网络", "互聯網", "互联网", "本地", "本港", "香港", "海外", "美國", "美国",
                "部分", "主要", "主流", "虛擬", "虚拟", "數字", "数字", "電子", "电子", "零售", "大型", "中資", "中资", "港資",
                "港资", "外資", "外资", "各大", "其他", "其它", "一般", "熱門", "热门", "老牌", "大型", "綜合", "综合", "國際性",
                "代表", "相關", "相关", "所有", "多家", "不同", "合資格", "合资格", "持牌", "上市", "私人", "個人", "个人")
_INLINE_BOLD = re.compile(r"(?:\*\*|__)([^*_\n]{2,40})(?:\*\*|__)")


def cjk_lead_name(text: str) -> str | None:
    """推荐位或加粗片段开头的中文机构名：以机构后缀结尾，或紧跟「（英文名）」；泛称前缀排除。"""
    m = _CJK_RUN.match(text or "")
    if not m:
        return None
    name = m.group(1)
    m2 = _CJK_SUFFIX.search(name)
    if not m2:
        return None
    stem = name[:m2.start()]
    if not 2 <= len(stem) <= 4 or stem.startswith(_CJK_GENERIC) or set(stem) & _CJK_FUNCTION:
        return None
    return name


def lead_name(text: str) -> str | None:
    """推荐位开头的名字：第一个大写词，加上后面紧跟的、不含数字、不是常用词的大写词，最多 3 个。

    「Aoocci C3 Pro」→ Aoocci；「Handlebar HQ」→ Handlebar HQ；「Best overall」→ Best（之后按常用词降档）。
    """
    m = _LEAD_WORDS.match(text or "")
    if not m:
        return None
    words = m.group(1).split()
    name = [words[0]]
    for w in words[1:3]:
        if any(ch.isdigit() for ch in w) or is_common_word(w):
            break
        name.append(w)
    cand = " ".join(name)
    return cand if usable(cand) else None


def list_heads(text: str) -> set[str]:
    heads = set()
    for regex in _LIST_HEAD_RES:
        for m in regex.finditer(text):
            rest = m.group("rest")
            if _TABLE_RULE.match(rest):
                continue
            cand = lead_name(rest) or cjk_lead_name(rest.lstrip("*_ \t"))
            if cand:
                heads.add(cand)
    for m in _INLINE_BOLD.finditer(text):
        cand = cjk_lead_name(m.group(1))
        if cand:
            heads.add(cand)
    return heads


def card_names(platform: str, task: dict) -> tuple[set[str], set[str]]:
    """商品卡上的名字：(卡标题开头的名字 ∪ 平台品牌字段, 其中来自平台品牌字段的)。"""
    names, brand_fields = set(), set()
    for card in extract_product_cards(platform, task) or []:
        hint = (card.get("brand_hint") or "").strip()
        if hint and re.match(WORD, hint):
            names.add(hint)
            brand_fields.add(hint)
        cand = lead_name(card.get("title") or "")
        if cand:
            names.add(cand)
    return names, brand_fields


def domain_labels(task: dict) -> set[str]:
    """答案里出现过的注册域名主标签，去掉非字母数字（hi-sound.com → hisound）。"""
    labels = set()
    for url in extract_urls(json.dumps(task, ensure_ascii=False)):
        host = normalize_host(url)
        if not host:
            continue
        label = registrable_domain(host).split(".")[0]
        key = re.sub(r"[^a-z0-9]", "", label.lower())
        if len(key) >= 3:
            labels.add(key)
    return labels


def name_key(cand: str) -> str:
    return re.sub(r"[^a-z0-9]", "", cand.lower())


def mine(collect_dirs):
    """Return (occurrences, doc_count, sample_sentences, stats, signals)."""
    if isinstance(collect_dirs, str):
        collect_dirs = [collect_dirs]
    occ = collections.Counter()
    docs = collections.Counter()
    samples = {}
    list_docs = collections.Counter()
    card_docs = collections.Counter()
    card_brand_docs = collections.Counter()
    labels_seen = set()
    head_total = collections.Counter()
    lower = collections.Counter()

    n_files = 0
    for platform, region, path, text, raw, task in (
            doc for d in collect_dirs for doc in iter_docs(d)):
        n_files += 1
        lower.update(_LOWER_RE.findall(text))
        heads = list_heads(text)
        cards, card_brands = card_names(platform, task)
        card_brand_docs.update(card_brands)
        labels_seen |= domain_labels(task)
        for cand in heads:
            list_docs[cand] += 1
            head_total[cand] += 1
        for cand in cards:
            card_docs[cand] += 1
        for cand in heads | cards:
            if cand not in samples:
                i = text.find(cand)
                samples[cand] = (re.sub(r"\s+", " ", text[max(0, i - 60):i + 80]).strip()
                                 if i >= 0 else f"[商品卡] {cand}")
        seen = set(heads | cards)
        for regex in (TOKEN_RE, NGRAM_RE):
            for m in regex.finditer(text):
                cand = m.group(0).strip()
                if not usable(cand):
                    continue
                occ[cand] += 1
                seen.add(cand)
                if cand not in samples:
                    a = max(0, m.start() - 60)
                    b = min(len(text), m.end() + 80)
                    samples[cand] = re.sub(r"\s+", " ", text[a:b]).strip()
        for cand in seen:
            docs[cand] += 1
    signals = {"list_docs": list_docs, "card_docs": card_docs,
               "domain": {c for c in docs if name_key(c) in labels_seen},
               "card_brand": card_brand_docs, "lower": lower, "occ": occ}
    return occ, docs, samples, {"files": n_files}, signals


_LOWER_RE = re.compile(r"\b[a-z][a-z0-9]*(?:[-'][a-z0-9]+)*\b")


def looks_common(cand: str, signals) -> bool:
    """第一个词是普通词：英文常用词表里有（连字符、撇号拆开后每段都有，Built-in、I'd），
    或在这批答案里小写写法不少于大写写法（Motorcycle、Touchscreen 这类常用词表收不全的现代词）。"""
    first = cand.split()[0]
    parts = [x for x in re.split(r"[-']", first) if x]
    if len(parts) > 1 and any(x[0].islower() and common_form(x) for x in parts[1:]):
        return True  # 修饰性复合词：Built-in、Glove-friendly、BMW-specific、I'd
    if len(parts) == 1 and not (first.isupper() and len(first) > 4) and common_form(first, signals["lower"]):
        return True  # 5 个字母以上全大写（RIDEN）不查词典，只看小写比例
    cap = signals["occ"][first]
    return signals["lower"][first.lower()] >= max(2, cap * 0.5)


def common_form(word: str, lower=None) -> bool:
    """英文常用词，含简单屈折变化（Largest、Advantages、Fees）。

    给了 ``lower``（答案里小写词的计数）时，屈折还原出的词根要在答案里以小写出现过，或这个词本身有小写写法：
    Motorys 去 s 得到冷僻词 motory，答案里从没有小写的 motory，不算普通词。"""
    w = word.lower()
    if len(w) <= 1 or is_common_word(w):
        return True
    stems = []
    for suf, rep_ in (("iest", "y"), ("ies", "y"), ("est", ""), ("es", ""), ("s", ""),
                      ("ed", ""), ("ing", ""), ("er", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stems += [w[: -len(suf)] + rep_, w[: -len(suf)] + rep_ + "e"]
    if lower is None:
        return any(is_common_word(x) for x in stems)
    return any(is_common_word(x) and (lower[x] > 0 or lower[w] > 0) for x in stems)


_MODEL_TOKEN = re.compile(r"^[A-Z]{0,4}-?\d+[A-Z]{0,3}$")


def tier_of(cand: str, verdict: str, signals) -> str:
    """A：必须逐个过；B：抽看；C：普通词。规则见文件开头「不漏开放竞品」。"""
    if verdict != "unknown":
        return ""
    common = looks_common(cand, signals)
    listed = signals["list_docs"][cand] > 0
    carded = signals["card_docs"][cand] > 0
    card_brand = signals["card_brand"][cand] > 0
    domain = cand in signals["domain"]
    model_like = any(_MODEL_TOKEN.match(tok) for tok in cand.split())
    acronym = cand.isupper() and len(re.sub(r"[^A-Z]", "", cand)) <= 4
    if common:
        return "A" if card_brand else "C"
    if model_like:
        return "B"
    if acronym:
        return "A" if (carded or domain) and (listed or carded) else "B"
    return "A" if (listed or carded) else "B"


# --------------------------------------------------------------------------
# Lexicon matching
# --------------------------------------------------------------------------

def load_lexicon(path: str):
    """Return (alias->brand, stopword set) lowercased. Brands come from core lexicon.load_lexicon
    (same reader as the report); ``uncertain`` names and ``stopwords`` are read from the raw file."""
    entries, _uncertain, _status = core_load_lexicon(path)
    alias_map = {}
    for brand in entries:
        for alias in [brand["name"], *brand["aliases"]]:
            if alias:
                alias_map[alias.lower()] = brand["name"]
    with open(path, encoding="utf-8") as fh:
        lex = json.load(fh)
    lex = lex if isinstance(lex, dict) else {}
    for entry in lex.get("uncertain", []):
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            alias_map.setdefault(name.lower(), f"uncertain:{name}")
    stop = {w.lower() for w in lex.get("stopwords", []) if w}
    return alias_map, stop

def config_brands(case_path: str | None, bank_path: str | None) -> dict:
    """Case 与题库 config 里的本品和配置竞品 → {别名小写: 品牌名}。它们常不在开放品牌词表里，
    不并进来会把本品和配置竞品误列成「没收」（oraimo、Solvely 实测）。"""
    out = {}
    if case_path:
        with open(case_path, encoding="utf-8") as fh:
            case = json.load(fh)
        names = [case.get(k) for k in ("品牌", "品牌名称", "brand")]
        names += [case.get(f"竞品 {i}") for i in range(1, 6)]
        comp = case.get("competitors")
        names += comp if isinstance(comp, list) else []
        for n in names:
            n = n.get("name") if isinstance(n, dict) else n
            if n and str(n).strip():
                out[str(n).strip().lower()] = str(n).strip()
    if bank_path:
        from trial_brand_count import build_brands  # 同目录；题库 config 的读法只有这一份
        from geo_presales_core.runs import load_bank
        _raw, bank, _questions = load_bank(bank_path)
        brands, _ = build_brands(bank.get("config") or {}, None)
        for b in brands:
            for a in b["aliases"]:
                out[a.lower()] = b["name"]
    return out


def classify(cand: str, alias_map, stop):
    """Return a verdict string for one candidate.

    Longest-alias-first so that "Aqua Kent Singapore" resolves to the brand
    "Aqua Kent" instead of being swallowed by the bare "Aqua" stopword, and
    "Bewinch's" resolves via possessive stripping.
    """
    low = cand.lower().strip()
    if low.endswith("'s"):
        low = low[:-2]
    if low in alias_map:
        return alias_map[low]
    if low in stop:
        return "stopword"
    # Any alias that is a whole-word prefix of the candidate ("Aqua Kent
    # Singapore", "Velta HydroFirst+").
    for alias, brand in alias_map.items():
        if len(alias) < len(low) and low.startswith(alias) and \
                low[len(alias)] in " -+/&":
            return brand
    # 中文名：词表里的中文别名包含在候选里，或候选包含在中文别名里（耀才 ⊂ 耀才證券）。
    if re.search(r"[\u3400-\u9fff]", cand):
        for alias, brand in alias_map.items():
            if re.search(r"[\u3400-\u9fff]", alias) and len(alias) >= 2 and (alias in cand or cand in alias):
                return brand
    # An n-gram whose head word is a known brand ("Coway Malaysia").
    parts = low.split()
    if len(parts) > 1 and parts[0] in alias_map:
        return alias_map[parts[0]]
    if len(parts) > 1 and parts[0] in stop:
        return "stopword"
    return "unknown"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect-dir", required=True, nargs="+",
                    help="one or more directories holding scraper.<platform>/<REGION>/*.json "
                         "(several trial runs are mined together)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="candidate CSV path")
    ap.add_argument("--lexicon", default=None,
                    help="brand lexicon JSON used for classification; "
                         "omitted = classify without it")
    ap.add_argument("--min-count", type=int, default=2,
                    help="drop candidates below this occurrence count "
                         "(default 2; singletons are mostly citation artefacts)")
    ap.add_argument("--top", type=int, default=0,
                    help="only emit the N most frequent candidates (0 = all)")
    ap.add_argument("--show-unknown", type=int, default=40,
                    help="how many tier-B unknown candidates to print to stdout "
                         "(tier A is always printed in full)")
    ap.add_argument("--case", default=None,
                    help="Case JSON：本品和竞品 1–3 当作已收（开放品牌词表里常不写它们）")
    ap.add_argument("--bank", default=None,
                    help="题库 bank.json：config 里的本品、别名和配置竞品当作已收")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when tier-A unknowns seen in >= --check-min-docs answers remain")
    ap.add_argument("--check-min-docs", type=int, default=2,
                    help="answer count for --check (default 2)")
    args = ap.parse_args(argv)

    for d in args.collect_dir:
        if not os.path.isdir(d):
            ap.error(f"collect dir not found: {d}")

    alias_map, stop = {}, set()
    if args.lexicon and os.path.isfile(args.lexicon):
        alias_map, stop = load_lexicon(args.lexicon)
    elif args.lexicon:
        print(f"[warn] lexicon not found, classifying without it: "
              f"{args.lexicon}", file=sys.stderr)

    for alias, brand in config_brands(args.case, args.bank).items():
        alias_map.setdefault(alias, brand)

    occ, docs, samples, stats, signals = mine(args.collect_dir)

    rows = []
    for cand in set(occ) | set(docs):
        count = occ[cand]
        verdict = classify(cand, alias_map, stop)
        tier = tier_of(cand, verdict, signals)
        if count < args.min_count and tier != "A":
            continue
        rows.append({
            "candidate": cand,
            "occurrences": count,
            "doc_count": docs[cand],
            "words": len(cand.split()),
            "verdict": verdict,
            "tier": tier,
            "list_docs": signals["list_docs"][cand],
            "card_docs": signals["card_docs"][cand],
            "domain": "yes" if cand in signals["domain"] else "",
            "sample": samples.get(cand, ""),
        })
    tier_rank = {"A": 0, "": 1, "B": 2, "C": 3}
    rows.sort(key=lambda r: (tier_rank[r["tier"]], -r["doc_count"], -r["occurrences"], r["candidate"]))
    if args.top:
        rows = rows[:args.top]

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["candidate", "occurrences", "doc_count", "words",
                            "verdict", "tier", "list_docs", "card_docs", "domain", "sample"])
        writer.writeheader()
        writer.writerows(rows)

    verdicts = collections.Counter(r["verdict"].split(":")[0] for r in rows)
    n_stop = verdicts.get("stopword", 0)
    n_unknown = verdicts.get("unknown", 0)
    print(f"files scanned : {stats['files']}")
    print(f"candidates    : {len(occ)} distinct, {len(rows)} emitted")
    print(f"  brand-name  : {len(rows) - n_stop - n_unknown}")
    print(f"  stopword    : {n_stop}")
    print(f"  unknown     : {n_unknown}")
    print(f"csv           : {out_path}")

    # 推荐位覆盖：推荐位上出现过的名字（去掉单个常用词）里，词表已收或已判停用词的占比。
    heads = [r for r in rows if r["list_docs"] and not (r["words"] == 1 and is_common_word(r["candidate"]))]
    covered = sum(r["list_docs"] for r in heads if r["verdict"] != "unknown")
    total = sum(r["list_docs"] for r in heads)
    if total:
        print(f"list-head coverage: {covered}/{total} = {covered / total:.0%} "
              f"(推荐位上的名字有多少已被词表或停用词收下)")

    tier_a = [r for r in rows if r["tier"] == "A"]
    if tier_a:
        print(f"\ntier A — 词表没收、但在推荐位/商品卡/同名域名上出现过，逐个过（{len(tier_a)} 个）:")
        print("  docs  list  card  domain  candidate")
        for r in tier_a:
            print(f"  {r['doc_count']:>4}  {r['list_docs']:>4}  {r['card_docs']:>4}  {r['domain'] or '-':>6}  {r['candidate']}")
    tier_b = [r for r in rows if r["tier"] == "B"]
    if tier_b and args.show_unknown:
        print(f"\ntier B top {args.show_unknown} — 其余没收的大写词，抽看即可:")
        for r in tier_b[:args.show_unknown]:
            print(f"  {r['occurrences']:>5}  {r['candidate']}")
    if args.check:
        failed = False
        if args.lexicon and os.path.isfile(args.lexicon):
            from audit_lexicon_domains import split_suspects  # 同目录；只查拆分，域名问题另跑该脚本
            with open(args.lexicon, encoding="utf-8") as fh:
                suspects = split_suspects(json.load(fh))
            if suspects:
                failed = True
                print(f"\n[check] 疑似同一品牌拆成两条（{len(suspects)} 对）：是同一家就合并成一条，"
                      f"确是两家写进词表顶层 distinct_brands", file=sys.stderr)
                for item in suspects:
                    print(f"  {item}", file=sys.stderr)
        blocking = [r for r in tier_a if r["doc_count"] >= args.check_min_docs]
        if blocking:
            print(f"\n[check] {len(blocking)} 个 A 档候选出现在 ≥{args.check_min_docs} 条回答里，"
                  f"收进词表或停用词后再算指标", file=sys.stderr)
            failed = True
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
