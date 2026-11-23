#!/usr/bin/env python3
"""售后监测采集（试跑或正式基线，多轮）→ 售前报告流水线的标准输入，再交给 run_pipeline.py 出同一套 HTML。

2026-11-20 起售前诊断报告与售后基线报告是一套渲染（Suda：「HTML 都一样，归 geo-presales-report-builder」）。
原 geo-monitoring/scripts/build_baseline_html.py 在售前 HTML 上做字符串替换的那层补丁已删除；
这里只做输入转换，统计、校验、情感、翻译、渲染全部走 run_pipeline.py 的原生步骤。

做的事（都写进 config.out_dir）：
1. collect/：N 轮采集目录合成一个。``scraper.<平台>/<市场>/<NNNN>-r<KK>.json``，地区层就是真实市场
   （不再借地区层放意图），每个文件补上题面（AI Overviews 不回传题面，数据层靠题面把文件归到题）。
   数据层原生认 ``-rKK`` 重复采样命名。
2. questions.csv：题面、中文、主题（``topic_labels`` 可改展示名）、真实意图类型（取题库 ``prompt_type``）。
   NNNN 是 config.questions_csv 的行号（采集时用的那份 CSV），题的意图按 question_id 从 config.bank_json 取，
   停测的题（bank.config.retired）也认。
3. case.json：品牌、官网、品类、竞品（个数不限）、``报告类型``（默认「正式基线」）、``报告标题``（config.title）。
4. lexicon.json：目标、竞品、开放品牌，加 case_sensitive_aliases、competitor_site_domains。

config 沿用原 baseline-html.json 的写法（相对路径相对 config 所在目录）：
    target / competitors / open_brands / compare_brands / runs / region / bank_json / questions_csv / out_dir /
    out_name / title / category / topic_labels / case_sensitive_aliases / competitor_site_domains /
    domain_categories / multi_label_suffixes / allow_unjudged_domains / allow_lexicon_gaps / report_kind /
    changeability（changeability.csv，可选）/ difficulty（写 false 不出难度模块）
不再使用的旧字段（platform_labels、hide_sections、sentiment、translations）会打印提示后忽略：情感与译文走
run_pipeline 的暂停点，旧批次的键是按「意图|平台」写的，和现在的「市场|平台」对不上，要重新导出。

用法（在客户的售后目录运行）：
    python3 -I <项目根>/.agents/skills/geo-presales-report-builder/scripts/prepare_baseline.py \\
        --config baseline-html.json [--run]
不带 --run 只生成输入并打印 run_pipeline 命令；带 --run 直接续跑到下一个暂停点。
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
CORE = SKILLS / "geo-metrics" / "scripts"
for p in (str(HERE), str(CORE)):
    if p not in sys.path:
        sys.path.insert(0, p)

IGNORED = {"platform_labels": "平台显示名统一用数据层内置的", "hide_sections": "没数据的模块自动隐藏",
           "sentiment": "情感走 run_pipeline 第 3 步", "translations": "译文走 run_pipeline 第 4 步"}


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    cfg["_dir"] = base
    for key in ("questions_csv", "bank_json", "out_dir"):
        if key not in cfg:
            raise SystemExit(f"config 缺 {key}")
        cfg[key] = (base / cfg[key]).resolve()
    if cfg.get("changeability"):
        cfg["changeability"] = (base / cfg["changeability"]).resolve()
    cfg["runs"] = [(base / r).resolve() for r in cfg.get("runs") or []]
    if not cfg["runs"]:
        raise SystemExit("config.runs 为空：列出每一轮采集目录")
    if not cfg.get("region"):
        raise SystemExit("config 缺 region（采集目录里的市场代码，如 SG）")
    if not cfg.get("competitors"):
        raise SystemExit("config.competitors 为空")
    for key, why in IGNORED.items():
        if cfg.get(key):
            print(f"○ config.{key} 不再使用：{why}")
    return cfg


def intent_codes(cfg: dict) -> dict:
    import build_report_data as brd
    bank = json.loads(cfg["bank_json"].read_text(encoding="utf-8"))
    out = {}
    for q in bank.get("questions", []) + (bank.get("config") or {}).get("retired", []):
        raw = str(q.get("prompt_type") or q.get("intent") or q.get("diagnosis_intent") or "").strip().casefold()
        code = raw.replace(" ", "_")
        if code not in brd.CSV_INTENT_MAP:
            raise SystemExit(f"{q.get('question_id')} 意图类型 {raw!r} 不认识（可用：{sorted(brd.CSV_INTENT_MAP)}）")
        out[q["question_id"]] = code
    return out


def check_domains(cfg: dict) -> None:
    """域名类别只认 geo-metrics 的共享缓存；config 里手填、缓存里没有的列出来，不另起一份。"""
    import geo_presales_core.util as core_util
    extra = set(cfg.get("multi_label_suffixes") or []) - core_util.COMMON_MULTI_LABEL_SUFFIXES
    if extra:
        raise SystemExit(f"multi_label_suffixes {sorted(extra)} 不在 core 后缀表里：加进 "
                         "geo-metrics/scripts/geo_presales_core/util.py 的 COMMON_MULTI_LABEL_SUFFIXES")
    from geo_presales_core.sources import _known_type, load_cache
    cache = load_cache()
    missing = [(d, kind) for kind, ds in (cfg.get("domain_categories") or {}).items() for d in ds
               if _known_type(d, cache) != kind]
    if missing:
        print("⚠ config.domain_categories 里这些域名和共享缓存不一致（数据层只读共享缓存）："
              + "、".join(f"{d}={k}" for d, k in missing[:20])
              + ("…" if len(missing) > 20 else "")
              + "。要采用就写进 geo-metrics/assets/domain-categories.json。")


def prepare(cfg: dict) -> dict:
    out = cfg["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    collect = out / "collect"
    if collect.exists():
        shutil.rmtree(collect)
    questions = list(csv.DictReader(open(cfg["questions_csv"], encoding="utf-8-sig")))
    intents = intent_codes(cfg)
    region = cfg["region"]
    platforms = sorted({d.name.split(".", 1)[1] for r in cfg["runs"] for d in r.iterdir()
                        if d.is_dir() and d.name.startswith("scraper.")})
    n = 0
    for p in platforms:
        for k, run in enumerate(cfg["runs"], 1):
            for i, q in enumerate(questions, 1):
                src = run / f"scraper.{p}" / region / f"{i:04d}.json"
                if not src.exists():
                    continue
                payload = json.loads(src.read_text(encoding="utf-8"))
                payload.setdefault("task_result", {})["prompt"] = q["query"]
                dst = collect / f"scraper.{p}" / region / f"{i:04d}-r{k:02d}.json"
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                shutil.copystat(src, dst)  # 抽屉的采集时间取文件时间
                n += 1
    if not n:
        raise SystemExit(f"runs 里没有 scraper.*/{region}/NNNN.json 文件")

    topics = cfg.get("topic_labels") or {}
    with open(out / "questions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["query", "question_zh", "topic", "diagnosis_intent", "tags", "question_types"])
        w.writeheader()
        for q in questions:
            qid = q.get("question_id")
            if qid not in intents:
                raise SystemExit(f"questions_csv 的 {qid} 不在 bank_json 里，取不到意图类型")
            w.writerow({"query": q["query"], "question_zh": q.get("question_zh", ""),
                        "topic": topics.get(q["topic"], q["topic"]), "diagnosis_intent": intents[qid],
                        "tags": "", "question_types": "visibility,sentiment"})

    # 难度用的题表：题面取采集时的 CSV（和回答里的题面一致），意图取题库。题库后来改过措辞时，
    # 直接用 bank_json 会让旧回答归不上题（Housebell 基线 10-21 采集、题库 v3 之后改了 360 条回答的题面）
    with open(out / "questions-readings.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["question_id", "query", "topic", "intent", "region"])
        w.writeheader()
        for q in questions:
            w.writerow({"question_id": q["question_id"], "query": q["query"],
                        "topic": topics.get(q["topic"], q["topic"]), "intent": intents[q["question_id"]],
                        "region": q.get("region", "")})

    t, comps = cfg["target"], cfg["competitors"]
    case = {"品牌名称": t["name"], "官方域名": t["official_domains"][0], "品类": cfg.get("category", ""),
            "报告类型": cfg.get("report_kind") or "正式基线", "报告标题": cfg.get("title") or ""}
    for i, c in enumerate(comps, 1):
        case[f"竞品 {i}"], case[f"竞品 {i} 官网域名"] = c["name"], c["official_domains"][0]
    (out / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")

    # open_brands 按定义是回答里的同类品牌（社群、媒体不写进来），难度和缺口诊断按 same_category 认同类；
    # 没写的默认同类，写了 false 的照旧
    brands = ([dict(t, type="target")] + [dict(c, type="competitor") for c in comps]
              + [dict(b, same_category=b.get("same_category", True)) for b in cfg.get("open_brands") or []])
    lexicon = {"brands": brands}
    for key in ("case_sensitive_aliases", "competitor_site_domains"):
        if cfg.get(key):
            lexicon[key] = list(cfg[key])
    (out / "lexicon.json").write_text(json.dumps(lexicon, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"合成采集文件 {n} 个（{len(cfg['runs'])} 轮 × 平台 {', '.join(platforms)}）→ {collect}")
    return {"platforms": platforms}


def pipeline_cmd(cfg: dict, platforms: list) -> list:
    out = cfg["out_dir"]
    show = [cfg["target"]["name"]] + list(cfg.get("compare_brands") or [c["name"] for c in cfg["competitors"]])
    name = Path(cfg.get("out_name") or cfg["target"]["name"]).stem
    cmd = [sys.executable, HERE / "run_pipeline.py", "--collect", out / "collect",
           "--questions", out / "questions.csv", "--case", out / "case.json", "--lexicon", out / "lexicon.json",
           "--out-dir", out, "--regions", cfg["region"], "--platforms", ",".join(platforms),
           "--source-limit", "0", "--brands", ",".join(show), "--target", cfg["target"]["name"],
           "--brand-name", name]
    if cfg.get("allow_unjudged_domains"):
        cmd += ["--allow-unjudged-domains", str(cfg["allow_unjudged_domains"])]
    if cfg.get("allow_lexicon_gaps"):
        cmd += ["--allow-lexicon-gaps", str(cfg["allow_lexicon_gaps"])]
    if (out / "difficulty" / "difficulty.json").exists():
        cmd += ["--difficulty", out / "difficulty"]
    return [str(c) for c in cmd]


def run_difficulty(cfg: dict) -> None:
    """竞争难度与优化难度：调 geo-gap-diagnosis 的 layer_readings.py → difficulty.py（判法归它），
    结果在 out_dir/difficulty/，run_pipeline 用 --difficulty 接进报告。config.difficulty = false 时不出。"""
    if cfg.get("difficulty") is False:
        print("○ config.difficulty = false，不出「竞争与优化难度」模块")
        return
    gap = SKILLS / "geo-gap-diagnosis" / "scripts"
    out = cfg["out_dir"] / "difficulty"
    readings = out / "readings"
    cmd = [sys.executable, "-I", gap / "layer_readings.py", "--bank", cfg["out_dir"] / "questions-readings.csv",
           "--brand", cfg["target"]["name"], "--collect", *cfg["runs"],
           "--lexicon", cfg["out_dir"] / "lexicon.json", "--out", readings]
    for d in cfg["target"].get("official_domains") or []:
        cmd += ["--official", d]
    rc = subprocess.run([str(c) for c in cmd]).returncode
    if rc not in (0, 1):  # 1 = 有归不上的文件，清单在 readings/issues.json，照常往下
        raise SystemExit(f"layer_readings 失败（退出码 {rc}）")
    cmd = [sys.executable, "-I", gap / "difficulty.py", "--readings", readings, "--out", out]
    if cfg.get("changeability"):
        cmd += ["--changeability", cfg["changeability"]]
    else:
        print("○ config 没写 changeability（geo-monitoring changeability_domains.py 的 changeability.csv）："
              "优化难度不判只改官网能否改变")
    if subprocess.run([str(c) for c in cmd]).returncode:
        raise SystemExit("difficulty.py 失败")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--run", action="store_true", help="生成输入后直接跑 run_pipeline 到下一个暂停点")
    args = ap.parse_args(argv)
    cfg = load_config(args.config.resolve())
    check_domains(cfg)
    info = prepare(cfg)
    run_difficulty(cfg)
    cmd = pipeline_cmd(cfg, info["platforms"])
    print("→ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    if not args.run:
        return 0
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
