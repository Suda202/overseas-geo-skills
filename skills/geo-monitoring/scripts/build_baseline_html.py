#!/usr/bin/env python3
"""候选基线 → 单文件 HTML 基线报告（Suda 2026-10-21：基线结果不再写进对客 Base，改出 HTML）。

复用 geo-presales-report-builder 的数据层与渲染层（build_report_data.py / verify_report_data.py /
render_report.py），只做售后口径适配，不改那个 skill 的源码：

1. 合成采集目录：N 轮采集放进同一个「平台 × 意图」目录。售前报告的「地区」一层在这里放意图，页面上的
   地区筛选就成了提示词类型筛选（全部类型 / 发现 / 信息 / …），与平台、主题两行筛选任意组合。每题 N 个文件，
   文件里补上题面（AI Overviews 不回传题面，build_report_data 靠题面把文件归到题）。
2. 选词阶段所有题都计入可见度（Suda 2026-10-20）：题库 CSV 统一标 discovery，真实意图回写到页面数据。
3. 售后口径：品牌识别前去掉裸 URL；指定别名区分大小写（ERA、SRX 这类缩写撞普通词）；可选按机构拆
   gov.sg 这类二级后缀；「竞品网站」= 配置竞品与开放品牌官网 + config 里列的同类平台域名（不限配置竞品）。
   声量份额由 core 按回答计（一个回答一个品牌只算一次）。
4. 页面：顶部多一个「引用率」指标（= 官网引用率，售前页面不展示），03 引用模块同时给引用份额与引用率；
   「全部类型」时 KPI 引用份额/引用率与 03 引用模块只统计发现＋品类认知题，点名题合计在 03 单列一行
   （Profound ch4，Suda 2026-10-22）；选中单一类型时按该类型统计，逐题读数各算各的。
   问题明细逐题给本品 提及率 / 提及率排名 / 声量份额 / 平均提及位置 / 引用份额 / 引用率，展开「与竞品对比」看竞品的前四项；主题行取主题
   切片的合计值，不对逐题读数取平均。平台筛选即分平台读数。
5. 校验：verify_report_data 独立复算全部切片，不一致就不渲染。

售前模板只容 3 个配置竞品：config.competitors 填答案层前三，其余竞品放 open_brands，
compare_brands 决定逐题对比显示哪些。情感与中文译文不在本脚本内，页面情感模块显示「尚未接入」。

用法（在客户的基线目录运行，config 里的相对路径相对 config 所在目录）：
    python3 -I <项目根>/.agents/skills/geo-monitoring/scripts/build_baseline_html.py --config baseline-html.json
流程、config 字段与页面规则见 references/baseline-report.md。
"""
from __future__ import annotations

import argparse
import csv
import html as html_mod
import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SK = ROOT / ".agents" / "skills" / "geo-presales-report-builder" / "scripts"
CORE = ROOT / ".agents" / "skills" / "geo-presales-report-editor" / "scripts"
for p in (str(SK), str(CORE)):
    if p not in sys.path:
        sys.path.insert(0, p)

INTENT_ZH = {"discovery": "发现", "information": "信息", "evaluation": "评价", "sentiment": "评价",
             "verification": "验证", "validation": "验证", "competitor": "竞品", "accuracy": "准确性",
             "category awareness": "品类认知", "category_awareness": "品类认知", "market_perception": "品类认知"}
INTENT_ORDER = ["发现", "信息", "评价", "验证", "竞品", "准确性", "品类认知"]
URL = re.compile(r"https?://\S+|www\.\S+")
# 引用聚合只统计题面不点名品牌的类型（Profound ch4 "scope your citation analysis to discovery prompts"，
# Suda 2026-10-22）：点名题会把被点名品牌的官网拉进引用、抬高份额。合成目录的 region 层就是提示词类型，
# 所以「全部类型」切片的引用口径 = 只合池这两类 region；单类型切片仍按该类型自己的回答算，逐题读数不受影响。
CITATION_SCOPE_TYPES = ("发现", "品类认知")
CITATION_KPI_FIELDS = ("official_share", "official_citation_rate", "official_citation_counts")


def citation_regions(regions) -> list:
    """「全部类型」引用聚合合池的 region（= 提示词类型）。build 与 verify 两侧共用这一个判断。"""
    return [r for r in regions if r in CITATION_SCOPE_TYPES]


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    cfg["_config_dir"] = base
    for key in ("questions_csv", "bank_json", "out_dir"):
        cfg[key] = (base / cfg[key]).resolve()
    cfg["runs"] = [(base / r).resolve() for r in cfg["runs"]]
    if len(cfg["competitors"]) != 3:
        raise SystemExit("competitors 必须正好 3 个（售前模板的配置竞品位数）；其余竞品放 open_brands")
    return cfg


def install_patches(cfg: dict):
    """口径补丁。必须在导入 build_report_data 之前打到 util 上，deterministic 导入时才绑定到补丁版。"""
    import geo_presales_core.util as core_util
    core_util.COMMON_MULTI_LABEL_SUFFIXES |= set(cfg.get("multi_label_suffixes") or [])
    orig_spans = core_util.find_alias_spans
    cs = set(cfg.get("case_sensitive_aliases") or [])

    def find_alias_spans(text, aliases):
        # core 按 casefold 去重同位置的别名，留下哪一个随集合顺序变（lyf / Lyf / LYF），
        # 所以判「原文写法是不是列出的某个大小写」，不判与留下的那个别名逐字相等
        return [s for s in orig_spans(text, aliases) if s["alias"] not in cs or s["matched_text"] in cs]

    core_util.find_alias_spans = find_alias_spans
    import build_report_data as brd
    import geo_presales_core.deterministic as det
    det.find_alias_spans = find_alias_spans
    orig_blank = brd.de_cite.blank_merchant_columns
    brd.de_cite.blank_merchant_columns = lambda text: URL.sub(" ", orig_blank(text))
    brd.KNOWN_PLATFORM_LABELS.update(cfg.get("platform_labels") or {})
    sites = set(cfg.get("competitor_site_domains") or [])
    orig_official = det._classify_official

    def classify_official(host, objects):
        found = orig_official(host, objects)
        if found[0]:
            return found
        return ("competitor_official", None) if core_util.registrable_domain(host) in sites else (None, None)

    det._classify_official = classify_official

    # 03 引用模块：每个「引用份额」旁边配「引用率」= 至少引用一次该来源的回答 ÷ 有效回答（按回答计）。
    # 挂在 build_sources 上，用它同一批回答与同一套 canonical / 域名 / 类别，口径与份额一致（Suda 2026-10-21）
    orig_sources = brd.build_sources

    def build_sources(metrics, answers, source_limit=brd.DEFAULT_SOURCE_LIMIT):
        out = orig_sources(metrics, answers, source_limit)
        # 与上游 build_sources 同一个回答池；「全部类型」时传进来的 answers 已由 build_slice 补丁收窄到
        # citation_regions（发现＋品类认知），这里不再另判类型
        pool = [a for a in answers if brd.is_valid(a) and brd.is_discovery(a)]
        dom, url, typ = Counter(), Counter(), Counter()
        for a in pool:
            ds, us, ts = set(), set(), set()
            for c in a["citations"]:
                canonical = c.get("canonical_url")
                if not canonical:
                    continue
                us.add(canonical)
                ds.add(c.get("registrable_domain") or c.get("host") or "")
                ts.add(brd.SOURCE_BUCKET.get(c.get("source_type") or "other", ("其他", ""))[0])
            dom.update(ds); url.update(us); typ.update(ts)
        n = len(pool)
        rate = lambda k: brd.fmt_pct(k / n) if n else "—"
        out["rates"] = {"types": {r[0]: rate(typ[r[0]]) for r in out.get("types") or []},
                        "domains": {r[0]: rate(dom[r[0]]) for r in out.get("domains") or []},
                        "pages": {r[0]: rate(url[r[0]]) for r in (out.get("pages") or []) + (out.get("official_pages") or [])}}
        return out

    brd.build_sources = build_sources

    # 「全部类型」切片（region == ""）的引用聚合只合池发现＋品类认知：KPI 引用份额/引用率、03 引用模块
    # （sources 整块）、品牌 citation_share（供平台矩阵）换成只用这两类 region 重算的值；提及/声量/排名/
    # 逐题 records 仍取全部类型。另算一份点名题合计挂在 sources.named_scope，03 模块单列一行。
    orig_slice = brd.build_slice

    def build_slice(region, platform, topic, config, bank, index, per_platform, regions,
                    source_limit=brd.DEFAULT_SOURCE_LIMIT):
        full = orig_slice(region, platform, topic, config, bank, index, per_platform, regions, source_limit)
        if region:
            return full
        scoped = citation_regions(regions)
        cite = orig_slice("", platform, topic, config, bank, index, per_platform, scoped, source_limit)
        for f in CITATION_KPI_FIELDS:
            full["kpis"][f] = cite["kpis"][f]
        full["sources"] = cite["sources"]
        for oid, row in full["_rows"].items():
            row["citation_share"] = cite["_rows"][oid]["citation_share"]
        named = [r for r in regions if r not in scoped]
        if named:
            nk = orig_slice("", platform, topic, config, bank, index, per_platform, named, source_limit)["kpis"]
            full["sources"]["named_scope"] = {"types": named, **{f: nk[f] for f in CITATION_KPI_FIELDS}}
        full["sources"]["citation_scope_types"] = scoped
        return full

    brd.build_slice = build_slice
    return brd, core_util, find_alias_spans


def patch_verify(vr):
    """verify 独立复算与 build 同口径：「全部类型」切片的引用字段改用只合池发现＋品类认知 region 的复算，
    点名题合计（sources.named_scope）用只合池点名类型的复算对账。复算本身仍是 verify 自己的实现。"""
    orig = vr.Recomputer._recompute

    def scoped(self, markets, platform, topic):
        self.slice_regions = lambda region: list(markets)
        try:
            return orig(self, "", platform, topic)
        finally:
            del self.slice_regions

    def _recompute(self, region, platform, topic):
        full = orig(self, region, platform, topic)
        if region:
            return full
        cite = scoped(self, citation_regions(self.regions), platform, topic)
        for f in CITATION_KPI_FIELDS + ("citation_units",):
            full[f] = cite[f]
        for name, st in full["object_stats"].items():
            st["citation_share"] = cite["object_stats"][name]["citation_share"]
        return full

    vr.Recomputer._recompute = _recompute
    orig_check = vr._check_slice

    def _check_slice(key, slc, recomputer, region, platform, topic, meta):
        out = orig_check(key, slc, recomputer, region, platform, topic, meta)
        if region:
            return out
        named = [r for r in recomputer.regions if r not in citation_regions(recomputer.regions)]
        got = (slc.get("sources") or {}).get("named_scope")
        if bool(named) != bool(got):
            out.append(f"{key}: sources.named_scope 与点名类型 {named} 不符")
        elif named:
            exp = scoped(recomputer, named, platform, topic)
            for f in ("official_share", "official_citation_rate"):
                if not vr._close(got.get(f), exp[f]):
                    out.append(f"{key}: sources.named_scope.{f} {got.get(f)!r} != 复算 {exp[f]!r}")
            if got.get("official_citation_counts") != exp["official_citation_counts"]:
                out.append(f"{key}: sources.named_scope.official_citation_counts "
                           f"{got.get('official_citation_counts')!r} != 复算 {exp['official_citation_counts']!r}")
        return out

    vr._check_slice = _check_slice


def intent_of(cfg: dict) -> dict:
    bank = json.loads(cfg["bank_json"].read_text(encoding="utf-8"))
    out = {}
    for q in bank["questions"]:
        raw = str(q.get("prompt_type") or q.get("intent") or q.get("diagnosis_intent") or "").strip().casefold()
        if raw not in INTENT_ZH:
            raise SystemExit(f"{q['question_id']} 提示词类型 {raw!r} 不认识")
        out[q["question_id"]] = INTENT_ZH[raw]
    return out


def prepare_inputs(cfg, questions, intent, platforms):
    out, collect = cfg["out_dir"], cfg["out_dir"] / "collect"
    if collect.exists():
        shutil.rmtree(collect)
    n = 0
    for p in platforms:
        for k, run in enumerate(cfg["runs"], 1):
            for i, q in enumerate(questions, 1):
                src = run / f"scraper.{p}" / cfg["region"] / f"{i:04d}.json"
                if not src.exists():
                    continue
                payload = json.loads(src.read_text(encoding="utf-8"))
                payload.setdefault("task_result", {})["prompt"] = q["query"]
                # <题号>-r<轮次>.json：情感抽取（sentiment_sentences）与接入（attach_sentiment）原生认这种重复采样命名
                dst = collect / f"scraper.{p}" / intent[q["question_id"]] / f"{i:04d}-r{k:02d}.json"
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps(payload, ensure_ascii=False))
                n += 1
    topics = cfg.get("topic_labels") or {}
    with open(out / "questions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["query", "question_zh", "topic", "diagnosis_intent", "tags", "question_types"])
        w.writeheader()
        for q in questions:
            w.writerow({"query": q["query"], "question_zh": q.get("question_zh", ""),
                        "topic": topics.get(q["topic"], q["topic"]),
                        "diagnosis_intent": "discovery", "tags": "", "question_types": "visibility,sentiment"})
    t, c = cfg["target"], cfg["competitors"]
    case = {"品牌名称": t["name"], "官方域名": t["official_domains"][0], "品类": cfg.get("category", "")}
    for i, comp in enumerate(c, 1):
        case[f"竞品 {i}"], case[f"竞品 {i} 官网域名"] = comp["name"], comp["official_domains"][0]
    (out / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=1))
    brands = [dict(t, type="target")] + [dict(x, type="competitor") for x in c] + list(cfg.get("open_brands") or [])
    (out / "lexicon.json").write_text(json.dumps({"brands": brands}, ensure_ascii=False, indent=1))
    cache = {d: kind for kind, ds in (cfg.get("domain_categories") or {}).items() for d in ds}
    (out / "domain-categories.json").write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    print("合成采集文件", n)


def official_rates(cfg, brd, core_util, questions, platforms):
    """逐题 × 平台的官网引用回答数 / 有效回答数（按回答计，一条回答引用多次只算一次）。"""
    official = {d.casefold() for d in cfg["target"]["official_domains"]}
    brand_domains = {b["name"]: [d.casefold() for d in b.get("official_domains") or []]
                     for b in [cfg["target"], *cfg["competitors"], *(cfg.get("open_brands") or [])]}
    stats = {"_cites": {}}
    for p in platforms:
        for run in cfg["runs"]:
            for i, q in enumerate(questions, 1):
                f = run / f"scraper.{p}" / cfg["region"] / f"{i:04d}.json"
                if not f.exists():
                    continue
                t = json.loads(f.read_text(encoding="utf-8")).get("task_result") or {}
                body = str(t.get(brd.ANSWER_FIELD[p]) or "")
                if not brd.answer_validity(body)[0]:
                    continue
                doms = set()
                hosts = []
                for c in brd._citation_entries(p, t, body):
                    host = core_util.normalize_host(c.get("raw_url") or "")
                    if host:
                        doms.add(core_util.registrable_domain(host))
                        hosts.append(host)
                for key in ((q["question_id"], p), (q["question_id"], None)):
                    hit, n = stats.get(key, (0, 0))
                    stats[key] = (hit + bool(doms & official), n + 1)
                    # 品牌对比的引用份额：指向该品牌官网的引用次数 ÷ 全部引用次数（不去重）
                    bc = stats["_cites"].setdefault(key, {"_total": 0})
                    bc["_total"] += len(hosts)
                    for name, ds in brand_domains.items():
                        k = sum(1 for h in hosts if any(core_util.domain_matches(h, d) for d in ds))
                        if k:
                            bc[name] = bc.get(name, 0) + k
    return stats


def attach_sentiment(cfg, data_path: Path):
    """接入情感判读（Claim 层）：04 情感模块与回答详情的品牌情感。

    config.sentiment = {"units", "claims", "metrics"}，由 geo-presales-sentiment-judge 产出：
    extract 用本脚本合成的 out_dir/collect 与 out_dir/questions.csv（单元的 region 即意图、文件名带轮次），
    抽 Claim、两趟聚类、claims-assemble、claims-metrics。缺省则情感模块显示「尚未接入」。
    必须在 patch_report_data 之前跑：attach 按「意图|平台|0001-r01」找每次运行的明细。
    """
    sent = cfg.get("sentiment") or {}
    if not sent or not all((cfg["_config_dir"] / sent.get(k, "_missing_")).exists() for k in ("units", "claims", "metrics")):
        print("情感结果不全（需要 units / claims / metrics），情感模块保持「尚未接入」")
        return
    base = cfg["_config_dir"]
    paths = {k: (base / v).resolve() for k, v in sent.items()}
    data = json.loads(data_path.read_text(encoding="utf-8"))
    brands = [str(r[0]).replace("★", "").strip() for r in data["slices"]["||"]["competition"]["mention"]]
    import attach_sentiment as at
    for label in (cfg.get("platform_labels") or {}).items():
        at.PLATFORM_INTERNAL[label[1]] = label[0]
    argv = sys.argv
    sys.argv = ["attach_sentiment", "--report", str(data_path), "--units", str(paths["units"]),
                "--labels-dir", str(paths["units"].parent), "--brands", ",".join(brands),
                "--target", cfg["target"]["name"], "--claims", str(paths["claims"]),
                "--expected-metrics", str(paths["metrics"]), "--out", str(data_path)]
    try:
        rc = at.main()
    finally:
        sys.argv = argv
    if rc:
        raise SystemExit(f"attach_sentiment 退出码 {rc}")


def brand_sentiment(cfg):
    """(题号, 平台目录名或 None, 品牌) → (正向 Claim 信号, 负向 Claim 信号)，同回答同品牌同 claim 只计一次。"""
    sent = cfg.get("sentiment") or {}
    if not sent.get("claims"):
        return {}
    rows = json.loads((cfg["_config_dir"] / sent["claims"]).read_text(encoding="utf-8"))
    rows = rows.get("claims") if isinstance(rows, dict) else rows
    out, seen = {}, set()
    for c in rows:
        num = str(c.get("question_id")).zfill(4)
        key = (c.get("region"), c.get("platform"), num, c.get("repeat"), c.get("brand"), c.get("claim"))
        if key in seen:
            continue
        seen.add(key)
        neg = c.get("sentiment") in ("negative", "负向")
        for k in ((num, c.get("platform"), c["brand"]), (num, None, c["brand"])):
            pos_n, neg_n = out.get(k, (0, 0))
            out[k] = (pos_n + (not neg), neg_n + neg)
    return out


def patch_report_data(path: Path, cfg, questions, intent, crate_stats):
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data["meta"]
    meta["regions"] = [r for r in INTENT_ORDER if r in meta["regions"]]
    meta["intents"] = [i for i in INTENT_ORDER if i in set(intent.values())]
    for q, row in zip(meta["questions"], questions):
        q["intent"] = intent[row["question_id"]]
        q["question_id"] = row["question_id"]
    label2p = {lab: p for p, lab in cfg["_platform_pairs"]}
    show = [cfg["target"]["name"]] + list(cfg.get("compare_brands") or [c["name"] for c in cfg["competitors"]])
    domain_of = {b["name"]: (b.get("official_domains") or [""])[0]
                 for b in [cfg["target"], *cfg["competitors"], *(cfg.get("open_brands") or [])]}
    sent = brand_sentiment(cfg)
    qid_of = {i: row["question_id"] for i, row in enumerate(questions, 1)}
    pct = lambda x: "—" if x is None else f"{x * 100:.1f}%"
    for key, s in data["slices"].items():
        plat = label2p.get(key.split("|")[1])
        for r in s.get("records", []):
            qid = qid_of[r["qid"]]
            r["intent"] = intent[qid]
            brands = r.get("brands") or []
            counts = {b["name"]: b.get("mention_count") or 0 for b in brands}
            rank = {n: 1 + sum(1 for c2 in counts.values() if c2 > c) for n, c in counts.items() if c}
            rows = []
            for name in show:
                b = next((x for x in brands if x["name"] == name), None)
                if b:
                    rows.append([name, pct(b.get("mention_rate")), str(rank.get(name, "—")), pct(b.get("share_of_voice")),
                                 "—" if b.get("average_rank") is None else f"{b['average_rank']:.1f}", name == show[0]])
            top = max(brands, key=lambda x: (x.get("mention_count") or 0, -(x.get("average_rank") or 99)), default=None)
            if top and (top.get("mention_count") or 0) and top["name"] not in show:
                rows.append([top["name"], pct(top.get("mention_rate")), str(rank.get(top["name"], "—")),
                             pct(top.get("share_of_voice")),
                             "—" if top.get("average_rank") is None else f"{top['average_rank']:.1f}", False])
            r["top"] = [top["name"], pct(top.get("mention_rate"))] if top and (top.get("mention_count") or 0) else None
            bc = crate_stats["_cites"].get((qid, plat)) or {"_total": 0}
            num = f"{r['qid']:04d}"
            for row in rows:
                tot = bc["_total"]
                row.append(pct(bc.get(row[0], 0) / tot) if tot else "无引用")
                pos, neg = sent.get((num, plat, row[0]), (0, 0))
                row.append(pct(pos / (pos + neg)) if pos + neg else "—")
                row.append(domain_of.get(row[0], ""))
            hit, n = crate_stats.get((qid, plat), (0, 0))
            hb = rows[0] if rows and rows[0][0] == show[0] else [show[0], "—", "—", "—", "—", True]
            # 对比表按提及回答数从高到低；没被提到的排在最后（本品没被提到也一样，免得排第一行像是领先）
            rows.sort(key=lambda x: (x[2] == "—", int(x[2]) if x[2] != "—" else 0, not x[5]))
            r["hb"] = {"rate": hb[1], "rank": hb[2], "sov": hb[3], "pos": hb[4],
                       "cshare": r.get("citation_share") or "—", "crate": pct(hit / n) if n else "—"}
            r["comp"] = rows
    # 抽屉明细：合成目录里每题有 N 个文件（<题号>-r<轮次>.json），build_details 按文件名建键，前端按
    # 「意图|平台|0001」查找。改成每题每平台一条，下挂全部运行（runs），抽屉先列运行记录再看单次回答。
    num_of = {row["question_id"]: f"{i:04d}" for i, row in enumerate(questions, 1)}
    zh_of = {row["question_id"]: row.get("question_zh", "") for row in questions}
    dir_of = {lab: p for p, lab in cfg["_platform_pairs"]}
    details = {}
    for key in sorted(data.get("details") or {}, key=lambda k: (k.rsplit("-r", 1)[0], int(k.rsplit("-r", 1)[1]))):
        region, plat_label, stem = key.split("|", 2)
        num, run = stem.rsplit("-r", 1)
        qid = qid_of[int(num)]
        entry = dict(data["details"][key], run=int(run))
        src = cfg["runs"][int(run) - 1] / f"scraper.{dir_of[plat_label]}" / cfg["region"] / f"{num}.json"
        if src.exists():
            entry["time"] = time.strftime("%m-%d %H:%M", time.localtime(src.stat().st_mtime))
        entry.pop("question_zh", None)
        details.setdefault(f"{region}|{plat_label}|{num_of[qid]}", {"question_zh": zh_of[qid], "runs": []})["runs"].append(entry)
    data["details"] = details
    polish_details(data, cfg)

    def zero(o):
        # 数值为 0 时显示「0%」，不显示「0.0%」（Suda 2026-10-22）
        if isinstance(o, dict):
            return {k: zero(v) for k, v in o.items()}
        if isinstance(o, list):
            return [zero(v) for v in o]
        return "0%" if o in ("0.0%", "0.00%") else o
    data["slices"] = zero(data["slices"])
    for s in data["details"].values():
        for r in s["runs"]:
            r["citation_share"] = zero(r.get("citation_share")) if r.get("citation_share") not in (None, "", "—") else "无引用"
    residue_report(data)
    for s in data["slices"].values():
        tm = (s.get("sentiment") or {}).get("theme_matrix") or {}
        if tm.get("themes"):
            # 展示品牌都没有信号的主题行不展示（Hbrand 的「价格与费用」只来自未展示的开放品牌）
            keep = [t for t in tm["themes"]
                    if any((tm["matrix"].get(t, {}).get(b) or {}).get("pos", 0) + (tm["matrix"].get(t, {}).get(b) or {}).get("neg", 0)
                           for b in tm.get("brands") or [])]
            tm["themes"] = keep
            tm["matrix"] = {t: tm["matrix"][t] for t in keep if t in tm["matrix"]}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


MD_ESCAPE = re.compile(r"\\([$:.\-~()#*_!+|\[\]：（） ])")
DOUBLE_ESC = re.compile(r"&amp;(amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);")
LATEX_HINT = re.compile(r"\\(text|frac|times|approx|cdot|le|ge|left|right)\b")


def latex_to_text(t: str) -> str:
    """把回答里的 LaTeX 公式写成可读文本：\text{A} → A，\frac{a}{b} → a ÷ b，\times → × 等。"""
    t = t.replace("&#92;", "\\")
    for _ in range(6):
        t2 = re.sub(r"\\text\{([^{}]*)\}", r"\1", t)
        t2 = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}",
                    lambda m: " ÷ ".join(f"({x})" if re.search(r"\s[+\-]\s", x) else x for x in m.groups()), t2)
        if t2 == t:
            break
        t = t2
    for k, v in {r"\times": "×", r"\approx": "≈", r"\cdot": "·", r"\le": "≤", r"\ge": "≥", r"\%": "%",
                 r"\left": "", r"\right": "", r"\,": " ", r"\;": " ", r"\$": "$"}.items():
        t = t.replace(k, v)
    t = re.sub(r"\$\$|\\\[|\\\]", "", t).replace("{", "").replace("}", "")
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def fix_answer_html(h: str) -> str:
    """回答 HTML 的渲染修复（Suda 2026-10-21 指出原文与译文里大量 markdown 残留）。
    采集到的回答里有：空目标图片 ![alt]()、空链接 [文字]()、--- 分隔、ChatGPT 组件残留（:::writing、{#each}、
    <Entity value=…>）、LaTeX 公式、HTML 实体被二次转义（&amp;amp;）、markdown 转义（如 S 加反斜杠加美元符）。"""
    for _ in range(3):
        h2 = DOUBLE_ESC.sub(r"&\1;", h)
        if h2 == h:
            break
        h = h2
    h = re.sub(r"&lt;Entity\s+value=(?:&quot;|\")([^&\"]*)(?:&quot;|\")[^<]*?(?:/?&gt;|(?=<))", r"\1", h)
    h = re.sub(r"&lt;/?(?:ListOption|Entity)[^<]*", "", h)
    # 图片（多为空目标；带网址的会被自动链接成 <a>，一并删到右括号或段落结束）
    h = re.sub(r"!\[(?:[^\[\]\n]|\[[^\]\n]*\])*\]\(.*?(?:\)|(?=</p>|</li>|</td>))", "", h)
    # [文字](<网址>)：尖括号网址被自动链接拆开了，只留文字
    h = re.sub(r"\[([^\[\]\n]+)\]\(&lt;.*?(?:&gt;\)|(?=</p>|</li>|</td>))", r"\1", h)
    h = re.sub(r"\\(?=</?em>)", "", h)                                        # \<em> 这类转义残留
    h = re.sub(r"<p>\s*!\[[^<\]]*</p>", "", h)                               # 换行截断的图片说明
    h = re.sub(r"\[([^\[\]]+)\]\(\)", r"\1", h)                               # 空链接只留文字
    h = re.sub(r"\[([^\]\n]*?)\]\(\)", r"\1", h)                              # 文字里还套着 [ 的空链接
    h = h.replace("]()", "")
    h = re.sub(r"<p>\s*-{3,}\s*</p>", "<hr>", h)
    h = re.sub(r"<p>\s*:::[^<]*</p>", "", h)                                   # :::writing{…} / :::
    h = re.sub(r"<(p|li)>\s*\{[#/@:][^<]*</\1>", "", h)                       # {#each …} / {@body …} 组件模板
    h = re.sub(r"\{@body[^<]*", "", h)
    h = re.sub(r"<p>\s*\\?[\[\]]\s*</p>", "", h)                              # 公式块的 [ ] 行

    def para(m):
        body = m.group(1)
        # 先处理行内 $…$（$\ge$、$30 + 60 = 90$），再整段处理残留命令，免得命令换掉后剩下孤立的 $
        body = re.sub(r"\$([^$<\n]{1,80}?)\$",
                      lambda x: latex_to_text(x.group(1)) if ("\\" in x.group(1) or re.fullmatch(r"[\d\s+\-×*/=().%]+", x.group(1))) else x.group(0), body)
        if LATEX_HINT.search(body) or "$$" in body:
            body = re.sub(r"\$\$(.+?)\$\$", lambda x: latex_to_text(x.group(1)), body)
            body = latex_to_text(body) if LATEX_HINT.search(body) else body
        body = re.sub(r"\$([^$<\n]{1,80}?)\$",
                      lambda x: latex_to_text(x.group(1)) if ("\\" in x.group(1) or re.fullmatch(r"[\d\s+\-×*/=().%]+", x.group(1))) else x.group(0), body)
        return f"<{m.group('t')}>{body}</{m.group('t')}>"

    h = re.sub(r"<(?P<t>p|li|td|th|h\d)>(.*?)</(?P=t)>", lambda m: para(type("M", (), {"group": lambda self, i: m.group(2) if i == 1 else m.group(i)})()), h, flags=re.S)
    h = re.sub(r"<p>\s*</p>", "", h)
    for _ in range(3):
        h2 = MD_ESCAPE.sub(r"\1", h)
        if h2 == h:
            break
        h = h2
    return h


def zh_tables(text: str):
    """译文是从渲染后的原文抽出的纯文本，表格只剩「a | b | c | 」行（每格后一个竖线）、没有分隔行。
    把这些行块换成占位符，返回 (文本, {占位符: 表格 HTML})：中文单元格短，售前渲染器会把
    「没有 12 字以上单元格」的表当空壳丢掉，所以表格由这里直接出 HTML。"""
    out, block, tables = [], [], {}

    def flush():
        if len(block) >= 2:
            rows = [[c.strip() for c in ln.rstrip().rstrip("|").split("|")] for ln in block]
            n = max(len(r) for r in rows)
            rows = [r + [""] * (n - len(r)) for r in rows]
            esc = lambda c: html_mod.escape(c, quote=False)
            head = "".join(f"<th>{esc(c)}</th>" for c in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            token = f"HBTABLE{len(tables)}X"
            tables[token] = f'<table class="answer-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
            out.append(token)
        else:
            out.extend(block)
        block.clear()

    for ln in text.split("\n"):
        if ln.count("|") >= 2 and not ln.lstrip().startswith("!"):
            block.append(ln)
        else:
            flush()
            out.append(ln)
    flush()
    return "\n".join(out), tables


PILL_FULL = re.compile(r'<a class="cite-pill"[^>]*title="[^"]*">.*?</a>|<span class="cite-pill" title="[^"]*">.*?</span></span>', re.S)


def restore_pills(zh_html: str, src_html: str) -> str:
    """译文里引用 pill 被抽成了「来源名+编号」纯文本（HDB2），按原文 pill 的顺序换回 pill 样式（链接与样式不变）。"""
    zh_html = zh_html.replace("&#x27;", "&#39;")   # 同一个撇号两种转义写法，统一后再对
    for m in PILL_FULL.finditer(src_html):
        pill = m.group(0)
        label = re.sub(r"<[^>]+>", "", pill).strip().replace("&#x27;", "&#39;")   # 「来源名编号」，HTML 转义后的文本
        if not re.search(r"\d$", label):
            continue
        zh_html = re.sub(re.escape(label) + r"(?!\d)", lambda _m, p=pill: p, zh_html, count=1)
    return zh_html
PILL = re.compile(r'<span class="cite-pill" title="([^"]*)">(.*?)<span class="cite-pill-num">(\d+)</span></span>')


RESIDUE = {"图片标记 ![": r"!\[", "markdown 链接 ](": r"\]\(", "粗体 **": r"\*\*", "公式 $$ / \\text": r"\$\$|\\(text|frac|times|approx)\b",
           "组件 ::: / {#": r":::|\{[#@/](body|each|if)", "二次转义 &amp;": r"&(amp|lt|gt|#\d+);", "markdown 转义": r"\\[$:.\-~()#*_!：]",
           "分隔线 ---": r"(?m)^\s*-{3,}\s*$", "未成表格的 | 行": r"(?m)^\s*\|.*\|\s*$"}


def residue_report(data):
    """渲染残留自检：把回答 HTML 去标签后按用户看到的文字扫一遍，打印各类残留条数（Suda 2026-10-21 要求自查渲染）。
    少量命中多为采集里本身截断的回答，逐条看样例判断。"""
    import collections
    hits, sample = collections.Counter(), {}
    for key, s in data["details"].items():
        for i, r in enumerate(s["runs"]):
            for lab, h in (("原文", r.get("answer_html") or ""), ("译文", r.get("answer_zh_html") or "")):
                t = re.sub(r"</(p|li|h\d|tr)>", "\n", h)
                t = html_mod.unescape(re.sub(r"<[^>]+>", "", t))
                for name, pat in RESIDUE.items():
                    n = len(re.findall(pat, t))
                    if n:
                        hits[(lab, name)] += n
                        sample.setdefault((lab, name), f"{key}#{i}")
    print("渲染残留自检：" + ("无" if not hits else "；".join(f"{a}·{b} {n}（如 {sample[(a, b)]}）" for (a, b), n in hits.items())))


def polish_details(data, cfg):
    """回答详情的三处补齐（Suda 2026-10-21）：
    - 品牌情感：每次运行列出全部品牌的 Claim（attach_sentiment 只挂展示的 5 个品牌），没有就给空，前端显示「未识别到」；
    - 正文引用 pill：采集里没有脚注定义行，pill 渲染成不可点的 span；按「来源名 + 编号」对到这次回答的 citations 补上链接；
    - 去掉 markdown 转义残留（S\\$2,600、around\\:），原文与译文都处理；
    - 译文：config.translations 目录下 batch-*.zh.json（键 = 「意图|平台|0001#运行下标」）转成 answer_zh_html。
    """
    import build_report_data as brd
    claims_by_answer = {}
    sent = cfg.get("sentiment") or {}
    if sent.get("claims"):
        rows = json.loads((cfg["_config_dir"] / sent["claims"]).read_text(encoding="utf-8"))
        rows = rows.get("claims") if isinstance(rows, dict) else rows
        seen = set()
        for c in rows:
            key = (c.get("region"), c.get("platform"), str(c.get("question_id")).zfill(4), c.get("repeat"))
            dedupe = key + (c.get("brand"), c.get("claim"))
            if dedupe in seen:
                continue
            seen.add(dedupe)
            per = claims_by_answer.setdefault(key, {})
            b = per.setdefault(c["brand"], {"brand": c["brand"], "pos_claims": [], "neg_claims": []})
            b["pos_claims" if c["sentiment"] in ("positive", "正向") else "neg_claims"].append(
                {"label": c.get("claim"), "claim": c.get("claim"), "attribute": c.get("attribute"),
                 "sentence": c.get("evidence_text") or ""})
    zh = {}
    tdir = cfg.get("translations")
    if tdir:
        for f in sorted((cfg["_config_dir"] / tdir).glob("batch-*.zh.json")):
            for k, v in json.loads(f.read_text(encoding="utf-8")).items():
                region, plat, rest = k.split("|", 2)
                zh[f"{region}|{(cfg.get('platform_labels') or {}).get('overview', plat) if plat in ('AI 概览', 'Google AI 概览') else plat}|{rest}"] = v
    dir_of = {lab: p for p, lab in cfg["_platform_pairs"]}
    target = cfg["target"]["name"]
    for key, s in data["details"].items():
        region, plat_label, num = key.split("|", 2)
        for i, r in enumerate(s["runs"]):
            brands = list((claims_by_answer.get((region, dir_of.get(plat_label), num, r.get("run"))) or {}).values())
            brands.sort(key=lambda b: (b["brand"] != target, b["brand"]))
            r["sentiment"] = {"brands": brands}
            src = cfg["runs"][int(r.get("run") or 1) - 1] / f"scraper.{dir_of.get(plat_label)}" / cfg["region"] / f"{num}.json"
            fan = []
            if src.exists():
                t = json.loads(src.read_text(encoding="utf-8")).get("task_result") or {}
                for field in ("search_model_queries", "related_queries"):
                    v = t.get(field)
                    v = v.get("queries") if isinstance(v, dict) else v
                    for q in v or []:
                        q = q.get("query") if isinstance(q, dict) else q
                        if isinstance(q, str) and q.strip() and q.strip() not in fan:
                            fan.append(q.strip())
            r["fanout"] = fan
            cites = r.get("citations") or []

            def link(m, cites=cites):
                name, inner, n = m.group(1), m.group(2), int(m.group(3))
                cand = cites[n - 1] if 0 < n <= len(cites) and (cites[n - 1].get("source_name") or "") == name else None
                cand = cand or next((c for c in cites if (c.get("source_name") or c.get("host")) == name), None)
                if not cand or not cand.get("url"):
                    return m.group(0)
                return (f'<a class="cite-pill" href="{cand["url"]}" target="_blank" rel="noopener noreferrer" '
                        f'title="{cand["url"]}">{inner}<span class="cite-pill-num">{m.group(3)}</span></a>')

            # 原文里有双重转义（S\\\\$），替换到不再变化为止
            r["answer_html"] = fix_answer_html(PILL.sub(link, r.get("answer_html") or ""))
            text = zh.get(f"{key}#r{int(r.get('run') or 0):02d}") or zh.get(f"{key}#{i}")
            if text:
                text = html_mod.unescape(html_mod.unescape(text))
                # 译文里原本是小标题的「1. 标题」各自成行，markdown 会把每行当成新列表、全部显示成 1.；
                # 转义掉让它按段落显示原编号
                text = re.sub(r"(?m)^(\s*)(\d+)\.\s", lambda m: f"{m.group(1)}{m.group(2)}\\. ", text)
                text, tables = zh_tables(text)
                zh_html = brd.markdown_to_html(text)
                for token, table in tables.items():
                    zh_html = zh_html.replace(f"<p>{token}</p>", table).replace(token, table)
                zh_html = fix_answer_html(zh_html)
                r["answer_zh_html"] = restore_pills(zh_html, r["answer_html"])


DRAWER_RUNS_JS = r"""    // 售后问题详情（Suda 2026-10-21/22，参考 Profound 的 Prompt 详情做简版）：顶部平台筛选 →
    // 品牌对比 → 各平台读数 → Query Fan-outs → 回答记录（平台、采集时间），点一行看那次回答；回答页只留「返回列表」
    state.drawerRun = state.drawerRun || {};
    state.drawerPlat = state.drawerPlat || {};
    if (!window.__hbRunBound) {
      window.__hbRunBound = true;
      document.addEventListener("click", function (ev) {
        var d = ev.target.closest("[data-detail]");
        if (d) {
          var q0 = String(d.getAttribute("data-detail")).padStart(4, "0");
          state.drawerRun[q0] = null;
          state.drawerPlat[q0] = state.platform || "";
        }
      }, true);
      document.addEventListener("click", function (ev) {
        var f = ev.target.closest("[data-dplat-qid]");
        if (f) {
          state.drawerPlat[f.getAttribute("data-dplat-qid")] = f.getAttribute("data-dplat");
          openDrawer(parseInt(f.getAttribute("data-dplat-qid"), 10));
          return;
        }
        var b = ev.target.closest("[data-run-qid]");
        if (!b) return;
        var q = b.getAttribute("data-run-qid");
        var v = b.getAttribute("data-run");
        state.drawerRun[q] = v === "" ? null : v;
        openDrawer(parseInt(q, 10));
      });
    }
    var dplat = state.drawerPlat[key] !== undefined ? state.drawerPlat[key] : (state.platform || "");
    function recFor(plat) {
      var sl = SLICES[sliceKey(state.region, plat, "")] || SLICES[sliceKey("", plat, "")] || {};
      return (sl.records || []).filter(function (r) { return String(r.qid).padStart(4, "0") === key; })[0] || null;
    }
    function compBlock(rec) {
      var rows = (rec && rec.comp) || [];
      if (!rows.length) return "";
      return '<h4 class="hb-sec">品牌对比</h4>' +
        '<table class="hb-runs hb-comp-table"><thead><tr><th>品牌</th><th>提及率</th><th>提及率排名</th><th>声量份额</th>' +
        '<th>平均提及位置</th><th>引用份额</th><th>正向情感占比</th></tr></thead><tbody>' +
        rows.map(function (r) {
          var miss = r[2] === "—";
          return '<tr' + (r[5] ? ' class="self"' : "") + '><td><span class="hb-brand">' + logo(r[8] || "", 16, r[0]) +
            "<span>" + esc(r[0]) + (r[5] ? " ★" : "") + "</span></span></td><td>" + (miss ? '<span class="hb-miss">未提及</span>' : esc(r[1])) +
            "</td><td>" + esc(r[2]) + "</td><td>" + (miss ? "—" : esc(r[3])) + "</td><td>" + esc(r[4]) +
            "</td><td>" + esc(r[6] || "—") + "</td><td>" + esc(r[7] || "—") + "</td></tr>";
        }).join("") + "</tbody></table>";
    }
    function platBlock() {
      if (dplat) return "";
      var rows = (META.platforms || []).map(function (p) {
        var h = (recFor(p) || {}).hb || {};
        return "<tr><td>" + esc(p) + "</td><td>" + esc(h.rate || "—") + "</td><td>" + esc(h.sov || "—") + "</td><td>" +
          esc(h.cshare || "—") + "</td><td>" + esc(h.crate || "—") + "</td></tr>";
      }).join("");
      return '<h4 class="hb-sec">' + esc(META.brand || "本品") + ' 各平台读数</h4><table class="hb-runs"><thead><tr><th>平台</th><th>提及率</th>' +
        "<th>声量份额</th><th>引用份额</th><th>引用率</th></tr></thead><tbody>" + rows + "</tbody></table>";
    }
    var allRuns = [];
    variants.forEach(function (v) {
      if (dplat && v.platform !== dplat) return;
      (v.entry.runs || [v.entry]).forEach(function (r, i) {
        allRuns.push({ id: v.platform + "|" + i, platform: v.platform, r: r });
      });
    });
    function fanBlock() {
      var cnt = {}, order = [];
      allRuns.forEach(function (x) {
        (x.r.fanout || []).forEach(function (q) {
          var k = x.platform + "|" + q;
          if (!cnt[k]) { cnt[k] = 0; order.push(k); }
          cnt[k] += 1;
        });
      });
      var head = '<h4 class="hb-sec">Query Fan-outs <span class="hb-sec-note">AI 研究这道题时自己生成的检索词</span></h4>';
      if (!order.length) return head + '<p class="support-line">这一轮采集没有返回检索词（ChatGPT 的 search_model_queries 为空，Gemini 只在少数回答里带相关问题）。</p>';
      order.sort(function (a, b) { return cnt[b] - cnt[a]; });
      return head + '<table class="hb-runs"><thead><tr><th>检索词</th><th>平台</th><th>出现次数</th></tr></thead><tbody>' +
        order.map(function (k) { var i = k.indexOf("|"); return "<tr><td>" + esc(k.slice(i + 1)) + "</td><td>" + esc(k.slice(0, i)) + "</td><td>" + cnt[k] + "</td></tr>"; }).join("") +
        "</tbody></table>";
    }
    var picked = allRuns.filter(function (x) { return x.id === state.drawerRun[key]; })[0];
    if (!picked) {
      var drec = recFor(dplat) || record;
      var filter = '<div class="hb-dfilter">' + ["", ].concat(META.platforms || []).map(function (p) {
        return '<button class="tab-btn' + (p === dplat ? " active" : "") + '" type="button" data-dplat="' + esc(p) + '" data-dplat-qid="' + key + '">' +
          esc(p || "全部平台") + "</button>";
      }).join("") + "</div>";
      var rowsHtml = allRuns.map(function (x) {
        var r = x.r;
        var hit = (r.brands || []).some(function (b) { return b.target; });
        var names = (r.brands || []).map(function (b) { return displayBrand(b.name); }).join("、");
        return '<tr><td>' + esc(x.platform) + '</td><td class="num">' + esc(r.time || "—") + '</td>' +
          '<td class="' + (hit ? "hb-hit" : "hb-miss") + '">' + (hit ? "提及" : "未提及") + '</td>' +
          '<td>' + esc(names || "—") + '</td>' +
          '<td class="num">' + esc(r.citation_share || "—") + '</td>' +
          '<td class="center"><button class="detail-btn" type="button" data-run="' + esc(x.id) + '" data-run-qid="' + key + '">查看回答</button></td></tr>';
      }).join("");
      body.innerHTML = '<div class="hb-runs-wrap">' +
        '<div class="hb-dhead"><div><p class="drawer-q">' + esc(record ? record.en : "") + "</p>" +
        '<p class="drawer-zh">' + esc(record ? record.zh : (entry.question_zh || "")) + "</p>" +
        '<p class="hb-dtags"><span>' + esc(record ? record.topic : "—") + "</span><span>" + esc(record ? record.intent : "—") + "</span></p></div>" +
        filter + "</div>" +
        compBlock(drec) + platBlock() + fanBlock() +
        '<h4 class="hb-sec">回答记录</h4>' +
        '<table class="hb-runs"><colgroup><col style="width:12%"><col style="width:14%"><col style="width:10%"><col>' +
        '<col style="width:10%"><col style="width:11%"></colgroup>' +
        '<thead><tr><th>平台</th><th>采集时间</th><th>' + esc(META.brand || "本品") + '</th><th>提到的品牌</th>' +
        '<th>引用份额</th><th class="center">操作</th></tr></thead><tbody>' + rowsHtml + '</tbody></table></div>';
      document.getElementById("drawerMask").classList.add("open");
      document.body.style.overflow = "hidden";
      return;
    }
    entry = picked.r;
    entry.__hbRunLabel = picked.platform + " · " + (picked.r.time || "");
    variantTabs = '<div class="hb-run-nav"><button class="variant-tab" type="button" data-run="" data-run-qid="' + key + '">← 返回列表</button></div>';
"""


SOURCES_JS = r"""  function renderSources() {
    // 售后版：每个「引用份额」旁边都配「引用率」（至少引用一次该来源的回答 ÷ 有效回答）
    var slice = currentSlice();
    var sources = slice.sources || {};
    var rates = sources.rates || {};
    var k = slice.kpis || {};
    function r(map, key) { return esc(((rates[map] || {})[key]) || "—"); }
    var badge = document.getElementById("sourceShareBadge");
    if (badge) {
      badge.innerHTML = "引用份额 <b>" + esc(sources.official_share || "—") + "</b> · 引用率 <b>" + esc(k.official_citation_rate || "—") + "</b>";
      // 全部类型：引用只统计发现＋品类认知题；点名题合计单列（Suda 2026-10-22）
      var ns = sources.named_scope;
      if (sources.citation_scope_types) {
        badge.innerHTML += '<span class="hb-scope">仅统计' + esc((sources.citation_scope_types || []).join("、") || "发现、品类认知") + "题" +
          (ns ? "；点名题（" + esc((ns.types || []).join("、")) + "）引用份额 <b>" + esc(ns.official_share || "—") +
            "</b> · 引用率 <b>" + esc(ns.official_citation_rate || "—") + "</b>，不计入本模块" : "") + "</span>";
      }
    }

    var typesEl = document.getElementById("sourceTypes");
    if (typesEl) {
      var types = sources.types || [];
      var max = types.reduce(function (acc, row) {
        return Math.max(acc, parseFloat(String(row[1]).replace("%", "")) || 0);
      }, 0) || 1;
      typesEl.innerHTML = '<div class="hb-src hb-src-type hb-src-head"><span>类别</span><span></span><span>引用份额</span><span>引用率</span></div>' +
        (types.map(function (row) {
          var value = parseFloat(String(row[1]).replace("%", "")) || 0;
          return '<div class="hb-src hb-src-type"><span class="bar-label">' + esc(row[0]) + "</span>" +
            '<div class="track"><div class="fill ' + esc(row[3] || "") + '" style="width:' + Math.max(2, (value / max) * 100) + '%"></div></div>' +
            '<b class="hb-num">' + esc(row[1]) + '</b><b class="hb-num">' + r("types", row[0]) + "</b></div>";
        }).join("") || emptyRow("暂无数据"));
    }

    var domainsEl = document.getElementById("sourceDomains");
    if (domainsEl) {
      var domains = pageSourceRows("domains", sources.domains || []);
      domainsEl.innerHTML = '<div class="hb-src hb-src-domain hb-src-head"><span>域名</span><span>类别</span><span>引用份额</span><span>引用率</span></div>' +
        (domains.map(function (row) {
          return '<div class="hb-src hb-src-domain"><span class="domain-name">' + logo(row[0]) + esc(row[0]) + "</span>" +
            catTag(row[2]) + '<span class="hb-num">' + esc(row[1]) + '</span><span class="hb-num">' + r("domains", row[0]) + "</span></div>";
        }).join("") || emptyRow("暂无数据"));
    }

    var pagesEl = document.getElementById("sourcePages");
    if (pagesEl) {
      var pages = pageSourceRows("pages", sources.pages || []);
      pagesEl.innerHTML = '<div class="hb-src hb-src-page hb-src-head"><span>页面</span><span>类别</span><span>页面中提及</span><span>引用份额</span><span>引用率</span></div>' +
        (pages.map(function (row) {
          var miss = row[2] === "未提及";
          return '<div class="hb-src hb-src-page" data-tip="' + esc(row[0]) + '">' +
            '<div class="page-title-with-logo">' + logo(row[0], 18) + '<small class="page-url" title="' + esc(row[0]) + '">' + esc(row[0]) + "</small></div>" +
            catTag(row[1]) +
            '<span class="page-mention' + (miss ? " miss" : "") + '">' + esc(row[2]) + "</span>" +
            '<span class="hb-num">' + esc(row[3]) + '</span><span class="hb-num">' + r("pages", row[0]) + "</span></div>";
        }).join("") || emptyRow("暂无数据"));
    }

    var officialEl = document.getElementById("officialPages");
    if (officialEl) {
      var official = pageSourceRows("official", sources.official_pages || []);
      officialEl.innerHTML = '<div class="hb-src hb-src-official hb-src-head"><span>页面</span><span>引用份额</span><span>引用率</span></div>' +
        (official.map(function (row) {
          return '<div class="hb-src hb-src-official" data-tip="' + esc(row[0]) + '"><div class="page-title-with-logo">' +
            logo(META.official_domain, 18) + '<small class="page-url" title="' + esc(row[0]) + '">' + esc(row[0]) + "</small></div>" +
            '<span class="hb-num">' + esc(row[1]) + '</span><span class="hb-num">' + r("pages", row[0]) + "</span></div>";
        }).join("") || emptyRow("官网尚未被引用"));
    }
  }

"""
SOURCES_CSS = (".hb-src{display:grid;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line-2);font-size:13px}"
               ".hb-src:last-child{border-bottom:0}"
               ".hb-src-head{padding:0 0 8px;border-bottom:1px solid var(--line);color:var(--quiet);font:800 10px/1.4 var(--mono);letter-spacing:.08em}"
               ".hb-src-head span:not(:first-child){text-align:right}"
               ".hb-src-type{grid-template-columns:96px minmax(0,1fr) 54px 54px}.hb-src-type .track{height:8px}"
               ".hb-src-domain{grid-template-columns:minmax(0,1fr) 72px 56px 56px}"
               ".hb-src-page{grid-template-columns:minmax(0,1fr) 78px 64px 56px 56px}"
               ".hb-src-official{grid-template-columns:minmax(0,1fr) 56px 56px}"
               ".hb-src .hb-num{text-align:right;font:12px/1.4 var(--mono);font-variant-numeric:tabular-nums;color:var(--ink);font-weight:400}"
               ".hb-src .domain-name{display:flex;align-items:center;gap:8px;min-width:0;overflow-wrap:anywhere}"
               ".hb-src .cat-tag{justify-self:end}.hb-src .page-mention{text-align:right}"
               ".hb-src .page-title-with-logo{min-width:0}"
               ".hb-src small.page-url{display:block;min-width:0;font:12px/1.45 var(--mono);color:var(--blue);"
               "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:default}"
               "#sources .source-head.with-cat{display:none}"
               ".hb-scope{display:block;margin-top:4px;font-size:12px;font-weight:400;color:var(--quiet)}")


RECORDS_JS = r'''  var RECORD_HEAD = "<thead><tr>" +
    '<th class="num">编号</th><th>问题</th><th class="num">提及率</th>' +
    '<th class="num">提及率排名</th><th class="num">声量份额</th><th class="num">平均提及位置</th>' +
    '<th class="num">引用份额</th><th class="num">引用率</th>' +
    '<th class="center">详情</th></tr></thead>';

  function compTable(rows) {
    if (!rows || !rows.length) return "";
    return '<details class="hb-comp"><summary>与竞品对比</summary><table><thead><tr><th>品牌</th>' +
      '<th>提及率</th><th>提及率排名</th><th>声量份额</th><th>平均提及位置</th></tr></thead><tbody>' +
      rows.map(function (r) {
        return '<tr' + (r[5] ? ' class="self"' : '') + '><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) +
          '</td><td>' + esc(r[2]) + '</td><td>' + esc(r[3]) + '</td><td>' + esc(r[4]) + '</td></tr>';
      }).join("") + '</tbody></table></details>';
  }

  function renderRecords() {
    var records = recordsForSlice();
    var groups = {};
    var order = [];
    records.forEach(function (record) {
      var topic = record.topic || "未分组";
      if (!groups[topic]) { groups[topic] = []; order.push(topic); }
      groups[topic].push(record);
    });

    var table = document.getElementById("recordTable");
    if (!table) return;
    if (!order.length) {
      table.innerHTML = RECORD_HEAD +
        '<tbody><tr><td class="empty" colspan="9">没有符合当前条件的记录</td></tr></tbody>';
      renderPagination(0, 1);
      return;
    }

    var pages = Math.max(1, Math.ceil(order.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    var visible = order.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);

    table.innerHTML = RECORD_HEAD + visible.map(function (topic) {
      var rows = groups[topic];
      var isOpen = state.expanded[topic] !== false;
      // 主题行直接取该主题切片的指标（按回答合计），不对逐题读数取平均
      var k = (SLICES[sliceKey(state.region, state.platform, topic)] || {}).kpis || {};
      function cell(v) { return '<td class="rank-num num"><strong>' + esc(v || "—") + '</strong></td>'; }
      var head = '<tr class="group-head" role="button" tabindex="0" aria-expanded="' + isOpen + '">' +
        '<td class="num group-toggle-cell"><span class="group-chevron">▸</span></td>' +
        "<td><strong>" + esc(topic) + '</strong><span class="group-count">' + rows.length + "</span></td>" +
        cell(k.mention_rate) + cell(k.mention_rank) + cell(k.share_of_voice) + cell(k.average_rank) +
        cell(k.official_share) + cell(k.official_citation_rate) +
        '<td class="center"></td></tr>';
      var items = rows.map(function (record) {
        var h = record.hb || {};
        function num(v) { return '<td class="rank-num num">' + esc(v || "—") + "</td>"; }
        return '<tr class="q-row">' +
          '<td class="num">' + esc(record.qid) + "</td>" +
          '<td class="q"><b>' + esc(record.en) + "</b><small>" + esc(record.zh) + " · " + esc(record.intent) + "</small></td>" +
          num(h.rate) + num(h.rank) + num(h.sov) + num(h.pos) + num(h.cshare) + num(h.crate) +
          '<td class="center"><button class="detail-btn" type="button" data-detail="' + esc(record.qid) + '">查看</button></td></tr>';
      }).join("");
      return '<tbody class="topic-group open" data-group-topic="' + esc(topic) + '">' + head + items + "</tbody>";
    }).join("");
    renderPagination(order.length, pages);
  }

'''
EXTRA_CSS = (".kpis{grid-template-columns:repeat(6,minmax(0,1fr))}"
             # 引用 pill 显示完整来源名和编号（售前样式把宽度截在 120–180px，长来源名连编号一起被吃掉，Suda 2026-10-21）
             ".cite-pill{max-width:100%!important;overflow:visible;text-overflow:clip;white-space:normal;flex-wrap:wrap}"
             ".cite-pill-num{flex:0 0 auto}"
             ".hb-comp{margin-top:6px}.hb-comp summary{cursor:pointer;color:var(--quiet);font-size:12px}"
             ".hb-comp table{margin-top:6px;border-collapse:collapse;font-size:12px}"
             ".hb-comp th,.hb-comp td{padding:3px 10px 3px 0;text-align:left;white-space:nowrap}"
             ".hb-comp tr.self td{font-weight:700}"
             ".hb-runs-wrap{padding:26px 32px 40px;height:100%;overflow-y:auto;box-sizing:border-box}.hb-runs{width:100%;margin-top:18px;border-collapse:collapse;font-size:13px;table-layout:fixed}"
             ".hb-runs th,.hb-runs td{padding:10px 12px;border-bottom:1px solid var(--line-2);text-align:left;vertical-align:top}"
             ".hb-runs th{color:var(--quiet);font-weight:600;font-size:12px}.hb-runs .hb-hit{color:var(--gold-deep);font-weight:700}"
             ".hb-runs .hb-miss{color:var(--quiet)}.hb-run-nav{margin-bottom:8px}"
             ".hb-sec{margin:22px 0 0;font:600 14px/1.4 var(--sans,inherit);color:var(--ink)}"
             ".hb-comp-table tr.self td{font-weight:700;color:var(--gold-deep)}"
             ".hb-brand{display:inline-flex;align-items:center;gap:8px;vertical-align:middle}.hb-brand .entity-logo{flex:0 0 auto}"
             ".hb-dhead{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding-bottom:14px;border-bottom:1px solid var(--line)}"
             ".hb-dfilter{display:flex;gap:6px;flex-wrap:wrap;flex:0 0 auto}.hb-dtags{margin-top:8px;display:flex;gap:8px}"
             ".hb-dtags span{padding:2px 8px;border:1px solid var(--line);border-radius:999px;font-size:12px;color:var(--muted)}"
             ".hb-sec-note{font-weight:400;font-size:12px;color:var(--quiet);margin-left:6px}"
             ".hb-top{white-space:nowrap;font-size:13px;color:var(--ink-2)}.hb-top-rate{font:12px var(--mono);color:var(--quiet)}")


def render(cfg, data_path: Path, out: Path):
    import render_report as rr
    orig_slim = rr.slim_for_html

    def slim(data):
        slim_data = orig_slim(data)
        for key, s in data["slices"].items():
            k = s.get("kpis") or {}
            for f in ("official_citation_rate", "official_citation_counts"):
                if f in k:
                    slim_data["slices"][key]["kpis"][f] = k[f]
        return slim_data

    rr.slim_for_html = slim
    data = json.loads(data_path.read_text(encoding="utf-8"))
    # 有数据的模块展示，没数据的整块隐藏（Suda 2026-10-22）：情感没接入就不出 04 和回答详情里的情感，一条引用都没有就不出 03
    has_sent = data["meta"].get("sentiment_claims_status") == "complete"
    has_cites = any((s.get("sources") or {}).get("total_citations") for s in data["slices"].values())
    drawer_js = DRAWER_RUNS_JS if has_sent else (
        DRAWER_RUNS_JS.replace("<th>正向情感占比</th>", "").replace(' + "</td><td>" + esc(r[7] || "—")', ""))
    html = rr.build_html(data)
    replace = [
        ('"全部地区"', '"全部类型"'),
        ('shown.push("地区")', 'shown.push("提示词类型")'),
        ('aria-label="地区筛选"', 'aria-label="提示词类型筛选"'),
        ('["引用份额", k.official_share, "指向监测对象官网的引用记录数 ÷ 全部引用记录数。"]',
         '["引用份额", k.official_share, "指向监测对象官网的引用记录数 ÷ 全部引用记录数。全部类型时只统计发现与品类认知题（题面点名品牌会把它的官网拉进引用），选中某一类型时按该类型统计。"],\n'
         '      ["引用率", k.official_citation_rate, "正文至少引用一次监测对象官网的回答 ÷ 有效回答。按回答计，一条回答引用多次只算一次。统计范围同引用份额。"]'),
        ('"官网引用份额 " + esc(sources.official_share || "—") + "。",',
         '"官网引用份额 " + esc(sources.official_share || "—") + "，引用率 " + esc(k.official_citation_rate || "—") + '
         '"（至少引用一次官网的回答占比）。",'),
        # 抽屉：先列每次运行，点某一次再看那次的回答（Suda 2026-10-21）
        ('    var ranking = (entry.brands || []).map(function (row) {', drawer_js + '    var ranking = (entry.brands || []).map(function (row) {'),
        ('\'<div class="detail-meta-cell"><span>标签</span><strong>\' + esc(record ? record.tag : "—")',
         '\'<div class="detail-meta-cell"><span>平台 · 采集时间</span><strong>\' + esc(entry.__hbRunLabel || (record ? record.tag : "—"))'),
        # 情感只给合计口径（正向信号之和 ÷ 正负信号之和），不展示跨平台等权值和附注（Suda 2026-10-21）
        ('      if (crossRate && crossRate !== "—" && signalPlatforms) {', '      if (false) {'),
        # 平台 × 品牌矩阵的品牌列加 logo，域名取同切片可见度榜
        ('<td class="brand-cell">\' + esc(displayBrand(row.name)) + "</td>"',
         '<td class="brand-cell"><span style="display:inline-flex;align-items:center;gap:8px">\' + '
         'logo((((currentSlice().competition || {}).mention || []).filter(function (m) { return displayBrand(m[0]) === displayBrand(row.name); })[0] || [])[1] || "", 16, row.name) + '
         'esc(displayBrand(row.name)) + "</span></td>"'),
        # 意图筛选（借用地区层）选中时，明细只列该意图的题；抽屉按全部意图找回答（一道题只属于一个意图）
        ('    var all = slice.records || [];', '    var all = (slice.records || []).filter(function (r) { return !state.region || r.intent === state.region; });'),
        ('    var regions = state.region ? [state.region] : (META.regions || []);', '    var regions = META.regions || [];'),
        # 品牌情感：没有识别到时也展示这一块，写明未识别到；情感没接入时整块不出
        ('    if (sentimentBrands.length) {',
         '    if (' + ("true" if has_sent else "false") + ' && !sentimentBrands.length) {\n      sentimentSection = \'<section class="detail-section"><div class="detail-section-head"><h4>品牌情感</h4></div>\' +\n'
         '        \'<p class="support-line">这次回答没有对品牌的明确褒贬</p></section>\';\n    }\n    if (sentimentBrands.length) {'),
        # 品牌提及识别的是全部同类平台与竞品，不只是配置品牌
        ("该回答未提及已配置品牌", "这次回答没有提到任何同类平台或竞品"),
        ('return "<td>" + Number(value).toFixed(1) + "%</td>";', 'return "<td>" + (Number(value) === 0 ? "0%" : Number(value).toFixed(1) + "%") + "</td>";'),
        # 售前模板里写死的视频流媒体品类话术，换品类会说错，去掉
        ("。官网被引用的多是应用下载页与首页，缺少可被 AI 直接引用的<strong>内容型页面</strong>（剧集与题材介绍、功能与价格说明、常见问题），第三方因此占据了事实定义权。", "。"),
        ("把可核验的事实（内容库、字幕语言、价格）说清楚", "把可核验的事实说清楚"),
        # 指标解释不提「可见度问题」：售后所有题都计入，范围由筛选决定（Suda 2026-10-21）
        ('"可见度问题中，监测对象被 AI 提及的比例。越高说明监测对象越容易进入相关回答。"',
         '"提到监测对象的回答占有效回答的比例。越高说明监测对象越容易进入相关回答。"'),
        # 筛选挪到核心洞察前面，作用于全部模块
        ('同时作用于 02 / 03 / 04 / 05 模块', '同时作用于下方全部模块'),
        # 问题明细加平台下拉，与上方平台筛选同步（改它等于点上方平台 tab）
        ('<option value="">全部类型</option></select>', '<option value="">全部类型</option></select>'
         '<select class="records-intent-select" id="recordPlatformFilter" aria-label="按平台筛选"></select>'),
        ('    el.innerHTML = html;\n  }\n\n  /* ---------- 事件 ---------- */',
         '    el.innerHTML = html;\n'
         '    var pf = document.getElementById("recordPlatformFilter");\n'
         '    if (pf) {\n'
         '      pf.innerHTML = \'<option value="">全部平台</option>\' + (META.platforms || []).map(function (p) {\n'
         '        return \'<option value="\' + esc(p) + \'"\' + (state.platform === p ? " selected" : "") + ">" + esc(p) + "</option>";\n'
         '      }).join("");\n'
         '    }\n'
         '  }\n\n  /* ---------- 事件 ---------- */'),
        ('    var intentSelect = document.getElementById("recordIntentFilter");\n    if (intentSelect) {',
         '    var platformSelect = document.getElementById("recordPlatformFilter");\n'
         '    if (platformSelect) {\n'
         '      platformSelect.addEventListener("change", function () {\n'
         '        state.platform = platformSelect.value;\n'
         '        state.page = 1;\n'
         '        state.sourcePage = { domains: 1, pages: 1, official: 1 };\n'
         '        renderAll();\n'
         '      });\n'
         '    }\n'
         '    var intentSelect = document.getElementById("recordIntentFilter");\n    if (intentSelect) {'),
        ("海外 AI 搜索可见度售前诊断", cfg.get("title") or "AI 搜索可见度 · 候选基线"),
        ("海外 GEO 售前诊断报告", "海外 GEO 候选基线报告"),
        ("GEO Presales Diagnosis", "GEO Candidate Baseline"),
        ('<span class="logo-tag">售前诊断</span>', '<span class="logo-tag">候选基线</span>'),
        ("</style>", EXTRA_CSS + "\n</style>"),
    ]
    for old, new in replace:
        if old not in html:
            raise SystemExit(f"售前渲染模板变了，找不到要替换的文字：{old[:60]}")
        html = html.replace(old, new)
    s0, s1 = html.find("  function renderSources() {"), html.find("  /* ---------- 04 情感 ---------- */")
    if s0 < 0 or s1 < s0:
        raise SystemExit("售前渲染模板变了，找不到引用模块代码段")
    html = html[:s0] + SOURCES_JS + html[s1:]
    html = html.replace("</style>", SOURCES_CSS + "\n</style>", 1)
    start, end = html.find("  var RECORD_HEAD = "), html.find("  function renderPagination(")
    if start < 0 or end < start:
        raise SystemExit("售前渲染模板变了，找不到明细表代码段")
    html = html[:start] + RECORDS_JS + html[end:]
    # config.hide_sections 里的模块整段隐藏（连同顶部导航），如 opportunities = 05 内容规划（Suda 2026-10-21 先隐藏）；
    # 没数据的模块自动加进来，剩下的模块按顺序重新编号
    hide = [h for h in (cfg.get("hide_sections") or []) if re.fullmatch(r"[a-z_-]+", h)]
    auto = [h for h, ok in (("distribution", has_sent), ("sources", has_cites)) if not ok and h not in hide]
    if auto:
        print("没数据、自动隐藏的模块：" + "、".join(auto))
    hide += auto
    if hide:
        css = "".join(f'#{h},a[href="#{h}"]{{display:none!important}}' for h in hide)
        html = html.replace("</style>", css + "\n</style>", 1)
    n = 0

    def renumber(m):
        nonlocal n
        if m.group(1) in hide or not m.group(3).isdigit():
            return m.group(0)
        n += 1
        return f"{m.group(2)}{n:02d}</span>"
    html = re.sub(r'(?s)(<section class="section" id="([a-z_-]+)">.*?<span class="section-no">)(\d+|[^<]*)</span>',
                  lambda m: renumber(type("M", (), {"group": lambda self, i: (m.group(0), m.group(2), m.group(1), m.group(3))[i]})()), html)
    # 「官网引用份额 / 官网引用率」统一叫「引用份额 / 引用率」（Suda 2026-10-21）
    html = html.replace("官网引用份额", "引用份额").replace("官网引用率", "引用率")
    # 数据筛选挪到核心洞察前面（Suda 2026-10-21）
    f0 = html.find('<div class="shared-filter" id="sharedFilter"')
    f1 = html.find('<section class="section" id="competition">', f0)
    o0 = html.find('<section class="section" id="overview">')
    if min(f0, f1, o0) < 0 or o0 > f0:
        raise SystemExit("售前渲染模板变了，找不到筛选面板或核心洞察段")
    block = html[f0:f1]
    html = html[:o0] + block + html[o0:f0] + html[f1:]
    rr.check_javascript(html[html.rfind("<script>") + 8:html.rfind("</script>")], out)
    # 整份数据 gzip 后内嵌，浏览器解压完再启动主脚本（主脚本自己按 readyState 启动）。
    # 5 次运行的回答原文都放进来后，明文 JSON 约 15 MB，侧边栏打不开（Suda 2026-10-21）。
    import base64
    import gzip
    d0 = html.find("<script>window.REPORT_DATA=")
    d1 = html.find(";</script>\n<script>\n", d0)
    j1 = html.rfind("\n</script>")
    if min(d0, d1, j1) < 0:
        raise SystemExit("售前渲染模板变了，找不到内嵌数据段")
    payload = html[d0 + len("<script>window.REPORT_DATA="):d1]
    main_js = html[d1 + len(";</script>\n<script>\n"):j1]
    blob = base64.b64encode(gzip.compress(payload.encode("utf-8"), 9)).decode("ascii")
    loader = ('(function () {\n'
              '  var s = window.__HB_DATA_GZ, b = atob(s), u = new Uint8Array(b.length);\n'
              '  for (var i = 0; i < b.length; i += 1) u[i] = b.charCodeAt(i);\n'
              '  new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream("gzip"))).text()\n'
              '    .then(function (t) { window.REPORT_DATA = JSON.parse(t); delete window.__HB_DATA_GZ; start(); })\n'
              '    .catch(function (e) { document.body.insertAdjacentHTML("afterbegin", '
              '"<p style=\\"color:#b00;padding:20px\\">数据解压失败：" + e + "。请用新版 Chrome / Edge / Safari 打开。</p>"); });\n'
              '  function start() {\n' + main_js + '\n  }\n})();')
    rr.check_javascript(loader, out)
    html = html[:d0] + '<script>window.__HB_DATA_GZ="' + blob + '";</script>\n<script>\n' + loader + html[j1:]
    out.write_text(html, encoding="utf-8")
    print("HTML", out, round(out.stat().st_size / 1e6, 2), "MB")


def export_translations(cfg, brd, out_dir: Path, batch_size: int = 60) -> None:
    """导出每次运行的回答原文供翻译，直接读 --prepare 合成的 out_dir/collect，不用先生成报告。
    batch-NN.json = [{key, text}]，key = 「提示词类型|平台|0001#r01」；文本按报告同一套渲染与清理后取纯文字，
    引用标记成「来源名+编号」（HDB2），回填时据此还原成引用标签。译文写同目录 batch-NN.zh.json（{key: 中文}）。"""
    collect = cfg["out_dir"] / "collect"
    if not collect.exists():
        raise SystemExit("先跑 --prepare 生成 out_dir/collect")

    def txt(h):
        t = re.sub(r"<br\s*/?>", "\n", h or "")
        t = re.sub(r"</p>|</li>|</h\d>|</tr>", "\n", t)
        t = re.sub(r"</t[dh]>", " | ", t)
        return re.sub(r"\n{3,}", "\n\n", html_mod.unescape(re.sub(r"<[^>]+>", "", t))).strip()

    items = []
    for p, label in cfg["_platform_pairs"]:
        for f in sorted((collect / f"scraper.{p}").glob("*/*.json")):
            num, run = f.stem.split("-r")
            answer = str((json.loads(f.read_text(encoding="utf-8")).get("task_result") or {}).get(brd.ANSWER_FIELD[p]) or "").strip()
            if answer:
                items.append({"key": f"{f.parent.name}|{label}|{num}#r{int(run):02d}",
                              "text": txt(fix_answer_html(brd.markdown_to_html(answer)))})
    out_dir.mkdir(parents=True, exist_ok=True)
    n = -(-len(items) // batch_size)
    for k in range(n):
        (out_dir / f"batch-{k + 1:02d}.json").write_text(
            json.dumps(items[k * batch_size:(k + 1) * batch_size], ensure_ascii=False), encoding="utf-8")
    print(f"导出 {len(items)} 条回答原文，{n} 批 → {out_dir}")


def export_claim_batches(units_path: Path, questions, out_dir: Path, batches: int = 6) -> None:
    """把 sentiment_sentences extract 的单元切批，供逐批抽 Claim：batch-NN.json = [{unit_index, brand, question, unit}]。
    抽完写 batch-NN.claims.json（[{unit_index, brand, claim, sentiment}]），再用 --merge-claims 合并。"""
    units = json.loads(units_path.read_text(encoding="utf-8"))["units"]
    q_of = {f"{i:04d}": q["query"] for i, q in enumerate(questions, 1)}
    items = [{"unit_index": i, "brand": u["brand"], "question": q_of.get(str(u["question_id"]).zfill(4), ""), "unit": u["unit"]}
             for i, u in enumerate(units)]
    out_dir.mkdir(parents=True, exist_ok=True)
    size = -(-len(items) // batches)
    for b in range(batches):
        (out_dir / f"batch-{b + 1:02d}.json").write_text(json.dumps(items[b * size:(b + 1) * size], ensure_ascii=False), encoding="utf-8")
    print(f"导出 {len(items)} 个情感单元，{batches} 批 → {out_dir}")


def merge_claims(units_path: Path, batch_dir: Path, out_path: Path) -> None:
    """合并 batch-*.claims.json 为 claims-raw.json，并核对 unit_index 与品牌都对得上单元。"""
    units = json.loads(units_path.read_text(encoding="utf-8"))["units"]
    rows = []
    for f in sorted(batch_dir.glob("batch-*.claims.json")):
        rows += json.loads(f.read_text(encoding="utf-8"))
    bad = [c for c in rows if not (0 <= c.get("unit_index", -1) < len(units)) or units[c["unit_index"]]["brand"] != c.get("brand")]
    if bad:
        raise SystemExit(f"{len(bad)} 条 claim 的 unit_index 或品牌对不上单元，如 {bad[:2]}")
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    pos = sum(1 for c in rows if c.get("sentiment") == "positive")
    print(f"合并 {len(rows)} 条 claim（正 {pos} / 负 {len(rows) - pos}）→ {out_path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="候选基线 → 单文件 HTML 基线报告")
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--render-only", action="store_true", help="只用已有 report-data.json 重新渲染")
    ap.add_argument("--prepare", action="store_true", help="只合成 out_dir/collect、questions.csv、lexicon.json，供情感抽取与翻译导出")
    ap.add_argument("--export-translations", type=Path, metavar="DIR", help="导出回答原文翻译批次（先 --prepare）")
    ap.add_argument("--export-claim-batches", type=Path, metavar="DIR", help="把 sentiment.units 切成 Claim 抽取批次")
    ap.add_argument("--merge-claims", type=Path, metavar="DIR", help="合并 DIR 下 batch-*.claims.json 为 sentiment 目录的 claims-raw.json")
    args = ap.parse_args(argv)
    cfg = load_config(args.config.resolve())
    brd, core_util, find_alias_spans = install_patches(cfg)
    questions = list(csv.DictReader(open(cfg["questions_csv"], encoding="utf-8-sig")))
    intent = intent_of(cfg)
    platforms = sorted({d.name.split(".", 1)[1] for r in cfg["runs"] for d in r.iterdir()
                        if d.is_dir() and d.name.startswith("scraper.")})
    cfg["_platforms"] = platforms
    cfg["_platform_pairs"] = [(p, brd.KNOWN_PLATFORM_LABELS.get(p, p)) for p in platforms]
    out = cfg["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    data_path = out / "report-data.json"
    html_path = out / (cfg.get("out_name") or f"{cfg['target']['name']}-候选基线报告.html")
    sent_cfg = cfg.get("sentiment") or {}
    if args.prepare:
        prepare_inputs(cfg, questions, intent, platforms)
        return 0
    if args.export_translations:
        export_translations(cfg, brd, args.export_translations.resolve())
        return 0
    if args.export_claim_batches or args.merge_claims:
        if not sent_cfg.get("units"):
            raise SystemExit("config.sentiment.units 未配置")
        units_path = (cfg["_config_dir"] / sent_cfg["units"]).resolve()
        if args.export_claim_batches:
            export_claim_batches(units_path, questions, args.export_claim_batches.resolve())
        else:
            merge_claims(units_path, args.merge_claims.resolve(), units_path.parent / "claims-raw.json")
        return 0
    if not args.render_only:
        prepare_inputs(cfg, questions, intent, platforms)
        rc = brd.main(["--collect", str(out / "collect"), "--questions", str(out / "questions.csv"),
                       "--case", str(out / "case.json"), "--lexicon", str(out / "lexicon.json"),
                       "--domain-cache", str(out / "domain-categories.json"), "--out", str(data_path),
                       "--source-limit", "0"])
        if rc:
            return rc
        # 校验在回写真实意图之前跑：校验脚本按 meta.questions 的意图挑可见度样本，回写后它只认发现题
        import verify_report_data as vr
        vr.find_alias_spans = find_alias_spans
        patch_verify(vr)
        if vr.main(["--report", str(data_path), "--collect", str(out / "collect")]):
            raise SystemExit("verify_report_data 未通过，不渲染")
        attach_sentiment(cfg, data_path)
        patch_report_data(data_path, cfg, questions, intent,
                          official_rates(cfg, brd, core_util, questions, platforms))
    render(cfg, data_path, html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
