# 阿里云部署 GEO 平台（server.py / search_server.py / platforms）

三个服务在**同一台服务器、同一个域名**下统一暴露：

| 路径 | 后端 | 说明 |
|---|---|---|
| `/` | platforms/geo-orchestrator :8080 | 编排器 Web UI + `/api/v1/runs*` |
| `/api/v1/invoke`、`/api/v1/tools`、`/api/v1/health` | server.py :8090 | 34 个技能工具统一入口 |
| `/api/v1/web_search`、`/api/v1/web_fetch[_batch]` | search_server.py :9998 | Scrapeless 搜索/抓取 |

```
公网 → nginx(:80/:443) ─┬─→ 127.0.0.1:8080  geo-orchestrator (uvicorn)
                        ├─→ 127.0.0.1:8090  geo-server       (stdlib)
                        └─→ 127.0.0.1:9998  geo-search       (stdlib)
```

三个后端只监听 `127.0.0.1`，公网无法绕过 nginx 直连。

## 0. 依赖前提（已实测确认）

- `server.py` + `skills/`（61 个脚本）：**只用 Python 标准库**，无第三方包、无 pandoc/node 等外部命令
- `search_server.py`：需要 `requests`
- `platforms/geo-orchestrator`：需要 `fastapi/uvicorn/pydantic/httpx/jinja2`（见其 `requirements.txt`）
- 因此服务器装 `python3` + `nginx` 即可，Python 版本 3.9 起即可运行

## 1. 阿里云控制台两件事

**① 安全组**：入方向放行 `80`、`443`（来源 `0.0.0.0/0`）；**不要**放行 8080/8090/9998。22 端口建议只放你本机出口 IP。

**② 域名与备案（决定成败，先确认）**

| 服务器地域 | 用域名走 80/443 | 结论 |
|---|---|---|
| 中国大陆（杭/京/沪/深…） | 域名**必须已完成 ICP 备案**，否则阿里云会拦截 80/443 | 没备案就用 `http://<公网IP>:8088` 这类非标端口，或改用 HK/海外地域 |
| 中国香港 / 新加坡 / 硅谷等 | 无需备案 | 可直接解析域名；也可先裸 IP 访问 |

本项目业务是海外 GEO，**优先选 HK/海外地域**最省事。没有域名的话，`install.sh` 默认 `server_name _`，用 `http://<公网IP>/` 即可访问（大陆地域仍需注意上面的端口拦截）。

## 2. ⚠️ Dify 内网依赖：这台服务器大概率连不通

`platforms/geo-orchestrator` 默认 `DIFY_BASE_URL=http://dify.ads.qihoo.net/v1`——**公司内网域名，公网 ECS 无法解析/访问**。三种处理：

1. **服务器能走公司内网**（同 VPC/专线/内网穿透）→ 保持默认值即可；
2. **有公网可访问的 Dify 端点** → 在 `/etc/geo-presales/env` 改 `DIFY_BASE_URL`；
3. **暂时没有** → 照常部署，`geo-orchestrator` 会跑起来但 `/healthz` 报 `dify_reachable: false`，`server.py` 与 `search_server.py` **不受影响**，可先用这两个。

`server.py` 与 `search_server.py` 只依赖 Scrapeless 公网 API，无此问题。

## 3. 上传代码

方式 A —— git（仓库已有 GitHub remote，推荐）：

```bash
ssh root@<公网IP>
git clone https://github.com/Suda202/geo-presales-skills /opt/geo-presales-skills
# 私有仓库：git clone git@github.com:Suda202/geo-presales-skills /opt/geo-presales-skills
#   （先在 GitHub 配好服务器上的 deploy key）
```

方式 B —— 从本机 rsync（不走 git，自动跳过 .env/runs/node_modules）：

```bash
cd "/Users/maqinyao/Desktop/海外geo2/geo-presales-skills"
rsync -avz --delete \
  --exclude '.git' --exclude '.env' --exclude 'runs' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '.codegraph' --exclude '.wisharness' \
  --exclude 'node_modules' \
  ./ root@<公网IP>:/opt/geo-presales-skills/
```

> `.env`（含 Scrapeless key）已在 `.gitignore` 内、未入库，**必须**靠环境变量注入，见下一步。

## 4. 一键安装

```bash
# 中国大陆地域若 80 被拦截，先改用其他端口：编辑 deploy/nginx/geo-presales.conf 的 listen
ssh root@<公网IP>
SCRAPELESS_API_KEY=sk_xx bash /opt/geo-presales-skills/deploy/install.sh
# 已有域名时：
DOMAIN=geo.yourdomain.com SCRAPELESS_API_KEY=sk_xx bash /opt/geo-presales-skills/deploy/install.sh
```

脚本做 7 件事（幂等，可重复执行）：装依赖 → 建 `geopress` 系统用户 → 生成 `/etc/geo-presales/env`（自动随机生成访问令牌）→ 建 venv 装包 → 安装并启动 3 个 systemd 单元 → 注入令牌生成 nginx 配置并 `nginx -t` 校验 → 本机自检（含 200/401 两条鉴权用例）。

之后补密钥/改 Dify 地址：

```bash
vi /etc/geo-presales/env        # chmod 600
systemctl restart geo-server geo-search geo-orchestrator
```

## 5. HTTPS（有域名后）

```bash
dnf -y install certbot python3-certbot-nginx    # Debian: apt-get install certbot python3-certbot-nginx
certbot --nginx -d geo.yourdomain.com
```

certbot 会自动改写 nginx 配置加 443 与跳转；令牌与路由不受影响。之后在 `/etc/geo-presales/env` 确认 `DIFY_TIMEOUT` 与 nginx `proxy_read_timeout` 仍匹配。

## 6. 验证

```bash
TOKEN=$(ssh root@<IP> "sed -n 's/^GEO_ACCESS_TOKEN=//p' /etc/geo-presales/env | tail -1")

curl -s https://<域名>/api/v1/health                      # 免鉴权健康检查
curl -s https://<域名>/api/v1/search-health
curl -s https://<域名>/healthz                            # Dify 连通性
curl -s -X POST https://<域名>/api/v1/invoke \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"tool":"normalize_case","params":{"payload":{}}}'   # 期望 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<域名>/api/v1/invoke \
  -H 'Content-Type: application/json' -d '{}'              # 期望 401
```

浏览器打开 `https://<域名>/` 会用 nginx Basic 账号弹出登录（用户名 `geo`，密码在 `/etc/nginx/geo-users.conf`，改密码：`htpasswd /etc/nginx/geo-users.conf geo`）。

## 7. 运维

```bash
systemctl status geo-server geo-search geo-orchestrator
journalctl -u geo-server -f          # server.py 日志（含每个请求行）
journalctl -u geo-orchestrator -f
tail -f /var/log/nginx/geo-presales.access.log
```

- 运行记录：`/var/lib/geo-orchestrator/runs/<run_id>/`（input/response/artifact/error 四件）
- 长任务：`collect_answers` 内部超时 3600s，nginx `proxy_read_timeout` 已设 3900s，`TimeoutStopSec` 已放宽，重启服务不会被 systemd 提前杀
- 更新代码：`cd /opt/geo-presales-skills && git pull && bash deploy/install.sh`（幂等，只重启相关服务）
- 备份：`/etc/geo-presales/env`、`/etc/nginx/geo-users.conf`、`/var/lib/geo-orchestrator/runs`

## 8. 安全说明与已知限制

- 后端全部只监听 `127.0.0.1`，公网入口唯一（nginx）。
- `/api/` 类接口要求 `Authorization: Bearer <GEO_ACCESS_TOKEN>`；UI 用 Basic。密钥不落仓库、不进 nginx 配置历史（install.sh 现场替换占位符 `__GEO_ACCESS_TOKEN__`）。
- **限制 1**：令牌明文写在 `/etc/nginx/conf.d/geo-presales.conf`（权限 640）。多令牌轮换、按人区分身份需要应用层鉴权，见限制 2。
- **限制 2**：`server.py` / `search_server.py` 自身仍无鉴权，令牌只校验到 nginx 层。若担心内网横向移动，需给两个服务加应用层 Bearer 校验（建议按项目 TDD 规范先补测试）。
- **限制 3**：nginx 无全局限流。Scrapeless 按量计费，公网暴露后可能被刷。建议至少加 `limit_req_zone`，或在 Scrapeless 侧设置额度上限与告警。
- **限制 4**：`server.py` 会用 `sys.executable` 起子进程执行 `skills/` 下脚本，且 `SKILLS_ROOT` 由环境变量决定——服务器上不要放不可信的 skills 目录，`GEO_PRESALES_SKILLS_ROOT` 不要接受外部输入。
- 单实例 stdlib `HTTPServer`（geo-server）并发能力有限，仅适合内部/中小流量；高并发需换 WSGI/ASGI 或多副本 + nginx upstream。

## 9. 尚未验证的项（须在服务器上实测）

- `install.sh` 未在真实阿里云 Linux 上执行过（本机为 macOS，无 systemd）；但 nginx 配置已通过 Docker 起真实 nginx:alpine + 三个 mock 后端做过 12 项路由/鉴权端到端用例，全部通过（健康检查 3 条、带令牌调用 2 条、无/错令牌 401 共 3 条、UI Basic 3 条、未知路径 404 共 1 条）。首次部署时仍以服务器上 `nginx -t` 与脚本自检为准。
- `ProtectSystem=full` + `PrivateTmp` 与 skills 脚本写临时文件的兼容性未实测；若出现权限报错，先临时去掉这两项定位，再改 `ReadWritePaths` 精确放行。
- ECS 到 Scrapeless（`api.scrapeless.com`）的出网连通性未实测（大陆地域访问海外 API 可能受限，届时改用 HK/海外地域）。
