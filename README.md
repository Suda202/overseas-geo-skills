# 海外 GEO Skills

这个仓库有 8 个 Skill 和一个共享目录 `shared/`，大部分 Skill 是被别的 Skill 调用的零件。日常只需要从下面「按你要做的事找入口」里找一个入口，其余的由入口按需调用。

## 按你要做的事找入口

| 你要做的事 | 用这个 Skill | 阶段 |
| --- | --- | --- |
| 品牌信息进来，生成售前诊断题 | `geo-prompt-selection-builder`（选词，线上出口） | 售前诊断 |
| 有题、有采集，要出给客户看的 HTML 诊断报告 | `geo-presales-pipeline` | 售前诊断 |
| 已交付的诊断报告要改 | `geo-presales-report-audit`，再 `geo-presales-report-editor` | 售前诊断 |
| 签约前后定长期监测哪些题、出对客确认表 | `geo-prompt-selection-builder`（选词，本地出口） | 选词 |
| 试跑、挑正式题并锁版，跑正式基线和按期采集 | `geo-monitoring` | 监测 |

下面这几个一般不直接用，由上面的入口调用：

| Skill | 谁调用它 | 做什么 |
| --- | --- | --- |
| `geo-presales-crawl-integrity` | pipeline、监测 | 算指标前检查采集能不能用 |
| `geo-presales-report-builder` | pipeline | 算可见度与引用指标，渲染 HTML 报告；`collect_answers.py` 采集也在这里 |
| `geo-presales-sentiment-judge` | pipeline | 句级情感判读，算正向情感占比 |

售前生词、品牌信息整理（Case Builder）和竞品核验原来是三个独立 Skill，已经退役：生词并进选词，Case 改由线上表单或本地 JSON 提供、用选词的 `normalize_case.py` 归一化，竞品照用 Case 里填的。

## 售前诊断

售前诊断报告是促成交用的，拆成四个环节，每个环节各有负责的 Skill，互不越界。线上给销售用时，只有 ② 生词换成本仓库的 Skill；③ 采集与出报告和人工改词都沿用线上原有流程。下面写的 ③ ④ 是本地跑法。

```text
① 准备品牌信息（Case） -> ② 生词 -> ③ 采集与出报告 -> ④ 修改已交付报告
```

| 环节 | 输入 | 输出 | Skill |
| --- | --- | --- | --- |
| ① 准备品牌信息 | 品牌资料 | Case：品牌、官网、品类、业务描述、1–3 个竞品 | 线上由销售填表单；本地按输入合同写 JSON |
| ② 生词 | Case | 每个市场一批诊断题，9 个字段 | `geo-prompt-selection-builder` |
| ③ 采集与出报告 | 诊断题 + Case | 单文件 HTML 诊断报告 | 线上：沿用线上原有流程；本地：`geo-presales-pipeline` |
| ④ 修改已交付报告 | 已交付报告 | 修正后的品牌识别、客户结论、上传 CSV | `geo-presales-report-audit`、`geo-presales-report-editor` |

### ② 生词（`geo-prompt-selection-builder`）

**输入**：一份 Case，格式见 `skills/geo-prompt-selection-builder/references/input-contract.md`，先过 `scripts/normalize_case.py`。不需要预先填主题，主题在生词时从调研结果里聚出来。

**怎么生**：规则和本地选词完全一样，都在 `references/selection-rules.md`，按 8 步走（见下文「选词」）；线上和本地不一样的几步写在 `references/online-runner.md`：没有品牌方数据、没有浏览器登录态、研究预跑只放 1 道品类认知题、只交上传行。导出前 `validate_after_sales_set.py` 和 `export_upload_csv.py` 都要退出码 0。

**输出**：每个市场一批题，每个市场最多 60 条，每题 9 个字段：

```text
query, question_zh, topic, diagnosis_intent, tags, question_types, purchase_intent, persona_name, scene_name
```

目前只出发现题。`question_types` 由导出脚本按意图类型自动填，是过渡字段：每种意图类型统计什么由类型决定，见 `skills/shared/canonical-intent-mapping.md`。报告主题就是题里的 `topic`。

**线上一条命令跑完**：

```bash
python3 skills/geo-prompt-selection-builder/scripts/run_selection_mode.py run \
  --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

- `--platforms` 填客户在表单里选的 AI 平台（`chatgpt`、`gemini`、`aimode`、`overview`、`perplexity`、`copilot`、`grok`、`alexa`）。
- 宿主有自己的 agent 框架时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。
- 检查没过时，脚本把报错回喂 agent 返修，默认最多 2 轮（`--repair-rounds`）。
- 退出码：`0` 成功；`1` 生词失败；`2` 输入或环境有错，这种情况不启动 agent。结果写在工作目录的 `out/result.json`。

**用到的外部服务**：

| 服务 | 用途 | 环境变量 |
| --- | --- | --- |
| 模型网关（Anthropic 兼容接口） | agent 本身 | `ANTHROPIC_BASE_URL`、`ANTHROPIC_API_KEY`、`AGENT_MODEL` |
| Scrapeless | 研究预跑采集 AI 回答、Google 搜索与 PAA、网页代理 | `SCRAPELESS_API_KEY`（必需） |
| DataForSEO | 搜索量、长尾词、趋势；Trustpilot、Google 地图、Google Play、App Store、Google Shopping 评价 | `DATAFORSEO_LOGIN`、`DATAFORSEO_PASSWORD` |
| 免费来源 | Google 搜索联想、Reddit RSS、Wayback、公开网页 | 无 |
| 无头 Chrome | 渲染 JS 页面 | `CHROME_PATH` |

不用任何浏览器登录态。要登录才能看的站跳过，并记进 `notes.md` 的「未覆盖来源」。

**不做的事**：不采集回答、不算指标、不出报告；不做对客确认表、试跑和锁定正式题；不增删竞品。

### ③ 采集与出报告（`geo-presales-pipeline`）

pipeline 只管阶段顺序和暂停点，到每个暂停点请对应的 Skill 出场：采集（`collect_answers.py`）→ 采集完整性检查（crawl-integrity）→ 指标与渲染（report-builder）→ 情感判读（sentiment-judge）。手动跑一条命令到下一个暂停点：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

采集前设 `no_proxy=api.scrapeless.com`，否则本机代理会掐断 HTTPS 握手。声量份额和提及率排名的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），所以必须带 `--lexicon`。

报告是单文件 HTML，所有客户共用同一个模板：数据筛选（地区、平台、意图类型、主题，多选）→ 核心洞察 → 可见度 → 购物商品卡 → 引用 → 情感 → 附录 问题明细。没有商品卡数据（选词判定关，或整份采集一张卡都没有）、没有情感数据（没判读完，或一条正负信号都没有）时，对应模块连同散在各处的 KPI、明细列、回答详情一起隐藏，后面的模块顺延编号。页面上的数由内嵌的计算引擎按筛选现算，和离线预算的切片逐项对账，不一致就停下（`check_engine_parity.js`）。

### ④ 修改已交付报告

先用 `geo-presales-report-audit` 把品牌提及识别和首现排序改对，再用 `geo-presales-report-editor` 改客户结论、出上传 CSV。

## 选词：生成要测的题（`geo-prompt-selection-builder`）

售前生词和签约后定长期监测题用同一套规则，一个 Skill 两个出口：线上一条命令只交上传行；本地多了品牌方数据和对客确认表（飞书多维表格）。到导出为止：

| 步 | 做什么 | 产出 |
| --- | --- | --- |
| 1 | 确认业务范围（线上用 Case 代替），品牌方先填、我们核对；目前只做发现型可见度 | 业务范围表 |
| 2 | 调研：先预跑品类认知与品牌、竞品评估，再收四类需求信号，看品牌与 3 家竞品官网 | 需求信号表、预跑答案、品牌能力清单 |
| 3 | 约束条件：收得宽、统一粒度，不判重要性和相对竞品，只记品牌可核实的明显劣势 | 三张表共用的约束条件选项 |
| 4 | 目标客户与使用场景：按会不会改变候选来拆并，只多看一条条件的挂成约束条件；品牌方确认后冻结 | 业务范围里的目标客户行与使用场景行 |
| 5 | 提示词矩阵：一行 ＝ 产品线 × 市场 × 目标客户 × 使用场景 × 意图类型，只开成立的行；每行判一次业务优先级，这是全流程唯一的档位判断 | 提示词矩阵 |
| 6 | 主题：主题 ＝ 同一类候选 × 同一意图类型，每主题至少 5 题；主题优先级从矩阵行汇总，不另判 | 主题表、`config.tag_dimensions` |
| 7 | 写题：只在高、中档发现行上出题，按决策差异定题数 | 提示词库、题库 JSON |
| 8 | 校验与导出：validator 错误全改、告警逐条记处理 | 题库 JSON、对客确认表和 / 或上传 CSV |

确定性校验用 `scripts/validate_after_sales_set.py`，只认现行结构，旧结构的历史题库直接报不支持（不迁移、不校验、不导出）。意图类型共八类：发现、问题解决、评估、对比、替代、验证、交易、售后；目前只出发现题，其他七类的开行条件与题面写法在 `references/type-branches.md`。主题按 AI 会推荐的同一类候选分组，候选换了一类就分开。

导出上传 CSV 的几条硬规则：`tags` 按 `config.tag_dimensions` 派生，不重复写意图类型，只有替代题在第一位写「替代」；问题解决、验证、交易、售后后端还没有枚举，不导出并打印题号；停测或需修改的题不导出；`question_types` 由脚本按 `diagnosis_intent` 自动填，是过渡字段，每种类型统计什么以 `skills/shared/canonical-intent-mapping.md` 的「统计指标」列为准。

## 监测：试跑、锁版、跑数并解释差距（`geo-monitoring`）

不写题。候选题在每个监测平台各试跑 3 次，判题问得对不对；品牌方挑正式题并锁版后跑正式基线，每个 query × 平台 × 国家 × 语言 7 次，产出单文件 HTML 基线报告和交给内容团队的缺口方向；之后按题型定频率采集。采集同样用 `collect_answers.py`，跑之前先过 crawl-integrity。

## 指标口径

指标口径全库只有一份实现，在 `skills/geo-presales-report-editor/scripts/geo_presales_core/`，其他 Skill 只读。

| 指标 | 谁算 | 口径 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置 | report-builder | 报告默认统计发现、替代两类（只剩问题解决题时算问题解决）；上传 CSV 与后端仍只看发现 |
| 引用次数、引用份额、引用率 | report-builder | 只数正文里带编号的引用标记；份额按未去重次数算 |
| 正向情感占比 | sentiment-judge 判读，report-builder 按切片汇总 | 正向 ÷（正向 + 负向），不设中性档 |
| 商品卡触发率、商品卡提及率、商品卡平均位置、官网购买链接覆盖率 | report-builder（实现在 core `shopping.py`） | 只统计发现、替代两类题，按平台分开算，和提及率分开报；商品卡提及率再分品牌级与 SKU 级；公式见 `skills/geo-presales-report-editor/references/metric-scope-and-copy-contract.md`「购物层指标」 |

每种意图类型统计哪些指标（提及率、情感、胜负、准确性）由类型决定，引用所有类型都统计，对照和后端字段见 `skills/shared/canonical-intent-mapping.md`。上传时填的 `diagnosis_intent` 和后端内部存的值是两层，评估题上传填 `evaluation`。

## 开发与维护

### 依赖

仓库根目录 `requirements.txt` 是整份依赖，`python3 -m pip install -r requirements.txt`，需要 Python ≥ 3.12。八个 Skill 里只有 `geo-prompt-selection-builder`（语种门禁、`--agent sdk`）和 `geo-presales-report-audit`（截图标注、引用清洗）要第三方包，各自的清单在它目录下；其余六个和 `shared/` 的脚本只用标准库，没有清单。所有第三方包都是可选的，缺了只降级对应功能，不挡其余流程。

### 跨 Skill 路径

脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。单独部署时用 `GEO_PRESALES_SKILLS_ROOT` 指定。

### 本地验证

在仓库根目录运行，全部通过才算干净：

```bash
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-builder/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-sentiment-judge/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-prompt-selection-builder/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/shared/scripts -p 'test_*.py'
python3 skills/geo-prompt-selection-builder/evals/e2e_repair_loop.py
```

测试不调用外部 AI 平台。

### 发布

`skills/` 的真源在本地，仓库是发布副本。发布走本地 `shared/scripts/redact_publish_tree.py`：建发布树 → `apply` → `scan` 必须 0 命中 → 在脱敏树里跑全部测试 → 复制进仓库提交。

### 不随仓库分发

按客户生成的品牌词表、引用域名缓存、`build/` 运行产物、客户 Case 与采集数据都不入库，`.gitignore` 已排除。仓库里的 Case 示例（`skills/geo-prompt-selection-builder/references/input-examples/` 下的 b2b、b2c 两份）是通用模板，不是真实客户。
