#!/usr/bin/env python3
"""precollect 与登记检查端到端校验（3.4.0，2026-11-10；3.5.0 加行业判断与按行业 × 市场选渠道，2026-11-11）。

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
  6. 开发者与云基础设施：评价走 Trustpilot + Capterra/TrustRadius 站内页（站名当关键词搜、网址要含竞品名），社区加 Hacker News；category_en 进种子词
  7. 内容与流媒体：评价只走 Google Play / App Store（带应用 ID、--country/--lang），不碰 Trustpilot；社区加 MyDramaList
  8. 行业写错两次 → 回喂 PLAN-REPAIR 一次，仍错退回默认渠道（竞品 Trustpilot + 市场社区），原因写进 plan-checked.json
  9. 泰国市场：社区换成 Pantip（net.py pantip 取帖子页评论，3.6.2 起不用无头 Chrome），不调 Reddit
 10. 想跳过表里的固定渠道 → check-plan 报错，返修后通过
 11. 只采到评价站页面、没拆成原话 → 登记报错写页面数和 pages/ 目录
 15. 行业写「其他」：AI 补渠道最多 5 个、渠道表外的站（add_sites）最多 2 个，超额被拒
 16. 其他实体消费品：评价走 Google Shopping 和 Trustpilot

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
sub = sys.argv[1]
targets = []
for i, x in enumerate(sys.argv[2:]):
    if x.startswith("--"):
        break
    targets.append(x)
rows = []
for n in range(5):
    d = targets[n % len(targets)]
    r = dict.fromkeys(FIELDS, "")
    r.update({"产品线": opt("--product-line"), "来源类型": "评价", "原话": f"{sub} review {n} of {d}: subtitles were late again",
              "出处": f"{sub}｜{d}｜2 星｜2026-10-0{n + 1}｜https://reviews.example/{sub}/{d}-{n}"})
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
LONG = "Buyer says: the onboarding took two weeks and support never answered. " * 12
if cmd == "search":
    if arg.startswith("reddit "):
        for i in range(1, int(os.environ.get("FAKE_SEARCH_THREADS", "3")) + 1):
            print(f"{i}. Thread {i} on r/CDrama\n   reddit.com（…）\n   链接：https://www.reddit.com/r/CDrama/comments/t{i:03d}/slug_t{i:03d}/\n   snippet\n")
        sys.exit(0)
    words = arg.split()
    site = words[0] + ".com"
    if site == "pantip.com":  # Pantip 只收帖子页（/topic/<数字>）
        print("1. A topic\n   pantip.com/topic（…）\n   链接：https://pantip.com/topic/40000001\n   snippet\n")
        print("2. A tag page\n   pantip.com/tag（…）\n   链接：https://pantip.com/tag/x\n   snippet\n")
        print("3. Another topic\n   pantip.com/topic（…）\n   链接：https://pantip.com/topic/40000002\n   snippet\n")
        sys.exit(0)
    slug = words[1].lower() if len(words) > 2 and words[-1] == "reviews" else "x"
    print(f"1. A page on {site}\n   {site}/x（Google 显示的网址路径，可能被截断；以打开后的页面为准）\n   链接：https://www.{site}/reviews/{slug}-p1\n   snippet\n")
    print(f"2. Off-site page\n   other.example（…）\n   链接：https://other.example/{site}\n   snippet\n")
    print(f"3. Look-alike product on {site}\n   {site}/z（…）\n   链接：https://{site}/p/999/Rivulet-one-suite/\n   snippet\n")
    print(f"4. Another page on {site}\n   {site}/y（…）\n   链接：https://{site}/reviews/{slug}-p2\n   snippet\n")
    sys.exit(0)
if cmd == "render":
    print(f"[来源] {arg} —— 无头 Chrome 渲染（独立临时 profile）\n\n{LONG}")
    sys.exit(0)
if cmd == "pantip":
    print(f"[来源] {arg} —— Pantip 评论接口直连\n\n标题：t\n主帖：s\n评论 1 条\n\n1. [评论] \n   u · 2026-10-01 · {arg}#comment1\n   {LONG}")
    sys.exit(0)
if cmd == "fetch":
    urls = [a for a in sys.argv[2:] if a.startswith("http")]
    for i, u in enumerate(urls, 1):
        if len(urls) > 1:
            print(f"\n===== {i}/{len(urls)} {u}")
        if "hn.algolia.com" in u:
            hits = [{"objectID": "111", "created_at": "2026-10-02T00:00:00Z", "story_title": "Ask HN: GPU clouds",
                     "comment_text": "I moved off <i>RivalOne</i> because availability was terrible.<p>Support took days."},
                    {"objectID": "222", "created_at": "2026-10-03T00:00:00Z", "story_title": "Show HN",
                     "comment_text": "Nice."},
                    {"objectID": "333", "created_at": "2026-10-04T00:00:00Z", "story_title": "",
                     "comment_text": "For cloud gpu rental the hourly price matters less than whether the box boots."},
                    {"objectID": "444", "created_at": "2026-10-05T00:00:00Z", "story_title": "",
                     "comment_text": "Completely unrelated discussion about kernels and schedulers in general."}]
            print(f"[来源] {u} —— 直连\n\n" + json.dumps({"hits": hits}))
        elif "-p2" in u and os.environ.get("FAKE_BLOCK_P2"):
            print(f"读不到：{u} —— 直连 HTTP 403")
        else:
            print(f"[来源] {u} —— 直连\n\n{LONG}")
    sys.exit(0)
assert cmd == "reddit", cmd
if "--proxy" in sys.argv:
    print(f"[来源] {arg} —— Reddit 网页版，2 条评论（经 Scrapeless US 代理，每帖 1 次付费请求；折叠的回复和主帖正文取不到）\n")
    print(f"1. [评论] \n   /u/AutoModerator · 1 赞 · 2026-10-01 · {arg}comment/c0/\n   Please read the rules.\n")
    tid = arg.rstrip("/").rsplit("/", 1)[-1]
    print(f"2. [评论] \n   /u/px · 42 赞 · 2026-10-02 · {arg}comment/c1/\n"
          f"   Proxy comment on {tid}: RivalThree subtitles lag behind RivalOne by a week.\n")
    sys.exit(0)
if os.environ.get("FAKE_REDDIT_403") and not arg.startswith("reddit "):
    print(f"读不到：HTTP 403 <?xml version=\"1.0\"?><feed xmlns=\"http://www.w3.org/2005/Atom\">")
    sys.exit(0)
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
if task.startswith("PLAN"):
    plan = os.environ.get("FAKE_PLAN_REPAIR") if task.startswith("PLAN-REPAIR") else None
    (ws / "research/precollect/plan.json").write_text(plan or os.environ["FAKE_PLAN"], encoding="utf-8")
    raise SystemExit(0)
bank = json.loads(Path(os.environ["FIXTURE"]).read_text(encoding="utf-8"))
with (ws / "research/precollect/signals.csv").open(encoding="utf-8-sig", newline="") as f:
    signals = list(csv.DictReader(f))


def quotes(cats):
    out = []
    for n, cat in enumerate(cats, 1):
        row = next((r for r in signals if r["采集类别"] == cat), None)
        if row is None:  # 这一类只有页面：从页面里摘一句
            page = sorted((ws / "research/precollect/pages").glob("*.txt"))[0].read_text(encoding="utf-8")
            row = {"来源类型": cat, "原话": "the onboarding took two weeks", "出处": page.splitlines()[0][5:]}
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


DEFAULT_PLAN = {"industry": "消费级软件与在线服务", "industry_basis": "官网首页写着 stream Asian dramas，https://brandx.example",
                "category_en": "asian drama streaming",
                "skip": {"google-play": "品牌和竞品都只有网页版", "app-store": "品牌和竞品都只有网页版"}}


def run_case(name: str, mode: str, reviews: str = "ok", repair_rounds: int = 2, plan: dict | None = None,
             plan_repair: dict | None = None, market: str = "US", extra_env: dict | None = None
             ) -> tuple[int, dict, Path, list[dict]]:
    ws = WS_ROOT / f"ws-{name}"
    log = WS_ROOT / f"calls-{name}.jsonl"
    env = {k: v for k, v in os.environ.items() if k not in ("NET_REDDIT_MAX", "DATAFORSEO_WHO")}
    env.update(FAKE_MODE=mode, FIXTURE=str(FIXTURE), FAKE_LOG=str(log), FAKE_REVIEWS=reviews,
               PRECOLLECT_SCRIPTS_DIR=str(STUBS), FAKE_PLAN=json.dumps(plan or DEFAULT_PLAN, ensure_ascii=False),
               **(extra_env or {}))
    if plan_repair is not None:
        env["FAKE_PLAN_REPAIR"] = json.dumps(plan_repair, ensure_ascii=False)
    cmd = [sys.executable, "-I", str(RUNNER), "run", "--case", str(CASE), "--market", market,
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
      and "撑不起任何题的也可以登记" in task_text and "plan-checked.json" in task_text and "research/precollect/pages/" in task_text,
      f"TASK.md {len(task_text)} 字")
plan_text = (ws0 / "PLAN.md").read_text(encoding="utf-8") if (ws0 / "PLAN.md").exists() else ""
check("0 PLAN 模板：判行业、取官网首页存 research/site/、读渠道表、自己跑 check-plan",
      "precollect-channels.json" in plan_text and "research/site/homepages.txt" in plan_text
      and "check-plan" in plan_text and "--country US" in plan_text and "{" not in plan_text.split("plan.json 的格式", 1)[0],
      f"PLAN.md {len(plan_text)} 字")

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
check("1 搜索联想：种子词用行业判断给的英文品类词、gl 小写市场、hl=locale",
      seeds[:2] == ["best asian drama streaming", "asian drama streaming recommendations"]
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

# 6. 开发者与云基础设施
P6 = {"industry": "开发者工具与云基础设施", "industry_basis": "官网写着 rent GPUs by the hour，https://brandx.example",
      "category_en": "cloud gpu rental"}
rc, res, ws, calls = run_case("devcloud", "all", plan=P6)
pc = json.loads((ws / "research/precollect/plan-checked.json").read_text(encoding="utf-8"))
names = {(c["category"], c["name"], c["status"]) for c in pc["channels"]}
check("6 云基础设施：计划 = 行业行（trustpilot、capterra、trustradius、hackernews）+ 美国 reddit",
      names == {("评价", "trustpilot", "planned"), ("评价", "capterra", "planned"), ("评价", "trustradius", "planned"),
                ("社区", "hackernews", "planned"), ("社区", "reddit", "planned")} and pc["source"] == "agent",
      json.dumps(sorted(names), ensure_ascii=False))
searches6 = [c["argv"] for c in calls if c["script"] == "net.py" and c["argv"][0] == "search"]
fetches6 = [c["argv"] for c in calls if c["script"] == "net.py" and c["argv"][0] == "fetch"]
check("6 评价站：站名当关键词搜竞品（不用 site:；第一个竞品够 2 页就不再搜）、只取本站且网址含竞品名的页面、存进 pages/",
      sorted(a[1] for a in searches6) == ["capterra RivalOne reviews", "trustradius RivalOne reviews"]
      and any("https://www.capterra.com/reviews/rivalone-p1" in a and "https://capterra.com/reviews/rivalone-p2" in a
              for a in fetches6)
      and not any("other.example" in x or "Rivulet-one-suite" in x for a in fetches6 for x in a)
      and (ws / "research/precollect/pages/capterra-1.txt").exists()
      and (ws / "research/precollect/pages/capterra-1.txt").read_text(encoding="utf-8").startswith("URL: https://www.capterra.com/"),
      f"search={searches6} fetch={fetches6}")
hn = [r for r in csv.DictReader((ws / "research/precollect/signals.csv").open(encoding="utf-8-sig"))
      if r["出处"].startswith("Hacker News")]
s6 = summary(ws)
check("6 Hacker News：只收提到竞品或两个品类词的评论，HTML 去掉，出处是 item 链接；评价类带页面数",
      len(hn) == 2 and all("<" not in r["原话"] for r in hn)
      and {r["出处"].rsplit("，", 1)[-1] for r in hn} == {"https://news.ycombinator.com/item?id=111",
                                                       "https://news.ycombinator.com/item?id=333"}
      and s6["categories"]["评价"]["pages"] == 4 and s6["industry"] == "开发者工具与云基础设施",
      f"hn={[(r['原话'][:30], r['出处']) for r in hn]} pages={s6['categories']['评价'].get('pages')}")
seeds6 = (ws / "research/precollect/serp/seeds.txt").read_text(encoding="utf-8").split("\n")
check("6 种子词用 category_en；run success", seeds6[0] == "best cloud gpu rental" and rc == 0 and res.get("status") == "success",
      f"seeds={seeds6[:2]} exit={rc} status={res.get('status')}")

# 7. 内容与流媒体
P7 = {"industry": "内容与流媒体", "industry_basis": "官网首页 Watch Asian dramas，https://brandx.example",
      "category_en": "asian drama streaming",
      "app_ids": {"google-play": ["com.brandx.app", "com.rivalone.android"], "app-store": ["id1234567"]}}
rc, res, ws, calls = run_case("streaming", "all", plan=P7)
rev7 = sorted((c["argv"] for c in calls if c["script"] == "collect_reviews.py"), key=lambda a: a[0], reverse=True)
check("7 流媒体：评价只调 google-play、app-store（应用 ID 去掉 id 前缀、带 --country us --lang en），不调 trustpilot；rerun.txt 是工作目录相对路径的完整命令",
      [a[0] for a in rev7] == ["google-play", "app-store"]
      and rev7[0][1:3] == ["com.brandx.app", "com.rivalone.android"] and rev7[1][1] == "1234567"
      and all(a[a.index("--country") + 1] == "us" and a[a.index("--lang") + 1] == "en" for a in rev7)
      and (ws / "research/precollect/reviews/google-play/rerun.txt").read_text(encoding="utf-8").strip().split(
          "collect_reviews.py ", 1)[-1] == "google-play com.brandx.app com.rivalone.android "
      "--out research/precollect/reviews/google-play --product-line 'Streaming platform: Asian drama library with "
      "English subtitles' --id-prefix PR1 --country us --lang en --wait 600",
      f"collect_reviews={rev7}")
c7 = summary(ws)["categories"]
check("7 两个评价渠道的行合并（10 条）、社区加 MyDramaList 站内页；run success",
      c7["评价"]["rows"] == 10 and c7["社区"]["pages"] >= 1 and rc == 0 and res.get("status") == "success"
      and any(a[0] == "search" and a[1] == "mydramalist asian drama streaming" for a in
              (c["argv"] for c in calls if c["script"] == "net.py")),
      json.dumps({k: (v["rows"], v.get("pages")) for k, v in c7.items()}, ensure_ascii=False))

# 8. 行业写错两次 → 默认渠道
BAD = {"industry": "流媒体", "industry_basis": "x"}
rc, res, ws, calls = run_case("badplan", "all", plan=BAD, plan_repair=BAD)
pc8 = json.loads((ws / "research/precollect/plan-checked.json").read_text(encoding="utf-8"))
repair8 = (ws / "PLAN-REPAIR.md").read_text(encoding="utf-8") if (ws / "PLAN-REPAIR.md").exists() else ""
check("8 行业写错：回喂 PLAN-REPAIR 带原报错，仍错退回默认（trustpilot + reddit），原因写进计划，run 照常 success",
      "「流媒体」不在 precollect-channels.json 的 industries 里" in repair8 and pc8["source"] == "fallback"
      and pc8["industry"] == "未判定" and "行业判断两次没通过检查" in pc8["industry_basis"]
      and [(c["category"], c["name"]) for c in pc8["channels"]] == [("评价", "trustpilot"), ("社区", "reddit")]
      and rc == 0 and res.get("status") == "success" and (res.get("precollect") or {}).get("plan_source") == "fallback",
      f"source={pc8.get('source')} basis={pc8.get('industry_basis', '')[:80]}")

# 9. 泰国市场：Pantip，不调 Reddit
rc, res, ws, calls = run_case("th", "all", market="TH",
                              plan={**DEFAULT_PLAN, "local_query": "ดูซีรีส์จีน"})
net9 = [c["argv"] for c in calls if c["script"] == "net.py"]
pantip9 = [a for a in net9 if a[0] == "pantip"]
check("9 泰国：社区走 Pantip（站名 + 本地语言品类词搜索、net.py pantip 只取帖子页、带 --country TH），不调 Reddit、不用无头 Chrome",
      not any(a[0] in ("reddit", "render") for a in net9)
      and any(a[0] == "search" and a[1] == "pantip ดูซีรีส์จีน" and a[a.index("--gl") + 1] == "th" for a in net9)
      and sorted(a[1] for a in pantip9) == ["https://pantip.com/topic/40000001", "https://pantip.com/topic/40000002"]
      and all(a[a.index("--country") + 1] == "TH" for a in pantip9),
      f"net={net9}")

# 10. 想跳过固定渠道 → check-plan 报错，返修后通过
SKIP = {**P6, "skip": {"trustpilot": "不想采"}}
rc, res, ws, calls = run_case("skipfixed", "all", plan=SKIP, plan_repair=P6)
repair10 = (ws / "PLAN-REPAIR.md").read_text(encoding="utf-8") if (ws / "PLAN-REPAIR.md").exists() else ""
pc10 = json.loads((ws / "research/precollect/plan-checked.json").read_text(encoding="utf-8"))
check("10 跳过固定渠道被拒：PLAN-REPAIR 写明只能跳过缺应用或门店的渠道；返修后按 agent 计划采",
      "「trustpilot」按表要采，不能跳过" in repair10 and pc10["source"] == "agent"
      and any(c["argv"][0] == "trustpilot" for c in calls if c["script"] == "collect_reviews.py"),
      repair10.split("报错原文：", 1)[-1][:160].replace("\n", " "))

# 11. 评价只有页面、没登记 → 报错写页面数
P11 = {"industry": "B2B 软件与 SaaS", "industry_basis": "官网写着 travel management software，https://brandx.example",
       "category_en": "travel management software"}
rc, res, ws, _ = run_case("pagesonly", "fix", plan=P11, extra_env={"FAKE_BLOCK_P2": "1"})
repair11 = (ws / "REPAIR-1.md").read_text(encoding="utf-8") if (ws / "REPAIR-1.md").exists() else ""
c11 = summary(ws)["categories"]["评价"]
check("11 评价只有页面（2 页，p2 被拦）：登记报错写「评价 0 条、页面 2 个」和 pages/，返修后 success",
      c11["rows"] == 0 and c11["pages"] == 2 and "评价 0 条、页面 2 个" in repair11
      and "research/precollect/pages/" in repair11 and rc == 0 and res.get("status") == "success",
      f"评价={c11.get('rows')}/{c11.get('pages')} reason={c11.get('reason', '')[:120]} repair={repair11[:0]}")

# 14. 消费电子：rtings 写了 scope，品类不在其中可以跳过；跳过无 scope 的 google-shopping 仍被拒
P14 = {"industry": "消费电子与智能家居", "industry_basis": "官网卖行车记录仪，https://brandx.example", "category_en": "dash cam",
       "skip": {"rtings": "RTINGS 不测行车记录仪"}}
rc, res, ws, calls = run_case("ce", "all", plan=P14)
pc14 = json.loads((ws / "research/precollect/plan-checked.json").read_text(encoding="utf-8"))
st14 = {c["name"]: c["status"] for c in pc14["channels"]}
check("14 rtings 写了 scope：品类不在其中可以跳过，不搜 rtings；google-shopping 照采",
      st14.get("rtings") == "skipped" and st14.get("google-shopping") == "planned" and pc14["source"] == "agent"
      and not any(c["argv"][0] == "search" and c["argv"][1].startswith("rtings") for c in calls if c["script"] == "net.py"),
      json.dumps(st14, ensure_ascii=False))

# 12. Reddit RSS 403 → Google 搜帖子链接 → 网页版
rc, res, ws, calls = run_case("redditproxy", "all", extra_env={"FAKE_REDDIT_403": "1"})
net12 = [c["argv"] for c in calls if c["script"] == "net.py"]
rsearch = [a for a in net12 if a[0] == "search" and a[1].startswith("reddit ")]
rproxy = [a for a in net12 if a[0] == "reddit" and "--proxy" in a]
pc12 = json.loads((ws / "research/precollect/community/summary.json").read_text(encoding="utf-8"))
comm12 = list(csv.DictReader((ws / "research/precollect/community/signals.csv").open(encoding="utf-8-sig")))
check("12 Reddit RSS 403：改 Google 搜「reddit <词>」拿帖子链接，再读网页版（每帖 1 次付费）",
      bool(rsearch) and rsearch[0][1].startswith("reddit ") and len(rproxy) == 2
      and all(a[1].startswith("https://www.reddit.com/r/") for a in rproxy),
      f"search={rsearch} proxy={rproxy}")
c12 = pc12["channels"][0]
check("12 网页版评论进信号表：AutoModerator 不收、点赞和日期解析对、出处是单条评论链接、proxy_pages 记下用了哪两帖",
      len(comm12) == 2 and all(r["出处"].startswith("Reddit r/") and "，https://www.reddit.com/r/" in r["出处"]
                              for r in comm12)
      and any("by a week" in r["原话"] for r in comm12)
      and c12["rows"] == 2 and len(c12.get("proxy_pages") or []) == 2 and "网页版 2 帖" in c12["reason"],
      f"rows={len(comm12)} proxy={c12.get('proxy_pages')} reason={c12['reason'][:200]}")

# 13. 网页版额度用完 → 后续帖子记失败，不静默丢
rc, res, ws, calls = run_case("redditcap", "all", extra_env={"FAKE_REDDIT_403": "1", "FAKE_SEARCH_THREADS": "4"})
net13 = [c["argv"] for c in calls if c["script"] == "net.py"]
c13 = json.loads((ws / "research/precollect/community/summary.json").read_text(encoding="utf-8"))["channels"][0]
check("13 网页版最多 2 帖：第 3 帖不再付费，记进 problems 和 reason，不静默丢",
      len([a for a in net13 if a[0] == "reddit" and "--proxy" in a]) == 2
      and "网页版额度已用完（2 帖）" in c13["reason"],
      c13["reason"][:300])

# 15. 行业写「其他」：AI 推理补渠道，add 最多 5 个、add_sites 加渠道表外的站（3.7.0）
P15 = {"industry": "其他", "industry_basis": "卖宠物营养品和训练用具，官网 shop our pet supplements，https://brandx.example",
       "category_en": "dog supplements",
       "add": {"google-shopping": "实体商品在零售站有评价", "trustpilot": "竞品有 DTC 店", "iherb": "保健品零售站",
               "capterra": "测试第 4 个", "rtings": "测试第 5 个"},
       "add_sites": {"https://www.petforums.co.uk/": {"category": "社区", "why": "英国宠物主论坛，买家讨论营养品"}}}
rc, res, ws, calls = run_case("other", "all", plan=P15)
pc15 = json.loads((ws / "research/precollect/plan-checked.json").read_text(encoding="utf-8"))
ch15 = {c["name"]: c for c in pc15.get("channels") or []}
pages15 = sorted(p.name for p in (ws / "research/precollect/pages").glob("petforums*"))
check("15 「其他」：add 5 个通过、add_sites 的站按站内页渠道采到页面",
      pc15.get("source") == "agent" and len([n for n in ch15 if ch15[n]["from"].startswith("补充")]) == 5
      and ch15.get("petforums.co.uk", {}).get("spec", {}).get("site") == "petforums.co.uk" and pages15,
      f"source={pc15.get('source')} channels={sorted(ch15)} pages={pages15}")
P15b = {**P15, "add": {**P15["add"], "clutch": "第 6 个"}, "add_sites": {"a.com": {"category": "社区", "why": "x"},
        "b.com": {"category": "社区", "why": "y"}, "c.com": {"category": "评价", "why": "z"}}}
rc, res, ws, calls = run_case("othercap", "all", plan=P15b, plan_repair=P15)
rep15 = (ws / "PLAN-REPAIR.md").read_text(encoding="utf-8") if (ws / "PLAN-REPAIR.md").exists() else ""
check("15b 「其他」超额：add 6 个、add_sites 3 个都被拒，返修后通过", "add 最多 5 个" in rep15 and "add_sites 最多 2 个" in rep15,
      rep15.split("报错原文：", 1)[-1][:200].replace("\n", " "))

# 16. 其他实体消费品：评价采 Google Shopping 和 Trustpilot（3.7.0）
P16 = {"industry": "其他实体消费品", "industry_basis": "卖厨房小家电，官网 shop air fryers，https://brandx.example",
       "category_en": "air fryer"}
rc, res, ws, calls = run_case("consumer", "all", plan=P16)
rv16 = sorted({c["argv"][0] for c in calls if c["script"] == "collect_reviews.py"})
check("16 其他实体消费品：评价走 google-shopping 和 trustpilot", rv16 == ["google-shopping", "trustpilot"], f"reviews={rv16}")

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
