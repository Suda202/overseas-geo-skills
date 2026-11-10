from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}

# Standard-library-only approximation used for display aggregation. Official-domain
# matching never depends on this list. The audit artifact exposes this limitation.
COMMON_MULTI_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au",
    "co.jp", "ne.jp", "or.jp",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.sg", "com.hk", "com.tw", "co.nz",
    "com.br", "com.mx", "co.in", "co.kr",
    # 东南亚市场二级后缀；缺了会把所有马来西亚站点并成一个 "com.my" 桶
    "com.my", "net.my", "org.my", "gov.my", "edu.my", "net.sg", "org.sg",
    "com.ph", "net.ph", "co.th", "or.th", "com.vn", "com.id", "co.id", "com.bn",
    # 新加坡政府、教育、个人站按机构拆开（hdb.gov.sg 与 ura.gov.sg 是两个来源），都是公共后缀表正式后缀
    "gov.sg", "edu.sg", "per.sg",
}

# Google 等新跟踪参数：采集入口先剥掉（strip_tracking_params），避免同一页面被计成多条引用
INGEST_EXTRA_TRACKING_KEYS = {
    "srsltid", "gbraid", "wbraid", "yclid", "igshid", "gad_source", "gclsrc",
    "msclkid", "ref_src", "ref_url", "guccounter", "guce_referrer", "spm", "scm",
}

# 平台站内跳转 / 聚合页链接，按契约不算引用
PLATFORM_INTERNAL_HOSTS = {
    "google.com", "google.com.sg", "google.com.my", "google.co", "google.com.hk",
    "gstatic.com", "googleusercontent.com", "bing.com", "chatgpt.com", "openai.com",
    "perplexity.ai", "gemini.google.com",
    "copilot.microsoft.com", "bingapis.com", "grok.com",
}


def is_platform_internal(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in PLATFORM_INTERNAL_HOSTS)


def strip_tracking_params(raw_url: str) -> str:
    """采集入口剥离跟踪参数，保留路径与分片；没有可剥的就原样返回。"""
    keys = TRACKING_QUERY_KEYS | INGEST_EXTRA_TRACKING_KEYS
    try:
        parts = urlsplit(str(raw_url))
        pairs = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        return str(raw_url)
    if not pairs:
        return str(raw_url)
    kept = [(k, v) for k, v in pairs if k.casefold() not in keys]
    if len(kept) == len(pairs):
        return str(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


class ContractError(ValueError):
    """Raised when an input or task result violates a frozen contract."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_json(path: str | Path, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_text(path: str | Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_alias(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


# 词边界只对拉丁字母/数字边缘成立。泰文、中文这类无空格文字里，品牌名前后紧邻
# 同文种字母同样是 `\w`，`(?<![\w])` / `(?![\w])` 会让别名在连续正文里永远匹配
# 不上（乙大学 `มหาวิทยาลัยอัลฟา` 即此例）。非拉丁边缘不加边界，改由
# `resolve_alias_spans` 用最长优先不重叠消解处理撞名。
_LATIN_EDGE = re.compile(r"[0-9A-Za-zÀ-ɏḀ-ỿ]")


def _has_latin_edge(char: str) -> bool:
    return bool(char and char.isalnum() and _LATIN_EDGE.match(char))


# 品牌识别的两条通用规则（2026-11-10），只作用于拉丁字母别名：
# 1. 5 个字母以上的别名，字符之间可夹 1 个空格/连字符/点/下划线（Blue Wave = BlueWave）；原文被这样
#    拆开时每段都要大写开头，免得普通短语混进来（「blue wave patterns」不算 BlueWave）；
# 2. 别名是英文常用词时，原文必须带大写才算（apple juice 不算 Apple）。
# 去后缀派生简称试过后撤回：「某系统名 + Security」派生出操作系统名、带数字的品牌派生出纯数字，
# 简称常是另一个实体，只在对账脚本里列成候选，由人工或 AI 确认后写进别名。
# 常用词表随包带（取自 Webster's 2nd 小写词条），线上拷贝 core 时一起走，各机器读数一致。
_LATIN_ALIAS = re.compile(r"^[0-9A-Za-zÀ-ɏḀ-ỿ .&'+\-_]+$")
_SEPARATORS = "-_. "
_SEPARATOR_RUN = re.compile(r"[\s\-_\.]+")
_WORDS_PATH = Path(__file__).with_name("english_words.txt")
_COMMON_WORDS: frozenset[str] | None = None


def is_common_word(alias: str) -> bool:
    global _COMMON_WORDS
    if _COMMON_WORDS is None:
        _COMMON_WORDS = frozenset(_WORDS_PATH.read_text(encoding="utf-8").split())
    token = str(alias or "").strip().casefold()
    return bool(token) and " " not in token and token in _COMMON_WORDS


def _alnum_len(alias: str) -> int:
    return sum(1 for ch in alias if ch.isalnum())


def _separator_tolerant(alias: str) -> bool:
    return bool(_LATIN_ALIAS.match(alias)) and _alnum_len(alias) >= 5


def _alias_regex(alias: str) -> str:
    if not _separator_tolerant(alias):
        return re.escape(alias).replace(r"\ ", r"[\s\-_\.]*")
    parts = []
    for index, char in enumerate(alias):
        if char in _SEPARATORS:
            parts.append(r"[\s\-_\.]*")
            continue
        parts.append(re.escape(char))
        following = alias[index + 1:index + 2]
        if char.isalnum() and following.isalnum():
            parts.append(r"[ \-_\.]?")
    return "".join(parts)


def _split_is_capitalised(alias: str, matched: str) -> bool:
    pieces = [p for p in _SEPARATOR_RUN.split(matched) if p]
    if len(pieces) <= len([p for p in _SEPARATOR_RUN.split(alias) if p]):
        return True
    return all(p[0].isupper() or p[0].isdigit() for p in pieces)


def find_alias_spans(text: str, aliases: list[str], case_sensitive=None) -> list[dict]:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    matches: list[dict] = []
    for raw_alias in sorted({str(a).strip() for a in aliases if str(a).strip()}, key=len, reverse=True):
        alias = unicodedata.normalize("NFKC", raw_alias)
        left = r"(?<![\w])" if _has_latin_edge(alias[:1]) else ""
        right = r"(?![\w])" if _has_latin_edge(alias[-1:]) else ""
        pattern = re.compile(left + _alias_regex(alias) + right, re.IGNORECASE | re.UNICODE)
        needs_upper = _LATIN_ALIAS.match(alias) is not None and is_common_word(alias)
        tolerant = _separator_tolerant(alias)
        for found in pattern.finditer(normalized):
            matched = found.group(0)
            if needs_upper and not any(ch.isupper() for ch in matched):
                continue
            if tolerant and not _split_is_capitalised(alias, matched):
                continue
            matches.append({
                "alias": raw_alias,
                "matched_text": matched,
                "start": found.start(),
                "end": found.end(),
            })
    matches.sort(key=lambda item: (item["start"], -(item["end"] - item["start"]), item["alias"].casefold()))
    deduped: list[dict] = []
    seen = set()
    for item in matches:
        key = (item["start"], item["end"], item["alias"].casefold())
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    if case_sensitive:
        # 列在名单里的写法只认原文与名单某个大小写逐字相同（ERA≠era、AVG≠avg）。同位置按
        # casefold 去重后留下哪个别名随集合顺序变，所以判原文写法在不在名单里，不判与留下的别名相等
        listed = set(case_sensitive)
        deduped = [s for s in deduped if s["alias"] not in listed or s["matched_text"] in listed]
    return deduped


def case_sensitive_for(aliases, case_sensitive) -> list[str]:
    """名单里属于这组别名的写法（按 normalize_alias 归并），挂到品牌对象的 case_sensitive_aliases。"""
    own = {normalize_alias(a) for a in aliases or []}
    return sorted({c for c in case_sensitive or [] if normalize_alias(c) in own})


def read_lexicon_list(lexicon_path, key: str) -> list[str]:
    """品牌词表 JSON 顶层的名单字段（case_sensitive_aliases、competitor_site_domains）。"""
    if not lexicon_path or not Path(lexicon_path).exists():
        return []
    raw = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
    values = raw.get(key) if isinstance(raw, dict) else None
    return [str(v).strip() for v in values or [] if str(v).strip()]


def read_case_sensitive_aliases(lexicon_path) -> list[str]:
    """要区分大小写的品牌名或别名写法，对词表内外所有品牌生效。"""
    return read_lexicon_list(lexicon_path, "case_sensitive_aliases")


def resolve_alias_spans(spans: list[dict]) -> list[dict]:
    """跨对象最长优先、互不重叠消解（候选项须带 `object_id`）。

    非拉丁别名丢掉词边界后，短别名会落进别的对象的长别名里：乙大学
    `มหาวิทยาลัยอัลฟา` 是乙大学南校区 `มหาวิทยาลัยอัลฟาตอนใต้` 的前缀，泰国甲大学
    `มหาวิทยาลัยอัลฟาศาสตร์` 又落在乙大学 `มหาวิทยาลัยอัลฟาศาสตร์แห่งประเทศเบตา` 内。
    按起点排序、同起点取更长者，只丢弃与**其它对象**已保留区间重叠的候选。

    只跨对象消解、不动同对象内部的重叠（如某对象同时有 `YouTube` 与
    `YouTube Music`），因此拉丁市场的既有结果逐字节不变——拉丁别名带词边界，
    本就无法互相嵌套，跨对象消解对它是空操作。
    """
    ordered = sorted(
        spans,
        key=lambda item: (item["start"], -(item["end"] - item["start"]), item["alias"].casefold()),
    )
    kept: list[dict] = []
    for candidate in ordered:
        overlaps_other = any(
            kept_item["object_id"] != candidate["object_id"]
            and kept_item["start"] < candidate["end"]
            and candidate["start"] < kept_item["end"]
            for kept_item in kept
        )
        if not overlaps_other:
            kept.append(candidate)
    kept.sort(key=lambda item: (item["start"], -(item["end"] - item["start"]), item["alias"].casefold()))
    return kept


def normalize_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = (urlsplit(raw).hostname or "").rstrip(".").lower()
        host = host.encode("idna").decode("ascii")
    except (ValueError, UnicodeError):
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def domain_matches(host: str, official_domain: str) -> bool:
    host = normalize_host(host)
    domain = normalize_host(official_domain)
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


def registrable_domain(host: str) -> str:
    host = normalize_host(host)
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in COMMON_MULTI_LABEL_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return suffix2


def normalize_url(raw_url: str) -> dict | None:
    raw = str(raw_url or "").strip().replace("\\/", "/")
    if not raw:
        return None
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        return None
    try:
        parsed = urlsplit(raw)
        host = normalize_host(raw)
        if not host:
            return None
        port = parsed.port
        netloc = host
        if port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
            netloc += f":{port}"
        removed: list[str] = []
        kept: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            low = key.casefold()
            if low.startswith("utm_") or low in TRACKING_QUERY_KEYS:
                removed.append(key)
            else:
                kept.append((key, value))
        kept.sort(key=lambda pair: (pair[0], pair[1]))
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        canonical = urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(kept), ""))
        return {
            "canonical_url": canonical,
            "host": host,
            "registrable_domain": registrable_domain(host),
            "removed_query_params": sorted(removed),
        }
    except (ValueError, UnicodeError):
        return None


def extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)\]>\"']+", str(text or ""), flags=re.IGNORECASE)
    return [url.rstrip(".,;:") for url in urls]


def stable_id(prefix: str, value) -> str:
    return f"{prefix}-{sha256_obj(value).split(':', 1)[1][:16]}"


def get_path(value, dotted: str):
    current = value
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(dotted)
    return current


def format_display(value) -> str:
    if isinstance(value, dict) and "display" in value:
        return str(value["display"])
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)

