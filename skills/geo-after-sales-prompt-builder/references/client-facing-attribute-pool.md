# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 中国农业大学海外招生监测属性池, Bewinch 台式净饮机售后生词, Botslab NightVue NV900 售后监测主题与词表, and Piltwave 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Format: the Feishu Base template

The client confirmation piece is a Feishu Base copied from the template 《AI 搜索监测确认表（模板）》, kept in the same wiki space as 《售后生词规则》. Copy it once per client and per market/language, delete every 【示例】 row, and fill the 使用说明 doc's data-source placeholders with the sources actually used. **The 使用说明 doc is the only client-facing explanation** (Suda 2026-10-15): it carries the service flow, what the brand party provides, platform permissions (GSC 受限 / GA4 查看者 / Bing 只读 — grant access first, export only as fallback), brand-material timing, how to check each table, content review and publishing, and how to read results. Do not send a separate guide document; edit the template's 使用说明 instead. The Base has no 需品牌方确认 checkbox: every table is for the brand party to review, and what we need from them is written in 提示词矩阵 还缺什么 (filter it non-empty) or as an 【请补充】 placeholder in 业务范围 (Suda 2026-10-15). The sections below still define what each table must contain.

**Settled table set (PETKIT, 2026-10-14/15).** Five confirmation tables plus the 使用说明 doc, then three baseline tables (added 2026-10-15, filled after the candidate baseline), in this order (监测主题 and 竞品名单 tables were removed 2026-10-15 and folded into 业务范围):

| 表 | 一行是什么 | 要点 |
|---|---|---|
| 业务范围 | 一个可以单独确认的事实 | Replaces 品牌事实. Multi-valued facts get one row each (产品线（1）（2）…, 主要受众（1）…, 买家要完成的任务（1）…, 竞品（1）…, 差异化优势（1）…). **Product lines**: the brand party may list every line it wants; we recommend starting with one, so mark it 产品线（1）（优先） and the rest （后续） — the priority line gets Prompts and monitoring first, the others join in later cycles. This is guidance, not a restriction: keep multi-line support in every table. 买家要完成的任务 gets one row per main audience. 初始题库规模 is filled by us, never by the brand party. Each 竞品（n） row reads `名称（直接竞品 / 替代方案；适用：产品线）：依据`, with mention-based reasons only — never 首推 or a rank. Always include 品牌与产品别名 (abbreviations, local-language names, former names, sub-brands, model nicknames, common misspellings, and similarly named other companies; we pre-fill what AI answers and reviews show, the brand party completes it — mention counting depends on it) and 差异化优势 rows (one fact plus its evidence each). No 「已核对」 rows: a fact we verified ourselves is either written here as fact or folded into the matching attribute's 备注 |
| 买家原话 | 一条买家说法 | The evidence log; see *买家原话* below |
| 提示词矩阵 | 一种买家处境下要测的一条属性 | Carries the attribute pool — **no separate 属性池 table**; see *提示词矩阵* below |
| 提示词库 | 一道提示词 | Links its 所属切片 (one 提示词矩阵 row) and its 证据 (买家原话 rows) |
| 需要品牌方提供的数据 | 一项只有品牌方能拿到的数据 | Buyer-signal data per [signal-sources.md](signal-sources.md) → 客户提供什么, plus three content-production rows: 官网未公开的产品事实, 品牌规范 (必须给), 即将发生的变化. Do not ask for anything the official site already publishes — we extract it into 业务范围 and the brand party only checks it |
| 基线读数 | 一道提示词在一个平台的基线结果 | Written by our statistics script; see *基线读数 · 主题汇总 · 被引来源* below |
| 主题汇总 | 一个主题在一个平台的基线结果 | Pooled per Topic × platform by the same script |
| 被引来源 | 一个被引用的域名或网页 | Top 20 per Topic × platform |

**No separate 监测主题 table.** 监测主题 is a single-select column on 提示词库 only; 提示词矩阵 has no Topic column, because a slice's Topic is whatever its linked Prompts carry and a second hand-filled copy drifts (Suda removed it 2026-10-15); Topics are ours to name and split — the brand party does not know what to write there, so 业务范围 carries no 监测主题 rows (Suda 2026-10-15); the ≥5 candidate / ≤10 formal counts are checked by filtering 提示词库. A topic table would only duplicate the name and need links kept in sync. Competitors are 竞品（n） rows in 业务范围 carrying 适用产品线, not 适用主题; no separate competitor table, since nothing links to it.

**Dashboard 「覆盖分布」 (Suda 2026-10-15).** The template carries one dashboard, so every copy has it: a short how-to-read text block; 提示词总数 and 已批准提示词 cards; 切片覆盖情况 (ring on 覆盖情况); 旅程阶段 × 提示词类型, 按受众 and 按优先级 (sum of 目标题数 on 提示词矩阵); 按主题 and 库分层 (count on 提示词库). Distributions sum 目标题数, which is filled before Prompts are written, so the plan's gaps show before review — an empty stage, a main audience or product line at zero. Read it before sending the Base and before the candidate baseline; it replaces no check in the validator.

Customer-facing names: call the Prompts **提示词** (tables 提示词矩阵 / 提示词库, field 提示词); keep **监测主题** for Topics. Suda reversed the 2026-08 ban on 「提示词」 on 2026-10-14. Use one term throughout the Base and the 使用说明.

### 提示词矩阵

One row is **one coverage slice × one tested attribute** (Suda 2026-10-15 realigned the matrix to Aleyda's slice columns). Aleyda's matrix row is a coverage slice and the attribute is one of the slice's dimensions; Prompts are written per slice, not per attribute. That is why the attribute pool is folded in rather than linked: a separate attribute table is many-to-many with the slices, and the brand party has to cross-read two tables to confirm one judgement.

Columns, in view order:

`切片编号（主字段） | 产品线 | 受众 | 旅程阶段 | 提示词类型 | 约束 | 属性 | 购买影响 | 相对竞品 | 可改变性 | 优先级 | 目标题数 | 已有问题 | 已批准题数 | 覆盖情况 | 还缺什么 | 备注`

- **切片编号** is the primary field: plain text M-001, M-002… in order (a text field, not a formula). The slice's meaning lives in its dimension columns — 受众, 旅程阶段, 提示词类型, 约束, 属性.
- **提示词类型** (single select: 推荐榜单 / 使用场景 / 对比 / 替代方案 / 验证 / 价格与购买 / 学习了解 / 评价口碑 / 售后支持, after Aleyda's Prompt Type) is a slice dimension. When one situation needs two question shapes, split it into two slices so the bank does not collapse into one shape.
- **约束** is its own column (same name as in 买家原话): the conditions the buyer carries beyond the attribute — budget, home size, number of cats, days away, a named rival or model. Write 2–3 keywords separated by 、 (「小公寓、2–3 只猫」「300 美元以内」「对手 Litter-Robot」), after Aleyda's CONSTRAINT column; do not restate 受众, 旅程阶段 or 属性 — the full wording lives in the Prompt. Slices that share every other dimension must still differ here (Suda 2026-10-15).
- **目标题数 / 已批准题数 / 覆盖情况**: we fill 目标题数 **before writing Prompts**, not after. Default is 1. Add one per additional buyer constraint wording where the candidate list would change — "two cats" vs "four or more" on the same feeder slice may pull different brands; different phrasings of the same constraint that would produce the same shortlist do not add a count. Note in 备注 which constraint each extra Prompt tests. Leave 目标题数 blank (never 0) on slices with no first-stage Prompt — the coverage cell then shows blank. 已批准题数 is a formula counting linked Prompts whose 审核状态 is 已批准; 覆盖情况 is a formula (已覆盖 / 未达标 / 不配题 for 0).
- **Rows.** Every situation × attribute pair that has Prompts is a row. Every attribute with no first-stage Prompt also gets one row (受众 the category's base audience, 约束 written from its buyer problem, a judged 旅程阶段, 目标题数 blank), with the reason at the start of 备注 — 「首期不配提示词：购买影响低，不决定买家选谁」 or 「…：能力缺口，发布内容改变不了 AI 的说法」. Do not add a separate 去向/缺口说明 column. Category-baseline Prompts sit on rows with an empty 属性.
- **受众** is a single select with the same option set as 买家原话. Use only real buyer groups. A journey state is not an audience — 「已在比较具体品牌」 is the 对比 stage, not a persona — so named-brand Prompts are filed by the group their wording names, and rows with no narrower group condition take the category's base audience — the buyer group the whole category serves, such as 「养猫家庭」 for pet-cat devices — never 「通用」 and never blank (Suda 2026-10-15). List the base audience as 主要受众（1） in 业务范围 so it is an option in the select. Audiences beyond the brand party's listed 主要受众 are added to 业务范围 as 主要受众 rows.
- **旅程阶段** uses the eight stages below; there is no separate 买家任务 column.
- **购买影响** is judged **per situation**: the same attribute may be 高 for one audience and 中 for another. Raise to 高 when the row's audience buys the product for exactly this attribute and drops any option that fails it (多猫家庭 × 每只猫分开记录; 预算敏感 × 耗材成本). Lower to 中 on post-purchase troubleshooting and returns rows, and on generic alternatives rows where the attribute is not what decides.
- **相对竞品 / 可改变性** are judgements about the attribute itself: identical on every row of that attribute, because the priority formula reads them. The brand party may correct any one row; we write the change back to all of its rows when collecting.
- **还缺什么 / 备注** are written **only on the first row of each attribute**, so the brand party meets each question once. When a named fact-check Prompt needs the brand's standard answer (does feature X need a subscription, how long does the battery last), write that request into the attribute's 还缺什么 with 「点名题要用：…」 — not on the Prompt itself.
- **优先级** is a formula; the brand party never fills it:
  - look up 购买影响 (高 / 中 / 低) × 可改变性 (高 / 中 / 低) in the tier table in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*; changeability is graded there by two ordered questions;
  - **P1 only at 高 × 高**; the Base formula field encodes the same table;
  - rows with an empty 属性 (category baseline) are fixed at P1 — they measure which brands AI lists with no condition, the base of natural visibility.
  - Check the distribution after filling: P1 must stay a short list. If 高 × 高 rows pile up, re-check whether the rows graded 高 changeability are really unwritten where AI can read.
- Drop: formula-built slice IDs, 市场与语言 (one Base is one market), 业务优先级 (half importance, half an echo of attribute priority), 客户确认 (the brand party edits cells directly — see *How the brand party reviews*), and any column whose every row holds the same value. 目标题数 / 覆盖情况 came back on 2026-10-15 because 审核状态 now separates written from approved, so coverage is no longer always 已覆盖.

### 旅程阶段：八段，三张表同一套

`发现 | 解决问题 | 评估 | 对比 | 替代方案 | 验证 | 交易 | 购后支持`

Use one stage column in 提示词矩阵, 提示词库 and 买家原话. Aleyda's shortlist step folds into 发现; category understanding and source discovery are not used for after-sales banks. The older five-stage labels map as 了解需求→发现, 比较方案→对比, 评估是否适合→评估, 准备购买→交易, 使用与续费→购后支持, but re-judge each quote by its content when converting: a 「how do I get rid of the smell」 post is 解决问题, a filtering condition such as 「must be stainless steel」 is 发现, a 「does it have a hidden monthly fee」 check is 验证. A row with no Prompt still gets a judged stage — never leave it blank.

### 买家原话

`原话（主字段） | 中文意思 | 涉及品牌 | 来源类型 | 受众 | 旅程阶段 | 约束 | 来源说明 | 来源链接 | 收集日期 | 证据可信度 | 引用它的问题 | 产品线 | 输入编号`

- **Primary fields are chosen for what a link cell shows** (Suda 2026-10-15). A linked cell displays the other table's primary field, so: 买家原话 leads with **原话**, and 提示词库's 证据 cell shows the quote itself, letting the brand party judge a Prompt's grounding without leaving the row; 提示词库 leads with **提示词**, so 提示词矩阵's 已有问题 lists the actual questions; 提示词矩阵 keeps **切片编号**, because no content column identifies a slice — PETKIT's 120 rows had 3 product lines, 52 attributes of which 25 repeat, and 17 repeated 属性 + 受众 + 旅程阶段 combinations. When the brand party reads only Chinese, lead 买家原话 with 中文意思 instead.
- **输入编号** stays as the last column. Our bank JSON's `evidence_refs` and `config.audience_inputs` cite it, and both sides use it to point at one quote in feedback.

- **涉及品牌** (multi-select) names the brand the quote is about; generic buying posts and search terms are 「未指明品牌」. A subreddit name is not a brand mention.
- **来源类型** is the real source — 社区 / 评价 / 搜索数据 (later 销售记录、客服记录、GSC、站内搜索 when the brand party supplies them). Never 「竞品评价」: whose product it is goes in 涉及品牌.
- **受众** uses the same single-select set as 提示词矩阵; who the poster owns (「PETKIT 用户」「LR 用户」) is not an audience.
- Marketplace summary tags (Amazon 「Customers say」) keep only the tag text in 原话, the product name in 来源说明, and a 中文意思 that names the brand.

### 提示词库

`提示词（主字段） | 中文含义 | 主题（单选） | 状态 | 库分层 | 所属切片 | 证据 | 审核状态 | 产品线`; 编号, AI 认知差距 and 提及率 exist but are hidden in the default view.

- **审核状态** (待审核 / 已批准 / 需修改, default 待审核) is the approval gate: we mark 待审核 after internal QA; the brand party marks 已批准 when the Prompt is fine or after editing it directly, 需修改 when it wants us to rewrite. **Only 已批准 Prompts enter the candidate baseline.** It is separate from 状态 (候选 / 正式 / 停测), which records what happened after the baseline.
- **No slice-level columns on 提示词库.** 旅程阶段, 提示词类型, 约束 (and the old 买家问题与场景) belong to the slice and were identical on all 100 PETKIT Prompts; a second copy drifts when the brand party edits one table. The reviewer opens 所属切片 to see them (Suda 2026-10-15). The bank JSON keeps `journey_stage` for metrics and the validator.

- Sort the view by 编号.
- **AI 认知差距 and 提及率 exist only after the candidate baseline.** Judge AI 认知差距 per Prompt from that Prompt's own answer text (有缺口 / 无人讨论 / 无缺口). Until then every row is 「待基线」 and both columns are hidden in the view. Never push an attribute-level judgement or presales answers onto individual Prompts — Prompts under one attribute would all read the same however their wording differs, which is not data.
- **监测主题 names describe what the Topic holds.** A category Topic that also carries condition Prompts (safety, large cats, one app) is 「××选购条件」, not 「××品类」; a Topic whose Prompts span cost, reliability and upkeep is named for all three.
- **The formal set is a view, not a table.** 提示词库 has a 「正式监测」 view filtered to 状态 = 正式. Do not copy formal Prompts into another table: two copies of one wording drift.

### 基线读数 · 主题汇总 · 被引来源 (Suda 2026-10-15)

Three tables hold the baseline results — every Prompt runs about 5 times per platform. Metric values are **written by our statistics script** (`geo-presales-report-builder` → `build_report_data.py`: `build_records` per Prompt, `build_slice` per Topic × platform, `build_sources` for top sources; all call the same core `compute_metrics`). The Base never recomputes a metric with formulas — a second implementation drifts from the core. Platforms are never merged into one number.

- **基线读数** — one row per Prompt × platform: `平台读数（主字段，公式 = 平台） | 提示词（关联提示词库，反向字段「基线读数」） | 主题（公式） | 平台 | 计入可见度 | 采集日期 | 有效回答数 | 提及率（%） | 声量份额（%） | 平均提及位置 | 官网引用份额（%） | 正向情感占比（%） | 备注`. **计入可见度** is 是 only for unbranded Discovery Prompts that ask for candidates (from the bank JSON's intent, brand scope and `formal_visibility_eligible`); 提及率, 声量份额, 平均提及位置 and 官网引用份额 are filled only on those rows and left blank elsewhere. 正向情感占比 covers every Prompt.
- **主题汇总** — one row per Topic × platform, the same metrics pooled over the Topic's answers (sum of numerators ÷ sum of denominators, never an average of per-Prompt rates). 主题 is written exactly as in 提示词库.
- **被引来源** — the top 20 domains and the top 20 pages per Topic × platform (plus 「全部主题」), with 排名, 引用次数 (正文引用，不去重), 引用份额 and 来源类别 (the report's labels: 自有网站 / 竞品网站 / 媒体网站 / 社交平台 / 新闻稿平台 / 机构网站 / 其他; 自有网站 is the official site).
- **Not tracked here, by decision:** 推荐率 and 决胜率 (not important enough for the baseline; 决胜率 stays an ad-hoc analysis for comparison Prompts); 事实准确率 (fact-accuracy Prompts are written only when a mention rate comes out low, and are followed in the retest table, never promised); Shopping GEO metrics (product and merchant cards are a different grain, Perplexity has no product field, and the presales report carries no shopping module either — add a separate table when a client's category actually triggers product cards). The hidden 提及率 field on 提示词库 predates 基线读数, pools platforms, and stays empty.

### How the brand party reviews

The brand party edits cells directly — wrong fact: change the cell; missing: add a row. There is no 客户确认 column (Suda 2026-10-15). Before sending, snapshot every table; when collecting, compare against the snapshot and `lark-cli base +record-history-list` to see each change, and review every edit to 购买影响 / 相对竞品 / 可改变性 because they move the priority formula. Filter 提示词矩阵 还缺什么 non-empty to find the must-answer cells.

### Facts we can verify ourselves

Settle what the public layer can settle before asking the brand party — for example whether a model is still sold: check the official site's product pages, redirects and search, then the main marketplace, and write the result into 业务范围 as a settled fact, not a question. Ask the brand party only for what only it knows.

## Canonical Shape

The sections below define the content. In the Base they live as: 品牌事实 → 业务范围, 属性池 → the attribute columns of 提示词矩阵, 监测主题与问题 → 提示词库. Where a section below conflicts with *Settled table set*, the table set wins. Use the sections that fit the task; do not force all of them into a small update.

1. **Opening scope paragraph**
   - State the monitoring object, product/category scope, market/language, and entry scenario.
   - Ask the brand party to confirm three things: the attribute list, the buying impact, and whether the brand is advantaged/at parity/weak versus competitors.
   - Explain the confirmation convention: in the Base the brand party edits cells directly and marks 审核状态 on 提示词库 (no 客户确认 column); document-format pieces keep a `客户确认` column, write-what-to-change, blank meaning reviewed with no change.
   - **State where our data came from**, in two or three plain sentences, so the brand party can judge the evidence instead of taking the table on trust: which public sources we collected (搜索需求与相关搜索、哪些评价平台、哪些社区——写实际用到的站点名，不写方法论), which of the brand party's own materials we used (销售/客服记录、GSC 等——只列用过的), and which AI answers were already collected (售前诊断或候选基线，带采集时间). Name only sources actually used in this engagement — the full menu stays internal in [signal-sources.md](signal-sources.md). One line of boundary: 公开来源查不到的，已在表中标为「待确认」或「需品牌方提供」，不会当成品牌方没有。

2. **核对时从哪里判断**

   The internal team may use a market-coverage pass to check whether the pool
   misses a product line, audience, journey stage, constraint, competitor,
   local terminology, regulation, currency, trust signal or source ecosystem.
   Show the filled slices in the 覆盖矩阵 table: we draft it, and the brand
   party only reviews whether an important buyer situation is missing. Never
   turn it into a questionnaire the client fills from scratch.

   | 要确认的 | 内部看什么 | 外部看什么 |
   |---|---|---|
   | 属性清单全不全 | 销售、客服、售后、win/loss、续费/退换货、GSC/站内搜索：是否有反复出现但表里缺失的问题 | 买家社区、评论、论坛、竞品页面、规格表、媒体评测、AI 回答里的高频属性 |
   | 购买影响高不高 | 这条不解决，买家会不会不入围、不购买、不续费、退货或要求补证据 | 买家公开选购理由、放弃理由、搜索规模、媒体评测维度、竞品主推方向 |
   | 相对竞品是优势还是持平 | 品牌自己的实测、交付记录、案例、服务条款、价格和可引用证据 | 竞品公开证据、第三方评测、榜单、社区口碑、AI 答案层同主题表现 |

   Adapt the wording by buyer type:
   - **B2B:** first-party sales/procurement/contract/renewal records usually outweigh public evidence.
   - **B2C hardware/consumer:** public reviews, community language, ecommerce Q&A and third-party reviews may carry the buyer-language layer; internal returns, service tickets, warranty terms and test data remain crucial for relative-competitor judgement.
   - Public absence is **not** `无优势` — but it is also **not** `待确认` until the external comparison has actually been run: the answer layer first, then the competitors' own public pages (spec sheets, certification pages, service terms), then third-party material. **Absence on both sides is likewise not `持平`** — that is exactly the case to put to the client, who knows where its own number sits in the industry. `待确认` is reserved for what stays undetermined *after* that pass and the client has not yet answered; name the material that would settle it, and ask the brand party for it. A verdict reached by comparison is ours to defend, and the client's internal records then either confirm it or upgrade it.

3. **品牌事实【请核对】**

   Keep factual scope separate from ranked attributes. Typical rows:
   - 品牌 / 业务模式 / 品类 / 产品或服务范围
   - 目标客户、目标企业画像或核心人群
   - 市场与语言、切入场景、适用边界
   - 官方域名
   - 竞品或替代方案（only if the comparison set itself needs confirmation）

   Use `项目 | 内容 | 为什么重要` (the Base's 业务范围; document-format pieces add `客户确认`). One fact per row; split multi-valued facts into numbered rows. Do not rank brand facts. Wording rules for these rows: describe AI performance as 推荐 / 提及 — never 首推、排第一、排首位 or a rank percentage, which the client-facing caliber does not use; competitor reasons cite mention rates only.

4. **属性池【请核对】**

   In the Base these are the attribute columns of 提示词矩阵 (see *提示词矩阵* above); the lists below define what each column means. For a document-format pool, default columns:

   `类别 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 还缺什么 | 备注 | 客户确认`

   Use a compact variant when evidence is simple:

   `类型 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 品牌方补充与确认`

   Column semantics:
   - `类别/类型`: readable grouping such as 品类、目标客户画像、痛点、使用场景、购买标准、产品能力、差异化、信任与合规、申请门槛、地域与市场、约束.
   - `属性`: the buyer decision focus AI should associate with the brand. Differentiators are rows in this table, not a separate section, Topic, or Tag.
   - `解决的买家问题`: plain buyer problem or selection risk. Keep it close to customer language.
   - `购买影响`: buyer-side impact, normally 高 / 中 / 低. Judge by “if unresolved, does the buyer drop or downgrade the brand?”, not by frequency alone.
   - `相对竞品`: the attribute's **real position in the industry** — 优势 / 持平 / 劣势 / 待确认. Judge it on the facts, not on whether they happen to be published (publication is the **gap type**, a separate axis). Compare against the leaders publicly **first**; where the public layer cannot settle it — the brand's own spec or internal capability — put the question to the client rather than guessing. Add a short evidence note.
   - `优先级`: our initial action priority, not the customer's vote and not the final optimization priority after baseline.
   - `还缺什么`: specific material needed from the brand party; omit or leave blank when no material is needed.
   - `备注`: evidence and caveats we found. Keep it factual and short. For factual attributes, also note where public sources conflict or AI answers state the fact wrongly or outdatedly (quote the wrong claim and its platform), so the brand party can confirm the right answer.
   - `客户确认`: write-what-to-change only.

   For multi-market work, add the market only when it changes the buyer
   decision or evidence context. Use the existing `类别/类型` and
   `市场/语言` facts, attribute, constraint, competitor, or Prompt columns;
   do not create one duplicated attribute row for every country merely to
   demonstrate coverage.

5. **Priority Rules**

   In the Base the tier is a formula on 提示词矩阵 (lookup in *提示词矩阵* above). Before any answers are collected, set the initial priority from **importance × changeability**; current gap is `待测` until the baseline (the three conditions and their scales are in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*). `购买影响` is the importance reading; `业务重点` the brand party states counts as evidence for it. `相对竞品` and the gap type feed changeability: an `优势` or `持平` row whose facts are unpublished (证据缺口) is the cheapest win; a `劣势` row behind on the facts, or a consensus-locked direction, scores low.

   Important constraints:
   - P1 can coexist with `持平`: for a new product or category gate, the first-stage problem may be "AI does not know we have this," not differentiation.
   - P3 rows remain visible so the brand party can disagree, but P3 attributes do **not** get first-batch Prompts.
   - Only P1/P2 attributes normally carry first-stage Discovery Prompts.
   - `待确认` means the evidence is missing, not that the attribute is weak.
   - Once the baseline has measured the current gap, re-judge changeability from the answer layer and adjust each Prompt by its current gap (importance × current gap × changeability); do not backfill the current gap before collection.

6. **监测主题与问题 / 提示词【请核对】**

   Include this section when the customer needs to confirm candidate Prompts, not when the current task is attribute-only.

   Recommended columns:

   `市场 | 监测主题 | 买家问题（或客户问题与场景） | 监测问题（英文或当地语言） | 中文含义 | 标签/属性 | 客户确认`

   Compact variant:

   `监测主题 | 买家问题 | 监测问题（英文或当地语言） | 中文含义 | 客户确认`

   Rules:
   - No question numbering in the customer document; crawler numbers are unstable.
   - Discovery-first: first staged set is normally all non-branded Discovery.
   - Keep the buyer problem / customer scenario adjacent to the Prompt, so the brand party can judge whether the wording matches real buying situations.
   - P3 attributes should not appear as first-stage Prompt coverage.
   - Each Prompt's buyer problem must exist in the intent/attribute table, and every P1/P2 buyer problem intended for first stage must have at least one Prompt.
   - Topic counts may differ; do not add filler for visual balance.
   - Keep `Prompt Task` in internal planning. The customer sees it only as the eight-stage 旅程阶段 column; do not add a separate 买家任务 column next to it.

7. **竞品（请确认）**

   In the Base these are 竞品（n） rows in 业务范围. For a document-format piece, add a separate section when competitor scope is unstable or customer-submitted competitors were replaced: `品牌 | 说明 | 客户确认`.

   Explain each inclusion/exclusion by “same buying comparison set,” not by brand fame alone.

8. **需要品牌方提供的数据**

   Include this section whenever the attribute pool is still being built. List only the data the brand party alone can access, using the table in [signal-sources.md](signal-sources.md) → 客户提供什么 (`数据 | 必要性与怎么给 | 品牌方补充与确认`). Mark 销售与 CRM 记录 and 客服记录 as 必须给 and the platform data as 最好给; do not ask for public search data, reviews or community language — we collect those. Say in one line that personal and customer-company details will be removed before use and raw records stay internal.

9. **候选基线与锁词流程**

   If the document hands off to monitoring, state the staged process in four lines:
   1. 品牌方确认业务重点、事实边界和属性池。
   2. Candidate Prompts run 5 times per proposed platform (the candidate baseline), in one sitting or over several days; the same runs check fit, ambiguity, leading wording and duplication.
   3. The formal set — at most 10 Prompts per purchased Topic — is chosen by attribute priority, confirmed by the brand party, and version-locked.
   4. Unchanged formal Prompts keep their candidate-baseline readings as the Before baseline; reworded ones are rerun 5 times.

## Wording Rules

- Use `品牌方`, not `贵司` / `贵校`.
- Write the final document directly; do not mention “上一版”, “补充更正”, or internal revision traces.
- Keep methodology, word-frequency work, validation steps, and evidence-position mappings out of the customer document. Archive them internally.
- Mark uncertain claims as `待核`, `待确认`, `待验证`, or `品牌自述`; do not turn trade-press/self-declared claims into facts.
- Avoid merged cells in Feishu tables. Empty cells are safer when rows are inserted or deleted.
- If a number is visible only through JavaScript or non-static page rendering, note the source limitation before treating it as AI-readable evidence.
- The brand party corrects facts and priorities; we make the judgement. Do not ask them to write our reasoning for us (for example, “why buyers credit this advantage”).
