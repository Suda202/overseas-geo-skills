/* 海外 GEO 售前诊断报告 · 交互层
 * 数据来源：页面内嵌的 window.REPORT_DATA（geo-presales-report-data/v1）。
 * 静态外壳由 scripts/render_report.py 产出，本文件负责按 地区 / 平台 / 意图类型 / 主题 筛选重渲染各模块。
 * 有 DATA.facts 时筛选是多选，各模块的数由 report-engine.js 现算（与预算切片同口径，check_engine_parity.js 对账）；
 * 没有 facts（监测基线报告）时仍是单选、读预算切片。
 */
(function () {
  "use strict";

  var DATA = window.REPORT_DATA || {};
  var META = DATA.meta || {};
  var SLICES = DATA.slices || {};
  var ENGINE = DATA.facts && window.ReportEngine ? window.ReportEngine.create(DATA) : null;
  var FILLS = ["gold", "blue", "cyan", "green", "amber", "red", ""];
  var MAX_COMPETITION_ROWS = 5;

  var state = { region: "", platform: "", intent: "", topic: "", matrixMetric: "mention", shopLevel: "brand",
    expanded: {}, page: 1, drawerRun: {}, drawerPlat: {},
    // 多选筛选（引擎模式）：空数组 = 全部
    sel: { regions: [], platforms: [], intents: [], topics: [] }, openMsel: null,
    sourcePage: { domains: 1, pages: 1, official: 1 } };
  var TYPE_PREFIX = META.type_topic_prefix || "类型:";
  // 情感、商品卡没有数据时整块不出，问题明细列、抽屉里的对应内容也不出（render_report.py 按数据写好开关）
  var HAS_SENTIMENT = META.sentiment_enabled !== undefined ? !!META.sentiment_enabled : META.sentiment_claims_status === "complete";
  var HAS_SHOPPING = !!(META.shopping || {}).enabled;
  // 切片 topic 位：选了主题用主题（一个主题只有一种意图类型）；只选了意图类型用「类型:X」切片
  function topicKey() {
    return state.topic || (state.intent ? TYPE_PREFIX + state.intent : "");
  }
  var PAGE_SIZE = 20;
  // 引用域名 / 页面 / 官网页面三张榜的分页：数据层售前给 Top 20、售后给全量，这里每页 10 条。
  var SOURCE_PAGE_SIZE = 10;
  var SOURCE_PAGER = { domains: "sourceDomainsPager", pages: "sourcePagesPager", official: "officialPagesPager" };

  function pageSourceRows(key, rows) {
    var pages = Math.max(1, Math.ceil(rows.length / SOURCE_PAGE_SIZE));
    var page = Math.min(Math.max(1, state.sourcePage[key] || 1), pages);
    state.sourcePage[key] = page;
    var el = document.getElementById(SOURCE_PAGER[key]);
    if (el) {
      if (pages <= 1) {
        el.hidden = true;
        el.innerHTML = "";
      } else {
        el.hidden = false;
        el.innerHTML = '<span class="page-status">共 ' + rows.length + " 条 · 第 " + page + " / " + pages + " 页</span>" +
          '<button class="page-btn" type="button" data-source-list="' + key + '" data-page="' + (page - 1) + '"' + (page <= 1 ? " disabled" : "") + ' aria-label="上一页">‹</button>' +
          '<button class="page-btn" type="button" data-source-list="' + key + '" data-page="' + (page + 1) + '"' + (page >= pages ? " disabled" : "") + ' aria-label="下一页">›</button>';
      }
    }
    return rows.slice((page - 1) * SOURCE_PAGE_SIZE, page * SOURCE_PAGE_SIZE);
  }

  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function favicon(domainOrUrl) {
    var d = String(domainOrUrl || "").replace(/^https?:\/\//, "").split("/")[0];
    return "https://favicone.com/" + encodeURIComponent(d) + "?s=64";
  }
  // 品牌显示名：剥掉数据层 key 里的品类/产品线后缀，让榜单读品牌本身。
  // 识别别名仍用全称匹配（数据层 key 不变），仅展示层精简。
  // 后缀词表由数据层按品类注入（meta.brand_suffixes）；缺省用净水器词表兜底，
  // 换品类时应提供该品类的后缀（如显示屏品类要剥 "Display"/"LED"）。
  var BRAND_SUFFIX = (function () {
    var custom = (DATA.meta || {}).brand_suffixes;
    if (custom && custom.length) {
      return new RegExp("\\s+(" + custom.map(function (w) {
        return String(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s*");
      }).join("|") + ")$", "i");
    }
    return /\s+(Water|Water\s*Purifier|Purification|Aqua|Filters?)$/i;
  })();
  function displayBrand(name) {
    var n = String(name || "").replace(/\s*★\s*$/, "");
    return n.replace(BRAND_SUFFIX, "").trim() || n;
  }
  function logo(domain, size, brandName) {
    var s = size || 16;
    var initial = displayBrand(brandName || domain || "?").trim().charAt(0).toUpperCase();
    // icon 加载失败时回退为首字母占位块，保持行对齐（原来 this.remove() 会留空白）
    // 注意：onerror 属性值用双引号包裹，内部所有双引号必须用 &quot; 转义
    var fallbackSpan = '<span class="entity-logo entity-logo-fallback" style="width:' + s + 'px;height:' + s + 'px;font-size:' + Math.round(s * 0.62) + 'px">' + initial + '</span>';
    if (!domain) {
      return fallbackSpan;
    }
    var escapedFallback = fallbackSpan.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    return '<img class="entity-logo" src="' + favicon(domain) + '" width="' + s + '" height="' + s + '" alt="" loading="lazy" onerror="this.outerHTML=\'' + escapedFallback + '\'">';
  }
  function sliceKey(region, platform, topic) {
    return [region, platform, topic].join("|");
  }
  function withSel(extra) {
    var out = {};
    Object.keys(state.sel).forEach(function (k) { out[k] = state.sel[k]; });
    Object.keys(extra || {}).forEach(function (k) { out[k] = extra[k]; });
    return out;
  }
  // 当前筛选下参与统计的平台（按报告平台顺序）
  function selPlatforms() {
    if (ENGINE) {
      return state.sel.platforms.length
        ? (META.platforms || []).filter(function (p) { return state.sel.platforms.indexOf(p) >= 0; }) : (META.platforms || []);
    }
    return state.platform ? [state.platform] : (META.platforms || []);
  }
  function currentSlice() {
    if (ENGINE) return ENGINE.slice(state.sel);
    // 逐级降级：精确切片 → 同国家全平台全主题 → 首个国家的精确切片 → 首个国家的全量切片。
    // 「全部地区」等合并切片由数据层产出；缺失时不能让整页空白。
    var firstRegion = (META.regions || [])[0] || "";
    var candidates = [
      sliceKey(state.region, state.platform, topicKey()),
      sliceKey(state.region, "", ""),
      sliceKey(firstRegion, state.platform, topicKey()),
      sliceKey(firstRegion, "", "")
    ];
    for (var i = 0; i < candidates.length; i += 1) {
      if (SLICES[candidates[i]]) return SLICES[candidates[i]];
    }
    return { kpis: {}, competition: {}, matrix: {}, sources: {}, sentiment: {}, records: [] };
  }
  function catTag(name) {
    if (!name) return "";
    return '<span class="cat-tag cat-' + esc(name) + '">' + esc(name) + "</span>";
  }
  function pctWidth(value) {
    var n = parseFloat(String(value).replace("%", ""));
    return Number.isFinite(n) ? Math.max(2, Math.min(100, n)) + "%" : "0%";
  }
  function rankDotLeft(value) {
    var n = parseFloat(value);
    if (!Number.isFinite(n)) return "50%";
    return Math.max(2, Math.min(98, 2 + ((n - 1) / 5) * 96)) + "%";
  }

  /* ---------- 基础信息 ---------- */

  function renderMasthead() {
    var el = document.getElementById("reportTitle");
    if (el) el.innerHTML = esc(META.brand || "") + "<span>海外 AI 搜索可见度售前诊断</span>";
    var eyebrow = document.getElementById("reportEyebrow");
    if (eyebrow) eyebrow.textContent = "GEO Presales Diagnosis · " + esc(META.generated_at || "");
    var foot = document.getElementById("footerBrand");
    if (foot) foot.textContent = "海外 GEO 售前诊断报告 · " + esc(META.brand || "");
  }

  /* ---------- tab ---------- */

  function buildTabs(containerId, values, activeValue, dataAttr, allLabel, toggleable) {
    var el = document.getElementById(containerId);
    if (!el) return false;
    // 只有一个取值时这行筛选没有意义（「全部」与那一项是同一个切片），整行不显示。
    // 注意 .filter-tabs 带 display:flex，会盖掉 [hidden]，必须显式设 display。
    if (values.length <= 1) {
      el.innerHTML = "";
      el.style.display = "none";
      return false;
    }
    el.style.display = "";
    var html = "";
    if (allLabel) {
      html += '<button class="tab-btn' + (activeValue === "" ? " active" : "") +
        '" type="button" data-' + dataAttr + '="" data-toggle="' + (toggleable ? "1" : "0") + '">' + esc(allLabel) + "</button>";
    }
    values.forEach(function (value) {
      html += '<button class="tab-btn' + (activeValue === value ? " active" : "") +
        '" type="button" data-' + dataAttr + '="' + esc(value) + '" data-toggle="' + (toggleable ? "1" : "0") + '">' + esc(value) + "</button>";
    });
    el.innerHTML = html;
    return true;
  }

  // show：这个维度在整份报告里有没有可选的（只有一个取值的维度整份报告都不出）；
  // 不按收窄后的选项数决定显隐，否则选了意图类型、主题只剩一个时下拉会突然消失
  function fillSelect(id, values, active, allLabel, show) {
    var el = document.getElementById(id);
    if (!el) return false;
    if (show === undefined ? values.length <= 1 : !show) { el.style.display = "none"; el.innerHTML = ""; return false; }
    el.style.display = "";
    el.innerHTML = '<option value="">' + esc(allLabel) + "</option>" + values.map(function (v) {
      return '<option value="' + esc(v) + '"' + (v === active ? " selected" : "") + ">" + esc(v) + "</option>";
    }).join("");
    return true;
  }

  function renderTabs() {
    var shown = [];
    if (fillSelect("regionSelect", META.regions || [], state.region, "全部地区")) shown.push("地区");
    if (fillSelect("platformSelect", META.platforms || [], state.platform, "全部平台")) shown.push("平台");
    var intentTopics = META.intent_topics || {};
    if (fillSelect("intentSelect", Object.keys(intentTopics), state.intent, "全部意图类型")) shown.push("意图类型");
    // 主题下拉按选中的意图类型收窄
    var topics = state.intent && intentTopics[state.intent] ? intentTopics[state.intent] : (META.topics || []);
    if (fillSelect("topicSelect", topics, state.topic, "全部主题", (META.topics || []).length > 1)) shown.push("主题");
    var box = document.getElementById("sharedFilter");
    if (box) box.style.display = shown.length ? "" : "none";
  }

  /* ---------- 核心洞察 KPI ---------- */

  // 提及类指标只算发现、替代（只剩问题解决时算问题解决）。对比、评估、验证、交易、售后题面点名了品牌，
  // 提及率接近 100%，不算；这类切片的提及类指标是「—」，不代表品牌没出现。
  function isTypeOnlySlice(slice) {
    var c = slice._counts || {};
    return (slice.records || []).length > 0 && c.visibility_answers === 0;
  }

  // 商品卡提及率 KPI：选了平台看这个平台；全部平台时把返回了商品字段的平台合计（分子分母各自相加）。
  // 提及率、触发率按回答计，可以跨平台合计；商品卡份额、平均位置按卡计，各平台卡数差很多，不合计。
  function shoppingKpi(slice) {
    if (!(META.shopping || {}).enabled) return null;
    var by = (slice.shopping || {}).by_platform || {};
    var dirs = META.platform_dirs || {};
    var noField = (META.shopping || {}).no_field_platforms || [];
    var platforms = selPlatforms();
    var num = 0, den = 0, trig = 0, scope = 0, used = [], skipped = [];
    platforms.forEach(function (p) {
      var dir = dirs[p] || p;
      var row = by[dir];
      if (!row || noField.indexOf(dir) >= 0) { skipped.push(p); return; }
      var target = (row.brands || []).filter(function (b) { return b.role === "target"; })[0] || {};
      var v = target.shopping_visibility || {};
      num += v.numerator || 0;
      den += v.denominator || 0;
      trig += row.shopping_answers || 0;
      scope += row.scope_answers || 0;
      used.push(p);
    });
    if (!used.length) return null;
    function pct(a, b) { return b ? (a === 0 ? "0%" : (a * 100 / b).toFixed(1).replace(/\.0$/, "") + "%") : "—"; }
    return {
      rate: pct(num, den), mode: pct(trig, scope), counts: num + " / " + den,
      note: ""
    };
  }

  // 01 指标下面一行写清每个数统计哪几类意图（随筛选变：只列当前切片里有的类型）
  // 核心洞察所有指标同一批题：发现、替代（只剩问题解决题时是问题解决）（Suda 2026-11-07）
  function kpiScopeLine(slice) {
    var present = [];
    (slice.records || []).forEach(function (r) { if (r.intent && present.indexOf(r.intent) < 0) present.push(r.intent); });
    function pick(types) { return types.filter(function (t) { return present.indexOf(t) >= 0; }); }
    var vis = pick(["发现", "替代"]);
    if (!vis.length) vis = pick(["问题解决"]);
    return "统计范围　" + (vis.length ? vis.join("、") : "当前筛选下不统计（点名品牌的问题）");
  }

  // 各模块标题右侧：本模块统计哪几类意图（只列当前筛选下有的类型）
  var SECTION_SCOPE = {
    competition: [["发现", "替代"], ["问题解决"]],
    shopping: [["发现", "替代"]],
    sources: "all",
    distribution: [["发现", "替代", "对比", "评估", "验证"]]
  };
  function renderScopes() {
    var present = [];
    (currentSlice().records || []).forEach(function (r) { if (r.intent && present.indexOf(r.intent) < 0) present.push(r.intent); });
    var allTypes = Object.keys(META.intent_topics || {});
    Object.keys(SECTION_SCOPE).forEach(function (id) {
      var el = document.getElementById("scope-" + id);
      if (!el) return;
      var rule = SECTION_SCOPE[id];
      var types = [];
      if (rule === "all") {
        types = allTypes.filter(function (t) { return present.indexOf(t) >= 0; });
        el.textContent = types.length && types.length === allTypes.length ? "全部意图类型" : types.join(" · ");
        return;
      }
      for (var i = 0; i < rule.length && !types.length; i += 1) {
        types = rule[i].filter(function (t) { return present.indexOf(t) >= 0; });
      }
      el.textContent = types.length ? types.join(" · ") : "当前筛选下不统计";
    });
  }

  function renderKpis() {
    var slice = currentSlice();
    var k = slice.kpis || {};
    var el = document.getElementById("overviewKpis");
    if (!el) return;
    var na = isTypeOnlySlice(slice);
    var items = [
      ["提及率", na ? "—" : k.mention_rate, "提到监测对象的回答 ÷ 有效回答。对比、评估、验证、交易、售后题面点名了品牌，提及率接近 100%，不统计。"],
      ["提及率排名", na ? "—" : k.mention_rank, "按提及率由高到低在当前品牌集合中的位置。"],
      ["声量份额", na ? "—" : k.share_of_voice, "监测对象被提及的次数 ÷ 全部纳入品牌被提及的次数之和。"],
      ["平均提及位置", na ? "—" : k.average_rank, "监测对象被提及时在回答里的平均位置，数值越小越靠前。"],
      ["引用份额", k.official_share, "指向监测对象官网的引用次数 ÷ 全部引用次数。"],
      ["引用率", k.official_citation_rate, "正文至少引用一次监测对象官网的回答 ÷ 有效回答。一条回答引用多次只算一次。"]
    ];
    var shop = shoppingKpi(slice);
    if (shop) {
      items.push(["商品卡提及率", shop.rate,
        "出现商品卡的回答里，有监测对象商品卡的回答占比（" + shop.counts + "）；只数商品卡，不含正文提及。同范围商品卡触发率 " + shop.mode + "。",
        shop.note]);
    }
    // 列数交给 CSS：宽屏一行放下全部指标，窄屏按 report.css 的断点换行（不写行内 grid，否则断点失效、数字挤在一起）
    el.style.removeProperty("grid-template-columns");
    el.style.setProperty("--kpi-n", items.length);
    el.innerHTML = items.map(function (row) {
      return '<div class="kpi"><span class="label">' + esc(row[0]) +
        '<button type="button" class="info" aria-label="查看' + esc(row[0]) + '含义" data-tip="' + esc(row[2]) + '">i</button>' +
        '</span><strong class="value">' + esc(row[1] === "0.0%" ? "0%" : (row[1] || "—")) + "</strong>" +
        (row[3] ? '<small class="kpi-sub">' + esc(row[3]) + "</small>" : "") + "</div>";
    }).join("");
    var scopeEl = document.getElementById("kpiScope");
    if (!scopeEl) {
      scopeEl = document.createElement("p");
      scopeEl.id = "kpiScope";
      scopeEl.className = "kpi-scope";
      el.parentNode.insertBefore(scopeEl, el.nextSibling);
    }
    scopeEl.textContent = kpiScopeLine(slice);
  }

  /* ---------- 02 可见度 ---------- */

  function renderCompetition() {
    var slice = currentSlice();
    var comp = slice.competition || {};
    var mention = (comp.mention || []).slice(0, MAX_COMPETITION_ROWS);
    var rank = (comp.rank || []).slice(0, MAX_COMPETITION_ROWS);

    var mentionEl = document.getElementById("competitionMentions");
    if (mentionEl) {
      mentionEl.innerHTML = mention.map(function (row) {
        var color = row[4] || "";
        var isTarget = color === "gold";
        return '<div class="bar-row' + (isTarget ? " is-target" : "") + '">' +
          '<span class="bar-rank">' + esc(row[5]) + "</span>" +
          '<span class="bar-label">' + logo(row[1], 16, row[0]) + esc(displayBrand(row[0])) + "</span>" +
          '<div class="track"><div class="fill ' + esc(color) + '" style="width:' + pctWidth(row[3]) + '"></div></div>' +
          '<b class="bar-val">' + esc(row[2]) + "</b></div>";
      }).join("") || emptyRow("暂无数据");
    }

    var rankEl = document.getElementById("competitionRank");
    if (rankEl) {
      rankEl.innerHTML = rank.map(function (row) {
        var isTarget = row[3] === "target";
        return '<div class="rankdot-row' + (isTarget ? " is-target" : "") + '">' +
          '<span class="rankdot-name">' + logo(row[1], 18, row[0]) + esc(displayBrand(row[0])) + "</span>" +
          '<span class="rankdot-track"><i class="' + (isTarget ? "gold" : "") + '" style="left:' + rankDotLeft(row[2]) + '"></i></span>' +
          '<span class="rankdot-val">' + esc(row[2]) + "</span></div>";
      }).join("") || emptyRow("暂无数据");
    }

    var share = comp.share || [];
    var donutEl = document.getElementById("competitionShare");
    if (donutEl) {
      var segments = [];
      var total = 0;
      mention.forEach(function (row, index) {
        var value = Number(share[index] || 0);
        var color = row[4] || "";
        segments.push({
          name: row[0],
          value: value,
          color: "var(--" + (color === "gold" ? "gold" : color === "" ? "navy" : color) + ")",
          target: color === "gold"
        });
        total += value;
      });
      // 声量份额分母是全部纳入品牌（含未展示的开放品牌），展示几行相加不足 100%，
      // 余量单列为「其他品牌」，否则环形图只会画出一小块。
      var residual = Math.round((100 - total) * 10) / 10;
      if (residual > 0.5) {
        segments.push({ name: "其他品牌", value: residual, color: "var(--quiet)", target: false });
      }
      // 环形图与图例使用同一份排序结果，保证颜色与品牌一一对应。
      segments.sort(function (a, b) { return b.value - a.value; });
      var stops = [];
      var cursor = 0;
      segments.forEach(function (seg) {
        stops.push(seg.color + " " + cursor + "% " + (cursor + seg.value) + "%");
        cursor += seg.value;
      });
      if (!stops.length) stops.push("var(--line) 0% 100%");
      var targetRow = segments.filter(function (r) { return r.target; })[0] || segments[0];
      donutEl.innerHTML =
        '<div class="donut-wrap"><div class="donut" style="background:conic-gradient(' + stops.join(",") + ')"></div>' +
        '<div class="donut-center"><b>' + esc(targetRow ? targetRow.value.toFixed(1) + "%" : "—") + "</b><small>" +
        esc((targetRow ? displayBrand(targetRow.name) : "")) + "</small></div></div>" +
        '<div class="donut-legend">' + segments.map(function (row) {
          return "<div" + (row.target ? ' class="is-target"' : "") + '><i style="background:' + row.color + '"></i><span>' +
            esc(displayBrand(row.name)) + "</span><b>" + row.value.toFixed(1) + "%</b></div>";
        }).join("") + "</div>";
    }

    renderMatrix();
  }

  function renderMatrix() {
    var slice = currentSlice();
    var matrix = slice.matrix || {};
    var metric = state.matrixMetric;
    var platforms = (matrix.platforms || []).length ? matrix.platforms : (META.platforms || []);
    var rows = matrix[metric] || [];
    var el = document.getElementById("platformMatrix");
    if (!el) return;
    if (!rows.length) { el.innerHTML = ""; return; }
    var head = "<thead><tr><th>品牌</th>" + platforms.map(function (p) { return "<th>" + esc(p) + "</th>"; }).join("") + "</tr></thead>";
    var body = "<tbody>" + rows.map(function (row) {
      var cells = platforms.map(function (_, index) {
        var value = (row.vals || [])[index];
        if (value === null || value === undefined) return "<td>—</td>";
        if (metric === "rank") return "<td>" + Number(value).toFixed(1) + "</td>";
        return "<td>" + Number(value).toFixed(1) + "%</td>";
      }).join("");
      return "<tr" + (row.target ? ' class="is-target"' : "") + '><td class="brand-cell">' + esc(displayBrand(row.name)) + "</td>" + cells + "</tr>";
    }).join("") + "</tbody>";
    el.innerHTML = head + body;
  }

  /* ---------- 购物商品卡 ---------- */

  var SHOP_TIPS = {
    mode: "出现商品卡的回答 ÷ 有效回答。",
    visibility: "出现商品卡的回答里，有该品牌商品卡的回答占比（只数商品卡，不含正文提及）。",
    position: "该品牌商品卡在每条回答里最靠前那张的位置取平均，数值越小越靠前。",
    link: "出现该品牌商品卡的回答里，商品卡带官网购买链接的回答占比。"
  };

  function shopVal(rate) {
    if (!rate || rate.display === undefined || rate.display === null) return "—";
    return String(rate.display).replace(/^#/, "");
  }
  function shopCell(rate, emptyTip) {
    var v = shopVal(rate);
    if (v === "—") return '<td title="' + esc(emptyTip) + '">—</td>';
    return '<td' + (rate.denominator ? ' title="' + esc(rate.numerator + " / " + rate.denominator) + '"' : "") + ">" + esc(v) + "</td>";
  }
  function tipLabel(text, tip) {
    return esc(text) + '<button type="button" class="info" aria-label="查看' + esc(text) + '含义" data-tip="' + esc(tip) + '">i</button>';
  }
  function shopRows() {
    var by = (currentSlice().shopping || {}).by_platform || {};
    var dirs = META.platform_dirs || {};
    var platforms = selPlatforms();
    return platforms.map(function (p) { return { platform: p, dir: dirs[p] || p, row: by[dirs[p] || p] || null }; });
  }
  // 平台不返回商品卡字段（Perplexity），或本次采集里一条都没带（2026-10 起的 Gemini），整列写「接口未返回」
  function noField(item) {
    return !item.row || ((META.shopping || {}).no_field_platforms || []).indexOf(item.dir) >= 0;
  }
  function shopTarget(row) {
    return ((row && row.brands) || []).filter(function (b) { return b.role === "target"; })[0] || {};
  }

  function renderShopping() {
    var core = document.getElementById("shoppingCore");
    if (!core) return;
    var cols = shopRows();
    var section = document.getElementById("shopping");
    var scoped = cols.some(function (c) { return c.row && c.row.scope_answers; });
    var emptyNote = document.getElementById("shoppingEmpty");
    if (!emptyNote && section) {
      emptyNote = document.createElement("p");
      emptyNote.id = "shoppingEmpty";
      emptyNote.className = "support-line";
      emptyNote.textContent = "当前筛选下没有发现、替代类问题，商品卡只统计这两类。";
      section.querySelector(".section-body").prepend(emptyNote);
    }
    if (section) {
      Array.prototype.forEach.call(section.querySelectorAll(".section-body > article, .section-body > .grid-2"), function (el) {
        el.style.display = scoped ? "" : "none";
      });
    }
    if (emptyNote) emptyNote.style.display = scoped ? "none" : "";
    if (!scoped) return;
    var missing = '<td title="采集接口没有返回商品卡字段">接口未返回</td>';
    // 商品卡触发率：一个指标卡，跟平台筛选走；全部平台时把返回了商品字段的平台合计（分子分母各自相加）
    var trig = 0, base = 0, live = cols.filter(function (c) { return !noField(c); });
    live.forEach(function (c) {
      trig += (c.row.shopping_mode_rate || {}).numerator || 0;
      base += (c.row.shopping_mode_rate || {}).denominator || 0;
    });
    var modeValue = !live.length ? "接口未返回" : (base ? (trig === 0 ? "0%" : (trig * 100 / base).toFixed(1).replace(/\.0$/, "") + "%") : "—");
    core.innerHTML = '<div class="kpi"><span class="label">商品卡触发率' +
      '<button type="button" class="info" aria-label="查看商品卡触发率含义" data-tip="' + esc(SHOP_TIPS.mode) + '">i</button></span>' +
      '<strong class="value"' + (base ? ' title="' + trig + " / " + base + '"' : "") + ">" + esc(modeValue) + "</strong></div>";

    // 行：品牌 = 目标品牌 + 配置竞品（按配置顺序）；SKU = 本品各 SKU（「未识别型号」排最后）
    var hasSku = cols.some(function (c) { return c.row && c.row.target_skus && c.row.target_skus.length; });
    var levelSwitch = document.getElementById("shopLevelSwitch");
    if (levelSwitch) levelSwitch.style.display = hasSku ? "" : "none";
    var level = hasSku ? state.shopLevel : "brand";
    var rows = [];
    if (level === "sku") {
      cols.forEach(function (c) {
        ((c.row && c.row.target_skus) || []).forEach(function (k) { if (rows.indexOf(k.name) < 0) rows.push(k.name); });
      });
      rows.sort(function (a, b) { return (a === "未识别型号") - (b === "未识别型号"); });
    } else {
      (META.objects || []).forEach(function (obj) {
        if (obj.role === "target" || obj.role === "competitor") rows.push(obj.name);
      });
    }
    var targetName = ((META.objects || []).filter(function (o) { return o.role === "target"; })[0] || {}).name;
    function item(row, name) {
      var list = level === "sku" ? (row.target_skus || []) : (row.brands || []);
      return list.filter(function (x) { return x.name === name; })[0];
    }
    function fill(tableId, field) {
      var el = document.getElementById(tableId);
      if (!el) return;
      var head = "<thead><tr><th>" + (level === "sku" ? "SKU" : "品牌") + "</th>" +
        cols.map(function (c) { return "<th>" + esc(c.platform) + "</th>"; }).join("") + "</tr></thead>";
      el.innerHTML = head + "<tbody>" + rows.map(function (name) {
        var isTarget = level === "brand" && name === targetName;
        return "<tr" + (isTarget ? ' class="is-target"' : "") + '><td class="brand-cell">' +
          esc(level === "sku" ? name : displayBrand(name)) + "</td>" + cols.map(function (c) {
            if (noField(c)) return missing;
            var k = item(c.row, name);
            // SKU 在出过商品卡的平台一次都没进：提及率记 0%，其余记「—」
            if (!k && level === "sku" && field === "shopping_visibility" && c.row.shopping_answers) {
              return '<td title="0 / ' + esc(c.row.shopping_answers) + '">0%</td>';
            }
            return shopCell(k && k[field], "没有出现商品卡，或没进商品卡");
          }).join("") + "</tr>";
      }).join("") + "</tbody>";
    }
    fill("shopVis", "shopping_visibility");
    fill("shopPos", "average_card_position");
    fill("shopLink", "official_link_coverage");
  }

  /* ---------- 03 引用 ---------- */

  function renderSources() {
    // 每个「引用份额」旁边配「引用率」（至少引用一次该来源的回答 ÷ 有效回答），参照现行基线报告样稿
    var slice = currentSlice();
    var sources = slice.sources || {};
    var rates = sources.rates || {};
    function r(map, key) { return esc(((rates[map] || {})[key]) || "—"); }
    var badge = document.getElementById("sourceShareBadge");
    if (badge) {
      badge.innerHTML = "引用份额 <b>" + esc(sources.official_share || "—") + "</b> · 引用率 <b>" + esc(sources.official_citation_rate || "—") + "</b>";
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

  /* ---------- 04 情感 ---------- */

  function renderSentiment() {
    var slice = currentSlice();
    var sentiment = slice.sentiment || {};
    var summary = sentiment.summary || {};
    var claims = sentiment.claims || { pos: [], neg: [] };

    var el = document.getElementById("sentimentRates");
    if (el) {
      var intro = "<h3>" + esc((META.brand || "") + " 的正负向表达") + "</h3>";
      var basisNote = "";
      el.innerHTML = intro +
        bucket("正向", summary.pos_rate, "pos", claims.pos || []) +
        bucket("负向", summary.neg_rate, "neg", claims.neg || []) +
        basisNote;
      var first = (claims.pos || [])[0] || (claims.neg || [])[0] || null;
      showEvidence(first, first && (claims.pos || []).indexOf(first) >= 0 ? "pos" : "neg");
    }
    renderSentimentOverview();
    renderSentimentMatrix();
  }

  function sentimentRateValue(text) {
    var n = parseFloat(String(text || "").replace("%", ""));
    return isFinite(n) ? n : null;
  }

  function sentimentRateClass(value) {
    if (value == null) return "rate-none";
    if (value >= 80) return "rate-good";
    if (value >= 60) return "rate-mid";
    return "rate-bad";
  }

  function renderSentimentOverview() {
    var slice = currentSlice();
    var byBrand = ((slice.sentiment || {}).by_brand) || {};
    var el = document.getElementById("sentimentOverviewBars");
    if (!el) return;
    var brands = (META.sentiment_brands && META.sentiment_brands.length
      ? META.sentiment_brands : Object.keys(byBrand));
    if (!brands.length) {
      el.innerHTML = '<p class="support-line">情感判读尚未接入</p>';
      return;
    }
    var target = META.brand || "";
    var items = brands.map(function (brand) {
      var cell = byBrand[brand] || {};
      var rateText = cell.pos_rate || "—";
      var value = sentimentRateValue(rateText);
      var width = value == null ? 0 : Math.max(2, Math.min(100, value));
      return '<div class="sentiment-overview-bar' + (brand === target ? " is-target" : "") + '">' +
        '<div class="bar-head"><span class="bar-brand">' + esc(displayBrand(brand)) +
        (brand === target ? " ★" : "") + "</span>" +
        '<span class="bar-value">' + esc(rateText) + "</span></div>" +
        '<div class="bar-track"><span class="bar-fill ' + sentimentRateClass(value) +
        '" style="width:' + width + '%"></span></div>' +
        "</div>";
    }).join("");
    el.innerHTML = '<div class="sentiment-overview-bars">' + items + "</div>";
  }

  // attribute 在数据层是「维度 > 极性」形式（如「字幕语言覆盖 > 广」），
  // 面板展示时去掉分隔符，读起来是人话。
  function naturalAttr(text) {
    return String(text === null || text === undefined ? "" : text).replace(/\s*>\s*/g, "");
  }

  function bucket(title, rateText, dir, items) {
    // 去重 + 只展示前 5 个（按数据层已排好的计数降序）。
    // data-claim 保留原数组下标，点击取证据仍走原数组，不受筛选影响。
    var seen = {}, chips = [];
    (items || []).forEach(function (item, index) {
      var label = naturalAttr(item.label || item.text || "");
      if (!label || seen[label] || chips.length >= 5) return;
      seen[label] = true;
      chips.push('<button type="button" class="sentiment-chip ' + dir + (chips.length === 0 ? " active" : "") +
        '" data-claim="' + esc(dir + ":" + index) + '">' + esc(label) + "</button>");
    });
    chips = chips.join("") || '<span class="support-line">暂无判读结果</span>';
    return '<div class="sentiment-bucket">' +
      '<div class="sentiment-rate ' + dir + '">' + esc(rateText || "—") + " " + esc(title) + "</div>" +
      '<div class="sentiment-chip-list">' + chips + "</div></div>";
  }

  function showEvidence(item, dir) {
    var el = document.getElementById("sentimentEvidence");
    if (!el) return;
    if (!item || !item.evidence) {
      el.innerHTML = '<p class="support-line">暂无判读结果</p>';
      return;
    }
    var ev = item.evidence;
    var platform = PLATFORM_LABEL_WITH_DIR[ev.platform] || ev.platform || "";
    var where = [ev.region, platform, ev.question_id].filter(Boolean).join(" · ");
    // 句子里残留的 markdown 加粗先转义再转 <strong>，避免裸 ** 显示
    var sentenceHtml = esc(ev.sentence || "")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    el.innerHTML =
      '<span class="sentiment-evidence-dir ' + esc(dir) + '">' + (dir === "pos" ? "正向" : "负向") + "</span>" +
      '<h4 class="sentiment-evidence-claim">' + esc(item.label || "") + "</h4>" +
      '<p class="sentiment-evidence-where">' + esc(where) + "</p>" +
      '<blockquote class="sentiment-evidence-text">' + sentenceHtml + "</blockquote>" +
      '<button type="button" class="sentiment-evidence-toggle" data-open-answer="' +
      esc(ev.question_id || "") + '" data-open-region="' + esc(ev.region || "") +
      '" data-open-platform="' + esc(platform) + '">查看对应回答</button>';
  }

  var PLATFORM_LABEL_WITH_DIR = { overview: "AIO", gemini: "Gemini", chatgpt: "ChatGPT", perplexity: "Perplexity", aimode: "AI Mode", copilot: "Copilot", grok: "Grok", alexa: "Alexa" };

  function renderSentimentMatrix() {
    var slice = currentSlice();
    var themeMatrix = (slice.sentiment || {}).theme_matrix || null;
    var el = document.getElementById("sentimentMatrix");
    if (!el) return;
    if (!themeMatrix || !themeMatrix.themes || !themeMatrix.brands) {
      el.innerHTML = '<tbody><tr><td class="support-line">情感判读尚未接入</td></tr></tbody>';
      return;
    }
    var themes = themeMatrix.themes;
    var brands = themeMatrix.brands;
    var matrix = themeMatrix.matrix || {};
    var target = META.brand || "";
    var head = "<thead><tr><th>Theme</th>" +
      brands.map(function (b) {
        return '<th class="' + (b === target ? "is-target" : "") + '">' + esc(displayBrand(b)) +
          (b === target ? " ★" : "") + "</th>";
      }).join("") + "</tr></thead>";
    var body = "<tbody>" + themes.map(function (theme) {
      var row = matrix[theme] || {};
      var cells = brands.map(function (brand) {
        var cell = row[brand] || { pos: 0, neg: 0, rate: "—", top_attribute: "", top_dir: "" };
        var display = cell.top_attribute || "—";
        var dirClass = cell.top_dir === "pos" ? "dir-pos" : cell.top_dir === "neg" ? "dir-neg" : "dir-none";
        var title = esc(brand + " · " + theme + " · 正 " + cell.pos + " / 负 " + cell.neg);
        return '<td class="theme-cell ' + dirClass + '" title="' + title + '">' + esc(display) + "</td>";
      }).join("");
      return "<tr><th>" + esc(theme) + "</th>" + cells + "</tr>";
    }).join("") + "</tbody>";
    el.innerHTML = head + body;
  }

  /* ---------- 附录 问题明细 ---------- */

  function recordsForSlice() {
    var slice = currentSlice();
    var all = slice.records || [];
    var query = (state.recordQuery || "").toLowerCase().trim();
    var intent = state.recordIntent || "";
    if (!query && !intent) return all;
    return all.filter(function (r) {
      if (intent && r.intent !== intent) return false;
      if (query) {
        var hay = [String(r.qid), r.en, r.zh].join(" ").toLowerCase();
        if (!hay.includes(query)) return false;
      }
      return true;
    });
  }

  function recordHead() {
    return "<thead><tr>" +
      '<th class="num">编号</th><th>问题</th><th class="num">提及率</th>' +
      '<th class="num">提及率排名</th><th class="num">声量份额</th><th class="num">平均提及位置</th>' +
      '<th class="num">引用份额</th><th class="num">引用率</th>' +
      (HAS_SENTIMENT ? '<th class="num">正向情感占比</th>' : "") +
      '<th class="center">详情</th></tr></thead>';
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
    var cols = HAS_SENTIMENT ? 10 : 9;

    var table = document.getElementById("recordTable");
    if (!table) return;
    if (!order.length) {
      table.innerHTML = recordHead() +
        '<tbody><tr><td class="empty" colspan="' + cols + '">没有符合当前条件的记录</td></tr></tbody>';
      renderPagination(0, 1);
      return;
    }

    var pages = Math.max(1, Math.ceil(order.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    var visible = order.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
    function cell(v, strong) {
      var text = esc(v === "0.0%" ? "0%" : (v || "—"));
      return '<td class="rank-num num">' + (strong ? "<strong>" + text + "</strong>" : text) + "</td>";
    }

    table.innerHTML = recordHead() + visible.map(function (topic) {
      var rows = groups[topic];
      var isOpen = state.expanded[topic] !== false;
      // 主题行取该主题切片的指标（按回答合计），不对逐题读数取平均
      var ts = ENGINE ? ENGINE.slice(withSel({ topics: [topic] })) : (SLICES[sliceKey(state.region, state.platform, topic)] || {});
      var k = ts.kpis || {};
      var na = isTypeOnlySlice(ts);
      var head = '<tr class="group-head" role="button" tabindex="0" aria-expanded="' + isOpen + '">' +
        '<td class="num group-toggle-cell"><span class="group-chevron">▸</span></td>' +
        "<td><strong>" + esc(topic) + '</strong><span class="group-count">' + rows.length + "</span></td>" +
        cell(na ? "—" : k.mention_rate, true) + cell(na ? "—" : k.mention_rank, true) +
        cell(na ? "—" : k.share_of_voice, true) + cell(na ? "—" : k.average_rank, true) +
          // 引用不受「点名类型」限制：主题行用该主题全部回答的引用（同问题行），不用核心洞察口径
        cell((ts.sources || {}).official_share, true) + cell((ts.sources || {}).official_citation_rate, true) +
        (HAS_SENTIMENT ? cell(((ts.sentiment || {}).summary || {}).pos_rate, true) : "") +
        '<td class="center"></td></tr>';
      var items = rows.map(function (record) {
        // 题面点名品牌的类型不算提及类读数
        var named = ["发现", "替代", "问题解决"].indexOf(record.intent) < 0;
        return '<tr class="q-row">' +
          '<td class="num">' + esc(record.qid) + "</td>" +
          '<td class="q"><b>' + esc(record.en) + "</b><small>" + esc(record.zh) + "</small></td>" +
          cell(named ? "—" : record.mention_rate) + cell(named ? "—" : record.mention_rank) +
          cell(named ? "—" : record.share) + cell(named ? "—" : record.position) +
          cell(record.citation_share) + cell(record.citation_rate) +
          (HAS_SENTIMENT ? cell(record.sentiment) : "") +
          '<td class="center"><button class="detail-btn" type="button" data-detail="' + esc(record.qid) + '">查看</button></td></tr>';
      }).join("");
      return '<tbody class="topic-group open" data-group-topic="' + esc(topic) + '">' + head + items + "</tbody>";
    }).join("");
    renderPagination(order.length, pages);
  }

  function renderPagination(total, pages) {
    var el = document.getElementById("recordPagination");
    if (!el) return;
    if (pages <= 1) { el.hidden = true; el.innerHTML = ""; return; }
    el.hidden = false;
    el.innerHTML = '<span class="page-status">' + total + " 组 · 第 " + state.page + " / " + pages + " 页</span>" +
      '<button class="page-btn" type="button" data-page="' + (state.page - 1) + '"' + (state.page <= 1 ? " disabled" : "") + ' aria-label="上一页">‹</button>' +
      '<button class="page-btn" type="button" data-page="' + (state.page + 1) + '"' + (state.page >= pages ? " disabled" : "") + ' aria-label="下一页">›</button>';
  }

  // 一题的全部回答：details 的键是「地区|平台|0003」或「地区|平台|0003-r2」（第 2 次运行）
  function runsFor(qid, platform) {
    var details = DATA.details || {};
    var padded = String(qid).padStart(4, "0");
    var regions = state.region ? [state.region] : (META.regions || []);
    if (ENGINE && state.sel.regions.length) regions = state.sel.regions;
    var plats = ENGINE && !platform && state.sel.platforms.length ? state.sel.platforms : null;
    var out = [];
    Object.keys(details).forEach(function (k) {
      var parts = k.split("|");
      if (parts.length < 3 || parts[2].split("-r")[0] !== padded) return;
      if (regions.indexOf(parts[0]) < 0) return;
      if (platform && parts[1] !== platform) return;
      if (plats && plats.indexOf(parts[1]) < 0) return;
      out.push({ key: k, region: parts[0], platform: parts[1], run: details[k].run || 1, entry: details[k] });
    });
    var order = META.platforms || [];
    // 按采集时间从近到远；同一时间按平台顺序（ChatGPT 在前）
    out.sort(function (a, b) {
      var ta = a.entry.time || "", tb = b.entry.time || "";
      return (ta < tb ? 1 : ta > tb ? -1 : 0) || (order.indexOf(a.platform) - order.indexOf(b.platform)) || (b.run - a.run);
    });
    return out;
  }

  function answerSwitch(entry) {
    var hasZh = !!entry.answer_zh_html;
    // 有译文时默认展示中文：报告读者是中文客户，原文退到一个点击之后。
    var enTab = '<button class="answer-tab' + (hasZh ? "" : " active") +
      '" type="button" role="tab" aria-selected="' + (hasZh ? "false" : "true") +
      '" data-answer-tab="en">回答原文</button>';
    var zhTab = '<button class="answer-tab active" type="button" role="tab" aria-selected="true" data-answer-tab="zh">中文译文</button>';
    var enPanel = '<div class="answer-panel' + (hasZh ? "" : " active") +
      ' answer-md" data-answer-panel="en">' +
      (entry.answer_html || '<p class="support-line">该回答无可解析内容</p>') + "</div>";
    var zhPanel = '<div class="answer-panel active answer-md" data-answer-panel="zh">' + entry.answer_zh_html + "</div>";
    var tabs = '<div class="answer-tabs" role="tablist" aria-label="切换回答语言">' +
      (hasZh ? zhTab + enTab : enTab) + "</div>";
    var panels = hasZh ? zhPanel + enPanel : enPanel;
    return '<div class="answer-switch">' + tabs + panels + "</div>";
  }

  // 顶部的商品卡块只在正文里没有原位卡片时才出（2026-11-09）：ChatGPT 的回答卡片已经在原文
  // 该在的位置渲染，再在上面摆一排就是同一批卡显示两遍。AI Mode、AIO 正文里没有卡片位置，
  // 仍靠 details[].product_cards 在这里按平台顺序排。
  function productCardsBlock(cards, entry) {
    if (!HAS_SHOPPING || !cards.length) return "";
    var inline = (entry && (entry.answer_html || "").indexOf("product-card-inline") >= 0 &&
      (entry.answer_zh_html || entry.answer_html || "").indexOf("product-card-inline") >= 0);
    if (inline) return "";
    return '<section class="answer-cards"><h4 class="drawer-sec">商品卡 <span class="drawer-sec-count">' + cards.length + " 张</span></h4>" +
      '<div class="answer-card-row">' + cards.map(function (c, i) {
        return '<div class="answer-card' + (c.target ? " is-target" : "") + '">' +
          '<span class="answer-card-pos">' + (i + 1) + "</span>" +
          (c.image ? '<div class="answer-card-img"><img src="' + esc(c.image) + '" alt="" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></div>' : "") +
          '<div class="answer-card-title" title="' + esc(c.title) + '">' + esc(c.title) + "</div>" +
          '<div class="answer-card-meta">' + [c.price ? "<b>" + esc(c.price) + "</b>" : "", c.rating ? "★ " + esc(c.rating) : ""].filter(Boolean).join(" · ") + "</div>" +
          (c.merchants && c.merchants.length ? '<div class="answer-card-merchant">' + esc(c.merchants.join("、")) + "</div>" : "") +
          (c.target ? '<div class="answer-card-flag">' + (c.official ? "本品 · 有官网购买链接" : "本品 · 无官网购买链接") + "</div>" : "") +
          "</div>";
      }).join("") + "</div></section>";
  }

  function drawerOverview(key, record, dplat, runs) {
    function recFor(plat) {
      var sl = ENGINE ? ENGINE.slice({ regions: state.sel.regions, platforms: plat ? [plat] : state.sel.platforms, intents: [], topics: [] })
        : (SLICES[sliceKey(state.region, plat, "")] || {});
      return (sl.records || []).filter(function (r) { return String(r.qid).padStart(4, "0") === key; })[0] || null;
    }
    var rec = recFor(dplat) || record || {};
    var filter = '<div class="drawer-plat">' + [""].concat(selPlatforms()).map(function (p) {
      return '<button class="tab-btn' + (p === dplat ? " active" : "") + '" type="button" data-dplat="' + esc(p) +
        '" data-dplat-qid="' + key + '">' + esc(p || "全部平台") + "</button>";
    }).join("") + "</div>";
    // 品牌对比：目标品牌、配置竞品，再加本题被提到最多的开放品牌，最多 8 个
    var brands = (rec.brands || []).slice();
    var core = brands.filter(function (b) { return b.role === "target" || b.role === "competitor"; });
    var open = brands.filter(function (b) { return b.role !== "target" && b.role !== "competitor" && b.mention_count; })
      .sort(function (a, b) { return b.mention_count - a.mention_count; });
    var shown = core.concat(open).slice(0, 8).sort(function (a, b) {
      return (b.mention_count - a.mention_count) || ((a.role === "target") ? 1 : -1);
    });
    function pct(v) { return v === null || v === undefined ? "—" : (v === 0 ? "0%" : (v * 100).toFixed(1) + "%"); }
    // 列同问题明细（排名不放：表本身按提及率排序）；点名类型的题不出提及类三列
    var named = record && ["发现", "替代", "问题解决"].indexOf(record.intent) < 0;
    var bs = rec.brand_sentiment || {};
    var head = "<th>品牌</th>" + (named ? "" : "<th>提及率</th><th>声量份额</th><th>平均提及位置</th>") +
      "<th>引用份额</th><th>引用率</th>" + (HAS_SENTIMENT ? "<th>正向情感占比</th>" : "");
    var comp = shown.length ? '<h4 class="drawer-sec">品牌对比</h4><table class="drawer-table"><thead><tr>' + head + "</tr></thead><tbody>" +
      shown.map(function (b) {
        var miss = !b.mention_count;
        return "<tr" + (b.role === "target" ? ' class="self"' : "") + "><td>" + esc(displayBrand(b.name)) + (b.role === "target" ? " ★" : "") + "</td>" +
          (named ? "" : "<td>" + (miss ? '<span class="miss">未提及</span>' : pct(b.mention_rate)) + "</td><td>" + (miss ? "—" : pct(b.share_of_voice)) +
            "</td><td>" + (b.average_rank ? b.average_rank.toFixed(1) : "—") + "</td>") +
          "<td>" + pct(b.citation_share) + "</td><td>" + pct(b.citation_rate) + "</td>" +
          (HAS_SENTIMENT ? "<td>" + esc(bs[b.name] || "—") + "</td>" : "") + "</tr>";
      }).join("") + "</tbody></table>" : "";
    var plat = "";
    if (false) {
      plat = '<h4 class="drawer-sec">' + esc(META.brand || "本品") + ' 各平台读数</h4><table class="drawer-table"><thead><tr><th>平台</th><th>提及率</th>' +
        "<th>声量份额</th><th>引用份额</th><th>引用率</th></tr></thead><tbody>" + (META.platforms || []).map(function (p) {
          var r = recFor(p) || {};
          return "<tr><td>" + esc(p) + "</td><td>" + esc(r.mention_rate || "—") + "</td><td>" + esc(r.share || "—") + "</td><td>" +
            esc(r.citation_share || "—") + "</td><td>" + esc(r.citation_rate || "—") + "</td></tr>";
        }).join("") + "</tbody></table>";
    }
    function fan(field, title, note, emptyText) {
      var cnt = {}, order = [];
      runs.forEach(function (x) {
        (x.entry[field] || []).forEach(function (q) {
          var k = x.platform + "|" + q;
          if (!cnt[k]) { cnt[k] = 0; order.push(k); }
          cnt[k] += 1;
        });
      });
      var head = '<h4 class="drawer-sec">' + esc(title) + "</h4>";
      if (!order.length) return "";
      order.sort(function (a, b) { return cnt[b] - cnt[a]; });
      return head + '<table class="drawer-table"><thead><tr><th>' + (field === "fanout" ? "检索词" : "延伸问题") +
        "</th><th>平台</th><th>出现次数</th></tr></thead><tbody>" + order.map(function (k) {
          var i = k.indexOf("|");
          return "<tr><td>" + esc(k.slice(i + 1)) + "</td><td>" + esc(k.slice(0, i)) + "</td><td>" + cnt[k] + "</td></tr>";
        }).join("") + "</tbody></table>";
    }
    var rows = runs.map(function (x) {
      var r = x.entry;
      var hit = (r.brands || []).some(function (b) { return b.target; });
      var names = (r.brands || []).map(function (b) { return displayBrand(b.name); }).join("、");
      return "<tr><td>" + esc(x.platform) + '</td><td class="num">' + esc(x.run) + '</td><td class="num">' + esc(r.time || "—") + "</td>" +
        '<td class="' + (hit ? "hit" : "miss") + '">' + (hit ? "提及" : "未提及") + "</td><td>" + esc(names || "—") + "</td>" +
        '<td class="num">' + esc(r.citation_share || "—") + "</td>" +
        '<td class="center"><button class="detail-btn" type="button" data-run="' + esc(x.key) + '" data-run-qid="' + key + '">查看回答</button></td></tr>';
    }).join("");
    return '<div class="drawer-overview">' +
      '<div class="drawer-overview-head"><div><p class="drawer-q">' + esc(record ? record.en : "") + "</p>" +
      '<p class="drawer-zh">' + esc(record ? record.zh : "") + "</p>" +
      '<p class="drawer-tags"><span>' + esc(record ? record.topic : "—") + "</span><span>" + esc(record ? record.intent : "—") + "</span></p></div>" +
      "</div>" + filter + comp + plat +
      fan("fanout", "Query Fan-outs", "", "") +
      '<h4 class="drawer-sec">回答记录</h4>' +
      (rows ? '<table class="drawer-table runs"><colgroup><col style="width:12%"><col style="width:7%"><col style="width:13%"><col style="width:9%"><col><col style="width:10%"><col style="width:12%"></colgroup>' +
        "<thead><tr><th>平台</th><th>运行</th><th>采集时间</th><th>" + esc(META.brand || "本品") + "</th><th>提到的品牌</th><th>引用份额</th><th class=\"center\">操作</th></tr></thead><tbody>" +
        rows + "</tbody></table>" : '<p class="support-line">当前采集目录里没有这道题的原始回答。</p>') +
      "</div>";
  }

  function openDrawer(qid) {
    var key = String(qid).padStart(4, "0");
    var record = recordsForSlice().filter(function (r) {
      return String(r.qid).padStart(4, "0") === key;
    })[0];
    var body = document.getElementById("drawerBody");
    if (!body) return;
    var dplat = state.drawerPlat[key] !== undefined ? state.drawerPlat[key] : (state.platform || "");
    var runs = runsFor(qid, dplat);
    var picked = runs.filter(function (x) { return x.key === state.drawerRun[key]; })[0];
    function open() {
      document.getElementById("drawerMask").classList.add("open");
      document.body.style.overflow = "hidden";
    }
    if (!picked) {
      body.innerHTML = drawerOverview(key, record, dplat, runs);
      open();
      return;
    }
    var entry = picked.entry;
    var variantTabs = '<div class="run-nav"><button class="variant-tab" type="button" data-run="" data-run-qid="' + key +
      '">← 返回列表</button><span>' + esc(picked.platform) + " · 第 " + esc(picked.run) + " 次 · " + esc(entry.time || "") + "</span></div>";
    var ranking = (entry.brands || []).map(function (row) {
      return '<div class="brand-rank-row' + (row.target ? " self-brand" : "") + '">' +
        '<span class="brand-name">' + logo(row.domain, 18, row.name) + esc(displayBrand(row.name)) + (row.target ? ' <span class="drawer-sentiment-star">★</span>' : '') + "</span><strong>" +
        esc(row.rank) + "</strong></div>";
    }).join("") || '<p class="support-line">该回答未提及已配置品牌</p>';

    // 引用列表：icon + URL 同一行，URL 单行截断，hover 显示完整
    function citationRow(row, hidden) {
      return '<article class="citation-item"' + (hidden ? " hidden" : "") + ">" +
        logo(row.host, 18) +
        '<a class="citation-url" href="' + esc(row.url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(row.url) + '">' + esc(row.url) + "</a></article>";
    }
    // 引用：平台原始字段（去重后的 URL）
    var platformCitations = (entry.platform_citations || []).map(function (row, index) {
      return citationRow(row, index >= 5);
    }).join("");
    if (!platformCitations) platformCitations = '<p class="support-line">该回答没有可解析的引用记录</p>';
    var citationToggle = (entry.platform_citations || []).length > 5
      ? '<button class="source-toggle" type="button" data-source-toggle aria-expanded="false">查看全部来源</button>'
      : "";

    // 搜索来源：仅 ChatGPT 的 search_result
    var searchResults = (entry.search_results || []).map(function (row, index) {
      var host = row.url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
      return citationRow({ host: host, url: row.url }, index >= 5);
    }).join("");
    var searchSection = "";
    if (searchResults) {
      searchSection = '<section class="detail-section"><div class="detail-section-head"><h4>搜索来源</h4><span>' +
        (entry.search_results || []).length + ' 个结果</span></div>' +
        '<div class="citation-list">' + searchResults + "</div>" +
        ((entry.search_results || []).length > 5
          ? '<button class="source-toggle" type="button" data-source-toggle aria-expanded="false">查看全部来源</button>'
          : "") + "</section>";
    }

    // 品牌情感：展示该回答中识别到品牌的正/负向 claim 标签
    var sentimentBrands = HAS_SENTIMENT ? (((entry.sentiment || {}).brands) || []) : [];
    var sentimentSection = "";
    if (sentimentBrands.length) {
      var targetName = META.brand || "";
      var sorted = sentimentBrands.slice().sort(function (a, b) {
        if (a.brand === targetName) return -1;
        if (b.brand === targetName) return 1;
        return 0;
      });
      var blocks = sorted.map(function (sb) {
        var isTarget = sb.brand === targetName;
        // 按 label 去重，同一 label 只显示一次
        var seen = {};
        var claims = [];
        (sb.pos_claims || []).forEach(function (c) {
          var label = c.label || "";
          if (seen["pos|" + label]) return;
          seen["pos|" + label] = true;
          claims.push('<div class="drawer-claim"><span class="drawer-claim-dir pos">正向</span>' +
            '<span class="drawer-claim-label">' + esc(naturalAttr(label)) + '</span></div>');
        });
        (sb.neg_claims || []).forEach(function (c) {
          var label = c.label || "";
          if (seen["neg|" + label]) return;
          seen["neg|" + label] = true;
          claims.push('<div class="drawer-claim"><span class="drawer-claim-dir neg">负向</span>' +
            '<span class="drawer-claim-label">' + esc(naturalAttr(label)) + '</span></div>');
        });
        if (!claims.length) return "";
        return '<div class="drawer-sentiment-brand' + (isTarget ? " is-target" : "") + '">' +
          '<div class="drawer-sentiment-name">' + esc(displayBrand(sb.brand)) + (isTarget ? ' <span class="drawer-sentiment-star">★</span>' : '') + '</div>' +
          claims.join("") + '</div>';
      }).filter(Boolean).join("");
      if (blocks) {
        sentimentSection = '<section class="detail-section"><div class="detail-section-head"><h4>品牌情感</h4></div>' +
          '<div class="drawer-sentiment">' + blocks + '</div></section>';
      }
    }

    body.innerHTML =
      '<div class="detail-layout"><div class="detail-main">' +
      variantTabs +
      '<p class="drawer-q">' + esc(record ? record.en : "") + "</p>" +
      '<p class="drawer-zh">' + esc(record ? record.zh : entry.question_zh) + "</p>" +
      // 主题、意图类型在问题概览里已经有，单次回答不再重复；商品卡放在回答正文前面
      productCardsBlock(entry.product_cards || [], entry) +
      // answer_html / answer_zh_html 在数据层由 markdown 转换并转义过，这里直接注入，不再二次 esc。
      answerSwitch(entry) +
      "</div>" +
      '<aside class="detail-side">' +
      '<section class="detail-section"><div class="detail-section-head"><h4>品牌提及</h4><span>' +
      (entry.brands || []).length + " 个结果</span></div>" +
      '<div class="brand-ranking">' + ranking + "</div></section>" +
      sentimentSection +
      '<section class="detail-section"><div class="detail-section-head"><h4>引用</h4><span>' +
      (entry.platform_citations || []).length + " 个来源</span></div>" +
      '<div class="citation-list">' + platformCitations + "</div>" + citationToggle + "</section>" +
      searchSection +
      "</aside></div>";

    document.getElementById("drawerMask").classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    var mask = document.getElementById("drawerMask");
    if (mask) mask.classList.remove("open");
    document.body.style.overflow = "";
  }

  /* ---------- 结论卡 ---------- */

  function setInsight(id, headline, points) {
    var el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = "<h4>" + esc(headline) + "</h4>" + (points.length
      ? "<ul>" + points.map(function (p) {
          return '<li><span class="point-copy">' + p + "</span></li>";
        }).join("") + "</ul>"
      : "");
  }

  function targetRow(rows) {
    return (rows || []).filter(function (r) { return r.target; })[0] || null;
  }

  function renderInsights() {
    var slice = currentSlice();
    var k = slice.kpis || {};
    var mention = (slice.competition || {}).mention || [];
    var target = mention.filter(function (r) { return (r[4] || "") === "gold"; })[0];
    var leader = mention[0];
    var scope = (state.region || "全部地区") + (state.platform ? " · " + state.platform : "") +
      (state.topic ? " · " + state.topic : "");

    if (isTypeOnlySlice(slice)) {
      setInsight("overviewInsight", "这一类问题题面点名了品牌，不统计提及率，逐题结果看「问题明细」。", []);
    } else if (leader && target) {
      var gap = (parseFloat(leader[2]) - parseFloat(target[2])).toFixed(1);
      var mentionRate = parseFloat(k.mention_rate) || 0;
      var mentionRank = parseInt(k.mention_rank) || 0;
      var shareRate = parseFloat(k.share_of_voice) || 0;
      var avgRank = parseFloat(k.average_rank) || 0;
      var citeShare = parseFloat(k.official_share) || 0;

      // 三层叙事：心智基本盘 → 断层 → 根因
      var narrative = "";
      if (mentionRate >= 60) {
        narrative = "AI 对本品牌「知道且主动推荐」——心智基本盘稳固，";
        if (mentionRank > 3) narrative += "但排名仍有提升空间，";
        narrative += "需守住现有优势并向薄弱环节渗透。";
      } else if (mentionRate >= 30) {
        narrative = "AI 对本品牌「知道但不主动推荐」——心智基本盘存在，";
        narrative += "但在这类问题中大量未进入首选名单，存在明显的推荐断层。";
      } else {
        narrative = "AI 对本品牌「认知薄弱」——在这类问题中极少被主动提及，";
        narrative += "心智基本盘尚未建立，需要先解决「被知道」的问题。";
      }

      setInsight("overviewInsight", narrative,
        [
          "<strong>心智现状：</strong>提及率 " + esc(k.mention_rate || "—") +
            "（第 " + esc(k.mention_rank || "—") + " 位），声量份额 " + esc(k.share_of_voice || "—") +
            "，平均提及位置 " + esc(k.average_rank || "—") + "。",
          "<strong>与头部差距：</strong>当前领先品牌为 " + esc(leader[0]) + "（" + esc(leader[2]) +
            "），监测对象与其相差 " + gap + " 个百分点。",
          citeShare < 5
            ? "<strong>根因判断：</strong>引用份额仅 " + esc(k.official_share || "—") +
              "，AI 可引用的官方事实源不足，第三方信源主导了叙事权。"
            : "<strong>信源优势：</strong>引用份额 " + esc(k.official_share || "—") +
              "，官方事实源已有基础，可继续扩大覆盖。"
        ]);
    } else {
      setInsight("overviewInsight", "当前切片下监测对象未出现在任何回答中。", []);
    }

    var matrix = slice.matrix || {};
    var sentTarget = targetRow(matrix.mention || []);
    var platforms = matrix.platforms || [];
    if (sentTarget && platforms.length) {
      // 跨平台横切看共识：所有平台两两差距都 ≤10pt 才叫有共识；否则就是无共识，
      // 直接点名提及率最高的平台，并把单一平台高低和"优化目标"解耦。
      var vals = (sentTarget.vals || []).map(function (v, i) {
        return v === null || v === undefined ? null : { name: platforms[i], value: v };
      }).filter(Boolean);
      var headline = "";
      var points = [];
      if (isTypeOnlySlice(slice)) {
        headline = "这个主题只有对比或评价题，不算提及率。";
      } else if (!vals.length) {
        headline = "当前切片下监测对象未进入任何平台回答。";
      } else {
        var sorted = vals.slice().sort(function (a, b) { return b.value - a.value; });
        var top = sorted[0];
        var bottom = sorted[sorted.length - 1];
        var spread = top.value - bottom.value;
        if (spread <= 10 && sorted.length >= 2) {
          var avg = sorted.reduce(function (a, c) { return a + c.value; }, 0) / sorted.length;
          headline = "跨平台存在共识：各平台提及率接近（均值约 " + avg.toFixed(1) + "%）。";
          points.push("<strong>各平台：</strong>" + sorted.map(function (c) {
            return c.name + " " + c.value.toFixed(1) + "%";
          }).join("、") + "。");
        } else {
          headline = "跨平台差距较大（最高与最低相差 " + spread.toFixed(1) + " 个百分点），未形成共识。";
          points.push("<strong>提及率最高：</strong>" + top.name + " " + top.value.toFixed(1) + "%。");
          if (sorted.length > 1) {
            points.push("<strong>其他平台：</strong>" + sorted.slice(1).map(function (c) {
              return c.name + " " + c.value.toFixed(1) + "%";
            }).join("、") + "。");
          }
        }
      }
      setInsight("competitionInsight", headline, points);
    }

    var sources = slice.sources || {};
    var topDomain = (sources.domains || [])[0];
    var officialPages = (sources.official_pages || []).length;
    // 官网引用份额与最大竞品来源的对比：只说「可继续扩展」太空，客户要的是
    // 「差在哪些内容上」。用类别里竞品网站的份额与目标官网份额对照，并点名
    // 最大来源域名，把差距落到具体来源。
    var compType = ((sources.types || []).filter(function (r) { return r[0] === "竞品网站"; })[0]) || null;
    var ownShare = parseFloat(String(sources.official_share || "").replace("%", ""));
    var compShare = compType ? parseFloat(String(compType[1]).replace("%", "")) : null;
    var gapNote = "";
    if (isFinite(ownShare) && isFinite(compShare) && compShare > 0) {
      gapNote = "<strong>差距：</strong>竞品网站合计 " + esc(compType[1]) +
        "，是本品官网的 " + (compShare / Math.max(ownShare, 0.1)).toFixed(1) + " 倍";
      if (topDomain) {
        gapNote += "；最大来源是 " + esc(topDomain[0]) + "（" + esc(topDomain[1]) + "）";
      }
      gapNote += "。";
    }
    setInsight("sourcesInsight",
      "引用份额 " + esc(sources.official_share || "—") + "，引用率 " + esc(sources.official_citation_rate || "—") + "。",
      [
        topDomain ? "<strong>最大来源：</strong>" + esc(topDomain[0]) + "（" + esc(topDomain[2]) +
          "，占 " + esc(topDomain[1]) + "）。" : "",
        officialPages <= 2
          ? "<strong>风险：</strong>官网可被引用的页面过少，事实定义权主要落在第三方。"
          : gapNote
      ].filter(Boolean));

  }

  function emptyRow(text) {
    return '<p class="support-line">' + esc(text) + "</p>";
  }

  /* ---------- 渲染总入口 ---------- */

  function renderAll() {
    renderScopes();
    renderKpis();
    renderCompetition();
    renderSources();
    renderSentiment();
    renderShopping();
    renderRecords();
    renderInsights();
    if (ENGINE) renderMultiFilters(); else renderTabs();
  }

  /* ---------- 多选筛选（引擎模式） ---------- */

  var MSEL_DIMS = [
    { id: "regionSelect", key: "regions", all: "全部地区", unit: "个地区" },
    { id: "platformSelect", key: "platforms", all: "全部平台", unit: "个平台" },
    { id: "intentSelect", key: "intents", all: "全部意图类型", unit: "种意图类型" },
    { id: "topicSelect", key: "topics", all: "全部主题", unit: "个主题" }
  ];
  function mselValues(key) {
    var intentTopics = META.intent_topics || {};
    if (key === "regions") return META.regions || [];
    if (key === "platforms") return META.platforms || [];
    if (key === "intents") return Object.keys(intentTopics);
    // 主题按选中的意图类型收窄
    if (!state.sel.intents.length) return META.topics || [];
    return (META.topics || []).filter(function (t) {
      return state.sel.intents.some(function (i) { return (intentTopics[i] || []).indexOf(t) >= 0; });
    });
  }
  function mselShown(key) {
    // 整份报告只有一个取值的维度不出（主题看全量，不因收窄后只剩一个而消失）
    if (key === "topics") return (META.topics || []).length > 1;
    return mselValues(key).length > 1;
  }
  function renderMultiFilters() {
    var shown = 0;
    MSEL_DIMS.forEach(function (d) {
      var host = document.getElementById(d.id);
      if (!host) return;
      if (host.tagName === "SELECT") {
        var div = document.createElement("div");
        div.id = d.id;
        div.className = "multi-select";
        div.setAttribute("aria-label", host.getAttribute("aria-label") || d.all);
        host.parentNode.replaceChild(div, host);
        host = div;
      }
      if (!mselShown(d.key)) { host.style.display = "none"; host.innerHTML = ""; return; }
      shown += 1;
      host.style.display = "";
      var chosen = state.sel[d.key];
      var label = !chosen.length ? d.all : chosen.length <= 2 ? chosen.join("、") : chosen.length + " " + d.unit;
      var open = state.openMsel === d.key;
      host.classList.toggle("open", open);
      host.innerHTML = '<button type="button" class="multi-select-button' + (chosen.length ? " has-value" : "") +
        '" data-msel-toggle="' + d.key + '" aria-expanded="' + open + '" title="' + esc(chosen.join("、") || d.all) + '">' + esc(label) + "</button>" +
        '<div class="multi-select-menu">' +
        '<button type="button" class="multi-select-option msel-all' + (chosen.length ? "" : " on") + '" data-msel-clear="' + d.key + '">' + esc(d.all) + "</button>" +
        mselValues(d.key).map(function (v) {
          return '<label class="multi-select-option"><input type="checkbox" data-msel="' + d.key + '" value="' + esc(v) + '"' +
            (chosen.indexOf(v) >= 0 ? " checked" : "") + "><span>" + esc(v) + "</span></label>";
        }).join("") + "</div>";
    });
    var box = document.getElementById("sharedFilter");
    if (box) box.style.display = shown ? "" : "none";
  }
  function afterFilterChange(key) {
    if (key === "intents") {
      var allowed = mselValues("topics");
      state.sel.topics = state.sel.topics.filter(function (t) { return allowed.indexOf(t) >= 0; });
    }
    state.page = 1;
    state.sourcePage = { domains: 1, pages: 1, official: 1 };
    renderAll();
  }

  /* ---------- 事件 ---------- */

  // 指标说明浮层：挂在 body 上、fixed 定位，不会被表格外框（overflow）裁掉，也不会跑出屏幕
  function bindTips() {
    var tip = document.createElement("div");
    tip.className = "float-tip";
    tip.hidden = true;
    document.body.appendChild(tip);
    function show(el) {
      var text = el.getAttribute("data-tip");
      if (!text) return;
      tip.textContent = text;
      tip.hidden = false;
      var r = el.getBoundingClientRect();
      var w = tip.offsetWidth, h = tip.offsetHeight;
      var left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
      var top = r.top - h - 8;
      if (top < 8) top = r.bottom + 8;
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    }
    function hide() { tip.hidden = true; }
    document.addEventListener("mouseover", function (e) {
      var el = e.target.closest(".info[data-tip]");
      if (el) show(el); else if (!e.target.closest(".float-tip")) hide();
    });
    document.addEventListener("focusin", function (e) {
      var el = e.target.closest(".info[data-tip]");
      if (el) show(el);
    });
    document.addEventListener("focusout", hide);
    window.addEventListener("scroll", hide, true);
  }

  // 筛选吸顶时贴在顶栏下面；顶栏高度随窗口宽度变，按实际高度算
  function pinFilter() {
    var bar = document.querySelector(".topbar");
    var box = document.getElementById("sharedFilter");
    if (bar && box) box.style.top = bar.offsetHeight + "px";
  }

  function bindEvents() {
    bindTips();
    pinFilter();
    window.addEventListener("resize", pinFilter);
    document.addEventListener("change", function (event) {
      var box = event.target.closest("input[data-msel]");
      if (box) {
        var key = box.getAttribute("data-msel");
        var picked = {};
        state.sel[key].forEach(function (v) { picked[v] = 1; });
        if (box.checked) picked[box.value] = 1; else delete picked[box.value];
        state.sel[key] = mselValues(key).filter(function (v) { return picked[v]; });
        afterFilterChange(key);
        return;
      }
      var sel = event.target.closest("select#regionSelect,select#platformSelect,select#intentSelect,select#topicSelect");
      if (!sel) return;
      if (sel.id === "regionSelect") {
        state.region = sel.value;
      } else if (sel.id === "platformSelect") {
        state.platform = sel.value;
      } else if (sel.id === "intentSelect") {
        state.intent = sel.value;
        // 换了意图类型，主题不在这一类里就清掉
        var allowed = (META.intent_topics || {})[state.intent] || META.topics || [];
        if (state.topic && state.intent && allowed.indexOf(state.topic) < 0) state.topic = "";
      } else {
        state.topic = sel.value;
      }
      state.page = 1;
      state.sourcePage = { domains: 1, pages: 1, official: 1 };
      renderAll();
    });
    document.addEventListener("click", function (event) {
      var toggle = event.target.closest("[data-msel-toggle]");
      if (toggle) {
        var tk = toggle.getAttribute("data-msel-toggle");
        state.openMsel = state.openMsel === tk ? null : tk;
        renderMultiFilters();
        return;
      }
      var clear = event.target.closest("[data-msel-clear]");
      if (clear) {
        var ck = clear.getAttribute("data-msel-clear");
        state.sel[ck] = [];
        afterFilterChange(ck);
        return;
      }
      // 点下拉以外的地方收起
      if (state.openMsel && !event.target.closest(".multi-select")) {
        state.openMsel = null;
        renderMultiFilters();
      }
      var shopBtn = event.target.closest("[data-shop-level]");
      if (shopBtn) {
        state.shopLevel = shopBtn.getAttribute("data-shop-level");
        Array.prototype.forEach.call(document.querySelectorAll("[data-shop-level]"), function (btn) {
          btn.classList.toggle("active", btn === shopBtn);
        });
        renderShopping();
        return;
      }
    });
    document.addEventListener("click", function (event) {
      var tab = event.target.closest(".filter-tabs [data-region],.filter-tabs [data-platform],.filter-tabs [data-topic]");
      if (tab) {
        if (tab.hasAttribute("data-region")) state.region = tab.getAttribute("data-region");
        if (tab.hasAttribute("data-platform")) state.platform = tab.getAttribute("data-platform");
        if (tab.hasAttribute("data-topic")) {
          var next = tab.getAttribute("data-topic");
          state.topic = (tab.getAttribute("data-toggle") === "1" && state.topic === next) ? "" : next;
        }
        state.page = 1;
        state.sourcePage = { domains: 1, pages: 1, official: 1 };
        renderAll();
        return;
      }
      var switchBtn = event.target.closest("[data-matrix-metric]");
      if (switchBtn) {
        state.matrixMetric = switchBtn.getAttribute("data-matrix-metric");
        Array.prototype.forEach.call(document.querySelectorAll("[data-matrix-metric]"), function (btn) {
          btn.classList.toggle("active", btn === switchBtn);
        });
        renderMatrix();
        return;
      }
      var chip = event.target.closest("[data-claim]");
      if (chip) {
        var sliceNow = currentSlice();
        var parts = chip.getAttribute("data-claim").split(":");
        var group = ((sliceNow.sentiment || {}).claims || {})[parts[0]] || [];
        Array.prototype.forEach.call(document.querySelectorAll(".sentiment-chip"), function (btn) {
          btn.classList.remove("active");
        });
        chip.classList.add("active");
        showEvidence(group[Number(parts[1])], parts[0]);
        return;
      }
      var openAnswer = event.target.closest("[data-open-answer]");
      if (openAnswer) {
        var wantRegion = openAnswer.getAttribute("data-open-region");
        var wantPlatform = openAnswer.getAttribute("data-open-platform");
        if (ENGINE) {
          var oq = String(openAnswer.getAttribute("data-open-answer")).padStart(4, "0");
          state.drawerRun[oq] = null;
          state.drawerPlat[oq] = selPlatforms().indexOf(wantPlatform) >= 0 ? wantPlatform : "";
          openDrawer(oq);
          return;
        }
        if (wantRegion && META.regions.indexOf(wantRegion) >= 0) state.region = wantRegion;
        if (wantPlatform && META.platforms.indexOf(wantPlatform) >= 0) state.platform = wantPlatform;
        state.topic = "";
        renderAll();
        openDrawer(openAnswer.getAttribute("data-open-answer"));
        return;
      }
      var groupHead = event.target.closest(".group-head");
      if (groupHead) {
        var group = groupHead.closest(".topic-group");
        var name = group.getAttribute("data-group-topic");
        var willOpen = !group.classList.contains("open");
        group.classList.toggle("open", willOpen);
        state.expanded[name] = willOpen;
        return;
      }
      var sourcePageBtn = event.target.closest("[data-source-list]");
      if (sourcePageBtn) {
        if (!sourcePageBtn.disabled) {
          state.sourcePage[sourcePageBtn.getAttribute("data-source-list")] = Number(sourcePageBtn.getAttribute("data-page"));
          renderSources();
        }
        return;
      }
      var pageBtn = event.target.closest(".page-btn");
      if (pageBtn && !pageBtn.disabled) {
        state.page = Number(pageBtn.getAttribute("data-page"));
        renderRecords();
        return;
      }
      var answerTab = event.target.closest("[data-answer-tab]");
      if (answerTab) {
        var wanted = answerTab.getAttribute("data-answer-tab");
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .answer-tab"), function (btn) {
          var on = btn === answerTab;
          btn.classList.toggle("active", on);
          btn.setAttribute("aria-selected", String(on));
        });
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .answer-panel"), function (panel) {
          panel.classList.toggle("active", panel.getAttribute("data-answer-panel") === wanted);
        });
        return;
      }
      var sourceToggle = event.target.closest("[data-source-toggle]");
      if (sourceToggle) {
        var expanded = sourceToggle.getAttribute("aria-expanded") === "true";
        sourceToggle.setAttribute("aria-expanded", String(!expanded));
        sourceToggle.textContent = expanded ? "查看全部来源" : "收起来源";
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .citation-item"), function (item, index) {
          if (index >= 5) item.hidden = expanded;
        });
        return;
      }
      var detailBtn = event.target.closest("[data-detail]");
      if (detailBtn) {
        var dq = String(detailBtn.getAttribute("data-detail")).padStart(4, "0");
        state.drawerRun[dq] = null;
        state.drawerPlat[dq] = state.platform || "";
        openDrawer(dq);
        return;
      }
      var platBtn = event.target.closest("[data-dplat-qid]");
      if (platBtn) {
        state.drawerPlat[platBtn.getAttribute("data-dplat-qid")] = platBtn.getAttribute("data-dplat");
        openDrawer(platBtn.getAttribute("data-dplat-qid"));
        return;
      }
      var runBtn = event.target.closest("[data-run-qid]");
      if (runBtn) {
        var rq = runBtn.getAttribute("data-run-qid");
        state.drawerRun[rq] = runBtn.getAttribute("data-run") || null;
        openDrawer(rq);
        var bodyEl = document.getElementById("drawerBody");
        if (bodyEl) bodyEl.scrollTop = 0;
        return;
      }
      if (event.target.closest("#drawerClose") || event.target.id === "drawerMask") { closeDrawer(); return; }
      var variantTab = event.target.closest("[data-variant]");
      if (variantTab) {
        var vKey = variantTab.getAttribute("data-variant");
        var vQid = variantTab.getAttribute("data-variant-qid");
        state.drawerVariant = state.drawerVariant || {};
        state.drawerVariant[String(vQid).padStart(4, "0")] = vKey;
        openDrawer(vQid);
        return;
      }
      var intentSelect = event.target.closest("#recordIntentFilter");
      if (intentSelect) return; // select handled by change event below
    });

    var searchEl = document.getElementById("recordSearch");
    if (searchEl) {
      searchEl.addEventListener("input", function () {
        state.recordQuery = searchEl.value;
        state.page = 1;
        renderRecords();
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        if (state.openMsel) { state.openMsel = null; renderMultiFilters(); return; }
        closeDrawer();
      }
    });

    var navLinks = Array.prototype.slice.call(document.querySelectorAll(".nav a"));
    var sections = navLinks.map(function (link) { return document.querySelector(link.getAttribute("href")); });
    window.addEventListener("scroll", function () {
      var activeIndex = 0;
      sections.forEach(function (section, index) {
        if (section && section.getBoundingClientRect().top <= 120) activeIndex = index;
      });
      navLinks.forEach(function (link, index) { link.classList.toggle("active", index === activeIndex); });
    }, { passive: true });
  }

  function boot() {
    if (!META.regions || !META.regions.length) {
      var main = document.getElementById("main");
      if (main) main.insertAdjacentHTML("afterbegin", '<p class="support-line">报告数据缺失：meta.regions 为空。</p>');
      return;
    }
    state.region = "";
    try {
      renderMasthead();
      renderAll();
      bindEvents();
    } catch (error) {
      // 渲染期异常会让页面半渲染且没有明显症状，这里显式报出来，避免把残页当成品交付。
      var main = document.getElementById("main");
      if (main) {
        main.insertAdjacentHTML("afterbegin",
          '<p class="support-line" style="color:var(--red)">报告渲染中断：' +
          esc(error && error.message) + "。请检查 report.js 与 report-data.json。</p>");
      }
      if (window.console && console.error) console.error(error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
