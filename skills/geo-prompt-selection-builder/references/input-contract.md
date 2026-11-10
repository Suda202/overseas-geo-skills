# 品牌资料输入合同（presales-case-input/v2）

给接入方用：线上诊断表单收集的数据，或本地的一份品牌资料文件（JSON）。调用方按本文组好一个 JSON，先过 `scripts/normalize_case.py` 校验和归一化，通过后再交给选词生成题库（线上一条命令入口见 [online-runner.md](online-runner.md)）。接入方不需要读 skill 的其他文件。

接口和脚本里的 case 字样（schema 名 `presales-case-input/v2`、顶层键 `case`、`case_fields`、`scripts/normalize_case.py`、`--case`）是历史命名，字段名和错误码原样保留，正文一律叫品牌资料。

品牌资料的字段就是飞书《AI 搜索监测｜品牌资料收集》第一部分：线上诊断表单和售后向品牌方收资料用同一套字段，改字段时两处一起改。v1（公司名、业务模式、品类、痛点等字段）2026-11-09 起停用，传进来整份拒收。

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
  "input_version": "presales-case-input/v2",
  "case": { "...": "见第 3 节" },
  "options": { "locale": "en" },
  "handoff": { "...": "见第 5 节，可省略" }
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `input_version` | 是 | 固定为 `presales-case-input/v2` |
| `case` | 是 | 品牌业务字段，见第 3 节 |
| `options` | 否 | 见第 4 节 |
| `handoff` | 否 | 来源与客户确认状态，见第 5 节 |

出现未定义的字段会报错（`unknown_field`），避免字段名拼错后被悄悄忽略。

## 3. `case` 业务字段

字段名用中文。所有字符串会去掉首尾空白；`null`、空字符串和空数组视为没填。填「待补充」按没填处理并告警；填「无」原样记录。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `品牌` | string | 是 | 对外使用的正式品牌名。一家公司多个品牌的，每个品牌一份品牌资料 |
| `品牌别名` | string 或 string[] | 否 | 简称、旧名、本地语言名、常见拼写和空格变体；易混淆、不能算作本品牌的名称也写在这里并注明。产品系列名和型号不从品牌方收，由我们查官网和公开资料补。报告的提及识别靠它 |
| `官方域名` | string 或 string[] | 是 | `http://` 或 `https://` 开头的完整网址。可填多个，第一个是品牌主站，子域名、市场独立站往后写 |
| `产品线` | string | 是 | 本期监测的产品或服务。品类名由选词从这里和官网推出，不单独收。旧名「本期产品线」（2026-11-10 改名）照收，按「产品线」记并给 `renamed_field` 警告 |
| `适用边界` | string | 否 | 本期不覆盖的产品、渠道、客群或服务；边界外的问法不出题 |
| `竞品` | object[] | 是 | 1–3 个，见下表。取客户填的，不冻结 |
| `核心目标客户与购买场景` | string 或 string[] | 否 | 按业务优先级排，最重要的写第 1 条。每条写目标客户（B2C 写客户人群；B2B 写企业类型、规模及决策或使用角色）和购买场景与需求（要解决什么问题、购买时关注什么）。建议不超过 5 条 |
| `差异化优势` | string 或 string[] | 否 | 相比主要竞品、买家能感知到的不同；只对特定客户或场景成立的注明。建议不超过 5 条 |

**多值字段传字符串还是数组**：`品牌别名`、`官方域名`、`核心目标客户与购买场景`、`差异化优势` 两种都收。传数组时逐项展开成 `核心目标客户与购买场景 1`、`核心目标客户与购买场景 2`……，顺序原样保留；传字符串（表单的单个文本框）时整段作为一项，不按逗号拆。能拿到分项时优先传数组。

**选填字段留空会怎样**：不报错。字段越少，题目越依赖产品线和公开调研。

**线上表单里不属于本合同的项**：「市场」传给入口脚本的 `--market`；「语言」映射到 `options.locale`；「AI 平台」传给 `--platforms`。手动上传题目时不调用生词 skill。

`竞品` 每一项：

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `名称` | string | 是 | 英文规范名称；竞品之间不能重名 |
| `官网域名` | string | 是 | 完整网址 |

竞品只收这两项，传别的字段报 `unknown_field`。竞品不分主题。线上报告的竞品名单按提及率补足，归线上报告逻辑，不在本合同里。

**v1 字段**：`公司名`、`品牌名称`、`业务 / 产品名称`、`业务模式`、`品类`、`目标企业画像`（`垂直行业`）、`目标客户`、`痛点`、`使用场景`、`产品特性`、`补充内容`、`希望解决的问题`、`主题`、`购买标准`、`集成与兼容`、`信任与合规`、`地理与市场` 传进来报 `retired_field`，报错里写明并到了哪个新字段。v2 曾有的选填字段 `业务目标` 2026-11-09 删除（《品牌资料收集》同步删了），传进来同样报 `retired_field`。

## 4. `options`

| 字段 | 默认 | 可选值 |
|---|---|---|
| `locale` | `en` | 题面语言，对应表单的「语言」；必须是 `references/locale-templates.json` 已登记的键（当前为 `en`、`th`、`ru`） |

## 5. `handoff`（可省略）

```json
{
  "confirmation_status": "partial",
  "confirmed_fields": ["竞品"],
  "sources": [{ "url": "https://www.example-biz.example", "summary": "官网产品与服务页" }]
}
```

| 字段 | 规则 |
|---|---|
| `confirmation_status` | `none`（客户未确认，默认）、`partial`、`confirmed` |
| `confirmed_fields` | 客户已确认的字段名，必须是第 3 节里的字段 |
| `sources` | 研究来源，每条至少有 `url` |

省略 `handoff` 时，按「客户未确认」生成题库。

## 6. 返回结构

成功：

```json
{
  "ok": true,
  "errors": [],
  "warnings": [{ "code": "pending_value", "field": "适用边界", "message": "适用边界 为「待补充」，已按未填写处理" }],
  "normalized": {
    "case_fields": { "品牌": "...", "产品线": "...", "核心目标客户与购买场景 1": "...", "竞品 1": "...", "...": "..." },
    "brand_name": "...",
    "brand_aliases": ["..."],
    "official_domain": "...",
    "official_domains": ["..."],
    "product_line": "...",
    "derived_field_sources": { "brand_name": "品牌", "official_domain": "官方域名", "category_label": "产品线（推断）" },
    "competitor_selection": { "status": "client_input", "selection_count": 3, "formal_competitors": [ "..." ] },
    "locale": "en",
    "handoff": { "confirmation_status": "none", "confirmed_fields": [], "sources": [] }
  }
}
```

失败时 `ok = false`，没有 `normalized`，`errors` 列出全部问题（不在第一个错误处停下；v1 payload 只报一条 `unsupported_version`）：

```json
{
  "ok": false,
  "errors": [{ "code": "missing_field", "field": "品牌", "message": "缺少必填字段 品牌" }],
  "warnings": []
}
```

`field` 指向出错位置，数组元素用 `核心目标客户与购买场景[2]`、`竞品[1].官网域名` 这种写法，序号从 1 开始。

错误码（阻断）：

| code | 含义 |
|---|---|
| `missing_field` | 必填字段缺失、为空或填了「待补充」 |
| `invalid_type` | 类型不对，例如竞品不是对象数组 |
| `invalid_item` | 数组里有空值或非字符串 |
| `duplicate_item` | 列表项重复、竞品重名 |
| `invalid_enum` | 枚举值不在允许范围（locale、input_version、确认状态） |
| `invalid_url` | 网址不是完整的 http(s) 地址 |
| `count_out_of_range` | 竞品不是 1–3 个 |
| `invalid_reference` | confirmed_fields 引用了不存在的字段 |
| `unsupported_version` | 传的是已停用的 `presales-case-input/v1` |
| `retired_field` | 传了已停用的 v1 字段 |
| `unknown_field` | 出现未定义字段 |

告警码（不阻断）：

| code | 含义 |
|---|---|
| `pending_value` | 选填项填了「待补充」，按没填处理 |
| `count_suggestion` | 核心目标客户与购买场景、差异化优势超过 5 条 |
| `confirmation_without_fields` | 状态是 `confirmed` 但没列已确认字段 |

## 7. skill 拿到 `normalized` 之后做什么

`case_fields`、`competitor_selection`、`locale` 直接写进题库 `config`，skill 不改；`config.generation_stage` 固定写 `selection`。以下内容需要判断，按选词规则生成：品类名 `category_label`（从产品线和官网推出）、`brand_object_type`、目标客户与使用场景、矩阵行、主题、全部题目（见 [online-runner.md](online-runner.md)）。

## 8. 验收

```bash
python3 evals/e2e_input_contract.py
```

检查内容：合同字段和《品牌资料收集》第一部分一致；两份示例和两份公开模板归一化无错误；只填必填项、1 个竞品能通过；v1 payload 和 v1 字段被拒；「待补充」「无」、多个官方域名、文本框字符串的处理；12 类错误输入返回对应错误码。结果写入 `reports/input-contract-e2e.md`。接口层自行实现校验时，用同一批示例和错误输入对账。

示例 payload：

- B2B：[input-examples/b2b-example.json](input-examples/b2b-example.json)（含 `handoff`）
- B2C：[input-examples/b2c-example.json](input-examples/b2c-example.json)
