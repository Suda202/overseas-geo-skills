#!/usr/bin/env python3
"""诊断素材包端到端校验（diagnosis_materials.py）。不联网、不花钱。

这个用例防的失败方式：
  1. 检索词字段只认 {"queries": [...]} 一种结构 —— 实际 raw json 里还有直接是列表、或整个字段缺失的，
     漏读会让 fan-out 总数和新增限定词凭空少一截。
  2. 脚注行（[数字]: ...）和 <img ...> 标签被当成正文 —— 品牌名会从引用清单、图片说明里被抓进
     「AI 对品牌的原话」，分析师会引用一句 AI 根本没说过的话。
  3. 题面里已有的词被算成「新增限定词」—— 新增限定词就失去意义，看不出 AI 在题面之外加了什么条件。
  4. 没给 --pagegap / --changeability 时崩溃，或仍然输出对应字段 —— 下游会读出空洞的缺口与可改变性。
  5. 旧名出现在检索词里、但回答正文没提品牌时，target_in_answer 被写成 True —— 会把「AI 搜索时想到旧名、
     回答里没提」误读成「回答提到了」。
  6. 每题读数、页面被引次数、可改变性原因前缀汇总错（跨回答/跨题累加、空 suggested 不记「不适用」）。

用假品牌（Veyra / Lumo）和 2 道题、4 条回答的假数据跑通，断言以上各点，最后打印 PASS 行数。

    python3 evals/e2e_diagnosis_materials.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts/diagnosis_materials.py"

results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" —— {detail[:400]}" if detail and not ok else ""))


def run(args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


QUESTIONS = [
    {"question_id": "T-01", "question": "best speech data providers for startups",
     "topic": "语音数据", "prompt_type": "discovery", "named": False},
    {"question_id": "T-02", "question": "how much does speech data cost",
     "topic": "语音数据", "prompt_type": "evaluation", "named": False},
]

# 4 条回答：raw1 字典式检索词、raw2 列表式、raw3 字典式、raw4 整个字段缺失
ANSWERS = [
    {"answer_id": "a1", "file": "raw1.json", "question_id": "T-01", "platform": "chatgpt",
     "target_mentioned": False, "official_retrieved": True, "official_cited": False,
     "competitor_cited_urls": ["https://comp.example/a"],
     "third_cited_urls": ["https://third.example/x"]},
    {"answer_id": "a2", "file": "raw2.json", "question_id": "T-01", "platform": "chatgpt",
     "target_mentioned": True, "official_retrieved": False, "official_cited": True,
     "competitor_cited_urls": ["https://comp.example/a"],
     "third_cited_urls": []},
    {"answer_id": "a3", "file": "raw3.json", "question_id": "T-02", "platform": "chatgpt",
     "target_mentioned": True, "official_retrieved": False, "official_cited": False,
     "competitor_cited_urls": [], "third_cited_urls": ["https://third.example/x"]},
    {"answer_id": "a4", "file": "raw4.json", "question_id": "T-02", "platform": "chatgpt",
     "target_mentioned": False, "official_retrieved": False, "official_cited": False,
     "competitor_cited_urls": [], "third_cited_urls": []},
]

RAW = {
    # 字典式；含旧名但回答没提品牌
    "raw1.json": {"task_result": {
        "result_text": (
            "Veyra provides speech data collection for teams that need multilingual coverage quickly.\n"
            "A competitor is Lumo.\n"
            "[1]: Veyra SpeechOcean speech data collection services for enterprise buyers everywhere.\n"
            '<img src="veyra.png" alt="Veyra speech data">\n'
            "Veyra short.\n"
        ),
        "search_model_queries": {"queries": [
            "speech data providers pricing for startups",
            "SpeechOcean data collection vendors 2026",
            "Veyra vs Lumo speech data vendors",
        ], "type": "search_model_queries"},
    }},
    # 列表式
    "raw2.json": {"task_result": {
        "result_text": "Veyra is a solid choice when you need fast delivery of multilingual speech data.",
        "search_model_queries": ["speech data providers 2025", "cheap speech data vendors"],
    }},
    # 字典式；旧名命中且回答提到品牌
    "raw3.json": {"task_result": {
        "result_text": "Pricing at Veyra depends on volume and language pair for each project.",
        "search_model_queries": {"queries": ["speech data cost per hour 2026 SpeechOcean"], "type": "x"},
    }},
    # 整个 search_model_queries 缺失
    "raw4.json": {"task_result": {"result_text": "No brand is mentioned in this answer at all."}},
}

PAGE_GAP_CSV = (
    "question_id,url,answers,answers_target_absent,fetch,gap,target_on_page,competitors_on_page\n"
    "T-01,https://comp.example/a,2,1,ok,页面缺口,False,4\n"
    "T-01,https://third.example/x,1,0,ok,无,True,0\n"
)

CHANGEABILITY_CSV = (
    "question_id,prompt_type,suggested,reason\n"
    "T-01,discovery,高,高（官网差距）：竞品官网在 67% 的回答里被引\n"
    "T-02,evaluation,,\n"
)


def build(tmp: Path) -> Path:
    readings = tmp / "readings"
    readings.mkdir()
    (readings / "readings.json").write_text(json.dumps(
        {"meta": {"target": "Veyra", "target_aliases": ["Veyra"],
                  "brands": [{"name": "Veyra", "aliases": ["Veyra"]},
                             {"name": "Lumo", "aliases": ["Lumo"]}]},
         "questions": QUESTIONS}, ensure_ascii=False), encoding="utf-8")
    for name, raw in RAW.items():
        (readings / name).write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    # answers.jsonl 的 file 字段用绝对路径，脚本才能读回原始采集 json
    for answer in ANSWERS:
        answer["file"] = str(readings / answer["file"])
    (readings / "answers.jsonl").write_text(
        "\n".join(json.dumps(a, ensure_ascii=False) for a in ANSWERS) + "\n", encoding="utf-8")
    pagegap = tmp / "pagegap"
    pagegap.mkdir()
    (pagegap / "page_gap.csv").write_text(PAGE_GAP_CSV, encoding="utf-8")
    change = tmp / "changeability.csv"
    change.write_text(CHANGEABILITY_CSV, encoding="utf-8")
    return readings


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        readings = build(tmp)

        # 1) 不传 pagegap / changeability
        bare_out = tmp / "out-bare"
        bare = run(["--readings", readings, "--target-pattern", "veyra", "--out", bare_out])
        check("不传可选参数时正常退出", bare.returncode == 0, bare.stderr)
        bare_data = {}
        if bare.returncode == 0:
            bare_data = json.loads((bare_out / "materials.json").read_text(encoding="utf-8"))
        topics = bare_data.get("by_topic") or {}
        check("不传 pagegap/changeability 时不出对应字段", bool(topics) and all(
            not ({"page_gaps", "gap_pages", "changeability", "changeability_reasons"} & set(item))
            for item in topics.values()), json.dumps(topics, ensure_ascii=False)[:300])
        check("materials.md 有素材声明", bare.returncode == 0 and
              "这是写诊断的素材，不是对客结论" in (bare_out / "materials.md").read_text(encoding="utf-8"))

        # 2) 全参数
        full_out = tmp / "out-full"
        full = run(["--readings", readings, "--target-pattern", "veyra",
                    "--old-names", "SpeechOcean", "--pagegap", tmp / "pagegap",
                    "--changeability", tmp / "changeability.csv", "--out", full_out])
        check("全参数时正常退出", full.returncode == 0, full.stderr)
        data = json.loads((full_out / "materials.json").read_text(encoding="utf-8")) \
            if full.returncode == 0 else {}
        fan = data.get("fanout") or {}
        topic = (data.get("by_topic") or {}).get("语音数据") or {}

        # 检索词三种结构
        check("检索词字典式+列表式都读到、缺失字段跳过（total=6）", fan.get("total") == 6, fan.get("total"))
        check("per_answer 按回答数平均（6/4=1.5）", fan.get("per_answer") == 1.5, fan.get("per_answer"))
        check("年份从两种结构里都统计到", fan.get("years") == {"2025": 1, "2026": 2}, fan.get("years"))

        # 新增限定词
        added = {w for w, _n in fan.get("added_terms") or []}
        check("题面已有的词不算新增（speech/data/providers 不在）",
              not ({"speech", "data", "providers"} & added), sorted(added))
        check("题面外的英文词进入新增（pricing/vendors）",
              {"pricing", "vendors"} <= added, sorted(added))
        check("推荐类与其他的新增词分组", bool(fan.get("added_terms_recommend")) and
              bool(fan.get("added_terms_other")), fan.get("added_terms_recommend"))

        # 原句清洗
        sentences = [s["sentence"] for s in data.get("target_sentences") or []]
        joined = "\n".join(sentences)
        check("脚注行不进原句", "[1]:" not in joined and "SpeechOcean speech data collection services" not in joined,
              joined)
        check("img 标签不进原句", "<img" not in joined and "alt=" not in joined, joined)
        check("正文里含品牌的原句留下", any("Veyra provides speech data collection" in s for s in sentences),
              sentences)
        check("过短的句子被过滤", all(len(s) >= 40 for s in sentences))
        check("同一句去重", len(sentences) == len(set(sentences)))

        # 旧名命中
        hits = fan.get("old_name_hits") or []
        check("旧名命中两处", len(hits) == 2, hits)
        by_qid = {h["question_id"]: h for h in hits}
        check("旧名命中且回答没提品牌时 target_in_answer=False",
              by_qid.get("T-01", {}).get("target_in_answer") is False, by_qid.get("T-01"))
        check("旧名命中且回答提了品牌时 target_in_answer=True",
              by_qid.get("T-02", {}).get("target_in_answer") is True, by_qid.get("T-02"))

        # 主题读数与页面
        check("主题读数按回答累加", topic.get("answers") == 4 and topic.get("target_mentioned") == 2
              and topic.get("official_retrieved") == 1 and topic.get("official_cited") == 1,
              {k: topic.get(k) for k in ("answers", "target_mentioned", "official_retrieved", "official_cited")})
        check("主题类型取最常见", topic.get("prompt_type") == "discovery", topic.get("prompt_type"))
        check("竞品页面按被引次数累计", topic.get("top_competitor_pages") == [["https://comp.example/a", 2]],
              topic.get("top_competitor_pages"))
        check("页面缺口分布", topic.get("page_gaps") == {"页面缺口": 1, "答案缺口": 0, "无": 1, "未知": 0},
              topic.get("page_gaps"))
        check("缺口页带被引次数与竞品数", topic.get("gap_pages") == [["https://comp.example/a", 2, 4]],
              topic.get("gap_pages"))
        check("可改变性计数，空 suggested 记不适用",
              topic.get("changeability") == {"高": 1, "中": 0, "低": 0, "不适用": 1},
              topic.get("changeability"))
        check("原因取冒号前前缀",
              topic.get("changeability_reasons") == [["高（官网差距）", 1]],
              topic.get("changeability_reasons"))

        # 推荐类检索词里的品牌
        brands = dict(fan.get("brands_in_recommend_fanouts") or [])
        check("推荐类检索词里的品牌统计", brands.get("Veyra") == 1, brands)

    passed = sum(1 for _n, ok, _d in results if ok)
    failed = len(results) - passed
    print(f"\n{passed} PASS / {failed} FAIL / {len(results)} 项")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
