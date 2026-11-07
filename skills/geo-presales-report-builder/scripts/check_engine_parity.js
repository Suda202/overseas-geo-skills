#!/usr/bin/env node
/* 前端计算引擎对账：单选组合下 assets/report-engine.js 现算的数，必须与 build_report_data.py /
 * attach_sentiment.py 预算的切片逐项一致（2026-11-07 数据筛选改多选时加）。
 *
 * 用法：node check_engine_parity.js <report-data.json>   （attach_sentiment 之后跑）
 * 退出码：0 = 全部一致；1 = 有不一致（逐条列出切片、字段、两边的值）。
 */
"use strict";
var fs = require("fs");
var path = require("path");
var Engine = require(path.join(__dirname, "..", "assets", "report-engine.js"));

var file = process.argv[2];
if (!file) { console.error("用法：node check_engine_parity.js <report-data.json>"); process.exit(2); }
var DATA = JSON.parse(fs.readFileSync(file, "utf8"));
if (!DATA.facts) { console.error("report-data.json 里没有 facts（build_report_data.py 版本过旧）"); process.exit(2); }
var engine = Engine.create(DATA);
var META = DATA.meta || {};
var prefix = META.type_topic_prefix || "类型:";
var problems = [], checked = 0;

// 对象按键名排序后比（Python dict 与 JS 对象的键顺序不影响读数）
function canon(v) {
  if (Array.isArray(v)) return v.map(canon);
  if (v && typeof v === "object") { var o = {}; Object.keys(v).sort().forEach(function (k) { o[k] = canon(v[k]); }); return o; }
  return v;
}
function same(a, b) { return JSON.stringify(canon(a)) === JSON.stringify(canon(b)); }
function report(key, field, mine, theirs) {
  problems.push(key + "  " + field + "\n    引擎 " + String(JSON.stringify(mine)).slice(0, 300) + "\n    切片 " + String(JSON.stringify(theirs)).slice(0, 300));
}
function eq(key, field, mine, theirs) { if (!same(mine, theirs)) report(key, field, mine, theirs); }
function rateFields(x) {
  return x ? { numerator: x.numerator, denominator: x.denominator, display: x.display } : x;
}

Object.keys(DATA.slices).forEach(function (key) {
  var parts = key.split("|"), region = parts[0], platform = parts[1], topic = parts[2];
  var sel = {
    regions: region ? [region] : [], platforms: platform ? [platform] : [],
    intents: topic.indexOf(prefix) === 0 ? [topic.slice(prefix.length)] : [],
    topics: topic && topic.indexOf(prefix) !== 0 ? [topic] : []
  };
  var py = DATA.slices[key], js = engine.slice(sel);
  checked += 1;
  ["mention_rate", "mention_rank", "share_of_voice", "average_rank", "official_share", "official_citation_rate"].forEach(function (f) {
    eq(key, "kpis." + f, js.kpis[f], py.kpis[f]);
  });
  eq(key, "competition", js.competition, py.competition);
  eq(key, "_counts.visibility_answers", js._counts.visibility_answers, (py._counts || {}).visibility_answers);
  // 矩阵：引擎只出选中平台的列，按平台名逐列对
  ["mention", "share", "rank", "official"].forEach(function (m) {
    (js.matrix[m] || []).forEach(function (row, ri) {
      var pyRow = (py.matrix[m] || [])[ri] || {};
      eq(key, "matrix." + m + "[" + ri + "].name", row.name, pyRow.name);
      js.matrix.platforms.forEach(function (p, ci) {
        var pi = (py.matrix.platforms || []).indexOf(p);
        eq(key, "matrix." + m + "[" + row.name + "][" + p + "]", row.vals[ci], (pyRow.vals || [])[pi]);
      });
    });
  });
  var s = py.sources || {};
  ["total_citations", "official_share", "official_citation_rate", "rates", "types", "domains",
    "third_party_domains", "pages", "official_pages", "citation_units"].forEach(function (f) {
    eq(key, "sources." + f, js.sources[f], s[f]);
  });
  if (DATA.facts.claims && py.sentiment && py.sentiment.summary) {
    var ps = py.sentiment, ms = js.sentiment;
    ["pos_rate", "neg_rate", "pos", "neg"].forEach(function (f) { eq(key, "sentiment.summary." + f, ms.summary[f], ps.summary[f]); });
    eq(key, "sentiment.claims", ms.claims, ps.claims);
    Object.keys(ps.by_brand || {}).forEach(function (b) { eq(key, "sentiment.by_brand." + b, ms.by_brand[b].pos_rate, ps.by_brand[b].pos_rate); });
    var pt = ps.theme_matrix || {}, mt = ms.theme_matrix || {};
    // 切片里一条 Claim 都没有时 Python 不出 theme_matrix，引擎出空表，两者等价
    eq(key, "sentiment.theme_matrix.themes", mt.themes || [], pt.themes || []);
    (pt.themes || []).forEach(function (t) {
      Object.keys((pt.matrix || {})[t] || {}).forEach(function (b) {
        var a = pt.matrix[t][b], c = ((mt.matrix || {})[t] || {})[b] || {};
        eq(key, "sentiment.theme_matrix." + t + "." + b, [c.pos, c.neg, c.top_attribute, c.top_dir], [a.pos, a.neg, a.top_attribute, a.top_dir]);
      });
    });
  }
  var shop = ((py.shopping || {}).by_platform) || {};
  Object.keys(shop).forEach(function (dir) {
    var a = shop[dir], b = (js.shopping.by_platform || {})[dir];
    if (!b) { report(key, "shopping." + dir, null, "有"); return; }
    ["product_field_returned", "scope_answers", "shopping_answers"].forEach(function (f) { eq(key, "shopping." + dir + "." + f, b[f], a[f]); });
    eq(key, "shopping." + dir + ".shopping_mode_rate", rateFields(b.shopping_mode_rate), rateFields(a.shopping_mode_rate));
    (a.brands || []).filter(function (x) { return x.role === "target" || x.role === "competitor"; }).forEach(function (x) {
      var y = (b.brands || []).filter(function (z) { return z.name === x.name; })[0] || {};
      ["shopping_visibility", "average_card_position", "official_link_coverage"].forEach(function (f) {
        eq(key, "shopping." + dir + "." + x.name + "." + f, rateFields(y[f]), rateFields(x[f]));
      });
    });
    eq(key, "shopping." + dir + ".target_skus", (b.target_skus || []).map(function (x) {
      return [x.name, rateFields(x.shopping_visibility), rateFields(x.average_card_position), rateFields(x.official_link_coverage)];
    }), (a.target_skus || []).map(function (x) {
      return [x.name, rateFields(x.shopping_visibility), rateFields(x.average_card_position), rateFields(x.official_link_coverage)];
    }));
  });
  var pr = py.records || [], jr = js.records || [];
  eq(key, "records.qids", jr.map(function (r) { return r.qid; }), pr.map(function (r) { return r.qid; }));
  pr.forEach(function (r, i) {
    var m = jr[i] || {};
    ["mention_rate", "rank", "mention_rank", "position", "share", "citation_share", "citation_rate", "sentiment", "mentioned", "intent", "topic"].forEach(function (f) {
      eq(key, "records[" + r.qid + "]." + f, m[f], r[f]);
    });
    if (r.brand_sentiment) eq(key, "records[" + r.qid + "].brand_sentiment", m.brand_sentiment, r.brand_sentiment);
    (r.brands || []).forEach(function (b) {
      var x = (m.brands || []).filter(function (z) { return z.name === b.name; })[0] || {};
      ["mention_count", "mention_rate", "share_of_voice", "average_rank", "citation_share", "citation_rate"].forEach(function (f) {
        var u = x[f], v = b[f];
        var ok = (u === v) || (typeof u === "number" && typeof v === "number" && Math.abs(u - v) < 1e-12);
        if (!ok) report(key, "records[" + r.qid + "].brands." + b.name + "." + f, u, v);
      });
    });
  });
});

if (problems.length) {
  console.log("对账不一致 " + problems.length + " 处（" + checked + " 个切片）：");
  problems.slice(0, 60).forEach(function (p) { console.log(p); });
  process.exit(1);
}
console.log("引擎对账通过：" + checked + " 个切片，单选组合下与预算切片逐项一致");
