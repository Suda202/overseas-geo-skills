# 海外 GEO Skills

这个仓库有 11 个 Skill，但大部分是被别的 Skill 调用的零件。日常只需要从下面「按你要做的事找入口」里找一个入口，其余的由入口按需调用。

## 按你要做的事找入口

| 你要做的事 | 用这个 Skill | 阶段 |
| --- | --- | --- |
| 品牌信息进来，生成售前诊断题 | `geo-presales-prompt-builder`（售前生词） | 售前诊断 |
| 有题、有采集，要出给客户看的 HTML 诊断报告 | `geo-presales-pipeline` | 售前诊断 |
| 已交付的诊断报告要改 | `geo-presales-report-audit`，再 `geo-presales-report-editor` | 售前诊断 |
| 签约前后定长期监测哪些题、出对客确认表 | `geo-prompt-selection-builder`（选词） | 选词 |
| 题定好了，跑正式基线和按期采集 | `geo-monitoring` | 监测 |

下面这几个一般不直接用，由上面的入口调用：

| Skill | 谁调用它 | 做什么 |
| --- | --- | --- |
| `geo-presales-eval-case-builder` | 需要先整理品牌信息时 | 把品牌资料整理成 Case，写飞书 Base |
| `overseas-geo-competitor-research` | Case Builder | 联网核验并冻结 3 个正式竞品 |
| `geo-presales-crawl-integrity` | pipeline、监测 | 算指标前检查采集能不能用 |
| `geo-presales-report-builder` | pipeline | 算可见度与引用指标，渲染 HTML 报告；`collect_answers.py` 采集也在这里 |
| `geo-presales-sentiment-judge` | pipeline | 句级情感判读，算正向情感占比 |

## 售前诊断

售前诊断报告是促成交用的，拆成四个环节，每个环节各有负责的 Skill，互不越界。线上给销售用时，只有 ② 生词换成本仓库的 Skill；③ 采集与出报告和人工改词都沿用线上原有流程。下面写的 ③ ④ 是本地跑法。

```text
① 准备品牌信息（Case） -> ② 生词 -> ③ 采集与出报告 -> ④ 修改已交付报告
```

| 环节 | 输入 | 输出 | Skill |
| --- | --- | --- | --- |
| ① 准备品牌信息 | 品牌资料 | Case：品牌、官网、品类、业务描述、1–3 个竞品 | `geo-presales-eval-case-builder`（线上由销售填表单） |
| ② 生词 | Case | 每个市场一批诊断题，9 个字段 | `geo-presales-prompt-builder` |
| ③ 采集与出报告 | 诊断题 + Case | 单文件 HTML 诊断报告 | 线上：沿用线上原有流程；本地：`geo-presales-pipeline` |
| ④ 修改已交付报告 | 已交付报告 | 修正后的品牌识别、客户结论、上传 CSV | `geo-presales-report-audit`、`geo-presales-report-editor` |

### ② 生词（`geo-presales-prompt-builder`）

**输入**：一份 Case，格式见 `skills/geo-presales-prompt-builder/references/input-contract.md`。必填只有公司名、品牌名称、业务模式、品类、官方域名、1–3 个竞品；业务描述字段都是选填。不需要预先填主题，主题在生词时从调研结果里聚出来。

**怎么生**：用选词的方法，写题规则只有一份，在 `geo-prompt-selection-builder`：

1. 归一化 Case（`scripts/normalize_case.py`）。
2. 研究预跑：在客户选的 AI 平台上，各问一次品类怎么选、目标品牌和每个竞品怎么样。
3. 收公开信号：搜索词、评价、社区里的买家原话。
4. 判断每个属性相对竞品的位置：优势、持平、劣势或待确认。
5. 画买家处境矩阵，给每一行定优先级。
6. 从矩阵的 P1、P2 行聚出主题。
7. 写题、去重。
8. 过两道检查再导出 9 字段题：选词校验器（`validate_after_sales_set.py`）查写题的通用规则；售前专属检查（`scripts/check_presales_bank.py`）查只出发现、对比、评价三类，发现型至少一半，每个主题至少 5 道，对比题必须点名 Case 里的竞品。

步骤细节和每一步判断记在题库 JSON 哪里，见 `references/selection-mode.md`。

**输出**：每个市场一批题，每个市场最多 60 条，每题 9 个字段：

```text
query, question_zh, topic, diagnosis_intent, tags, question_types, purchase_intent, persona_name, scene_name
```

题型只出发现、对比、评价三类，发现型至少占一半。报告主题就是题里的 `topic`。

**线上一条命令跑完**：

```bash
python3 skills/geo-presales-prompt-builder/scripts/run_selection_mode.py run \
  --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

- `--platforms` 填客户在表单里选的 AI 平台（`chatgpt`、`gemini`、`aimode`、`overview`、`perplexity`、`copilot`、`grok`、`alexa`）。
- 宿主有自己的 agent 框架时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。
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

**旧题库**：2026-10-29 之前用的是「默认模式」（Case 先填 1–3 个主题，属性按重要性和可改变性分级）。这套规则已归档到 `references/legacy/`，只用来读懂旧题库；旧题库仍用 `scripts/validate_question_bank.py` 校验。

### ③ 采集与出报告（`geo-presales-pipeline`）

pipeline 只管阶段顺序和暂停点，到每个暂停点请对应的 Skill 出场：采集（`collect_answers.py`）→ 采集完整性检查（crawl-integrity）→ 指标与渲染（report-builder）→ 情感判读（sentiment-judge）。手动跑一条命令到下一个暂停点：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

采集前设 `no_proxy=api.scrapeless.com`，否则本机代理会掐断 HTTPS 握手。声量份额和提及率排名的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），所以必须带 `--lexicon`。

### ④ 修改已交付报告

先用 `geo-presales-report-audit` 把品牌提及识别和首现排序改对，再用 `geo-presales-report-editor` 改客户结论、出上传 CSV。

## 选词：定长期监测哪些题（`geo-prompt-selection-builder`）

签约前后用，比售前生词多了客户数据、对客确认表、试跑和锁定正式题：

| 阶段 | 回答什么 | 产出 |
| --- | --- | --- |
| 1 调研 → 属性池 | 买家在意什么，我们相对竞品站在哪 | 属性池（只判相对竞品）；研究预跑先爬再调研 |
| 2 矩阵与主题 | 哪些买家处境值得测、各测几题 | 提示词矩阵：每行优先级 = 业务重点 × 买家证据；从 P1、P2 行聚出主题 |
| 3 写题 | 题面怎么问 | 候选题，每个条件都要有买家原话支撑 |
| 4 试跑 | 题问得对不对，内容能不能影响答案 | 各监测平台各跑 3 次；按引用域名判可改变性 |
| 5 客户选词与锁版 | 正式测哪些题 | 每个采购主题最多 10 道正式题，锁定考核口径 |

确定性校验用 `scripts/validate_after_sales_set.py`。试跑读数不进任何统计，品牌自己被提及多少也不参与排序。正式题面不可改，要改就停测旧题、开新题号。

## 监测：跑数并解释差距（`geo-monitoring`）

只跑和算，不改题、不选题。正式基线每个 query × 平台 × 国家 × 语言跑 30 次，产出单文件 HTML 基线报告和交给内容团队的缺口方向。采集同样用 `collect_answers.py`，跑之前先过 crawl-integrity。

## 指标口径

指标口径全库只有一份实现，在 `skills/geo-presales-report-editor/scripts/geo_presales_core/`，其他 Skill 只读。

| 指标 | 谁算 | 口径 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置、可见度 | report-builder | 只统计发现题 |
| 引用次数、引用份额、引用率 | report-builder | 只数正文里带编号的引用标记；份额按未去重次数算 |
| 正向情感占比 | sentiment-judge 判读，report-builder 按切片汇总 | 正向 ÷（正向 + 负向），不设中性档 |

题型与后端字段的对照见 `skills/shared/canonical-intent-mapping.md`。上传时填的 `diagnosis_intent` 和后端内部存的值是两层，评价题上传填 `evaluation`。

## 开发与维护

### 跨 Skill 路径

脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。单独部署时用 `GEO_PRESALES_SKILLS_ROOT` 指定。

### 本地验证

在仓库根目录运行，全部通过才算干净：

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

测试不调用外部 AI 平台。

### 发布

`skills/` 的真源在本地，仓库是发布副本。发布走本地 `shared/scripts/redact_publish_tree.py`：建发布树 → `apply` → `scan` 必须 0 命中 → 在脱敏树里跑全部测试 → 复制进仓库提交。

### 不随仓库分发

按客户生成的品牌词表、引用域名缓存、`build/` 运行产物、客户 Case 与采集数据都不入库，`.gitignore` 已排除。仓库里的 Case 示例（`references/input-examples/` 下的 b2b、b2c 两份）是通用模板，不是真实客户。
