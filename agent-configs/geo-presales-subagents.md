# GEO 售前链路 — 三个子 agent 规格

把原本一个 agent 扛 10+ 工具的链路，切成 A/B/C 三段。**段与段之间只传文件路径**，不内联大对象、不跨段用 `$ref`——这是消灭 400 和 `$ref` 指错的根本手段。

## 全局铁律（每个子 agent 的系统提示都要包含）

1. **绝不手工拼 JSON 字符串**。请求体一律由 `json.dumps` / `JSON.stringify` 从对象生成。
2. **大对象先 `write_file` 落盘，后续一律按 `*_path` 引用**，不把同一对象内联进 `invoke_batch` 或别的工具。`write_file` 的 `content` 传 **JSON 对象/数组**（服务端自己序列化），不要传拼好的字符串。
3. **`$ref` 只能引用"本段内、已成功返回"的调用**，且路径要落到真实字段（如 `{"$ref": "0.data.path"}`）。**禁止** 指向 `stdout` / 不存在的键。凡是 `$ref` 可能指错的地方，直接写字面路径，不用 `$ref`。
4. **调用任何工具前，先读它的契约**（工具 docstring 或对应 SKILL.md / references），按文档字段名传参，不凭记忆。
5. 失败的恢复顺序：读 `error` / `error_code` → 修正参数 → **用路径重试**；不重建整条链路。

## 段交接契约（唯一允许跨段传递的东西）

```
case_path        = /tmp/geo-<品牌>/case.json
bank_path        = /tmp/geo-<品牌>/question-bank.json
questions_csv    = /tmp/geo-<品牌>/questions.csv
collect_dir      = /tmp/geo-<品牌>/collect
report_data_path = /tmp/geo-<品牌>/report-data.json
research_path    = /tmp/geo-<品牌>/research.json        （竞品证据，可选）
report_html_path = /tmp/geo-<品牌>/report.html
```

上一段结束时，把本段产出的**路径 + 关键校验结论**（如 validate 是否通过、采集有效格数）作为结果返回，下一段只取这些路径。

---

## 子 agent A — Case 与题库构建

**职责**：竞品研究冻结 → Case 归一化 → 写 `case.json` 与 `question-bank.json` → 题库校验。只到"题库可用"为止，不采集。

**输入**：原始 case payload（中文 Case 字段）、竞品候选（名称 + 官网域名）、竞品研究证据（research 对象或 `research_path`）。

**输出**：`case_path`、`bank_path` + `validate_question_bank` 的 `{valid, errors, summary}`。

**工具契约摘要**

| 工具 | 必填参数 | 关键点 |
|---|---|---|
| `competitor_research_finalize` | `run_dir` + （`research` 或 `research_path`） | 大对象用 `research_path`。每个候选的 `evidence_bindings.*` **只能引用本候选 `evidence_ids` 里的 ID**，跨候选引用会被 ContractError 拒绝 |
| `normalize_case` | `payload` | 返回 `data.normalized.case_fields`，可直接用于写 `case.json` |
| `write_file` | `path` + `content` | `content` 传对象；落盘 `case.json` / `question-bank.json` |
| `validate_question_bank` | `bank_path`（或内联 `data`） | 按路径校验，返回 `{valid, errors, warnings, summary}` |

**题库硬契约（`attribute_plan`，最易错）**

```
attribute_plan[i] = { "topic_id", "priorities": { "P1": [], "P2": [], "P3": [] }, "excluded": [] }
```
- `excluded` 在**条目外层**，与 `priorities` 平级；**不要塞进 `priorities`**。
- `priorities` 只含 `P1/P2/P3` 三个键，各为**数组**（空写 `[]`，不省略）。
- `schema_version = overseas-geo-question-bank/v8`；`config` 是闭合合同，字段见 `presales-contract.md`。

**错误恢复退路**
- `validate_question_bank` 返回 `valid:false` → 逐条读 `errors`，改题库对象、重新 `write_file`、再校验；不改流程。
- finalize 报 ContractError（证据越界）→ 把越界的 `evidence_bindings` 改回本候选 `evidence_ids` 内的 ID，重写 `research.json` 后重跑 finalize。
- 任何 400 → 说明请求体被手工拼了；改为 `write_file` + 路径，重发。

---

## 子 agent B — 采集

**职责**：导出上传 CSV → 采集答案 → 爬虫完整性审计。不建题库、不出报告。

**输入**：`bank_path`。

**输出**：`questions_csv`、`collect_dir` + 审计结论（有效格数、阻断缺陷、警告）。

**工具契约摘要**

| 工具 | 必填参数 | 关键点 |
|---|---|---|
| `export_question_bank_csv` | `bank_path` + `out` | 返回 `{path, rows}`；CSV 由服务端按固定规则导出，不手工拼 |
| `collect_answers` | `questions_csv` + `out_dir` + `regions` | 可选 `platforms`。需要 `SCRAPELESS_API_KEY`。`dry_run` 只打印不调用 |
| `audit_crawl_integrity` | `collect_dir` + `target` | `collect_dir` 不存在时返回 `skipped:true`（视为未采集，非缺陷） |

**错误恢复退路**
- **题面不一致 / 采集题面过期**：`collect_answers` 按"文件是否存在"判断格子已采。若题库改了题面而旧样本还在，**先删掉过期平台的 `scraper.<平台>/` 目录**（可备份），再重跑 `collect_answers`——它只补采缺失格，避免全量重采浪费 API。
- 审计报**阻断性缺陷** → 停止，把缺陷清单交还；只有警告（如 `CITATION_FIELD_BODY_MISMATCH`）时可放行，但在结果里记为已知警告。
- `collect_answers` 报缺 `SCRAPELESS_API_KEY` → 环境配置问题，交还给上层，不在脚本参数里塞 key。

---

## 子 agent C — 报告

**职责**：报告数据构建 → 情感单元抽取 → Claim 抽取/聚类/统计 → HTML 渲染 → 独立校验。不采集。

**输入**：`bank_path`、`questions_csv`、`case_path`、`collect_dir`、品牌词表（目标品牌 + 竞品别名）。

**输出**：`report_data_path`、`report_html_path` + `verify_report_data` 结论 + 情感/claim 指标路径。

**工具契约摘要**

| 工具 | 必填参数 | 关键点 |
|---|---|---|
| `build_report_data` | `collect_dir` + `questions_csv` + `case_path` + `out` | 缺件会返回清晰错误码（`MISSING_COLLECT_DIR` 等）。可选 `regions`/`lexicon_path` |
| `sentiment_extract` | `bank_path` + `collect_dir` + `output` + （`aliases` 或 `lexicon`） | 可选 `inline:true` 直返 units。**只认 `aliases`（逗号分隔）或 `lexicon`（词表路径），不认 `brand_names`** |
| `claims_cluster_list` | `input_path` + `key` + `output` | 两趟聚类：先按 `claim` 归 attribute，再按 attribute 归 theme |
| `claims_metrics` | `claims_path` + `brands` + `out_metrics` | `brands` 逗号分隔（目标 + 竞品） |
| `render_report` | `report_path`（或内联 `report_data`） | 返回 HTML / 落盘 |
| `verify_report_data` | `report_path` + `collect_dir` | 独立校验报告数据与采集的一致性 |

**情感品牌来源铁律**
- 单品牌：`aliases` = 逗号分隔字符串（含当地文字转写），可加 `brand` 指定写入名。
- 多品牌无现成词表：把全部品牌名逗号分隔塞进 `aliases`。
- 有词表：`lexicon` = 词表 JSON 路径（`brands[].name/aliases/type` 或「标准名→别名 list」）。

**错误恢复退路**
- `sentiment_extract` 报「必须提供 --aliases 或 --lexicon」→ 参数名用错（多半误传 `brand_names`），改成 `aliases`/`lexicon` 重跑。
- `sentiment_extract` 报「题面完整性失败」→ 采集题面与题库不一致：先核对题库版本，必要时回到子 agent B 重采，不在本段强行抽取。
- `build_report_data` 返回 `MISSING_*` → 缺哪个文件补哪个（回 B 采集或回 A 出题库），不跳过校验。
- `verify_report_data` 不过 → 读差异项，定位是采集还是报告构建的问题，交还对应段。

---

## 编排建议

- 三段**串行**：A 出题库 → B 采集 → C 出报告。段间只传上面那组路径。
- 每段内部可用 `invoke_batch` 打包自己的 2–4 个工具调用（控制调用次数），但**大对象仍先 `write_file`**，批次里只留路径。
- 平台若对单 agent 工具调用次数设限，拆段后各段独立计数，自然绕开"同一工具 ≤3 次"的墙。
