#!/usr/bin/env python3
"""对客确认 Base 与生成脚本 spec 的逐字段比对。部署前后各跑一次，0 差异才算部署完成。

用法：
    python3 diff_base_against_spec.py --base <base_token> --spec <spec.json> [--tables 提示词矩阵,提示词库]
                                      [--key 提示词矩阵=切片编号 ...] [--alias 监测主题=主题 ...] [--json out.json]

spec 格式：{表名: [行, ...]}，行是字段名 → 值，即生成脚本写入 Base 前的样子：
  - 以 _ 开头的键不比（_key 等内部键）；例外 `_属性名`：按「属性关联」链接到属性池后的「属性」比；
  - 链接字段写成 ["表名:主键值", ...]（如 "提示词矩阵:M-001"），按目标表主键比，不比 record_id；
  - 只比 spec 里出现的字段；线上多出的字段（公式、统计列）不报。
退出码：0 无差异；1 有差异；2 读取失败（读不到线上数据时不会报「无差异」）。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_KEYS = {"提示词矩阵": "切片编号", "提示词库": "编号", "买家原话": "输入编号", "业务范围": "项目",
                "属性池": "属性", "需要品牌方提供的数据": "数据", "品牌事实核查": "事实项",
                "主题": "主题+市场"}  # 「+」连起几个字段当一个主键（主题表一行 = 主题 × 市场）


def keyval(r, k):
    if "+" not in k:
        return norm(r.get(k))
    return "|".join(str(norm(r.get(x))) for x in k.split("+"))
DEFAULT_ALIAS = {"监测主题": "主题"}


def fetch(base, table_id):
    # lark-cli 只允许写到当前目录之下，临时文件放在 cwd 里，用完删掉
    with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix=".diff_tmp_") as d:
        out = Path(d) / "rows.ndjson"
        p = subprocess.run(["lark-cli", "base", "+record-list", "--base-token", base, "--table-id", table_id,
                            "--format", "ndjson", "--output", str(out), "--overwrite"], capture_output=True, text=True)
        if not out.exists():
            raise SystemExit(f"读取失败 {table_id}：{p.stdout[:300]} {p.stderr[:300]}")
        return [json.loads(l) for l in out.read_text().splitlines() if l.strip()]


def tables(base):
    p = subprocess.run(["lark-cli", "base", "+table-list", "--base-token", base], capture_output=True, text=True)
    try:
        return {t["name"]: t["id"] for t in json.loads(p.stdout)["data"]["tables"]}
    except Exception:  # noqa: BLE001
        raise SystemExit(f"读取表清单失败：{p.stdout[:300]} {p.stderr[:300]}")


def norm(v):
    """空值统一成 None；数字统一成数值；字符串列表排序；链接已在外面转成键。"""
    if v in (None, "", [], {}):
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        m = re.fullmatch(r"\[(.+?)\]\((.+?)\)", s)  # 网址字段线上读回来是 [文字](链接)
        if m:
            s = m.group(2)
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T00:00:00(\.0+)?([+-]\d{2}:\d{2}|Z)?", s)  # 日期字段读回来带零点时刻
        if m:
            s = m.group(1)
        try:
            return float(s) if s.replace(".", "", 1).lstrip("-").isdigit() else s
        except ValueError:
            return s
    if isinstance(v, list):
        items = [norm(x) for x in v]
        items = [x for x in items if x is not None]
        if not items:
            return None
        return sorted(items, key=str) if all(isinstance(x, (str, float)) for x in items) else items
    if isinstance(v, dict):
        return v.get("text") or v.get("name") or v.get("id") or json.dumps(v, ensure_ascii=False, sort_keys=True)
    return v


def link_ids(v):
    if not v:
        return []
    v = v if isinstance(v, list) else [v]
    return [x.get("id") if isinstance(x, dict) else x for x in v]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--tables", help="只比这些表，逗号分隔；默认 spec 里所有表")
    ap.add_argument("--key", action="append", default=[], help="表名=主键字段，覆盖默认")
    ap.add_argument("--alias", action="append", default=[], help="spec 字段名=线上字段名")
    ap.add_argument("--json", help="差异明细另存为 JSON")
    a = ap.parse_args()

    spec = json.loads(Path(a.spec).read_text())
    keys = dict(DEFAULT_KEYS, **dict(x.split("=", 1) for x in a.key))
    alias = dict(DEFAULT_ALIAS, **dict(x.split("=", 1) for x in a.alias))
    want = a.tables.split(",") if a.tables else list(spec)
    tids = tables(a.base)

    # 读线上：要比的表，加上链接会指向的表（属性池、买家原话等），用来把 record_id 还原成主键
    need = set(want) | {"属性池"}
    for t in want:
        for r in spec.get(t, []):
            for v in r.values():
                if isinstance(v, list):
                    need |= {x.split(":", 1)[0] for x in v if isinstance(x, str) and ":" in x and x.split(":", 1)[0] in tids}
    live, rid2key = {}, {}
    for t in need:
        if t not in tids:
            continue
        rows = fetch(a.base, tids[t])
        live[t] = rows
        k = keys.get(t)
        for r in rows:
            rid2key[r["record_id"]] = f"{t}:{keyval(r, k)}" if k else r["record_id"]

    report, total = {}, 0
    for t in want:
        if t not in spec:
            continue
        if t not in live:
            report[t] = {"error": "线上没有这张表"}; total += 1
            continue
        k = keys.get(t)
        if not k:
            report[t] = {"error": f"没有主键配置，用 --key {t}=字段名 指定"}; total += 1
            continue
        lrows = {}
        dup = []
        for r in live[t]:
            kv = keyval(r, k)
            if kv in lrows:
                dup.append(kv)
            lrows[kv] = r
        srows = {keyval(r, k): r for r in spec[t]}
        miss = sorted(str(x) for x in set(srows) - set(lrows))
        extra = sorted(str(x) for x in set(lrows) - set(srows))
        diffs = []
        for kv, sr in srows.items():
            lr = lrows.get(kv)
            if lr is None:
                continue
            for f, sv in sr.items():
                if f.startswith("_") and f != "_属性名":
                    continue
                if f == "_属性名":
                    got = [rid2key.get(i, i).split(":", 1)[-1] for i in link_ids(lr.get("属性关联"))]
                    lv, sv2, fname = norm(got), norm(sv), "属性关联"
                    if isinstance(lv, list) and len(lv) == 1:
                        lv = lv[0]
                elif isinstance(sv, list) and sv and all(isinstance(x, str) and ":" in x and x.split(":", 1)[0] in tids for x in sv):
                    lf = alias.get(f, f)
                    lv = norm([rid2key.get(i, i) for i in link_ids(lr.get(lf))])
                    sv2, fname = norm([f"{x.split(':', 1)[0]}:{norm(x.split(':', 1)[1])}" for x in sv]), lf
                else:
                    fname = alias.get(f, f)
                    lv, sv2 = norm(lr.get(fname)), norm([sv] if fname != f and isinstance(sv, str) else sv)
                    if isinstance(sv2, list) and len(sv2) == 1 and not isinstance(lv, list):
                        sv2 = sv2[0]
                    if isinstance(lv, list) and len(lv) == 1 and not isinstance(sv2, list):
                        lv = lv[0]
                if lv != sv2:
                    diffs.append({"主键": kv, "字段": fname, "spec": sv2, "线上": lv})
        n = len(miss) + len(extra) + len(diffs) + len(dup)
        total += n
        report[t] = {"spec 行数": len(srows), "线上行数": len(lrows), "线上缺": miss, "线上多": extra,
                     "主键重复": dup, "字段差异": diffs}
        print(f"== {t}：spec {len(srows)} 行 / 线上 {len(lrows)} 行，差异 {n}")
        for x in miss[:20]:
            print(f"   线上缺  {x}")
        for x in extra[:20]:
            print(f"   线上多  {x}")
        for x in dup[:20]:
            print(f"   主键重复 {x}")
        for d in diffs[:40]:
            print(f"   {d['主键']} · {d['字段']}\n      spec: {str(d['spec'])[:160]}\n      线上: {str(d['线上'])[:160]}")
        if len(diffs) > 40:
            print(f"   ……另有 {len(diffs) - 40} 处，见 --json")
    if a.json:
        Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print(f"合计差异 {total}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
