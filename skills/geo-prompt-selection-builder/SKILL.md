---
name: geo-prompt-selection-builder
description: Build or maintain evidence-backed GEO prompt selection (选词) — confirm the business scope, run the research pre-run, collect demand signals, organize constraints (约束条件), target customers (目标客户) and use scenarios (使用场景), draw the prompt matrix (target customer × use scenario × intent type, 意图类型) with business priority per row, cluster Topics (the purchase intents we sell) with Topic priority, write Prompts (currently Discovery-visibility only), validate and export — as a Feishu client-confirmation Base, as 9-field upload rows, or both; later add or merge Prompts. Input is either the brand party's business scope or their brand intake (品牌资料: online form data or a file, normalized by scripts/normalize_case.py); scripts/run_selection_mode.py runs one brand intake × market unattended end to end. Use for presales Prompt generation (售前生词), the presales word-selection tool and monitoring-set maintenance; do not use for the 3-run trial, picking or locking the formal set, retiring formal Prompts, baselines, collection or reports (geo-monitoring), defining metric calibers, or written report conclusions.
metadata:
  author: Overseas GEO Project
  version: "3.3.4"
---

# GEO Prompt Selection Builder（选词）

选词生成要测的题：从业务范围（或一份品牌资料）和买家调研出发，梳理约束条件、目标客户与使用场景，画提示词矩阵，聚出主题（我们卖的购买意图），写题，校验后导出；签约后补题、并题。售前生词也用本 skill。到导出为止：试跑判读、品牌方挑正式题、锁版、正式题停测，以及跑基线、按期采集、出报告，都归 `geo-monitoring`。

**规则全文在 [references/selection-rules.md](references/selection-rules.md)，按下面 8 步分节；下表只是索引，判断标准以对应一节为准，开始任何一步前先读那一节。线上无人值守跑一份品牌资料时，先读 [references/online-runner.md](references/online-runner.md)，它只写和本地不一样的地方。**

## 8 步

| 步 | 做什么 | 按什么判断 | 产出 |
|-|-|-|-|
| 1 | 确认业务范围 | 品牌方先填，我们核对（线上用品牌资料代替，见 online-runner.md）；目前只做发现型可见度 | 业务范围表 |
| 2 | 调研 | 先预跑品类认知（品牌、竞品评估按需补跑），再收四类需求信号，看品牌官网和 3 家竞品官网；官网和模型联想只开假设级候选 | 需求信号表、预跑答案、品牌能力清单 |
| 3 | 约束条件 | 收得宽、统一粒度；不判重要性和相对竞品，只记品牌可核实的明显劣势；写题前确认硬条件 | 三张表共用的「约束条件」选项、品牌明显劣势记录 |
| 4 | 目标客户与使用场景 | 按改不改变候选来拆并；只多看一条条件的挂成约束条件 | 业务范围里的目标客户行和使用场景行，品牌方确认后冻结 |
| 5 | 提示词矩阵与业务优先级 | 一行 ＝ 产品线 × 市场 × 目标客户 × 使用场景 × 意图类型；只开成立的行；每个发现行判一次业务优先级，这是全流程唯一的档位判断，非发现行只登记、不判档 | 提示词矩阵表 |
| 6 | 主题与主题优先级 | 主题 ＝ 同一类候选 × 同一意图类型；按主题售卖，每个发现主题至少 10 题；主题优先级取组内最高的业务优先级，不另判，同档按点名条目序号排 | 主题表、`config.tag_dimensions` |
| 7 | 写题 | 本期只在高、中档发现行上出题；按决策差异定题数；问不出发现题的行改类型 | 提示词库、题库 JSON |
| 8 | 校验与导出 | validator 错误全改、告警逐条记处理；按场景导出。试跑、挑题、锁版归 `geo-monitoring` | 题库 JSON、对客确认表和 / 或上传 CSV |

**接手线上生成的题库时**：线上每个市场留一份 `bank.json` 和 `notes.md`（`run_selection_mode.py` 工作目录的 `out/`），按 online-runner.md「交给本地选词接着做」继续。

**维护已有题集**：本 skill 只管加题和并题，保留旧题号和证据（selection-rules.md → 维护）；正式题停测、改措辞开新题号见 `geo-monitoring/references/trial-and-lock.md`。

## 交付

题库 JSON 是唯一底稿（字段和门禁见 [references/output-contract.md](references/output-contract.md)），从它导出，两种可以都要：

1. 对客确认表（飞书多维表格）：要品牌方看和改时用，表和字段见 [references/client-facing-base.md](references/client-facing-base.md)。
2. 上传 CSV / 接口行：`python3 -I scripts/export_upload_csv.py <bank.json> --out <dir>`，九列模板，一个市场 × 一条产品线一个文件，每个文件最多 60 条；线上一条命令跑（`scripts/run_selection_mode.py`）只交这一种。

附 validator 结论一行和告警处理记录（`config.warning_decisions`）。

## 边界

- 不试跑、不挑正式题、不锁版、不停测正式题，不采集、不跑基线、不出报告（都归 `geo-monitoring`）；不定义指标口径（`geo-metrics`）、情感规则（`geo-presales-sentiment-judge`）。
- 竞品用品牌方在品牌资料里填的，不冻结、不自己增删；试跑后按答案补哪几家归 `geo-monitoring`。
- 没有任何买家信号时，可以先出一版标明「假设」的题集，列出还要品牌方确认的证据；不能进正式基线，不能把模型联想说成高频需求。这条说的是整份题集都没有买家信号；单个标了假设的矩阵行上的题，经品牌方批准可以进正式题，见 selection-rules.md → 5。

## 参考与脚本

脚本和 evals 除两个可选包外只用标准库。需要语种门禁或 `--agent sdk` 时先 `python3 -m pip install -r requirements.txt`（要求 Python ≥ 3.12）：缺 `lingua-language-detector` 时语种检查跳过并给 W32 告警；`claude-agent-sdk` 只有 `--agent sdk` 用到，走 `--agent-cmd` 或自己写 `bank.json` 不用装。

| 文件 | 什么时候读 |
|-|-|
| [references/selection-rules.md](references/selection-rules.md) | 每一步 |
| [references/type-branches.md](references/type-branches.md) | 发现以外七类：开行条件、对应目标、出几道、题面写法；业务优先级上限开放对应目标时才启用 |
| [references/client-facing-base.md](references/client-facing-base.md) | 建或改对客确认表；线上不建表，不用读 |
| [references/output-contract.md](references/output-contract.md) | 写题库 JSON、跑 validator |
| [references/signal-sources.md](references/signal-sources.md) | 第 1、2 步：我方自己去哪收搜索数据、评价和社区 |
| [references/demand-side-signals.md](references/demand-side-signals.md) | 第 1、2 步：向品牌方要什么数据、拿到后怎么用；线上没有品牌方资料，不用读 |
| [references/community-channels.md](references/community-channels.md) | 第 2 步：每个站点用什么通道取数 |
| [references/online-runner.md](references/online-runner.md) | 线上无人值守跑一份品牌资料：和本地不一样的几步、没有浏览器怎么办 |
| [references/input-contract.md](references/input-contract.md) | 品牌资料输入合同：字段、必填、错误码（给接入方） |

| 脚本 | 用途 |
|-|-|
| `scripts/validate_after_sales_set.py <bank.json> [--previous <旧版>]` | 题库门禁，输出就绪结论；旧结构题库报「不支持」并退出 |
| `scripts/write_prompt_reasons.py --base <token> --bank <bank.json> --brand <品牌> --noun <品类名词>` | 往提示词库写出题原因和提示词优先级 |
| `scripts/check_client_base.py --base <token> [--template]` | 对客确认表发出前检查 |
| `scripts/diff_base_against_spec.py --base <token> --spec <spec.json>` | 增量部署前后对账，0 差异才算部署完 |
| `scripts/normalize_case.py <payload.json> [-o <out>]` | 品牌资料校验与归一化（线上表单数据或品牌资料文件，字段同《品牌资料收集》第一部分） |
| `scripts/run_selection_mode.py run --case <payload.json> --market <市场> --platforms <平台> --out <新目录> --agent sdk` | 线上一条命令跑完一个品牌 × 市场，检查不过自动返修，过了再按 review-rubric.md 审核一轮，见 online-runner.md |
| `scripts/export_upload_csv.py <bank.json> --out <dir>` | 导出上传 CSV |
| `scripts/write_tags.py --base <token> --bank <bank.json> [--write]` | 把切片标签写进提示词库「标签」列 |
| `scripts/check_skill_terms.py` | 维护本 skill 时扫已退役说法 |
| `../shared/scripts/cost_report.py <目录> … [--since <日期>]` | 按客户汇总选词轮、采集和 DataForSEO 花费，算平均每客户；单价读本机 `~/.geo-cost/prices.json` |

## 维护本 skill

动手前先读 [CHANGELOG.md](CHANGELOG.md) 最新版本号：比你会话里拿到的版本新，说明另一会话改过，先对账再改。还在讨论、当天可能翻转的判法先放 `30-选Topic与生词/方案/` 讨论稿，拍板后再进正文。改任何规则后跑 `python3 -I scripts/check_skill_terms.py`（扫本 skill、`geo-monitoring` 和 shared 两份文档的退役说法）、validator 测试 `python3 -m pytest -q scripts/test_validate_after_sales_set.py` 和 `python3 -I evals/verify_workflow.py`，三者都通过才算改完；动了品牌资料输入或线上入口的，再跑 `python3 evals/e2e_input_contract.py`、`python3 evals/e2e_repair_loop.py` 和 `python3 evals/e2e_review_loop.py`；动了语种检查的，再跑 `python3 evals/e2e_language_check.py`。validator 的语种检查依赖 `lingua-language-detector`（在 `requirements.txt` 里），没装时跳过并给 W32 警告。退役一个说法时，同一次改动把它加进扫描清单。规则的修订历史记在 [CHANGELOG.md](CHANGELOG.md)，正文只写现在的规则。
