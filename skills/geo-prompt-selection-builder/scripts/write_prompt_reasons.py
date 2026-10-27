#!/usr/bin/env python3
"""写提示词库的「建议优先级」「出题原因」（对客确认 Base，任意客户通用）。

规则见 references/client-facing-attribute-pool.md → *提示词库*：
  - 建议优先级 = 所挂属性的档位（重要性 × 可改变性查表，须与属性池「优先级」一致），
    发现 / 替代题的信源壁垒为「来源追不上」时再降一档；不按受众压档。
  - 出题原因一段话三部分：这道题测哪类买家在什么处境下的需求 → 依据的买家原话
    （按来源类型计数、社区和评价列出站点、一条代表原话）→ 属性为什么是这个档位。
    第三部分直接取属性池「判据与证据」（或「判据」）里带标签的
    「可改变性（中）：…」「相对竞品（持平）：…」两行；判断只写在属性池，这里不留第二份。
  - 「优先级」空着时按建议优先级预填；手改得和建议不一致时，原因结尾写「按规则是 Px。」，
    并保留人写的「改档：理由，定为 Py。」，没写的列出来（check_client_base.py 也会拦）。
脚本算的档位和属性池「优先级」对不上就报错、不写入。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I write_prompt_reasons.py --base <token> --brand Nina [--alias Nbrand] [--noun 工具] [--write]
    python3 -I write_prompt_reasons.py --from-dump <目录> --brand Nina    # 读 <表名>.ndjson，只预览
预览产物：--preview out.json（每道题算出的字段）。
退出码：0 正常；1 档位对不上或有题算不出；2 读不到 Base。
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

TIER = {("高", "高"): "P1", ("高", "中"): "P2", ("高", "低"): "P2",
        ("中", "高"): "P2", ("中", "中"): "P2", ("中", "低"): "P3",
        ("低", "高"): "P3", ("低", "中"): "P3", ("低", "低"): "P3"}
DROP = {"P1": "P2", "P2": "P3", "P3": "P3"}
IMP = {"高": "买家挑{noun}时会因为它直接排除一个选项",
       "中": "买家会拿它比较，但不靠它决定",
       "低": "买家不拿它做取舍"}
SOURCE_LABEL = {"社区": "社区原话", "评价": "应用商店评价", "PAA 与相关搜索": "Google 相关搜索",
                "搜索数据": "搜索词", "GSC": "品牌方 Google 搜索后台查询",
                "销售记录": "销售记录", "客服记录": "客服记录", "站内搜索": "站内搜索词"}
SOURCE_RANK = {"社区": 0, "评价": 1, "客服记录": 2, "销售记录": 3, "GSC": 4, "站内搜索": 5,
               "PAA 与相关搜索": 6, "搜索数据": 7}
SITE_SOURCES = {"社区", "评价"}  # 只给这两类列站点
# 通用平台名：来源说明以它开头就归到这个名字（「PTT Stock 板」→ PTT）
PLATFORMS = ["PTT", "Dcard", "Mobile01", "CMoney", "巴哈姆特", "Reddit", "YouTube", "Quora", "Facebook",
             "Instagram", "Threads", "TikTok", "X", "Twitter", "Trustpilot", "G2", "Capterra", "Amazon",
             "Google Play", "App Store", "小红书", "知乎", "微博", "抖音", "B站", "Pantip",
             "네이버 지식iN", "네이버 블로그", "네이버 카페", "디시인사이드", "블라인드", "클리앙", "뽐뿌", "OKKY"]
LABEL_RE = r"{label}[（(](高|中|低|优势|领先|持平|劣势|待确认)[)）][：:]\s*(.+)"
NOISE = re.compile(r"[（(][^（）()]*(20\d\d|Suda|原记|按规则|核对)[^（）()]*[)）]")
CAP = 120


def text(v):
    if isinstance(v, list):
        return "/".join(str(x.get("text", x.get("name", x.get("id", "")))) if isinstance(x, dict) else str(x)
                        for x in v)
    return "" if v is None else str(v)


def ids(v):
    return [x["id"] for x in (v or []) if isinstance(x, dict) and "id" in x]


def basis(evidence: str, label: str) -> str:
    """属性池判据里「label（值）：…」那一行的正文，去掉日期、改判记录这类内部括注，过长时截到分句。"""
    m = re.search(LABEL_RE.format(label=label), evidence)
    if not m:
        return ""
    line = NOISE.sub("", m.group(2).split("\n", 1)[0]).strip().rstrip("。；;")
    if len(line) > CAP:
        cut = max(line.rfind("；", 0, CAP), line.rfind("。", 0, CAP))
        if cut > 20:
            line = line[:cut]
    return line


def site_of(note: str) -> str:
    head = re.split(r"[｜|／/]", note, maxsplit=1)[0].strip()
    for p in PLATFORMS:
        if head.startswith(p):
            return p
    return re.sub(r"\s*板$", "", head)[:20]


def condition(sl) -> str:
    """切片约束；点名题的「品牌点名：」「公司名点名：」前缀去掉。"""
    c = text(sl.get("约束")).strip()
    return re.sub(r"^[^：:]{0,8}点名[：:]", "", c)

def situation(typ, who, cond, brand, noun, baseline):
    """第一部分：这道题测哪类买家在什么处境下的需求。"""
    if typ == "发现":
        if baseline:
            return f"不加任何条件问这一类{noun}，看 AI 默认推荐谁。"
        return f"{who}找{noun}时在意「{cond}」，看 AI 推荐时会不会列出 {brand}。"
    if typ == "替代":
        return f"{who}在找现有{noun}之外的选择（{cond}），看 AI 列出的选项里有没有 {brand}。"
    if typ == "对比":
        return f"{who}在 {brand} 和对手之间做选择（{cond}），看 AI 选谁。"
    if typ == "验证":
        return f"{who}点名查 {brand}（{cond}），看 AI 知不知道、说得对不对。"
    if typ == "评价":
        return f"{who}点名问 {brand}（{cond}），看 AI 怎么评价。"
    if typ in ("问题解决", "信息"):
        return f"{who}在自己想办法解决问题（{cond}），看 AI 回答时会不会引用 {brand} 官网。"
    if typ == "准确性":
        return f"核对 AI 讲 {brand} 的事实对不对（{cond}）。"
    if typ == "品类认知":
        return f"{who}还在弄清这一类{noun}是什么（{cond}），看 AI 怎么讲这个品类。"
    return None


def evidence_part(rows):
    """第二部分：按来源类型计数，社区和评价列站点，再挑一条代表原话。"""
    cnt, sites = collections.Counter(), collections.defaultdict(set)
    for e in rows:
        t = text(e.get("来源类型"))
        cnt[t] += 1
        if t in SITE_SOURCES and text(e.get("来源说明")):
            sites[t].add(site_of(text(e.get("来源说明"))))
    if not cnt:
        return ""
    order = sorted(cnt, key=lambda t: (-cnt[t], SOURCE_RANK.get(t, 9)))
    parts = [f"{SOURCE_LABEL.get(t, t)} {cnt[t]} 条" + (f"（{'、'.join(sorted(sites[t]))}）" if sites[t] else "")
             for t in order]
    rep = sorted(rows, key=lambda e: (SOURCE_RANK.get(text(e.get("来源类型")), 9),
                                      {"高": 0, "中": 1, "低": 2}.get(text(e.get("证据可信度")), 3)))[0]
    z = (text(rep.get("中文意思")) or text(rep.get("原话"))).strip().rstrip("。？?！!")
    quote = f"，例如「{z[:38]}{'…' if len(z) > 38 else ''}」" if z else ""
    return f"依据：{'、'.join(parts)}{quote}。"


def attribute_part(a, noun):
    """第三部分：属性为什么是这个档位，判断原文取自属性池。返回 (文字, 缺的标签)。"""
    ev = text(a.get("判据与证据") if "判据与证据" in a else a.get("判据"))
    imp, chg = text(a.get("重要性")), text(a.get("可改变性"))
    name = text(a.get("属性"))
    if name.startswith("品类基线"):
        why = basis(ev, "可改变性")
        handle = re.search(r"处理[：:]\s*(.+)", ev)
        tail = NOISE.sub("", handle.group(1).split("\n", 1)[0]).strip().rstrip("。") if handle else ""
        return "；".join(x for x in (why, tail) if x) + "。", ([] if why else ["可改变性"])
    chg_basis, comp_basis = basis(ev, "可改变性"), basis(ev, "相对竞品")
    missing = [lab for lab, b in (("可改变性", chg_basis), ("相对竞品", comp_basis)) if not b]
    bits = [IMP.get(imp, "").format(noun=noun), chg_basis, comp_basis]
    return f"属性「{name}」：{'；'.join(b for b in bits if b)}。", missing


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

    def records(self, table):
        with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix=".reasons_tmp_") as d:
            out = Path(d) / "rows.ndjson"
            subprocess.run(["lark-cli", "base", "+record-list", "--base-token", self.base,
                            "--table-id", table, "--format", "ndjson",
                            "--output", str(out), "--overwrite"], capture_output=True, text=True)
            if not out.exists():
                print(f"读不到表：{table}", file=sys.stderr)
                sys.exit(2)
            return [json.loads(x) for x in out.read_text().splitlines() if x.strip()]

    def update(self, table, upd):
        items = list(upd.items())
        for i in range(0, len(items), 200):
            self._json("+record-batch-update", "--table-id", table,
                       js={"update_records": dict(items[i:i + 200])})


def load_dump(d, table):
    p = Path(d) / f"{table}.ndjson"
    if not p.exists():
        print(f"读不到：{p}", file=sys.stderr)
        sys.exit(2)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def build(pool, matrix, quotes, lib, brand, aliases, noun, base_audiences):
    """逐题算字段。返回 (更新, 档位冲突, 缺改档理由, 算不出)。"""
    out, bad, need, skipped = {}, [], [], []
    for r in lib:
        code, typ = text(r.get("编号")), text(r.get("提示词类型"))
        sl_ids = ids(r.get("所属切片"))
        if not sl_ids or sl_ids[0] not in matrix:
            skipped.append((code, "没有所属切片"))
            continue
        sl = matrix[sl_ids[0]]
        aud = text(sl.get("受众"))
        who = "买家" if (not aud or aud in base_audiences) else aud
        named = next((a for a in aliases if a and a in text(r.get("提示词"))), brand)
        atts = [pool[i] for i in ids(sl.get("属性关联")) if i in pool]
        att = atts[0] if atts else None
        baseline = att is None or text(att.get("属性")).startswith("品类基线")
        p1 = situation(typ, who, condition(sl), named if typ in ("验证", "准确性") else brand, noun, baseline)
        if p1 is None:
            skipped.append((code, f"提示词类型「{typ}」没有句式"))
            continue
        p2 = evidence_part([quotes[i] for i in ids(r.get("证据")) if i in quotes])
        if att is None:
            tier, p3 = "待判", "这道题所属切片还没挂属性；宽泛题要挂属性池的「品类基线」行，优先级待判。"
        else:
            tier = TIER.get((text(att.get("重要性")), text(att.get("可改变性"))))
            if tier is None:
                skipped.append((code, f"属性「{text(att.get('属性'))}」重要性或可改变性没填"))
                continue
            pool_tier = text(att.get("优先级"))
            if pool_tier and pool_tier != tier:
                bad.append((code, text(att.get("属性编号")), tier, pool_tier))
            p3, missing = attribute_part(att, noun)
            if missing:
                skipped.append((code, f"属性「{text(att.get('属性'))}」判据里缺" + "、".join(f"「{m}（值）：…」" for m in missing)))
                continue
            if typ in ("发现", "替代") and text(r.get("信源壁垒")) == "来源追不上":
                tier = DROP[tier]
                p3 += "AI 的推荐依赖品牌进不去的来源，再降一档。"
        fields = {}
        if tier != text(r.get("建议优先级")):
            fields["建议优先级"] = [tier]
        manual = text(r.get("优先级"))
        if not manual and tier != "待判":
            manual = tier
            fields["优先级"] = [tier]
        tail = ""
        if tier != "待判":
            if manual == tier:
                tail = f"所以是 {tier}。"
            else:
                tail = f"按规则是 {tier}。"
                m = re.search(r"改档[：:].*$", text(r.get("出题原因")), re.S)
                if m and f"定为 {manual}" in m.group(0):
                    tail += m.group(0)
                else:
                    need.append((code, tier, manual))
        reason = f"{p1}{p2}{p3}{tail}"
        if reason != text(r.get("出题原因")):
            fields["出题原因"] = reason
        if fields:
            out[r["record_id"]] = (code, fields)
    return out, bad, need, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--base", help="对客确认 Base 的 token")
    src.add_argument("--from-dump", help="离线目录，含 属性池/提示词矩阵/买家原话/提示词库 .ndjson；只能预览")
    ap.add_argument("--brand", required=True, help="题面里称呼的品牌或产品名，如 Nina")
    ap.add_argument("--alias", action="append", default=[], help="点名题里可能出现的其他名字（公司名等），可重复")
    ap.add_argument("--noun", default="产品", help="品类名词，写进句子：买家找「工具」时…")
    ap.add_argument("--base-audience", action="append", default=[],
                    help="品类基础人群（受众是它时写「买家」）；不给时按矩阵里出现最多的受众")
    ap.add_argument("--preview", help="把算出的字段写成 JSON 文件")
    ap.add_argument("--write", action="store_true", help="写回 Base 并回读核对")
    a = ap.parse_args()
    if a.write and not a.base:
        ap.error("--write 只能配 --base")

    lark = Lark(a.base) if a.base else None
    get = lark.records if lark else (lambda t: load_dump(a.from_dump, t))
    pool = {r["record_id"]: r for r in get("属性池")}
    matrix = {r["record_id"]: r for r in get("提示词矩阵")}
    quotes = {r["record_id"]: r for r in get("买家原话")}
    lib = get("提示词库")
    base_aud = set(a.base_audience) or {
        collections.Counter(text(r.get("受众")) for r in matrix.values() if text(r.get("受众"))).most_common(1)[0][0]}

    out, bad, need, skipped = build(pool, matrix, quotes, lib, a.brand, [a.brand, *a.alias], a.noun, base_aud)
    if a.preview:
        Path(a.preview).write_text(json.dumps({c: f for c, f in out.values()}, ensure_ascii=False, indent=1))
    print(f"提示词 {len(lib)} 道；要更新 {len(out)} 道；基础人群按「{'、'.join(sorted(base_aud))}」写成「买家」")
    for c, why in skipped:
        print(f"算不出：{c}：{why}")
    if need:
        print("手改了优先级但还没写改档理由（在出题原因末尾写「改档：理由，定为 Px。」）：", need)
    if bad:
        print("脚本算的档位和属性池「优先级」对不上（题号, 属性, 脚本, 属性池），不写入：", bad)
        sys.exit(1)
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
    print(f"写入并回读一致 {ok} / {len(out)}；预填优先级 {sum(1 for _, f in out.values() if '优先级' in f)} 条")
    sys.exit(0 if ok == len(out) else 1)


if __name__ == "__main__":
    main()
