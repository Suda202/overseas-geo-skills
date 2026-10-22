"""售前采集：v8 题库 CSV → Scrapeless 采集目录（项目唯一的采集实现）。

直接调 Scrapeless AI Scraper API（创建任务 → 轮询结果），产出 builder 和
crawl-integrity 直接能读的目录：

    <collect>/scraper.<平台>/<REGION>/<NNNN>.json      NNNN = 题库行号（从 1 起）

每个文件是 Scrapeless 结果接口的原始返回（{"status", "task_result"}），与 Go 版试点
（已归档到 90-历史归档/scrapeless-demo）落盘格式一致，历史采集目录可直接续采。

答案有效性复用 geo_presales_core.crawler.answer_validity，字段读取复用 crawl-integrity
的平台契约，这里不另写口径。每格独立重试；重试耗尽仍无效的格移出采集目录、登记进
manifest，不进任何分母（integrity D5）。AIO 例外：接口 success 就算采到，空正文是
「本次未触发概览」，不重试（契约 empty_answer_allowed）。

用法：
    export SCRAPELESS_API_KEY=...
    python3 scripts/collect_answers.py --questions <题库.csv> --out <采集目录> --regions US --dry-run
    python3 scripts/collect_answers.py --questions <题库.csv> --out <采集目录> --regions US
    python3 scripts/collect_answers.py --questions <题库.csv> --out <采集目录> --regions US --check-only
    python3 scripts/collect_answers.py --questions <题库.csv> --out <采集目录> --regions US --platforms all

平台：默认 chatgpt,gemini,aimode,overview；`--platforms all` 采 Scrapeless 支持的全部 8 个
（另含 perplexity、copilot、grok、alexa）。各平台 input 参数不同，见 platform_input()。

退出码：0 全部有效；1 有格重试耗尽，已移出分母并登记；2 输入、环境、鉴权或余额错误；
3 仅 --check-only：还有格待采。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
CORE_DIR = SKILLS / "geo-presales-report-editor" / "scripts"
INTEGRITY = SKILLS / "geo-presales-crawl-integrity" / "scripts" / "audit_crawl_integrity.py"
BASE_URL = os.environ.get("SCRAPELESS_BASE_URL", "https://api.scrapeless.com")  # 覆盖仅供本地假服务测试
CREATE_PATH = "/api/v2/scraper/request"
RESULT_PATH = "/api/v2/scraper/result/"
DEFAULT_PLATFORMS = "chatgpt,gemini,aimode,overview"
ALL_PLATFORMS = "chatgpt,perplexity,copilot,gemini,aimode,overview,grok,alexa"
# 回答里回显题面的字段：Grok 叫 user_query，Alexa 叫 user_text，其余叫 prompt
PROMPT_ECHO_KEYS = ("prompt", "user_query", "user_text")
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
from geo_presales_core.crawler import answer_validity  # noqa: E402
from geo_presales_core.util import normalize_text  # noqa: E402


def _load_integrity():
    spec = importlib.util.spec_from_file_location("audit_crawl_integrity", INTEGRITY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


integrity = _load_integrity()
LOCK = threading.Lock()
STOP = threading.Event()
API_KEY = ""


class Fatal(Exception):
    """鉴权、权限或余额错误：继续调用只会全部失败，整批停下。"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sanitize(text: str) -> str:
    return text.replace(API_KEY, "[REDACTED]") if API_KEY else text


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(sanitize(json.dumps(value, ensure_ascii=False, indent=2)) + "\n", encoding="utf-8")
    tmp.replace(path)


def log_event(out: Path, event: str, **fields) -> None:
    line = sanitize(json.dumps({"time": now(), "event": event, **fields}, ensure_ascii=False))
    with LOCK:
        events = out / "_collector" / "events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        with events.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def load_questions(path: Path) -> list[dict]:
    """读题库，并拒绝会让编号或题面匹配错位的输入。"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"题库为空：{path}")
    if "query" not in rows[0]:
        raise SystemExit(f"题库缺少 query 列：{path}")
    seen: dict[str, int] = {}
    questions = []
    for index, row in enumerate(rows, 1):
        query = str(row.get("query") or "").strip()
        if not query:
            raise SystemExit(f"题库第 {index} 行 query 为空：题号会与 builder 错位，先删掉空行")
        key = normalize_text(query)
        if key in seen:
            raise SystemExit(f"题库第 {index} 行与第 {seen[key]} 行题面相同：builder 按题面匹配样本，会分错题")
        seen[key] = index
        questions.append({"qid": f"{index:04d}", "query": query})
    return questions


def judge_payload(payload, platform: str, query: str, contract: dict) -> tuple[bool, str]:
    """一份返回能否进分母。返回 (有效, 原因)。"""
    if not isinstance(payload, dict):
        return False, "BAD_PAYLOAD"
    if str(payload.get("status") or "").lower() != "success":
        return False, f"STATUS_{str(payload.get('status') or 'none').upper()}"
    result = payload.get("task_result") or {}
    prompt = next((str(result[k]).strip() for k in PROMPT_ECHO_KEYS if result.get(k)), "")
    # AI Mode / AIO 的返回不带 prompt，只能信文件名；带了就必须对得上
    if prompt and normalize_text(prompt) != normalize_text(query):
        return False, "PROMPT_MISMATCH"
    answer = integrity.as_text(integrity.first_present(payload, contract[platform]["answer"]))
    if not answer.strip() and contract[platform].get("empty_answer_allowed"):
        return True, "AIO_NOT_TRIGGERED"  # AIO 不是每次都出概览：接口 success 就算采到
    valid, reason = answer_validity(answer)
    return (True, "OK") if valid else (False, reason or "INVALID")


def judge_file(path: Path, platform: str, query: str, contract: dict) -> tuple[bool, str]:
    if not path.exists():
        return False, "MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "BAD_JSON"
    return judge_payload(payload, platform, query, contract)


def cell_path(out: Path, platform: str, region: str, qid: str) -> Path:
    return out / f"scraper.{platform}" / region / f"{qid}.json"


def http_json(method: str, path: str, payload, timeout: float):
    request = urllib.request.Request(
        BASE_URL + path, method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"x-api-token": API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=min(45.0, max(timeout, 1.0))) as response:
            status, content = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, content = error.code, error.read()
    text = content.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, {"status": "invalid_json", "message": sanitize(text)[:2000]}


def check_fatal(status: int, raw) -> None:
    message = json.dumps(raw, ensure_ascii=False).lower()
    if status in (401, 402, 403) or any(p in message for p in (
            "insufficient balance", "insufficient credit", "balance is insufficient")):
        STOP.set()
        raise Fatal(f"HTTP {status}：鉴权、权限或余额错误，整批停止")


def task_id_from(value) -> str:
    if isinstance(value, dict):
        for name in ("task_id", "taskId"):
            if isinstance(value.get(name), str) and value[name]:
                return value[name]
        for child in value.values():
            found = task_id_from(child)
            if found:
                return found
    return ""


def platform_input(platform: str, region: str, query: str, args) -> dict:
    """只发该平台文档列出的参数（2026-10-21 按 Scrapeless 各平台 README 核对）。"""
    payload = {"prompt": query, "country": region}
    if platform == "perplexity":
        payload["web_search"] = args.web_search
    elif platform == "copilot":
        payload["mode"] = args.copilot_mode
    elif platform == "grok":
        payload["mode"] = args.grok_mode
    elif platform != "alexa":
        payload.update(web_search=args.web_search, shopping=args.shopping)
    return payload


def one_attempt(platform: str, region: str, query: str, args) -> tuple[dict | None, str, str]:
    """创建一次任务并轮询到终态。返回 (最后一次返回体, 错误码, task_id)。"""
    body = {"actor": f"scraper.{platform}", "input": platform_input(platform, region, query, args)}
    deadline = time.monotonic() + args.timeout
    status, raw = http_json("POST", CREATE_PATH, body, deadline - time.monotonic())
    check_fatal(status, raw)
    if status not in (200, 201, 202):
        return raw, f"CREATE_HTTP_{status}", ""
    if isinstance(raw, dict) and str(raw.get("status") or "").lower() in ("success", "failed"):
        return raw, "", task_id_from(raw)  # 偶有同步直接返回结果
    task_id = task_id_from(raw)
    if not task_id:
        return raw, "MISSING_TASK_ID", ""
    interval = 2.0
    last = raw
    while time.monotonic() < deadline and not STOP.is_set():
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
        try:
            status, raw = http_json("GET", RESULT_PATH + urllib.parse.quote(task_id, safe=""),
                                    None, deadline - time.monotonic())
        except (urllib.error.URLError, TimeoutError, OSError):
            interval = 10.0
            continue
        check_fatal(status, raw)
        if status in TRANSIENT_HTTP:
            interval = 10.0
            continue
        if status not in (200, 202):
            return raw, f"POLL_HTTP_{status}", task_id
        last = raw
        provider = str(raw.get("status") or "").lower() if isinstance(raw, dict) else "invalid"
        if provider in ("", "pending", "running", "processing"):
            interval = min(interval + 1.0, 10.0)
            continue
        return raw, "", task_id
    return last, "STOPPED" if STOP.is_set() else "TIMEOUT", task_id


def collect_cell(cell: tuple[str, str, str], query: str, out: Path, args, contract: dict) -> tuple[bool, str]:
    platform, region, qid = cell
    target = cell_path(out, platform, region, qid)
    attempts_dir = out / "_collector" / "attempts" / f"scraper.{platform}" / region
    reason = "NOT_RUN"
    for attempt in range(1, args.max_attempts + 1):
        if STOP.is_set():
            return False, "STOPPED"
        try:
            payload, error, task_id = one_attempt(platform, region, query, args)
        except Fatal:
            raise
        except Exception as exc:  # 网络等偶发异常：记一次失败尝试，继续重试
            payload, error, task_id = None, f"{type(exc).__name__}", ""
        if not error:
            ok, reason = judge_payload(payload, platform, query, contract)
        else:
            ok, reason = False, error
        log_event(out, "attempt", cell="/".join(cell), attempt=attempt, task_id=task_id, ok=ok, reason=reason)
        if ok:
            write_json(target, payload)
            return True, "OK"
        if payload is not None:
            write_json(attempts_dir / f"{qid}.attempt{attempt:02d}.json", payload)
        if error.startswith("CREATE_HTTP_4") and error not in ("CREATE_HTTP_408", "CREATE_HTTP_429"):
            break  # 请求本身不合法，重试没有意义
        time.sleep(min(attempt * 2, 10))
    return False, reason


def scan(out: Path, questions: list[dict], platforms: list[str], regions: list[str], contract: dict) -> dict:
    return {(p, r, q["qid"]): judge_file(cell_path(out, p, r, q["qid"]), p, q["query"], contract)
            for p in platforms for r in regions for q in questions}


def load_manifest(out: Path) -> dict:
    path = out / "collect-manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_manifest(out: Path, args, questions, platforms, regions, cells, unrecoverable: dict, state: str) -> dict:
    manifest = {
        "schema": "presales-collect-manifest/v1",
        "state": state,
        "updated_at": now(),
        "questions_file": str(args.questions),
        "questions_sha256": hashlib.sha256(args.questions.read_bytes()).hexdigest(),
        "question_count": len(questions),
        "platforms": platforms,
        "regions": regions,
        "repeats": 1,
        "web_search": args.web_search,
        "shopping": args.shopping,
        **({"copilot_mode": args.copilot_mode} if "copilot" in platforms else {}),
        **({"grok_mode": args.grok_mode} if "grok" in platforms else {}),
        "max_attempts_per_cell": args.max_attempts,
        "planned_cells": len(cells),
        "valid_cells": sum(1 for ok, _ in cells.values() if ok),
        "unrecoverable": [{"cell": list(cell), "reason": reason} for cell, reason in sorted(unrecoverable.items())],
        "note": "unrecoverable 里的格已移到 _collector/unrecoverable/，不进任何分母（integrity D5）；各平台分母可以不等。",
    }
    write_json(out / "collect-manifest.json", manifest)
    return manifest


def main() -> int:
    global API_KEY
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", type=Path, required=True, help="v8 上传 CSV（含 query 列）")
    parser.add_argument("--out", type=Path, required=True, help="采集目录")
    parser.add_argument("--regions", required=True, help="逗号分隔的国家/地区代码，如 US 或 SG,MY")
    parser.add_argument("--platforms", default=DEFAULT_PLATFORMS,
                        help=f"逗号分隔的平台名（scraper. 后缀），默认 {DEFAULT_PLATFORMS}；all = {ALL_PLATFORMS}")
    parser.add_argument("--copilot-mode", default="search",
                        choices=["search", "smart", "chat", "reasoning", "study"],
                        help="Copilot 模式，默认 search（联网检索，带引用）")
    parser.add_argument("--grok-mode", default="MODEL_MODE_AUTO",
                        choices=["MODEL_MODE_AUTO", "MODEL_MODE_FAST", "MODEL_MODE_EXPERT"],
                        help="Grok 模式，默认 MODEL_MODE_AUTO（与网页版默认一致）")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=6, help="每格最多尝试次数（含首次）")
    parser.add_argument("--timeout", type=float, default=300, help="单次尝试的轮询上限（秒）")
    parser.add_argument("--no-web-search", dest="web_search", action="store_false")
    parser.add_argument("--no-shopping", dest="shopping", action="store_false")
    parser.add_argument("--retry-unrecoverable", action="store_true", help="对 manifest 里已移出的格重新采集")
    parser.add_argument("--dry-run", action="store_true", help="只打印待采格与调用量，不调用")
    parser.add_argument("--check-only", action="store_true", help="只验收现有目录；有待采格时退出码 3")
    args = parser.parse_args()
    args.out = args.out.expanduser().resolve()

    if not args.questions.exists():
        print(f"题库不存在：{args.questions}", file=sys.stderr)
        return 2
    questions = load_questions(args.questions)
    by_qid = {q["qid"]: q["query"] for q in questions}
    raw_platforms = ALL_PLATFORMS if args.platforms.strip().lower() == "all" else args.platforms
    platforms = [p.strip().removeprefix("scraper.") for p in raw_platforms.split(",") if p.strip()]
    regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
    contract = integrity.load_platform_contract()
    unknown = [p for p in platforms if p not in contract]
    if unknown:
        print(f"平台 {unknown} 没有字段契约（integrity D7），先在 platform-contract.json 登记再采", file=sys.stderr)
        return 2

    cells = scan(args.out, questions, platforms, regions, contract)
    unrecoverable = {tuple(x["cell"]): x["reason"] for x in load_manifest(args.out).get("unrecoverable", [])}
    if args.retry_unrecoverable:
        for cell in list(unrecoverable):
            src = args.out / "_collector" / "unrecoverable" / f"scraper.{cell[0]}" / cell[1] / f"{cell[2]}.json"
            src.unlink(missing_ok=True)
        unrecoverable = {}
    todo = [cell for cell, (ok, _) in cells.items() if not ok and cell not in unrecoverable]
    valid = sum(1 for ok, _ in cells.values() if ok)
    print(f"题库 {len(questions)} 题 × 平台 {len(platforms)}（{','.join(platforms)}）× 区域 "
          f"{len(regions)}（{','.join(regions)}）× 1 次 = {len(cells)} 格；"
          f"已有效 {valid}，已登记移出 {len(unrecoverable)}，待采 {len(todo)}")

    if args.check_only:
        if todo:
            print(f"待采 {len(todo)} 格，例如 {['/'.join(c) for c in todo[:3]]}")
            return 3
        return 0
    if args.dry_run or not todo:
        if todo:
            print(f"[dry-run] 首轮 {len(todo)} 次调用；失败格每格最多再试 {args.max_attempts - 1} 次")
        return 0

    API_KEY = os.environ.get("SCRAPELESS_API_KEY", "").strip()
    if not API_KEY:
        print("缺少 SCRAPELESS_API_KEY 环境变量（不要把 Key 写进脚本或命令行参数）", file=sys.stderr)
        return 2

    done = 0
    fatal = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(collect_cell, cell, by_qid[cell[2]], args.out, args, contract): cell
                   for cell in todo}
        for future in concurrent.futures.as_completed(futures):
            cell = futures[future]
            try:
                ok, reason = future.result()
            except Fatal as exc:
                fatal = str(exc)
                continue
            done += 1
            if not ok and reason != "STOPPED":
                unrecoverable[cell] = reason
            print(f"[{done}/{len(todo)}] {'/'.join(cell)} {'OK' if ok else reason}", flush=True)

    for cell in unrecoverable:
        src = cell_path(args.out, *cell)
        if src.exists():  # 旧的无效样本挪走，不留在分母里
            dst = args.out / "_collector" / "unrecoverable" / f"scraper.{cell[0]}" / cell[1] / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    cells = scan(args.out, questions, platforms, regions, contract)
    state = "halted" if fatal else "completed"
    manifest = write_manifest(args.out, args, questions, platforms, regions, cells, unrecoverable, state)
    print(f"有效 {manifest['valid_cells']}/{manifest['planned_cells']}；采集目录 {args.out}")
    if fatal:
        print(f"✗ {fatal}；已采到的结果保留，修好后重跑同一命令续采", file=sys.stderr)
        return 2
    if manifest["unrecoverable"]:
        print(f"⚠ {len(manifest['unrecoverable'])} 格重试耗尽仍无效，已移出分母：")
        for item in manifest["unrecoverable"]:
            print(f"   {'/'.join(item['cell'])}  {item['reason']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
