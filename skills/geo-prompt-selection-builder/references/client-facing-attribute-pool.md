# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 某大学海外招生监测属性池, Abrand 台式净饮机售后生词, Bbrand ModelN1 售后主题与词表, and Wbrand 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Format: the Feishu Base template

The client confirmation piece is a Feishu Base copied from the template 《AI 搜索监测确认表（模板）》 in the project wiki space (the template stays in use; the separate 《售后生词规则》 document is retired, see after-sales-rules.md). Copy it once per client — several markets share one copy (see *Several markets in one Base* below) — delete every 【示例】 row, and fill the 使用说明 doc's data-source placeholders with the sources actually used. **The 使用说明 doc is the only client-facing explanation** (Suda 2026-10-15): it carries the service flow, what the brand party provides, platform permissions (GSC 受限 / GA4 查看者 / Bing 只读 — grant access first, export only as fallback), brand-material timing, how to check each table, content review and publishing, and how to read results. Do not send a separate guide document; edit the template's 使用说明 instead. The Base has no 需品牌方确认 checkbox: every table is for the brand party to review, and what we need from them is written in 属性池 还缺什么 (filter it non-empty) or as an 【请补充】 placeholder in 业务范围 (Suda 2026-10-15; moved from the matrix to 属性池 2026-10-20). The sections below still define what each table must contain.

**Settled table set (Pbrand, 2026-10-14/15; 品牌事实核查 added 2026-10-16; 属性池 added 2026-10-20).** Seven confirmation tables plus the 使用说明 doc, in this order. Baseline results are not written into the Base — they are delivered as a single-file HTML report (Suda 2026-10-21; see [baseline-report.md](../../geo-monitoring/references/baseline-report.md)). The 基线读数 / 主题汇总 / 被引来源 tables and their dashboard, added 2026-10-15, were removed from the template and from Hbrand (主题 and 竞品名单 tables were removed 2026-10-15 and folded into 业务范围):

| 表 | 一行是什么 | 要点 |
|---|---|---|
| 业务范围 | 一个可以单独确认的事实 | Replaces 品牌事实. Multi-valued facts get one row each (产品线（1）（2）…, 主要受众（1）…, 买家要完成的任务（1）…, 竞品（1）…, 差异化优势（1）…). **Product lines**: the brand party may list every line it wants; we recommend starting with one, so mark it 产品线（1）（优先） and the rest （后续） — the priority line gets Prompts and monitoring first, the others join in later cycles. This is guidance, not a restriction: keep multi-line support in every table. **Audiences carry a priority mark; the conversion path is written as the priority one** (Suda 2026-10-22, conversion path revised 2026-10-23): 主要受众（1）（优先） names the audience that drives the business — the brand party confirms this, it is their daily sales judgement, we never derive it from evidence volume; 转化路径 is the path visibility should feed first. **The brand party answers two questions, in these words** (Suda 2026-10-23): 「核心业务目标是什么？」 (→ 业务目标 rows) and 「希望用户完成什么关键转化动作？」 (→ 转化路径 rows); the bracketed detail on each row below is ours to pre-fill, not extra questions. 转化路径 is Aleyda's step-1 question, filled in by the brand party in its own industry's terms (a fixed option list does not fit across industries): which action the business wants a buyer to take after AI points them to it — 「直接购买」「提交询盘」「预约 Demo」「注册」「申请试用」, or whatever the industry actually calls it (「预约看房」「申请入学」「加购」「到店」). Write only the priority path, one 转化路径 row, 一句话 in the brand party's wording, with the channel in the same line or 备注 when it matters (Amazon US, 官网表单, App Store); non-priority paths are not listed, because nothing downstream reads them (Prompt allocation reads only the priority one — Suda 2026-10-23). Only when two paths are equally key (a B2B tool that wants both demo bookings and self-serve signups) write two rows, unranked. We pre-fill the candidate from the buttons on the brand's site (Buy on Amazon, Book a demo, Download, Find a store …) and the sales conversation; the row opens with 【请品牌方补充】, and the brand party confirms, corrects or replaces it. No funnel steps and no journey-stage question: as Aleyda puts it, the path decides which journey stages and Topics carry weight (「It decides which journey stages and Topics carry weight」), so the stage weighting is our inference from the priority path plus 业务目标, never a second question. Prompt allocation and Topic weighting read these marks (SKILL step 6), and a skeleton cell left empty for a non-priority audience is closed as 「低业务优先，留到后续周期」 — the brand party's trade-off — which is distinct from 「无买家证据」, our research gap. **业务目标（n） and 营销活动（n）** (Suda 2026-10-23) are the two rows that say what the visibility is for and what the brand is about to push. 业务目标 reads `目标（产品线 / 市场 / 受众；衡量方式）` — what the brand party wants AI visibility to do this service period. The brand party's own answer is one plain sentence — 「提升销售额」「获取有效销售线索」「增加试用用户」 — and we complete the bracket from the sales conversation (which product line, market and audience, and how it is measured), the brand party correcting it; at its most specific it reads like entering the candidate list for one buying situation, carrying a new product line into a new market, or feeding demo requests. 营销活动 reads `活动名（时间；产品线 / 市场）：主推卖点` — launches, big promotions, market entries, PR or creator pushes inside the service window; only the brand party knows these, so the row opens with 【请品牌方补充】. Neither row is buyer evidence and neither licenses a Prompt by itself: a business goal decides which product lines, audiences and Topics get the Prompt count and sets audience 重要性 (see *属性池*); a campaign's 主推卖点 enters 属性池 only as a candidate attribute that still needs buyer evidence, a product not yet launched gets no Discovery Prompt (AI cannot know it; plan a Verification Prompt for after launch), and campaign dates go into the collection plan handed to `geo-monitoring` so the baseline avoids or deliberately brackets them. 买家要完成的任务 gets one row per main audience. 初始题库规模 is filled by us, never by the brand party. Each 竞品（n） row reads `名称（官网域名；适用：产品线）：依据`, with mention-based reasons only — never 首推 or a rank; direct competitors and alternatives are not labelled apart (Suda 2026-10-21: the distinction changes nothing for us), and an alternative with no site writes 「无固定域名」. The domain is required (Suda 2026-10-20): citation counting matches competitor pages by domain. Always include 品牌别名 (abbreviations, local-language names, former names, sub-brands, common misspellings, and similarly named other companies; we pre-fill what AI answers and reviews show, and the row opens with 【请品牌方补充】 because only the brand party knows its Chinese name and internal nicknames — mention counting depends on it). Name it 品牌与产品别名 only when product or model names circulate on their own (Bbrand N1, Pbrand feeder models); a platform whose app name is just the brand plus a descriptor needs no product layer (Hbrand, Suda 2026-10-20) and 差异化优势 rows (the brand party lists its selling points as plain statements; no evidence and no 品牌自述 label are asked for — we judge `相对竞品` ourselves, and evidence is gathered only when content work starts after the baseline, Suda 2026-10-19/20). 核心可见度问题 rows state only the buyer question itself — not 「问 AI」 framing and not what AI should say about the brand (Suda 2026-10-20). No 「已核对」 rows: a fact we verified ourselves is either written here as fact or folded into the matching attribute's 备注 |
| 买家原话 | 一条买家说法 | The evidence log; see *买家原话* below |
| 属性池 | 一条买家决策属性 | The single place an attribute is maintained — 属性名、类别、相对竞品、可改变性、还缺什么、判据与证据、产品线. 提示词矩阵 links to it through 属性关联 and reads only 可改变性 back as a formula; 相对竞品, 还缺什么 and 判据与证据 are read here, so the same judgement is written once (Suda 2026-10-20). See *属性池* below |
| 提示词矩阵 | 一种买家处境下要测的一条属性 | Carries coverage slices and links each one to an 属性池 row; see *提示词矩阵* below |
| 提示词库 | 一道提示词 | Links its 所属切片 (one 提示词矩阵 row) and its 证据 (买家原话 rows) |
| 需要品牌方提供的数据 | 一项只有品牌方能拿到的数据 | Buyer-signal data per [signal-sources.md](signal-sources.md) → 客户提供什么 only — data that changes a Prompt-generation judgement. The content-production rows (官网未公开的产品事实, 品牌规范) were dropped 2026-10-19: they belong to the content stage, not Prompt generation. 即将发生的变化 (new launches, promotions) was dropped with them and came back on 2026-10-23 as 营销活动 rows in 业务范围, not as a data request here. Do not ask for anything the official site already publishes — we extract it into 业务范围 and the brand party only checks it |
| 品牌事实核查 | 一条官网自相矛盾、或只有自述没有外部佐证的事实 | Filled during the same research pass that judges `相对竞品`; see *品牌事实核查* below. Sits next to 业务范围 in the Base — both are the brand-fact layer, this one is the problem list |

**IDs freeze once the Base reaches the brand party** (Suda 2026-10-20). 切片编号 (M-…) and Prompt IDs never change after the first send: new slices and Prompts are appended at the end; a deleted one keeps its ID (or stays as a row with no Prompt); merging Topics does not renumber Prompts. Exceptions and mappings in generation scripts key on stable values — 「属性|约束」 for a slice, `intent_key` for a Prompt — never on the displayed ID. Hbrand drifted three times in one day: a slice inserted mid-table shifted the next 73 IDs, a Topic merge renumbered the Prompts, and an audience exception keyed on a Prompt ID landed on another Prompt (M-071 ended up marked as a buyer).

**After the brand party can see the Base, deploy incrementally only** (Suda 2026-10-20). Never delete a table's rows and rebuild them: append or edit in place so every record_id survives, because link fields (属性关联, 所属切片, 证据) point at record_ids. Run `python3 scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` before and after each deploy; the deploy is done only at zero differences. The script compares the live Base with the spec the generation script writes (`{表名: [行]}`): only fields present in the spec are compared, formula columns are skipped, keys starting with `_` are ignored except `_属性名`, which is resolved through 属性关联 to the pool's 属性; link fields are written `"表名:主键"` and compared by the target's key, never by record_id. Default keys: 提示词矩阵=切片编号, 提示词库=编号, 买家原话=输入编号, 业务范围=项目, 属性池=属性, 需要品牌方提供的数据=数据, 品牌事实核查=事实项 (override with `--key 表名=字段`; rename with `--alias spec字段=线上字段`, default 监测主题=主题; `--tables` limits the run; `--json` saves the detail). URL cells read back as `[文字](链接)` and dates carry a midnight time — both are normalised. Exit code 0 = no difference, 1 = differences, 2 = the Base could not be read (never reported as clean). Run it from the client's directory with the script's absolute path — `python3 -I <项目根>/.agents/skills/geo-prompt-selection-builder/scripts/diff_base_against_spec.py --base <token> --spec <spec.json>`: lark-cli only writes to the working directory, so running it from the skill directory fails with `unsafe output path`; the script deletes its temporary files afterwards. On Hbrand its first run found 14 real drifts (9 in 需要品牌方提供的数据·必要性 still using the retired 必须给 / 最好给 options, 5 matrix 备注). Hbrand's whole-table rebuild replaced record_ids and emptied all 87 属性关联 links, shifted 买家原话 KW-018–032 by three rows, and once wiped every matrix 备注 — each found by hand afterwards.

**No separate 主题 table.** 主题 is a single-select column on 提示词库 only; 提示词矩阵 has no Topic column, because a slice's Topic is whatever its linked Prompts carry and a second hand-filled copy drifts (Suda removed it 2026-10-15); Topics are ours to name and split — the brand party does not know what to write there, so 业务范围 carries no 主题 rows (Suda 2026-10-15); the ≥5 candidate / ≤10 formal counts are checked by filtering 提示词库. A topic table would only duplicate the name and need links kept in sync. Competitors are 竞品（n） rows in 业务范围 carrying 适用产品线, not 适用主题; no separate competitor table, since nothing links to it.

**Dashboard 「覆盖分布」 (Suda 2026-10-15).** The template carries one dashboard, so every copy has it: a short how-to-read text block; 提示词总数 and 已批准提示词 cards; 切片覆盖情况 (ring on 覆盖情况); 按旅程阶段, 按受众 and 按优先级 (sum of 目标题数 on 提示词矩阵); 按主题 and 按提示词类型 (count on 提示词库). 库分层 is not charted (Suda 2026-10-15). Distributions sum 目标题数, which is filled before Prompts are written, so the plan's gaps show before review — an empty stage, a main audience or product line at zero. Read it before sending the Base and before the trial; it replaces no check in the validator.

**Several markets in one Base (Suda 2026-10-19, Nbrand 韩国 + 台湾).** A multi-market engagement gets one Base, not one per market; every table carries a 市场 select placed right after the primary field. What is shared across markets is written once; what differs gets one row per market:

- 业务范围 has one 市场与语言（n） row per market. Rows that hold for every market (brand, business model, audiences, differentiators…) are written once with all markets selected; rows whose content differs (official site path, local terminology, regulation, aliases, competitors) get one row per market under the same 项目 name, placed next to each other. 需要品牌方提供的数据 and 品牌事实核查 follow the same rule.
- **提示词库 merges by intent and language** (Suda 2026-10-19). One row is one wording. When several markets share the intent **and the language** (US + UK in English, Singapore + Malaysia in English), the Prompt is one row with all those markets selected in 市场 — reuse identical wording only after the coverage pass found the buyer decision and expected answer set equivalent (SKILL.md → *Review the market, then decide reuse*). When the intent is shared but the **language differs** (Korean in Korea, Traditional Chinese in Taiwan), write one row per language: a row holding two wordings breaks 状态 (each market's reviewer approves or asks for a rewrite of its own wording; each market picks its own ≤10 formal Prompts per Topic), the crawler upload (one wording per row) and the per-Prompt readings in the baseline report. Do not add a pairing column to the Base (a 共有意图 field was tried and dropped 2026-10-20): the language versions of one intent already link to the same 提示词矩阵 slice and carry the same 中文含义, and the brand party reviews one market at a time. The pairing lives in the bank JSON as a shared `intent_key` with `market_decision` `localized`, which is what cross-market analysis reads. Write the language versions next to each other (Topic, then intent, then market) and leave the main view unsorted so they stay adjacent; per-market views sort by 编号. A same-language row shared by several markets still gets per-market baseline readings (one baseline report per market: `build_baseline_html.py` reads one `region` per run); if the markets later need different wording or one market retires it, split it into per-market rows.
- **提示词矩阵 is shared across markets.** A slice records who, at which stage, testing which attribute, and the attribute judgements; none of that depends on the language. A slice is one row with 市场 = every market whose Prompts link to it, and 目标题数 counts the linked per-market Prompts. So 市场 is multi-select on 业务范围, 需要品牌方提供的数据, 品牌事实核查, 提示词矩阵 and 提示词库.
- When a shared slice's judgement differs by market (Nbrand: 本地语言 is 优势 in Korea, 持平 in Taiwan), keep one row with the stronger reading and state the per-market verdicts at the start of 备注; split the slice only if the difference changes its priority tier.
- 买家原话 and the three baseline tables are single-select: a quote comes from one market, and a baseline reading is one Prompt × one platform × one market.
- Prefix the market code on IDs that belong to one market (quotes `KR-R001`, question IDs `AN-KR-T1-D01`) so they stay unique in one table; slice IDs stay plain `M-001`.
- Add one filtered grid view per market (named after the market, filter 市场 contains it) on 买家原话, 提示词矩阵 and 提示词库; the brand party reviews a market by switching views. The dashboard counts all markets together — filter it by 市场 before reading a market's coverage.
- Measurement stays per market: the bank JSON, validator run, version and baseline remain one per market (see output-contract.md → *Market Coverage and Localization*); compare the language versions of one intent (same `intent_key`) side by side, never average them.

Customer-facing names: call the Prompts **提示词** (tables 提示词矩阵 / 提示词库, field 提示词); keep **主题** for Topics. Suda reversed the 2026-08 ban on 「提示词」 on 2026-10-14. Use one term throughout the Base and the 使用说明.

### 属性池

One row is **one buyer decision attribute**. It is the only place the attribute itself is maintained: the matrix links to it, and one matrix column (可改变性) is a formula that reads it (Suda 2026-10-20 unified the two structures after a client Base ended up with both a text 属性 column and a separate pool).

Columns, in view order: `属性（主字段） | 相对竞品 | 可改变性 | 判断冲突 | 类别 | 判据与证据 | 还缺什么 | 产品线 | 属性编号`. The default view groups by 类别.

- 属性名 is the primary field and the link target: the matrix's 属性关联 cell displays it. Keep one wording per attribute — never a long form here and a short form there.
- 属性编号 (A-001, A-002…) is filled once when the pool is created and stays stable across rewrites; nothing links by it, so it is a label, not a key.
- No priority column, not even a read-only roll-up of the matrix tiers (Suda 2026-10-20): priority is a slice-level result and is read on 提示词矩阵 only.
- **判断冲突** is a formula that flags a 相对竞品 / 可改变性 pair the rules forbid (Suda 2026-10-20, after Hbrand's competitor-parity pass left three 劣势 rows at 高): `IF(AND([相对竞品]="劣势",[可改变性]="高"),"劣势不应判高",IF(AND([相对竞品]="待确认",[可改变性]!="中"),"待确认先记中",""))`. A 「判断冲突」 view filters it non-empty; it must be empty before the Base goes to the brand party and after every batch of 相对竞品 edits. The check lives in the Base because the judgements live there — do not copy them into the bank JSON just to validate them.
- 产品线 is kept even when the engagement has one line, because later cycles add lines: one attribute can belong to several lines, and the matrix is what narrows it to the slice.
- 类别 is the twelve-class sweep label (产品特性 / 购买标准 / 差异化优势 / 信任与合规 / 品类 / 限制与边界 / 地理与市场 / 使用场景 …), so the sweep can be checked for holes.
- 相对竞品 / 可改变性 / 重要性 are the three judgements the priority formula reads; 判据与证据 carries the evidence behind them — the answer-layer observation, the competitor page, the buyer quote. No separate 证据 column.
- 还缺什么 is the material we still need from the brand party **before the baseline** — only what the brand party alone knows and what would change a Prompt or a judgement now: whether a business or capability exists at all, a policy only they set, or the standard answer a named Prompt needs (write 「点名题要用：…」). Do not ask here for counts, update frequencies, user statistics or other evidence: that is gathered when content work starts after the baseline. Do not ask for anything their site or app already shows — check it ourselves. Hbrand went from 35 rows to 9 on this rule (Suda 2026-10-20); the deferred items are kept in the engagement's `_evidence/` folder, not in the Base.
- **重要性** (高 / 中 / 低, added 2026-10-22, replacing the matrix's per-slice 购买影响): does the buyer care about this attribute when choosing — 淘汰条件 (failing it drops the option from the shortlist) = 高, 比较维度 (weighed after shortlisting) = 中, 加分项 = 低. Judged **once per attribute**: Hbrand's replay showed 41 of 43 attributes carried one value across every slice, so the per-slice copy was 95% repetition (Suda 2026-10-22). When a situation genuinely changes the reading (Hbrand: 地铁与学校距离筛选 was 高 for school-driven renters, 中 elsewhere), **split the attribute into two pool rows** with the situation in the name (「非本国居民适用性（租）」/「（购）」) — the difference is real information and belongs in the attribute, not in a hand-edited matrix cell. Validated like any importance claim: Step 3.5 demand evidence, hypothesis grade without a first-party source.
- Add one row per attribute as soon as it is judged, including attributes with no Prompt at all; the matrix then gets one row per attribute × slice, and an attribute with no Prompt still gets its own matrix row carrying the 首期不配提示词 reason.
- **Audiences are pool rows too** (Suda 2026-10-23). Every 主要受众 except the category's base audience gets one row with 类别 = 买家角色 and 属性 = **the 受众 option verbatim** (「多猫家庭」, not 「适合多猫家庭」) — the matrix matches the two by name. 买家角色 holds audiences only: a persona that changes eligibility, dominant criteria or the answer is an audience (after-sales-rules.md → *Audience Segments*), one that does not is a 约束, so there is no third kind of 买家角色 row. Only 重要性 is judged on an audience row (Suda 2026-10-23); 相对竞品 and 可改变性 stay blank, and the 判断冲突 formula ignores blank cells. Its 重要性 reads **how much this audience matters to the engagement** — 高 when the brand party marked it 主要受众（优先） or a 业务目标 names it, 中 for other 主要受众 with first-party demand evidence, 低 for a 后续 or hypothesis-grade audience. It is the only place business weight enters 重要性; every other row stays a buyer-side judgement. The row has one job: its 重要性 caps every slice whose 受众 names it (see *提示词矩阵* → 优先级). It is never linked as 属性关联 — the audience's anchor slice (「best X for <audience>」) is a category-baseline row with an empty 属性关联 and that audience in 受众, so it starts at P1 and the cap applies like anywhere else. The base audience gets no row — it is the category itself, like `config.base_conditions`, and caps nothing.

### 提示词矩阵

One row is **one coverage slice × one tested attribute** (Suda 2026-10-15 realigned the matrix to Aleyda's slice columns). Aleyda's matrix row is a coverage slice and the attribute is one of the slice's dimensions; Prompts are written per slice, not per attribute. The slice is many-to-many with attributes, so 属性关联 is a link field rather than an embedded copy: one attribute judged once, many slices pointing at it.

Columns, in view order:

`切片编号（主字段） | 市场 | 受众 | 旅程阶段 | 约束 | 优先级 | 优先级原因 | 已有问题 | 产品线 | 目标题数 | 覆盖情况 | 备注 | 属性关联 | 可改变性`

The default view groups by 旅程阶段 only (Suda 2026-10-20): 受众 is multi-select, and grouping by it puts a row with two audiences into a group of its own, so to read one audience, filter 受众 instead. Without several markets the 市场 column is absent (Hbrand: 13 columns).

- **切片编号** is the primary field: plain text M-001, M-002… in order (a text field, not a formula), also when several markets share the Base. The slice's meaning lives in its dimension columns — 受众, 旅程阶段, 约束, 属性关联.
- **属性关联** is the link to 属性池 and **the only attribute column**: its cell already displays the attribute name (the link target's primary field), so a separate 属性 column would repeat it. 相对竞品 and 还缺什么 are **not** copied onto the matrix at all — they live in 属性池, and filtering 还缺什么 non-empty happens there (Suda 2026-10-20 trimmed the matrix from 17 columns to 13, 14 with 市场).
- **可改变性** stays on the matrix as a formula, `ARRAYJOIN([属性关联].[可改变性],"")`. It is a copy of the pool value, kept because the priority formula reads it and because the brand party must see *why* a slice is P1 without cross-reading another table.
- **No Aleyda nine-type column on 提示词矩阵** (Suda 2026-10-15). Aleyda's Prompt Type (推荐榜单 / 对比 / 替代方案 …) mostly repeats 旅程阶段 — on Pbrand's 120 rows 对比 / 替代方案 / 购后支持 each held one type and 交易 was 12 of 15 one type — and the rest repeats 约束 (scenario, budget) or 属性 (reliability). How a Prompt is read is 提示词类型 on 提示词库 (our eight types, renamed from 意图 on 2026-10-22; 替代 split out the same day), a per-Prompt field, not a slice dimension.
- **约束** is its own column (same name as in 买家原话): the conditions the buyer carries beyond the attribute — budget, home size, number of cats, days away, a named rival or model. Write 2–3 keywords separated by 、 (「小公寓、2–3 只猫」「300 美元以内」「对手 Litter-Robot」), after Aleyda's CONSTRAINT column; do not restate 受众, 旅程阶段 or 属性 — the full wording lives in the Prompt. Slices that share every other dimension must still differ here (Suda 2026-10-15).
- **目标题数 / 覆盖情况**: we fill 目标题数 **before writing Prompts**, not after. Default is 1. Add one per additional buyer constraint wording where the candidate list would change — "two cats" vs "four or more" on the same feeder slice may pull different brands; different phrasings of the same constraint that would produce the same shortlist do not add a count. Note in 备注 which constraint each extra Prompt tests. Leave 目标题数 blank (never 0) on slices with no first-stage Prompt. 覆盖情况 is a single formula that counts the linked Prompts whose 状态 is 已批准 or 正式 and compares them with 目标题数 (已覆盖 / 未达标 / 不配题 for 0) — there is no separate 已批准题数 column, the count is inlined (Suda 2026-10-20).
- **Rows.** Every situation × attribute pair that has Prompts is a row. Every attribute with no first-stage Prompt also gets one row (受众 the category's base audience, 约束 written from its buyer problem, a judged 旅程阶段, 目标题数 blank), with the reason at the start of 备注 — 「首期不配提示词：重要性低，不决定买家选谁」 or 「…：能力缺口，发布内容改变不了 AI 的说法」. Do not add a separate 去向/缺口说明 column. Category-baseline Prompts sit on rows with an empty 属性关联. **The grid behind the rows is enumerated top-down before slices are filled** (Suda 2026-10-22): 产品线 × 受众 × 旅程阶段 is written out from 业务范围 first and signal collection fills it; a cell still empty when the matrix settles is closed with a reason in the internal handoff — `scripts/check_matrix_coverage.py` lists the open cells. Closed empty cells stay internal; they do not become client Base rows.
- **受众** is a multi-select with the same option set as 买家原话 (single-select until Suda 2026-10-20). A slice or quote that fits several buyer groups ticks each of them instead of falling back to a catch-all audience; the dashboard's 按受众 chart then counts such a row once per group, so its bars can sum to more than the total. Use only real buyer groups. A journey state is not an audience — 「已在比较具体品牌」 is the 对比 stage, not a persona — so named-brand Prompts are filed by the group their wording names, and rows with no narrower group condition take the category's base audience — the buyer group the whole category serves, such as 「养猫家庭」 for pet-cat devices — never 「通用」 and never blank (Suda 2026-10-15). List the base audience as 主要受众（1） in 业务范围 so it is an option in the select. Audiences beyond the brand party's listed 主要受众 are added to 业务范围 as 主要受众 rows.
- **旅程阶段** uses the eight stages below; there is no separate 买家任务 column.
- **购买影响 was removed from the matrix** (Suda 2026-10-22): it restated the attribute's 重要性 per slice — Hbrand's replay found 41 of 43 attributes identical across all their slices — so importance is now judged once in 属性池 and the two genuinely situation-dependent cases are handled by splitting the pool row (see *属性池* above). The matrix keeps no hand-filled judgement columns at all: its own columns are the slice dimensions (受众 / 旅程阶段 / 约束), planning (目标题数 / 覆盖情况 / 备注), and formulas.
- **可改变性** is a read-only formula from 属性池; 相对竞品, 重要性 and 还缺什么 are read there instead. When the brand party corrects a judgement, change the 属性池 row — every slice of that attribute follows. 备注 stays per slice and is written only on the slice's first row.
- **优先级** is a formula; the brand party never fills it:
  - look up 重要性 (高 / 中 / 低, from 属性池 via 属性关联) × 可改变性 (高 / 中 / 低) in the tier table in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*; changeability is graded there by two ordered questions;
  - **P1 only at 高 × 高**; the Base formula field encodes the same table;
  - rows with an empty 属性关联 (category baseline) are fixed at P1 — they measure which brands AI lists with no condition, the base of natural visibility.
  - **then the audience cap** (Suda 2026-10-23), inside the same 优先级 formula — no separate column, the formula reads 属性池 重要性 directly (`[属性池].FILTER(AND(CurrentValue.[类别]="买家角色",[受众].CONTAIN(CurrentValue.[属性]))).[重要性]`; a single-select 受众 compares `CurrentValue.[属性]=[受众]`) and keeps the highest; 高 or empty (base audience, or an audience with no pool row yet) leaves the tier alone, 中 lowers P1 to P2, 低 makes the slice P3. A slice serving several audiences takes its most important one. The cap reads 重要性 only, not the audience row's own tier: whether content can move this slice is already its attribute's 可改变性, and counting an audience's changeability again would keep the brand party's top audience out of P1 merely because "fits <audience>" is hard to move. Before sending, check that every non-base 受众 option has a 买家角色 row with 重要性 filled in 属性池 — an audience without one is never capped.
  - Check the distribution after filling: P1 must stay a short list. If 高 × 高 rows pile up, re-check whether the rows graded 高 changeability are really unwritten where AI can read.
- Drop: formula-built slice IDs, a 市场与语言 text column (the 市场 select carries the market), 业务优先级 (half importance, half an echo of attribute priority), 客户确认 (the brand party edits cells directly — see *How the brand party reviews*), and any column whose every row holds the same value. 目标题数 / 覆盖情况 came back on 2026-10-15 because 状态 now separates written (待审核) from approved (已批准), so coverage is no longer always 已覆盖.

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

- **月搜索量** (single-select) is the target market's monthly volume tier for 搜索数据 rows (Ahrefs free-tier estimate: >10,000 / >1000 / >100 / <100). Google 自动补全 rows carry no volume — leave the cell blank. Keep the tier out of 来源说明, which already states the tool and market; the column exists so the brand party can sort and filter by demand size.

- **Primary fields are chosen for what a link cell shows** (Suda 2026-10-15). A linked cell displays the other table's primary field, so: 买家原话 leads with **原话**, and 提示词库's 证据 cell shows the quote itself, letting the brand party judge a Prompt's grounding without leaving the row; 提示词库 leads with **提示词**, so 提示词矩阵's 已有问题 lists the actual questions; 提示词矩阵 keeps **切片编号**, because no content column identifies a slice — Pbrand's 120 rows had 3 product lines, 52 attributes of which 25 repeat, and 17 repeated 属性 + 受众 + 旅程阶段 combinations. When the brand party reads only Chinese, lead 买家原话 with 中文意思 instead.
- **输入编号** stays near the end, before 月搜索量. Our bank JSON's `evidence_refs` and `config.audience_inputs` cite it, and both sides use it to point at one quote in feedback.

- **涉及品牌** (multi-select) names the brand the quote is about; generic buying posts and search terms are 「未指明品牌」. A subreddit name is not a brand mention.
- **来源类型** is the real source — 社区 / 评价 / 搜索数据 (later 销售记录、客服记录、GSC、站内搜索 when the brand party supplies them). Never 「竞品评价」: whose product it is goes in 涉及品牌.
- **受众** uses the same multi-select set as 提示词矩阵; who the poster owns (「Pbrand 用户」「LR 用户」) is not an audience.
- Marketplace summary tags (Amazon 「Customers say」) keep only the tag text in 原话, the product name in 来源说明, and a 中文意思 that names the brand.

### 提示词库

`提示词（主字段） | 中文含义 | 提示词类型 | 状态 | 主题（单选） | 所属切片 | 优先级 | 证据 | 产品线`, default view grouped by 主题 (with several markets: 市场 right after 提示词, see *Several markets in one Base*); 编号, 库分层 and AI 认知差距 exist but are hidden in the default view. 库分层 stays hidden until the formal set is chosen — during the candidate stage nearly every Prompt is 核心, so the column tells the brand party nothing (Suda 2026-10-19). **优先级 is a read-only formula** (Suda 2026-10-22; 2026-10-23 narrowed to the selection question), `IF([信源壁垒]="来源追不上",SWITCH(ARRAYJOIN([所属切片].[优先级],""),"P1","P2","P2","P3","P3","P3",""),ARRAYJOIN([所属切片].[优先级],""))` — the slice's tier, dropped one tier **only** when the Prompt's 信源壁垒 is 来源追不上. It is the **selection** priority, the order in which we recommend the client pick Prompts; optimisation order is a separate result read in the baseline report after collection. **The brand's own reading never moves this column** (Suda 2026-10-23): 已打平或领先 / 部分出现仍落后 / 竞品领先 are recorded and shown, but none of them drops a tier here — a Prompt the brand already wins is still worth monitoring, and the trial's three runs are not a stable reading. **信源壁垒** (replaced the seven-value 竞争格局 on 2026-10-23, Suda) is a single-select we fill: 待判 / 来源追不上 / 无, default 待判. Only Discovery and Alternatives Prompts are judged; every other type is 无. 来源追不上 means the recommendation itself rests on sources the brand cannot get into (a government portal leading the candidate list, or a list built from such pages) — read from the trial answers and re-checked on the formal baseline; competitor official pages and review sites never count. How far the brand trails or leads is not recorded in the Base: the five competition patterns are computed in the baseline report and used only for optimisation order (after-sales-rules.md → *Priority is set in two passes*). Hidden in the default view like AI 认知差距; it is not a hand-filled copy of a slice field, so the no-slice-level-columns rule (below) is untouched; in views it sits right after 所属切片.

- **提示词类型** (single select: 发现 / 对比 / 替代 / 评价 / 验证 / 准确性 / 品类认知 / 信息; 信息 and 替代 are after-sales only — 信息 Suda 2026-10-19, 替代 split out 2026-10-22; the 对比 label was 竞品对比/竞品 before 2026-10-23, and the field was renamed from 意图 on 2026-10-22) is the bank JSON's `prompt_type` shown in Chinese, using the names in shared/canonical-intent-mapping.md; the two are one field, never two vocabularies (Suda 2026-10-15). It decides which metric a Prompt feeds (see after-sales-rules.md → *Prompt Priorities*). We fill it; the brand party does not edit it. **看什么指标** (Suda 2026-10-23) is a read-only formula, `SWITCH([提示词类型],"发现","提及率（计入考核指标）…",…)`, that shows the brand party in plain words what each type is read for — 发现: 提及率, the only KPI; 对比: 胜率; 替代: 提及率 in the alternatives list (the column does not say whether it counts toward the KPI — undecided, Suda 2026-10-23); 评价: AI's verdict and reasons; 验证: whether AI knows the capability; 准确性: whether the fact is right; 品类认知: whether the buying criteria include the brand's strengths; 信息: site citation only, no mention rate (Suda 2026-10-23) — the other non-Discovery lines end 「不计入提及率」. It is a formula, not a hand-filled 分析类型 column, so it cannot drift from 提示词类型. It names no sentiment reading (not sold to clients since 2026-10-21).

- **状态** (待审核 / 需修改 / 已批准 / 正式 / 停测, default 待审核) is one column for the whole life of a Prompt (Suda 2026-10-19 merged the former 审核状态 and 状态, which looked duplicated because one only mattered before the baseline and the other only after): we mark 待审核 after internal QA; the brand party marks 已批准 when the Prompt is fine or after editing it directly, 需修改 when it wants us to rewrite. **Only 已批准 Prompts enter the formal selection.** At lock — when the brand party confirms the formal set, before the formal baseline runs — the selected Prompts move to 正式 and every other candidate to 停测 (Suda 2026-10-23: 正式 means "in the formal set", so monitoring knows what to collect; it no longer waits for the baseline to finish). 覆盖情况 on 提示词矩阵 counts 已批准 and 正式, and so does the dashboard's 已批准提示词 card.
- **优先级原因 is a formula, added 2026-10-23 (Suda) because a bare P1/P2 tells the brand party nothing.** On 提示词矩阵 it renders the slice's own judgement in plain language: the attribute name, what its 重要性 means for the buyer, what its 可改变性 means for content, the 相对竞品 verdict, and — when it differs from the raw tier — that the audience's business weight caps it. On 提示词库 it pulls the slice text and appends the 信源壁垒 drop when it applies. Build both from the same expressions so the two can never disagree with the 优先级 column; the check before sending is that every row's reason implies that row's tier (Hbrand 2026-10-23: 119 matrix rows and 80 Prompts, zero mismatches). Wording is the brand party's language, never the rule's internal vocabulary — 「买家会因为它直接排除品牌」, not 「重要性 高」.
- **No slice-level columns on 提示词库.** 旅程阶段, 约束 (and the old 买家问题与场景) belong to the slice and were identical on all 100 Pbrand Prompts; a second copy drifts when the brand party edits one table. The reviewer opens 所属切片 to see them (Suda 2026-10-15). The bank JSON keeps `journey_stage` for metrics and the validator.

- The main view is grouped by 主题 and not sorted, so the language versions of one intent stay adjacent; per-market views sort by 编号.
- **AI 认知差距 exists only after the formal baseline.** Judge it per Prompt from that Prompt's own answer text (知道但不推荐 / 不知道该能力 / 无人讨论 / 无缺口; the pre-2026-10-22 single value 有缺口 split into the first two — a paired Verification Prompt on the same attribute tells them apart, see after-sales-rules *Prompt Priorities*). Until then every row is 「待基线」 and the column is hidden in the view. The 3-run trial on each monitored platform does not fill it: three runs are an exploratory lead, not the reading. Metric readings (提及率 and the rest) never go into 提示词库 — they live in the HTML report. Never push an attribute-level judgement or presales answers onto individual Prompts — Prompts under one attribute would all read the same however their wording differs, which is not data.
- **主题 names describe what the Topic holds.** A category Topic that also carries condition Prompts (safety, large cats, one app) is 「××选购条件」, not 「××品类」; a Topic whose Prompts span cost, reliability and upkeep is named for all three.
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
- **This is where the Accuracy gate's research lands.** For each factual P1 (and factual P2 carrying Prompts), the public-layer and answer-layer checks the intent rules describe are recorded here rather than only in an attribute 备注. A row becomes an Accuracy Prompt only through the accuracy gate (the client has confirmed the correct value with an official source and a wrong answer changes the purchase) — most rows stay 改官网 / 提供材料 and never become Prompts.

### How the brand party reviews

The brand party edits cells directly — wrong fact: change the cell; missing: add a row. There is no 客户确认 column (Suda 2026-10-15). Before sending, snapshot every table (and deploy later changes incrementally, checked with `python3 scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` — see *IDs freeze* above); when collecting, compare against the snapshot and `lark-cli base +record-history-list` to see each change, and review every edit to 重要性 / 相对竞品 / 可改变性 (属性池) because they move the priority formula. Filter 属性池 还缺什么 non-empty to find the must-answer cells.

### Facts we can verify ourselves

Settle what the public layer can settle before asking the brand party — for example whether a model is still sold: check the official site's product pages, redirects and search, then the main marketplace, and write the result into 业务范围 as a settled fact, not a question. Ask the brand party only for what only it knows.

## Canonical Shape

The sections below define the content. In the Base they live as: 品牌事实 → 业务范围, 属性池 → the 属性池 table (linked from 提示词矩阵), 主题与问题 → 提示词库. Where a section below conflicts with *Settled table set*, the table set wins. Use the sections that fit the task; do not force all of them into a small update.

1. **Opening scope paragraph**
   - State the monitoring object, product/category scope, market/language, and entry scenario.
   - Ask the brand party to confirm three things: the attribute list, the buying impact, and whether the brand is advantaged/at parity/weak versus competitors.
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
   | 重要性高不高 | 这条不解决，买家会不会不入围、不购买、不续费、退货或要求补证据 | 买家公开选购理由、放弃理由、搜索规模、媒体评测维度、竞品主推方向 |
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

   `类别 | 属性 | 解决的买家问题 | 重要性 | 相对竞品 | 优先级 | 还缺什么 | 备注 | 客户确认`

   Use a compact variant when evidence is simple:

   `类型 | 属性 | 解决的买家问题 | 重要性 | 相对竞品 | 优先级 | 品牌方补充与确认`

   Column semantics:
   - `类别/类型`: readable grouping such as 品类、目标客户画像、痛点、使用场景、购买标准、产品能力、差异化、信任与合规、申请门槛、地域与市场、约束.
   - `属性`: the buyer decision focus AI should associate with the brand. Differentiators are rows in this table, not a separate section, Topic, or Tag.
   - `解决的买家问题`: plain buyer problem or selection risk. Keep it close to customer language.
   - `重要性` (called 购买影响 in documents before 2026-10-22): buyer-side impact, normally 高 / 中 / 低. Judge by “if unresolved, does the buyer drop or downgrade the brand?”, not by frequency alone.
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

   In the Base the tier is a formula on 提示词矩阵 (lookup in *提示词矩阵* above). Before any answers are collected, set the initial priority from **importance × changeability**; current gap is `待测` until the baseline (the three conditions and their scales are in [after-sales-rules.md](after-sales-rules.md) → *Priority is set in two passes*). `重要性` is the importance reading, judged once per attribute in 属性池; `业务重点` the brand party states counts as evidence for it. `相对竞品` and the gap type feed changeability: an `优势` or `持平` row whose facts are unpublished (证据缺口) is the cheapest win; a `劣势` row behind on the facts, or a consensus-locked direction, scores low.

   Important constraints:
   - P1 can coexist with `持平`: for a new product or category gate, the first-stage problem may be "AI does not know we have this," not differentiation.
   - P3 rows remain visible so the brand party can disagree, but P3 attributes do **not** get first-batch Prompts.
   - Only P1/P2 attributes normally carry first-stage Discovery Prompts.
   - `待确认` means the evidence is missing, not that the attribute is weak.
   - Once the baseline has measured the current gap, re-judge changeability from the answer layer and adjust each Prompt by its current gap (importance × current gap × changeability); do not backfill the current gap before collection.

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
   - P3 attributes should not appear as first-stage Prompt coverage.
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
   1. 品牌方确认业务重点、事实边界和属性池。
   2. 每道候选题在每个监测平台各跑 3 次，检查问法是否准确、回答是否切题、各平台结果是否一致；结果只作参考，不作为数据统计。
   3. 品牌方从候选题中选定正式题（每个采购主题最多 10 条），确认后锁定版本。
   4. 正式题在每个平台、国家和语言下各跑 30 次，作为优化前的基准。

## Wording Rules

- Use `品牌方`, not `贵司` / `贵校`.
- Write the final document directly; do not mention “上一版”, “补充更正”, or internal revision traces.
- Keep methodology, word-frequency work, validation steps, and evidence-position mappings out of the customer document. Archive them internally.
- Mark uncertain claims as `待核`, `待确认`, `待验证`, or `品牌自述`; do not turn trade-press/self-declared claims into facts.
- Avoid merged cells in Feishu tables. Empty cells are safer when rows are inserted or deleted.
- If a number is visible only through JavaScript or non-static page rendering, note the source limitation before treating it as AI-readable evidence.
- The brand party corrects facts and priorities; we make the judgement. Do not ask them to write our reasoning for us (for example, “why buyers credit this advantage”).
