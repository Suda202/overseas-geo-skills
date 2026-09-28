# Client-Facing Attribute Pool and Confirmation Document

This reference turns researched attributes and candidate Prompts into a client-facing confirmation piece. It is based on recent customer documents such as 中国农业大学海外招生监测属性池, Bewinch 台式净饮机售后生词, Botslab NightVue NV900 售后监测主题与词表, and Piltwave 监测属性与优先级确认.

## Purpose

The document lets the brand party quickly correct business facts, attribute priority, relative competitive position, and Prompt wording. It is not a methodology note, evidence dump, approval record, or internal reasoning archive.

Use it when delivering or updating an after-sales attribute pool, first monitoring-topic set, customer confirmation document, or trial handoff. Keep the document in Chinese unless the customer explicitly needs another language.

## Canonical Shape

Use the sections that fit the task; do not force all of them into a small update.

1. **Opening scope paragraph**
   - State the monitoring object, product/category scope, market/language, and entry scenario.
   - Ask the brand party to confirm three things: the attribute list, the buying impact, and whether the brand is advantaged/at parity/weak versus competitors.
   - Explain the confirmation convention: every table's `客户确认` column is write-what-to-change; blank means reviewed with no change.

2. **核对时从哪里判断**

   The internal team may use a market-coverage pass to check whether the pool
   misses a product line, audience, journey stage, constraint, competitor,
   local terminology, regulation, currency, trust signal or source ecosystem.
   Do not expose that full matrix as a customer questionnaire. Show the
   customer only the resulting brand facts, attributes, and market-specific
   Prompt rows that require factual or priority confirmation.

   | 要确认的 | 内部看什么 | 外部看什么 |
   |---|---|---|
   | 属性清单全不全 | 销售、客服、售后、win/loss、续费/退换货、GSC/站内搜索：是否有反复出现但表里缺失的问题 | 买家社区、评论、论坛、竞品页面、规格表、媒体评测、AI 回答里的高频属性 |
   | 购买影响高不高 | 这条不解决，买家会不会不入围、不购买、不续费、退货或要求补证据 | 买家公开选购理由、放弃理由、搜索规模、媒体评测维度、竞品主推方向 |
   | 相对竞品是优势还是持平 | 品牌自己的实测、交付记录、案例、服务条款、价格和可引用证据 | 竞品公开证据、第三方评测、榜单、社区口碑、AI 答案层同主题表现 |

   Adapt the wording by buyer type:
   - **B2B:** first-party sales/procurement/contract/renewal records usually outweigh public evidence.
   - **B2C hardware/consumer:** public reviews, community language, ecommerce Q&A and third-party reviews may carry the buyer-language layer; internal returns, service tickets, warranty terms and test data remain crucial for relative-competitor judgement.
   - Public absence means `待确认`, not `无优势`; ask what material the brand party can provide.

3. **品牌事实【请核对】**

   Keep factual scope separate from ranked attributes. Typical rows:
   - 品牌 / 业务模式 / 品类 / 产品或服务范围
   - 目标客户、目标企业画像或核心人群
   - 市场与语言、切入场景、适用边界
   - 官方域名
   - 竞品或替代方案（only if the comparison set itself needs confirmation）

   Use `项目 | 内容 | 客户确认` or `项目 | 内容 | 品牌方补充与确认`. Do not rank brand facts.

4. **属性池【请核对】**

   Default columns:

   `类别 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 还缺什么 | 备注 | 客户确认`

   Use a compact variant when evidence is simple:

   `类型 | 属性 | 解决的买家问题 | 购买影响 | 相对竞品 | 优先级 | 品牌方补充与确认`

   Column semantics:
   - `类别/类型`: readable grouping such as 品类、目标客户画像、痛点、使用场景、购买标准、产品能力、差异化、信任与合规、申请门槛、地域与市场、约束.
   - `属性`: the buyer decision focus AI should associate with the brand. Differentiators are rows in this table, not a separate section, Topic, or Tag.
   - `解决的买家问题`: plain buyer problem or selection risk. Keep it close to customer language.
   - `购买影响`: buyer-side impact, normally 高 / 中 / 低. Judge by “if unresolved, does the buyer drop or downgrade the brand?”, not by frequency alone.
   - `相对竞品`: 优势 / 持平 / 劣势 / 待确认. Add a short evidence note when needed.
   - `优先级`: our initial action priority, not the customer's vote and not the final optimization priority after baseline.
   - `还缺什么`: specific material needed from the brand party; omit or leave blank when no material is needed.
   - `备注`: evidence and caveats we found. Keep it factual and short.
   - `客户确认`: write-what-to-change only.

   For multi-market work, add the market only when it changes the buyer
   decision or evidence context. Use the existing `类别/类型` and
   `市场/语言` facts, attribute, constraint, competitor, or Prompt columns;
   do not create one duplicated attribute row for every country merely to
   demonstrate coverage.

5. **Priority Rules**

   Use `购买影响 × 相对竞品 × 业务重点` for the initial attribute priority.

   | Condition | Initial priority |
   |---|---|
   | 高影响 + 优势, or core scope/table-stakes recognition that must enter the candidate set | P1 |
   | 高影响 + 持平 | P1 when the first task is to make a new/unknown product recognized; otherwise P2 |
   | 高影响 + 劣势 | P3 or baseline-only; do not create a standalone Depth Topic to fight a structural loss |
   | 高影响 + 待确认 | 待定 / P2 pending evidence; ask for evidence instead of silently downgrading |
   | 中影响 | Usually P3 unless it is a confirmed strategic priority with evidence |
   | 低影响 | P3 or excluded |

   Important constraints:
   - P1 can coexist with `持平`: for a new product or category gate, the first-stage problem may be “AI does not know we have this,” not differentiation.
   - P3 rows remain visible so the brand party can disagree, but P3 attributes do **not** get first-batch Prompts.
   - Only P1/P2 attributes normally carry first-stage Discovery Prompts.
   - `待确认` means the evidence is missing, not that the attribute is weak.
   - Final operational priority after the three-day baseline adds measured AI Gap and optimizability; do not backfill those columns before collection.

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
   - Keep `Prompt Task` in internal planning. Show an optional `买家任务` column only if the customer needs to distinguish why candidate question groups exist; use plain labels such as 发现、比较、替代方案或验证可信度, never backend routing terminology.

7. **竞品名单（请确认）**

   Add a separate section when competitor scope is unstable or customer-submitted competitors were replaced.

   `品牌 | 说明 | 客户确认`

   Explain each inclusion/exclusion by “same buying comparison set,” not by brand fame alone.

8. **试跑与锁词流程**

   If the document hands off to monitoring, state the staged process in four lines:
   1. 品牌方确认业务重点、事实边界和属性池。
   2. Candidate Prompts run three to five trial collections per proposed platform to check fit, ambiguity, leading wording and duplication.
   3. The final Prompt set is confirmed and version-locked after trial.
   4. Formal baseline uses three consecutive calendar days, once per Prompt/platform/day; trial answers are not baseline data.

## Wording Rules

- Use `品牌方`, not `贵司` / `贵校`.
- Write the final document directly; do not mention “上一版”, “补充更正”, or internal revision traces.
- Keep methodology, word-frequency work, validation steps, and evidence-position mappings out of the customer document. Archive them internally.
- Mark uncertain claims as `待核`, `待确认`, `待验证`, or `品牌自述`; do not turn trade-press/self-declared claims into facts.
- Avoid merged cells in Feishu tables. Empty cells are safer when rows are inserted or deleted.
- If a number is visible only through JavaScript or non-static page rendering, note the source limitation before treating it as AI-readable evidence.
- The brand party corrects facts and priorities; we make the judgement. Do not ask them to write our reasoning for us (for example, “why buyers credit this advantage”).
