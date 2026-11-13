---
name: geo-metrics
description: Owns every overseas GEO statistic rule and its single implementation — brand / competitor mention recognition (alias matching, case-sensitive aliases, cross-brand overlap resolution, the brand lexicon format and open-brand mining), answer-body cleaning before recognition (citation stripping, merchant columns), answer validity, citation URL normalization, the metric calculations and sample scopes for mention rate, share of voice, average position, citation share, official-site rate and shopping product cards, and brand sentiment (extracting atomic Claims from answers, clustering them into Attributes and neutral Themes, computing positive-sentiment share per brand and platform). Use it when changing, checking or explaining how any of these is counted, when another skill needs to recognise brands or compute a metric, or when judging brand sentiment for a presales report or monitoring baseline. Do not use it to assemble or render a report (geo-presales-report-builder, geo-monitoring baseline), to collect answers or rule on crawl trustworthiness (geo-monitoring), or to write customer-facing conclusions (geo-presales-report-editor).
---

# GEO 统计口径与实现

品牌识别和指标计算只有这一份实现。其他 skill 需要认品牌、清正文、算指标时调用这里，不在自己目录里另写一份；发现口径不对，改这里。

## 归本 skill 的

| 能力 | 位置 |
|---|---|
| 品牌识别：别名匹配、拉丁词边界、非拉丁文字跨品牌最长优先消解、区分大小写的写法 | `scripts/geo_presales_core/util.py` 的 `find_alias_spans`、`resolve_alias_spans`、`case_sensitive_for` |
| 识别前的正文清洗：去引用标记、图片、链接网址、HTML，删 AI 反问用户的追问块，清空商品卡渠道列 | `scripts/de_cite_crawl.py` 的 `strip_citations`（传 `follow_up_form`）、`strip_follow_up_form`、`strip_choice_lists`、`blank_merchant_columns` |
| 答案是否有效、商品卡抽取 | `scripts/geo_presales_core/crawler.py`、`shopping.py` |
| 引用网址规范化：跟踪参数、平台站内域名、域名后缀表 | `util.py` 的 `normalize_url`、`strip_tracking_params`、`is_platform_internal`、`COMMON_MULTI_LABEL_SUFFIXES` |
| 指标计算：提及率、声量份额、平均位置、引用份额、官网引用率、商品卡三项 | `scripts/geo_presales_core/metrics.py`、`deterministic.py`、`shopping.py` |
| 每个指标用哪批样本、对客户能叫什么名字 | [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md) |
| 开放品牌候选挖掘（人工收成词表） | `scripts/mine_brand_lexicon.py` |
| 识别对账：按报告同一套识别列出词表内品牌的漏判候选（近似拼写、空格变体）和误判候选（标准名带大写、命中全是小写），出 summary.json / candidates.csv / report.md 给人复核 | `scripts/reconcile_brand_recognition.py` |
| 品牌情感：抽句子、拆原子 Claim、两趟聚类（Claim → Attribute → Theme）、回装、算正向情感占比（按品牌、平台、属性、主题） | 正向占比计算只在 `scripts/geo_presales_core/sentiment.py`（Claim 信号去重、正向 ÷（正向 + 负向）、跨平台等权），`sentiment_sentences.py claims-metrics` 和报告接入 `attach_sentiment.py` 都调它；流程脚本 `scripts/sentiment_sentences.py`；做法见 [sentiment.md](references/sentiment.md)，结构和统计口径见 [claim-layer-contract.md](references/claim-layer-contract.md)，正负怎么判见 [judgment-rules.md](references/judgment-rules.md) |

情感里拆 Claim 和两趟聚类是语义判断，由模型按 [sentiment.md](references/sentiment.md) 做，拿不准的交人裁决；抽句子、回装和统计由脚本做。组装和渲染报告归 `geo-presales-report-builder`（本地出售前 HTML 报告从 `geo-presales-pipeline` 进）和 `geo-monitoring` 的基线报告。

## 品牌词表

结构 `{"brands": [{"name", "aliases", "type", "domains"}], "case_sensitive_aliases": [...]}`。

- 品牌名本身自动算一条别名。
- `case_sensitive_aliases`：品牌名或别名本身是普通词或缩写时（ERA / era、AVG / avg），把要认的大小写写法逐个列出；原文写法与名单里某个写法逐字相同才算提及。名单对词表内外所有品牌生效（目标品牌、配置竞品、开放品牌），售前报告、监测基线、试跑计数、情感抽取读的是同一份。
- 同一别名只归一个品牌：报告数据层按首次登记的品牌归属、丢弃后来的重名；core 配置入口遇到重名直接报错。
- **别名收什么**（每个客户、每个品牌各自补，目标品牌由品牌方填，竞品由我们或 AI 查官网补、人工确认，不做跨客户共享）：
  - 收：品牌名本身认不出的写法，即全称、简称或缩写、旧名、本地语言名；不含品牌名、且 AI 常单独提起的自有产品名和子品牌名（LG 的 PuriCare：AI 只写 PuriCare 时才需要它，总写成 LG PuriCare 就靠品牌名认出），命中计入母品牌，口径见 [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md)「品牌提及率」。
  - 不收：带品牌名的产品名（Bbrand H1，品牌名已能认出）；只差大小写、空格、连字符的写法；型号清单；通用品类词（Calipers、CMM，会把整个品类算给一个品牌）。
  - 易混淆、不能算作本品牌的名称（同集团其他品牌、同名公司、被收购后单独经营的品牌）不进别名，由品牌方逐案确认。
  - 出报告前跑 `scripts/reconcile_brand_recognition.py` 查拼写漏判和常用词误判。词表里没有的、不含品牌名的产品名它查不到，要看 `mine_brand_lexicon.py` 列出的未知大写词。

## 识别规则（core `find_alias_spans`，只作用于拉丁字母别名）

- 分隔符放宽：5 个字母以上的别名，字符之间可以夹 1 个空格、连字符、点或下划线（「Blue Wave」= BlueWave）。原文被这样拆开时，每一段都要大写开头，免得普通短语混进来（「blue wave patterns」不算 BlueWave，「Blue Wave」算）。
- 常用词要大写：别名是英文常用词时，原文必须带大写才算（「apple juice」不算 Apple）。词表在 `geo_presales_core/english_words.txt`，取自 Webster's 2nd 的小写词条。
- 去拼接噪声：识别前去掉「Go to product viewer dialog for this item.」。
- 不做去后缀派生简称（2026-11-10 试过后撤回）：去掉后缀得到的简称常常是另一个实体。实测三类误判：安全软件词表里「某系统名 + Security」派生出操作系统名，正文里每次提到这个系统都被算成品牌提及，提及率翻倍；带数字的品牌名派生出纯数字，误中别家产品名里的同一个数字；「某词 + Water」派生出的单词误中别家型号。这类别名改由 `reconcile_brand_recognition.py` 列成候选，人工或 AI 确认后写进词表。

## 谁在调用

- `geo-presales-report-builder`：`build_report_data.py`、`verify_report_data.py`、`infer_brand_domains.py`、`collect_domain_candidates.py`、`run_pipeline.py`（词表挖掘、情感阶段）、`attach_sentiment.py`（正向占比调 `geo_presales_core/sentiment.py`）
- `geo-monitoring`：`build_baseline_html.py`、`trial_brand_count.py`、`changeability_domains.py`；基线报告的情感走 `sentiment_sentences.py`
- `geo-monitoring`（采集 `collect_answers.py`、采集完整性检查 `audit_crawl_integrity.py`）：`answer_validity`、`extract_product_cards`
- `geo-presales-report-editor`：`geo_presales_editor/`（影子审计 CLI）
- `geo-prompt-selection-builder`：`run_selection_mode.py` 线上运行时拷贝 `geo_presales_core`

调用方用 `sys.path` 指向 `geo-metrics/scripts`（脱离整套 skill 部署时用环境变量 `GEO_PRESALES_SKILLS_ROOT` 指 skills 根目录），包名仍是 `geo_presales_core`。

## 改动后的回归

- 单元测试：`geo-presales-report-editor/scripts/tests/test_geo_presales.py`（core）、`geo-presales-report-audit/tests/test_scripts.py`（去引用）、`geo-presales-report-builder/tests`、`geo-metrics/tests`（情感）。
- 端到端：用三份现有客户数据（一份售前报告、两份监测基线）跑售前报告数据层、校验、情感抽取、基线报告、试跑计数，输出与改前逐项比对。脚本见项目根 `.snapshots/geo-metrics-20261110/run_ref.sh` 与 `compare.py`，读数有变化必须逐条说明原因。

## 还没收进来的

第二期（2026-11-10）已收进：逐品牌引用份额、逐题读数（`metrics.question_object_stats`）、引用抽取与计次（`citations.py`）、平台正文字段表（`crawler.ANSWER_FIELD`）、品牌词表读取（`lexicon.py`）、竞品站点名单（词表顶层 `competitor_site_domains`）；监测基线已不打统计补丁。

刻意保留的第二份实现：`verify_report_data.py`（独立复算，用来抓数据层的错）和报告页 `report-engine.js`（浏览器里多选现算，靠 `check_engine_parity.js` 对账）。改口径时这两处要一起改。清单在项目根 `docs/exec-plans/active/geo-metrics-skill-progress.md`。
