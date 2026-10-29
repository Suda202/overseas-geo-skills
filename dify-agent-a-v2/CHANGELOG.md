# GEO Agent A v2 - All-English Refactoring

## 2026-10-29：统一 Bearer 鉴权与公网服务地址

- 所有 11 个 `requests.post` 调用节点统一携带 `Authorization: Bearer <geo_api_token>`。
- `geo_api_token` 通过 Dify 环境变量注入，并经节点 0 传递给各代码节点；仓库仅保留占位符，不保存真实密钥。
- `biz_api_base` 与 `search_api_base` 默认更新为 `http://123.57.162.4`。
- 新增 DSL 回归测试，校验鉴权参数、请求头、环境变量透传、代码语法和转换幂等性。

## 核心改动

### 1. 全链路英文字段
- 用户输入：competitors[].name / official_domain
- Dify 工作流：所有变量和代码用英文键
- 服务端 normalize_case：接受英文字段输入，输出英文字段
- v8 题库：case_fields 里也是英文键

### 2. 服务端改动（normalize_case.py）
- SCALAR_REQUIRED: ("company_name", "brand_name", "business_mode", "category", "official_domain")
- NUMBERED_LISTS: ("target_customers", "pain_points", "use_cases", "product_features")
- COMPETITOR_KEYS: {"name", "official_domain", "applicable_topics"}
- 所有中文字段名 → 英文

### 3. Dify 工作流改动
- 节点 8（normalize_case）：payload 用英文字段
- 节点 9（LLM 生成题库）：prompt 强调英文字段名
- 节点 9.5（修正）：source_field 映射表删除（不需要了，因为全英文）
- 节点 11（build_question_bank）：category_label 从 case_fields.category 读

### 4. 测试验证
- test-input.json 用英文字段
- 所有节点代码用英文键

## 文件清单

- workflow.dsl.yaml - 完整 16 节点工作流
- README.md - 使用指南
- test-input.json - 测试输入（英文）
- CHANGELOG.md - 本文件

## 迁移指南

### 从 v1（中文）迁移到 v2（英文）

1. 服务端：normalize_case.py 已改，支持英文字段
2. Dify：导入新的 workflow.dsl.yaml
3. 输入：competitors 用英文字段名

### 不兼容的地方

- v1 的输入（中文字段）不能直接在 v2 用
- v1 的 case.json 不能在 v2 的 build_question_bank 用（字段名不匹配）

### 兼容的地方

- v8 题库结构没变（schema_version 还是 overseas-geo-question-bank/v8）
- 服务端 validate_question_bank 逻辑没变

## 后续工作

1. validate_question_bank.py 也要英文化（当前还是校验中文字段）
2. input-contract.md 文档要更新
3. presales-contract.md 文档要更新
4. examples.md 示例要更新
