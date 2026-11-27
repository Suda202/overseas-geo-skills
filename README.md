# 海外 GEO Skills

6 个 Skill 加一个共享目录 `shared/`，每项能力只由一个 Skill 负责。`.agents/skills/` 是内部真源，本仓库是发布副本；改动从真源推向仓库。

| Skill | 一句话 |
| --- | --- |
| `geo-prompt-selection-builder` | 选词：品牌资料 → 矩阵 → 主题 → 题库 → 上传 CSV / 对客确认表 |
| `geo-monitoring` | 采集与采集检查：全库唯一的采集程序，跑试跑、基线、日常监测 |
| `geo-metrics` | 所有统计口径与唯一实现：品牌识别、提及、引用、商品卡、情感 |
| `geo-presales-report-builder` | 报告数据层与 HTML 渲染 |
| `geo-gap-diagnosis` | 缺口诊断；售前报告的「诊断与行动」也由它写 |
| `geo-presales-pipeline` | 售前全链路编排，只排阶段和暂停点，零口径 |

## 从 0 到 1：生词 → 采集 → 生成 HTML 报告

起点是一份品牌资料（线上表单或本地文件，字段见 `skills/geo-prompt-selection-builder/references/input-contract.md`）；归一化在生词脚本内部完成，不用单独产 Case 文件。

| 阶段 | 做什么 | Skill | 产物 |
| --- | --- | --- | --- |
| 1 生词 | 调研 → 约束条件 → 矩阵 → 主题 → 写题 → 校验导出 | `geo-prompt-selection-builder` | `bank.json` + 每市场一份 5 列上传 CSV |
| 2 采集 | 每题每平台 1 次，采完做完整性检查 | `geo-monitoring` | 采集目录 + 缺陷清单 |
| 3 生成 HTML 报告 | 指标与报告数据 → 情感 → 诊断与行动 → 渲染 → 验证 | `geo-presales-pipeline` 编排：`geo-metrics` 口径、`geo-presales-report-builder` 组装与渲染、`geo-gap-diagnosis` 写诊断 | 单文件 HTML |

第三阶段内部的顺序是固定的：指标与报告数据 → 情感（必做）→ 诊断与行动（必做）→ 渲染 → 独立复算与前端对账。

`geo-presales-pipeline` 把采集检查到渲染串起来，一条命令跑到下一个暂停点：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py \
  --collect <采集目录> --questions <上传.csv> --case <bank.json 或 Case.json> \
  --lexicon <品牌词表.json> --out-dir <输出目录> \
  --brands "目标,配置1,配置2,配置3" --target <目标品牌标准名> --brand-name <品牌> \
  --regions US --diagnosis <diagnosis.json>
```

`--case` 可以直接传生词产出的题库，脚本取其中的 `config.case_fields`。退出码 3 是暂停点，补齐后重跑同一命令续跑；常见暂停：采集没齐、词表不存在或查漏没过、引用域名未判读超过 5%、译文未齐、缺情感、缺诊断。

### 售前报告硬规则

- **情感必做**：缺 `--brands`/`--target` 时开跑前暂停；确实不出要 `--allow-missing-sentiment "<理由>"`。
- **诊断与行动必做**：缺 `diagnosis.json` 停在阶段 5d；确实不出要 `--allow-missing-diagnosis "<理由>"`。四张「诊断」卡是模块里唯一的结论层，模板结论卡已删。
- **商品卡默认不出**：要出传 `--shopping-cards 开`，且采集里至少有一张带目录的商品卡。
- **可见度与情感共用展示品牌**：本品 + 配置竞品必留，剩余名额按提及率补开放品牌，最多 5 个；没判读的显示「—」。
- **采集平台**：默认 ChatGPT、Gemini、Google AI Mode、Google AI Overview；`--platforms all` 共 9 个，含 Perplexity、Copilot、Grok、Alexa、Bing AI Mode。
- **词表是分母**：提及率排名与声量份额按全部纳入品牌算，`--lexicon` 必填。
- **译文必做**：抽屉里逐批翻成中文，缺 `<批次>-zh.json` 会暂停。

## 每个 Skill 负责什么

| Skill | 负责 | 交给谁 |
| --- | --- | --- |
| `geo-prompt-selection-builder` | 业务范围、调研、约束条件、目标客户与场景、矩阵、主题、写题、校验导出、试跑后回写 | 采集与报告（`geo-monitoring`、`geo-presales-pipeline`） |
| `geo-monitoring` | 采集与采集检查；试跑、正式基线、日常采集与基线 HTML | 指标口径（`geo-metrics`）、诊断（`geo-gap-diagnosis`） |
| `geo-metrics` | 品牌识别、正文清洗、引用抽取、引用来源分类、全部指标与样本范围 | 组装与渲染（report-builder）、结论撰写（诊断） |
| `geo-presales-report-builder` | 数据层、情感与诊断接入、HTML 渲染、校验与对账 | 指标公式、采集、诊断内容 |
| `geo-gap-diagnosis` | 售前「诊断与行动」素材与写法；售后缺口诊断与优化机会表 | 采集、指标口径、写内容本身 |
| `geo-presales-pipeline` | 阶段顺序、断点续跑、暂停点分派 | 所有口径与实现都在被调 Skill |

## 常用命令

```bash
# 生词（线上一条命令）
python3 skills/geo-prompt-selection-builder/scripts/run_selection_mode.py run \
  --case <品牌资料.json> --market <市场> --platforms <AI 平台> --out <工作目录> --agent sdk

# 采集：先报调用量，再真实调用；采集前设 no_proxy=api.scrapeless.com
cd skills/geo-monitoring
python3 scripts/collect_answers.py --questions <上传.csv> --out <采集目录> \
  --regions US --platforms all --dry-run
python3 scripts/audit_crawl_integrity.py --collect-dir <采集目录> --target <品牌>
```

- 签约后节奏：试跑每题每平台 3 次；正式基线每 query × 平台 × 国家 × 语言 7 次；日常发现题每天 1 次、其他类型每月 1 次。
- 基线 HTML 复用售前数据层与渲染层，口径同一套；默认不出商品卡、情感、难度、诊断，要出在 config 的 `extra_modules` 写明。
- 诊断两种用法：售前按 `skills/geo-gap-diagnosis/references/diagnosis-writing.md` 写 `diagnosis.json`；售后读基线出优化机会诊断表。

## 统计口径

全库只有一份实现，在 `skills/geo-metrics/scripts/`，其他 Skill 只调用；样本范围与对客命名见 `skills/geo-metrics/references/metric-scope-and-copy-contract.md`。

- 提及类指标统计全部意图类型；点名品牌的题不置「—」，由看报告的人按主题、意图类型筛选。
- 引用份额按未去重次数算：核心洞察与提及率同一批回答，引用模块统计全部有效回答。
- 情感按 Claim 判读，正向率 = 正向 ÷（正向 + 负向），不设中性档。
- 引用来源分类：配置竞品与开放品牌官网都算「竞品网站」，开放品牌没写 `same_category` 默认同类；品牌站索引 `assets/domain-brand-sites.json` 随仓库发布，只参考同品类条目。
- 两处刻意保留的第二实现：`verify_report_data.py` 复算切片、`report-engine.js` 浏览器现算，由 `check_engine_parity.js` 对账。

## 开发与维护

依赖见根目录 `requirements.txt`，Python ≥ 3.12；只有 `geo-prompt-selection-builder` 要第三方包。脚本用 `Path(__file__).resolve().parents[2]` 找 skills 根，单独部署用 `GEO_PRESALES_SKILLS_ROOT`。

```bash
python3 -m pytest -q skills/geo-metrics/tests
python3 -m pytest -q skills/geo-presales-report-builder/tests
python3 -m unittest discover -s skills/geo-prompt-selection-builder/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/shared/scripts -p 'test_*.py'
python3 skills/geo-gap-diagnosis/evals/e2e_gap_diagnosis.py
```

发布走 `shared/scripts/redact_publish_tree.py`：建发布树 → `apply` → `scan` 0 命中 → 树内测试全过 → 提交。`scan` 拦密钥、内部链接、本地路径；客户/竞品名可留（2026-11-18 起），客户品牌资料样例走 `shared/publish-templates/` 换模板。不随仓库分发按客户生成的 `brand_lexicon.*.json`、`build/`、运行报告；`category-taxonomy.json`、`domain-brand-sites.json`、`domain-categories.json` 随仓库发布。
