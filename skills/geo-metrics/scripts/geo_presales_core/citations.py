"""从各平台回答里抽引用、计次：报告数据层、监测试跑判读、品牌识别对账都调这一份。

计数单位与折叠规则见 geo-metrics/references/metric-scope-and-copy-contract.md。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .util import is_platform_internal, normalize_host, normalize_url
from .util import strip_tracking_params as clean_url

# 引用字段：逐平台不同。Grok 的 footnotes 是以 card id 为键的对象，不是数组
CITATION_FIELD = {"overview": "source", "gemini": "citations",
                  "chatgpt": "content_references", "perplexity": "web_results", "aimode": "citations",
                  "copilot": "citations", "grok": "footnotes", "alexa": "references"}

# Alexa 的 md_text 不带引用标记，引用位置只留在 raw_text 的 `{ref cite_<id>}`，按 id 对
# references。id 偶有重复前缀（`cite_cite_dx9kveQ`），比对前剥掉。2026-10-21 实测：
# 正文引用的 id 有一部分在 references 里找不到，照样计次数、记为 unresolved。
ALEXA_REF_MARKER = re.compile(r"\{ref\s+((?:cite_)+)([A-Za-z0-9_-]+)\}")

# 「同一回答内同一 URL 折叠为一条」的平台：这些平台会把一个逻辑来源拆成多条引用条目，
# 把同一页面在一个回答里重复计数——Gemini 按 `…#:~:text=` 文本片段拆，AIO(overview)
# 按「空壳条目(title/snippet 空) + 填充条目」或同页多摘要拆。按 canonical 折叠成一条
# （「同一 url 视为同一引用」）。ChatGPT / Perplexity 不在此列：它们的重复是正文里对同一
# 来源的多次真实引用，按实际次数计，不折叠。
CITATION_URL_COLLAPSE_PLATFORMS = {"gemini", "overview"}

# 正文引用标记。四平台格式一致：定义行 `[3]: https://… "标题"`，行内标记 `([来源名][3])`。
_BODY_REF_DEF = re.compile(r"^\s*\[(\d+)\]:\s*(\S+?)(?:\s+\"([^\"]*)\")?\s*$", re.M)
_BODY_REF_MARKER = re.compile(r"\(\[([^\]\n]{1,80})\]\[(\d+)\]\)")
_BODY_REF_MARKER_BARE = re.compile(r"(?<!\[)\[([^\]\n]{1,80})\]\[(\d+)\]")


def _platform_citation_entries(task_result: dict, field: str) -> list[dict]:
    """供应商引用字段的条目。字段是回退来源，不是首选来源。"""
    items = task_result.get(field) or []
    if not isinstance(items, list):
        return []
    out = []
    for order, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
        if not url:
            continue
        url = clean_url(url)
        host = normalize_host(url)
        if not host or is_platform_internal(host):
            continue
        title = (raw.get("title") or raw.get("name") or raw.get("attribution")
                 or raw.get("website_name") or "")
        out.append({
            "raw_citation_id": None,
            "source": "platform",
            "source_order": order,
            "raw_url": url,
            "source_name": raw.get("website_name") or raw.get("attribution"),
            "domain_hint": host,
            "title": str(title).strip() or None,
            "date": raw.get("date"),
            "summary": raw.get("snippet") or raw.get("summary"),
            "source_position": None,
            "positions": raw.get("positions") or [],
            "extraction_method": field,
            "platform_reported_type": raw.get("type"),
        })
    return out


def _body_citation_occurrences(text: str) -> tuple[dict, list]:
    """从回答正文解析引用定义行与标记出现。

    定义行形如 `[3]: https://… "标题"`，行内标记形如 `([来源名][3])`。
    标记出现次数才是「引用次数」的计数单位：同一 URL 在一篇里出现 N 次就计 N 次。
    """
    definitions = {}
    for number, url, title in _BODY_REF_DEF.findall(text or ""):
        definitions[number] = {"url": url, "title": title}
    spans, occurrences = [], []
    for match in _BODY_REF_MARKER.finditer(text or ""):
        spans.append(match.span())
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    for match in _BODY_REF_MARKER_BARE.finditer(text or ""):
        if any(start <= match.start() < end for start, end in spans):
            continue
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    occurrences.sort(key=lambda item: item[2])
    return definitions, occurrences


def _citation_keep_mask(occ_canonicals: list, collapse: bool) -> list:
    """逐条正文引用是否计入引用次数（区分平台伪拆分与正文真重复）。

    `occ_canonicals`：按正文顺序的 `(reference_number, canonical_url)` 列表，
    `canonical_url` 为 None 表示这条 pill 解析不出 URL。

    `collapse=True`（Gemini / AIO）：这些平台会把**一个来源**拆成多个编号
    （Gemini 按 `…#:~:text=` 文本片段、AIO 按「裸桩条目 + 完整条目」），造成
    「不同编号指向同一 URL」的伪重复；但正文**同一编号被多次引用**是真重复，必须保留。
    规则：每个 canonical 只保留「出现次数最多的那个编号」的全部引用（并列取编号最小者），
    其余编号视为伪拆分丢弃；解析不出 URL 的引用无法判断，一律保留。
    这样 Gemini（各编号各一次）折叠到每 URL 一条，AIO 的真重复（同编号多次）原样保留。

    `collapse=False`（ChatGPT / Perplexity）：正文对同一来源的多次引用都是真实次数，
    全部保留。
    """
    if not collapse:
        return [True] * len(occ_canonicals)
    per_canon: dict[str, Counter] = defaultdict(Counter)
    for number, canonical in occ_canonicals:
        if canonical is not None:
            per_canon[canonical][number] += 1
    winner: dict[str, str] = {}
    for canonical, counter in per_canon.items():
        winner[canonical] = min(
            counter.items(),
            key=lambda kv: (-kv[1], int(kv[0]) if str(kv[0]).isdigit() else 1_000_000),
        )[0]
    return [canonical is None or number == winner[canonical]
            for number, canonical in occ_canonicals]


def _cited_count_entries(platform: str, task_result: dict):
    """新格式引用条目：直接按供应商的 `cited_count` 计次数。

    `cited_count` 是**未去重的引用次数**（供应商按正文 pill 统计，实测与正文逐条一致：
    Bbrand 探针 2026-10-13，ChatGPT 14=14、Gemini 16=16、AI Mode 15=15、Perplexity 3=3；
    当天新采的 ChatGPT 3=3）。字段已按 URL 去重，所以一条来源就是一行数据 + 一个次数。

    返回 None 表示这批是旧格式（字段里没有任何 `cited_count`），调用方回退到正文 pill 计数。

    **逐格判代数，不按平台或日期一刀切**：ChatGPT 2026-10-10 及更早的批次没有该字段，
    10-13 起才有；AIO 同一批里正文未引用的来源条目也可能缺字段（AI Mode 写 0，AIO 省略）。
    两种情况都由下面这个 `any(...)` 分派到正确的计数路径。

    计数规则：
    - `cited_count > 0`：计该次数，次数写入 `cited_count`。
    - `cited_count == 0`：正文没引用，不计（Perplexity 实测 10 条里 7 条为 0）。
    - 字段缺失：按 0 处理（AIO 的未引用来源直接省略字段，而不是写 0）。
    - AIO 的商品卡（`type=product`、`index` 为 null）没有该字段，自然为 0，不计入引用。
    """
    field = CITATION_FIELD.get(platform)
    raw_items = task_result.get(field)
    if not isinstance(raw_items, list):
        return None
    if not any(isinstance(item, dict) and isinstance(item.get("cited_count"), int)
               for item in raw_items):
        return None
    out = []
    for order, raw in enumerate(raw_items, 1):
        if not isinstance(raw, dict):
            continue
        count = raw.get("cited_count")
        count = count if isinstance(count, int) else 0
        if count <= 0:
            continue
        raw_url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
        url = clean_url(raw_url) if raw_url else ""
        host = normalize_host(url) if url else None
        if host and is_platform_internal(host):
            continue
        title = (raw.get("title") or raw.get("name") or raw.get("attribution")
                 or raw.get("website_name") or "")
        for _ in range(count):
            out.append({
                "raw_citation_id": None,
                "source": "platform_cited_count",
                "source_order": order,
                "raw_url": url or None,
                "source_name": raw.get("website_name") or raw.get("attribution"),
                "domain_hint": host,
                "title": str(title).strip() or None,
                "date": raw.get("date"),
                "summary": raw.get("snippet") or raw.get("summary"),
                "source_position": None,
                "positions": raw.get("positions") or [],
                "extraction_method": f"{field}.cited_count",
                "platform_reported_type": raw.get("type"),
                "reference_number": str(raw.get("index")) if raw.get("index") is not None else None,
                "mapping_method": "platform_cited_count",
                "in_table_row": False,
            })
    return out


def _alexa_citation_entries(task_result: dict) -> list[dict]:
    """Alexa 的引用次数：raw_text 里 `{ref cite_<id>}` 的出现次数，按 id 对 references 取 URL。

    与正文 pill 口径一致：一次出现计一次；references 里找不到的 id 照样计入、记 unresolved。
    """
    raw_text = str(task_result.get("raw_text") or "")
    refs = {}
    for item in task_result.get("references") or []:
        if isinstance(item, dict) and item.get("id"):
            refs[re.sub(r"^(?:cite_)+", "", str(item["id"]))] = item
    out = []
    for match in ALEXA_REF_MARKER.finditer(raw_text):
        ref_id = match.group(2)
        item = refs.get(ref_id) or {}
        raw_url = str(item.get("url") or "").strip()
        url = clean_url(raw_url) if raw_url else ""
        host = normalize_host(url) if url else None
        if host and is_platform_internal(host):
            continue
        line_start = raw_text.rfind("\n", 0, match.start()) + 1
        out.append({
            "raw_citation_id": None,
            "source": "body_marker",
            "source_order": len(out) + 1,
            "raw_url": url or None,
            "source_name": None,
            "domain_hint": host,
            "title": str(item.get("title") or "").strip() or None,
            "date": None,
            "summary": None,
            "source_position": match.start(),
            "positions": [],
            "extraction_method": "alexa_raw_text_ref",
            "platform_reported_type": None,
            "reference_number": ref_id,
            "mapping_method": "alexa_reference_id" if url else "unresolved",
            "in_table_row": raw_text[line_start:].lstrip().startswith("|"),
        })
    return out


def _citation_entries(platform: str, task_result: dict, answer_text: str = "") -> list[dict]:
    """引用条目 = 该回答实际引用各来源的次数。

    计数单位是「引用次数」：同一来源被引用 N 次就计 N 次（拆成 N 行，每行次数 1，
    下游按行数统计，`cited_count` 字段保留原始次数便于核对）。

    首选**供应商 `cited_count`**（新格式，2026-10-13 起五个平台都带；实测与正文 pill
    逐条一致，Suda 2026-10-13 定为唯一口径）。字段不存在时回退到正文 pill 计数：
    解析定义行与行内标记，Gemini / AIO 的旧格式伪拆分按 `_citation_keep_mask` 折叠、
    保留正文同一编号的真重复，ChatGPT / Perplexity 全部按实际次数计。
    Alexa 正文不带标记，走 `_alexa_citation_entries`。
    """
    if platform == "alexa":
        return _alexa_citation_entries(task_result)
    cited = _cited_count_entries(platform, task_result)
    if cited is not None:
        return cited

    field = CITATION_FIELD.get(platform)
    definitions, occurrences = _body_citation_occurrences(answer_text)

    if not occurrences:
        # 引用次数只计正文 pill（`([来源名][N])`）的出现次数。
        # 正文一条 pill 都没有就是 0 条引用——不拿供应商字段的来源清单充数，
        # 那是「回答引用了哪些来源」的另一个口径（Suda 2026-09-16）。
        return []

    raw_items = task_result.get(field)
    fallback_items = raw_items if isinstance(raw_items, list) else []
    candidates = []
    occ_canonicals = []
    for label, number, position in occurrences:
        line_start = answer_text.rfind("\n", 0, position) + 1
        in_table_row = answer_text[line_start:].lstrip().startswith("|")
        definition = definitions.get(number)
        raw_url = definition["url"] if definition else None
        title = definition["title"] if definition else None
        mapping = "body_definition"
        if not raw_url and number.isdigit() and 0 < int(number) <= len(fallback_items):
            item = fallback_items[int(number) - 1]
            if isinstance(item, dict):
                raw_url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
                title = title or item.get("title") or item.get("name")
                mapping = "platform_field_positional"
        if not raw_url:
            mapping = "unresolved"
        url = clean_url(raw_url) if raw_url else ""
        host = normalize_host(url) if url else None
        if host and is_platform_internal(host):
            continue
        canonical = None
        if url:
            normalized = normalize_url(url)
            canonical = (normalized or {}).get("canonical_url") or url
        occ_canonicals.append((number, canonical))
        candidates.append({
            "raw_citation_id": None,
            "source": "body_marker",
            "source_order": None,
            "raw_url": url or None,
            "source_name": label,
            "domain_hint": host,
            "title": str(title).strip() if title else None,
            "date": None,
            "summary": None,
            "source_position": position,
            "positions": [],
            "extraction_method": "body_reference_marker",
            "platform_reported_type": None,
            "reference_number": number,
            "mapping_method": mapping,
            "in_table_row": in_table_row,
        })

    keep = _citation_keep_mask(occ_canonicals, platform in CITATION_URL_COLLAPSE_PLATFORMS)
    out = []
    for candidate, keep_it in zip(candidates, keep):
        if not keep_it:
            continue
        candidate["source_order"] = len(out) + 1
        out.append(candidate)
    return out
