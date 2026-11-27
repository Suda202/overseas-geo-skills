---
name: geo-metrics
description: Owns every overseas GEO statistic rule and its single implementation — brand / competitor mention recognition (alias matching, case-sensitive aliases, cross-brand overlap resolution, the brand lexicon format and open-brand mining), answer-body cleaning before recognition (citation stripping, merchant columns), answer validity, citation URL normalization, the metric calculations and sample scopes for mention rate, share of voice, average position, citation share, official-site rate and shopping product cards, and brand sentiment (extracting atomic Claims from answers, clustering them into Attributes and neutral Themes, computing positive-sentiment share per brand and platform). Use it when changing, checking or explaining how any of these is counted, when another skill needs to recognise brands or compute a metric, or when judging brand sentiment for a presales report or monitoring baseline. Do not use it to assemble or render a report (geo-presales-report-builder, geo-monitoring baseline), to collect answers or rule on crawl trustworthiness (geo-monitoring), or to write customer-facing conclusions.
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
| 词表自检：同一域名挂两个品牌、域名标签是别家品牌名、域名写法不规范、疑似同一品牌拆成两条 | `scripts/audit_lexicon_domains.py`；报告生成前对 Case 产出的词表跑一遍；拆分检查 `split_suspects` 也随 `mine_brand_lexicon.py --check` 跑 |
| 引用来源分类与未判读门禁：自有 > 竞品 > 内置表与共享缓存 > 未判读；未判读引用超过 5% 停下补判 | `scripts/geo_presales_core/sources.py` 的 `classify_source`、`unjudged_coverage`、`enforce_judged`；规则见 [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md)「引用来源分类」；政府/百科判断 `is_government`、`is_wiki`，注册域名 `util.registrable_domain`（含国家二级后缀与多租户平台），监测与诊断都调这几个，不另写。改动后跑 `tests/test_source_classification.py` |
| 引用域名补判流程与数据：开放品牌官网推断、待判域名收集、补证据、判读自检、品牌站索引与品类归一 | `scripts/infer_brand_domains.py`、`collect_domain_candidates.py`、`enrich_domain_candidates.py`、`check_domain_judgments.py`、`build_brand_site_index.py`；数据在 `assets/`（`domain-categories.json` 共享缓存、`domain-categories-meta.json` 判读依据、`domain-brand-sites.json`、`category-taxonomy.json`）；流程见 [domain-judging-workflow.md](references/domain-judging-workflow.md)。2026-11-18 从 geo-presales-report-builder 迁来，旧路径留软链 |
| 品类级开放品牌词表 | `assets/brand_lexicon.<品类>.json`（2026-11-18 从 geo-presales-report-builder 迁来） |
| 试跑品牌计数：发现题、替代题每个平台答案点了几个品牌 | `scripts/trial_brand_count.py`（2026-11-18 从 geo-monitoring 迁来） |
| 题库与试跑目录的公共读法：读题库、找试跑目录、按 manifest 归题、同类品牌与官网匹配 | `scripts/geo_presales_core/runs.py`；品牌计数、可改变性、缺口诊断都用这一份 |
| 临时引用统计：采集目录 → 来源类别、域名榜、品牌官网、按主题和逐题的官网引用份额与引用率，带同一道门禁 | `scripts/citation_sources.py`；试跑读数、单次分析用它，不要自己另写统计脚本 |
| 指标计算：提及率、声量份额、平均位置、引用份额、官网引用率、商品卡三项 | `scripts/geo_presales_core/metrics.py`、`deterministic.py`、`shopping.py` |
| 每个指标用哪批样本、对客户能叫什么名字 | [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md) |
| 开放品牌候选挖掘与词表查漏（人工收成词表） | `scripts/mine_brand_lexicon.py`；`--check` 有 A 档候选没收时退出码 1 |
| 识别对账：按报告同一套识别列出词表内品牌的漏判候选（近似拼写、空格变体）和误判候选（标准名带大写、命中全是小写），出 summary.json / candidates.csv / report.md 给人复核 | `scripts/reconcile_brand_recognition.py` |
| 品牌情感：抽句子、拆原子 Claim、两趟聚类（Claim → Attribute → Theme）、回装、算正向情感占比（按品牌、平台、属性、主题） | 正向占比计算只在 `scripts/geo_presales_core/sentiment.py`（Claim 信号去重、正向 ÷（正向 + 负向）、跨平台等权），`sentiment_sentences.py claims-metrics` 和报告接入 `attach_sentiment.py` 都调它；流程脚本 `scripts/sentiment_sentences.py`；做法见 [sentiment.md](references/sentiment.md)，结构和统计口径见 [claim-layer-contract.md](references/claim-layer-contract.md)，正负怎么判见 [judgment-rules.md](references/judgment-rules.md) |

情感里拆 Claim 和两趟聚类是语义判断，由模型按 [sentiment.md](references/sentiment.md) 做，拿不准的交人裁决；抽句子、回装和统计由脚本做。组装和渲染报告归 `geo-presales-report-builder`（本地出售前 HTML 报告从 `geo-presales-pipeline` 进）和 `geo-monitoring` 的基线报告。

## 品牌词表

结构 `{"brands": [{"name", "aliases", "type", "domains"}], "case_sensitive_aliases": [...]}`。

- 品牌名本身自动算一条别名。
- 目标品牌的 `domains` 只用品牌方在提报表、品牌资料或 Case 里给的域名，不按页面标题、注册信息等线索自行扩充。答案里出现疑似品牌站（子域名、旧站、地区站、页面标题带品牌名的站）时，先列出来交品牌方确认，确认前按普通域名判类（2026-11-24 DataOceanAI：infinityai.ai 被误加进品牌官网，15 次引用被算成品牌官网引用）。
- `same_category`（可选）：是否和本品卖同一类东西。目标品牌和配置竞品默认是；开放品牌没写时，**引用来源分类按同类算**（官网计入「竞品网站」，2026-11-27 起），别的品类厂商写 `false`（车载屏客户的便携导航仪品牌）。**每个开放品牌都要判，不能只判有引用链接的**：这个标记决定官网算不算「竞品网站」，也决定难度、可改变性、缺口诊断里谁算同类竞品；诊断这几个消费者按显式标注取同类（没写按非同类，保守处理）。判法是看买家能不能在这家买到本品类的东西，卖工具或平台的、卖下游产品的、招聘兼职站都判 `false`（2026-11-24 DataOceanAI：CVAT、Databricks、Mobileye、AITraining.jobs）。`geo-monitoring` 的可改变性用它判品类错位、认竞品官网。
- `case_sensitive_aliases`：品牌名或别名本身是普通词或缩写时（ERA / era、AVG / avg），把要认的大小写写法逐个列出；原文写法与名单里某个写法逐字相同才算提及。名单对词表内外所有品牌生效（目标品牌、配置竞品、开放品牌），售前报告、监测基线、试跑计数、情感抽取读的是同一份。
- 同一别名只归一个品牌：报告数据层按首次登记的品牌归属、丢弃后来的重名；core 配置入口遇到重名直接报错。
- **别名收什么**（每个客户、每个品牌各自补，目标品牌由品牌方填，竞品由我们或 AI 查官网补、人工确认，不做跨客户共享）：
  - 收：品牌名本身认不出的写法，即全称、简称或缩写、旧名、本地语言名；不含品牌名、且 AI 常单独提起的自有产品名和子品牌名（LG 的 PuriCare：AI 只写 PuriCare 时才需要它，总写成 LG PuriCare 就靠品牌名认出），命中计入母品牌，口径见 [metric-scope-and-copy-contract.md](references/metric-scope-and-copy-contract.md)「品牌提及率」。
  - 不收：带品牌名的产品名（Botslab G980H，品牌名已能认出）；只差大小写、空格、连字符的写法；型号清单；通用品类词（Calipers、CMM，会把整个品类算给一个品牌）。
  - 易混淆、不能算作本品牌的名称（同集团其他品牌、同名公司、被收购后单独经营的品牌）不进别名，由品牌方逐案确认。
  - 出报告前跑 `scripts/reconcile_brand_recognition.py` 查拼写漏判和常用词误判。词表里没有的、不含品牌名的产品名它查不到，要看 `mine_brand_lexicon.py` 列出的未知大写词。
- **开放品牌不漏收**（2026-11-20）：每次用词表算指标前（售前报告、试跑计数、基线、可改变性、缺口诊断），对这批采集跑 `mine_brand_lexicon.py --collect-dir <一个或多个采集目录> --lexicon <词表> --check`。A 档是词表没收、但在答案推荐位（加粗列表项、编号项、标题、表格第一列的开头）或商品卡上出现过的名字，出现一次也列，必须逐个过：同类厂商收进 `brands` 并写 `same_category`，别的品类品牌也收（写 `same_category: false`），自有 App 或子品牌名（Futubull 之于富途）收成母品牌别名，不是品牌的写进 `stopwords`。退出码 1 表示还有出现在 ≥2 条回答里的 A 档没过。只按出现次数看前几十个会漏长尾厂商：路拓 7 次 231 条回答漏了 12 家同类厂商（平均每答品牌数 2.81→3.03），老虎香港试跑漏了 Futubull（56 条回答）、BiyaPay、华泰等。中文（繁简）品牌按机构后缀（證券、銀行、金融、集團等）从推荐位和加粗片段里挖，繁简写法不同算没收，要把答案里的写法补成别名（老虎香港繁中漏了耀才、華盛、華泰，以及「恆生銀行」「匯豐」「盛寶」这类异写）。泰文、日文、韩文品牌仍挖不出来，要另外人工看。
- **引用域名里补同品类厂商站**（2026-11-27）：正文挖到的品牌只覆盖「回答里被点名的」，厂商官网经常只出现在引用里。冻结词表或补词表时，取最近一份报告数据的 `slices["||"].sources.domains`（按引用次数降序、带类别）和 `<输出名>.domain-candidates.json` 里判成「其他」或未判读的企业站，逐个打开页面判断是不是同品类厂商官网：是就把域名补进对应品牌条目的 `official_domains`（同品类 `same_category: true`，别的品类写 `false`），品牌不在词表就新建开放品牌条目。`assets/domain-brand-sites.json` 的 `known_brand` / `known_categories` 能直接看出这个站是谁家的、做什么品类：**`known_categories` 与本品类一致（经 `category-taxonomy.json` 归一后同一个键）的条目可以直接参考**，把域名补进本客户词表对应品牌；**不同品类的备注只说明「这是一个企业站」，不能拿来判竞品关系**——别的品类里的同行换到本品类是无关厂商。共享缓存只接受六类、不能存 competitor，所以同一个域名换了客户，也要在该客户自己的词表里重新补。验收：`audit_lexicon_domains.py` 通过；重跑 `build_report_data.py` 后这些域名从「其他」进「竞品网站」、「其他」占比下降；`verify_report_data.py` 通过。某 VR 客户补了 VR Star Space、LEKE VR、VART、MoviePower 四家厂商站后竞品网站到 53.9%，补之前这些站全落「其他」。
- **同一品牌不拆成两条**（2026-11-20）：`--check` 同时查词表里疑似同一品牌的两条——别名重复、一条的别名整词出现在另一条里（Webull ⊂ Webull Hong Kong、Futu ⊂ Futu Securities）、中文别名互相包含（致富 ⊂ 致富證券）、官网域名主标签相同（webull.com / webull.hk）。拆开会把一家的提及分给两条，两条都偏低：老虎港英 Webull 因此从 65.3% 少算成 52.3%。是同一家就合并成一条（各市场站、子公司、App 名都做别名，域名并到一起）；确是两家（中銀香港与中銀國際）写进词表顶层 `distinct_brands: [["A", "B"]]`。

## 识别规则（core `find_alias_spans`，只作用于拉丁字母别名）

- 分隔符放宽：5 个字母以上的别名，字符之间可以夹 1 个空格、连字符、点或下划线（「Blue Wave」= BlueWave）。原文被这样拆开时，每一段都要大写开头，免得普通短语混进来（「blue wave patterns」不算 BlueWave，「Blue Wave」算）。
- 常用词要大写：别名是英文常用词时，原文必须带大写才算（「apple juice」不算 Apple）。词表在 `geo_presales_core/english_words.txt`，取自 Webster's 2nd 的小写词条。
- 去拼接噪声：识别前去掉「Go to product viewer dialog for this item.」。
- 不做去后缀派生简称（2026-11-10 试过后撤回）：去掉后缀得到的简称常常是另一个实体。实测三类误判：安全软件词表里「某系统名 + Security」派生出操作系统名，正文里每次提到这个系统都被算成品牌提及，提及率翻倍；带数字的品牌名派生出纯数字，误中别家产品名里的同一个数字；「某词 + Water」派生出的单词误中别家型号。这类别名改由 `reconcile_brand_recognition.py` 列成候选，人工或 AI 确认后写进词表。

## 谁在调用

- `geo-presales-report-builder`：`build_report_data.py`（默认读本 skill 的 `assets/domain-categories.json`）、`verify_report_data.py`、`run_pipeline.py`（词表挖掘、域名门禁、情感阶段）、`attach_sentiment.py`（正向占比调 `geo_presales_core/sentiment.py`）；引用域名补判走本 skill 的脚本
- `geo-presales-report-builder` 的 `prepare_baseline.py`（售后基线报告的输入准备，核对共享域名缓存 `sources._known_type`）
- `geo-monitoring`：`changeability_domains.py`（题库与试跑目录读法来自 `runs.py`，引用抽取来自 `citations.py`，不再经由售前报告的 `build_report_data`）；基线报告的情感走 `sentiment_sentences.py`；临时引用统计用本 skill 的 `citation_sources.py`，品牌计数用本 skill 的 `trial_brand_count.py`
- `geo-gap-diagnosis`：`layer_readings.py`、`page_gap.py`、`label_batches.py`（品牌计数、引用抽取、正文字段）、`diagnose.py`（来源类型调 `classify_source`）
- `geo-monitoring`（采集 `collect_answers.py`、采集完整性检查 `audit_crawl_integrity.py`）：`answer_validity`、`extract_product_cards`
- `geo-prompt-selection-builder`：`run_selection_mode.py` 线上运行时拷贝 `geo_presales_core`

调用方用 `sys.path` 指向 `geo-metrics/scripts`（脱离整套 skill 部署时用环境变量 `GEO_PRESALES_SKILLS_ROOT` 指 skills 根目录），包名仍是 `geo_presales_core`。

## 改动后的回归

- 单元测试：`geo-presales-report-builder/tests`、`geo-metrics/tests`（情感、引用来源分类、域名自检、开放品牌官网推断）。core 的 `test_geo_presales.py` 随已退役的 report-editor 归档在 `90-历史归档/旧版与过程稿/退役skill/geo-presales-report-editor/scripts/tests/`，改动 core 指标时需要在那里手动跑。
- 端到端：改 `mine_brand_lexicon.py` 或 `audit_lexicon_domains.py` 的挖掘、分档、拆分规则后跑 `python3 evals/e2e_lexicon_recall.py`（12 条用例，造数据、不联网），报告写到 `reports/lexicon-recall-e2e.md`；用例开头列了它防的十种失败方式。
- 端到端：用三份现有客户数据（一份售前报告、两份监测基线）跑售前报告数据层、校验、情感抽取、基线报告、试跑计数，输出与改前逐项比对。脚本见项目根 `.snapshots/geo-metrics-20261110/run_ref.sh` 与 `compare.py`，读数有变化必须逐条说明原因。

## 还没收进来的

第二期（2026-11-10）已收进：逐品牌引用份额、逐题读数（`metrics.question_object_stats`）、引用抽取与计次（`citations.py`）、平台正文字段表（`crawler.ANSWER_FIELD`）、品牌词表读取（`lexicon.py`）、竞品站点名单（词表顶层 `competitor_site_domains`）；监测基线已不打统计补丁。

2026-11-18 收进：引用域名补判的脚本与数据（原 geo-presales-report-builder 的 `assets/domain-*`、`category-taxonomy.json`、`brand_lexicon.*` 与 5 个脚本）、试跑品牌计数（原 geo-monitoring `trial_brand_count.py`）、题库与试跑目录读法（原 `changeability_domains.py` 里的 Resolver 等，现 `runs.py`）。仍留在原 skill、只调用 core 的：`changeability_domains.py`（可改变性是选词与监测的判断规则，不是指标）、`build_baseline_html.py` 与 `build_report_data.py`（报告组装）、`verify_report_data.py`、`audit_independent.py`（报告独立复算）。

刻意保留的第二份实现：`verify_report_data.py`（独立复算，用来抓数据层的错）和报告页 `report-engine.js`（浏览器里多选现算，靠 `check_engine_parity.js` 对账）。改口径时这两处要一起改。清单在项目根 `docs/exec-plans/active/geo-metrics-skill-progress.md`。
