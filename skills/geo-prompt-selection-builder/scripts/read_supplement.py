#!/usr/bin/env python3
"""读品牌资料「补充内容」上传的文件，拆成需求信号（只用标准库，不调模型）。

线上表单的「补充内容」是多文件上传（Suda 2026-11-13）：品牌方传 GSC、Bing、Semrush / Ahrefs / Similarweb、
Google Ads 搜索词、站内搜索词这类导出，ChatGPT Business Hub Insights 之类的截图，以及销售、客服整理的常见问题。

- CSV / TSV / Excel（.xlsx）：按表头找查询词列；找到的每行一条信号，含本品牌名或别名的查询去掉（只用非品牌词）。
  来源类型按文件名和表头判：GSC、Bing、Semrush、Ahrefs、Similarweb、Google Ads，判不出的记「品牌方关键词文件」。
  关键词工具的搜索量写进「月搜索量」；GSC、Bing、Google Ads 的展示次数受排名和出价影响，只写进出处
  （demand-side-signals.md「GSC 与搜索词报告怎么用」）。找不到查询词列的表格（销售、客服整理的问题表），
  每行把文字单元格连起来记一条「品牌方资料」；只有网址、数字、日期、短标签（GSC 的国家、设备、网页、图表导出）的行不收。
- TXT / Markdown / Word（.docx）：按段落拆，每段一条「品牌方资料」；标题、短标签这类不成句的段落不收。
- PDF 和图片：这里不读，列进 summary.json 的 to_read，由 agent 直接打开读（能看图的模型），读出的信号登记时
  出处写「补充内容：<文件名>」。
- 读不了的文件（损坏、加密）记进 failed，不中断。

每条信号的出处写「补充内容：<文件名>」，表格加工作表和行号。产物与其他采集脚本同一套列（signals.csv），
另写 summary.json：{files, rows, to_read, failed}。

    python3 -I read_supplement.py <文件…> --out <目录> --brand <品牌> [--alias <别名> …] [--product-line <产品线>]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SIGNAL_FIELDS = ["输入编号", "产品线", "来源类型", "月搜索量", "原话", "译文", "目标客户", "约束条件",
                 "出处", "引用它的问题"]
TABLE_EXT = {".csv", ".tsv", ".xlsx"}
TEXT_EXT = {".txt", ".md", ".docx"}
AGENT_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_EXT = TABLE_EXT | TEXT_EXT | AGENT_EXT
QUERY_HEADERS = ("top queries", "queries", "query", "search query", "search term", "search terms", "keyword",
                 "keywords", "grounding query", "grounding queries", "查询", "热门查询", "关键词", "关键字", "搜索词", "搜索字词")
VOLUME_HEADERS = ("search volume", "volume", "impressions", "展示次数", "展示", "搜索量", "月搜索量")
SOURCE_BY_NAME = (("search console", "GSC"), ("gsc", "GSC"), ("bing", "Bing"), ("semrush", "Semrush"),
                  ("ahrefs", "Ahrefs"), ("similarweb", "Similarweb"), ("google ads", "Google Ads"),
                  ("googleads", "Google Ads"), ("adwords", "Google Ads"))
# 只有关键词工具的量是搜索量，写进「月搜索量」；GSC、Bing、Google Ads 的展示次数受排名和出价影响，只写进出处
VOLUME_SOURCES = {"Semrush", "Ahrefs", "Similarweb"}
_NOISE_CELL = re.compile(r"^(https?://\S+|[\d.,%\s:/-]+)$")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _header_key(value: str) -> str:
    return " ".join(str(value or "").replace("﻿", "").strip().casefold().split())


def _find(headers: list[str], names: tuple[str, ...]) -> int | None:
    keys = [_header_key(h) for h in headers]
    for name in names:
        if name in keys:
            return keys.index(name)
    return None


def _source_type(filename: str, headers: list[str]) -> str:
    low = filename.casefold().replace("_", " ").replace("-", " ")
    for needle, label in SOURCE_BY_NAME:
        if needle in low:
            return label
    keys = {_header_key(h) for h in headers}
    if keys & {"top queries", "queries", "query", "热门查询", "查询"} and keys & {"impressions", "展示次数", "展示"}:
        return "GSC"
    if keys & {"search term", "search terms", "搜索字词"}:
        return "Google Ads"
    return "品牌方关键词文件"


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(path: Path) -> list[tuple[str, list[list[str]]]]:
    """返回 [(工作表名, 行)]；只读单元格的值，公式取缓存结果。"""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        book = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        out = []
        sheets = book.find("m:sheets", NS)
        for sheet in (list(sheets) if sheets is not None else []):
            target = targets.get(sheet.get(f"{{{NS['r']}}}id"), "")
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if member not in z.namelist():
                continue
            rows = []
            for row in ET.fromstring(z.read(member)).iter(f"{{{NS['m']}}}row"):
                cells: dict[int, str] = {}
                for c in row.findall("m:c", NS):
                    kind, v = c.get("t"), c.find("m:v", NS)
                    if kind == "inlineStr":
                        text = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                    elif v is None:
                        continue
                    elif kind == "s":
                        text = shared[int(v.text)]
                    else:
                        text = v.text or ""
                    cells[_col_index(c.get("r") or "A1")] = text
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            out.append((sheet.get("name") or member, rows))
        return out


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter(f"{{{NS['w']}}}t")) for p in root.iter(f"{{{NS['w']}}}p")]


def text_paragraphs(path: Path) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    blocks = re.split(r"\n\s*\n", text) if "\n\n" in text.replace("\r", "") else text.splitlines()
    return blocks


def csv_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "gb18030", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    delim = "\t" if path.suffix.lower() == ".tsv" or sample.count("\t") > sample.count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delim)]


def _header_row(rows: list[list[str]]) -> int:
    """表头不一定在第一行（导出常带说明行）：取前 10 行里第一个能找到查询词列的行，找不到用第一行非空行。"""
    for i, row in enumerate(rows[:10]):
        if _find(row, QUERY_HEADERS) is not None:
            return i
    for i, row in enumerate(rows):
        if any(str(c).strip() for c in row):
            return i
    return 0


def _brand_hit(text: str, brand_terms: list[str]) -> bool:
    low = text.casefold()
    return any(t and re.search(r"(?<![\w])" + re.escape(t.casefold()) + r"(?![\w])", low) for t in brand_terms)


def _is_sentence(text: str) -> bool:
    """像一句话或一个问题：拉丁文字至少 4 个词，或中日韩、泰文等至少 12 个字。国家名、设备名、短标签不算。"""
    if len(re.findall(r"[A-Za-zÀ-ÿĀ-ž\u0400-\u04ff]+", text)) >= 4:
        return True
    return len(re.findall(r"[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text)) >= 12


def table_signals(name: str, sheet: str, rows: list[list[str]], brand_terms: list[str]) -> tuple[list[dict], int]:
    """返回 (信号, 去掉的品牌词条数)。"""
    if not rows:
        return [], 0
    h = _header_row(rows)
    headers = [str(c) for c in rows[h]]
    qi, vi = _find(headers, QUERY_HEADERS), _find(headers, VOLUME_HEADERS)
    where = f"补充内容：{name}" + (f"「{sheet}」" if sheet else "")
    out, dropped = [], 0
    if qi is None:
        for n, row in enumerate(rows[h + 1:], start=h + 2):
            texts = [str(v).strip() for v in row if str(v).strip() and not _NOISE_CELL.match(str(v).strip())]
            if not texts or not any(_is_sentence(t) for t in texts):
                continue
            out.append({"来源类型": "品牌方资料", "原话": "；".join(texts), "出处": f"{where} 第 {n} 行"})
        return out, 0
    source = _source_type(name, headers)
    for n, row in enumerate(rows[h + 1:], start=h + 2):
        query = str(row[qi]).strip() if qi < len(row) else ""
        if not query:
            continue
        if _brand_hit(query, brand_terms):
            dropped += 1
            continue
        vol = str(row[vi]).strip().replace(",", "") if vi is not None and vi < len(row) else ""
        tool = source in VOLUME_SOURCES
        out.append({"来源类型": source, "原话": query, "月搜索量": vol if tool else "",
                    "出处": f"{where} 第 {n} 行" + (f"，展示 {vol}" if vol and not tool else "")})
    return out, dropped


def read_files(files: list[Path], brand_terms: list[str]) -> tuple[list[dict], dict]:
    signals: list[dict] = []
    summary = {"files": [], "to_read": [], "failed": [], "brand_queries_dropped": 0}
    for path in files:
        ext, name = path.suffix.lower(), path.name
        try:
            if ext in AGENT_EXT:
                summary["to_read"].append(str(path))
                summary["files"].append({"file": name, "kind": "交给 agent 读", "rows": 0})
                continue
            if ext not in ALLOWED_EXT:
                raise ValueError(f"不支持的格式 {ext or '（无扩展名）'}")
            got: list[dict] = []
            if ext in (".csv", ".tsv"):
                got, dropped = table_signals(name, "", csv_rows(path), brand_terms)
                summary["brand_queries_dropped"] += dropped
            elif ext == ".xlsx":
                for sheet, rows in xlsx_sheets(path):
                    rows_got, dropped = table_signals(name, sheet, rows, brand_terms)
                    got += rows_got
                    summary["brand_queries_dropped"] += dropped
            else:
                paras = docx_paragraphs(path) if ext == ".docx" else text_paragraphs(path)
                got = [{"来源类型": "品牌方资料", "原话": " ".join(p.split()), "出处": f"补充内容：{name} 第 {i} 段"}
                       for i, p in enumerate(paras, start=1) if _is_sentence(p)]
            signals += got
            summary["files"].append({"file": name, "kind": "程序已读", "rows": len(got)})
        except (OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError) as exc:
            summary["failed"].append({"file": name, "reason": f"{type(exc).__name__}: {str(exc)[:200]}"})
    return signals, summary


def write(out: Path, signals: list[dict], summary: dict, product_line: str, prefix: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    seen, rows = set(), []
    for s in signals:
        key = (s["来源类型"], " ".join(s["原话"].split()).casefold())
        if key in seen:
            continue
        seen.add(key)
        row = dict.fromkeys(SIGNAL_FIELDS, "")
        row.update({"产品线": product_line, **s})
        rows.append(row)
    for i, row in enumerate(rows, 1):
        row["输入编号"] = f"{prefix}{i:04d}"
    with (out / "signals.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SIGNAL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary["rows"] = len(rows)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--brand", required=True, help="品牌名；含品牌名或别名的查询词去掉")
    ap.add_argument("--alias", action="append", default=[], help="品牌别名，可重复")
    ap.add_argument("--product-line", default="")
    ap.add_argument("--id-prefix", default="PB")
    a = ap.parse_args()
    signals, summary = read_files(a.files, [a.brand, *a.alias])
    write(a.out, signals, summary, a.product_line, a.id_prefix)
    print(json.dumps({k: summary[k] for k in ("rows", "brand_queries_dropped", "to_read", "failed")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
