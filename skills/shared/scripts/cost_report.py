#!/usr/bin/env python3
"""按客户汇总花费，算平均每个客户花多少钱（2026-11-10 起）。

只读本地文件，不调任何接口。三类来源：

  选词轮     扫描目录下每个 out/result.json 的 costs 块（run_selection_mode.py 3.1.0 起写）：
             LLM usage、预跑尝试次数、SERP 请求数、代理页数、net.py 搜索次数。客户取 costs.brand。
  采集       扫描目录下每个 _collector/events.jsonl（collect_answers.py 的产物：试跑、基线、售前采集、
             本地选词的研究预跑），数 event=attempt 的行。客户取路径里「评测数据/<客户>/」那一段，
             取不到的归「未归集」并列出路径。在选词工作目录里的不重复算（已在选词轮里）；
             内容完全相同的 events.jsonl（镜像目录）只算一次。
  DataForSEO 服务端流水（默认 ~/.dataforseo/ledger.jsonl，DATAFORSEO_LEDGER 或 --ledger 可改），
             按 case 汇总、不含沙盒；case 去掉末尾的市场代码当客户名。选词轮 costs 里的 DataForSEO
             也来自这份流水，表里只按流水算一次，不重复加。

单价一律读本机配置，本文件不写任何单价（本脚本会进公开仓库）：
  ~/.geo-cost/prices.json（--prices 可改），键见 PRICE_KEYS；没有配置时全部按 0 计价并提示。
  python3 -I cost_report.py --write-example   在 ~/.geo-cost/prices.example.json 写示例（内部单价留 0 自己填）

    python3 -I cost_report.py <目录> [<目录> ...] [--since 2026-11-01] [--alias 英文名=客户名] [--json]

客户名对不上（Case 填英文名、目录是中文名）时用 --alias 合并，可重复。名字匹配 --exclude（默认
「test」「测试」，不分大小写）的是记账测试，单列「已排除」，不进平均；--exclude '' 关闭。
金额单位：元；美元项按配置里的 usd_cny 换算。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PRICE_KEYS = {
    "answer_unit_cny": "每条 AI 答案（Scrapeless AI Scraper，一次尝试）的采购价，元；内部价，自己填",
    "bill_failed_attempts": "失败的尝试是否也计费（true / false）；未和后台对账前按 true 算上沿",
    "llm_input_usd_per_m": "大模型未缓存输入，美元 / 百万 token（按网关账单填）",
    "llm_output_usd_per_m": "大模型输出，美元 / 百万 token",
    "llm_cache_read_usd_per_m": "大模型缓存读取，美元 / 百万 token",
    "llm_cache_write_usd_per_m": "大模型缓存写入，美元 / 百万 token",
    "serp_usd_per_k": "Scrapeless Google 搜索，美元 / 千次（collect_serp_signals、net.py search）",
    "proxy_usd_per_k": "Scrapeless 网页代理，美元 / 千次（net.py fetch 走代理）",
    "usd_cny": "美元兑人民币汇率",
}
EXAMPLE = {
    "_说明": "复制为 prices.json 后填写。内部采购价只放在本机，不要提交到任何仓库。键的含义见 cost_report.py 的 PRICE_KEYS。",
    "answer_unit_cny": 0,
    "bill_failed_attempts": True,
    "llm_input_usd_per_m": 0,
    "llm_output_usd_per_m": 0,
    "llm_cache_read_usd_per_m": 0,
    "llm_cache_write_usd_per_m": 0,
    "serp_usd_per_k": 1.0,
    "proxy_usd_per_k": 1.0,
    "usd_cny": 7.1,
}
UNASSIGNED = "未归集"
MARKET = re.compile(r"\s+[A-Z]{2,3}$")


def load_prices(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {k: 0 for k in PRICE_KEYS} | {"bill_failed_attempts": True}, (
            f"[提示] 没有单价配置 {path}，全部按 0 计价。先运行 --write-example，复制成 prices.json 再填单价。")
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in PRICE_KEYS if k not in data]
    note = f"[提示] {path} 缺 {', '.join(missing)}，按 0 计" if missing else ""
    return {k: data.get(k, True if k == "bill_failed_attempts" else 0) for k in PRICE_KEYS}, note


def brand_from_path(path: Path) -> str:
    parts = path.parts
    for i, part in enumerate(parts[:-1]):
        if part == "评测数据" and i + 1 < len(parts) - 1:
            return parts[i + 1]
    return UNASSIGNED


def in_selection_ws(path: Path, ws_roots: set[Path]) -> bool:
    return any(root in path.parents for root in ws_roots)


def day(t: str) -> str:
    return (t or "")[:10]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*", type=Path, help="扫描目录：选词工作目录、采集输出目录、评测数据目录")
    ap.add_argument("--since", default="", help="只算这个日期及以后，如 2026-11-01")
    ap.add_argument("--prices", type=Path, default=Path.home() / ".geo-cost" / "prices.json")
    ap.add_argument("--ledger", type=Path, default=None, help="DataForSEO 流水，默认同 collect_keyword_data.py")
    ap.add_argument("--no-ledger", action="store_true", help="不算 DataForSEO")
    ap.add_argument("--alias", action="append", default=[], help="别名=客户名，合并同一客户，可重复")
    ap.add_argument("--exclude", default=r"(?i)test|测试", help="客户名匹配这个正则的不进平均（默认排除测试记账）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--write-example", action="store_true", help="写 ~/.geo-cost/prices.example.json 后退出")
    a = ap.parse_args()

    if a.write_example:
        out = Path.home() / ".geo-cost" / "prices.example.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(EXAMPLE, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"已写 {out}")
        return 0
    if not a.dirs and a.no_ledger:
        ap.error("至少给一个扫描目录，或去掉 --no-ledger")

    prices, note = load_prices(a.prices)
    alias = dict(x.split("=", 1) for x in a.alias if "=" in x)
    canon = lambda name: alias.get(name, name) or UNASSIGNED  # noqa: E731
    usd = float(prices["usd_cny"] or 0)
    rows: dict[str, dict] = defaultdict(lambda: {"rounds": 0, "llm_cny": 0.0, "sel_scrapeless_cny": 0.0,
                                                 "answers": 0, "answers_cny": 0.0, "dfs_calls": 0, "dfs_usd": 0.0,
                                                 "dfs_cny": 0.0})
    unassigned_paths: list[str] = []
    detail: list[dict] = []

    # 1. 选词轮
    ws_roots: set[Path] = set()
    for root in a.dirs:
        for res in sorted(root.resolve().rglob("out/result.json")):
            try:
                costs = json.loads(res.read_text(encoding="utf-8")).get("costs")
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(costs, dict):
                continue
            ws = res.parent.parent
            ws_roots.add(ws)
            if a.since and day(costs.get("since") or costs.get("until")) < a.since:
                continue
            llm, sc = costs.get("llm") or {}, costs.get("scrapeless_requests") or {}
            llm_usd = (llm.get("input_tokens", 0) * prices["llm_input_usd_per_m"]
                       + llm.get("output_tokens", 0) * prices["llm_output_usd_per_m"]
                       + llm.get("cache_read_input_tokens", 0) * prices["llm_cache_read_usd_per_m"]
                       + llm.get("cache_creation_input_tokens", 0) * prices["llm_cache_write_usd_per_m"]) / 1e6
            attempts = sc.get("prerun_attempts", 0) if prices["bill_failed_attempts"] else sc.get("prerun_ok", 0)
            num = lambda v: v if isinstance(v, (int, float)) else 0  # noqa: E731 -「不可归集」按 0
            sel_usd = ((num(sc.get("serp_requests")) + num(sc.get("net_search_requests"))) * prices["serp_usd_per_k"]
                       + num(sc.get("proxy_pages")) * prices["proxy_usd_per_k"]) / 1000
            name = canon(costs.get("brand") or "")
            r = rows[name]
            r["rounds"] += 1
            r["llm_cny"] += llm_usd * usd
            r["sel_scrapeless_cny"] += attempts * prices["answer_unit_cny"] + sel_usd * usd
            if llm.get("runs") and not llm.get("runs_with_usage"):
                detail.append({"type": "选词轮无 usage", "path": str(ws), "note": "宿主 --agent-cmd 没回报 token，LLM 记 0"})
            if not isinstance(sc.get("proxy_pages"), (int, float)):
                detail.append({"type": "代理页不可归集", "path": str(ws)})
            if name == UNASSIGNED:
                unassigned_paths.append(str(ws))

    # 2. 采集（不在选词工作目录里的 events.jsonl）
    seen: set[str] = set()
    for root in a.dirs:
        for ev in sorted(root.resolve().rglob("_collector/events.jsonl")):
            if in_selection_ws(ev, ws_roots):
                continue
            raw = ev.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            n = 0
            for line in raw.decode("utf-8", "replace").splitlines():
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("event") != "attempt" or (a.since and day(e.get("time", "")) < a.since):
                    continue
                if prices["bill_failed_attempts"] or e.get("ok"):
                    n += 1
            if not n:
                continue
            name = canon(brand_from_path(ev))
            rows[name]["answers"] += n
            rows[name]["answers_cny"] += n * prices["answer_unit_cny"]
            if name == UNASSIGNED:
                unassigned_paths.append(str(ev))

    # 3. DataForSEO 流水
    if not a.no_ledger:
        ledger = a.ledger or Path(os.environ.get("DATAFORSEO_LEDGER", "").strip()
                                  or Path.home() / ".dataforseo" / "ledger.jsonl")
        try:
            lines = ledger.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
            note = (note + "\n" if note else "") + f"[提示] 没有 DataForSEO 流水 {ledger}"
        for line in lines:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("sandbox") or (a.since and day(e.get("time", "")) < a.since):
                continue
            case = (e.get("case") or "").strip()
            name = canon(MARKET.sub("", case)) if case else UNASSIGNED
            rows[name]["dfs_calls"] += 1
            rows[name]["dfs_usd"] += float(e.get("cost_usd") or 0)
            rows[name]["dfs_cny"] += float(e.get("cost_usd") or 0) * usd
            if name == UNASSIGNED:
                unassigned_paths.append(f"DataForSEO 流水 {e.get('time', '')} {e.get('who', '')}（无 case）")

    for r in rows.values():
        r["total_cny"] = r["llm_cny"] + r["sel_scrapeless_cny"] + r["answers_cny"] + r["dfs_cny"]
    skip = re.compile(a.exclude) if a.exclude else None
    excluded = sorted(k for k in rows if k != UNASSIGNED and skip and skip.search(k))
    named = {k: v for k, v in rows.items() if k != UNASSIGNED and k not in excluded}
    avg = (sum(v["total_cny"] for v in named.values()) / len(named)) if named else 0.0

    if a.json:
        print(json.dumps({"since": a.since, "prices_file": str(a.prices), "customers": rows, "avg_per_customer_cny": avg,
                          "customer_count": len(named), "excluded": excluded, "unassigned": sorted(set(unassigned_paths)), "notes": detail,
                          "hint": note}, ensure_ascii=False, indent=1))
        return 0
    if note:
        print(note)
    print(f"范围：{', '.join(str(d) for d in a.dirs) or '（只看流水）'}；起始日期：{a.since or '不限'}；单价：{a.prices}")
    head = ["客户", "选词轮数", "LLM 花费", "选词 Scrapeless", "采集条数", "采集花费", "DataForSEO", "合计"]
    print("| " + " | ".join(head) + " |")
    print("|" + "-|" * len(head))
    order = sorted(named, key=lambda k: -named[k]["total_cny"]) + ([UNASSIGNED] if UNASSIGNED in rows else [])

    def line(label: str, r: dict) -> None:
        print(f"| {label} | {r['rounds']} | {r['llm_cny']:.2f} | {r['sel_scrapeless_cny']:.2f} | {r['answers']} | "
              f"{r['answers_cny']:.2f} | {r['dfs_cny']:.2f}（${r['dfs_usd']:.4f}，{r['dfs_calls']} 次） | {r['total_cny']:.2f} |")
    for k in order:
        line(k, rows[k])
    print(f"| 平均每客户（{len(named)} 个，不含{UNASSIGNED}和已排除） | | | | | | | {avg:.2f} |")
    for k in excluded:
        line(f"已排除：{k}", rows[k])
    if unassigned_paths:
        print(f"\n{UNASSIGNED}：")
        for p in sorted(set(unassigned_paths)):
            print(f"  {p}")
    for d in detail:
        print(f"[注意] {d['type']}：{d['path']}" + (f"（{d['note']}）" if d.get("note") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
