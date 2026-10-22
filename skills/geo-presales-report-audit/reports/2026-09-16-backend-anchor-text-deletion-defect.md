# 待研发确认：后端品牌抽取疑似沿用「删锚文本」清洗，导致内联品牌提及丢失

记录日期：2026-09-16
状态：待验证（需研发确认后端是否同源）
发现人：本轮 Task 246 报告审计

## 现象

Task 246（Kbrand）报告 JSON 中，`chatgpt` + `wordid 10119`（发现类问题 Q007「营养师指导」）的 `brand_rankings` 只有 `RivalK1`，漏掉 `RivalK2`。

原始 `answer_text` 里该品牌确实存在，位于句首的加粗内联链接中：

```html
<li><p><strong><span class="contents">
  <a class="decorated-link" href="https://www.rival-k2.example/">RivalK2<span …><svg …></svg></span></a>
</span></strong> — certified nutritionists provide ongoing 1:1 consultations and can adjust supplement plans as needs change.</p></li>
<li><p><strong><a class="decorated-link" href="https://rival-k1.example/">RivalK1</a></strong> — emphasizes ongoing progress tracking …</p></li>
```

同一回答里 `RivalK1` 抽取正常，只有同样位于句首链接内的 `RivalK2` 丢失。该回答正文后续还有一句 `Persona and RivalK1 are primarily individualized rather than family nutrition-care platforms.`，两个品牌在这一句中都出现。

## 判定依据

- **生产结果与一手正文不一致**，不是模型输出问题：两个品牌在同一回答、同一句式、同一标记结构中出现，只有一个被抽出。
- **本 skill 的审计层已确认同一缺陷并修复**：`scripts/structured_result_audit.py` 的 `remove_citations` 原先对去引用后所有剩余 `<a>` 一并连锚文本删除，已在同一天修复为「内联内容锚点解包保留文字」。修复前后对比见 `reports/2026-09-16-inline-anchor-clean-layer-gate.md`。
- **`scripts/de_cite_crawl.py`（原始采集层）不含该缺陷**：它用 `MD_LINK.sub(r"\1", …)` 保留锚文本，实测输出正常。所以缺口落在报告后端自己的清洗/实体抽取环节。

## 影响

内联品牌提及丢失会直接改变客户可见指标：品牌提及率、声量份额、平均提及位置与品牌表达样本都会少算。Task 246 中该记录同时是「16 条品牌提及」中的一条口径来源，漏提会让负向表达比例与提及数同时失真。

同类标记结构在 ChatGPT 回答中常见（句首加粗的实体内联链接），Gemini 购物卡的商品名也以内联链接形式出现在描述句中，所以不是单条偶发。

## 建议排查方向

1. 定位后端把 `answer_text` 转去引用正文的实现，确认是否与 `structured_result_audit.remove_citations` 修复前的行为一致（对剩余 `<a>` 一律连锚文本删除）。
2. 若同源，移植同一判定：把「引用链接」与「句子内的内容链接」分开，后者解包保留文字。
3. 加确定性回归用例，输入即上面这段 HTML，断言正文保留 `RivalK2 — certified nutritionists …`，且 `RivalK2` 出现在品牌序列中。

## 复现样本

| 项 | 值 |
|---|---|
| Task | 246 |
| platform + wordid | `chatgpt` + `10119` |
| 问题 | Which family nutrition supplement brands provide ongoing nutritionist guidance and progress feedback? |
| 当前品牌序列 | `RivalK1` |
| 期望品牌序列 | `RivalK2` → `RivalK1` |
| 原始正文位置 | `<local-path>`，`platform=chatgpt`、`wordid=10119` 的 `answer_text` |
| 审计层修复后一致性 | 修复清洗层后重跑该条，品牌序列即恢复为 `RivalK2` → `RivalK1` |

## 备注

本记录只登记缺陷与复现，不改后端实现。修复归属与排期由研发确认。
