#!/usr/bin/env python3
"""平台网关端到端校验（3.6.4，2026-11-11）：skill 只认 Scrapeless、DataForSEO 两家原厂接口，地址可指向研发的网关。

模拟研发的数据接入层：本机起一个透传网关（只用标准库），校验调用方带的 X-Gateway-Token，
注入真实密钥后原样转发到 api.scrapeless.com / api.dataforseo.com，并记下每个请求。
调用方（跑 skill 的机器）没有任何密钥、读不到钥匙串、除网关外哪儿都连不上，设：
  SCRAPELESS_BASE_URL=http://127.0.0.1:<端口>/scrapeless
  DATAFORSEO_BASE_URL=http://127.0.0.1:<端口>/dataforseo
  GEO_GATEWAY_HEADERS={"X-Gateway-Token": "..."}
  GEO_NET_DOMESTIC=1
真实调用，会付费：Scrapeless 约 15 次，DataForSEO 约 0.01 美元。

验证：
  G0 不带网关令牌被网关拒绝（证明请求确实经过网关、网关头确实带上了）
  G1 net.py search 经网关有结果
  G2 net.py fetch 经网关取到网页
  G3 net.py pantip 经网关（v2 网页代理渲染）取到评论
  G4 collect_serp_signals.py：PAA/相关搜索 + 自动补全，原始页 rawUrl 也经网关取
  G5 collect_keyword_data.py balance（本机没有 DataForSEO 凭据）
  G6 collect_reviews.py trustpilot 经网关取到评价
  G7 collect_answers.py 采 1 题 × ChatGPT × US
  G8 网关日志：两家都有请求、没有一个请求绕过网关（调用方直连全部被死端口挡住）

产物：reports/gateway-e2e.md；临时目录跑完删除。

    python3 evals/e2e_gateway.py
"""
from __future__ import annotations

import base64
import csv
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SKILLS = SKILL.parent
NET = SKILLS / "shared/scripts/net.py"
SERP = SKILLS / "shared/scripts/collect_serp_signals.py"
KW = SKILLS / "shared/scripts/collect_keyword_data.py"
REV = SKILLS / "shared/scripts/collect_reviews.py"
ANSWERS = SKILLS / "geo-presales-report-builder/scripts/collect_answers.py"
REPORT = SKILL / "reports/gateway-e2e.md"
GW_TOKEN = "gw-" + os.urandom(6).hex()
DEAD = "http://127.0.0.1:9"
UPSTREAM = {"scrapeless": "https://api.scrapeless.com", "dataforseo": "https://api.dataforseo.com"}
LOG: list[dict] = []
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" —— {detail[:300]}" if detail and not ok else ""), flush=True)


def secret(name):
    v = os.environ.get(name, "").strip()
    if v:
        return v
    try:
        return subprocess.run(["security", "find-generic-password", "-s", name, "-w"], capture_output=True,
                              text=True).stdout.strip()
    except FileNotFoundError:
        return ""


KEYS = {k: secret(k) for k in ("SCRAPELESS_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")}
# 网关自己的出站：不经系统代理（测试进程本身没被断网）
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Gateway(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _proxy(self):
        vendor, _, rest = self.path.lstrip("/").partition("/")
        entry = {"vendor": vendor, "method": self.command, "path": "/" + rest.split("?")[0][:80]}
        if self.headers.get("X-Gateway-Token") != GW_TOKEN:
            entry["status"] = 403
            LOG.append(entry)
            body = b'{"error": "gateway token missing"}'
            self.send_response(403); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body); return
        if vendor not in UPSTREAM:
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n) if n else None
        hdr = {"Content-Type": self.headers.get("Content-Type") or "application/json", "User-Agent": "gateway-e2e"}
        if vendor == "scrapeless":
            hdr["x-api-token"] = KEYS["SCRAPELESS_API_KEY"]  # 覆盖调用方带来的占位值
        else:
            hdr["Authorization"] = "Basic " + base64.b64encode(
                f"{KEYS['DATAFORSEO_LOGIN']}:{KEYS['DATAFORSEO_PASSWORD']}".encode()).decode()
        req = urllib.request.Request(UPSTREAM[vendor] + "/" + rest, data=data, headers=hdr, method=self.command)
        try:
            with OPENER.open(req, timeout=300) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        except Exception as e:  # noqa: BLE001
            status, body = 502, json.dumps({"error": str(e)}).encode()
        entry["status"] = status
        LOG.append(entry)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _proxy


def main() -> int:
    if not all(KEYS.values()):
        print("缺 Scrapeless key 或 DataForSEO 凭据（环境变量或钥匙串）")
        return 2
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Gateway)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    tmp = Path(tempfile.mkdtemp(prefix="e2e-gateway-"))
    (tmp / "emptybin").mkdir(); (tmp / "home").mkdir()
    strip = {"SCRAPELESS_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "SCRAPELESS_BASE_URL", "DATAFORSEO_BASE_URL", "GEO_GATEWAY_HEADERS", "NET_CACHE_DIR", "DATAFORSEO_LEDGER"}
    clean = {k: v for k, v in os.environ.items() if k not in strip and not k.lower().endswith("_proxy")}
    env = {**clean, "PATH": str(tmp / "emptybin"), "HOME": str(tmp / "home"), "GEO_NET_DOMESTIC": "1",
           "SCRAPELESS_BASE_URL": base + "/scrapeless", "DATAFORSEO_BASE_URL": base + "/dataforseo",
           "GEO_GATEWAY_HEADERS": json.dumps({"X-Gateway-Token": GW_TOKEN}),
           "NET_CACHE_DIR": str(tmp / "net"), "DATAFORSEO_LEDGER": str(tmp / "ledger.jsonl"),
           "DATAFORSEO_WHO": "e2e-gateway", "DATAFORSEO_CASE": "Brandx US",
           "HTTPS_PROXY": DEAD, "HTTP_PROXY": DEAD, "https_proxy": DEAD, "http_proxy": DEAD,
           "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}

    def run(args, timeout=600, **extra):
        p = subprocess.run([sys.executable, *map(str, args)], env={**env, **extra}, capture_output=True, text=True,
                           timeout=timeout, cwd=tmp)
        return p.returncode, p.stdout, p.stderr

    try:
        rc, out, err = run([NET, "search", "cloud gpu rental", "--gl", "us", "--hl", "en"],
                           GEO_GATEWAY_HEADERS="{}", NET_CACHE_DIR=str(tmp / "net0"))
        check("G0 不带网关令牌被网关拒绝", not out.lstrip().startswith("1. ") and any(e["status"] == 403 for e in LOG), out[:200])
        rc, out, err = run([NET, "search", "cloud gpu rental", "--gl", "us", "--hl", "en"])
        check("G1 net.py search 经网关", out.lstrip().startswith("1. "), out[:200] + err[:200])
        rc, out, err = run([NET, "fetch", "https://example.com/", "--country", "US"])
        check("G2 net.py fetch 经网关", "经 Scrapeless US 代理取得" in out and "Example Domain" in out, out[:200] + err[:200])
        rc, out, err = run([NET, "pantip", "https://pantip.com/topic/41366493", "--country", "TH"], timeout=400)
        check("G3 net.py pantip 经网关（v2 渲染）", "渲染取得" in out and "1. [评论]" in out, out[:200] + err[:200])
        serp = tmp / "serp"
        rc, out, err = run([SERP, "best cloud gpu rental", "--gl", "us", "--hl", "en", "--out", serp], timeout=400)
        sm = json.loads((serp / "summary.json").read_text()) if (serp / "summary.json").exists() else {}
        seed = (sm.get("per_seed") or [{}])[0]
        check("G4 collect_serp_signals 经网关：PAA/相关搜索 + 自动补全", rc == 0 and seed.get("paa", 0) + seed.get("related", 0) > 0
              and seed.get("autocomplete", 0) > 0, json.dumps(seed, ensure_ascii=False) + err[-200:])
        rc, out, err = run([KW, "balance"])
        check("G5 collect_keyword_data balance 经网关（本机无 DataForSEO 凭据）", rc == 0 and "余额" in out, out + err)
        rev = tmp / "rev"
        rc, out, err = run([REV, "trustpilot", "digitalocean.com", "--depth", "20", "--out", rev], timeout=900)
        rows = list(csv.DictReader((rev / "signals.csv").open(encoding="utf-8-sig"))) if (rev / "signals.csv").exists() else []
        check("G6 collect_reviews trustpilot 经网关", rc == 0 and len(rows) > 0, f"rc={rc} rows={len(rows)} {out[-200:]} {err[-200:]}")
        q = tmp / "q.csv"
        q.write_text("query\nWhat should I look for when choosing a cloud GPU rental service?\n", encoding="utf-8")
        ans = tmp / "ans"
        rc, out, err = run([ANSWERS, "--questions", q, "--out", ans, "--regions", "US", "--platforms", "chatgpt"], timeout=900)
        check("G7 collect_answers 经网关采 1 格", rc == 0 and (ans / "scraper.chatgpt/US/0001.json").exists(),
              f"rc={rc} {out[-200:]} {err[-200:]}")
        ok_log = [e for e in LOG if e.get("status") != 403]
        vendors = {e["vendor"] for e in ok_log}
        check("G8 网关日志：两家都经过网关", vendors == {"scrapeless", "dataforseo"}, json.dumps(sorted(vendors)))
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(ok for _, ok, _ in results)
    by = {}
    for e in LOG:
        k = (e["vendor"], e["path"].rsplit("/", 1)[0] if e["path"].count("/") > 4 else e["path"], e["status"])
        by[k] = by.get(k, 0) + 1
    lines = ["# 平台网关端到端校验\n", f"运行时间：{datetime.now():%Y-%m-%d %H:%M}，脚本 `evals/e2e_gateway.py`\n",
             "模拟：本机透传网关注入密钥、转发到 Scrapeless / DataForSEO；调用方无密钥、除网关外不通外网（境内模式）。\n",
             f"结论：{passed}/{len(results)} 通过\n", "| 项 | 结果 | 说明 |", "|-|-|-|"]
    lines += [f"| {n} | {'通过' if ok else '失败'} | {d[:200].replace('|', '/').replace(chr(10), ' ') if not ok else ''} |"
              for n, ok, d in results]
    lines += ["", "## 网关收到的请求", "", "| 厂商 | 路径 | 状态 | 次数 |", "|-|-|-|-|"]
    lines += [f"| {v} | {p} | {s} | {n} |" for (v, p, s), n in sorted(by.items())]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} 通过，报告：{REPORT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
