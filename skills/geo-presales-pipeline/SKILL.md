---
name: geo-presales-pipeline
description: This skill should be used when running the full overseas GEO presales flow end to end — from an evaluation Case through Prompt generation, Scrapeless answer collection, crawl integrity, sentiment and rendering, to the customer-facing single-file HTML diagnosis report — or when resuming that flow from any intermediate stage (question bank ready, collection directory ready). It orchestrates stage order and, at each pause point, invokes the dedicated skill (geo-presales-prompt-builder, geo-presales-crawl-integrity, geo-presales-report-builder, geo-presales-sentiment-judge) whose contract governs that stage. Do not use it to define or re-derive any metric caliber, to audit brand mention recognition (geo-presales-report-audit), to produce the upload CSV or written conclusions (geo-presales-report-editor), or to build or research the Case itself (geo-presales-eval-case-builder / overseas-geo-competitor-research).
metadata:
  author: 海外 GEO 项目
  version: "2.0.0"
---

# 售前全链路编排：Case → 生词 → 采集 → HTML 报告

## 目标与边界

把一条评测 Case 一路带到可交客户的单文件 HTML 报告。**本 skill 只编排、零新逻辑**：口径、校验、计算、渲染都在被调 skill 及其脚本里。这里只回答两个问题：下一步跑什么；停下来时请哪个 skill 出场。

- 负责：阶段顺序、断点续跑、每个暂停点的分派。
- 不负责：任何指标口径（builder/editor 统一实现）、采集缺陷的判定规则（crawl-integrity）、Claim 判读规则（sentiment-judge）、品牌纠错与 Bad Case（report-audit）、上传 CSV 与结论（report-editor）、Case 研究与竞品冻结（eval-case-builder / competitor-research）。
- 只要指标数字、不出报告时，直接用 `geo-presales-report-builder` 的 `build_report_data.py`（同样要先过 crawl-integrity）；只判情感用 `geo-presales-sentiment-judge`；改已有报告走 `geo-presales-report-audit` → `geo-presales-report-editor`。

## 从哪一段进

| 手里有什么 | 从哪步开始 |
| --- | --- |
| 只有品牌信息，没有 Case | 先走 `geo-presales-eval-case-builder`，产出 Case 后回到第 1 步 |
| Case（`presales-case-input/v1` payload 或飞书 Record） | 第 1 步 |
| 已导出的 9 字段题（上传 CSV） | 第 3 步 |
| 采集目录 `<collect>/scraper.<平台>/<REGION>/*.json` | 第 4 步（旧采集目录没有 manifest，第 4 步会跳过采集检查） |

## 第 1–2 步：生词

1. 用 Skill 工具 invoke `geo-presales-prompt-builder`，读它的 SKILL.md 和 `references/selection-mode.md`。
2. 先归一化 Case：`python3 <skills>/geo-presales-prompt-builder/scripts/normalize_case.py <payload.json> -o normalized.json`。`ok=false` 时把 `errors` 原样交回 Case 上游，不替上游补字段。
3. 按 selection-mode.md 第 2–8 步生词，产出 `bank.json` 和每个市场一份 9 字段上传 CSV（`query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`）。无人值守时改用 `scripts/run_selection_mode.py` 一条命令跑完。
4. 选词 validator `validate_after_sales_set.py` 与导出脚本 `export_upload_csv.py` 都要退出码 0，然后做一遍语义 review。检查通过只代表确定性门槛通过，不等于客户已批准。

## 第 3 步：采集（付费）

采集只有一套实现：`<skills>/geo-presales-report-builder/scripts/collect_answers.py`。它直接调 Scrapeless AI Scraper API，按题库行号落盘 `<collect>/scraper.<平台>/<REGION>/<NNNN>.json`，格式和 builder、integrity 对齐。

```bash
cd <skills>/geo-presales-report-builder
python3 scripts/collect_answers.py --questions <上传.csv> --out <采集目录> --regions US --dry-run
export SCRAPELESS_API_KEY=...          # 只从环境变量读，不写进文件或命令参数
python3 scripts/collect_answers.py --questions <上传.csv> --out <采集目录> --regions US
```

- 售前默认参数：平台为 ChatGPT、Gemini、Google AI Mode、AIO（`chatgpt,gemini,aimode,overview`，AI Mode 和 AIO 是两个平台），每题每平台 1 次，联网搜索和购物卡都开。区域按 Case 的目标市场传，多个市场写 `SG,MY`。
- **先 `--dry-run` 报调用量**，再真实调用。题量、平台或区域超出用户已确认的范围时，先确认再跑。
- 每格独立重试（默认最多 6 次）。失败页、空回答、题面对不上都按 core 的 `answer_validity` 判无效；重试耗尽仍无效的格会移到 `_collector/unrecoverable/`，登记在 `collect-manifest.json`，不进任何分母（integrity D5），各平台分母因此可能不相等。
- AIO 例外：Google 不是每次都出 AI 概览，AIO 接口返回 success 就算采到，空正文记为「本次未触发」，不重试、不阻断，也不进提及分母。
- 中断或部分失败后重跑同一命令即可续采，已经有效的格不会重复付费；要重采已移出的格，加 `--retry-unrecoverable`。
- 鉴权、权限或余额错误（401/402/403）会让整批立即停下，退出码 2。
- 采集写入数据输出目录，不写进 skill 目录。

## 第 4 步起：驾驶脚本跑到报告

```bash
cd <skills>/geo-presales-report-builder
python3 scripts/run_pipeline.py \
  --collect <采集目录> --questions <上传.csv> --case <v8 题库.json 或 Case.json> \
  --lexicon <品牌词表.json> --out-dir <输出目录> \
  --brands "目标,配置1,配置2,配置3" --target <目标品牌> --brand-name <品牌> \
  --regions US [--theme-keywords <主题关键词.json>] [--brand-suffixes "Dash Cam"] [--dry-run]
```

- `--case` 可以直接传 v8 题库 JSON，脚本会取其中的 `config.case_fields` 写成 `<输出目录>/case.json`。
- 阶段 -1 会验收采集目录：没采齐时以退出码 3 暂停，并打印 `collect_answers.py` 的采集命令。驾驶脚本只检查、不代跑付费采集。
- **退出码 3 = 暂停点**，会打印缺什么文件。按下表补齐后**重跑同一命令**续跑。暂停点产物（词表、claims、聚类映射、译文）重跑时不会被覆盖；要重做，先删掉对应文件。
- 不带 `--brands`/`--target` 会跳过情感环节，报告情感板块显示 pending。这只用于中途查看，正式交付不允许。
- `--lexicon` 必填：声量份额与提及率排名的分母必须是全部纳入品牌（目标品牌 + 3 个配置竞品 + 开放词表命中），否则算出来的数不成立。换品类时还要传 `--theme-keywords` 与 `--brand-suffixes`，否则主题矩阵落空，品牌名会带品类后缀。

## 暂停点指挥表

**铁律：每到语义暂停点，先用 Skill 工具 invoke 对应子 skill，让它的契约进入上下文后再产出文件。禁止凭记忆写口径，禁止用关键词自动打标。**

| 停在哪 | 请谁出场 | 干什么 |
| --- | --- | --- |
| 第 2 步选词 validator 或导出检查不通过 | `geo-presales-prompt-builder` | 按 errors 改题；新增事实交回 Case Builder，不在题面扩张 |
| 阶段 -1 采集未齐 | 用户确认调用量 | `--dry-run` 报数，确认后跑 `collect_answers.py` |
| 阶段 0 采集校验退出码 2（阻断）或 1（警告） | `geo-presales-crawl-integrity` | 按缺陷目录逐条定位到平台和文件，修采集或显式降级口径后续跑；不许带着缺陷算指标 |
| 阶段 1 词表不存在 | 人工（Suda 或授权人） | 脚本已挖出候选 CSV，由人工冻结成 `brands[].name/aliases/type`。机器分不清品牌名和品类词，**这步不能自动化**；已有同品类冻结词表可直接复用 |
| 阶段 2 数据生成失败 | `geo-presales-report-builder` | 读数据接口契约排障；不要绕过 build_report_data 手写数据 |
| 阶段 3b Claim 抽取 | `geo-presales-sentiment-judge` | 按 Claim 层契约逐单元拆原子 Claim；拿不准的进 review-queue 交 Suda 裁决 |
| 阶段 3d / 3f 两趟聚类 | `geo-presales-sentiment-judge` | claim→attribute、attribute→theme；维度优先于极性，theme 必须中性；输入是去重清单，同一 claim 只判一次 |
| 阶段 4 译文未齐 | 翻译（语义工作，派 haiku 子代理即可） | 按批次翻成 `<批次>-zh.json`：保留 markdown 结构、品牌名与型号留英文、URL 与数值原样、不增删内容、每翻完一条立即落盘。译文必做，报告是给中文读者看的 |
| 阶段 6 渲染完成 | 浏览器验证 | 逐个切换国家、平台、主题，确认各模块有数、无空白、无变形；判据见 report-builder 的渲染规范 |

阶段 3 的机器工序（3a 抽取、3c/3e 去重清单、3g 回装、3h 统计、3i 接入）由脚本自动跑，不需要分派。3h 与 3i 之间有 `--expected-metrics` 对账门禁，两处实现不一致会报错；报错时回 sentiment-judge 排查口径，不许改数硬过。

## 完成与出口

- 完成标准：HTML 渲染成功，`verify_report_data.py` 通过，浏览器逐切片检查无空白、无变形。命令跑完不算完成。
- 报告数字有疑点（品牌识别错、排名不对）→ `geo-presales-report-audit`，改完从阶段 2 重跑。
- 要交上传 CSV 和客户结论 → `geo-presales-report-editor`，输入是本链产出的已确认数据。
- 替换已交付报告，或修复抽取器后重跑 → 先读 report-builder 的《重跑与产物卫生》，隔离重跑，不许原地覆盖。
