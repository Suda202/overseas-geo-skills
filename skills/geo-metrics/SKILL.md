---
name: geo-metrics
description: Owns every overseas GEO statistic rule and its single implementation — brand / competitor mention recognition (alias matching, case-sensitive aliases, cross-brand overlap resolution, the brand lexicon format and open-brand mining), answer-body cleaning before recognition (citation stripping, merchant columns), answer validity, citation URL normalization, and the metric calculations and sample scopes for mention rate, share of voice, average position, citation share, official-site rate and shopping product cards. Use it when changing, checking or explaining how any of these is counted, or when another skill needs to recognise brands or compute a metric. Do not use it to assemble or render a report (geo-presales-report-builder, geo-monitoring baseline), to judge sentiment (geo-presales-sentiment-judge), to rule on crawl trustworthiness (geo-presales-crawl-integrity), or to write customer-facing conclusions (geo-presales-report-editor).
---

# GEO 统计口径与实现

品牌识别和指标计算只有这一份实现。其他 skill 需要认品牌、清正文、算指标时调用这里，不在自己目录里另写一份；发现口径不对，改这里。

## 归本 skill 的

| 能力 | 位置 |
|---|---|
| 品牌识别：别名匹配、拉丁词边界、非拉丁文字跨品牌最长优先消解、区分大小写的写法 | `scripts/geo_presales_core/util.py` 的 `find_alias_spans`、`resolve_alias_spans`、`case_sensitive_for` |
| 识别前的正文清洗：去引用标记、图片、链接网址、HTML，清空商品卡渠道列 | `scripts/de_cite_crawl.py` 的 `strip_citations`、`blank_merchant_columns` |
| 答案是否有效、商品卡抽取 | `scripts/geo_presales_core/crawler.py`、`shopping.py` |
| 引用网址规范化：跟踪参数、平台站内域名、域名后缀表 | `util.py` 的 `normalize_url`、`strip_tracking_params`、`is_platform_internal`、`COMMON_MULTI_LABEL_SUFFIXES` |
| 指标计算：提及率、声量份额、平均位置、引用份额、官网引用率、商品卡三项 | `scripts/geo_presales_core/metrics.py`、`deterministic.py`、`shopping.py` |
| 每个指标用哪批样本、对客户能叫什么名字 | [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md) |
| 开放品牌候选挖掘（人工收成词表） | `scripts/mine_brand_lexicon.py` |
| 识别对账：按报告同一套识别列出词表内品牌的漏判候选（近似拼写、空格变体）和误判候选（标准名带大写、命中全是小写），出 summary.json / candidates.csv / report.md 给人复核 | `scripts/reconcile_brand_recognition.py` |

## 品牌词表

结构 `{"brands": [{"name", "aliases", "type", "domains"}], "case_sensitive_aliases": [...]}`。

- 品牌名本身自动算一条别名。
- `case_sensitive_aliases`：品牌名或别名本身是普通词或缩写时（ERA / era、AVG / avg），把要认的大小写写法逐个列出；原文写法与名单里某个写法逐字相同才算提及。名单对词表内外所有品牌生效（目标品牌、配置竞品、开放品牌），售前报告、监测基线、试跑计数、情感抽取读的是同一份。
- 同一别名只归一个品牌：报告数据层按首次登记的品牌归属、丢弃后来的重名；core 配置入口遇到重名直接报错。

## 谁在调用

- `geo-presales-report-builder`：`build_report_data.py`、`verify_report_data.py`、`collect_answers.py`、`infer_brand_domains.py`、`collect_domain_candidates.py`、`run_pipeline.py`（词表挖掘）
- `geo-monitoring`：`build_baseline_html.py`、`trial_brand_count.py`、`changeability_domains.py`
- `geo-presales-sentiment-judge`：`sentiment_sentences.py extract` 的单元清洗与品牌匹配
- `geo-presales-crawl-integrity`：`answer_validity`、`extract_product_cards`
- `geo-presales-report-editor`：`geo_presales_editor/`（影子审计 CLI）
- `geo-prompt-selection-builder`：`run_selection_mode.py` 线上运行时拷贝 `geo_presales_core`

调用方用 `sys.path` 指向 `geo-metrics/scripts`（脱离整套 skill 部署时用环境变量 `GEO_PRESALES_SKILLS_ROOT` 指 skills 根目录），包名仍是 `geo_presales_core`。

## 改动后的回归

- 单元测试：`geo-presales-report-editor/scripts/tests/test_geo_presales.py`（core）、`geo-presales-report-audit/tests/test_scripts.py`（去引用）、`geo-presales-report-builder/tests`、`geo-presales-sentiment-judge/tests`。
- 端到端：用 Bbrand H1、Hbrand、360 三份现有数据跑售前报告数据层、校验、情感抽取、基线报告、试跑计数，输出与改前逐项比对。脚本见项目根 `.snapshots/geo-metrics-20261110/run_ref.sh` 与 `compare.py`，读数有变化必须逐条说明原因。

## 还没收进来的

`build_report_data.py` 里仍有一份按切片组装的指标计算、报告页 `report-engine.js` 在多选筛选时重算，监测基线对 `build_report_data` 有运行时补丁。这些属于第二期，清单在项目根 `docs/exec-plans/active/geo-metrics-skill-progress.md`。
