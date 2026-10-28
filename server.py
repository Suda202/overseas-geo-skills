#!/usr/bin/env python3
"""GEO Skills 统一 HTTP API 服务。

零外部依赖，用标准库 http.server 实现。
平台方只需配置一个 URL：POST /api/v1/invoke，通过 tool 字段路由到所有能力。

启动：
    export GEO_PRESALES_SKILLS_ROOT=/path/to/skills   # 可选，默认 ./skills
    python3 server.py --port 8080

调用：
    curl -X POST http://localhost:8080/api/v1/invoke \
      -H "Content-Type: application/json" \
      -d '{"tool": "normalize_case", "params": {"payload": {...}}}'
"""

from __future__ import annotations

import argparse
import csv
import difflib
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import date
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------- 路径

REPO_ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """把 .env 读进 os.environ（不覆盖已存在的真实环境变量）。

    collect_answers 等子脚本通过环境变量拿 SCRAPELESS_API_KEY，
    而 _run_script 只透传 os.environ。若 key 只写在 .env 里、
    本进程没加载，子进程就会报"缺少 SCRAPELESS_API_KEY"。
    这里启动时统一加载，避免每个子脚本各自找 .env。
    """
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv(REPO_ROOT / ".env")

SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT",
    str(REPO_ROOT / "skills"),
))

# 核心包路径（geo_presales_core 所在目录）
CORE_DIR = SKILLS_ROOT / "geo-presales-report-editor" / "scripts"
AUDIT_SCRIPTS = SKILLS_ROOT / "geo-presales-report-audit" / "scripts"

# 注入 sys.path，使所有脚本的跨 Skill 导入可用
for _p in (str(CORE_DIR), str(AUDIT_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 工具脚本所在目录也加入 sys.path（供直接函数调用）
_SCRIPT_DIRS = {
    "geo-presales-prompt-builder": SKILLS_ROOT / "geo-presales-prompt-builder" / "scripts",
    "geo-presales-report-builder": SKILLS_ROOT / "geo-presales-report-builder" / "scripts",
    "geo-presales-sentiment-judge": SKILLS_ROOT / "geo-presales-sentiment-judge" / "scripts",
    "geo-presales-crawl-integrity": SKILLS_ROOT / "geo-presales-crawl-integrity" / "scripts",
    "geo-presales-eval-case-builder": SKILLS_ROOT / "geo-presales-eval-case-builder" / "scripts",
    "overseas-geo-competitor-research": SKILLS_ROOT / "overseas-geo-competitor-research" / "scripts",
    "geo-after-sales-prompt-builder": SKILLS_ROOT / "geo-after-sales-prompt-builder" / "scripts",
}
for _d in _SCRIPT_DIRS.values():
    if _d.exists() and str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


# ---------------------------------------------------------------- 工具函数

def _parse_embedded(text: str):
    """尝试把字符串解析为 JSON 对象；失败返回哨兵。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # 平台有时传的是 Python repr（单引号），例如 "{'payload': {...}}"
        try:
            import ast
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            pass
        return _UNPARSED


_UNPARSED = object()


def _complete_json(text: str):
    """把括号不配平 / 字符串未闭合的 JSON 补全。

    平台拼嵌套 JSON 时经常丢掉一个结尾的 } 或 "，导致 json.loads 报
    "Expecting ',' delimiter"。这里按字符串状态扫描，补上缺失的引号和括号。
    补不补得好看结果——补完仍解析失败就返回 None。
    """
    out = []
    stack = []
    in_str = False
    escaped = False
    for ch in text:
        if in_str:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
        elif ch in "{[":
            stack.append(ch)
            out.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            out.append(ch)
        else:
            out.append(ch)

    if in_str:
        if escaped:
            out.append("\\")
        out.append('"')
    for opener in reversed(stack):
        out.append("}" if opener == "{" else "]")

    repaired = "".join(out)
    if repaired == text:
        return None
    try:
        return json.loads(repaired, strict=False)
    except (json.JSONDecodeError, ValueError):
        return None


def _recover_body(text: str):
    """尽最大努力把平台发来的 body 解析成 dict。

    平台在传嵌套 JSON 时，常见两种坏 body：
      1. params 被序列化成字符串，但里面的引号没转义——外层 JSON 直接不合法；
      2. 字符串里带了裸换行/制表符——json.loads 默认 strict 会拒绝。

    这里逐级降级：标准解析 → 宽松解析 → Python repr → 从坏 body 里
    「抠」出 params 原文再单独修。全都失败才返回 None，交由调用方报错。
    """
    # 1. 标准解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 宽松解析：允许字符串内出现裸换行/制表符
    try:
        return json.loads(text, strict=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # 3. Python repr（平台偶尔直传 dict 的 str()）
    try:
        import ast
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        pass

    # 3b. 括号不配平：补全缺失的 } ] "
    parsed = _complete_json(text)
    if isinstance(parsed, (dict, list)):
        return parsed

    # 4. 从坏 body 里抠出 params 原文 + tool，各自单修
    tool = None
    m_tool = re.search(r'"?tool"?\s*:\s*"([^"]+)"', text)
    if m_tool:
        tool = m_tool.group(1)

    m = re.search(r'"?params"?\s*:\s*', text)
    if not m:
        return None

    rest = text[m.end():].strip()
    # 去掉尾部的 tool 键与闭合花括号，留下 params 的值
    rest = re.sub(r',?\s*"?tool"?\s*:\s*"[^"]*"\s*\}?\s*$', "", rest).strip()

    # 0. 最稳的一招：直接对 rest 做花括号配平，找到完整 JSON 对象。
    #    平台经常把 params 字符串的转义弄丢，但里面的 JSON 本身是合法的，
    #    用配平扫描比正则/引号定位都可靠，不受字符串长度限制。
    def _balanced(span):
        start = span.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        i = start
        while i < len(span):
            c = span[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c in "{[":
                    depth += 1
                elif c in "}]":
                    depth -= 1
                    if depth == 0:
                        return span[start:i + 1]
            i += 1
        return None

    balanced = _balanced(rest)
    if balanced is not None:
        for strict in (True, False):
            try:
                val = json.loads(balanced, strict=strict)
                if isinstance(val, (dict, list)):
                    return {"tool": tool, "params": val} if tool else val
            except (json.JSONDecodeError, ValueError):
                pass

    if rest.startswith('"'):
        body_str = rest[1:]
        variants = []

        # a) 花括号配平：从第一个 { 扫到真正闭合的位置，无视引号是否转义。
        #    平台把 params 字符串的结束引号吃掉时，后面会整段被吞进字符串，
        #    只有配平扫描能救回来。
        start = body_str.find("{")
        if start != -1:
            depth = 0
            in_str = False
            k = start
            while k < len(body_str):
                c = body_str[k]
                if in_str:
                    if c == "\\":
                        k += 2
                        continue
                    if c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c in "{[":
                        depth += 1
                    elif c in "}]":
                        depth -= 1
                        if depth == 0:
                            variants.append(body_str[start:k + 1])
                            break
                k += 1

        # b) 转义感知扫描：找到 params 字符串真正的结束引号（跳过 \"）
        end = None
        i = 0
        while i < len(body_str):
            if body_str[i] == "\\":
                i += 2
                continue
            if body_str[i] == '"':
                end = i
                break
            i += 1
        if end is not None and body_str[:end] not in variants:
            variants.append(body_str[:end])

        # c) 兜底：取最后一个引号（应对内层引号未转义、但有尾部垃圾的情况）
        last_q = body_str.rfind('"')
        if last_q != -1 and body_str[:last_q] not in variants:
            variants.append(body_str[:last_q])

        candidates = []
        for v in variants:
            for cand in (v, v.replace('\\"', '"'), v.replace('\\"', '"').replace("\\'", "'")):
                if cand not in candidates:
                    candidates.append(cand)

        for cand in candidates:
            for strict in (True, False):
                try:
                    val = json.loads(cand, strict=strict)
                    if isinstance(val, (dict, list)):
                        return {"tool": tool, "params": val} if tool else val
                except (json.JSONDecodeError, ValueError):
                    pass
            try:
                import ast
                val = ast.literal_eval(cand)
                if isinstance(val, (dict, list)):
                    return {"tool": tool, "params": val} if tool else val
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                pass
    else:
        # params 本身没被字符串化，只是外层坏了：试着补一个大括号再解析
        for cand in (rest, rest.rstrip("}") + "}"):
            try:
                val = json.loads(cand, strict=False)
                if isinstance(val, (dict, list)):
                    return {"tool": tool, "params": val} if tool else val
            except (json.JSONDecodeError, ValueError):
                pass

    return None


def _deep_parse(value):
    """递归修复：如果某个值是 JSON 字符串，自动反序列化为对象。

    平台在传递嵌套 JSON 时，可能把 dict/list 序列化成字符串，
    例如 "input": "{\"target\": ...}" 而不是 "input": {"target": ...}。
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            parsed = _parse_embedded(stripped)
            if parsed is not _UNPARSED:
                return _deep_parse(parsed)
        return value
    if isinstance(value, dict):
        return {k: _deep_parse(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_parse(item) for item in value]
    return value


def _coerce_params(raw):
    """把 params 规整为 dict。

    平台偶尔会把整个 params 当成字符串传（甚至空串）。这里尽量还原，
    还原不了就返回 (None, 错误信息)，由调用方转成 400，而不是 500。
    """
    if raw is None:
        return {}, None
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return {}, None
        if stripped.startswith(("{", "[")):
            parsed = _parse_embedded(stripped)
            if isinstance(parsed, dict):
                return parsed, None
            if parsed is not _UNPARSED:
                return None, f"params 解析后不是对象（dict），实际解析出 {type(parsed).__name__}"
            # 括号不配平 / 字符串未闭合：补全后再试
            repaired = _complete_json(stripped)
            if isinstance(repaired, dict):
                return repaired, None
            # 看起来像 JSON/repr 但解析失败：把原文截断后放进报错，方便平台定位
            preview = stripped[:120] + ("..." if len(stripped) > 120 else "")
            return None, f"params 不是合法 JSON 或 Python repr：{preview}"
        # 普通字符串（参数名、None、undefined 等）
        preview = stripped[:120] + ("..." if len(stripped) > 120 else "")
        return None, f"params 必须是 JSON 对象；收到的是非 JSON 字符串：{preview}"
    return None, f"params 必须是 JSON 对象，收到 {type(raw).__name__}"


def _ok(data, warnings=None):
    return {"ok": True, "data": data, "error": None, "warnings": warnings or []}


def _err(message, code=None):
    return {"ok": False, "data": None, "error": str(message), "error_code": code}


def _run_script(script_path: Path, args: list[str], timeout: int = 600) -> dict:
    """subprocess 调用脚本，捕获 stdout/stderr/exit_code。"""
    env = {**os.environ, "GEO_PRESALES_SKILLS_ROOT": str(SKILLS_ROOT)}
    cmd = [sys.executable, str(script_path)] + [str(a) for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"超时（{timeout}s）"}
    return {"exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}


def _load_module(script_path: Path):
    """动态加载 Python 模块，用于直接函数调用。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _script(skill: str, name: str) -> Path:
    """解析工具脚本路径。"""
    p = SKILLS_ROOT / skill / "scripts" / name
    if not p.exists():
        raise FileNotFoundError(f"工具脚本不存在: {p}")
    return p


def _write_tmp(data, suffix=".json") -> Path:
    """把 dict/str 写入临时文件，返回路径。"""
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return Path(tmp)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 工具处理器
# 每个处理器接收 params dict，返回 dict。
# 两种方式：
#   A. 直接调函数（脚本有可复用的纯函数）
#   B. subprocess 调用（脚本只有 argparse CLI）

# ── geo-presales-prompt-builder ──

def handle_normalize_case(params):
    """Case 归一化。直接调 normalize() 函数。"""
    mod = _load_module(_script("geo-presales-prompt-builder", "normalize_case.py"))
    result = mod.normalize(params["payload"])
    return _ok(result)


def handle_validate_question_bank(params):
    """题库校验。直接调 validate() 函数。

    data 可以内联传对象，也可以只传 bank_path——平台把 params 序列化成
    字符串时体积翻倍，大题库内联两遍（write_file + validate）极易超坏，
    所以 write_file 之后按路径校验是默认推荐姿势。
    """
    mod = _load_module(_script("geo-presales-prompt-builder", "validate_question_bank.py"))
    data = params.get("data")
    if data is None:
        bank_path = params.get("bank_path")
        if not bank_path:
            raise KeyError("data / bank_path 至少提供一个")
        data = json.loads(Path(bank_path).read_text(encoding="utf-8"))
    errors, warnings, summary = mod.validate(data, baseline=params.get("baseline"))
    return _ok({"valid": not errors, "errors": errors, "warnings": warnings, "summary": summary})


# ── geo-presales-eval-case-builder ──

def handle_validate_case(params):
    """Case Markdown 校验。subprocess。"""
    md_path = params.get("markdown_path")
    if not md_path and params.get("markdown_content"):
        md_path = str(_write_tmp(params["markdown_content"], suffix=".md"))
    r = _run_script(_script("geo-presales-eval-case-builder", "validate_case.py"), [md_path])
    return _ok(r)


# ── overseas-geo-competitor-research ──

def handle_competitor_research_prepare(params):
    """竞品研究：冻结输入。subprocess。

    params.overwrite=true 时透传 --overwrite，允许脚本清空已存在的 run-dir；
    默认不传，保持“空目录”硬约束，防止 finalize 拿到错配的旧证据。

    响应里附带 research_plan 的完整 JSON 内容，让平台 agent 不用 read_file
    就能拿到检索计划（平台对通用工具有调用次数限制）。
    """
    input_path = _write_tmp(params["input"])
    run_dir = params["run_dir"]
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    args = ["prepare", "--input", str(input_path), "--run-dir", run_dir]
    if params.get("overwrite"):
        args.append("--overwrite")
    r = _run_script(
        _script("overseas-geo-competitor-research", "competitor_research.py"),
        args,
    )
    # 成功时附带 research-plan.json 内容
    if r.get("exit_code") == 0:
        plan_path = Path(run_dir) / "research-plan.json"
        if plan_path.exists():
            try:
                r["research_plan"] = json.loads(plan_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return _ok(r)


def _normalize_research(research: dict) -> dict:
    """把 agent 常见的字段名偏差纠正为契约字段名（不改变语义）。

    只做**无歧义**的重命名；评分/证据链等语义仍由脚本严格校验。
    目的是别让 id→evidence_id 这种纯粹抄错名字的问题浪费一次调用。
    """
    if not isinstance(research, dict):
        return research
    # evidence: id → evidence_id, supports(str) → claims(list)
    ev = research.get("evidence")
    if isinstance(ev, list):
        for item in ev:
            if not isinstance(item, dict):
                continue
            if "evidence_id" not in item and "id" in item:
                item["evidence_id"] = item.pop("id")
            if "claims" not in item and "supports" in item:
                sup = item.pop("supports")
                item["claims"] = sup if isinstance(sup, list) else ([sup] if sup else [])
            st = item.get("source_type")
            if st == "independent_reviews":
                item["source_type"] = "independent_review"
    # candidates: name → canonical_name, domain → official_domain
    cands = research.get("candidates")
    if isinstance(cands, list):
        for item in cands:
            if not isinstance(item, dict):
                continue
            if "canonical_name" not in item and "name" in item:
                item["canonical_name"] = item.pop("name")
            if "official_domain" not in item and "domain" in item:
                item["official_domain"] = item.pop("domain")
    return research


def handle_competitor_research_finalize(params):
    """竞品研究：校验证据并冻结。subprocess。
    响应附带 competitor-selection.json 内容，免去 read_file 调用。

    容错（只补写权威/无歧义字段，不降低脚本校验强度）：
    - input_hash：从 prepare 冻结的 input.json 读取（权威值）
    - researched_at：今天（UTC）
    - 常见字段名偏差：id→evidence_id、name→canonical_name 等
    """
    research = params.get("research")
    if research is None:
        research_file = params.get("research_path")
        if not research_file:
            raise KeyError("research / research_path 至少提供一个")
        research = json.loads(Path(research_file).read_text(encoding="utf-8"))
    run_dir = params["run_dir"]
    if isinstance(research, dict):
        # 权威 input_hash：从冻结的 input.json 读取
        try:
            frozen = _read_json(Path(run_dir) / "input.json")
            if frozen.get("input_hash"):
                research["input_hash"] = frozen["input_hash"]
        except (OSError, json.JSONDecodeError):
            pass
        # 权威 researched_at：今天（UTC），格式 YYYY-MM-DD
        research["researched_at"] = date.today().isoformat()
        research = _normalize_research(research)

    research_path = _write_tmp(research)
    r = _run_script(
        _script("overseas-geo-competitor-research", "competitor_research.py"),
        ["finalize", "--run-dir", run_dir, "--research", str(research_path)],
    )
    if r.get("exit_code") == 0:
        sel_path = Path(run_dir) / "competitor-selection.json"
        if sel_path.exists():
            try:
                r["selection"] = json.loads(sel_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return _ok(r)


# ── geo-presales-crawl-integrity ──

def handle_audit_crawl_integrity(params):
    """采集完整性校验。subprocess。

    collect_dir 不存在时（collect_answers 没跑成、或 dry_run 后没执行正式采集）
    视为"采集未发生"而不是"采集有缺陷"，避免下游误判。
    """
    collect_dir = Path(params["collect_dir"])
    if not collect_dir.exists():
        return _ok({
            "exit_code": 0,
            "skipped": True,
            "reason": f"采集目录不存在: {collect_dir}",
            "stdout": "", "stderr": "",
        })
    args = ["--collect-dir", str(collect_dir), "--target", params.get("target", "-")]
    if params.get("out"):
        args += ["--out", params["out"]]
    r = _run_script(_script("geo-presales-crawl-integrity", "audit_crawl_integrity.py"), args)
    return _ok(r)


# ── geo-presales-report-builder ──

def handle_collect_answers(params):
    """Scrapeless 采集。subprocess。"""
    args = [
        "--questions", params["questions_csv"],
        "--out", params["out_dir"],
        "--regions", params["regions"],
    ]
    if params.get("platforms"):
        args += ["--platforms", params["platforms"]]
    if params.get("dry_run"):
        args.append("--dry-run")
    if params.get("check_only"):
        args.append("--check-only")
    if params.get("retry_unrecoverable"):
        args.append("--retry-unrecoverable")
    r = _run_script(_script("geo-presales-report-builder", "collect_answers.py"), args, timeout=3600)
    return _ok(r)


def handle_mine_brand_lexicon(params):
    """品牌词表挖掘。subprocess。"""
    args = ["--collect-dir", params["collect_dir"], "--out", params["out"]]
    if params.get("lexicon"):
        args += ["--lexicon", params["lexicon"]]
    r = _run_script(_script("geo-presales-report-builder", "mine_brand_lexicon.py"), args)
    return _ok(r)


def handle_infer_brand_domains(params):
    """域名推断。subprocess。"""
    r = _run_script(_script("geo-presales-report-builder", "infer_brand_domains.py"), [
        "--collect", params["collect_dir"],
        "--lexicon", params["lexicon"],
        "--out", params["out"],
        "--candidates", params.get("candidates", ""),
    ])
    return _ok(r)


def handle_collect_domain_candidates(params):
    """域名候选收集。subprocess。"""
    r = _run_script(_script("geo-presales-report-builder", "collect_domain_candidates.py"), [
        "--collect", params["collect_dir"],
        "--case", params["case_path"],
        "--cache", params.get("cache", ""),
        "--out", params["out"],
    ])
    return _ok(r)


def handle_build_report_data(params):
    """报告数据生成。subprocess。"""
    # 前置校验：让常见缺件报清晰错误，而不是 Python traceback
    collect_dir = Path(params["collect_dir"])
    if not collect_dir.exists():
        return _err(f"采集目录不存在: {collect_dir}", "MISSING_COLLECT_DIR")
    questions_csv = Path(params["questions_csv"])
    if not questions_csv.exists():
        return _err(f"题库 CSV 不存在: {questions_csv}", "MISSING_QUESTIONS_CSV")
    case_path = Path(params["case_path"])
    if not case_path.exists():
        return _err(f"case.json 不存在: {case_path}", "MISSING_CASE_JSON")

    args = [
        "--collect", params["collect_dir"],
        "--questions", params["questions_csv"],
        "--case", params["case_path"],
        "--out", params["out"],
    ]
    # lexicon 可省略：脚本端 --lexicon 默认 None，允许无词表跑报告
    if params.get("lexicon_path"):
        args += ["--lexicon", params["lexicon_path"]]
    if params.get("domain_cache"):
        args += ["--domain-cache", params["domain_cache"]]
    if params.get("regions"):
        args += ["--regions", params["regions"]]
    if params.get("brand_suffixes"):
        args += ["--brand-suffixes", params["brand_suffixes"]]
    if params.get("topic_labels"):
        args += ["--topic-labels", params["topic_labels"]]
    r = _run_script(_script("geo-presales-report-builder", "build_report_data.py"), args)
    # 内容直返：下游 render_report / attach_sentiment 常常没有额度再 read_file。
    out_path = Path(params["out"])
    if params.get("inline", True) and out_path.exists():
        try:
            r["report_data"] = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            r["report_data_error"] = f"{type(e).__name__}: {e}"
    return _ok(r)


def handle_render_report(params):
    """HTML 渲染。直接调 build_html() 函数。

    report_data 可以直接传对象，也可以只传 report_path 让服务端自己读——
    平台调用次数有限，agent 通常没有余量再 read_file 一次。
    """
    mod = _load_module(_script("geo-presales-report-builder", "render_report.py"))
    report_data = params.get("report_data")
    if report_data is None:
        path = params.get("report_path")
        if not path:
            raise KeyError("report_data / report_path 至少提供一个")
        report_data = json.loads(Path(path).read_text(encoding="utf-8"))
    elif isinstance(report_data, str):
        report_data = json.loads(report_data)
    html = mod.build_html(report_data)
    return _ok({"html": html, "bytes": len(html)})


def handle_verify_report_data(params):
    """独立校验。subprocess。"""
    args = ["--report", params["report_path"], "--collect", params["collect_dir"]]
    if params.get("self_test"):
        args.append("--self-test")
    r = _run_script(_script("geo-presales-report-builder", "verify_report_data.py"), args)
    return _ok(r)


def handle_export_translations(params):
    """导出待翻译。subprocess。"""
    args = ["--collect", params["collect_dir"], "--out-dir", params["out_dir"]]
    if params.get("regions"):
        args += ["--regions", params["regions"]]
    if params.get("batch_size"):
        args += ["--batch-size", str(params["batch_size"])]
    r = _run_script(_script("geo-presales-report-builder", "export_translations.py"), args)
    return _ok(r)


def handle_attach_translations(params):
    """译文回填。subprocess。"""
    args = [
        "--report", params["report_path"],
        "--batches", params["batches_dir"],
        "--out", params["out"],
    ]
    if params.get("allow_partial"):
        args.append("--allow-partial")
    if params.get("strict_length"):
        args.append("--strict-length")
    r = _run_script(_script("geo-presales-report-builder", "attach_translations.py"), args)
    return _ok(r)


def handle_attach_sentiment(params):
    """情感接入。subprocess。"""
    args = [
        "--report", params["report_path"],
        "--units", params["units_path"],
        "--labels-dir", params["labels_dir"],
        "--brands", params["brands"],
        "--target", params["target"],
        "--claims", params["claims_path"],
        "--expected-metrics", params["expected_metrics_path"],
        "--out", params["out"],
    ]
    if params.get("theme_keywords"):
        args += ["--theme-keywords", params["theme_keywords"]]
    r = _run_script(_script("geo-presales-report-builder", "attach_sentiment.py"), args)
    return _ok(r)


def handle_prep_sentiment_handoff(params):
    """情感批次管理。subprocess。"""
    sub = params["subcommand"]  # split / assemble / check-claims
    args = [sub]
    if sub == "split":
        args += ["--units", params["units"], "--brands", params["brands"],
                 "--out-dir", params["out_dir"]]
    elif sub == "assemble":
        args += ["--units", params["units"], "--labels-dir", params["labels_dir"],
                 "--brands", params["brands"], "--out", params["out"]]
    elif sub == "check-claims":
        args += ["--judged", params["judged"], "--claims-dir", params["claims_dir"]]
    r = _run_script(_script("geo-presales-report-builder", "prep_sentiment_handoff.py"), args)
    return _ok(r)


# ── geo-presales-sentiment-judge ──

_SENTIMENT_SCRIPT = "geo-presales-sentiment-judge"

def handle_sentiment_extract(params):
    """情感单元抽取。subprocess。"""
    args = ["extract", "--bank", params["bank_path"], "--crawl-dir", params["collect_dir"],
            "--output", params["output"]]
    if params.get("lexicon"):
        args += ["--lexicon", params["lexicon"]]
    elif params.get("aliases"):
        args += ["--aliases", params["aliases"]]
    if params.get("brand"):
        args += ["--brand", params["brand"]]
    r = _run_script(_script(_SENTIMENT_SCRIPT, "sentiment_sentences.py"), args)
    # 内容直返：agent 要基于 units 做 claim 抽取，省一次 read_file。
    # 平台调用次数有限，这一步必须能从返回值里直接拿到数据。
    out_path = Path(params["output"])
    if params.get("inline", True) and out_path.exists():
        try:
            r["units"] = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            r["units_error"] = f"{type(e).__name__}: {e}"
    return _ok(r)


def handle_claims_cluster_list(params):
    """聚类清单生成。subprocess。"""
    r = _run_script(_script(_SENTIMENT_SCRIPT, "sentiment_sentences.py"), [
        "claims-cluster-list",
        "--input", params["input_path"],
        "--key", params["key"],
        "--output", params["output"],
    ])
    return _ok(r)


def handle_claims_assemble(params):
    """Claim 回装。subprocess。"""
    r = _run_script(_script(_SENTIMENT_SCRIPT, "sentiment_sentences.py"), [
        "claims-assemble",
        "--units", params["units_path"],
        "--claims", params["claims_path"],
        "--claim-attributes", params["claim_attributes_path"],
        "--attribute-themes", params["attribute_themes_path"],
        "--output", params["output"],
    ])
    return _ok(r)


def handle_claims_metrics(params):
    """Claim 统计。subprocess。"""
    r = _run_script(_script(_SENTIMENT_SCRIPT, "sentiment_sentences.py"), [
        "claims-metrics",
        "--claims", params["claims_path"],
        "--brands", params["brands"],
        "--out-metrics", params["out_metrics"],
    ])
    return _ok(r)


# ── geo-presales-report-editor ──

def handle_backend_report(params):
    """后端报告。subprocess，5 个子命令。"""
    sub = params["subcommand"]  # prepare / next-task / submit-task / status / finalize
    args = [sub, "--run-dir", params["run_dir"]]
    if sub == "prepare":
        args += ["--input", params["input_path"]]
    elif sub == "next-task":
        if params.get("inline"):
            args.append("--inline")
        if params.get("all_ready"):
            args.append("--all-ready")
    elif sub == "submit-task":
        args += ["--task-id", params["task_id"], "--result", params["result_path"]]
    r = _run_script(_script("geo-presales-report-editor", "backend_report.py"), args)
    return _ok(r)


# ── geo-presales-report-audit ──

def handle_de_cite_crawl(params):
    """去引用清洗。subprocess。"""
    r = _run_script(_script("geo-presales-report-audit", "de_cite_crawl.py"), [
        "--collect-dir", params["collect_dir"],
        "--out", params["out"],
    ])
    return _ok(r)


def handle_verify_brand_extraction(params):
    """品牌抽取校验。subprocess。"""
    r = _run_script(_script("geo-presales-report-audit", "verify_brand_extraction.py"), [
        "--collect-dir", params["collect_dir"],
        "--lexicon", params["lexicon_path"],
        "--out", params["out"],
    ])
    return _ok(r)


def handle_structured_result_audit(params):
    """结构化结果审计。subprocess。"""
    sub = params["subcommand"]  # prepare / validate / apply
    args = [sub, "--input", params["input_path"]]
    if sub == "prepare":
        args += ["--output", params["output"]]
    elif sub == "validate":
        if params.get("before"):
            args += ["--before", params["before"]]
    elif sub == "apply":
        args += ["--patch", params["patch_path"], "--output", params["output"]]
        if params.get("backup"):
            args += ["--backup", params["backup"]]
    r = _run_script(_script("geo-presales-report-audit", "structured_result_audit.py"), args)
    return _ok(r)


# ── geo-after-sales-prompt-builder ──

def handle_validate_after_sales_set(params):
    """售后词组校验。subprocess。"""
    args = [params["bank_path"]]
    if params.get("monitoring_csv"):
        args.append(params["monitoring_csv"])
    if params.get("previous"):
        args += ["--previous", params["previous"]]
    r = _run_script(_script("geo-after-sales-prompt-builder", "validate_after_sales_set.py"), args)
    return _ok(r)


# ── 通用：读取技能提示词和参考文档 ──

_SKILL_REFERENCES = {
    "geo-presales-eval-case-builder": [
        "references/field-contract.md",
        "references/topic-generation-reference.md",
        "references/customer-confirmation-doc.md",
        "references/competitor-handoff.md",
        "references/output-template.md",
        "../shared/prompt-generation-principles.md",
        "../shared/canonical-intent-mapping.md",
    ],
    "overseas-geo-competitor-research": [
        "references/research-contract.md",
    ],
    "geo-presales-prompt-builder": [
        "references/input-contract.md",
        "references/generation-method.md",
        "references/presales-contract.md",
        "references/quality-gates.md",
        "../shared/prompt-generation-principles.md",
        "../shared/canonical-intent-mapping.md",
    ],
    "geo-presales-crawl-integrity": [
        "references/layer-contract.md",
        "references/defect-catalog.md",
    ],
    "geo-presales-report-builder": [
        "references/report-data-contract.md",
        "references/render-spec.md",
        "../shared/canonical-intent-mapping.md",
    ],
    "geo-presales-sentiment-judge": [
        "references/claim-layer-contract.md",
        "references/judgment-rules.md",
        "../shared/canonical-intent-mapping.md",
    ],
    "geo-presales-report-editor": [
        "references/conclusion-synthesis-guide.md",
        "references/report-upload-csv-contract.md",
        "references/metric-scope-and-copy-contract.md",
        "references/backend-input-contract.md",
        "references/backend-report-task-contract.md",
    ],
    "geo-presales-report-audit": [
        "references/audit-workflow.md",
        "references/structured-result-audit.md",
        "references/raw-crawl-extraction.md",
        "references/badcase-output-contract.md",
    ],
    "geo-after-sales-prompt-builder": [
        "references/after-sales-rules.md",
        "references/representative-library.md",
        "references/client-facing-attribute-pool.md",
        "references/output-contract.md",
        "../shared/prompt-generation-principles.md",
        "../shared/canonical-intent-mapping.md",
    ],
}


def _read_skill_content(skill: str) -> str:
    """读取单个 skill 的 SKILL.md + references，返回拼接文本。失败抛 FileNotFoundError。"""
    skill_dir = SKILLS_ROOT / skill
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"技能不存在: {skill}")
    parts = [skill_md.read_text(encoding="utf-8")]
    for ref in _SKILL_REFERENCES.get(skill, []):
        ref_path = (skill_dir / ref).resolve()
        if ref_path.exists():
            parts.append(f"\n---\n\n# 参考：{ref}\n\n{ref_path.read_text(encoding='utf-8')}")
    return "\n".join(parts)


def handle_read_skill(params):
    """读取指定技能的 SKILL.md + 必要 references，拼成完整提示词。"""
    try:
        return _ok({"content": _read_skill_content(params["skill_name"])})
    except FileNotFoundError as e:
        return _err(str(e), "SKILL_NOT_FOUND")


def handle_read_skills_batch(params):
    """批量读取多个技能的完整提示词。平台侧通用工具有调用次数限制（如 3 次），
    用此工具一次拉取所有需要的 skill 指引，替代多次 read_skill。

    params:
      skills: list[str]  必填，skill id 列表
      include_shared: bool  可选，默认 False。True 时附带 shared/ 下两份共享文档。
    返回:
      {skills: {skill_id: content}, shared: {file: content}?, missing: [skill_id]}
    """
    skills = params.get("skills") or []
    if not isinstance(skills, list) or not skills:
        return _err("params.skills 必须是非空 list", "BAD_PARAMS")

    out, missing = {}, []
    for s in skills:
        try:
            out[s] = _read_skill_content(s)
        except FileNotFoundError:
            missing.append(s)

    data = {"skills": out, "missing": missing}

    if params.get("include_shared"):
        shared_dir = SKILLS_ROOT / "shared"
        shared = {}
        for name in ("prompt-generation-principles.md", "canonical-intent-mapping.md"):
            p = shared_dir / name
            if p.exists():
                shared[name] = p.read_text(encoding="utf-8")
        if shared:
            data["shared"] = shared

    return _ok(data)


def handle_read_reference(params):
    """按需读取单个 references 文件。支持 skill references 和 shared 目录。"""
    skill = params["skill"]
    file = params["file"]
    # shared 目录直接在 skills/ 下，不在某个 skill 的 references/ 下
    if skill == "shared":
        ref_path = (SKILLS_ROOT / "shared" / file).resolve()
    else:
        ref_path = (SKILLS_ROOT / skill / "references" / file).resolve()
    # 安全检查：不允许路径穿越
    if not str(ref_path).startswith(str(SKILLS_ROOT)):
        return _err("路径不合法", "INVALID_PATH")
    if not ref_path.exists():
        return _err(f"文件不存在: {skill}/references/{file}", "NOT_FOUND")
    return _ok({"content": ref_path.read_text(encoding="utf-8")})


def handle_read_file(params):
    """读取本地文件内容。

    只允许读 /tmp 和仓库目录下的文件，防止读取系统敏感文件。
    平台用例：读取 competitor_research_prepare 生成的 research-plan.json 等。
    """
    path_str = params["path"]
    path = Path(path_str).resolve()

    # 安全边界：只允许 /tmp 和仓库目录（用 resolve 后的绝对路径比较，兼容 macOS 的 /private/tmp）
    allowed_roots = [Path("/tmp").resolve(), REPO_ROOT.resolve()]
    if not any(str(path).startswith(str(root)) for root in allowed_roots):
        return _err(f"路径不在允许范围内（只允许 /tmp 和仓库目录）: {path}", "FORBIDDEN_PATH")
    if not path.exists():
        return _err(f"文件不存在: {path}", "FILE_NOT_FOUND")
    if not path.is_file():
        return _err(f"不是文件: {path}", "NOT_A_FILE")

    try:
        content = path.read_text(encoding="utf-8")
        return _ok({"content": content, "path": str(path)})
    except UnicodeDecodeError:
        return _err(f"文件不是文本编码（可能是二进制）: {path}", "NOT_TEXT")


def handle_write_file(params):
    """写文件（用于把 agent 的语义产物落盘，再交给后续工具）。

    params:
      path: str           必填，只允许 /tmp 和仓库目录
      content: str|obj    必填；对象/数组会自动 JSON 序列化（UTF-8, ensure_ascii=False）
      indent: int         可选，默认 2；对象序列化时使用
    返回:
      {path, bytes}
    """
    path_str = params["path"]
    path = Path(path_str).resolve()
    allowed_roots = [Path("/tmp").resolve(), REPO_ROOT.resolve()]
    if not any(str(path).startswith(str(root)) for root in allowed_roots):
        return _err(f"路径不在允许范围内（只允许 /tmp 和仓库目录）: {path}", "FORBIDDEN_PATH")

    content = params.get("content")
    if isinstance(content, (dict, list)):
        content = json.dumps(content, ensure_ascii=False, indent=int(params.get("indent", 2)))
    elif isinstance(content, str):
        stripped = content.strip()
        # 平台可能把对象又序列化成字符串传进来，保持原样写盘即可
        if not stripped:
            return _err("params.content 不能为空", "BAD_PARAMS")
    else:
        return _err("params.content 必须是字符串或对象", "BAD_PARAMS")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return _err(f"写入失败: {e}", "WRITE_FAILED")

    return _ok({"path": str(path), "bytes": len(content.encode("utf-8"))})


def handle_build_question_bank(params):
    """把 v8 题库拼装落盘（agent 侧避免手拼嵌套大 JSON）。

    v8 config 是闭合合同，嵌套 6 层，agent 手工拼 JSON 极易在 attribute_plan /
    quotas / competitor_selection 之间丢一层 } 导致 400 BAD_JSON。

    平台对同一工具最多 3 次调用，所以这里只让 agent 写**一个**扁平 input 文件
    （嵌套 ≤3 层），服务端从这里拆 attribute_plan / questions / config_meta 去
    merge，write_file 只耗 1 次额度。

    params:
      case_path: str    与 case_data 二选一。normalize_case 写出的 case.json 路径
      case_data: dict   与 case_path 二选一。normalize_case 返回的 normalized 对象
                        （通过 $ref 内联传入，避免 write_file 耗一次额度）
      input_path: str   必填，扁平 JSON，含三个键：
                          attribute_plan: list   纯 attribute_plan 数组
                          questions:      list   纯 questions 数组
                          config_meta:    dict   可选，扁平 config 覆盖字段，
                                                 允许 expected_total / quotas /
                                                 generation_stage / locale /
                                                 brand_object_type / competitor_selection 等
                                                 不允许 case_fields / attribute_plan
      out: str          必填，question-bank.json 输出路径
    返回: {path, bytes, question_count, topic_count}
    """
    case_path = params.get("case_path")
    case_data = params.get("case_data")
    input_path = params.get("input_path")
    out_path = params.get("out")
    if not input_path or not out_path:
        raise KeyError("input_path / out 均为必填")
    if not case_path and not case_data:
        raise KeyError("case_path / case_data 二选一必填")

    if case_data is not None:
        if not isinstance(case_data, dict):
            return _err("case_data 必须是对象", "BAD_PARAMS")
    else:
        try:
            case_data = _read_json(Path(case_path))
        except (OSError, json.JSONDecodeError) as e:
            return _err(f"读取 case.json 失败: {e}", "READ_FAILED")

    try:
        agent_input = _read_json(Path(input_path))
    except (OSError, json.JSONDecodeError) as e:
        return _err(f"读取 input 失败: {e}", "READ_FAILED")

    if not isinstance(agent_input, dict):
        return _err("input_path 内容必须是对象 {attribute_plan, questions, config_meta?}", "BAD_PARAMS")

    attribute_plan = agent_input.get("attribute_plan")
    questions = agent_input.get("questions")
    meta = agent_input.get("config_meta") or {}

    if not isinstance(attribute_plan, list):
        return _err("input.attribute_plan 必须是数组", "BAD_PARAMS")
    if not isinstance(questions, list):
        return _err("input.questions 必须是数组", "BAD_PARAMS")
    if not isinstance(meta, dict):
        return _err("input.config_meta 必须是对象", "BAD_PARAMS")

    forbidden = {"case_fields", "attribute_plan"} & set(meta.keys())
    if forbidden:
        return _err(f"config_meta 不允许覆盖: {sorted(forbidden)}", "FORBIDDEN_FIELD")

    # 从 normalize_case 写出的 case.json 提取基础字段。
    # 同时兼容两种结构：
    #   A. normalize_case 的返回：{normalized: {...}} 或直接 {...case_fields...}
    #   B. 已 merge 的 question-bank.json：{schema_version, config: {...}, questions: [...]}
    #      用于 validate 失败后的重建——此时拿旧 bank 的 config 作为 case 数据源
    if isinstance(case_data.get("normalized"), dict):
        normalized = case_data["normalized"]
    elif isinstance(case_data.get("config"), dict) and "case_fields" in case_data.get("config", {}):
        # question-bank.json：config 段就是 normalized 等价物
        normalized = case_data["config"]
    else:
        normalized = case_data
    case_fields = normalized.get("case_fields")
    if not isinstance(case_fields, dict):
        return _err("case.json 缺少 case_fields 对象", "BAD_PARAMS")

    config = {
        "case_fields": case_fields,
        "brand_name": normalized.get("brand_name"),
        "brand_object_type": normalized.get("brand_object_type") or "company",
        "category_label": normalized.get("category_label") or case_fields.get("category", ""),
        "official_domain": normalized.get("official_domain"),
        "derived_field_sources": normalized.get("derived_field_sources"),
        "topics": normalized.get("topics"),
        "attribute_plan": attribute_plan,
        "competitor_selection": normalized.get("competitor_selection"),
        "locale": normalized.get("locale") or "en",
        "generation_stage": normalized.get("generation_stage") or "discovery",
    }

    allowed = {
        "brand_name", "brand_object_type", "category_label", "official_domain",
        "derived_field_sources", "topics", "expected_total", "quotas",
        "competitor_selection", "locale", "generation_stage",
    }
    for k, v in meta.items():
        if k in allowed:
            config[k] = v

    missing = [k for k in ("brand_name", "category_label", "official_domain", "topics") if not config.get(k)]
    if missing:
        return _err(f"config 缺少必填字段: {missing}", "MISSING_FIELD")

    bank = {
        "schema_version": "overseas-geo-question-bank/v8",
        "config": config,
        "questions": questions,
    }

    out = Path(out_path).resolve()
    allowed_roots = [Path("/tmp").resolve(), REPO_ROOT.resolve()]
    if not any(str(out).startswith(str(root)) for root in allowed_roots):
        return _err(f"输出路径不在允许范围: {out}", "FORBIDDEN_PATH")

    text = json.dumps(bank, ensure_ascii=False, indent=2)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except OSError as e:
        return _err(f"写入失败: {e}", "WRITE_FAILED")

    return _ok({
        "path": str(out),
        "bytes": len(text.encode("utf-8")),
        "question_count": len(questions),
        "topic_count": len(config.get("topics") or []),
    })


def handle_export_question_bank_csv(params):
    """把 v8 题库 JSON 导出成上传 CSV。

    params:
      bank_path: str      必填，question-bank.json 路径
      out: str            必填，CSV 输出路径
    返回: {path, rows}

    字段顺序按 presales-contract.md 的固定导出规则；diagnosis_intent 与
    question_types 由 Intent Tag 转写，不要求 agent 手工拼 CSV。
    """
    bank = json.loads(Path(params["bank_path"]).read_text(encoding="utf-8"))
    questions = bank.get("questions") or []
    config = bank.get("config") or {}
    topics = {t.get("topic_id"): t for t in (config.get("topics") or [])}

    intent_map = {
        "discovery": "discovery",
        "competitor": "competitor",
        "verification": "verification",
        "accuracy": "accuracy",
        "evaluation": "evaluation",
        "category awareness": "category_awareness",
    }

    def intent_of(question):
        for tag in question.get("tags") or []:
            if not str(tag).startswith("Intent:"):
                continue
            name = str(tag).split(":", 1)[1].strip().casefold()
            if name in intent_map:
                return intent_map[name]
        return "discovery"

    def types_of(intent):
        if intent in {"discovery"}:
            return "visibility,sentiment"
        if intent in {"competitor", "evaluation"}:
            return "sentiment"
        return "visibility"

    fieldnames = ["query", "question_zh", "topic", "diagnosis_intent",
                  "tags", "question_types", "purchase_intent", "persona_name", "scene_name"]
    rows = []
    for q in questions:
        topic = topics.get(q.get("topic_id")) or {}
        intent = intent_of(q)
        tags = q.get("tags") or []
        short_tags = [t for t in tags if isinstance(t, str) and len(t) < 40][:4]
        rows.append({
            "query": q.get("user_question", ""),
            "question_zh": q.get("zh_translation", ""),
            "topic": topic.get("source_value") or topic.get("topic") or "",
            "diagnosis_intent": intent,
            "tags": ",".join(short_tags),
            "question_types": types_of(intent),
            "purchase_intent": "",
            "persona_name": "",
            "scene_name": "",
        })

    out = Path(params["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return _ok({"path": str(out), "rows": len(rows)})


# ---------------------------------------------------------------- 批量调用
def handle_invoke_batch(params):
    """把多个工具调用打包成一次平台调用。

    平台按"工具调用次数"计费（同一工具 ≤3 次），整条售前链路有 20+ 次业务工具调用，
    逐次调用必然超限。这里用一次 invoke_batch 串起多个工具。

    params:
      calls: list[{tool, params}]      必填，按顺序执行；后续调用可用前序返回值
      stop_on_error: bool              默认 False。True 时遇到第一个失败就停
    返回:
      {results: [{tool, ok, data, error, error_code}], succeeded, failed}

    值占位：后续调用的 params 里可以写 {"$ref": "0.data.run_dir"}，
    引用第 0 个调用的返回。这样"prepare → finalize → normalize_case"可以一次发完。
    """
    calls = params.get("calls")
    if not isinstance(calls, list) or not calls:
        return _err("params.calls 必须是非空 list", "BAD_PARAMS")
    stop_on_error = bool(params.get("stop_on_error"))

    results = []
    succeeded = failed = 0

    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            results.append({"tool": None, "ok": False,
                            "error": "calls 每项必须是 {tool, params} 对象", "error_code": "BAD_PARAMS"})
            failed += 1
            continue
        name = call.get("tool")
        raw_params = call.get("params") or {}
        try:
            raw_params = _deep_parse(_resolve_refs(raw_params, results))
        except ValueError as e:
            results.append({"tool": name, "ok": False, "error": str(e), "error_code": "BAD_REF"})
            failed += 1
            if stop_on_error:
                break
            continue

        handler = TOOLS.get(name)
        if handler is None:
            results.append({"tool": name, "ok": False,
                            "error": f"Unknown tool: {name}", "error_code": "UNKNOWN_TOOL"})
            failed += 1
            if stop_on_error:
                break
            continue

        try:
            out = handler(raw_params)
        except KeyError as e:
            out = _err(f"缺少必填参数: {e.args[0] if e.args else ''}", "MISSING_PARAM")
        except Exception as e:
            out = _err(f"{type(e).__name__}: {e}", "INTERNAL")

        entry = {"tool": name}
        if isinstance(out, dict) and "ok" in out:
            entry.update({"ok": out["ok"], "data": out.get("data"), "error": out.get("error"),
                          "error_code": out.get("error_code")})
        else:
            entry.update({"ok": True, "data": out, "error": None, "error_code": None})
        results.append(entry)

        if entry["ok"]:
            succeeded += 1
        else:
            failed += 1
            if stop_on_error:
                break

    return _ok({"results": results, "succeeded": succeeded, "failed": failed})


def _resolve_refs(value, results):
    """把 {"$ref": "i.a.b"} 替换成第 i 个调用的返回值。"""
    if isinstance(value, dict):
        if set(value.keys()) == {"$ref"}:
            path = str(value["$ref"]).split(".")
            try:
                idx = int(path[0])
            except (ValueError, IndexError):
                raise ValueError(f"$ref 必须以调用序号开头，例如 '0.data.run_dir'，收到 {value['$ref']!r}")
            if idx >= len(results):
                raise ValueError(f"$ref 引用了尚未执行的调用 {idx}（当前已完成 {len(results)} 个）")
            cur = results[idx]
            for key in path[1:]:
                # 很多工具（subprocess 类）把结果放在 stdout 的 JSON 字符串里，
                # 这里每步都尝试把字符串解析成对象，让 $ref 能穿透。
                if isinstance(cur, str):
                    cur = _parse_embedded(cur.strip())
                    if cur is _UNPARSED:
                        raise ValueError(
                            f"$ref {value['$ref']!r} 的 {key!r} 处是普通字符串，不能继续下钻"
                        )
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                elif isinstance(cur, list) and key.isdigit() and int(key) < len(cur):
                    cur = cur[int(key)]
                else:
                    raise ValueError(f"$ref {value['$ref']!r} 在下标 {key!r} 处置空")
            if isinstance(cur, str):
                parsed = _parse_embedded(cur.strip())
                if parsed is not _UNPARSED:
                    cur = parsed
            if cur is None:
                raise ValueError(f"$ref {value['$ref']!r} 解析结果为 null（前序调用可能失败）")
            return cur
        return {k: _resolve_refs(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(item, results) for item in value]
    return value


# ---------------------------------------------------------------- 路由表

TOOLS = {
    # prompt-builder
    "normalize_case": handle_normalize_case,
    "validate_question_bank": handle_validate_question_bank,
    # eval-case-builder
    "validate_case": handle_validate_case,
    # competitor-research
    "competitor_research_prepare": handle_competitor_research_prepare,
    "competitor_research_finalize": handle_competitor_research_finalize,
    # crawl-integrity
    "audit_crawl_integrity": handle_audit_crawl_integrity,
    # report-builder
    "collect_answers": handle_collect_answers,
    "mine_brand_lexicon": handle_mine_brand_lexicon,
    "infer_brand_domains": handle_infer_brand_domains,
    "collect_domain_candidates": handle_collect_domain_candidates,
    "build_report_data": handle_build_report_data,
    "render_report": handle_render_report,
    "verify_report_data": handle_verify_report_data,
    "export_translations": handle_export_translations,
    "attach_translations": handle_attach_translations,
    "attach_sentiment": handle_attach_sentiment,
    "prep_sentiment_handoff": handle_prep_sentiment_handoff,
    # sentiment-judge
    "sentiment_extract": handle_sentiment_extract,
    "claims_cluster_list": handle_claims_cluster_list,
    "claims_assemble": handle_claims_assemble,
    "claims_metrics": handle_claims_metrics,
    # report-editor
    "backend_report": handle_backend_report,
    # report-audit
    "de_cite_crawl": handle_de_cite_crawl,
    "verify_brand_extraction": handle_verify_brand_extraction,
    "structured_result_audit": handle_structured_result_audit,
    # after-sales
    "validate_after_sales_set": handle_validate_after_sales_set,
    # 通用
    "invoke_batch": handle_invoke_batch,
    "write_file": handle_write_file,
    "build_question_bank": handle_build_question_bank,
    "export_question_bank_csv": handle_export_question_bank_csv,
    "read_skill": handle_read_skill,
    "read_skills_batch": handle_read_skills_batch,
    "read_reference": handle_read_reference,
    "read_file": handle_read_file,
}


# ---------------------------------------------------------------- HTTP 服务

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 扁平端点：/api/v1/tools/<tool_name>，body 直接是 params（Dify / 直接 HTTP 调用用）
        if self.path.startswith("/api/v1/tools/"):
            tool_name = self.path[len("/api/v1/tools/"):].strip("/")
            if not tool_name:
                self._send(404, _err("Missing tool name in path", "NOT_FOUND"))
                return
            handler = TOOLS.get(tool_name)
            if handler is None:
                suggestions = difflib.get_close_matches(tool_name, TOOLS.keys(), n=3, cutoff=0.4)
                msg = f"Unknown tool: {tool_name}"
                if suggestions:
                    msg += f"。你是不是想调：{', '.join(suggestions)}？"
                self._send(404, _err(msg, "UNKNOWN_TOOL"))
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw_body.decode("utf-8"))
                except json.JSONDecodeError as e:
                    self._send(400, _err(f"请求体不是合法 JSON: {e}", "BAD_BODY"))
                    return
                if not isinstance(body, dict):
                    self._send(400, _err(f"请求体必须是 JSON 对象，收到 {type(body).__name__}", "BAD_BODY"))
                    return
                params, params_error = _coerce_params(body)
                if params_error:
                    self._send(400, _err(params_error, "BAD_PARAMS"))
                    return
                params = _deep_parse(params)
                result = handler(params)
            except Exception as e:
                traceback.print_exc()
                self._send(500, _err(f"{type(e).__name__}: {e}", "INTERNAL"))
                return
            status = 200 if (isinstance(result, dict) and result.get("ok")) else 400
            self._send(status, result)
            return

        if self.path not in ("/api/v1/invoke", "/api/v1/invoke_gzip"):
            self._send(404, _err(f"Unknown path: {self.path}", "NOT_FOUND"))
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            body = {}
            recovered = False
            if self.path == "/api/v1/invoke_gzip":
                # 平台拼 JSON 字符串时极易出错；gzip 压缩后的字节流没有字符串转义问题
                try:
                    raw_body = gzip.decompress(raw_body)
                    body = json.loads(raw_body.decode("utf-8"))
                except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as e:
                    self._send(400, _err(f"gzip 解压失败或内容不是合法 JSON: {e}", "BAD_GZIP"))
                    return
            elif length:
                text = raw_body.decode("utf-8", errors="replace")
                try:
                    body = json.loads(text)
                except json.JSONDecodeError:
                    body = _recover_body(text)
                    if body is None:
                        raise
                    recovered = True
            if not isinstance(body, dict):
                self._send(400, _err(
                    f"请求体必须是 JSON 对象，收到 {type(body).__name__}", "BAD_BODY"))
                return
            tool = body.get("tool", "")

            # 平台可能把整个 params 或嵌套 JSON 序列化成字符串，自动修复
            params, params_error = _coerce_params(body.get("params", {}))
            if params_error:
                self._send(400, _err(params_error, "BAD_PARAMS"))
                return
            params = _deep_parse(params)

            handler = TOOLS.get(tool)
            if not handler:
                # 拼写建议：difflib 找最相近的 3 个工具名，避免平台 agent 幻觉名字后无所适从
                suggestions = difflib.get_close_matches(tool, TOOLS.keys(), n=3, cutoff=0.4)
                msg = f"Unknown tool: {tool}。可用工具共 {len(TOOLS)} 个，先调 GET /api/v1/tools 获取完整列表。"
                if suggestions:
                    msg += f" 你是不是想调：{', '.join(suggestions)}？"
                self._send(400, _err(msg, "UNKNOWN_TOOL"))
                return

            result = handler(params)
            if recovered and isinstance(result, dict):
                result.setdefault("warnings", []).append(
                    "请求体不是严格合法 JSON（params 字符串未转义/含裸换行），服务端已尽力修复并继续执行。"
                )
            self._send(200, result)

        except json.JSONDecodeError as e:
            snippet = ""
            dump_hint = ""
            try:
                body_text = raw_body.decode("utf-8", errors="replace")
                # 把坏 body 落盘，让排查不用靠报错片段猜——平台拼坏的位置五花八门
                try:
                    import time as _t
                    dump_path = Path(tempfile.gettempdir()) / f"geo-bad-body-{int(_t.time())}.log"
                    dump_path.write_bytes(raw_body)
                    dump_hint = f" 完整请求体已落盘: {dump_path}"
                except OSError:
                    pass
                pos = e.pos if hasattr(e, "pos") else 0
                start = max(0, pos - 60)
                end = min(len(body_text), pos + 60)
                snippet = (
                    f" 出错位置附近（char {pos}）："
                    f"...{body_text[start:pos]!r} 【>>>HERE<<<】 {body_text[pos:end]!r}..."
                )
            except Exception:
                pass
            self._send(400, _err(
                f"Invalid JSON: {e}.{snippet} 提示：请求体必须是合法 JSON，"
                f"请用 JSON 序列化函数（json.dumps / JSON.stringify）从对象生成，不要手工拼字符串。{dump_hint}",
                "BAD_JSON",
            ))
        except FileNotFoundError as e:
            self._send(404, _err(str(e), "FILE_NOT_FOUND"))
        except KeyError as e:
            # 缺少必填参数：给出参数名，按客户端错误返回 400
            missing = e.args[0] if e.args else ""
            self._send(400, _err(
                f"缺少必填参数: {missing}", "MISSING_PARAM"))
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            self._send(500, _err(f"{type(e).__name__}: {e}", "INTERNAL"))

    def do_GET(self):
        if self.path == "/api/v1/tools":
            self._send(200, _ok({"tools": sorted(TOOLS.keys())}))
        elif self.path == "/api/v1/tools/detail":
            # 平台 agent 自发现用：每个工具返回 name + docstring 首行 + 所属分组
            detail = []
            for name in sorted(TOOLS.keys()):
                fn = TOOLS[name]
                doc = (fn.__doc__ or "").strip().splitlines()
                detail.append({
                    "name": name,
                    "summary": doc[0] if doc else "",
                })
            self._send(200, _ok({"tools": detail, "count": len(detail)}))
        elif self.path == "/api/v1/health":
            # 只暴露"有没有配"，绝不返回 key 本身
            self._send(200, _ok({
                "status": "ok",
                "skills_root": str(SKILLS_ROOT),
                "env_file": (REPO_ROOT / ".env").exists(),
                "scrapeless_key_configured": bool(os.environ.get("SCRAPELESS_API_KEY", "").strip()),
                "tools": len(TOOLS),
            }))
        else:
            self._send(404, _err(f"Unknown path: {self.path}", "NOT_FOUND"))

    def _send(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # 简化日志：只打请求行
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def main():
    parser = argparse.ArgumentParser(description="GEO Skills 统一 HTTP API 服务")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    args = parser.parse_args()

    print(f"Skills root: {SKILLS_ROOT}")
    print(f"Tools: {len(TOOLS)} 个")
    print(f"Listening on {args.host}:{args.port}")
    print(f"Health check: GET  /api/v1/health")
    print(f"Tool list:    GET  /api/v1/tools")
    print(f"Invoke:       POST /api/v1/invoke")

    HTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
