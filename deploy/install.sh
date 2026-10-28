#!/usr/bin/env bash
# 在阿里云服务器上以 root 执行：bash /opt/geo-presales-skills/deploy/install.sh
# 幂等：可重复执行；已存在的密钥/配置不会被覆盖
set -euo pipefail

APP_DIR=/opt/geo-presales-skills
VENV=/opt/geo-presales-venv
CONF_DIR=/etc/geo-presales
ENV_FILE=$CONF_DIR/env
RUNS_DIR=/var/lib/geo-orchestrator
USER_NAME=geopress
DOMAIN=${DOMAIN:-_}

log() { printf '\n[install] %s\n' "$*"; }

[ "$(id -u)" = 0 ] || { echo "请用 root 运行"; exit 1; }
command -v dnf >/dev/null || command -v apt-get >/dev/null || { echo "未识别的包管理器"; exit 1; }

log "1/7 安装系统依赖"
if command -v dnf >/dev/null; then
  dnf -y install python3 python3-pip nginx httpd-tools >/dev/null
else
  apt-get update -qq
  apt-get install -y -qq python3 python3-pip python3-venv nginx apache2-utils rsync >/dev/null
fi

log "2/7 创建运行用户与目录"
id -u "$USER_NAME" >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$CONF_DIR" "$RUNS_DIR"
chown "$USER_NAME:$USER_NAME" "$RUNS_DIR"

log "3/7 初始化密钥文件 $ENV_FILE（已存在则跳过）"
if [ ! -f "$ENV_FILE" ]; then
  install -m 600 "$APP_DIR/deploy/env.example" "$ENV_FILE"
  key=$(openssl rand -hex 32)
  if grep -q '^SCRAPELESS_API_KEY=$' "$ENV_FILE"; then
    sed -i "s|^SCRAPELESS_API_KEY=$|SCRAPELESS_API_KEY=${SCRAPELESS_API_KEY:-}|" "$ENV_FILE"
  fi
  sed -i "s|^GEO_ACCESS_TOKEN=$|GEO_ACCESS_TOKEN=$key|" "$ENV_FILE"
  echo "  已生成访问令牌，请记录：$key"
  [ -n "${SCRAPELESS_API_KEY:-}" ] || echo "  警告：SCRAPELESS_API_KEY 为空 -> search/采集类工具会报缺少密钥"
  echo "        修复：SCRAPELESS_API_KEY=sk_xxx bash $APP_DIR/deploy/install.sh 或直接编辑 $ENV_FILE"
  echo "  还需手工填写：DIFY_API_KEY（以及无法访问内网时的 DIFY_BASE_URL）"
  echo "  编辑命令：vi $ENV_FILE"
else
  echo "  已存在，保留原值"
fi
if [ ! -f "$APP_DIR/.env" ]; then
  grep '^SCRAPELESS_API_KEY=' "$ENV_FILE" > "$APP_DIR/.env" || true
  chown "$USER_NAME:$USER_NAME" "$APP_DIR/.env" || true
fi

log "4/7 建立 Python 虚拟环境（platforms/geo-orchestrator 依赖）"
if command -v python3 >/dev/null && ! python3 -c "import ensurepip" >/dev/null 2>&1 && command -v apt-get >/dev/null; then
  apt-get install -y -qq python3-venv >/dev/null 2>&1 || true
fi
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$APP_DIR/platforms/geo-orchestrator/requirements.txt"
"$VENV/bin/pip" install --quiet requests

log "5/7 安装 systemd 单元"
for u in geo-server geo-search geo-orchestrator; do
  sed "s|^Environment=GEO_PRESALES_SKILLS_ROOT=.*|Environment=GEO_PRESALES_SKILLS_ROOT=$APP_DIR/skills|" \
      "$APP_DIR/deploy/systemd/$u.service" > "/etc/systemd/system/$u.service"
  sed -i "s|/opt/geo-presales-skills|$APP_DIR|g; s|/opt/geo-presales-venv|$VENV|g" "/etc/systemd/system/$u.service"
done
systemctl daemon-reload
systemctl enable geo-server geo-search geo-orchestrator >/dev/null 2>&1 || true
chown -R "$USER_NAME:$USER_NAME" "$APP_DIR" 2>/dev/null || true
systemctl restart geo-server geo-search geo-orchestrator

log "6/7 配置 nginx（令牌注入 + 域名）"
if [ ! -f /etc/nginx/geo-users.conf ]; then
  htpasswd -bc /etc/nginx/geo-users.conf geo "$(openssl rand -hex 12)" >/dev/null 2>&1
  echo "  已生成 UI Basic 账号 /etc/nginx/geo-users.conf（用户名 geo）"
fi
tok=$(sed -n 's/^GEO_ACCESS_TOKEN=//p' "$ENV_FILE" | tail -1)
[ -n "$tok" ] || { echo "  警告：GEO_ACCESS_TOKEN 为空，nginx 校验将全部拒绝"; }
conf=/etc/nginx/conf.d/geo-presales.conf
[ -f "$conf" ] || conf=/etc/nginx/sites-enabled/geo-presales.conf
mkdir -p "$(dirname "$conf")"
sed "s|__GEO_ACCESS_TOKEN__|$tok|; s|server_name geo.example.com;.*|server_name $DOMAIN;|" \
    "$APP_DIR/deploy/nginx/geo-presales.conf" > "$conf"
chmod 640 "$conf"
nginx -t && systemctl reload nginx

log "7/7 本机自检"
sleep 3
for u in http://127.0.0.1/api/v1/health http://127.0.0.1/api/v1/search-health http://127.0.0.1/healthz; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$u" || echo 000)
  echo "  $code  $u"
done
echo "  带令牌调用（应返回 200）："
curl -s -o /dev/null -w '  %{http_code}  POST /api/v1/invoke\n' -m 30 \
  -X POST http://127.0.0.1/api/v1/invoke \
  -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
  -d '{"tool":"normalize_case","params":{"payload":{}}}'
echo "  无令牌调用（应返回 401）："
curl -s -o /dev/null -w '  %{http_code}  POST /api/v1/invoke\n' -m 20 \
  -X POST http://127.0.0.1/api/v1/invoke -H 'Content-Type: application/json' -d '{"tool":"normalize_case"}'

echo
echo "服务状态： systemctl status geo-server geo-search geo-orchestrator"
echo "日志：     journalctl -u geo-server -f"
