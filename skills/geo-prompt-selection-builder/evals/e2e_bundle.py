#!/usr/bin/env python3
"""部署包端到端校验（3.15.0）。

线上只部署 `run_selection_mode.py bundle` 打出来的目录。选词运行要用到别的 skill 的文件（shared 整个目录；
研究预跑的 geo-monitoring 采集程序、采集检查、平台合同；采集程序导入的 geo-metrics geo_presales_core），
源文件各在各的 skill 里，bundle 原样拷出同样的目录结构。验证：

  1. 打包：退出码 0，BUNDLE.json 记录的内容和 runner 的清单一致，清单里的文件都在
  2. 包里不带快照、缓存和 lark-cli 落下的 Base 导出
  3. 目标目录已存在 → 退出码 2，不覆盖
  4. 从包里跑 prepare：工作目录里有采集程序，collect_answers.py --dry-run 能跑（不调付费接口）
  5. 从包里跑返修循环 e2e：整条 run（假 agent）在包里跑得通
  6. 包里缺 geo-monitoring 或 shared → prepare 退出码 2，result.json 写 missing_skill_files 和缺的路径

产物：reports/bundle-e2e.md；临时目录跑完删除。

    python3 evals/e2e_bundle.py
退出码 0 表示全部符合预期。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RUNNER = SKILL / "scripts" / "run_selection_mode.py"
CASE_REL = Path("references/input-examples/b2c-example.json")
ROOT = Path(tempfile.mkdtemp(prefix="sel-bundle-e2e-"))
rows: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    rows.append((name, bool(ok), detail))


def run(cmd: list, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd)


sys.path.insert(0, str(SKILL / "scripts"))
import run_selection_mode as runner  # noqa: E402

expected = [f"{n}/{r}".rstrip("/") for n, r in runner.runtime_files()]

# 1. 打包
pkg = ROOT / "bundle"
p = run([sys.executable, "-I", RUNNER, "bundle", "--out", pkg])
manifest = json.loads((pkg / "BUNDLE.json").read_text(encoding="utf-8")) if (pkg / "BUNDLE.json").exists() else {}
missing = runner.missing_sources(pkg)
check("打包成功，BUNDLE.json 内容和 runner 清单一致、文件都在",
      p.returncode == 0 and manifest.get("contents") == expected and not missing,
      f"exit={p.returncode} contents={manifest.get('contents')} missing={missing}")

# 2. 不带快照、缓存、客户数据
junk = [str(f.relative_to(pkg)) for f in pkg.rglob("*")
        if f.name in (".snapshots", "__pycache__", ".pytest_cache") or f.suffix == ".bak"
        or (f.name.startswith("tbl") and f.name.endswith(".ndjson"))]
check("包里没有快照、缓存和 Base 导出", not junk, f"命中 {junk[:5]}")

# 3. 已存在不覆盖
p = run([sys.executable, "-I", RUNNER, "bundle", "--out", pkg])
check("目标目录已存在 → 退出码 2", p.returncode == 2, f"exit={p.returncode}")

# 4. 从包里 prepare，工作目录里的采集程序能 dry-run
prunner = pkg / SKILL.name / "scripts" / "run_selection_mode.py"
case = pkg / SKILL.name / CASE_REL
ws = ROOT / "ws"
p = run([sys.executable, "-I", prunner, "prepare", "--case", case, "--market", "US", "--platforms", "chatgpt",
         "--out", ws])
collector = ws / ".agents/skills/geo-monitoring/scripts/collect_answers.py"
qcsv = ROOT / "q.csv"
qcsv.write_text("query,question_zh,topic,diagnosis_intent,tags\nbest robot vacuum for pet hair,测试,测试,Discovery,\n",
                encoding="utf-8")
d = run([sys.executable, "-I", collector, "--questions", qcsv, "--out", ws / "pre", "--regions", "US",
         "--platforms", "chatgpt", "--dry-run"]) if collector.exists() else None
check("从包里 prepare，工作目录的 collect_answers.py --dry-run 能跑",
      p.returncode == 0 and d is not None and d.returncode == 0,
      f"prepare exit={p.returncode} dry-run exit={d.returncode if d else '无采集程序'} {(d.stdout.strip().splitlines()[-1] if d and d.stdout.strip() else '')}")

# 5. 整条 run 在包里跑得通（借返修循环 e2e 的假 agent）
p = run([sys.executable, pkg / SKILL.name / "evals" / "e2e_repair_loop.py"])
check("包里跑返修循环 e2e（假 agent 走完整条 run）", p.returncode == 0,
      f"exit={p.returncode} {next((x for x in p.stdout.splitlines() if x.startswith('- 结果')), p.stderr[-200:])}")

# 6. 缺文件启动即停
for drop, want in (("geo-monitoring", "geo-monitoring/scripts/collect_answers.py"), ("shared", "shared")):
    broken = ROOT / f"broken-{drop}"
    shutil.copytree(pkg, broken)
    shutil.rmtree(broken / drop)
    bws = ROOT / f"ws-{drop}"
    p = run([sys.executable, "-I", broken / SKILL.name / "scripts/run_selection_mode.py", "prepare",
             "--case", broken / SKILL.name / CASE_REL, "--market", "US", "--platforms", "chatgpt", "--out", bws])
    res = json.loads((bws / "out/result.json").read_text(encoding="utf-8")) if (bws / "out/result.json").exists() else {}
    err = (res.get("errors") or [{}])[0]
    check(f"包里缺 {drop} → 退出码 2，missing_skill_files 列出缺的文件，不拷 skill",
          p.returncode == 2 and err.get("code") == "missing_skill_files" and want in err.get("files", [])
          and not (bws / ".agents").exists(),
          f"exit={p.returncode} code={err.get('code')} files={err.get('files')}")

passed = sum(1 for _, ok, _ in rows if ok)
lines = ["# 部署包端到端校验", "", f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
         "- 命令：`python3 evals/e2e_bundle.py`", f"- 结果：{passed}/{len(rows)} 通过", "",
         "| 检查 | 结果 | 说明 |", "|---|---|---|"]
lines += [f"| {n} | {'通过' if ok else '失败'} | {d.replace('|', '/').replace(chr(10), ' ')} |" for n, ok, d in rows]
(SKILL / "reports").mkdir(exist_ok=True)
(SKILL / "reports" / "bundle-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
shutil.rmtree(ROOT, ignore_errors=True)
sys.exit(0 if passed == len(rows) else 1)
