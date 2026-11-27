# 引用域名判读流程

报告、监测基线、临时统计用的引用来源类别都由 `scripts/geo_presales_core/sources.py` 判，判据在
[metric-scope-and-copy-contract.md](metric-scope-and-copy-contract.md)「引用来源分类」。这一份只写「新域名怎么补判」的操作流程。
所有命令在 `geo-metrics/` 目录下跑；数据都在 `assets/`：

| 文件 | 内容 |
|---|---|
| `assets/domain-categories.json` | 共享域名类别缓存（跨客户复用） |
| `assets/domain-categories-meta.json` | 每条判读的依据、置信度、来源、日期 |
| `assets/domain-brand-sites.json` | 品牌站索引：域名 → 品牌、品类、行业、市场（不记竞品关系） |
| `assets/category-taxonomy.json` | 品类归一表（与选词 skill 行业知识档案同一套英文品类词） |
| `assets/brand_lexicon.<品类>.json` | 品类级开放品牌词表 |

2026-11-18 从 geo-presales-report-builder 迁来；报告 skill 的旧路径留了软链，老命令照常能跑。

随仓库分发的数据：

| 文件 | 是否随仓库发布 | 说明 |
|---|---|---|
| `category-taxonomy.json` | 是 | 通用品类表 |
| `domain-categories.json` | 是 | 站点类型缓存；域名键不点客户，直接发布 |
| `domain-categories-meta.json` | 是 | 判读依据；依据里不写客户名 |
| `domain-brand-sites.json` | 否 | 记着域名属于哪个项目、是本品牌还是竞品 |
| `brand_lexicon.*.json` | 否 | 具体客户的品牌清单 |

## 开放品牌的官网域名

**开放品牌也要有官网域名**，否则它们的官网引用会落进「其他」、竞品网站被低估。域名不必手填，用引用来源推断：

```bash
python3 scripts/infer_brand_domains.py --collect <采集目录> \
  --lexicon assets/brand_lexicon.<品类>.json \
  --out build/brand-domains-inferred.json --candidates build/brand-domains-candidates.json
```

高置信规则是「引用注册域的标签 == 品牌名/别名归一形式」（`viu.com`↔Viu）；推不出的（缩写类，如 `mgtv.com`↔Mango TV）进候选清单，**联网搜索或人工确认后**写回词表的 `official_domains`，不要用模糊相似度硬猜。目标与配置竞品的域名以 Case 为准，词表里的同名条目只做别名合并。

反向也要查：**引用里出现、正文没点名的同品类厂商站**，按其官网域名补进对应品牌条目（词表没有就新建），否则判「其他」会把竞品网站压低。「其他」占比偏高时先做这一步，再逐域名判缓存；哪些域名是哪个品类的品牌站可看 `assets/domain-brand-sites.json` 的 `known_brand` / `known_categories`。**只有 `known_categories` 与本品类一致（经 `category-taxonomy.json` 归一后同一个键）的条目可以拿来判竞品并补词表**；不同品类的备注只说明它是企业站，不作竞品判断依据。共享缓存不能写 competitor，竞品关系只写在客户词表和 Case 里；同一个域名换了客户要重新补。

先列出本品类已经被别的项目判过的域名，能直接参考（品类键取 `category-taxonomy.json` 的 `categories`，示例是 `dash cam`）：

```bash
python3 -c 'import json,sys; cat=sys.argv[1]; idx=json.load(open("assets/domain-brand-sites.json")); [print(d, r.get("brands"), r.get("roles")) for d,r in idx.items() if cat in (r.get("categories") or [])]' "dash cam"
```

索引由 `build_brand_site_index.py` 从各项目重建；新品类要先进 `category-taxonomy.json` 才归得进索引，刚开的品类一开始没有可参考条目，属正常。

## 补判未登记的引用域名（不是封闭集合）

```bash
python3 scripts/collect_domain_candidates.py --collect <采集目录> --case <Case.json> \
  --lexicon <词表.json> --cache assets/domain-categories.json --out build/domain-candidates.json
```

判读按固定顺序做，不许跳步。已知域名缓存里已经判过，直接复用，不重复抓取；新域名先补证据再判：

0. **按引用次数补证据**（只抓前 N 个，不全量抓）：

   ```bash
   python3 scripts/enrich_domain_candidates.py --candidates build/domain-candidates.json \
     --out build/domain-candidates.enriched.json --top 50
   ```

   输出每个域名的首页标题与 meta 描述；抓不到的标 `fetch_error`，当待复核处理，不要强行归类。
1. **先过品牌词表与 Case**：这个域名是不是某个品牌的官网（含子域）？是就交给词表判定，不写缓存。同类产品站没进词表是「其他」过高的头号原因——真实案例里，几家互相独立、只卖同一类检测或改写工具的产品站，一开始都被判成了「其他」。候选里带 `known_brand` / `known_categories` / `known_industries` 的，是品牌站索引（`assets/domain-brand-sites.json`）给的备注：说明这个域名是哪个品类里谁家的官网，按「其他」判，同类的话补进本项目的 `competitor_site_domains`。带 `same_label_as` 的是和本项目某官网同标签、不同顶级域的域名（`example-brand.com.sg` ↔ `example-brand.com`），大概率是同一家，但不同顶级域也可能是别家，确认后把区域域名补进 Case 或词表。索引只记「它是谁、做什么品类」，不记「它是不是你的竞品」——竞品关系按项目写在 Case 和词表里。新项目跑完后更新索引（品类按 `assets/category-taxonomy.json` 归一，与选词 skill 行业知识档案同一套英文品类词）：

   ```bash
   python3 scripts/build_brand_site_index.py --roots <项目根目录>... \
     --out assets/domain-brand-sites.json
   ```
2. **引用次数前 20 的域名必须打开页面核实**：自己卖检测或改写工具 → 产品站（有品牌名的补进词表，没有的判「其他」并写理由）；只做榜单、横评、目录 → 媒体网站；学校、政府、期刊、协会 → 机构网站。只读页面标题不够：「Best Free AI Detectors」这类标题可能是评测站，也可能是厂商给自己产品做的内容营销，性质完全不同。
3. **判「其他」必须写理由**：一句话说明这个站是什么、为什么不属前六类，写进 `build/domain-judgments.json`。
4. **写回共享缓存与判读记录**：类别写 `assets/domain-categories.json`；依据写 `assets/domain-categories-meta.json`（`evidence` / `confidence` / `source` / `verified_at`）。证据不足的标 `confidence: pending`，保持原判，不要为了清空「其他」硬判。
5. **跑自检**，退出码非 0 不许生成报告数据：

   ```bash
   python3 scripts/check_domain_judgments.py --collect <采集目录> \
     --cache assets/domain-categories.json --lexicon assets/brand_lexicon.<品类>.json \
     [--case <Case.json>] --reasons build/domain-judgments.json
   ```

   它查四件事：前 20 有没有未判读、「其他」有没有缺理由、「其他」占引用是否超过 15%（超过就回头找漏掉的品牌官网和评测站）、待复核（`confidence=pending`）占多少引用。待复核按引用次数排前几位，先复核这些；写报告时这一项要让人知道。子域名按父域归属，`guides.turnitin.com` 算 `turnitin.com`。另外会列出「历史判读无依据」（`confidence=legacy`）和「父域未判」的域名。

这一步有门禁：报告的 `build_report_data.py` 发现未判读的引用超过 5% 会以退出码 3 停下，并写出 `<输出名>.domain-candidates.json`，判完写回缓存再重跑。单个域名引用不足 `min(100, 总引用 1%)`（下限 5）次的是长尾，不强制判读，展示归「其他」并记在 `meta.source_classification.low_volume_*`，写交付说明时要说清「其他」里这一部分没判。确实不判时加 `--allow-unjudged-domains "<理由>"`。分类实现和门禁在 geo-metrics core `sources.py`。
