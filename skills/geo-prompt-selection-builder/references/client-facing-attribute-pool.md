# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 某大学海外招生监测属性池, Abrand 台式净饮机售后生词, Bbrand ModelN1 售后主题与词表, and Wbrand 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Format: the Feishu Base template

The client confirmation piece is a Feishu Base copied from the template 《AI 搜索监测确认表（模板）》 in the project wiki space (the template stays in use; the separate 《售后生词规则》 document is retired, see after-sales-rules.md). Copy it once per client — several markets share one copy (see *Several markets in one Base* below) — delete every 【示例】 row, and fill the 使用说明 doc's data-source placeholders with the sources actually used. **The 使用说明 doc is the only client-facing explanation** (Suda 2026-10-15): it carries the service flow, what the brand party provides, platform permissions (GSC 受限 / GA4 查看者 / Bing 只读 — grant access first, export only as fallback), brand-material timing, how to check each table, content review and publishing, and how to read results. Do not send a separate guide document; edit the template's 使用说明 instead. The Base has no 需品牌方确认 checkbox: every table is for the brand party to review, and what we need from them is written in 属性池 还缺什么 (filter it non-empty) or as an 【请补充】 placeholder in 业务范围 (Suda 2026-10-15; moved from the matrix to 属性池 2026-10-20). The sections below still define what each table must contain. **The brand party always reads 提示词库; 属性池, 主题 and 提示词矩阵 are optional reading** (Suda 2026-10-28), so 提示词库 must stand on its own: each Prompt's 主题, 优先级 and 出题原因 explain themselves, and a question we need answered is never left only in a table the brand party may skip without telling them where to look.

**Settled table set (Pbrand, 2026-10-14/15; 品牌事实核查 added 2026-10-16; 属性池 added 2026-10-20; 主题 re-added 2026-10-27; 属性池 / 提示词矩阵 / 主题 reworked 2026-10-28).** Eight confirmation tables plus the 使用说明 doc, in this order. Baseline results are not written into the Base — they are delivered as a single-file HTML report (Suda 2026-10-21; see [baseline-report.md](../../geo-monitoring/references/baseline-report.md)). The 基线读数 / 主题汇总 / 被引来源 tables and their dashboard, added 2026-10-15, were removed from the template and from Hbrand (竞品名单 was removed 2026-10-15 and folded into 业务范围; the 主题 table removed the same day came back on 2026-10-27, see *主题表*):

| 表 | 一行是什么 | 要点 |
|---|---|---|
| 业务范围 | 一个可以单独确认的事实 | Replaces 品牌事实. Multi-valued facts get one row each (产品线（1）（2）…, 主要受众（1）…, 买家要完成的任务（1）…, 竞品（1）…, 差异化优势（1）…). **Product lines**: the brand party may list every line it wants; we recommend starting with one, so mark it 产品线（1）（优先） and the rest （后续） — the priority line gets Prompts and monitoring first, the others join in later cycles. This is guidance, not a restriction: keep multi-line support in every table. **Audiences carry a priority mark; the conversion path is written as the priority one** (Suda 2026-10-22, conversion path revised 2026-10-23): 主要受众（1）（优先） names the audience that drives the business — the brand party confirms this, it is their daily sales judgement, we never derive it from evidence volume. When the brand party has already written enough to tell (its template answers, the priority product line, its 核心可见度问题), we pre-fill the mark ourselves, say so in the row (「我方按品牌方已填内容推断，品牌方可改」) and do not spend meeting time asking (Suda 2026-10-23, Nbrand); 转化路径 is the path visibility should feed first. **The brand party answers two questions, in these words** (Suda 2026-10-23): 「核心业务目标是什么？」 (→ 业务目标 rows) and 「希望用户完成什么关键转化动作？」 (→ 转化路径 rows); the bracketed detail on each row below is ours to pre-fill, not extra questions. 转化路径 is Aleyda's step-1 question, filled in by the brand party in its own industry's terms (a fixed option list does not fit across industries): which action the business wants a buyer to take after AI points them to it — 「直接购买」「提交询盘」「预约 Demo」「注册」「申请试用」, or whatever the industry actually calls it (「预约看房」「申请入学」「加购」「到店」). Write only the priority path, one 转化路径 row, 一句话 in the brand party's wording, with the channel in the same line or 备注 when it matters (Amazon US, 官网表单, App Store); non-priority paths are not listed, because nothing downstream reads them (Suda 2026-10-23). Only when two paths are equally key (a B2B tool that wants both demo bookings and self-serve signups) write two rows, unranked. We pre-fill the candidate from the buttons on the brand's site (Buy on Amazon, Book a demo, Download, Find a store …) and the sales conversation; the row opens with 【请品牌方补充】, and the brand party confirms, corrects or replaces it. No funnel steps and no journey-stage question. **Selection reads the path for one thing** (Suda 2026-10-28): the pages the brand edits on that channel (Amazon store and product pages, App Store page, own store) count as 官网 when a Prompt's 可改变性 is judged from cited domains; stage weight does not come from the path but from the fixed stage cap on matrix rows (*提示词矩阵* → 优先级). The 优先 marks on product lines and audiences feed the rows' business focus, and a skeleton cell left empty for a non-priority audience is closed as 「低业务优先，留到后续周期」 — the brand party's trade-off — which is distinct from 「无买家证据」, our research gap. **社区平台与信源服务（我方填）** is one row naming the communities the brand party posts in from its own account (Reddit, LinkedIn…) and any source service the client bought; it decides which cited domains count as 社区 rather than 难影响 (see *提示词库* → 可改变性). **业务目标（n） and 营销活动（n）** (Suda 2026-10-23) are the two rows that say what the visibility is for and what the brand is about to push. 业务目标 reads `目标（产品线 / 市场 / 受众；衡量方式）` — what the brand party wants AI visibility to do this service period. The brand party's own answer is one plain sentence — 「提升销售额」「获取有效销售线索」「增加试用用户」 — and we complete the bracket from the sales conversation (which product line, market and audience, and how it is measured), the brand party correcting it; at its most specific it reads like entering the candidate list for one buying situation, carrying a new product line into a new market, or feeding demo requests. 营销活动 reads `活动名（时间；产品线 / 市场）：主推卖点` — launches, big promotions, market entries, PR or creator pushes inside the service window; only the brand party knows these, so the row opens with 【请品牌方补充】. Neither row is buyer evidence and neither licenses a Prompt by itself: a business goal makes the matching matrix rows a business focus (see *提示词矩阵* → 优先级); a campaign's 主推卖点 enters 属性池 only as a candidate attribute that still needs buyer evidence, a product not yet launched gets no Discovery Prompt (AI cannot know it; plan a Verification Prompt for after launch), and campaign dates go into the collection plan handed to `geo-monitoring` so the baseline avoids or deliberately brackets them. 买家要完成的任务 gets one row per main audience. 初始题库规模 is filled by us, never by the brand party. Each 竞品（n） row reads `名称（官网域名；适用：产品线）：依据`, with mention-based reasons only — never 首推 or a rank; direct competitors and alternatives are not labelled apart (Suda 2026-10-21: the distinction changes nothing for us), and an alternative with no site writes 「无固定域名」. The domain is required (Suda 2026-10-20): citation counting matches competitor pages by domain. Always include 品牌别名 (abbreviations, local-language names, former names, sub-brands, common misspellings, and similarly named other companies; we pre-fill what AI answers and reviews show, and the row opens with 【请品牌方补充】 because only the brand party knows its Chinese name and internal nicknames — mention counting depends on it). Name it 品牌与产品别名 only when product or model names circulate on their own (Bbrand N1, Pbrand feeder models); a platform whose app name is just the brand plus a descriptor needs no product layer (Hbrand, Suda 2026-10-20) and 差异化优势 rows (the brand party lists its selling points as plain statements; no evidence and no 品牌自述 label are asked for — we judge `相对竞品` ourselves, and evidence is gathered only when content work starts after the baseline, Suda 2026-10-19/20). 核心可见度问题 rows state only the buyer question itself — not 「问 AI」 framing and not what AI should say about the brand (Suda 2026-10-20). No 「已核对」 rows: a fact we verified ourselves is either written here as fact or folded into the matching attribute's 备注 |
| 买家原话 | 一条买家说法 | The evidence log; see *买家原话* below |
| 属性池 | 一条属性 | The single place an attribute is maintained — 属性名、类别、相对竞品、判据与证据、还缺什么、产品线. It judges only 相对竞品 — no tier, no 重要性, no 可改变性 (Suda 2026-10-28). 提示词矩阵 links to it through 属性关联. See *属性池* below |
| 主题 | 一个主题 × 一个市场 | Clustered from 提示词矩阵 rows once the skeleton and row priorities are set (Suda 2026-10-28); carries the demand evidence, status and recommended order. See *主题表* below |
| 提示词矩阵 | 一个处境：主题 × 产品线 × 受众 × 市场 × 旅程阶段 | Our working table. Lists the situation's important attributes and is **the only place priority is judged**; see *提示词矩阵* below |
| 提示词库 | 一道提示词 | Links its 所属切片 (one 提示词矩阵 row), its 属性 (one 属性池 row) and its 证据 (买家原话 rows); 主题 comes from the slice. The one table the brand party always reads |
| 需要品牌方提供的数据 | 一项只有品牌方能拿到的数据 | Buyer-signal data per [signal-sources.md](signal-sources.md) → 客户提供什么 only — data that changes a Prompt-generation judgement. The content-production rows (官网未公开的产品事实, 品牌规范) were dropped 2026-10-19: they belong to the content stage, not Prompt generation. 即将发生的变化 (new launches, promotions) was dropped with them and came back on 2026-10-23 as 营销活动 rows in 业务范围, not as a data request here. Do not ask for anything the official site already publishes — we extract it into 业务范围 and the brand party only checks it |
| 品牌事实核查 | 一条官网自相矛盾、或只有自述没有外部佐证的事实 | Filled during the same research pass that judges `相对竞品`; see *品牌事实核查* below. Sits next to 业务范围 in the Base — both are the brand-fact layer, this one is the problem list |

**IDs freeze once the Base reaches the brand party** (Suda 2026-10-20). 切片编号 (M-…) and Prompt IDs never change after the first send: new slices and Prompts are appended at the end; a removed Prompt's ID is never reused, and a slice whose Prompts are all removed stays as a row (目标题数 blank, reason at the start of 备注); merging Topics does not renumber Prompts. Exceptions and mappings in generation scripts key on stable values — 「主题|受众|旅程阶段」 for a slice, `intent_key` for a Prompt — never on the displayed ID. Hbrand drifted three times in one day: a slice inserted mid-table shifted the next 73 IDs, a Topic merge renumbered the Prompts, and an audience exception keyed on a Prompt ID landed on another Prompt (M-071 ended up marked as a buyer).

**The Base holds only Prompts under test** (Suda 2026-10-23, Nbrand). A Prompt that stops — reworded or culled at the trial, not selected at lock, or retired from the formal set later — is deleted from 提示词库, not kept as a 停测 row: the brand party reads 提示词库 to decide, and dead rows are noise. Its question_id and reason stay in the bank JSON `config.retired` (bank `status` 停测, readings in the reports), so nothing is lost; no table links to a Prompt except the matrix's back-link 已有问题, which simply drops it. Delete only after a snapshot, and say in 备注 of the slice when it changes a 目标题数.

**After the brand party can see the Base, deploy incrementally only** (Suda 2026-10-20). Never delete a table's rows and rebuild them: append or edit in place so every record_id survives, because link fields (属性关联, 所属切片, 证据) point at record_ids. Run `python3 scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` before and after each deploy; the deploy is done only at zero differences. The script compares the live Base with the spec the generation script writes (`{表名: [行]}`): only fields present in the spec are compared, formula columns are skipped, keys starting with `_` are ignored except `_属性名`, which is resolved through 属性关联 to the pool's 属性; link fields are written `"表名:主键"` and compared by the target's key, never by record_id. Default keys: 主题=主题+市场 (a `+` joins several fields into one key), 提示词矩阵=切片编号, 提示词库=编号, 买家原话=输入编号, 业务范围=项目, 属性池=属性, 需要品牌方提供的数据=数据, 品牌事实核查=事实项 (override with `--key 表名=字段`; rename with `--alias spec字段=线上字段`, default 监测主题=主题; `--tables` limits the run; `--json` saves the detail). URL cells read back as `[文字](链接)` and dates carry a midnight time — both are normalised. Exit code 0 = no difference, 1 = differences, 2 = the Base could not be read (never reported as clean). Run it from the client's directory with the script's absolute path — `python3 -I <项目根>/.agents/skills/geo-prompt-selection-builder/scripts/diff_base_against_spec.py --base <token> --spec <spec.json>`: lark-cli only writes to the working directory, so running it from the skill directory fails with `unsafe output path`; the script deletes its temporary files afterwards. On Hbrand its first run found 14 real drifts (9 in 需要品牌方提供的数据·必要性 still using the retired 必须给 / 最好给 options, 5 matrix 备注). Hbrand's whole-table rebuild replaced record_ids and emptied all 87 属性关联 links, shifted 买家原话 KW-018–032 by three rows, and once wiped every matrix 备注 — each found by hand afterwards.

**主题表** (Suda 2026-10-27; reworked 2026-10-28). A Topic is a set of intents around one shared buyer need or purchase decision, each intent represented by a Prompt; it is the unit of visibility statistics, competitor comparison, optimisation diagnosis and purchase. **Topics are clustered from 提示词矩阵 rows** once the skeleton and the row priorities are set (SKILL.md Workflow step 5): P1 and P2 rows whose buyers are solving the same problem or making the same decision — same competitor set, same evaluation standard, same optimisation direction — form one Topic. We cluster by judging the decision task, never by text similarity: algorithmic keyword clustering drifts with its threshold and fragments one need into several groups (SE Ranking, Keyword Insights; 30-选Topic与生词/研究与方法/SEO主题聚类方向调研-20261027.md). One row is one Topic × one market. Columns: `主题（主字段） | 市场 | 产品线 | 状态 | 推荐顺序 | 父关键词 | Google 月搜索 | GSC 展示 | 买家原话条数 | 计划题数 | 可改变性低占比 | 依据与说明`.
- **主题** is named in the buyer's words for the category or task (「钱包安全体检」), never after one attribute or selling point. A Topic can span several attributes, audiences and journey stages; each Prompt belongs to exactly one Topic. There is no coverage / depth Topic type.
- **状态**: 候选 (in the trial) / 已采购 (bought, under formal monitoring) / 停测 (not selected or retired). A 停测 Topic keeps its row so the reason stays visible.
- **推荐顺序** (number) is our recommended purchase order: first the Topics holding business-focus rows (a 核心可见度问题, 业务目标, 营销活动 or priority audience — see *提示词矩阵* → 优先级); then by number of P1 Prompts; after the trial, a Topic with a high 可改变性低占比 moves back. The reason goes in 依据与说明. 提示词库's hidden 主题排序 column reads it so the dashboard shows Topics in this order.
- **父关键词 / Google 月搜索 / GSC 展示 / 买家原话条数 / 依据与说明** carry the demand evidence the Topic is named from. A Topic with 0 buyer quotes is marked 待验证 in 依据与说明. No 需求等级 column.
- **计划题数** sums 目标题数 over the matrix rows filed under the Topic (formula through the reverse link of 提示词矩阵 主题): a candidate Topic needs at least five before Prompts are written. The written count is checked on 提示词库.
- **可改变性低占比** is the share of the Topic's Prompts whose 可改变性 is 低, written by script after the trial; blank before it.
- **No 来源属性 column** (Suda 2026-10-28): which attributes a Topic covers is read from its rows' 属性关联.
- Topics are ours to name and split — the brand party does not know what to write there, so 业务范围 carries no 主题 rows (Suda 2026-10-15).

Competitors are 竞品（n） rows in 业务范围 carrying 适用产品线, not 适用主题; no separate competitor table, since nothing links to it.

**Dashboard 「覆盖分布」 (Suda 2026-10-15).** The template carries one dashboard, so every copy has it: a short how-to-read text block; 提示词总数 and 已批准提示词 cards; 切片覆盖情况 (ring on 覆盖情况); 按旅程阶段 and 按受众 (sum of 目标题数 on 提示词矩阵), 按优先级 (count on 提示词库); **按主题 × 优先级** (count on 提示词库, grouped by the hidden helper 主题排序 then 优先级, ascending — Suda 2026-10-23, replacing the plain 按主题 count; a link or lookup field cannot carry the recommended order, a 「推荐顺序 + 主题名」 text formula can, tested on a scratch Base 2026-10-27) and 按提示词类型 (count on 提示词库). 按主题 × 优先级 is where the brand party reads why one Topic is recommended before another; see 主题表 → 推荐顺序. 库分层 is not charted (Suda 2026-10-15). Distributions sum 目标题数, which is filled before Prompts are written, so the plan's gaps show before review — an empty stage, a main audience or product line at zero. Read it before sending the Base and before the trial; it replaces no check in the validator.

**Several markets in one Base (Suda 2026-10-19, Nbrand 韩国 + 台湾).** A multi-market engagement gets one Base, not one per market; every table carries a 市场 select placed right after the primary field. What is shared across markets is written once; what differs gets one row per market:

- 业务范围 has one 市场与语言（n） row per market. Rows that hold for every market (brand, business model, audiences, differentiators…) are written once with all markets selected; rows whose content differs (official site path, local terminology, regulation, aliases, competitors) get one row per market under the same 项目 name, placed next to each other. 需要品牌方提供的数据 and 品牌事实核查 follow the same rule.
- **提示词库 merges by intent and language** (Suda 2026-10-19). One row is one wording. When several markets share the intent **and the language** (US + UK in English, Singapore + Malaysia in English), the Prompt is one row with all those markets selected in 市场 — reuse identical wording only after the coverage pass found the buyer decision and expected answer set equivalent (SKILL.md → *Review the market, then decide reuse*). When the intent is shared but the **language differs** (Korean in Korea, Traditional Chinese in Taiwan), write one row per language: a row holding two wordings breaks 状态 (each market's reviewer approves or asks for a rewrite of its own wording; each market picks its own ≤10 formal Prompts per Topic), the crawler upload (one wording per row) and the per-Prompt readings in the baseline report. Do not add a pairing column to the Base (a 共有意图 field was tried and dropped 2026-10-20): the language versions of one intent already link to the same 提示词矩阵 slice and carry the same 中文含义, and the brand party reviews one market at a time. The pairing lives in the bank JSON as a shared `intent_key` with `market_decision` `localized`, which is what cross-market analysis reads. Write the language versions next to each other (Topic, then intent, then market) and leave the main view unsorted so they stay adjacent; per-market views sort by 编号. A same-language row shared by several markets still gets per-market baseline readings (one baseline report per market: `build_baseline_html.py` reads one `region` per run); if the markets later need different wording or one market retires it, split it into per-market rows.
- **提示词矩阵 is shared across markets.** A slice records the Topic, who, at which stage, which attributes matter and its priority; none of that depends on the language. A slice is one row with 市场 = every market whose Prompts link to it, and 目标题数 counts the linked per-market Prompts. So 市场 is multi-select on 业务范围, 需要品牌方提供的数据, 品牌事实核查, 提示词矩阵 and 提示词库.
- When a slice's priority differs by market, split it into one row per market. When an attribute's 相对竞品 differs by market (Nbrand: 本地语言 is 优势 in Korea, 持平 in Taiwan), split the 属性池 row by market (「本地语言（韩文）」/「本地语言（繁体中文）」). 主题 is one row per Topic × market already.
- 买家原话 is single-select: a quote comes from one market.
- Prefix the market code on IDs that belong to one market (quotes `KR-R001`, question IDs `AN-KR-T1-D01`) so they stay unique in one table; slice IDs stay plain `M-001`.
- Add one filtered grid view per market (named after the market, filter 市场 contains it) on 买家原话, 提示词矩阵 and 提示词库; the brand party reviews a market by switching views. The dashboard counts all markets together — filter it by 市场 before reading a market's coverage.
- Measurement stays per market: the bank JSON, validator run, version and baseline remain one per market (see output-contract.md → *Market Coverage and Localization*); compare the language versions of one intent (same `intent_key`) side by side, never average them.

Customer-facing names: call the Prompts **提示词** (tables 提示词矩阵 / 提示词库, field 提示词); keep **主题** for Topics. Suda reversed the 2026-08 ban on 「提示词」 on 2026-10-14. Use one term throughout the Base and the 使用说明.

### 属性池

One row is **one attribute**: a point the brand wants AI to associate with it **and** buyers actually use when choosing (Profound AEO Guide ch2: "The specific, buyer-relevant things you want your brand to be known for in AI answers", https://www.tryprofound.com/aeo-guide/chapter-2 ). Collect both sides — brand-side (selling points, differentiators, positioning) and buyer-side (what buyers weigh and the brand cannot lose on: price, after-sales, transaction and post-purchase factors) — and keep what buyers actually use. It is the only place an attribute is maintained; 提示词矩阵 links to it through 属性关联.

Columns, in view order: `属性（主字段） | 相对竞品 | 类别 | 判据与证据 | 还缺什么 | 产品线 | 属性编号`. The default view groups by 类别. **No 优先级, 重要性 or 可改变性 here, and no conflict formula** (Suda 2026-10-28): how much an attribute matters depends on the situation, so it is judged on the matrix row that lists it; whether content can move AI's answer is judged per Prompt from the trial's cited domains (see *提示词库* → 可改变性).

- 属性名 is the primary field and the link target: the matrix's 属性关联 cell displays it. Keep one wording per attribute — never a long form here and a short form there.
- 属性编号 (A-001, A-002…) is filled once when the pool is created and stays stable across rewrites; nothing links by it, so it is a label, not a key.
- 产品线 is kept even when the engagement has one line, because later cycles add lines: one attribute can belong to several lines, and the matrix narrows it to the situation.
- 类别 is the twelve-class sweep label (产品特性 / 购买标准 / 差异化优势 / 信任与合规 / 品类 / 限制与边界 / 地理与市场 / 使用场景 …), so the sweep can be checked for holes. There is no audience class and no stand-in row for no-condition category Prompts (Suda 2026-10-28): whether an audience matters is the 主要受众（优先） mark in 业务范围, read when a matrix row's priority is judged; a no-condition category Prompt sits on a matrix row with an empty 属性关联.
- **相对竞品** (优势 / 持平 / 劣势 / 待确认) is the one judgement made here: the brand's **real position in the industry**, not whether the facts happen to be published. Compare against the 竞品 rows in 业务范围 for that product line and market; when an attribute's real rivals are not on that list (Nbrand 钱包体检: Revoke.cash, GoPlus), name them in 判据与证据; when the position differs by market, split the row by market. Run the public layer yourself first — the answer layer (open the page AI actually cites), competitor pages, third-party material — and ask the brand party only for what the public layer cannot settle; absence on both sides is not 持平. 待确认 names what is still missing.
- **Every judgement is written down with its basis** (Suda 2026-10-23). 判据与证据 opens with `相对竞品（持平）：<compared with whom, on what fact>`, e.g. 「持平：与 X、Y 比，三家都支持 Z」. A judgement with no basis line is not made: leave the cell blank rather than fill it from impression. `scripts/check_client_base.py` fails a filled 相对竞品 with no matching labelled line (lines labelled 重要性 or 可改变性 left from older Bases are ignored).
- **Listed or not replaces 重要性.** An attribute is either listed on matrix rows or it is not; there is no 不出题原因 column (Suda 2026-10-28). An attribute no row lists shows an empty reverse link; when the reason is not obvious, add one sentence to 判据与证据.
  - **劣势 is never listed** (Suda 2026-10-28): content cannot move what the brand genuinely lacks, whether buyers use the attribute to eliminate or only to compare. Before judging 劣势, look for a remedy channel (foundation year, bridging course, quota…): public layer first (site, blog, subdomains, what AI answers mention), then the brand party for gate, language, credential or channel weaknesses — UNI_A's foundation year was not on its site.
  - **待确认 is listed**; the matrix row resting on it caps at P2. Re-judge after the trial: read the answers and open the cited pages to check what they say about the rivals; if still unsettled, ask in 还缺什么. The trial shows AI's view of the brand; the real position still rests on facts.
  - **A category threshold is not listed** (Suda 2026-10-23, Nbrand 「不承诺收益」). When every legitimate option already meets it (no return promises, basic compliance, a free tier), buyers do not choose between legitimate options on it; route the buyer worry to the attribute that does decide (here 可信度 — buyers ask 「是不是诈骗」, not 「哪个不承诺收益」). Keep the row so the reason stays visible.
- **还缺什么** stays in this column (Suda 2026-10-28): only what the brand party alone can answer and that decides whether an attribute is listed or how it is judged — an unsettled 相对竞品, whether a business or capability exists at all, whether a remedy channel exists. Point the brand party to it (filter non-empty); do not copy the questions into other tables. Material for content work and the standard answer an Accuracy Prompt needs are asked for after the baseline. Do not ask for anything their site or app already shows — check it ourselves. Hbrand went from 35 rows to 9 on this rule (Suda 2026-10-20); deferred items are kept in the engagement's `_evidence/` folder, not in the Base.
- **Sweep the journey stages once the pool is drafted**: for each stage — transaction and post-purchase especially — check that no attribute buyers weigh there is missing (Nbrand had almost none for those two stages). It does not depend on the conversion path.
- **Concrete values are not attributes**: 预算 and 地形 are attributes (价格与性价比、动力与爬坡); 「1000 镑以内」「通勤有长坡」 are values that appear only in Prompts, taken from the 约束 of 买家原话.
- 相对竞品 also decides whether a selling point may be worded as a differentiator, whether a Verification Prompt may be planned, and, inside one tier and one prompt type, that 优势 Prompts go before 持平.

### 提示词矩阵

One row is **one buying situation**: 主题 × 产品线 × 受众 × 市场 × 旅程阶段, listing the attributes that matter there (Suda 2026-10-28; Aleyda's matrix row likewise lists several factors in its constraint column, and her template's second column is Product / Topic). It is our working table — the brand party may read it, it does not have to — and **the only place priority is judged**. 提示词库 takes its 主题, its default 优先级 and the attribute choice from the row.

Columns, in view order:

`切片编号（主字段） | 市场 | 主题 | 产品线 | 受众 | 旅程阶段 | 属性关联 | 优先级 | 优先级依据 | 目标题数 | 覆盖情况 | 已有问题 | 备注`

The default view groups by 主题. Without several markets the 市场 column is absent.

- **The skeleton comes first, top-down** (Suda 2026-10-22): write out 产品线 × 受众 × 市场 × 旅程阶段 from 业务范围, open only the cells worth testing (never the full Cartesian product), and close the rest with a reason in the internal handoff — `scripts/check_matrix_coverage.py` lists open cells. 主题 is filled after the rows are prioritised (see *主题表*); a row serving two Topics is split into two, keeping its priority unless the basis differs.
- **切片编号** is the primary field: plain text M-001, M-002… in order (a text field, not a formula), also when several markets share the Base.
- **主题** links 主题表 (one Topic per row).
- **属性关联** links 属性池 and lists **the important attributes of this situation** — the ones buyers here use to drop or seriously compare options; it may hold several. A no-condition category row leaves it empty. Listing an attribute on a row is the per-situation importance judgement; there is no separate column for it.
- **优先级** (P1 / P2 / P3) is judged here, once, from two things, both written in **优先级依据**:
  1. **业务重点**: the row's product line is the priority line, and any of: its audience is a priority (marked 优先 in 业务范围, or named by a 业务目标); it matches one of the brand party's 核心可见度问题; it matches a situation a 业务目标 or 营销活动 names. The conversion path is not read here.
  2. **买家证据强弱**: 强 when at least two independent source types recur (买家原话 from community or reviews, search data, brand first-party data); 弱 with one. A 核心可见度问题 counts as business focus, never as buyer evidence.

  | | 证据强 | 证据弱 |
  |---|---|---|
  | 业务重点 | P1 | P2 |
  | 非重点 | P2 | P3 |

  - **旅程阶段 cap**: 发现 / 评估 / 对比 / 替代方案 / 验证 may reach P1; 交易, 购后支持 and 解决问题 cap at P2 unless the row matches a 核心可见度问题 (Aleyda's example rows grade discovery, evaluation, comparison and validation high, transaction and support medium).
  - A row resting mainly on 待确认 attributes caps at P2.
  - **P3 rows get no Prompts this period**: keep the row, leave 目标题数 blank, open 备注 with the reason. A P3 on 提示词库 only comes from a trial drop.
  - Self-check: the P1 rows' 目标题数 should roughly match the formal slots (at most 10 per purchased Topic); far more means P1 was judged too wide.
  - 优先级依据 states both judgements in one or two short lines; `write_prompt_reasons.py` carries it into each Prompt's 出题原因, because the brand party may never open the matrix. A brand-party phrasing may be recorded here to show why the row was opened; Prompt wording still comes from buyer quotes.
- **目标题数 / 覆盖情况**: we fill 目标题数 **before writing Prompts** — our internal plan, which shows before writing whether each Topic reaches five. 目标题数 = the number of clearly different decision needs in the row; decision difference, not phrasing count (Suda 2026-10-28):

  | 条件 | 目标题数 |
  |---|---|
  | 不属于本期监测范围 | 留空（不写 0），原因写在备注开头 |
  | 重要且独立的决策场景 | 1 |
  | 存在两种明显不同的决策需求 | 2 |
  | 存在三种以上重要且独立的决策需求 | 3 及以上 |

  A decision need differs by attribute (quiet comfort vs salt-spray resistance on one hotel-lift row) or by a value of one attribute that would change the candidate list (two cats vs four or more); 「酒店适合什么电梯」 and 「酒店电梯怎么选」 are one need. Pick values from the 约束 of the row's attributes' buyer quotes: group values that would yield the same candidate list and take, per group, the most frequent one closest to the brand's target buyer; a group with one quote, no search volume and no tie to the target buyer gets no Prompt. When above 1, name each need in 备注 with keywords (「① 安静舒适 ② 耐盐雾」「① 不限只数 ② 4 只以上」). 覆盖情况 is a single formula that counts the linked Prompts whose 状态 is 已批准 or 正式 and compares them with 目标题数 (已覆盖 / 未达标 / 不配题 for blank).
- **受众** is a multi-select with the same option set as 买家原话. Tick several only when the row's priority holds for each; otherwise split the row. Use only real buyer groups; a journey state is not an audience. Rows with no narrower group take the category's base audience — such as 「养猫家庭」 — never 「通用」 and never blank (Suda 2026-10-15).
- **旅程阶段** uses the eight stages below; there is no separate 买家任务 column.
- **Removed 2026-10-28**: the 约束 column (concrete values live in Prompts, planned needs in 备注) and the 可改变性 formula column (changeability is judged per Prompt). No Aleyda nine-type column either (Suda 2026-10-15): her Prompt Type mostly repeats 旅程阶段; how a Prompt is read is 提示词类型 on 提示词库.
- Drop: formula-built slice IDs, a 市场与语言 text column (the 市场 select carries the market), 客户确认 (the brand party edits cells directly — see *How the brand party reviews*), and any column whose every row holds the same value.

### 旅程阶段：八段，三张表同一套

`发现 | 解决问题 | 评估 | 对比 | 替代方案 | 验证 | 交易 | 购后支持`

提示词类型也用「验证」「评估」两个词，含义不同（类型验证＝AI 认不认这个能力，阶段验证＝买家在查可信度与事实；类型评价＝要 AI 对具名品牌下判断，阶段评估＝买家在判断具名选项合不合适）。在《使用说明》里用一句话讲清这组重名；允许的组合见 shared/canonical-intent-mapping.md → 提示词类型 × 旅程阶段，validator 按它硬校验。

Use one stage column in 提示词矩阵, 提示词库 and 买家原话. Judge each stage by what the buyer is doing:

| 旅程阶段 | The buyer is | Example |
|---|---|---|
| 发现 | looking for candidates or learning how to choose, no brand settled | 「Which automatic litter boxes work for a small apartment?」「What should I look for in an automatic litter box for multiple cats?」 |
| 解决问题 | starting from a problem, looking for what fixes it | 「The waste drawer smells before it's full — which litter boxes seal odor best?」 |
| 评估 | judging whether one named brand or model fits them or is worth buying | 「Is the Pbrand Purobot Max Pro 2 worth it for three cats?」「What are the most common problems with Pbrand litter boxes?」 |
| 对比 | choosing between two or more named options | 「Pbrand vs Litter-Robot: which is better for multiple cats?」 |
| 替代方案 | looking beyond a named option | 「What are the best alternatives to Litter-Robot?」 |
| 验证 | checking one specific capability, term or fact of a named brand | 「Do Pbrand litter boxes need a paid subscription?」「Can the Purobot Crystal Duo take a Maine Coon?」 |
| 交易 | deciding where, when and on what terms to buy | 「Which automatic litter boxes are on sale right now?」 |
| 购后支持 | already owns it: setup, returns, warranty, troubleshooting | 「Why did my Pbrand fountain pump stop working?」 |

评估 asks for a judgement (fit, worth, weaknesses); 验证 asks for one checkable answer. When unsure, ask whether the reply can be marked right or wrong against an official source — if yes, it is 验证. Aleyda's shortlist step folds into 发现, and category understanding (how to choose, what to look for) is 发现 with 意图 品类认知; source discovery is not used for after-sales banks. The older five-stage labels map as 了解需求→发现, 比较方案→对比, 评估是否适合→评估, 准备购买→交易, 使用与续费→购后支持, but re-judge each quote by its content when converting: a 「how do I get rid of the smell」 post is 解决问题, a filtering condition such as 「must be stainless steel」 is 发现, a 「does it have a hidden monthly fee」 check is 验证. A row with no Prompt still gets a judged stage — never leave it blank.

### 买家原话

`原话（主字段） | 中文意思 | 涉及品牌 | 来源类型 | 受众 | 旅程阶段 | 约束 | 来源说明 | 来源链接 | 收集日期 | 证据可信度 | 引用它的问题 | 产品线 | 输入编号 | 月搜索量` (with several markets: 市场 right after 原话). The default view groups by 旅程阶段.

- **月搜索量** (single-select) is the target market's monthly volume tier for 搜索数据 rows (DataForSEO / Google Ads volume via `shared/scripts/collect_keyword_data.py`, or a client's Ahrefs, Semrush or Similarweb export: >10,000 / >1000 / >100 / <100; Korea uses Naver keyword-tool volume in the same tiers — see signal-sources.md 关键词工具 row). Google 自动补全 rows carry no volume — leave the cell blank. Keep the tier out of 来源说明, which already states the tool and market; the column exists so the brand party can sort and filter by demand size.

- **Primary fields are chosen for what a link cell shows** (Suda 2026-10-15). A linked cell displays the other table's primary field, so: 买家原话 leads with **原话**, and 提示词库's 证据 cell shows the quote itself, letting the brand party judge a Prompt's grounding without leaving the row; 提示词库 leads with **提示词**, so 提示词矩阵's 已有问题 lists the actual questions; 提示词矩阵 keeps **切片编号**, because no content column identifies a slice — Pbrand's 120 rows had 3 product lines, 52 attributes of which 25 repeat, and 17 repeated 属性 + 受众 + 旅程阶段 combinations. When the brand party reads only Chinese, lead 买家原话 with 中文意思 instead.
- **输入编号** stays near the end, before 月搜索量. Our bank JSON's `evidence_refs` and `config.audience_inputs` cite it, and both sides use it to point at one quote in feedback.

- **涉及品牌** (multi-select) names the brand the quote is about; generic buying posts and search terms are 「未指明品牌」. A subreddit name is not a brand mention.
- **来源类型** is the real source — 社区 / 评价 / 搜索数据 (later 销售记录、客服记录、GSC、站内搜索 when the brand party supplies them). Never 「竞品评价」: whose product it is goes in 涉及品牌.
- **受众** uses the same multi-select set as 提示词矩阵; who the poster owns (「Pbrand 用户」「LR 用户」) is not an audience.
- Marketplace summary tags (Amazon 「Customers say」) keep only the tag text in 原话, the product name in 来源说明, and a 中文意思 that names the brand.

### 提示词库

`提示词（主字段） | 中文含义 | 提示词类型 | 状态 | 主题 | 所属切片 | 优先级 | 出题原因 | 证据 | 产品线`, default view grouped by 主题 (with several markets: 市场 right after 提示词, see *Several markets in one Base*); 编号, 属性, 可改变性, AI 认知差距, 优化顺序, 库分层, 看什么指标 and 主题排序 exist but are hidden in the default view. 库分层 stays hidden until the formal set is chosen — during the candidate stage nearly every Prompt is 核心 (Suda 2026-10-19). This is the one table the brand party always reads.

- **主题** is a lookup from 所属切片 (Suda 2026-10-28), never typed: renaming a Topic in 主题表 renames it here. **主题排序** is a hidden text formula 「推荐顺序 + 主题名」 used only to order the dashboard's 按主题 × 优先级 chart.
- **属性** links 属性池: the one attribute this Prompt tests, chosen from its slice's 属性关联. A no-condition category Prompt (written only when the brand party asks for the head term, Suda 2026-10-29) leaves it blank and its 出题原因 says 「测品类整体格局」; `check_client_base.py` lets such Prompts pass.
- **优先级** is an editable single-select (Suda 2026-10-28; no formula and no 建议优先级 column). `write_prompt_reasons.py` prefills it from the slice's 优先级, one tier lower when the Prompt's 可改变性 is 低; the prefilled value is the recommendation. Anyone may change it — the brand party included — and a changed Prompt's 出题原因 ends 「改档：理由，定为 Px」; `check_client_base.py` recomputes the default and fails a difference with no such line. The judgement itself stays on the slice: a hand change is a recorded exception for one Prompt. **The brand's own reading never moves the tier** (Suda 2026-10-23): 已打平或领先 / 部分出现仍落后 / 竞品领先 are recorded and shown, but none of them drops a tier — a Prompt the brand already wins is still worth monitoring, and choosing by the brand's own result would bias the baseline.
- **可改变性** (高 / 中 / 低 / 待试跑, default 待试跑; renamed from 信源壁垒 on 2026-10-28, Suda) says whether content can change this Prompt's answer. It is the only changeability judgement in the flow, made from the trial: take the top 20 domains by citation count in this Prompt's trial answers (正文引用 only, not retrieval candidates; undeduplicated counts) and put each in one of three tiers —

  | 档 | 包括 |
  |---|---|
  | 官网 | the brand's site, subdomains and blog; pages the brand edits on its 转化路径 channel (Amazon store and product pages, App Store page, own e-commerce store); competitor official sites too — AI citing them shows it takes vendor pages for this question, so a brand page with the same content can be cited |
  | 社区 | text communities where the brand party posts from its own account with content we provide (Reddit, LinkedIn) |
  | 难影响 | third-party reviews, media, rankings, review platforms, government and regulators, communities the brand party does not post in, video platforms such as YouTube — not covered by our service unless the client buys a source service, which moves that class to 社区; a platform the brand party will not post on counts here |

  No fixed threshold: mostly 官网 + 社区 → 高, mostly 难影响 → 低, about even → 中. A fact the brand already publishes but AI cannot read (JS-rendered numbers, image-only specs) → 高, recorded as a content to-do. The basis lists the top 20 domains by tier and the shares of brand site, competitor sites and community (bank JSON `changeability_basis`; the older `source_barrier_basis` is read as an alias). Not judged here: whether the brand has the capability (劣势 attributes are never listed), retrieval vs memory (the monitored platforms search), and whether sources have already formed a consensus (that shows only after content is published and is re-judged after the baseline). Each client's community platforms and bought source services are written in one 业务范围 row.
- **提示词类型** (single select: 发现 / 对比 / 替代 / 评价 / 验证 / 准确性 / 品类认知 / 问题解决; 问题解决 and 替代 are after-sales only — 问题解决 Suda 2026-10-19 (client label renamed from 信息 and scope narrowed to problem-solving on 2026-10-26), 替代 split out 2026-10-22; the 对比 label was 竞品对比/竞品 before 2026-10-23, and the field was renamed from 意图 on 2026-10-22) is the bank JSON's `prompt_type` shown in Chinese, using the names in shared/canonical-intent-mapping.md; the two are one field, never two vocabularies (Suda 2026-10-15). It decides which metric a Prompt feeds (see after-sales-rules.md → *Prompt Priorities*). We fill it; the brand party does not edit it. **看什么指标** (Suda 2026-10-23) is a read-only formula, `SWITCH([提示词类型],"发现","提及率（计入考核指标）…",…)`, that shows the brand party in plain words what each type is read for — 发现: 提及率, the only KPI; 对比: 胜率; 替代: 提及率 in the alternatives list (the column does not say whether it counts toward the KPI — undecided, Suda 2026-10-23); 评价: AI's verdict and reasons; 验证: whether AI knows the capability; 准确性: whether the fact is right; 品类认知: whether the buying criteria include the brand's strengths; 问题解决: site citation only, no mention rate (Suda 2026-10-23) — the other non-Discovery lines end 「不计入提及率」. It is a formula, not a hand-filled 分析类型 column, so it cannot drift from 提示词类型. It names no sentiment reading (not sold to clients since 2026-10-21).

- **状态** (待审核 / 需修改 / 已批准 / 正式, default 待审核; 停测 was dropped from the Base 2026-10-23 — a stopped Prompt is deleted, see *The Base holds only Prompts under test*) is one column for the whole life of a Prompt (Suda 2026-10-19 merged the former 审核状态 and 状态, which looked duplicated because one only mattered before the baseline and the other only after): we mark 待审核 after internal QA; the brand party marks 已批准 when the Prompt is fine or after editing it directly, 需修改 when it wants us to rewrite. **Only 已批准 Prompts enter the formal selection.** At lock — when the brand party confirms the formal set, before the formal baseline runs — the selected Prompts move to 正式 and every other candidate is deleted from the Base, its ID and reason recorded in `config.retired` (Suda 2026-10-23: 正式 means "in the formal set", so monitoring knows what to collect; it no longer waits for the baseline to finish). 覆盖情况 on 提示词矩阵 counts 已批准 and 正式, and so does the dashboard's 已批准提示词 card.
- **出题原因 is a text field written by our script, one per Prompt** (Suda 2026-10-23, Nbrand). The brand party may read nothing but 提示词库, so one paragraph answers 「为什么出这道题」 and 「为什么是这个优先级」, in three parts: **what this Prompt tests** (which buyer, at which stage, which decision need from the slice's 备注, and what is read — whether AI lists the brand, whom it picks, whether it cites the site); **the evidence** (how many linked 买家原话 by source type and site, plus one representative quote, highest-credibility community or review quote first); **why this tier** (the slice's 优先级依据 in plain words — whether the situation is a business focus and how strong the buyer evidence is — then, after the trial, the 可改变性 drop when it applies; it ends 「所以是 P1」). A no-condition category Prompt says it measures whom AI recommends unconditioned (「测品类整体格局」). Text, not a formula: a formula can only assemble generic grade meanings, so every Prompt in one slice would read the same (Nbrand: eight identical lines). The script is `scripts/write_prompt_reasons.py --base <token> --brand <题面里的品牌名> --noun <品类名词>` (preview by default, `--write` writes and reads back; `--from-dump` previews offline). It reads the slice's 优先级 and 优先级依据, prefills 优先级 only where blank, keeps a hand change's 「改档」 line, and stops on a slice with no 优先级 or a Prompt type it has no sentence for. Wording is the brand party's language — 「买家挑工具时会因为它直接排除一个选项」, not 「证据强」. The 证据 link stays: the reason is its summary, the link is the quotes themselves.
- **AI 认知差距** (知道但不推荐 / 不知道该能力 / 无人讨论 / 无缺口 / 待试跑): an initial reading from the trial, marked 「试跑初判」 in its basis, final after the formal baseline (Suda 2026-10-28). It orders content work only and **never changes the tier**. Judge it per Prompt from that Prompt's own answer text; a paired Verification Prompt on the same attribute tells 知道但不推荐 from 不知道该能力 (after-sales-rules *Prompt Priorities*). Metric readings (提及率 and the rest) never go into 提示词库 — they live in the HTML report. Never push an attribute-level judgement or presales answers onto individual Prompts.
- **优化顺序 is a text column filled after each formal baseline** (Suda 2026-10-26): the order the baseline report computes (tier → competition pattern → 相对竞品, see `geo-monitoring` → baseline-report.md → *优化顺序*) is written back per Prompt as 「第 N 档（P1 · 竞品领先 · 优势）」, one line per market when the row spans markets; blank until the formal baseline has run. It orders optimisation work only — it never rewrites 优先级.
- **Default view of 提示词库 shows only what the brand party decides with** (Suda 2026-10-23): 提示词 / 中文含义 / 市场 / 主题 / 提示词类型 / 优先级 / 出题原因 / 状态 / 证据. 编号, 所属切片, 属性, 可改变性, 看什么指标, 库分层, AI 认知差距, 优化顺序, 主题排序 and 产品线 stay in the table but are hidden; 看什么指标 and 可改变性 are explained once in 使用说明.
- **No hand-filled slice-level columns on 提示词库.** 受众, 旅程阶段 and 约束 belong to the slice; a typed second copy drifts. 主题 is a lookup, not a copy. The bank JSON keeps `journey_stage` for metrics and the validator.
- The main view is grouped by 主题 and not sorted, so the language versions of one intent stay adjacent; per-market views sort by 编号.
- **主题 names describe what the Topic holds.** A Topic whose Prompts span cost, reliability and upkeep is named for all three.
- **The formal set is a view, not a table.** 提示词库 has a 「正式监测」 view filtered to 状态 = 正式. Do not copy formal Prompts into another table: two copies of one wording drift.

### 基线报告（HTML） (Suda 2026-10-21)

Baseline results are not written into the Base; they go to the brand party as one HTML file. Workflow, config, page layout and display rules: [baseline-report.md](../../geo-monitoring/references/baseline-report.md).

### 品牌事实核查 (Suda 2026-10-16)

`事实项（主字段） | 产品线 | 官方值 | 来源页面 | 冲突说法 | 冲突来源 | 品牌方要做什么`

One row is one fact that is **either self-contradictory on the official site or asserted without external support**. Filled during the same research pass that judges `相对竞品` — the attribute-pool research already opens the product, spec, warranty and FAQ pages, so the conflicts surface there. Sits next to 业务范围 in the Base: 业务范围 is the fact layer the brand party checks, this is the fact layer they must fix.

- **Official-site facts the public layer can settle never appear here** — they go into 业务范围 as settled fact. This table holds only what is wrong, contradictory, or unsupported.
- **来源页面 / 冲突来源 hold full URLs** (Suda 2026-10-16). When the conflict is inside one page, write the same URL in both, or name the block (`同页面 FAQ 区块`) in 冲突来源 when the URL would be identical. No URL, no row.
- **品牌方要做什么** is our call, single-select, and states the action, not the verdict:
  - **改官网** — the conflict is entirely inside the brand party's own channels (same page, page vs FAQ, site vs App / support). The brand party unifies the wording.
  - **提供材料** — the claim has no support we can verify: no third-party test, test conditions undisclosed, or contradicted by an outside source. The brand party supplies the evidence.
- **Do not add a 证据等级 or 内容使用限制 column** (Suda 2026-10-16): the tier is already implied — a 冲突说法 present means the evidence is not clean, and whether a claim may be written as fact follows from whether 品牌方要做什么 is 改官网 or 提供材料.
- **This is where the Accuracy gate's research lands.** For each factual attribute listed on a P1 or P2 slice, the public-layer and answer-layer checks the intent rules describe are recorded here rather than only in an attribute 备注. A row becomes an Accuracy Prompt only through the accuracy gate (the client has confirmed the correct value with an official source and a wrong answer changes the purchase) — most rows stay 改官网 / 提供材料 and never become Prompts.

### How the brand party reviews

The brand party edits cells directly — wrong fact: change the cell; missing: add a row. There is no 客户确认 column (Suda 2026-10-15). Before sending, snapshot every table (and deploy later changes incrementally, checked with `python3 scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` — see *IDs freeze* above); when collecting, compare against the snapshot and `lark-cli base +record-history-list` to see each change, and review every edit to 相对竞品 (属性池 — it decides whether an attribute is listed) and to 优先级 (提示词库 — a change needs its 「改档」 line). Filter 属性池 还缺什么 non-empty to find the must-answer cells.

### Facts we can verify ourselves

Settle what the public layer can settle before asking the brand party — for example whether a model is still sold: check the official site's product pages, redirects and search, then the main marketplace, and write the result into 业务范围 as a settled fact, not a question. Ask the brand party only for what only it knows.

## Canonical Shape

The sections below define the content. In the Base they live as: 品牌事实 → 业务范围, 属性池 → the 属性池 table (linked from 提示词矩阵), 主题 → the 主题 table, 问题 → 提示词库. Where a section below conflicts with *Settled table set*, the table set wins. Use the sections that fit the task; do not force all of them into a small update.

1. **Opening scope paragraph**
   - State the monitoring object, product/category scope, market/language, and entry scenario.
   - Ask the brand party to confirm, in 提示词库, whether each Prompt matches a real buying situation and whether its tier makes sense; 属性池 (whether the brand is advantaged / at parity / weak) and 主题 are optional reading, with the questions we need answered in 属性池 还缺什么.
   - Explain the confirmation convention: in the Base the brand party edits cells directly and marks 状态 on 提示词库 (no 客户确认 column); document-format pieces keep a `客户确认` column, write-what-to-change, blank meaning reviewed with no change.
   - **State where our data came from**, in two or three plain sentences, so the brand party can judge the evidence instead of taking the table on trust: which public sources we collected (搜索需求与相关搜索、哪些评价平台、哪些社区——写实际用到的站点名，不写方法论), which of the brand party's own materials we used (销售/客服记录、GSC 等——只列用过的), and which AI answers were already collected (售前诊断或试跑，带采集时间). Name only sources actually used in this engagement — the full menu stays internal in [signal-sources.md](signal-sources.md). One line of boundary: 公开来源查不到的，已在表中标为「待确认」或「需品牌方提供」，不会当成品牌方没有。

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
   | 在这个处境里重不重要 | 这条不解决，买家会不会不入围、不购买、不续费、退货或要求补证据 | 买家公开选购理由、放弃理由、搜索规模、媒体评测维度、竞品主推方向 |
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

   Facts that are self-contradictory or unsupported do **not** go here — they go to the 品牌事实核查 表格 (Base) or a following `事实项 | 官方值 | 来源页面 | 冲突说法 | 冲突来源 | 品牌方要做什么` section in document format (see *品牌事实核查*).

4. **属性池【请核对】**

   In the Base these live in the 属性池 table (see *属性池* above); 提示词矩阵 links to it through 属性关联. The lists below define what each column means. For a document-format pool, default columns:

   `类别 | 属性 | 解决的买家问题 | 相对竞品 | 还缺什么 | 备注 | 客户确认`

   Use a compact variant when evidence is simple:

   `类型 | 属性 | 解决的买家问题 | 相对竞品 | 品牌方补充与确认`

   Column semantics:
   - `类别/类型`: readable grouping such as 品类、目标客户画像、痛点、使用场景、购买标准、产品能力、差异化、信任与合规、申请门槛、地域与市场、约束.
   - `属性`: the buyer decision focus AI should associate with the brand. Differentiators are rows in this table, not a separate section, Topic, or Tag.
   - `解决的买家问题`: plain buyer problem or selection risk. Keep it close to customer language.
   - `相对竞品`: the attribute's **real position in the industry** — 优势 / 持平 / 劣势 / 待确认. Judge it on the facts, not on whether they happen to be published (publication is the **gap type**, a separate axis). Compare against the leaders publicly **first**; where the public layer cannot settle it — the brand's own spec or internal capability — put the question to the client rather than guessing. Add a short evidence note.
   - `还缺什么`: specific material needed from the brand party; omit or leave blank when no material is needed.
   - `备注`: evidence and caveats we found. Keep it factual and short. For factual attributes, also note where public sources conflict or AI answers state the fact wrongly or outdatedly (quote the wrong claim and its platform), so the brand party can confirm the right answer.
   - `客户确认`: write-what-to-change only.

   For multi-market work, add the market only when it changes the buyer
   decision or evidence context. Use the existing `类别/类型` and
   `市场/语言` facts, attribute, constraint, competitor, or Prompt columns;
   do not create one duplicated attribute row for every country merely to
   demonstrate coverage.

5. **Priority Rules**

   Priority is judged once, on the 提示词矩阵 row (*提示词矩阵* → 优先级): business focus × buyer-evidence strength, with the journey-stage cap; a Prompt takes its slice's tier and drops one when its 可改变性 is 低. 属性池 carries no tier.

   Important constraints:
   - 相对竞品 decides whether an attribute is listed at all (劣势 never), not its tier; P1 can coexist with `持平`.
   - P3 rows stay visible on the matrix with the reason in 备注, but get no Prompts this period.
   - `待确认` means the evidence is missing, not that the attribute is weak; its row caps at P2.
   - Once the baseline has measured the current gap, AI 认知差距 and the five competition patterns order optimisation (geo-monitoring baseline-report.md → *优化顺序*). They never rewrite the selection tier.

6. **主题与问题 / 提示词【请核对】**

   Include this section when the customer needs to confirm candidate Prompts, not when the current task is attribute-only.

   Recommended columns:

   `市场 | 主题 | 买家问题（或客户问题与场景） | 监测问题（英文或当地语言） | 中文含义 | 标签/属性 | 客户确认`

   Compact variant:

   `主题 | 买家问题 | 监测问题（英文或当地语言） | 中文含义 | 客户确认`

   Rules:
   - No question numbering in the customer document; crawler numbers are unstable.
   - Discovery-first: first staged set is normally all non-branded Discovery.
   - Keep the buyer problem / customer scenario adjacent to the Prompt, so the brand party can judge whether the wording matches real buying situations.
   - P3 slices get no first-stage Prompts.
   - Each Prompt's buyer problem must exist in the intent/attribute table, and every P1/P2 buyer problem intended for first stage must have at least one Prompt.
   - Topic counts may differ; do not add filler for visual balance.
   - The buyer's job shows to the customer only as the eight-stage 旅程阶段 column; do not add a separate 买家任务 column next to it.

7. **竞品（请确认）**

   In the Base these are 竞品（n） rows in 业务范围. For a document-format piece, add a separate section when competitor scope is unstable or customer-submitted competitors were replaced: `品牌 | 说明 | 客户确认`.

   Explain each inclusion/exclusion by “same buying comparison set,” not by brand fame alone.

8. **需要品牌方提供的数据**

   Include this section whenever the attribute pool is still being built. List only the data the brand party alone can access, using the table in [signal-sources.md](signal-sources.md) → 客户提供什么 (`数据 | 必要性与怎么给 | 品牌方补充与确认`). Mark 销售与 CRM 记录 and 客服记录 as 优先提供 and the platform data as 有就提供 — never 必须给, and a summarised version from the brand party is enough, raw records are not required; do not ask for public search data, reviews or community language — we collect those. Say in one line that personal and customer-company details will be removed before use and raw records stay internal.

9. **试跑、选词与正式基线流程**

   If the document hands off to monitoring, state the staged process in four lines (Suda 2026-10-23):
   1. 品牌方确认业务重点和事实边界（业务范围），回答属性池「还缺什么」里的问题。
   2. 每道候选题在每个监测平台各跑 3 次，检查问法是否准确、回答是否切题、各平台结果是否一致；结果只作参考，不作为数据统计。
   3. 品牌方在提示词库里从候选题中选定正式题（每个采购主题最多 10 条），确认后锁定版本。
   4. 正式题在每个平台、国家和语言下各跑 30 次，作为优化前的基准。

## Wording Rules

- Use `品牌方`, not `贵司` / `贵校`.
- Write the final document directly; do not mention “上一版”, “补充更正”, or internal revision traces.
- Keep methodology, word-frequency work, validation steps, and evidence-position mappings out of the customer document. Archive them internally.
- Mark uncertain claims as `待核`, `待确认`, `待验证`, or `品牌自述`; do not turn trade-press/self-declared claims into facts.
- Avoid merged cells in Feishu tables. Empty cells are safer when rows are inserted or deleted.
- If a number is visible only through JavaScript or non-static page rendering, note the source limitation before treating it as AI-readable evidence.
- The brand party corrects facts and priorities; we make the judgement. Do not ask them to write our reasoning for us (for example, “why buyers credit this advantage”).
