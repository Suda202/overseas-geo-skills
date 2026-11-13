# 海外 GEO Skills

这个仓库有 9 个 Skill 和一个共享目录 `shared/`。每项能力只由一个 Skill 负责，其他 Skill 需要时调用它，不另写一份。日常从下面「按你要做的事找入口」找一个入口就够了，其余的由入口按需调用。

## 按你要做的事找入口

| 你要做的事 | 用这个 Skill | 阶段 |
| --- | --- | --- |
| 品牌信息进来，生成售前诊断题 | `geo-prompt-selection-builder`（选词，线上出口） | 售前诊断 |
| 本地出售前诊断 HTML 报告（从品牌信息一路跑到报告，或从生词、采集任一步续跑） | `geo-presales-pipeline`（总入口） | 售前诊断 |
| 线上已交付的诊断报告要改 | `geo-presales-report-audit`，再 `geo-presales-report-editor` | 售前诊断 |
| 签约前后定长期监测哪些题、出对客确认表，试跑后回写 | `geo-prompt-selection-builder`（选词，本地出口） | 选词 |
| 签约后采集（试跑、正式基线、日常）、检查采集能不能用，出基线报告 | `geo-monitoring` | 监测 |
| 指标统计（提及、引用、商品卡，品牌怎么识别） | `geo-metrics` | 全部阶段 |

## 每个 Skill 负责什么

| Skill | 负责 | 不负责（交给谁） |
| --- | --- | --- |
| `geo-prompt-selection-builder` | 选词：业务范围、调研、约束条件、提示词矩阵、主题、写题、校验与导出，试跑后回写 | 采集、报告（`geo-monitoring`、`geo-presales-pipeline`）；正式题由品牌方在对客确认表上挑 |
| `geo-presales-pipeline` | 本地出售前 HTML 报告的总入口：排阶段顺序（生词 → 采集 → 采集检查 → 组装渲染 → 情感），到暂停点请对应 Skill 出场，零口径 | 每个阶段的规则（交给该阶段的 Skill） |
| `geo-metrics` | 统计口径与唯一实现：品牌识别、识别前的正文清洗、答案有效性、引用抽取与计次、提及率、声量、引用份额、官网引用率、商品卡，以及每个指标用哪批样本 | 组装与渲染报告（report-builder、monitoring）、情感判读（sentiment-judge） |
| `geo-presales-report-builder` | 售前报告数据层组装、HTML 渲染 | 采集（`geo-monitoring`）；指标公式（`geo-metrics`） |
| `geo-presales-sentiment-judge` | 句级情感判读，算正向情感占比 | 品牌识别（`geo-metrics`） |
| `geo-presales-report-audit` | 修改线上售前诊断报告的品牌提及识别结果 JSON（品牌名单和首现排序），出 Bad Case | 客户结论（report-editor） |
| `geo-presales-report-editor` | 修改线上售前诊断报告的结论 CSV | 指标计算（`geo-metrics`） |
| `geo-monitoring` | 采集和采集检查：`collect_answers.py` 是全库唯一的采集程序，售前 pipeline、选词研究预跑也调它；`audit_crawl_integrity.py` 在算指标前查字段层混用、引用定义丢失、空回答、未登记平台。签约后跑试跑、正式基线和日常采集；外加基线 HTML 报告、缺口交给内容团队 | 指标口径（`geo-metrics`） |

售前生词、品牌信息整理（Case Builder）和竞品核验原来是三个独立 Skill，已经退役：生词并进选词，Case 改由线上表单或本地 JSON 提供、用选词的 `normalize_case.py` 归一化，竞品照用 Case 里填的。

## 售前诊断

售前诊断报告是促成交用的，拆成四个环节，每个环节各有负责的 Skill。线上给销售用时，只有 ② 生词换成本仓库的 Skill；③ 采集与出报告和人工改词都沿用线上原有流程。下面写的 ③ ④ 是本地跑法。

```text
① 准备品牌信息（Case） -> ② 生词 -> ③ 采集与出报告 -> ④ 修改已交付报告
```

| 环节 | 输入 | 输出 | Skill |
| --- | --- | --- | --- |
| ① 准备品牌信息 | 品牌资料 | Case：品牌、官网、品类、业务描述、1–3 个竞品 | 线上由销售填表单；本地按输入合同写 JSON |
| ② 生词 | Case | 每个市场一批诊断题，5 列 | `geo-prompt-selection-builder` |
| ③ 采集与出报告 | 诊断题 + Case | 单文件 HTML 诊断报告 | 线上：沿用线上原有流程；本地：`geo-presales-pipeline` |
| ④ 修改已交付报告 | 已交付报告 | 修正后的品牌识别、客户结论、上传 CSV | `geo-presales-report-audit`、`geo-presales-report-editor` |

### ② 生词（`geo-prompt-selection-builder`）

**输入**：一份 Case，格式见 `skills/geo-prompt-selection-builder/references/input-contract.md`，先过 `scripts/normalize_case.py`。不需要预先填主题，主题在生词时从调研结果里聚出来。

**怎么生**：规则和本地选词完全一样，都在 `references/selection-rules.md`，按 8 步走（见下文「选词」）；线上和本地不一样的几步写在 `references/online-runner.md`：没有品牌方数据、没有浏览器登录态、研究预跑只放 1 道品类认知题、只交上传行。导出前 `validate_after_sales_set.py` 和 `export_upload_csv.py` 都要退出码 0。

**输出**：每个市场一批题，30–60 道（超过 60 报错；不到 30 时脚本补一轮，补不到照常交付），每题 5 列：

```text
query, question_zh, topic, diagnosis_intent, tags
```

线上只出发现题。每种意图类型统计什么由类型决定，见 `skills/shared/canonical-intent-mapping.md`。报告主题就是题里的 `topic`。

**线上一条命令跑完**：

```bash
python3 skills/geo-prompt-selection-builder/scripts/run_selection_mode.py run \
  --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

- `--platforms` 填客户在表单里选的 AI 平台（`chatgpt`、`gemini`、`aimode`、`overview`、`perplexity`、`copilot`、`grok`、`alexa`）。
- 宿主有自己的 agent 框架时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。
- 检查没过时，脚本把报错回喂 agent 返修，默认最多 2 轮（`--repair-rounds`）。
- 部署：先跑 `python3 skills/geo-prompt-selection-builder/scripts/run_selection_mode.py bundle --out <新目录>`，把打出来的整个目录部署上去。包里除了选词，还有它运行要的 `shared`、`geo-monitoring` 的采集程序和平台合同、`geo-metrics` 的 `geo_presales_core`；只部署选词目录时，runner 启动就报 `missing_skill_files` 停下。
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

**不做的事**：不采集回答、不算指标、不出报告；线上不做对客确认表；不增删竞品。

### ③ 采集与出报告（`geo-presales-pipeline`）

pipeline 只管阶段顺序和暂停点，到每个暂停点请对应的 Skill 出场：采集和采集完整性检查（`geo-monitoring` 的 `collect_answers.py`、`audit_crawl_integrity.py`）→ 指标与渲染（report-builder，指标调 `geo-metrics`）→ 情感判读（sentiment-judge）。手动跑一条命令到下一个暂停点：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon <品牌词表.json> --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

采集前设 `no_proxy=api.scrapeless.com`，否则本机代理会掐断 HTTPS 握手。声量份额和提及率排名的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），所以必须带 `--lexicon`；词表格式见下文「品牌识别」。

报告是单文件 HTML，所有客户共用同一个模板：数据筛选（地区、平台、意图类型、主题，多选）→ 核心洞察 → 可见度 → 购物商品卡 → 引用 → 情感 → 附录 问题明细。没有商品卡数据、没有情感数据时，对应模块连同散在各处的 KPI、明细列、回答详情一起隐藏，后面的模块顺延编号。页面上的数由内嵌的计算引擎按筛选现算，和离线预算的切片逐项对账，不一致就停下（`check_engine_parity.js`）。

### ④ 修改已交付报告

先用 `geo-presales-report-audit` 把品牌提及识别和首现排序改对，再用 `geo-presales-report-editor` 改客户结论、出上传 CSV。

## 选词：生成要测的题（`geo-prompt-selection-builder`）

售前生词和签约后定长期监测题用同一套规则，一个 Skill 两个出口：线上一条命令只交上传行；本地多了品牌方数据和对客确认表（飞书多维表格）。到导出为止：

| 步 | 做什么 | 产出 |
| --- | --- | --- |
| 1 | 确认业务范围（线上用 Case 代替），品牌方先填、我们核对；线上只出发现题，本地按对话里定的目标开放其他类型 | 业务范围表 |
| 2 | 调研：先预跑品类认知（品牌、竞品评估按需补跑），再收搜索、评价、社区三类需求信号，看品牌与 3 家竞品官网 | 需求信号表、预跑答案 |
| 3 | 约束条件：收得宽、统一粒度，不判重要性；逐条判品牌情况（有 / 没有 / 待确认，没有和待确认都不出题）和公开硬事实上的相对竞品 | 三张表共用的约束条件选项、约束条件表 |
| 4 | 目标客户与使用场景：按会不会改变候选来拆并，只多看一条条件的挂成约束条件；品牌方确认后冻结 | 业务范围里的目标客户行与使用场景行 |
| 5 | 提示词矩阵：一行 ＝ 产品线 × 市场 × 目标客户 × 使用场景 × 意图类型，只开成立的行；发现行和已开放类型的行各判一次业务优先级 | 提示词矩阵 |
| 6 | 主题：先按 AI 会推荐的候选类别初聚，再按竞争格局、评价标准、优化方向三问判断要不要拆；一个主题一种意图类型，个数不限；主题优先级取组内最高的业务优先级 | 主题表、`config.tag_dimensions` |
| 7 | 写题：在高、中档发现行和已开放类型的行上出题，按决策差异定题数；每条产品线 × 每个市场 30–60 道，每个发现主题至少 10 道 | 提示词库、题库 JSON |
| 8 | 校验与导出：validator 错误全改、告警逐条记处理；监测试跑后回来回写：改题、补竞品、定商品卡开关、复核主题 | 题库 JSON、对客确认表和 / 或上传 CSV |

确定性校验用 `scripts/validate_after_sales_set.py`，只认现行结构，旧结构的历史题库直接报不支持。意图类型共八类：发现、问题解决、评估、对比、替代、验证、交易、售后；线上只出发现题，本地选了对应目标才出其他类型（交易、售后本期不出），开行条件与题面写法在 `references/type-branches.md`。

导出上传 CSV 的几条硬规则：一个市场 × 一条产品线一个文件，每个文件最多 60 条；`tags` 按 `config.tag_dimensions` 派生，不写意图类型名；问题解决、验证、交易、售后后端还没有枚举，不导出并打印题号；需修改的题不导出。

## 监测：签约后的采集（`geo-monitoring`）

只管把题跑出来：候选题先试跑；品牌方在对客确认表上挑完正式题后跑正式基线，之后日常采集。采集用 `skills/geo-monitoring/scripts/collect_answers.py`，采完先跑 `scripts/audit_crawl_integrity.py`，缺陷怎么处理见 `references/crawl-integrity.md`。试跑答案交回选词回写。

另外两件事也在这里：用采集结果出单文件 HTML 基线报告，以及把定位到的缺口交给内容团队（缺口转动作表）。基线报告复用售前报告的数据层与渲染层，统计口径和售前报告是同一套，只改展示：意图类型放在地区那一行当筛选，页面多一个「引用率」指标、每题的运行记录抽屉和竞品逐题对比。

## 统计口径（`geo-metrics`）

全库只有一份实现，在 `skills/geo-metrics/scripts/`，其他 Skill 只调用。每个指标用哪批样本、对客户能叫什么名字，定义在 `skills/geo-metrics/references/metric-scope-and-copy-contract.md`。

| 指标 | 样本范围（HTML 报告） | 口径 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置 | 发现、替代两类；只剩问题解决题时算问题解决；对比、评估等题面点名品牌的类型显示「—」 | 品牌出现在去引用正文里才算提及；声量分母是全部纳入品牌 |
| 引用份额、引用率、官网引用率 | 统计层默认全部意图类型；核心洞察只展示和提及率同一批回答，引用模块展示全部类型 | 只数正文里带编号的引用标记；份额按未去重次数算 |
| 正向情感占比 | 情感题 | 正向 ÷（正向 + 负向），不设中性档；判读在 sentiment-judge |
| 商品卡触发率、商品卡提及率、商品卡平均位置、官网购买链接覆盖率 | 发现、替代两类，按平台分开 | 和提及率分开报；商品卡提及率分品牌级与 SKU 级 |

上传 CSV 与后端仍只看发现题。每种意图类型统计哪些指标由类型决定，对照和后端字段见 `skills/shared/canonical-intent-mapping.md`。

有两处是刻意保留的第二份实现，改口径时要一起改：`geo-presales-report-builder/scripts/verify_report_data.py` 独立复算全部切片，用来抓数据层的错；报告页 `report-engine.js` 在浏览器里按多选筛选现算，由 `check_engine_parity.js` 对账。

### 品牌识别

识别入口是 core 的 `find_alias_spans`，售前报告、监测基线、试跑计数、情感抽取都调它。

- **正文清洗**：先去掉引用标记、图片、链接网址、全部 HTML 标签（图片标签里的被引网页标题不算提及）、裸网址，清空商品卡的销售渠道列，再识别。
- **匹配**：大小写不敏感；拉丁字母别名带词边界；泰文、中文这类连写文字不加词边界，不同品牌之间按最长优先、不重叠消解。
- **分隔符放宽**：5 个字母以上的拉丁别名，字符之间可以夹 1 个空格、连字符、点或下划线；原文被这样拆开时每段都要大写开头。
- **常用词要大写**：别名是英文常用词时，原文必须带大写才算。常用词表是 `geo_presales_core/english_words.txt`（取自 Webster's 2nd 小写词条）。
- **不自动派生简称**：去掉 Security、Water 这类后缀得到的简称常常是另一个实体，所以不派生；`reconcile_brand_recognition.py` 把这类候选列出来，人工或 AI 确认后再写进词表。

品牌词表结构：

```json
{
  "brands": [{"name": "品牌名", "aliases": ["别名"], "type": "competitor_open", "domains": ["官网域名"]}],
  "case_sensitive_aliases": ["要区分大小写的写法，比如和普通词撞的缩写"],
  "competitor_site_domains": ["算作「竞品网站」的同类平台域名，不挂具体品牌"]
}
```

别名按客户、按品牌各自补，不做跨客户共享。出报告前跑 `reconcile_brand_recognition.py` 查拼写漏判和常用词误判，用 `mine_brand_lexicon.py` 挖词表里没有的新品牌候选。

## 开发与维护

### 依赖

仓库根目录 `requirements.txt` 是整份依赖，`python3 -m pip install -r requirements.txt`，需要 Python ≥ 3.12。只有 `geo-prompt-selection-builder`（语种门禁、`--agent sdk`）和 `geo-presales-report-audit`（截图标注、引用清洗）要第三方包，各自的清单在它目录下；其余 Skill 和 `shared/` 的脚本只用标准库。所有第三方包都是可选的，缺了只降级对应功能，不挡其余流程。

### 跨 Skill 路径

脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录，统计实现从 `<skills>/geo-metrics/scripts` 导入（包名 `geo_presales_core`）。单独部署时用 `GEO_PRESALES_SKILLS_ROOT` 指定 skills 根目录。脚本按 `python3 -I` 隔离模式跑也能启动。

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

`geo-metrics` 的单元测试在 `geo-presales-report-editor/scripts/tests/test_geo_presales.py`（core）和 `geo-presales-report-audit/tests`（去引用）。几个目录里有同名的 `test_scripts.py`，按上面逐个目录跑，别合成一条命令。测试不调用外部 AI 平台。

### 发布

`skills/` 的真源在本地，仓库是发布副本。发布走本地 `shared/scripts/redact_publish_tree.py`：建发布树 → `apply` → `scan` 必须 0 命中 → 在脱敏树里跑全部测试 → 复制进仓库提交。

### 不随仓库分发

按客户生成的品牌词表、引用域名缓存、`build/` 运行产物、客户 Case 与采集数据都不入库，`.gitignore` 已排除。仓库里的 Case 示例（`skills/geo-prompt-selection-builder/references/input-examples/` 下的 b2b、b2c 两份）是通用模板，不是真实客户。
