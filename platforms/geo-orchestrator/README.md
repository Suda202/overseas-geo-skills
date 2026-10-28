# GEO Orchestrator

`dify-agent-a-v2` 工作流的前门：表单或粘贴 JSON 输入一个 presales case，
调用 Dify workflow，拿回题库 JSON。

## 快速开始

```bash
cd platforms/geo-orchestrator
python3 -m pip install -r requirements.txt   # 若提示 pip 找不到，用 pip3

cp .env.example .env
# 编辑 .env，填入 DIFY_API_KEY（Dify → 应用 → API 访问）

python3 -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

打开 http://localhost:8080

> 本机 `/usr/bin/python3` 已自带全部依赖，可直接跳过安装步骤。

## 两种输入方式

- **表单**：9 个字段，竞品可增删行
- **粘贴 JSON**：直接粘 case JSON，支持 markdown 代码块、`{"case": {...}}` 包装、Dify 运行历史里复制的扁平对象；容错处理智能引号和尾随逗号

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | Dify 连通性与鉴权状态 |
| POST | `/api/v1/runs` | `{"case": {...}}` 提交运行 |
| POST | `/api/v1/runs/paste` | `{"raw": "..."}` 容错粘贴提交 |
| GET | `/api/v1/runs` | 最近 50 次运行列表 |
| GET | `/api/v1/runs/{run_id}` | 完整运行记录 |
| GET | `/api/v1/runs/{run_id}/artifact` | 题库产物 |

### curl 示例

```bash
curl -X POST http://localhost:8080/api/v1/runs/paste \
  -H "Content-Type: application/json" \
  -d '{"raw": "{\"brand_name\":\"KeepBalance\",\"company_name\":\"KeepBalance\",\"business_mode\":\"B2C\",\"category\":\"family dietary supplements\",\"official_domain\":\"https://keepbalance.life\",\"topics\":\"family dietary supplements\",\"competitors\":\"[{\\\"name\\\":\\\"By-Health\\\",\\\"official_domain\\\":\\\"https://by-health.com\\\"}]\",\"regions\":\"US\",\"supplemental\":\"\"}"}'
```

## 产物结构

`GET /api/v1/runs/{run_id}/artifact` 返回：

```json
{
  "run_id": "20261027T080000Z-a1b2c3",
  "questions": [...],
  "question_count": 6,
  "bank_config": {...},
  "schema_version": "overseas-geo-question-bank/v8",
  "validate_valid": true,
  "validate_error_count": 0,
  "validate_first_errors": "",
  "bank_path": "/tmp/geo-KeepBalance/question-bank.json"
}
```

校验失败（`validate_valid: false`）时返回 409 + `validate_first_errors`；
Dify 执行失败时返回 422 + Dify 原始错误。

## 运行记录

每次运行落盘到 `runs/<run_id>/`：

- `input.json` — 提交的 case + 发给 Dify 的 inputs
- `response.json` — Dify 原始响应体
- `artifact.json` — 提取后的产物
- `error.json` — 失败时的错误（kind: dify | failed | invalid | shape）

## 配置

见 `.env.example`。密钥从环境变量读取，平台无内置密钥。

## 目录

```
platforms/geo-orchestrator/
├── app.py            # FastAPI 入口与路由
├── dify_client.py    # Dify workflow 调用（Bearer auth, blocking）
├── models.py         # CaseInput（字段名 = Dify start 变量名）
├── paste.py          # 容错粘贴解析
├── artifact.py       # Dify 响应 → 题库产物
├── runs.py           # run 落盘
├── templates/        # 表单 + 粘贴 + 结果页
├── static/
└── runs/             # 运行记录（gitignore）
```

## 设计文档

`openspec/changes/add-geo-orchestrator/` 下的 proposal / design / tasks / spec。
