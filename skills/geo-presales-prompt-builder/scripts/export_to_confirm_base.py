"""把售前 v8 题库（含 case_fields 与 attribute_plan）预填进《AI 搜索监测确认表（模板）》的一份副本，供内部参考。

副本不发给客户：售前没有客户逐条确认，表里的分级是我方判断。只写售前有的东西：
  业务范围     ← case_fields、冻结竞品、采集配置（市场、平台）、调研文件的 scope_facts
  买家原话     ← 调研文件的 buyer_quotes
  品牌事实核查 ← 调研文件的 fact_checks
  提示词矩阵   ← attribute_plan：每个 Topic × 属性一行；没有属性的品类基线题挂在空属性行
  提示词库     ← questions；「证据」按调研文件的 prompt_evidence 挂买家原话
基线三表只删【示例】行，不写；需要品牌方提供的数据保持模板原样。调研文件格式见 references/public-research.md。

用法：
  python3 export_to_confirm_base.py <bank.json> [--research r.json] --spec-out spec.json   # 只生成本地规格
  python3 export_to_confirm_base.py <bank.json> --research r.json --copy --market "美国 / 英语"
  python3 export_to_confirm_base.py <bank.json> --research r.json --base <token> --rewrite  # 重写已导出过的内部副本
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from pathlib import Path

# 模板与目标知识库的 token 放在同目录 confirm-base-target.local.json（不进公开仓库），
# 或用环境变量 CONFIRM_BASE_<KEY 大写> 覆盖：template_node / template_base / template_space / default_parent / wiki_url_prefix
_TARGET_FILE = Path(__file__).with_name("confirm-base-target.local.json")
_TARGET = json.loads(_TARGET_FILE.read_text()) if _TARGET_FILE.exists() else {}


def _target(key):
    import os
    return os.environ.get("CONFIRM_BASE_" + key.upper()) or _TARGET.get(key, "")


TEMPLATE_NODE = _target("template_node")
TEMPLATE_BASE = _target("template_base")
TEMPLATE_SPACE = _target("template_space")
DEFAULT_PARENT = _target("default_parent")  # 知识库「客户交付」
WIKI_URL_PREFIX = _target("wiki_url_prefix")
DEFAULT_PLATFORMS = "ChatGPT、Gemini、Google AI Mode、Google AI Overviews"

INTENT_ZH = {"Discovery": "发现", "Competitor": "竞品", "Evaluation": "评价", "Verification": "验证",
             "Accuracy": "准确性", "Category Awareness": "品类认知"}
STAGE_BY_INTENT = {"发现": "发现", "品类认知": "发现", "竞品": "对比", "评价": "验证", "验证": "验证", "准确性": "验证"}
CORE_INTENTS = {"发现", "品类认知"}
AUDIENCE_FIELD = re.compile(r"^(目标客户|目标企业画像) ?\d+$")
# 模板里的选项值；调研文件用别的值会被拦下（受众、涉及品牌、产品线按本 Case 重建，不在此列）
OPTIONS = {"来源类型": {"搜索数据", "PAA 与相关搜索", "评价", "社区", "销售记录", "客服记录", "GSC", "站内搜索", "AI 回答"},
           "旅程阶段": {"发现", "解决问题", "评估", "对比", "替代方案", "验证", "交易", "购后支持"},
           "证据可信度": {"高", "中", "低"}, "品牌方要做什么": {"改官网", "提供材料"}}
WRITE_TABLES = ("业务范围", "买家原话", "品牌事实核查", "提示词矩阵", "提示词库")


def tag_value(q, prefix):
    for t in q.get("tags") or []:
        if t.startswith(prefix + ":"):
            return t.split(":", 1)[1].strip()
    return None


def as_list(v):
    return v if isinstance(v, list) else [v]


def research_rows(research, line, collected_at):
    """调研文件 → 买家原话、品牌事实核查两表的行；选项值和必填链接不合格就停止。"""
    errors, quotes, facts = [], [], []
    for q in research.get("buyer_quotes", []):
        k = q.get("输入编号")
        for col in ("输入编号", "原话", "来源类型", "来源链接"):
            if not q.get(col):
                errors.append(f"买家原话 {k}: 缺 {col}")
        for col in ("来源类型", "旅程阶段", "证据可信度"):
            if q.get(col) and q[col] not in OPTIONS[col]:
                errors.append(f"买家原话 {k}: {col}「{q[col]}」不是模板选项")
        row = {c: v for c, v in q.items() if v not in (None, "", [])}
        for col in ("来源类型", "旅程阶段", "证据可信度", "受众", "涉及品牌"):
            if col in row:
                row[col] = as_list(row[col])
        row["产品线"] = [line]
        row["收集日期"] = (q.get("收集日期") or collected_at) + " 00:00"
        quotes.append(row)
    for f in research.get("fact_checks", []):
        if not f.get("事实项") or not str(f.get("来源页面", "")).startswith("http"):
            errors.append(f"品牌事实核查「{f.get('事实项')}」: 没有来源页面链接，不写这一行")
        if f.get("品牌方要做什么") not in OPTIONS["品牌方要做什么"]:
            errors.append(f"品牌事实核查「{f.get('事实项')}」: 品牌方要做什么只能是 改官网 / 提供材料")
        row = {c: v for c, v in f.items() if v not in (None, "", [])}
        row["品牌方要做什么"] = as_list(row.get("品牌方要做什么"))
        row["产品线"] = [line]
        facts.append(row)
    ids = [q.get("输入编号") for q in quotes]
    if len(ids) != len(set(ids)):
        errors.append("买家原话 输入编号有重复")
    if errors:
        raise SystemExit("调研文件不合格：\n" + "\n".join(errors))
    return quotes, facts


def build_spec(bank, market, platforms, research=None):
    cfg = bank["config"]
    cf = cfg["case_fields"]
    line = cf.get("业务 / 产品名称") or cf["品类"]
    b2b = cf.get("业务模式") == "B2B"
    audiences = [v for k, v in cf.items() if AUDIENCE_FIELD.match(k) and v
                 and k.startswith("目标企业画像" if b2b else "目标客户")]
    if not audiences:
        audiences = [v for k, v in cf.items() if AUDIENCE_FIELD.match(k) and v]
    base_audience = audiences[0] if audiences else cf["品类"] + "买家"
    topic_zh = {t["topic_id"]: (t.get("source_value") or t["topic"]) for t in cfg["topics"]}

    # 业务范围：项目名去掉序号后与模板示例行同名，「为什么重要」从模板示例行带过来
    scope = []
    brand = cf["品牌名称"] + (f"（{cf['公司名']}）" if cf.get("公司名") else "")
    for item, value in [("品牌", brand), ("业务模式", cf.get("业务模式")), ("品类", cf["品类"]),
                        ("市场与语言", market), ("官方域名", cf.get("官方域名")),
                        ("适用边界", cf.get("适用边界")), ("产品线（1）（优先）", line)]:
        if value:
            scope.append({"项目": item, "内容": value})
    scope += [{"项目": f"主要受众（{i}）", "内容": a} for i, a in enumerate(audiences, 1)]
    scope.append({"项目": "平台", "内容": platforms})
    research = research or {}
    if not any(r["项目"] == "品牌与产品别名" for r in research.get("scope_facts", [])):
        scope.append({"项目": "品牌与产品别名", "内容": cf["品牌名称"] + "（售前只核对了品牌名，别名待售后补全）"})
    if cf.get("差异化优势"):
        scope.append({"项目": "差异化优势（1）", "内容": cf["差异化优势"]})
    for i, c in enumerate(cfg.get("competitor_selection", {}).get("formal_competitors", []), 1):
        scope.append({"项目": f"竞品（{i}）",
                      "内容": f"{c['name']}（直接竞品；适用：{line}）：售前冻结竞品，官网 {c.get('official_domain', '')}"})

    scope += [dict(r) for r in research.get("scope_facts", [])]
    quotes, facts = research_rows(research, line, research.get("collected_at", ""))
    evidence = research.get("prompt_evidence", {})
    known = {q["输入编号"] for q in quotes}
    bad = sorted({x for v in evidence.values() for x in v} - known)
    if bad:
        raise SystemExit(f"prompt_evidence 引用了不存在的输入编号：{bad}")

    # 提示词矩阵与提示词库
    questions = bank["questions"]
    matrix, prompts = [], []
    slot = OrderedDict()  # (topic_id, attribute or "") -> matrix row
    ungraded = []

    def add_row(topic_id, attribute, **cols):
        row = {"_key": f"{topic_id}|{attribute}", "切片编号": f"M-{len(matrix) + 1:03d}", "产品线": [line],
               "受众": [cols.pop("受众", base_audience)], **({"属性": attribute} if attribute else {}), **cols}
        matrix.append(row)
        slot[(topic_id, attribute)] = row
        return row

    for plan in cfg.get("attribute_plan", []):
        tid = plan["topic_id"]
        if any(q["topic_id"] == tid and not tag_value(q, "Attribute") for q in questions):
            add_row(tid, "", 备注=f"品类基线（{topic_zh[tid]}）：不带属性条件，测 AI 无条件列出哪些品牌")
        for tier in ("P1", "P2", "P3"):
            for e in plan["priorities"][tier]:
                cols = {"备注": f"售前档位 {tier}。{e['decision_reason']}（来源字段：{e['source_field']}）"}
                if AUDIENCE_FIELD.match(e["source_field"]):
                    cols["受众"] = e["source_value"]
                for src, dst in (("importance", "购买影响"), ("changeability", "可改变性"), ("relative_competitor", "相对竞品")):
                    if e.get(src):
                        cols[dst] = [e[src]]
                if not (e.get("importance") and e.get("changeability")):
                    ungraded.append(f"{topic_zh[tid]} / {e['attribute']}")
                    cols["备注"] = "售前未记重要性与可改变性，本行优先级公式不可信。" + cols["备注"]
                add_row(tid, e["attribute"], **cols)
        for e in plan.get("excluded", []):
            add_row(tid, e["candidate"], 备注=f"售前排除，首期不配提示词：{e['reason']}（来源字段：{e['source_field']}）")

    for q in questions:
        intent = INTENT_ZH.get(tag_value(q, "Intent") or "", "发现")
        attribute = tag_value(q, "Attribute") or ""
        row = slot.get((q["topic_id"], attribute))
        if row is None:
            raise SystemExit(f"{q['question_id']} 的属性「{attribute}」不在 {q['topic_id']} 的 attribute_plan 里")
        row.setdefault("_intents", []).append(intent)
        prompts.append({"编号": q["question_id"], "提示词": q["monitoring_prompt"], "中文含义": q.get("zh_translation", ""),
                        "主题": [topic_zh[q["topic_id"]]], "产品线": [line], "意图": [intent], "状态": ["待审核"],
                        "AI 认知差距": ["待基线"],
                        "库分层": ["核心" if intent in CORE_INTENTS else "监测"], "所属切片": ["@" + row["_key"]],
                        **({"证据": ["@" + x for x in evidence[q["question_id"]]]} if evidence.get(q["question_id"]) else {})})
    for row in matrix:
        intents = row.pop("_intents", [])
        row["旅程阶段"] = [STAGE_BY_INTENT[intents[0]] if intents else "发现"]
        if intents:
            row["目标题数"] = len(intents)
        elif "售前排除" not in row["备注"]:
            row["备注"] = "首期不配提示词：售前题量内未覆盖。" + row["备注"]
    no_evidence = [p["编号"] for p in prompts if "证据" not in p] if research else []
    if market:  # 模板 2026-10-19 起每张表有「市场」字段，一份表可放多个市场
        mname = market.split("/")[0].strip()
        for rows in (scope, quotes, facts, matrix, prompts):
            for r in rows:
                r["市场"] = [mname]
    return {"业务范围": scope, "买家原话": quotes, "品牌事实核查": facts, "提示词矩阵": matrix, "提示词库": prompts,
            "_ungraded": ungraded, "_no_evidence": no_evidence,
            "_title": f"{cf['品牌名称']} 售前分级参考（内部，{market or '市场未填'}）"}


# ---------------------------------------------------------------- 写入飞书
class Lark:
    def __init__(self, base):
        self.base = base
        self.tmp = Path(tempfile.mkdtemp())

    def run(self, *args, payload=None, extra=()):
        cmd = ["lark-cli", "base", *args, "--base-token", self.base, *extra]
        if payload is not None:
            p = self.tmp / "payload.json"
            p.write_text(json.dumps(payload, ensure_ascii=False))
            cmd += ["--json", "@" + str(p)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=self.tmp)
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise SystemExit(f"非 JSON：{args}\n{r.stdout}\n{r.stderr}")
        if not out.get("ok"):
            raise SystemExit(f"失败：{args}\n{json.dumps(out, ensure_ascii=False)[:1500]}")
        return out["data"]

    def records(self, table):
        path = self.tmp / "records.ndjson"
        subprocess.run(["lark-cli", "base", "+record-list", "--base-token", self.base, "--table-id", table,
                        "--format", "ndjson", "--output", str(path), "--overwrite"], capture_output=True, text=True, cwd=self.tmp)
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def fields(self, table):
        d = self.run("+field-list", "--table-id", table)
        return d.get("fields") or d.get("items") or []

    def create(self, table, rows):
        ids = []
        for i in range(0, len(rows), 200):
            d = self.run("+record-batch-create", "--table-id", table, payload={"create_records": rows[i:i + 200]})
            ids += d.get("record_id_list") or [x["record_id"] for x in d.get("records", [])]
        assert len(ids) == len(rows), (table, len(ids), len(rows))
        return ids

    def delete(self, table, ids):
        for i in range(0, len(ids), 100):
            args = ["+record-delete", "--table-id", table]
            for rid in ids[i:i + 100]:
                args += ["--record-id", rid]
            self.run(*args, extra=("--yes",))


def is_example(r):
    vals = [x for v in r.values() for x in (v if isinstance(v, list) else [v])]
    return any(isinstance(x, str) and (x.startswith("【示例】") or x.startswith("EX-")) for x in vals)


def copy_template(title, parent):
    if not (TEMPLATE_NODE and TEMPLATE_SPACE and parent):
        raise SystemExit(f"缺模板或目标知识库 token：在 {_TARGET_FILE.name} 或 CONFIRM_BASE_* 环境变量里配置")
    r = subprocess.run(["lark-cli", "wiki", "+node-copy", "--node-token", TEMPLATE_NODE, "--space-id", TEMPLATE_SPACE,
                        "--target-parent-node-token", parent, "--title", title, "--yes"], capture_output=True, text=True)
    d = json.loads(r.stdout)
    if not d.get("ok"):
        raise SystemExit(f"复制模板失败：{r.stdout}{r.stderr}")
    node = d["data"].get("node") or d["data"]
    return node["node_token"], node["obj_token"]


def deploy(base, spec, rewrite=False, snap_dir=None):
    if TEMPLATE_BASE and base == TEMPLATE_BASE:
        raise SystemExit("不能写模板本身，先复制一份")
    lk = Lark(base)
    for _ in range(30):  # 刚复制的 Base 要等后台复制完成（800004046 base is copying）
        r = subprocess.run(["lark-cli", "base", "+table-list", "--base-token", base], capture_output=True, text=True)
        if '"ok": true' in r.stdout:
            break
        time.sleep(10)
    tables = {t["name"]: t["id"] for t in lk.run("+table-list")["tables"]}

    # 1) 删【示例】行。写入的五张表已有非示例行说明导出过：默认停止；--rewrite 先把这些行存快照再整表清空
    why = {}
    for name in WRITE_TABLES + ("基线读数", "主题汇总", "被引来源"):
        if name not in tables:
            continue
        rows = lk.records(tables[name])
        real = [r for r in rows if not is_example(r) and any(v for k, v in r.items() if k != "record_id")]
        if name in WRITE_TABLES and real:
            if not rewrite:
                raise SystemExit(f"{name} 已有非示例行，停止；这份副本已导出过，确认是内部副本后加 --rewrite")
            snap_dir.mkdir(parents=True, exist_ok=True)
            (snap_dir / f"{base}.{name}.{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=1))
        if name == "业务范围":
            for r in rows:
                key = re.sub(r"（\d+）|（优先）|（后续）", "", str(r.get("项目", "")).replace("【示例】", ""))
                if r.get("为什么重要"):
                    why.setdefault(key, r["为什么重要"])
        drop = [r for r in rows if is_example(r) or (rewrite and name in WRITE_TABLES)]
        lk.delete(tables[name], [r["record_id"] for r in drop])

    # 2) 单选选项换成本 Case 的值
    def want(table, col):
        return sorted({x for r in spec[table] for x in (r.get(col) or [])})
    for table, col in (("业务范围", "市场"), ("买家原话", "市场"), ("品牌事实核查", "市场"), ("提示词矩阵", "市场"), ("提示词库", "市场"),
                       ("提示词矩阵", "产品线"), ("提示词矩阵", "受众"), ("提示词库", "产品线"), ("提示词库", "主题"),
                       ("买家原话", "产品线"), ("买家原话", "受众"), ("买家原话", "涉及品牌"), ("品牌事实核查", "产品线")):
        if not spec[table]:
            continue
        f = next((f for f in lk.fields(tables[table]) if f["name"] == col), None)
        if f is None:  # 2026-10-19 前复制的副本没有「市场」字段
            continue
        lk.run("+field-update", "--table-id", tables[table], "--field-id", f["id"], extra=("--yes",),
               payload={"name": col, "type": "select", "multiple": bool(f.get("multiple")),
                        "options": [{"name": n} for n in want(table, col)]})

    # 3) 写记录；「为什么重要」只写在每类的第一行
    seen = set()
    for r in spec["业务范围"]:
        key = re.sub(r"（\d+）|（优先）|（后续）", "", r["项目"])
        if key in why and key not in seen:
            r["为什么重要"] = why[key]
        seen.add(key)
    lk.create(tables["业务范围"], spec["业务范围"])
    if spec["品牌事实核查"]:
        lk.create(tables["品牌事实核查"], spec["品牌事实核查"])
    qid = dict(zip((q["输入编号"] for q in spec["买家原话"]),
                   lk.create(tables["买家原话"], spec["买家原话"]) if spec["买家原话"] else []))
    mrows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in spec["提示词矩阵"]]
    mid = dict(zip((r["_key"] for r in spec["提示词矩阵"]), lk.create(tables["提示词矩阵"], mrows)))
    prows = []
    for p in spec["提示词库"]:
        row = {**p, "所属切片": [{"id": mid[x[1:]]} for x in p["所属切片"]]}
        if "证据" in p:
            row["证据"] = [{"id": qid[x[1:]]} for x in p["证据"]]
        prows.append(row)
    lk.create(tables["提示词库"], prows)

    # 4) 回读核对
    back = {n: len(lk.records(tables[n])) for n in WRITE_TABLES}
    expect = {n: len(spec[n]) for n in back}
    prompts_back = lk.records(tables["提示词库"])
    linked = sum(1 for r in prompts_back if r.get("所属切片"))
    evid = sum(1 for r in prompts_back if r.get("证据"))
    want_evid = sum(1 for p in spec["提示词库"] if "证据" in p)
    print(json.dumps({"回读行数": back, "应有行数": expect, "已挂切片的提示词": linked, "已挂证据的提示词": evid},
                     ensure_ascii=False))
    if back != expect or linked != len(spec["提示词库"]) or evid != want_evid:
        raise SystemExit("回读与规格不一致")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank")
    ap.add_argument("--market", default="", help="如「美国 / 英语」；写进业务范围「市场与语言」，并把「/」前的市场名写进各表「市场」字段（一份表可放多个市场，见售后 client-facing-attribute-pool.md）")
    ap.add_argument("--platforms", default=DEFAULT_PLATFORMS)
    ap.add_argument("--research", help="售前公开调研文件 presales-public-research/v1")
    ap.add_argument("--rewrite", action="store_true", help="重写已导出过的内部副本：先存快照再清空写入的五张表")
    ap.add_argument("--spec-out")
    ap.add_argument("--base", help="已复制好的空副本 base_token")
    ap.add_argument("--copy", action="store_true", help="先复制模板再写入")
    ap.add_argument("--parent", default=DEFAULT_PARENT, help="副本放在哪个知识库节点下，默认「客户交付」")
    a = ap.parse_args()

    research = json.loads(Path(a.research).read_text()) if a.research else None
    if research and research.get("schema_version") != "presales-public-research/v1":
        raise SystemExit("调研文件 schema_version 应为 presales-public-research/v1")
    spec = build_spec(json.loads(Path(a.bank).read_text()), a.market, a.platforms, research)
    if a.spec_out:
        Path(a.spec_out).write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    print(json.dumps({**{n: len(spec[n]) for n in WRITE_TABLES}, "未分级属性": spec["_ungraded"],
                      "没挂原话的提示词": spec["_no_evidence"]}, ensure_ascii=False))
    base = a.base
    if a.copy:
        node, base = copy_template(spec["_title"], a.parent)
        print(f"已复制：{WIKI_URL_PREFIX}{node}（base {base}）")
    if base:
        deploy(base, spec, a.rewrite, Path(a.bank).resolve().parent / ".snapshots")


if __name__ == "__main__":
    sys.exit(main())
