#!/usr/bin/env python3
"""写出提示词库的「出题原因」和「提示词优先级」（对客确认 Base，任意客户通用）。

规则见 references/selection-rules.md → 7「品牌明显劣势」「出题原因」和 client-facing-base.md → *提示词库*。
提示词优先级不判，算出来：等于所属切片（矩阵行）的「业务优先级」；题库里这道题记了 `brand_weakness` 的降一档，
低档不再降，验证题不降。出题原因一两句：有降档、假设的写在开头，再写哪类买家在什么处境下问什么、看 AI 什么，
最后接题上的 `reason_note`。证据看「证据」列，行的依据看提示词矩阵，这里不重复。

只认现行结构的 Base：没有属性池表，提示词矩阵有「业务优先级」「业务优先级依据」「目标客户」「意图类型」，
需求信号表叫「需求信号」，提示词库有「提示词优先级」。旧 Base 不迁移，脚本报「不支持的旧结构」并以退出码 2 结束。

用法（在客户目录下跑，lark-cli 只能写当前目录）：
    python3 -I write_prompt_reasons.py --base <token> --bank bank.json --brand Nina [--alias Nbrand] [--noun 工具] [--write]
    python3 -I write_prompt_reasons.py --from-dump <目录> --bank bank.json --brand Nina    # 读 <表名>.ndjson，只预览
多市场每个市场的题库各给一次 --bank。预览产物：--preview out.json（每道题算出的字段）。
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
STEP_DOWN = {"高": "中", "中": "低", "低": "低"}
# 现行结构的提示词矩阵必须有的字段
CURRENT_MATRIX_FIELDS = ("业务优先级", "业务优先级依据", "目标客户", "意图类型")


def text(v):
    if isinstance(v, list):
        return "/".join(str(x.get("text", x.get("name", x.get("id", "")))) if isinstance(x, dict) else str(x)
                        for x in v)
    return "" if v is None else str(v)


def ids(v):
    return [x["id"] for x in (v or []) if isinstance(x, dict) and "id" in x]


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


def load_banks(paths):
    """题库里每道题的 brand_weakness、reason_note，按题号。"""
    notes = {}
    for p in paths:
        for q in json.loads(Path(p).read_text(encoding="utf-8")).get("questions", []):
            notes[q["question_id"]] = {"weakness": (q.get("brand_weakness") or "").strip().rstrip("。"),
                                       "note": (q.get("reason_note") or "").strip().rstrip("。")}
    return notes


def build(matrix, lib, bank, brand, aliases, noun, base_audiences):
    """逐题算出题原因和提示词优先级。返回 (更新, 算不出, 降档题号)。"""
    out, skipped, lowered = {}, [], []
    for r in lib:
        code = text(r.get("编号"))
        sl_ids = ids(r.get("所属切片"))
        if not sl_ids or sl_ids[0] not in matrix:
            skipped.append((code, "没有所属切片"))
            continue
        sl = matrix[sl_ids[0]]
        typ = text(sl.get("意图类型"))  # 类型只有一个来源：所属切片
        tier = text(sl.get("业务优先级"))
        if tier not in ROW_TIERS:
            skipped.append((code, f"所属切片 {text(sl.get('切片编号'))} 没判业务优先级"))
            continue
        if code not in bank:
            skipped.append((code, "题库里没有这个题号（--bank 给全了吗）"))
            continue
        aud = text(sl.get("目标客户"))
        who = "买家" if (not aud or aud in base_audiences) else aud
        scene = text(sl.get("使用场景")).strip().rstrip("。")
        named = next((a for a in aliases if a and a in text(r.get("提示词"))), brand)
        # 约束条件是多选，第一个是主约束
        att = (text(r.get("约束条件")).split("/") or [""])[0] or None
        cond = att or "这一类需求"
        p1 = situation(typ, who, cond, named if typ in ("评估", "验证", "交易", "售后") else brand, noun, att is None)
        if p1 is None:
            skipped.append((code, f"意图类型「{typ}」没有句式"))
            continue
        weak, note = bank[code]["weakness"], bank[code]["note"]
        prio, head = tier, []
        if weak and typ == "验证":
            head.append(f"风险：{weak}。")
        elif weak:
            prio = STEP_DOWN[tier]
            head.append(f"降为{prio}：{weak}。" if prio != tier else f"风险：{weak}。")
            if prio != tier:
                lowered.append(code)
        basis = text(sl.get("业务优先级依据"))
        if "假设" in basis:
            m = re.search(r"假设[:：]([^。；;\n]+)", basis)
            guess = m.group(1).strip() if m else "这个处境有一部分依据是推断"
            head.append(f"假设：{guess}，请品牌方确认。")
        if not any(h.startswith("假设") for h in head) and att is not None and not ids(r.get("证据")):
            head.append("待核实：这道题没有挂买家原话，条件来自调研推断，请品牌方用销售和客服常被问到的问题核对。")
        tail = f"{note}。" if note else ""
        if att is None:
            tail = f"测品类整体格局。{tail}"
        reason = "".join(head) + (f"处境：{scene}。" if scene else "") + p1 + tail
        upd = {}
        if reason != text(r.get("出题原因")):
            upd["出题原因"] = reason
        if prio != text(r.get("提示词优先级")):
            upd["提示词优先级"] = prio
        if upd:
            out[r["record_id"]] = (code, upd)
    return out, skipped, lowered


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--base", help="对客确认 Base 的 token")
    src.add_argument("--from-dump", help="离线目录，含 提示词矩阵/提示词库 .ndjson；只能预览")
    ap.add_argument("--bank", action="append", default=[], required=True,
                    help="题库 JSON（读 brand_weakness、reason_note）；多市场每份各给一次")
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
    lib = get("提示词库")
    if lib and "提示词优先级" not in {k for r in lib for k in r}:
        print("提示词库没有「提示词优先级」字段：先按模板加上（单选 高 / 中 / 低）再跑", file=sys.stderr)
        sys.exit(2)
    base_aud = set(a.base_audience) or {
        collections.Counter(text(r.get("目标客户")) for r in matrix.values() if text(r.get("目标客户"))).most_common(1)[0][0]}

    out, skipped, lowered = build(matrix, lib, load_banks(a.bank), a.brand, [a.brand, *a.alias], a.noun, base_aud)
    if a.preview:
        Path(a.preview).write_text(json.dumps({c: f for c, f in out.values()}, ensure_ascii=False, indent=1))
    print(f"提示词 {len(lib)} 道；要更新 {len(out)} 道；因品牌明显劣势降档 {len(lowered)} 道{('：' + '、'.join(lowered)) if lowered else ''}；"
          f"基础人群按「{'、'.join(sorted(base_aud))}」写成「买家」")
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
