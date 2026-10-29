# GEO Presales Agent A - All-English Workflow

完整的全英文 Dify 工作流，包含 16 个节点。

## 快速开始

### 1. 导入 DSL

1. Dify → 工作室 → **导入 DSL 文件**
2. 选择 `workflow.dsl.yaml`
3. 点击创建

### 2. 配置环境变量

导入后，Dify 会提示配置环境变量：

| 变量名 | 值 |
|---|---|
| `biz_api_base` | `http://123.57.162.4` |
| `search_api_base` | `http://123.57.162.4` |
| `geo_api_token` | ECS `/etc/geo-presales/env` 中 `GEO_ACCESS_TOKEN` 的真实值 |

导入文件中的 `geo_api_token` 使用占位符，不包含真实密钥；导入后先在 Dify 环境变量中替换为真实值。更换服务地址只需更新两个 base URL，更换访问令牌只需更新 `geo_api_token`，均不用改工作流代码。

### 3. 配置 LLM 模型

两个 LLM 节点需要手动选模型：
- **节点 5: LLM 组装 research**
- **节点 9: LLM 生成题库**

点击节点 → 右上角"模型"下拉 → 选择已配置的模型（推荐 GPT-4o / Claude Sonnet 4.5）。

### 4. 测试运行

点右上角"运行"，填入 `test-input.json` 的测试数据，开始运行。

## 节点拓扑

```
开始 (9 个输入变量)
  ↓
0. 读取配置（输出 biz_api_base / search_api_base）
  ↓
1. 读技能契约（read_skills_batch）
  ↓
2. 竞品研究准备（competitor_research_prepare）
  ↓
3. 联网搜索（web_search_batch，3 次重试）
  ↓
4. 官网抓取（web_fetch_batch，3 次重试）
  ↓
5. LLM 组装 research（structured_output）
  ↓
6. 写 research.json（write_file）
  ↓
7. 竞品研究冻结（competitor_research_finalize）
  ↓
8. Case 归一化（normalize_case，全英文输入）
  ↓
9. LLM 生成题库（structured_output，12 条铁律 prompt）
  ↓
9.5 修正题库输入（自动对齐 source_value / quotas / 候选词）
  ↓
10. 写题库输入（write_file）
  ↓
11. 题库拼装（build_question_bank，补 category_label / brand_object_type）
  ↓
12. 题库校验（validate_question_bank，输出 String 化）
  ↓
13. 读取最终题库（read_file）
  ↓
输出（8 个变量：questions / question_count / bank_config / schema_version / validate_valid / validate_error_count / validate_first_errors / bank_path）
```

## 关键特性

- ✅ **全英文字段**：从用户输入到服务端到题库，全链路英文，零中英映射
- ✅ **统一鉴权**：所有 HTTP 调用自动携带 `Authorization: Bearer <geo_api_token>`
- ✅ **带重试**：所有 HTTP 调用最多 3 次指数退避（1s/2s/4s），联网搜索为 5 次
- ✅ **自动修正**：节点 9.5 自动对齐 source_value / quotas / 候选词
- ✅ **防御性设计**：所有节点检查 `ok` 字段，失败时返回明确错误
- ✅ **统一配置**：环境变量集中在节点 0，服务地址和访问令牌各只维护一处

## 输入字段说明

| 字段 | 类型 | 必填 | 示例 |
|---|---|---|---|
| `brand_name` | Text | ✅ | KeepBalance |
| `company_name` | Text | ✅ | KeepBalance |
| `business_mode` | Text | ✅ | B2C |
| `category` | Text | ✅ | family dietary supplements |
| `official_domain` | Text | ✅ | https://keepbalance.life |
| `topics` | Text | ✅ | family dietary supplements |
| `competitors` | Paragraph | ✅ | `[{"name":"By-Health","official_domain":"https://by-health.com"}]` |
| `regions` | Text | ✅ | US |
| `supplemental` | Paragraph | ❌ | Target market US |

**competitors 格式**：JSON 数组字符串，每竞品含 `name` 和 `official_domain` 两个英文字段。

## 输出字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `questions` | Array[Object] | 题库题目数组（核心产物） |
| `question_count` | Number | 题目总数 |
| `bank_config` | Object | 题库配置（含 topics / attribute_plan / quotas） |
| `schema_version` | String | 版本号（overseas-geo-question-bank/v8） |
| `validate_valid` | Boolean | 题库是否通过校验 |
| `validate_error_count` | Number | 校验错误总数 |
| `validate_first_errors` | String | 前 5 个错误摘要 |
| `bank_path` | String | 题库文件服务器路径 |

## 故障排查

### 1. 环境变量读不到

**症状**：代码节点报 `MissingSchema: Invalid URL '/api/v1/...'`

**原因**：Dify 的环境变量**不能通过 `os.environ.get()` 读取**，必须通过**输入变量**传递。

**解决**：所有代码节点的 `biz_api_base`、`search_api_base` 和 `geo_api_token` 都从**节点 0（读取配置）**的输出变量获取。

### 2. LLM 生成题库校验失败

**症状**：节点 12 返回 `valid: false`，错误列表很长

**常见错误**：
- `source_field must reference an existing supported Case field` → LLM 用了英文字段名，节点 9.5 会自动修正
- `discovery must request concrete candidates` → 题面缺候选词，节点 9.5 会自动补
- `topics[0].topic must be English` → topics 是中文，节点 9 的 prompt 已要求翻译成英文

**解决**：看节点 12 的 `first_errors` 字段，按错误提示调整节点 9 的 prompt 或节点 9.5 的修正逻辑。

### 3. 公网服务不可达

**症状**：所有 HTTP 调用报 `Connection refused`、超时或 nginx 502。

**解决**：在 ECS 检查 `geo-server`、`geo-search` 和 nginx，并确认 Dify 的两个 base URL 均为 `http://123.57.162.4`。如果 nginx 返回 401，检查 `geo_api_token` 是否与 ECS 的 `GEO_ACCESS_TOKEN` 完全一致。

## 文件清单

- `workflow.dsl.yaml` - 完整工作流 DSL（16 节点 + 16 边）
- `README.md` - 本文件
- `test-input.json` - 测试输入数据（KeepBalance 案例）
- `node-9-system-prompt.md` - 节点 9 的完整 system prompt（12 条铁律）
- `node-9-user-prompt.md` - 节点 9 的完整 user prompt

## 后续优化

1. **Scrapeless 限流**：如果遇到间歇性 429 错误，可以在 search_server.py 里加 `time.sleep()` 限流
2. **LLM 模型选择**：GPT-4o 和 Claude Sonnet 4.5 都支持 structured_output，但 Claude 更擅长遵循复杂规则
3. **错误恢复**：当前是"失败后人工重跑"，可以改成"validate 失败自动回到节点 9 重新生成"
4. **性能优化**：web_search 和 web_fetch 可以并行（当前是串行）

## 技术支持

遇到问题先看：
1. Dify 节点的"上次运行"面板 → 看输入/输出/错误
2. 服务端日志：`tail -50 /tmp/geo-servers/9999.log` 和 `tail -50 /tmp/geo-servers/9998.log`
3. 隧道日志：`tail -50 /tmp/cloudflared-logs/9999.log`

如果还解决不了，把以下信息贴给开发：
- 节点的完整输出（含 error 字段）
- Dify 运行历史截图
- 服务端日志最后 20 行
