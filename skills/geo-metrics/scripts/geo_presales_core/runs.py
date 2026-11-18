"""题库与试跑采集目录的公共读法：读题库、找试跑目录、按 manifest 归题、同类品牌与官网匹配。

2026-11-18 从 geo-monitoring/scripts/changeability_domains.py 抽到 core：品牌计数（trial_brand_count）、
可改变性（changeability_domains）、缺口诊断（layer_readings、page_gap、label_batches）都用这一份，
不再互相 import，也不再经由售前报告的 build_report_data 绕进 core。
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from .util import normalize_host, normalize_text

# 题库 region 写国名时对到采集目录的市场代码，只在同一题面出现在多个市场时用来分题。
REGION_CODE = {"singapore": "SG", "malaysia": "MY", "thailand": "TH", "nigeria": "NG", "kenya": "KE",
               "united states": "US", "usa": "US", "korea": "KR", "south korea": "KR", "taiwan": "TW",
               "hong kong": "HK", "philippines": "PH", "indonesia": "ID", "vietnam": "VN",
               "united kingdom": "GB", "uk": "GB", "japan": "JP", "india": "IN", "australia": "AU",
               "canada": "CA", "germany": "DE", "france": "FR", "ghana": "GH", "egypt": "EG",
               "saudi arabia": "SA", "united arab emirates": "AE", "uae": "AE", "mexico": "MX",
               "brazil": "BR", "pakistan": "PK", "bangladesh": "BD"}


class Matcher:
    """域名或「主机+路径前缀」清单。"""

    def __init__(self, values):
        self.hosts, self.prefixes = set(), []
        for raw in values or []:
            raw = str(raw or "").strip()
            if not raw:
                continue
            text = raw if "://" in raw else "https://" + raw
            parts = urlsplit(text)
            host = normalize_host(text)
            path = parts.path.rstrip("/")
            if not host:
                continue
            if path:
                self.prefixes.append((host, path.lower()))
            else:
                self.hosts.add(host)

    def match(self, host: str, url: str) -> bool:
        if not host:
            return False
        if any(host == h or host.endswith("." + h) for h in self.hosts):
            return True
        if self.prefixes:
            path = urlsplit(url).path.lower() if url else ""
            for h, prefix in self.prefixes:
                if (host == h or host.endswith("." + h)) and (path == prefix or path.startswith(prefix + "/")):
                    return True
        return False

    def describe(self):
        return sorted(self.hosts) + [h + p for h, p in self.prefixes]


def load_bank(path: Path):
    raw = path.read_text(encoding="utf-8")
    bank = json.loads(raw)
    questions = bank.get("questions") or []
    if not questions:
        raise SystemExit(f"题库没有 questions：{path}")
    return raw, bank, questions


def q_text(q: dict) -> str:
    return str(q.get("user_question") or q.get("monitoring_prompt") or q.get("query") or "").strip()


def q_region_code(q: dict) -> str:
    region = str(q.get("region") or "").strip()
    return REGION_CODE.get(region.casefold(), region.upper())


def competitor_domains(config: dict) -> list[str]:
    out = []
    pools = [config.get("competitors") or []]
    selection = config.get("competitor_selection") or {}
    if isinstance(selection, dict):
        pools.append(selection.get("formal_competitors") or [])
    for pool in pools:
        for item in pool if isinstance(pool, list) else []:
            if not isinstance(item, dict):
                continue
            for key in ("domain", "official_domain", "website", "official_site"):
                value = item.get(key)
                values = value if isinstance(value, list) else [value]
                out.extend(str(v) for v in values if v)
    return out


def load_vendor_brands(config: dict, lexicon_path):
    """同类品牌：用于品类门槛（认品牌）和竞品官网（认域名）。

    目标品牌和题库 config 里的配置竞品默认同类；词表里 type 为 target / competitor* 的默认同类，
    open 品牌要写 same_category: true 才算（便携导航仪这类别的品类厂商不算）；任何品牌写 same_category: false 就排除。
    返回 ({竞品名: Matcher(官网)}, [{name, aliases, case_sensitive_aliases}], 提示)。
    """
    from . import util as core_util
    merged: dict[str, dict] = {}

    def add(name, aliases=(), domains=(), same=True):
        name = str(name or "").strip()
        if not name:
            return
        slot = merged.setdefault(normalize_text(name), {"name": name, "aliases": set(), "domains": set(), "flags": []})
        slot["aliases"].update(x for x in [name, *(str(a).strip() for a in aliases or [])] if x)
        slot["domains"].update(str(d) for d in domains or [] if d)
        slot["flags"].append(same)  # True / False（词表明写）/ None（开放品牌没写）

    add(config.get("brand_name"), config.get("aliases") or [], [], True)
    target_key = normalize_text(str(config.get("brand_name") or ""))
    for item in config.get("competitors") or []:
        if isinstance(item, dict):
            add(item.get("name"), item.get("aliases") or [],
                [item.get(k) for k in ("domain", "official_domain") if item.get(k)], True)
    note, missing = "", []
    if lexicon_path:
        lex = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
        for b in lex.get("brands") or []:
            kind = str(b.get("type") or "")
            flag = b.get("same_category")
            same = flag if isinstance(flag, bool) else (True if kind == "target" or kind.startswith("competitor") else None)
            if same is None:
                missing.append(b.get("name"))
            add(b.get("name"), b.get("aliases") or [], b.get("domains") or b.get("official_domains") or [], same)
            if kind == "target":
                target_key = normalize_text(str(b.get("name") or "")) or target_key
        if missing:
            note = (f"词表里 {len(missing)} 个开放品牌没写 same_category，按非同类处理：{'、'.join(map(str, missing[:8]))}"
                    + ("…" if len(missing) > 8 else ""))
    else:
        note = "没给 --lexicon：同类品牌只认题库 config 里的本品和配置竞品，品类门槛可能误判"
    case_sensitive = core_util.read_case_sensitive_aliases(lexicon_path) if lexicon_path else set()
    brands, vendors = [], {}
    for key, v in merged.items():
        if False in v["flags"] or True not in v["flags"]:
            continue
        brands.append({"name": v["name"], "aliases": sorted(v["aliases"]),
                       "case_sensitive_aliases": core_util.case_sensitive_for(v["aliases"], case_sensitive)})
        if key != target_key and v["domains"]:
            vendors[v["name"]] = Matcher(sorted(v["domains"]))
    if not any(v for v in merged.values() if True in v["flags"] and False not in v["flags"]):
        note = (note + "；" if note else "") + "题库和词表里都没有同类品牌，跳过品类门槛"
    return vendors, brands, note


def find_runs(paths: list[Path]) -> list[Path]:
    runs = []
    for root in paths:
        root = root.resolve()
        if not root.is_dir():
            raise SystemExit(f"采集目录不存在：{root}")
        candidates = [root] + [p for p in sorted(root.rglob("*")) if p.is_dir()]
        for d in candidates:
            if "_collector" in d.parts or d.name.startswith("scraper."):
                continue
            if any(c.is_dir() and c.name.startswith("scraper.") for c in d.iterdir()):
                if d not in runs:
                    runs.append(d)
    if not runs:
        raise SystemExit("给的目录下没有任何 scraper.<平台> 子目录")
    return runs


def run_questions_csv(run: Path, issues: list):
    """manifest 里的 questions_file → {NNNN: {query, question_id}}；sha256 对不上就不用。"""
    manifest_path = run / "collect-manifest.json"
    if not manifest_path.exists():
        return {}, None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("questions_file")
    if not name:
        return {}, None
    candidates = [Path(name)] if Path(name).is_absolute() else \
        [base / name for base in [run, *run.parents][:6]] + [Path.cwd() / name]
    found = next((p for p in candidates if p.is_file()), None)
    if not found:
        issues.append({"code": "QUESTIONS_CSV_NOT_FOUND", "run": str(run), "questions_file": name})
        return {}, None
    with found.open(encoding="utf-8-sig", newline="") as handle:
        rows = {f"{i:04d}": {"query": str(r.get("query") or "").strip(),
                             "question_id": str(r.get("question_id") or r.get("qid") or "").strip()}
                for i, r in enumerate(csv.DictReader(handle), 1)}
    digest = hashlib.sha256(found.read_bytes()).hexdigest()
    if not manifest.get("questions_sha256") or digest == manifest["questions_sha256"]:
        return rows, found
    # CSV 采集后被改过（常见是补了译文列）。行数不变、且本批所有回显题面的文件都和 CSV 同行一致，
    # 才继续用它给不回显题面的 AIO / AI Mode 归题；否则整批不用 CSV。
    agree, disagree = 0, 0
    for path in run.glob("scraper.*/*/*.json"):
        try:
            task = json.loads(path.read_text(encoding="utf-8")).get("task_result") or {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        echo = str(task.get("prompt") or task.get("user_query") or task.get("user_text") or "").strip()
        row = rows.get(path.stem)
        if not echo:
            continue
        if row and normalize_text(row["query"]) == normalize_text(echo):
            agree += 1
        else:
            disagree += 1
    ok = len(rows) == manifest.get("question_count", len(rows)) and agree > 0 and disagree == 0
    issues.append({"code": "QUESTIONS_CSV_SHA_MISMATCH_VERIFIED" if ok else "QUESTIONS_CSV_SHA_MISMATCH",
                   "run": str(run), "questions_file": str(found), "echo_agree": agree, "echo_disagree": disagree})
    return (rows if ok else {}), found


class Resolver:
    def __init__(self, questions):
        self.by_id = {q["question_id"]: q for q in questions if q.get("question_id")}
        self.by_text = defaultdict(list)
        for q in questions:
            self.by_text[normalize_text(q_text(q))].append(q)

    @staticmethod
    def region_ok(q: dict, region: str) -> bool:
        """题库 region 能对成两位市场代码时，必须和采集目录的市场一致；对不成（如 Global）不拦。"""
        code = q_region_code(q)
        return not (len(code) == 2 and code.isalpha()) or code == region.upper()

    def by_query(self, text: str, region: str):
        hits = self.by_text.get(normalize_text(text)) or []
        if not hits:
            return None, "TEXT_NOT_IN_BANK"
        same = [q for q in hits if self.region_ok(q, region)]
        if len(same) == 1:
            return same[0]["question_id"], None
        return None, "AMBIGUOUS_TEXT" if same else "REGION_NOT_IN_BANK"

    def resolve(self, echo: str, row: dict | None, stem: str, region: str):
        """返回 (question_id, 方法, 问题码)。"""
        if row and row.get("question_id") in self.by_id:
            q = self.by_id[row["question_id"]]
            if normalize_text(row.get("query")) == normalize_text(q_text(q)) and self.region_ok(q, region):
                if echo and normalize_text(echo) != normalize_text(q_text(q)):
                    return None, None, "ECHO_DIFFERS_FROM_CSV"
                return q["question_id"], "csv_question_id", None
        if echo:
            qid, code = self.by_query(echo, region)
            return (qid, "echo", None) if qid else (None, None, code)
        if row and row.get("query"):
            qid, code = self.by_query(row["query"], region)
            return (qid, "csv_query", None) if qid else (None, None, code)
        if stem in self.by_id and self.region_ok(self.by_id[stem], region):
            return stem, "filename", None
        return None, None, "NO_PROMPT_NO_CSV"
