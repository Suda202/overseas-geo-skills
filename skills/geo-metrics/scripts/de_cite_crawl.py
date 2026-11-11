"""把原始爬虫输出规范化为可审计的回答记录，并做确定性去引用。

这是在「报告 JSON 层」之前的一步：结构化结果审计（structured_result_audit.py）
消费已经带 wordid / brand_rankings 的 JSON；本脚本消费的是采集目录里的原始响应，
产出与采集方无关的正文，供品牌抽取与后续审计使用。

只做确定性清洗，不识别品牌、不判情绪。

用法
    python3 de_cite_crawl.py --collect-dir <采集目录> --question-bank <题库.json> \
        --out <输出>/normalized-answers.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


# 正文引用标记的两种形态，四平台一致
REF_DEF = re.compile(r"^\s*\[\d+\]:\s*\S+.*$", re.M)
REF_MARKER_PAREN = re.compile(r"\(\[[^\]\n]{1,80}\]\[\d+\]\)")
REF_MARKER_BARE = re.compile(r"\[[^\]\n]{1,80}\]\[\d+\]")
# alt 里可能有转义方括号（`![\[Direct from Japan\] RivalO2 … | Shopee](<url>)`），旧写法 `[^\]]*` 在 `\]` 处断开，
# 整段 alt 漏进正文被算成提及（2026-11-11 全库 10,276 条去重回答里 73 条，Obrand 13 条）
IMAGE = re.compile(r"!\[(?:\\.|[^\]\\\n])*\]\([^)\n]*\)")
MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
# 标签名必须紧跟 `<`，免得把「< $100 … >」这类正文吃掉；不限长度：ChatGPT 的 <img> 常超 300 字，
# 它的 title 是被引网页标题（「Bbrand dashcam Pro vs. …」），漏删就会被算成提及
HTML_TAG = re.compile(r"<[A-Za-z/!][^<>]*>")
# 裸网址不是正文提及（www.rival-b2.example 里的 rivalb2 不算）
BARE_URL = re.compile(r"https?://\S+|www\.\S+")
# markdown 反斜杠转义：Gemini 把正文里的标点全转义（「rival-h2\.example」「OrangeTee \& Tie」），
# ChatGPT 也有「Hbrand.com\.」「\$」。不还原就按字面匹配不到带点的品牌名——Hbrand 基线
# Gemini 漏了 74 条 rival-h2.example 提及（2026-10-29）。`|` 不还原：表格里的 `\|` 是单元格内容，
# 还原后会被 blank_merchant_columns 当成分列符。
# Scrapeless 商品卡锚点残留文案，会粘在商品名后面（「DispenserGo」）；报告渲染、词表挖掘都用这一份
PRODUCT_VIEWER_NOISE = "Go to product viewer dialog for this item."

MD_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{}~])")

# 失败页判定统一走同目录 geo_presales_core 的唯一实现，不在下游复刻一份签名表。
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from geo_presales_core.crawler import answer_body, answer_validity  # noqa: E402


def dig(payload: dict, key: str):
    node = payload
    for part in ("task_result", key):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def answer_text(payload: dict, platform: str) -> str:
    """正文字段与报告数据层同一张表（core crawler.ANSWER_FIELD；AI Mode 取 result_text 不取 result_md）。"""
    return answer_body(payload.get("task_result") or {}, platform)


# AI 反问用户、让用户选的追问块不算品牌提及（2026-11-11 Suda 定）：选项里的品牌只是 AI 在问
# 「你用哪个牌子」，不是它推荐或评价了谁。Obrand 不扣时 Tecno、Infinix 提及率 32%，扣后 2%。
# 两步，都只看结构和版式、不看行业：
#   1. ChatGPT 表单：`follow_up_form` 字段渲染进了 result_text（问题标题、`- [x]` 选项、多选的纯文本
#      选项行、`{#if}` 残留、提交按钮）。用字段定位这一段、按位置删，不按选项字符串全文替换——
#      选项里的 Samsung 在正文推荐里也会出现。
#   2. 没有表单字段的普通追问：向用户提问的句子后紧跟 2 条以上短列表项，连问句一起删。
# 旧的「连续复选框行整段删」已撤回：没有表单的回答里它触发 19 次，全是正文自检清单
# （Abrand、Hbrand、Nbrand、Ubrand 的 `- [ ] Confirm …`），表单那部分由第 1 步按字段删。
LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")
ASKS_USER = re.compile(r"\byou\b|\byour\b|\bwhich\b|\bwhat\b|你|您|哪", re.I)
# Markdown 标题里的问句是小节名，后面的列表是正文（安全软件题的「### What problems can they help with?」）
HEADING = re.compile(r"^\s*#")
SHORT_ITEM_WORDS = 5
SHORT_ITEM_CJK = 12


def _is_short_item(text: str) -> bool:
    text = text.replace("*", "").strip()
    if re.search(r"[一-鿿]", text):
        return len(text) <= SHORT_ITEM_CJK
    return len(text.split()) <= SHORT_ITEM_WORDS


def follow_up_form_span(text: str, form) -> tuple[int, int] | None:
    """ChatGPT 追问表单在正文里的起止位置；字段缺失或定位不到时返回 None。

    起点取第一个问题标题的最后一段（真正的提问句）：标题字段偶尔把前面的推荐语也解析进来
    （Obrand 266 份里 16 份，如「My verdict: Get the RivalO2 30W …」），取整段会把推荐删掉。
    终点是提交按钮那一行；按钮之后 ChatGPT 自己写的收尾句保留为正文。
    """
    if not isinstance(form, dict):
        return None
    questions = form.get("questions") or []
    submit = str(form.get("submit_label") or "").strip()
    if not questions or not submit:
        return None
    label = str((questions[0] or {}).get("label") or "")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", label) if p.strip()]
    if not paragraphs:
        return None
    end = text.rfind(submit)
    if end < 0:
        return None
    # 先按整行找：标题可能很短（「Phone」），子串查找会落进后面的「iPhone」选项里
    anchor = re.escape(paragraphs[-1])
    whole_lines = list(re.finditer(rf"(?m)^[ \t]*{anchor}[ \t]*$", text[:end]))
    start = whole_lines[-1].start() if whole_lines else text.rfind(paragraphs[-1], 0, end)
    if start < 0:
        return None
    line_end = text.find("\n", end + len(submit))
    return start, len(text) if line_end < 0 else line_end


def strip_follow_up_form(text: str, form) -> str:
    """删掉 ChatGPT 追问表单渲染进正文的那一段（在原始正文上用，清洗前调用）。"""
    span = follow_up_form_span(text, form)
    return text if span is None else text[:span[0]] + text[span[1]:]


def strip_choice_lists(text: str) -> str:
    """删掉没有表单字段的普通追问选项：向用户提问的句子后面紧跟 2 条以上很短的列表项，
    问句连同列表整段删除。问句须以问号结尾、含 you/which/what/你/哪 等、不是 Markdown 标题。
    只看版式，不看行业。
    """
    lines = text.split("\n")
    drop = set()
    i = 0
    while i < len(lines):
        q = lines[i].replace("*", "").strip()
        if (q.endswith(("?", "？")) and ASKS_USER.search(q)
                and not LIST_ITEM.match(lines[i]) and not HEADING.match(lines[i])):
            j, items = i + 1, []
            while j < len(lines):
                m = LIST_ITEM.match(lines[j])
                if m and _is_short_item(m.group(1)):
                    items.append(j)
                    j += 1
                elif not lines[j].strip() and not items:
                    j += 1
                else:
                    break
            if len(items) >= 2:
                drop.add(i)
                drop.update(items)
            i = max(j, i + 1)
            continue
        i += 1
    return "\n".join(l for k, l in enumerate(lines) if k not in drop)


def strip_citations(text: str, follow_up_form=None) -> str:
    """去掉引用标记与来源名称，保留正文与商品卡可见标题。

    商品卡形如 `| id | goods | price | rating | merchants | picture |`：
    `goods` 列是可见产品名，保留；`merchants` 列是销售渠道，由
    blank_merchant_columns 另行清空，避免渠道名被当成正文品牌。

    follow_up_form 传 ChatGPT task_result 里的同名字段，有它才删得掉表单那一段；
    拿得到 task_result 的调用方都要传，不传只剩普通追问那一步。
    """
    text = strip_follow_up_form(text, follow_up_form)
    text = REF_DEF.sub("", text)
    text = REF_MARKER_PAREN.sub("", text)
    text = REF_MARKER_BARE.sub("", text)
    text = IMAGE.sub("", text)
    text = MD_LINK.sub(r"\1", text)
    text = HTML_TAG.sub(" ", text)
    text = BARE_URL.sub(" ", text)
    # AI Mode 商品表格把这句贴在商品名后（Google NestGo to …），不去掉品牌词边界会断
    text = text.replace(PRODUCT_VIEWER_NOISE, " ")
    # 引用标记剥完再还原转义，免得 `\[` `\]` 还原后拼出假引用标记
    text = MD_ESCAPE.sub(r"\1", text)
    text = strip_choice_lists(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def blank_merchant_columns(markdown: str) -> str:
    """清空商品卡 merchants 列。

    该列只会出现销售渠道（Best Buy，或品牌自营店），不构成采购候选，
    因此不能用来决定一个品牌的首次出现位置。
    """
    lines = markdown.split("\n")
    merchant_index = None
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            merchant_index = None
            out.append(line)
            continue
        cells = stripped.strip("|").split("|")
        if merchant_index is None:
            header = [c.strip().lower() for c in cells]
            if "merchants" in header:
                merchant_index = header.index("merchants")
            elif all(set(c) <= set("-: ") for c in cells):
                continue
        if merchant_index is not None and merchant_index < len(cells):
            cells[merchant_index] = ""
            out.append("|" + "|".join(cells) + "|")
        else:
            out.append(line)
    return "\n".join(out)


def to_plain(markdown: str) -> str:
    text = markdown.replace("**", "").replace("*", "")
    text = re.sub(r"^\s*\|", " ", text, flags=re.M)
    return re.sub(r"[ \t]{2,}", " ", text)


def load_question_index(bank_path: Path) -> dict:
    bank = json.loads(bank_path.read_text())
    topics = {t["topic_id"]: t["topic"] for t in bank["config"].get("topics", [])}
    index = {}
    for q in bank["questions"]:
        prompt = (q.get("monitoring_prompt") or q.get("user_question") or "").strip()
        analysis = q.get("analysis_type", "visibility")
        types = ["visibility", "sentiment"] if analysis == "visibility" else ["sentiment"]
        index[prompt] = {
            "question_id": q["question_id"],
            "topic_id": q.get("topic_id"),
            "topic": topics.get(q.get("topic_id"), q.get("topic_id")),
            "diagnosis_intent": q.get("diagnosis_intent"),
            "question_types": types,
            "analysis_type": analysis,
            "formal_visibility_eligible": q.get("formal_visibility_eligible"),
            "question_en": q.get("user_question", prompt),
            "question_zh": q.get("zh_translation", ""),
        }
    return index


def detect_platforms(collect_dir: Path):
    for child in sorted(collect_dir.iterdir()):
        if child.is_dir() and child.name.startswith("scraper."):
            yield child.name.split(".", 1)[1], child


def normalize(collect_dir: Path, bank_path: Path):
    question_index = load_question_index(bank_path)
    rows, unknown = [], set()
    for platform, platform_dir in detect_platforms(collect_dir):
        for path in sorted(platform_dir.rglob("*.json")):
            raw = json.loads(path.read_text())
            prompt = str(dig(raw, "prompt") or dig(raw, "user_query") or dig(raw, "user_text") or "").strip()
            meta = question_index.get(prompt)
            if meta is None:
                unknown.add(prompt)
                continue
            source = answer_text(raw, platform)
            body = strip_citations(source, dig(raw, "follow_up_form"))
            valid, invalid_code = answer_validity(body)
            rows.append({
                "answer_id": f"{platform}:{meta['question_id']}:{path.stem}",
                "question_id": meta["question_id"],
                "topic": meta["topic"],
                "topic_id": meta["topic_id"],
                "diagnosis_intent": meta["diagnosis_intent"],
                "question_types": meta["question_types"],
                "analysis_type": meta["analysis_type"],
                "formal_visibility_eligible": meta["formal_visibility_eligible"],
                "question_en": meta["question_en"],
                "question_zh": meta["question_zh"],
                "platform": platform,
                "repeat": int(path.stem) if path.stem.isdigit() else path.stem,
                "source_file": str(path),
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "capture_status": raw.get("status"),
                "answer_status": "available" if valid else "unavailable",
                "invalid_code": invalid_code,
                "body_markdown": body,
                "body_ranking": blank_merchant_columns(body),
                "body_plain": to_plain(body),
            })
    if unknown:
        raise SystemExit(
            "以下 prompt 不在题库中，先确认题库版本："
            + "；".join(sorted(unknown)[:5])
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collect-dir", required=True)
    parser.add_argument("--question-bank", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = normalize(Path(args.collect_dir).expanduser().resolve(),
                     Path(args.question_bank).expanduser().resolve())
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    available = [r for r in rows if r["answer_status"] == "available"]
    print(f"rows={len(rows)} available={len(available)} unavailable={len(rows) - len(available)}")
    print("by platform:", dict(Counter(r["platform"] for r in rows)))
    print("by intent:", dict(Counter(r["diagnosis_intent"] for r in rows)))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
