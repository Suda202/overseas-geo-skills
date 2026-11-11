#!/usr/bin/env python3
"""行业知识档案端到端校验（3.8.0，2026-11-11）。不联网、不花钱。

用两个假客户（同属「消费电子与智能家居」、同在 US）的线上工作目录跑 `industry_kb.py add --ws`，验证：
  K1 第一个客户并入后，条目都标「单例」；含品牌名、品牌别名、竞品名的条目没有进档案；JSON 和 MD 里都搜不到品牌和竞品名
  K2 第二个客户并入后，两家共有的约束条件标「通用」、记 2 个客户；只有一家有的仍是「单例」
  K2b 写法不同的同一条（只差连接词、空格）合并计数
  K3 同一客户重跑不重复计数
  K4 渠道效果：一家采到、一家没采到的渠道记「1 个客户采到、1 个没采到」；skipped 的渠道不记
  K4b 不同品类分开：耳机客户的条目进品类-earbud，不进行车记录仪那份；行业文件列品类和跨品类通用条目
  K5 行业没判出来（plan-checked.json 的 source 是 fallback）不并入任何档案
  K6 行业写「其他」时记成「其他」，靠品类区分
  K7 本地题库 `add --bank --industry --brand --competitor` 能并入
  K7b 同一品牌另一个市场分开记，合起来仍算 1 个客户
  K8 runner 钩子：learn_industry 在测试模式且没设 GEO_INDUSTRY_KB 时不写；设了就写，并在 result.json 记 industry_kb
  K9 prepare 写出的 TASK.md 让 agent 读 references/industry-knowledge/
  K10 同一客户重跑换了行业和品类：从旧行业撤掉、不重复计；没有客户的旧品类文件删除

产物：reports/industry-kb-e2e.md；临时目录跑完删除。

    python3 evals/e2e_industry_kb.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
KB = SKILL / "scripts/industry_kb.py"
RUNNER = SKILL / "scripts/run_selection_mode.py"
REPORT = SKILL / "reports/industry-kb-e2e.md"
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" —— {detail[:300]}" if detail and not ok else ""))


def make_ws(root: Path, name: str, brand: str, aliases: list[str], comps: list[str], attrs: list[str],
            channels: list[dict], industry="消费电子与智能家居", source="agent", category_en="dash cam") -> Path:
    ws = root / name
    for d in ("out", "inputs", "research/precollect"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    bank = {"config": {"brand_name": brand,
                       "slices": [{"slice_id": "s1", "audience": "私家车车主", "scene": "停车时被刮蹭要留证据",
                                   "attributes": attrs, "prompt_type": "Discovery", "priority": "高"},
                                  {"slice_id": "s2", "audience": ["网约车司机"], "scene": f"在 {brand} 和对手之间选",
                                   "attributes": [], "prompt_type": "Discovery", "priority": "中"}],
                       "topics": [{"topic_id": "t1", "topic": "行车记录仪选购"}, {"topic_id": "t2", "topic": f"{comps[0]} 替代"}],
                       "category_aliases": ["dash cam", "car camera"]}, "questions": []}
    (ws / "out/bank.json").write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    (ws / "out/result.json").write_text(json.dumps({"status": "success", "market": "US"}), encoding="utf-8")
    norm = {"normalized": {"brand_name": brand, "brand_aliases": aliases,
                           "competitor_selection": {"formal_competitors": [{"name": c} for c in comps]}}}
    (ws / "inputs/case-normalized.json").write_text(json.dumps(norm, ensure_ascii=False), encoding="utf-8")
    (ws / "research/precollect/plan-checked.json").write_text(json.dumps(
        {"industry": industry, "source": source, "category_en": category_en}, ensure_ascii=False), encoding="utf-8")
    (ws / "research/precollect/summary.json").write_text(json.dumps(
        {"categories": {"评价": {"channels": channels}}}, ensure_ascii=False), encoding="utf-8")
    return ws


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="e2e-kb-"))
    kbdir = tmp / "kb"
    env = {**os.environ, "GEO_INDUSTRY_KB": str(kbdir)}

    def add(*args):
        p = subprocess.run([sys.executable, "-I", str(KB), "add", *map(str, args)], env=env, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    try:
        ch_a = [{"name": "google-shopping", "status": "ok", "rows": 12}, {"name": "rtings", "status": "skipped"}]
        ws_a = make_ws(tmp, "a", "Zorbo", ["ZorboCam"], ["Velor", "Nexo"],
                       ["夜间画质", "停车监控", "Zorbo 专属 App", "比 Velor 便宜"], ch_a)
        rc, out = add("--ws", ws_a)
        kb = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        md = (kbdir / "品类-dash-cam.md").read_text(encoding="utf-8")
        blob = json.dumps(kb, ensure_ascii=False) + md + (kbdir / "行业-消费电子与智能家居.md").read_text(encoding="utf-8")
        cons = kb["items"]["constraints"]
        check("K1 第一个客户：条目单例；含品牌、竞品名的条目不进；全文搜不到品牌和竞品名",
              rc == 0 and {e["label"] for e in cons.values()} == {"夜间画质", "停车监控"} and "单例" in md and "（通用" not in md
              and not any(n in blob for n in ("Zorbo", "Velor", "Nexo"))
              and "在 Zorbo 和对手之间选" not in kb["items"]["scenes"], json.dumps(kb["items"], ensure_ascii=False)[:300])

        ch_b = [{"name": "google-shopping", "status": "failed", "rows": 0}]
        ws_b = make_ws(tmp, "b", "Kivo", [], ["Garvo"], ["夜间画质", "存储卡容量"], ch_b, category_en="dash cams")
        add("--ws", ws_b)
        kb = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        md = (kbdir / "品类-dash-cam.md").read_text(encoding="utf-8")
        cons = kb["items"]["constraints"]
        check("K2 第二个客户：共有的标通用（2 个客户），独有的仍是单例",
              len(cons["夜间画质"]["clients"]) == 2 and "夜间画质（通用，2 个客户" in md
              and "存储卡容量（单例，1 个客户" in md and len(kb["clients"]) == 2, md[:400])

        ws_n = make_ws(tmp, "n", "Novix", [], ["Kobri"], ["夜间 画质", "价格与预算"], [])
        ws_m = make_ws(tmp, "m", "Mirra", [], ["Zentro"], ["价格预算"], [])
        kbn = tmp / "kbn"
        envn = {**env, "GEO_INDUSTRY_KB": str(kbn)}
        for w in (ws_n, ws_m):
            subprocess.run([sys.executable, "-I", str(KB), "add", "--ws", str(w)], env=envn, capture_output=True, text=True)
        mdn = (kbn / "品类-dash-cam.md").read_text(encoding="utf-8")
        check("K2b 写法不同的同一条合并：「价格与预算」「价格预算」记 2 个客户、注明另一种写法",
              "（通用，2 个客户" in mdn and "也写作" in mdn, mdn[:500])
        add("--ws", ws_a)
        kb2 = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        check("K3 同一客户重跑不重复计数", len(kb2["clients"]) == 2 and len(kb2["items"]["constraints"]["夜间画质"]["clients"]) == 2,
              json.dumps(kb2["clients"]))

        gs = kb2["channels"].get("google-shopping") or {}
        check("K4 渠道效果：1 家采到、1 家没采到；skipped 不记", len(gs.get("ok", [])) == 1 and len(gs.get("failed", [])) == 1
              and "rtings" not in kb2["channels"] and "google-shopping：1 个客户采到、1 个没采到" in
              (kbdir / "行业-消费电子与智能家居.md").read_text(encoding="utf-8"), json.dumps(kb2["channels"]))

        # K4b 不同品类分开：耳机客户的约束条件进「品类-earbud」，不进行车记录仪那份；两个品类都出现的（假数据里的目标客户「私家车车主」）进行业文件的跨品类通用
        ws_f = make_ws(tmp, "f", "Sonia", [], ["Jabri"], ["降噪", "价格预算"], [], category_en="earbuds")
        ws_g = make_ws(tmp, "g", "Audix", [], ["Soundix"], ["价格与预算", "佩戴"], [], category_en="earbuds")
        add("--ws", ws_f); add("--ws", ws_g)
        md_e = (kbdir / "品类-earbud.md").read_text(encoding="utf-8")
        md_d = (kbdir / "品类-dash-cam.md").read_text(encoding="utf-8")
        md_i = (kbdir / "行业-消费电子与智能家居.md").read_text(encoding="utf-8")
        check("K4b 品类分开：耳机条目只进品类-earbud；行业文件列出两个品类、跨品类通用条目",
              "降噪" in md_e and "降噪" not in md_d and "夜间画质" not in md_e and "dash cam（" in md_i and "earbud（" in md_i
              and "跨品类通用的目标客户" in md_i and "私家车车主" in md_i.split("跨品类通用")[1]
              and "降噪" not in md_i, md_i[-600:])

        ws_c = make_ws(tmp, "c", "Plexa", [], ["Rinko"], ["续航"], [], industry="消费电子与智能家居", source="fallback")
        before = sorted(p.name for p in kbdir.iterdir())
        rc, out = add("--ws", ws_c)
        kb3 = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        check("K5 行业没判出来（fallback）不并入", "没有并入" in out and sorted(p.name for p in kbdir.iterdir()) == before
              and "续航" not in kb3["items"]["constraints"], out)

        ws_d = make_ws(tmp, "d", "Petly", [], ["Furlo"], ["自动喂食"], [], industry="其他", category_en="pet feeder")
        add("--ws", ws_d)
        check("K6 行业「其他」记成「其他」，靠品类区分", (kbdir / "其他.json").exists() and (kbdir / "品类-pet-feeder.md").exists(),
              str(sorted(p.name for p in kbdir.iterdir())))

        bank_e = tmp / "bank_e.json"
        bank_e.write_text(json.dumps({"config": {"brand_name": "Lumo", "collection_config": {"market": "TH"},
                                                 "slices": [{"attributes": ["夜间画质", "Lumo 云存储"], "audience": "摩托车骑手",
                                                             "scene": "骑行记录"}], "topics": []}}, ensure_ascii=False),
                          encoding="utf-8")
        rc, out = add("--bank", bank_e, "--industry", "消费电子与智能家居", "--category", "dash cam", "--competitor", "Instix")
        kb4 = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        check("K7 本地题库并入：3 个客户共有约束条件、带市场 TH，含品牌名的跳过",
              rc == 0 and len(kb4["items"]["constraints"]["夜间画质"]["clients"]) == 3
              and "TH" in kb4["items"]["constraints"]["夜间画质"]["markets"] and "lumo云存储" not in kb4["items"]["constraints"], out)
        rc, out = add("--bank", bank_e, "--industry", "消费电子与智能家居", "--category", "dash cam", "--market", "VN")
        kb4b = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        e4b = kb4b["items"]["constraints"]["夜间画质"]
        check("K7b 同一品牌另一个市场：分开记、合起来仍算 1 个客户（夜间画质还是 3 个客户，市场有 TH 和 VN）",
              rc == 0 and len(e4b["clients"]) == 3 and {"TH", "VN"} <= set(e4b["markets"]) and len({c["who"] for c in kb4b["clients"].values()}) == len(kb4b["clients"]) - 1
              and "夜间画质（通用，3 个客户" in (kbdir / "品类-dash-cam.md").read_text(encoding="utf-8"), json.dumps(e4b, ensure_ascii=False))

        # K10 同一客户重跑换了行业和品类：从旧行业撤掉、不重复计；没有客户的旧品类文件删掉
        ws_a2 = make_ws(tmp, "a2", "Zorbo", ["ZorboCam"], ["Velor", "Nexo"],
                        ["夜间画质", "停车监控"], [], industry="其他", category_en="car camera")
        add("--ws", ws_a2)
        ws_d2 = make_ws(tmp, "d2", "Petly", [], ["Furlo"], ["自动喂食"], [], industry="其他", category_en="automatic pet feeder")
        add("--ws", ws_d2)
        ce = json.loads((kbdir / "消费电子与智能家居.json").read_text(encoding="utf-8"))
        ot = json.loads((kbdir / "其他.json").read_text(encoding="utf-8"))
        zorbo = [w for w, c in ot["clients"].items() if c["category"] == "car camera"]
        check("K10 换行业换品类：旧行业撤掉、新行业记上；没客户的旧品类文件删除",
              len(zorbo) == 1 and zorbo[0] not in ce["clients"] and len(ce["items"]["constraints"]["夜间画质"]["clients"]) == 2
              and "停车监控" not in ce["items"]["constraints"] and "停车监控" in ot["items"]["constraints"]
              and len(ot["clients"]) == 2 and (kbdir / "品类-car-camera.md").exists() and (kbdir / "品类-dash-cam.md").exists()
              and not (kbdir / "品类-pet-feeder.md").exists() and (kbdir / "品类-automatic-pet-feeder.md").exists(),
              json.dumps({"ce": list(ce["clients"]), "ot": ot["clients"]}, ensure_ascii=False)
              + str(sorted(p.name for p in kbdir.iterdir())))

        spec = importlib.util.spec_from_file_location("runner", RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        kbdir2 = tmp / "kb2"
        os.environ.pop("GEO_INDUSTRY_KB", None)
        runner.learn_industry(ws_b, testing=True)
        no_write = not kbdir2.exists() and "industry_kb" not in json.loads((ws_b / "out/result.json").read_text())
        os.environ["GEO_INDUSTRY_KB"] = str(kbdir2)
        runner.learn_industry(ws_b, testing=True)
        res = json.loads((ws_b / "out/result.json").read_text())
        check("K8 runner 钩子：测试模式没设 GEO_INDUSTRY_KB 不写，设了就写并记进 result.json",
              no_write and (kbdir2 / "消费电子与智能家居.json").exists() and "industry_kb" in res, json.dumps(res, ensure_ascii=False))
        os.environ.pop("GEO_INDUSTRY_KB", None)

        case = tmp / "case.json"
        case.write_text(json.dumps({"input_version": "presales-case-input/v2", "case": {
            "品牌": "Brandx", "官方域名": "https://brandx.example", "产品线": "Dash cams: front and rear",
            "竞品": [{"名称": "RivalOne", "官网域名": "https://rival-one.example"}],
            "核心目标客户与购买场景": ["私家车车主：停车被刮蹭要留证据"]}, "options": {"locale": "en"}}, ensure_ascii=False),
            encoding="utf-8")
        p = subprocess.run([sys.executable, str(RUNNER), "prepare", "--case", str(case), "--market", "US", "--platforms",
                            "chatgpt", "--out", str(tmp / "ws-prep")], capture_output=True, text=True)
        task = (tmp / "ws-prep/TASK.md").read_text(encoding="utf-8") if (tmp / "ws-prep/TASK.md").exists() else ""
        check("K9 TASK.md 让 agent 调研前读行业和最接近的品类档案", "references/industry-knowledge/" in task and "品类-" in task
              and "行业-" in task and "假设级线索" in task,
              p.stdout[-200:] + p.stderr[-200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(ok for _, ok, _ in results)
    lines = ["# 行业知识档案端到端校验\n", f"运行时间：{datetime.now():%Y-%m-%d %H:%M}，脚本 `evals/e2e_industry_kb.py`（不联网）\n",
             f"结论：{passed}/{len(results)} 通过\n", "| 项 | 结果 | 说明 |", "|-|-|-|"]
    lines += [f"| {n} | {'通过' if ok else '失败'} | {d[:200].replace('|', '/') if not ok else ''} |" for n, ok, d in results]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} 通过，报告：{REPORT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
