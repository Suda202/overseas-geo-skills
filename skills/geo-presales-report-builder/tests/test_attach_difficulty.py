"""attach_difficulty.py：难度接进报告后，对客说法不出内部用语、已常被推荐的题不留空也不说达标。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "attach_difficulty.py"
INTERNAL = ("达标", "守住", "轮换位", "固定竞品", "可改变性", "same_category", "预判")


def _prompt(qid, text, comp, opt, code, **detail):
    base = {"slots": 3, "fixed": [], "free": 3, "named_any": 1.0, "target_rate": 0.0, "leader": "Lumo",
            "change_step": "", "change_attr": ""}
    base.update(detail)
    base["opt_code"] = code
    return {"question_id": qid, "question": text, "n": 7, "竞争难度": comp, "优化难度": opt, "预判": "", "detail": base}


def _run(tmp: Path, prompts, topics):
    report = {"meta": {"brand": "Veyra", "questions": [
        {"qid": i + 1, "en": p["question"], "topic": "露营充电"} for i, p in enumerate(prompts)]}}
    (tmp / "r.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (tmp / "d.json").write_text(json.dumps({"prompts": prompts, "topics": topics}, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, "-I", str(SCRIPT), "--report", str(tmp / "r.json"), "--difficulty",
                    str(tmp / "d.json"), "--out", str(tmp / "o.json")], check=True, capture_output=True)
    return json.loads((tmp / "o.json").read_text(encoding="utf-8"))["difficulty"]


def test_copy_is_plain_and_achieved_is_low(tmp_path):
    prompts = [
        _prompt("Q1", "best camping solar charger", "高", "高", "comp_high", fixed=["Lumo", "Nexo"], free=1),
        _prompt("Q2", "solar charger for van life", "中", "已达标", "achieved", target_rate=0.86),
        _prompt("Q3", "cheap solar charger", "低", "低", "in_pool", target_rate=0.29),
        _prompt("Q4", "is Veyra reliable", "不适用", "不适用", ""),
        _prompt("Q5", "how to size a solar panel", "不判", "不判", "not_judged", named_any=0.05),
    ]
    topics = [{"topic": "t1", "竞争难度": "中", "detail": {"pattern": "多家固定", "fixed": ["Lumo", "Nexo"],
                                                          "question_ids": ["Q1", "Q2", "Q3", "Q4", "Q5"]}}]
    d = _run(tmp_path, prompts, topics)
    p = d["prompts"]
    assert "4" not in p, "点名题不评估"
    assert p["2"]["opt"] == "低" and "常推荐" in p["2"]["opt_text"], "已常被推荐的题记低，不留空"
    assert p["5"]["comp"] == "" and p["5"]["opt"] == "", "不点品牌的题暂不评估"
    assert "Lumo 和 Nexo 几乎每次都在" in p["1"]["comp_text"], "中英混排留空格"
    assert d["topics"][0]["topic"] == "露营充电", "主题名取报告里的名字"
    assert d["topics"][0]["first"] == [3], "建议先做只放已进候选、还没常被推荐的题"
    assert p["1"]["opt_reason"] == "推荐名单被固定的几家占满", "优化难度要给原因"
    assert p["3"]["opt_reason"] == "已在 AI 的候选名单里"
    assert "Lumo 和 Nexo 等固定占满（1 道）" in d["topics"][0]["opt_text"], "主题按原因归类计数"
    text = json.dumps(d, ensure_ascii=False)
    for word in INTERNAL:
        assert word not in text, f"对客说法里出现了内部用语「{word}」"
