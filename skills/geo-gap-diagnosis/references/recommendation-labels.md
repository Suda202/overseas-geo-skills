# 推荐与准确性标注

给每条回答里的指定品牌标一个推荐状态，并记下关于本品的事实错误。编码沿用 Citation Labs 的答案行为编码（ARB v1.12.2），按我们的用途收成 6 个值。

## 标谁

- 本品，加上该题合并读数里被提及最多的 3 家同类竞品（`label_batches.py prepare` 自动选）。
- 只标正文里出现了的品牌。本品没出现、同类竞品出现了的回答，脚本直接记「应出现而缺席」（Z-GAP），不送模型。

## 6 个值

| 值 | 编码 | 判据 | 例 |
|---|---|---|---|
| 首推 | D-TOP | 明确说它是第一选择、最佳、最推荐（"best overall"、"my top pick"、"go with X"） | "If you want one display, get the CHIGEE AIO-5." |
| 推荐 | D-REC | 推荐给用户选，或列为某场景下的推荐（"best for X"、"a strong option for…"），但不是唯一首选 | "Carpuride W702S Plus is a good pick if you want offline maps." |
| 仅列举 | R-LIST | 出现在名单、表格、事实陈述里，没有让用户选它的话 | 列表第 4 项只写参数 |
| 有条件不推荐 | Q-FIT | 承认是好产品，但因价格、复杂度、规模、兼容性等约束不建议在本题场景用；必须写出约束 | "Great screen, but overkill for short commutes." |
| 劝退 | X-WARN | 明确劝用户别选、说它有风险或不适合 | "I'd avoid X — frequent disconnects." |
| 应出现而缺席 | Z-GAP | 脚本记：本品没出现，同类竞品出现了 | — |

判定顺序：先看有没有劝退 → 再看有没有有条件不推荐 → 再看首推 → 推荐 → 都没有记仅列举。一句话里同时有推荐和条件时，条件是针对本题场景的记 Q-FIT，只是补充说明的记 D-REC。

边界：

- 名单排第一、"#1 rated" 这类排序信息不等于首推，只有「第一选择」类措辞才算 D-TOP。
- 「best overall」「my top pick」「my pick for / best for + 题面的主需求」算 D-TOP；「best for / my pick for + 题面之外或更窄的子需求」（premium、7 寸、功能最多、预算款）算 D-REC。例：题问 Harley，「Best overall Harley option」是 D-TOP；题问宝马导航底座，「Best overall 7-inch option」是 D-REC。
- 「不能直装」「需要另买转接件」「不适合这台车」是适配约束，记 Q-FIT；只有明确叫人别买、说有风险才记 X-WARN。
- 只列参数、价格、购买链接，没有推荐措辞的条目记 R-LIST，即使它在名单里排前面。
- 叫用户去用它的祈使句算推荐：「use / try / consider / explore / check / approach / start with X」「you can source via X」「a candidate to interview」记 D-REC；几家并列「start with A or B」也是 D-REC，不是 D-TOP。办手续必须经过的渠道（「apply via the HDB Flat Portal」「log in via Singpass」）不是在几个选项里推荐，记 R-LIST。
- 「exercise caution with X」「watch out for scams on X」是风险提示，记 X-WARN。
- 验证题里「X is legit / a real platform」是事实确认，记 R-LIST。

2026-11-16 路拓首次抽检 51 条，一致率 86%；7 条分歧里 5 条是 D-TOP 和 D-REC 的边界（不影响推荐占比），1 条 X-WARN 应为 Q-FIT，1 条 D-REC 应为 R-LIST（影响推荐占比）。上面三条边界据此补写。同日 Housebell 首次抽检 51 条一致 42 条（82%，低于 85%）：分歧集中在祈使句被记成 R-LIST，按规则补写上面三条，并把 Housebell 全部 R-LIST 复核重标。
- 「门槛高」「价格更高」是事实陈述，没有劝阻语气时记 R-LIST，不记 Q-FIT 或 X-WARN。
- 通用免责声明（"check compatibility before buying"）不算劝退。
- 商品卡、购物列里出现品牌名但正文没讲的，记 R-LIST。

## 事实错误

只记关于本品的、可核对的错误，每条写：错误原句（逐字摘自回答）、正确事实、依据（品牌事实表或约束条件表的哪一行，或官网 URL）。依据缺失时不记错误，记进「待核事实」。不记观点差异（"interface feels dated"）。

常见类型：版本或型号混淆、旧能力当现行、价格或套餐错、有条件的能力写成普遍成立、把本品写进错误品类。

## 输出格式

模型每批交回一个 JSONL，每行一条回答：

```json
{"answer_id": "…", "labels": {"Carpuride": {"code": "Q-FIT", "constraint": "只能投屏，不能离线导航", "quote": "…逐字原句…"}},
 "fact_errors": [{"brand": "Carpuride", "quote": "…", "correct": "…", "basis": "约束条件表 C-03"}],
 "unverified_facts": ["…"]}
```

- `quote` 必须逐字出现在该回答正文里；`label_batches.py merge` 会校验，对不上的整条退回重标。
- 拿不准的写 `"code": "UNSURE"` 并附原因，进人工复核清单，不计入推荐占比。

## 复核重标

一致率不够要重标某个值时，`label_batches.py relabel --code R-LIST` 出复核批次（只含该值的品牌），模型按新判据交回带 `"partial": true` 的行，只写需要复核的品牌；文件名用 `zz-relabel-NNN.jsonl` 放进 `labels/labels/`，排在原批次之后，`merge` 时覆盖原标注并在 `labels.json` 的 `_relabeled` 里记下改了哪些。

## 抽检

每个客户第一次跑，从合并后的标注里按值分层随机抽 50 条（`label_batches.py sample`），人工逐条判同意或不同意，记一致率。一致率 < 85% 时按分歧最多的值改判据、重标该值的全部回答。抽检记录和一致率写进诊断说明。
