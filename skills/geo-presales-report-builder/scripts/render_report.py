"""把 build_report_data.py 产出的 report-data.json 渲染成单文件 HTML 报告。

用法：
    python3 render_report.py --data report-data.json --out report.html

样式与交互分别来自 assets/report.css、assets/report-extra.css、assets/report.js，
全部内联进最终 HTML，产出与原型一致的单文件、无外部依赖（favicon 除外）报告。
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# 模块顺序；购物商品卡、情感没有数据时整块不出，其余按顺序编号（Suda 2026-11-07：内容规划去掉）
SECTION_ORDER = [
    ("overview", "核心洞察", "核心洞察"),
    ("competition", "可见度", "可见度"),
    ("shopping", "购物商品卡", "商品卡"),
    ("sources", "引用", "引用"),
    ("distribution", "情感", "情感"),
    ("records", "问题明细", "明细"),
]


def sentiment_enabled(meta: dict) -> bool:
    """情感模块开不开：判读完成（sentiment_claims_status = complete）且整份报告至少有一条正负信号。
    slim_for_html 会按数据算好写进 meta.sentiment_enabled；没算过时退回只看状态。"""
    if "sentiment_enabled" in meta:
        return bool(meta["sentiment_enabled"])
    return meta.get("sentiment_claims_status") == "complete"


def sections_for(meta: dict) -> list[tuple[str, str, str, str]]:
    """(编号, id, 标题, 导航名)。"""
    shown = []
    for section_id, title, nav in SECTION_ORDER:
        if section_id == "shopping" and not (meta.get("shopping") or {}).get("enabled"):
            continue
        if section_id == "distribution" and not sentiment_enabled(meta):
            continue
        shown.append((section_id, title, nav))
    out, n = [], 0
    for section_id, title, nav in shown:
        if section_id == "records":
            out.append(("附录", section_id, title, nav))
        else:
            n += 1
            out.append((f"{n:02d}", section_id, title, nav))
    return out

KPI_TIPS = [
    ("提及率", "提到监测对象的回答 ÷ 有效回答。默认统计发现、替代类问题，筛选意图类型后按所选类型统计。"),
    ("提及率排名", "按提及率由高到低在当前品牌集合中的位置。"),
    ("声量份额", "监测对象提及量 ÷ 全部纳入品牌的提及量之和。"),
    ("平均提及位置", "监测对象被提及时的平均位置。数值越小，表示位置越靠前。"),
    ("引用份额", "指向监测对象官网的引用记录数 ÷ 全部引用记录数。"),
    ("引用率", "正文至少引用一次监测对象官网的回答 ÷ 有效回答。"),
]


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def favicon(domain: str) -> str:
    host = urlsplit(domain if "//" in domain else f"//{domain}").netloc or domain
    host = host.split("/")[0]
    return f"https://favicone.com/{host}?s=64"


def kpi_row() -> str:
    cells = []
    for label, tip in KPI_TIPS:
        cells.append(
            '<div class="kpi"><span class="label">'
            f'{esc(label)}<button type="button" class="info" aria-label="查看{esc(label)}含义" '
            f'data-tip="{esc(tip)}">i</button></span>'
            '<strong class="value">—</strong></div>'
        )
    return '<div class="kpis" id="overviewKpis">' + "".join(cells) + "</div>"


def section_head(number: str, title: str, section_id: str = "") -> str:
    # 右侧写本模块统计哪几类意图（report.js renderScopes 按筛选填）
    scope = f'<span class="section-scope" id="scope-{esc(section_id)}"></span>' if section_id else ""
    return (
        '<div class="section-head"><div class="section-title">'
        f'<span class="section-no">{esc(number)}</span><h2>{esc(title)}</h2>'
        "</div>" + scope + "</div>"
    )


def panel(title: str, body_id: str, extra_class: str = "", head_extra: str = "") -> str:
    return (
        f'<article class="panel {extra_class}">'
        f'<div class="panel-head"><h3>{esc(title)}</h3>{head_extra}</div>'
        f'<div class="panel-body" id="{body_id}"></div></article>'
    )


def insight_note(label: str, body_id: str, accent: str = "") -> str:
    style = f' style="border-left-color:var(--{accent})"' if accent else ""
    return (
        f'<div class="insight-note"{style}>'
        f'<span class="insight-label">{esc(label)}</span>'
        f'<div class="insight-copy" id="{body_id}"></div></div>'
    )


def build_body(meta: dict) -> str:
    brand = esc(meta.get("brand", ""))

    masthead = (
        '<div class="masthead"><div class="shell masthead-inner">'
        f'<p class="eyebrow" id="reportEyebrow">GEO Presales Diagnosis · {esc(meta.get("generated_at", ""))}</p>'
        f'<div class="title-row"><div><h1 id="reportTitle">{brand}<span>海外 AI 搜索可见度售前诊断</span></h1></div></div>'
        "</div></div>"
    )

    shared_filter = (
        '<div class="shared-filter" id="sharedFilter" aria-label="数据筛选">'
        '<div class="shared-filter-head"><strong>数据筛选</strong>'
        '<span id="filterScope"></span></div>'
        '<div style="display:grid;gap:12px">'
        '<div class="filter-selects">'
        '<select id="regionSelect" aria-label="地区筛选"></select>'
        '<select id="platformSelect" aria-label="平台筛选"></select>'
        '<select id="intentSelect" aria-label="意图类型筛选"></select>'
        '<select id="topicSelect" aria-label="主题筛选"></select>'
        "</div>"
        "</div></div>"
    )

    matrix_switch = (
        '<span class="matrix-switch">'
        '<button type="button" class="active" data-matrix-metric="mention">提及率</button>'
        '<button type="button" data-matrix-metric="share">声量份额</button>'
        '<button type="button" data-matrix-metric="rank">平均提及位置</button>'
        "</span>"
    )

    share_badge = (
        '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:999px;'
        'background:rgba(192,90,54,.1);border:1px solid rgba(192,90,54,.22);font-size:11px;line-height:1;color:var(--muted)" '
        'id="sourceShareBadge">引用份额 <b style="color:var(--gold-deep);font:700 18px/1 var(--serif);margin-left:1px">—</b></span>'
    )

    sections = sections_for(meta)
    parts = [shared_filter]
    for number, section_id, title, _nav in sections:
        body = [section_head(number, title, section_id)]
        if section_id == "overview":
            body.append('<div class="section-body">')
            body.append(kpi_row())
            body.append(
                insight_note("结论", "overviewInsight")
            )
            body.append("</div>")
        elif section_id == "competition":
            body.append('<div class="section-body">')
            body.append(
                '<article class="panel"><div class="panel-head"><h3>提及率</h3></div>'
                '<div class="panel-body"><div class="bar-list compare-bars" id="competitionMentions"></div></div></article>'
            )
            body.append(
                '<div class="grid-2" style="gap:20px;margin-top:20px">'
                + panel("声量份额", "competitionShare", "donut-panel")
                + '<article class="panel average-rank-panel"><div class="panel-head"><h3>平均提及位置</h3></div>'
                '<div class="panel-body"><div class="rankdots" id="competitionRank"></div></div></article>'
                + "</div>"
            )
            body.append(
                '<article class="panel matrix-panel" id="platform-matrix" style="margin-top:20px">'
                '<div class="panel-head"><h3>平台 × 品牌矩阵</h3>' + matrix_switch + "</div>"
                '<div class="panel-body"><div class="matrix-wrap">'
                '<table class="matrix" id="platformMatrix" aria-label="各平台下品牌与竞品的指标矩阵"></table>'
                "</div></div></article>"
            )
            body.append(insight_note("结论", "competitionInsight"))
            body.append("</div>")
        elif section_id == "shopping":
            # 三个指标是主体，品牌 / SKU 是切换（2026-11-07 Suda）
            def shop_panel(title: str, tip: str, table_id: str) -> str:
                return (
                    '<article class="panel matrix-panel shop-metric" style="margin-top:20px"><div class="panel-head">'
                    f'<h3>{esc(title)}<span class="info" data-tip="{esc(tip)}">i</span></h3></div>'
                    '<div class="panel-body"><div class="matrix-wrap">'
                    f'<table class="matrix shop-table" id="{table_id}"></table>'
                    "</div></div></article>"
                )
            body.append('<div class="section-body">')
            body.append(
                '<div class="shop-top"><div class="kpis shop-kpis" id="shoppingCore"></div>'
                '<span class="matrix-switch" id="shopLevelSwitch">'
                '<button type="button" class="active" data-shop-level="brand">品牌</button>'
                '<button type="button" data-shop-level="sku">SKU</button>'
                "</span></div>"
            )
            body.append(shop_panel("商品卡提及率", "出现商品卡的回答里，有该品牌（SKU）商品卡的回答占比。只数商品卡，不含正文提及。", "shopVis"))
            body.append(shop_panel("商品卡平均位置", "该品牌（SKU）商品卡在每条回答里最靠前那张的位置取平均，数值越小越靠前。", "shopPos"))
            # offers 没返回时不出这一栏：全是 0% 是采集缺口，不是品牌表现（2026-11-11 Obrand）
            if meta.get("shopping_offers_returned", True):
                body.append(shop_panel("官网购买链接覆盖率", "出现该品牌（SKU）商品卡的回答里，商品卡带官网购买链接的回答占比。", "shopLink"))
            body.append("</div>")
        elif section_id == "sources":
            body.append('<div class="section-body">')
            body.append(
                '<div class="grid-2" style="gap:20px">'
                + '<article class="panel"><div class="panel-head"><h3>官网引用页面</h3>' + share_badge + '</div>'
                + '<div class="panel-body">'
                + '<div class="page-list" id="officialPages">'
                + '<div class="page-head"><span>页面</span><span>引用份额</span></div>'
                + "</div>"
                + '<div class="pagination" id="officialPagesPager" aria-label="官网引用页面分页" hidden></div>'
                + "</div></article>"
                + '<article class="panel"><div class="panel-head"><h3>引用来源类别</h3></div>'
                + '<div class="panel-body"><div class="bar-list source-type-list" id="sourceTypes"></div></div></article>'
                + "</div>"
            )
            body.append(
                '<div class="grid-2" style="gap:20px;margin-top:20px">'
                + '<article class="panel"><div class="panel-head"><h3>热门引用域名</h3></div>'
                + '<div class="panel-body">'
                + '<div class="source-head with-cat"><span>域名</span><span>类别</span><span>引用份额</span></div>'
                + '<div class="domain-list" id="sourceDomains"></div>'
                + '<div class="pagination" id="sourceDomainsPager" aria-label="引用域名分页" hidden></div>'
                + "</div></article>"
                + '<article class="panel"><div class="panel-head"><h3>热门引用页面</h3></div>'
                + '<div class="panel-body">'
                + '<div class="page-list has-mention cat" id="sourcePages">'
                + '<div class="page-head"><span>页面</span><span>类别</span><span>页面中提及</span><span>引用份额</span></div>'
                + "</div>"
                + '<div class="pagination" id="sourcePagesPager" aria-label="引用页面分页" hidden></div>'
                + "</div></article>"
                + "</div>"
            )
            body.append(insight_note("结论", "sourcesInsight"))
            body.append("</div>")
        elif section_id == "distribution":
            body.append('<div class="section-body">')
            body.append(
                '<div class="sentiment-board">'
                '<div class="sentiment-overview" id="sentimentRates"></div>'
                '<div class="sentiment-evidence-card" id="sentimentEvidence"></div>'
                "</div>"
            )
            body.append(
                '<article class="panel" style="margin-top:20px">'
                '<div class="panel-head"><h3>竞品情感占比</h3>'
                '<span class="tag">正向情感占比</span></div>'
                '<div class="panel-body"><div id="sentimentOverviewBars"></div></div></article>'
            )
            body.append(
                '<article class="panel" style="margin-top:20px">'
                '<div class="panel-head"><h3>竞品情感矩阵</h3></div>'
                '<div class="panel-body"><div class="table-wrap" style="padding:0;border:0;box-shadow:none">'
                '<table class="attribute-matrix theme-matrix" id="sentimentMatrix"></table>'
                "</div></div></article>"
            )
            body.append("</div>")
        elif section_id == "records":
            body.append('<div class="section-body">')
            body.append(
                '<div class="records-toolbar">'
                '<input class="records-search" id="recordSearch" type="search" placeholder="搜索编号或问题（中英文）" aria-label="搜索问题">'
                '</div>'
                '<div class="table-wrap records">'
                '<table class="records-table" id="recordTable" style="min-width:1080px"></table>'
                "</div>"
                '<div class="pagination" id="recordPagination" aria-label="问题明细分页" hidden></div>'
            )
            body.append("</div>")
        parts.append(f'<section class="section" id="{section_id}">' + "".join(body) + "</section>")

    nav = "".join(f'<a href="#{sid}">{esc(label)}</a>' for _n, sid, _t, label in sections)

    shell = (
        '<body class="formal-report">'
        '<a class="skip" href="#main">跳到主要内容</a>'
        '<header class="topbar"><div class="shell topbar-inner">'
        '<div class="logo"><span class="logo-cn">海外 GEO</span>'
        '<span class="logo-tag">售前诊断</span></div>'
        f'<nav class="nav" aria-label="报告目录">{nav}</nav>'
        "</div></header>"
        + masthead
        + '<main id="main" class="shell">'
        + "".join(parts)
        + "</main>"
        + '<div class="drawer-mask" id="drawerMask" role="dialog" aria-modal="true" aria-label="问题详情">'
        '<aside class="drawer"><div class="drawer-head"><strong>问题详情</strong>'
        '<button class="drawer-close" id="drawerClose" type="button" aria-label="关闭">×</button>'
        '</div><div class="drawer-body" id="drawerBody"></div></aside></div>'
        '<footer><div class="shell"><span id="footerBrand"></span></div></footer>'
    )
    return shell


def check_javascript(js: str, source: Path) -> None:
    """渲染前校验交互脚本语法。

    语法错误会让整页空白，且浏览器只报一句 SyntaxError，排查成本远高于在这里拦住。
    node 不可用时跳过，不阻塞渲染。
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(js)
        temp_path = handle.name
    try:
        result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    finally:
        Path(temp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SystemExit(f"{source.name} 存在 JavaScript 语法错误：\n" + "\n".join(detail[:6]))


def slim_for_html(data: dict) -> dict:
    """剥掉渲染层用不到的大字段，再嵌进 HTML。

    记录级的 `brands` 是每题 × 全部纳入对象的统计（Abrand 有 96 个对象），
    45 个切片合计约 20MB，而渲染层一个字段都没用到——页面只用切片级的
    `competition`/`matrix`。它保留在 report-data.json 里供归档与下游读取，
    但不进 HTML，否则单文件会从 3.6MB 涨到 22MB。
    """
    import copy
    slim = copy.deepcopy(data)
    for slice_key, slice_value in slim.get("slices", {}).items():
        keep_brands = slice_key.endswith("|")  # 只有不分主题的切片给抽屉「品牌对比」用
        for record in slice_value.get("records", []):
            brands = record.pop("brands", None) or []
            if keep_brands:
                # 目标品牌、配置竞品，加本题被提到最多的 4 个开放品牌
                core = [b for b in brands if b.get("role") in ("target", "competitor")]
                extra = sorted((b for b in brands if b.get("role") not in ("target", "competitor") and b.get("mention_count")),
                               key=lambda b: -b["mention_count"])[:4]
                record["brands"] = [{k: b.get(k) for k in ("name", "role", "mention_count", "mention_rate",
                                                           "share_of_voice", "average_rank",
                                                           "citation_share", "citation_rate")} for b in core + extra]
        # 带官网的提及率只供统计与下游读取，不进售前 HTML（Suda 2026-09-29）。
        # 引用率（官网引用率）2026-11-07 起进问题明细，参照现行基线报告样稿。
        for field in ("linked_mention_rate", "linked_mention_counts", "official_citation_counts"):
            (slice_value.get("kpis") or {}).pop(field, None)
        for row in slice_value.get("competition_all", []):
            row.pop("linked_mention_rate", None)
        # 购物层只留「AI 购物商品卡」面板要用的数：每平台触发率，目标品牌与配置竞品的入选率。
        # 商品、商家、卡位和逐题下钻是内部字段，不进 HTML（Suda 2026-11-06）。
        slice_value["shopping"] = slim_shopping(slice_value.get("shopping"))
    meta = slim.setdefault("meta", {})
    meta["shopping"] = shopping_switch(slim)
    meta["sentiment_enabled"] = sentiment_switch(slim)
    # 模块不出时，对应的数据也不进 HTML（Suda 2026-11-08：没有商品卡、情感数据就隐藏相应模块和数据）
    if not meta["shopping"]["enabled"]:
        for entry in (slim.get("details") or {}).values():
            entry.pop("product_cards", None)
        for answer in ((slim.get("facts") or {}).get("answers") or []):
            answer["s"] = None
        for slice_value in slim.get("slices", {}).values():
            slice_value["shopping"] = {"by_platform": {}}
    if not meta["sentiment_enabled"]:
        for entry in (slim.get("details") or {}).values():
            entry.pop("sentiment", None)
        if slim.get("facts"):
            slim["facts"].pop("claims", None)
            slim["facts"].pop("sentiment", None)
        for slice_value in slim.get("slices", {}).values():
            slice_value.pop("sentiment", None)
            for record in slice_value.get("records", []):
                record["sentiment"] = None
                record.pop("brand_sentiment", None)
    # 有逐条回答事实时，页面按筛选现算（report-engine.js），预算切片不进 HTML；
    # 切片仍留在 report-data.json 里供 verify / 对账 / 下游读取
    if slim.get("facts"):
        slim["slices"] = {}
    return slim


SHOPPING_MIN_TRIGGER = 0.05  # 工业类产品线的开关门槛，和 geo-monitoring trial-and-lock 同一个数


def _rate(value) -> dict:
    value = value if isinstance(value, dict) else {}
    return {key: value.get(key) for key in ("numerator", "denominator", "display", "raw")}


def slim_shopping(block) -> dict:
    """购物商品卡模块要用的数；逐题下钻等其余字段不进 HTML。"""
    out = {}
    for platform_dir, row in ((block or {}).get("by_platform") or {}).items():
        out[platform_dir] = {
            "product_field_returned": row.get("product_field_returned", True),
            "scope_answers": row.get("scope_answers"),
            "shopping_answers": row.get("shopping_answers"),
            "shopping_mode_rate": _rate(row.get("shopping_mode_rate")),
            "brands": [
                {"name": brand.get("name"), "role": brand.get("role"),
                 "shopping_visibility": _rate(brand.get("shopping_visibility")),
                 "average_card_position": _rate(brand.get("average_card_position")),
                 "official_link_coverage": _rate(brand.get("official_link_coverage"))}
                for brand in row.get("brands") or [] if brand.get("role") in ("target", "competitor")
            ],
            "target_skus": [
                {"name": item.get("name"),
                 "shopping_visibility": _rate(item.get("shopping_visibility")),
                 "average_card_position": _rate(item.get("average_card_position")),
                 "official_link_coverage": _rate(item.get("official_link_coverage"))}
                for item in row.get("target_skus") or []
            ],
        }
    return {"by_platform": out}


def sentiment_switch(data: dict) -> bool:
    """情感模块开不开：判读完成，且最宽切片里任一展示品牌有正负信号（全是 0 的情感模块只有一排「—」）。"""
    meta = data.get("meta") or {}
    if meta.get("sentiment_claims_status") != "complete":
        return False
    slices = data.get("slices") or {}
    widest = slices.get("||") or next(iter(slices.values()), {})
    sentiment = widest.get("sentiment") or {}
    summary = sentiment.get("summary") or {}
    if summary.get("total"):
        return True
    for row in (sentiment.get("by_brand") or {}).values():
        if row.get("signal_total") or row.get("positive") or row.get("negative"):
            return True
    return bool((data.get("facts") or {}).get("claims"))


def shopping_switch(data: dict) -> dict:
    """商品卡面板开不开。meta.shopping_cards 写了开 / 关就照办（选词 config.shopping_cards 的结论）；
    没写时按数据判：最宽切片里任一平台商品卡触发率到 5% 才开，软件、服务、多数工业品类达不到。"""
    meta = data.get("meta") or {}
    declared = str(meta.get("shopping_cards") or "").strip()
    slices = data.get("slices") or {}
    widest = slices.get("||") or next(iter(slices.values()), {})
    # 本次采集里一条商品字段都没返回的平台（按全量切片判，单个主题切片里没有不算）
    no_field = sorted(p for p, row in ((widest.get("shopping") or {}).get("by_platform") or {}).items()
                      if row.get("product_field_returned") is False)
    best = 0.0
    for row in ((widest.get("shopping") or {}).get("by_platform") or {}).values():
        rate = row.get("shopping_mode_rate") or {}
        if rate.get("denominator"):
            best = max(best, (rate.get("numerator") or 0) / rate["denominator"])
    # 本次采集里一张商品卡都没有（品类不出卡、平台都不返回商品字段、或筛不出发现 / 替代题）：模块不出，
    # 写了「开」也一样——只剩一排 0% 和「接口未返回」的模块没有信息量
    total_cards = sum(int(row.get("shopping_answers") or 0)
                      for row in ((widest.get("shopping") or {}).get("by_platform") or {}).values())
    if total_cards == 0:
        return {"enabled": False, "basis": f"本次采集没有商品卡（选词判定：{declared or '未写'}）",
                "no_field_platforms": no_field}
    if declared in ("开", "on"):
        return {"enabled": True, "basis": "选词判定：开", "no_field_platforms": no_field}
    if declared in ("关", "off"):
        return {"enabled": False, "basis": "选词判定：关", "no_field_platforms": no_field}
    enabled = best >= SHOPPING_MIN_TRIGGER
    return {"enabled": enabled, "basis": f"按数据判：最高平台商品卡触发率 {best:.0%}，门槛 5%",
            "no_field_platforms": no_field}


def build_html(data: dict) -> str:
    data = slim_for_html(data)
    meta = data.get("meta", {})
    title = f'{meta.get("brand", "")} · 海外 GEO 售前诊断报告'
    css = (ASSETS / "report.css").read_text(encoding="utf-8")
    css_extra = (ASSETS / "report-extra.css").read_text(encoding="utf-8")
    # 计算引擎与主脚本放同一个 <script>（监测基线报告按「数据段 → 主脚本」切 HTML，不能多一段 script）
    js = (ASSETS / "report-engine.js").read_text(encoding="utf-8") + "\n" + (ASSETS / "report.js").read_text(encoding="utf-8")
    check_javascript(js, ASSETS / "report.js")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        "<style>\n" + css + "\n</style>\n"
        "<style>\n" + css_extra + "\n</style>\n"
        "</head>\n"
        + build_body(meta)
        + "\n<script>window.REPORT_DATA=" + payload + ";</script>\n"
        + "<script>\n" + js + "\n</script>\n</body>\n</html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染海外 GEO 售前诊断报告 HTML")
    parser.add_argument("--data", required=True, help="report-data.json 路径")
    parser.add_argument("--out", required=True, help="输出的 HTML 路径")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    if data.get("schema") != "geo-presales-report-data/v1":
        raise SystemExit(f"数据 schema 不匹配：{data.get('schema')!r}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(data), encoding="utf-8")
    slices = data.get("slices", {})
    print(f"wrote {output}  slices={len(slices)}  bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
