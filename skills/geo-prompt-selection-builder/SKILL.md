---
name: geo-prompt-selection-builder
description: Build or maintain evidence-backed GEO prompt selection (选词) — confirm the business scope, run the research pre-run, collect demand signals, organize buyer constraints, audiences and purchase tasks, draw the prompt matrix with business priority per row, cluster Topics (the purchase intents we sell) with Topic priority, write Prompts (currently Discovery-visibility only), read the 3-run trial, and help the brand party pick and lock the formal set; later add, merge or retire Prompts. Use for the presales word-selection tool and for ongoing monitoring-set maintenance; do not use for the early presales diagnosis bank (geo-presales-prompt-builder), running baselines, collection or baseline reports (geo-monitoring), defining metric calibers, written report conclusions, or automatic competitor discovery.
metadata:
  author: Overseas GEO Project
  version: "2.40.1"
---

# GEO Prompt Selection Builder（选词）

选词决定测哪些题：从业务范围和买家调研出发，梳理买方约束、受众与购买任务，画提示词矩阵，聚出主题候选（我们卖的购买意图），写题后定稿主题，读试跑结果，由品牌方挑正式题并锁版；签约后补、并、停题。跑基线、按期采集、出报告归 `geo-monitoring`。它也是写题规则的唯一来源，`geo-presales-prompt-builder` 引用本 skill 的写题规则与门禁。

**规则全文在 [references/selection-rules.md](references/selection-rules.md)，按下面 9 步分节。开始任何一步前先读对应一节。**

## 9 步

| 步 | 做什么 | 按什么判断 | 产出 |
|-|-|-|-|
| 1 | 确认业务范围 | 品牌方先填，我们核对；按目标和买家需求出题，预跑正负面表现不决定准入 | 业务范围表 |
| 2 | 调研 | 先预跑（品类认知 ＋ 品牌和竞品评价，各平台 1 次），再查公开资料和品牌方数据；看品牌官网卖什么、卖给谁、在哪卖、能做到什么，整理品牌能力清单；3 家竞品官网轻量看三个问题（服务谁、强调什么条件、暴露哪些买家问题），只当线索、要找买家信号 | 需求信号表、预跑答案、品牌能力清单 |
| 3 | 买方约束 | 收得宽、统一粒度（一条 ＝ 买家比较选项的一个维度，买家任务写成矩阵行）；不判重要性、不逐条判相对竞品，只记品牌有可核实明显劣势的几条；写题前确认硬条件 | 三张表共用的「买方约束」选项、品牌明显劣势记录 |
| 4 | 受众与购买任务 | 受众按改不改变候选来拆并；购买任务是买家在找什么、要定什么，换了任务候选或起作用的约束会变，只多看一条约束的挂成约束 | 业务范围里的受众行和购买任务行，交品牌方确认后冻结 |
| 5 | 提示词矩阵与业务优先级 | 一行 ＝ 产品线 × 市场 × 受众 × 购买任务 × 提示词类型，标上旅程阶段（需求认知 / 方案考虑 / 购买决策，按类型取默认值、可改），挂这一行看重的买方约束；发现行用核心受众 × 购买任务查漏，只开真实存在、决策不同、有合理需求依据的行（没证据标假设）；替代、对比、评价、问题解决行有证据或合理假设才开，档位默认跟同任务的发现行；范围外、没依据、品牌做不到又没服务路径的不开，记进 notes「没开的格子」；每行判一次业务优先级：一类买家需求对品牌的商业价值、战略重要性和当前业务重点的贡献（Aleyda），不打分、不看证据多少、强弱、阶段；高 / 中出题，低默认不出 | 提示词矩阵表 |
| 6 | 主题与主题优先级 | 在本期产品线范围内按核心意图和解决方案范围划分主题，一条产品线可以有多个主题；三个条件：核心意图一致（买家想拿到同一类结果）、解决方案范围相近为必要，合并后读数能说清哪类需求要优化为验证；产品类型、客群、场景要有需求和试跑证据才拆，品牌方要独立监测时可单拆；不因购买任务相同就放一起；看板没有类型字段，一个主题只放一种提示词类型，其他类型按决策＋类型开主题、不够 5 题跨决策合成类型主题；属性、场景、购买条件写成主题内的题；先把要出题的行聚成主题候选，第 7 步写完候选题后定稿、试跑后按候选集合复核；品牌能合理满足任务就出题，不要求同一产品形态；买方约束和问法不单开主题；每主题至少 5 题、不设上限，不足时按补需求 → 复合条件 → 查过细的顺序处理，题数不判断粗细；主题优先级默认取组内多数行的业务优先级（没有多数时人工判断），同档按搜索量排先后；优先级差异不作为拆主题的依据；要跨主题切数据的维度（多为受众、主推卖点）登记成切片标签，主题的切分轴不做标签 | 主题表、`config.tag_dimensions` |
| 7 | 写题 | 一道题表达一个完整购买任务，关联矩阵行和相关买方约束，类型就是所在行的类型；本期只做发现型可见度，只在发现行上出题，其他类型的行留待以后开放；写题时逐题判断能不能自然问出发现题，问不出的把这一行改成对应类型；出几道看 selection-rules 第 7 步类型表；题面条件落在品牌明显劣势里的，出题原因写风险提示，不降档 | 提示词库、题库 JSON |
| 8 | 试跑 | 每题每个监测平台 3 次；判题是否合格（点名品牌少的题用脚本先筛），记录信源结构与动作假设；零提及时可临时点名核查，记录在题库之外；品牌读数不进选题 | 回写合格判断、试跑报告、独立诊断记录 |
| 9 | 选正式题、锁版 | 品牌方按业务优先级和增量覆盖挑题，同档按覆盖、质量、代表性挑，每条产品线 × 国家 × 语言合计最多 60 道、单主题不设上限；锁考核口径 | 正式题集版本、上传 CSV |

**接手售前选词时**：售前每个市场留一份 `bank.json` 和 `notes.md`（`run_selection_mode.py` 工作目录的 `out/`）。需求信号、买方约束、矩阵行、主题照收，用品牌方填的核心目标客户与购买场景重判业务优先级，用品牌方数据复核买方约束；`notes.md`「预跑答案」里的答案直接用，不重跑；售前预跑只有品类认知题，品牌和竞品评价题要用时补跑；「未覆盖来源」补采。售前与选词的分工见 `../shared/prompt-generation-principles.md` → 售前与售后的边界。

**维护已有题集**：先判断这次是新增、改写、合并还是停测，保留旧题号和证据；规则见 selection-rules.md → 维护。

## 交付

1. 对客确认表（飞书多维表格）：表和字段见 [references/client-facing-base.md](references/client-facing-base.md)。
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
| [references/type-branches.md](references/type-branches.md) | 本期不出的替代、对比、评价、问题解决四种类型的规则；未来开放时看 |
| [references/client-facing-base.md](references/client-facing-base.md) | 建或改对客确认表 |
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
| `scripts/trial_brand_count.py --bank <bank.json> --collect <试跑目录> --out <dir> [--lexicon <品牌词表>]` | 试跑后数发现、替代题答案点了几个品牌，标出点名品牌少的题，人工判原因 |
| `scripts/export_upload_csv.py <bank.json> --out <dir>` | 导出上传 CSV |
| `scripts/write_tags.py --base <token> --bank <bank.json> [--write]` | 把切片标签写进提示词库「标签」列 |
| `scripts/check_skill_terms.py` | 维护本 skill 时扫已退役说法 |

## 维护本 skill

动手前先读 [CHANGELOG.md](CHANGELOG.md) 最新版本号：比你会话里拿到的版本新，说明另一会话改过，先对账再改。还在讨论、当天可能翻转的判法先放 `30-选Topic与生词/方案/` 讨论稿，拍板后再进正文。改任何规则后跑 `python3 -I scripts/check_skill_terms.py`（扫本 skill、`geo-monitoring`、`geo-presales-prompt-builder` 和 shared 两份文档的退役说法）、validator 测试 `python3 -m pytest -q scripts/test_validate_after_sales_set.py` 和 `python3 -I evals/verify_workflow.py`，三者都通过才算改完。退役一个说法时，同一次改动把它加进扫描清单。规则的修订历史记在 [CHANGELOG.md](CHANGELOG.md)，正文只写现在的规则。
