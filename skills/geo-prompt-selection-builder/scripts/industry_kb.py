#!/usr/bin/env python3
"""行业知识档案（3.8.0 起；3.9.0 加品类一层，2026-11-11）：每做完一个客户的选词，把品类层面的经验积累下来，下一个同品类、同行业客户先读。

规则只写高频、容易错的情况；经验随客户增长，存成数据，不写进规则（selection-rules.md 总纲）。
档案只存品类层面的东西，不存品牌名、竞品名、域名、买家原话和客户资料（skill 要推公开仓库、要交给研发平台化）：
  约束条件、目标客户、使用场景、主题名、品类叫法（来自题库 bank.json 的矩阵行和主题）
  渠道效果（来自线上 precollect：哪些评价站、社区采到了、哪些没采到）
条目里含本客户品牌名、品牌别名或竞品名的整条跳过。客户只记品牌名的 SHA-1 前 10 位，用来数「出现在几个客户」。
同一客户同一市场重跑以最近一次为准：先把这次（品牌 × 市场）从所有行业档案里撤掉再并入，换了行业或品类也不会重复计；
同一品牌不同市场分开记、合起来算 1 个客户。没有客户的「品类-」文件随之删除。
写法只差连接词、标点、空格的算同一条（「价格与预算」「价格预算」）。

两层，各管各的：
  品类（英文品类词，如 dash cam）：约束条件、目标客户、使用场景、主题划分、品类叫法都按品类看，生成「品类-<品类>.md」。
  行业（precollect-channels.json 的行业键）：渠道效果按行业看（评价站、社区是按行业选的），外加跨品类、2 个以上客户都出现的条目，
                                         生成「行业-<行业>.md」。
同一条在 2 个及以上客户出现标「通用」，1 次标「单例」。AI 读本行业的「行业-」和最接近本客户品类的「品类-」两份，只当假设级线索，
要用本客户的买家信号核实，不能直接当依据；本客户没有信号的不硬加。

  python3 -I industry_kb.py add --ws <线上工作目录>          线上一轮跑完（runner 成功后自动调）；品类取 plan-checked.json 的 category_en
  python3 -I industry_kb.py add --bank <bank.json> --industry <行业> --category <英文品类词> [--market US] [--brand <品牌>] [--competitor <竞品> …]
  python3 -I industry_kb.py show --industry <行业> [--category <品类>]

数据一个行业一份 <行业>.json；档案目录默认是本 skill 的 references/industry-knowledge/，环境变量 GEO_INDUSTRY_KB 可改。
线上判成「其他」的行业记「其他」，靠品类区分。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SECTIONS = {"constraints": "常见约束条件", "audiences": "目标客户", "scenes": "使用场景", "topics": "主题划分",
            "category_terms": "品类叫法"}
TOP_N = 20


def kb_dir() -> Path:
    raw = os.environ.get("GEO_INDUSTRY_KB", "").strip()
    return Path(raw) if raw else SKILL / "references" / "industry-knowledge"


def _slug(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "-", text.strip()).strip("-") or "未分类"


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def norm_key(name: str) -> str:
    """归一键：忽略连接词、标点、空格和大小写；显示时取最常用的写法。"""
    return re.sub(r"[与和及、/／\s·,，。()（）\-]", "", name).lower()


def norm_category(cat: str) -> str:
    """品类词归一：小写、去标点，每个词去掉复数 s（dash cams → dash cam）。"""
    words = re.findall(r"[a-z0-9]+", str(cat or "").lower())
    keep = ("ss", "us", "is", "os")  # antivirus、analysis、chaos 这类词尾的 s 不是复数
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith(keep) else w for w in words)


def _forbidden(names: list[str]):
    low = [n.lower() for n in names if n and len(n) >= 2]
    return lambda text: any(n in text.lower() for n in low)


def extract(bank: dict, brand: str, competitors: list[str]) -> dict:
    """从题库抽品类层面的条目；含品牌、竞品名的跳过。"""
    bad = _forbidden([brand, *competitors])
    cfg = bank.get("config") or {}
    out: dict[str, set] = {k: set() for k in SECTIONS}
    for s in cfg.get("slices") or []:
        for a in s.get("attributes") or []:
            out["constraints"].add(_clean(a))
        aud = s.get("audience")
        for a in (aud if isinstance(aud, list) else [aud]):
            if a and _clean(a) not in ("通用", "其他"):
                out["audiences"].add(_clean(a))
        if s.get("scene"):
            out["scenes"].add(_clean(s["scene"]))
    for t in cfg.get("topics") or []:
        if t.get("topic"):
            out["topics"].add(_clean(t["topic"]))
    for a in cfg.get("category_aliases") or []:
        out["category_terms"].add(_clean(a))
    return {k: sorted(v for v in vals if v and not bad(v)) for k, vals in out.items()}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _add(lst: list, v) -> None:
    if v and v not in lst:
        lst.append(v)


def merge(industry: str, category: str, market: str, brand: str, items: dict, channels: list[dict]) -> Path:
    d = kb_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_slug(industry)}.json"
    kb = _load(path)
    if kb.get("schema") != 4:  # 旧结构不知道每个客户贡献了哪种写法，重建（回填脚本会重新并入）
        kb = {"schema": 4, "industry": industry, "items": {k: {} for k in SECTIONS}, "channels": {}, "clients": {}}
    category = norm_category(category) or "未分品类"
    who = hashlib.sha1(brand.strip().lower().encode("utf-8")).hexdigest()[:10]
    today = time.strftime("%Y-%m-%d")
    run = f"{who}|{market}"  # 一次 = 品牌 × 市场；同一品牌不同市场分开记，数客户时合并
    for other in d.glob("*.json"):  # 同一品牌同一市场重跑以最近一次为准：先从所有行业撤掉，换了行业也不重复计
        if other != path:
            okb = _load(other)
            if okb.get("schema") == 4 and run in okb.get("clients", {}):
                drop_run(okb, run)
                _save(other, okb)
    drop_run(kb, run)
    kb["clients"][run] = {"who": who, "market": market, "category": category, "updated": today}
    for sec, vals in items.items():
        bucket = kb["items"].setdefault(sec, {})
        for v in vals:
            bucket.setdefault(norm_key(v), {"label": v, "by": {}})["by"][run] = v
    for c in channels:
        e = kb["channels"].setdefault(c["name"], {"ok": [], "failed": []})
        _add(e["ok"] if c["ok"] else e["failed"], run)
    kb["updated"] = today
    _save(path, kb)
    return path


def drop_run(kb: dict, run: str) -> None:
    """把一次（品牌 × 市场）从档案里撤掉；没有客户的条目、渠道一起删。"""
    kb["clients"].pop(run, None)
    for sec in list(kb["items"]):
        for key in [k for k, e in kb["items"][sec].items() if e["by"].pop(run, None) is not None and not e["by"]]:
            del kb["items"][sec][key]
    for name in list(kb["channels"]):
        e = kb["channels"][name]
        for lst in (e["ok"], e["failed"]):
            if run in lst:
                lst.remove(run)
        if not e["ok"] and not e["failed"]:
            del kb["channels"][name]


def _derive(kb: dict) -> None:
    """客户数、写法计数、市场、品类都从 by 和 clients 算，存进 JSON 方便直接看。clients 是去重后的品牌。"""
    cl = kb["clients"]
    for sec in kb["items"].values():
        for e in sec.values():
            e["clients"] = sorted({cl[r]["who"] for r in e["by"]})
            e["names"] = {}
            for n in {cl[r]["who"]: n for r, n in e["by"].items()}.values():  # 同一品牌几个市场只计一次
                e["names"][n] = e["names"].get(n, 0) + 1
            e["label"] = max(e["names"], key=lambda n: (e["names"][n], -len(n)))
            e["markets"] = sorted({cl[w]["market"] for w in e["by"] if cl[w]["market"]})
            e["categories"] = sorted({cl[w]["category"] for w in e["by"]})
    for e in kb["channels"].values():
        e["ok_clients"] = sorted({cl[r]["who"] for r in e["ok"]})
        e["failed_clients"] = sorted({cl[r]["who"] for r in e["failed"]})
        ws = e["ok"] + e["failed"]
        e["markets"] = sorted({cl[w]["market"] for w in ws if cl[w]["market"]})
        e["categories"] = sorted({cl[w]["category"] for w in ws})


def _save(path: Path, kb: dict) -> None:
    _derive(kb)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(kb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    write_md(kb)


HEAD = ("只当假设级线索：标「通用」的在 2 个及以上客户出现过，「单例」只出现过 1 次；都要用本客户的买家信号核实，"
        "不能直接当依据，本客户没有信号的不硬加。括号里是出现过的市场。")


def _line(e: dict, n: int) -> str:
    alias = [x for x in e["names"] if x != e["label"]]
    return (f"- {e['label']}（{'通用' if n >= 2 else '单例'}，{n} 个客户；{'、'.join(e['markets'])}）"
            + (f"；也写作 {'、'.join(alias)}" if alias else ""))


def render_category(kb: dict, cat: str) -> str:
    whos = {c["who"] for c in kb["clients"].values() if c.get("category") == cat}
    lines = [f"# 品类知识：{cat}（行业：{kb['industry']}）", "",
             f"由 `scripts/industry_kb.py` 从 {len(whos)} 个这个品类的客户自动积累，最近更新 {kb.get('updated', '')}。{HEAD}", ""]
    for sec, title in SECTIONS.items():
        rows = [(e, len(set(e["clients"]) & whos)) for e in kb["items"].get(sec, {}).values() if cat in e["categories"]]
        rows = sorted(rows, key=lambda r: (-r[1], r[0]["label"]))
        if not rows:
            continue
        lines.append(f"## {title}")
        lines += [_line(e, n) for e, n in rows[:TOP_N]]
        if len(rows) > TOP_N:
            lines.append(f"- 另有 {len(rows) - TOP_N} 条只列在 JSON 里")
        lines.append("")
    ch = {k: v for k, v in kb["channels"].items() if cat in v.get("categories", [])}
    if ch:
        lines.append("## 渠道效果（线上预采集）")
        lines += [f"- {k}：{len(set(v['ok_clients']) & whos)} 个客户采到、{len(set(v['failed_clients']) & whos)} 个没采到" for k, v in sorted(ch.items())]
        lines.append("")
    return "\n".join(lines)


def render_industry(kb: dict) -> str:
    per: dict[str, set] = {}
    for c in kb["clients"].values():
        per.setdefault(c.get("category", "未分品类"), set()).add(c["who"])
    cats = {k: len(v) for k, v in per.items()}
    n_clients = len({c["who"] for c in kb["clients"].values()})
    lines = [f"# 行业知识：{kb['industry']}", "",
             f"由 `scripts/industry_kb.py` 从 {n_clients} 个客户自动积累，最近更新 {kb.get('updated', '')}。"
             f"约束条件、目标客户、场景、主题先看最接近本客户品类的「品类-」文件；这里只放渠道效果和跨品类都出现的条目。{HEAD}", "",
             "## 已有品类", ""]
    lines += [f"- {c}（{n} 个客户）：品类-{_slug(c)}.md" for c, n in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))]
    lines.append("")
    ch = kb.get("channels") or {}
    if ch:
        lines.append("## 渠道效果（线上预采集，按行业看）")
        for k, v in sorted(ch.items(), key=lambda kv: (-len(kv[1]["ok_clients"]), kv[0])):
            lines.append(f"- {k}：{len(v['ok_clients'])} 个客户采到、{len(v['failed_clients'])} 个没采到（{'、'.join(v['markets'])}）")
        lines.append("")
    cross = []
    for sec, title in SECTIONS.items():
        rows = [e for e in kb["items"].get(sec, {}).values() if len(e["clients"]) >= 2 and len(e["categories"]) >= 2]
        if rows:
            cross.append(f"## 跨品类通用的{title}")
            cross += [_line(e, len(e["clients"])) + f"；品类：{'、'.join(e['categories'])}" for e in
                      sorted(rows, key=lambda e: (-len(e["clients"]), e["label"]))[:TOP_N]]
            cross.append("")
    lines += cross or ["## 跨品类通用的条目", "", "- 暂无（还没有在 2 个以上不同品类的客户里都出现的条目）", ""]
    return "\n".join(lines)


def write_md(kb: dict) -> None:
    d = kb_dir()
    ind = d / f"行业-{_slug(kb['industry'])}.md"
    if kb["clients"]:
        ind.write_text(render_industry(kb), encoding="utf-8")
    elif ind.exists():
        ind.unlink()
    for cat in {c.get("category", "未分品类") for c in kb["clients"].values()}:
        (d / f"品类-{_slug(cat)}.md").write_text(render_category(kb, cat), encoding="utf-8")
    live = {f"品类-{_slug(c['category'])}.md" for f in d.glob("*.json") for c in (_load(f).get("clients") or {}).values()}
    for f in d.glob("品类-*.md"):  # 客户换了品类或撤走后，旧品类文件没有客户了，删掉免得 AI 读到
        if f.name not in live:
            f.unlink()


def channels_from_ws(ws: Path) -> list[dict]:
    summ = _load(ws / "research/precollect/summary.json")
    out = []
    for cat in (summ.get("categories") or {}).values():
        for c in cat.get("channels") or []:
            if c.get("status") == "skipped" or not c.get("name"):
                continue
            got = (c.get("rows") or 0) > 0 or (c.get("pages") or 0) > 0
            out.append({"name": c["name"], "ok": c.get("status") == "ok" and got})
    return out


def add_from_ws(ws: Path) -> Path | None:
    plan = _load(ws / "research/precollect/plan-checked.json")
    industry = str(plan.get("industry") or "").strip()
    if plan.get("source") == "fallback" or not industry:
        return None  # 行业没判出来，不往任何档案里记
    bank = _load(ws / "out/bank.json")
    norm = (_load(ws / "inputs/case-normalized.json").get("normalized") or {})
    brand = norm.get("brand_name") or (bank.get("config") or {}).get("brand_name") or ""
    comps = [c.get("name", "") for c in (norm.get("competitor_selection") or {}).get("formal_competitors") or []]
    comps += [a for a in norm.get("brand_aliases") or [] if a]  # 品牌别名也算品牌名
    market = (_load(ws / "out/result.json").get("market") or "").upper()
    category = plan.get("category_en") or ((bank.get("config") or {}).get("category_aliases") or [""])[0]
    if not bank or not brand:
        return None
    return merge(industry, category, market, brand, extract(bank, brand, comps), channels_from_ws(ws))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("add")
    a1.add_argument("--ws", type=Path, help="线上工作目录（读 out/bank.json、plan-checked.json、precollect summary）")
    a1.add_argument("--bank", type=Path, help="本地题库 bank.json")
    a1.add_argument("--industry", help="本地题库用：precollect-channels.json 的行业键，都不合适写「其他」")
    a1.add_argument("--category", default="", help="本地题库用：英文品类词（买家搜这类产品用的词，如 dash cam）")
    a1.add_argument("--market", default="")
    a1.add_argument("--brand", default="", help="本地题库用：品牌名（只用来去重和过滤，不写进档案）")
    a1.add_argument("--competitor", action="append", default=[], help="本地题库用：竞品名，含竞品名的条目不进档案")
    a2 = sub.add_parser("show")
    a2.add_argument("--industry", required=True)
    a2.add_argument("--category", default="")
    a = ap.parse_args()
    if a.cmd == "show":
        kb = _load(kb_dir() / f"{_slug(a.industry)}.json")
        if not kb:
            print(f"还没有「{a.industry}」的行业知识")
        else:
            print(render_category(kb, norm_category(a.category)) if a.category else render_industry(kb))
        return 0
    if a.ws:
        path = add_from_ws(a.ws.resolve())
        print(f"已并入 {path}" if path else "没有并入：行业没判出来、或缺题库 / 品牌名")
        return 0
    if not (a.bank and a.industry):
        ap.error("给 --ws，或给 --bank 和 --industry（再加 --category）")
    bank = _load(a.bank)
    cfg = bank.get("config") or {}
    brand = a.brand or cfg.get("brand_name") or ""
    if not brand:
        ap.error("题库里没有 config.brand_name，用 --brand 给")
    market = (a.market or (cfg.get("collection_config") or {}).get("market") or "").upper()
    category = a.category or (cfg.get("category_aliases") or [""])[0]
    print(f"已并入 {merge(a.industry, category, market, brand, extract(bank, brand, a.competitor), [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
