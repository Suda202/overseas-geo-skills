#!/usr/bin/env python3
"""境内模式端到端校验（3.5.1，2026-11-11）：模拟境内服务器只连得上 api.scrapeless.com。

做法：给所有子进程设 HTTPS_PROXY / HTTP_PROXY 指向一个不存在的本地端口，NO_PROXY 只放行
api.scrapeless.com——Python urllib 读这几个环境变量，于是除 Scrapeless 以外的直连全部失败，
DataForSEO 也连不上（最坏情况）。Scrapeless 走真实接口，会花钱：每次全跑约 20 次调用。

验证：
  S1 模拟有效：直连 www.google.com、example.com、api.dataforseo.com 都失败；Scrapeless 能连上
  D1 net.py fetch 普通网页：来源写「跳过直连（境内模式），经 Scrapeless US 代理取得」，正文完整
  D2 net.py fetch --raw 短 JSON 接口（Google 自动补全，约 300 字符）经代理取到并放行
  D3 net.py fetch --raw Hacker News Algolia 接口：JSON 可解析、有 hits
  D4 net.py reddit 搜索：直接回「读不到：境内模式…」；render：不起 Chrome，改经 Scrapeless 代理取（RTINGS）
  D5 net.py search：Scrapeless Google 搜索有编号结果
  D10 net.py pantip：Pantip 帖子评论经 Scrapeless JS 渲染取到（3.6.2）
  D6 collect_serp_signals.py 开境内模式：PAA 或相关搜索 > 0，自动补全 > 0，付费调用 = 2
  D6b 境内模式重跑同一目录：自动补全读 raw/*.autocomplete.json，不再付费
  D7 对照：同一目录不开境内模式重跑（PAA 读缓存）→ 自动补全失败，证明是开关让它通的
  D8 runner prepare：开关打开时 TASK.md 带「## 境内模式」一节，关掉时没有
  D9 runner precollect（开发者与云基础设施行业）：搜索联想 ok；Hacker News 经代理采到；
     Reddit RSS 记「境内模式」，取到的只能是帖子网页版（代理）；评价（DataForSEO）连不上只记失败，precollect 照常写完 summary.json

  D11 每轮记账：Scrapeless 搜索、代理页、境内自动补全都计数，cost_report 按单价算出这一轮的钱

产物：reports/domestic-network-e2e.md；工作目录建在系统临时目录，跑完删除。

    python3 evals/e2e_domestic_network.py
退出码 0 表示全部符合预期。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SHARED = SKILL.parent / "shared" / "scripts"
RUNNER = SKILL / "scripts" / "run_selection_mode.py"
NET = SHARED / "net.py"
SERP = SHARED / "collect_serp_signals.py"
REPORT = SKILL / "reports" / "domestic-network-e2e.md"

# 自带中性品牌资料：品牌是假的，竞品用真实公开的 GPU 云服务，让搜索和社区有东西可采
CASE_PAYLOAD = {
    "input_version": "presales-case-input/v2",
    "case": {
        "品牌": "Brandx",
        "官方域名": "https://brandx.example",
        "产品线": "Cloud GPU rental: on-demand GPU instances for AI training and inference",
        "竞品": [{"名称": "AWS", "官网域名": "https://aws.amazon.com"},
                 {"名称": "Google Cloud", "官网域名": "https://cloud.google.com"},
                 {"名称": "Microsoft Azure", "官网域名": "https://azure.microsoft.com"}],
        "核心目标客户与购买场景": ["AI 初创团队：按小时租 GPU 训练和推理模型"],
    },
    "options": {"locale": "en"},
}
PLAN = {"industry": "开发者工具与云基础设施", "industry_basis": "产品线写着 Cloud GPU rental（测试固定）",
        "category_en": "cloud gpu rental"}


def scrapeless_key() -> str:
    k = os.environ.get("SCRAPELESS_API_KEY", "").strip()
    if k:
        return k
    try:
        return subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                              capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return ""


KEY = scrapeless_key()
SANDBOX = {"HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9",
           "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9",
           "NO_PROXY": "api.scrapeless.com", "no_proxy": "api.scrapeless.com",
           "SCRAPELESS_API_KEY": KEY}

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" —— {detail}" if detail and not ok else ""))


def env(domestic: bool, **extra) -> dict:
    e = {k: v for k, v in os.environ.items() if k not in ("GEO_NET_DOMESTIC",)}
    e.update(SANDBOX)
    if domestic:
        e["GEO_NET_DOMESTIC"] = "1"
    e.update(extra)
    return e


def run(args: list, domestic: bool, timeout: int = 300, **extra) -> tuple[int, str, float]:
    t = time.time()
    p = subprocess.run([sys.executable, *map(str, args)], env=env(domestic, **extra), capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr, time.time() - t


PROBE = r'''
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1], timeout=10); print("OK")
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
except Exception as e:
    print("FAIL", type(e).__name__)
'''


def main() -> int:
    if not KEY:
        print("缺 SCRAPELESS_API_KEY（环境变量或钥匙串），这个测试要真实调用 Scrapeless")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="e2e-domestic-"))
    try:
        cache = tmp / "net_cache"
        # S1 模拟是否生效
        probes = {u: run(["-c", PROBE, u], False)[1].strip() for u in
                  ("https://www.google.com/", "https://example.com/", "https://api.dataforseo.com/v3/appendix/user_data",
                   "https://api.scrapeless.com/api/v1/scraper/request")}
        blocked = all(probes[u].startswith("FAIL") for u in list(probes)[:3])
        scrapeless_up = probes["https://api.scrapeless.com/api/v1/scraper/request"].startswith(("OK", "HTTP"))
        check("S1 模拟生效：只有 Scrapeless 连得上", blocked and scrapeless_up, json.dumps(probes, ensure_ascii=False))

        # D1 普通网页
        rc, out, _ = run([NET, "fetch", "https://example.com/", "--country", "US"], True, NET_CACHE_DIR=str(cache))
        check("D1 fetch 普通网页经 Scrapeless 代理", rc == 0 and "跳过直连（境内模式），经 Scrapeless US 代理取得" in out
              and "Example Domain" in out, out[:300])

        # D2 短 JSON 接口
        sug = "https://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q=cloud+gpu+rental"
        rc, out, _ = run([NET, "fetch", sug, "--raw", "--country", "US"], True, NET_CACHE_DIR=str(cache))
        body = out.split("\n\n", 1)[1] if "\n\n" in out else ""
        try:
            arr = json.loads(body)
        except ValueError:
            arr = None
        check("D2 短 JSON（自动补全）经代理放行", isinstance(arr, list) and len(arr) > 1 and len(arr[1]) > 0, out[:300])

        # D3 Hacker News
        hn = "https://hn.algolia.com/api/v1/search?query=gpu%20cloud&tags=comment&hitsPerPage=5"
        rc, out, _ = run([NET, "fetch", hn, "--raw", "--country", "US"], True, NET_CACHE_DIR=str(cache))
        body = out.split("\n\n", 1)[1] if "\n\n" in out else ""
        try:
            hits = json.loads(body).get("hits")
        except (ValueError, AttributeError):
            hits = None
        check("D3 Hacker News 接口经代理取到", isinstance(hits, list) and len(hits) > 0, out[:300])

        # D4 reddit / render 不发请求
        rc, out_r, secs_r = run([NET, "reddit", "cloud gpu rental"], True, NET_CACHE_DIR=str(cache))
        rc2, out_c, secs_c = run([NET, "render", "https://www.rtings.com/headphones/reviews/best", "--country", "US"], True,
                                 timeout=300, NET_CACHE_DIR=str(cache))
        check("D4 reddit 搜索直接回读不到；render 不起 Chrome、改经 Scrapeless 代理取到 RTINGS 正文（3.6.4）",
              out_r.startswith("读不到：境内模式") and secs_r < 3
              and "境内模式不用无头 Chrome，改经 Scrapeless US 代理取得" in out_c and "RTINGS" in out_c, f"{out_r[:120]} | {out_c[:160]}")

        # D10 Pantip（3.6.2）：境内模式经 Scrapeless JS 渲染取评论，不用本机 Chrome
        rc, out, secs_p = run([NET, "pantip", "https://pantip.com/topic/43425984", "--country", "TH"], True, timeout=400,
                              NET_CACHE_DIR=str(cache))
        check("D10 net.py pantip 境内模式经 Scrapeless 渲染取到评论", out.startswith("[来源]") and "经 Scrapeless TH 渲染取得" in out
              and "1. [评论]" in out and "#comment1" in out, out[:300])

        # D5 search
        rc, out, _ = run([NET, "search", "cloud gpu rental", "--gl", "us", "--hl", "en"], True, NET_CACHE_DIR=str(cache))
        check("D5 net.py search 有结果", rc == 0 and out.lstrip().startswith("1. "), out[:300])

        # D6 / D7 搜索联想
        serp_out = tmp / "serp"
        rc, out, _ = run([SERP, "cloud gpu rental", "--gl", "us", "--hl", "en", "--out", serp_out], True, timeout=400)
        s = json.loads((serp_out / "summary.json").read_text(encoding="utf-8")) if (serp_out / "summary.json").exists() else {}
        seed = (s.get("seeds") or s.get("per_seed") or [{}])[0] if isinstance(s.get("seeds") or s.get("per_seed"), list) else {}
        check("D6 collect_serp_signals 境内模式：PAA/相关搜索/自动补全都有，付费 2 次",
              rc == 0 and (seed.get("paa", 0) + seed.get("related", 0)) > 0 and seed.get("autocomplete", 0) > 0
              and s.get("paid_calls") == 2, json.dumps({"rc": rc, "seed": seed, "paid": s.get("paid_calls"),
                                                        "tail": out[-300:]}, ensure_ascii=False))
        rc, out, _ = run([SERP, "cloud gpu rental", "--gl", "us", "--hl", "en", "--out", serp_out], True, timeout=200)
        s1b = json.loads((serp_out / "summary.json").read_text(encoding="utf-8"))
        seed1b = (s1b.get("per_seed") or [{}])[0]
        check("D6b 境内模式重跑：自动补全读 raw/*.autocomplete.json，不再付费", s1b.get("paid_calls") == 0
              and seed1b.get("autocomplete", 0) > 0 and any(serp_out.glob("raw/*.autocomplete.json")),
              json.dumps({"seed": seed1b, "paid": s1b.get("paid_calls")}, ensure_ascii=False))
        rc, out, _ = run([SERP, "cloud gpu rental", "--gl", "us", "--hl", "en", "--out", serp_out], False, timeout=200)
        s2 = json.loads((serp_out / "summary.json").read_text(encoding="utf-8")) if (serp_out / "summary.json").exists() else {}
        seed2 = (s2.get("seeds") or s2.get("per_seed") or [{}])[0] if isinstance(s2.get("seeds") or s2.get("per_seed"), list) else {}
        check("D7 对照：不开境内模式，自动补全连不上", seed2.get("autocomplete", -1) == 0
              and "自动补全接口失败" in str(seed2.get("error")) and s2.get("paid_calls") == 0,
              json.dumps({"seed": seed2, "paid": s2.get("paid_calls")}, ensure_ascii=False))

        # D8 prepare 的 TASK.md
        case = tmp / "case.json"
        case.write_text(json.dumps(CASE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
        ws_on, ws_off = tmp / "ws-on", tmp / "ws-off"
        rc_on, out_on, _ = run([RUNNER, "prepare", "--case", case, "--market", "US", "--platforms", "chatgpt",
                                "--out", ws_on], True)
        rc_off, out_off, _ = run([RUNNER, "prepare", "--case", case, "--market", "US", "--platforms", "chatgpt",
                                  "--out", ws_off], False)
        task_on = (ws_on / "TASK.md").read_text(encoding="utf-8") if (ws_on / "TASK.md").exists() else ""
        task_off = (ws_off / "TASK.md").read_text(encoding="utf-8") if (ws_off / "TASK.md").exists() else ""
        check("D8 prepare：开关打开 TASK.md 带境内模式一节，关掉没有",
              rc_on == 0 and rc_off == 0 and "## 境内模式" in task_on and "## 境内模式" not in task_off,
              (out_on + out_off)[-400:])

        # D9 precollect
        plan_dir = ws_on / "research/precollect"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan.json").write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
        rc, out, secs = run([RUNNER, "precollect", "--out", ws_on], True, timeout=1500)
        summ_p = plan_dir / "summary.json"
        summ = json.loads(summ_p.read_text(encoding="utf-8")) if summ_p.exists() else {}
        cats = summ.get("categories") or {}
        dump = json.dumps(cats, ensure_ascii=False)
        chans = [c for cat in cats.values() for c in (cat.get("channels") or [])]
        by = {c.get("name") or c.get("channel"): c for c in chans if isinstance(c, dict)}
        hn_ok = (by.get("hackernews") or {}).get("status") == "ok" and (by.get("hackernews") or {}).get("rows", 0) > 0
        rd = by.get("reddit") or {}
        check("D9a precollect 写完 summary.json，搜索联想 ok", rc == 0 and bool(summ)
              and (cats.get("搜索联想") or {}).get("status") == "ok" and (cats.get("搜索联想") or {}).get("rows", 0) > 0,
              f"rc={rc} {out[-300:]} {dump[:400]}")
        check("D9b Hacker News 经代理采到", hn_ok, json.dumps(by.get("hackernews"), ensure_ascii=False))
        check("D9c Reddit：RSS 记境内模式；取到的话只能是网页版（代理）", (((rd.get("status") == "ok" and rd.get("proxy_pages")) or (rd.get("status") != "ok" and "境内模式" in json.dumps(rd, ensure_ascii=False)))),
              json.dumps(rd, ensure_ascii=False))
        tp = by.get("trustpilot") or {}
        check("D9d DataForSEO 连不上只记失败", tp.get("status") not in (None, "ok"), json.dumps(tp, ensure_ascii=False))
        # D11 每轮记账：Scrapeless 各类用量都数得到，cost_report 按单价算出钱（3.6.3）
        prepared_at = json.loads((ws_on / "out/result.json").read_text(encoding="utf-8")).get("prepared_at", "")
        code = ("import importlib.util,json,pathlib;"
                f"s=importlib.util.spec_from_file_location('r',{str(RUNNER)!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                f"print(json.dumps(m.collect_costs(pathlib.Path({str(ws_on)!r}),'US',{prepared_at!r}),ensure_ascii=False))")
        rc, out, _ = run(["-c", code], True)
        try:
            costs = json.loads(out)
        except ValueError:
            costs = {}
        sc = costs.get("scrapeless_requests") or {}
        res_p = ws_on / "out/result.json"
        res = json.loads(res_p.read_text(encoding="utf-8"))
        res["costs"] = costs
        res_p.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        prices = tmp / "prices.json"
        prices.write_text(json.dumps({"answer_unit_cny": 0.5, "bill_failed_attempts": True, "llm_input_usd_per_m": 0,
                                      "llm_output_usd_per_m": 0, "llm_cache_read_usd_per_m": 0, "llm_cache_write_usd_per_m": 0,
                                      "serp_usd_per_k": 1.0, "proxy_usd_per_k": 1.0, "render_usd_per_k": 2.0, "usd_cny": 7.1}))
        rc, rep, _ = run([SHARED / "cost_report.py", ws_on, "--prices", prices, "--no-ledger"], True)
        row = next((ln for ln in rep.splitlines() if ln.startswith("| Brandx")), "")
        expect_usd = ((sc.get("serp_requests", 0) + sc.get("net_search_requests", 0)) * 1.0
                      + (sc.get("proxy_pages", 0) + sc.get("autocomplete_proxy", 0)) * 1.0 + sc.get("render_pages", 0) * 2.0) / 1000
        check("D11 记账：搜索、代理页、境内自动补全都计数，cost_report 按单价算出 Brandx 这一轮",
              isinstance(sc.get("serp_requests"), int) and sc["serp_requests"] > 0 and sc.get("autocomplete_proxy", 0) > 0
              and isinstance(sc.get("proxy_pages"), int) and sc["proxy_pages"] > 0 and rc == 0
              and f"{expect_usd * 7.1:.2f}" in row,
              json.dumps({"scrapeless": sc, "row": row, "expect_cny": round(expect_usd * 7.1, 4)}, ensure_ascii=False)[:500])
        precollect_secs = round(secs)
        channel_lines = [f"| {c.get('name') or c.get('channel')} | {c.get('status')} | {c.get('rows', '')} | "
                         f"{c.get('pages', '')} | {str(c.get('reason') or '')[:120]} |" for c in chans if isinstance(c, dict)]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(ok for _, ok, _ in results)
    lines = [f"# 境内模式端到端校验\n", f"运行时间：{datetime.now():%Y-%m-%d %H:%M}，脚本 `evals/e2e_domestic_network.py`\n",
             "模拟：HTTPS_PROXY 指向死端口、NO_PROXY 只放行 api.scrapeless.com（DataForSEO 也连不上）。\n",
             f"结论：{passed}/{len(results)} 通过\n", "| 项 | 结果 | 说明 |", "|-|-|-|"]
    lines += [f"| {n} | {'通过' if ok else '失败'} | {d[:200].replace('|', '/') if not ok else ''} |" for n, ok, d in results]
    if "channel_lines" in locals():
        lines += ["", f"## precollect 各渠道（用时 {precollect_secs} 秒）", "", "| 渠道 | 状态 | 条数 | 页面 | 原因 |",
                  "|-|-|-|-|-|", *channel_lines]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} 通过，报告：{REPORT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
