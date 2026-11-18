"""多轮采集的文件归属：0001-r2.json 不能因为没剥 -rN 被丢掉。

2026-11-17 某项目双平台实测：AIO 不回传题面，回退按文件名对题号时没剥 ``-r2``，
第 2、3 次运行整批被当成 UNMATCHED 丢掉，AIO 分母从 90 掉到 30，报告与独立复算同时失真。
"""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_report_data.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_report_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_report_data"] = module
    spec.loader.exec_module(module)
    return module


def _write(folder: Path, name: str):
    payload = {"status": "success", "task_result": {"answer": f"answer {name}"}}
    (folder / name).write_text(json.dumps(payload), encoding="utf-8")


def test_repeat_runs_without_prompt_are_grouped(tmp_path):
    module = _load()
    folder = tmp_path / "US"
    folder.mkdir()
    for name in ("0001.json", "0001-r2.json", "0001-r3.json"):
        _write(folder, name)

    questions = [{"question_id": "0001", "question_text": "What is the best AI detector?"}]
    files, issues = module.discover_sample_files(folder, questions)

    assert len(files) == 3, f"三轮都应归属到同一题，实际 {len(files)} 条"
    assert {item[2] for item in files} == {1, 2, 3}, "重复序号应按 -rN 排"
    assert not [i for i in issues if i.get("code") == "UNMATCHED_SAMPLE_FILE"]


def test_files_without_matching_question_still_reported(tmp_path):
    module = _load()
    folder = tmp_path / "US"
    folder.mkdir()
    _write(folder, "0099.json")

    questions = [{"question_id": "0001", "question_text": "What is the best AI detector?"}]
    files, issues = module.discover_sample_files(folder, questions)

    assert files == []
    assert [i for i in issues if i.get("code") == "UNMATCHED_SAMPLE_FILE"]
