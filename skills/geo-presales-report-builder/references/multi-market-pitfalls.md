# 多市场 / 跨品类实施的坑清单

一条报告同时覆盖几个国家、两条产品线时，最容易踩的不是指标公式，是「题库、采集目录、展示集合」三者对不齐。以下是 2026-11-11 Obrand（肯尼亚 + 尼日利亚 × 耳机 + 快充，94 道题、303 次回答）实测出来的坑，动手前先对一遍。

## 1. 题库按市场写时，必须有 `region` 列

**症状**：报告里有些题显示「—」（无答案），但采集文件明明在工作目录里。

**根因**：`discover_sample_files` 用 `prompt → question_id` 建映射。肯尼亚和尼日利亚挂了同一句提示词时，后一道覆盖前一道，被覆盖的题在它自己的市场里一条回答都匹配不到。Obrand 94 道题里有 26 对跨国重复，直接导致 26 道题空着。

**修法**：题库 CSV 加 `region` 列（`KE` / `NG`），`build_question_bank` 把它写进 `question["region"]`，`load_samples` 里先按市场过滤再匹配：

```python
region_questions = [q for q in questions if not q.get("region") or q["region"] == region]
files, discover_issues = discover_sample_files(folder, region_questions)
```

**验收**：`meta.sample_issues` 必须为空数组。非空说明还有题对不上——先看是不是这个问题，不要当成采集缺失。

## 2. 采集文件名必须是题库全局题号

**症状**：问题明细能打开抽屉，但显示「当前采集目录里没有这道题的原始回答」。

**根因**：`details` 的键是 `<地区>|<平台>|<文件名 stem>`，抽屉按 `String(qid).padStart(4,"0")` 回查。用原始批次名（`KECHG005_1.json`）建出来的键是 `KE|ChatGPT|KECHG005_1`，和 `0001` 对不上。

**修法**：复制采集文件时用全局题号命名，第 1 次 `0001.json`、第 2 次 `0001-r2.json`，以此类推。

**连带影响**：译文批次的键也是从 details 导出的，换命名后要重新映射一遍再 `attach_translations`。

## 3. 配置竞品不设 3 个上限，按产品线各挂

**症状**：两条产品线的竞品不同，但报告只能挂一套。

**修法**：Case 的竞品用「竞品 N 主题」限定归属：

```json
"竞品 1": "RivalO2", "竞品 1 官网域名": "https://www.rival-o2.example",
"竞品 1 主题": "耳机选购,充电器选购"
```

- `build_config` 不再截断 `[:3]`，读 `comp.get("topics")` 写进 `object["topics"]`。
- `build_slice` 与 `report-engine.js` 的 `slice()` 都按当前主题过滤配置竞品；全部主题切片与「类型:X」意图切片展示全部。
- 子品牌并入母品牌（`Soundcore` → `RivalO2`）靠词表的 `aliases` + `domains` 合并，不要另起对象。
- **裸词别名会误报**：`Nothing` 这个品牌名本身是普通英文词，`- [x] Nothing inside my ear canal` 会被当成提及。Obrand 实测 3 条误报（51 次里 3 次是假）。别名写成 `Nothing Ear` / `Nothing Phone` / `CMF` / `CMF Buds` 这类带型号的形式；同理要当心 `One`、`Play`、`Best` 这类通用词。

**验收**：`check_engine_parity.js` 必须过；每个主题切片只出现本线的 3 个配置竞品 + 目标 + 1 个开放竞品。

## 4. 问题明细必须按地区 / 平台过滤

**症状**：切换地区后，指标变了，但明细条数不变。

**根因**：`qOk(sel, qid)` 只比对 `sel.intents` 和 `sel.topics`，漏了地区和平台。`records()` 因此把全部题都列了出来。

**修法**：两侧都加「该题在当前筛选下有有效回答」的门禁：

```js
return (byQ[qid] || []).length > 0;   // report-engine.js
if not valid: continue                // build_report_data.py build_records
```

## 5. 只有一个平台时，不出「跨平台」结论

**症状**：单平台报告写出「跨平台差距较大（最高与最低相差 0.0 个百分点）」。

**修法**：`report.js` 的 competition 洞察里加 `vals.length === 1` 分支，直接给「当前只有 X 一个平台的数据，提及率 Y%」。

## 6. 域名判读：枚举值、二级后缀、媒体 vs 机构

三件事都出过：

**a. 缓存只接受 5 个枚举值**：`media_review` / `ugc` / `institutional` / `press_release` / `other`。品牌官网**不要**往缓存里写 `competitor`——那由 Case + 词表的 `official_domains` 判定，写进去会 `SystemExit`。

**b. 非洲二级后缀缺失**：`geo_presales_core/util.py` 的 `COMMON_MULTI_LABEL_SUFFIXES` 原来只有东南亚和中东，`citygadgetskenya.co.ke` 被归成 `co.ke`、`jumia.com.ng` 归成 `com.ng`，凭空多出两个「域名」。已补 `co.ke`、`com.ng`、`co.za`、`com.gh`、`co.tz`、`com.eg`、`com.sa`、`com.ae` 等。

**c. 消费者评测站不是机构**：`which.co.uk`（Which?）、`abc.net.au`、`theguardian.com`、`road.cc`、`bikeradar.com` 这类得归「媒体网站」。`institutional` 只收政府、学术、标准组织（`cdc.gov`、`sec.gov`、`ieee.org`、`nist.gov`）。文档站（`manualslib.com`、`scribd.com`）、百科（`baike.baidu.com`）、电商与经销商（`jumia.com.ng`、`konga.com`、`citygadgetskenya.co.ke`）归「其他」。

**d. 品牌地区站要并进词表，不能只塞缓存**：`rival-o4.example`、`jbl.co.ke`、`rival-o3.example`、`rival-o5.example`、`rival-o2-mea.example`、`blog.google`、`support.oppo.com` 这类是词表品牌的地区站或子站，应写进该品牌的 `official_domains`，这样它们的引用才进「竞品网站」。写进域名缓存只会得到「其他」，因为缓存根本没有 `competitor_official` 这个枚举。

**e. 判读必须逐个读，不能写关键词脚本批量打标。** 2026-11-11 我用关键词脚本给 185 个域名打标、只抽查前 40 个，结果 `which.co.uk` 被打成机构、`jumia.com.ng` 被打成媒体、`tollbit.rollingstone.com` 被打成新闻稿。改判 23 个。

正确做法：

```python
# 1) 先导出「域名 + 页面标题」全清单
for i, x in enumerate(candidates, 1):
    print(f"{i:>3}\t{x['count']:>3}\t{x['domain']}\t{' || '.join(x['titles'][:2])[:150]}")

# 2) 逐个读完，把结果写成显式清单，并用断言保证一个不漏
covered = brand_set | set(cache)
missing, extra = all_domains - covered, covered - all_domains
assert not missing and not extra, (sorted(missing), sorted(extra))
```

断言必须过，否则说明还有域名没判。

**验收**：媒体网站份额应与「答案里大量引用评测站」的直觉一致。Obrand 修前「其他」占 79%、媒体只有 3%；逐个判读后媒体 69%、竞品 20.5%、其他 9%。

## 7. 商品卡：有的市场只有商品名，这是 ChatGPT 上游如此

**症状**：`task_result.products` 只有 `title` 和 `query`（两者相同），`price`、`rating`、`image_urls`、`merchants`、`offers` 全为空。Obrand 肯尼亚、尼日利亚 1066 张卡全是这样；10-28 到 11-07 全部 KE/NG 采集约 3,200 张卡也一张不例外。同一天、同一个采集器，美国、英国的卡字段都完整。

**根因（2026-11-11 用 `--fetch-html` 取回答页核对，美国、肯尼亚、尼日利亚各 3 道同题）**：

- 美国：卡片图片取自商品目录（`alt` 是商品 ID，`title` 是商品标题），卡里有 `Price: $299.99`。
- 肯尼亚、尼日利亚：卡片图片是网页配图（`title` 是日本耳机店的文章标题之类），卡里没有价格、商家、购买入口；页面上的 `$` 只出现在预算选项里。

回答页本身就没有这些信息，所以不是 Scrapeless 漏解析。OpenAI 商家页原文 "Shopping is currently live for ChatGPT users in the U.S."（https://chatgpt.com/merchants/），没写其他国家。

**口径（2026-11-11 Suda 定）**：只有带商品目录的购物卡才统计商品卡指标。判据在 geo-metrics `shopping.chatgpt_catalog_backed`：条目带 `id`、`cite`（`turn0productN`）、`offers`、`price` 之一。肯尼亚、尼日利亚的条目一条都不带，商品卡数为 0，报告的购物商品卡模块和核心洞察里的商品卡提及率自动不出，不用手动 `--shopping-cards 关`。美国 Bbrand 180 个切片按新口径重算，购物指标无变化。

**已问服务商的点**：`products` 是只取自 ChatGPT 商品检索，还是也从正文摘商品名；为什么有图文卡的回答 `products` 为空；`products` 顺序是否等于页面顺序。问题清单在 `10-售前诊断报告/评测数据/brand-o/售前/_trial/html-probe-20261111/给爬虫服务商的问题-商品卡-20261111.md`。

**交付前必查**：

```bash
python3 -c "
import json,glob
tp=ok=0
for f in glob.glob('collect/scraper.chatgpt/*/*.json'):
    for c in (json.load(open(f)).get('task_result',{}).get('products') or []):
        tp+=1
        if c.get('price') or c.get('rating') or c.get('image_urls') or c.get('merchants'): ok+=1
print(tp, ok, f'{ok/tp*100:.1f}%' if tp else 'no cards')
"
```

新市场第一次出报告、命中率是 0% 时，先用 `collect_answers.py --fetch-html` 对该市场和美国各采两三道同题，看回答页里的卡有没有价格；有价格而 `products` 为空才是采集问题，要找供应商。

## 8. 地区显示名走 Case，不要写死在模板

Case 加「地区名称」字段：

```json
"地区名称": {"KE": "肯尼亚", "NG": "尼日利亚"}
```

`build_meta` 写进 `meta.region_labels`，`report.js` 的 `dimLabel()` 只换显示文本，`value` 仍是代码（切片键靠它）。

## 9. 「第几次运行」按 `-rN` 排，不按文件名字符串排

**症状**：`facts.answers[].n` 和文件名里的 `-rN` 对不上——n=1 对应 `0001-r2.json`，n=3 才对应 `0001.json`。

**根因**：`sorted(paths)` 按字符串排，`0001-r2.json` 里 `-` 的 ASCII 是 45，排在 `0001.json` 的 `.`（46）前面。

**修法**：

```python
def _run_number(path: Path) -> int:
    match = re.search(r"-r(\d+)$", path.stem)
    return int(match.group(1)) if match else 1

for index, path in enumerate(sorted(paths, key=lambda item: (_run_number(item), item.name)), 1):
```

**影响**：抽屉用 `details[].run`（文件名解析）不受影响，但任何拿 `facts.n` 回查文件的逻辑都会取错。

## 10. 交付前必须跑一次独立审计

`verify_report_data.py` 复算时**复用生产的 `discover_sample_files` 映射**，所以「题目归属错」它永远查不出来——映射错了它跟着错，对账永远是平的。Obrand 的 26 道题无答案就是这么漏过去的。

独立审计的要求：

1. **不 import 项目模块**（`geo_presales_core`、`build_report_data` 一律不用），自己写品牌识别、引用解析、指标公式。
2. 先核对「文件 → 题目」归属：`task_result.prompt` 与文件名题号对应的 `query` 是否一致、文件所在市场是否在该题 `region` 里、每道题在所属市场是否至少有一条回答。**这一项是重点**，其余指标错通常是映射错的下游。
3. 对每个切片（`||`、`KE||`、`NG||`、每个主题）逐项比对：有效回答数、Top5 品牌提及率、声量份额、引用总次数、官网引用份额、商品卡触发率。
4. 随机抽 10 条（固定种子），人工读原文核对品牌与首次出现顺序。
5. 有出入时必须判定「报告错 / 审计脚本错 / 口径歧义」，并给原文片段。

Obrand 实测：recon 口径下 303 条回答、9720 条「题 × 品牌」行、12 个切片 **0 差异**；严格口径下的 1093 项出入全部是审计脚本没剔除图片标题和链接文字造成的，不是报告错。

判读口径要一起写进报告的方法说明：

- 品牌识别先剔除 `<img title="…">` 里的标题、markdown 链接文字、裸 URL、脚注定义行——否则第三方商品图的标题会把 Apple、Samsung 的提及率抬高 4–12 个百分点。
- `google.com` 及其子域（`support.google.com`、`store.google.com`）是平台站内跳转，按契约不计引用。Obrand 因此少算 21 次引用，不影响官网份额。

## 11. 选题里点名的手机品牌，份额怎么算（未定）

**现象**：`Best 25W fast charger for Samsung phones` 这类题，Samsung 必然出现在答案里。它既可能是「适配对象」，也可能是真的在推荐 Samsung 原厂充电器，规则区分不了。

**量化**（Obrand 94 题、303 条回答）：

| 主题 | 手机品牌提及占比 | RivalO2 全部口径 | RivalO2 仅配件口径 |
|---|---|---|---|
| 手机充电器选购 | 67.2% | 15.2% | **46.2%** |
| 无线耳机选购 | 47.2% | 12.6% | 23.8% |
| 运动与开放式耳机 | 18.0% | 23.0% | 28.0% |

68 题里 14 题题面点了手机品牌。

**先排除了一个假设**：「只算推荐位（加粗标题 / 列表项 / 商品卡标题）就能把适配对象剔掉」——实测**不成立**。Apple 233→208、Samsung 181→161、RivalO2 218→213，只降 11%，说明这些品牌本来就大量出现在推荐列表里，AI 确实在推荐原厂配件。

**还没定的事**：口径怎么选（全算 / 按产品线排除 / 只排除题面点名）。定之前不要自己拍，这是客户会拿着报告问的第一个问题。无论选哪种，**「目标品牌提及率 0%」这个结论都不受影响**。

## 12. 品牌名会从三个「不是回答」的地方溜进来

品牌识别的输入必须是**回答正文**，但 ChatGPT 的 `result_text` 里混了三类别的东西。Obrand 实测：不剥的话 Apple 会从 132 虚高到 213（多算 81 次，38%）。

| 来源 | 例子 | 为什么不能算 | 剥法 |
|---|---|---|---|
| 商品图标题 | `<img title="Apple Watch, and More - Walmart">` | 第三方商品图的标题是被引网页的标题 | `HTML_TAG = re.compile(r"<[A-Za-z/!][^<>]*>")` |
| 追问块 | `- [x] Samsung` / `- [ ] iPhone`、`What phone do you use?` 后的 `- Tecno` | 这是 AI 在问「你用哪款手机」，不是它推荐 | ChatGPT 表单按 `follow_up_form` 字段定位、从提问句删到提交按钮行；没有表单的，问句（非标题）连同后面 2 条以上短列表一起删。正文自检清单 `- [ ] …` 不删 |
| 脚注定义行 | `[1]: https://…-cmf-100w-…` | 是引用 URL，不是正文 | `^\s*\[\d+\]:\s*\S+.*$` |
| alt 带转义方括号的 markdown 图 | `![\[Direct from Japan\] RivalO2 Soundcore … \| Shopee](<url>)` | 同商品图标题 | `IMAGE` 的 alt 部分写成 `(?:\\.\|[^\]\\\n])*`，旧写法 `[^\]]*` 遇 `\]` 就断（全库 10,276 条去重回答里 73 条） |

前两条在 `de_cite_crawl.strip_citations` / `strip_follow_up_form` / `strip_choice_lists`（geo-metrics 侧，调用方要把 `task_result.follow_up_form` 传给 `strip_citations`），第三条在 `REF_DEF`。

**验收**：独立审计的 `facts mismatch` 必须是 0。Obrand 修完是 0/303，修之前是 249/303。

**踩过的坑**：审计脚本自己也要实现这三条（它不 import 项目模块）。少实现一条，就会算出「报告多算了 187 个提及」的假警报——实际是审计口径偏松。

## 13. 每次改完的口径门禁

按顺序跑，任何一步非 0 不许交付：

```bash
python3 scripts/build_report_data.py --collect <dir> --questions <csv> --case <case> \
  --lexicon <lexicon> --domain-cache assets/domain-categories.json --out build/report-data.json
python3 scripts/attach_translations.py --report build/report-data.json \
  --batches build/translation-batches --out build/report-data.json
python3 scripts/verify_report_data.py --report build/report-data.json --collect <dir>
node scripts/check_engine_parity.js build/report-data.json
python3 scripts/check_inline_cards.py build/report-data.json
python3 scripts/render_report.py --data build/report-data.json --out <品牌>-售前诊断报告.html
```

每一步看完整输出再往下走。`| tail -1` 会把失败原因截掉：`verify_report_data.py` 的最后一行是切片统计，失败项在开头。

浏览器里再过一遍：切地区（条数要变）、切主题（竞品要换）、开抽屉（要有原文和中文）、关抽屉、滚到底看明细。
