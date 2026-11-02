#!/usr/bin/env python3
"""试跑答案 → 每道题的可改变性预判（selection-rules.md → 8. 试跑「可改变性」）。

脚本只做预判，档位由人复核后才算数。做法：

1. 读题库 bank.json 和一个或多个试跑采集目录（collect_answers.py 产出的
   ``scraper.<平台>/<市场>/<NNNN>.json``）。每个含 ``scraper.*`` 子目录的目录算一次试跑；
   给的是上层目录时，往下找出所有这样的目录（跳过 ``_collector``）。同平台正文与引用字段完全相同的
   回答只算一次（``html-report/collect`` 这类镜像目录会让次数翻倍）。
2. 文件归到题：NNNN 是采集用 CSV 的行号（manifest 里的 ``questions_file``）。CSV 采集后被改过
   （sha256 对不上）时，行数不变且本批所有回显题面都和 CSV 同行一致才继续用，否则这批不用 CSV。
   依次用：CSV 行的 ``question_id``（题面与题库一致时）→ 回答回显的题面 → CSV 行的题面 → 文件名就是题号。
   题面和当前题库对不上的文件不计：改过措辞的题重跑，不沿用旧读数。题库 region 能对成两位市场代码时，
   必须和采集目录的市场一致。
3. 取引用：只数正文引用，不数 search_result 这类检索候选。直接复用售前报告数据层
   ``geo-presales-report-builder/scripts/build_report_data.py`` 的 ``_citation_entries``：
   带 ``cited_count`` 的新格式按供应商次数计；字段里一条 ``cited_count`` 都没有的旧格式（10-10 及更早的
   ChatGPT、部分 AIO）回退数正文引用标记，Gemini / AIO 旧格式的伪拆分按同一套规则折叠；Alexa 数
   ``{ref cite_…}``。逐个回答判代数，不按日期。正文字段用同一模块的 ``ANSWER_FIELD``，
   失败页判定用 core 的 ``answer_validity``。
4. 每道题跨所有平台、所有试跑次数汇总被引次数，子域名归到注册域名（``blog.x.com`` 算 ``x.com``；
   ``hdb.gov.sg`` 这类 国家二级后缀下的站保留到机构一级），取被引次数前 20 的域名（并列按域名字母序）。
5. 分三类：官网（品牌官网、竞品官网、``--official`` 给的转化渠道页）、社区（``--community-domain``：
   品牌用自己账号发帖的社区、另买的信源服务）、其余都是难影响。
6. 两种占比都算：按被引次数、按域名个数。建议档用按被引次数的：官网+社区 ≥60% 高、≤40% 低、其余中
   （阈值暂定，可用 ``--high`` / ``--low`` 改）。前 20 里政府站加百科的被引次数超过 50%，
   打「需人工：政府/百科主导」，不给建议档；有回答但一条正文引用都没有，打「需人工：无正文引用」。
   前 20 合计被引不足 5 次的照样给档，但在 note 和依据里写「被引不足 5 次，档位不稳」。

域名参数的写法：不带 ``/`` 按域名比（含子域名），带 ``/`` 按「主机+路径前缀」比，例如
``reddit.com/r/yourbrand``、``amazon.com/stores/YourBrand``——这样品牌自己的版块算社区，Reddit 其余帖子仍是难影响。
品牌官网 = ``config.official_domain`` ∪ ``--official``；竞品官网 = 题库 config 里竞品条目的 domain /
official_domain ∪ ``--competitor-domain``。

输出（``--out`` 目录）：``changeability.csv``（每题一行）、``changeability.json``（每题完整明细、
分平台回答数与引用格式、归题问题清单）。默认只预览；``--write`` 才把建议档和一句依据写回题库的
``changeability`` / ``changeability_basis``，打了需人工标记的题不写；题库里已有高/中/低的题默认不覆盖，
要覆盖加 ``--overwrite``。写回前把原题库复制一份到 ``--out/bank.before-write.json``。

用法：
    python3 -I changeability_domains.py --bank <bank.json> --collect <试跑目录> [<试跑目录> …] \\
        --out <输出目录> [--official brand.cn] [--competitor-domain rival.com …] \\
        [--community-domain reddit.com/r/yourbrand …] [--write [--overwrite]]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

SKILLS = Path(__file__).resolve().parents[2]
BUILDER = SKILLS / "geo-presales-report-builder" / "scripts"
if str(BUILDER) not in sys.path:
    sys.path.insert(0, str(BUILDER))

import build_report_data as brd  # noqa: E402  （同时把 core 加进 sys.path）
from geo_presales_core.crawler import answer_validity  # noqa: E402
from geo_presales_core.util import normalize_host, normalize_text, registrable_domain  # noqa: E402

TOP_N = 20
DEFAULT_HIGH = 0.60
DEFAULT_LOW = 0.40
GOV_WIKI_LIMIT = 0.50
FEW_CITATIONS = 5  # 前 20 域名合计被引少于这个数，照样给建议档，但在 note 里提示档位不稳
PENDING = {"", "待试跑", None}

# 国家代码顶级域下的通用二级标签：x.co.th、x.gov.sg 的注册域名要保留三段。
# core 的 registrable_domain 只认一张近似的固定表，缺东南亚、非洲等市场。
GENERIC_SLD = {"co", "com", "net", "org", "gov", "go", "ac", "edu", "or", "ne", "gob", "gouv",
               "govt", "gv", "mil", "nic", "ltd", "plc", "sch", "in", "nom", "info", "biz"}
GOV_SLD = {"gov", "go", "gob", "gouv", "govt", "gv", "mil"}
GOV_EXTRA = {"europa.eu", "gc.ca", "canada.ca", "gov", "mil"}
WIKI = {"wikipedia.org", "wikimedia.org", "wikidata.org", "wiktionary.org", "wikivoyage.org",
        "britannica.com", "namu.wiki", "baike.com"}

# 题库 region 写国名时对到采集目录的市场代码，只在同一题面出现在多个市场时用来分题。
REGION_CODE = {"singapore": "SG", "malaysia": "MY", "thailand": "TH", "nigeria": "NG", "kenya": "KE",
               "united states": "US", "usa": "US", "korea": "KR", "south korea": "KR", "taiwan": "TW",
               "hong kong": "HK", "philippines": "PH", "indonesia": "ID", "vietnam": "VN",
               "united kingdom": "GB", "uk": "GB", "japan": "JP", "india": "IN", "australia": "AU",
               "canada": "CA", "germany": "DE", "france": "FR", "ghana": "GH", "egypt": "EG",
               "saudi arabia": "SA", "united arab emirates": "AE", "uae": "AE", "mexico": "MX",
               "brazil": "BR", "pakistan": "PK", "bangladesh": "BD"}


# ------------------------------------------------------------------ 域名

def reg_domain(host: str) -> str:
    host = normalize_host(host)
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in GENERIC_SLD:
        return ".".join(parts[-3:])
    return registrable_domain(host)


def is_gov(domain: str) -> bool:
    parts = domain.split(".")
    if parts[-1] in {"gov", "mil"} or domain in GOV_EXTRA or any(domain.endswith("." + g) for g in GOV_EXTRA):
        return True
    return len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in GOV_SLD or \
        (len(parts) == 2 and len(parts[-1]) == 2 and parts[0] in GOV_SLD)


def is_wiki(domain: str) -> bool:
    return domain in WIKI


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


# ------------------------------------------------------------------ 题库

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


# ------------------------------------------------------------------ 采集目录

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


# ------------------------------------------------------------------ 主流程

def classify(host: str, url: str, official: Matcher, competitor: Matcher, community: Matcher):
    if official.match(host, url):
        return "官网", "品牌官网"
    if competitor.match(host, url):
        return "官网", "竞品官网"
    if community.match(host, url):
        return "社区", "品牌社区"
    return "难影响", ""


def collect(args, questions, official, competitor, community):
    resolver = Resolver(questions)
    runs = find_runs(args.collect)
    issues: list[dict] = []
    seen_hashes: dict[str, str] = {}
    per_q = {q["question_id"]: {"answers": Counter(), "valid": Counter(), "format": Counter(),
                                "domains": Counter(), "unresolved": 0, "files": []}
             for q in questions}
    for run in runs:
        rows, _csv = run_questions_csv(run, issues)
        for pdir in sorted(run.glob("scraper.*")):
            platform = pdir.name.split(".", 1)[1]
            if platform not in brd.ANSWER_FIELD:
                issues.append({"code": "UNKNOWN_PLATFORM", "dir": str(pdir)})
                continue
            for rdir in sorted(p for p in pdir.iterdir() if p.is_dir()):
                region = rdir.name
                for path in sorted(rdir.glob("*.json")):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        issues.append({"code": "BAD_JSON", "file": str(path)})
                        continue
                    task = payload.get("task_result") or {}
                    # 去重按回答内容，不按文件字节：build_baseline_html 的 html-report/collect 是补了题面的
                    # 镜像副本，字节不同、回答相同。空正文（AIO 未触发）不参与去重，它本来就不计引用。
                    body = str(task.get(brd.ANSWER_FIELD[platform]) or "")
                    digest = None
                    if body.strip():
                        digest = hashlib.sha256(json.dumps(
                            [platform, body, task.get(brd.CITATION_FIELD.get(platform))],
                            ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                        if digest in seen_hashes:
                            issues.append({"code": "DUPLICATE_ANSWER", "file": str(path),
                                           "same_as": seen_hashes[digest]})
                            continue
                    echo = str(task.get("prompt") or task.get("user_query") or task.get("user_text") or "").strip()
                    qid, method, code = resolver.resolve(echo, rows.get(path.stem), path.stem, region)
                    if not qid:
                        issues.append({"code": code, "file": str(path),
                                       "prompt": (echo or (rows.get(path.stem) or {}).get("query") or "")[:100]})
                        continue
                    if digest:
                        seen_hashes[digest] = str(path)  # 归上题才登记，免得没归上的原件挡掉能归上的镜像
                    if method == "filename":
                        issues.append({"code": "FILENAME_FALLBACK", "file": str(path), "question_id": qid})
                    slot = per_q[qid]
                    slot["answers"][platform] += 1
                    status = str(payload.get("status") or "success").lower()
                    text = body
                    valid, _ = answer_validity(text)
                    if status != "success" or not valid:
                        continue
                    slot["valid"][platform] += 1
                    slot["files"].append(str(path))
                    if platform == "alexa":
                        slot["format"]["alexa_ref"] += 1
                    elif brd._cited_count_entries(platform, task) is not None:
                        slot["format"]["cited_count"] += 1
                    else:
                        slot["format"]["body_marker"] += 1
                    for entry in brd._citation_entries(platform, task, text):
                        host = entry.get("domain_hint") or ""
                        url = entry.get("raw_url") or ""
                        if not host:
                            slot["unresolved"] += 1
                            continue
                        cls, sub = classify(host, url, official, competitor, community)
                        dom = reg_domain(host)
                        slot["domains"][(dom, cls, sub)] += 1
    return runs, per_q, issues


def summarize(q: dict, slot: dict, high: float, low: float) -> dict:
    ranked = sorted(slot["domains"].items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
    top = ranked[:TOP_N]
    total_all = sum(slot["domains"].values())
    top_total = sum(n for _, n in top)
    oc_cites = sum(n for (d, cls, _), n in top if cls in ("官网", "社区"))
    oc_domains = sum(1 for (d, cls, _), n in top if cls in ("官网", "社区"))
    gw_cites = sum(n for (d, cls, _), n in top if cls == "难影响" and (is_gov(d) or is_wiki(d)))
    share_c = oc_cites / top_total if top_total else None
    share_d = oc_domains / len(top) if top else None
    gw_share = gw_cites / top_total if top_total else None
    valid = sum(slot["valid"].values())
    flag, tier = "", None
    if not valid:
        flag = "无试跑答案"
    elif not top_total:
        flag = "需人工：无正文引用"
    elif gw_share > GOV_WIKI_LIMIT:
        flag = "需人工：政府/百科主导"
    else:
        tier = "高" if share_c >= high else "低" if share_c <= low else "中"
    domains = []
    for rank, ((d, cls, sub), n) in enumerate(top, 1):
        tag = "政府" if is_gov(d) else "百科" if is_wiki(d) else ""
        domains.append({"rank": rank, "domain": d, "class": cls, "detail": sub or tag, "citations": n})
    return {
        "question_id": q["question_id"], "user_question": q_text(q), "prompt_type": q.get("prompt_type"),
        "region": q.get("region"),
        "answers_valid": valid, "answers_by_platform": dict(slot["valid"]),
        "citation_format": dict(slot["format"]),
        "citations_all": total_all, "citations_unresolved": slot["unresolved"],
        "domains_all": len(slot["domains"]), "top20_citations": top_total,
        "official_community_citations": oc_cites,
        "share_by_citations": share_c, "share_by_domains": share_d, "gov_wiki_share": gw_share,
        "suggested": tier, "flag": flag,
        "note": f"被引不足 {FEW_CITATIONS} 次，档位不稳" if tier and top_total < FEW_CITATIONS else "",
        "current": q.get("changeability"), "current_basis": q.get("changeability_basis"),
        "top20": domains,
        "answer_files": slot["files"],
    }


def label(item: dict) -> str:
    return item["domain"] + ("(品牌账号)" if item["class"] == "社区" else "")


def basis_sentence(r: dict) -> str:
    oc = [i for i in r["top20"] if i["class"] in ("官网", "社区")]
    hard = [i for i in r["top20"] if i["class"] == "难影响"]
    head = (f"官网+社区 {round(r['share_by_citations'] * 100)}%（被引 {r['official_community_citations']}/"
            f"{r['top20_citations']}，前 {len(r['top20'])} 域名，{r['answers_valid']} 次回答）")
    parts = [head + "：" + ("、".join(f"{label(i)} {i['citations']}" for i in oc[:4]) or "无")]
    if hard:
        parts.append("难影响：" + "、".join(f"{i['domain']} {i['citations']}" for i in hard[:3])
                     + ("…" if len(hard) > 3 else ""))
    if r.get("gov_wiki_share"):
        parts.append(f"其中政府/百科 {round(r['gov_wiki_share'] * 100)}%")
    if r.get("note"):
        parts.append(r["note"])
    return "；".join(parts) + "（脚本预判）"


def pct(v):
    return "" if v is None else f"{v * 100:.0f}%"


def write_outputs(out: Path, results: list, meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    (out / "changeability.json").write_text(
        json.dumps({"meta": meta, "questions": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    headers = ["question_id", "prompt_type", "region", "answers_valid", "answers_by_platform", "citation_format",
               "citations_all", "citations_unresolved", "top20_citations", "official_community_citations",
               "share_by_citations", "share_by_domains", "gov_wiki_share", "suggested", "flag", "note",
               "current", "basis_preview", "top20_domains", "user_question"]
    with (out / "changeability.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=headers)
        w.writeheader()
        for r in results:
            w.writerow({
                **{k: r.get(k) for k in headers if k in r},
                "answers_by_platform": " ".join(f"{k}={v}" for k, v in sorted(r["answers_by_platform"].items())),
                "citation_format": " ".join(f"{k}={v}" for k, v in sorted(r["citation_format"].items())),
                "share_by_citations": pct(r["share_by_citations"]), "share_by_domains": pct(r["share_by_domains"]),
                "gov_wiki_share": pct(r["gov_wiki_share"]), "suggested": r["suggested"] or "",
                "basis_preview": basis_sentence(r) if r["suggested"] else "",
                "top20_domains": "; ".join(
                    f"{i['domain']}[{i['class']}{'/' + i['detail'] if i['detail'] else ''}] {i['citations']}"
                    for i in r["top20"]),
            })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bank", type=Path, required=True, help="题库 bank.json")
    ap.add_argument("--collect", type=Path, nargs="+", required=True, help="试跑采集目录（可多个，或其上层目录）")
    ap.add_argument("--out", type=Path, required=True, help="输出目录")
    ap.add_argument("--official", nargs="*", default=[], help="品牌官网 / 转化渠道页（与 config.official_domain 合并）")
    ap.add_argument("--competitor-domain", nargs="*", default=[], help="竞品官网（与题库 config 竞品域名合并）")
    ap.add_argument("--community-domain", nargs="*", default=[], help="品牌发帖的社区、另买的信源服务")
    ap.add_argument("--high", type=float, default=DEFAULT_HIGH, help="官网+社区被引占比 ≥ 此值记高（默认 0.60）")
    ap.add_argument("--low", type=float, default=DEFAULT_LOW, help="官网+社区被引占比 ≤ 此值记低（默认 0.40）")
    ap.add_argument("--write", action="store_true", help="把建议档和依据写回 bank.json")
    ap.add_argument("--overwrite", action="store_true", help="配合 --write：覆盖题库里已有的高/中/低")
    args = ap.parse_args(argv)

    raw, bank, questions = load_bank(args.bank)
    config = bank.get("config") or {}
    official_values = [config.get("official_domain")] + list(args.official)
    if not any(official_values):
        raise SystemExit("题库 config.official_domain 为空，用 --official 给品牌官网域名")
    official = Matcher(official_values)
    competitor = Matcher(competitor_domains(config) + list(args.competitor_domain))
    community = Matcher(args.community_domain)

    runs, per_q, issues = collect(args, questions, official, competitor, community)
    results = [summarize(q, per_q[q["question_id"]], args.high, args.low) for q in questions]
    meta = {
        "bank": str(args.bank), "runs": [str(r) for r in runs],
        "official": official.describe(), "competitor": competitor.describe(), "community": community.describe(),
        "thresholds": {"high_ge": args.high, "low_le": args.low, "gov_wiki_gt": GOV_WIKI_LIMIT, "top_n": TOP_N},
        "issues": issues,
    }
    write_outputs(args.out, results, meta)

    print(f"试跑目录 {len(runs)} 个；官网 {', '.join(official.describe())}；竞品 {', '.join(competitor.describe()) or '无'}；"
          f"社区 {', '.join(community.describe()) or '无'}")
    print(f"阈值：官网+社区被引占比 ≥{args.high:.0%} 高、≤{args.low:.0%} 低；政府/百科 >{GOV_WIKI_LIMIT:.0%} 需人工")
    codes = Counter(i["code"] for i in issues)
    if codes:
        print("归题问题：" + "、".join(f"{k} {v}" for k, v in codes.most_common()))
    print()
    print(f"{'题号':<16}{'回答':>4}{'被引':>6}{'按次':>6}{'按域名':>7}{'政/百':>6}  建议  现值  标记 / 前 5 域名")
    for r in results:
        top5 = "、".join(f"{label(i)}{'*' if i['class'] == '官网' else ''} {i['citations']}" for i in r["top20"][:5])
        print(f"{r['question_id']:<16}{r['answers_valid']:>4}{r['top20_citations']:>6}{pct(r['share_by_citations']):>6}"
              f"{pct(r['share_by_domains']):>7}{pct(r['gov_wiki_share']):>6}  {r['suggested'] or '—':<4}"
              f"{str(r['current'] or '—'):<5} {r['flag'] + ' ' if r['flag'] else ''}"
              f"{'〔' + r['note'] + '〕' if r['note'] else ''}{top5}")
    print(f"\n（* = 官网；输出：{args.out / 'changeability.csv'}、{args.out / 'changeability.json'}）")

    if not args.write:
        print("预览模式，未改题库；加 --write 写回。")
        return 0

    backup = args.out / "bank.before-write.json"
    shutil.copy2(args.bank, backup)
    written, skipped = [], []
    by_id = {r["question_id"]: r for r in results}
    for q in questions:
        r = by_id[q["question_id"]]
        if not r["suggested"]:
            skipped.append((q["question_id"], r["flag"] or "无建议档"))
            continue
        if q.get("changeability") not in PENDING and not args.overwrite:
            skipped.append((q["question_id"], f"已有「{q.get('changeability')}」，未加 --overwrite"))
            continue
        q["changeability"] = r["suggested"]
        q["changeability_basis"] = basis_sentence(r)
        written.append(q["question_id"])
    indent = 2
    lines = raw.splitlines()
    if len(lines) > 1:
        stripped = lines[1].lstrip(" ")
        indent = (len(lines[1]) - len(stripped)) or None
    tail = "\n" if raw.endswith("\n") else ""
    args.bank.write_text(json.dumps(bank, ensure_ascii=False, indent=indent) + tail, encoding="utf-8")
    print(f"已写回 {len(written)} 题：{'、'.join(written) or '无'}；原题库备份 {backup}")
    for qid, why in skipped:
        print(f"  未写 {qid}：{why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
