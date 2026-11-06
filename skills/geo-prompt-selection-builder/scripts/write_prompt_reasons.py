#!/usr/bin/env python3
"""写出提示词库的「出题原因」（对客确认 Base，任意客户通用）。

规则见 references/client-facing-base.md → *提示词矩阵* / *提示词库*。提示词库没有优先级列，档位只读所属切片
（矩阵行）的「业务优先级」（高 / 中 / 低）。出题原因三部分：这道题测哪类买家在什么处境下的需求 → 依据的需求信号
（按来源类型计数、社区和评价列出站点、一条代表原话）→ 为什么重要（切片「业务优先级依据」原文）。判断只写在矩阵行，
这里不留第二份。

只认现行结构的 Base：没有属性池表，提示词矩阵有「业务优先级」「业务优先级依据」「目标客户」「意图类型」，
需求信号表叫「需求信号」。旧 Base 不迁移，脚本报「不支持的旧结构」并以退出码 2 结束。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I write_prompt_reasons.py --base <token> --brand Nina [--alias Nbrand] [--noun 工具] [--write]
    python3 -I write_prompt_reasons.py --from-dump <目录> --brand Nina    # 读 <表名>.ndjson，只预览
预览产物：--preview out.json（每道题算出的字段）。
退出码：0 正常；1 有题算不出；2 读不到 Base，或是不支持的旧结构 Base。
"""
import argparse
import collections
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROW_TIERS = ("高", "中", "低")
# 现行结构的提示词矩阵必须有的字段
CURRENT_MATRIX_FIELDS = ("业务优先级", "业务优先级依据", "目标客户", "意图类型")
# 来源类型的显示名
SOURCE_LABEL = {"社区": "社区原话", "评价": "用户评价", "搜索联想": "Google 相关搜索",
                "关键词工具": "搜索词", "GSC": "品牌方 Google 搜索后台查询",
                "Bing": "品牌方 Bing 搜索后台查询", "Google Ads": "Google 广告搜索词",
                "电商平台搜索": "电商平台搜索词",
                "Bing AI 检索词": "Bing AI 检索词", "query fan-outs": "AI 检索时拆出的子查询",
                "AI 追问": "AI 回答末尾的追问", "模型建议问题": "AI 推荐的延伸问题",
                "销售": "销售记录", "客服": "客服记录",
                "站内搜索": "站内搜索词", "品牌官网": "品牌官网线索", "竞品官网": "竞品官网线索"}
# 挑代表原话的先后：买家亲口说的在前，AI 检索词最后
SOURCE_RANK = {"社区": 0, "评价": 1, "客服": 2, "销售": 3, "GSC": 4, "Bing": 5,
               "Google Ads": 6, "站内搜索": 7, "电商平台搜索": 8, "搜索联想": 9,
               "关键词工具": 10, "Bing AI 检索词": 11, "query fan-outs": 12, "AI 追问": 12, "模型建议问题": 13,
               "品牌官网": 14, "竞品官网": 14}
SITE_CLUES = {"品牌官网", "竞品官网"}  # 品牌自己写的内容，只计数，不拿来当代表原话（2026-11-05）
SITE_SOURCES = {"社区", "评价"}  # 只给这两类列站点
# 关键词工具按工具分选项；出题原因里合成「搜索词」一类计数
KEYWORD_TOOLS = {"DataForSEO", "Semrush", "Ahrefs", "Similarweb", "Keyword Planner", "Naver"}
# 网址域名 → 站点名（「出处」里有网址时按它认）
SITE_DOMAINS = {"reddit.com": "Reddit", "ptt.cc": "PTT", "dcard.tw": "Dcard", "mobile01.com": "Mobile01",
                "pantip.com": "Pantip", "trustpilot.com": "Trustpilot", "g2.com": "G2", "capterra.com": "Capterra",
                "play.google.com": "Google Play", "apps.apple.com": "App Store", "youtube.com": "YouTube",
                "quora.com": "Quora", "facebook.com": "Facebook", "instagram.com": "Instagram",
                "threads.net": "Threads", "tiktok.com": "TikTok", "x.com": "X", "twitter.com": "X",
                "xiaohongshu.com": "小红书", "zhihu.com": "知乎", "weibo.com": "微博", "bilibili.com": "B站",
                "hardwarezone.com.sg": "HardwareZone", "hardwarezone.com": "HardwareZone", "kin.naver.com": "네이버 지식iN", "blog.naver.com": "네이버 블로그", "cafe.naver.com": "네이버 카페"}
# 通用平台名：出处以它开头就归到这个名字（「PTT Stock 板」→ PTT）
PLATFORMS = ["PTT", "Dcard", "Mobile01", "CMoney", "巴哈姆特", "Reddit", "YouTube", "Quora", "Facebook",
             "Instagram", "Threads", "TikTok", "X", "Twitter", "Trustpilot", "G2", "Capterra", "Amazon",
             "Google Play", "App Store", "小红书", "知乎", "微博", "抖音", "B站", "Pantip",
             "네이버 지식iN", "네이버 블로그", "네이버 카페", "디시인사이드", "블라인드", "클리앙", "뽐뿌", "OKKY"]
NOISE = re.compile(r"[（(][^（）()]*(20\d\d|Suda|原记|按规则|核对)[^（）()]*[)）]")


def text(v):
    if isinstance(v, list):
        return "/".join(str(x.get("text", x.get("name", x.get("id", "")))) if isinstance(x, dict) else str(x)
                        for x in v)
    return "" if v is None else str(v)


def ids(v):
    return [x["id"] for x in (v or []) if isinstance(x, dict) and "id" in x]


def site_of(note: str) -> str:
    """出处认站点：已知网址按域名认 → 各段开头的平台名 → 第一段人写的说明 → 网址的域名。"""
    m = re.search(r"https?://([^/\s)\]]+)", note)
    host = m.group(1).lower().removeprefix("www.") if m else ""
    for dom, name in SITE_DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return name
    if re.match(r"amazon\.", host):
        return "Amazon"
    for part in re.split(r"[｜|]", note):
        for p in PLATFORMS:
            if part.strip().startswith(p):
                return p
    head = re.split(r"[｜|／/]", note, maxsplit=1)[0].strip()
    if head and not head.startswith(("http", "[http")):
        return re.sub(r"\s*板$", "", re.split(r"[（(，,]", head)[0]).strip()[:20]
    return host



def situation(typ, who, cond, brand, noun, baseline):
    """第一部分：这道题测哪类买家在什么处境下的需求。"""
    if typ == "发现":
        if baseline:
            return f"不加任何条件问这一类{noun}，看 AI 默认提到谁。"
        return f"{who}找{noun}时在意「{cond}」，看 AI 的回答里会不会提到 {brand}。"
    if typ == "替代":
        return f"{who}在找现有{noun}之外的选择（{cond}），看 AI 列出的选项里有没有 {brand}。"
    if typ == "对比":
        return f"{who}在 {brand} 和对手之间做选择（{cond}），看 AI 选谁。"
    if typ == "评估":
        return f"{who}点名问 {brand} 适不适合自己（{cond}），看 AI 怎么判断。"
    if typ == "验证":
        return f"{who}点名问 {brand} 靠不靠谱（{cond}），看 AI 怎么说口碑和风险。"
    if typ == "交易":
        return f"{who}准备买（{cond}），看 AI 把人指到哪个渠道、有没有指到 {brand} 官网。"
    if typ == "售后":
        return f"{who}已经在用 {brand}（{cond}），看 AI 回答时会不会引用 {brand} 官网的帮助页、政策说得对不对。"
    if typ == "问题解决":
        return f"{who}在自己想办法解决问题（{cond}），看 AI 回答时会不会引用 {brand} 官网。"
    return None


def source_group(e):
    t = text(e.get("来源类型"))
    return "关键词工具" if t in KEYWORD_TOOLS else t


def evidence_part(rows):
    """第二部分：按来源类型计数，社区和评价列站点，再挑一条代表原话。"""
    cnt, sites = collections.Counter(), collections.defaultdict(set)
    for e in rows:
        t = source_group(e)
        cnt[t] += 1
        where = text(e.get("出处"))
        if t in SITE_SOURCES and where:
            sites[t].add(site_of(where))
    if not cnt:
        return ""
    order = sorted(cnt, key=lambda t: (-cnt[t], SOURCE_RANK.get(t, 9)))
    parts = [f"{SOURCE_LABEL.get(t, t)} {cnt[t]} 条" + (f"（{'、'.join(sorted(sites[t]))}）" if sites[t] else "")
             for t in order]
    # 同一来源类型里有月搜索量的在前
    buyer_rows = [e for e in rows if source_group(e) not in SITE_CLUES]
    rep = sorted(buyer_rows, key=lambda e: (SOURCE_RANK.get(source_group(e), 12),
                                            0 if text(e.get("月搜索量")) else 1))[0] if buyer_rows else {}
    z = (text(rep.get("译文")) or text(rep.get("中文意思")) or text(rep.get("原话"))).strip().rstrip("。？?！!")
    quote = f"，例如「{z[:38]}{'…' if len(z) > 38 else ''}」" if z else ""
    return f"依据：{'、'.join(parts)}{quote}。"


class Lark:
    def __init__(self, base):
        self.base = base  # --table-id 直接传表名，lark-cli 认

    def _json(self, *args, js=None):
        cmd = ["lark-cli", "base", *args, "--base-token", self.base]
        if js is not None:
            cmd += ["--json", json.dumps(js, ensure_ascii=False)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        try:
            out = json.loads(p.stdout)
        except json.JSONDecodeError:
            sys.exit(f"lark-cli 输出无法解析：{args[0]} {p.stdout[:200]} {p.stderr[:200]}")
        if p.returncode or out.get("ok") is False:
            sys.exit(f"lark-cli 失败：{args[0]} {p.stdout[-400:]} {p.stderr[-400:]}")
        return out

    def records(self, table, missing_ok=False):
        with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix=".reasons_tmp_") as d:
            out = Path(d) / "rows.ndjson"
            subprocess.run(["lark-cli", "base", "+record-list", "--base-token", self.base,
                            "--table-id", table, "--format", "ndjson",
                            "--output", str(out), "--overwrite"], capture_output=True, text=True)
            if not out.exists():
                if missing_ok:
                    return None
                print(f"读不到表：{table}", file=sys.stderr)
                sys.exit(2)
            return [json.loads(x) for x in out.read_text().splitlines() if x.strip()]

    def update(self, table, upd):
        items = list(upd.items())
        for i in range(0, len(items), 200):
            self._json("+record-batch-update", "--table-id", table,
                       js={"update_records": dict(items[i:i + 200])})


def load_dump(d, table, missing_ok=False):
    p = Path(d) / f"{table}.ndjson"
    if not p.exists():
        if missing_ok:
            return None
        print(f"读不到：{p}", file=sys.stderr)
        sys.exit(2)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def old_structure(pool, matrix) -> list[str]:
    """旧 Base 的标记：有属性池表，或提示词矩阵缺现行字段。"""
    found = ["有属性池表"] if pool is not None else []
    have = {k for r in matrix.values() for k in r}
    missing = [n for n in CURRENT_MATRIX_FIELDS if n not in have]
    if matrix and missing:
        found.append(f"提示词矩阵缺字段 {'、'.join(missing)}")
    return found


def build(matrix, quotes, lib, brand, aliases, noun, base_audiences):
    """逐题算出题原因。返回 (更新, 算不出)。"""
    out, skipped = {}, []
    for r in lib:
        code = text(r.get("编号"))
        sl_ids = ids(r.get("所属切片"))
        if not sl_ids or sl_ids[0] not in matrix:
            skipped.append((code, "没有所属切片"))
            continue
        sl = matrix[sl_ids[0]]
        typ = text(sl.get("意图类型"))  # 类型只有一个来源：所属切片
        if text(sl.get("业务优先级")) not in ROW_TIERS:
            skipped.append((code, f"所属切片 {text(sl.get('切片编号'))} 没判业务优先级"))
            continue
        why = NOISE.sub("", text(sl.get("业务优先级依据")).split("\n", 1)[0]).strip().rstrip("。；;")
        if not why:
            skipped.append((code, f"所属切片 {text(sl.get('切片编号'))} 没写业务优先级依据"))
            continue
        aud = text(sl.get("目标客户"))
        who = "买家" if (not aud or aud in base_audiences) else aud
        named = next((a for a in aliases if a and a in text(r.get("提示词"))), brand)
        # 约束条件是多选，第一个是主约束
        att = (text(r.get("约束条件")).split("/") or [""])[0] or None
        cond = att or "这一类需求"
        p1 = situation(typ, who, cond, named if typ in ("评估", "验证", "交易", "售后") else brand, noun, att is None)
        if p1 is None:
            skipped.append((code, f"意图类型「{typ}」没有句式"))
            continue
        p2 = evidence_part([quotes[i] for i in ids(r.get("证据")) if i in quotes])
        p3 = f"这个处境：{why}。"
        if att is None:
            p3 = f"测品类整体格局；{p3}"
        reason = f"{p1}{p2}{p3}"
        if reason != text(r.get("出题原因")):
            out[r["record_id"]] = (code, {"出题原因": reason})
    return out, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--base", help="对客确认 Base 的 token")
    src.add_argument("--from-dump", help="离线目录，含 提示词矩阵/需求信号/提示词库 .ndjson；只能预览")
    ap.add_argument("--brand", required=True, help="题面里称呼的品牌或产品名，如 Nina")
    ap.add_argument("--alias", action="append", default=[], help="点名题里可能出现的其他名字（公司名等），可重复")
    ap.add_argument("--noun", default="产品", help="品类名词，写进句子：买家找「工具」时…")
    ap.add_argument("--base-audience", action="append", default=[],
                    help="品类基础人群（目标客户是它时写「买家」）；不给时按矩阵里出现最多的目标客户")
    ap.add_argument("--preview", help="把算出的字段写成 JSON 文件")
    ap.add_argument("--write", action="store_true", help="写回 Base 并回读核对")
    a = ap.parse_args()
    if a.write and not a.base:
        ap.error("--write 只能配 --base")

    lark = Lark(a.base) if a.base else None
    get = lark.records if lark else (lambda t, missing_ok=False: load_dump(a.from_dump, t, missing_ok))
    pool = get("属性池", True)
    matrix = {r["record_id"]: r for r in get("提示词矩阵")}
    old = old_structure(pool, matrix)
    if old:
        print(f"不支持的旧结构 Base（{'；'.join(old)}）：旧 Base 不迁移，不写出题原因", file=sys.stderr)
        sys.exit(2)
    signals = get("需求信号", True)
    if signals is None:
        sys.exit("读不到需求信号表")
    quotes = {r["record_id"]: r for r in signals}
    lib = get("提示词库")
    base_aud = set(a.base_audience) or {
        collections.Counter(text(r.get("目标客户")) for r in matrix.values() if text(r.get("目标客户"))).most_common(1)[0][0]}

    out, skipped = build(matrix, quotes, lib, a.brand, [a.brand, *a.alias], a.noun, base_aud)
    if a.preview:
        Path(a.preview).write_text(json.dumps({c: f for c, f in out.values()}, ensure_ascii=False, indent=1))
    print(f"提示词 {len(lib)} 道；要更新 {len(out)} 道；基础人群按「{'、'.join(sorted(base_aud))}」写成「买家」")
    for c, why in skipped:
        print(f"算不出：{c}：{why}")
    if skipped:
        sys.exit(1)
    if not a.write:
        return
    lark.update("提示词库", {k: f for k, (_, f) in out.items()})
    for _ in range(4):  # 刚写入要等几秒才读得回来
        time.sleep(5)
        back = {r["record_id"]: r for r in lark.records("提示词库")}
        ok = sum(1 for k, (_, f) in out.items() if all(text(back[k].get(x)) == text(v) for x, v in f.items()))
        if ok == len(out):
            break
    print(f"写入并回读一致 {ok} / {len(out)}")
    sys.exit(0 if ok == len(out) else 1)


if __name__ == "__main__":
    main()
