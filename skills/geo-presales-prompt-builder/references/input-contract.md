# 售前 Case 输入合同（presales-case-input/v1）

给接入方（线上接口、本地飞书读取）用。调用方按本文组好一个 JSON，先过 `scripts/normalize_case.py` 校验和归一化，通过后再交给 skill 生成题库。不需要读 skill 的其他文件。

## 1. 调用流程

1. 调用方按第 2–5 节组装 payload。
2. 运行归一化：

   ```bash
   python3 scripts/normalize_case.py payload.json -o normalized.json
   ```

   退出码 `0` 表示可以生成，`1` 表示输入有错，`2` 表示文件读不了或 JSON 坏了。不能运行 Python 的环境，按本文规则在接口层实现同样的校验，并用第 8 节的端到端校验对账。
3. `ok = true` 时把 `normalized` 交给 skill；`ok = false` 时把 `errors` 原样返回给上游补数据，skill 不替上游补字段。

## 2. 顶层结构

```json
{
  "input_version": "presales-case-input/v1",
  "case": { "...": "见第 3 节" },
  "options": { "locale": "en", "generation_stage": "discovery" },
  "handoff": { "...": "见第 5 节，可省略" }
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `input_version` | 是 | 固定为 `presales-case-input/v1` |
| `case` | 是 | 品牌业务字段，见第 3 节 |
| `options` | 否 | 见第 4 节 |
| `handoff` | 否 | 来源与客户确认状态，见第 5 节 |

出现未定义的字段会报错（`unknown_field`），避免字段名拼错后被悄悄忽略。

## 3. `case` 业务字段

字段名用中文。所有字符串会去掉首尾空白；`null` 和空字符串视为没填。必填项与线上「配置海外诊断参数」表单的星号一致，业务描述字段全部选填。

| 字段 | 线上表单 | 类型 | 必填 | 规则 |
|---|---|---|---|---|
| `公司名` | 公司名（英文） | string | 是 | 公开英文主体名 |
| `业务 / 产品名称` | 业务/产品名称（英文） | string | 否 | 一条 Case 只写一条产品线 |
| `品牌名称` | 品牌名称（英文） | string | 是 | |
| `业务模式` | 业务模式 | string | 是 | 只接受 `B2B`、`B2C`、`B2B / B2C` |
| `品类` | 品类 | string | 是 | |
| `目标企业画像`（也可传 `垂直行业`） | 垂直行业 | string 或 string[] | 否 | 仅 `B2B` 和 `B2B / B2C` 可填，纯 `B2C` 必须省略。接口直接传 `垂直行业` 即可，skill 映射为 `目标企业画像`；两个都传时以 `目标企业画像` 为准并告警 |
| `目标客户` | 目标客户 | string 或 string[] | 否 | |
| `痛点` | 痛点 | string 或 string[] | 否 | |
| `使用场景` | 使用场景 | string 或 string[] | 否 | |
| `产品特性` | 产品特性 | string 或 string[] | 否 | |
| `差异化优势` | 差异化优势 | string 或 string[] | 否 | 数组会按「，」合并成一个字符串 |
| `适用边界` | 适用边界 | string | 否 | |
| `主题` | 无（2026-10-29 起线上表单去掉监测主题） | string 或 string[] | 否 | 生词时主题从矩阵行聚出；填了只当矩阵行优先级的业务重点线索，不当主题名单；不传时归一化结果的 `topic_source` 为 `to_derive`。旧 Case 带着主题也能通过：1–3 个，第一个记为宽泛主题 |
| `官方域名` | 官方域名 | string | 是 | 以 `http://` 或 `https://` 开头的完整网址 |
| `竞品` | 竞品（添加竞品） | object[] | 是 | 1–3 个，见下表 |
| `补充内容` | 补充内容 | string | 否 | 省略时按空字符串处理 |
| `购买标准`、`集成与兼容`、`信任与合规` | 无 | string 或 string[] | 否 | 线上表单没有这三项，只有飞书 Case 会带。仅 `B2B` 和 `B2B / B2C` 可填，纯 `B2C` 必须省略 |
| `地理与市场` | 无（见 `options` 的国家/地区） | string 或 string[] | 否 | |

**多值字段传字符串还是数组**：`目标企业画像`、`目标客户`、`痛点`、`使用场景`、`产品特性`、`主题` 两种都收。传数组时逐项展开成 `痛点 1`、`痛点 2`……；传字符串（表单的单个文本框）时整段作为一项，不按逗号拆，因为值本身也可能含逗号（例如「输出电压和功率，同时控制安全风险」），拆分结果不可靠。能拿到分项时优先传数组。

**业务字段留空会怎样**：不报错。字段越少，题目越依赖品类、主题和补充内容，诊断能覆盖的买家关注点也越少。`购买标准`、`集成与兼容`、`信任与合规` 传了 `待人工确认` 会按未填写处理并告警。

**线上表单里不属于本合同的项**：AI 平台、国家/地区等采集配置不传给 Case；其中「语言」映射到 `options.locale`，「AI 平台」传给入口脚本的 `--platforms`。手动上传题目时不调用生词 skill。

`竞品` 每一项：

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `名称` | string | 是 | 英文规范名称；竞品之间不能重名 |
| `官网域名` | string | 是 | 完整网址 |

竞品只收这两项，传别的字段报 `unknown_field`。竞品不分主题。

## 4. `options`

| 字段 | 默认 | 可选值 |
|---|---|---|
| `locale` | `en` | 题面语言，对应线上表单的「语言」；必须是 `references/locale-templates.json` 已登记的键（当前为 `en`、`th`） |
| `generation_stage` | `discovery` | `discovery`：只生成发现型问题；`diagnostic`：在已有题库上补竞品、评价题，此时调用方必须同时提供原 Discovery 题库 |

## 5. `handoff`（可省略）

```json
{
  "confirmation_status": "partial",
  "confirmed_fields": ["主题", "竞品"],
  "sources": [{ "url": "https://www.example-biz.example", "summary": "官网产品与服务页" }]
}
```

| 字段 | 规则 |
|---|---|
| `confirmation_status` | `none`（客户未确认，默认）、`partial`、`confirmed` |
| `confirmed_fields` | 客户已确认的字段名，必须是第 3 节里的字段 |
| `sources` | 研究来源，每条至少有 `url` |

省略 `handoff` 时，按「客户未确认」生成题库，产出会标为待客户确认的 V1。

## 6. 返回结构

成功：

```json
{
  "ok": true,
  "errors": [],
  "warnings": [{ "code": "pending_value", "field": "购买标准", "message": "购买标准 为「待人工确认」，已按未填写处理" }],
  "normalized": {
    "case_fields": { "痛点 1": "...", "主题 1（宽泛）": "...", "竞品 1": "...", "...": "..." },
    "brand_name": "...",
    "official_domain": "...",
    "derived_field_sources": { "brand_name": "品牌名称", "category_label": "品类", "official_domain": "官方域名" },
    "topics": [{ "topic_id": "topic_1", "source_field": "主题 1（宽泛）", "source_value": "..." }],
    "topic_source": "case",
    "competitor_selection": { "status": "frozen", "selection_count": 3, "formal_competitors": [ "..." ] },
    "locale": "en",
    "generation_stage": "discovery",
    "handoff": { "confirmation_status": "none", "confirmed_fields": [], "sources": [] }
  }
}
```

失败时 `ok = false`，没有 `normalized`，`errors` 列出全部问题（不在第一个错误处停下）：

```json
{
  "ok": false,
  "errors": [{ "code": "missing_field", "field": "品牌名称", "message": "缺少必填字段 品牌名称" }],
  "warnings": []
}
```

`field` 指向出错位置，数组元素用 `痛点[2]`、`竞品[1].官网域名` 这种写法，序号从 1 开始。

错误码（阻断）：

| code | 含义 |
|---|---|
| `missing_field` | 必填字段缺失或为空 |
| `invalid_type` | 类型不对，例如竞品不是对象数组 |
| `invalid_item` | 数组里有空值或非字符串 |
| `duplicate_item` | 列表项重复、竞品重名 |
| `invalid_enum` | 枚举值不在允许范围（业务模式、locale、generation_stage、input_version、确认状态） |
| `invalid_url` | 网址不是完整的 http(s) 地址 |
| `count_out_of_range` | 传了主题但不是 1–3 个，或竞品不是 1–3 个 |
| `invalid_reference` | confirmed_fields 引用了不存在的字段 |
| `forbidden_for_b2c` | 纯 B2C Case 填了 B2B 专属字段 |
| `unknown_field` | 出现未定义字段 |

告警码（不阻断）：

| code | 含义 |
|---|---|
| `pending_value` | B2B 字段是「待人工确认」；三个选填字段会被当作未填写丢弃 |
| `count_suggestion` | 列表项数量超出建议范围 |
| `comma_in_item` | 列表项里含中文逗号；接口按一项接收没问题，但写回飞书合并列后再读会被拆错 |
| `baseline_required` | `diagnostic` 阶段需要原题库 |
| `confirmation_without_fields` | 状态是 `confirmed` 但没列已确认字段 |
| `alias_ignored` | 同时传了 `垂直行业` 和 `目标企业画像`，已按后者取值 |
| `renamed_column`、`ignored_column` | 仅飞书适配：旧列名已转换、管理列已忽略 |

## 7. skill 拿到 `normalized` 之后做什么

`case_fields`、`topics` 的来源映射、`competitor_selection`、`locale`、`generation_stage` 直接写进题库 `config`，skill 不改。以下内容需要判断，仍由 skill 生成：主题英文名 `topics[].topic`、品类英文名 `category_label`、`brand_object_type`、`attribute_plan`、全部题目。

## 8. 飞书来源（本地用）

本地从飞书多维表格读到的 Record 走适配器，转成同一个 payload：

```bash
python3 scripts/normalize_case.py readback.ndjson --from-base-record
```

适配规则：合并列（`目标企业画像`、`目标客户`、`痛点`、`使用场景`、`产品特性`、`主题`）按「，」拆成数组；`竞品 n` / `竞品 n 官网域名` 平铺列合成 `竞品` 数组；`[url](url)` 形式的网址去掉 markdown 包裹；旧列 `垂直行业` 按 `目标企业画像` 读取；`record_id`、`Case序号` 忽略。主题局部竞品边界写在 `补充内容`，由 skill 解析。

已知限制：飞书合并列里某个值本身含「，」时会被多拆一项。接口用数组传值没有这个问题。

## 9. 验收

下面的端到端校验依赖项目内部的评测数据，只在项目内运行，不随公开仓库发布；接入方可以用第 2–6 节的规则和两份示例 payload 自行对账。

```bash
python3 evals/e2e_input_contract.py
```

检查内容：两份示例 payload 归一化后和现有题库的 `case_fields` 逐字段相等，拼回题库后通过 `validate_question_bank.py`；同一 Case 走飞书路径和接口路径的归一化结果一致；三条真实飞书 Record 的处理结果符合预期；13 类错误输入都返回对应错误码；只填必填项、1 个竞品、文本框字符串都能通过。结果写入 `reports/input-contract-e2e.md`。接口层自行实现校验时，用同一批示例和错误输入对账。

示例 payload：

- B2B：[input-examples/b2b-example.json](input-examples/b2b-example.json)（含 `handoff`）
- B2C：[input-examples/b2c-example.json](input-examples/b2c-example.json)
