#!/usr/bin/env python3
"""回答正文里的原位商品卡渲染门禁。

扫 report-data.json 里每条回答的 answer_html / answer_zh_html，找出卡片吞进了
不属于卡的内容、或链接写坏的情况。规则与 references/render-spec.md「卡片的组成」一致：

  footnote   卡内出现脚注定义行 [N]: url
  checkbox   卡内出现追问勾选项（☑ ☐ [x] [ ]）
  question   卡内某一段/卖点以问号结尾（追问句被吞进卡）
  lead       卡内出现加粗引导段（**One question:** …）或以冒号结尾的引导句
  untitled   卡没有标题
  badlink    正文任意位置出现尖括号残留的坏链接（href 里含 &lt; / <a 嵌套）
  bangimg    markdown 图没转成卡也没删，渲染成「!链接」

用法：
  python3 scripts/check_inline_cards.py build/report-data.json [更多 report-data.json …]

有任一问题时退出码为 1，并逐条打印 <details 键> <语言> <规则> <片段>。
改 _render_inline_card 或 de_cite 清洗规则后，至少对两份不同品牌的数据各跑一次。
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

CARD_OPEN = '<div class="product-card product-card-inline">'
TAG = re.compile(r"<[^>]+>")
BLOCK = re.compile(r"<(p|li|div)[^>]*>(.*?)</\1>", re.S)
FOOTNOTE = re.compile(r"\[\d+\]:\s*\S")
CHECKBOX = re.compile(r"[☑☐]|\[[ xX]\]")
BOLD_LEAD = re.compile(r"^\s*<strong>[^<]{1,60}:\s*</strong>")
BANG_IMG = re.compile(r"!<a\b")
BAD_LINK = re.compile(r'href="[^"]*(?:&lt;|&gt;|<)|<a\b[^>]*>[^<]*<a\b|\]\(&lt;')


def card_segments(answer_html: str) -> list[str]:
    """按开标签切出每张卡；卡以 </div></div> 收尾（见 _render_inline_card）。"""
    out = []
    pos = 0
    while True:
        start = answer_html.find(CARD_OPEN, pos)
        if start < 0:
            return out
        end = answer_html.find("</div></div>", start)
        end = len(answer_html) if end < 0 else end + len("</div></div>")
        out.append(answer_html[start:end])
        pos = end


def check_card(card: str) -> list[tuple[str, str]]:
    problems = []
    text = html.unescape(TAG.sub(" ", card))
    if FOOTNOTE.search(text):
        problems.append(("footnote", FOOTNOTE.search(text).group(0)))
    if CHECKBOX.search(text):
        problems.append(("checkbox", text[max(0, CHECKBOX.search(text).start() - 20):][:60]))
    if 'class="product-card-title"' not in card:
        problems.append(("untitled", text.strip()[:60]))
    for _, inner in BLOCK.findall(card):
        if "product-card" in inner:  # 外层容器，里面还有块，跳过
            continue
        plain = html.unescape(TAG.sub("", inner)).strip()
        if not plain:
            continue
        if plain.endswith(("?", "？")):
            problems.append(("question", plain[:80]))
        if BOLD_LEAD.match(inner) or (plain.endswith((":", "：")) and len(plain) > 12):
            problems.append(("lead", plain[:80]))
    return problems


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    total_bad = 0
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        details = data.get("details") or {}
        cards = answers = 0
        bad = []
        for key, item in details.items():
            for lang, field in (("en", "answer_html"), ("zh", "answer_zh_html")):
                body = item.get(field) or ""
                if not body:
                    continue
                answers += 1
                for m in BAD_LINK.finditer(body):
                    bad.append((key, lang, "badlink", body[m.start():m.start() + 80]))
                for m in BANG_IMG.finditer(body):
                    bad.append((key, lang, "bangimg", body[m.start():m.start() + 80]))
                for card in card_segments(body):
                    cards += 1
                    for rule, snippet in check_card(card):
                        bad.append((key, lang, rule, snippet))
        print(f"{path}: 回答 {answers} 份，原位卡片 {cards} 张，问题 {len(bad)} 条")
        for key, lang, rule, snippet in bad:
            print(f"  {key}\t{lang}\t{rule}\t{snippet!r}")
        total_bad += len(bad)
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
