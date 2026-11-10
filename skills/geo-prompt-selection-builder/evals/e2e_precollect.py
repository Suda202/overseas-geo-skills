#!/usr/bin/env python3
"""precollect 与登记检查端到端校验（3.4.0，2026-11-10）。

用假 agent（--agent-cmd）走 run_selection_mode.py 的 run 子命令；三个采集脚本换成假脚本
（PRECOLLECT_SCRIPTS_DIR 指向临时目录里同名的 collect_serp_signals.py、collect_reviews.py、net.py），
它们按真脚本的参数接收调用、按真脚本的产物格式写 signals.csv / 打印 Reddit 文本，不联网、不花钱。
验证：

  0. TASK 模板：prepare 写出的 TASK.md 指向 research/precollect/signals.csv，旧的「只登记撑起某道题的那几条」已删
  1. 三类都采到、agent 三类都登记 → success，不报登记错误，没有 REPAIR-1.md；summary.json 三类 ok、
     合并表带「采集类别」列；种子词、gl/hl、竞品域名（去掉 https://、www.）、Reddit 次数（≤5）和
     --limit 15/40 按约定传给脚本；Reddit 文本解析出帖子和评论，AutoModerator 不收、出处带完整 URL
  2. 评价采到 5 条、agent 一条没登记、notes 没说明 → 首轮报 [precollect] 登记错误，进 REPAIR-1，
     返修补登记后 success，repair_rounds=1
  3. 同 2，但 notes.md「未覆盖来源」写了评价与本产品线无关 → 不报，首轮 success
  4. 评价类缺凭据 → summary 里评价 status=failed 带原因，不检查评价，其他两类照常 → success
  5. 每轮都不登记评价 → 最后一轮只记 warning，不删题（题数不变、config.retired 没新增）→ success

产物：reports/precollect-e2e.md；工作目录建在系统临时目录，跑完删除。

    python3 evals/e2e_precollect.py
退出码 0 表示全部符合预期。
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RUNNER = SKILL / "scripts" / "run_selection_mode.py"
FIXTURE = SKILL / "evals" / "fixtures" / "online-sample-bank.json"
# 自带中性品牌资料：不依赖 references/input-examples 里的客户样例（发布仓库会把它们换成别的名字）
CASE_PAYLOAD = {
    "input_version": "presales-case-input/v2",
    "case": {
        "品牌": "Brandx",
        "官方域名": "https://brandx.example",
        "产品线": "Streaming platform: Asian drama library with English subtitles",
        "竞品": [{"名称": "RivalOne", "官网域名": "https://www.rival-one.example"},
                 {"名称": "RivalTwo", "官网域名": "https://rival-two.example/en"},
                 {"名称": "RivalThree", "官网域名": "http://rival-three.example/"}],
        "核心目标客户与购买场景": ["海外华人观众：想看带英文字幕的亚洲剧"],
    },
    "options": {"locale": "en"},
}
FIXTURE_COUNT = len(json.loads(FIXTURE.read_text(encoding="utf-8"))["questions"])
FIXTURE_RETIRED = len(json.loads(FIXTURE.read_text(encoding="utf-8"))["config"].get("retired") or [])

COMMON = r'''
import csv, json, os, sys
from pathlib import Path
FIELDS = ["输入编号", "产品线", "来源类型", "月搜索量", "原话", "译文", "目标客户", "约束条件", "出处", "引用它的问题"]


def log(name):
    with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"script": name, "argv": sys.argv[1:], "who": os.environ.get("DATAFORSEO_WHO", ""),
                            "reddit_max": os.environ.get("NET_REDDIT_MAX", "")}, ensure_ascii=False) + "\n")


def opt(name, default=""):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def write_rows(out, rows):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "signals.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
'''

FAKE_SERP = COMMON + r'''
log("collect_serp_signals.py")
seeds = [s.strip() for s in Path(opt("--seeds-file")).read_text(encoding="utf-8").splitlines() if s.strip()]
rows = []
for seed in seeds:
    for q in (f"is {seed} worth it", f"what is the cheapest {seed}"):
        r = dict.fromkeys(FIELDS, "")
        r.update({"产品线": opt("--product-line"), "来源类型": "搜索联想", "原话": q,
                  "出处": f"Google People Also Ask｜种子词：{seed}｜gl={opt('--gl')} hl={opt('--hl')}｜2026-11-10｜"
                          f"https://www.google.com/search?q={seed.replace(' ', '+')}"})
        rows.append(r)
for i, r in enumerate(rows, 1):
    r["输入编号"] = f"{opt('--id-prefix', 'S')}{i:03d}"
write_rows(opt("--out"), rows)
Path(opt("--out"), "summary.json").write_text(json.dumps({"failed_seeds": []}), encoding="utf-8")
print(f"去重后 {len(rows)} 条信号")
'''

FAKE_REVIEWS = COMMON + r'''
log("collect_reviews.py")
if os.environ.get("FAKE_REVIEWS") == "nocreds":
    print("停止：缺少 DataForSEO 凭据：设环境变量 DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD，或存进钥匙串（服务名同名）",
          file=sys.stderr)
    sys.exit(2)
targets = []
for i, x in enumerate(sys.argv[2:]):
    if x.startswith("--"):
        break
    targets.append(x)
rows = []
for n in range(5):
    d = targets[n % len(targets)]
    r = dict.fromkeys(FIELDS, "")
    r.update({"产品线": opt("--product-line"), "来源类型": "评价", "原话": f"Review {n} of {d}: subtitles were late again",
              "出处": f"Trustpilot｜{d}｜2 星｜2026-10-0{n + 1}｜https://www.trustpilot.com/reviews/{d}-{n}"})
    rows.append(r)
for i, r in enumerate(rows, 1):
    r["输入编号"] = f"{opt('--id-prefix', 'R')}{i:03d}"
write_rows(opt("--out"), rows)
Path(opt("--out"), "summary.json").write_text(json.dumps({"failed": []}), encoding="utf-8")
print(f"{len(rows)} 条评价")
'''

FAKE_NET = COMMON + r'''
log("net.py")
cmd, arg = sys.argv[1], sys.argv[2]
assert cmd == "reddit", cmd
if arg.startswith("http"):
    base = arg.rstrip("/")
    print(f"[来源] {base}/.rss?limit=100 —— Reddit RSS 直连，5 条（第 1 条是帖子，其余是评论，扁平无楼层/点赞）\n")
    print(f"1. [帖子] Thread title for {base.split('/')[-1]}\n   /u/op · 2026-10-01 · {base}/\n"
          f"   I want a streaming platform with good English subtitles for C-dramas.\n"
          f"Second paragraph of the post. submitted by /u/op to r/CDrama\n")
    print(f"2. [评论] \n   /u/AutoModerator · 2026-10-01 · {base}/c0/\n   Please read the rules.\n")
    for n in range(1, 4):
        print(f"{n + 2}. [评论] \n   /u/user{n} · 2026-10-0{n + 1} · {base}/c{n}/\n"
              f"   Comment {n} on {base.split('/')[-1]}: RivalThree has the best fan subs.\n")
else:
    print(f"[来源] https://www.reddit.com/search.rss?q={arg} —— Reddit RSS 直连，4 条\n")
    posts = [("Best streaming platform for Chinese dramas?", "CDrama", "aaa111", "Looking for a streaming platform."),
             ("RivalOne vs RivalTwo for asian dramas", "CDrama", "bbb222", "Which one has faster subtitles?"),
             ("Rams kicker news", "nfl", "ccc333", "submitted by /u/x to r/nfl")]
    for i, (title, sub, pid, body) in enumerate(posts, 1):
        print(f"{i}. [帖子] {title}\n   /u/p{i} · 2026-10-1{i} · https://www.reddit.com/r/{sub}/comments/{pid}/slug_{pid}/\n   {body}\n")
    print("4. [版块] Subreddit CDrama\n   /u/mod · 2015-01-01 · https://www.reddit.com/r/CDrama/\n   About.\n")
'''

FAKE_AGENT = r'''
import csv, json, os
from pathlib import Path

ws = Path(os.environ["WORKSPACE"])
task = Path(os.environ["TASK_FILE"]).name
mode = os.environ["FAKE_MODE"]
bank = json.loads(Path(os.environ["FIXTURE"]).read_text(encoding="utf-8"))
with (ws / "research/precollect/signals.csv").open(encoding="utf-8-sig", newline="") as f:
    signals = list(csv.DictReader(f))


def quotes(cats):
    out = []
    for n, cat in enumerate(cats, 1):
        row = next(r for r in signals if r["采集类别"] == cat)
        out.append({"输入编号": f"US-R9{n:02d}", "来源类型": row["来源类型"], "原话": row["原话"], "目标客户": "",
                    "约束条件": "", "出处": row["出处"].rsplit("｜", 1)[-1].split("，")[-1]})
    return out


cats = ["搜索联想", "评价", "社区"] if mode == "all" else ["搜索联想", "社区"]
if mode == "fix" and task.startswith("REPAIR-"):
    cats = ["搜索联想", "评价", "社区"]  # 返修：把评价补登记进去
bank["config"]["buyer_quotes"] = list(bank["config"].get("buyer_quotes") or []) + quotes(cats)
(ws / "out/bank.json").write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
notes = "# 生成记录\n\n## 需求信号\n\n登记了 precollect 信号。\n\n## 未覆盖来源\n\n"
if mode == "explain":
    notes += "- 评价：Trustpilot 上的竞品评价都是 B2C 退款纠纷，与本产品线无关\n"
elif mode == "nocreds":
    notes += "- 评价：precollect 失败，缺少 DataForSEO 凭据\n"
else:
    notes += "- 无\n"
notes += "\n## 假设\n\n- 无\n"
(ws / "out/notes.md").write_text(notes, encoding="utf-8")
'''

rows: list[tuple[str, bool, str]] = []
WS_ROOT = Path(tempfile.mkdtemp(prefix="precollect-e2e-"))
CASE = WS_ROOT / "case.json"
CASE.write_text(json.dumps(CASE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
STUBS = WS_ROOT / "stubs"
STUBS.mkdir()
for name, body in (("collect_serp_signals.py", FAKE_SERP), ("collect_reviews.py", FAKE_REVIEWS), ("net.py", FAKE_NET)):
    (STUBS / name).write_text(body, encoding="utf-8")
fake = WS_ROOT / "fake_agent.py"
fake.write_text(FAKE_AGENT, encoding="utf-8")
dummy_task = WS_ROOT / "dummy-task.md"
dummy_task.write_text("测试任务：由假 agent 执行，内容不读。\n", encoding="utf-8")


def check(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))


def run_case(name: str, mode: str, reviews: str = "ok", repair_rounds: int = 2) -> tuple[int, dict, Path, list[dict]]:
    ws = WS_ROOT / f"ws-{name}"
    log = WS_ROOT / f"calls-{name}.jsonl"
    env = {k: v for k, v in os.environ.items() if k not in ("NET_REDDIT_MAX", "DATAFORSEO_WHO")}
    env.update(FAKE_MODE=mode, FIXTURE=str(FIXTURE), FAKE_LOG=str(log), FAKE_REVIEWS=reviews,
               PRECOLLECT_SCRIPTS_DIR=str(STUBS))
    cmd = [sys.executable, "-I", str(RUNNER), "run", "--case", str(CASE), "--market", "US",
           "--platforms", "chatgpt", "--out", str(ws), "--task-file", str(dummy_task),
           "--repair-rounds", str(repair_rounds), "--review-rounds", "0",
           "--agent-cmd", f'"{sys.executable}" -I "{fake}"']
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    path = ws / "out/result.json"
    result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"_stderr": proc.stderr[-800:]}
    calls = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return proc.returncode, result, ws, calls


def summary(ws: Path) -> dict:
    return json.loads((ws / "research/precollect/summary.json").read_text(encoding="utf-8"))


def stages(res: dict) -> list[str]:
    return [e.get("stage") for e in res.get("errors", [])]


# 0. TASK 模板
ws0 = WS_ROOT / "ws-prepare"
subprocess.run([sys.executable, "-I", str(RUNNER), "prepare", "--case", str(CASE), "--market", "US",
                "--platforms", "chatgpt", "--out", str(ws0)], capture_output=True, text=True)
task_text = (ws0 / "TASK.md").read_text(encoding="utf-8") if (ws0 / "TASK.md").exists() else ""
check("TASK 模板：指向 precollect 合并表、要求照抄来源类型和完整 URL、删掉「只登记撑起某道题」",
      "research/precollect/signals.csv" in task_text and "\"来源类型\"" in task_text and "同上帖" in task_text
      and "未覆盖来源" in task_text and "只登记撑起某道题的那几条" not in task_text
      and "撑不起任何题的也可以登记" in task_text,
      f"TASK.md {len(task_text)} 字")

# 1. 三类都采到、都登记
rc, res, ws, calls = run_case("all", "all")
s = summary(ws)
cats = s.get("categories", {})
check("1 三类都登记：success，无登记错误，不返修",
      rc == 0 and res.get("status") == "success" and "precollect" not in stages(res)
      and not (ws / "REPAIR-1.md").exists()
      and not any("[precollect]" in w for w in res.get("warnings", [])),
      f"exit={rc} status={res.get('status')} stages={stages(res)}")
check("1 summary.json 三类 ok、行数、out_dir；result.json 带 precollect 块",
      all(cats.get(c, {}).get("status") == "ok" for c in ("搜索联想", "评价", "社区"))
      and cats["评价"]["rows"] == 5 and cats["搜索联想"]["rows"] == 4 and cats["社区"]["rows"] >= 1
      and cats["社区"]["out_dir"] == "research/precollect/community"
      and (res.get("precollect") or {}).get("categories", {}).get("评价", {}).get("rows") == 5,
      json.dumps({c: (v.get("status"), v.get("rows")) for c, v in cats.items()}, ensure_ascii=False))
with (ws / "research/precollect/signals.csv").open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    merged, header = list(reader), reader.fieldnames or []
check("1 合并表：原有列不变、末尾加「采集类别」、条数 = 三类行数之和",
      header[:10] == ["输入编号", "产品线", "来源类型", "月搜索量", "原话", "译文", "目标客户", "约束条件", "出处", "引用它的问题"]
      and header[-1] == "采集类别" and len(merged) == s.get("total_rows") == sum(v["rows"] for v in cats.values()),
      f"列={header} 行={len(merged)}")
serp = next((c for c in calls if c["script"] == "collect_serp_signals.py"), {})
seeds_file = ws / "research/precollect/serp/seeds.txt"
seeds = seeds_file.read_text(encoding="utf-8").split("\n") if seeds_file.exists() else []
argv = serp.get("argv", [])
check("1 搜索联想：种子词按品类推（去掉品牌词）、gl 小写市场、hl=locale",
      seeds[:2] == ["best streaming platform", "streaming platform recommendations"]
      and argv[argv.index("--gl") + 1] == "us" and argv[argv.index("--hl") + 1] == "en",
      f"seeds={seeds} argv={argv}")
rev = next((c for c in calls if c["script"] == "collect_reviews.py"), {})
rargv = rev.get("argv", [])
check("1 评价：trustpilot + 竞品域名去掉 https://、www.、--depth 40，DATAFORSEO_WHO 由 runner 设好",
      rargv[:4] == ["trustpilot", "rival-one.example", "rival-two.example", "rival-three.example"] and rargv[rargv.index("--depth") + 1] == "40"
      and rev.get("who") == "线上选词（未传调用人）",
      f"argv={rargv} who={rev.get('who')}")
reddit = [c["argv"] for c in calls if c["script"] == "net.py"]
searches = [a for a in reddit if not a[1].startswith("http")]
threads = [a for a in reddit if a[1].startswith("http")]
check("1 社区：Reddit ≤5 次（搜索 --limit 15、帖子 --limit 40），只读相关帖子不读无关帖",
      len(reddit) <= 5 and len(searches) in (1, 2) and all(a[-2:] == ["--limit", "15"] for a in searches)
      and all(a[-2:] == ["--limit", "40"] for a in threads) and len(threads) == 2
      and {a[1] for a in threads} == {"https://www.reddit.com/r/CDrama/comments/aaa111/slug_aaa111/",
                                      "https://www.reddit.com/r/CDrama/comments/bbb222/slug_bbb222/"},
      f"reddit 调用={reddit}")
comm = [r for r in merged if r["采集类别"] == "社区"]
check("1 社区：Reddit 文本解析成帖子+评论行，AutoModerator 不收，submitted by 去掉，出处带版块、日期、完整 URL",
      len(comm) == 8 and not any("Please read the rules" in r["原话"] for r in comm)
      and not any("submitted by" in r["原话"] for r in comm)
      and all(r["来源类型"] == "社区" and r["出处"].startswith("Reddit r/") and "，https://www.reddit.com/r/" in r["出处"]
              for r in comm)
      and any(r["原话"].startswith("Thread title for slug_aaa111\n") for r in comm),
      f"社区 {len(comm)} 行；首行 {comm[0]['出处'] if comm else ''}")

# 2. 评价没登记、没说明 → 报错进 REPAIR，返修补上
rc, res, ws, _ = run_case("missing", "fix")
repair = (ws / "REPAIR-1.md").read_text(encoding="utf-8") if (ws / "REPAIR-1.md").exists() else ""
check("2 评价未登记：首轮报 [precollect] 登记错误进 REPAIR-1，原文写清条数和两条出路",
      "[precollect] research/precollect/ 里已采到 评价 5 条，buyer_quotes 里一条没有" in repair
      and "research/precollect/signals.csv" in repair and "未覆盖来源" in repair
      and "搜索联想" not in repair.split("报错原文", 1)[-1].split("改完后", 1)[0],
      repair.split("报错原文：", 1)[-1][:200].replace("\n", " "))
check("2 返修补登记后 success，repair_rounds=1，没有第 2 轮",
      rc == 0 and res.get("status") == "success" and res.get("repair_rounds") == 1 and not (ws / "REPAIR-2.md").exists(),
      f"exit={rc} status={res.get('status')} rounds={res.get('repair_rounds')}")

# 3. notes.md「未覆盖来源」说明了评价与本产品线无关 → 不报
rc, res, ws, _ = run_case("explain", "explain")
check("3 未覆盖来源写了评价及理由 → 不报登记错误，首轮 success",
      rc == 0 and res.get("status") == "success" and res.get("repair_rounds") == 0
      and not (ws / "REPAIR-1.md").exists() and summary(ws)["categories"]["评价"]["status"] == "ok",
      f"exit={rc} status={res.get('status')} rounds={res.get('repair_rounds')}")

# 4. 评价缺凭据 → failed 带原因，不检查评价
rc, res, ws, _ = run_case("nocreds", "nocreds", reviews="nocreds")
c4 = summary(ws)["categories"]
check("4 评价缺凭据：status=failed 带原因、0 行，其他两类 ok",
      c4["评价"]["status"] == "failed" and "缺少 DataForSEO 凭据" in c4["评价"]["reason"] and c4["评价"]["rows"] == 0
      and c4["搜索联想"]["status"] == "ok" and c4["社区"]["status"] == "ok"
      and (res.get("precollect") or {}).get("categories", {}).get("评价", {}).get("status") == "failed",
      json.dumps(c4["评价"], ensure_ascii=False))
check("4 不检查失败的评价类 → 首轮 success，不返修",
      rc == 0 and res.get("status") == "success" and not (ws / "REPAIR-1.md").exists(),
      f"exit={rc} status={res.get('status')} stages={stages(res)}")

# 5. 每轮都不登记评价 → 最后一轮只记 warning、不删题、照常交付
rc, res, ws, _ = run_case("never", "never")
bank = json.loads((ws / "out/bank.json").read_text(encoding="utf-8"))
repair2 = (ws / "REPAIR-2.md").read_text(encoding="utf-8") if (ws / "REPAIR-2.md").exists() else ""
warns = [w for w in res.get("warnings", []) if w.startswith("[precollect]")]
check("5 最后一轮仍缺：success，只记 1 条 warning，题数不变、retired 没新增",
      rc == 0 and res.get("status") == "success" and res.get("repair_rounds") == 2 and len(warns) == 1
      and "评价" in warns[0] and res.get("prompt_count") == FIXTURE_COUNT
      and len(bank["config"].get("retired") or []) == FIXTURE_RETIRED and "precollect" not in stages(res),
      f"exit={rc} status={res.get('status')} rounds={res.get('repair_rounds')} count={res.get('prompt_count')} "
      f"warnings={warns}")
check("5 最后一轮任务里登记报错写明不要为它删题",
      "不要为这条删题" in repair2 and "丢题不丢库" in repair2, "")

passed = sum(1 for _, ok, _ in rows if ok)
lines = ["# precollect 与登记检查端到端校验", "", f"- 运行时间：{datetime.now():%Y-%m-%d %H:%M}",
         "- 命令：`python3 evals/e2e_precollect.py`", f"- 结果：{passed}/{len(rows)} 通过", "",
         "| 检查 | 结果 | 说明 |", "|---|---|---|"]
lines += [f"| {n} | {'通过' if ok else '失败'} | {d.replace(str(WS_ROOT), '<tmp>').replace('|', '/')} |"
          for n, ok, d in rows]
(SKILL / "reports").mkdir(exist_ok=True)
(SKILL / "reports" / "precollect-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
shutil.rmtree(WS_ROOT, ignore_errors=True)
sys.exit(0 if passed == len(rows) else 1)
