---
name: geo-gap-diagnosis
description: Use after a formal GEO monitoring baseline (after-sales, 5–7 runs per Prompt × platform) to diagnose why the brand or a target SKU underperforms and decide what to optimise — reads the collection directory into seven layers (reach, search, retrieval, citation, mention, recommendation, accuracy), labels recommendation status per answer (D-TOP / D-REC / R-LIST / Q-FIT / X-WARN / Z-GAP) and brand fact errors, checks cited third-party pages for page gaps vs answer gaps, then applies business-value / product-fit / stability gates and a first-breakpoint table to produce an optimisation-opportunity table with a decision (test / observe / research first / hold / not now / route to product), one carrier, the four action fields and a measurement contract. Use when asked 「为什么提及率低」「该优化什么」「优化机会诊断」「缺口诊断」「品牌在、型号不在」「SKU 推荐率低」, or to turn baseline readings into work for the content team. Do not use to collect answers or check crawl integrity (geo-monitoring), to change metric calibers or brand recognition (geo-metrics), to pick or write Prompts (geo-prompt-selection-builder), for the presales diagnosis report (geo-presales-report-builder / -editor), or to write the content itself.
metadata:
  author: Overseas GEO Project
  version: "1.1.0"
---

# GEO 缺口诊断

拿一份已过完整性检查的正式基线，产出「优化机会诊断表」。不采集、不改口径、不写内容。

规则只有一份：[diagnosis-rules.md](references/diagnosis-rules.md)（七层读数、三道门、第一断点、决定、度量契约）。断点对应的原因和动作写法在 [gap-cause-action-table.md](references/gap-cause-action-table.md)，推荐与事实标注判据在 [recommendation-labels.md](references/recommendation-labels.md)，规则背后的研究和降级掉的说法在 [evidence-base.md](references/evidence-base.md)，产物字段在 [output-contract.md](references/output-contract.md)。

## 什么时候能用

- 售后正式基线：每题每平台 ≥5 次（标准 7 次），已过 `geo-monitoring/scripts/audit_crawl_integrity.py`。售前和 3 次试跑不用：样本太少，断点判不稳。
- 品牌词表要标 `same_category`：领先竞品只在同类品牌里找。开放品牌没写的按非同类处理，诊断前补齐（可另存一份诊断用副本，不改原词表）。

## 流程

1. **读数**：`scripts/layer_readings.py --bank <bank.json 或 questions.csv> --collect <基线目录…> --lexicon <词表> --out readings`。有 SKU 时加 `--sku-map`（型号正则、SKU 页网址正则）和 `--sku-fit`（每个 SKU 真实适配哪些题，品牌方确认）。题库没写业务优先级时用 `--priority` 补。读数和 `build_baseline_html.py`、选词试跑表同口径：同一套归题、去重、去引用、品牌识别。
2. **标注**：`scripts/label_batches.py prepare` 出批次 → 按 recommendation-labels.md 逐条标（可派便宜模型，每批交回 JSONL）→ `merge` 校验引文、合并 → `sample` 抽 50 条人工判，`--score` 算一致率；首次跑某客户必须抽检，< 85% 改判据重标。标注要用品牌事实表（`facts.md`，每条事实带编号和出处）。
3. **页面缺口**：`scripts/page_gap.py --readings readings --out pagegap` 抓每题被引 ≥2 次的第三方页面，判页面缺口 / 答案缺口；抓不到的记未知，不猜。
4. **诊断**：`scripts/diagnose.py --readings readings --labels labels/labels.json --pagegap pagegap --out diagnosis`，可加 `--constraints`（相对竞品）、`--site-audit`（官网诊断报告的爬虫可达性）。产出 diagnosis.csv / .json / .md。
5. **分析师复核**：diagnosis.md 是初稿。每条「测试」按 gap-cause-action-table.md 的三项核对（回答原文、被引来源、官网与产品事实）确认原因，挑定最接近的现有页面，写成交内容团队的版本；「先补研究」写清缺哪项证据、谁去补。

## 读数上的硬限制

- **ChatGPT 是强制联网口径**：采集用 `web_search=true`，联网层不可观察（Graphite 实测强制搜索让从不自然联网的题可见度平均偏 20 个点）。复测必须同一口径。
- 检索层只有 ChatGPT、AI 模式、AI 概览、Copilot、Grok 能看；Gemini、Perplexity 上判不了断点 3、4。
- 每格 7 次时单题单平台区间很宽，门 3 只抓得住大差距；SKU 跨适配题合并判，事实错误跨题按事实编号合并判。
- 推荐标注和事实错误是模型判断，抽检一致率写进诊断说明；事实错误每一条都要人工核过再交出（零售价、促销价常被误判成写错）。

## 产物放哪

该客户的售后工作目录下 `诊断-<日期>/`：readings、labels、pagegap、diagnosis 四个子目录，加 facts.md、诊断用词表副本、priority / sku 输入文件，以及和人工结论的差异清单。

## 自检

改脚本或规则后跑 `python3 evals/e2e_gap_diagnosis.py`，36 条用例覆盖四个脚本的完整链路（读数、门与断点、标注校验、页面缺口、三份产物），不联网、不花钱；报告写到 `reports/gap-diagnosis-e2e.md`。
