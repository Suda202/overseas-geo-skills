# 售后基线报告（试跑、正式基线）

2026-11-20 起售前诊断报告和售后基线报告是同一套 HTML（Suda：「HTML 都一样，归 geo-presales-report-builder」）。基线报告不另写渲染，口径、模块、筛选、问题明细、抽屉、译文和情感都和售前报告相同，见 [render-spec.md](render-spec.md)。两者只有三处不同，都写在 Case 里，由 `scripts/prepare_baseline.py` 生成：

| 不同处 | 售前诊断 | 售后基线 |
|---|---|---|
| `报告类型` | 售前诊断（缺省） | 正式基线；试跑写「试跑」 |
| `报告标题` | 缺省「海外 AI 搜索可见度售前诊断」 | config.title |
| 每题次数 | 通常 1 次 | 多轮采集合成 `NNNN-rKK.json`，抽屉的回答记录逐次列出 |

基线结果只出 HTML，不写进多维表格（Suda 2026-10-21）：Base 仪表盘只能 SUM / AVG / MAX / MIN，不能跨行相除，每个比率都得按筛选组合预算，仪表盘级筛选也不能用 API 建。Base 只留品牌方要确认或修改的内容。

## 流程

1. **采集**（`geo-monitoring`）：每轮一个目录（`collect_r1` … `collect_rN`，`scraper.<平台>/<市场>/NNNN.json`，NNNN 是采集用 CSV 的行号），每轮跑 `audit_crawl_integrity.py`。
2. **准备输入**：在客户售后目录运行

   ```bash
   python3 -I <项目根>/.agents/skills/geo-presales-report-builder/scripts/prepare_baseline.py --config baseline-html.json --run
   ```

   把 N 轮合成 `out_dir/collect`（地区层是真实市场，文件 `NNNN-rKK.json`，补上题面），写 `questions.csv`（题库的真实意图类型）、`case.json`、`lexicon.json`，然后调 `run_pipeline.py` 跑到下一个暂停点。不带 `--run` 只生成输入并打印命令。
   **基线报告默认只出核心洞察、可见度、引用和问题明细**（Suda 2026-11-27）。购物商品卡、情感、竞争与优化难度、诊断与行动四块默认不出：商品卡默认按 `--shopping-cards 关` 处理；情感要人工抽 Claim、聚类，难度和诊断是「先优化什么」的判断，归缺口诊断服务。要出时在 config 的 `extra_modules` 里写 `"shopping"`、`"sentiment"`、`"difficulty"`、`"diagnosis"`：
   - `difficulty`：同一步调 geo-gap-diagnosis 的 `layer_readings.py` + `difficulty.py`，结果在 `out_dir/difficulty/`，用 `--difficulty` 接进报告（说法规则见 render-spec.md 同名一节）；config 写了 `changeability` 才判「只改官网能不能改变」。
   - `sentiment`：把展示品牌传给 `--brands`，流水线进情感暂停点。
   - `diagnosis`：还要 config 写 `diagnosis`（diagnosis.json 路径）。
3. **后面全按售前流水线**：采集校验 → 词表查漏 → 数据生成（`--source-limit 0`，引用榜单全量）→（开了情感才有：情感 Claim 与两趟聚类）→ 译文 → 独立校验 → 引擎对账 → 渲染。每个暂停点的要求见 SKILL.md 执行流程；补齐后重跑同一条 `prepare_baseline.py --run`。输出文件名是 `<out_name>-正式基线报告.html`。

## config（baseline-html.json）

相对路径相对 config 所在目录。

| 字段 | 含义 |
|---|---|
| `target`、`competitors` | `name / aliases / official_domains`；竞品个数不限，写进 Case 的「竞品 N」 |
| `open_brands` | 回答里出现的其他同类品牌（写进词表时默认 `same_category: true`，难度和缺口诊断按它认同类；不是同类的写 `false`）。中介、代理公司和品牌争同一个买家动作，写上公司域名；社群（Facebook、Telegram 群）和媒体站不是品牌，不写（Suda 2026-10-21） |
| `compare_brands` | 情感统计的展示品牌（`extra_modules` 含 `sentiment` 时连同目标品牌传给 `--brands`）；缺省用全部竞品 |
| `runs`、`region` | 各轮采集目录、目录里的市场代码 |
| `questions_csv`、`bank_json` | 采集用的题库 CSV（`query / question_zh / topic / question_id`）和题库 JSON（取每题 `prompt_type`；停测题在 `config.retired` 里也认） |
| `topic_labels` | 主题展示名 |
| `case_sensitive_aliases` | 和普通单词撞车的缩写（ERA）；每种写法都列（lyf / Lyf / LYF），写进词表顶层 |
| `competitor_site_domains` | 配置品牌以外、算「竞品网站」的同类平台域名，写进词表顶层 |
| `multi_label_suffixes` | 必须已在 geo-metrics core 的 `COMMON_MULTI_LABEL_SUFFIXES` 里，不在就停 |
| `domain_categories` | 只做核对：和 geo-metrics 共享域名缓存（含内置表）不一致的会列出来。数据层只读共享缓存，要采用就写进 `geo-metrics/assets/domain-categories.json` |
| `allow_unjudged_domains` | 未判读引用超过 5% 时仍要出报告的理由 |
| `changeability` | 可改变性结果 changeability.csv（可选），给了优化难度才判只改官网能否改变 |
| `extra_modules` | 默认不出的模块要出时列在这里：`shopping` / `sentiment` / `difficulty` / `diagnosis`；缺省为空。旧字段 `"difficulty": false` 仍认（等于不列 difficulty） |
| `allow_lexicon_gaps` | 词表查漏不通过时仍要出报告的理由 |
| `report_kind`、`title`、`out_dir`、`out_name` | 报告类型（缺省「正式基线」）、标题、输出目录、文件名 |

旧字段 `platform_labels`、`hide_sections`、`sentiment`、`translations` 不再使用：平台名用数据层内置的，没数据的模块自动隐藏，情感和译文走流水线暂停点。2026-11-20 前做的情感与译文批次按「意图|平台」写键，和现在的「市场|平台」对不上，重出报告要重新导出。已交付的旧 HTML 照常有效。

## 平台自报参照（Suda 2026-11-04）

品牌方给了 GSC Generative AI Performance（近 3 个月 Impressions、Pages、Countries、Dates）或 Bing AI Performance（Cited Pages、Citations）时，原样存进客户基线目录，作为优化前的平台自报参照。

- 前后对比：后续每期取同样长度的时段，只比官网自己的展示量、被引页面数和引用量的变化方向。
- 交给内容：Bing Cited Pages 里已被 AI 引用的官网页面列给内容团队，优先在这些页上补事实。
- 不混算：不并进提及率、引用份额、引用率；GSC 这份没有查询词，对不到某道提示词。
- 不进 HTML，写在基线交付说明里。

## 已知限制

- ChatGPT 子查询形态随 `task_result.model` 变化：`gpt-6`（2026-10-29 起）只有一条关键词堆叠式宽查询、不带 `site:`，两代读数不可比。
- 可改变性和优化顺序是判断，不在这份报告里，规则在 `geo-monitoring/references/changeability-and-order.md`，缺口诊断归 `geo-gap-diagnosis`。
