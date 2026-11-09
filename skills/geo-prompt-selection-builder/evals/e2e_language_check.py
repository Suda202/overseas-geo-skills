#!/usr/bin/env python3
"""End-to-end check of the Prompt language gate (lingua, 2026-11-09).

For each collection language, one bank is built from evals/fixtures/online-sample-bank.json with Prompts that are
written correctly, written in the wrong language, or mixed the way real buyers write. The real validator runs on
each bank; every Prompt's outcome (error / warning / pass) is compared with what it should be.

Writes evals/reports/language-check-<date>.json and exits 1 if any case is wrong.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_after_sales_set.py"
FIXTURE = ROOT / "evals" / "fixtures" / "online-sample-bank.json"

# (collection language, market, [(Prompt, expected outcome: "pass" | "error" | "not_error")])
# "not_error" = mixed wording real buyers use; a W32 warning is fine, an error is not.
CASES = [
    ("id", "Indonesia", [
        ("Robot vacuum mana yang paling bagus untuk apartemen kecil dengan kucing?", "pass"),
        ("Merek robot vakum apa yang terbaik untuk rumah dengan bulu hewan?", "pass"),
        ("Which robot vacuum is best for a small apartment with cats?", "error"),
        ("Robot vacuum yang best buat apartment kecil apa ya?", "not_error"),
    ]),
    ("ms", "Malaysia", [
        ("Robot vakum mana yang terbaik untuk rumah teres di Kuala Lumpur?", "pass"),
        ("Saya ada dua ekor kucing, robot vakum mana yang sesuai untuk kondo kecil?", "pass"),
        ("Which robot vacuum is best for a terrace house in Malaysia?", "error"),
    ]),
    ("vi", "Vietnam", [
        ("Nên mua robot hút bụi nào cho căn hộ nhỏ có nuôi mèo?", "pass"),
        ("Robot hút bụi lau nhà loại nào tốt cho nhà có trẻ nhỏ?", "pass"),
        ("Robot vakum mana yang paling bagus untuk apartemen kecil?", "error"),
        ("Which robot vacuum should I buy for a small flat with pets?", "error"),
    ]),
    ("sw", "Kenya", [
        ("Ni roboti gani bora ya kusafisha nyumba ndogo yenye paka?", "pass"),
        ("Nataka kununua robot vacuum kwa nyumba yangu, ipi ni nzuri zaidi?", "pass"),
        ("Which robot vacuum is best in Kenya under KSh 30,000?", "error"),
    ]),
    ("tl", "Philippines", [
        ("Anong robot vacuum ang pinakamaganda para sa maliit na condo na may pusa?", "pass"),
        ("Ano ang best na robot vacuum para sa condo na may dalawang pusa?", "not_error"),
        ("Which robot vacuum is best for a small condo with cats?", "error"),
    ]),
    ("es", "Spain", [
        ("¿Cuál es el mejor robot aspirador para un piso pequeño con gatos?", "pass"),
        ("Which robot vacuum is best for a small flat with cats?", "error"),
    ]),
    ("pt-BR", "Brazil", [
        ("Qual é o melhor robô aspirador para apartamento pequeno com gatos?", "pass"),
        ("¿Cuál es el mejor robot aspirador para un piso pequeño con gatos?", "error"),
    ]),
    ("tr", "Turkey", [
        ("Kedili küçük bir daire için en iyi robot süpürge hangisi?", "pass"),
        ("Which robot vacuum is best for a small apartment with cats?", "error"),
    ]),
    ("pl", "Poland", [
        ("Jaki robot sprzątający jest najlepszy do małego mieszkania z kotem?", "pass"),
        ("Which robot vacuum is best for a small apartment with a cat?", "error"),
    ]),
    ("Hindi", "India", [
        ("बिल्ली वाले छोटे फ्लैट के लिए सबसे अच्छा रोबोट वैक्यूम कौन सा है?", "pass"),
        ("Which robot vacuum is best for a small flat with a cat in India?", "error"),
    ]),
    ("th", "Thailand", [
        ("หุ่นยนต์ดูดฝุ่นยี่ห้อไหนดีที่สุดสำหรับคอนโดเล็กที่เลี้ยงแมว", "pass"),
        ("Which robot vacuum is best for a small condo with cats?", "error"),
    ]),
    ("en", "US", [
        ("Which robot vacuums are best for pet hair on carpet?", "pass"),
        ("Which robot vacuum is best in Kenya under KSh 30,000?", "pass"),
        # real English Prompts from client banks that lingua tops with German / Spanish (2026-11-06)
        ("Best fast charger for a Samsung tablet", "pass"),
        ("Best Type-C charger head for Android phones", "pass"),
        ("Where can I buy the XR-200 mirror dash cam in the US?", "pass"),
    ]),
]
# A language lingua does not know: the check is skipped with one W32 warning, never an error.
UNKNOWN = ("Klingon", "Qo'noS", "Which robot vacuum is best for a small apartment with cats?")


def build_bank(language: str, market: str, prompts: list[str]) -> dict:
    bank = json.loads(FIXTURE.read_text(encoding="utf-8"))
    template = bank["questions"][0]
    bank["config"]["collection_config"] = {"market": market, "language": language}
    bank["config"]["expected_total"] = len(prompts)
    questions = []
    for i, text in enumerate(prompts, 1):
        q = copy.deepcopy(template)
        q.update({"question_id": f"Q{i:02d}", "user_question": text, "monitoring_prompt": text, "region": market})
        questions.append(q)
    bank["questions"] = questions
    return bank


def run(bank: dict) -> str:
    """Validator output; a crash (no summary line) is raised, never read as "no language finding"."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(bank, handle, ensure_ascii=False)
    try:
        proc = subprocess.run([sys.executable, str(VALIDATOR), handle.name], text=True, capture_output=True)
        output = proc.stdout + proc.stderr
        if '"readiness"' not in output and "ERROR" not in output:
            raise RuntimeError(f"validator did not finish:\n{output}")
        if "Traceback" in output:
            raise RuntimeError(f"validator crashed:\n{output}")
        return output
    finally:
        Path(handle.name).unlink()


def language_outcome(output: str, qid: str) -> tuple[str, list[str]]:
    lines = [line for line in output.splitlines() if f"{qid}:" in line
             and ("collection language" in line or "reads more like" in line)]
    if any(not line.startswith("WARNING") for line in lines):
        return "error", lines
    return ("warning" if lines else "pass"), lines


def main() -> int:
    results, wrong = [], 0
    for language, market, items in CASES:
        output = run(build_bank(language, market, [text for text, _ in items]))
        for i, (text, expected) in enumerate(items, 1):
            got, lines = language_outcome(output, f"Q{i:02d}")
            ok = got == expected if expected != "not_error" else got != "error"
            wrong += not ok
            results.append({"language": language, "prompt": text, "expected": expected, "got": got,
                            "ok": ok, "validator_lines": lines})
            print(f"{'OK ' if ok else 'BAD'} [{language}] expected={expected:9} got={got:7} {text}")
    output = run(build_bank(UNKNOWN[0], UNKNOWN[1], [UNKNOWN[2]]))
    skipped = "language check skipped" in output and "reads as" not in output
    wrong += not skipped
    results.append({"language": UNKNOWN[0], "prompt": UNKNOWN[2], "expected": "skipped with W32", "ok": skipped,
                    "validator_lines": [l for l in output.splitlines() if "language check skipped" in l]})
    print(f"{'OK ' if skipped else 'BAD'} [{UNKNOWN[0]}] expected=skipped   {UNKNOWN[2]}")

    out = ROOT / "evals" / "reports" / f"language-check-{dt.date.today():%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"validator": str(VALIDATOR.relative_to(ROOT)), "cases": len(results), "wrong": wrong,
                               "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(results) - wrong}/{len(results)} correct -> {out.relative_to(ROOT)}")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
