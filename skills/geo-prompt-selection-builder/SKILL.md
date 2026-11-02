---
name: geo-prompt-selection-builder
description: Build or maintain evidence-backed GEO prompt selection (选词) — confirm the business scope, research buyers, build the attribute pool, audiences and core usage scenes, the prompt matrix with business importance, Topics (the purchase intents we sell) with Topic priority, write Prompts, read the 3-run trial, and help the brand party pick and lock the formal set; later add, merge or retire Prompts. Use for the presales word-selection tool and for ongoing monitoring-set maintenance; do not use for the early presales diagnosis bank (geo-presales-prompt-builder), running baselines, collection or baseline reports (geo-monitoring), defining metric calibers, written report conclusions, or automatic competitor discovery.
metadata:
  author: Overseas GEO Project
  version: "2.4.0"
---

# GEO Prompt Selection Builder（选词）

选词决定测哪些题：从业务范围和买家调研出发，梳理属性、受众与场景，画提示词矩阵，聚成主题（我们卖的购买意图），写题，读试跑结果，由品牌方挑正式题并锁版；签约后补、并、停题。跑基线、按期采集、出报告归 `geo-monitoring`。它也是写题规则的唯一来源，`geo-presales-prompt-builder` 引用本 skill 的写题规则与门禁。

**规则全文在 [references/selection-rules.md](references/selection-rules.md)，按下面 9 步分节。开始任何一步前先读对应一节。**

## 9 步

| 步 | 做什么 | 按什么判断 | 产出 |
|-|-|-|-|
| 1 | 确认业务范围 | 品牌方先填，我们核对；问品牌方最希望解决哪些 AI 搜索问题，默认只做发现型可见度，其他目标看证据再出 | 业务范围表 |
| 2 | 调研 | 先预跑（品类认知 ＋ 品牌和竞品评价，各平台 1 次），再查公开资料和品牌方数据 | 买家原话表、预跑答案 |
| 3 | 属性池 | 收得宽；只判相对竞品；记常见约束和品牌取值 | 属性池表、品牌事实核查表 |
| 4 | 受众与核心使用场景 | 受众按改不改变候选来拆并；场景只列有证据、品牌在竞争的 | 业务范围里的受众行和场景行，交品牌方确认后冻结 |
| 5 | 提示词矩阵与业务重要性 | 一行 ＝ 产品线 × 市场 × 受众 × 场景 × 旅程阶段（需求认知 / 方案考虑 / 购买决策），挂这一行看重的属性；核心受众 × 核心场景 × 三段都过一遍，买家会在这个处境问 AI 就开行（没证据标假设），组合本身不成立才不开，不看目标；每行判业务重要性，高 / 中出题、低不出 | 提示词矩阵表 |
| 6 | 主题与主题优先级 | 要出题的行按核心购买需求聚合；能独立交付才单开；高 ＝ 有业务重要性为高的行，中 ＝ 有搜索需求，低 ＝ 都弱 | 主题表 |
| 7 | 写题 | 一道题 ＝ 一行 × 一条属性 × 一种类型，以发现为主，其他类型按品牌方选的目标和证据出；出不出、出几道只看 selection-rules 第 7 步类型表 | 提示词库、题库 JSON |
| 8 | 试跑 | 每题每个监测平台 3 次；判题是否合格和可改变性；验证题只在试跑后按 selection-rules 第 8 步的条件触发；品牌读数不进选题 | 回写提示词库、试跑报告 |
| 9 | 选正式题、锁版 | 品牌方按主题挑，每主题最多 10 道；不按单题读数挑；锁考核口径 | 正式题集版本、上传 CSV |

**接手售前选词时**：售前每个市场留一份 `bank.json` 和 `notes.md`（`run_selection_mode.py` 工作目录的 `out/`）。买家原话、属性、矩阵行、主题照收，用品牌方的业务目标重判业务重要性，用品牌方数据复核属性池；`notes.md`「预跑答案」里的答案直接用，不重跑，「未覆盖来源」补采。售前与选词的分工见 `../shared/prompt-generation-principles.md` → 售前与售后的边界。

**维护已有题集**：先判断这次是新增、改写、合并还是停测，保留旧题号和证据；规则见 selection-rules.md → 维护。

## 交付

1. 对客确认表（飞书多维表格）：表和字段见 [references/client-facing-attribute-pool.md](references/client-facing-attribute-pool.md)。
2. 题库 JSON：字段和门禁见 [references/output-contract.md](references/output-contract.md)。
3. 上传 CSV：`python3 -I scripts/export_upload_csv.py <bank.json> --out <dir>`，九列模板，一个市场一个文件。

附 validator 结论一行和告警处理记录（`config.warning_decisions`）。

## 边界

- 售前诊断题库（一次性、只用公开证据、最多 60 题）用 `geo-presales-prompt-builder`，它沿用本 skill 的写题规则。
- 不定义指标口径（`geo-presales-report-editor` core）、情感规则（`geo-presales-sentiment-judge`），不采集、不跑基线、不出报告（`geo-monitoring`），不自动发现或冻结竞品（`overseas-geo-competitor-research`）。
- 没有任何买家信号时，可以先出一版标明「假设」的题集，列出还要品牌方确认的证据；不能进正式基线，不能把模型联想说成高频需求。这条说的是整份题集都没有买家信号；单个标了假设的矩阵行上的题，经品牌方批准可以进正式题，见 selection-rules.md → 5。

## 参考与脚本

| 文件 | 什么时候读 |
|-|-|
| [references/selection-rules.md](references/selection-rules.md) | 每一步 |
| [references/client-facing-attribute-pool.md](references/client-facing-attribute-pool.md) | 建或改对客确认表 |
| [references/output-contract.md](references/output-contract.md) | 写题库 JSON、跑 validator |
| [references/signal-sources.md](references/signal-sources.md) | 第 1、2 步：向品牌方要什么数据、自己去哪收 |
| [references/community-channels.md](references/community-channels.md) | 第 2 步：每个站点用什么通道取数 |

| 脚本 | 用途 |
|-|-|
| `scripts/validate_after_sales_set.py <bank.json> [--previous <旧版>]` | 题库门禁，输出就绪结论 |
| `scripts/write_prompt_reasons.py --base <token> --brand <品牌> --noun <品类名词>` | 往提示词库写优先级和出题原因 |
| `scripts/check_client_base.py --base <token> [--template]` | 对客确认表发出前检查 |
| `scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` | 增量部署前后对账，0 差异才算部署完 |
| `scripts/changeability_domains.py --bank <bank.json> --collect <试跑目录> --out <dir> [--official …] [--competitor-domain …] [--community-domain …] [--write]` | 试跑后按引用前 20 域名预判可改变性，人工复核 |
| `scripts/export_upload_csv.py <bank.json> --out <dir>` | 导出上传 CSV |
| `scripts/check_skill_terms.py` | 维护本 skill 时扫已退役说法 |

## 维护本 skill

改任何规则后跑 `python3 -I scripts/check_skill_terms.py`（扫本 skill、`geo-monitoring` 和 `shared/canonical-intent-mapping.md` 的退役说法）、validator 测试 `python3 -m pytest -q scripts/test_validate_after_sales_set.py` 和 `python3 -I evals/verify_workflow.py`，三者都通过才算改完。退役一个说法时，同一次改动把它加进扫描清单。规则的修订历史记在 [CHANGELOG.md](CHANGELOG.md)，正文只写现在的规则。
