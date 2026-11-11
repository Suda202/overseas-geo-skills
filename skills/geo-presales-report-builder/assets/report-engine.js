/* 海外 GEO 售前诊断报告 · 前端计算引擎（2026-11-07）
 *
 * 数据筛选支持多选（几个平台、几种意图类型、几个主题合在一起看）。预算切片只覆盖单选组合，
 * 多选时由本引擎从 DATA.facts（逐条有效回答的原始事实 + Claim）现算出与预算切片同结构的数据，
 * 渲染层不用分两套。公式逐条对应 Python 实现：
 *   提及类 / 引用 KPI / 可见度矩阵   build_report_data.build_slice + core metrics.compute_metrics
 *   引用模块                         build_report_data.build_sources
 *   问题明细                         build_report_data.build_records + attach_sentiment 明细列
 *   情感模块                         attach_sentiment.build_claims_sentiment
 *   商品卡                           core shopping.compute_shopping_metrics（render_report.slim_shopping 的字段）
 * 单选组合下本引擎的输出必须与预算切片逐项一致：scripts/check_engine_parity.js 逐切片对账。
 * 改任何一侧的口径，两侧一起改，再跑对账。
 */
(function (root) {
  "use strict";

  // ---------- 与 Python 一致的格式化 ----------

  // Python f"{x:.{d}f}"：按 double 的精确值舍入，恰好落在 5 上时取偶数（JS toFixed 取大的）
  function pyFixed(x, d) {
    var full = x.toFixed(Math.min(100, d + 25));
    var dot = full.indexOf(".");
    var cut = dot + d + 1;
    var tail = full.slice(cut);
    if (/^50*$/.test(tail)) {
      var kept = full.slice(0, d ? cut : dot);
      var last = Number(kept.replace(".", "").slice(-1));
      if (last % 2 === 0) return kept;
    }
    return x.toFixed(d);
  }
  function fmtPct(frac) { return frac === null || frac === undefined ? "—" : pyFixed(frac * 100, 1) + "%"; }
  function fmtNum(v) { return v === null || v === undefined ? "—" : pyFixed(v, 1); }
  function pctNum(v) { return v === null || v === undefined ? null : Number(pyFixed(v * 100, 1)); }
  function round1(v) { return v === null || v === undefined ? null : Number(pyFixed(v, 1)); }
  function barWidth(value, max) {
    if (value === null || value === undefined || !max || max <= 0) return "0%";
    var pct = value / max * 100;
    return pct >= 99.95 ? "100%" : pyFixed(pct, 1) + "%";
  }
  // core _percent(digits=1) / _average(digits=1)：十进制精确值四舍五入（ROUND_HALF_UP），整数百分比去掉小数点
  //（8.45% → "8.5%"，8.0% → "8%"）。商品卡指标一律 1 位小数，与核心洞察的百分比同一精度。
  function corePercent(num, den) {
    if (!den) return { numerator: num, denominator: den, display: "—", raw: null };
    var tenths = Math.floor((2000 * num + den) / (2 * den));
    var text = (tenths / 10).toFixed(1).replace(/\.0$/, "");
    return { numerator: num, denominator: den, display: text + "%", raw: num / den };
  }
  function coreAverage(values) {
    if (!values.length) return { numerator: 0, denominator: 0, display: "—", raw: null };
    var sum = values.reduce(function (a, b) { return a + b; }, 0), n = values.length;
    var tenths = Math.floor((20 * sum + n) / (2 * n));
    return { numerator: sum, denominator: n, display: "#" + (tenths / 10).toFixed(1), raw: sum / n };
  }
  function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  function create(DATA) {
    var F = DATA.facts || {};
    var META = DATA.meta || {};
    var OBJ = F.objects || [];
    var TARGET = OBJ.map(function (o) { return o.role; }).indexOf("target");
    var Q = {};
    (META.questions || []).forEach(function (q) { Q[Number(q.qid)] = q; });
    var SENT = F.sentiment || null;
    var CLAIMS = F.claims || [];
    var INTERNAL_TO_LABEL = {};
    if (SENT) Object.keys(SENT.platform_internal || {}).forEach(function (label) {
      if ((META.platforms || []).indexOf(label) >= 0) INTERNAL_TO_LABEL[SENT.platform_internal[label]] = label;
    });
    var BUCKET = (F.source_types || []).map(function (t) { return t.bucket; });

    function inSel(list, value) { return !list || !list.length || list.indexOf(value) >= 0; }
    function qOk(sel, qid) {
      var q = Q[qid] || {};
      return inSel(sel.intents, q.intent) && inSel(sel.topics, q.topic);
    }
    function pick(sel) {
      return (F.answers || []).filter(function (a) {
        return inSel(sel.regions, a.r) && inSel(sel.platforms, a.p) && qOk(sel, a.q);
      });
    }
    function intentOf(a) { return (Q[a.q] || {}).intent; }
    function visibility(answers) {
      var groups = F.visibility_groups || [];
      for (var i = 0; i < groups.length; i += 1) {
        var got = answers.filter(function (a) { return groups[i].indexOf(intentOf(a)) >= 0; });
        if (got.length) return got;
      }
      return [];
    }
    function mentionedSet(a) {
      var m = {};
      a.m.forEach(function (x) { m[x[0]] = x[1]; });
      return m;
    }

    // ---------- 品牌行（build_slice rows） ----------
    function objectRows(answers) {
      var vis = visibility(answers);
      var counts = OBJ.map(function () { return 0; });
      var ranks = OBJ.map(function () { return []; });
      var cites = 0, own = OBJ.map(function () { return 0; });
      vis.forEach(function (a) {
        a.m.forEach(function (x) {
          counts[x[0]] += 1;
          if (x[1] !== null && x[1] !== undefined) ranks[x[0]].push(x[1]);
        });
        a.c.forEach(function (c) { cites += 1; if (c[0] >= 0) own[c[0]] += 1; });
      });
      var total = counts.reduce(function (s, v) { return s + v; }, 0);
      return OBJ.map(function (o, i) {
        return {
          index: i, role: o.role, name: o.name, domain: o.domain,
          topics: o.topics || [],
          mention_rate: vis.length ? counts[i] / vis.length : null,
          share_of_voice: total ? counts[i] / total : null,
          average_rank: ranks[i].length ? ranks[i].reduce(function (s, v) { return s + v; }, 0) / ranks[i].length : null,
          citation_share: cites ? own[i] / cites : null
        };
      });
    }
    function rankLookup(rows) {
      var out = {};
      if (rows.every(function (r) { return r.mention_rate === null; })) {
        rows.forEach(function (r) { out[r.index] = "—"; });
        return out;
      }
      var ordered = rows.slice().sort(function (a, b) {
        return ((b.mention_rate || 0) - (a.mention_rate || 0)) || cmp(a.name, b.name);
      });
      var last, lastRank = 0;
      ordered.forEach(function (r, i) {
        if (i === 0 || r.mention_rate !== last) { lastRank = i + 1; last = r.mention_rate; }
        out[r.index] = lastRank;
      });
      return out;
    }

    function slice(sel) {
      var answers = pick(sel);
      var rows = objectRows(answers);
      var vis = visibility(answers);
      // 配置竞品可挂在指定主题上（facts.objects[].topics）；选中的主题里只展示本线竞品。
      // 没选主题（全部 / 只选了意图类型）时展示全部配置竞品（2026-11-11 放开 3 个上限）。
      var selTopics = (sel.topics && sel.topics.length) ? sel.topics : [];
      var configured = rows.filter(function (r) {
        if (r.role === "target") return true;
        if (r.role !== "competitor") return false;
        if (!selTopics.length) return true;
        if (!r.topics || !r.topics.length) return true;
        return selTopics.some(function (t) { return r.topics.indexOf(t) >= 0; });
      });
      var open = rows.filter(function (r) { return r.role === "open"; }).sort(function (a, b) {
        return ((b.mention_rate || 0) - (a.mention_rate || 0)) || cmp(a.name, b.name);
      });
      var display = configured.concat(open.slice(0, 1));
      var byMention = display.slice().sort(function (a, b) {
        return ((b.mention_rate || 0) - (a.mention_rate || 0)) || ((a.role !== "target") - (b.role !== "target"));
      });
      var ranks = rankLookup(rows);
      var maxRate = Math.max.apply(null, byMention.map(function (r) { return r.mention_rate || 0; }).concat([0]));
      var fills = F.competition_fills || [], fi = 0;
      var mentionRows = [], shareValues = [];
      byMention.forEach(function (r) {
        var fill, label;
        if (r.role === "target") { fill = "gold"; label = r.name + " ★"; } else { fill = fills[fi % fills.length]; fi += 1; label = r.name; }
        mentionRows.push([label, r.domain, fmtPct(r.mention_rate), barWidth(r.mention_rate, maxRate), fill, ranks[r.index]]);
        shareValues.push(r.share_of_voice === null ? null : pctNum(r.share_of_voice));
      });
      var rankRows = display.slice().sort(function (a, b) {
        return (a.average_rank !== null ? a.average_rank : 999) - (b.average_rank !== null ? b.average_rank : 999);
      }).map(function (r) {
        var item = [r.role === "target" ? r.name + " ★" : r.name, r.domain, fmtNum(r.average_rank)];
        if (r.role === "target") item.push("target");
        return item;
      });
      // 可见度矩阵：列 = 选中的平台（没选 = 全部），值是同一筛选下逐平台单算
      var platforms = sel.platforms && sel.platforms.length
        ? (META.platforms || []).filter(function (p) { return sel.platforms.indexOf(p) >= 0; }) : (META.platforms || []);
      var perPlat = platforms.map(function (p) {
        return objectRows(answers.filter(function (a) { return a.p === p; }));
      });
      var matrix = { platforms: platforms, mention: [], share: [], rank: [], sent: [], official: [] };
      byMention.forEach(function (r) {
        var label = r.role === "target" ? r.name + " ★" : r.name;
        function row(fn) { return { name: label, target: r.role === "target", vals: perPlat.map(function (pr) { return fn(pr[r.index]); }) }; }
        matrix.mention.push(row(function (x) { return pctNum(x.mention_rate); }));
        matrix.share.push(row(function (x) { return pctNum(x.share_of_voice); }));
        matrix.rank.push(row(function (x) { return round1(x.average_rank); }));
        matrix.sent.push(row(function () { return null; }));
        matrix.official.push(row(function (x) { return pctNum(x.citation_share); }));
      });
      var target = rows[TARGET];
      var visCites = 0, visOwn = 0, visCited = 0;
      vis.forEach(function (a) {
        var hit = false;
        a.c.forEach(function (c) { visCites += 1; if (c[0] === TARGET) { visOwn += 1; hit = true; } });
        if (hit) visCited += 1;
      });
      return {
        kpis: {
          mention_rate: fmtPct(target.mention_rate),
          mention_rank: String(ranks[TARGET] !== undefined ? ranks[TARGET] : rows.length),
          share_of_voice: fmtPct(target.share_of_voice),
          average_rank: fmtNum(target.average_rank),
          official_share: visCites ? fmtPct(visOwn / visCites) : "—",
          official_citation_rate: vis.length ? fmtPct(visCited / vis.length) : "—"
        },
        competition: { mention: mentionRows, share: shareValues, rank: rankRows },
        matrix: matrix,
        sources: sources(answers),
        sentiment: sentiment(sel),
        shopping: shopping(answers, platforms),
        records: records(sel, answers),
        _counts: { valid_answers: answers.length, visibility_answers: vis.length }
      };
    }

    // ---------- 引用模块（build_sources，全部意图类型） ----------
    function sources(answers) {
      var limit = F.source_limit || 0;
      function top(list) { return limit > 0 ? list.slice(0, limit) : list; }
      var domainTypes = new Map(), pageMeta = {}, pageAnswers = {}, pageCounts = {}, officialCounts = {};
      var rawTotal = 0, officialRaw = 0, officialCited = 0, bucketCounts = {}, tableRows = 0, unique = {};
      var domainAnswers = {}, typeAnswers = {};
      answers.forEach(function (a, ai) {
        var hit = false;
        a.c.forEach(function (c) {
          rawTotal += 1;
          var domain = F.domains[c[1]];
          var bucket = BUCKET[c[2]];
          bucketCounts[bucket] = (bucketCounts[bucket] || 0) + 1;
          if (c[0] === TARGET) { officialRaw += 1; hit = true; }
          if (c[4]) tableRows += 1;
          if (domain) (domainAnswers[domain] = domainAnswers[domain] || {})[ai] = 1;
          (typeAnswers[bucket] = typeAnswers[bucket] || {})[ai] = 1;
          if (c[3] < 0) return;
          var url = F.urls[c[3]];
          unique[url] = 1;
          if (domain) {
            if (!domainTypes.has(domain)) domainTypes.set(domain, new Map());
            var m = domainTypes.get(domain);
            m.set(c[2], (m.get(c[2]) || 0) + 1);
          }
          if (!(url in pageMeta)) pageMeta[url] = c[2];
          (pageAnswers[url] = pageAnswers[url] || {})[ai] = 1;
          pageCounts[url] = (pageCounts[url] || 0) + 1;
          if (c[0] === TARGET) officialCounts[url] = (officialCounts[url] || 0) + 1;
        });
        if (hit) officialCited += 1;
      });
      function share(n) { return rawTotal ? fmtPct(n / rawTotal) : "—"; }
      var order = F.bucket_order || [];
      var types = order.slice().sort(function (a, b) {
        return ((bucketCounts[b] || 0) - (bucketCounts[a] || 0)) || (order.indexOf(a) - order.indexOf(b));
      }).map(function (name) {
        return [name, share(bucketCounts[name] || 0), String(bucketCounts[name] || 0), (F.bucket_fill || {})[name] || ""];
      });
      function domainBucket(domain) {
        var m = domainTypes.get(domain), best = null, bestN = -1;
        if (!m) return "其他";
        m.forEach(function (n, t) { if (n > bestN) { best = t; bestN = n; } });
        return BUCKET[best] || "其他";
      }
      var domainCounts = [];
      domainTypes.forEach(function (m, d) {
        var n = 0;
        m.forEach(function (v) { n += v; });
        domainCounts.push([d, n]);
      });
      domainCounts.sort(function (a, b) { return (b[1] - a[1]) || cmp(a[0], b[0]); });
      var domainRows = top(domainCounts).map(function (x) { return [x[0], share(x[1]), domainBucket(x[0])]; });
      var thirdParty = [];
      domainCounts.forEach(function (x) {
        var bucket = domainBucket(x[0]);
        if (thirdParty.length >= 5 || bucket === "自有网站" || bucket === "竞品网站") return;
        thirdParty.push([x[0], share(x[1]), bucket]);
      });
      var mentionedAt = answers.map(function (a) { return a.m.some(function (x) { return x[0] === TARGET; }); });
      function sortedCounts(map) {
        return Object.keys(map).map(function (u) { return [u, map[u]]; })
          .sort(function (a, b) { return (b[1] - a[1]) || cmp(a[0], b[0]); });
      }
      var pageRows = top(sortedCounts(pageCounts)).map(function (x) {
        var mentioned = Object.keys(pageAnswers[x[0]] || {}).some(function (ai) { return mentionedAt[ai]; });
        return [x[0], BUCKET[pageMeta[x[0]]] || "其他", mentioned ? "提及" : "未提及", share(x[1])];
      });
      var officialRows = top(sortedCounts(officialCounts)).map(function (x) { return [x[0], share(x[1])]; });
      function rate(set) { return answers.length ? fmtPct(Object.keys(set || {}).length / answers.length) : "—"; }
      var rates = { types: {}, domains: {}, pages: {} };
      types.forEach(function (r) { rates.types[r[0]] = rate(typeAnswers[r[0]]); });
      domainRows.forEach(function (r) { rates.domains[r[0]] = rate(domainAnswers[r[0]]); });
      pageRows.concat(officialRows).forEach(function (r) { rates.pages[r[0]] = rate(pageAnswers[r[0]]); });
      return {
        total_citations: rawTotal,
        official_share: rawTotal ? fmtPct(officialRaw / rawTotal) : "—",
        official_citation_rate: answers.length ? fmtPct(officialCited / answers.length) : "—",
        rates: rates, types: types, domains: domainRows, third_party_domains: thirdParty,
        pages: pageRows, official_pages: officialRows,
        citation_units: { occurrences: rawTotal, unique_sources: Object.keys(unique).length, occurrences_in_table_rows: tableRows }
      };
    }

    // ---------- 情感（Claim 信号） ----------
    function claimOk(sel, c) {
      if (!inSel(sel.regions, c.r)) return false;
      if (sel.platforms && sel.platforms.length && sel.platforms.indexOf(INTERNAL_TO_LABEL[c.p]) < 0) return false;
      return qOk(sel, c.q);
    }
    function rateText(pos, neg) { var t = pos + neg; return t ? pyFixed(pos / t * 100, 1) + "%" : "—"; }
    function sentiment(sel) {
      if (!SENT || !CLAIMS.length) return {};
      var claims = CLAIMS.filter(function (c) { return claimOk(sel, c); });
      var brands = SENT.brands || [], target = SENT.target;
      var seen = {}, perAttr = new Map(), perTheme = new Map(), perPlatform = new Map();
      function bump(map, key, extra) {
        if (!map.has(key)) map.set(key, extra);
        map.get(key).v += 1;
      }
      claims.forEach(function (c) {
        if (brands.indexOf(c.b) < 0) return;
        var key = [c.b, c.r, c.p, c.k, c.t, c.d].join("\u0001");
        if (seen[key]) return;
        seen[key] = 1;
        if (c.d !== "positive" && c.d !== "negative") return;
        var pk = c.b + "\u0001" + c.p;
        if (!perPlatform.has(pk)) perPlatform.set(pk, { b: c.b, pos: 0, neg: 0 });
        perPlatform.get(pk)[c.d === "positive" ? "pos" : "neg"] += 1;
        bump(perAttr, [c.b, c.a, c.d].join("\u0001"), { b: c.b, a: c.a, s: c.d, v: 0 });
        bump(perTheme, [c.b, c.h, c.d].join("\u0001"), { b: c.b, t: c.h, s: c.d, v: 0 });
      });
      var byBrand = {};
      brands.forEach(function (b) {
        var pos = 0, neg = 0, attrs = [];
        perAttr.forEach(function (x) {
          if (x.b !== b) return;
          if (x.s === "positive") pos += x.v; else neg += x.v;
          attrs.push({ attribute: x.a, sentiment: x.s, occurrence: x.v });
        });
        attrs.sort(function (x, y) { return (y.occurrence - x.occurrence) || cmp(x.attribute, y.attribute); });
        byBrand[b] = { signal_total: pos + neg, positive_signals: pos, negative_signals: neg, pos_rate: rateText(pos, neg), by_attribute: attrs };
      });
      var themes = [], attrTheme = {};
      claims.forEach(function (c) {
        if (c.h && themes.indexOf(c.h) < 0) themes.push(c.h);
        attrTheme[c.a] = c.h;
      });
      var matrix = {};
      themes.forEach(function (theme) {
        matrix[theme] = {};
        brands.forEach(function (b) {
          var rows = [];
          perAttr.forEach(function (x) { if (x.b === b && attrTheme[x.a] === theme) rows.push(x); });
          if (!rows.length) {
            matrix[theme][b] = { pos: 0, neg: 0, top_attribute: "", top_count: 0, top_dir: "", rate: "—" };
            return;
          }
          var top = rows[0];
          rows.forEach(function (x) { if (x.v > top.v || (x.v === top.v && x.a > top.a)) top = x; });
          var pos = 0, neg = 0;
          rows.forEach(function (x) { if (x.s === "positive") pos += x.v; else neg += x.v; });
          matrix[theme][b] = { pos: pos, neg: neg, top_attribute: top.a, top_count: top.v,
            top_dir: top.s === "positive" ? "pos" : "neg", rate: rateText(pos, neg) };
        });
      });
      var ts = byBrand[target] || { by_attribute: [] };
      function groups(direction) {
        var evidence = {};
        claims.forEach(function (c) {
          if (c.b !== target || c.d !== direction || (c.a in evidence) || !c.e) return;
          evidence[c.a] = { sentence: c.e, region: c.r, platform: c.p, question_id: String(c.q).padStart(4, "0") };
        });
        return ts.by_attribute.filter(function (x) { return x.sentiment === direction; }).map(function (x) {
          return { label: x.attribute, count: x.occurrence, evidence: evidence[x.attribute] || {} };
        });
      }
      var pos = ts.positive_signals || 0, neg = ts.negative_signals || 0;
      return {
        metric_basis: "claim_signals",
        summary: { total: pos + neg, pos: pos, neu: 0, neg: neg, pos_rate: rateText(pos, neg),
          neg_rate: pos + neg ? rateText(neg, pos) : "—" },
        claims: { pos: groups("positive"), neg: groups("negative") },
        by_brand: byBrand,
        theme_matrix: { themes: themes, brands: brands.slice(), matrix: matrix }
      };
    }

    // 明细列：目标品牌按 (地区, 平台, 回答, claim) 去重；品牌对比按品牌再去重（attach_sentiment main）
    var recordSignals = null;
    function signals() {
      if (recordSignals || !SENT) return recordSignals || [];
      var seenT = {}, seenB = {};
      recordSignals = [];
      CLAIMS.forEach(function (c) {
        if (c.d !== "positive" && c.d !== "negative") return;
        var base = [c.r, c.p, c.k, c.t].join("\u0001");
        if (c.b === SENT.target && !seenT[base]) { seenT[base] = 1; recordSignals.push({ c: c, kind: "target" }); }
        if ((SENT.brands || []).indexOf(c.b) >= 0 && !seenB[c.b + "\u0001" + base]) {
          seenB[c.b + "\u0001" + base] = 1;
          recordSignals.push({ c: c, kind: "brand" });
        }
      });
      return recordSignals;
    }

    // ---------- 问题明细（build_records） ----------
    function records(sel, answers) {
      var byQ = {};
      answers.forEach(function (a) { (byQ[a.q] = byQ[a.q] || []).push(a); });
      var sentQ = SENT ? (SENT.record_qids || []) : [];
      var sig = SENT ? signals().filter(function (x) {
        return inSel(sel.regions, x.c.r) && (!sel.platforms || !sel.platforms.length || sel.platforms.indexOf(INTERNAL_TO_LABEL[x.c.p]) >= 0);
      }) : [];
      // 题库按市场写（同一句提示词可能只在某一个市场），选地区/平台后没有回答的题
      // 不应出现在明细里，否则筛选后条数不变（2026-11-11 实测）。
      return (META.questions || []).filter(function (q) {
        var qid = Number(q.qid);
        return qOk(sel, qid) && (byQ[qid] || []).length > 0;
      }).map(function (q) {
        var qid = Number(q.qid);
        var valid = byQ[qid] || [];
        var row = { qid: qid, en: q.en, zh: q.zh, topic: q.topic, intent: q.intent, tag: q.tag === "—" ? "" : (q.tag || ""),
          mention_rate: "—", rank: "—", mention_rank: "—", position: "—", share: "—",
          citation_share: "—", citation_rate: "—", sentiment: null, mentioned: null, brands: [] };
        if (valid.length) {
          var counts = OBJ.map(function () { return 0; }), rankSum = OBJ.map(function () { return 0; }), rankN = OBJ.map(function () { return 0; });
          var own = OBJ.map(function () { return 0; }), cited = OBJ.map(function () { return 0; });
          var citeTotal = 0, totalMentions = 0, targetRanks = [];
          valid.forEach(function (a) {
            var owners = {};
            a.c.forEach(function (c) { citeTotal += 1; if (c[0] >= 0) { own[c[0]] += 1; owners[c[0]] = 1; } });
            Object.keys(owners).forEach(function (i) { cited[i] += 1; });
            a.m.forEach(function (x) {
              counts[x[0]] += 1;
              totalMentions += 1;
              if (x[1]) { rankSum[x[0]] += x[1]; rankN[x[0]] += 1; }
              if (x[0] === TARGET) targetRanks.push(x[1]);
            });
          });
          row.mention_rate = fmtPct(counts[TARGET] / valid.length);
          row.share = totalMentions ? fmtPct(counts[TARGET] / totalMentions) : "—";
          row.citation_share = citeTotal ? fmtPct(own[TARGET] / citeTotal) : "—";
          row.citation_rate = fmtPct(cited[TARGET] / valid.length);
          row.mentioned = counts[TARGET] > 0;
          if (targetRanks.length) {
            var avg = targetRanks.reduce(function (s, v) { return s + v; }, 0) / targetRanks.length;
            row.rank = fmtNum(avg);
            row.position = fmtNum(avg);
          } else {
            row.rank = String(OBJ.length);
          }
          row.brands = OBJ.map(function (o, i) {
            return { name: o.name, role: o.role, mention_count: counts[i], mention_rate: counts[i] / valid.length,
              share_of_voice: totalMentions ? counts[i] / totalMentions : null,
              average_rank: rankN[i] ? rankSum[i] / rankN[i] : null,
              citation_share: citeTotal ? own[i] / citeTotal : null, citation_rate: cited[i] / valid.length };
          });
          if (counts[TARGET]) {
            row.mention_rank = String(1 + counts.filter(function (n) { return n > counts[TARGET]; }).length);
          }
        }
        if (SENT && sentQ.indexOf(qid) >= 0) {
          var tp = 0, tn = 0, bp = {}, bn = {};
          sig.forEach(function (x) {
            if (x.c.q !== qid) return;
            var pos = x.c.d === "positive";
            if (x.kind === "target") { if (pos) tp += 1; else tn += 1; }
            else { bp[x.c.b] = (bp[x.c.b] || 0) + (pos ? 1 : 0); bn[x.c.b] = (bn[x.c.b] || 0) + 1; }
          });
          row.sentiment = tp + tn ? pyFixed(tp * 100 / (tp + tn), 1) + "%" : null;
          row.brand_sentiment = {};
          Object.keys(bn).forEach(function (b) { row.brand_sentiment[b] = pyFixed(bp[b] * 100 / bn[b], 1) + "%"; });
        }
        return row;
      });
    }

    // ---------- 商品卡（compute_shopping_metrics，按平台分开） ----------
    function shopping(answers, platforms) {
      var dirs = META.platform_dirs || {};
      var scopeTypes = F.shopping_scope || [];
      var skuNames = F.sku_names || [];
      var out = {};
      platforms.forEach(function (label) {
        var list = answers.filter(function (a) { return a.p === label && a.s; });
        if (!list.length) return;
        var scoped = list.filter(function (a) { return scopeTypes.indexOf(intentOf(a)) >= 0; });
        var shop = scoped.filter(function (a) { return a.s.t > 0; });
        var present = {}, firstPos = {}, linked = {}, skuPos = {}, skuLinked = {};
        shop.forEach(function (a) {
          var seen = {}, link = {}, seenSku = {}, linkSku = {};
          a.s.k.forEach(function (k) {
            if (k[0] < 0) return;
            if (!(k[0] in seen)) seen[k[0]] = k[1];
            if (k[2]) link[k[0]] = 1;
            if (k[0] === TARGET && k[3] >= 0) {
              if (!(k[3] in seenSku)) seenSku[k[3]] = k[1];
              if (k[2]) linkSku[k[3]] = 1;
            }
          });
          Object.keys(seen).forEach(function (i) { (present[i] = present[i] || []).push(seen[i]); });
          Object.keys(link).forEach(function (i) { linked[i] = (linked[i] || 0) + 1; });
          Object.keys(seenSku).forEach(function (i) { (skuPos[i] = skuPos[i] || []).push(seenSku[i]); });
          Object.keys(linkSku).forEach(function (i) { skuLinked[i] = (skuLinked[i] || 0) + 1; });
        });
        var brands = [];
        OBJ.forEach(function (o, i) {
          if (o.role !== "target" && o.role !== "competitor") return;
          var pos = present[i] || [];
          brands.push({ name: o.name, role: o.role,
            shopping_visibility: corePercent(pos.length, shop.length),
            average_card_position: coreAverage(pos),
            official_link_coverage: corePercent(linked[i] || 0, pos.length) });
        });
        var skus = [];
        skuNames.forEach(function (name, i) {
          if (!skuPos[i]) return;
          skus.push({ name: name, shopping_visibility: corePercent(skuPos[i].length, shop.length),
            average_card_position: coreAverage(skuPos[i]),
            official_link_coverage: corePercent(skuLinked[i] || 0, skuPos[i].length) });
        });
        out[dirs[label] || label] = {
          product_field_returned: list.some(function (a) { return a.s.f !== 0; }),
          scope_answers: scoped.length, shopping_answers: shop.length,
          shopping_mode_rate: corePercent(shop.length, scoped.length),
          brands: brands, target_skus: skus
        };
      });
      return { by_platform: out };
    }

    var cache = {};
    return {
      slice: function (sel) {
        var key = JSON.stringify([sel.regions || [], sel.platforms || [], sel.intents || [], sel.topics || []]);
        if (!cache[key]) cache[key] = slice(sel);
        return cache[key];
      },
      _fmt: { pyFixed: pyFixed }
    };
  }

  var api = { create: create };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReportEngine = api;
})(typeof window !== "undefined" ? window : this);
