# 基线报告（HTML）

Formal-baseline results go to the brand party as one HTML file (the candidate baseline was retired 2026-10-23; old candidate-baseline reports built with this script stay valid), never as Base tables (Suda 2026-10-21). A Base dashboard can only SUM / AVG / MAX / MIN and cannot divide across rows, so every rate had to be precomputed per filter combination (Hbrand: 1,344 helper rows), and a dashboard-level filter cannot be created through the API. The HTML is precomputed and verified too, but filters freely. The Base keeps only what the brand party confirms or edits (AI 认知差距 stays on 提示词库).

Script: `scripts/build_baseline_html.py`. It reuses `geo-presales-report-builder` (build_report_data → verify_report_data → render_report) and `geo-presales-sentiment-judge`, patching them at run time; it never edits those skills' source.

Run every command from the client's baseline directory with the script's absolute path:

```bash
S=<项目根>/.agents/skills/geo-monitoring/scripts/build_baseline_html.py
```

## Workflow

Sentiment and translations are prepared before the report is built, so the report is generated once with everything in it (Suda 2026-10-22).

1. **Collect** each round into its own directory (`collect_r1` … `collect_rN`, `scraper.<platform>/<region>/NNNN.json`, numbered by `questions_csv` row order) and run `geo-presales-crawl-integrity` on each.
2. **Prepare** — `python3 -I $S --config baseline-html.json --prepare`. Writes `out_dir/collect` (all rounds merged, files `<NNNN>-r<RR>.json`, region directory = 提示词类型), `out_dir/questions.csv` and `out_dir/lexicon.json`. Nothing is computed yet.
3. **Sentiment** (skip it and the 04 情感 module and the per-answer sentiment are left out):
   - `python3 <sentiment-judge>/scripts/sentiment_sentences.py extract --bank out_dir/questions.csv --crawl-dir out_dir/collect --lexicon out_dir/lexicon.json --output sentiment/units.json`
   - `python3 -I $S --config baseline-html.json --export-claim-batches sentiment/batches` → hand each `batch-NN.json` to a subagent that writes `batch-NN.claims.json` (`unit_index / brand / claim / sentiment`, rules in sentiment-judge `judgment-rules.md`). One subagent per one or two batches; it must not delegate.
   - `python3 -I $S --config baseline-html.json --merge-claims sentiment/batches` → `sentiment/claims-raw.json` (unit index and brand checked).
   - Cluster claim → attribute → theme by hand in `claim-attributes.json` / `attribute-themes.json` (sentiment-judge `claim-layer-contract.md`: an attribute is a standalone phrase without a theme prefix, synonyms merged, distinct selling points kept apart), then `claims-assemble` and `claims-metrics`; set `sentiment` in the config.
4. **Translations** (skip them and each run shows 回答原文 only), in parallel with step 3:
   - `python3 -I $S --config baseline-html.json --export-translations translation-batches` → `batch-NN.json` (`key / text`, 60 answers each, key `提示词类型|平台|0001#r01`). The text is the answer after the report's own rendering and clean-up, with citations as 「来源名+编号」 (HDB2) so they can be restored as pills.
   - One cheap subagent per two batches writes `batch-NN.zh.json` (`{key: 中文}`): keep paragraph and list structure, brand / project / term names, numbers, URLs and citation markers as they are; write after every 10 items; validate the JSON; translate itself, never hand the work on. Check each returned file for key count, line count and length ratio before accepting it — a subagent that delegates and returns early leaves no file.
   - Set `translations` in the config.
5. **Build** — `python3 -I $S --config baseline-html.json`. Computes every slice, stops if verify_report_data disagrees on any of them, attaches sentiment (reconciled against `claims-metrics`) and translations, and renders the HTML. `--render-only` re-renders without recomputing.
6. **Check** — the build prints `校验通过：N 个切片全部与独立复算一致`, the sentiment reconciliation and a `渲染残留自检` line; open the HTML, switch 提示词类型 / 平台 / 主题, open a few Prompt details and runs.

## Config

| Field | Meaning |
|---|---|
| `target`, `competitors` | `name / aliases / official_domains`. Exactly 3 competitors (the presales template's slots); take the answer layer's top three |
| `open_brands` | Every other brand in the answers. Agencies compete for the same buyer action: list them with their corporate domain so their pages count as 竞品网站 (an individual agent's own site stays 其他). Social groups (Facebook, Telegram) and media sites are not brands — leave them out (Suda 2026-10-21) |
| `compare_brands` | Brands in each Prompt's comparison table (may include open brands) |
| `runs`, `region` | Round directories and the region folder inside them |
| `questions_csv`, `bank_json` | `query / question_zh / topic / question_id`; the bank gives each Prompt's type (`intent`, or `prompt_type`) |
| `topic_labels`, `platform_labels` | Display names; Google's answer box is 「AI Overviews」 |
| `case_sensitive_aliases` | Abbreviations that collide with words (ERA); list every accepted casing (lyf / Lyf / LYF) |
| `multi_label_suffixes` | e.g. `gov.sg`, so each agency counts as its own domain |
| `competitor_site_domains` | Same-category platforms counted as 竞品网站 beyond the configured brands |
| `domain_categories` | `ugc / media_review / press_release / institutional` domain lists |
| `sentiment` | `{units, claims, metrics}` paths; ignored until all three exist |
| `translations` | Folder of `batch-*.zh.json` |
| `hide_sections` | Module ids to hide with their nav link, e.g. `opportunities` (05 内容规划) until content work starts. Modules with no data are hidden without being listed here: `distribution` (04 情感) when sentiment is not attached, `sources` (03 引用) when no answer cites anything. Remaining modules are renumbered in order (Suda 2026-10-22) |
| `title`, `out_dir`, `out_name` | Page title and output |

## What the page shows

- **Filters** above 核心洞察, acting on every module: 提示词类型 × 平台 × 主题. Every formal Prompt counts in the baseline report, named-brand ones included (Suda 2026-10-20); choose 发现 for natural visibility.
- **01 KPI row**: 提及率 / 提及率排名 / 声量份额 / 平均提及位置 / 引用份额 / 引用率. Labels never say 官网引用份额 / 官网引用率; tooltips never say 「可见度问题」.
- **02 可见度**: presales modules; the platform × brand matrix has logos.
- **03 引用**: every 引用份额 is paired with 引用率 (answers citing that source at least once ÷ valid answers) — official pages, source categories, domains, pages; URLs on one line, full on hover; no top-N cut. **The whole module and the KPI-row 引用份额 / 引用率 count Discovery and Category Awareness answers only** (Profound ch4, adopted 2026-10-22: "scope your citation analysis to discovery prompts" — a Prompt that names a brand pulls that brand's own pages into the citations and inflates its share). Named-brand types (Competitor, Alternatives, Evaluation, Verification, Accuracy) are excluded from these aggregates and read citation-wise only in 问题明细 and the Prompt detail, where every type still shows its own per-Prompt 引用份额.
- **04 情感**: the brand's pooled positive share (positive signals ÷ all signals, no cross-platform equal-weight line), competitor shares and the theme × brand matrix whose cells show the top attribute phrase; themes where no shown brand has a signal are dropped.
- **问题明细**: one row per Prompt with the brand's 提及率 / 提及率排名 / 声量份额 / 平均提及位置 / 引用份额 / 引用率; Topic rows read the Topic slice's pooled value, never an average of Prompt rows. No inline expansion, no extra columns. Its own 提示词类型 and 平台 dropdowns (the 平台 dropdown moves the page filter).
- **查看 (Prompt detail)**, top to bottom (Suda 2026-10-22, a simplified take on Profound's Prompt page):
  1. Question, Chinese meaning, topic and type tags; a platform filter at the top right that drives everything below.
  2. 品牌对比 — 提及率 / 提及率排名 / 声量份额 / 平均提及位置 / 引用份额 / 正向情感占比 for the brand, `compare_brands` and the Prompt's most-mentioned brand; sorted by mentions, unmentioned brands last as 「未提及」; logo and name aligned.
  3. Brand's per-platform readings (全部平台 only).
  4. Query Fan-outs — ChatGPT `search_model_queries`, Gemini `related_queries`, with counts; an empty state when the collection returned none.
  5. 回答记录 — one row per run: 平台, 采集时间 (the collection file's time; the payload has none), brand mentioned, brands named, 引用份额, 操作. No 「第 n 次」.
  6. A run's answer: only 「← 返回列表」 on top; meta shows 平台 · 采集时间; 中文译文 / 回答原文 tabs; 品牌提及 (all same-category brands; empty state 「这次回答没有提到任何同类平台或竞品」), 品牌情感 (all brands; empty state 「这次回答没有对品牌的明确褒贬」), citations, search sources.

## 优化顺序 (Suda 2026-10-23)

The five competition patterns moved here from the client Base, where the seven-value 竞争格局 field was replaced by 信源壁垒 (待判 / 来源追不上 / 无). They are computed per formal Prompt from the formal baseline (30 runs per query × platform × country × language), pooled across platforms, and used to order optimisation work. They never change the selection 优先级 (属性池 attribute tier, 提示词库 建议优先级/优先级).

Applies to Discovery and Alternatives Prompts only; named-brand types put the brand in the question and would always read as mentioned. Let t = the brand's mention rate on the Prompt and L = the highest rate among the other brands named as candidates:

| Pattern | How to tell | Place in the optimisation order |
|---|---|---|
| 部分出现仍落后 | t > 20% and L − t ≥ 30 points | First within the tier — closest to winning |
| 竞品领先（引用以竞品官网为主） | t ≤ 20%, L − t ≥ 30 points, citations mostly competitor official pages | Next — write the equivalent on the brand's own site |
| 竞品领先（引用以第三方为主） | Same, citations mostly review sites, communities, trade media | Next — reachable, but off-site work takes longer |
| 无品牌点名 | t ≤ 20% and L − t < 30 points | Next — an open slot; first confirm the wording asks for candidates |
| 已打平或领先 | t > 20% and L − t < 30 points | Last — the job is to hold; monitoring continues unchanged |
| 来源追不上 | The Base 信源壁垒 is 来源追不上 (re-checked on these answers) | Already one tier down in the Base; within its tier, last |

Order: tier (提示词库 优先级, which already carries the 来源追不上 drop) → pattern as above → 相对竞品 (领先 before 持平). Content effort is not a key; changeability already sits in the tier. The thresholds (20%, 30 points) were set on Hbrand's 15 answers per Prompt; with 30 runs per cell a 50% reading carries roughly ±18 points per platform (1.96 × √(p(1−p)/n)), so a Prompt within a few points of a threshold is reported with both neighbouring patterns rather than forced into one. Show the pattern and the order in 问题明细, **and write the computed order back into the client Base as the 提示词库 优化顺序 text column** (Suda 2026-10-26, reversing the 2026-10-23 report-only rule): one value per Prompt, 「第 N 档（优先级 · pattern · 相对竞品）」, one line per market when the row spans markets. Only this derived order is written back — the patterns' inputs (t, L, citation mix) stay in the report, and the selection 优先级 is never rewritten.

## Display rules

- Zero reads 「0%」, never 「0.0%」. A run with no citations reads 「无引用」 (its 引用份额 has no denominator); 「—」 is kept for values with no denominator, e.g. 声量份额 when no brand was mentioned, or a topic made only of named-brand Prompts whose citation aggregates under 全部类型 have no eligible answers (its per-Prompt rows still show).
- Citation pills show the full source name and number (the presales style cut them at 120–180 px), link to the run's own citation, and are restored as pills in the translation.
- Answer HTML is cleaned of crawler leftovers: empty-target images, empty links, `[text](<url>)`, `---`, ChatGPT widget residue (`:::writing`, `{#each}`, `{@body}`, `<Entity value=…>`), LaTeX (written as × ÷ ≥ ≈), double-escaped entities and markdown escapes. Translated tables (flattened to `a | b |` lines) are rebuilt as tables; heading-style `1.` lines keep their own numbers. The remaining few hits in 渲染残留自检 are answers the crawler cut off mid-markup.
- Payload is gzipped into the page and unpacked in the browser; Hbrand with 5 runs' answers and translations is about 6 MB (15 MB uncompressed, which the app side panel could not open).

## Definitions

声量份额 counts answers (one brand once per answer). 提及率排名 is the competition rank by mention count among every lexicon brand, unranked when not mentioned. 引用份额 = citations to the brand's official domains ÷ all citations, not de-duplicated. 引用率 = answers citing the official site at least once ÷ valid answers; never converted to or from 引用份额. 正向情感占比 = positive Claim signals ÷ (positive + negative), one signal per answer × brand × claim.

## Known gaps

- Hbrand 2026-10-21: ChatGPT `search_model_queries` was empty in all 380 answers and Gemini returned related questions in 11 of 380, so Query Fan-outs is mostly empty. Confirm the collector returns ChatGPT search queries before the next baseline.
- Not in the report: 推荐率, 决胜率 (ad-hoc for comparison Prompts), 事实准确率 (retest table), Shopping GEO.
