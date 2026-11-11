"""线上 runner 的固定预采集（precollect）：agent 启动前按渠道计划采搜索联想、评价、社区。

2026-11-11（3.7.0）从 run_selection_mode.py 拆出，行为不变：行业判断后的渠道计划检查（check_plan、fallback_plan）、
三类采集（搜索联想、评价、社区）、登记检查、每轮记账里预采集那部分要用的常量。由 run_selection_mode.py 导入，
不单独运行。行业判断本身（plan_step，要起 agent）留在 run_selection_mode.py。
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def domestic() -> bool:
    """境内模式（3.5.1）：GEO_NET_DOMESTIC=1 时服务器只连得上 api.scrapeless.com（和 DataForSEO，如果放行了），
    net.py 和 collect_serp_signals.py 不试直连、全部经 Scrapeless 代理，Reddit 和无头 Chrome 不发请求。"""
    return os.environ.get("GEO_NET_DOMESTIC", "").strip().lower() in ("1", "true", "yes", "on")


def net_env(ws: Path) -> dict:
    """net.py 的线上限量：Reddit RSS 约每分钟 1 次，是线上调研最慢的一环，默认每个工作目录最多 10 次联网请求。
    缓存目录按工作目录隔离（3.1.0），代理页数和搜索次数才能按轮归集；代价是不同品牌 × 市场的运行之间不共享网页缓存。
    境内模式开关显式透传，不依赖子进程是否继承环境变量。"""
    env = {"NET_REDDIT_MAX": os.environ.get("NET_REDDIT_MAX", "10"),
           "NET_REDDIT_COUNTER": str(ws / "logs/reddit_calls"),
           "NET_CACHE_DIR": str(ws / "logs/net_cache")}
    if domestic():
        env["GEO_NET_DOMESTIC"] = "1"
    for k in ("SCRAPELESS_BASE_URL", "DATAFORSEO_BASE_URL", "GEO_GATEWAY_HEADERS"):  # 平台网关（3.6.4）
        if os.environ.get(k, "").strip():
            env[k] = os.environ[k]
    return env


# ---- precollect（3.4.0）：agent 启动前由脚本固定采集评价、社区、搜索联想 ---------------------------

PRECOLLECT_DIR = "research/precollect"
PRECOLLECT_TIMEOUT = 6 * 60          # 每类上限
PRECOLLECT_REDDIT_CAP = 5            # precollect 最多用这么多次 Reddit 联网请求，其余留给 agent
PRECOLLECT_PROXY_PAGES = 2           # RSS 读不到时改读网页版（Scrapeless 代理，每帖 1 次付费请求）最多几个帖子
REVIEW_DEPTH = 40                    # 每个竞品域名约 40 条 Trustpilot 评价（20 条一个计费单位）
# 采集类别 = 采集脚本写进 signals.csv 的「来源类型」值（collect_serp_signals.py 写「搜索联想」、
# collect_reviews.py 写「评价」，社区由本脚本按 net.py reddit 的输出写「社区」）
PRECOLLECT_CATEGORIES = {"搜索联想": "serp", "评价": "reviews", "社区": "community"}
# 与 shared/scripts/collect_keyword_data.py 的 FIELDS 一致（三个采集脚本的 signals.csv 同一套列）
SIGNAL_FIELDS = ["输入编号", "产品线", "来源类型", "月搜索量", "原话", "译文", "目标客户", "约束条件",
                 "出处", "引用它的问题"]
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'&+-]*")
_STOP = {"best", "with", "from", "that", "this", "your", "for", "and", "the", "of", "to", "in", "on", "a", "an"}


CHANNELS_REL = "references/precollect-channels.json"
PARAM_CHANNELS = {"google-play": "app_ids", "app-store": "app_ids", "google-maps": "maps_queries"}
FALLBACK_INDUSTRY = "未判定"
FALLBACK_REVIEWS = ["trustpilot"]     # 只在行业判断失败时用
PLAN_TIMEOUT = 15 * 60
CATEGORY_TIMEOUT = {"评价": 10 * 60}  # 评价任务是 DataForSEO 异步队列，比搜索和社区慢；三类并行跑，总时长约等于最慢的一类
SHOPPING_PRODUCTS = 2
SITE_PAGES = 2                        # 站内页每个渠道最多读几页
HN_HITS = 20                          # Hacker News 每个搜索词取几条评论


def load_channels(ws: Path | None = None) -> dict:
    """行业 × 市场渠道表：优先读工作目录里复制的那份（线上 agent 读的就是它）。"""
    for root in ([ws / ".agents/skills/geo-prompt-selection-builder"] if ws else []) + [SKILL]:
        path = root / CHANNELS_REL
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(CHANNELS_REL)


def _market_communities(table: dict, market: str) -> list[str]:
    markets = table.get("markets") or {}
    return list(markets.get(market.upper()) or markets.get("_default") or [])


def check_plan(ws: Path) -> tuple[list[str], dict]:
    """检查 research/precollect/plan.json，返回 (报错, 展开后的渠道计划)。没有报错时同时写 plan-checked.json。

    要采的渠道 = 行业行的评价、社区 + 市场行的社区 + add；只有要参数的渠道（应用 ID、门店名）和写了 scope 的站能 skip，
    这样「采不采」仍由表决定，模型只负责判行业和填参数。"""
    table = load_channels(ws)
    market = ""
    try:
        market = json.loads((ws / "out/result.json").read_text(encoding="utf-8")).get("market", "")
    except (OSError, json.JSONDecodeError):
        pass
    path = ws / PRECOLLECT_DIR / "plan.json"
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return [f"没有 {PRECOLLECT_DIR}/plan.json"], {}
    except json.JSONDecodeError as exc:
        return [f"plan.json 不是合法 JSON：{exc}"], {}
    if not isinstance(plan, dict):
        return ["plan.json 顶层要是对象"], {}
    errors: list[str] = []
    industries = table.get("industries") or {}
    reviews_all, comms_all = table.get("review_channels") or {}, table.get("community_channels") or {}
    industry = str(plan.get("industry") or "").strip()
    if industry != "其他" and industry not in industries:
        errors.append(f"industry「{industry}」不在 precollect-channels.json 的 industries 里；键名原样照抄，都不合适写「其他」")
    if not str(plan.get("industry_basis") or "").strip():
        errors.append("industry_basis 不能空：写品牌卖什么、卖给谁，引官网原文并带网址")
    cat_en = str(plan.get("category_en") or "").strip()
    if cat_en and not (1 <= len(_EN_WORD.findall(cat_en)) <= 5 and not re.search(r"[^\x00-\x7f]", cat_en)):
        errors.append(f"category_en「{cat_en}」要是 1–5 个英文词")
    row = industries.get(industry) or {}
    planned: dict[str, dict] = {}
    for name in row.get("评价") or []:
        planned[name] = {"category": "评价", "from": f"行业：{industry}"}
    for name in row.get("社区") or []:
        planned[name] = {"category": "社区", "from": f"行业：{industry}"}
    for name in _market_communities(table, market):
        planned.setdefault(name, {"category": "社区", "from": f"市场：{market or '_default'}"})
    add = plan.get("add") or {}
    if not isinstance(add, dict):
        errors.append("add 要是 {渠道名: 原因}")
        add = {}
    add_cap = 5 if industry == "其他" else 3  # 「其他」这一行本身没有渠道，多给 AI 一些余地（3.7.0）
    if len(add) > add_cap:
        errors.append(f"add 最多 {add_cap} 个，现在 {len(add)} 个")
    for name, why in add.items():
        if name in reviews_all:
            planned.setdefault(name, {"category": "评价", "from": f"补充：{why}"})
        elif name in comms_all:
            planned.setdefault(name, {"category": "社区", "from": f"补充：{why}"})
        else:
            errors.append(f"add 里的「{name}」不在 review_channels / community_channels 里")
        if not str(why or "").strip():
            errors.append(f"add 里的「{name}」要写原因")
    # 渠道表里没有、但这个品牌明显该看的站（3.7.0）：AI 推理加进来，按站内页渠道采（搜「站名 品类词」再取页面正文）
    sites = plan.get("add_sites") or {}
    if not isinstance(sites, dict):
        errors.append("add_sites 要是 {域名: {category: 评价或社区, why: 原因}}")
        sites = {}
    if len(sites) > 2:
        errors.append(f"add_sites 最多 2 个，现在 {len(sites)} 个")
    custom: dict[str, dict] = {}
    for dom, v in sites.items():
        dom = str(dom).strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").strip("/")
        v = v if isinstance(v, dict) else {}
        if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", dom):
            errors.append(f"add_sites 的键要是域名（如 example.com），收到「{dom}」")
            continue
        if dom.split(".")[0] in reviews_all or dom.split(".")[0] in comms_all or dom in planned:
            errors.append(f"「{dom}」渠道表里已有，写进 add，不要写进 add_sites")
            continue
        if v.get("category") not in ("评价", "社区") or not str(v.get("why") or "").strip():
            errors.append(f"add_sites 里的「{dom}」要写 category（评价 或 社区）和 why")
            continue
        planned[dom] = {"category": v["category"], "from": f"AI 推理加的站：{str(v['why']).strip()}"}
        custom[dom] = {"site": dom, "query": "category"}
    if industry == "其他" and not any(v["category"] == "评价" for v in planned.values()):
        errors.append("industry 写「其他」时，add 或 add_sites 里至少挑 1 个评价渠道")
    skip = plan.get("skip") or {}
    if not isinstance(skip, dict):
        errors.append("skip 要是 {渠道名: 原因}")
        skip = {}
    scoped = {n for n, v in planned.items()
              if ((reviews_all if v["category"] == "评价" else comms_all).get(n) or {}).get("scope")}
    for name, why in skip.items():
        if name not in PARAM_CHANNELS and name not in scoped:
            errors.append(f"skip 只能跳过 {sorted(PARAM_CHANNELS)}（缺应用或门店时）和渠道表里写了 scope 的站，"
                          f"「{name}」按表要采，不能跳过")
        elif not str(why or "").strip():
            errors.append(f"skip 里的「{name}」要写原因")
    app_ids = plan.get("app_ids") or {}
    maps_q = [str(q).strip() for q in (plan.get("maps_queries") or []) if str(q).strip()]
    for name, field in PARAM_CHANNELS.items():
        if name not in planned or name in skip:
            continue
        vals = maps_q if field == "maps_queries" else [str(v).strip() for v in (app_ids.get(name) or []) if str(v).strip()]
        if not vals:
            errors.append(f"要采 {name}：在 {field} 里填{'门店「店名 城市」' if field == 'maps_queries' else '应用 ID'}，"
                          f"或在 skip 里写为什么没有")
        if name == "google-play" and any(not re.fullmatch(r"[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+", v) for v in vals):
            errors.append(f"google-play 应用 ID 是包名（如 com.example.app），收到 {vals}")
        if name == "app-store" and any(not re.fullmatch(r"(id)?\d{6,12}", v) for v in vals):
            errors.append(f"app-store 应用 ID 是 6–12 位数字，收到 {vals}")
    for key, cap in (("reddit_queries", 2), ("hn_queries", 3)):
        if len(plan.get(key) or []) > cap:
            errors.append(f"{key} 最多 {cap} 条")
    if errors:
        return errors, {}
    channels = []
    for name, info in planned.items():
        spec = custom.get(name) or (reviews_all if info["category"] == "评价" else comms_all).get(name) or {}
        channels.append({"name": name, "category": info["category"], "from": info["from"], "spec": spec,
                         "status": "skipped" if name in skip else "planned",
                         "reason": str(skip.get(name) or "")})
    checked = {"industry": industry, "industry_basis": str(plan["industry_basis"]).strip(), "market": market,
               "category_en": cat_en, "local_query": str(plan.get("local_query") or "").strip(),
               "app_ids": {k: [str(v).strip().removeprefix("id") if k == "app-store" else str(v).strip()
                               for v in (app_ids.get(k) or [])] for k in ("google-play", "app-store")},
               "maps_queries": maps_q,
               "reddit_queries": [str(q).strip() for q in plan.get("reddit_queries") or [] if str(q).strip()],
               "hn_queries": [str(q).strip() for q in plan.get("hn_queries") or [] if str(q).strip()],
               "channels": channels, "source": "agent"}
    write_json(ws / PRECOLLECT_DIR / "plan-checked.json", checked)
    return [], checked


def fallback_plan(ws: Path, why: str) -> dict:
    """行业判断没交出合格的 plan.json：评价只采竞品 Trustpilot，社区按市场采，原因记进计划。"""
    table = load_channels(ws)
    try:
        market = json.loads((ws / "out/result.json").read_text(encoding="utf-8")).get("market", "")
    except (OSError, json.JSONDecodeError):
        market = ""
    comms = table.get("community_channels") or {}
    channels = [{"name": n, "category": "评价", "from": "行业未判定，默认采", "spec": (table.get("review_channels") or {})[n],
                 "status": "planned", "reason": ""} for n in FALLBACK_REVIEWS]
    channels += [{"name": n, "category": "社区", "from": f"市场：{market or '_default'}", "spec": comms.get(n) or {},
                  "status": "planned", "reason": ""} for n in _market_communities(table, market)]
    checked = {"industry": FALLBACK_INDUSTRY, "industry_basis": why, "market": market, "category_en": "", "local_query": "",
               "app_ids": {}, "maps_queries": [], "reddit_queries": [], "hn_queries": [], "channels": channels,
               "source": "fallback"}
    write_json(ws / PRECOLLECT_DIR / "plan-checked.json", checked)
    return checked


def load_plan(ws: Path) -> dict:
    try:
        return json.loads((ws / PRECOLLECT_DIR / "plan-checked.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if (ws / PRECOLLECT_DIR / "plan.json").exists():
        errors, checked = check_plan(ws)
        if not errors:
            return checked
        return fallback_plan(ws, "plan.json 没通过检查：" + "；".join(errors)[:400])
    return fallback_plan(ws, "没有跑行业判断（单跑 precollect 或旧工作目录）")




def _scripts_dir(ws: Path) -> Path:
    override = os.environ.get("PRECOLLECT_SCRIPTS_DIR", "").strip()
    return Path(override) if override else ws / ".agents/skills/shared/scripts"


def _clean_domain(raw: str) -> str:
    raw = str(raw or "").strip()
    if not raw:
        return ""
    host = (urllib.parse.urlsplit(raw if "://" in raw else "https://" + raw).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def precollect_terms(norm: dict, category_override: str = "") -> dict:
    """从归一化品牌资料推品类词、人群词、种子词、竞品名和竞品域名；行业判断给了英文品类词（category_en）就用它。"""
    brand_words = {w.lower() for name in [norm.get("brand_name", "")] + list(norm.get("brand_aliases") or [])
                   for w in _EN_WORD.findall(str(name))}
    product_line = str(norm.get("product_line") or "").strip()
    category = category_override.strip() or str(norm.get("category_label") or "").strip()
    if not category:
        # 产品线常写成「短名：规格说明」，规格里的型号会把种子词带偏（一家 GPU 云客户实测：取全文前 6 个英文词得到
        # 「gpu gpu instances nvidia rtx pro」，PAA 全是 4080 vs 4090、Reddit 选中联想笔记本帖）。只取冒号/分号前的短名，
        # 英文词去重后最多 4 个；短名里没有英文词再退回全文。
        head = re.split(r"[：:;；\n]", product_line, maxsplit=1)[0]
        def _pick(text: str) -> list[str]:
            seen, out = set(), []
            for w in _EN_WORD.findall(text):
                lw = w.lower()
                if lw in brand_words or lw in seen:
                    continue
                seen.add(lw)
                out.append(w)
            return out[:4]
        words = _pick(head) or _pick(product_line)
        while words and words[-1].lower() in _STOP:
            words.pop()
        category = " ".join(words) if words else product_line
    category = category.lower()
    cf = norm.get("case_fields") or {}
    first = str(cf.get("核心目标客户与购买场景 1") or "")
    crowd_part = re.split(r"[：:]", first, maxsplit=1)[0]
    crowd_part = re.split(r"[（(]", crowd_part, maxsplit=1)[0]  # 括号里多是角色说明（CTO / 决策人），不进种子词
    crowd_words = [w for w in _EN_WORD.findall(crowd_part) if w.lower() not in brand_words]
    # 人群写成中文、只夹着一个英文缩写（「AI 应用初创团队」）时拼不成英文人群词，不出这个种子
    crowd = " ".join(crowd_words).lower() if len(crowd_words) >= 2 else ""
    seeds = [f"best {category}"] + ([f"{category} for {crowd}"] if crowd else []) + [f"{category} recommendations"]
    comps = (norm.get("competitor_selection") or {}).get("formal_competitors") or []
    return {"category": category, "crowd": crowd, "seeds": list(dict.fromkeys(seeds)), "product_line": product_line,
            "competitors": [str(c.get("name") or "").strip() for c in comps if str(c.get("name") or "").strip()],
            "domains": list(dict.fromkeys(d for d in (_clean_domain(c.get("official_domain")) for c in comps) if d)),
            "category_words": [w.lower() for w in _EN_WORD.findall(category)
                               if len(w) >= 4 and w.lower() not in _STOP]}


def _run_script(ws: Path, args: list[str], timeout: float, log: Path) -> tuple[int | None, str, str]:
    """跑一个采集脚本；返回 (退出码，超时为 None；stdout；stderr)，原始输出追加进 log。"""
    env = dict(os.environ, **net_env(ws))
    cmd = [sys.executable, "-I", *args]
    try:
        p = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=max(1.0, timeout))
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        dec = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")  # noqa: E731
        rc, out, err = None, dec(exc.stdout), dec(exc.stderr)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"$ {' '.join(Path(a).name if i == 0 else a for i, a in enumerate(args))}\n"
                 f"[exit {rc if rc is not None else 'timeout'}]\n{out}\n{err}\n")
    return rc, out, err


def _read_signals(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if str(r.get("原话") or "").strip()]


def _write_signals(path: Path, rows: list[dict], extra: tuple[str, ...] = ()) -> None:
    fields = SIGNAL_FIELDS + [k for r in rows for k in r if k not in SIGNAL_FIELDS and k not in extra] + list(extra)
    fields = list(dict.fromkeys(fields))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _last_line(*texts: str) -> str:
    for text in texts:
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        if lines:
            return lines[-1][:300]
    return ""


def _collect_serp(ws: Path, terms: dict, market: str, locale: str, out: Path, log: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "seeds.txt").write_text("\n".join(terms["seeds"]) + "\n", encoding="utf-8")
    rc, so, se = _run_script(ws, [str(_scripts_dir(ws) / "collect_serp_signals.py"), "--seeds-file", str(out / "seeds.txt"),
                                  "--gl", market.lower(), "--hl", locale, "--out", str(out),
                                  "--product-line", terms["product_line"], "--id-prefix", "PS", "--timeout", "90"],
                             PRECOLLECT_TIMEOUT, log)
    rows = _read_signals(out / "signals.csv")
    try:
        failed = json.loads((out / "summary.json").read_text(encoding="utf-8")).get("failed_seeds") or []
    except (OSError, json.JSONDecodeError):
        failed = []
    note = "；".join(f"{f.get('seed')}：{f.get('error')}" for f in failed)[:400]
    if rc is None:
        why = f"超时（{PRECOLLECT_TIMEOUT} 秒）"
    elif rc not in (0, 1):
        why = f"collect_serp_signals.py 退出码 {rc}：{_last_line(se, so)}"
    else:
        why = note
    if rows:
        return {"status": "ok", "reason": (f"部分失败：{why}" if why else ""), "rows": len(rows)}
    return {"status": "failed" if (rc not in (0,) or failed) else "ok",
            "reason": why or "采集完成但 0 条", "rows": 0}


def _collector_targets(spec: dict, terms: dict, plan: dict, name: str) -> list[str]:
    kind = spec.get("targets")
    if kind == "competitor_domains":
        return list(terms["domains"])
    if kind == "category":
        return [terms["category"]] if terms["category"] else []
    if kind == "app_ids":
        return list((plan.get("app_ids") or {}).get(name) or [])
    if kind == "maps_queries":
        return list(plan.get("maps_queries") or [])
    return []


def _run_collector(ws: Path, name: str, spec: dict, targets: list[str], idx: int, terms: dict, market: str,
                   locale: str, out: Path, log: Path, budget: float) -> dict:
    """跑一个 collect_reviews.py 子命令；返回渠道结果（status、reason、rows）。"""
    out.mkdir(parents=True, exist_ok=True)
    collector = spec["collector"]
    # 每个任务顺序等结果，按任务数分摊这个渠道的时间、留 30 秒收尾；Google Shopping 每个搜索词是
    # 1 个商品搜索任务 + SHOPPING_PRODUCTS 个评价任务（2026-11-11 实测一个词 4 个任务要 10 分钟以上）
    tasks = len(targets) * (1 + SHOPPING_PRODUCTS if collector == "google-shopping" else 1)
    wait = max(45, min(300, int((budget - 30) / max(1, tasks))))
    args = [str(_scripts_dir(ws) / "collect_reviews.py"), collector, *targets, "--out", str(out),
            "--product-line", terms["product_line"], "--id-prefix", f"PR{idx}", "--wait", str(wait)]
    if collector == "trustpilot":
        args += ["--depth", str(REVIEW_DEPTH)]
    else:
        args += ["--country", market.lower(), "--lang", locale]
    if collector == "google-shopping":
        args += ["--products", str(SHOPPING_PRODUCTS)]
    # DataForSEO 评价任务排队慢（2026-11-11 Google Shopping 评价任务 5 分钟没出结果）；任务号存在 --out 里，
    # 主 agent 后面用同一条命令重跑会直接取结果、不再付费，所以把命令写下来
    rel = lambda a: os.path.relpath(a, ws) if a.startswith(str(ws)) else a  # noqa: E731
    w = args.index("--wait")
    rerun = "python3 " + " ".join(shlex.quote(rel(a)) for a in args[:w] + args[w + 2:]) + " --wait 600"
    (out / "rerun.txt").write_text(rerun + "\n", encoding="utf-8")
    rc, so, se = _run_script(ws, args, budget, log)
    rows = _read_signals(out / "signals.csv")
    try:
        failed = json.loads((out / "summary.json").read_text(encoding="utf-8")).get("failed") or []
    except (OSError, json.JSONDecodeError):
        failed = []
    note = "；".join(f"{f.get('target')}：{f.get('error')}" for f in failed)[:300]
    if rc is None:
        why = f"超时（{int(budget)} 秒）"
    elif rc == 2:  # Fatal：缺凭据、缺调用人等，整个渠道没采
        why = f"collect_reviews.py 停止：{_last_line(se, so).removeprefix('停止：')}"
    elif rc not in (0, 1):
        why = f"collect_reviews.py 退出码 {rc}：{_last_line(se, so)}"
    else:
        why = note
    if rc is None or "任务号" in why:
        why += f"；任务已提交，重跑 {(out / 'rerun.txt').relative_to(ws)} 里的命令取结果，不重复付费"
    if rows:
        return {"status": "ok", "reason": (f"部分失败：{why}" if why else ""), "rows": len(rows), "targets": targets}
    return {"status": "failed" if (rc != 0 or failed) else "ok", "reason": why or "采集完成但 0 条", "rows": 0,
            "targets": targets}


_LINK = re.compile(r"^\s+链接：(\S+)\s*$")
_FETCH_BLOCK = re.compile(r"^===== \d+/\d+ (\S+)\s*$")


def _page_text(block: str) -> str | None:
    """net.py fetch / render 一个页面的输出：第一行是「[来源] …」才算取到，正文在第一个空行之后。"""
    lines = block.strip("\n").splitlines()
    if not lines or not lines[0].startswith("[来源]"):
        return None
    text = "\n".join(lines[1:]).strip()
    return text or None


def _split_fetch(out: str, urls: list[str]) -> dict[str, str | None]:
    if len(urls) == 1:
        return {urls[0]: _page_text(out)}
    blocks: dict[str, list[str]] = {}
    cur = None
    for line in out.splitlines():
        m = _FETCH_BLOCK.match(line)
        if m:
            cur = m.group(1)
            blocks[cur] = []
        elif line.startswith("===== 共 "):
            cur = None
        elif cur is not None:
            blocks[cur].append(line)
    return {u: _page_text("\n".join(blocks.get(u) or [])) for u in urls}


def _site_queries(spec: dict, terms: dict, plan: dict) -> list[str]:
    """站内页搜索词：站名当普通关键词（Scrapeless 的 Google 搜索不认 site:，2026-11-11 实测 site:rtings.com
    返回的全是别的站；把「rtings」「pantip」写进词里，本站页面才排得上来）。竞品模式每个竞品一条，最多 2 条。"""
    kw = spec.get("keyword") or spec["site"].split(".")[0]
    mode = spec.get("query")
    if mode == "competitors" and terms["competitors"]:
        return [f"{kw} {c} reviews" for c in terms["competitors"][:2]]
    if mode == "local":
        return [f"{kw} {plan.get('local_query') or terms['category']}"]
    return [f"{kw} {terms['category']}"]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _on_site(url: str, site: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    name = site.split(".")[0]
    return host == site or host.endswith("." + site) or name in host.split(".")  # capterra.ca 这类同站别的国家域名也算


def _collect_site(ws: Path, name: str, spec: dict, terms: dict, plan: dict, market: str, locale: str,
                  pages_dir: Path, log: Path, budget: float) -> dict:
    """站内页渠道：先 site: 搜索拿真实页面网址，再取前 SITE_PAGES 页正文存进 pages/，原话由 agent 读后登记。"""
    deadline = time.time() + budget
    net = str(_scripts_dir(ws) / "net.py")
    site = spec["site"]
    queries = _site_queries(spec, terms, plan)
    comp_slugs = [_slug(c) for c in terms["competitors"] if len(_slug(c)) >= 3] if spec.get("query") == "competitors" else []
    urls, notes = [], []
    for q in queries:
        if time.time() >= deadline or len(urls) >= SITE_PAGES:
            break
        rc, so, se = _run_script(ws, [net, "search", q, "--gl", market.lower(), "--hl", locale],
                                 deadline - time.time(), log)
        if rc is None:
            notes.append(f"「{q}」超时")
            continue
        found = 0
        for line in so.splitlines():
            m = _LINK.match(line)
            if not m or not _on_site(m.group(1), site) or m.group(1) in urls:
                continue
            if spec.get("fetcher") == "pantip" and not re.search(r"pantip\.com/topic/\d+", m.group(1)):
                continue  # 只有帖子页有评论
            # 竞品模式：网址里要有竞品名，防止搜到名字相近的别家产品页
            if comp_slugs and not any(c in _slug(m.group(1)) for c in comp_slugs):
                continue
            urls.append(m.group(1))
            found += 1
        if not found:
            notes.append(f"「{q}」没有 {site} 的相关页面")
    urls = urls[:SITE_PAGES]
    if not urls:
        return {"status": "failed", "reason": "；".join(notes)[:300] or f"没有 {site} 的页面",
                "rows": 0, "pages": 0, "queries": queries}
    texts: dict[str, str | None] = {}
    if spec.get("fetcher") == "pantip":
        # Pantip 评论是页面加载后另行请求的（3.6.2）：net.py pantip 调评论接口，直连不通（境内模式）时经 Scrapeless 渲染，不需要本机 Chrome
        for u in urls:
            if time.time() >= deadline:
                texts[u] = None
                continue
            rc, so, se = _run_script(ws, [net, "pantip", u, "--country", market.upper()], deadline - time.time(), log)
            texts[u] = _page_text(so) if rc is not None else None
    elif spec.get("render"):
        for u in urls:
            if time.time() >= deadline:
                texts[u] = None
                continue
            rc, so, se = _run_script(ws, [net, "render", u, "--country", market.upper()], deadline - time.time(), log)
            texts[u] = _page_text(so) if rc is not None else None
    else:
        rc, so, se = _run_script(ws, [net, "fetch", *urls, "--country", market.upper()], deadline - time.time(), log)
        texts = _split_fetch(so, urls) if rc is not None else dict.fromkeys(urls)
    pages_dir.mkdir(parents=True, exist_ok=True)
    saved, bad = [], []
    for u in urls:
        t = texts.get(u)
        if not t or len(t) < 500:
            bad.append(u)
            continue
        f = pages_dir / f"{name}-{len(saved) + 1}.txt"
        f.write_text(f"URL: {u}\n渠道: {name}\n\n{t[:30000]}\n", encoding="utf-8")
        saved.append(str(f.relative_to(ws)))
    reason = f"读不到或正文太短：{'、'.join(bad)}" if bad else ""
    return {"status": "ok" if saved else "failed", "reason": reason or ("" if saved else "页面都没取到"),
            "rows": 0, "pages": len(saved), "files": saved, "queries": queries}


def _merge_channel_rows(out: Path, subdirs: list[Path]) -> int:
    rows, seen = [], set()
    for d in subdirs:
        for r in _read_signals(d / "signals.csv"):
            k = " ".join(str(r.get("原话") or "").split()).lower()
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    out.mkdir(parents=True, exist_ok=True)
    _write_signals(out / "signals.csv", rows)
    return len(rows)


def _run_one_channel(ws: Path, c: dict, idx: int, terms: dict, plan: dict, market: str, locale: str, out: Path,
                     log: Path, budget: float) -> tuple[dict, Path | None]:
    name, spec = c["name"], c.get("spec") or {}
    log = log.with_name(f"{log.stem}-{name}.txt")
    sub = out / name
    try:
        if spec.get("collector"):
            targets = _collector_targets(spec, terms, plan, name)
            if not targets:
                return {"status": "skipped", "reason": f"没有可采的对象（{spec.get('targets')}为空）", "rows": 0}, None
            return _run_collector(ws, name, spec, targets, idx, terms, market, locale, sub, log, budget), sub
        if spec.get("site"):
            return _collect_site(ws, name, spec, terms, plan, market, locale, ws / PRECOLLECT_DIR / "pages", log,
                                 budget), None
        if spec.get("kind") == "reddit":
            return _collect_reddit(ws, terms, plan, sub, log, budget), sub
        if spec.get("kind") == "hackernews":
            return _collect_hn(ws, terms, plan, sub, log, budget), sub
        return {"status": "failed", "reason": f"渠道表里「{name}」没有采集方式", "rows": 0}, None
    except Exception as exc:  # noqa: BLE001 - 一个渠道出错不影响别的渠道
        return {"status": "failed", "reason": f"{type(exc).__name__}: {str(exc)[:200]}", "rows": 0}, sub


def _run_channels(ws: Path, category: str, terms: dict, plan: dict, market: str, locale: str, out: Path,
                  log: Path) -> dict:
    """按计划跑一类（评价或社区）的全部渠道：渠道之间并行（各自打不同的站），每个渠道都有这一类的整段时间，
    单独记结果和日志（logs/precollect-<类>-<渠道>.txt）。"""
    chans = [c for c in plan.get("channels") or [] if c["category"] == category]
    if not chans:
        return {"status": "skipped", "rows": 0, "pages": 0, "channels": [],
                "reason": f"行业「{plan.get('industry')}」× 市场「{plan.get('market')}」在渠道表里没有{category}渠道"}
    out.mkdir(parents=True, exist_ok=True)
    budget = CATEGORY_TIMEOUT.get(category, PRECOLLECT_TIMEOUT)
    todo = [(i, c) for i, c in enumerate(chans, 1) if c["status"] != "skipped"]
    done: dict[str, tuple[dict, Path | None]] = {}
    with ThreadPoolExecutor(max(1, len(todo))) as ex:
        futs = {c["name"]: ex.submit(_run_one_channel, ws, c, i, terms, plan, market, locale, out, log, budget)
                for i, c in todo}
        for name, fut in futs.items():
            done[name] = fut.result()
    results, subdirs = [], []
    for c in chans:
        res = {"name": c["name"], "from": c.get("from", "")}
        if c["status"] == "skipped":
            results.append({**res, "status": "skipped", "reason": c.get("reason") or "计划里跳过", "rows": 0})
            continue
        r, sub = done[c["name"]]
        results.append({**res, **r})
        if sub is not None:
            subdirs.append(sub)
    rows = _merge_channel_rows(out, subdirs)
    pages = sum(int(r.get("pages") or 0) for r in results)
    (out / "summary.json").write_text(json.dumps({"channels": results}, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    brief = "；".join(f"{r['name']} {r['status']}" + (f"（{r['reason']}）" if r.get("reason") and r["status"] != "ok" else "")
                     for r in results)[:1200]
    status = "ok" if (rows or pages) else ("skipped" if all(r["status"] == "skipped" for r in results) else "failed")
    return {"status": status, "reason": brief, "rows": rows, "pages": pages, "channels": results}


def _collect_reviews(ws: Path, terms: dict, market: str, locale: str, out: Path, log: Path, plan: dict) -> dict:
    return _run_channels(ws, "评价", terms, plan, market, locale, out, log)


def _collect_community(ws: Path, terms: dict, market: str, locale: str, out: Path, log: Path, plan: dict) -> dict:
    return _run_channels(ws, "社区", terms, plan, market, locale, out, log)


_REDDIT_HEAD = re.compile(r"^(\d+)\. \[(帖子|评论|版块)\] ?(.*)$")
_REDDIT_META = re.compile(r"^   (.*?) · (\S*) · (\S*)\s*$")
# 网页版（net.py reddit --proxy）多一个点赞数：作者 · 12 赞 · 日期 · 链接
_REDDIT_META_SCORE = re.compile(r"^   (.*?) · (\S*) 赞 · (\S*) · (\S*)\s*$")
_SUBMITTED = re.compile(r"\s*submitted by\s+/u/\S+(\s+to\s+r/\S+)?\s*$")


def parse_reddit_output(text: str) -> tuple[list[dict], str]:
    """解析 net.py reddit 的文本输出（每条：「n. [类别] 标题」、「   作者 · 日期 · 链接」、正文若干行）。
    返回 (条目, 出错说明)；没有「[来源]」行就是没取到，出错说明取 net.py 打印的「读不到」那一行。"""
    if "[来源]" not in text:
        bad = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("读不到")]
        return [], (bad[-1] if bad else _last_line(text) or "net.py reddit 没有输出")
    items: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = _REDDIT_HEAD.match(line)
        if m:
            cur = {"kind": m.group(2), "title": m.group(3).strip(), "author": "", "date": "", "url": "", "score": "",
                   "body": [], "meta": False}
            items.append(cur)
            continue
        if cur is None:
            continue
        if not cur["meta"]:
            ms = _REDDIT_META_SCORE.match(line)
            mm = None if ms else _REDDIT_META.match(line)
            if ms:
                cur.update(author=ms.group(1).strip(), score=ms.group(2), date=ms.group(3), url=ms.group(4), meta=True)
            elif mm:
                cur.update(author=mm.group(1).strip(), date=mm.group(2), url=mm.group(3), meta=True)
            continue
        cur["body"].append(line[3:] if line.startswith("   ") else line)
    for it in items:
        it["body"] = _SUBMITTED.sub("", "\n".join(it.pop("body")).strip()).strip()
        it.pop("meta")
    return items, ""


def _thread_key(url: str) -> str:
    m = re.search(r"/r/([^/]+)/comments/([^/]+)", url)
    return f"{m.group(1).lower()}/{m.group(2)}" if m else url


def _subreddit(url: str) -> str:
    m = re.search(r"/r/([^/]+)/", url)
    return f"r/{m.group(1)}" if m else "r/?"


def _collect_reddit(ws: Path, terms: dict, plan: dict, out: Path, log: Path, budget: float) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    try:
        total_max = int(os.environ.get("NET_REDDIT_MAX", "10"))
    except ValueError:
        total_max = 10
    share = min(PRECOLLECT_REDDIT_CAP, total_max // 2)
    if share < 2:
        return {"status": "skipped", "reason": f"NET_REDDIT_MAX={total_max}，不够 precollect 分（至少要 4 次）", "rows": 0}
    searches = 2 if share >= 5 else 1
    deadline = time.time() + budget
    net = str(_scripts_dir(ws) / "net.py")
    # 只用品类词搜，泛词（gpu、instances）会搜进无关版块（一家 GPU 云客户实测命中 r/godot 游戏渲染帖）。
    # 买家比较竞品的帖子最对口，先拿竞品名拼一条，再补一条品类推荐问法。
    comps = terms["competitors"][:3]
    vs_query = " vs ".join(comps) if len(comps) >= 2 else (f"{comps[0]} alternative" if comps else "")
    queries = list(dict.fromkeys(q for q in [*(plan.get("reddit_queries") or []), vs_query, f"best {terms['category']}",
                                             terms["category"]] if q))[:searches]
    calls, problems, candidates = 0, [], {}
    for q in queries:
        if time.time() >= deadline:
            problems.append(f"搜索「{q}」：时间用完")
            break
        calls += 1
        rc, so, se = _run_script(ws, [net, "reddit", q, "--limit", "15"], deadline - time.time(), log)
        items, err = parse_reddit_output(so)
        if rc is None or err or not any(it["kind"] == "帖子" for it in items):
            # Reddit 自己的搜索经代理也被拦、RSS 又 403 时（2026-11-11 本机两天都这样）用 Google 搜「reddit <词>」拿帖子链接
            rss_why = "超时" if rc is None else (err or "没有帖子")
            gl = str(plan.get("market") or "US").lower()
            rc2, so2, se2 = _run_script(ws, [net, "search", f"reddit {q}", "--gl", gl, "--hl", "en"],
                                        deadline - time.time(), log)
            links = list(dict.fromkeys(m.group(1) for line in (so2 or "").splitlines()
                                       if (m := _LINK.match(line)) and "/comments/" in m.group(1)))
            # 标题和正文都没有，出处只有 URL；用 URL 里的版块名和标题 slug 判相关性
            items = [{"kind": "帖子", "title": "", "author": "", "date": "", "url": u, "body": "",
                      "from_search": True} for u in links]
            if links:
                problems.append(f"搜索「{q}」：RSS {rss_why}，改用 Google 搜到 {len(links)} 个帖子")
            else:
                problems.append(f"搜索「{q}」：RSS {rss_why}，Google 也没搜到帖子链接"
                                f"（{'超时' if rc2 is None else _last_line(so2, se2)[:120] or '无结果'}）")
                continue
        for it in items:
            if it["kind"] != "帖子" or "/comments/" not in it["url"]:
                continue
            title = (it["title"] or re.sub(r"[-/_?=&]", " ", it["url"])).lower()
            body = it["body"].lower()
            hit_words = {w for w in terms["category_words"] if w in title or w in body}
            hit_comps = {c for c in terms["competitors"] if c.lower() in title or c.lower() in body}
            score = sum(2 * (w in title) + (w in body) for w in hit_words) + 3 * len(hit_comps)
            key = _thread_key(it["url"])
            # 至少提到一个竞品，或命中两个以上不同的品类词；只撞上一个泛词（gpu）不算相关。
            # Google 搜出来的帖子只有 URL，主题相关性由 Google 的排序负责，撞上一个品类词就算
            relevant = bool(hit_comps) or len(hit_words) >= 2 or (it.get("from_search") and bool(hit_words))
            if relevant and (key not in candidates or candidates[key][0] < score):
                candidates[key] = (score, it["url"], len(candidates))
    picked = sorted(candidates.values(), key=lambda x: (-x[0], x[2]))[:min(3, share - calls)]
    proxy_pages, proxy_used = PRECOLLECT_PROXY_PAGES, []
    rows: list[dict] = []
    for _, url, _ in picked:
        if time.time() >= deadline:
            problems.append(f"{url}：时间用完")
            break
        calls += 1
        rc, so, se = _run_script(ws, [net, "reddit", url, "--limit", "40"], deadline - time.time(), log)
        items, err = parse_reddit_output(so)
        if rc is None or err or not items:
            if proxy_pages > 0 and time.time() < deadline:
                proxy_pages -= 1
                reason = "超时" if rc is None else (err or "没有评论")
                rc, so, se = _run_script(ws, [net, "reddit", url, "--proxy"], deadline - time.time(), log)
                items, err = parse_reddit_output(so)
                if rc is not None and not err and items:
                    proxy_used.append(url)
                    problems.append(f"{url}：RSS {reason}，改用网页版")
                else:
                    problems.append(f"{url}：RSS {reason}，网页版也失败（{'超时' if rc is None else err}）")
                    continue
            else:
                problems.append(f"{url}：{'超时' if rc is None else err or '没有评论'}"
                                + (f"；网页版额度已用完（{PRECOLLECT_PROXY_PAGES} 帖）" if proxy_pages <= 0 else ""))
                continue
        comments = 0
        for it in items:
            is_post = it["kind"] == "帖子"
            if not is_post:
                if comments >= 40:
                    break
                comments += 1
            text = (f"{it['title']}\n{it['body']}" if is_post else it["body"]).strip()
            if not text or text in ("[deleted]", "[removed]") or it["author"].endswith("/AutoModerator"):
                continue
            link = it["url"] or url
            row = dict.fromkeys(SIGNAL_FIELDS, "")
            row.update({"产品线": terms["product_line"], "来源类型": "社区", "原话": text[:3000],
                        "出处": f"Reddit {_subreddit(link)} {it['date'] or '日期未知'}，{link}"})
            rows.append(row)
    seen, uniq = set(), []
    for r in rows:
        k = r["原话"].strip().lower()
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    for i, r in enumerate(uniq, 1):
        r["输入编号"] = f"PC{i:03d}"
    _write_signals(out / "signals.csv", uniq)
    (out / "summary.json").write_text(json.dumps({"queries": queries, "threads": [u for _, u, _ in picked],
                                                  "reddit_calls": calls, "reddit_cap": share, "rows": len(uniq),
                                                  "proxy_pages": proxy_used, "proxy_note": "网页版评论只有顶层、没有折叠回复和主帖正文",
                                                  "problems": problems}, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    note = f"Reddit 请求 {calls} 次（precollect 上限 {share}）" + (f"，网页版 {len(proxy_used)} 帖" if proxy_used else "")
    if uniq:
        return {"status": "ok", "reason": note + (f"；部分失败：{'；'.join(problems)[:800]}" if problems else ""),
                "rows": len(uniq), "proxy_pages": proxy_used}
    if not picked and not problems:
        why = f"搜索 {', '.join(queries)} 没有标题或正文含品类词、竞品名的帖子"
    else:
        why = "；".join(problems)[:400] or "帖子读到了但没有可用正文"
    return {"status": "failed", "reason": f"{note}；{why}"[:800], "rows": 0, "proxy_pages": proxy_used}


def _relevant(text: str, terms: dict) -> bool:
    low = text.lower()
    return any(c.lower() in low for c in terms["competitors"]) or \
        len({w for w in terms["category_words"] if w in low}) >= 2


def _collect_hn(ws: Path, terms: dict, plan: dict, out: Path, log: Path, budget: float) -> dict:
    """Hacker News：Algolia 接口取评论全文（net.py fetch --raw，直连免费），只留提到竞品或两个以上品类词的评论。"""
    out.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + budget
    net = str(_scripts_dir(ws) / "net.py")
    queries = (plan.get("hn_queries") or terms["competitors"][:3] or [terms["category"]])[:3]
    rows, problems = [], []
    for q in queries:
        if time.time() >= deadline:
            problems.append(f"「{q}」：时间用完")
            break
        url = (f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=comment"
               f"&hitsPerPage={HN_HITS}")
        rc, so, se = _run_script(ws, [net, "fetch", url, "--raw", "--country", "US"], deadline - time.time(), log)
        body = _page_text(so) if rc is not None else None
        try:
            hits = json.loads(body[body.index("{"):])["hits"] if body else None
        except (ValueError, KeyError, TypeError):
            hits = None
        if hits is None:
            problems.append(f"「{q}」：{'超时' if rc is None else _last_line(so, se)[:120] or '没有取到 JSON'}")
            continue
        for h in hits:
            text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<p>", "\n", str(h.get("comment_text") or ""))))
            text = re.sub(r"[ \t]+", " ", text).strip()
            if len(text) < 40 or not _relevant(text, terms):
                continue
            row = dict.fromkeys(SIGNAL_FIELDS, "")
            story = str(h.get("story_title") or "").strip()
            row.update({"产品线": terms["product_line"], "来源类型": "社区", "原话": text[:3000],
                        "出处": f"Hacker News{f'「{story}」' if story else ''} {str(h.get('created_at') or '')[:10] or '日期未知'}，"
                                f"https://news.ycombinator.com/item?id={h.get('objectID')}"})
            rows.append(row)
    for i, r in enumerate(rows, 1):
        r["输入编号"] = f"PH{i:03d}"
    _write_signals(out / "signals.csv", rows)
    if rows:
        return {"status": "ok", "reason": f"部分失败：{'；'.join(problems)[:300]}" if problems else "", "rows": len(rows),
                "queries": queries}
    return {"status": "failed", "rows": 0, "queries": queries,
            "reason": "；".join(problems)[:300] or f"搜索 {queries} 没有提到竞品或品类词的评论"}


def precollect(ws: Path) -> dict:
    """agent 启动前跑三类采集。每类单独 try，失败只记原因；写 summary.json 与合并的 signals.csv。"""
    root = ws / PRECOLLECT_DIR
    root.mkdir(parents=True, exist_ok=True)
    prior = json.loads((ws / "out/result.json").read_text(encoding="utf-8")) if (ws / "out/result.json").exists() else {}
    market, locale = prior.get("market", ""), prior.get("locale", "") or "en"
    norm = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]
    plan = load_plan(ws)
    terms = precollect_terms(norm, plan.get("category_en") or "")
    collectors = {"搜索联想": _collect_serp, "评价": _collect_reviews, "社区": _collect_community}
    cats: dict[str, dict] = {}
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    def run_cat(cat: str, fn) -> dict:
        sub = PRECOLLECT_CATEGORIES[cat]
        started = time.time()
        try:
            args = (ws, terms, market, locale, root / sub, ws / f"logs/precollect-{sub}.txt")
            info = fn(*args) if cat == "搜索联想" else fn(*args, plan)
        except Exception as exc:  # noqa: BLE001 - 一类出错不影响其他类和 agent
            info = {"status": "failed", "reason": f"{type(exc).__name__}: {str(exc)[:300]}", "rows": 0}
        info["secs"] = round(time.time() - started, 1)
        return info

    # 三类打的是不同服务（Scrapeless 搜索、DataForSEO、Reddit / 各站），并行跑
    with ThreadPoolExecutor(len(collectors)) as ex:
        futs = {cat: ex.submit(run_cat, cat, fn) for cat, fn in collectors.items()}
        infos = {cat: f.result() for cat, f in futs.items()}
    for cat in collectors:
        info, out = infos[cat], root / PRECOLLECT_CATEGORIES[cat]
        rows = 0
        if info["status"] == "ok":
            for r in _read_signals(out / "signals.csv"):
                key = (cat, " ".join(str(r.get("原话") or "").split()).lower())
                if key in seen:
                    continue
                seen.add(key)
                merged.append({**r, "采集类别": cat})
                rows += 1
        info["rows"] = rows
        info.setdefault("pages", 0)
        info["out_dir"] = str(out.relative_to(ws))
        cats[cat] = info
    _write_signals(root / "signals.csv", merged, extra=("采集类别",))
    summary = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "industry": plan.get("industry"), "industry_basis": plan.get("industry_basis"),
               "plan_source": plan.get("source"), "plan": f"{PRECOLLECT_DIR}/plan-checked.json",
               "pages_dir": f"{PRECOLLECT_DIR}/pages", "terms": {k: terms[k] for k in
               ("category", "crowd", "seeds", "competitors", "domains")},
               "categories": cats, "total_rows": len(merged), "signals_csv": f"{PRECOLLECT_DIR}/signals.csv"}
    write_json(root / "summary.json", summary)
    if (ws / "out/result.json").exists():
        prior["precollect"] = precollect_block(ws)
        write_json(ws / "out/result.json", prior)
    return summary


def precollect_block(ws: Path) -> dict | None:
    """result.json 里的 precollect 块：每类状态、原因、行数。没跑过 precollect 返回 None。"""
    try:
        s = json.loads((ws / PRECOLLECT_DIR / "summary.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {"industry": s.get("industry"), "plan_source": s.get("plan_source"),
            "categories": {c: {k: v.get(k) for k in ("status", "reason", "rows", "pages")}
                           for c, v in (s.get("categories") or {}).items()},
            "total_rows": s.get("total_rows", 0), "signals_csv": s.get("signals_csv", "")}


def _uncovered_section(ws: Path) -> str:
    """notes.md「未覆盖来源」一节的文本：从含这几个字的那一行起，到下一个 Markdown 标题为止。"""
    try:
        lines = (ws / "out/notes.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    out, inside = [], False
    for line in lines:
        if "未覆盖来源" in line and not inside:
            inside = True
            out.append(line.split("未覆盖来源", 1)[1])
            continue
        if inside:
            if line.lstrip().startswith("#"):
                break
            out.append(line)
    return "\n".join(out)


def precollect_registration_errors(ws: Path) -> list[str]:
    """登记检查：precollect 采到（ok 且 ≥1 条）的类别，buyer_quotes 里至少要有 1 条同来源类型的信号，
    或 notes.md「未覆盖来源」写了这一类。返回缺登记的报错；没跑过 precollect 或题库读不了返回 []。"""
    try:
        summary = json.loads((ws / PRECOLLECT_DIR / "summary.json").read_text(encoding="utf-8"))
        bank = json.loads((ws / "out/bank.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    quotes = [q for q in ((bank.get("config") or {}).get("buyer_quotes") or []) if isinstance(q, dict)]
    norm = lambda s: " ".join(str(s or "").split()).lower()  # noqa: E731
    texts: dict[str, set[str]] = {}
    for r in _read_signals(ws / PRECOLLECT_DIR / "signals.csv"):
        texts.setdefault(str(r.get("采集类别") or ""), set()).add(norm(r.get("原话")))
    uncovered = _uncovered_section(ws)
    errors = []
    for cat, info in (summary.get("categories") or {}).items():
        n, pages = int(info.get("rows") or 0), int(info.get("pages") or 0)
        if info.get("status") != "ok" or n + pages < 1:
            continue
        hit = any(str(q.get("来源类型") or "").strip() == cat or norm(q.get("原话")) in texts.get(cat, set())
                  for q in quotes)
        if hit or cat in uncovered:
            continue
        got = f"{n} 条" + (f"、页面 {pages} 个" if pages else "")
        where = "research/precollect/signals.csv" + ("和 research/precollect/pages/" if pages else "")
        errors.append(f"research/precollect/ 里已采到 {cat} {got}，buyer_quotes 里一条没有；读 "
                      f"{where} 把相关的登记进去，或在 notes.md『未覆盖来源』说明为什么这一类"
                      f"全部与本产品线无关（只需补登记或说明，不要为这条删题）")
    return errors
