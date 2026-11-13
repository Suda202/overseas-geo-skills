## 3.15.1（2026-11-13）情感判读并进 geo-metrics

触发依据：Suda 2026-11-13「geo-presales-sentiment-judge 是不是应该放到 geo-metrics 里」「并进去吧，反正都是指标统计」。

- `geo-presales-sentiment-judge` 退役：`sentiment_sentences.py` 进 `geo-metrics/scripts/`，Claim 层契约、判读规则、品类联合分析进 `geo-metrics/references/`，原 SKILL 正文改成 `geo-metrics/references/sentiment.md`，单元测试进 `geo-metrics/tests/test_sentiment.py`。
- 本 skill 跟着改：SKILL.md「边界」的情感规则指向 `geo-metrics`；`check_skill_terms.py` 把旧 skill 名列为退役说法。其他 skill（pipeline、report-builder 的 `run_pipeline.py`、`attach_sentiment.py`、report-audit、geo-monitoring 基线报告、shared 意图映射）同步改路径和说法。

## 3.15.0（2026-11-13）线上部署包：bundle 子命令，缺文件启动即停

触发依据：Suda 2026-11-13「线上售前诊断报告只用 geo-prompt-selection-builder 这个 skill」「按推荐做打包命令」。

- `run_selection_mode.py bundle --out <新目录>`：按 `SKILL_DIRS` + `PARTIAL_COPIES` 把选词、`shared`、研究预跑要的 geo-monitoring 采集程序、采集检查、平台合同和 geo-metrics `geo_presales_core` 拷成一个目录，结构和仓库一样，写 `BUNDLE.json`（选词版本、内容、文件数）；排除快照、缓存、本机配置和 Base 导出，保留 evals 供部署后验收。源文件仍各归各的 skill，不在选词里放副本。
- run / prepare 启动时先核对这些文件，缺一个就退出码 2，`result.json` 写 `missing_skill_files` 和缺的路径，不拷 skill、不启动 agent；原来缺文件会被静默跳过，到研究预跑才报找不到。
- runner-ops.md 部署清单改成「部署 bundle 打出来的目录」；验收加 `evals/e2e_bundle.py`；SKILL.md 脚本表和维护说明同步。
- `e2e_input_contract.py` 写报告前先建 `reports/`：公开仓库不带这个目录，新克隆里第一个跑它时会报找不到目录。
- 回归：新增 `e2e_bundle.py` 7/7（打包内容、不带快照缓存和 Base 导出、不覆盖已有目录、从包里 prepare 后采集程序 dry-run、包里跑返修循环 e2e、缺 geo-monitoring 或 shared 启动即停）；包里跑 test_validate 56 passed、verify_workflow 62/62、e2e_input_contract 42/42、e2e_repair_loop 11/11、e2e_review_loop 14/14。

## 3.14.4（2026-11-12）采集程序和采集检查并进 geo-monitoring

触发依据：Suda 2026-11-12「geo-presales-crawl-integrity 是不是应该放到 geo-monitoring 里才对」「并进去」。

- `collect_answers.py` 从 `geo-presales-report-builder/scripts/` 移到 `geo-monitoring/scripts/`；`geo-presales-crawl-integrity` 退役，脚本 `audit_crawl_integrity.py` 进 `geo-monitoring/scripts/`，平台字段合同、数据分层契约、缺陷目录进 `geo-monitoring/references/`，原 SKILL.md 正文改成 `geo-monitoring/references/crawl-integrity.md`。
- 本 skill 跟着改：`run_selection_mode.py` 的 `PARTIAL_COPIES` 改拷 geo-monitoring 的采集程序、检查脚本和平台合同（不再拷 report-builder 的整个 `scripts/`），TASK 里研究预跑命令换路径；selection-rules.md、online-runner.md、client-facing-base.md 的采集路径；runner-ops.md 部署清单写明要带哪些文件；`e2e_gateway.py` 换路径。**研发部署线上选词时要同步换成新路径。**
- 其他 skill 同步：pipeline、report-builder（`run_pipeline.py` 从 geo-monitoring 调采集和检查）、report-audit、geo-metrics 的 SKILL.md 与 references，shared 的 `render_crawl_audit_report.py`、`skill-layout-conventions.md`。改前快照 `.agents/skills/.snapshots/migrate-collect-20261112-190006/`，旧文件在废纸篓 `migrate-collect-20261112/`。
- 回归：check_skill_terms 无命中；test_validate 56 passed；verify_workflow 62/62；e2e_input_contract 42/42、e2e_repair_loop 11/11、e2e_review_loop 14/14；按 `PARTIAL_COPIES` 拷出的工作目录里 `collect_answers.py --dry-run` 正常；某制氧机客户 collect_us_r2 上新旧 `audit_crawl_integrity.py` 输出逐键一致，`collect_answers.py --check-only` 45/45，`run_pipeline.py` 跑过采集检查、采集校验、词表、数据生成，停在译文暂停点；report-builder、report-audit、report-editor、sentiment-judge 单元测试通过。`e2e_gateway.py`（付费）没跑。

## 3.14.3（2026-11-12）第二轮审核 R1–R20：试跑后回写归选词；语言不设白名单；门禁 12 认品牌别名

触发依据：Suda 2026-11-12 第二轮审核回复：「R1 线下 agent 对话的时候支持开就行了，线上目前默认是不开的」「线上录入什么语言就以线上选择什么语言为准，我们不用管」「对客表不加本期目标」「R4 归选词做『试跑后回写』一步」「其他的按照你的修」。清单在 `docs/exec-plans/active/selection-skill-audit-20261112-progress.md`「第二轮审核」。

- **R1 目标开放**：selection-rules.md 第 1 步写明本地对话里定了开哪些目标就写进 `config.business_goals`，不需要品牌方在资料或对客表里填；线上不开。对客表不加「本期目标」行。
- **R19 语言**：`normalize_case.py` 去掉语言白名单，表单选什么语言就用什么，题面语种由门禁 32 查；删掉只当白名单用的 `references/locale-templates.json`（快照在 `.snapshots/audit-R2-20261112-175100/`）。e2e_input_contract 改为「法语、日语照收」，42/42。
- **R4 试跑后回写**：selection-rules.md 第 8 步新增「试跑后回写」：改或删问法有问题的题、竞品不足 3 个时补到 3 个（上限 5）、商品卡「试跑后定」按 5% 定开关、按答案复核主题、补约束条件和品牌事实核查。第 1 步竞品和商品卡、SKILL.md、client-facing-base.md 指过去；baseline-report.md 写明报告模板固定 3 个竞品位、题库最多 5 个。
- **R2 门禁 12**：`entity_terms` 读 `config.brand_aliases`（normalize_case 的输出）、旧键 `aliases` 和 `case_fields` 里的「品牌别名 n」；output-contract.md 加 `brand_aliases` 字段，online-runner.md 要求照抄。
- **R3 需求信号键**：output-contract.md、online-runner.md 的 `buyer_quotes` 加 `来源类型`、`出处`，和 runner 的 TASK、登记检查一致。
- **R5 就绪结论**：`first_party_data` 不是 true（含没写）就封顶 Usable；结论文字只写「Ready」，去掉「lifecycle stage」。
- **R6 主题优先级**：主题缺 `priority` 由跳过改为报错（门禁 43）；测试夹具补主题优先级。
- **R7–R13 说法对齐**：demand-side-signals.md 的相对竞品判法和 Usable 出处；shared/prompt-generation-principles.md 的低档、题量、选词顺序整段（去掉锁版、停测、版本说法）；SKILL.md 第 1、5 步不再写「目前只做发现」；第 7 步拆题与第 6 步拆主题的分工（个别品牌进出名单不拆题，候选类别或竞争格局整体变了是拆主题的事）；canonical-intent-mapping.md 的验证（本地选了声誉与信任才出）、准确性（不出题）、上传值出处；问题解决题面不写品牌；「只开一行」的判定键加约束条件，和 `check_client_base.py` 一致。
- **R14–R18、R20 残留与断链**：总纲第 5 条和阶段表删掉选正式题、正式基线、持续监测三行，试跑行改为试跑后回写；去掉「混合选择」一词；题 `status` 不再列「停测」；check_client_base.py 注释、review-rubric.md 两处链接、W54 提示、input-contract.md 的 `brand_object_type` 改正；`diff_base_against_spec.py` 默认主键加约束条件表、删三张退役表；runner PLAN 找 App ID 不再用 `site:`；切片标签计数排除不上传的问题解决、验证、交易、售后；online-runner.md 写明补题在审核之前、审核删题后不再补。
- `check_skill_terms.py` 加这一轮的退役说法；旧的「selection-rules 第 8、9 步」扫描改为只扫第 9 步（第 8 步现在含试跑后回写）。
- e2e_input_contract 的「竞品 4 个」「竞品重名」两例不再写死样例里的竞品个数和名字（补到 4 个、复制第 1 个的名字），公开仓库的脱敏样例上也能过（Suda「修这个测试」）。
- 回归：check_skill_terms 无命中；test_validate 56 passed；verify_workflow 62/62；e2e_repair_loop 11/11、e2e_review_loop 14/14、e2e_input_contract 42/42、e2e_precollect 33/33、语种与行业档案 e2e 通过；shared test_prompt_gates 2 passed。
- 飞书《生词规则》同步（Suda「同步飞书」，rev 860 → 870）：新增 9.6「试跑后回写」；流程总览第 10 行、第 3 节分工说明指向 9.6；竞品补足指向 9.6；7.1 只开一行加约束条件；7.2 目标在对话里定；7.4 拆题与拆主题分工；9.1 问题解决不写品牌；9.5 校验清单补主题优先级没写、品牌别名。语言一节原本就写「国家和语种都不限」，没动。改前快照 `30-选Topic与生词/.snapshots/rules-full-20261112-181131.json`；改后回读只多了 1 个二级标题、5 条列表项、1 段，加粗成对。

## 3.14.2（2026-11-12）geo-monitoring 精简成只管采集；选词里指向它的锁版说法同步

触发依据：Suda 2026-11-12「爬虫就看爬虫的活，不用搞那么多限制和规则」「每主题 10 道上限不需要放到爬虫 skill」「按清单删」。

- geo-monitoring 2.0.0：SKILL.md 只留跑几次（试跑每题每平台 3 次、正式基线每格 7 次、日常发现题每天 1 次、其他类型每月 1 次）、工具（采集、完整性、两个试跑读数脚本、基线报告）和交给内容团队；删掉 `references/trial-and-lock.md`（试跑判题表、信源与动作假设、商品卡开关、零提及诊断、准确性题、选正式题与锁版、停测与复查）以及 SKILL.md 里的版本规则、2–4 周复查、季节性、对照组、调研预跑、问题解决默认不出。快照在 `geo-monitoring/.snapshots/*20261112-170447*`。
- 链接和说法同步：选词 SKILL.md、selection-rules.md、online-runner.md、client-facing-base.md、output-contract.md 不再说「挑正式题、锁版、停测归 geo-monitoring」，改为试跑和采集归监测、品牌方在对客确认表上挑正式题；type-branches.md 品牌呈现只留品牌事实核查记录；准确性题不再出。工业类商品卡「试跑后定」的 5% 判法搬进 selection-rules.md 第 1 步（`config.shopping_cards` 是选词写的字段，售前报告读它）。gap-cause-action-table.md、shared 两份文档、validator 报错文字、两个监测脚本说明、render_report.py 注释里的 trial-and-lock 链接改掉。`check_skill_terms.py` 把 trial-and-lock 列为退役说法。
- 回归：check_skill_terms 无命中；test_validate 56 passed；verify_workflow 62/62；e2e_repair_loop 11/11、e2e_review_loop 14/14、e2e_input_contract 41/41、e2e_precollect 33/33、语种与行业档案 e2e 通过；监测三个脚本 `--help` 正常。
- 飞书《生词规则》（Suda「删飞书 10–12 节」）：一次删掉第 10–12 节（试跑与回写、选正式题与锁版、正式基线与之后，3 个一级标题、10 个二级标题、3 张表），其余内容逐字未变；流程总览第 10–12 行、导读、第 3 节分工说明、9.1 和目标表里指向这几节和准确性题的说法改掉（8 处）。改前快照 `30-选Topic与生词/.snapshots/rules-full-20261112-171229.xml`，rev 843 → 852。随后（Suda「重排并删这段」）章节号 13–15 重排为 10–12，导读改为「第 1、3、12 节」；第 11 节「题库维护」删掉停测、另立题集版本、复核节奏三条（与 geo-monitoring 2.0.0 删掉的规则对应），rev 860。

## 3.14.1（2026-11-12）删掉锁版检查脚本；没人读的题库字段拿掉

触发依据：Suda 2026-11-12「geo-monitoring 为啥要管锁版门禁啊，就是默认跑 3 次或者 7 次而已」「ok」「没人读的字段就拿掉」「文字规则其实不用留吧」。核对过：项目里 19 份带生命周期字段的题库全部停在 hypothesis / planned，从没走到锁版；锁版在对客表上把状态改成「正式」，正式题 60 道额度 `check_client_base.py` 已在表上查。

- 删掉 3.14.0 新建的 `geo-monitoring/scripts/check_locked_set.py`、`scripts/test_check_locked_set.py`、`evals/verify_lock_gates.py`（快照在 `geo-monitoring/.snapshots/`），trial-and-lock.md「锁版前跑门禁」改为锁版后用 `check_client_base.py` 查额度；monitoring 1.9.1。没有新加「每主题 10 道」的检查。
- 题库字段只留有脚本读的：删 `lifecycle_status`、`customer_confirmation`、`trial`、`baseline`、`prompt_version`、`purchase_selection`、`assessment_scope`（config）和 `intent_key`、`market_decision`（题），写了也不读；output-contract.md 根结构改写 `collection_config`（语种门禁读）和 `retired`（基线报告读），删「试跑与基线元数据」一节。W33、W57 去掉锁版后报错的说法；validator 报错文字去掉「required before lock」。selection-rules.md 多市场、client-facing-base.md 编号规则、online-runner.md 固定值、shared/prompt-generation-principles.md 同步。
- 回归：check_skill_terms 无命中，test_validate 56 passed，verify_workflow 62/62，e2e_repair_loop 11/11，e2e_review_loop 14/14。

## 3.14.0（2026-11-12）锁版门禁搬到 geo-monitoring；审核 C 组；飞书《生词规则》同步

触发依据：Suda 2026-11-12「选词 skill 不应该写锁版之类的规则，这个 skill 只负责生词」「同步飞书」「其他的继续做」。审核时还发现 geo-monitoring 的文档从没提过跑锁版门禁，这些门禁只在选词 validator 里，监测侧实际用不到。

- **锁版门禁搬走**：新建 `geo-monitoring/scripts/check_locked_set.py`，继承选词 validator 的全部生词门禁，再查生命周期和两次确认、试跑 3 次与证据、正式基线元数据、正式题额度（门禁 14：每条产品线 × 国家 × 语言 60 道、10 × 主题数）、W34、`--previous` 改版检查；W33 锁版后、W57 客户确认后由告警升为报错。选词 validator 删掉这些代码和 `--previous`，W33、W57 在选词阶段只告警，W47 不再按锁版跳过。监测 trial-and-lock.md「选正式题与锁版」写明锁版前跑它，SKILL.md 工具节登记，monitoring 版本 1.9.0。
- **测试跟着搬**：verify_workflow 的 20 个锁版用例搬到 `geo-monitoring/evals/verify_lock_gates.py`（另加假设证据不能锁版、锁版后缺主约束、60/61 道额度 4 例，24/24）；`test_validate_after_sales_set.py` 的 7 个锁版测试搬到 `geo-monitoring/scripts/test_check_locked_set.py`（加「锁版后不查候选题范围」，8 passed）。搬前用两套检查器跑全部 81 例对照，监测检查器 81/81，确认行为没变。选词 verify_workflow 62/62、test_validate 56 passed。
- **C 组**：W54 改按合同字段判（`attribute_ref` 留空且没有条件关键词；旧的 `constraint_type` 标记照读），原来只读合同外字段、按文档写的题库永远不触发；W56 告警文字不再用已拒收的旧字段名 `review_status`；门禁 42（硬条件人工核实）没有实现，移到人工检查；output-contract.md 补上题号重复、切片编号、`slice_ref` 不存在等没写进文档的报错，写明门禁 12 的候选式问法只在英文市场查、门禁 38 只查对比题、旧字段 `intent` 在没写 `prompt_type` 时才拒收；online-runner.md 改正 `schema_version` 不是 validator 要求的；`check_client_base.py` 注释改正。
- **飞书《生词规则》**（rev 821 起增量改 22 处）：3.13.0 的题量、约束条件表、业务优先级、7.2「哪些行出题」、需求信号登记、校验清单同步；顺带修了文档里早于 3.13 的旧口径：主题优先级取组内最高（原写多数行）、同档按点名条目序号排（原写先排发现类、再按搜索量）、提示词库有提示词优先级列、售后重聚不按主题个数差、问题解决看引用不看提及率。改前快照 `30-选Topic与生词/.snapshots/rules-full-20261112-162042.xml`；改后回读块数、表数、行数、加粗配对与改前一致。
- `check_skill_terms.py` 加「validator --previous / 锁版门禁在本 validator」退役说法。

## 3.13.0（2026-11-12）审核 A 组：规则冲突修复；题量 30–60 定死在一处，超 60 报错；线上不到 30 补一轮

触发依据：Suda 2026-11-12 全面审核选词 skill（清单 `docs/exec-plans/active/selection-skill-audit-20261112-progress.md` A 组 14 条），「先修 A 组冲突」；同日口径：主题数量不限、单产品线 × 单市场至少 30 道、单产品线 × 单市场 60 道硬上限要保留（控制成本）；售前线上没有正式题和批准，生成即测量。

- **题量只在 selection-rules.md 第 7 步定义**：每条产品线 × 每个市场候选题 30–60 道。超过 60 由告警改为报错（门禁 47，成本上限）；不到 30 仍是告警 W47，按产品线 × 市场计数（原来只按产品线）。删掉第 6 步、client-facing-base.md 里的「候选题不设上限」。主题个数不设限写进第 6 步。
- **线上补题轮**：`run_selection_mode.py` 检查通过但不到 30 道时写 `TOPUP.md` 补一轮（先开中档我方补充行和假设行，再用低档行，不许同义改写；`--repair-rounds 0` 不补）；补完没过检查退回原题库；仍不够照常交付，`result.json` 记 `top_up` 和一条 warning。e2e_repair_loop 加 4 例（11/11）。
- **约束条件表门禁不再能绕过**：`brand_status` 必填；矩阵行或题挂了约束条件却没有 `attribute_plan` 报错；题的 `attribute_ref` 必须在表里；表条目可带 `product_line`，只管那条产品线的题（门禁 67、68）。online-runner.md 补第 3 步。**影响**：3.11.0 之前写的题库（某制氧机客户、Ubrand、某车载品牌、Bbrand、brand-o）重跑 validator 会因缺品牌情况报错，维护这些题库时先补约束条件表。
- **`write_prompt_reasons.py` 降档也看主约束**：原来只拿 `constraints`（买家说法关键词）去对约束条件表，关键词很少和选项同名，主约束明显劣势的题不降档；现在 `attribute_ref` 和关键词都看，带 `product_line` 的条目按产品线取。门禁 68 的范围在 output-contract.md 写明，其余条件列入人工检查。
- **已开放类型的行要判档**：validator 按 `business_goals` 判哪些类型已开放（`opened_types`），这些行缺业务优先级报错、高中档没题给 W48（原来只查发现行）。W59 只管发现主题，删掉其他类型「至少 5 道」（替代每竞品 1 道、交易每线 1 道，结构上凑不满）。
- **交易、售后**：没有对应目标，本期只登记、不判档不出题；删掉 type-branches.md「品牌方把官网直购、客服列为目标可提到中」。「开放时要改的地方」改写成「还没开放的部分」（线上非发现、交易售后、后端枚举三块）。
- **需求信号登记只定义一处**（selection-rules.md 第 2 步）：相关且会改变选词判断的都登记，不只登记撑起题的；client-facing-base.md、online-runner.md 改为引用。
- **业务优先级**：「有转化可提档」改为我方补充的行可从低提到中，高只认点名；劣势不构成排除理由补上第 5 步例外；起决定作用的条件品牌没有或待确认的，按第 3 步处理（不开行或不写进题面），不再写「可降为低」；线上「排在前面的判高」改为品牌资料写了的条目都判高，资料为空时按官网主推判。
- **其他**：阶段表允许预跑答案作候选类别线索；低档行补了题随题进主题；client-facing-base.md 去掉 3.10.0 遗留的「对客表只有发现行」；差异化优势改指约束条件表；线上 `evidence_status` 按买家信号写；output-contract.md 上传文件改为「一个市场 × 一条产品线」、门禁 14 改为按产品线计。SKILL.md 版本号从 3.9.4 补到 3.13.0、description 改 5 列。
- `check_skill_terms.py` 加 7 组退役说法；verify_workflow 81/81（新增 7 例），test_validate_after_sales_set 63 passed，e2e_review_loop 14/14、e2e_input_contract 41/41、e2e_precollect 33/33、e2e_language_check、e2e_industry_kb 通过。

## 3.12.2（2026-11-12）撤回「不判」：品牌情况只判有没有，高低在相对竞品

触发依据：Suda 2026-11-12「为啥是不判，我们不是评估品牌情况吗，有高低不是判断相对竞品吗」。

- 品牌情况回到 有 / 没有 / 待确认。每家都有、只分高低的条件，品牌情况填有（依据写「每家都有」），好坏高低填在相对竞品；不再单设取值。口碑可信度、竞品缺点那两句随「不判」一起删。
- validator、`check_client_base.py` 取值去掉「不判」，verify_workflow 改为「不判是非法取值」，75/75；`check_skill_terms.py` 把「有 / 没有 / 待确认 / 不判」「填不判照常出题」列为退役说法。selection-rules.md 第 3 步、client-facing-base.md、output-contract.md、SKILL.md、shared/prompt-generation-principles.md、模板 Base（删「不判」选项）、飞书《生词规则》同步。

## 3.12.1（2026-11-12）品牌情况判法不罗列条件类别

触发依据：Suda 2026-11-12「我觉得你不应该罗列这些」（指 3.12.0 列出的功能、资质认证、书面承诺、渠道地区、支付配送等类别和「还没上线算没有」）。

- selection-rules.md 第 3 步只留判法：先看条件本身，同一品类里是有的品牌有、有的没有，还是每家都有、只分高低。前者调研品牌官网和其他渠道后判有 / 没有 / 待确认，后者填不判。删掉两组类别清单和「还没上线的算没有」。client-facing-base.md、SKILL.md、模板 Base 字段说明、飞书《生词规则》5.2 同步。

## 3.12.0（2026-11-12）品牌情况加「不判」：每家都有、只分高低的条件照常出题；判法写成跨品类通用

触发依据：Suda 2026-11-12「把质量维度设成例外」「规则需要通用，而不是只适用于这个品类」。

- 判法先问「这个条件，品牌有没有可能没有」。可能没有的（功能、型号或配置选项、资质认证、书面承诺、销售渠道与覆盖地区、服务范围、支付和配送方式）判有 / 没有 / 待确认，还没上线的算没有；不可能没有的（质量、耐用、使用体验、服务表现、价格、常规规格数值）填不判、照常出题，高低看相对竞品和监测结果。问品牌本身口碑可信度的题、只描述竞品缺点的条件也填不判。能力和程度绑在一起的拆开判；只在部分型号、套餐、地区有的按产品线 × 市场判，题面不超出覆盖范围；要另签合同、加购或靠第三方的，公开写明算有，只能个案谈算待确认。
- 门禁 67 取值加「不判」，四种都要写 `brand_status_basis`（不判写属于哪一类）；门禁 68 不拦不判。`check_client_base.py` 同口径。verify_workflow 75/75（新增「不判条件照常出题」）。
- 规则和用例里的示例换成中性写法，不再用具体客户品类的竞品名。selection-rules.md 第 3 步、client-facing-base.md、output-contract.md、SKILL.md、shared/prompt-generation-principles.md 同步；模板 Base 加选项「不判」，飞书《生词规则》5.2 同步。

## 3.11.3（2026-11-12）品牌情况写进总原则；「有」也必须写证据

触发依据：Suda 2026-11-12「仅将已确认品牌具备或有充分证据支持的属性纳入后续生词。确认不具备的属性直接排除；能力未知或缺乏证据的属性默认不出题，保留待确认。品牌相对竞品存在劣势，不单独构成排除理由。核心是：宁可少出几道题，也不要把品牌可能不具备的能力纳入 GEO 优化目标。」

- selection-rules.md 第 3 步「品牌情况」开头写这条原则；能力未知归待确认；写明劣势不单独构成排除理由。第 5 步「我们补充的行，起决定作用的条件是明显劣势或品牌没有的，可以降为低」保留（Suda 同日确认不去掉）。
- 门禁 67：有 / 没有 / 待确认三种取值都要写 `brand_status_basis`（原来只要求没有、待确认）。output-contract.md 同步。verify_workflow 74/74（新增「有但没写证据」），test_validate_after_sales_set 63 passed，check_skill_terms 无退役说法。
- 飞书《生词规则》5.2 同步。

## 3.11.2（2026-11-12）品牌情况恢复「待确认」：待确认和没有都不出题

触发依据：Suda 2026-11-12「其实可以是待确认，默认待确认的能力不出题就好了」。改写 3.11.1：没找到证据就填「没有」等于替品牌下结论，品牌方看到会认为我们没做功课，也分不出哪几行需要他们核对；出不出题和 3.11.1 一样。

- 品牌情况 有 / 没有 / 待确认。有要有证据；没有要有明确证据（品牌方说过、文档和宣传页相反、在适用边界外）；查过但没找到证据的是待确认。没有、待确认都必须写 `brand_status_basis`（证据，或查过哪里），挂这两种条件的题都不出。对客字段说明：「待确认的请改成有或没有，改成有的我们补题」。
- 门禁 67 加「没有 / 待确认写了 brand_status_basis」，门禁 68 扩到待确认；`check_client_base.py` 同口径。出题原因仍不写「待核实：品牌有没有 X」（这类题不出）。
- 修复：14:50 selection-rules.md、client-facing-base.md、validate_after_sales_set.py、evals/verify_workflow.py 被写回 3.11.0 的「待确认照常出题」，本版一并改正。第 2 步官网和文档说法不一致的改为以文档等为准、判不出才填待确认。shared/prompt-generation-principles.md 第 11 条同步。
- 验证：verify_workflow 73/73（新增「题挂待确认条件」「待确认无出处」两例），test_validate_after_sales_set 63 passed，check_skill_terms 无退役说法。

## 3.11.1（2026-11-12）品牌情况只分有 / 没有：找不到证据的算没有，不出题

触发依据：Suda 2026-11-12「没找到证据的证明都没有，不用出题」。推翻 3.11.0 的「待确认照常出题、出题原因写待核实」。

- 约束条件表「品牌情况」只剩 有 / 没有。有证据（文档、控制台、条款、规格表、品牌方材料）才填有；找不到证据、在适用边界外、文档和宣传页相反的都是没有，挂这些条件的题不出。品牌方交付后把其实有的改成有并给出处，我们再补题。selection-rules.md 第 2、3、7 步，client-facing-base.md，output-contract.md，SKILL.md 同步。
- validator、`check_client_base.py` 的取值只认 有 / 没有；`write_prompt_reasons.py` 去掉「待核实：品牌有没有 X 还没确认」那句。`verify_workflow.py` 用例改为「待确认」是非法取值，71/71。`check_skill_terms.py` 加退役说法「有 / 没有 / 待确认」「待确认的照常出题」。
- 模板 Base 与飞书《生词规则》同步。

## 3.11.0（2026-11-12）对客 Base 加「约束条件」表：品牌情况、公开硬事实上的相对竞品；业务优先级依据写赢面

触发依据：Suda 2026-11-12。Dbrand 客户指出词库里有他们没有的能力（按秒计费、自带模型托管）。官网首页写了按秒计费，文档写的是按小时，我们按首页记成了品牌能力；品牌能力清单只在内部 notes，品牌方看不到也改不了。Suda 定：按约束条件逐条判品牌有没有、和竞品比的公开硬事实，放进对客表；参照 Value Proposition Canvas（匹配要按客群、要有证据）和 Playing to Win（赢面写进业务优先级依据）。

- **约束条件表**（client-facing-base.md）：`约束条件 | 品牌情况 | 相对竞品 | 相对竞品依据 | 产品线 | 市场`，一个选项一行，第七张表。品牌情况 有 / 没有 / 待确认，「没有」要有明确证据，哪里都没写的是待确认、照常出题、出题原因写「待核实」；出处只记 JSON `brand_status_basis`，不进对客表。相对竞品 明显优势 / 明显劣势 / 持平 / 未知，只判价格、规格、数量、计费方式、区域这类公开硬事实，比不出来填未知。不判重要性、不放目标客户和场景。表名不叫属性池：名单就是三张表的约束条件选项，里面有品牌没有的条件，属性池又是 2.19.0 退役的旧口径。
- selection-rules.md：第 2 步品牌官网的出处规则（文档、控制台、条款、规格表优先于首页和宣传页，冲突填待确认并记品牌事实核查）；第 3 步品牌情况、相对竞品只判硬事实，「品牌明显劣势」就是相对竞品为明显劣势的行；第 5 步业务优先级依据写赢面，品牌方点名的行不因赢面降档，我们补充的行起决定作用的条件明显劣势或品牌没有的可降为低；第 7 步降档由脚本从约束条件表推，题上手写 `brand_weakness` 只用于表达不了的情况。
- 题库 JSON：`config.attribute_plan` 每条加 `brand_status`、`brand_status_basis`、`vs_competitors`、`vs_competitors_basis`（不用旧键 `relative_competitor`）。validator 门禁 67（取值合法、非未知要依据）、68（题挂了品牌没有的条件），告警 W67（明显优势没有题测）。
- `write_prompt_reasons.py`：题挂的约束条件是明显劣势的自动降一档、依据写进出题原因开头；挂了待确认条件的写「待核实」。`check_client_base.py` 查约束条件表：缺表、和选项名单不一致、取值不合法、非未知没依据、提示词库挂了品牌没有的条件。
- `verify_workflow.py` 加 4 个用例（71/71）；`check_skill_terms.py` 撤掉「相对竞品依据」退役，改扫「品牌能力清单」「约束条件不单设表」。geo-monitoring gap-cause-action-table.md、shared/prompt-generation-principles.md 同步一句。
- 模板 Base 加约束条件表。

## 3.10.0（2026-11-11）对客表不再限发现行；「只出发现」只管线上

触发依据：Suda 2026-11-11「多维表格没有这个限制啊，只是线上有限制而已」。Dbrand 按品牌方要求出了对比、替代、评估、验证四类，`check_client_base.py` 却要求把这几行从对客表删掉。

- selection-rules.md → 1、5、7，type-branches.md，client-facing-base.md，output-contract.md `slices`，SKILL.md：线上一条命令跑只出发现题；本地选词按品牌方在 `config.business_goals` 选的目标开放对应类型（判档、进对客表、出题、聚主题），没选的目标照旧只登记。
- `check_client_base.py` 不再把非发现行当问题，这些行照常查业务优先级和依据。
- `verify_workflow.py` 对应用例改期望；`check_skill_terms.py` 撤掉 3.0.0「非发现行不进对客表」那条，改扫「对客表只放发现行」「本期只开放发现」。
- validator、online-runner.md、上传 CSV 不变（后端没有的题型照旧不导出）。

## 3.9.4（2026-11-11）行业知识档案：品牌标识去掉盐；恢复「Tecno/Infinix 用户」

触发依据：Suda 2026-11-11「去掉盐再推送」「『Tecno/Infinix 用户』这条没必要拦截」。档案里本来就写着品类和市场，盐只挡住「拿品牌名一算就确认」这一步，不值得让研发多配一个密钥。

- `industry_kb.py` 品牌标识改回不加盐（SHA-256 前 12 位），删 `GEO_INDUSTRY_KB_SALT`；数据 `schema: 6`，档案按新标识重建。持久化目录、照抄 Case 原句不进的规则不变。
- 耳机充电器客户回填不再把 Tecno、Infinix 当排除词，「Tecno/Infinix 用户」这类目标客户照常进档案。
- runner-ops.md 删 `GEO_INDUSTRY_KB_SALT` 一行，README 同步；`e2e_industry_kb.py` 删加盐用例 K11，15/15。

## 3.9.3（2026-11-11）行业知识档案随 skill 发布；服务器从它起步、在持久化目录继续积累

触发依据：Suda 2026-11-11「不用留在本地吧，skill 运行在服务器上的时候可不知道呢」。3.9.2 同步公开仓库时档案数据没推，服务器拿不到已积累的经验；不推的原因是品牌标识用的是不加盐的 SHA-1，拿品牌名一算就能对上。

- 品牌标识改成加盐的 HMAC-SHA256（前 12 位），盐取 `GEO_INDUSTRY_KB_SALT`（环境变量或 macOS 钥匙串同名项，本地已生成），不进仓库；没有盐不写档案（`add` 退出码 2，runner 只记 warning）。数据 `schema: 5`，档案按新标识重建。
- 服务器设 `GEO_INDUSTRY_KB`（持久化目录）时：runner prepare 先 `seed_if_empty()`，目录还没有档案就从随 skill 的 `references/industry-knowledge/` 复制；再把这个目录的档案拷进工作目录，agent 读到的是持续积累的那份。新增 `industry_kb.py seed`。
- 照抄品牌资料（Case）12 字以上原句的条目不进档案（线上读工作目录里的品牌资料，本地 `add --case`）：公开扫描拦下了行车记录仪客户 Case 里的两句使用场景原文。回填按客户目录下所有 Case 文件过滤后重建。
- 脱敏扫描修一处误报：「竞品 1 主题」这类字段是主题名，不再当竞品名扫。
- runner-ops.md 环境变量表加 `GEO_INDUSTRY_KB`、`GEO_INDUSTRY_KB_SALT`；档案 README 同步。
- `e2e_industry_kb.py` 加 K7c（照抄 Case 原句的不进）、K11（档案里没有不加盐的哈希、没有盐不写）、K12（空持久化目录第一次 prepare 从随 skill 档案复制，新并入的品类拷进下一次工作目录），16/16。

## 3.8.1（2026-11-11）多产品线共用一个 Base 的三条运维坑

Suda 定，起因是某制氧机客户第二期加了 DA400 Air：同一份对客表装两条产品线时连踩三个坑，都是「编号必须跨产品线唯一」这条规则被违反造成的。

- 切片编号撞车：两条线都从 M-001 起，矩阵里出现同名切片，题目链接按编号解析会挂到另一条线的行上。改成接续编号（M-015 起）。
- 题号撞车：两条线都从 Q001 起，`write_prompt_reasons.py` 按题号匹配会错配。改成接续编号（Q046 起）。
- `write_prompt_reasons.py` 只要有一道题的题号不在所给题库里就整批退出、一个字不写。多产品线必须把所有题库一起传（`--bank` 可重复），`--noun` 取跨品类都说得通的词。写进 client-facing-base.md → 提示词库。

另：写进需求信号表的来源类型必须用模板下拉里已有的值（如 DataForSEO），子代理常自己写成「搜索词」，批量写入会报 not_found。

## 3.9.2（2026-11-11）行业知识档案：同一客户重跑换了行业或品类不再重复计

触发依据：同步公开仓库前检查档案时发现，一个便携存储客户先按「消费电子与智能家居 / portable photo backup」回填，另一会话又按「其他 / portable nas」并入，同一客户在两个行业各算一次；中间还换过一次品类（home nas），留下没有客户的「品类-home-nas.md」。

- `industry_kb.py` 数据结构 `schema: 4`：每条记「哪次（品牌 × 市场）用了哪种写法」（`by`），客户数、写法计数、市场、品类都从它算。同一品牌同一市场重跑：先从所有行业档案撤掉这一次再并入，以最近一次为准；同一品牌不同市场分开记、合起来仍算 1 个客户。没有客户的「品类-」文件自动删除。
- 按新结构重建档案（回填 9 份题库 + 另一会话并入的那次，快照 `.snapshots/industry-kb-dedupe-20261111-183940/`）：8 个品类、5 个行业；该客户现在只在「其他 / portable nas」（最近一次）。
- `e2e_industry_kb.py` 加 K7b（同一品牌两个市场算 1 个客户）、K10（换行业换品类撤旧、删空品类文件），13/13。

## 3.9.1（2026-11-11）精简线上必读的两份文档：signal-sources.md、output-contract.md

触发依据：Suda 2026-11-11「先精简两份文档」，按 3.7.0 的精简判据（保留被引用的定义、validator 会查的字段和门禁、反复出错的判断；重复的只留一处、故事进 CHANGELOG、穷举改原则、本地才用的移到本地文档）。改前全文快照 `.snapshots/slim-docs-20261111-181530/`。

- `signal-sources.md` 14,133 → 5,836 字：「GSC 与搜索词报告怎么用」整节和品牌方数据的偏差移到 `demand-side-signals.md`（只在有品牌方资料时读，线上不拷）；行业表删「典型决策摩擦」列和客户名示例；关键词工具、Trends 的脚本用法改指 `--help`，只留四档填法、父关键词取最大不相加、Trends 能做什么；AI 追问、模型联想合成一段；子代理取数、深度调研压成「本地调研补充」两条；实测故事删去（见历史 CHANGELOG）。被引用的节名（所有行业都做、按行业收评价和社区、按目标市场换成当地平台、每类数据怎么用、月搜索量取哪家的、每类信源能用来干什么）保留。
- `output-contract.md` 11,919 → 7,746 字：字段、门禁编号全部保留，描述压短；监测阶段才写的 config 字段合成一行指向 trial-and-lock.md；上传 CSV 删报告脚本内部读法；旧结构判法改指 `legacy_markers`；试跑与基线元数据只留 validator 查的。
- 线上 agent 必读 references 约 6.6 万 → 5.4 万字。`online-runner.md` 改一句（浏览器替代说明的指向）。
- 测试：check_skill_terms 0 命中，validator pytest 63，verify_workflow 67/67，e2e 全过（precollect 33、domestic 16、gateway 9、industry_kb 11、input_contract 41、language 35、repair 7、review 14）。

## 3.9.0（2026-11-11）行业知识档案加品类一层：内容按品类看，渠道按行业看

触发依据：Suda 2026-11-11 同意「在行业下面按品类分一层」。3.8.1 回填后「消费电子与智能家居」4 个客户分属行车记录仪、耳机充电器、便携存储、摩托车 CarPlay 屏，行车记录仪客户会读到大半耳机的经验。Suda 追问「是不是只看品类不需要看行业」：约束条件、目标客户、场景、主题只按品类看；渠道效果仍按行业看（评价站、社区本来就按行业选），行业文件另放跨品类、2 个以上客户都出现的条目，所以保留行业这一层但只管这两样。

- `industry_kb.py`：每个客户记英文品类词（线上取 plan-checked.json 的 `category_en`，本地 `--category`；小写、去复数，dash cams → dash cam，antivirus 这类词尾 s 不去），条目和渠道都记出现过的品类。生成「品类-<品类>.md」（这个品类的约束条件、目标客户、场景、主题、品类叫法、渠道）和「行业-<行业>.md」（已有品类列表、渠道效果、跨品类通用条目）。行业「其他」不再拼品类进档名，记成「其他」，靠品类区分。数据结构 `schema: 2`，旧档案自动重建。
- TASK 模板和 selection-rules.md 第 2 步改成：读本行业的「行业-」和最接近本客户品类的「品类-」两份（按英文品类词判断，没有接近的不读）。
- 重新回填 9 份题库（快照 `.snapshots/industry-kb-v1-*`）：8 个品类文件、5 个行业文件，全文搜不到客户名和竞品名；消费电子跨品类通用 1 条（价格预算，行车记录仪和摩托车 CarPlay 屏）。
- `e2e_industry_kb.py` 加 K4b（品类分开、行业文件列品类和跨品类通用），11/11；其余测试照过。

## 3.8.1（2026-11-11）行业知识档案回填 9 份历史题库；写法不同的同一条合并计数

触发依据：Suda 2026-11-11 同意用已做过的客户题库回填档案。

- 回填：8 个客户的 9 份题库，分属 5 个行业（同一品牌两个市场算一个客户）。回填前在临时目录预演，人工过了一遍档案里的英文专名（CarPlay 这类生态和兼容对象不是客户或竞品），全文搜不到任何客户名和竞品名。
- `industry_kb.py` 加归一键：忽略「与、和、及」、顿号、斜杠、空格、括号和大小写后相同的算同一条，显示最常用的写法并注明「也写作」。JSON 条目改成 `{label, names, clients, markets}`，以归一键为键。
- 现状：消费电子 4 个客户只有「价格预算」1 条通用——这一行业覆盖行车记录仪、耳机充电器、便携存储、摩托车 CarPlay 屏，品类差得远，重合少；其余行业各只有 1 个客户。档案要等同品类客户多了才有通用条目。
- `e2e_industry_kb.py` 加 K2b（写法不同合并），10/10。

## 3.8.0（2026-11-11）行业知识档案：每个客户的品类经验自动积累，下一个同行业客户先读

触发依据：Suda 2026-11-11 定「积累行业通用规则是需要的」，同时否掉跨客户缓存（数据费一轮只有几美分，省不了多少钱，还加复杂度）和 DataForSEO 快速队列。

- 新增 `scripts/industry_kb.py`：从题库抽约束条件、目标客户、使用场景、主题名、品类叫法，从线上预采集抽渠道效果（采到 / 没采到），并进 `references/industry-knowledge/<行业>.json`，同时生成给 AI 读的 `<行业>.md`。同一条在 2 个及以上客户出现标「通用」，1 次标「单例」；同一客户重跑不重复计。只存品类层面的条目：含品牌名、品牌别名、竞品名的整条跳过，客户只记品牌名 SHA-1 前 10 位。行业没判出来（fallback）不并入；判成「其他」的档名是「其他-<英文品类词>」。档案目录可用 `GEO_INDUSTRY_KB` 改（平台部署指到持久化目录）。不设人工审核关，靠「通用 / 单例」区分可信度（Suda 未另定把关方式，按此默认）。
- 线上 runner 在审核环之后、成功交付时自动并入（`learn_industry`），结果路径记进 `out/result.json` 的 `industry_kb`；测试模式（`--task-file`）只在显式设了 `GEO_INDUSTRY_KB` 时写，假数据不进正式档案。TASK 模板加一段：调研前读本行业的 `.md`，只当假设级线索，用本客户买家信号核实，不硬加、不当依据。
- selection-rules.md 第 2 步加「同行业积累的经验」，第 8 步加「并入行业知识档案」（本地选词交付后手动跑 `industry_kb.py add --bank`）。
- 撤掉做了一半的跨客户缓存：删 `shared/scripts/shared_cache.py`，`net.py` 的搜索、取网页、Reddit 改回本轮缓存。改前快照：项目根 `.snapshots/shared-cache-revert-20261111-165803/`。
- 新增 `evals/e2e_industry_kb.py`（9 项，不联网）：两个假客户并入后共有条目变「通用」、品牌和竞品名全文搜不到、重跑不重复计、渠道效果、fallback 不并入、「其他」档名、本地题库并入、runner 钩子在测试模式不写正式档案、TASK 提示读档案；9/9。其余测试照过。

## 3.7.0（2026-11-11）精简：规则减半、撤掉搜索服务层、runner 拆模块；规则外让 AI 推理

触发依据：研发 2026-11-11 书面反馈 skill 太复杂、不需要再包一层搜索服务；Suda 同日要求优化臃肿处、线上每轮要读的规则尽量写通用，并定原则「没有落在规则内的应该让 AI 推理，规则无法穷举」；还问到 Google Shopping 评价是否只有三个行业需要。

- **规则外让 AI 推理**：selection-rules.md 总纲加第四条原则「规则没写到的按目标推理」，依据写进 notes「假设」，门禁只拦明显错误和不能执行的输出。precollect 行业写「其他」时 add 上限 3 → 5；新增 `add_sites`（最多 2 个）让 AI 加渠道表里没有的站，按站内页渠道采（搜「站名 品类词」取页面正文）。
- **新行业行「其他实体消费品」**（家居厨房、宠物、母婴玩具、服饰鞋包、运动户外、汽车用品、食品饮料等网上零售的实物）：评价采 Google Shopping 和 Trustpilot。原表只有医疗器械、消费电子、美妆三行有 Google Shopping。
- **selection-rules.md 2.99 万字 → 1.4 万字**，判断标准：被其他步骤依赖的定义、validator 会查的规则和字段名、反复出过错的判断保留并压成一两句；同一规则写了两三遍的只留一处；一条规则多个例子和实测故事的只留一个（故事都在本 CHANGELOG 和归档里）；能写成通用原则的穷举清单改成原则加提示（目标客户八种切法表和按行业查表收成「按会不会改变候选、标准、问法来切」）；只有本地流程用的内容（向品牌方要哪些数据、GSC 导出细节、飞书表回读）改成一句话指向 demand-side-signals.md、client-facing-base.md（那里本来就有完整版）。第 6 步「报价与交付的先后」「品牌方售前点名的主题不重聚」合成「售后重聚」。跨文档的章节引用逐条核对仍能找到。改前全文：项目根 `.snapshots/selection-rules.md.20261111-161927.bak`。
- **online-runner.md 1.25 万字 → 0.75 万字**：部署、环境变量、境内服务器、接平台网关、审核环、每轮记账、验收移到新文件 `references/runner-ops.md`（给研发，runner 拷工作目录时排除，agent 不读）。线上 agent 必读的规则合计从约 8.8 万字降到约 6 万字。
- **撤掉 3.6.0 的搜索服务层**：删 `shared/search-service/`（server.py、API.md）、`shared/scripts/search_api_client.py`、`evals/e2e_search_api.py`，去掉 net.py 和四个采集脚本里的 `GEO_SEARCH_API` 转发；平台接入改由 3.6.4 的网关地址（`SCRAPELESS_BASE_URL` 等）承担。`check_skill_terms.py` 加退役说法 `GEO_SEARCH_API|search-service|搜索服务模式`。
- **run_selection_mode.py 1,900 行 → 约 970 行**：预采集（渠道计划检查、三类采集、登记检查）拆到 `scripts/precollect.py`，行为不变；行业判断（要起 agent）留在 runner。
- **CHANGELOG 25 万字节 → 5 万字节**：3.0.0 之前的记录原样移到 `CHANGELOG-archive.md`；两份 CHANGELOG 都不拷进线上工作目录。
- **客户数据移出 skill 目录**：根目录和 `scripts/` 下 17 个飞书 Base 导出（lark-cli 残留）移到项目 `90-历史归档/选词skill目录残留的Base导出-20261111/`。
- 验证：`e2e_precollect` 加第 15、15b、16 项（「其他」加 5 个渠道和表外站、超额被拒、其他实体消费品），33/33；validator 测试、verify_workflow、input-contract、repair-loop、review-loop、language-check 照过；`e2e_domestic_network` 16/16、`e2e_gateway` 9/9（真实调用）。
- 改前快照：项目根 `.snapshots/slim-20261111-155914/`（本 skill、shared/scripts、search-service、collect_answers）。

## 3.6.4（2026-11-11）厂商接口地址可配置，接平台网关；render 不再依赖本机 Chrome

触发依据：研发 2026-11-11 反馈要减少搜索服务的接口、最终把 skill 平台化，平台用不用我们的搜索服务未定（同日研发确认不需要再包一层）。skill 对外只依赖 Scrapeless、DataForSEO 两家，所以改成两家的接口地址可配置，平台网关透传即可；另外平台服务器没有 Chrome，`net.py render` 在那里一直是失败的。

- 新环境变量 `SCRAPELESS_BASE_URL`、`DATAFORSEO_BASE_URL`、`GEO_GATEWAY_HEADERS`（JSON 请求头）：`net.py`、`collect_serp_signals.py`、`collect_keyword_data.py`（`collect_reviews.py` 随之）、`collect_answers.py` 发给两家的请求都改走可配置地址并带上网关头；Scrapeless 搜索结果原始页的 `rawUrl` 一并改写到网关；设了地址时本机没有 key 或凭据不再报错（网关注入）。runner 透传这三个变量，设了 `SCRAPELESS_BASE_URL` 不再要求本机有 key。不设就是原来的官方地址。
- `net.py render`：本机没有 Chrome 或境内模式时，改经 Scrapeless 代理不开 JS 取（2026-11-11 实测 RTINGS 能取到正文，开 JS 渲染反而报 frame detached；GlobalSources 两种都被 AWS WAF 拦）；新增 `--country`，runner 的站内页渠道传市场代码。
- 新增 `evals/e2e_gateway.py`（9 项）：本机起透传网关注入真实密钥，调用方无密钥、除网关外不通外网，网页、搜索、Pantip、搜索联想、关键词余额、Trustpilot 评价、AI 回答都经网关跑通，不带网关头被拒；9/9。`e2e_domestic_network` D4 改为断言 render 经代理取到 RTINGS，16/16；`e2e_search_api` 12/12。
- online-runner 加「接平台网关」一节，列出两家用到的接口路径。

## 3.6.3（2026-11-11）每轮记账补齐 Scrapeless 漏项；搜索服务改为规格不部署

触发依据：Suda 2026-11-11 问 Scrapeless 能不能算每次生词的成本；核对 runner 的 `costs` 块发现两处漏数：境内模式下自动补全经 Scrapeless 网页代理取（3.5.1 起），既不落盘也不计数，重跑还会重复付费；Pantip 渲染页（3.6.2）有计数但 `cost_report.py` 不计价。同日 Suda 确认研发已有或打算建自己的数据接入层。

- `collect_serp_signals.py`：境内模式的自动补全结果存 `raw/<种子词>.autocomplete.json`（证据），重跑直接复用、不再付费；`--cache-only` 时不发请求。
- `run_selection_mode.py` 的 `costs.scrapeless_requests`：`serp_requests` 不再把 autocomplete 文件算成搜索；新增 `autocomplete_proxy`（按代理页计价）；`render_pages` 照旧。
- `shared/scripts/cost_report.py`：新单价键 `render_usd_per_k`（JS 渲染页，没填按 `proxy_usd_per_k` 算并提示），选词轮 Scrapeless 花费＝搜索 ×serp 价 ＋（代理页＋境内自动补全）× 代理价 ＋ 渲染页 × 渲染价 ＋ 预跑尝试 × 答案单价。
- `shared/search-service/API.md` 加状态说明：研发有自己的数据接入层，这个服务不部署，文档和 `server.py` 作为接口规格与参考实现，接入方式待定。
- 验证：`e2e_domestic_network` 加 D6b（重跑不再付费）、D11（真实一轮 precollect 的用量计数＋`cost_report` 按单价算出的金额和手算一致），16/16。

## 3.6.2（2026-11-11）Pantip 帖子改用 net.py pantip：不需要本机 Chrome，境内模式也能采

触发依据：Suda 2026-11-11 要求把 Scrapeless 官网上能用的能力接上；境内模式下 Pantip（泰国市场固定社区渠道）原来只能靠本机无头 Chrome，服务器上采不到。实测：Pantip 评论是页面加载后另请求 `/forum/topic/render_comments` 取的，静态页只有模板占位符；Scrapeless 网页代理开 JS 渲染直接取页面拿不到评论，给代理加 `X-Requested-With` 请求头也不转发；改成用网页代理 v2 的 JS 渲染、在页面里执行一段脚本请求评论接口，一帖 17–48 秒拿到完整评论 JSON。本机能直连时这个接口带请求头直接返回 JSON，免费。

- `shared/scripts/net.py` 新增 `pantip <帖子 URL> [--country TH]`：缓存 → 直连评论接口（境内模式跳过）→ Scrapeless v2 渲染（失败多试一次）；输出标题、主帖、评论（每条最多带 5 条回复，作者、日期、`#comment<N>` 链接），第一行「[来源]」，runner 的 `_page_text` 直接能读。缓存 `pantip_<帖号>.json`。
- 搜索服务 1.1.0 加 `POST /v1/pantip`；`net.py pantip` 在 `GEO_SEARCH_API` 下改调它，本地缓存照写。
- `precollect-channels.json` 的 `pantip` 从 `render: true` 改为 `fetcher: "pantip"`；`_collect_site` 对它只收 `pantip.com/topic/<数字>` 的帖子页、逐帖调 `net.py pantip`。每轮记账加 `render_pages`（经 Scrapeless 渲染的 Pantip 帖数，单价可能高于普通代理页）。
- 文档：community-channels 第 2、4、8 条，online-runner 的 precollect 段和境内服务器一节，TASK 模板和境内模式一节，API.md 加 `/v1/pantip`。
- 验证：`e2e_precollect` 第 9 项改为断言走 `net.py pantip`、只取帖子页、带 `--country TH`、不调无头 Chrome，30/30；`e2e_domestic_network` 加 D10（14/14）、`e2e_search_api` 加 P（12/12，均为真实调用）；validator 测试、verify_workflow、其余三个 e2e 照过；另在模拟境内环境跑了一次真实的泰国 precollect（内容与流媒体）：Pantip 取到 2 帖（30 条、5 条评论）、MyDramaList 2 页、搜索联想 22 条，37 秒。
- 顺带比较了 Google Shopping：Scrapeless 的 Google 搜索 Shopping 模式只返回商品列表、价格、星级和评价数，没有评价原文；搜商品这一步两家都约 0.001 美元一次，评价原文只有 DataForSEO 给（每商品约 0.0015 美元），所以 `collect_reviews.py google-shopping` 不换。

## 3.6.1（2026-11-11）Reddit RSS 403 时改读网页版；评价站可写 scope

触发依据：Suda 2026-11-11 问「Reddit 不能通过 Scrapeless 抓吗」，并指出 RTINGS 不是所有行业都用得上。实测当天 RSS 连续 403（单发也 403），Scrapeless 美国代理取**帖子网页版**能拿到（1.28 MB HTML，24 条评论，作者/点赞/日期/单条链接/正文齐全），**搜索页**经代理被拦（返回 blocked），Google 搜「reddit 关键词」能拿到帖子直链。

- `net.py reddit <帖子 URL> --proxy`：网页版取评论，解析 `<shreddit-comment>`；只有顶层评论，折叠的「N more replies」和主帖正文取不到；搜索词不支持（提示先 `net.py search`）。顺带修正境内模式的说法：RSS 连不上，网页版经代理可以。
- `run_selection_mode.py` 的 Reddit 渠道：RSS 搜索失败（403 或没有帖子）时改用 `net.py search "reddit <词>"` 拿帖子链接、按 URL 判相关性；读帖 RSS 失败时改 `--proxy`，一个渠道最多 `PRECOLLECT_PROXY_PAGES`=2 帖付费，额度用完的帖子在 reason 里写明。`summary.json` 的社区渠道多 `proxy_pages`。解析器兼容网页版的「作者 · N 赞 · 日期 · 链接」元信息。
- 渠道表加 `scope` 字段：RTINGS 只测它自己的约 28 个品类（电视、显示器、耳机、吸尘器、床垫、路由器、相机、跑鞋等），客户品类不在其中时计划里可以跳过并写原因；没写 scope 的固定渠道仍然不能跳。2026-11-11 实测 Bbrand 行车记录仪在 RTINGS 没有对应分类，那次「rtings 没有相关页面」是品类本身没有。
- `evals/e2e_precollect.py` 29 → 30 项：RSS 403 改网页版、网页版额度用完、写了 scope 的站可跳过。

## 3.6.0（2026-11-11）搜索服务：Scrapeless、DataForSEO 采集收成 HTTP 接口，密钥只放服务端

触发依据：研发 2026-11-11 书面反馈选词 skill 太复杂，搜索相关服务应集中、以接口提供；Suda 确认做「搜索能力接口」（整个选词不做成一个接口）。研发同日确认境内服务器能连 Scrapeless 和 DataForSEO。

- 新增 `shared/search-service/server.py`（标准库 HTTP 服务）和接口文档 `shared/search-service/API.md`：`/v1/health`、`/v1/fetch`（网页正文，进程内调 `net.py get()`）、`/v1/search`（Google 搜索，调新拆出的 `net.py search_text()`）、`/v1/run/{serp-signals|reviews|keywords|ai-answers}`（在服务端跑对应采集脚本，参数就是脚本命令行参数，输入文件和产物目录已有文件随请求上传，新增和改动的产物传回）。Bearer 令牌鉴权；拒绝绝对路径、`..`、`--out` 指向别处、未知工具、`keywords ledger`；`env` 只收 `DATAFORSEO_WHO`、`DATAFORSEO_CASE`。服务端缓存跨客户共享；按调用方产物目录留镜像（`out_key`，7 天清理），调用方超时断开后已提交的 DataForSEO 任务重跑能续上；DataForSEO 流水服务端记总账、同时传回调用方追加进本地流水。
- 新增 `shared/scripts/search_api_client.py`；`net.py fetch / search / reddit --proxy` 和四个采集脚本（`collect_serp_signals.py`、`collect_reviews.py`、`collect_keyword_data.py`、`geo-presales-report-builder/scripts/collect_answers.py`）在设了 `GEO_SEARCH_API` 时改调服务，命令和产物不变；`keywords ledger` 仍读本机流水。不设就是原来的本地直连。
- 采什么（行业 × 市场渠道表、种子词、相关性过滤、precollect 编排）和选词规则留在 skill，不进服务：这些规则改得频繁，放进服务每次都要研发发版。
- `run_selection_mode.py`：`net_env` 透传 `GEO_SEARCH_API`、`GEO_SEARCH_API_TOKEN`；搜索服务模式下不再要求本机有 Scrapeless key。
- 境内模式的 Reddit 说法和同日另一会话加的「帖子网页版经 Scrapeless 代理」对齐：RSS 连不上，帖子网页版（`--proxy`）照常可取；online-runner、community-channels、TASK 境内模式一节、`net.py` 说明同步改。
- 新增 `evals/e2e_search_api.py`（11 项）：本机起服务，服务端模拟只连得上两家接口、调用方没有任何密钥和外网，覆盖鉴权与输入检查、网页（含本地缓存命中不再请求）、搜索、关键词余额与沙盒、AI 回答采集、runner 整轮 precollect 与每轮记账、两边流水。首轮 K2 失败是测试模拟没放行 `sandbox.dataforseo.com`，放行后 11/11。原有 validator 测试、verify_workflow、e2e 照过。
- 改前快照：`.snapshots/search-api-20261111-141001/`。

## 3.5.1（2026-11-11）境内模式：服务器没有海外直连时只靠 Scrapeless 采集

触发依据：研发 2026-11-11 反馈选词 skill 最终部署在境内服务器，估计连不上外网；Suda 确认 `api.scrapeless.com` 境内能直接调、大模型用国内 API。本机实测（办公网绕开代理）：Scrapeless、DataForSEO 能连，Reddit RSS 返回 403；经 Scrapeless 网页代理能取到 Hacker News 接口和 Google 自动补全，取不到 Reddit。决定不建海外网关、不拆两套 skill，加一个环境变量开关。

- 新开关 `GEO_NET_DOMESTIC=1`（不设时行为不变）：`shared/scripts/net.py fetch` 不试直连和 Wayback，直接走 Scrapeless 目标国代理，代理偶发失败多试一次；`net.py reddit`、`net.py render` 不发请求，直接回「读不到：境内模式…」。`collect_serp_signals.py` 的自动补全改经 Scrapeless 代理取（每个种子词多付费 1 次，计入 `paid_calls`）。
- `net.py` 代理正文放行规则：接口返回的 JSON（以 `{` `[` 开头）不再因为短于 2000 字符被当成拦截页（本地模式同样受益，原来会退到 Wayback）；境内模式下正常的短页面也放行，只拦开头写着拒绝或人机验证的。
- `run_selection_mode.py`：`net_env` 显式透传开关；开关打开时 `TASK.md` 末尾加「境内模式」一节，告诉 agent Reddit、渲染页、DataForSEO 连不上时记未覆盖来源。
- `online-runner.md` 新增「境内服务器」一节：服务器只需连通 `api.scrapeless.com`（必须）和 `api.dataforseo.com`（连不上就缺评价和关键词量）。`community-channels.md` 加一条指向它。
- 新增 `evals/e2e_domestic_network.py`（13 项，真实调用 Scrapeless 约 20 次）：用死端口代理加 `NO_PROXY=api.scrapeless.com` 模拟服务器，覆盖网页、短 JSON、HN、搜索、搜索联想、对照组、prepare、precollect；首轮发现 example.com 这类短页面被误拦、HN 一次代理偶发失败，修后 13/13 通过，报告 `reports/domestic-network-e2e.md`。原有 validator 测试、verify_workflow、四个 e2e 照过。
- 研发同日确认境内服务器能连 `api.dataforseo.com`，境内模式下评价和关键词数据照常可用；连不通 Google、Reddit 等海外站点。
- 改前快照：`.snapshots/domestic-net-20261111-125036/`。

## 3.5.0（2026-11-11）线上 precollect 先判行业，评价和社区按行业 × 市场选渠道

触发依据：Suda 2026-11-11 指出 3.4.0 的 precollect 不分行业都采竞品 Trustpilot、不分市场都搜 Reddit，和 signal-sources.md 的行业表、市场表对不上；品牌资料 v2 没有行业字段，行业交给 AI 在官网调研时推。

- `run_selection_mode.py` 在 precollect 前加一步行业判断（`PLAN.md`，短 agent 调用）：取品牌和竞品官网首页存 `research/site/homepages.txt`，从新表 `references/precollect-channels.json` 选行业，填英文品类词、应用 ID、门店名，写 `research/precollect/plan.json`；新子命令 `check-plan` 检查，不过回喂一次（`PLAN-REPAIR.md`），仍不过退回默认渠道（竞品 Trustpilot + 市场社区），原因写进 `plan-checked.json`。
- 采哪些渠道由表定：行业行的评价、社区 + 市场行的社区；agent 只能跳过缺应用或门店的三个渠道，最多补 3 个。新增行业行「开发者工具与云基础设施」「消费级软件与在线服务」「本地生活与门店」，signal-sources.md 行业表同步补行。
- 评价渠道：`collect_reviews.py` 五个子命令按计划调（应用商店、Google Shopping、Google 地图带 `--country`、`--lang`）；Capterra、TrustRadius、Clutch、Alibaba、RTINGS 这类评价站先用「站名 + 竞品名或品类词」搜出本站页面（Scrapeless 的 Google 搜索不认 `site:`，实测返回的全是别的站；竞品模式还要求网址含竞品名，防止搜到名字相近的别家产品），再取前 2 页正文存 `research/precollect/pages/`，原话由 agent 摘出来登记。社区渠道：Reddit（沿用 3.4.0）、Hacker News Algolia 评论（只留提到竞品或两个品类词的）、本地论坛站内页（Pantip 走无头 Chrome）。
- 登记检查把页面数算进去：某类只采到页面、没登记也没说明时同样回喂返修。`summary.json`、`result.json` 的 precollect 块加 `industry`、`plan_source`、`pages`。
- `shared/scripts/net.py search` 每条结果多打一行「链接：<完整网址>」，precollect 按它取站内页。
- 三类采集并行、同类渠道并行；评价一类最多 10 分钟（DataForSEO 评价任务排队慢，Google Shopping 一个词 4 个任务实测 15 分钟没出完），超时渠道在 `rerun.txt` 留重跑命令，主 agent 重跑直接取结果、不重复付费。
- 实测（2026-11-11，判行业用 DeepSeek flash）：一家 GPU 云客户判为「开发者工具与云基础设施」（69 秒），Trustpilot 45 条、Hacker News 37 条，Capterra、TrustRadius 没有竞品档案；一家行车记录仪客户判为「消费电子与智能家居」（98 秒）并自己补了 Trustpilot。当天本机 Reddit RSS 返回 403，两家社区都靠 agent 补采，原因写进了 summary。
- `evals/e2e_precollect.py` 15 → 26 项：云基础设施、流媒体、行业写错退回默认、泰国 Pantip、跳过固定渠道被拒、只有页面的登记检查。

## 3.4.0（2026-11-10）线上 runner 固定采集评价、社区、搜索联想，审核加调研缺口条

触发依据：Suda 2026-11-10 指出线上售前诊断一次性生完词、没有主会话，生成和审核用的都可能是 DeepSeek，3.3.7 写的「调研怎么收尾」三条判断在线上没人执行；实测 DeepSeek 调研会偷懒——评价一条不采、社区只搜一两次就停。改法是把「采不采」从模型手里拿走：

- `run_selection_mode.py` 新增 `precollect` 步骤（也可单跑 `precollect --out <工作目录>`）：agent 启动前由 runner 跑 `collect_serp_signals.py`（品类种子词的 PAA、相关搜索、自动补全）、`collect_reviews.py trustpilot`（每个竞品域名约 40 条）、`net.py reddit`（先用竞品名对比和品类推荐问法搜帖，再读最相关的 3 帖评论，最多占 5 次 Reddit 请求）。每类单独超时 6 分钟、单独失败不影响其他类，产物合并到 `research/precollect/signals.csv`，成败原因写 `summary.json` 和 `out/result.json` 的 `precollect` 块。
- 种子词只取产品线冒号前的短名（规格里的型号会把种子带偏：实测取全文前 6 个英文词得到「gpu gpu instances nvidia rtx pro」，PAA 全是显卡对比、Reddit 选中笔记本帖）；Reddit 选帖要求提到竞品，或命中两个以上不同品类词，只撞上一个泛词不算。
- TASK.md：先读 precollect 结果、只对缺口补采；登记口径从「只登记撑起题的那几条」改为「登记与本产品线相关的信号」；`来源类型` 照抄、`出处` 写完整 URL，不写「同上帖」。
- finalize 新增登记检查：precollect 某类采到了、`buyer_quotes` 里这一类一条没有、`notes.md`「未覆盖来源」也没说明的，作为返修报错回喂；最后一轮仍缺只记 warning，不触发删题。
- `review-rubric.md` 加第 9 条「调研有没有明显缺口」（非阻塞，`question_id` 写 `-`）；runner 解析审核结果时第 9 条一律按非阻塞处理，`-` 不进删题逻辑。
- `community-channels.md`：Reddit 改两步取（搜索只给主帖，评论要单帖 URL）；加 Hacker News（Algolia 接口直连）；Trustpilot 规定走 `collect_reviews.py`，不抓网页；B2B 软件评价站实测更新——G2 被 DataDome 拦、代理和无头 Chrome 都不通，Capterra、TrustRadius 走代理能取到完整评价但要先确认产品有档案。
- `client-facing-base.md`：需求信号「出处」每行写全、来源名放最前，禁止「同上帖」简写（行序会变、来源类型会被认错）。
- `online-runner.md`：写明 precollect、Reddit 两步取、B2B 评价站通道。
- `geo-presales-report-builder/scripts/collect_answers.py`：Scrapeless key 读不到环境变量时回落到 macOS 钥匙串（与 net.py、collect_serp_signals.py 一致）；同事本机把 key 存在钥匙串里时，试跑和预跑之前会直接报缺 key。
- 新增 `evals/e2e_precollect.py`（15 项，用假采集脚本，不联网）；`e2e_repair_loop`、`e2e_review_loop`、`e2e_input_contract`、`verify_workflow`、validator 测试全部照过。
- 改前快照：`.snapshots/research-optimize-20261110-204740/`。

## 3.3.8（2026-11-10）补需求调研的退出规则，区分外部调研与内部数据

触发依据：Suda 2026-11-10 发现一单 GPU 云客户的调研严重不足——只查了 2 次 Reddit、评价类一次没采，而 skill 第 2 步只写「四类来源都要看」，没有任何退出标准。先加了一版硬门禁（连续 2 个来源零新增、每个约束至少 1 条信号、四类各触达一次、最多 3 轮 × 6 来源、W65 按来源数量告警），Suda 指出这版过度工程化：来源质量不同，低质量来源连续零新增不代表需求已覆盖；一条买家原话常同时含多个约束，机械补证据会逼出凑数。改为轻量退出机制。

- `selection-rules.md` §2「收需求信号」：原「四类来源都要看」改为「外部调研三类来源，内部数据另算」——外部是搜索数据、评价、社区（推荐不强制，行业不适用可跳并写原因），销售/客服属品牌方内部数据，售前不收、售后选填。
- 新增「调研怎么收尾」：三条停止判断——需求覆盖（主要目标客户和使用场景无遗漏）、证据质量（重要需求有可追溯来源，推断标假设）、增量价值（继续搜不会显著改变矩阵）；按轮推进最多 3 轮，第二轮只查缺口不重搜，到上限记录未覆盖项后进下一阶段。明确写「不按来源条数判断覆盖」，区分已验证与待验证假设。
- `validate_after_sales_set.py`：撤掉当天早先加的 W65（按来源数量告警），与轻量规则一致。
- 改前快照：`.snapshots/merge-audience-rows-20261110-*/`。

## 3.3.7（2026-11-10）主题划分改为三问标准，允许按受众或场景拆分

触发依据：Suda 2026-11-10 看一单 GPU 云客户时指出，原定义「主题 ＝ 同一类候选 × 同一意图类型」太严：GEO 行业里 Profound、Aleyda、Peec 都按目标客户和使用场景划分 Topic，即使推荐的是同一类产品。原定义会把这单的初创团队、个人创作者、3D 渲染强行并成一个主题，掩盖三类买家的竞争格局差异（实测：三组题的头名各不相同，3D 渲染题平均只列 3.5 家并混入渲染农场）。

- `selection-rules.md` §6「主题是什么」：定义改为「值得独立监测和优化的一组买家需求」；新增「拆不拆看三个问题，不要求全满足」——竞争格局不同 / 评价标准不同 / 优化方向不同，任一成立即可按目标客户或使用场景拆；新增「先按候选类别初聚，再判断要不要细分」「矩阵要全，主题不必跟着碎」「不因为名字不同就拆」三条防碎片化约束。
- `selection-rules.md` §6「怎么聚」：初聚后按三问过一遍；「放不放在一起只看候选是不是同一类」拆成两条——候选类别变了必须拆（硬性），候选类别相同但三问有实质差异的也可以拆，并写入这单的实测数据作为例子；「产品类型、客群、场景是条件性拆分维度」改为「客群、场景要按三问判，不按名称拆」；发现题分主题那条补上三问判断。
- `selection-rules.md` 硬要求 3 第 3 步：合并条件从「候选同类即可合并」改为「候选类别相同且三问都答不出差异才合并」，并写明三问有差异的主题不合并、题不够走混合选择。
- `SKILL.md` 第 6 步、`client-facing-base.md` 主题章节说明同步。
- 改前快照：`.snapshots/merge-audience-rows-20261110-*/`。

## 3.3.6（2026-11-10）品牌别名改收「认不出的写法＋不含品牌名的自有产品」，产品提及计入母品牌

触发依据：Suda 2026-11-10 定口径「不含品牌名的子品牌和产品，提及计入母品牌」（与 Profound Asset Hierarchies 一致，原文「every mention of a sub-asset also counts toward OpenAI, the parent brand」）；同日基线读数证明别名会改变提及数：同一套识别去掉全部别名，Abrand 提及少 7%、Tbrand 少 5%，Bbrand 不变。另外本 skill 两处说法与 PRD 矛盾：`input-contract.md` 写「产品系列名和型号不从品牌方收」，PRD 和研发文档写的是品牌别名包含产品系列名。只改字段说明，字段名、表单、`normalize_case.py` 不动。

- `input-contract.md`「品牌别名」与 `client-facing-base.md` 业务范围「品牌别名」改为：
  - 收：品牌名本身认不出的写法（全称、简称或缩写、旧名、本地语言名），以及不含品牌名的自有产品名和子品牌名（如 LG 的 PuriCare），提到它们也计入本品牌提及。
  - 不用填：带品牌名的产品名、只差大小写或空格的写法、型号清单、通用品类词。
  - 易混淆名称加上「被收购后单独经营的品牌」。
  - 收录规则以 `geo-metrics` SKILL.md「品牌词表」为准。删掉「产品系列名和型号不从品牌方收」。
- 同步：`geo-metrics` 的 SKILL.md「品牌词表」、`metric-scope-and-copy-contract.md` 新增「品牌提及率」定义行；`10-售前诊断报告/PRD/售前选词工具PRD.md`、`售前诊断-选词模式生词研发改造需求-20261029.md` 的「品牌别名」行。
- 同日收窄（Suda）：产品名只收「经常被单独提起、不带品牌名的」。总写成「LG PuriCare」的靠品牌名就能认出，加别名不改变提及数。五处说明同步改。飞书《AI 搜索监测｜品牌资料收集》「品牌别名」行已按此改（rev 603–605，示例换成旧名、缩写、常被单独提起的自有产品）；回读核对表格 24 行只变了这一行。
- `check_skill_terms.py` 加退役说法「产品系列名和型号不从品牌方收」「常见拼写和空格变体」。
- 「只差大小写或空格的写法不用填」依赖 `geo-metrics` 的识别规则 1（分隔符），该规则 11-10 已验证、待落盘（`docs/exec-plans/active/brand-recognition-rules-progress.md`）。落盘前，空格变体仍要靠别名。
- 改前快照：项目根 `.snapshots/*.20261110-193203.bak`。

## 3.3.5（2026-11-10）业务范围删「目标客户与使用场景」与「社区平台与信源服务」两行

触发依据：Suda 2026-11-10 看一单客户的对客表时指出两处重复与冗余。一、「核心目标客户与购买场景」和「目标客户与使用场景」内容几乎一样，品牌方本来就写在一起，没必要在业务范围拆两遍；二、「社区平台与信源服务」不该出现在对客的业务范围表里。

- `client-facing-base.md` §业务范围：多值行删「目标客户与使用场景（n）」，只剩产品线、核心目标客户与购买场景、竞品、差异化优势；「核心目标客户与购买场景（n）」改为唯一一组客户行，品牌方怎么写就怎么记、不拆不并，我方调研新增的处境另起一行并写依据，拆并留到画矩阵时做；删「社区平台与信源服务」这一行，我们填的只剩「品类」；行序、幂等去重那句里的举例同步，「目标客户」「使用场景」两列的选项来源改成「从核心目标客户与购买场景拆出来」。
- `selection-rules.md` 第 1 步「品类、目标客户与使用场景由我们填」改为「品类由我们填；目标客户和使用场景在第 4 步按调研从核心目标客户与购买场景拆出来」；第 2 步官网表「预填业务范围的目标客户与使用场景」改指核心目标客户与购买场景；第 4 步末条改为场景和目标客户直接写进矩阵行，不回头改写业务范围那几行。
- `SKILL.md` 开头摘要与第 4 步表格同步；`online-runner.md` 第 4 步同步。
- 改前快照：`.snapshots/merge-audience-rows-20261110-*/`。

## 3.3.4（2026-11-10）业务范围补「AI 平台」字段，改由品牌方选

触发依据：Suda 2026-11-10 指出业务范围表漏了「AI 平台」字段。飞书《品牌资料收集》第一部分和《AI 搜索监测确认表（模板）》里都有这一项，线上 runner 也已经按「表单『AI 平台』里客户选的」跑研究预跑，只有 skill 的字段定义没跟上：写的是「平台」，而且归我方填，跟另外三处对不上。

- `client-facing-base.md` 业务范围：单值行和品牌方填的字段列表加「AI 平台」，我们填的列表删掉「平台」；加字段说明——品牌方在资料收集文档里选本期监测哪些平台，可多选，默认 ChatGPT、Gemini、Google AI Overview、Google AI Mode，需要时加 Perplexity、Copilot、Grok、Alexa（平台名见 `collect_answers.py` 的 `ALL_PLATFORMS`）；线上传给 `--platforms`，研究预跑只在这些平台上各跑 1 次，各平台结果分开统计、不合成一个分数。行序里「平台」移到品牌方填的一段。
- `selection-rules.md` 第 1 步：「每期只收一个市场、一种语言、一条产品线，监测的 AI 平台由品牌方选」；「品类、平台、目标客户与使用场景由我们填」删「平台」。
- 飞书《AI 搜索监测｜品牌资料收集》的「AI 平台」行第二列原来只有平台名，补成说明加可选项（rev 601），字段名「AI平台」按中文排版补空格（rev 602）；《AI 搜索监测确认表（模板）》业务范围【示例】平台改【示例】AI 平台，内容改多平台示例，「为什么重要」改「品牌方选、各平台结果分开看」。
- `check_skill_terms.py` 加退役说法「品类、平台、目标客户与使用场景」。
- 改前快照：项目根 `.snapshots/client-facing-base.md.20261110-185404.bak`、`.snapshots/selection-rules.md.20261110-185404.bak`、`.snapshots/CHANGELOG.md.20261110-185404.bak`。

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

3.0.0 之前的记录见 [CHANGELOG-archive.md](CHANGELOG-archive.md)。
