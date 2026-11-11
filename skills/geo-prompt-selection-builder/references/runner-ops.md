# 线上 runner 部署与运维（给研发）

这份写给部署和维护线上选词的人：要放哪些环境变量、服务器要能连哪些地址、审核环和每轮记账怎么工作、怎么验收。生成题目的 agent 不读这份（runner 拷工作目录时排除），agent 要遵守的规则在 [online-runner.md](online-runner.md) 和 [selection-rules.md](selection-rules.md)。2026-11-11（3.7.0）从 online-runner.md 拆出。

## 部署清单

- 运行环境：Python ≥ 3.12（`--agent sdk` 需要 `claude-agent-sdk`；语种检查需要 `lingua-language-detector`，见 `requirements.txt`，国内装包用阿里云或清华 PyPI 镜像）。不需要 Chrome、不需要 lark-cli、不需要浏览器登录态。
- 服务器出网：只需要 `api.scrapeless.com`（必须）和 `api.dataforseo.com`（评价、关键词搜索量），或者研发网关上转发这两家的地址；大模型用国内 API，地址由 `ANTHROPIC_BASE_URL` 定。
- 一次只跑一个市场，每次一个新工作目录：`python3 scripts/run_selection_mode.py run --case <品牌资料.json> --market <市场> --platforms <AI 平台> --out <新目录> --agent sdk`。

| 环境变量 | 必填 | 说明 |
|-|-|-|
| `ANTHROPIC_BASE_URL`、`ANTHROPIC_API_KEY`、`AGENT_MODEL` | `--agent sdk` 时必填 | 模型网关和模型名；审核 agent 用 `AGENT_REVIEW_MODEL`，没设用 `AGENT_MODEL`。宿主自带 harness 时改用 `--agent-cmd` |
| `SCRAPELESS_API_KEY` | 是（接平台网关时不用） | Scrapeless 密钥 |
| `DATAFORSEO_LOGIN`、`DATAFORSEO_PASSWORD` | 是（接平台网关时不用） | DataForSEO 凭据 |
| `GEO_NET_DOMESTIC` | 境内服务器设 `1` | 没有海外直连时只走两家接口，见下「境内服务器」 |
| `SCRAPELESS_BASE_URL`、`DATAFORSEO_BASE_URL`、`GEO_GATEWAY_HEADERS` | 否 | 接平台网关，见下「接平台网关」 |
| `DATAFORSEO_WHO`、`DATAFORSEO_CASE` | 否 | 记账用：发起人姓名、客户；没传时记「线上选词（未传调用人）」和「品牌 市场」 |
| `DATAFORSEO_LEDGER` | 否 | DataForSEO 流水位置，默认 `~/.dataforseo/ledger.jsonl` |
| `NET_REDDIT_MAX` | 否 | 每个工作目录 Reddit 请求上限，默认 10 |
| `GEO_INDUSTRY_KB` | 建议设 | 行业知识档案的持久化目录。第一次运行时从随 skill 发布的档案（`references/industry-knowledge/`）复制一份，之后每个客户跑完在这里积累；每次运行前拷进工作目录给 agent 读。不设就写在 skill 目录里，重新部署会丢 |

产物、退出码和全部参数见 `scripts/run_selection_mode.py` 开头说明；交给线上的是 `out/upload/*.csv`（9 字段），结果摘要在 `out/result.json`。

## 审核环

校验和导出第一次都通过后，脚本再新开一个审核 agent（不带生成时的上下文），按 [review-rubric.md](review-rubric.md) 九条核对 `out/bank.json` 和 `out/notes.md`，发现写进 `out/review.json`，只写这一个文件。

- 审核模型：`--agent sdk` 时读环境变量 `AGENT_REVIEW_MODEL`，没设用 `AGENT_MODEL`；`--agent-cmd` 时照常执行宿主命令（`TASK_FILE` 指向 `REVIEW.md`），模型由宿主定。
- 阻塞发现（`blocking: true`）按返修的报错格式写成 `REVIEW-REPAIR-<n>.md`（stage 记 `review`）回喂 agent 返修，再跑校验和导出，然后 `REVIEW-<n>.md` 只复核上一轮报过的题号；复核仍有阻塞就继续返修，`--review-rounds` 轮（默认 1＝审一轮＋复核一轮，0 关闭审核）。最后一轮审核返修同样授权丢题不丢库；轮次用完仍有阻塞时，脚本自己把这些题删掉（删前题库存 `out/bank.before-drop.json`，题号和审核原文记进 `config.retired` 与 notes「删题（脚本兜底）」，删空的主题连登记一起删、挂在上面的矩阵行注明本期不出），再跑一遍校验和导出，通过就交付。删完仍没过，或阻塞发现没写题号删不了，才判生词失败。审核返修把校验改坏了，下一轮把校验报错和没修的阻塞发现一起回喂。审核轮次不占 `--repair-rounds` 的额度。
- 非阻塞发现不触发返修，记进 `out/result.json` 的 `review.nonblocking`；本来就要审核返修时，顺带让返修 agent 写进 `notes.md`「评审意见」一节。
- 审核是增强，validator 才是闸门：`review.json` 缺失、不是合法 JSON、结构不对，或审核 agent 超时、出错时，只在 `review.warnings` 记一条，照常交付已过校验的题库。审核 agent 改了 `bank.json` 时脚本恢复审核前的题库并记 warning。
- `out/result.json` 的 `review` 块：`rounds`（审核加复核跑了几轮）、`blocking_found` / `nonblocking_found`（各轮累计）、`status`（`passed` 无阻塞发现；`repaired` 返修后复核通过；`dropped` 轮次用完后脚本删题交付，删了哪些看 `dropped`；`skipped` 关闭审核；`review_failed` 审核没产出可用结果或阻塞没修完，看 `reason` 和总的 `status` 区分）、`review_repair_rounds`、`warnings`、`nonblocking`、`blocking_unresolved`。每轮原件存 `logs/review-<n>.json`；审核和审核返修的 agent 记录（`logs/agent-run-review*.json`）进 `costs.llm` 加总。

## 每轮记账

每轮自动记账，统计口径是每个客户平均花多少钱。脚本每次 finalize 都往 `out/result.json` 写一个 `costs` 块，只记数量和用量，不乘单价：

| 键 | 内容 | 从哪数 |
|-|-|-|
| `brand`、`market` | 客户和市场 | `inputs/case-normalized.json` |
| `llm` | 主跑和各返修轮的 token 用量加总（`input_tokens`、`output_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`）、轮次、turns、耗时；`total_cost_usd_anthropic_price_unreliable` 是 SDK 按 Anthropic 价算的，网关后面是别家模型时不可信，只留存不用 | `logs/agent-run*.json`（`--agent sdk` 才有 usage；`--agent-cmd` 记 `runs_with_usage: 0`） |
| `scrapeless_requests` | 研究预跑尝试次数（失败重试也算）和成功次数、SERP 请求数、网页代理页数、`net.py search` 次数 | `research/**/_collector/events.jsonl` 的 attempt 行、`research/**/serp*/raw/*.json`、`logs/net_cache/`（runner 设 `NET_CACHE_DIR`，每轮一份缓存） |
| `dataforseo` | 本轮时间窗内这个 case 的调用次数和花费 | `~/.dataforseo/ledger.jsonl`，按 `DATAFORSEO_CASE`（默认「品牌 市场」）过滤，不含沙盒 |

按客户汇总、算平均：`python3 -I .agents/skills/shared/scripts/cost_report.py <工作目录或评测数据目录> … [--since 2026-11-01]`。单价只读本机 `~/.geo-cost/prices.json`（`--write-example` 生成示例），不写进任何仓库文件。

## 境内服务器（没有海外直连）

部署在境内、连不上 Google、Reddit 这些海外站的服务器，运行前设环境变量 `GEO_NET_DOMESTIC=1`。本地开 VPN 跑不设，行为不变；skill 只有一份，不拆两套。

服务器只要连得上下面两个地址：

| 地址 | 用来做什么 | 连不上会怎样 |
|-|-|-|
| `api.scrapeless.com` | 研究预跑、Google 搜索和 PAA、自动补全、所有网页正文、Hacker News | 选词跑不了，这一个必须通 |
| `api.dataforseo.com` | 评价（Trustpilot、应用商店、Google Shopping、Google 地图）、关键词搜索量和 Trends（研发 2026-11-11 确认境内服务器能连） | 这两类信号记进「未覆盖来源」，其余照常出题 |

大模型网关用国内的，和这里无关。开关打开后：

- `net.py fetch` 不试直连、不试 Wayback，每个页面直接经 Scrapeless 目标国代理取，每页付费一次，缓存命中不付；代理偶发失败自动多试一次。正常的短页面和接口返回的 JSON 照常放行。
- `collect_serp_signals.py` 的自动补全改经 Scrapeless 代理取，每个种子词多付费一次。
- Reddit 的 RSS（搜索、版块）连不上，`net.py reddit <搜索词>` 直接回「读不到：境内模式…」；帖子网页版经 Scrapeless 代理取得到（`net.py reddit <帖子 URL> --proxy`，每帖付费 1 次，只有顶层评论），帖子链接先用 `net.py search` 搜。`net.py render` 不起无头 Chrome，改经 Scrapeless 代理不开 JS 取（本机没装 Chrome 时也一样）：RTINGS 能取到，GlobalSources 被 AWS WAF 拦、取不到就记失败、agent 写进「未覆盖来源」。Pantip 帖子用 `net.py pantip <帖子 URL> --country TH`，经 Scrapeless 网页代理 v2 的 JS 渲染取评论（每帖付费 1 次），precollect 的 Pantip 渠道已经改用它。
- runner 把开关透传给所有子进程，并在 `TASK.md` 末尾加一节「境内模式」，告诉 agent 哪些来源不用试。

本地验证跑 `python3 evals/e2e_domestic_network.py`：用死端口代理模拟「只连得上 Scrapeless」，真实调用 Scrapeless 约 20 次，会付费。部署到服务器后，先确认两个地址能连上：`curl -s -o /dev/null -w '%{http_code}\n' https://api.scrapeless.com`、`curl -s -o /dev/null -w '%{http_code}\n' https://api.dataforseo.com`，返回任意 HTTP 状态码就是通的，`000` 是不通。

### 接平台网关（3.6.4）

研发的平台有自己的数据接入网关（统一管密钥、计费）时，skill 不用改代码，只设：

```bash
export SCRAPELESS_BASE_URL=<网关上转发到 api.scrapeless.com 的地址>
export DATAFORSEO_BASE_URL=<网关上转发到 api.dataforseo.com 的地址>
export GEO_GATEWAY_HEADERS='{"<网关要的请求头>": "<值>"}'   # 可选
export GEO_NET_DOMESTIC=1
```

设了地址后本机可以不放 Scrapeless key 和 DataForSEO 凭据，由网关注入。skill 对外只依赖这两家：Scrapeless 用到 `/api/v1/scraper/request`、`/api/v1/scraper/result/<任务号>`、`/api/v2/scraper/request`（AI 平台回答）、`/api/v1/unlocker/request`、`/api/v2/unlocker/request`、`/storage/…`（搜索结果原始页）；DataForSEO 用到 `/v3/` 下的评价、商品、关键词、Trends 和账户接口。网关原样转发即可。验证跑 `python3 evals/e2e_gateway.py`（本机起一个透传网关，调用方无密钥、除网关外不通外网，真实付费），结果写 `reports/gateway-e2e.md`。

## 验收

- `python3 evals/e2e_input_contract.py`：品牌资料输入合同（示例 payload、飞书路径与接口路径一致、错误输入的错误码），结果写 `reports/input-contract-e2e.md`。
- `python3 evals/e2e_repair_loop.py`：返修循环四条路径（修好、丢题保底、关闭返修、无 bank），结果写 `reports/repair-loop-e2e.md`。
- `python3 evals/e2e_review_loop.py`：审核环七条路径（无发现、阻塞返修后复核通过、review.json 坏掉、结构不对、关闭审核、额度用完、审核超时），结果写 `reports/review-loop-e2e.md`。
- `python3 evals/e2e_gateway.py`：平台网关（本机透传网关注入密钥，调用方无密钥，真实付费），结果写 `reports/gateway-e2e.md`。动了任何采集脚本的厂商地址或请求头时跑。
- `python3 evals/e2e_domestic_network.py`：境内模式（模拟只连得上 Scrapeless，真实付费调用约 20 次），结果写 `reports/domestic-network-e2e.md`。动了 `net.py`、`collect_serp_signals.py` 或境内模式时跑。
