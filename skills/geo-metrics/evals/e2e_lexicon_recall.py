#!/usr/bin/env python3
"""端到端：开放品牌查漏（mine_brand_lexicon.py --check）与「同一品牌拆成两条」自检。

不联网、不用客户数据：在临时目录造一批 Scrapeless 格式的回答和词表，跑真实脚本（子进程），
核对候选分档、退出码和拆分报告；结果写到 ``reports/lexicon-recall-e2e.md``。

先写下它可能失败的方式，每条都有对应用例：
  F1 长尾厂商只在推荐位出现一两次，按出现次数排不到前面 → 漏收（必须进 A 档）
  F2 品牌只出现在 ChatGPT 商品卡里 → 漏收（必须进 A 档）
  F3 中文（繁体）机构名在加粗列表里 → 英文大写规则看不到（必须进 A 档）
  F4 繁简写法不同（词表「恒生银行」、答案「恆生銀行」）→ 被当成已收而漏掉（必须进 A 档）
  F5 泛称、普通词、型号、短缩写淹没 A 档（「傳統銀行」「Best」「Built-in」「C3」「GPS」不得进 A 档）
  F6 词表已收的品牌又被列成候选（不得出现在 A 档）
  F7 同一品牌拆成两条：别名重复、整词包含、中文包含、域名主标签相同 → 必须报出
  F8 确属两家写进 distinct_brands 后仍被报 → 不得再报
  F9 名字只是前缀相同、不是整词（Citi / Citizen）→ 不得误报
  F10 退出码：有漏收或拆分为 1，处理干净为 0
用法：python3 evals/e2e_lexicon_recall.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
MINE = SKILL / "scripts" / "mine_brand_lexicon.py"
AUDIT = SKILL / "scripts" / "audit_lexicon_domains.py"
REPORT = SKILL / "reports" / "lexicon-recall-e2e.md"

ANSWERS = {
    "0001": ("chatgpt", "Here are the best options.\n\n**1. Aoocci C3 Pro**\n- Bright screen\n\n"
             "**2. Podofo**\n- OEM/ODM manufacturer\n\n**3. MotoOptix**\n- Wholesale program\n\n"
             "**Best overall:** Built-in GPS matters.\n\nMore: [Podofo Official](<https://www.podofo.com/>)",
             [{"title": "Zentrix 6 inch CarPlay Screen", "id": "p1", "cite": "turn0product1", "price": "$99"}]),
    "0002": ("chatgpt", "| Brand | Note |\n|---|---|\n| Aoocci | budget |\n| Spedal | dealer |\n\n"
             "Also consider the motorcycle display market; best overall picks vary.", []),
    "0003": ("gemini", "在香港可以考慮：\n\n- **耀才證券**：老牌本地券商\n- **恆生銀行**：銀行渠道\n"
             "- **傳統銀行**：手續費較高\n- **富途證券**：App 好用", []),
    "0004": ("gemini", "### 1. 耀才證券\n介紹……\n\n**哪間香港銀行** 最適合？\n\n- **GPS** support\n", []),
}

LEX_OPEN = {  # 查漏用：漏收 Podofo、MotoOptix、Spedal、Zentrix、耀才、恆生異寫
    "brands": [
        {"name": "Aoocci", "aliases": ["Aoocci"], "domains": ["aoocci.com"], "type": "competitor"},
        {"name": "moomoo", "aliases": ["moomoo", "富途證券"], "domains": ["moomoo.com"], "type": "competitor"},
        {"name": "Hang Seng Bank", "aliases": ["Hang Seng Bank", "恒生银行"], "domains": [], "type": "open"},
    ],
    "stopwords": ["Here", "More", "Also", "Brand", "Note"],
}
LEX_SPLIT = {
    "brands": [
        {"name": "Webull", "aliases": ["Webull"], "domains": ["webull.com"]},
        {"name": "Webull Hong Kong", "aliases": ["Webull HK"], "domains": ["webull.hk"]},       # 整词包含 + 域名
        {"name": "Chief Securities", "aliases": ["致富證券"], "domains": []},
        {"name": "CF Securities", "aliases": ["致富"], "domains": []},                        # 中文包含
        {"name": "KGI", "aliases": ["KGI"], "domains": []},
        {"name": "KGI Securities", "aliases": ["KGI", "KGI Securities"], "domains": []},      # 别名重复
        {"name": "Bank of China (Hong Kong)", "aliases": ["中银"], "domains": []},
        {"name": "BOCI", "aliases": ["中银国际"], "domains": []},                              # 确属两家
        {"name": "Citi", "aliases": ["Citi"], "domains": ["citi.com"]},
        {"name": "Citizens Bank", "aliases": ["Citizens Bank"], "domains": ["citizensbank.com"]},  # 前缀不是整词
        {"name": "Zeta", "aliases": ["Zeta"], "domains": ["zeta.com"]},
        {"name": "Omega Asia", "aliases": ["Omega Asia"], "domains": ["zeta.hk"]},          # 只有域名主标签相同
    ],
    "distinct_brands": [["Bank of China (Hong Kong)", "BOCI"]],
}


def build_collect(root: Path) -> Path:
    for qid, (platform, text, products) in ANSWERS.items():
        d = root / f"scraper.{platform}" / "US"
        d.mkdir(parents=True, exist_ok=True)
        field = "result_text"
        task = {field: text, "prompt": f"q{qid}"}
        if products:
            task["products"] = products
        (d / f"{qid}.json").write_text(json.dumps({"status": "success", "task_result": task}), encoding="utf-8")
    return root


def run(cmd):
    p = subprocess.run([sys.executable, "-I", *map(str, cmd)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def tiers(csv_path: Path) -> dict:
    return {r["candidate"]: r["tier"] for r in csv.DictReader(csv_path.open(encoding="utf-8"))}


def main() -> int:
    results = []

    def case(cid, desc, ok, detail=""):
        results.append((cid, desc, bool(ok), detail))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        collect = build_collect(tmp / "collect")
        lex = tmp / "lex.json"
        lex.write_text(json.dumps(LEX_OPEN, ensure_ascii=False), encoding="utf-8")
        out = tmp / "cand.csv"
        code, log = run([MINE, "--collect-dir", collect, "--lexicon", lex, "--out", out, "--check", "--show-unknown", "0"])
        t = tiers(out)
        a = {k for k, v in t.items() if v == "A"}
        case("F1", "推荐位长尾厂商进 A 档（Podofo、MotoOptix、Spedal）", {"Podofo", "MotoOptix", "Spedal"} <= a, sorted(a))
        case("F2", "只在商品卡出现的品牌进 A 档（Zentrix）", "Zentrix" in a, t.get("Zentrix"))
        case("F3", "繁体中文机构名进 A 档（耀才證券）", "耀才證券" in a, t.get("耀才證券"))
        case("F4", "繁简异写算没收（恆生銀行）", "恆生銀行" in a, t.get("恆生銀行"))
        noise = {"傳統銀行", "哪間香港銀行", "Best", "Built-in", "C3", "GPS", "Best overall"}
        case("F5", "泛称、普通词、型号、短缩写不进 A 档", not (noise & a), sorted(noise & a))
        case("F6", "已收品牌不进 A 档（Aoocci、富途證券）", not ({"Aoocci", "富途證券"} & a), sorted({"Aoocci", "富途證券"} & a))
        case("F10a", "有漏收时 --check 退出码 1", code == 1, code)

        # 补齐后应为 0
        fixed = json.loads(json.dumps(LEX_OPEN))
        for name in ["Podofo", "MotoOptix", "Spedal", "Zentrix"]:
            fixed["brands"].append({"name": name, "aliases": [name], "domains": [], "type": "open"})
        fixed["brands"].append({"name": "Bright Smart Securities", "aliases": ["耀才證券"], "domains": [], "type": "open"})
        fixed["brands"][2]["aliases"].append("恆生銀行")
        lex.write_text(json.dumps(fixed, ensure_ascii=False), encoding="utf-8")
        code2, log2 = run([MINE, "--collect-dir", collect, "--lexicon", lex, "--out", out, "--check", "--show-unknown", "0"])
        case("F10b", "补齐后 --check 退出码 0", code2 == 0, log2[-300:] if code2 else 0)

        # 拆分自检
        split = tmp / "split.json"
        split.write_text(json.dumps(LEX_SPLIT, ensure_ascii=False), encoding="utf-8")
        code3, log3 = run([AUDIT, "--lexicon", split])
        pairs = {
            "整词包含/域名": "Webull ↔ Webull Hong Kong",
            "中文包含": "Chief Securities ↔ CF Securities",
            "别名重复": "KGI ↔ KGI Securities",
            "域名主标签": "Zeta ↔ Omega Asia",
        }
        case("F7", "四类拆分都报出（别名重复、整词包含、中文包含、域名主标签）",
             all(v in log3 for v in pairs.values()), [k for k, v in pairs.items() if v not in log3])
        case("F8", "distinct_brands 里的品牌对不再报", "BOCI" not in log3, "")
        case("F9", "前缀相同但不是整词不误报（Citi / Citizens Bank）", "Citizens Bank" not in log3, "")
        code4, log4 = run([MINE, "--collect-dir", collect, "--lexicon", split, "--out", out, "--check", "--show-unknown", "0"])
        case("F10c", "拆分也让 --check 退出码 1", code4 == 1 and "拆成两条" in log4, code4)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(ok for *_, ok, _ in results)
    lines = [f"# 开放品牌查漏与拆分自检 端到端（{passed}/{len(results)} 通过）", "",
             "由 `evals/e2e_lexicon_recall.py` 生成；数据为脚本内造的回答和词表，不含客户数据。", "",
             "| 用例 | 检查 | 结果 | 细节 |", "|---|---|---|---|"]
    for cid, desc, ok, detail in results:
        lines.append(f"| {cid} | {desc} | {'通过' if ok else '失败'} | {'' if ok else str(detail).replace('|', '/')[:200]} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for cid, desc, ok, detail in results:
        print(f"{'✓' if ok else '✗'} {cid} {desc}" + ("" if ok else f"  → {detail}"))
    print(f"{passed}/{len(results)} 通过；报告 {REPORT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
