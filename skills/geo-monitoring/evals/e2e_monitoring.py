"""geo-monitoring 端到端自检：不联网、不花钱。

它防的失败方式（先列，再写用例）：
F1 平台登记表里有、平台合同里没有：--platforms all 一跑就被 D7 拦下，整批采不了
F2 平台合同里有、登记表里没有：采得到，报告链路不认（2026-11-27 Bing AI Mode 实例）
F3 --platforms all 没覆盖登记表全部平台
F4 --dry-run 报的待采格数算错（题数 × 平台 × 区域），付费调用量被低估
F5 已有效的格被当成待采，重跑同一命令重复付费
F6 --check-only 有缺格时不返回 3，驾驶脚本以为采齐了
F7 采集完整性检查对未登记平台不阻断（应退出码 2，UNKNOWN_PLATFORM_CONTRACT）
F8 采集完整性检查把干净目录判成有缺陷（误报会卡住整条流水线）
F9 失败答案（空正文）没被判成阻断缺陷，空答案进分母

报告写到 reports/monitoring-e2e.md，可复跑。
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
CORE = SKILL.parent / "geo-metrics" / "scripts"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))

from geo_presales_core.platforms import ALL_PLATFORM_DIRS, ANSWER_FIELDS, CITATION_FIELDS  # noqa: E402
import audit_crawl_integrity as integrity  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("✓ " if ok else "✗ ") + name + (f"：{detail}" if detail and not ok else ""))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "SCRAPELESS_API_KEY": ""})


def write_questions(path: Path, n: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["query", "question_zh", "topic", "diagnosis_intent", "tags"])
        for i in range(1, n + 1):
            w.writerow([f"best matcha supplier number {i} for cafes", f"题{i}", "主题A", "discovery", ""])


def good_answer(platform: str, query: str) -> dict:
    body = "Acme Matcha is a strong pick for cafes. ([Acme][1])"
    tr = {"prompt": query, ANSWER_FIELDS[platform]: body}
    field = CITATION_FIELDS.get(platform)
    if field:
        tr[field] = [{"url": "https://acme.example/matcha", "title": "Acme", "index": 1, "cited_count": 1}]
    return {"status": "success", "task_result": tr}


def main() -> int:
    contract = integrity.load_platform_contract()

    # F1 / F2：登记表和合同互相覆盖
    missing_contract = [p for p in ALL_PLATFORM_DIRS if p not in contract]
    check("F1 登记表里的平台都有字段合同", not missing_contract, f"缺合同 {missing_contract}")
    extra_contract = [p for p in contract if p not in ALL_PLATFORM_DIRS]
    check("F2 字段合同里的平台都在登记表", not extra_contract, f"登记表缺 {extra_contract}")

    # F3：--platforms all
    import collect_answers as ca  # noqa: E402
    check("F3 --platforms all 覆盖登记表全部平台", ca.ALL_PLATFORMS.split(",") == ALL_PLATFORM_DIRS,
          ca.ALL_PLATFORMS)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        qcsv = tmp / "q.csv"
        write_questions(qcsv, 3)
        out = tmp / "collect"

        # F4：dry-run 调用量 = 3 题 × 9 平台 × 2 区域
        r = run([str(SCRIPTS / "collect_answers.py"), "--questions", str(qcsv), "--out", str(out),
                 "--regions", "US,GB", "--platforms", "all", "--dry-run"])
        expect = 3 * len(ALL_PLATFORM_DIRS) * 2
        check("F4 dry-run 报对调用量", r.returncode == 0 and f"待采 {expect}" in r.stdout,
              (r.stdout + r.stderr)[-300:])

        # F5 / F6：造一部分有效格
        qs = [row["query"] for row in csv.DictReader(qcsv.open(encoding="utf-8"))]
        for platform in ("chatgpt", "bingaimode"):
            d = out / f"scraper.{platform}" / "US"
            d.mkdir(parents=True, exist_ok=True)
            for i, q in enumerate(qs, 1):
                (d / f"{i:04d}.json").write_text(json.dumps(good_answer(platform, q)), encoding="utf-8")
        r = run([str(SCRIPTS / "collect_answers.py"), "--questions", str(qcsv), "--out", str(out),
                 "--regions", "US", "--platforms", "chatgpt,bingaimode", "--check-only"])
        check("F5 已有效的格不重采", r.returncode == 0 and "待采 0" in r.stdout, (r.stdout + r.stderr)[-300:])
        r = run([str(SCRIPTS / "collect_answers.py"), "--questions", str(qcsv), "--out", str(out),
                 "--regions", "US", "--platforms", "chatgpt,bingaimode,gemini", "--check-only"])
        check("F6 --check-only 有缺格退出码 3", r.returncode == 3, f"退出码 {r.returncode}")

        # F8：干净目录过完整性检查
        integ = SCRIPTS / "audit_crawl_integrity.py"
        r = run([str(integ), "--collect-dir", str(out), "--target", "Acme", "--out", str(tmp / "i.json")])
        report = json.loads((tmp / "i.json").read_text(encoding="utf-8")) if (tmp / "i.json").exists() else {}
        defects = [c for c in report.get("defect_index", {}) if report.get("counts", {}).get("defects")]
        check("F8 干净目录不报阻断缺陷", r.returncode in (0, 1) and not defects,
              f"退出码 {r.returncode}，缺陷 {defects}")

        # F9：空正文
        bad = out / "scraper.chatgpt" / "US" / "0002.json"
        data = json.loads(bad.read_text(encoding="utf-8"))
        data["task_result"]["result_text"] = ""
        bad.write_text(json.dumps(data), encoding="utf-8")
        r = run([str(integ), "--collect-dir", str(out), "--target", "Acme", "--out", str(tmp / "i2.json")])
        check("F9 空正文判成阻断（退出码 2）", r.returncode == 2, f"退出码 {r.returncode}")

        # F7：未登记平台
        unk = out / "scraper.madeupai" / "US"
        unk.mkdir(parents=True)
        (unk / "0001.json").write_text(json.dumps({"status": "success", "task_result": {"result_text": "x"}}),
                                       encoding="utf-8")
        bad.write_text(json.dumps(good_answer("chatgpt", qs[1])), encoding="utf-8")
        r = run([str(integ), "--collect-dir", str(out), "--target", "Acme", "--out", str(tmp / "i3.json")])
        rep3 = json.loads((tmp / "i3.json").read_text(encoding="utf-8")) if (tmp / "i3.json").exists() else {}
        codes = list(rep3.get("defect_index", {}))
        check("F7 未登记平台阻断", r.returncode == 2 and "UNKNOWN_PLATFORM_CONTRACT" in codes,
              f"退出码 {r.returncode}，缺陷 {codes}")

    passed = sum(ok for _, ok, _ in RESULTS)
    lines = ["# geo-monitoring 端到端自检", "", f"{passed}/{len(RESULTS)} 通过（`python3 evals/e2e_monitoring.py` 复跑）", ""]
    lines += [f"- {'通过' if ok else '失败'}：{name}" + (f"（{d}）" if d and not ok else "") for name, ok, d in RESULTS]
    rp = SKILL / "reports" / "monitoring-e2e.md"
    rp.parent.mkdir(exist_ok=True)
    rp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{passed}/{len(RESULTS)} 通过；报告 {rp}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
