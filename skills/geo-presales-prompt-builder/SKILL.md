---
name: geo-presales-prompt-builder
description: Generate the overseas GEO presales diagnosis Prompt set (售前生词) from a brand Case using the selection method — normalize the Case, research public signals with no browser login, judge attributes against competitors, draw matrix rows, cluster Topics, write Prompts, validate, and export the nine-field upload rows for the online diagnosis report. Also the one-command online runner. Do not use it for collecting answers, building the report, client confirmation Bases, or after-sales monitoring sets (geo-prompt-selection-builder).
metadata:
  author: Overseas GEO Project
  version: "5.0.0"
---

# 售前生词

## 做什么

售前诊断报告的第一步：品牌 Case 进来，生成一批诊断题，交给采集和出报告。售前诊断里只有这一步归本 skill。

| 售前诊断的环节 | 由谁做 |
|---|---|
| 生词 | 本 skill |
| 采集 AI 回答、出 HTML 报告 | 线上：现有的 Dify 流程；本地：`geo-presales-pipeline` 编排，`geo-presales-report-builder` 等执行 |

生词用的是选词方法：先做公开调研，判断属性相对竞品的位置，画买家处境矩阵，从矩阵里聚主题，再写题。写题规则只有一份，在 `geo-prompt-selection-builder`，本 skill 按章节引用、不复制；那个 skill 里的对客确认表、试跑、锁定正式题，售前都不做。

最终交给线上的是每个市场一批题，每题 9 个字段：

`query, question_zh, topic, diagnosis_intent, tags, question_types, purchase_intent, persona_name, scene_name`

研发可以走上传 CSV，也可以走接口传入，字段相同。线上给销售用时，只有生词这一步换成本 skill，生成的题直接进 Dify 采集与报告流程，不给销售修改生成词的入口。

## 怎么做

1. 读 [Case 输入合同](references/input-contract.md)。线上表单和本地飞书记录都先跑 `scripts/normalize_case.py`（飞书加 `--from-base-record`）；`ok=false` 时把 `errors` 原样交回，不替上游补字段。
2. 按 [售前生词步骤](references/selection-mode.md) 做完第 2–8 步：研究预跑 → 公开信号 → 属性与相对竞品 → 矩阵行与优先级 → 聚主题 → 写题 → 校验与导出。每一步的判断记在题库 JSON 的哪个字段，那里都写了。
3. 交付：`bank.json`（内部底稿）和导出的 9 字段题。选词 validator 与导出脚本都是退出码 0 才算完成。

线上无人值守时用一条命令跑完：

```bash
python3 scripts/run_selection_mode.py run --case <payload.json> --market <市场代码> --platforms <AI 平台> --out <新工作目录> --agent sdk
```

宿主有自己的 agent 框架时，把 `--agent sdk` 换成 `--agent-cmd "<命令>"`。环境变量、退出码和产物见脚本开头说明。

## 文件

| 文件 | 用途 |
|---|---|
| `references/input-contract.md` | Case 输入合同：字段、必填、错误码 |
| `references/selection-mode.md` | 售前生词步骤与题库 JSON 字段 |
| `references/locale-templates.json` | 已登记的题库语言 |
| `references/input-examples/` | B2B、B2C 两份 Case 示例 |
| `scripts/normalize_case.py` | Case 归一化 |
| `scripts/run_selection_mode.py` | 线上一条命令入口 |
| `scripts/validate_question_bank.py` | 旧 v8 题库校验，以及上传行检查（导出脚本会调用） |
| `references/legacy/` | 已归档的默认模式规则，只用于读懂 10-29 之前的旧题库 |

题型与后端字段的对照见 `../shared/canonical-intent-mapping.md`。

## 不做的事

- 不采集回答、不算指标、不出报告。
- 不做对客确认表、试跑、锁定正式题（售后选词的事）。
- 不新增或替换竞品；竞品以 Case 为准。
- 不用浏览器登录态；打不开的站按 selection-mode.md「线上没有浏览器」处理。
