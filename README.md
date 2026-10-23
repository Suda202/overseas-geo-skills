# 海外 GEO Skills

海外 GEO 的 11 个 Skill，分三段：**售前诊断**（建 Case 和题库，跑采集，出客户能看的 HTML 报告）、**选词**（定监测哪些题）、**监测**（跑正式基线，按期采集，出基线报告）。

一段之内按任务对号入座；交付给客户的东西只在报告层出现，口径与判读规则各只有一份实现。

## 三段怎么接

```text
品牌资料
  -> 售前诊断：Eval Case Builder 归一成 Case -> Prompt Builder 出 v8 题库
             -> collect_answers 采集 -> 完整性校验 -> 指标/情感/渲染 -> HTML 诊断报告
  -> 选词：业务研究 -> 属性池 -> Topic 与出题 -> 各平台试跑 3 次 -> 排序交客户选词 -> 锁版
  -> 监测：正式基线（每格 30 次）-> 按期采集 -> 基线 HTML 报告 -> 缺口方向交内容团队
```

售前负责发现机会、促成交；选词决定签下来之后长期测哪些题；监测负责把数跑出来并解释差距。三段共用同一套写题规则（在 `geo-prompt-selection-builder`）和同一套指标口径（在 `geo-presales-report-editor` 的 core）。

## 售前诊断：三个任务

前期工作完成后按手上的活选任务。最常见的是任务一——从爬虫数据一路出给客户看的完整 HTML 报告；任务二是它的前半段单独跑，只出指标数字；任务三处理已交付报告的修改。

### 前期工作：建 Case 和题库

三个任务都依赖两份输入——Case（品牌归一化档案）和 v8 题库。没有就先走这条链：

```text
品牌资料
  -> Eval Case Builder    品牌资料归一成 Case（含 2–3 个监测主题），写飞书 Base 与客户确认文档
  -> Prompt Builder       Case -> v8 英文监测题库
```

竞品核验可以单独跑（`overseas-geo-competitor-research`），也常在 Eval Case Builder 里一并完成：正式竞品不足 3 个或候选待核验时，Case Builder 会内部委派它联网核验并冻结 3 个处于同一购买集合的正式竞品。

### 任务一 · 从爬虫数据出完整 HTML 报告

前置：已完成前期工作，手上有 Case 和题库。
输入：第三方采集目录（`<collect>/scraper.<platform>/<REGION>/<NNNN>.json`）+ 题库 + Case。
输出：单文件 HTML 售前诊断报告（支持国家 / 平台 / 主题三层筛选），内含全部可见度、引用与情感指标。

采集本身用 `collect_answers.py`（本项目唯一的采集实现，默认 4 个平台，`--platforms all` 采 Scrapeless 支持的全部 8 个）；跑之前设 `no_proxy=api.scrapeless.com`，否则本机代理会掐断 HTTPS 握手。

一条命令跑到下一个暂停点，补齐后重跑同一命令续跑：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

`run_pipeline.py` 串起采集校验、词表冻结、指标计算、情感判读接入、翻译、渲染；确定性步骤自动跑，语义环节（词表冻结、Claim 判读、翻译）停下并提示补什么。链上各环节归属：

| 环节 | 谁负责 | 说明 |
| --- | --- | --- |
| 采集校验 | `geo-presales-crawl-integrity` | 先确认这份采集能不能用：分不清「正文明说品牌」和「只是被检索到」，提及率就会失真；有阻断缺陷不许往下算 |
| 指标 + 报告数据 + 渲染 | `geo-presales-report-builder` | 复用全库统一口径算可见度与引用类指标，渲染 HTML；不自己判情感，只把判读结果按切片汇总 |
| 情感判读 | `geo-presales-sentiment-judge` | 判读只有它做（Claim 抽取与集中规则都在它那里）；不提供 `--brands`/`--target` 时跳过，报告情感板块为 pending，正式交付不允许 |

要让 Agent 全程自动接管（到暂停点自动请对应 Skill 出场），用编排 Skill `geo-presales-pipeline`：它只定阶段顺序和暂停点分派，口径与实现仍全部在上面三个 Skill 里。

### 任务二 · 只要指标数字，不出报告

任务一的前半段单独跑：只算可见度与引用类指标（提及率、提及率排名、声量份额、平均提及位置、可见度、引用次数），产出报告数据文件，不渲染 HTML。

```bash
cd skills/geo-presales-report-builder
python3 scripts/build_report_data.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --out <输出>/report-data.json
```

两条注意事项与任务一相同：先跑 `geo-presales-crawl-integrity` 确认采集能用；必须补上 `--lexicon assets/brand_lexicon.<品类>.json --domain-cache assets/domain-categories.json`——**口径要求声量份额与提及率排名的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），省略时开放品牌不进指标，算出来的数不成立，不能当正式指标交付**。这两个文件用 `mine_brand_lexicon.py` 和 `collect_domain_candidates.py` 生成（见 [SKILL.md](skills/geo-presales-report-builder/SKILL.md) 步骤 2–3）。需要「正向情感占比」时另跑 `geo-presales-sentiment-judge`。

### 任务三 · 已有报告要修改

| 要改什么 | 用哪个 Skill |
| --- | --- |
| 品牌提及识别 / 正文首现排序有问题 | `geo-presales-report-audit`（先修底层） |
| 客户结论要改、要出上传 CSV | `geo-presales-report-editor`（在修好的底层上改结论） |

先用 Report Audit 把底层结果改对，再用 Report Editor 改结论；两者处理同一份报告的不同层次，可连用。

> 指标口径全库只有一份实现：Report Builder、Report Audit、Crawl Integrity 都直接引用它算数，自己不另写。位置和改动方式见文末「开发与维护」。

## 选词：定监测哪些题

`geo-prompt-selection-builder` 是写题规则的唯一来源，也是选词流程本身。六个阶段，每个阶段只回答一个问题：

| 阶段 | 回答什么 | 产出 |
| --- | --- | --- |
| 1 需求研究 → 属性池 | 什么值得监测 | 买家重要性、相对竞品、可改变性三项判断的属性池；竞品；候选 Topic 方向 |
| 2 Topic 规划与出题 | 哪些需求变成题、各出多少 | 从 P1 落点聚出的 Topic、覆盖矩阵切片、候选 Prompt |
| 3 试跑 | 每道题问得对不对、AI 现在答什么 | 合格 / 修改 / 淘汰；信源壁垒；探索性读数（只展示） |
| 4 机会排序与客户选词 | 客户该选哪些题 | 按切片档位排序的推荐表，客户选定后锁版 |
| 5 正式基线 | 锁定题集下的 Before 基准是多少 | 分平台可见度与引用诊断、可改变性重判、优化顺序、承诺可行性 |
| 6 优化与持续监测 | 差距是否持续、优化有没有效果 | 同题同条件同口径的跨期对比 |

几条贯穿全流程的硬规则：

- **试跑是探索，不是基线。** 每道候选题在**每个监测平台各跑 3 次**（某平台异常时该平台补到 5 次封顶），只用来查题目质量、初判信源壁垒、给客户看当前竞争语境；不进任何统计，不填 AI 认知差距，不驱动选词顺序。
- **选词排序只看需求价值与可争取性。** 按切片档位（买家重要性 × 可改变性，再受受众业务权重封顶），只有信源壁垒＝来源追不上时降一档；同档内相对竞品领先排在持平前。品牌自己被提及多少不参与排序——按读数挑题会把均值回归当成优化效果。
- **正式基线只为客户选定的题跑**：每个 query × 平台 × 国家 × 语言 30 次独立运行，这一轮就是 Before 基线。全部候选题 × 全平台跑一轮的候选基线已于 2026-10-23 取消。
- **优先级必须带原因。** 提示词矩阵和提示词库各有一个「优先级原因」公式字段，用客户能读懂的话说明这一行为什么是这个档位；判定标准是每行原因反推出来的档位必须等于该行的优先级。
- **考核口径在正式基线前锁定**：考核题清单、平台 × 市场 × 语言与次数、分母、计算规则；之后任何变更都开新版本并由品牌方重新确认。
- **正式题面不可改**。要改词就停测旧题、开新题号、起新版本；改过的题重跑受影响部分。
- **正式监测开始 2–4 周后复查一次题库**，只看题目本身（是否切题、各平台是否答对、结果是否稳定、有无重复、业务上是否仍相关）。品牌没被提到不是删题或改题的理由。

确定性校验由 `scripts/validate_after_sales_set.py` 执行（40 条门禁，覆盖 Discovery 不得点名品牌、题面条件必须有买家原话约束支撑、同一购买决策不得问两遍、发现型占比、受众提问人是否写明等），对客 Base 的部署差异用 `scripts/diff_base_against_spec.py` 对账，矩阵空格子用 `scripts/check_matrix_coverage.py` 列出。

## 监测：跑数并解释差距

`geo-monitoring` 负责跑和算，不改题、不选题。

| 交接 | 内容 |
| --- | --- |
| 选词 → 监测 | 一份题集（题库 JSON，带 `prompt_type`、`group_role`、市场与语言）＋要跑的平台、次数、频率约定 |
| 监测 → 选词 | 每题每平台的有效读数、基线 HTML 报告；选词据此复查题库 |
| 监测 → 内容团队 | 缺口诊断与优化方向 |

产出是单文件 HTML 基线报告（不是多维表格）：预计算并独立复算校验，可按提示词类型 / 平台 / 主题筛选，含可见度、引用、情感模块与逐题详情。优化顺序也在这里算——五种竞争格局（竞品领先 / 部分出现仍落后 / 已打平或领先 / 无品牌点名 / 来源追不上）由 30 次读数算出，只用来排优化顺序，不写回多维表格。

采集用同一个 `collect_answers.py`；采集完整性仍先走 `geo-presales-crawl-integrity`；缺口转动作见 `references/gap-cause-action-table.md`。

## 完整清单（11 个 Skill）

| Skill | 任务 | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- | --- |
| `geo-presales-pipeline` | 售前任务一（编排） | 有采集目录 + Case + 题库，要一路跑到 HTML 报告，让 Agent 在每个暂停点自动请对应 Skill 出场 | 阶段顺序 + 暂停点分派；产物即链上各 Skill 的产物 | 零新逻辑：不定义口径、不校验、不判读、不审计、不出上传 CSV |
| `geo-presales-crawl-integrity` | 售前任务一/二 | 算任何指标之前，先确认这份采集能不能用：每条回答是正文明说了品牌，还是只是被检索到 | 分层判定 + 问题清单，指明涉及的平台和文件 | 不算提及率、声量、排名、引用份额，不判情绪，不纠品牌 |
| `geo-presales-report-builder` | 售前任务一/二 | 有采集目录 + 题库 + Case，要一份能给客户看的报告 | 可见度与引用类指标 + 单文件 HTML 报告，支持国家 / 平台 / 主题三层筛选 | 不做情感判读（归 sentiment-judge，只汇总其结果），不另写指标口径，不出上传 CSV，不纠品牌识别，不做采集校验 |
| `geo-presales-sentiment-judge` | 售前任务一/二 | 需要句级正负句和正向情感占比 | 逐句 CSV + 正向情感占比，按品牌、平台、Attribute、Theme 分层 | 只算「正向情感占比」一个指标；不改后端已有的情绪字段，不判竞品胜负，不算可见度 |
| `geo-presales-report-audit` | 售前任务三（跨任务） | 品牌提及识别或正文首现排序需要审核和修正 | 修正后的品牌提及识别与首现排序、安全补丁、可复现的问题说明与 Bad Case 草稿 | 不改客户结论，不审情绪，不做竞品研究或出题 |
| `geo-presales-report-editor` | 售前任务三 | 底层结果已确认，要改客户结论并出上传件 | 更新后的客户结论、可上传 CSV | 不重算底层，不渲染 HTML，不操作报告页面 |
| `overseas-geo-competitor-research` | 售前共用 | 正式竞品不足 3 个，或用户填的候选需要核验 | 3 个通过同一购买集合硬门槛的正式竞品 + 选择证据 | 不建 Case、不出题、不采集 |
| `geo-presales-eval-case-builder` | 售前共用 | 有品牌资料，要构建监测输入或积累到飞书 Base | 规范化 Case、2–3 个监测主题、已核验竞品，写入飞书 Base | 不出题、不采集、不写报告 |
| `geo-presales-prompt-builder` | 售前共用 | 已有 Case，要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不建主题、不选竞品、不算指标 |
| `geo-prompt-selection-builder` | 选词 | 售前选词工具与签约后建正式监测题库 | 属性池、对客确认表、提示词矩阵与题库、正式题选定、考核口径 | 不做早期售前诊断题库，不跑基线与出报告（走 `geo-monitoring`），不定指标口径，不自行发现或冻结竞品 |
| `geo-monitoring` | 监测 | 题库定好后跑正式基线与按期采集 | 单文件 HTML 基线报告、采集节奏与重跑触发、交给内容团队的缺口方向 | 不选题改题，不做早期售前诊断报告，不定指标口径 |

**Report Audit 跨任务。** 它既服务于任务三的修正流程，它的采集原始层脚本也被任务一/二的 Report Builder 直接引用——去引用正文是品牌识别的入口，两边必须用同一份实现。

## 指标归属一览

| 指标 | 谁算 | 口径实现 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置、可见度 | `geo-presales-report-builder` | 全库统一实现（`geo_presales_core`） |
| 引用次数 / 引用份额 / 引用率 | `geo-presales-report-builder` | 只计正文里带编号的引用标记出现次数，不拿供应商给的来源清单凑数；引用份额按未去重次数算 |
| 正向情感占比（判读） | `geo-presales-sentiment-judge` | 正向 Claim 信号 ÷（正向 + 负向），不设中性档：没有明确正负倾向就不生成 Claim，不补值、不进分母 |
| 正向情感占比（按切片汇总进报告） | `geo-presales-report-builder` | 复用 sentiment-judge 的判读结果，按国家 / 平台 / 主题分别统计 |

**改口径只改统一实现这一处**，其他 Skill 对它只读。位置、改动前的验证命令和影响范围见文末「开发与维护」。

## 关键约束

**Prompt Builder（售前诊断题库）**

- 每个 Topic 先排属性优先级（P1 核心 / P2 次要 / P3 补充），再出题。
- 每 Topic 至少 5 条，整批（含后补题）不超过 60 条；单产品线单市场总量 30–60 条，其中核心层 20–30 条就够。这是下限与总量上限，不是均衡配额——不同 Topic 可以不均，只有重要关注点尚未覆盖时才加题。
- 默认只出发现型（Discovery）；竞品、评价、品类认知按需补，没有固定配额；信息型与验证题留给选词侧的正式题库。
- 每个 Topic 里发现型必须覆盖该 Topic 的全部 P1 属性；信息不足直接报 Case 过薄，不凑题。
- 发现型与品类认知题不出现任何具体品牌；每题用 `tags` 标出它测什么（`tags` 只是标注，不参与指标口径）。
- 正式可见度只统计 Discovery 这一类，其他类型都不进分子分母。

**Report Builder**

- 引用次数只计正文里带编号的引用标记的出现次数，不拿供应商字段的来源清单充数。
- 正文为空的答案不进任何分母，也不计为「未提及」。
- 声量份额、平均提及位置与提及率排名的分母 / 比较范围都是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），前端只展示 5 行是为了可读性。
- 交付前必须做一次独立复算校验（`verify_report_data.py`）并全部通过，不通过不出报告。

**选词与监测**

- 试跑读数不进统计、不改排序；正式基线每格 30 次；正式题面不可改，改词即新版本。
- 优先级必须带「优先级原因」，每行原因反推的档位要等于该行优先级。
- 考核口径（题清单、平台 × 市场 × 语言与次数、分母、计算规则）在正式基线前锁定，变更即新版本。

## 开发与维护（同事可跳过）

以下面向改脚本、跑测试的人。

### 指标口径实现

统一实现在 `skills/geo-presales-report-editor/scripts/geo_presales_core/`，其他 Skill 只读。改动前先跑：

```bash
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
```

并在改动说明里写明受影响的下游 Skill。

### 跨 Skill 路径

脚本按自身位置定位兄弟 Skill：每个脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。整套放在一起时，从任意工作目录调用都可以。

单独部署某个 Skill、兄弟目录不在同一层时，用环境变量指定：

```bash
export GEO_PRESALES_SKILLS_ROOT=/path/to/skills
```

### 本地验证

在仓库根目录运行（9 组，全部通过才算干净）：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-builder/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-sentiment-judge/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-prompt-selection-builder/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/overseas-geo-competitor-research/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/shared/scripts -p 'test_*.py'
```

当前基线：21 / 128 / 35 / 40 / 77 / 21 / 43 / 15 / 3。测试不调用外部 AI 平台。

### 发布

`skills/` 是唯一真源，仓库是发布副本。对外发布走本地 `shared/scripts/redact_publish_tree.py`：建发布树 → `apply` → `scan` 必须 0 命中 → 在脱敏树里跑上面全部测试 → 复制进仓库提交。不要直接把工作目录 rsync 进仓库。

### 不随仓库分发

各 Skill 的 `assets/` 下按客户生成的品牌词表与引用域名缓存、`build/` 运行产物、客户 Case 与采集数据都不入库，`.gitignore` 已排除。需要时按对应 `SKILL.md` 在自己的 `assets/` 下生成。客户案例示例走 `shared/publish-templates/`，不发布真实客户文件。
