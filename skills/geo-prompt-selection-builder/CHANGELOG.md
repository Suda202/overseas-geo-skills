## 3.3.3（2026-11-10）审核返修用完后脚本删题兜底

触发依据：研发 2026-11-10 用线上代码跑 5 个品牌，其中一份 42 题的题库里 3 道题面写「美国提供服务/备件支持」却没写 `condition_basis`，审核返修一轮后复核仍阻塞，整库判生词失败。设计本来是丢题不丢库，但删不删全靠 agent 自觉。只改失败兜底，审核标准和门禁不动。

- `run_selection_mode.py` 新增 `drop_blocked_questions()`：审核返修轮次用完仍有阻塞时，脚本删掉阻塞发现指向的题，题号与审核原文记进 `config.retired` 和 notes「删题（脚本兜底）」，删空的主题连登记一起删、矩阵行去掉 `topic_id` 并注明本期不出；删前题库存 `out/bank.before-drop.json`；再跑校验和导出，通过即交付，`review.status=dropped`、`review.dropped` 列明删题。删完仍没过或发现没写题号，照旧判生词失败。
- `online-runner.md` 审核环与 `review` 块状态说明同步；脚本退出码说明同步。
- 验证：`evals/e2e_review_loop.py` 14/14 通过（场景 6 改为删题后交付，新增 6b 主题级阻塞仍失败）。
- 改前快照：项目根 `.snapshots/run_selection_mode.py.*`、`e2e_review_loop.py.*`、`online-runner.md.*`。

## 3.3.2（2026-11-10）补 requirements.txt

触发依据：Suda 2026-11-10 指出选词 skill 的脚本缺依赖清单，仓库里也没有。只补清单和文档指向，不改任何规则和脚本。

- 新增 `requirements.txt`：两个第三方包，`lingua-language-detector>=2.2.0,<3.0.0`、`claude-agent-sdk>=0.2.171,<0.3.0`，每个包下注缺了会怎样。Python 下限写 3.12（lingua 2.2.0 的 `Requires-Python`；只装 SDK 时 3.10 起）。
- 依赖面用 AST 扫过全部 `scripts/`、`evals/` 和 `../shared/scripts/`：除这两个包外只用标准库，`geo_presales_core` 包本身也没有第三方依赖。两个包都是可选的：`lingua` 只在 `validate_after_sales_set.py` 的语种门禁里用，缺了跳过并给 W32；`claude-agent-sdk` 只在 `run_selection_mode.py` 的 `_run_sdk()` 里延迟导入，走 `--agent-cmd` 或自己写 `bank.json` 都不用装。
- SKILL.md「参考与脚本」加一句安装说明，维护节里的 `pip install lingua-language-detector` 改为指向 `requirements.txt`。
- 验证：Python 3.14 干净 venv 里 `pip install -r requirements.txt` 装上 SDK 0.2.180 和 lingua 2.2.0，`from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage` 通过，validator 带 lingua 跑样例不再报 W32；无 lingua 的 venv 里 validator 和 `run_selection_mode.py --help` 都正常（W32 按设计给出）。`check_skill_terms.py`、`test_validate_after_sales_set.py`（63 passed）、`evals/verify_workflow.py`（67/67）通过。
- 改前快照：项目根 `.snapshots/SKILL.md.20261110-155738.bak`。

## 3.3.1（2026-11-10）字段「本期产品线」改名「产品线」

触发依据：Suda 2026-11-10 指示，字段名不需要「本期」（每期只做一条产品线已写在规则里）。只改字段名，规则不变。

- `scripts/normalize_case.py`：必填字段改为「产品线」；加 `RENAMED_FIELDS`，传旧名「本期产品线」照收、按「产品线」记，给 `renamed_field` 警告（线上表单未必同步改名，不报错）；两个都传时用「产品线」。
- 同步改名：input-contract.md（字段表加旧名照收说明）、selection-rules.md、client-facing-base.md、demand-side-signals.md、online-runner.md、`run_selection_mode.py` 任务说明、两份输入示例、shared 两份公开模板、`check_skill_terms.py` v2 字段说明；report-builder `build_report_data.py` 的 `load_case` 认「产品线」，旧名「本期产品线」仍认。
- `check_skill_terms.py` 退役说法加「本期产品线」。
- `evals/e2e_input_contract.py` 改用新字段名，加一条旧名照收用例。
- 飞书同步：《AI 搜索监测｜品牌资料收集》rev 567、研发文档《售前诊断生词优化》rev 235、《生词规则》rev 788，`本期产品线` 全部改为 `产品线`，其余内容逐字未动（改前改后 markdown 对比）。模板 Base 无此字样；已交付的客户 Base 不改。
- 改前快照：项目根 `.snapshots/*.20261110-152113.bak`。

## 3.3.0（2026-11-10）锁版证据门槛、品牌方数据定位、去掉 Case 说法

1. **锁版证据门禁对齐现实**。触发依据：Suda 2026-11-10 确认《品牌资料收集》第二部分（GSC、关键词工具、销售、客服数据）实际是选填，售前诊断阶段大部分客户不会提供；原门禁「证据级别不到一手不能锁版」（`after_sales_signal` 也挡）与现实冲突。改为：只有 `evidence_status: "hypothesis"`（整份题集没有任何买家信号，全靠推测）不能锁版；`after_sales_signal`（评价、社区、搜索数据等公开买家信号撑起的题集）加品牌方确认正式题即可锁版；`first_party_data: false` 只让就绪结论最高 Usable、交付说明写清还能补什么，不挡锁版。
   - `scripts/validate_after_sales_set.py`：锁版检查（lifecycle 为 locked / formal_baseline / active）和正式基线元数据检查都只挡 `hypothesis`，报错文字改为 `hypothesis evidence cannot be marked formal-ready`；就绪封顶逻辑不变。
   - `scripts/test_validate_after_sales_set.py`：删「after_sales_signal 不能锁版」用例，新增 `lockable_bank()` 夹具（两次确认、试跑通过）和两个用例：after_sales_signal 已确认可锁（退出码 0、仍封顶 Usable）、hypothesis 不可锁（只报这一条错）。
   - `references/output-contract.md` `evidence_status`、`first_party_data` 两行和「锁版」一条；`references/selection-rules.md` 交付节；`geo-monitoring/references/trial-and-lock.md`「选正式题与锁版」的「锁版」一条加证据门槛（同文件今天早些时候「品牌读数不进选题」加的饱和剔除段保留）。
2. **《品牌资料收集》第二部分定位为「售前不收、售后选填」**。触发依据同第 1 条。`references/selection-rules.md` 第 1 步数据清单前加一条：售前不向品牌方要；签约后选填，给了用于把证据升到一手、补需求信号，优先级最高的是销售常被问到的问题和客服高频问题；不给不影响流程、不挡锁版。`references/demand-side-signals.md` 开头加同样的定位，并说明下文「优先提供」是选填前提下的先后。
3. **人读文字去掉「Case」，统一叫「品牌资料」**。触发依据：Suda 2026-11-10 要求去掉 Case 概念。改了 SKILL.md（英文 description 改 brand intake 表述、正文和表格）、`references/selection-rules.md`、`references/online-runner.md`、`references/input-contract.md`（标题改「品牌资料输入合同」）、`references/output-contract.md`、`references/signal-sources.md`、`references/demand-side-signals.md`、`scripts/run_selection_mode.py` 的 docstring / help / TASK 叙述、`shared/scripts/cost_report.py` 一处说明。接口全部不动：schema 名 `presales-case-input/v2`、顶层键 `case`、`case_fields`、`normalize_case.py`、`--case`、`inputs/case-normalized.json`、`DATAFORSEO_CASE`、DataForSEO 流水里的 `case` 字段，等研发有结论再说；input-contract.md 和 online-runner.md 各加一句「case 字样是历史命名」。online-runner.md 第 1 步顺手删掉「Case 的『业务目标』只当业务重点线索」一句：该字段 2026-11-09 已退役、传进来报 `retired_field`。
   - 不把「Case」加进 `check_skill_terms.py` 的退役说法扫描：接口名、文件名和 CHANGELOG 里到处是 case，扫描会误报。
   - evals 脚本标题里的「Case 输入合同」未改（只是测试报告标题）。

- 改前快照：项目根 `.snapshots/*.20261110-113327.bak`（SKILL.md、CHANGELOG.md、output-contract.md、selection-rules.md、demand-side-signals.md、online-runner.md、input-contract.md、validator 与测试、run_selection_mode.py、cost_report.py、trial-and-lock.md）和 `signal-sources.md.20261110-113734.bak`。

## 3.2.0（2026-11-10）线上审核环

触发依据：Suda 2026-11-10 要求线上加审核环，审核模型由宿主配置。

1. **runner 加审核阶段**（`scripts/run_selection_mode.py`）：`run` 在校验和导出第一次都通过后，写 `REVIEW.md` 让新开的审核 agent 按 `references/review-rubric.md` 八条核对 `out/bank.json` 和 `out/notes.md`，发现写进 `out/review.json`（只写这一个文件）。走现有 `run_agent`，tag `-review`，agent 记录自动进 `costs.llm`。`--agent sdk` 时审核用 `AGENT_REVIEW_MODEL`（没设用 `AGENT_MODEL`），`--agent-cmd` 时 `TASK_FILE` 指向 `REVIEW.md`、模型由宿主定。
2. **阻塞发现回喂返修**：`blocking: true` 的发现按返修报错格式（`[review] <题号> 第 <n> 条：…（建议：…）`）写成 `REVIEW-REPAIR-<n>.md`，返修后重跑 finalize，再用 `REVIEW-<n>.md` 只复核上一轮报过的题号；`--review-rounds`（默认 1，0 关闭）用完仍有阻塞才判失败，退出码 1。最后一轮审核返修同样授权丢题不丢库；返修把校验改坏时，下一轮把校验报错和未修的阻塞发现一起回喂。审核轮次不占 `--repair-rounds` 额度。`REPAIR_TASK` 抽出 `why` / `extra` 两个占位，原返修任务文字不变。
3. **非阻塞发现**：不触发返修，记进 `out/result.json` 的 `review.nonblocking`；本来就要审核返修时，返修任务顺带要求写进 `notes.md`「评审意见」一节。
4. **不当闸门**：`review.json` 缺失、不是合法 JSON、结构不对（要是数组，每条有非空 `problem` 和布尔 `blocking`），或审核 agent 超时、出错，只在 `review.warnings` 记一条，照常交付。审核 agent 改了 `bank.json` 时恢复审核前的题库并记 warning。
5. **`out/result.json` 加 `review` 块**：`rounds`、`blocking_found`、`nonblocking_found`（各轮累计）、`status`（`passed` / `repaired` / `skipped` / `review_failed`，`review_failed` 用 `reason` 区分审核没产出和阻塞没修完）、`review_repair_rounds`、`warnings`、`nonblocking`、`blocking_unresolved`；写块时重数一遍 `costs`，审核轮的 usage 才算得进去。
6. **评审清单**（`references/review-rubric.md`）：八条核对一字未动；「输出格式」改为写进 `out/review.json` 并列出每条的键（`question_id` 可写题号数组），「约束」按 runner 实际做法改写阻塞 / 非阻塞的去向，加一条 review.json 坏掉不挡交付。
7. 文档：online-runner.md「怎么跑」加「审核环」小节、「验收」加新 e2e；SKILL.md 脚本表和维护节验证命令加 `evals/e2e_review_loop.py`。

- 测试：新增 `evals/e2e_review_loop.py`（假 agent 走 `--agent-cmd`），七条路径 13 项检查全过，结果写 `reports/review-loop-e2e.md`；`e2e_repair_loop.py` 在默认开审核下仍全过（假 agent 不写 review.json，审核记 review_failed、不影响交付）。
- 改前快照：项目根 `.snapshots/*.20261110-112225.bak`（runner、review-rubric.md、online-runner.md、SKILL.md、CHANGELOG.md）。

## 3.1.0（2026-11-10）每轮自动记账

触发依据：Suda 2026-11-10 要求每轮自动记账，统计口径为每客户平均花费。估算见 `30-选Topic与生词/方案/研究与评审/生词单轮成本估算-20261110.md` 末节「怎么把估算换成实测」。

1. **runner 记 LLM 用量**（`scripts/run_selection_mode.py`）：`_run_sdk` 从 `ResultMessage` 取 `usage` 四个计费字段、`duration_ms`、`duration_api_ms` 和 `total_cost_usd`，写进 `logs/agent-run{tag}.json`（主跑和每轮返修各一份）；`total_cost_usd` 改名 `total_cost_usd_anthropic_price_unreliable` 原样留存，因为 SDK 按 Anthropic 价算，网关后面是别家模型时不可信。每份记录加 `started_at`，`out/result.json` 加 `prepared_at`。
2. **`out/result.json` 加 `costs` 块**：`brand`、`market`、`llm`（各轮 usage 加总和次数）、`scrapeless_requests`（预跑 attempt 行数和成功数、`research/**/serp*/raw/*.json` 数、`logs/net_cache/` 里经 Scrapeless 代理的页数和搜索次数）、`dataforseo`（服务端流水按 `DATAFORSEO_CASE` 和本轮时间窗过滤，不含沙盒）。只记数量和用量，不乘单价；每次 finalize 重数一遍，返修后的结果包含全部轮次。
3. **网页缓存按工作目录隔离**：`shared/scripts/net.py` 加环境变量 `NET_CACHE_DIR`（不设时仍是 `/tmp/hb_net_cache`），runner 设成 `logs/net_cache`，代理页数才能按轮归集。代价：不同 Case 之间不共享网页缓存和直连被拦域名记录，同一页面在两个 Case 各付一次。
4. **报表脚本** `shared/scripts/cost_report.py`：扫描选词工作目录和采集目录，读 `costs` 块、数 `_collector/events.jsonl` 的 attempt 行（客户取路径里「评测数据/<客户>/」，取不到的归「未归集」并列出）、按 case 汇总 DataForSEO 流水，输出每客户花费和平均每客户；`--since` 按日期过滤，`--alias` 合并同一客户的不同写法，名字带 test / 测试的记账测试单列不进平均。单价只读本机 `~/.geo-cost/prices.json`，脚本里不写任何单价；`--write-example` 生成示例配置（内部单价留 0）。
5. 文档：online-runner.md「怎么跑」加「每轮记账」小节；SKILL.md 脚本表加 `cost_report.py`。

## 3.0.0（2026-11-10）定稿冻结版

触发依据：`30-选Topic与生词/方案/生词方法论定稿-20261110.md` 第四节「定稿前最后一批减法」8 条、四b「门禁严度排查」和第四节表格后的「两处文字修正」。本版之后正文按定稿第五节「改动协议」冻结：改正文只认线上真实失败、品牌方或销售书面反馈、试跑或基线证明产出错题三类触发，CHANGELOG 每条记触发证据。

1. **线上瘦身**（`scripts/run_selection_mode.py` prepare）：不再拷贝 `geo-monitoring`，TASK 加一句「指向 geo-monitoring 的链接是锁版阶段规则，线上不读」；`geo-presales-report-builder` 只拷 `scripts/`。查 `collect_answers.py` 的导入发现它在模块加载时就要 `geo-presales-report-editor/scripts/geo_presales_core` 和 `geo-presales-crawl-integrity/scripts/audit_crawl_integrity.py`（后者再读同 skill 的 `references/platform-contract.json`），旧版 prepare 这两个都没拷，工作目录里的 `collect_answers.py --help` 直接 `ModuleNotFoundError`；现在按最小集合拷这三样（`PARTIAL_COPIES`），实测工作目录里 `--help` 正常。另把 skill 目录里 lark-cli 落下的 Base 导出（`tbl*.ndjson`、`tbl*.manifest.json`、`tpl_*.manifest.json`）加进 `IGNORE`。TASK 加跳读清单：selection-rules.md 里对客 Base 写法、品牌方资料流程、售前主题重聚对账三类小节线上跳过。online-runner.md「怎么跑」同步。
2. **删 `changeability` / `changeability_basis`**：选词阶段取值只能是「待试跑」，判定依据（引用域名结构）试跑后才有，归监测侧（`geo-monitoring/scripts/changeability_domains.py` 照旧写回题库，选词不读）。output-contract.md 题字段表删这一行；online-runner.md 第 7 步删「写待试跑」；client-facing-base.md 提示词库删「可改变性」列和隐藏列提法；validator 删 `CHANGEABILITY` 取值检查；`check_client_base.py` 把提示词库「可改变性」列入已移除字段，「信源壁垒」的现行说法改为「归监测侧」。
3. **`business_goals` 常量化**：只做发现期间，validator 对缺失的 `config.business_goals` 按 `{selected: ["发现型可见度"], information_named: false}` 填充（`DEFAULT_BUSINESS_GOALS`），W49 只报写了但写法不对；默认填充后 W52 照查。删休眠门禁 W50、W51（及只为 W50 服务的 `competitor_rows`）。type-branches.md「开放时要改的地方」加第 6 条「恢复 business_goals 必填与 W50 / W51」。selection-rules.md → 1、output-contract.md、online-runner.md 第 1 步同步。
4. **W59 删第二阈值**：去掉「8 个不同购买决策」（`TOPIC_DECISION_FLOOR` 与决策签名计数），只留「每发现主题至少 10 道、每道一个不同购买决策」一个数；每道是否不同仍按第 7 步「去重看购买决策」人工判。output-contract.md W59 描述同步；selection-rules.md 硬要求 3 在 2.62.0 已是单一数字，未改。
5. **主题同档排序砍为一级**（selection-rules.md → 6「主题优先级」）：同档只按点名条目序号排（对应第 1 条在前，只对应我方补充处境的在后），搜索量写进依据作参考、不参与排序；删「先排发现类主题 → 条目序号 → 搜索量」三级瀑布和「月搜索量取哪家的」强制取数段。原段里全书唯一的「展示量不算搜索量」定义和取量方法搬到 signal-sources.md 新小节「月搜索量取哪家的（关键词工具）」，signal-sources.md 两处、client-facing-base.md 一处原指向 selection-rules 的引用改指新位置。总纲档位表、client-facing-base.md 主题表、SKILL.md 步骤表同步。
6. **非发现行只登记、不判档、不进对客确认表**：selection-rules.md → 5（「意图类型：八类」末段、「业务优先级」的非发现行条目、查漏段）改为非发现行只写进 `config.slices`、开行依据照写、不写 `priority`；type-branches.md「业务优先级上限」整节标为开放对应目标时启用、本期暂不执行，「开放时要改的地方」加第 7 条反向步骤；output-contract.md `slices` 说明去掉「和其他行一样写进对客确认表」、门禁 43 只查发现行；client-facing-base.md 提示词矩阵只放发现行；validator 对非发现行缺 `priority` / `priority_basis` 不报错；`check_client_base.py` 见到非发现行报「从对客表删掉」并不再查其档位。
7. **重聚对账阈值**（selection-rules.md → 6「报价与交付的先后」）：删「个数差不超过 1 / 差 2 个及以上」，改为被采购的主题有变动必须书面告知品牌方确认，其余调整在交付说明里写明；client-facing-base.md 主题表同步。
8. **TASK 明写题量硬限**：候选 30–60 道、每个导出文件 ≤60 条，超出先砍中档行里证据最弱的题（validator 对超 60 只告警 W47，导出却报错，agent 不改就白跑一轮返修）。online-runner.md 第 7 步同步。
9. **两处文字修正**：总纲「只测买家真在问、有机会推动的问题」删「、有机会推动」；第 6 步主题判法「问买家会不会拿这类东西换那类东西（看用途、特性、价格）」2.62.0 已在「怎么聚」里，未重复加。

- 测试：pytest 删 W50 / W51 用例，加缺失 goals 默认填充、默认填充后 W52 照查、W50 / W51 已删、W59 只看 10 道、非发现行不判档五处断言（62 passed）；`verify_workflow.py` 改「行没定档」用例到发现行，新增非发现行不判档、goals 缺失默认、goals 写错告警、changeability 不读四个用例，`check_client_base` 的类型行用例改为非发现行要报（67/67）。
- `check_skill_terms.py` 加 8 组退役说法（有机会推动、个数差阈值、三级排序、指向 selection-rules 的取量、8 个不同决策、changeability 待试跑、非发现行照常判档进对客表、business_goals 一律写 / 必须写）；原 2026-11-02 那条「不写进对客表」严格规则收窄到低档发现行，避免和本版非发现行不进对客表冲突。
- 改前快照：项目根 `.snapshots/*.20261110-104950.bak`（本 skill 14 个文件）。

## 2.65.0（2026-11-09）约束列统一叫「约束条件」

Suda 指出 2.64.0 的做法是把补丁当修复：发现 `scope_gates.py` 读 `约束`、文档写 `约束条件` 后，只在文档里加了一句「键名是 `约束`」，两边还是不统一，下一个照文档写的人照样会踩。

统一到 `约束条件`——对客 Base 需求信号页的列名、三个采集脚本的 `signals.csv` 列名、第 2.25.0 版起的字段改名结果，用的都是这个名字；只有 `scope_gates.quote_index` 还停在旧短键名 `约束`。

- `shared/scripts/scope_gates.py`：`quote_index` 改读 `约束条件`，`constraint` 英文别名保留，**旧键名 `约束` 继续兼容**（2.65.0 之前写的题库照读）。文件头那段「11-04 起对客 Base 不再记录约束」的说明已过时（对客表现在把约束条件列为必填两列之一），一并改正。
- `references/output-contract.md`、`references/online-runner.md`、`run_selection_mode.py` 的 TASK：去掉「键名必须是 `约束`」的告警，改为「键名就是 `约束条件`，和 Base 列名、signals.csv 一致」。
- 测试：`QUOTES` 改用 `约束条件`；新增 `QUOTES_LEGACY_KEY` 与 `test_legacy_quote_key_is_still_read`，锁住旧键名兼容。60 passed。
- 端到端实测：`约束条件`、`约束`、`constraint` 三种键名都能被 W36 正确读到；条件对不上时仍报 W36。
- 存量数据不迁移：三份客户旧题库用的是 `约束` 旧键名，靠兼容分支继续可读。

## 2.64.0（2026-11-09）线上必填需求信号；线上不读对客表与品牌方数据文档

Suda 定，起因是查线上 token 消耗时发现：6 次线上实跑（`80-代码/选词工具-harness-AB/runs/`）的 `config.buyer_quotes` 全是空数组，而线上 TASK 里从来没要求 agent 写它。后果是 W36（题面条件没有依据）、W37（同一决策问两遍）两道门禁整段跳过，validator 报「0 错误 0 告警」其实是没查；题上的 `evidence_refs` 也只能填自己的题号，一回事都追不到。

- `scripts/run_selection_mode.py` 的 TASK 加「需求信号（必填）」一节：调研收到的买家原话、搜索词、AI 检索词里只登记撑起某道题的几条，写进 `config.buyer_quotes`；`evidence_refs` 填信号编号不填题号；挂不上原话的题必须写 `condition_basis`。`out/notes.md` 节清单加「需求信号」。
- `references/online-runner.md` 加「需求信号必须填」一节，并同步 notes 节清单。
- **键名坑**：`buyer_quotes` 里约束那一列的键名是 `约束`，不是 `约束条件`（对客 Base 的列叫「约束条件」，题库 JSON 沿用旧键名）。`shared/scripts/scope_gates.py` 的 `quote_index` 只读 `约束`，写成 `约束条件` 门禁读不到、静默失效。已用三个样本实测：键名写对时正常核对，写错时连合法的「200 美元」都被判成无依据。`references/output-contract.md` 的 `buyer_quotes` 行把这处写清。
- **线上不拷两个文件**：`run_selection_mode.py` 的 `IGNORE` 加上 `client-facing-base.md` 和 `demand-side-signals.md`。前者只用来建对客确认表，线上不建表；后者是拆出来的品牌方数据文档，线上没有客户资料。一次跑单次少读约 38KB。
- **`signal-sources.md` 拆分**：把「客户提供什么」「品牌方填写的业务信息」「品牌方提供的数据」三块搬到新文件 `references/demand-side-signals.md`，原文件留一句指针。`signal-sources.md` 从 19,984 字符降到 13,081（线上读这份），新文件 7,337 字符（线上不读）。`client-facing-base.md` 里两处指向 `signal-sources.md → 客户提供什么` 的链接改指新文件，`online-runner.md` 第 2 步同步。
- 验证：`check_skill_terms.py` 通过、`pytest scripts/test_validate_after_sales_set.py` 59 passed、`evals/verify_workflow.py` 65/65、`e2e_input_contract.py` 与 `e2e_repair_loop.py` 全过。改前快照 `.snapshots/*.20261109-2026xx.bak` 与 `.snapshots/signal-sources.md.split-20261109-202835.bak`。

## 2.64.0（2026-11-09）列序按实际填充率排

Suda 定。用某制氧机客户那份表 198 条信号统计了每个字段的填充率，发现需求信号的「月搜索量」只有 4.5% 有值却排在第 6 列，品牌方扫表时看到一大片空白会以为没填完；主题表的「父关键词」「月搜索量」两个结构化字段全空，量只写在依据文字里。模板与某制氧机客户表都已调：需求信号把月搜索量、引用它的问题收到尾部；主题表把父关键词、月搜索量提到依据前面。Suda 明确编号类字段不重要，不往回加。

## 2.63.0（2026-11-09）信号登记按目录收齐；对客表首次写入的重复与空值防护

Suda 定，起因是某制氧机客户 PocketDevice 那次交付：选词规则本身写得清楚，但执行时漏了脚本产物——只读了子代理手收的那份社区原话，DataForSEO 的 10 条搜索量和搜索侧 133 条搜索联想都没进需求信号表，对客表里信号停在 72 条。同期部署脚本跑了两遍，业务范围整表翻倍，成对重复在表格里很难一眼看出。

- selection-rules.md → 2 收需求信号：脚本产物按目录收齐再登记，不凭记忆挑；「会改变选词判断」是筛掉无关条目，不是只挑几条够用的；剔除了哪些噪声要在交付里说明。
- selection-rules.md → 8：交付前核对三件事，信号来源覆盖本轮跑过的所有工具、写进对客表后回读行数去重、三张表词表一致。
- client-facing-base.md：首次填充要幂等——清空后回读确认 0 行再写，写完全表按主字段统计唯一值；重复后怎么删、单值行的「市场」字段留空、同项目名合法多行的要加编号。译文不强制填：需求信号是内部判约束条件用的，品牌方一般不逐条读原话，要求看中文意思时再填。

# 选词 skill 修订记录

正文（SKILL.md 和 references/）只写现在的规则；规则怎么来的记在这里。2026-11-01 之前每条规则后面带的「Suda 某日」决定记录，完整保留在快照 `.snapshots/selection-simplify-20261101-002909/geo-prompt-selection-builder/`（项目根目录下），包括已合并删除的 after-sales-rules.md、representative-library.md 和被移出的对照笔记。

## 2.62.0（2026-11-09）主题优先级取组内最高行；主题在矩阵阶段定；删掉条件组合数

Suda 定。讨论过取多数行、按高档题数、主干行、看父关键词几种算法，各有算错的情况；调研（`30-选Topic与生词/方案/研究与评审/topic-priority-research-20261109.md`）没有一家用汇总公式定主题优先级，Aleyda 直接给提示词组判档，Profound 直接给属性（主题）判档。产品线已收窄，矩阵行判高的标准又是品牌方点名的核心目标客户与购买场景，所以主题优先级直接取组内最高行。推翻 2.32.0 的「默认取组内多数行」。

- **主题优先级**（selection-rules 第 6 步）：定义为本期 GEO 投入优先级，不是市场机会排名；取组内最高的业务优先级。不看行数、题数、父关键词定档。依据写对应业务范围核心目标客户与购买场景的第几条，以及可买题（最多 10 道）里几道是点名需求。同档先排发现类主题，再按对应条目序号，再按父关键词月搜索量。主题都偏高时回头查矩阵行，不改主题规则；品牌方要调先后，改业务范围顺序或行档位。
- **矩阵行业务优先级**（第 5 步）：高档以品牌方点名为准，要能指出对应第几条；我方补充的处境默认中，依据写「我方补充，请品牌方确认」；没填业务范围时按官网主推判、标「推断」。
- **主题在矩阵阶段定**：判候选是不是同一类问买家会不会拿这类换那类（用途、特性、价格），不用等写完题；写题后、试跑后复核，只有证据说明候选同类或不同类时才调整，边界变了重判主题优先级。业内（Scrunch、Profound、Aleyda 矩阵的 Product / Topic 列）都是先定结构再写题。
- **删掉「至少 8 道的约束条件组合各不相同」**：组合相同的题可能是不同购买决策，组合不同的也可能是同义改写，validator 也没查。改为「每道对应一个不同的购买决策（第 7 步去重看购买决策），不写同义改写凑数」。
- validator W46 改为「主题优先级和组内最高行对不上」；测试与 workflow 用例的期望文字同步。client-facing-base 主题表、output-contract W46、SKILL.md 步骤表、shared/prompt-generation-principles 同步；`check_skill_terms.py` 加退役说法（组内多数行、主干行、约束条件组合各不相同、主题不在矩阵阶段定死）。
- Bbrand、Ubrand、Rbrand 28 个主题按新规则算档位全部不变，三份题库跑 validator 无 W46。改前快照项目根 `.snapshots/topic-priority-20261109-193233/`。

## 2.61.1（2026-11-09）net.py 再提速：被拦域名跳过直连、fetch 多 URL 并发、线上 Reddit 限量

Suda 定取数按「耗时 × 成功率」排，付费且快的可以排在免费但慢的前面。接 2.60.1 的三条：

- **被拦域名跳过直连**：`net.py fetch` 直连被拦（403/429/503/挑战页/超时）的域名记进 `/tmp/hb_net_cache/blocked_domains.json`，7 天内同域名直接走代理；Facebook、X、Instagram、Threads、HardwareZone 默认就在名单里。`--fresh` 不看记录、重新试直连。实测 topuniversities 新页面显示「跳过直连（11-09 直连被拦过）」，29 秒取到。
- **多 URL 并发**：`fetch` 可传多个 URL 或 `--urls-file`，`--jobs` 默认 5 路，按输入顺序输出，末行报取到几个。实测 10 个 topuniversities 页面（`--fresh`，都要走代理）：串行 303 秒取到 10 个，5 路并发 80 秒取到 9 个（Mahidol 那页代理返回 4.5 万字符但被判成挑战页，串行时取到了）。
- **线上 Reddit 限量**：`net.py reddit` 设了环境变量 `NET_REDDIT_MAX` 时，联网请求数到上限就停、提示记进未覆盖来源，缓存命中不计数；`run_selection_mode.py` 给 agent 默认设 10 次、计数在工作目录 `logs/reddit_calls`，宿主可用同名环境变量改。本地不设就不限。实测上限 1 时第二次请求被拦下。
- online-runner.md、community-channels.md 第 5 条、runner 的 agent 任务文本同步（「要读的页面攒成一批一次传」「Reddit 本次最多 N 次」）。输入合同、返修循环两个 e2e 和 check_skill_terms 通过。实测约 22 次 Scrapeless 调用。改前快照项目根 `.snapshots/netpy-speed2-20261109-185358/`。

## 2.61.0（2026-11-09）生词不设上限，售卖以一个主题 10 道正式题为上限

Suda 定：生词（候选题）没有上限，售卖时一个意图（主题）10 道提示词是上限。推翻 2.33.0（2026-11-05）「单个主题不设上限」在正式题上的部分；候选阶段不设上限照旧。

- **门禁 14**：锁版后除每条产品线 × 国家 × 语言最多 60 道外，正式题合计不超过 10 × 有正式题的主题数（`TOPIC_SALES_CAP = 10`），超出报错。按合计算，不按单个主题卡：混合选择时某个主题可以超过 10 道（用它补别的主题的名额）。候选阶段不查。测试 `test_formal_set_caps_each_topic_at_ten`（10 道过、11 道错、4＋16 过、4＋17 错、停测不计、候选不查）。
- selection-rules 第 6 步硬要求 3、client-facing-base、output-contract 门禁 14、geo-monitoring trial-and-lock「选正式题与锁版」、shared/prompt-generation-principles.md 同步：生词时发现主题至少写 10 道、候选不设上限；售卖一个主题 10 道为上限。`check_skill_terms.py` 把「单个已采购主题不设上限」等写法加进退役清单，原来退役的「每主题最多 10 道」那条按本次决定撤掉。
- 飞书《生词规则》同步到 rev 775（第 1 节宁少而准、流程总览第 11 步、8.1 硬要求、11.2 选正式题），本地同事版副本用回读覆盖。改前快照项目根 `.snapshots/sale-cap-10-*`、`.snapshots/feishu-生词规则-pre-salecap-*`。

## 2.60.1（2026-11-09）net.py fetch 提速：去掉代理开 JS 重试、直连 15 秒超时、成功结果缓存

Suda 问线上调研从速度看取数顺序要不要改。同日实测 3 个直连 403 的站（Trustpilot、topuniversities、RivalH1）：直连约 1 秒；`render` 3/3 在 68 秒超时；Scrapeless 代理不开 JS 13–46 秒取到，开 JS 没有一次更好；Wayback 3/3 返回 429。改前一个被拦页面失败要 46–65 秒。上一轮提的「被拦后先 render 再走代理」按这组数据作废。

- `shared/scripts/net.py fetch`：代理只调 1 次（不开 JS）；直连超时 60 → 15 秒；成功结果按 URL 缓存在 `/tmp/hb_net_cache/fetch_*.json`，`--fresh` 跳过；读不到时报直连、代理、Wayback 三段状态；直连 200 但正文不到 500 字符时提示改用 `render`（不缓存）。
- `--country` 要填目标市场：topuniversities 用 SG 节点失败、US 节点 25 秒取到。online-runner.md 和 `run_selection_mode.py` 的 agent 任务写明 `net.py fetch <url> --country {market}`、被拦页面不再试 `render`；`render` 在服务器上要装 Chrome 并设 `CHROME_PATH`。
- signal-sources.md「调研子代理怎么取数」、community-channels.md 第 2、3 条改成新顺序。
- 改后复测：topuniversities 24.5 秒、RivalH1 44.3 秒取到，第二次取缓存 0.0 秒；不可达地址 19 秒失败（原来最多约 60 + 300 秒）；Trustpilot 仍取不到（评价走 `collect_reviews.py`，不受影响）。实测共约 12 次 Scrapeless 调用。改前快照在项目根 `.snapshots/netpy-speed-20261109-184638/`。
- geo-article-polish / geo-article-research 两个 skill 里「403 再退 render」的写法没改。

## 2.60.0（2026-11-09）按主题售卖，一个发现主题 10 道；锁版记品牌方选择方式

Suda 定：我们按一个意图（主题）10 道提示词售卖，题数下限跟售卖单位走；同时记录品牌方实际是只选一个主题还是跨主题混合选，攒几单后判断按意图售卖是否合理。依据是同日的 5 vs 10 对照（项目 `30-选Topic与生词/研究与方法/主题题数5vs10-20261109/结论.md`）：4 组试跑答案里，随机 10 道比随机 5 道多发现的主要是被引来源（反复被引域名覆盖 67–77% → 92–98%），竞品名单只多 0.3–1.4 个；同样 10 条回答，10 道各跑 1 次比 5 道各跑 2 次发现得多；约束多的主题（某车载品牌 CarPlay 屏 8 类重要约束）5 道会漏，约束少的主题（Ubrand）5–6 道已在重复同一类约束。

- **selection-rules 第 6 步硬要求 3**：每个发现主题至少 10 道、其中至少 8 个不同约束条件组合（原 5 道 / 4 个）；其他意图类型的主题本期不单独售卖，仍按至少 5 道提醒。补题顺序不变；三步做完仍不足 10 道的不写重复题凑数，品牌方可以用其他主题的题补足 10 道（混合选择），处理记录写进 `warning_decisions`。「分组与售卖分开判断」「粗细复核」两处的 5 道同步改。
- **validator W59**：门槛改成常量 `TOPIC_FLOOR = 10`、`TOPIC_DECISION_FLOOR = 8`、`OTHER_TOPIC_FLOOR = 5`；提示语加「仍不足时不凑重复题，可用其他主题的题补足（混合选择）」。仍是告警，不是报错。output-contract W59 一行同步。
- **geo-monitoring trial-and-lock**：挑题写明每个已采购发现主题选 10 道；锁版新增「记选择方式」，写 `config.purchase_selection`（`mode` 单主题 / 混合、`topics` 每个主题几道、`reason`），output-contract 登记这个可选字段，不设门禁。
- SKILL.md 第 6 步、shared/prompt-generation-principles.md 售后段同步；`check_skill_terms.py` 加退役说法（主题至少 5 道等）。
- 现有题库回归：某车载品牌 T3（5 道）、Bbrand T1/T2（6、7 道）、Ubrand 17 个主题（5–8 道）现在都报 W59，按硬要求 3 处理；Hbrand 现行题库是旧结构，validator 不支持，照旧。改前快照项目根 `.snapshots/topic-floor-10-*`。

## 2.59.0（2026-11-09）提示词优先级加回、劣势降题档；出题原因精简；对比题按买家决策选比较条件


Suda 定：提示词库加回「提示词优先级」，落在品牌明显劣势上的题降一档；出题原因太长没人看，精简。起因是 Bbrand：提示词库看不到档位，35 道题出题原因中位 291 字，风险提示排在第 288、385 字之后，品牌方挑题时看不到。推翻 2.39.0（撤字段）和 2.32.0（劣势只提示不降档）。2.39.0 撤字段的理由是「没有独立信息、让模型以为要判三次」，这次字段由脚本算、不人工判，理由不再成立。

- **提示词优先级**：等于所属切片的业务优先级；题上记了 `brand_weakness` 的降一档，低档不再降，验证题不降（它问的就是靠不靠谱，劣势正是要看的风险）。只降题、不降行。`write_prompt_reasons.py` 算出写入，不手改；品牌方要提前某道题，改行档位后重跑。selection-rules 总纲档位表、第 3 步、第 5 步，client-facing-base 提示词库，geo-monitoring trial-and-lock 挑题顺序同步。
- **出题原因**：一两句。降档写「降为中：品牌在 X 上不如 Y（出处）」、验证题写「风险：……」、行依据带「假设」的写一句请品牌方确认，都放开头；再写哪类买家（使用场景）问什么、看 AI 什么；最后接题上的 `reason_note`（拆题理由、复合条件真实性）。不再写证据计数、代表原话和行的业务优先级依据（看证据列和提示词矩阵）。
- **题库 JSON**：题上新增可选字段 `brand_weakness`、`reason_note`（output-contract）。`priority` 仍不写在题库里。
- **对比题**（同日 Suda 口径，改写 2.58.0）：围绕真实买家决策，覆盖高价值使用场景和关键决策属性；比较条件选会改变最终推荐的，不穷举属性，也不强制每个场景都拆属性对比；落在品牌明显劣势上的照写、按上条降档。type-branches「出几道」「题面怎么写」同步。
- **脚本**：`write_prompt_reasons.py` 加必填 `--bank`（读 `brand_weakness`、`reason_note`），同时写「出题原因」「提示词优先级」，提示词库没有这个字段时退出码 2；删掉证据计数相关代码。`check_client_base.py` 不再把「提示词优先级」当退役字段，`--template` 要求有这个字段，并核对每道题的档位和所属切片、出题原因是否一致。`check_skill_terms.py` 加退役说法（提示词库不设优先级列、品牌明显劣势的提示、出题原因末尾的风险提示、对比题不另挑单一属性等）。
- 同日补：没挂任何买家原话、行上也没写假设的题，出题原因开头写「待核实：这道题没有挂买家原话，条件来自调研推断，请品牌方用销售和客服常被问到的问题核对」（取代 Ubrand `deploy_base.py` 里手补的那句，那段已停用）。
- 模板 Base 和现行结构的客户 Base（Bbrand、Ubrand、Rbrand）的提示词库加「提示词优先级」（单选 高 / 中 / 低），默认视图组内按它排，出题原因按新写法重写并回读一致。Hbrand、Sbrand、Obrand 是旧结构 Base，按「旧 Base 不迁移」不改。改前快照项目根 `.snapshots/prompt-priority-back-20261109-165527/`。

## 2.58.0（2026-11-09）对比题按所在行的使用场景写、明确要 AI 推荐一家

Suda 问 Bbrand 题库为什么有「Bbrand or RivalB4: which 4-channel dash cam records clearer footage around the whole car at night?」（T5-04）：夜间画质是记下的品牌明显劣势，这道对比题自己挑了这个属性当比较维度。讨论过「比较维度避开明显劣势」，查外部做法后没有采用，改按场景写。

- 外部做法：Aleyda「[品牌 A] vs [品牌 B]，用来…」；Profound 第 3 章要求具体使用场景、两个具名品牌、明确要推荐三样齐，「Compare X and Y」会被 AI 打成平局，并主张题要反映想测的意图、不写成希望看到的答案；Semrush「is [competing product] or [your product] better for [problem]」；Peec 把「iPhone vs Samsung Galaxy」改写成「Should I buy an iPhone or Samsung Galaxy?」。四家都没有按品牌强弱挑比较维度。
- type-branches「题面怎么写」：对比题按所在行的使用场景写、题面明确要 AI 推荐一家；不另挑单一属性，只有买家原话在比某一项时才写进题面并挂信号；落在品牌明显劣势上的照写、写风险提示。「出几道」表里「场景取这一行最关键的」改为「取这一行的使用场景」。
- 门禁不改（38 仍只查对比题 `constraints` 非空）。改前快照项目根 `.snapshots/type-branches.md.*-compare-scene.bak`。

## 2.57.0（2026-11-09）撤回 `ranked`：DataForSEO 只用 volume、suggest、trends 和评价

Suda 让先调研生词到底需要哪些搜索数据，再定 DataForSEO 怎么用。结论和证据在项目 `30-选Topic与生词/方案/研究与评审/geo生词搜索数据与DataForSEO接口取舍-20261109.md`。

- 生词要搜索数据回答的只有三件事：需求在不在、买家怎么叫这个东西、同档主题谁先。`volume`、`suggest`（加 `collect_serp_signals.py` 的 PAA）已经覆盖。外部证据：Semrush 比对 ChatGPT 点击流，65%–85% 的提问对不上任何搜索关键词；15 家从业方没有一家直接拿 Google 量当提示词量；DataForSEO 的 AI 搜索量由 PAA 推算。
- 2.54.0 加的 `ranked` 撤回。正式接口实测：一个美国宠物用品竞品域名前 300 条非品牌词只有 32 条和本品类有关（其余是博客流量）；两个非洲小市场手机品牌域名 423 条里 2 条和本品类有关；加品类词过滤后再和 4 个种子词的 `suggest` 比，新增的购买说法只有两个竞品词。竞品付费词 4 个域名共 5 条、全是「品牌 + 国家」；竞品的 AI Overview 引用词同样以博客、型号词为主。实测花费约 0.95 美元，产物在同目录 `dataforseo-ranked-实测-20261109/`；脚本外直接调接口的几次已补记进 `~/.dataforseo/ledger.jsonl`（Case「ranked-test 补记」）。
- signal-sources：删「搜索数据」行和「我方收集的数据」表里的 `ranked`、关键词工具用法行里的 `ranked`；关键词工具行「不能用来做什么」补「估 AI 提问量」「查竞品域名的排名词」两条及依据。
- `collect_keyword_data.py`：删 `ranked` 子命令、`--brand-terms`、`clean_domain`，恢复成四个子命令。沙盒跑通 `suggest`、`volume`，`ranked` 报未知命令，`collect_reviews.py` 照常导入。改前快照项目根 `.snapshots/*.20261109-153113.bak`。

## 2.56.1（2026-11-09）主题表「月搜索量」改成数字字段

Suda 定：父关键词的精确月搜索量直接填进「月搜索量」，不另设「父关键词月搜索」字段，模板也这样改。

- client-facing-base.md 主题表：月搜索量是数字字段，填父关键词的精确月均搜索量（优先 DataForSEO，品牌方给的 Semrush / Ahrefs 也可以）；只有区间时（没投放的 Google Ads 关键字规划师）留空、区间写进主题优先级依据，再用 DataForSEO 补；默认视图按主题优先级、再按月搜索量从大到小排。需求信号表的月搜索量仍是四档单选。
- 取数顺序（Suda 同日补充）：品牌方给了 Semrush / Ahrefs / Similarweb 数据的直接用，不再跑 DataForSEO；没给的才跑 DataForSEO。selection-rules.md 第 6 步「月搜索量取哪家的」是唯一定义处，client-facing-base.md 改为引用；模板和 Ubrand 的「月搜索量」字段说明同步。
- 飞书模板《AI 搜索监测确认表（模板）》主题表：删掉四档单选「月搜索量」，新建同名数字字段（整数、千分位），两行示例填 2,400、320，视图加排序，「主题优先级依据」示例改写；改前快照在项目根 `.snapshots/tpl-scene-rename-20261109/tpl_topics_before_vol.ndjson`。Ubrand 对客 Base 同步，填 DataForSEO 英国精确月均。

## 2.56.0（2026-11-09）评估预跑默认不跑、按需补跑；能力不明确的照常开行

Suda 定：本地选词和线上出词要一致，评估预跑在本地也删掉，按需判断要不要跑。推翻 2026-10-29（1.81.9）的「品牌和业务范围竞品各一道评估预跑」。原因：它当时的三个用途里，判属性池相对竞品已随属性池删除（相对竞品挪到基线后），品牌事实核查随品牌呈现暂停，只剩补约束条件候选，品类认知题和需求信号已覆盖；品牌劣势的类型（说错、各家都一样、没公开、能力缺口）基线后看具体题的答案判更准，选词阶段只按官网规格判能力缺口。外部调研（`30-选Topic与生词/方案/研究与评审/brand-weakness-prompt-inclusion-research-20261109.md`）确认没有一家主张因品牌弱排除题。

- selection-rules 第 2 步：默认只跑品类认知题；评估预跑题有具体需要时按需补跑，问法不变。删「各家强弱的线索留到基线后用」两处。
- 第 3 步「写题前确认硬条件」补一句：品牌能不能做到不明确的（官网没写、品牌方没确认）不算做不到，照常开行，等品牌方确认。
- 同步：SKILL.md 步骤表、signal-sources 预跑答案一行、online-runner 第 2 步与本地接手、type-branches 评估验证一条、geo-monitoring SKILL.md 调研预跑一条。脚本不改（线上 runner 本来只跑品类认知）。改前快照 `.snapshots/eval-prerun-ondemand-*/`。

## 2.55.0（2026-11-09）DataForSEO 按人记账

DataForSEO 一个账户只有一组 API 凭据（官方认证文档：登录名 + 自动生成的 API 密码，只支持 Basic Auth），不能按人发多个 key。Suda 定按人分开记账：
- `collect_keyword_data.py`、`collect_reviews.py` 每次调用要给 `--who`（或环境变量 `DATAFORSEO_WHO`），没给就不发调用；`--case`（或 `DATAFORSEO_CASE`）可选。`--cache-only` 不需要。
- 每次付费调用往 `~/.dataforseo/ledger.jsonl`（`DATAFORSEO_LEDGER` 可改）追加一行：时间、调用人、Case、接口、花费、任务号；同时把 `who=…;case=…` 写进请求的 `tag`，DataForSEO 后台明细里能对上。tag 不进缓存键，旧缓存照样命中。
- `collect_keyword_data.py ledger` 免费汇总，`--by who/case/month` 可叠加，默认不含沙盒。
- `run_selection_mode.py`：宿主把发起人姓名放进 `DATAFORSEO_WHO`；没传时记成「线上选词（未传调用人）」，`DATAFORSEO_CASE` 没传时填「品牌 市场」。
- 实测：沙盒四种情况（缺调用人报错、环境变量与参数两种给法、缓存命中不记账、`--cache-only` 不要调用人）；正式接口 Trends 一次 0.011 美元、Google 地图评价一次 0.00075 美元，返回里都带回了 tag，流水金额与返回 cost 一致。
- 流水只覆盖这两个脚本；DataForSEO MCP 和其他代码直接调接口不进流水。
- 同日研发文档《售前诊断：线上生词改用选词 skill》（rev 188）第 1 节运行环境加 `DATAFORSEO_WHO` 等三项、怎样算做对加一条记账验收，「我方的进度」加一项；本地源 `10-售前诊断报告/PRD/售前诊断-选词模式生词研发改造需求-20261029.md` 同步。

改动：`shared/scripts/collect_keyword_data.py`、`shared/scripts/collect_reviews.py`、`scripts/run_selection_mode.py`、signal-sources「关键词工具」行。改前快照 `shared/scripts/.snapshots/*.20261109-145108.bak`、项目根 `.snapshots/*.20261109-145531.bak`。

## 2.54.2（2026-11-09）文档对齐：语言登记、外部文档同步

- input-contract.md 的 `locale` 已登记语言改为 `en`、`th`、`ru`（`locale-templates.json` 早已有 `ru`，文档漏改）。
- CHANGELOG 里重复的 2.52.1 改为「2.52.0 同日补记」。
- 外部文档按 2.52–2.54 同步：研发需求《售前诊断：线上生词改用选词 skill》（rev 185：删「业务目标」、语言加 `ru`、运行环境要装 `lingua-language-detector`、外部服务加 `ranked_keywords`、上传文件按市场 × 产品线一份）；PRD《售前选词工具》（删业务目标、语言加俄语）；飞书《生词规则》同事版（rev 766：硬条件改「服务路径」、语言按品牌方指定、业务范围行名改「目标客户与使用场景（n）」并按产品线分块、售前竞品与报告补足的分工），本地副本已覆盖。规则不变。

## 2.54.1（2026-11-09）硬条件的「服务路径」改成跨行业定义

Suda 指出「替代型号、桥梁课程、定向名额」是 UNI_A 招生案的例子，换行业对不上。selection-rules 第 3 步改为按作用定义：品牌用别的产品、服务或方案仍能让买家达成目的，按品牌实际业务判断。「补救通道」统一叫「服务路径」（client-facing-base 同步）；geo-monitoring gap-cause-action-table「判劣势前先找服务路径」改为引用这一处定义，不再自列例子。第 2 步资料用途表里残留的「写完题查适配度」（2.26 降档版叫法）改为「品牌明显劣势的提示」。规则不变，脚本不改；改前快照 `.snapshots/*.20261109-141628.bak`。

## 2.54.0（2026-11-09）关键词脚本加 `ranked`：查竞品域名的自然排名词

Suda 拿到一份「DataForSEO 接 4+2 个接口」的方案，让按选词逻辑取舍。只加一个：`collect_keyword_data.py ranked`（Labs Ranked Keywords，`item_types: ["organic"]`、按月搜索量降序、默认前 300 条），只查业务范围里的竞品域名。用处是补种子词扩不出来的同品类说法和竞品词；售前拿不到 GSC 时它是唯一能看到竞品那边真实搜索说法的来源。排名位置、排名页面不进选词，脚本不输出。`--brand-terms` 给出处标「含品牌词」，方便按竞品词、本品牌词分开用。沙盒跑通（域名清洗、品牌词标注、缓存复用）；正式接口未实测：账户余额 -0.03 美元，充值前所有付费子命令都调不了。

不接的接口和原因（不写进正文，免得被当成待办）：
- Ranked Keywords 查本品牌：和 GSC 重复，排名不进选词。
- Domain Intersection：缺口里的词都在竞品的排名词里；「品牌没排名」这层标签不作为出题或排优先级的理由，交内容计划。
- Keyword Ideas、Keywords For Site：按品类相关性匹配，返回很发散，和站点本身无关；扩词已有种子词、相邻词和竞品 alternative。
- Competitors Domain：我们的竞品按产品线 × 市场从 AI 回答里取，口径不同。
- Related Keywords：`collect_serp_signals.py` 已采相关搜索。
- Keyword Overview：查量用 `volume`。
- AI Keyword Data：由 PAA 建模的估算，不是 AI 提问量，不用来定优先级。

改动：`shared/scripts/collect_keyword_data.py`；signal-sources「搜索数据」行、「我方收集的数据」表、「关键词工具」用法行。改前快照 `.snapshots/*.20261109-125744.bak`。

## 报告侧（2026-11-09）商品卡回到回答正文原位（report-builder 2.9.0）

Suda 问「商品卡是不是得放在正文里，现在为什么是分开的」。查下来位置信息一直在：ChatGPT 每条带商品卡的回答，正文里都有对应的卡区块（图 + 徽标 + 编号标题 + 价格 + 评分 + 卖点 + Shop 链接），是清洗阶段 `_HTML_IMG` 把图全删了，卡片位置一起丢了（当初为防 AIO 的 base64 内嵌图撑爆表格）。

- 清洗改为先把「http 图 + 非空 title」转成占位符留在原位，再删其余图；`markdown_to_html` 遇到占位行渲染成卡片（`product-card-inline`）。Bbrand：552 张正文图全部还原成卡片，131 条回答中英文都有。
- 判定不看 title 就算卡：必须带价格、「x/5」评分，或编号标题 + 卖点/描述，否则按文章配图处理（0034 的「360 Logo」差点被当成卡）。
- 顺带修一个一直存在的 bug：兜底正则 `_HTML_LEFT` 会把 `[Shop RivalB2](<https://…>)` 里的 `<url>` 当标签删掉，报告里这类链接此前全是空括号。改成跳过 `http`/`https` 开头，再把 `&lt;/&gt;/&amp;` 还原。
- AI Mode、Gemini 正文无卡片位置，AIO 只有 8 张 base64 图，这三个平台仍按平台顺序把卡排在正文上方。

## 报告侧（2026-11-09）商品卡百分比统一一位小数（report-editor 2.9.1、report-builder 2.8.1）

Suda 发现核心洞察「商品卡提及率 8.5%」与购物模块表格「8%」对不上：两处都是 6/71，但 core `_percent` 默认 `digits=0` 取整到整数。商品卡的触发率、提及率、平均位置、官网购买链接覆盖率改为一律 1 位小数（`percent(n, d, 1)`），前端 `report-engine.js` 的 `corePercent` 同式；整数时不写小数（72% 不写 72.0%）。口径契约「购物层指标」补精度规则。本地报告重建、引擎对账通过、重新部署 Netlify。

## 2.53.1（2026-11-09）业务范围对齐《品牌资料收集》、按产品线分块；目标客户和使用场景合成一行；删「业务目标」

Suda 定：业务范围里品牌方填的行按《AI 搜索监测｜品牌资料收集》第一部分的字段写；同一条产品线的行放在一起，不然看不懂；收集表里目标客户和购买场景填在一块，不同产品线的目标客户和使用场景不一样，业务范围也合成一行、按产品线写；行名不写「（我方填）」「（本期）」；资料收集文档删了「业务目标」，模板、skill 和 Case 输入都不收。

- client-facing-base.md 业务范围：
  - 「市场与语言」拆成「市场」「语言」两行；表头加「产品线」（多选）。
  - 「主要目标客户（n）」「使用场景（n）」合成「目标客户与使用场景（n）」，写成「目标客户：A、B；使用场景：……」，放进所属产品线的块里；提示词矩阵仍分「目标客户」「使用场景」两列，选项从这几行取（目标客户跨场景、跨产品线复用，需求信号只标目标客户）。
  - 行序：共用的行在前（品牌方填的按文档顺序，再是我们填的品类、平台、社区平台与信源服务），然后每条产品线一块（产品线、竞品、只属于这条线的核心目标客户与购买场景和差异化优势、目标客户与使用场景）。
  - 行名不加「（我方填）」；产品线行只写编号，后续期的产品线在内容里注明「后续」。
  - selection-rules.md 第 1、2、4 步同步行名。
- 业务目标：Case 输入合同（input-contract.md、normalize_case.py）删掉选填字段 `业务目标`，传进来报 `retired_field`；两份 input-examples、shared/publish-templates 两份示例、online-runner.md、run_selection_mode.py 的提示词、e2e_input_contract.py 同步。
- 飞书模板《AI 搜索监测确认表（模板）》业务范围：加「产品线」字段；「【示例】核心优势（1）」改「差异化优势（1）」（2.25.1 已改名，模板漏改）；按上面规则改写并重建为 18 行示例；「项目」、需求信号「目标客户」、提示词矩阵「使用场景」三个字段说明同步。Ubrand 对客 Base 同步（76 行）。业务范围不被其他表关联，删了重建不断链，每次重建后逐行回读核对；改前快照在项目根 `.snapshots/tpl-scene-rename-20261109/`，Case 相关文件快照在 `.snapshots/case-goal-removal-20261109/`。重排脚本 `10-售前诊断报告/评测数据/Ubrand/选词-UK/regroup_scope.py`、`merge_scope.py`。
- check_skill_terms.py 加扫「市场与语言」作行名、「（我方填）」「主要目标客户（n）」「使用场景（n）」「（本期）」的写法。
- 验证：check_skill_terms 通过；validator 测试 58 passed；verify_workflow 65/65；e2e_input_contract、e2e_repair_loop 通过；模板与 Ubrand 的 check_client_base 通过。

## 2.53.0（2026-11-09）语种检查改用通用识别库 lingua

Suda 定：国家和语言按品牌方指定、没法穷举，语种检查不再按语言手写词表。

- validator 门禁 32 / W32：删掉英、西、法、德、葡、意六门语言的虚词表，改用 lingua（离线、75 种语言）判断题面实际是什么语言。判成另一门语言、且采集语言自身置信度低于 0.05 报错，0.05–0.10 给 W32；判定前去掉品牌、竞品、品类名和市场名；字母少于 12 个、或按空格分词的语言少于 5 个词的不判；最高置信度不到 0.15 的不判（多半是型号和术语堆起来的句子）；印尼语 / 马来语等近亲语言互判不算错。原来的文字类型检查（泰文、中文、俄文等占一半以上）保留。
- 采集语言写法支持 ISO 代码（`id`、`pt-BR`）、英文名（`Indonesian`）和常见别名（`Bahasa Indonesia`、`Filipino`）。lingua 不认识的语言、或本机没装 lingua，跳过语种检查并给一条 W32，提醒人工看。
- 阈值来源：新增 `evals/e2e_language_check.py`，12 种采集语言 35 条（写对、写成英文或邻国语言、买家常用的夹英文写法、3 条真实题库里被误判成德语 / 西班牙语的英文题）加 1 种不支持语言，35/35 符合预期，结果存 `evals/reports/language-check-20261109.json`。错写的题采集语言置信度 0.00–0.04；真实英文题被误判时最高置信度只有 0.07–0.13。
- `evals/verify_workflow.py`：西班牙语题写进英语题库原来只给 W32，现在报错，从「措辞问题只警告」用例拆成单独的 `spanish_query_in_english_bank`（期望不通过），65/65 通过。
- 回归：8 个客户的 18 份真实题库（英语为主，含泰语、韩语、繁中）共 783 道题，新旧 validator 输出逐字一致，语种检查零误报。改前快照在项目根 `.snapshots/validate_after_sales_set.py.*.bak`、`output-contract.md.*.bak`。

## 2.52.2（2026-11-09）市场和语言按品牌方指定，不限语种

Suda 定：选词按客户指定的国家和语言生词，不设限制。

- selection-rules 第 1 步「测试语言跟着买家做决策用的语言」改为「按品牌方指定的出题」；原来的判断依据（被哪门语言筛过、当地英语水平）降为对不上时提醒品牌方、建议加测，不自行替换。
- 本地选词没有语种白名单，validator 对未知语言跳过文字校验，不拦。线上入口 `normalize_case.py` 的 `locale-templates.json` 白名单（en、th、ru）归线上，本次不动。改前快照在项目根 `.snapshots/selection-rules.md.*.bak`。

## 2.52.1（2026-11-09）模型生成的线索照样登记；GSC 里 AI 发出的检索不再跳过

Suda 审同事版 4.4 节时提出：模型生成的联想写清来源类型就能进表；深度调研不必每条引用都核；GSC 里 AI 发出的检索是 AI 会搜的词，跳过不合适。

- **模型生成的线索**：selection-rules 第 2 步改写为「照样登记，来源类型写清」，能开假设级的行和候选题进试跑，不算矩阵行买家支撑，不能据此说需求高频。规则本身没变（需求信号表早就收这几类），只改掉「不算原话」这个容易读成「不进表」的说法。
- **GSC 里 AI 发出的检索**：不再跳过，按一条需求信号登记，来源类型记 query fan-outs、出处写 GSC，只开假设级（分不清背后是真实用户、监测工具，还是我们自己试跑的子查询）；同时交内容计划对照站内页面。只有提示词模板碎片仍跳过。signal-sources 信号表 query fan-outs 行、client-facing-base 来源类型说明同步。
- **用大模型做意图调研**：标为选做；结果按「模型建议问题」登记，不逐条核；只有要改记成社区、评价来支撑矩阵行的那几条，登记前打开原帖核对原话（Hbrand 那次 Gemini 有 3 条挂错帖子）。
- `check_skill_terms.py` 加退役说法。改前快照在项目根 `.snapshots/signal-model-generated-*/`。

## 2.52.0 同日补记（2026-11-09）60 条上限按市场 × 产品线算；八类意图类型售前也能用

两个会话同时从 2.52.0 往上升了一版，这条原来也记作 2.52.1；版本号让给上面「模型生成的线索」那条。

- Suda 定：每个市场每条产品线的题加起来不超过 60 条。`export_upload_csv.py` 改为按「市场 × 产品线」分文件（产品线从题所在矩阵行读），每份查 60 条；一个市场只有一条产品线时文件名不变，多条时带 `.line<n>` 并打印对应产品线。Ubrand 英国 17 条产品线 101 题导出成 17 份，Bbrand 单产品线文件名不变。
- Suda 定：八类意图类型售前、售后都能用，线上售前诊断只是默认只出发现题。shared/canonical-intent-mapping 删掉「仅售后」「售前不使用」，补上后端新增值 `trust`、`transactional`、`support`（研发需求第 4 节，含售后数据看板的意图类型筛选）。
- 同步 online-runner、shared/prompt-generation-principles、SKILL 交付一节。验证：validator 测试 58 passed、`verify_workflow.py` 65/65、返修循环 7/7、输入合同 40/40、退役说法 0 命中。

## 2.52.0（2026-11-09）Case 输入合同 v2：字段同《品牌资料收集》第一部分

Suda 定：线上诊断表单和售后收资料用同一套字段，以飞书《AI 搜索监测｜品牌资料收集》第一部分为准；旧字段删掉，不兼容。

- **字段**：必填 品牌、官方域名（可多个，第一个是主站）、本期产品线、竞品（1–3）；选填 品牌别名、适用边界、核心目标客户与购买场景（按业务优先级排）、差异化优势、业务目标。市场走 `--market`，语言走 `options.locale`。
- **删掉的字段**：公司名、品牌名称（改名品牌）、业务 / 产品名称、业务模式、品类、目标企业画像（垂直行业）、目标客户、痛点、使用场景、产品特性、补充内容、希望解决的问题、主题、购买标准、集成与兼容、信任与合规、地理与市场。v2 里传了报 `retired_field` 并写明并到哪；`presales-case-input/v1` 整份报 `unsupported_version`。品类改由选词从本期产品线和官网推出，写 `config.category_label`；业务模式随 B2B 专属字段一起删。
- **「待补充」按没填处理**（告警 `pending_value`），必填项填「待补充」报 `missing_field`；「无」原样记录，品牌别名填「无」时 `brand_aliases` 为空。
- `normalize_case.py` 重写；`--from-base-record`（飞书 Case 表适配）删除，旧 Case 表字段都是 v1。归一化结果去掉 `topics`、`topic_source`，新增 `brand_aliases`、`official_domains`、`product_line`。
- 同步：input-contract.md、两份示例、shared 两份公开模板、online-runner 第 1、4、5、7 步、`run_selection_mode.py` 任务说明、shared/prompt-generation-principles「主题的两种来源」、canonical-intent-mapping 字段互查表、售前流水线 SKILL；report-builder `load_case` 认「品牌」「本期产品线」，`run_pipeline.py` 把 `config.category_label` 带进报告用 Case。`check_skill_terms.py` 加退役说法。
- 同日研发文档《售前诊断：线上生词改用选词 skill》第 2 节改字段表，第 4 节改为意图类型八类（后端按类型统计、删 `question_types` 列、新增 `alternatives` 和 `information`），竞品沿用线上「表单＋按提及率补足＋本品＝5 个品牌」移入「不改的」。导出脚本等后端上线后再改。
- 验证：`e2e_input_contract.py` 40/40（重写为 v2 用例）、`e2e_repair_loop.py` 7/7、validator 测试 58 passed、`verify_workflow.py` 64/64、shared 测试 2 passed、report-builder 测试 40 passed、退役说法扫描 0 命中。改前快照在项目根 `.snapshots/case-input-v2-20261109-105510/`。

## 报告侧（2026-11-08）Bbrand H1 预览定为所有售前诊断报告的模板（report-builder 2.8.0、售前流水线 2.1.0）

- **模块显隐按数据判**（`render_report.slim_for_html` 写 `meta.shopping.enabled`、`meta.sentiment_enabled`）：商品卡在选词判定「关」、或整份采集一张卡都没有时关（写了「开」也关）；情感在没判读完、或判读完一条正负信号都没有时关。关掉的不只是模块：核心洞察的商品卡提及率、回答详情里的商品卡、问题明细与抽屉的情感列、单次回答的品牌情感一起不出，对应数据也不进 HTML。四种组合（都有 / 缺商品卡 / 缺情感 / 都没有）用 Bbrand 数据各出一份在浏览器核过。
- 修：之前关了商品卡，回答详情里仍会渲染商品卡。
- 核心洞察指标行不再写行内 grid：宽屏一行，1080 / 880 / 480 以下按 3 / 2 / 1 列换行，数字不重叠（之前窄屏下「2.2%2.8」贴在一起）。
- `run_pipeline.py` 加阶段 5b 引擎对账（`check_engine_parity.js`）；不带 `--brands` 跳过情感时报告直接不出情感模块，情感没卖的客户可以这样交付。

## 报告侧（2026-11-08）译文导出长度修正

- `export_translations.py` 的 `--max-chars` 默认从 4000 改为 6000，与数据层抽屉原文（`answer[:6000]`）一致。之前长回答的中文比英文少一截；Bbrand 312 条里 183 条受影响，已补译 4000–6000 字段接回原译文。
- Bbrand H1：补跑 14 题 ChatGPT 第 2、3 次后 52 题都是 3 次；整体提及率 9.7% → 8.3%（补进来的多是发现、替代题），Bbrand 正向情感占比 53.4% → 52.9%。

## 报告侧（2026-11-07 夜）数据筛选改多选；核心洞察引用只看发现、替代；回答详情渲染商品卡（report-builder 2.7.0、监测 1.8.4；选词版本不变）

- **多选筛选**：地区、平台、意图类型、主题四个下拉都能多选。预算切片只覆盖单选组合，所以数据层新增 `facts`（逐条有效回答的提及、引用、商品卡事实 + Claim），页面新增 `assets/report-engine.js` 按选中组合现算，公式逐条对应 Python。门禁 `scripts/check_engine_parity.js`：每个预算切片对应的单选组合跑一遍引擎，KPI、可见度、引用、情感、商品卡、问题明细逐项一致才算过（Bbrand 180 个切片全过）。HTML 不再嵌预算切片，Bbrand 12.9MB → 3.9MB。监测基线报告渲染前去掉 `facts`，仍是单选。
- **核心洞察的引用份额、引用率改为只看发现＋替代**（`config.citation_scope = "visibility"`），和提及率同一批题；引用模块、问题明细仍是全部意图类型。Bbrand：全部类型 13.1% / 26.1%，发现＋替代 0% / 0%（官网只在点名题里被引用）。统计范围一行只写一组类型。
- 修 `attach_sentiment.py`：「类型:X」切片之前按主题名过滤，情感全空，改为按题的意图类型过滤。
- 问题明细主题行：正向情感占比取该主题的情感汇总（之前占位「—」）；引用两列取该主题全部回答（同问题行）；「查看」不换行；0.0% 写 0%。
- 回答详情第二层：回答正文上方按平台顺序渲染商品卡（图片、标题、价格、评分、商家，本品描边并标是否有官网购买链接），数据来自 `details[].product_cards`；去掉与第一层重复的主题、意图类型、标签。抽屉品牌对比列同问题明细，加引用份额、引用率、正向情感占比。

## 报告侧（2026-11-07 晚）官网购买链接覆盖率；商品卡模块版式

- core `shopping.py` 品牌级、SKU 级都加 `official_link_coverage`（出现该品牌 / SKU 卡的回答里，卡带官网购买链接的占比；官网判定沿用 offer.channel）。HTML 品牌对比和 SKU 表的切换加第三项「官网购买链接覆盖率」。Bbrand 读数：ChatGPT、AI Mode、AIO 都是 100%（每条出现 Bbrand 卡的回答都有 brand-b.example 链接），RivalB3 ChatGPT 66%。
- 商品卡触发率改成一个指标卡（全部平台时合计）；「本品 SKU」改名「SKU」；统计范围里「提及类」改叫「可见度」。

## 报告侧（2026-11-07 傍晚）商品卡分品牌级、SKU 级；核心洞察加引用率（report-builder 2.6.0 内修订）

- **SKU 级**：core `shopping.py` 新增 `sku_of` 和 `target_skus[]`（SKU 商品卡提及率、平均位置，分母同品牌级）；`build_report_data.py` / `run_pipeline.py` 加 `--sku-map`（「SKU 名 + 正则」归并表，按顺序第一条命中胜出）；HTML 购物商品卡模块在品牌对比下面加「本品 SKU」表，跟品牌对比共用指标切换。Bbrand 归并表 `sku-map.json`：硬线套件（配件）先判，再分 H1 四路 / 三路 / Pro / 双路 / 未写路数、G300H Plus。读数：ChatGPT 上 H1 四路 24%；AI Mode、AIO 的卡标题多不带型号，「未识别型号」分别 83%、60%。
- **核心洞察**：引用份额旁边加引用率。监测基线 HTML 只改引用份额的提示文字，不再重复插入引用率。
- **问题明细**：去掉和上方重复的三个筛选，只留搜索框；选了意图类型后主题下拉不再消失（显隐按整份报告判断，不按收窄后的选项数）。

## 报告侧（2026-11-07 下午）售前 HTML 第二轮精简（report-builder 2.6.0；选词版本不变）

Suda 看预览后逐条定。

- **购物商品卡**：只留商品卡触发率（单独一块）和品牌对比（商品卡提及率 / 平均位置切换）。商品卡份额、首位率、本品商品（SKU）、购买渠道（商家份额、官网购买链接占比）计算和展示都删掉，core `shopping.py` 不再产出 `products`、`target_products`、`merchants`、`target_offer_channel`、`shelf_share`、`first_card_rate`。核心洞察的商品卡提及率在「全部平台」时按回答跨平台合计（不含接口未返回的平台）。
- **筛选**：数据筛选吸顶；地区、平台、意图类型、主题全改下拉；问题明细只留搜索框，筛选用上方吸顶的那一组。平台顺序 ChatGPT 第一。
- **统计范围**：每个模块标题右侧写本模块统计哪几类意图（随筛选变），01 指标下一行写同样的范围，不写题数。
- **删解释性文字**：情感的跨平台等权附注、抽屉里的本品各平台读数和延伸问题、Fan-out 的说明句、可见度结论里的「怎么看」、「不含 Gemini（接口未返回）」、问题明细每题的意图类型标注。i 提示改成 body 上的浮层，修了表格里被裁掉的问题。
- **引用模块**：参照 Hbrand 加引用率（`sources.rates`、`sources.official_citation_rate`），每个引用份额旁配引用率。
- **抽屉**：平台按钮移到标签下面、品牌对比上面。
- **情感**：Suda 认可 6 类判法全部按建议，删 3 条 Claim（Bbrand「客服响应快」为厂商自述；Rexing 两条纯规格），Bbrand 正向情感占比 53.6% → 53.4%。待裁决清单改写成中文版 `build/情感待裁决-中文.md`（Bbrand 评测目录）。
- **监测基线 HTML**：删掉售前已不需要的补丁（跨平台等权、引用说明句），统计范围在基线报告里隐藏（基线所有类型都计入提及率）。Hbrand 选中 10 题试跑在临时副本里重建通过。
- 验证：Bbrand 180 个切片独立复算一致；六组测试全过（audit 35、builder 40、editor 77、sentiment 21、选词 58、shared 2）。改前快照在项目根 `.snapshots/`（`*.trim-*`、`*.kpiscope-*`、`*.rates-*`、`*.docs3.bak`、`brand-b-claims-raw.json.*`）。

## 报告侧（2026-11-07）售前 HTML 改版：筛选前置、购物商品卡独立成模块、问题明细参照 Hbrand（report-builder 2.5.0、report-editor 2.9.0、监测 1.8.3；选词版本不变）

Suda 定（看 Bbrand H1 预览后）。

- **统计口径（只用于售前 HTML，上传 CSV 和后端不变）**：提及类指标默认算发现＋替代，只剩问题解决题时算问题解决，点名品牌的类型不算；引用默认算全部意图类型，按筛选收窄。core `compute_metrics` 新增 `config.visibility_intent_groups`、`config.citation_scope`，不写时仍是只看 Discovery；`verify_report_data.py` 同口径独立复算。代价写进 metric-scope 契约：点名题会把官网拉进引用（Bbrand 全部类型引用份额 13.1%，只看发现题 0%）。监测基线 HTML 仍按 10-22 口径。
- **意图类型切片**：题库有两种以上意图类型时多出「类型:X」切片，数据筛选加意图类型下拉；主题改成下拉，按意图类型收窄。
- **页面**：数据筛选移到 01 前面；内容规划模块删掉；情感没数据时不出；01 加「商品卡提及率」（全部平台时看 ChatGPT）；指标解释不再写「可见度问题」。
- **购物商品卡独立成模块（03）**：核心 3 项（商品卡触发率、商品卡提及率、商品卡平均位置）＋辅助 3 项（商品卡份额、SKU 商品卡提及率、官网购买链接占比），品牌对比可切换提及率 / 平均位置 / 份额 / 首位率。「品牌商品卡入选率」改名「商品卡提及率」。core 新增 `shelf_share`、`first_card_rate`、`product_field_returned`；一条商品字段都没返回的平台（2026-10 中起的 Gemini，11-07 复测 3 道 ChatGPT 出卡的发现题仍没有）写「接口未返回」，不写 0%。
- **问题明细与抽屉（参照 Hbrand 基线报告）**：明细加平均提及位置、引用率，主题行取主题切片合计值，点名类型的提及类列写「—」；抽屉先看问题概览（品牌对比、本品各平台读数、Query Fan-outs、延伸问题、回答记录），再点进单次回答。一题多次运行用 `0003-r2.json` 命名，details 带 run / time / fanout / related。引用模块不加「仅统计发现题……」那类说明。
- **监测基线 HTML**：`build_baseline_html.py` 删掉售前已自带的补丁（抽屉运行列表、筛选挪动、明细平台下拉、旧话术），details 摊平成按文件一条；Hbrand 选中 10 题试跑重建通过、页面检查正常（交付目录已恢复原文件）。
- **验证**：Bbrand H1（52 题，ChatGPT 38 题 3 次）180 个切片独立复算一致、突变 29/29；六组测试全过（audit 35、builder 40、editor 77、sentiment 21、选词 58、shared 2）。
- 改前快照在项目根 `.snapshots/`（`*.scope-*`、`*.v2-*`、`*.rename-*`、`shopping-html-*`、`build_baseline_html.py.*`）。

## 2.51.2（2026-11-07）上传 CSV 的 tags 不再重复写类型

- Suda 2026-11-07：`diagnosis_intent` 已经写了发现、对比、评估，`tags` 第一个再写类型中文名是重复。`export_upload_csv.py` 的 `tags_cell` 改为只有替代题（后端没有 alternatives 枚举，临时按 competitor 上传）在 tags 第一个写「替代」，其他类型只写切片标签，没有标签就留空；后端加了替代枚举后把 `TYPE_IN_TAGS` 清空。
- 下游不受影响：售前报告的意图类型标签和筛选读 `diagnosis_intent`（`build_report_data.py` 的 `INTENT_LABEL`），tags 只作切片标签显示；Base 的「标签」列（`write_tags.py`）本来就不写类型。
- 同步改 output-contract.md、online-runner.md、client-facing-base.md；测试改 1 条、加 1 条（替代写「替代」、对比和发现不写），58 条全过。

## 报告侧（2026-11-06）商品卡指标接进代码和售前 HTML（report-builder 2.4.0、report-editor 2.8.0；选词版本不变）

接 2.51.1 的口径。

- **core `shopping.py`**：新增 `SHOPPING_SCOPE_INTENTS`（发现、替代、对比、交易）。商品卡触发率、品牌商品卡入选率、商品、商家、卡位都只在这四类题里算，原来只看 Discovery。`shopping_mode_rate` 的分母改为四类题有效回答（新字段 `scope_answers`）；`discovery_answers`、`discovery_shopping_*` 两个字段删掉；`all_intent_shopping_answers` 和 `shopping_mode_rate_by_intent` 保留作诊断。`verify_report_data.py` 的独立复算同步改成四类（按中文标签另写一份 `SHOPPING_SCOPE_LABELS`），突变测试 29/29 全检出。
- **售前 HTML**：02 可见度底部、结论之前加「AI 购物商品卡」面板。一张表：列是平台（跟平台筛选走），第一行是商品卡触发率，下面一组是品牌商品卡入选率（目标品牌在前，配置竞品按配置顺序，开放品牌不进表）；指标名带 i 提示写公式，悬停数字看分子 / 分母。品牌商品卡出现率、商品、商家、卡位不展示。`slim_for_html` 只留面板要的字段（HTML 从 2.76MB 涨到 2.86MB）。
- **面板开关**：`build_report_data.py` / `run_pipeline.py` 加 `--shopping-cards 开|关`，写进 `meta.shopping_cards`（来自选词 `config.shopping_cards`）。没传时按数据判：最宽切片里任一平台触发率到 5% 才显示。当前主题下没有四类题时也隐藏。
- **验证**：Bbrand H1（52 题、四平台）显示正常，AI Mode 19% / ChatGPT 94% / Gemini 0% / AIO 32%，Bbrand 入选率 83% / 24% / — / 60%；只选可信度主题时隐藏；`--shopping-cards 关` 时隐藏；Hbrand（触发率 0%）自动隐藏；控制台无报错。六组测试全过（audit 35、builder 40、editor 77、sentiment 21、选词 57、shared 2）。
- 文档：render-spec 新增「AI 购物商品卡面板」，report-data-contract 的 shopping 字段，metric-scope-and-copy-contract 的模块归属和实现说明，report-builder SKILL 的购物层一行。
- 改前快照在项目根 `.snapshots/shopping-html-20261106-*/` 和 `*.shophtml-*.bak`。

## 2.51.1（2026-11-06）商品卡指标四类都进汇总

Suda 定（看过 Profound 文档：Shopping 指标由商品卡是否触发驱动，不按意图类型硬排除）：发现、替代、对比、交易四类题都进商品卡触发率、品牌商品卡入选率等汇总，支持按意图类型筛选；评估、验证、问题解决、售后照常采集商品卡字段、不进汇总。原「入选率只用发现、替代」「对比、交易只报出现率」撤销，出现率改为四类上可选。改 `geo-presales-report-editor/references/metric-scope-and-copy-contract.md`「购物层指标」（report-editor 2.7.1）、shared 映射表购物一段。代码未改，实现现状一句改为接入替代、对比、交易时加进取样并做按类型筛选。

## 2.51.0（2026-11-06）商品卡指标：哪些产品线、哪些题、算什么

Suda 定：商品卡是不是要统计由我们按产品线的商品属性推理决定，不让品牌方填；指标对标 Profound Shopping（Shopping Mode Rate、Shopping Visibility Score），和发现题提及率分开报。

- **产品线开关**（selection-rules 第 1 步、output-contract 新增 `config.shopping_cards`）：消费类实体商品开；软件、SaaS、服务、房地产关；工业、工程类记「试跑后定」，由监测按试跑出卡比例定（≥5% 开）。售前没有试跑，工业类记关（online-runner）。5% 的依据是本地 ChatGPT 发现题实测：Obrand 86%、Pbrand 70%、Bbrand 64%、某品牌 57%、Abrand 36%，Ebrand 3%，Sbrand 和 Hbrand 1–2%。
- **指标清单**（`geo-presales-report-editor/references/metric-scope-and-copy-contract.md`「购物层指标」，report-editor 2.7.0）：对客三项——商品卡触发率（出卡回答 ÷ 有效回答，发现、替代、对比、交易，按类型拆）、品牌商品卡入选率（有本品卡的回答 ÷ 出卡回答，发现、替代，竞品同式）、品牌商品卡出现率（有本品卡的回答 ÷ 有效回答，发现、替代上可选，对比、交易上是唯一读数）；商品曝光率、平均商品卡位置、商家份额、商家内品牌份额、官方店入口占比留作内部字段。原「购物触发率 / 购物可见度 / 购物曝光率」改名，内部字段名不变；report-builder（2.3.2）SKILL、report-data-contract、verify_report_data、shopping.py 说明、crawl-integrity 缺陷目录、shared 映射表同步。
- **监测**（1.8.2）：trial-and-lock「试跑」加工业类开关判法。
- 实现未改：`shopping.py` 仍按 Discovery 取样，触发率按全部意图拆开，没按产品线开关和四类题过滤；售前只有发现题，读数不受影响。监测报告接入替代题商品卡时再改。
- 改前快照在项目根 `.snapshots/*.shopping-*.bak`。检查：report-builder、report-editor 单测通过。

## 2.50.0（2026-11-06）不再兼容旧题库和旧 Base

Suda 定：「不要兼容旧题库了」；Hbrand 选词 2.1 和 Sbrand 选词两份按旧结构写的题库「不补，报错就报错」。2.48.0 拆出的 `validate_legacy_bank.py` 随之删除，旧题库门禁不再保留。

- **validator 只认现行结构**：`legacy_markers()` 认出旧结构就报 `unsupported old structure` 并列出命中项，退出码 2，不往下查、不出告警。旧结构：`generation_stage` 不是 `selection`、没有矩阵行、`extra_prompt_types`（旧售前题库）、`leader_default`、行没写 `prompt_type` 或写 `prompt_types` 列表或档位 P1–P3、旅程阶段、`group_role`、旧字段名（`intent`、`Prompt Type:` 标签、`persona`、`buyer`、`attribute`、`buyer_demand_evidence`、`condition_slot`、`review_status`）、`attribute_plan` 的 `{p1, p2, p3}` 写法或带 `relative_competitor`、`priority`、`common_constraints`、`brand_value`。
- **删掉的门禁和兼容**：7 / W7、31、33、41、44、W58、W55，60 / 61 读 `prompt_types` 列表的分支，无 `generation_stage` 的 v8 固定配额，售前题库（`extra_prompt_types`）的豁免，`formal_visibility_eligible` 门禁和豁免，`monitoring_prompt` 一致性，`expected_total`，常见约束当条件依据，`review_status`、英文审核状态别名，试跑 5 次、基线 5 次和按天数窗口。基线 30 次保留：某车载品牌、Bbrand 两份现行题库今天写的就是 30，锁版前改 7。
- **锁版门禁 14、26 留在 validator**：锁版归 `geo-monitoring`，但这两条读题库 JSON 的 `lifecycle_status`、`trial`、`baseline`，题库锁版时要查，监测 skill 没有自己的 validator。
- **其他脚本**：`check_client_base.py`、`write_prompt_reasons.py` 只认现行 Base（无属性池、矩阵有目标客户 / 使用场景 / 意图类型 / 约束条件 / 业务优先级及依据），删掉旧结构检查和写「建议优先级」的旧流程、字段旧名换算、旧来源类型选项；`export_upload_csv.py`、`write_tags.py` 遇旧结构题库退出码 2；`tag_dimensions.py` 维度只认目标客户、使用场景、属性 / 约束条件、自定义，属性维度必须登记 values。`normalize_case.py` 的 Case 旧选项告警属于输入合同，没动。
- 测试：pytest 去掉旧结构用例，新增每种旧结构都被拒收的用例，`validate()` 遇到被拒收的夹具直接失败，防止 assertNotIn 空过；2026-10-22 盲审样本在测试里就地转成现行结构再跑门禁 36–37，覆盖率下限不变。verify_workflow 夹具改成现行结构（64/64，`reports/workflow-e2e.json` 已重生成），同样防空过；线上返修夹具 `online-sample-bank.json` 档位 P1 改高、删不再写的字段。
- 对照：某车载品牌、Bbrand 选词-20261106 两份现行题库删前删后报错、告警、退出码逐条一致，上传 CSV 逐字节一致。Hbrand 选词 2.1、Sbrand 选词按预期报不支持。
- 收尾：W57 列出的约束条件后面不再挂「(?)」（原来是属性优先级，现行 `attribute_plan` 没有这个字段）。两份现行题库只有这一行文字变了，两边都按 `gate: W57` 记了处理，仍是已处理。
- 改前快照 `.snapshots/drop-legacy-compat-20261106-175219/`（项目根）。

## 2.49.0（2026-11-06）统计指标由意图类型决定

Suda 定：每种意图类型统计什么由类型本身决定，提示词库不加分析维度字段；上传列 `question_types` 是过渡字段，后端改为按 `diagnostic_intent` 决定统计什么之后删掉。

- **shared/canonical-intent-mapping.md**：映射表 `analysis_type` 列改为「统计指标」——发现、替代：提及率、情感；对比：胜负、情感；评估、验证：情感；问题解决：提及率；交易、售后：准确性。新增三段：引用所有类型都统计、按类型分开看（「全部类型」汇总只合并不点名品牌的类型，沿用基线报告口径）；提及只数去掉引用标记后的正文，正文里当数据来源点名的品牌也算提及；准确性怎么判（有品牌方资料对照事实表；没有时只对照官方公开页面记冲突，官网没写的记「无法核对」，不叫准确率；平台互相矛盾只当提示）。删掉替代行里与 11-03 口径相反的「2026-11-02 起计入提及率考核」。「后端问题类型」节改为过渡字段说明。
- **问题解决改看提及率**（推翻 10-23「只看引用」）：Hbrand 10-21 基线 41 道问题解决题 607 条有效回答，去引用标记后竞品正文提及 11 次（1.8%），其中 Gemini 在「西晒怎么查」的步骤里写「Cross-Check with Property Listings (RivalH1 / rival-h2.example)」，品牌出现在解决步骤里是这类题最有价值的位置；引用照常统计（竞品官网被引 27.5%）。
- **交易、售后改看准确性**：原读数「渠道是否指对、官网卖家占比」「帮助页引用、政策准确性」收为准确性；引用照常统计。
- type-branches.md「出几道、读什么」、`geo-monitoring/SKILL.md`（1.8.1）「采集频率与重跑」读法、online-runner.md、output-contract.md、`export_upload_csv.py` 说明同步。导出逻辑不变：替代仍按 `competitor` + `sentiment` 上传，等后端加 `alternatives` 枚举。
- 待后端：按 `diagnostic_intent` 决定统计指标；加替代、验证、问题解决、交易、售后枚举；加准确性指标。
- 改前快照 `.snapshots/intent-metrics-20261106-174615/`（项目根）。检查：check_skill_terms 通过，pytest 78 passed，verify_workflow 87/87，Bbrand 题库导出冒烟退出码 0。

## 2.48.0（2026-11-06）validator 拆出旧题库门禁

2.50.0 起旧题库不再兼容，本版拆出的 `validate_legacy_bank.py` 已删除。

接 2.47.0「不再兼容旧题库」：主 validator 只反映现行选词门禁，旧客户题库（Abrand、Bbrand 9 月版、UNI_A、Ebrand 等，已定不迁移）改用单独脚本，判定结果不变。

- **新增 `scripts/validate_legacy_bank.py`**：旧题库门禁搬到这里，7 / W7、31、33、41、44、W58、60 / 61 的 `prompt_types` 列表分支、`group_role` 分层规则、无 `generation_stage` 的 v8 固定配额，以及只对旧题库才有的放宽（`discovery` / `diagnostic` 不查 W47、W49–W52、W59、W62、W63，不拒收 Verification、Accuracy）。它继承主 validator 的类、只覆写这些分支，现行门禁的改动自动带到旧题库。选单独脚本、没加 `--legacy` 开关：开关会让主文件继续带着全部旧分支，而这次的目的是主文件读起来只有现行规则。
- **主 validator 拒收旧结构**：`legacy_markers()` 认九种旧结构标记（没有或旧的 `generation_stage`、没有矩阵行、行缺 `prompt_type`、`prompt_types` 列表、旅程阶段、`group_role`、`{p1, p2, p3}` 属性计划、属性计划带相对竞品或优先级、`leader_default`）；命中任一项就逐项列出并指向旧脚本，退出码 2，不静默跳过。原来近 500 行的 `main()` 拆成 `BankValidator` 类里按门禁分组的方法。
- **锁版门禁 14、26 留在主 validator**：锁版归 `geo-monitoring`，但这两条读的是题库 JSON 上的 `lifecycle_status`、`trial`、`baseline`，新题库锁版同样要查，监测 skill 没有自己的 validator。旧脚本照常跑它们。
- **W55 删除**（2026-11-05 已停用，原来只剩一行空赋值）。
- output-contract：门禁表只列现行门禁，新增「旧题库」一节（判定标记、旧脚本命令、只在旧脚本里的门禁表）；`slices`、`attribute_plan`、题字段里「旧题库照认」的说法改成「写了按旧题库处理」。SKILL.md 脚本表加旧脚本。`check_skill_terms.py` 加退役说法「旧字段名只在 validator 里兼容 / discovery、diagnostic 照认 / 两个键都没有的不查」，用改前快照验证三处都能扫出。
- 测试：pytest 现行用例改用现行结构的题库（`current_bank`），旧结构用例改跑旧脚本；新增旧结构拒收 / 旧脚本接收 / 两个脚本对现行题库输出一致的用例。verify_workflow 按结构分派脚本，新增「主 validator 拒收旧题库」一例（87/87），`reports/workflow-e2e.json` 已重生成。`evals/fixtures/online-sample-bank.json`（线上返修 e2e 夹具）去掉旅程阶段、`group_role`、相对竞品，行补 `prompt_type`，改成现行结构。
- 前后一致性：评测数据与 30-选Topic与生词 下 58 份题库（旧题库 56 份走旧脚本，某车载品牌、Bbrand 选词-20261106 两份走主脚本）拆分前后报错、告警、退出码、就绪结论逐条一致；另用 1,200 份随机改动的题库做差分，旧脚本与拆分前完全一致，现行结构题库上主脚本与拆分前完全一致。对照表在会话笔记 `legacy-validator-split-20261106.md`。
- 改前快照 `.snapshots/legacy-validator-split-20261106-171505/`、`.snapshots/legacy-validator-split-20261106-174000/`。

## 2.47.0（2026-11-06）正文精简：改名残留、暂停类型规则归位、SKILL 表格只做索引

Suda 定（审阅「选词 skill 还有没有过度复杂」后）：先修改名残留、把本期不出的七类规则集中到 type-branches、SKILL.md 步骤表只留索引；同时不再兼容旧题库和旧 Base。规则本身不变。

- **改名残留**：selection-rules「9 步」改 8 步；「目标目标客户」两处；约束条件查漏「十二类」统一为十一类；「搜索量不进行的业务优先级」改成「不进矩阵行的业务优先级」；第 7 步「完整购买决策任务」改「完整使用场景」；client-facing-base 里「购买任务」残留随旧名说明一起删。`geo-monitoring/references/trial-and-lock.md` 指向的「全面梳理」小节已不存在，改指「用清单查漏，只开成立的行」。
- **W59 写进正文**：validator 一直要求主题里至少 4 个不同决策（约束条件组合），正文只写了 5 道；selection-rules 第 6 步硬要求 3 补上这一句。
- **暂停类型规则归位**：第 1 步四目标表和「目标开放后按目标和买家需求决定是否出题」、第 5 步非发现行的业务优先级上限（2.46.0 新增）整段移到 type-branches.md（新小节「对应哪个目标」「业务优先级上限」），selection-rules 各留一句指向；第 5 步八类表删「什么时候开行」列；第 5、7 步重复的「本期只出发现」「其他七类见 type-branches」合成一处。selection-rules 中「本期不出 / 开放后 / 暂停 / 本期只」从 20 处降到 12 处。
- **SKILL.md 步骤表只做索引**：第 2、5、6、7 步单元格原来是 selection-rules 的长摘要，今天第 6 步改了三版、每次要同步两处；改成一句话加节号，判断标准以 selection-rules 为准。SKILL.md 从 11.5 KB 降到 8.6 KB。正文里交代来历的日期（「2026-11-06 前叫……」「2026-11-05 之前的题库……」「旧 Base 不迁移」等）删除。
- **不再兼容旧题库**：selection-rules、client-facing-base 里的旧题库、旧 Base 兼容说明全部删除；validator 和其他脚本里的兼容分支由另一会话删（见下一版）。
- 阶段表（总纲「每一步能说什么」）保留试跑、基线、持续监测几行：它是「前一步只能提假设」这条原则唯一的定义处，监测 skill 里没有同样的表。
- `check_skill_terms.py` 加 6 条：目标目标、9 步分节、十二类、不进行的业务优先级、购买任务、旧 Base 兼容说法；用改前快照验证每条都能扫出旧文本。
- 改前快照 `.snapshots/selection-simplify-AC-20261106-171053/`。三项检查：check_skill_terms 通过，pytest 72 passed，verify_workflow 86/86。

## 2.46.1（2026-11-06）正式基线每格 30 次改为 7 次

Suda 定：正式基线（Before）每个 query × 平台 × 国家 × 语言跑 7 次，不再跑 30 次。

- validator 的 `baseline.planned_runs` 改为要求 7，旧项目写 5 或 30 的照认；eval 用例同步（7 次为正例、30 次为旧口径正例、8 次和 2 次报错），`reports/workflow-e2e.json` 已重生成，86/86 通过。
- output-contract、selection-rules、`check_skill_terms.py`、`check_client_base.py`、shared/prompt-generation-principles 里的「30 次」改为「7 次」。
- 监测 skill 同步升到 1.8.0：SKILL「正式基线与版本」「采集频率与重跑」、trial-and-lock、gap-cause-action-table、baseline-report 改为 7 次。7 次下单平台单题 50% 读数误差约 ±37 个百分点，单题读数只看方向；竞争格局五档只按跨平台合并读数分（四个平台合并约 ±19 个百分点），不按单平台分。
- 改前快照在项目根 `.snapshots/*.20261106-171426.bak`。

## 2.46.0（2026-11-06）非发现行的档位按意图类型和本期目标定上限

Suda 定（Bbrand 选词时发现交易、验证、评估行都被判成高）：原规则「其他七类行档位默认跟同任务的发现行」会把已知道本品、已选定本品的人的问题也抬成高。

- **新增判档因素：意图类型和本期目标对不对得上**（selection-rules 第 5 步）。同一使用场景，不同意图类型的提问人处在购买的不同位置：发现、替代是新获客，对比是争取被选，评估、验证是已知本品在决定买不买，交易、售后是已选定或已买，问题解决不直接找品牌。按品牌方本期要解决的问题定上限：短板是知名度时，替代、对比可与发现行同档，评估、验证最高中，交易、售后默认低，问题解决默认最高中（品牌方点名问题型诉求时可同档）；短板是口碑或信任时评估、验证可同档；把官网直购、客服或复购列为目标时交易、售后可到中。只定上限，上限内照常按商业价值、战略重要性、当前业务重点判。
- 「不拿来调档」清单去掉「意图类型」，改为只按上一条看它和目标的对应。
- **主题优先级**：同一档里先排发现类主题（考核口径），再按父关键词月搜索量排。
- 改了 selection-rules 第 5、6 步，type-branches、client-facing-base、SKILL；`check_skill_terms.py` 加退役说法「默认跟同任务的发现行」。validator 不加新门禁。改前快照 `.snapshots/priority-goal-fit-20261106-163514/`。

## 2.45.1（2026-11-06）提示词库加回「意图类型」查找列

Suda 定：线上有诊断意图字段，提示词库要能直接看到每道题的类型。原来「不设意图类型列」的理由（后台看板没有这个字段）不对：后台有 `diagnosis_intent`。类型只有一个来源（矩阵行，一行一种类型），所以这一列从所属切片带出，不手填。

- 模板 Base 提示词库加公式字段「意图类型」（`[所属切片].[意图类型].LISTCOMBINE().ARRAYJOIN("、")`），两个视图都放在「主题」后面；回读两条示例行都算出「发现」。
- client-facing-base.md 提示词库字段清单加这一列，「不设意图类型列」改为查找带出的说明。
- `check_client_base.py --template` 要求提示词库有「意图类型」；模板检查通过，Hbrand 实表检查结果不变。
- 旧 Base 的手填「提示词类型」列不迁移（Hbrand 的 `sync_from_base.py` 读的就是这一列，不能删）。

## 2.45.0（2026-11-06）主题按同一类候选划分；对客 Base 不带看板

Suda 定：

- **主题 ＝ 同一类候选 × 同一意图类型**。「候选」指 AI 回答时推荐的那一类东西（某类产品、平台或服务商）。原来的三个条件里，「核心需求一致」「解决方案范围相近」落地时是同一个判断，合成一句：AI 回答这些题，推荐的是不是同一类东西；「读数能说清哪块要优化」降为试跑后的复核。目标客户、使用场景、约束条件是主题内题与题的差别，只有让候选换了一类才拆。「核心意图 / 核心需求」的说法删掉，不再和意图类型撞名。改了 selection-rules 第 6 步、SKILL 第 6 步、online-runner、shared/prompt-generation-principles。
- **约束条件查漏清单去掉「使用场景」**：场景是矩阵的一列，十二类变十一类，撤回 2.43.0 里自造的「使用情境里的条件」。
- **对客 Base 不再带「覆盖分布」看板**：Suda 已从模板删除，client-facing-base 删掉看板一节。模板 Base 的「旅程阶段」字段也已删（快照 `.snapshots/template-journey-stage-20261106-151808/`）。

## 2.44.0（2026-11-06）售前生词并入选词；试跑、锁版、停测搬到监测；Case Builder、竞品研究退役

Suda 定：售前生词的输入可能是一个文件或线上表单数据，主题不限数，对比和评估题默认不出，竞品是客户输入加试跑答案、不冻结；生词只做到出题，试跑几次、品牌方挑题锁版都和生词无关。两个 skill 规则已经一样，只剩输入、输出和运行环境不同，合成一个，不分两个版本。

- **并入**：`normalize_case.py`、`run_selection_mode.py`（含返修循环）、`input-contract.md`、`input-examples/`、`locale-templates.json` 搬进本 skill；新增 `references/online-runner.md`，只写线上和本地不一样的地方（Case 代替业务范围、只预跑品类认知、没有浏览器、业务优先级从 Case 字段推、只交上传行）。runner 只跑 validator 和导出两项检查。
- **输出两个出口**：题库 JSON 是唯一底稿，按场景导出飞书对客确认表、9 字段上传行，或两者都要。
- **Case 输入合同**：`extra_prompt_types`、`generation_stage` 照收不生效（`deprecated_option` 告警），「希望解决的问题」只当业务优先级线索；Case 主题个数不限；竞品状态 `client_input`、不冻结。版本号仍是 `presales-case-input/v1`，已接入的调用方不用改。
- **删掉**：`check_presales_bank.py`（「主题都有题」validator 本来就查；题型按 `business_goals` 走 W52；冻结竞品、`extra_prompt_types` 点名两条作废；「约束条件名单不为空」没有搬）、`e2e_presales_gates.py`。上传行检查从旧 `validate_question_bank.py` 原样搬进 `export_upload_csv.py`（新旧函数对 4 个真实上传 CSV 和 3 组造的坏数据结果一致）。
- **搬到监测**：原第 8 步试跑、第 9 步选正式题与锁版、维护里的停测 / 措辞不可改 / 复查 / 复核节奏，原文搬进 `geo-monitoring/references/trial-and-lock.md`；`trial_brand_count.py`、`changeability_domains.py` 搬进 `geo-monitoring/scripts/`。本 skill 第 8 步改为「校验与导出」，维护只留加题、并题。竞品不足 3 个时由监测按试跑发现题答案补。
- **退役归档**：`geo-presales-prompt-builder`、`overseas-geo-competitor-research`、`geo-presales-eval-case-builder` 移到 `90-历史归档/旧版与过程稿/退役skill/`，`.claude/skills` 软链已删。改了 pipeline、shared 三份文档、`prompt_gates.py`、`test_prompt_gates.py`、`redact_publish_tree.py`、售前选词工具 PRD 的 skill 引用。`check_skill_terms.py` 加三条退役说法。
- 验证：validator 测试 72 通过，`verify_workflow.py` 86/86，`e2e_input_contract.py` 43/43，`e2e_repair_loop.py` 全过，`test_prompt_gates` 通过，退役说法扫描 0 条。快照 `.snapshots/merge-presales-into-selection-20261106-151118/`。

## 2.43.0（2026-11-06）矩阵四个字段改名；准确性题默认不出

Suda 定：

- **字段改名**：受众 → 目标客户，购买任务 → 使用场景，买方约束 → 约束条件，提示词类型 → 意图类型。矩阵一行 ＝ 产品线 × 市场 × 目标客户 × 使用场景 × 意图类型，挂约束条件；一行就是一个覆盖切片（Aleyda 的 scenario），不另设一列。
- **使用场景的定义**：目标客户在什么情境下用产品、要解决什么问题（停车被刮蹭要留证据、跑网约车要记录车内纠纷；平台类写在什么情境下找什么）。换了场景，要解决的问题和候选会变；只多看一条条件的写成约束条件；同一场景要的结果不同（平台 vs 房源）照旧分行、在场景里写明。约束条件查漏清单去掉「使用场景」一类（场景是矩阵的一列，第 4 步梳理），十二类变十一类。主题定义里的「核心意图」改叫「核心需求」，避免和意图类型撞名。
- **兼容**：JSON 键不改（`audience`、`scene`、`attributes`、`prompt_type`）；`check_client_base.py`、`write_prompt_reasons.py` 读 Base 时把旧字段名换成新名，旧 Base 不迁移；`tag_dimensions` 新旧维度名都认；三个采集脚本产出的 signals.csv 列名改成目标客户、约束条件；售前旧流程 `export_to_confirm_base.py` 写新模板时自动换名。基线 HTML 的筛选标签改叫意图类型筛选。
- **准确性题默认不出**：只在我们判断有必要时出（如关键事实修复上线后要确认 AI 读到了），零提及不触发。
- 模板 Base：五个字段改名并改说明，示例场景改成场景写法，业务范围两类行改名，看板两张图和说明文字跟着改。快照 `.snapshots/field-rename-20261106-144355/`。

## 2.42.0（2026-11-06）提示词类型改为八类，删除旅程阶段

Suda 定（讨论稿 `30-选Topic与生词/方案/提示词类型八类-定稿方案-20261106.md`）：

- **删旅程阶段**：Hbrand、Bbrand 新格式 34 行的阶段全部等于按类型取的默认值，业务优先级、主题、挑题、切片标签都不读它。矩阵一行 ＝ 产品线 × 市场 × 受众 × 购买任务 × 提示词类型。旧题库、旧 Base 的阶段照认，不迁移；模板 Base 的「旅程阶段」字段 Suda 确认后已删（删前快照 `.snapshots/template-journey-stage-20261106-151808/`），看板「按旅程阶段」图已改成「按提示词类型」。
- **购买任务保留**：去掉后同受众同类型的行分不开（Bbrand M-001/002/003/006），主题也没有可聚的依据。
- **提示词类型八类**：参考 Aleyda 九段客户旅程，发现与候选名单合成「发现」，只用推荐式一种问法、不设探索式 / 候选式标签；评价改名评估；新增验证（Trust，只问可信度）、交易（Transactional）、售后（Support，题面必须点名品牌、型号或服务名）。验证的英文键用 Trust，避免和历史 Verification（`validation`）混。
- **能力核查并入评估**：`Does [brand] offer X?` 是买家真会问的评估问法；零提及不再专门出点名题，先查可爬性、引用页和推荐理由句（selection-rules 第 8 步）。
- **准确性单独保留在八类之外**：按品牌事实核查表的事实点名问值，只用于修复上线前后验收和开放品牌呈现后，不进题库、名额、考核；validator 拒绝新选词库里的 Accuracy。
- **目标对应**：评估、验证归声誉与信任；交易、售后不属于四个目标，写了就 W52 告警。后端没有替代、问题解决、验证、交易、售后的枚举，这几类不导出上传 CSV。
- 第 408 行补平台类客户：问「去哪买、去哪找」按发现题写。
- 改动：SKILL、selection-rules、type-branches（重写为七类）、client-facing-base、output-contract、signal-sources；validator（类型集、W51/W52、Verification/Accuracy 报错文案）、check_client_base（八类选项、不再按阶段限制类型）、tag_dimensions、export_upload_csv、write_prompt_reasons、check_skill_terms；shared 两份文档；售前 selection-mode、input-contract、export_to_confirm_base 等；监测 SKILL、gap-cause-action-table、build_baseline_html。测试补 EightTypeTests 和两个 e2e 用例。模板 Base 提示词类型选项换八类、字段说明去旧说法。快照 `.snapshots/eight-types-20261106-135640/`。

## 2.41.2（2026-11-06）主题表删信号条数、主题范围、状态

Suda 定：三列都不影响定档和排序。信号条数取决于收集了几个来源、主题里有几行，容易被读成需求大小，且靠手填会过时（模板与 Hbrand 精度还设成 2 位，显示成 4.00）；没有信号支撑的情况在矩阵行一级查。主题范围与「切片」关联的矩阵行重复。状态能从提示词库推出：主题里有「正式」题即已采购。

- 线上删字段：模板 Base 信号条数；Hbrand 信号条数、状态、主题范围；Sbrand 买家原话条数、状态、主题范围。改前快照（含字段定义和全部记录）：项目根 `.snapshots/drop-topic-fields-20261106-112947/`。
- client-facing-base 主题表字段清单改为 `主题 | 市场 | 产品线 | 主题优先级 | 主题优先级依据 | 父关键词 | 月搜索量 | 切片`；「状态是候选的主题」改为「提示词库里还没有正式题的主题」。
- `check_client_base.py` 去掉「主题状态不空」，五个字段登记为已移除；`check_skill_terms.py` 加退役说法。
- Hbrand `sync_from_base.py` 改为直接读提示词库的状态，不再用主题状态套到每道题上；「不批准」的题不进题库。W59 题少理由从删前的主题范围搬进脚本常量。重跑后 36 道题逐字段与改前一致（线上提示词库状态目前全空，都按待审核），只有 W59 的说明文字变了；validator 通过，`check_client_base.py` 对 Hbrand 和模板都通过。
- 飞书《生词规则》主题表一行删「状态」「买家原话条数」。

## 2.41.1（2026-11-06）主题表删「GSC 展示」列

Suda 定：GSC 展示量取决于官网自己的排名，不参与主题优先级判档和排序，单设一列容易被读成需求大小。对照 Ahrefs（GSC 只作题源，主题需求量用父关键词谷歌月搜索量）、Peec、Profound、LLMrefs、SE Ranking、AthenaHQ，没有一家用 GSC 展示量给主题排优先级。父关键词查不到搜索量时，可在主题优先级依据里写一句非品牌展示量证明需求存在。

- 线上删字段 `fld9bDPUOq`：模板 Base（J5j2…）、Hbrand（A6Rq…）、Sbrand（VdfL…）三张主题表；Sbrand 主题优先级、主题优先级依据两个字段说明去掉 GSC。Sbrand 两行原值「有曝光」「0」、模板两条示例值在快照里。
- 飞书《生词规则》主题表一行删「GSC 展示」。
- client-facing-base、selection-rules 第 6 步同步；`check_skill_terms.py` 加退役说法。
- 改前快照：项目根 `.snapshots/drop-gsc-column-20261106-110536/`。

## 2.41.0（2026-11-05）主题定义改为核心购买决策 × 提示词类型

Suda 定：主题 ＝ 同一核心购买决策 × 同一提示词类型下的一组相关问题。撤销 2.40.0 的「不够 5 题跨决策合成类型主题」，不同决策的同类型题不合并；发现题内部不再按问法细分。type-branches 的题量从「每个购买决策最多几道」改为按竞品 × 场景、场景、具体问题计，否则类型主题到不了 5 道。「三个条件」继续用来判核心购买决策；单主题不设上限、主题名不带品牌不变。售前生词 6.8.0 同步。改前快照 `.snapshots/topic-definition-decision-type-20261105-*/`。

## 2.40.1（2026-11-05）一个主题一种类型扩到售前；模板 Base 同步

Suda 定：「通用」包括售前，并同意删模板列和图表。门禁 66 改查写了 `extra_prompt_types` 的售前题库（线上售前题库目前没有写这个键的存量）；售前不设 5 题下限，W59 的类型主题提醒不查售前。`selection-mode.md` 第 6、7 步、`run_selection_mode.py` 返修提示、`prompt-generation-principles.md` 同步；售前 skill 升 6.7.0；样例题库拆成发现、对比、评价三个主题。模板 Base：删提示词库「提示词类型」列（fldy1kYycE）和看板「按提示词类型」环形图，看板说明删对应一句，各类型读法并入矩阵「提示词类型」字段说明。改前快照 `.snapshots/template-prompt-type-field-20261105-192209/`、`.snapshots/topic-one-type-presales-20261105-192502/`。

## 2.40.0（2026-11-05）一个主题只放一种提示词类型；提示词库不设类型列

Suda 定：后台数据看板没有提示词类型字段，提示词库不放这一列，主题要同时考虑购买决策和提示词类型；改成通用规则，不按看板有没有字段分情况。改前快照：项目根 `.snapshots/topic-by-decision-and-type-20261105-191810/`。

- **主题**（第 6 步）：撤销 2.38.0 的「不按提示词类型拆」。发现题照三个条件分；其他类型一个决策够 5 题开「决策 + 类型」主题，不够 5 题跨决策合成类型主题；主题名写出类型。本期只出发现题，现有题库不受影响。
- **门禁**：新增门禁 66（选词题库一个主题一种类型，看行上有 `prompt_type`、没写 `extra_prompt_types`）；这类题库不再查门禁 41 的「每个主题至少一道发现题」；W59 增加其他类型主题不够 5 道。`check_client_base.py` 按矩阵行查同一主题挂了几种类型。
- **提示词库**：去掉「提示词类型」列，类型读所属切片；`write_prompt_reasons.py` 改读所属切片，`export_to_confirm_base.py` 不再写这一列；看板去掉按提示词类型的图表。飞书模板 Base 见 2.40.1。
- **type-branches.md**：对比、评价、问题解决的题量上限从「每个主题」改为「每个购买决策」，否则类型主题凑不满 5 题。

## 2.39.0（2026-11-05）撤掉提示词优先级字段

Suda 定：「不需要提示词优先级字段了」——它是所属切片的业务优先级，没有独立信息，却让模型以为要判三次。改前快照 `.snapshots/*.20261105-drop-prompt-priority.bak`。

- **规则正文**：selection-rules 总纲的档位表把「题的档位（提示词库）」改成「题的先后」，写明提示词库不设优先级列、挑题读所属切片带出的行档位；第 5 步档位处理表删掉「题的提示词优先级为高/中/低」；第 7 步题目来源表删该行；第 9 步「手动改档」改成「改档只改矩阵行」。出题原因的写法不再写「提示词优先级：高」结尾。
- **对客表**（client-facing-base）：提示词库列清单去掉「提示词优先级」，默认排序改为按所属切片的业务优先级；字段说明改写为「不设优先级列」；看板里「按提示词优先级」改成按业务优先级。
- **字段契约**（output-contract）：题字段表删 `priority`，按需字段删 `priority_change_reason`，停写清单加这两个，W55 标停用。
- **脚本**：`check_client_base.py` 不再要求每道题有优先级、不再查题档位与行档位一致，`--template` 不再要求该列；`write_prompt_reasons.py` 只写行档位和出题原因，旧 Base 还留着这一列的照旧预填、人改过的只列出不拦；`validate_after_sales_set.py` 停发 W55。
- **测试**：单测里 W55 的两条断言改成「不再报」；`verify_workflow.py` 的 absent 用例同时排除旧文案。
- 模板 Base 和旧客户 Base 的「提示词优先级」列不删（会换掉字段、影响已有视图和看板），按「旧字段不迁移」处理，我们不再填。

## 2.38.0（2026-11-05）矩阵按提示词类型分行；主题按核心意图和解决方案范围划分

Suda 定：矩阵按不同提示词类型拆开分析，不放在一行；主题判据对照 Graphite、Aleyda、Omniscient、Ahrefs 收敛为「核心意图一致 ＋ 解决方案范围相近」。改前快照：项目根 `.snapshots/matrix-row-per-type-20261105-183235/`（本 skill、shared、售前 selection-mode.md）、`.snapshots/template-matrix-row-per-type-20261105-185101/`（模板 Base 矩阵字段与记录）。（本条与 2.36.0、2.37.0 由不同会话同日并行写入，2.37.0 已把四种类型的细则搬进 type-branches.md。）

- **矩阵一行一种提示词类型**：一行 ＝ 产品线 × 市场 × 受众 × 购买任务 × 提示词类型，旅程阶段按类型取默认值（发现、替代为方案考虑，对比、评价为购买决策，问题解决为需求认知）、可以改。只有发现行用查漏清单开，其他类型有证据或合理假设才开；替代、对比行的开行依据写在业务优先级依据里；非发现行档位默认跟同任务的发现行。非发现行本期不出题，不用写「本期不出」；只有低档发现行要写。发现行写不出自然的发现题时改成对应类型，不为凑发现题改写意图。去重改为受众、购买任务、提示词类型、买方约束都相同才报。
- **同一任务里要的结果不同也分行**：「找转售组屋」里问哪些网站适合找组屋（要平台）和问某区某价位的三房（要房源）开成两行、归不同主题；题仍只通过所在行归主题，提示词库与主题优先级的结构不变。
- **主题判据**（第 6 步）：主题 ＝ 核心用户意图相近、对应相近解决方案或竞争对象的一组提示词。三个条件：核心意图一致、解决方案范围相近为必要；诊断可解释（原「第四件」）为验证，不用它合并前两条判定该拆的。产品类型、客群、场景是条件性拆分维度，要有需求和试跑证据才拆（找房平台问题先不按组屋、公寓、新盘拆）。不因购买任务相同或同属一件大事就放一起，不按提示词类型拆主题；不为凑 5 道把要房源的题改写成要平台的题。SKILL.md 第 6 步行、售前 `selection-mode.md` 第 7 步同步（售前只改这一行，不升版本）。
- **输出合同与脚本**：`slices[].prompt_type` 单值取代 `prompt_types` 列表（旧题库照认，两个键同时出现报错）；门禁 60 查单值合法，61 查题的类型和行一致，W48 改为查高、中发现行没题（旧题库仍按方案考虑行，告警原文保留「rows with no Prompt」以匹配已有处理记录）；W50 新形态下数对比行。`check_client_base.py` 单选行按新规则查、多选的旧 Base 照旧。一度加过的「同一任务各类型行归同一主题」和门禁 65 已撤回（与上一条冲突）。
- **对客表**：client-facing-base 矩阵列序改为购买任务后接提示词类型，「提示词类型」改单选，切片稳定键改为「产品线|市场|受众|购买任务|提示词类型」（旧 Base 仍用旅程阶段）。模板 Base（J5j2bAc63az2dqsjLJmcFH3qn5c）提示词矩阵：「提示词类型」改单选并重写说明，「旅程阶段」「业务优先级依据」说明同步；示例 M-002 去掉「替代」，新增 M-004 替代行示例；`check_client_base.py --template` 通过。已有客户 Base 不迁移。
- **shared/canonical-intent-mapping.md**「提示词类型与旅程阶段」一段同步。退役清单加「不按问法另开行」「所在行登记」「行上登记」「只能出其他题型」等说法。
- 验证：单测 68/68；workflow e2e 84/84（新增 typed_* 7 例和 client_base_typed_rows）；check_skill_terms 0 命中；Hbrand、Sbrand 两份现有题库 validator 结果与改前一致；Hbrand 线上 Base 的 check_client_base 结果与改前一致；售前 e2e_presales_gates、e2e_input_contract 全过。

## 2.37.0（2026-11-05）只留一个判断点；四种类型移到独立文件

Suda 定：大模型执行时维度不能多、规则要能一遍读懂；四种暂不开放的类型保留，但拆出正文。改前快照 `.snapshots/*.20261105-simplify.bak`。

- **新增「只有一个判断，其余都是派生」**（selection-rules 总纲）：业务优先级是唯一需要判的档位，主题优先级是组内多数行的汇总、题的档位照抄所在行；改档只改矩阵行。目的是一次判断、一个口径，模型不再逐层判三次。
- **替代、对比、评价、问题解决拆到 `references/type-branches.md`**：开行条件、阶段默认值、出几道、读什么、题面写法集中一处；selection-rules 第 5、7 步只留发现链和「见 type-branches.md」的指针。规则内容不删不改，只搬家。文件末尾附「开放时要改的五处」。SKILL.md 参考表加一行。
- **去重**：评价/问题解决的重复陈述合并成一条；替代、对比、评价的题面写法从第 7 步移走，只留指针。

## 2.36.0（2026-11-05）主题边界与报价先后；拆分判据加第四条；主题定义句

Suda 定：主题不在矩阵之前定，售前报的主题名只是名额锚点，签约后按重画的矩阵重聚；拆分判据从三件事补到四件（合并后能不能独立诊断）。改前快照见项目根 `.snapshots/`。

- **selection-rules 第 6 步「怎么聚」**加两条：报价与交付的先后（售前聚过主题、按名额报价，接手时仍按本节重聚，不继承售前名单；个数差 ≤1 且没有被采购的主题消失就直接按新集合交付并在对客表说明，差 ≥2 或有主题被整个并掉、拆掉要书面告知后锁版）；品牌方售前点名要独立监测的主题按给定处理、不重聚。
- **拆分判据加第四条**：合并后只剩一个平均提及率、说不清哪一类买家需求没做好就拆。SKILL.md 第 6 步行、`geo-presales-prompt-builder/references/selection-mode.md` 第 7 步同步（售前 skill 随之升 6.6.1，只改这一行）。
- **主题定义句**写进 selection-rules 第 6 步「主题是什么」，作为 SOP 和对外说明的统一说法（围绕核心需求或决策目标、解决方案范围相近、适合统一开展监测与优化诊断的提示词集合）。
- **client-facing-base 主题表**加一条：主题边界可能在出题后调整，状态为候选的主题边界未定死。

## 2.35.0（2026-11-05）去掉提示词类型依据；主题名不带市场

Suda 定：矩阵行的提示词类型只登记、不再逐个写依据（「没必要」）；主题名不写市场（Hbrand 只做新加坡，「新加坡买转售组屋」的前缀是重复）。改前快照：项目根 `.snapshots/check_client_base.py.20261105-181020.bak`、`selection-CHANGELOG.md.*`、`selection-SKILL.md.*`。

- **门禁 60 放宽**：`validate_after_sales_set.py` 只查登记的类型合法，不再要求每个类型带 `basis`；`check_client_base.py` 删掉「登记了 X 但提示词类型依据里没有 X：依据一行」的检查，阶段上限照查。
- **对客矩阵去掉「提示词类型依据」列**：client-facing-base.md 列清单、字段说明、「不设备注列」一段同步；selection-rules 第 5 步「行上的提示词类型」改为只登记，第 7 步删「依据写在行的登记上」；output-contract `prompt_types.basis` 改选填；signal-sources 竞品词一行改掉「写进提示词类型依据」。
- **主题命名**：selection-rules 第 6 步加「不带市场」：市场、产品线是独立字段，写进主题名是重复。
- **Hbrand**：线上主题表 5 个主题去掉「新加坡」前缀（买转售组屋、买新盘和 EC、买转售公寓与私宅、选买房平台、找买房中介）；线上矩阵的「提示词类型依据」列已被删；`sync_from_base.py` 按 11-05 线上结构重写（表名需求信号、主题，字段购买任务、业务优先级、买方约束，主题是公式字段），本地 bank.json 重新同步为 15 行矩阵、5 主题、38 题。
- **模板 Base**（J5j2bAc63az2dqsjLJmcFH3qn5c）：提示词矩阵删掉「提示词类型依据」列，删前三行示例与字段定义存项目根 `.snapshots/template-matrix-type-basis-20261105/`；`check_client_base.py --template` 通过。「提示词类型依据」「可出题型依据」进退役清单。
- 验证：Hbrand bank.json validator 0 错误；check_client_base 通过；单测 68/68；workflow e2e 76/76；check_skill_terms 0 命中。

## 2.34.1（2026-11-05）线上生词返修循环（售前 runner 6.6.0）

Suda 定：选词方法要放到线上一次性出词，门禁不放松，最终得能生词。改前快照 `.snapshots/audit-fixes-20261105/`（run_selection_mode.py、售前 SKILL.md、selection-mode.md）。

- `run_selection_mode.py` 的 `run` 加 `--repair-rounds`（默认 2，0 关闭）：finalize 检查没过而 `out/bank.json` 存在时，把 result.json 的报错原文写成 `REPAIR-<n>.md` 回喂 agent 返修再查；最后一轮授权丢题不丢库（改不好的题删掉、题号记 `config.retired`、notes.md 写「删题」一节，每个主题仍要至少一道发现题）。没有 bank.json 不返修。返修轮的 agent 记录带 `-repair<n>` 后缀，result.json 新增 `repair_rounds`。
- 新增 `evals/e2e_repair_loop.py`（假 agent 走 run 全链）：修好（1 轮）、丢题保底（2 轮、retired 记题号、只有最后一轮带丢题授权）、`--repair-rounds 0` 回归旧行为、无 bank 不返修，7/7 通过。
- 售前文档三处 2.19.0 同步漏掉的残余：SKILL.md description「judge attributes against competitors」和步骤列表「属性与相对竞品」改为买方约束口径；selection-mode.md 两处「题面条件取自属性的 `common_constraints`」（新题库没有这个字段）改为「有依据的 1–3 个条件，依据写原话或 `condition_basis`」，与第 4 步自己的 `attribute_plan` 合同对齐。
- 验证：repair-loop e2e 7/7；门禁 e2e 24/24；选词三件套（退役扫描 0 命中、单测 68、workflow 76）全过。

## 2.34.0（2026-11-05）审核修复：现行矛盾、历史残余、模糊段落、重复口径

Suda 让按审核清单全部修。改前快照 `.snapshots/audit-fixes-20261105/`（项目根目录下，含 geo-monitoring、shared 被改的两份）。

- **目标触发机制对齐**：「品牌方选目标」机制已删（2.14.0），但第 1 步四类目标表、第 7 步类型表、W50–W52 仍写「品牌方选了」。统一改为「该目标开放后（启用方式待定）」；W50/W51 标「休眠」，措辞改成查 `business_goals` 配置；`business_goals` 字段说明删掉「按品牌方写的先后排」。「品牌方选了竞争定位/声誉与信任」「没选竞争定位/声誉与信任」进退役清单。
- **W64 补进 output-contract 告警表**（2.32.0 实现时漏登记）：低档行挂题告警；按第 5 步从低档补题属正常，写处理记录保留理由。
- **属性口径对齐买方约束**：`attribute_ref` 的对客表映射从「属性」改为「买方约束（第一个，默认视图隐藏）」；`tag_dimensions` 属性维度的「优势属性」改为「差异化优势对应的买方约束」（新题库必须列 values；旧题库不写时取相对竞品为优势的，`tag_dimensions.py` 行为不变、docstring 同步）。「优势属性」进退役清单，geo-monitoring gap-cause-action-table 的一处同步改掉。
- **check_skill_terms 替换文案翻新**：约 20 条「现在的说法」还停在 2.23.0–2.28.0 已撤回的口径（替代题计入考核、主题排优先级三档规则、需求重要性×商业目标相关性、核心场景、业务重要性、常见约束等），全部改到 2.32.0/2.33.0 现行口径，照着提示改不会再把旧规则改回来。
- **文件改名**：client-facing-attribute-pool.md → client-facing-base.md（属性池已不存在）。本 skill、signal-sources、shared/prompt-generation-principles、check_client_base.py、write_prompt_reasons.py 的引用同步；旧名进退役清单（strict）。
- **日期与修订痕迹出正文**：正文里的「Suda 2026-11-04」「2026-11-01 前」「2026-11-04 起」「2026-11-05 前叫场景」等标注删去日期、改成「旧 Base / 旧题库照读」式写法；client-facing 的「不设 ×7 行」负空间清单改为正面写法「只设列出的行」，被删行名（本地术语与市场差异、监管与敏感事项、初始题库规模）进退役清单（业务模式不进：售前 input-contract 还在用）。
- **模糊段落重写成可执行规则**：第 5 步「品类题与真实购买条件」改名「宽泛品类题」，和 W54 对齐（只在品牌方点名大词时写，之前正文写成「有需求就可进候选」是矛盾）；第 7 步「阶段/题型两条轴」「出几道 1–2 条」「发现题要候选（where to buy 限本地服务）」「措辞」「替代现有做法」各改写出主语和动作，删掉与第 5 步重复的「品类调研与购买任务按实际意图区分」一行；第 8 步「信源结构与动作假设」写明四类来源和记录位置（`changeability_basis`＋试跑报告）；临时点名核查删掉未定义的「正式确认率」；第 6 步「分组与售卖」「粗细复核」改写。
- **重复口径收敛**：60 道总额度的唯一定义处定为第 9 步，第 1 步名额、第 6 步硬要求 3、client-facing 主题表改为指针（SKILL.md 第 9 步概览和门禁 14 保留数字）；业务范围字段清单唯一定义处定为 client-facing-base.md → 业务范围（补上语言、适用边界的定义），selection-rules 第 1 步改为指针。
- **SKILL.md**：frontmatter description 还停在属性池/业务重要性时代，改为买方约束/业务优先级口径并写明本期只做发现型可见度；维护节加两条——动手前先读 CHANGELOG 最新版本号（另一会话可能已改，先对账）、讨论中的判法先放 `30-选Topic与生词/方案/` 讨论稿；扫描范围说明改为实际覆盖（含售前 skill）。
- **售前侧同步**：`check_presales_bank.py` 的 attribute_plan 为空报错文案还写着「列属性并判相对竞品」（已退役），改为「列买方约束名单」；售前 e2e（e2e_presales_gates.py）两条过时预期——「拦下题测劣势属性」「拦下属性池缺相对竞品」——validator 2.32.0 起已不拦（相对弱势可保留、新口径不判相对竞品），2.32.0 发布时没跑这套 e2e 所以一直红着，改为通过预期后 24/24。
- 验证：check_skill_terms 0 命中（扫出的 4 处——「看什么指标」改「读什么指标」、恢复「不再收」、gap-cause-action-table 和 prompt-generation-principles 各一处——已改）；单测 68/68；workflow e2e 76/76；售前 gates e2e 24/24。

## 2.33.1（2026-11-05）主题定义写成一句话

Suda 定。selection-rules 第 6 步「主题是什么」改为：主题 = 围绕同一类买家需求（购买决策）、涉及同一类产品或服务解决方案的一组提示词，两个条件同时满足。飞书规则文档术语表同步，删掉其中「同一批候选、同一套评估标准、同一个优化方向」的旧说法。

## 2.33.0（2026-11-05）正式题改按总额度封顶；主题不足 5 道的处理顺序

Suda 定。改前快照 `.snapshots/formal-quota-60-20261105-161946/`（项目根目录下）。

- 撤掉「每个已采购主题最多 10 道」。正式题总额度改为每条产品线 × 每个国家 × 每种语言合计最多 60 道，单个主题不设上限，额度在已采购主题之间按业务优先级分配。理由：上限管的是交付成本，按主题封顶会让题数在主题间平均分，重点主题拿不到额度，还会逼人把题挪进相邻主题。selection-rules 第 1、6、9 步，SKILL.md 第 9 步，output-contract 门禁 14，client-facing 主题表，shared 原则同步。
- validator 门禁 14：锁版后（locked / formal_baseline / active）按产品线数正式题（一个题库 = 一个国家 × 一种语言），超过 60 报错；验证题、停测题不计；候选阶段不查。原来的单主题超过 10 道报错删除。
- `check_client_base.py`：删除「已采购主题超过 10 道」；提示词库状态为「正式」的题按产品线 × 市场（× 语言，有该字段时）数，超过 60 报问题，市场多选的每个市场各算一次。
- 主题不足 5 道（W59）改为按顺序处理：① 补遗漏的买方约束、使用场景、受众、限制条件；② 构建有真实购买意义的复合条件，不靠同义改写、调换顺序、机械排列条件凑数；③ 检查主题是否拆得过细，只合并同一类购买决策、候选解决方案相近的相邻主题，不同购买决策或解决方案类别的不合并。三步后仍不足的写处理记录。W59 告警文字同步。
- check_skill_terms 登记退役说法「每主题最多 10 道」。
- SKILL.md 第 6 步表格里遗留的「每主题配 5–10 题」改为「至少 5 题、不设上限」（推送后补改）。
- 验证：单测 68/68 通过（`test_formal_set_caps_each_topic_at_ten` 改为 `..._each_product_line_at_sixty`：单主题 11、60 道放行，61 道报错，停测不计，候选阶段 61 道放行）；Sbrand US、Hbrand 走查题库、Hbrand v3、Ebrand v5 新旧 validator 对比，退出码不变，差异只有 W59 文字；构造两条产品线各 40 道放行、一条 62 道报错；Base 检查构造：SG 61 道报；SG+MY 多选 40 道加 SG 21 道，只报 SG 61、MY 40 不报；60 道不报。

## 2.32.0（2026-11-05）业务优先级一次判定；主题按需求及解决方案类别划分

另一会话在本版之前把版本改到 2.31.0（第 6 步拆合改成「决策任务、候选解决方案、内容方向」三个维度并加「品牌匹配」；售前预跑只留品类认知题），没有写修订记录；本版第 6 步的拆合标准按 Suda 11-05 新定的口径改写，「品牌匹配」保留。

Suda 定（讨论稿 `30-选Topic与生词/方案/选词矩阵-购买任务与业务优先级判法-20261105.md`）。主线：重要性只在矩阵行判一次，主题和题沿用；品牌强弱、AI 现在提不提品牌、品牌有没有内容都留到基线后。改前快照 `.snapshots/priority-mainline-20261105-154928/`。

- 业务优先级：按 Aleyda 的定义「一类买家需求对品牌的商业价值、战略重要性和当前业务重点的贡献」判高 / 中 / 低，不打分、不套公式。删除买家需求重要性、商业目标相关性两张表和三条定档规则（撤回 2.23.0 起的双项判断、2.27.2 的需求重要性门槛）。判断时考虑需求对目标客户购买决策的影响；证据多少、AI 读数、强弱、有没有内容、旅程阶段、信息型还是推荐型都不调档。
- 开行：受众 × 购买任务 × 三段只作查漏清单；只开真实存在、决策不同、有合理需求依据的行；范围外、没依据、品牌做不到又没服务路径的不开（取代 2.29.0 的「品牌用不上」口径）。同一任务的几种问法登记在同一行。
- 低档默认不出题，行保留，写「本期不出：业务优先级低」；高、中覆盖不够时可以补（撤回 2.28.0 的低档也出题）。validator 新增 W64（低档行挂了题）；W48 恢复只看高、中。
- 题型在写题时逐题判断：矩阵行登记的是可能的题型；有自然的找选项、找工具、找服务商问法就出发现题，没有的才本期不出；不为凑发现题改写意图。
- 品牌明显劣势只在出题原因里写风险提示，不降档（撤回 2.25 起的「写完查适配度降一档」）。
- 主题：在本期产品线范围内按主要买家需求及解决方案类别划分，一条产品线可以有多个主题；买家意图、竞争对手、评价标准和内容策略相近的放一起（Profound），差异显著时拆，品牌方要独立监测时可单拆；不细到每个属性或购买条件；业务优先级差异不作为拆分依据。主题优先级默认取组内多数行的业务优先级，没有多数时人工判断；同档按搜索量排先后，搜索量未知不当作需求小。validator W46 改为按多数行核对。
- 购买任务按买家要完成的目标、要做的决定区分，不按 AI 候选会不会变。
- 试跑合格判断补「问法是否自然」「是否和已有题重复」。挑正式题同档按需求覆盖、题目质量和代表性挑，删除 2.29.2 的「同档先选方案考虑、购买决策阶段」。
- 同步：client-facing、output-contract、signal-sources、SKILL.md、售前 selection-mode、shared/prompt-generation-principles；`check_client_base.py`；测试与 workflow 用例；`check_skill_terms.py` 加退役说法。

## 2.30.0（2026-11-05）「场景」改为「购买任务」

Suda 定：Hbrand 矩阵的「购买场景」混了购买目的（买房自住）、房源偏好（新盘）、家庭特征（有孩子按学区）和生命周期事件（住满五年换私宅），不在同一层级。对照 Aleyda 原文，她的矩阵 8 列没有场景，use case、family 都在 Buyer constraint 里；但她的约束是自由文本、本身写着这一行在做什么，我们的买方约束是不带取值的固定选项，删掉场景后「找组屋」「找公寓」两行分不开。所以保留这一列，改名「购买任务」并收紧定义。改前快照 `.snapshots/purchase-task-20261105-135314/`。

- 第 4 步「核心使用场景」改为「购买任务」：买家在找什么、要定什么，一个动宾短语；判断标准是换了任务 AI 列的候选会变、或起作用的买方约束明显不同；只多看一条约束的挂成约束；受众身份、购买目的、不改变问法的标签不写进任务。
- 矩阵一行 ＝ 产品线 × 市场 × 受众 × 购买任务 × 旅程阶段；全面梳理按核心受众 × 购买任务 × 三段；同一受众、同一购买任务只开一行。切片标签的「场景」维度改为「购买任务」（一般不登记）。业务范围「核心使用场景（n）」改为「购买任务（n）（我方填）」，矩阵列「场景 / 购买场景」改为「购买任务」。
- 题库 JSON 的 `scene` 键名沿用，含义改为购买任务；`tag_dimensions.py` 认新旧两个维度名；`check_client_base.py` 认购买任务、场景、购买场景三个字段名。售前 selection-mode 同步。
- 商业相关性判法这次不改（Suda 仍在考虑）。

## 2.29.2（2026-11-05）挑正式题时同档里中下部漏斗优先

Suda 提出方案考虑、购买决策一般比需求认知重要（漏斗中部）。不改业务优先级定档（阶段仍不是固定权重，需求认知里重要的痛点照样能判高），只在第 9 步挑正式题时规定：同一档里先选方案考虑、购买决策行的题，需求认知的题要说明新增覆盖。第 5 步「旅程阶段不是固定权重」改写为指向这条。

## 2.29.1（2026-11-05）第 5 步一句旧口径对齐

Suda 定：「旅程阶段不是固定权重」一条去掉「阶段决定这一行能出哪些题型」「本期出不出由品牌方的目标决定」，改为题型按依据登记、和阶段分别判断，本期出哪些题型看第 1 步。

## 2.29.0（2026-11-05）品牌用不上、硬条件的处境不开行

Suda 定：不定档的行根本不符合，不该出现在矩阵里。推翻 2.28.0 的「不定档、留空、写本期不出」。改前快照 `.snapshots/no-row-for-unusable-*/`。

- 第 3 步硬条件、第 5 步商业相关性低：这两种处境不开行，和「组合本身不成立」一样记进题库 notes「没开的格子」（处境和原因）；买家问得多的在交付说明里列出、说明为什么没测。矩阵里每行都有档位，取消「不定档」。
- 「本期不出」只剩一种：行上登记的题型本期都不出（只能出对比、评价等），照常定档。
- validator 与 `check_client_base.py`：撤回 2.28.0 的留空放行，矩阵行必须有高 / 中 / 低；低档行可以出题不变。测试与 workflow 用例同步（fixture M-003 改为购买决策行、本期不出其他题型）。
- client-facing、output-contract、SKILL.md、售前 selection-mode 同步；`check_skill_terms.py` 加「不定档」等退役说法。

## 2.28.1（2026-11-05）商业相关性低的说法改清楚

Suda 问「品牌根本不卖」指不卖相关产品还是没有相关约束。改为：买家在这个处境要找的根本不是品牌这一类产品或服务；并写明和硬条件（要的是这一类、但必须的条件做不到）、品牌明显劣势（做得到但比竞品弱）的区别。

## 2.28.0（2026-11-05）业务优先级改按三条规则定档，低档也出题

Suda 定：组合表看起来像两项相乘、区分度不够，改写成三条规则；商业相关性低的行不出题、不占档位；低档出题。判断结果和原组合表在高、中两档上不变。改前快照 `.snapshots/priority-three-rules-*/`。

- 三条规则：品牌方列出的重点（商业相关性高）——需求重要性高记高，其余记中；我们调研补出的（商业相关性中）——有买家来源的信号记中，只有假设记低；品牌用不上（商业相关性低）——不定档，本期不出，业务优先级留空。
- 商业相关性低要判得严：只有买家在这个处境要的东西品牌根本不卖才算；沾边、能服务只是不在重点里的算中；判不准的按中。
- 高 / 中 / 低都出题，低档题的提示词优先级为低，挑正式题时排在高、中之后。「本期不出」三种：只能出其他题型（照常定档）、品牌用不上（不定档）、硬条件（不定档）；取消「本期不出：业务优先级低」。
- validator：低档行可以出题；不定档的行依据里要有「本期不出」，挂题报错；W48 扩到低档方案考虑行。`check_client_base.py` 同步。测试与 workflow 用例改为新口径。售前 selection-mode 同步。

## 2.27.2（2026-11-05）需求重要性「中」降到至少一条买家来源的信号

Suda 定：需求重要性「中」的门槛改成「至少一条买家来源的信号」；「低」只剩只有假设（推理，或只有品牌官网、竞品官网、query fan-outs、AI 追问、模型建议问题）。原来「只有零星一条信号」也判低，调研补出的客群（商业相关性中）里只有一条真实买家说法的行会因此本期不出。买家来源的范围写明为买家原话、搜索数据和 Bing AI 检索词。高的条件不变。改前快照 `.snapshots/need-mid-threshold-*/`。

## 2.27.1（2026-11-05）官网评价先辨真伪；评价和社区按内容分

Suda 提醒：官网上标成买家评价的，可能只是品牌挑出来展示的，要辨别；评价和社区的区别要讲清。改前快照 `.snapshots/review-vs-community-*/`。

- 第 2 步「品牌官网」：官网上的评价有发布人、日期、星级、看得到中差评（或来自评价系统、标了已验证买家）才算买家信号；品牌挑选的好评、客户案例、无星级无日期的引语记「品牌官网」；问答区买家提问算买家信号、品牌回答记「品牌官网」；分不清的记「品牌官网」。
- 来源类型说明：评价和社区按内容分、不按网站分。买后使用体验记评价，买前提问、求推荐、比较讨论记社区。保留两类，因为需求重要性「两类及以上来源」把它们算作两类，买前有人问、买后有人评的条件更可靠。

## 2.27.0（2026-11-05）官网线索进需求信号表

Suda 定：品牌官网、竞品官网调研补出的受众、场景、买方约束线索进需求信号表，写清来源类型；但只开假设级候选，不算矩阵行的信号支撑，规则同 query fan-outs。原因：支撑决定买家需求重要性，进而决定业务优先级；官网线索算支撑的话，竞品宣传加品牌官网就能凑成「两类来源」，把买家未必在意的条件判成高。改前快照 `.snapshots/site-clues-to-signals-20261105-113353/`（含模板「来源类型」字段改前定义）。

- 来源类型新增「品牌官网」「竞品官网」：品牌自己写的内容（导航和专页、FAQ、购买指南、竞品强调的选择条件）；官网上买家写的评价、问答仍记评价或社区。找到对应买家说法的另登一行。
- selection-rules 第 2 步两节、第 5 步需求重要性依据，client-facing 需求信号字段说明，signal-sources 三处同步；竞品官网不再单记 notes，竞品自称的定位和卖点不记。
- `check_client_base.py`：`HYPOTHESIS_SOURCES` 加这两类，不算支撑。`write_prompt_reasons.py`：计数显示为「品牌官网线索」「竞品官网线索」，不拿来当代表原话。售前 `export_to_confirm_base.py` 选项白名单加这两个值。
- 飞书《AI 搜索监测确认表（模板）》需求信号表「来源类型」加两个选项并补说明；`check_client_base.py --template` 通过。

## 2.26.3（2026-11-05）竞品官网按 3 家看

Suda 定：竞品官网调研按 3 家梳理。取业务范围里第 1 步核对补足后的竞品，超过 3 家的取品牌方列在前面的 3 家。改前快照 `.snapshots/competitor-3sites-*/`。

## 2.26.2（2026-11-05）竞品官网删去第四问

Suda 定：竞品官网只回答三个问题，删去「有没有覆盖品牌没考虑的品类、产品或替代方案」。品类边界和适用边界由品牌方定、每期一条产品线；竞品集合在第 1 步核对；替代方案发现题会自己列、预跑和社区能看到，这一问不改变出哪些题。定位里的「确认竞争范围」一并去掉。改前快照 `.snapshots/competitor-q4-*/`。

## 2.26.1（2026-11-05）竞品官网改回轻量调研

Suda 定：竞品官网需要调研，作用是补买家需求、发现漏掉的决策条件、确认竞争范围，不判品牌相对竞品的强弱，是辅助线索、不决定主题和题。推翻 2.26.0 的「不单独调研竞品官网」。Aleyda 的受众语言来源清单里有 Comparison pages、Product documentation and help center queries（已核原文）。改前快照 `.snapshots/competitor-site-light-20261105-111841/`。

- 第 2 步「竞品」一节改为「竞品官网」：每个竞品只回答四个问题（服务谁、强调哪些选择条件、FAQ 与指南暴露哪些买家问题、有没有覆盖品牌没考虑的品类或替代方案）；看到的都当候选，找到买家信号才进需求信号表和矩阵；记进题库 notes「竞品官网」一节（竞品、看到什么、来源网址、买家需求是否已验证）；不做 SWOT、逐项打分、SEO 审计。
- 第 3 步「品牌明显劣势」补一句：竞品那边只为核对这一条看对应产品页或规格表，不全面建库。
- SKILL.md 第 2 步、signal-sources 两处补回竞品官网行。

## 2.26.0（2026-11-05）官网调研只看必要的；品牌明显劣势给题降档

Suda 定：官网调研只看对生词有影响的内容，不过度复杂化；按专家调研结论改（原始笔记 `30-选Topic与生词/研究与方法/官网与竞品调研-专家做法-原始笔记A-工具厂商-20261105.md`、`…B-独立专家-20261105.md`）。专家里没有人系统看竞品网站结构，竞品情报都取自 AI 回答和竞品评价；官网内容没有人当买家需求证据；品牌事实清单用于判 AI 说得对不对，不用来定出哪些题；出题前没有人逐条判真实强弱。改前快照 `.snapshots/site-research-simplify-20261105-*/`。

- 第 2 步「竞品网站结构」一节删除，改为「品牌官网」（卖什么、卖给谁、在哪卖、能做到什么，后三项整理成品牌能力清单记进题库 notes）和「竞品」（不单独看官网，从预跑答案里 AI 比较各家用的条件和竞品评价、社区里取）。官网上买家写的评价、问答进需求信号表；品牌写的 FAQ、博客选题只当线索。第 6 步「聚完拿竞品网站结构查漏」删除；题面条件依据去掉「竞品筛选项」。
- 第 3 步品牌事实核查：属于品牌呈现，本期暂停，不专门做，预跑、试跑或看官网时顺带看到才记。
- 第 3 步新增「品牌明显劣势」：买方约束收齐后拿能力清单对一遍，只记有可核实事实的明显劣势（在哪种情况下不如竞品、事实、出处），记在 notes，不判优势、持平。第 7 步新增「写完查适配度」：题面条件落在记下的劣势情况里的题，提示词优先级降一档并写改档理由；行的业务优先级不动；写题时不回避这些条件。依据是 Profound 第 2 章「差距补不上的往后排」，逐题降档是我们自己的做法。
- 对客表「本期不出」补上第三种「硬条件」；提示词优先级说明补一句劣势降档。signal-sources 删竞品官网相关三行，品牌官网一行改为指向第 2 步。
- `check_skill_terms.py` 加退役说法「竞品网站结构」「竞品筛选项」等。售前 `geo-presales-prompt-builder` 没有引用被删的一节，未改；它的「属性与相对竞品」一步与选词不一致，待 Suda 定。

## 2.25.1（2026-11-05）业务范围「核心优势」改名「差异化优势」

Suda 定：业务范围表的「核心优势」改叫「差异化优势」。这个字段用作买方约束候选和切片标签取值，叫「核心优势」时品牌方容易填正品保障、售后完善这类品类门槛，第 3 步本来就不收它们，拿来做切片也切不出差异。改前快照 `.snapshots/selection-rules.md.20261105-100940.bak` 等同批文件。

- 字段说明改为「相比主要竞品、买家能感知到的不同之处；竞品普遍也有的不算；只对特定客户或场景成立的注明适用范围」；仍不要求证据，相对竞品仍在正式基线后判。
- selection-rules.md、client-facing-attribute-pool.md、signal-sources.md 同步改名；售前 `export_to_confirm_base.py` 写业务范围的行名改为「差异化优势（1）」（售前 Case 字段本来就叫差异化优势）。
- `check_skill_terms.py` 加退役说法「核心优势」「业务范围的「优势」」。

## 2.25.0（2026-11-04）矩阵字段改名，补 Hbrand 重梳的教训

Suda 定：「可出题型」跟提示词库一样叫「提示词类型」；结合 Hbrand 矩阵重梳的经验教训优化 skill。改前快照 `.snapshots/selection-rules.md.20261104-193837.bak` 等同批文件。

- 矩阵「可出题型」「可出题型依据」改名「提示词类型」「提示词类型依据」；`check_client_base.py` 新旧名都认；模板和 Hbrand Base 同步改名。
- 第 4 步场景：场景名里不写受众和身份（新公民、PR、本地人），不写去掉后问法和买方约束都不变的标签（「第一次买房」）。Hbrand 曾因此开出两个重复场景。
- 第 5 步：同一场景下同一个买家任务只开一行，放在一个旅程阶段（Hbrand 的 BTO、购房资格各在需求认知和方案考虑开了一行）；`check_client_base.py` 对场景、受众、买方约束完全相同的行报问题。
- 第 5 步：梳理完按「有信号却没挂在任何矩阵行上的买方约束」逐条查漏（Hbrand 因此补出「查具体楼盘」）。
- 「本期不出」的理由不能写试跑读数（Hbrand M-024、M-025 曾因「Hbrand 0/5」停测）；`check_client_base.py` 拦截。没有切片编号的空行报问题。

## 2.24.0（2026-11-04）需求信号的来源类型按关键词工具拆开

Suda 定：关键词工具一类要写清数据是哪个工具给的。不同工具估出的搜索量可能差几倍，只写「关键词工具」时核对不了、也看不出能不能放在一起比。改前快照 `.snapshots/source-type-split-20261104-192406/`（项目根目录下，含两个 Base 的字段定义与 Hbrand 改前记录）。

- 来源类型去掉「关键词工具」，改为 DataForSEO / Semrush / Ahrefs / Similarweb / Keyword Planner / Naver 六项，按数据实际从哪个工具导出选；月搜索量字段说明改为「来源类型选那个工具」，其他来源类型补查了量的，出处写明量取自哪家。
- 飞书《AI 搜索监测确认表（模板）》需求信号表的来源类型选项与说明、月搜索量说明已改；Hbrand 32 条按出处迁成 Ahrefs 20、Semrush 12，旧选项已删。
- 脚本：`collect_keyword_data.py` 输出来源类型 DataForSEO；`write_prompt_reasons.py` 出题原因里六个工具仍合成「搜索词」一类计数；售前 `export_to_confirm_base.py` 写新模板时，旧的「搜索数据」「关键词工具」按出处认工具，认出是自动补全、相关搜索的归搜索联想（原来一律映射成关键词工具，Bbrand 那 4 条其实是自动补全），都认不出就停下要求补出处；`check_skill_terms.py` 加退役说法。

## 2.23.0（2026-11-04）业务优先级 ＝ 买家需求重要性 ＋ 商业目标相关性

Suda 定（按营销的市场细分、目标市场选择和购买决策研究）：矩阵优先级回答「哪些买家需求最值得品牌争取进入购买决策」，由目标客户的需求重要性和品牌的商业目标相关性共同决定。推翻 2.22.0 的「商业价值按旅程阶段看离线索多远」和 2.20.0 起的「需求只判有没有」。改前快照 `.snapshots/selection-rules.md.20261104-192452.bak` 等同批文件。

- 买家需求重要性：看需求信号，综合普遍程度、对购买决策的影响和紧迫程度判高 / 中 / 低；不等于搜索量，低频但决定最终选择的需求可以是高。
- 商业目标相关性：品牌方列出的本期重点客群和需求为高；品牌能服务、我们调研补的为中；买家在这个处境用不上品牌卖的东西为低。
- 两项按表共同决定，不相乘、不换算分数；只设一个「业务优先级」字段。
- 旅程阶段不是固定权重：阶段决定可出题型，本期出不出看目标。
- 前提：品牌服务不了的需求不出题，写「本期不出：硬条件」。
- 业务优先级和优化优先级分开：AI 可见度、竞争难度、可改变性不进矩阵档位，基线后排优化顺序。
- 档位名仍用高 / 中 / 低（对应 Suda 说的 P1 / P2 / P3），不再改名。

## 2.22.0（2026-11-04）业务优先级 ＝ 业务重要性 × 商业价值

Suda 定：BTO、查资格这类行对业务没价值、离线索远，2.20.0 却判成高，判法有问题；改为业务范围的核心目标客户与购买场景结合旅程阶段，综合判业务重要性和商业价值。改前快照 `.snapshots/selection-rules.md.20261104-191051.bak` 等同批文件。

- 2.20.0 的两处错：起点只对客群，不对需求（BTO 客群是第一次买房的人，需求却不是找房）；「推断不改档」让离线索远的行保留高档。
- 业务重要性：不分第几条，客群和需求都是品牌方列出的为高；我们调研补出的（客群或需求品牌方没列、有信号、品牌用得上）为中，确认时品牌方可以提档或删行。
- 商业价值：结合旅程阶段看买家下一步会不会用上品牌卖的东西，会为高，不会为低；有成交或转化数据的以数据为准。原「需求认知降一档」并进这一项。
- 两项按表综合（高×高＝高、高×低＝中、中×高＝中、中×低＝低），只有假设的再降一档。
- 「业务重要性」重新作为判断项名称使用；退役检查只拦旧字段写法（业务重要性为X、业务重要性依据、业务重要性（高））。

## 2.21.3（2026-11-04）AI 生成的来源拆成三类

Suda 指出追问、Perplexity 相关问题都不是 query fan-out。改前快照 `.snapshots/*.20261104-191111.bak`、`.snapshots/template-base-signal-source-field.*.json`。

- 来源类型在 Bing AI 检索词之外，把模型生成的拆成 query fan-outs（AI 检索时拆出的子查询，ChatGPT `search_model_queries`、Grok `tool_usages`）、AI 追问（答案末尾反问的条件，ChatGPT 读 `follow_up_form`，其他平台从正文末尾读）、模型建议问题（Gemini `related_queries`、Perplexity 相关问题、让模型列的顾虑与搜索词）。三类都只开假设级候选，`check_client_base.py` 统计信号支撑时都不算。
- 核实（2026-11-04 本地采集逐平台扫字段）：fan-out 除 ChatGPT 外 Grok `tool_usages`（web_search 的 `tool_args.query`）也有；ChatGPT 追问有结构化字段 `follow_up_form`；Grok `follow_up_suggestions`、Alexa `suggestions` 是延伸问题；Perplexity、AI Mode、AI Overview、Copilot 没有 fan-out 字段。Perplexity 的 `related_prompt` 最近 207 份全空；Gemini `related_queries` 400 份里 16 份有值，内容是延伸问题而不是检索词；按正文末段粗筛约 200 份/平台，带追问的 AI Mode 约六成、Gemini 约四分之一、Perplexity 约一成、ChatGPT 不到一成。
- 模板 Base「来源类型」加两个选项、改字段说明；`write_prompt_reasons.py`、售前 `export_to_confirm_base.py` 同步。

## 2.21.2（2026-11-04）搜索词先分簇再改写

Suda 定，参考 Similarweb「搜索词 → 意图聚类 → 代表性 Prompt」。改前快照 `.snapshots/signal-sources.md.20261104-190803.bak`。

- signal-sources「搜索词改写成题面」开头加分簇：同一购买任务、同样会改变答案的条件算一簇，一簇最多一道代表题；条件不同、候选或评估标准跟着变的分簇；复合条件按第 7 步默认 1–3 个；没带来新需求、没改善问法、也没增加证据的簇不出题。
- 「原查询按一条需求信号登记」改为簇里用上的每条查询各登记一条，代表题证据挂这些编号。

## 2.21.1（2026-11-04）PAA 与 Bing Grounding Queries 口径统一

Suda 定：signal-sources 前后两张表对这两类信源说法打架；Grounding Queries 背后是真实用户的提问，是证据，不该和试跑 fan-out 同级。改前快照 `.snapshots/signal-sources.md.20261104-185051.bak`。

- Bing Grounding Queries：算需求存在的证据，和搜索词同级；里面的条件可能是 AI 补的，写进题面前另找原话或写 `condition_basis`；报告按引用次数排序能看出相对热度，次数是品牌被引用的次数、只覆盖已引用到品牌的提问，和 GSC 展示量一样只作主题优先级依据的补充。推翻「按 query fan-out 同级处理」。
- 试跑 fan-out、AI 追问：背后没有真实用户，只开假设级候选，不再写「同 Grounding Queries」。
- PAA、相关搜索、自动补全：删「估主题规模」（不带量），「不能决定题面措辞」改为「不经改写直接当题面」，题面措辞来源加 PAA 问题，与「搜索词改写成题面」一致。
- 长尾词导出不改（Suda 定）。
- 需求信号「来源类型」的「AI 检索词」拆成「Bing AI 检索词」（Grounding Queries、Topics Portfolio 机会查询）和「query fan-outs」（试跑和基线子查询、AI 追问条件、Perplexity 相关问题等模型生成的）（Suda 定）。`check_client_base.py` 统计矩阵行信号支撑时不算 query fan-outs；`write_prompt_reasons.py` 加两个显示名，旧选项照读；售前 `export_to_confirm_base.py` 把旧「AI 回答」「AI 检索词」映射到 query fan-outs（售前没有 Bing 后台数据）。模板 Base 需求信号「来源类型」选项与字段说明已改，改前字段定义存 `.snapshots/template-base-signal-source-field.*.json`；已有客户 Base 不迁移。

## 2.21.0（2026-11-04）主题按核心购买决策定，写完候选题后定稿

Suda 定，参考 Profound、Semrush、Peec AI、Aleyda 的分组原则（Profound 课程原文未核对，规则写成我们自己的判断标准）。改前快照 `.snapshots/selection-rules.md.20261104-184625.bak` 等同批文件。

- 定义：主题是围绕同一核心购买决策的一组提示词，组内可跨买方约束、客群、场景和阶段，推荐对象和评价标准相近；买方约束、问法不单开主题。
- 拆合依次判核心决策、推荐对象、评价标准、内容方向（能不能用同一类内容回答，写题时按题面推断），不要求四件全部一致。推翻「候选相同或不同都只作辅助信号」「AI 推荐结果用于复核，结果变化本身不决定边界」。
- 顺序：矩阵后聚主题候选，第 7 步写完候选题后定稿，试跑后按候选集合复核。
- SKILL、signal-sources、shared 原则同步。

## 2.20.0（2026-11-04）业务优先级改为品牌方排序起点、三项调档

Suda 定：三个因素太复杂，战略重要性和当前业务重点重复；业务优先级判的是在特定客群、需求场景和购买阶段下这类问题有多重要，要综合买家需求与业务价值。改前快照 `.snapshots/selection-rules.md.20261104-184042.bak` 等同批文件。

- 起点：品牌方排序（核心目标客户与购买场景第 1 条为高、其他列出的为中、列表外为低）。当前业务重点由适用边界管，不另判；战略重要性就是这个排序。
- 三项各调一档：需求认知阶段降一档；成交数据按数据升降，没数据由模型推断、写进依据不改档；只有假设没有需求信号的降一档。
- 推翻 2.19.0「不另算需求普遍程度」和「证据不进档位」：需求只判有没有，多少仍在主题优先级按月搜索量排。
- client-facing、signal-sources、SKILL、shared 原则、check_client_base 提示语、售前 export_to_confirm_base 草稿依据同步；两份 Base「业务优先级」「业务优先级依据」字段说明同步。

## 2.19.1（2026-11-04）资料收集字段对齐文档定稿

Suda 在《品牌资料收集》里定稿后同步。改前快照 `.snapshots/intake-core-advantage-20261104-181736/`。

- 「优势」改名「核心优势」。
- 「核心目标客户与购买场景」按文档写法：按业务优先级填最重要的几条，不再写 1–3 条；每条写目标客户和购买场景与需求；B2B 写企业类型、规模及决策或使用角色。
- 业务目标继续不收：它不改变出哪道题，内容规划和复盘阶段再问。
- 确认表模板业务范围：「目标人群及使用场景」「目标企业画像」两条示例行合成「核心目标客户与购买场景」，「差异化优势」改「核心优势」，其余示例行和字段说明的引用同步。Hbrand 业务范围同步。售前 `export_to_confirm_base.py` 写入的行名改「核心优势（1）」，读的 Case 字段仍是「差异化优势」。

## 2.19.0（2026-11-04）不设属性池，改为「买方约束」选项；业务重要性改名业务优先级

Suda 定：约束不要了；属性池没必要，只看提示词矩阵；属性改叫「买方约束」；矩阵「业务重要性」改「业务优先级」，按 Aleyda《AI Search Prompt Library》Step 5 的商业价值、战略重要性、当前业务重点判。改前快照 `.snapshots/drop-attr-pool-20261104-165620/`（两份 Base 全部表的字段、记录、视图，skill、shared、售前、监测文档和脚本，迁移脚本 `drop_pool.py`）。

- 对客 Base：需求信号「属性关联」、提示词矩阵「属性关联」、提示词库「属性」三个链接字段改为同名选项字段「买方约束」（都可多选，提示词库第一个是主约束），选项是同一份名单；删需求信号「约束」。模板删属性池表；Hbrand 原值逐行回填、回读一致（信号 302 行、矩阵 27 行、提示词库 33 行，原来挂两三条属性的 10 道题全部保留），属性池表保留待确认后删，类别、相对竞品和依据存档在 `售后/属性池存档-20261104.md`。
- 矩阵「业务重要性」「业务重要性依据」改名「业务优先级」「业务优先级依据」，字段说明写明三个判断因素；主题优先级、提示词优先级说明同步。
- selection-rules 第 3 步改为「买方约束」：统一粒度（一条 ＝ 买家比较选项的一个维度；买家任务写成矩阵行；一条里两件事拆开；具体取值不拆条），不判重要性、不判相对竞品，写题前确认硬条件；第 5 步业务优先级按三个因素判，不另算需求普遍程度；第 7 步题面具体条件从这一行相关的需求信号原话取，用到的信号挂在「证据」上。client-facing、signal-sources、output-contract、SKILL、shared 原则、售前 selection-mode 同步。
- 相对竞品挪到正式基线后、只判有缺口的题：判法从 selection-rules 移到 geo-monitoring gap-cause-action-table「相对竞品怎么判」；baseline-report 优化顺序注明没判的不参与排序。
- 脚本：`check_client_base.py` 改读「买方约束」（旧 Base 的链接照认），新增三张表选项一致检查，没有属性池时不查属性池，业务优先级新旧名都认；`write_prompt_reasons.py` 没有属性池也能跑，主约束取「买方约束」第一个；售前导出写新模板时属性名写成「买方约束」选项、不写相对竞品；三个采集脚本输出列「买方约束」、去掉「约束」；`tag_dimensions.py` 认「买方约束」维度。
- validator：`attribute_plan` 不再要求相对竞品；门禁 36 在信号没有「约束」时改为查题面条件有没有引用需求信号或写 `condition_basis`、数字是否出现在所引原话里（shared `scope_gates.py`），旧题库照旧逐词核对。evals 新增 `condition_without_cited_signal`，76/76 通过；单测 68 通过。
- check_skill_terms 登记退役说法：业务重要性、属性池、属性关联、常见约束、相对竞品依据。
- 同日追加（Suda 定）：提示词矩阵删「备注」（模板和 Hbrand），拆题理由写进出题原因、竞品依据在可出题型依据、没有信号的行在业务优先级依据写「假设：……」；Hbrand 14 行备注原文存档在 `售后/矩阵备注存档-20261104.md`。Hbrand 属性池表已删。`check_client_base.py` 把「备注」列为已移除字段。快照 `.snapshots/drop-note-pool-20261104-180529/`。
- 同日追加（Suda 用 Hbrand 举例）：三个因素互相独立，商业价值高不代表是当前重点；业务优先级依据按三点各写一句，没数据的写「待验证」。selection-rules 第 5 步加例子，client-facing 与两份 Base 的字段说明同步。

## 2.18.0（2026-11-04）资料收集文档字段合并

Suda 定。改前快照 `.snapshots/intake-fields-merge-20261104-172704/`。

- 《品牌资料收集》第一部分的「目标企业画像」「目标人群及使用场景」合成「核心目标客户与购买场景」，每条写服务什么样的买家、解决什么问题、购买决策关注哪些属性；「差异化优势」改名「优势」。selection-rules、signal-sources、client-facing、SKILL，以及 geo-monitoring、shared 原则里的字段名同步。
- 优势按文档说明收：本期产品相比主要竞品的核心优势（功能、性能、价格、服务或资源），仅适用于特定客户或使用场景的注明。相对竞品仍由我们判，不要求品牌方举证。
- 拆受众、优先受众、业务重要性的判断规则不变，只改从哪个字段取；B2B 第 1 条同时定优先的企业类型和角色。售前 Case 字段（目标企业画像、差异化优势）属于另一份合同，不动。

## 2.17.1（2026-11-04）相对竞品依据只写依据；不收 GEO 优化目标

Suda 定。改前快照 `.snapshots/attr-pool-slim-20261104-161524/`（`hbpool3.ndjson`、`tplpool3.ndjson`、`basis_noprefix.json`）。

- 相对竞品依据不再写「相对竞品（持平）：」开头，也不在末尾写「判持平」：结论只在「相对竞品」一列。Hbrand 45 行、模板示例 1 行已去掉；顺手清掉 5 行残留的搜索量和出题决定。`check_client_base.py`：新字段只查优势 / 持平 / 劣势时依据不空；旧 Base 的「判据与证据」仍要求带结论开头。
- 常见约束公式改为按顿号（以及逗号、分号、斜杠）拆开后去重。写法不同的同一条件去不掉，所以登记信号时约束要用统一说法。
- 不让品牌方选 GEO 优化目标：只做发现型可见度，四类目标表保留、暂停。SKILL、selection-rules、client-facing、shared 原则里「品牌方本期选的目标」「用业务目标重判」「品牌方未选竞争定位」的写法改为「本期只做发现型可见度」；模板矩阵「旅程阶段」「可出题型」「业务重要性依据」字段说明同步，业务重要性依据加 Google Ads 转化。

## 2.17.0（2026-11-04）属性池精简：手填只剩五列

Suda 定（Hbrand 先精简了品牌取值、还缺什么、常见约束）。改前快照 `.snapshots/attr-pool-slim-20261104-161524/`（两份属性池的字段、记录、视图，清理前后的依据文字 `clean_basis.json`，售前 selection-mode 原文）。

- 属性池手填只剩：属性、类别、相对竞品、相对竞品依据、产品线；自动：常见约束、关联信号、信号条数、提示词。
- 删「品牌取值」：品牌和竞品的实际值写进相对竞品依据里比较的那一句。删「还缺什么」：待确认或要品牌方回答的写「还缺……」，放在相对竞品依据。「常见约束」从手填改为公式（关联信号的约束自动汇总；Suda 定名字仍叫常见约束，没有用「信号约束」），不来自信号的条件写题的 `condition_basis`；题库 JSON `common_constraints` 保留，改为由关联信号的约束生成，validator 不改。
- 「判据与证据」改名「相对竞品依据」，只写为什么这样判（和谁比、比的事实、结论），不写需求证据、信号编号、搜索量（看关联信号）。Hbrand 32 行清掉需求证据，回读一致、残留 0。
- Hbrand 删「属性编号」（规则早已退役，45 行全空）。
- 脚本：`check_client_base.py`、`write_prompt_reasons.py` 先读相对竞品依据、旧名照认；售前导出写新模板时把判据与证据映射到相对竞品依据。售前 selection-mode 的常见约束、品牌取值说法同步。
- check_skill_terms 登记退役说法：判据与证据、「还缺什么」、属性池手填常见约束的说法；「信号约束」也登记为退役（中间版本的名字）。

## 2.16.1（2026-11-04）需求信号只判受众、属性、约束

Suda 定：需求信号保留受众、属性关联、约束三样，登记时各判一次；不设矩阵行关联。依据：Hbrand 342 条信号里矩阵行关联只挂上 130 条，而且全靠信号上原有的受众推出来；矩阵是最常重切的表，挂在行上的关联每改一次要重挂；10-14 已定受众依据就是买家原话、两表共用一套受众选项（2.16.0 删受众违背了这条）。改前快照 `.snapshots/signal-audience-20261104-152829/`。

- 模板与 Hbrand：删需求信号「矩阵行关联」和矩阵「依据信号」「依据信号条数」；需求信号加回「受众」（多选，选项同矩阵受众）。Hbrand 342 条按迁移前导出原样回填，回读 342/342 一致。
- client-facing、signal-sources、selection-rules：信号只判受众、属性、约束；场景从约束聚，旅程阶段在矩阵行判；矩阵行有没有信号支撑由脚本按「受众相同、属性在这一行上」统计。
- `check_client_base.py` 新增第 7 项：信号受众不在矩阵受众里报问题；另打印提示（不算问题）：没有信号支撑的矩阵行、没有信号的受众、有信号却没挂在矩阵行上的属性。Hbrand 实跑：4 行无支撑（M-003 和 3 行无编号），19 条属性有信号却不在矩阵里。
- 三个采集脚本输出列「矩阵行关联」换成「受众」；售前导出保留受众。
- check_skill_terms 登记「矩阵行关联」「依据信号」为退役说法。

## 2.16.0（2026-11-04）买家原话表改为需求信号表，每类数据写清用途

Suda 2026-11-04 定：表名改「需求信号」，买家原话、搜索词、AI 检索词放一张表；删受众、旅程阶段、收集日期、证据可信度、涉及品牌、来源说明 6 个字段；来源链接改为文本「出处」；中文意思统一叫「译文」；加「属性关联」「矩阵行关联」；AI 检索词可以进表、按普通证据综合判断；月搜索量哪家有数据填哪家；Google Ads 有转化的查询对应场景写进业务重要性依据；所有数据写清用途；来源类型选项由我方定。讨论与改动清单见项目 `docs/exec-plans/active/demand-signal-table-redesign-20261104.md`，改前快照 `.snapshots/demand-signal-20261104-142038/`（模板五张表的字段、记录、视图，skill、shared 脚本、售前导出脚本、监测 references）。

- 飞书《AI 搜索监测确认表（模板）》：表改名、删 6 字段、来源链接改「出处」、来源类型改 12 个选项、加两个关联；属性池加「关联信号」「信号条数」「信号约束」，矩阵加「依据信号」「依据信号条数」；默认视图按来源类型分组；主题表「Google 月搜索」改「月搜索量」、「买家原话条数」改「信号条数」；业务范围主要受众、核心使用场景示例行加「（我方填）」；属性池常见约束、矩阵可出题型依据的字段说明同步。
- client-facing：需求信号一节重写；属性池、矩阵、主题、提示词库字段同步；业务范围写明哪些行我方填；业务重要性依据加 Google Ads 转化。
- signal-sources：新增「每类数据怎么用」（处理顺序＋三张用途表：品牌方填写的业务信息、品牌方提供的数据、我方收集的数据）；关键词工具写明非品牌筛选（品牌方有就选、没有直接导，我方按别名再筛，缺口报告的竞品词归竞品词）；Grounding Queries、模型联想、AI 追问可作为 AI 检索词登记，删掉「进正式集前需买家信号佐证」；月搜索量哪家有填哪家，展示量和站内次数不填；Trends 结论写进主题优先级依据。
- selection-rules：第 2 步「收需求信号」；第 5 步业务重要性加 Google Ads 转化；第 6 步月搜索量来源改为哪家有数据用哪家。
- output-contract：`buyer_quotes` 键名沿用，条目可带 `属性`；W35、W36 文字改为需求信号。
- geo-monitoring baseline-report：新增「平台自报参照」，GSC Generative AI Performance 和 Bing AI Performance 的引用页作为优化前参照和内容交接线索，不混进提及率、引用率，暂不进页面。
- 脚本：三个共享采集脚本输出新列（来源类型分别记搜索联想、关键词工具、评价；出处合并原来源说明、链接、日期）；`write_prompt_reasons.py` 先读需求信号、读不到再读买家原话，代表原话按来源类型排、同类有月搜索量的在前，站点从出处网址认；`diff_base_against_spec.py` 默认主键加需求信号；售前 `export_to_confirm_base.py` 写新模板副本时把旧调研行转成需求信号行、业务范围匹配加「（我方填）」，旧副本照旧写买家原话。
- check_skill_terms 登记退役说法：买家原话表、证据可信度、涉及品牌、来源说明、来源链接、中文意思、Google 月搜索。
- 旧客户 Base 不迁移；验证用 Hbrand 确认表的副本跑了一遍迁移（见 Hbrand 目录 `售后/需求信号验证-20261104/`）。

## 2.15.0（2026-11-04）按《品牌资料收集》最新字段同步

Suda 要求按飞书《AI 搜索监测｜品牌资料收集》（原《品牌方填写模板》，2026-11-04 版）更新 skill 和确认表模板。改前快照 `.snapshots/intake-doc-sync-20261104-114444/`（references、SKILL、CHANGELOG、确认表业务范围原值、抓下来的文档、presales 导出脚本）。

- 业务范围（selection-rules 第 1 步、client-facing）：品牌方填的字段对齐文档第一部分：品牌、品牌别名（加产品系列名，易混淆、不计入的另注）、官方域名（官网、子域名、市场独立站，各注用途；没有官网写「无」）、市场、语言（买家向 AI 提问的语言）、本期产品线、适用边界、目标人群及使用场景 1–3、差异化优势 1–3（写清具体能力）、竞品 1–3（名称和官方域名，我们补足到默认 3 个）。品类、平台改为我方填。每期只收一个市场、一种语言、一条产品线；产品线不再「全列再标优先」，改标（本期）/（后续）。「无」照写，「待补充」行首写【请品牌方补充】。
- 资料（signal-sources、selection-rules、client-facing）：GSC 不再由我方写非品牌正则，没有 Non-branded 筛选的直接导出、我们按别名去品牌词；不再要求按展示次数排序；长查询改为只在顶到 1000 行时另导，4 个词以上（`^(\S+\s+){3,}\S+$`，原 6 个词）；加 Page URL 筛选和导出字段。Bing 改「建议开通、有数据时提供」，加从 GSC 导入、Topics Portfolio（Beta）。GSC Generative AI Performance 写明 Web: text-based 和四个维度。Semrush / Ahrefs / Similarweb 改为三类导出（自然搜索、长尾 ≥4 词、对比 3 个竞品的关键词缺口）及条数上限。销售、客服加「会影响购买决策的兼容性、安装、使用成本、售后保障和维护问题」，销售没有团队的跳过；B2B 成交客户分布文档里没有，改为不再向品牌方要、主动给了照常用（Suda 当日确认）。没有官网时：关键词工具改导竞品官网的自然搜索词和长尾词。权限去掉 GA4 查看者。
- 购后边界：买完才问的安装操作、退货、排障不进选词；买前影响选择的安装要求等照常进（selection-rules 旅程阶段、signal-sources 偏差表）。
- 飞书《AI 搜索监测确认表（模板）》业务范围：改 10 条【示例】行（市场与语言、适用边界、官方域名、目标人群及使用场景、品牌别名、差异化优势、竞品的说明与示例；品类、平台注明我方填；产品线（1）（优先）→（本期））和「项目」字段说明。
- 同日追加（Suda 定「4 个词不算长尾」）：长尾门槛统一为 6 个词。GSC 长查询正则改回 `^(\S+\s+){5,}\S+$`（Suda 已在文档里改），Bing 加 Search Performance → Keywords 导出与 6 词长查询；Semrush / Ahrefs Word count、竞品缺口额外筛选都改 6 词。飞书资料收集文档其余 5 处「4 词」改为 6 词；signal-sources、selection-rules、client-facing 同步。本条推翻上一条资料同步里的「4 个词以上」。
- 同日追加（Suda 定）：B2B 加「目标企业画像」字段（1–3 条：行业＋规模、覆盖市场等特征；B2C 写「无」），和售前 Case 的同名字段对齐；「目标人群及使用场景」保留，B2B 写决策或使用角色。selection-rules 第 1、4 步（B2B 先按企业、再按角色拆受众，受众写「企业类型＋角色」）、client-facing 业务范围同步；飞书资料收集文档第一部分在目标人群前插入这一行；确认表模板加【示例】目标企业画像（1）并改「项目」字段说明。没有改成泛化的「目标客户画像」：画像会引来年龄、收入这类不改变 AI 候选的人口属性，还会丢掉「什么情况下需要」。
- geo-presales-prompt-builder `export_to_confirm_base.py`：写入的产品线行改为「产品线（1）（本期）」，匹配模板说明的正则加「（本期）」，旧模板副本仍兼容。

## 2.14.0（2026-11-03）只做发现型可见度，业务范围精简

Suda 定：目前只做发现型可见度，其他三类目标先不做；业务范围字段保持极简。改前快照 `.snapshots/biz-scope-slim-20261103/`（skill、填写模板、确认表模板业务范围都在里面）。

- selection-rules 第 1 步：只做发现型可见度，竞争定位、品牌呈现、声誉与信任和问题解决题暂停，四类目标表与第 7 步题型规则保留待重新开放；`config.business_goals` 一律写 `{selected: ["发现型可见度"], information_named: false}`；删掉「最希望改善的 AI 搜索表现」问法块；需求收集只走核心可见度问题。validator 不改（W52 照常拦多出的题型）。
- client-facing 业务范围：删「希望解决的 AI 搜索问题」「品牌方关心的问法」两条；「品牌与产品别名」统一叫「品牌别名」；差异化优势写明是主推卖点、不另设「产品卖点」；列出单值行。
- 飞书《品牌方填写模板》：删业务模式、本地术语与市场差异、监管与敏感事项三行；品牌名称→品牌、不做的业务→适用边界、目标受众→主要受众；差异化优势、竞品、核心可见度问题的说明与示例改为只服务发现型可见度（竞品写「名称（官网域名）」，核心可见度问题不再写「说得对」）。
- 飞书《AI 搜索监测确认表（模板）》业务范围：删三条对应【示例】行；核心可见度问题、竞品、差异化优势的「为什么重要」同步；「项目」字段说明更新。
- check_skill_terms 登记「品牌方关心的问法」「希望解决的 AI 搜索问题」为退役说法。
- 同日追加（Suda 定）：业务范围再删核心购买需求（填写模板 Suda 已删）、业务目标、营销活动、初始题库规模（确认表模板删对应【示例】行）；业务重要性依据去掉业务目标、营销活动，改以核心可见度问题为准。
- 同日追加（Suda 定）：资料优先级重排为 GSC、Semrush / Ahrefs / Similarweb（有订阅时）、销售记录、客服记录优先提供，Bing Webmaster、GA4 降为有就提供；GSC 只请品牌方按本期市场、按展示次数排序导出两份：非品牌查询（正则不匹配，表达式由我方按别名写好）和 6 个词以上的长查询，不按空格分词的语言只导非品牌。selection-rules 第 1、2 步、signal-sources、client-facing 和《品牌方填写模板》第二部分同步。
- 同日追加（Suda 定）：《品牌方填写模板》第二部分原「平台数据」「数据与资料」两表合成一张，按优先级排（GSC、Semrush 类、销售、客服 → Bing、GA4、Google Ads、站内搜索、服务器日志），开权限级别写进「怎么给」。快照 `.snapshots/biz-scope-slim-20261103/doc.before-merge.xml`。
- 同日追加（Suda 定）：销售、客服两项改名「销售常被问到的问题、成交与流失原因」「客服高频问题」，写明不要原始通话、CRM、工单或聊天记录，由品牌方整理重要或高频问题清单；填写模板与 signal-sources、selection-rules 同步。
- 同日追加（Suda 定）：填写模板删「服务器日志中的 AI 抓取记录」和没有官网时的「产品与公司资料」两行；精简 GSC「已有曝光却没被点击」、Ahrefs Top Pages、Similarweb AI Traffic、客服的退换货与保修原因（只收买前咨询）、GA4 Organic Search 落地页报告、callout 里重复的 Google Ads 提示。GSC 的 Generative AI 报告与 Bing 档位待 Suda 定。示例从虚构的 OxyHome 换成两组脱敏案例（B2B 企业差旅平台 AcmeTrip、B2C 智能宠物用品 AcmePet）。signal-sources 同步。
- 同日追加（Suda 定）：「核心可见度问题」改为品牌方填的「目标人群及使用场景（1–3）」，问「主要面向哪些人群、什么情况下需要、特别关注什么」，第 1 条是本期最想先拿下的；填写模板里原「主要受众」「核心可见度问题」两组合成这一组。我们据此拆出业务范围的主要受众和核心使用场景，第 1 条对应的受众标优先；业务重要性、主题优先级、问题解决点名都改以它为依据。确认表模板对应示例与字段说明同步；monitoring SKILL、单测同步。
- 同日追加（Suda 定「只留有必要的资料」）：填写模板第二部分只留 GSC、Semrush / Ahrefs / Similarweb（有订阅时）、销售常被问到的问题、客服高频问题四项；删 Bing、GA4、Google Ads 搜索词、站内搜索词四行和 GSC 的 Generative AI 报告；没有官网时删 Google 商家资料搜索词，电商平台搜索词报告改为有店铺时优先提供。skill 里这些数据改为「不再向品牌方要，主动给了照常用」。
- 2026-11-04 追加（Suda 定）：Google Ads 搜索词、站内搜索词、Bing Webmaster（含 AI Performance、Topics Portfolio）、GSC Generative AI Performance 改回选填；GSC 改为最近 12 个月、搜索类型 Web、优先用 Non-branded 筛选；填写模板第二部分重写：四列（资料 / 必要性 / 怎么给 / 用途），删「文件或链接」列（内容并进 Semrush 的「怎么给」），提交说明并成一个提示框。改前快照 `.snapshots/biz-scope-slim-20261103/doc.section2-before-rewrite.xml`。
- 2026-11-04 追加（Suda 定）：客服高频问题不再限买前，买后问题由我方筛掉、不进选词。

## 2.13.0（2026-11-03）考核只算发现题，竞品数量按产品线 × 市场

Suda 定，推翻 2026-11-02「替代计入考核」。改前快照 `.snapshots/discovery-only-kpi-20261103-142138/`。

- 发现型可见度只对应发现题；替代题归竞争定位，品牌方选了竞争定位、所在行登记了替代才出，提及率单独报告，不计入考核。删掉「没选竞争定位也可以出 1 到 2 道」。
- validator：`KPI_INTENTS` 只留 Discovery，W59 只数发现题；W52 增查替代题没选竞争定位。测试同步（evals 75/75、单测 68 通过）。
- 同步 output-contract、client-facing、shared 原则第 15 条、geo-monitoring 采集节奏（替代题从每天移到每月专项）；check_skill_terms 登记退役说法，撤掉原来把「只有发现题算」列为退役的条目。
- 竞品数量：每条产品线 × 每个目标市场分别定，默认 3 个主要竞品，上限 5 个（selection-rules 第 1 步、client-facing 竞品行）。售前冻结 3 个竞品的流程不变。
- 对客文案只说提及：`write_prompt_reasons.py` 生成的出题原因去掉「推荐」。飞书《AI 搜索监测确认表（模板）》改了提示词类型字段说明、核心可见度问题和竞品的说明与示例、一条示例出题原因；《品牌方填写模板》改了第一部分导语、竞品行、发现型可见度选项。确认表模板「提示词类型」删掉「验证」选项和对应说明（Suda 点名，模板没有行在用）。改前快照 `.snapshots/client-template-kpi-20261103-143329/`。

## 2.12.0（2026-11-03）按购买任务与增量覆盖选题

Suda 批准规则审查后的修订，并明确验证仅用于零提及时临时点名核查，结果存入题库之外的诊断记录。

- 正式选题依据业务重要性和新增需求覆盖。相对弱势可保留，无法满足硬条件的记录排除依据。预跑正负面表现不决定题目准入。
- Topic 按核心购买任务划分，题数作为容量和覆盖提示，取消强行合并与统计可靠性承诺。
- 旅程阶段与题型分别判断。信源结构仅支持动作假设，取消可改变性低自动降档。
- 验证不进入题库、Base、上传和正式采样，零提及时按需核查，保留回答与证据，不直接归因为站内或站外问题。
- 同步校验、导出、流程验证和相关文档。改前主文件快照见项目 `.snapshots/selection-rules-20261103/main-before/`。

## 2.11.0（2026-11-03）AI 引荐转化进业务重要性

依据：Suda 2026-11-03 读 HubSpot 同一篇「Which prompts should I track to prove business impact?」一节后定「加上」（文章第一类：从已有 AI 引荐流量且能转化的落地页出发选题）。报告侧把主题可见度和对应落地页的引荐会话、转化放在一起看，属 geo-monitoring，本次不动。改前快照 `.snapshots/*.20261103-140034.bak`。

- signal-sources 数据清单 AI 来源流量一行：GA4 设了转化事件的，按落地页附 AI 引荐会话的转化数；用途加「有转化的页面对应的处境写进业务重要性依据」。
- selection-rules 第 5 步业务重要性依据加 AI 引荐转化；和成交数据一样只反映现有客户和页面，业务目标指向新市场新客群时以业务目标为准；引荐量很小（几十次会话以内）的页面只作参考，不单独定档。client-facing-attribute-pool 同步。

## 2.10.0（2026-11-03）成交数据进受众拆分和业务重要性

依据：Suda 2026-11-03 读 HubSpot《Which AI prompts should you track?》后定「加上」（文章用 CRM 成交客户的行业、规模、地区、用途分布定题，按客单、周期、续约给客群分配题量）。改前快照 `.snapshots/selection-rules.md.20261103-131957.bak`、`signal-sources.md.…`、`client-facing-attribute-pool.md.…`、`SKILL.md.…`、`CHANGELOG.md.…`（同一时间戳）。

- signal-sources 数据清单 CRM 一行：B2B 另要近 12 个月成交客户分布（行业、规模、地区、用途；客单、周期、续约给区间或高中低，不要客户名单），用途加受众拆分、优先受众、业务重要性；信源偏差表同一行补「不能用来判断还没进销售流程的买家有多少需求」。
- selection-rules 第 4 步：代标优先受众的依据加成交数据；新增「有成交数据就用来拆」——成交集中在某个规模、行业或用途且候选不同才拆。
- selection-rules 第 5 步业务重要性依据加成交数据；成交数据只反映现有客户，业务目标指向新市场或新客群时以业务目标为准。client-facing-attribute-pool 业务重要性依据同步。

## 2.9.0（2026-11-03）受众切法补全、按行业查漏表

依据：Suda 2026-11-03 读 Peec《How to choose the right prompts for LLM tracking》后同意 B2B 受众加「规模」，并要求按行业一次盘点还缺哪些切法。盘点依据是已有题库实际用过的受众（Zbrand 整机厂和经销商、UNI_A 学生和家长、Hbrand 公民/PR 与外国买家和买租卖、Pbrand 多猫和长时间离家、Bbrand 车型、Sbrand 老旧 PC 和小微商户、Nbrand 散户和链上用户）加 B2B 常用的企业画像维度（规模、行业、技术栈）。改前快照 `.snapshots/selection-rules.md.20261103-123028.bak`、`SKILL.md.…`、`CHANGELOG.md.…`、`client-facing-attribute-pool.md.…`（同一时间戳）。

- selection-rules 第 4 步受众切法表新增三行：买的人和用的人（原「B2B 把决策、使用、付款、风控角色分开」并入这一行）、规模或体量、所在行业或机构性质（B2B）；扩写三行的例子：资格或身份加合格投资者，钱从哪来加奖学金，和标的的关系加转售和装进整机，硬约束加使用对象、要依附的平台或系统、能用的语言。
- 表后加「按行业先查这几种切法」查漏表，七类行业。
- 「不允许」补三种旧题库里出现过的切法：按在用竞品切（要依附的平台不算竞品，归硬约束）、按在意哪条属性切（Pbrand「预算敏感」、Bbrand「关注夜间画质」）、只按地区切；原三条检验末尾的「只是关心某个主题的人群不算受众」并入这里。
- 第 2 步竞品网站结构：品牌自己的官网也看一遍，用来预填主要受众和核心使用场景；表里加「定价页和套餐档位」一行，对应受众的规模或体量。
- client-facing-attribute-pool「受众」说明改为「在用哪家竞品不是受众」，和要依附的平台区分开。

## 2.8.0（2026-11-03）试跑点名品牌数、受众加经验程度切法

依据：Suda 2026-11-03 读 Semrush《How to do prompt research for AI SEO》后定「两处都加」（文章选题看「答案里点名品牌多」的题，人设特征列了经验水平）。改前快照 `.snapshots/selection-rules.md.20261103-120839.bak`、`SKILL.md.…`、`CHANGELOG.md.…`（同一时间戳）。

- 新增 `scripts/trial_brand_count.py`：发现题、替代题按平台数每次答案正文（`de_cite_crawl` 去引用、清商品卡渠道列）点了几个不同品牌，品牌 ＝ 题库 config 本品和竞品 ∪ `--lexicon`，别名匹配用 core `find_alias_spans` / `resolve_alias_spans`；归题、镜像去重、失败页判定复用 `changeability_domains.py`。中位数 ≤1 标「点名品牌少」，人工判原因。
- 实测（阈值 ≤1 由此定）：Hbrand 10-29 改写前题库 × 基线与补跑，标出 9 题，人工看 7 题是解释模式（列区域、房型、市场类型、流程），其中 T2-D04、T1-D19、T6-D02 正是当时人工改写的题，改写后的 T2-D30、T1-D29、T6-D09 都不再被标；另 2 题（T3-D10、T4-D11 的 ChatGPT）答案列的是中文网站，词表没收，属误标。Sbrand US 试跑（ChatGPT ×3）标出 5 题，没有一题是解释模式：US-002、US-014、US-027 题面是单数「Which tool」，AI 只推一个；US-026、US-032 答案点的 AllDup、Windows Network Troubleshooter 等不在临时词表里。因此规则把「点名品牌少」分三种原因，只有解释模式按「两三次同样失败」改写。同一份 Sbrand 数据不给词表、只认题库 config 里 6 家时标出 18/30 题，所以没有词表先挖词表，不直接用脚本结论。
- selection-rules 第 4 步受众切法表加「经验或专业程度」一行（新手和老手能选的候选是否不同；候选一样只是说法更专业的算措辞）；第 8 步「判题是否合格」表后加脚本用法和三种原因；SKILL.md 第 8 步与脚本表同步。

## 2.7.1（2026-11-03）对客确认表加「标签」列

- Suda 定（「加标签」）：模板 Base 提示词库加多选「标签」（fld97oTXD0），两个视图都放在「主题」后面；字段说明写明跨主题切数据用、我方按切片维度填、品牌方不填。改前字段与视图快照 `.snapshots/template-tags-field-20261103-113238/`。
- 新增 `scripts/write_tags.py`：按题库（多市场可多份）用 `tag_dimensions.py` 算标签，按编号写进提示词库，先补字段里缺的选项（多选不会自动建选项，按名字写不存在的值报 not_found），回读核对。在模板示例行用合成题库实测：补选项、写 2 行回读一致、重跑 0 行要改；测完已清空并删掉测试选项。
- 同步：client-facing-attribute-pool 提示词库列与字段说明、selection-rules 第 6 步「切片标签」、SKILL.md 脚本表。已经发出的客户 Base（Hbrand、Sbrand 等）没加这一列。

## 2.7.0（2026-11-03）跨主题切片标签

依据：Suda 2026-11-03 拍板——提示词库划分主题后，有意义、需要跨主题切片分析的方向加对应标签（受众、属性等）；标签和主题不重复，主题按属性切就不写属性标签。改前快照 `.snapshots/tag-dimensions-20261103-112059/`。

- selection-rules 第 6 步新增「切片标签」：维度登记在 `config.tag_dimensions`（受众 / 场景 / 旅程阶段 / 属性 / 自定义），导出时从矩阵行和属性池派生，题上不手写；三条都满足才登记（值落在至少 2 个主题、每值至少 5 道题、写明切完谁用来做什么）；主题的切分轴不做标签；属性只给主推卖点和优势属性；产品线、市场不做标签。第 5 步「矩阵的四个作用」改为指针。
- 新增 `scripts/tag_dimensions.py`，导出脚本和 validator 共用：`export_upload_csv.py` 在类型中文名后接派生标签，不合格的值不出并打印原因；选词新题库不再带出没登记的手写 tags，售前题库和旧题库没写 `tag_dimensions` 时照旧。validator 新增告警 W62（维度或值不合格、和主题重复）、W63（手写标签没登记），只查 `generation_stage: selection`。
- 测试：新增 SliceTagTests 5 例；`goal_bank` 去掉夹具里的手写 tags。走查 `30-选Topic与生词/方案/切片标签走查-20261103/run.sh`：Hbrand 2.1 出「租房者」「公民与 PR 购房者」两个受众标签（各跨 3 个主题），「非 PR 外国购房者」和两条优势属性不出；Sbrand US 出两个受众标签，优势属性每条只在一个主题里，整维不出。
- 同步：output-contract（config 字段、题上 `tags`、上传 CSV、告警表）、SKILL.md 第 6 步、售前 selection-mode 上传列说明；check_skill_terms 登记退役说法「维度带到题上当标签」。

## 2.6.0（2026-11-03）矩阵行登记可出题型

依据：Suda 2026-11-03 拍板（讨论起点是 Aleyda 用旅程阶段把问法类型并进矩阵轴；结论保留两条轴，但矩阵梳理阶段按依据把每行支持的题型登记出来，合理假设也算依据）。改前快照 `.snapshots/selection-rules.md.20261103-110411.bak` 等五份。

- **第 5 步新增「可出题型」**：每行登记能出哪些提示词类型。阶段映射是上限（方案考虑最多发现、替代；购买决策最多对比、评价；需求认知最多问题解决），不被证据放宽——证据指向别的阶段时核对该开哪一行。方案考虑行的发现默认登记；其余类型逐个登记、各带一条依据（买家原话、搜索词、社区帖、销售记录，或写明的「假设：……」），没有依据不登记。假设沿用现行批准路径（出题试跑、品牌方标已批准）。验证题试跑后触发，不登记。
- **第 7 步出题改为「行的登记 ∩ 品牌方本期选的目标」**：目标筛选留在写题阶段不前移；替代、对比、评价的证据检查改为引用行上的登记，写题时不重查；类型表的出题条件同步改写。
- **validator 门禁 60 / 61**：60 查 `slices[].prompt_types` 登记合法（阶段子集、非默认类型带 basis）；61 查题的类型在所属行登记范围内（验证题豁免）。没有 `prompt_types` 键的旧题库不查，不迁移。output-contract `slices` 字段与报错表同步。
- **对客 Base 矩阵表加「可出题型」（多选）「可出题型依据」两字段**：依据一个类型一行「类型：依据」；对比、替代点名竞品的依据从备注移到这里。`check_client_base.py` 同步三条检查（超阶段上限、登记缺依据行、挂题类型未登记），没有该字段的旧 Base 不查。
- 回放验证：Sbrand US 与 Hbrand 选词 2.1 两个真实题库跑 validator，新门禁零触发零误报；构造题库五场景（合法登记、超上限、缺依据、未登记、旧题库无键）行为全部符合预期。既有单测 63 过 62：`test_gate_decision_covers_the_whole_class` 的失败是 2.5.0 加 W59 后样本没补处理记录，与本版无关。

## 2.5.0（2026-11-03）主题单一主轴与题数下限

依据：Suda 2026-11-03 拍板（Hbrand 2.1 与 Sbrand US 两个题库逐题复盘：Hbrand 6 主题混用受众 / 标的 / 管道三条轴，T-A 的整租题和 T-B 互相渗透，T-D/E/F 只有 2–3 题；Sbrand T-AV 16 题混了选购和故障修复两类任务）。改前快照 `.snapshots/topic-axis-20261103/`。

- **单一主轴**：删除「各主题不必按同一种维度分」，改为同一条产品线的主题用同一条主轴切、不混轴；主轴 ＝ 品牌方按什么单元赚钱或交付 × 买家把什么说成一件事，常见形态：候选池会分裂的品类按决策任务切、平台型按交易类型切、B2B 服务按服务线切；受众、场景、预算、语言降为主题内差异。一句话检验补平台型例外：各主题候选同为一批门户时改问「品牌方会不会为它单独付费」。
- **题数下限**（推翻 2026-10-30「主题不设题数底线」）：每主题至少 5 道考核题（发现＋替代）且来自至少 4 个不同购买决策，不足并进同主轴的相近主题；品牌方点名单买走 `warning_decisions` 放行并写明读数波动风险。validator 新增告警 W59（只查 `generation_stage: selection`，验证题、停测题不计，决策近似为 attribute_ref × constraints），`topic_checks` 加 stage 参数；evals 锁版样本补 q5 至 5 道考核题，新增触发、放行两例（73/73 通过）。
- 同步：SKILL.md 第 6 步、selection-rules 第 6 步（主题是什么 / 怎么聚 / 硬要求第 3 条）、output-contract 告警表、shared/prompt-generation-principles.md 选词顺序；check_skill_terms 登记退役说法「主题不设题数底线」「各主题不必按同一种维度分」（0 命中）。

## 2.4.1（2026-11-03）竞品网站结构查漏

- Suda 定（Hbrand 对照 RivalH1 攻略分类时提出）：第 2 步加「竞品网站结构」，选 2–3 家竞品看导航、筛选项、落地页、博客与攻略分类、对比替代页、帮助中心，逐项补到场景、受众、属性、需求认知行或主题查漏；只当线索、要找买家信号，博客分类不照搬成主题；对照记在题库 notes，不进对客表。第 6 步聚完主题后用它查漏。signal-sources「竞品官网」一行改为指向这一节。

## 2.4.0（2026-11-02）审核清单修订：开行口径、验证题触发、目标进题库、去重

依据：Suda 2026-11-02 审核清单拍板（`30-选Topic与生词/方案/选词skill审核优化清单_20261102.md` 的 A、B、C、E 组；D 组还在讨论，本版不动）。改前快照 `.snapshots/selection-builder-pre-2.4.0-20261102-184628/`。

A 组（矛盾）
- A1 矩阵开行：每个核心受众 × 核心使用场景 × 三段旅程阶段都过一遍，买家确实会在这个处境问 AI 的组合就开行，有证据写证据、没证据标「假设」；组合本身不成立的才不开，原因记内部。删掉「只开值得测的行」「有买家证据的阶段才开行」「没有证据的阶段不开」；阶段表「开行要的证据」改名「依据举例」；「证据不进档位」改为证据只决定写什么依据、标不标假设。SKILL.md 第 5 步、对客表矩阵节、售前 selection-mode 第 6 步、shared 原则第 11 条同步。
- A2、A3 验证题：写题时不出，只在试跑后按第 8 步两个条件触发（零提及诊断：合格发现题全平台全部试跑 0 提及、行为高或中、属性为优势或持平，同属性只补 1 道；事实说错：只在选了品牌呈现时，AI 把高、中行属性的品牌关键事实说错、说漏或和同名公司混淆）。不占名额、不进考核，触发后单独各跑 3 次。第 1 步目标表、第 7 步类型表、SKILL.md、对客表业务范围、shared 原则第 15 条只留指针；品牌呈现从第 1 步证据表移出，答错例子先记品牌事实核查。第 8 步开头改为品类认知不进试跑、验证题不进候选题试跑批次。
- A4 GSC 和 Bing Webmaster 从「必须提供」改为「优先提供（默认品牌方导出，取最长历史）」：selection-rules、signal-sources、对客表。不加 validator 降级逻辑。
- A5 矩阵行统一为五维：产品线 × 市场 × 受众 × 场景 × 旅程阶段（SKILL.md、selection-rules、对客表、shared 选词顺序、售前 selection-mode）；切片稳定键改为「产品线|市场|受众|场景|旅程阶段」；output-contract `slices` 加 `market`（单市场可省）。scripts/ 里没有按「受众|场景|旅程阶段」拼键的代码，`diff_base_against_spec.py` 用切片编号做主键，不用改。
- A6 shared/prompt-generation-principles.md 交接一节的「每张表都有客户确认列」改为指针：确认方式见对客表通用规则。

B 组（逻辑链断点）
- B1 第 1 步证据表前加一句：判断在第 2 步调研预跑完成后落定，第 1 步只收目标、先后、关心的问法和核心可见度问题。
- B2 题库 `config.business_goals`（`selected` 按先后排，`information_named`）；validator 新增告警 49（selection 新题库没写或写错）、50（选了竞争定位但没有对比题）、51（选了声誉与信任但没有评价题）、52（有对比、评价、问题解决题但对应目标没选；替代题不查）。没有 `generation_stage` 的旧题库和带 `extra_prompt_types` 的售前题库不查。测试各加触发和不触发样本，`evals/verify_workflow.py` 的 selection 样本补 `business_goals`、加两例。
- B3 selection-rules 交付、output-contract 上传 CSV 节加：交付说明要告诉品牌方替代题（和问题解决题）读数现在只在基线 HTML 报告里。
- B4 问题解决题：品牌方点名并且有需求认知行才出，每个主题最多 2 道，占正式名额，读引用，不导出上传 CSV、读数只在基线 HTML 报告里；第 1 步名额句、第 9 步同步。
- B5 selection-rules 第 2 步的原话字段改指针；对客表买家原话节给「证据可信度」补定义（`write_prompt_reasons.py` 用它挑代表原话，不删列）。

C 组（去重）
- C1 第 7 步类型表是题型出题条件和数量的唯一完整定义；第 1 步目标表只留目标 → 类型 → 什么时候出；专项题不设总数上限移到第 7 步；SKILL.md 第 7 步压成一句加指针。
- C2 selection-rules 内考核口径只在第 1 步定义，第 6、7 步改指针。
- C3 对客表旅程阶段表只留例句和指针、主题命名改指针；「韩国用 Naver」只在 selection-rules 第 6 节定义，对客表、signal-sources GSC 节改指针（signal-sources 关键词工具一行的 Naver 取量方法保留）。
- C4 community-channels 第 1 条改为指针，Google 地图行的价格数字删掉，单价只在 signal-sources。

E 组（小错漏）
- E1 SKILL.md 脚本表 `write_prompt_reasons.py` 补 `--noun <品类名词>`。
- E2 output-contract 告警「措辞高度相似」改编号 8b（validator 和测试都不引用这个编号）。
- E3 预跑题模板后补一句：非英语市场用市场语言写。
- E4 output-contract 人工检查加：对比题的条件里要有使用场景，光有预算不算。
- E5 上传 CSV 后三列留空的原因：本地 `build_report_data.py` 不读这三列，`geo-presales-report-editor` core 只在旧格式题库 JSON 里读；线上后端是否读未确认，确认前留空（output-contract 与 `export_upload_csv.py` 说明同步）。

退役扫描：`check_skill_terms.py` 新增 GSC / Bing「必须提供」、「只开值得测的行」、「有买家证据的阶段才开行」等开行门槛说法、「开行要的证据」、第 7 步按品牌呈现写验证题的旧说法、旧零提及条件、「品牌方要几道出几道」、「告警 8」；改了几条旧规则的替换说明。

待办：后端加 `alternatives` 枚举（替代题现在按 competitor 上传，线上报告看不到替代题提及率）；上线后同步 `export_upload_csv.py` 的 INTENT / QUESTION_TYPES、validator 的 `V8_CSV_QUESTION_TYPES` 和 `shared/canonical-intent-mapping.md`。

### D 组与收口（同日，版本号不变）

改前快照 `.snapshots/selection-builder-pre-2.4.0-D-20261102-190459/`。

- D1「本期不出」分两种理由，都写在业务重要性依据末尾（格式「依据……。本期不出：……」），不写备注：没选对应目标写「本期不出：品牌方未选竞争定位；选了可在此行出对比题（有证据的竞品：X、Y）」，业务重要性低写「本期不出：业务重要性低，原因……」。selection-rules 第 5 节业务重要性表与「目标不进档位」、对客表矩阵节（含「备注」不再写本期不出原因）、output-contract `slices` 同步。对客表矩阵写明两个视图：默认「本期出题」筛主题不为空，「完整矩阵」显示全部行，都按业务重要性、再按切片编号排序（模板 Base 已由主会话在飞书改好）。`check_client_base.py` 扩到低档行：业务重要性为低的行依据里没有「本期不出」就报；`verify_workflow.py` 的对客表样例加低档行两例。
- D3 没写 `config.audience_terms` 时，告警 39 不再出，改为 output-contract 人工检查一条；写了时照原样跑。validator、测试、`verify_workflow.py`（原「audience_terms_missing_warns」改为「audience_terms_missing_is_manual_check」）同步。
- D4 对客表买家原话：受众、旅程阶段两列只在这条原话被用作矩阵行依据或代表原话时才填，空着不算欠账。validator 和 `check_client_base.py` 都不查这两列，只改文字。
- D5 每条告警以稳定编号开头（`[W7]` `[W8b]` `[W32]`–`[W58]`），原来没编号的分到 W53（题没有所在行）、W54（无条件发现题）、W55（手动改档没写理由）、W56（审核状态缺）、W57（属性只被未批准的题承载）、W58（旧题库结构），锁版前的缺字段、旧阶段名记 W33、W7。`warning_decisions` 新增 `{gate: "W39", decision}` 一条覆盖整类，原 `match` 子串写法照用。output-contract 告警表改成带 W 编号并写明两种写法；测试加「每条告警都带编号」「按编号覆盖整类」两例；`verify_workflow.py` 的告警断言改为接受编号前缀，测试里两处按「WARNING: q…」拼的断言同步；`e2e_presales_gates.py` 没有按告警原文匹配的断言，不用改。
- D2 登记 `scripts/changeability_domains.py`（另一子代理新建，代码未改）：SKILL.md 脚本表加一行，selection-rules 第 8 步「可改变性」加用法：按被引次数占比判档，官网加社区 ≥60% 记高、≤40% 记低，其余记中；「需人工」标记的题和竞品官网域名清单要人工复核。
- Suda 定：假设行上的题品牌方批准即可进正式题。selection-rules 第 5 节补规则（出题原因写「假设：……」，品牌方标已批准即确认处境存在），第 9 步加指针；SKILL.md「边界」的整份假设题集一条保留，补半句区分单个假设行。validator 不改。
- 收口：output-contract 人工检查「矩阵和题双向对得上」改为高、中的方案考虑行都有题，需求认知、购买决策行本期不出的写「本期不出：……」；售前 selection-mode 第 7 步月搜索量改指针、第 9 步删「发现型过半」（`check_presales_bank.py` 已无此项）；对客表「主题优先级」改指针。
- 退役扫描新增：备注写本期不出原因、无编号的「—」告警行、「发现型过半」、「（Google；韩国用 Naver」、「config.audience_terms missing」。

## 2.3.3（2026-11-02）搜索数据种子词加竞品名和本品名

- Suda 定（读 AlsoAsked《AI Visibility: Find the right queries to track》后）：signal-sources 搜索数据行的种子词，除品类词和相邻词外，每个竞品加 `<竞品名> alternative`、本品加 `<本品名>`。原因：替代题要买家在考虑或想换掉某竞品的证据，品牌自己的 GSC 里竞品词很少，DataForSEO 余额也已用完。
- 依据是已有缓存（没有新付费调用）：Hbrand、Nbrand、Obrand 7 个品牌名种子词只有 Nansen AI 出了 PAA（4 条），但相关搜索和自动补全给出了「RivalH1 alternative reddit」「alternative to rivalh1」「Is Nansen AI legit」「Nansen AI review」，RivalH1 那条还带出了 SRX、PropNex、RivalH2 这批买家拿来比的平台。
- 同篇文章里的「PAA 批量用模型先分类」本次未加：10-30 删掉的打标脚本每份数据只标出 0–8 个无关词，Hbrand 一份 SERP 产物 177 行，人工逐条判断的成本不高。单批超过几百行（GSC 全量导出、多种子词 `--paa-depth 2`）时再议。

## 2.3.2（2026-11-02）主题表删「依据与说明」

- Suda 定：主题表的「依据与说明」和「主题优先级依据」重复，只留后者；需求证据、代表搜索词和量、停测原因都写进主题优先级依据。selection-rules 第 6 步删掉「依据与说明里写一句买家要完成什么」，主题名本身要让人一看就懂。
- 退役扫描加「依据与说明」。模板 Base 的主题表已经没有这个字段；Hbrand 确认表的这个字段已删（Suda 确认，删前快照 `.snapshots/topic-desc-field-delete-20261102-190013/`）。

## 2.3.1（2026-11-02）对客表放完整矩阵

- Suda 定（Sbrand Security 美国选词时）：需求认知、购买决策行本期不出题的，也写进对客确认表，品牌方看到完整矩阵和每行本期不出的原因；推翻 2.3.0 的「只留在内部矩阵、不写进对客表」。题库 JSON 不变：这些行仍不带 `topic_id`、不进主题，`priority_basis` 末尾写「本期不出：……」。
- selection-rules 第 5 步、对客表「旅程阶段」、output-contract `slices`、SKILL.md 第 7 步同步；模板 Base 提示词矩阵「旅程阶段」「业务重要性」字段说明同步。
- `check_client_base.py`：不再把没挂题的需求认知、购买决策行（高、中）报成问题，改为查它的业务重要性依据里有没有「本期不出」；`evals/verify_workflow.py` 加一例；`check_skill_terms.py` 加退役说法「只留在内部题库 / 不写进对客表」。
- 售前生词同步（Suda 定，geo-presales-prompt-builder 6.3.1）：selection-mode 第 6 步改为「售前报告只按题统计、不展示矩阵；售后选词接手时这些行随完整矩阵写进对客确认表」；`e2e_presales_gates.py` 样本改名「没点名的阶段行留在矩阵里、本期不出题」。旧流程的 `export_to_confirm_base.py`（矩阵按主题 × 属性生成、不读 `config.slices`）没改。

## 2.3.0（2026-11-02）矩阵全面梳理，选词按目标筛

- Suda 定：「最优先的问题」「问题例子」不单设——目标那一行按重要性排先后、最在意的写最前；见过 AI 答错的例子并进「品牌方关心的问法」。selection-rules 第 1 步与证据表、对客业务范围、飞书填写模板同步；售前 Case 由「选词skill残留清理」会话同步。
- Suda 定：模板删掉使用说明文档（快照 `.snapshots/usage-doc-slim-20261102-172122/`），各列怎么读只靠字段说明；Suda 另手动删了矩阵「目标题数」「覆盖情况」、主题「计划题数」等字段。
- Suda 定：属性池和提示词矩阵全面梳理，覆盖不同购买阶段、需求和决策约束，避免漏掉重要机会；选词层按目标筛，只对当前监测目标相关的高价值主题出候选题，不按阶段或题型配额。推翻 2.2.0 的「购买决策行默认不开」。
- 第 5 步：每个核心使用场景三段都查，有买家证据就开行，不看品牌方选了哪些目标；三段各自的开行证据写进阶段表。需求认知、购买决策行照常判业务重要性。
- 品牌方没选的目标默认不出正式题，也不给品牌方看：对应的行只留在题库 JSON 的 `config.slices`（不带 `topic_id`，依据末尾写「本期不出：……」），不进主题、不写进对客确认表；下期加了目标直接在这些行上出题。
- 评价题从「每个主题 1 道」改为只在有可信度证据的主题出、每个主题最多 1 道。
- validator 告警 48 只查方案考虑行；`check_client_base.py` 新增：对客表里没挂题的需求认知、购买决策行（高、中）报出来；e2e 新增「目标未选的购买决策行不告警」一例。
- 「点名问题解决」口径（Suda 定）：品牌方自己写的核心可见度问题或问题例子里有问题型诉求就算；我方代填的要品牌方确认后才算；搜索词、社区帖里的问题型说法只用来开需求认知行。Hbrand 核心可见度问题（1）「怎么避开租房诈骗」是我方代填，不算。
- 售前生词同步（geo-presales-prompt-builder 6.3.0，`selection-mode.md` 第 6、7 步）：三段都查、有公开证据就开行；售前不出问题解决题，需求认知行都不出题，购买决策行只在 `extra_prompt_types` 点名又有证据时出；不出题的行留在 `config.slices`，不进报告和对客表，留给售后选词接手。`e2e_presales_gates.py` 加一例通过样本。

## 2.2.3（2026-11-02）删转化路径，目标多选改写，受众拆成受众与购买需求

- Suda 定：业务范围不再收「转化路径」，它对生词没有作用；品牌在转化渠道能编辑的页面在判可改变性时仍算官网（selection-rules → 可改变性）。
- 不加购后阶段：买完之后的问题本来就不进选词范围。
- 目标多选题改成「标签＋一句说明」：发现型可见度、竞争定位、品牌呈现、声誉与信任；问题解决题不进选项，仍是品牌方点名才出；表单上不标默认项、不写「暂不提供」，发现题仍照常默认出。
- 第 1 步重写（「选词skill残留清理」会话按 Suda 确认）：目标表、需求收集问法、出不出专项题的证据表（买家在问且 AI 答得有问题才出）；第 7 步类型表改为替代每个有证据的竞品 1 道、对比 / 评价 / 验证按第 1 步判断；对客业务范围加「希望解决的 AI 搜索问题」「最优先的问题」「问题例子」三行。
- 两边措辞对齐：目标题不预选、不叫「勾选」，发现题仍默认出；GSC / Bing「必须提供（默认导出）」。
- 声誉与信任开放（Suda）：品牌方选了、并且买家在问可信度才出评价题；专项题不设总数上限。售前同步：Case 加「希望解决的问题」「最优先的问题」「问题例子」三项（售前生词 6.2.0、Case Builder 1.14.0，飞书 Case 评测集表加三列），选了竞争定位、声誉与信任时 `options.extra_prompt_types` 自动推出 `Competitor`、`Evaluation`；品牌呈现售前只记录。
- 填写模板的「受众：任务」拆成「目标受众」（主要购买者或决策者）和「核心购买需求」（受众最关注的问题、使用场景和购买标准），后者作为属性池和核心使用场景的候选。

## 2.2.2（2026-11-02）模板删数据表，提示词库按主题分组按优先级排

- Suda 定：品牌方要填的业务信息、数据和平台权限统一用飞书《AI 搜索监测｜品牌方填写模板：业务范围与资料清单》收，模板 Base 删「需要品牌方提供的数据」表（快照 `.snapshots/template-brand-data-table-20261102-161455/`），使用说明删「业务范围与内部数据」「平台权限」两节、开头链到填写模板、后面各节重新编号。业务范围表保留。
- 提示词库「表格」「正式监测」两个视图按主题分组、组内按提示词优先级再按编号排。
- 平台数据改为导出为主：目前客户都是导出文件、没人开权限，GSC / Bing / GA4 默认品牌方导出上传，愿意开权限的再开；飞书填写模板「平台权限」一节同步改名「平台数据」。

## 2.2.1（2026-11-02）替代题要买家原话证据；售前统一

- 替代题按需出：买家原话表里有在用、在考虑或想换掉这个竞品的说法才写。
- 售前生词（6.1.0）与选词统一：默认只出发现题；Case 的 `options.extra_prompt_types` 点名 `Competitor` / `Evaluation` 才出；`check_presales_bank.py` 删「发现型过半」，改查题型是否被点名。报告的竞品胜率只读对比题，不出时为空；情感照常从发现题统计。

## 2.2.0（2026-11-02）目标四类，默认只出发现题

- 品牌方目标归四类：发现型可见度（发现）、竞争定位（替代、对比）、品牌呈现监测（验证）、声誉 / 信任监测（评价）。默认只做发现型可见度；替代有证据才出；对比、评价、问题解决品牌方要才出；声誉监测暂不做。考核只认题型：发现＋替代。
- 对比题从「有证据就出」改为品牌方要才出；B2B 软件、消费电子、汽车、工业设备这类买家常拿具名品牌直接比的行业，在业务范围里建议品牌方加。购买决策行默认不开。
- 删除「交易场景发现题」：发现题只放方案考虑行（validator 同步）；「在哪买、价格、库存」不进选词题库，点名本品问在哪买的记进品牌事实核查；本地服务和门店的「找哪家」照常是发现题。
- 回归：77 份题库只有 4 份 2.1.0 走查样本多出阶段报错，真实客户题库错误数不变。

## 2.1.4（2026-11-02）目标两类与本地服务

- 品牌方目标归两类：可见度（发现、替代，计入考核）和品牌表现（对比、评价、验证，不单独售卖、不计入考核），以题面点不点名本品为界。
- 交易场景看答案是否随价格、优惠、库存变（不限实物商品）；本地服务和门店类品牌的「找哪家、在哪做」放方案考虑行写发现题，计入考核；本地题面可以写城市，「near me」写成具体城市并把采集代理设在同地。

## 2.1.3（2026-11-02）逻辑链断点修补

- 主题优先级「中」的搜索量：Google 月搜索量，韩国用 Naver（2.1.1 只写 Google，会把韩国主题压到低）。
- validator 新增告警 48：业务重要性为高、中的行没有题；人工检查同步改为高、中。
- 待确认的补判材料改为调研预跑的评价答案和试跑里发现题、对比题的答案（原写法依赖默认不出的评价题）。
- 选正式题拆成两步：主题优先级只建议买哪些主题；主题内按提示词优先级 → 类型 → 优势在前挑题。
- 交易场景发现题读提及率，但不计入主题考核，报告里单独列（答案随促销和库存波动）。

## 2.1.2（2026-11-02）主题命名放宽

- 主题名不再固定「需求 ＋ 品类」格式，只管三件事：一看就懂是哪一类购买需求；不以单个属性或卖点命名、不带品牌；同产品线的主题彼此分得开。「依据与说明」去掉必须以「帮我」开头，保留一句话写买家要完成什么。

## 2.1.1（2026-11-02）GSC 怎么用

- GSC、Bing 查询词和 Google Ads 搜索词研究阶段全收，不先剔除品牌词；按本品牌词、竞品词、非品牌查询分开用（signal-sources.md → GSC 与搜索词报告怎么用）。依据：外部做法对照（Similarweb 去品牌后聚类、Aleyda 访谈多来源交叉）和 某安全软件近 6 个月 GSC 实测：品牌词占展示 67%，非品牌 10 个词以上只有 5 条，竞品词 0 条。
- 长查询按 6 个词以上筛（只为把长尾从导出上限里取出来，不另成一类），不用 10 个词；不按空格分词的语言改用疑问词和字符长度。
- 界面导出上限 1000 行，先在 GSC 里用正则分类筛再导出，超出走 API。
- 主题优先级「中」以父关键词的 Google 月搜索量为准，GSC 展示取决于官网排名，只作补充。
- GSC 和搜索词报告里的竞品词可以作为开购买决策行的证据。

## 2.1.0（2026-11-02）阶段、类型与优先级理顺

依据：`30-选Topic与生词/方案/选词skill2.0盘点修改清单_20261102.md`（Suda 逐条定）。

- 旅程阶段从八段简化为三段：需求认知 / 方案考虑 / 购买决策；不设购后，买家买完之后的问题不进选词。旧题库八段照认、按表换算。
- 阶段和提示词类型仍是两条轴；允许组合缩成三行：需求认知只放问题解决，方案考虑放发现、替代，购买决策放对比、评价、交易场景的发现题。验证题挂在触发它的发现题所在行，不查组合。
- 替代题计入提及率考核（推翻 10-23「未定」）；考核题 ＝ 发现 ＋ 替代。核心 / 实验 / 监测三层取消，`group_role` 只在旧题库查。
- 评价、问题解决、交易场景题默认不出，品牌方要才出；准确性题不进选词题库，AI 说错的事实记进品牌事实核查。
- 出几道只看决策差异：取消「中档行只出 1 道」（删告警 45）；发现按属性，对比按有证据的竞品，替代每主题最多 1 道，评价 1 道。新增题量告警：单产品线 × 单市场候选题不在 30–60 道。
- 三个优先级改名：矩阵「业务重要性」、主题表「主题优先级」、提示词库「提示词优先级」；题库 JSON 键不变。
- 门禁 41 改为每个主题至少一道方案考虑行上的发现题；删告警 40（发现不到一半）；门禁 31 只要求优势属性没题时写原因；`generation_stage` 不再区分 discovery / diagnostic。

## 2.0.0（2026-11-01）逻辑链重整与精简

依据：`30-选Topic与生词/生词规则与工作流/选词逻辑链梳理_讨论稿_20261030.md`（定稿）和 `30-选Topic与生词/方案/选词skill输出物精简清单_20261031.md`。

- 新增「核心使用场景」：每类受众只列有证据、品牌在竞争的场景，落在业务范围，和受众一起确认；矩阵一行改为受众 × 场景 × 旅程阶段。
- 行优先级只看业务重要性，档位改名高 / 中 / 低；证据只决定开不开行，相对竞品、可改变性、待确认都不进档位。中档行出 1 道，低档行不出。
- 主题 ＝ 一类核心购买需求（决策任务），按「买家会不会说成同一件事」聚合；商业化原则：能独立交付才单开；不数题，数不同的购买决策。硬要求：每题只归一个主题、没有空主题、每个主题至少一道发现题。
- 恢复主题优先级（推翻 10-30 的删除）：高 ＝ 有高档行，中 ＝ 有搜索需求，低 ＝ 都弱，同档按搜索量排。
- 属性池加「常见约束」「品牌取值」；写题前相对竞品只确认劣势和优势；劣势属性可以挂在行上、写题时剔除；不标「品牌自述」。
- 题不逐条挂买家原话，条件取自常见约束；评价题有必要才出；对比、替代行开行时写明竞品和依据；可改变性只在试跑后判。
- 删除：矩阵「目标题数」「覆盖情况」，主题「计划题数」「可改变性低占比」，属性池「属性编号」，提示词库「库分层」「看什么指标」「AI 认知差距」「优化顺序」；题库 JSON 每道题精简到常驻字段；五列 CSV 和 validator 的 CSV 参数；`check_matrix_coverage.py`、`build_baseline_html.py` 软链、`deep-research-brief.md`；人工检查 21 条删到 7 条。
- after-sales-rules.md 和 representative-library.md 合并为 selection-rules.md，按 9 步分节；aleyda-21-step-mapping.md、peec-geobubbles-ahrefs-mapping.md 移到 `30-选Topic与生词/方案/外部方法对照/`。
- validator：每条告警可写处理记录（`config.warning_decisions`），只有公开数据或假设级证据时最高 Usable；新增主题门禁（空主题、主题无发现题、主题优先级依据）、劣势属性出题报错、中档行多题告警；条件可由属性的常见约束支撑。

## 2.0.0 之前的主要节点

- 10-30：出题与题面条件综合判断（门禁 36 改告警）；受众由品牌方先给；验证题按试跑读数写；主题不设题数底线；主题优先级删除（11-01 恢复）。
- 10-29：调研预跑先爬再调研；不写宽泛品类题；评价题默认买家问法；问题解决默认不出；提示词不限句式。
- 10-28：属性池只判相对竞品；优先级只在矩阵行判；主题从矩阵行聚；可改变性按试跑前 20 个被引域名判。
- 10-23：候选基线取消，改为各平台试跑 3 次＋正式基线每格 30 次；考核口径锁定；正式监测 2–4 周后复查一次。
- 10-22：售后生词改名选词；拆出监测 skill；提示词类型取代意图；替代题从对比题拆出。
