# 缺口诊断 e2e（2026-11-27 17:51）

68/68 通过

| 用例 | 结果 | 说明 |
|---|---|---|
| R1 layer_readings 输出四份文件 | 通过 | 有效回答 37，平台 {'chatgpt': 37}，题 6；强制联网平台 ['chatgpt']
本品 Veyra，官网 ['veyra.com']，同类品牌 3 个；
问题清单 {'TEXT_NOT_IN_BANK': 1, 'DUPLICATE_ANSWER': 1}（见 issues.json）
 |
| R2 Q1 零提及、领先竞品识别为 Lumo | 通过 | [1.0, 0.6457, 1.0] |
| R3 ChatGPT 强制联网口径记「强制」 | 通过 | {'强制': 7} |
| R4 Q1 官网未进检索（search_result 只有第三方和竞品） | 通过 | [0.0, 0.0, 0.3543] |
| R5 Q2 官网进检索与被引都 100% | 通过 | [1.0, 0.6457, 1.0] [1.0, 0.6457, 1.0] |
| R6 Q5 只有 2 条有效回答（门 0 的依据） | 通过 | 2 |
| R7 重复回答与无解题都登记进 issues | 通过 | ['DUPLICATE_ANSWER', 'TEXT_NOT_IN_BANK'] |
| R8 有未解题时退出码 1 | 通过 | rc=1 |
| G1 低优先级过不了门 1 → 暂不做 | 通过 | 门 1 未过 |
| G2 有效回答不足过不了门 0 → 观察 | 通过 | 门 0 未过 |
| G3 已领先的题 → 守住 | 通过 | 守住 |
| G4 Q1 定位到断点 3（官网没进检索层） | 通过 | 3 官网没进检索层 / 有检索字段的 7 条回答里官网进检索 0%（0/7） |
| G5 断点 3 的载体是官网、负责方内容团队 | 通过 | 官网 内容团队 |
| G6 无标注、无页面缺口时 Q3 退回观察 | 通过 | 守住 / 点名题 |
| C1 主约束明显劣势过不了门 2 → 转产品 | 通过 | 门 2 未过 |
| C2 其余题受站点可达性低影响改判断点 1 | 通过 | 1 抓取不可达 |
| C3 断点 1 的负责方是官网技术 | 通过 | 官网技术 |
| L1 prepare 产出批次文件与 auto-zgap | 通过 | 送模型标注 37 条，2 批；自动记 Z-GAP 21 条。批次在 /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/labels/batches
 |
| L2 点名题 Q3 送模型标注，标注品牌含本品 | 通过 | [{"answer_id": "01f9689c75ba", "question_id": "G-03", "question": "is Veyra solar charger reliable", "platform": "chatgpt", "label_brands": ["Veyra"], "body": "Veyra works outdoors, but buyers report  |
| L3 引文逐字对上的标注被接受 | 通过 | {"code": "X-WARN", "constraint": "", "quote": "Veyra works outdoors", "reason": "\u53ea\u9002\u5408\u77ed\u9014"} |
| L4 引文对不上、漏标、Q-FIT 缺约束都被退回 | 通过 | rejected=3 |
| L5 退回条目写了原因 | 通过 | [{"answer_id": "01f9689c75ba", "file": "m1.jsonl", "line": 8, "reason": "Veyra \u7684 quote \u5728\u6b63\u6587\u91cc\u627e\u4e0d\u5230"}, {"answer_id": "01f9689c75ba", "file": "m1.jsonl", "line": 9, " |
| L6 merge 后 labels.json 带 _fact_errors 结构 | 通过 |  |
| L7 sample 产出人工抽检表 | 通过 | 抽了 1 条到 /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/labels/sample-review.csv（按值分层，种子 20261116）
 |
| L8 抽检表有 agree 列 | 通过 | ['answer_id', 'question', 'platform', 'brand', 'code', 'constraint', 'quote', 'agree', 'note'] |
| L9 --score 算出一致率 | 通过 | 已判 1/1，一致 1，一致率 100%；按值 X-WARN 1/1
 |
| L10 点名题有标注后定位到断点 7（被提及没被推荐） | 通过 | 7 被提及但没被推荐 / 被提及 7 条里推荐占比 0%，最多的是 X-WARN：Veyra works outdoors |
| P1 page_gap 输出 json 与 csv | 通过 | 页面 3 个，抓到 2 个；题×页面 7 行，{'页面缺口': 5, '未知': 1, '答案缺口': 1}
[1/3] ok https://reviewhub.example/guides
[2/3] http_403 https://reviewhub.example/reviews
[3/3] ok https://reviewhub.example/van
 |
| P2 没提本品、提了两家竞品的页面判页面缺口 | 通过 | [{"url": "https://reviewhub.example/guides", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": "https://reviewhub.example/guides", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": "https://reviewhub.example/revi |
| P3 提到本品但引用它的回答没提 → 答案缺口 | 通过 | [{"url": "https://reviewhub.example/guides", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": "https://reviewhub.example/guides", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": "https://reviewhub.example/revi |
| P4 403 页面记抓取失败、不猜 | 通过 | [{"url": "https://reviewhub.example/guides", "fetch": "ok", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": "https://reviewhub.example/guides", "fetch": "ok", "gap": "\u9875\u9762\u7f3a\u53e3"}, {"url": " |
| P5 官网已在检索层时，页面缺口接进诊断判断点 5 | 通过 | 5 页面缺口 / https://reviewhub.example/guides（被引 7 条，提了 Lumo、Nexo） |
| D1 三份产物都在 | 通过 | 机会 6 行：{'测试': 3, '观察': 1, '守住': 1, '暂不做': 1}；断点 {'5 页面缺口': 1, '3 官网没进检索层': 1, '7 被提及但没被推荐': 1}
 |
| D2 md 里写断点与决定 | 通过 | # Veyra 优化机会诊断（自动初稿）

本文件由 `diagnose.py` 生成，是分析师的初稿：每条「测试」的原因假设、候选页面都要按 gap-cause-action-table.md 的三项核对（回答原文、被引来源、官网与产品事实）确认后再交内容团队。

## 数据与口径

- 有效回答 37 条，平台 {'chatgpt': 37}；采集目录 1 个。
- 强制联网的平台：chatg |
| D3 json 带每题行与元信息 | 通过 | ['params', 'meta', 'crawlability', 'rows'] |
| D4 退出码 0 | 通过 | rc=0 |
| K1 四份产物都在、退出码 0 | 通过 | 题 6：竞争难度 {'高': 4, '不适用': 1, '不判': 1}；优化难度 {'高': 2, '已达标': 1, '不适用': 1, '不判': 1, '低': 1}；主题 1 → /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/difficulty
 |
| K2 两家竞品每次都在、每答只列 2 家 → 轮换位 0，竞争难度高 | 通过 | Lumo、Nexo 每次都在（≥80% 的回答）；每条回答列 2 家，轮换位 0 个 |
| K3 本品零提及且竞争难度高 → 优化难度高 | 通过 | 竞争难度高，本品目前出现在 0% 的回答里 |
| K4 本品提及率 ≥30% → 已达标 | 通过 | 本品出现在 100% 的回答里，提及最多的竞品 Lumo 100%，任务是守住 |
| K5 点名题 → 不适用 | 通过 | {'question_id': 'G-03', 'topic': 'brand reliability', 'prompt_type': 'Evaluation', 'priority': '高', 'question': 'is Veyra solar charger reliable', 'n': 7, '竞争格局': '—', '竞争难度': '不适用', '竞争依据': '题面点名本品', |
| K6 可改变性低 → 优化难度高并写出原因 | 通过 | 只改官网改不了（第三方主导）：只有 0% 的有引用回答引了厂商官网 |
| K7 有效回答不到 7 条 → 标预判 | 通过 | 2 |
| K8 本品在 29% 的回答里出现 → 已进候选，优化难度低（先于竞争难度高） | 通过 | 高 / 本品已在 29% 的回答里出现，已进候选，离 30% 差 1% |
| K9 主题：Lumo 每道题都在、份额领先 → 单一主导 | 通过 | 单一主导 / Lumo 在 ≥80% 的题里都出现；声量份额第一领先第二 15% |
| K10 主题档取题的多数档并给出分布 | 通过 | 高 4 · 不判 1 |
| K11 可先做的题列出优化难度低的题 | 通过 | G-06 |
| K12 每题只有 1 次回答 → 竞争、优化难度都不判，依据写回答次数不足 | 通过 | 不判 / 每道题只有 1 次回答，分不出哪些竞品每次都在；至少 3 次回答再判 |
| F1 抓到 5 页、404 和 403 记失败不补 | 通过 | 找页面：只用 --url；共 7 页，抓到 5 页（其中代理补抓 0 页），仍失败 2 页（不猜）
[1/7] ok 378 http://127.0.0.1:60131/
[2/7] ok 398 http://127.0.0.1:60131/pages/about
[3/7] ok 378 http://127.0.0.1:60131/policies/terms
[4/7] http_403 |
| F2 正文按块保留换行（页脚和条款段不被吞） | 通过 | Terms
Mailing address: 30 Old Road, Sheridan, WY.
Veyra SolarPack 20 is priced at $129.99.
Filler text for length. Filler text for length. Filler text for length. Filler text for length. Filler text f |
| F3 长页面切成多段、不截断 | 通过 | 15 段 / 5 页切成 15 段，2 个批次；按 references/facts-extraction.md 抽，交回 /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/facts-draft/extracted/*.jsonl
 |
| F4 原文逐字对不上、值不在原文里都退回 | 通过 | 原文在这一段里找不到（逐字） 值不在原文里 |
| F5 同一型号两个价格标冲突、可变标是 | 通过 | [{"草稿编号": "D-002", "对象": "Veyra SolarPack 20", "属性": "price", "值": "$129.99", "原文": "Veyra SolarPack 20 is priced at $129.99.", "页面": "http://127.0.0.1:60131/policies/terms", "可变": "是", "冲突": "官网另有写法： |
| F6 确认列没填完拒绝生成 facts.md | 通过 | 确认表没填完，不生成：4 行确认列为空、填错，或「改」没写改正值、「新增」缺对象属性值：D-001、D-002、D-003、D-004
 |
| F7 只用确认行生成：删掉的不在、新增的在、带 F 编号 | 通过 | facts.md 4 条（删 1 条）→ /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/facts.md
# 品牌事实表（标注用，4 条）

由 `facts_draft.py` 从官网抽取、逐字校验，经品牌方逐条确认（/var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/ |
| F8 已有 facts.md 不覆盖 | 通过 | /var/folders/r5/hrm2b2gn6n39ck3tzwwrjlzs0p32h9/T/gap-e2e-fku7pfkq/facts.md 已存在，不覆盖；确认要替换加 --force
 |
| T1 八条错误都有出处结论 | 通过 | 事实错误 8 条，官网页面 5 个；出处 {'官网自相矛盾': 2, '第三方页面': 1, '混淆别家': 1, '未知': 2, '混淆型号': 2}
 |
| T2 错误价在官网条款页 → 官网自相矛盾，出处指向条款页 | 通过 | {"answer_id": "93b045123b5d", "question_id": "G-01", "platform": "chatgpt", "basis": "F-01", "quote": "It costs $129.99.", "correct": "$149.99", "wrong_values": "$129.99", "cause": "官网自相矛盾", "carrier" |
| T3 只在被引第三方页 → 第三方页面，附片段 | 通过 | {"answer_id": "524bf0093556", "question_id": "G-01", "platform": "chatgpt", "basis": "F-01", "quote": "Price around $99", "correct": "$149.99", "wrong_values": "$99", "cause": "第三方页面", "carrier": "第三方 |
| T4 标了 other_entity → 混淆别家 | 通过 | 混淆别家 |
| T5 被引页抓不到 → 未知，不当成没写 | 通过 | {"answer_id": "947a957b08b5", "question_id": "G-01", "platform": "chatgpt", "basis": "F-01", "quote": "costs $111.11", "correct": "$149.99", "wrong_values": "$111.11", "cause": "未知", "carrier": "待定",  |
| T6 哪里都没有，但官网有页面没抓到（403；404 不算）→ 未知，不判未找到 | 通过 | {"answer_id": "7cdfaf50b2d1", "question_id": "G-01", "platform": "chatgpt", "basis": "F-01", "quote": "costs $222.22", "correct": "$149.99", "wrong_values": "$222.22", "cause": "未知", "carrier": "待定",  |
| T7 旧标注没有 wrong_value 时从 quote 抽出价格 | 通过 | $129.99 |
| T10 错误值是事实表另一条的值 → 混淆型号，指出是哪条 | 通过 | {"answer_id": "93b045123b5d", "question_id": "G-01", "platform": "chatgpt", "basis": "F-09", "quote": "It costs $149.99 with 1.2 kg weight", "correct": "$139.99", "wrong_values": "$149.99", "cause": " |
| T11 正确事实是价格时只追价格，不追原句里顺带的 1080p / 20 W | 通过 | $129.99 |
| T12 错误值是官网另一个产品页上的值（片段里没有被判错的型号）→ 混淆型号，不判官网自相矛盾 | 通过 | {"answer_id": "524bf0093556", "question_id": "G-01", "platform": "chatgpt", "basis": "F-02", "quote": "SolarPack 20 sells for $89.99", "correct": "$149.99", "wrong_values": "$89.99", "cause": "混淆型号",  |
| T8 诊断事实行写出处分布、载体按出处定、附官网出处页 | 通过 | {"机会编号": "O-001", "对象": "事实：F-01", "题号": "G-01", "题面": "", "主题": "", "类型": "准确性", "业务优先级": "高", "有效回答": "5", "本品提及率": "", "领先竞品": "", "领先竞品提及率": "", "官网进检索率": "", "官网被引率": "", "推荐分布": "", "过门情况": "通过" |
| T9 md 注明已溯源 | 通过 | # Veyra 优化机会诊断（自动初稿）

本文件由 `diagnose.py` 生成，是分析师的初稿：每条「测试」的原因假设、候选页面都要按 gap-cause-action-table.md 的三项核对（回答原文、被引来源、官网与产品事实）确认后再交内容团队。

## 数据与口径

- 有效回答 37 条，平台 {'chatgpt': 37}；采集目录 1 个。
- 强制联网的平台：chatg |
