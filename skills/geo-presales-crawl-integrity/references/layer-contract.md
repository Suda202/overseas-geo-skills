# 数据分层契约

采集文件里同时装着四类互不相同的数据。指标只能取其中一类，混用会静默产生错误数字。

## 四层定义

| 层 | 含义 | 不允许混入 |
|---|---|---|
| 正文引用 `citation_pills` | 回答正文里带编号的引用标记，及其关联来源 | 普通正文链接、实体入口、推荐追问 |
| 普通正文链接 `inline_links` | 正文里的普通文字超链接 | 引用标记内部的链接 |
| 回答来源面板 `answer_sources` | 与这条回答关联的来源卡片/来源列表 | 普通搜索结果、点击品牌后生成的实体面板 |
| 检索结果 `retrieval_results` | 模型检索工具返回的网页结果 | 回答来源面板、普通 SERP |

**普通 SERP、模型检索返回、回答来源面板是三个概念。** 现有采集里没有可验证的独立普通 SERP 数据，不得把回答右侧来源卡片改名为普通搜索结果为上游补数据。

## 每平台字段映射

按采集文件实际字段核验（`自建爬虫/四平台HTML字段与采集边界.md`，2026-09-11）。

| 平台 | 回答正文 | 正文引用元数据 | 检索字段 | 来源面板 |
|---|---|---|---|---|
| `chatgpt` | `task_result.result_text` | `content_references` | `search_result`、`links`、`sse_data` | 未单独保存 |
| `gemini` | `task_result.result_text`（`rawtext` 供对照） | `citations` | 未公开独立字段 | `citations` |
| `aimode` | `task_result.result_md`（`result_text` 供对照） | `citations` | 本批多为空 | `citations`；另有 `result_html` 可做 DOM 核验 |
| `overview` | `task_result.content`（`rawtext` 供对照） | `source` | `web_source`（不直接用于引用统计） | `source` |

`related_queries`、`search_model_queries`、`ads`、`products` 都不是来源列表。

## 字段代数（新旧格式批次）

供应商 2026-09-18 起分批切换到新格式，**同一轮采集里不同平台可能新旧混杂，同一平台跨批次也会混杂**，统计前先看字段判代数。判据只有一条：**引用条目里有没有 `cited_count`**——按文件/按格判，不要按平台名或日期一刀切。

| 代 | 判别特征 | 覆盖（截至 2026-10-13） |
|---|---|---|
| **新格式** | 引用条目带 `cited_count`（AI Mode / AIO 另有 `index`，AIO 还有 `type`），来源列表**已去重** | 五平台均有批次命中：AI Mode、AIO（2026-09-18 起）、Gemini（2026-10-08 起去掉重、10-10 起带计数）、ChatGPT（**2026-10-13 起**带计数）、Perplexity（10-13 探针） |
| **旧格式** | 无 `cited_count`；Gemini 未去重（同 URL 重复 + 片段拆分）、AIO/AI Mode 有「裸桩+完整」成对重复（见 [缺陷 D8](defect-catalog.md#d8--引用列表伪重复警告仅旧格式批次)） | 全部历史批次，含 **ChatGPT 10-10 及更早**、**AIO 10-10 那批里正文未引用的来源条目**（AI Mode 写 0，AIO 直接省略该字段） |

新格式已实测：`sum(cited_count)` == 正文 pill 出现次数（2026-09-21 的 16/16；2026-10-13 五平台逐题复核，ChatGPT 14=14、Gemini 16=16、AI Mode 15=15、AIO 24/24 条、当天新采 3=3），即**一份字段同时给了引用次数与去重来源两个单位**。旧格式的伪重复折叠规则只适用于旧格式；对新格式数据套用折叠应是无操作（没有伪重复可折叠），若折叠改变了数字说明判代数出错。

**缺字段的语义是「0 次」不是「未知」**：`cited_count` 缺省或为 0 的条目，是列进来源清单但正文没有引用它，计 0 次，但仍算一个去重来源。AIO 的 `type=product` 商品卡（`index=null`）没有该字段，不产生引用行。

## 两个计数单位，必须同时给出

来源网页和引用位置分别计数：

- **引用次数（occurrences）**：正文引用标记的出现次数。同一来源被引两次就算两次。
- **去重来源（unique sources）**：按规范化 URL 去重后的来源页面数，只用于来源清单展示。

依据：`collect-test-20260914/citation_policy.py` 的 `display` 字段——「Group counted events by normalized URL only for the right-hand source list」；以及 `citation-field-mapping.md` 对 Overview 0001 的实测——26 次标记、24 次计入、9 个唯一页面。

**对外只说一个数时必须写明是哪个单位。** 说「4 次引用」而对方按来源页面理解会变成 3。

## URL 规范化

去追踪参数（`utm_*`、`gclid`、`fbclid`、`mc_*`、`ref_*`、`_gl`、`igshid`、`srsltid`、`fp`、`fs`、`smid`、`source`、`campaign`）与 fragment，域名小写，路径去尾斜杠。去重后仍保留原始引用位置、分组与展示次数。

## 缺失状态必须分开

| 状态 | 含义 |
|---|---|
| `[]` + `not_observed` | 检查了已保存的相关区块，本条没有该类节点 |
| `null` + `not_captured` | 快照没有相关区块或数据，不能判为平台没有 |
| `null` + `not_applicable` | 本次界面不属于这类数据场景 |
| `partial` | 有一部分记录，但成员关系或 URL 不完整 |

不能用空数组同时表示这四种状态。
