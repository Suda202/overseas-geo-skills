#!/usr/bin/env python3
"""选词的线上一条命令入口：品牌资料（表单数据或文件）→ 每个市场一批 5 字段的题（Suda 2026-10-29；
2026-11-06 随售前生词并入选词 skill）。参数名 --case、文件名 case-normalized.json、normalize_case.py
里的 case 是历史命名，正文一律叫品牌资料（3.3.0）。

规则见 references/online-runner.md 和 references/selection-rules.md。本脚本把
确定性的部分包起来，中间的调研和写题交给 agent：

    prepare   归一化品牌资料，建独立工作目录（skill 拷贝、inputs/、TASK.md）
    行业判断  precollect 前先跑一次短 agent（PLAN.md，3.5.0）：取品牌和竞品官网首页（存 research/site/，给后面
              官网调研接着用），从 references/precollect-channels.json 选行业，填英文品类词、应用 ID、门店名等参数，
              写 research/precollect/plan.json；runner 检查（check-plan）不过回喂一次，仍不过退回默认渠道。
              要采哪些渠道由表决定（行业行 + 市场行），agent 只能跳过缺应用或门店的渠道、补渠道表里的站（最多 3 个，行业写「其他」时 5 个）和表外的站（add_sites，最多 2 个）
    precollect agent 启动前由脚本按渠道计划固定采集三类公开信号，采不采、采多少不交给 agent（3.4.0）：
              搜索联想（collect_serp_signals.py，2–3 个发现型种子词）；评价按行业（collect_reviews.py 的
              Trustpilot / Google Shopping / 应用商店 / Google 地图，或评价站 site: 搜索后取页面正文）；
              社区按市场（Reddit 搜索后读最相关的 3 帖、Hacker News 评论、本地论坛站内页）。每类单独超时
              （评价 10 分钟、其余 6 分钟）、单独失败，三类之间和同类渠道之间并行；失败只记原因不中断 run；
              产物在 research/precollect/，合并表 signals.csv
              多一列「采集类别」，页面正文在 pages/
    agent     在工作目录里让 agent 按 TASK.md 调研、写 out/bank.json
    finalize  跑选词 validator 和导出脚本，写 out/result.json；再做登记检查（runner 层，不是 validator 门禁）：
              precollect 采到（status=ok 且 ≥1 条）的类别，config.buyer_quotes 里一条该来源类型都没有、
              notes.md「未覆盖来源」也没写这一类时记一条错误，走返修；最后一轮返修仍缺只记 warning，不删题
    返修      run 里检查没过而 out/bank.json 存在时，把报错原文写成 REPAIR-<n>.md 回喂 agent 再
              finalize，默认最多 2 轮（--repair-rounds，0 关闭）；最后一轮授权 agent 丢题不丢库
              （改不好的题删掉、题号进 config.retired，每个主题仍只放一种意图类型）
    补题      检查通过但导出不到 30 道时，写 TOPUP.md 让 agent 补一轮（3.13.0，--repair-rounds 0 时不补）：先开我方
              补充的中档行和假设行，再用低档行，不许同义改写；补完没过检查就退回补题前的题库；仍不到 30 道照常交付，
              result.json 记 top_up {before, after, status} 和一条 warning
    审核      首次 finalize 通过后，新开一个审核 agent 按 references/review-rubric.md 九条核对题库，
              发现写进 out/review.json；blocking 的发现写成 REVIEW-REPAIR-<n>.md 回喂返修、再 finalize、
              只复核报过的题，默认 1 轮（--review-rounds，0 关闭；不占 --repair-rounds 额度）。
              review.json 缺失、坏掉或审核 agent 超时只记 warning，不挡交付（3.2.0）

    python3 run_selection_mode.py run --case payload.json --market US --platforms chatgpt,gemini --out <工作目录> --agent sdk
    python3 run_selection_mode.py run --case payload.json --market US --platforms chatgpt --out <工作目录> --agent-cmd "<命令>"
    python3 run_selection_mode.py prepare  --case payload.json --market US --platforms chatgpt --out <工作目录>
    python3 run_selection_mode.py precollect --out <工作目录>     # 对已 prepare 的目录单独补跑采集
    python3 run_selection_mode.py check-plan --out <工作目录>     # 检查行业判断写的 plan.json
    python3 run_selection_mode.py finalize --out <工作目录>

run 带 --task-file（只用于测试）时不跑 precollect，除非设了 PRECOLLECT_SCRIPTS_DIR（测试用假采集脚本目录，
默认用工作目录里拷贝的 .agents/skills/shared/scripts）。

一次只跑一个市场；选了几个国家/地区就调几次，每次一个新工作目录。
--platforms 传表单「AI 平台」选中的平台（collect_answers.py 的平台名，逗号分隔）：研究预跑只在
这些平台上各跑 1 次，客户没选的平台不采。

agent 两种接法：
  --agent sdk       内置 Claude Agent SDK 适配（pip 包 claude-agent-sdk）。环境变量：
                    ANTHROPIC_BASE_URL、ANTHROPIC_API_KEY（模型网关）、AGENT_MODEL（模型名）；
                    审核 agent 用 AGENT_REVIEW_MODEL，没设就用 AGENT_MODEL。
  --agent-cmd "…"   宿主自己的 harness：在工作目录里用 shell 执行，环境变量 WORKSPACE、
                    TASK_FILE 指向工作目录和任务说明；命令结束后应已写出 out/bank.json。审核轮 TASK_FILE
                    指向 REVIEW.md（或 REVIEW-<n>.md），应写出 out/review.json；模型由宿主定。
调研要用的密钥照常放环境变量：SCRAPELESS_API_KEY、DATAFORSEO_LOGIN、DATAFORSEO_PASSWORD。
Reddit 限量：agent 里的 net.py reddit 每个工作目录最多 NET_REDDIT_MAX 次联网请求（默认 10，约 10 分钟），
计数在 logs/reddit_calls；宿主可用同名环境变量改。
DataForSEO 按人记账：宿主把发起这次选词的同事姓名放进 DATAFORSEO_WHO；没传时记成「线上选词（未传调用人）」。
DATAFORSEO_CASE 没传时自动填「品牌 市场」。流水在服务端 ~/.dataforseo/ledger.jsonl（DATAFORSEO_LEDGER 可改），
用 shared/scripts/collect_keyword_data.py ledger 汇总。

产物（都在工作目录里）：
  out/bank.json        题库 JSON（内部底稿）
  out/upload/*.csv     交给线上的 5 字段题（每个市场一份）
  research/precollect/ precollect 产物：serp/、reviews/、community/ 各类原始产物，summary.json（每类
                       {status: ok|failed|skipped, reason, rows, out_dir}），signals.csv（三类去重合并，加「采集类别」列）
  out/result.json      {status, market, locale, upload_files, prompt_count, topics, repair_rounds, precollect, review,
                       costs, errors…}；precollect 是每类采集状态与行数
                       review 是审核块（3.2.0）：{rounds, blocking_found, nonblocking_found,
                       status: passed/repaired/skipped/review_failed, reason, warnings, nonblocking…}
                       costs 是本轮记账（3.1.0）：LLM usage 加总、Scrapeless 请求数、DataForSEO 流水，只记数量
                       不乘单价；按客户算钱用 shared/scripts/cost_report.py（单价读本机 ~/.geo-cost/prices.json）
  logs/                agent 记录（返修轮带 -repair<n> 后缀；agent-run*.json 含 SDK 的 usage）、两个检查与导出的原始输出
  logs/net_cache/      本轮 net.py 缓存（NET_CACHE_DIR），代理页数和搜索次数从这里数
  REPAIR-<n>.md        每轮返修回喂 agent 的任务（报错原文在里面）
  REVIEW.md、REVIEW-<n>.md、REVIEW-REPAIR-<n>.md  审核、复核、审核返修的任务；out/review.json 是最近一轮
                       审核的发现，logs/review-<n>.json 存每轮原件

退出码：0 生词成功；1 生词失败（agent 出错、超时，返修轮次用完检查仍没过，或审核返修轮次用完仍有阻塞发现且
删掉这些题后检查仍没过、或发现没写题号删不了，原因见 result.json）；
2 输入或环境有错（品牌资料归一化不过、参数错、缺 SCRAPELESS_API_KEY），不启动 agent，errors 原样在 result.json。

可能出错的地方（本脚本针对的就是这些）：
  1. 品牌资料缺必填字段 → prepare 停下，不启动 agent，errors 原样交回
  2. agent 没写出 bank.json、超时或异常退出 → 没有 bank.json 就失败，不返修、不拿半成品导出
  3. 题库没过选词 validator（含主题都有题、一个主题一种类型）或导出检查（超 60 条、字段缺、类型不对） → 回喂报错返修（最多 --repair-rounds 轮），仍没过才失败，报错原文进 result.json
  4. 题库的市场和传入的 --market 不一致 → 同样走返修（agent 改 region），仍不一致才失败
  4b. --platforms 里有采集器不认识的平台名 → 输入错误，不启动 agent
  5. 工作目录已存在 → 拒绝覆盖，避免两次运行（品牌 × 市场）共用一个目录
  6. 没有 SCRAPELESS_API_KEY → agent 采不了研究预跑会凭空写题，启动前就停下
  7. 审核 agent 没写 review.json、写坏了、结构不对或超时 → review.status=review_failed，记 warning，照常交付
  8. 审核 agent 违规改了 bank.json → 恢复审核前的题库并记 warning
  8b. 题太少（不到 30 道）→ 补一轮；补坏了退回原题库，补不到照常交付并记 warning
  9. 审核返修把检查改坏 → 下一轮审核返修把检查报错和未修的阻塞发现一起回喂，额度用完才失败
  10. agent 不采评价、社区只搜一两次就交题库 → precollect 由脚本固定采；采到了却一条没登记 → 登记检查回喂返修
  11. 不分行业都采 Trustpilot、不分市场都搜 Reddit → 先判行业，渠道按表（行业 × 市场）定；行业判错或
      plan.json 两次不过 → 退回默认渠道（竞品 Trustpilot + 市场社区），原因写进 plan-checked.json，agent 按表补采
  11. precollect 某类缺凭据、超时或被挡 → 该类 status=failed 带原因，其他类和 agent 照常跑，该类不做登记检查
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS = SKILL.parent
# 预采集（渠道计划检查、三类采集、登记检查）在 precollect.py（3.7.0 拆出）；python3 -I 下脚本目录不在 sys.path，显式加上
sys.path.insert(0, str(HERE))
from precollect import (PLAN_TIMEOUT, PRECOLLECT_DIR, check_plan, domestic, fallback_plan, load_channels,  # noqa: E402
                        net_env, precollect, precollect_block, precollect_registration_errors)
# 整个拷贝的 skill：选词本身、shared 的联网与信号脚本。
# geo-monitoring 不拷（3.0.0）：线上不试跑、不采集。
SKILL_DIRS = ("geo-prompt-selection-builder", "shared")
# 只拷一部分的 skill（3.0.0）：研究预跑只用 geo-presales-report-builder/scripts/collect_answers.py，
# 它在导入时还要 geo-metrics 的 geo_presales_core 包和 geo-presales-crawl-integrity 的
# audit_crawl_integrity.py（后者读同 skill 的 references/platform-contract.json 覆盖平台合同）。
# 这是让 collect_answers.py 能在工作目录里跑起来的最小集合。
PARTIAL_COPIES = (
    ("geo-presales-report-builder", "scripts"),
    ("geo-metrics", "scripts/geo_presales_core"),
    ("geo-presales-crawl-integrity", "scripts/audit_crawl_integrity.py"),
    ("geo-presales-crawl-integrity", "references/platform-contract.json"),
)
# legacy = 已归档的旧规则，不给 agent 看，免得混用两套口径
# client-facing-base.md = 只用来建对客确认表，线上不写这张表，不拷贝（省 ~31KB 上下文）
# demand-side-signals.md = signal-sources.md 里「客户提供什么」等品牌方数据小节，线上没有客户数据
IGNORE = shutil.ignore_patterns(".snapshots", "__pycache__", ".pytest_cache", "*.bak", "evals", "reports",
                                "*.local.json", "build", "legacy",
                                "client-facing-base.md", "demand-side-signals.md", "CHANGELOG*.md", "runner-ops.md",
                                # lark-cli 在 skill 目录里落下的 Base 导出（客户数据），线上不需要
                                "tbl*.ndjson", "tbl*.manifest.json", "tpl_*.manifest.json")
DEFAULT_TIMEOUT = 120 * 60
# 与 geo-presales-report-builder/scripts/collect_answers.py 的 ALL_PLATFORMS 一致
KNOWN_PLATFORMS = {"chatgpt", "perplexity", "copilot", "gemini", "aimode", "overview", "grok", "alexa"}

TASK = """你在一个无人值守的流水线里，没有人会回答问题。遇到歧义按最合理的判断继续，把假设写进 `out/notes.md`。

任务：给这个品牌生成一批提示词。先读 `.agents/skills/geo-prompt-selection-builder/references/online-runner.md`（线上和本地不一样的地方），再按 `.agents/skills/geo-prompt-selection-builder/references/selection-rules.md` 第 1–8 步逐步做。只做到校验与导出，不试跑、不写对客确认表。

以前客户积累的经验：读 `.agents/skills/geo-prompt-selection-builder/references/industry-knowledge/` 里本行业的「行业-<行业>.md」（行业写在 `research/precollect/plan-checked.json` 的 `industry`），再挑一份和本客户品类最接近的「品类-<品类>.md」（看「行业-」文件里的已有品类列表，按英文品类词判断，没有接近的就不读）。约束条件、目标客户、场景、主题看品类那份，渠道效果看行业那份。它们只是假设级线索：帮你少漏，每条都要用本客户的买家信号核实，本客户没有信号的不硬加，不能写成依据。

线上跳过不读：
- 文档里指向 `geo-monitoring` 的链接是采集阶段（试跑、基线），线上不读，工作目录里也没有这个 skill。
- selection-rules.md 里这几处线上跳过：对客确认表（第 8 步回读行数、「交付」里的对客确认表，以及所有指向 client-facing-base.md、demand-side-signals.md 的说明，工作目录里没有这两份）；第 6 步「售后重聚」。

题量（selection-rules.md 第 7 步「出几道」）：
- 候选题一个市场 × 一条产品线 30–60 道。超过 60 是硬限（validator 门禁 47 和导出都报错，控制成本），写到 60 道就停，超出先砍业务优先级为中的行里证据最弱的题。不到 30 不凑题；检查通过后脚本会补一轮题，补不到也照常交付。
- 主题个数不限；发现主题每个至少 10 道，60 道里最多 6 个满额主题。

输入：
- `inputs/case-normalized.json`：归一化后的品牌资料。竞品用品牌资料里客户填的，不自己增删。主题一律由你从矩阵行聚出，个数不限。品类名从「产品线」和官网推出，写进 `config.category_label`。
- 题型：只出发现题。品牌资料里的「核心目标客户与购买场景」是品牌方点名的处境，对应的行判高、我们补充的判中；填写先后只用于主题同档排序。
- 市场：`{market}`；语言：`{locale}`。所有题的 `region` 写 `{market}`，`config.collection_config` 写 `{{"market": "{market}", "language": "{locale}"}}`。

需求信号（必填）：
- runner 在你启动前已判断品牌所在行业、按行业和市场选好评价站与社区并采了一轮：行业、依据和每个渠道采不采、为什么跳过在 `research/precollect/plan-checked.json`；评价、社区、搜索联想的原话合并在 `research/precollect/signals.csv`（`采集类别` 列标明哪一类）；评价站和本地社区的页面正文在 `research/precollect/pages/`，这一类没有拆成原话，读完把买家原话登记进去，出处写页面网址；各类状态和失败原因见 `research/precollect/summary.json`。品牌和竞品官网首页已取过，在 `research/site/homepages.txt`，第 2 步官网调研从这份接着看。先读完这些再决定还要不要补采；不要重复采同样的来源（同一批竞品域名、同样的种子词、已读过的帖子和页面）。计划里跳过或采失败的渠道，能补就按 signal-sources.md 补，补不了写进「未覆盖来源」；评价渠道超时的，任务已经提交过，在你写题前重跑 `research/precollect/reviews/<渠道>/rerun.txt` 里的命令就能取到结果、不重复付费。
- 登记与本产品线相关的信号，写进 `config.buyer_quotes`；撑不起任何题的也可以登记，用来说明买家在意什么。`research/precollect/signals.csv` 里与本产品线相关的都要登记。一条一个对象：`{{"输入编号": "<市场前缀>-R001", "来源类型": "<评价 / 社区 / 搜索联想 等，precollect 来的照抄文件里的值>", "原话": "<买家原话原文，不要翻译>", "目标客户": "<谁在问，看不出留空>", "约束条件": "<这条信号能证明题面哪些条件，关键词写法>", "出处": "<完整 URL，不要写「同上帖」之类的简写>"}}`。
- precollect 某类失败（summary.json 里 status 为 failed）的，写进 notes.md「未覆盖来源」并带上 summary.json 里的原因。某类采到了但全部与本产品线无关、一条不登记的，也在「未覆盖来源」写出类别名和理由；否则结束检查会要求返修。
- 约束那一列的键名就是 `约束条件`，和对客 Base 列名、`signals.csv` 一致。
- 题的 `evidence_refs` 填它引用的信号编号（如 `["US-R003"]`），不要填别的题的题号。题面带条件却挂不上任何原话时，在 `condition_basis` 里写 `{{"<条件>": "<依据>"}}`，不许留空。
- 一条原话可以撑多道题。没有条件、也没有标题面的题可以不引用。
- 线上没有品牌方提供的资料（销售、客服、GSC、关键词工具），只收公开层（评价、社区、搜索联想）。

联网：
- 不用 WebSearch / WebFetch。搜索和取网页用 `.agents/skills/shared/scripts/net.py`，取网页一律 `net.py fetch <url> [<url> ...] --country {market}`，要读的页面攒成一批一次传（脚本并发取），被拦的页面不要再试 `render`；Pantip 帖子用 `net.py pantip <帖子 URL> --country TH`（取标题、主帖和评论）；Reddit 本次最多 {reddit_max} 次联网请求（`net.py reddit` 到上限会提示，precollect 已用掉一部分），先挑最相关的版块和帖子，读不到的记进未覆盖来源；搜索信号、关键词数据、评价用同目录的 `collect_serp_signals.py`、`collect_keyword_data.py`、`collect_reviews.py`（precollect 采过的种子词、竞品域名、帖子不要再采）。
- 研究预跑只在客户选的平台上跑：`python3 .agents/skills/geo-presales-report-builder/scripts/collect_answers.py --questions research/prerun.csv --out research/prerun --regions {market} --platforms {platforms}`。不要加别的平台。
- 没有带登录态的浏览器。要登录或通道表里标「不通」的站跳过，按 online-runner.md「线上没有浏览器」一节处理，写进 notes.md 的「未覆盖来源」。
- 调研过程文件都放 `research/`。只在本工作目录里读写，不要访问工作目录以外的路径。

交付（只写这两个路径）：
1. `out/bank.json`：题库 JSON，字段按 `.agents/skills/geo-prompt-selection-builder/references/output-contract.md` 和 online-runner.md。
2. `out/notes.md`：简短记录，分这几节：「预跑答案」（研究预跑的答案目录和每个平台是否采到）、「目标客户」、「使用场景候选」（每个场景推理的解决方案类型、品牌能否满足、回答里会不会出现品牌这一类）、「约束条件」、「需求信号」（`config.buyer_quotes` 登记了几条、各是什么来源类型、哪些题引用了它们、哪些题的条件只靠 `condition_basis`）、「没开的格子」（矩阵里没开的格子和原因）、「主题」（每个主题为什么成立）、「假设」、「未覆盖来源」、「validator 告警」。

结束前依次运行，两条都要退出码 0；有错就改题库再跑：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""

PLAN_TASK = """你在一个无人值守的流水线里，没有人会回答问题。遇到歧义按最合理的判断继续。

这一步只做一件事：判断品牌所在行业，决定 runner 去哪些评价站和社区预采买家原话，写出 `research/precollect/plan.json`。不写题，不做别的调研，10 分钟内完成。

1. 读 `inputs/case-normalized.json`：品牌、产品线、竞品、核心目标客户与购买场景。
2. 一次取完品牌官网首页和竞品官网首页，存下来给后面的官网调研接着用：
   `python3 .agents/skills/shared/scripts/net.py fetch <品牌官网> <竞品官网 …> --country {market} > research/site/homepages.txt`
3. 读 `.agents/skills/geo-prompt-selection-builder/references/precollect-channels.json` 和 `.agents/skills/geo-prompt-selection-builder/references/signal-sources.md`「按行业收评价和社区」。按品牌卖什么、卖给谁，从 `industries` 里选一个行业，键名原样照抄；行业看品牌本身，不看竞品。一个都不合适就写「其他」，按品牌卖什么、买家在哪里讨论和评价，自己推理该采哪些渠道：在 add 里挑渠道表里有的（最多 5 个），表里没有的站写进 add_sites（最多 2 个）。
4. 本行业的「评价」「社区」，加上市场 {market} 在 `markets` 里的社区（没有这个市场就用 `_default`），就是 runner 要采的渠道，都会采，不能删。只有两种情况能写进 skip 并说明原因：要参数的三个渠道（google-play、app-store 要应用 ID，google-maps 要门店名）在品牌和竞品都没有 App、没有门店时；渠道表里写了 `scope` 的站（如 rtings 只测它自己的那些品类），品牌的品类不在 scope 里时。表里这一行没写、但这个品牌明显该采的，从 `review_channels`、`community_channels` 里挑，写进 add，最多 3 个，写原因；渠道表里没有的站（比如这个品类的专业评测站、垂直论坛），写进 add_sites，最多 2 个，runner 会用「站名 品类词」搜出本站页面再取正文。规则没写到的情况按这一步的目标自己推理，依据写进 industry_basis 或原因里。
5. 要采 Google Play 或 App Store 的，找品牌和竞品的应用 ID：先看官网首页里的应用商店链接；没有再用 `python3 .agents/skills/shared/scripts/net.py search "<名称> app store" --gl {gl} --hl {lang}`（Scrapeless 的 Google 搜索不认 `site:`），搜索一共不超过 3 次。要采 Google 地图的，在 maps_queries 写竞品门店的「店名 城市」。

plan.json 的格式（除 industry、industry_basis 外都可省略）：
{{
  "industry": "industries 里的一个键，或「其他」",
  "industry_basis": "一两句：品牌卖什么、卖给谁，引官网原文并带网址",
  "category_en": "买家搜这类产品用的英文品类词，2–4 个词，例如 cloud gpu rental",
  "local_query": "市场语言的品类词，非英语市场才填",
  "skip": {{"google-play / app-store / google-maps / 写了 scope 的站": "为什么不采"}},
  "add": {{"渠道名": "为什么要加"}},
  "add_sites": {{"域名": {{"category": "评价 或 社区", "why": "为什么要看这个站"}}}},
  "app_ids": {{"google-play": ["com.example.app"], "app-store": ["123456789"]}},
  "maps_queries": ["店名 城市"],
  "reddit_queries": ["最多 2 条：买家比较或求推荐的说法，不填就用竞品名对比和品类推荐问法"],
  "hn_queries": ["最多 3 条，不填就用竞品名"]
}}

写完运行 `python3 .agents/skills/geo-prompt-selection-builder/scripts/run_selection_mode.py check-plan --out .`，退出码 0 才算完，不是 0 就按报错改。最后只回复一行：`PLAN <行业>`。
"""

PLAN_REPAIR_TASK = """你在无人值守流水线的渠道计划返修环节。`research/precollect/plan.json` 没通过检查，报错原文：

{errors}

按 `PLAN.md` 的要求只改报错的地方；改完运行 `python3 .agents/skills/geo-prompt-selection-builder/scripts/run_selection_mode.py check-plan --out .`，退出码 0 才算完。最后只回复一行：`PLAN <行业>`。
"""

REPAIR_TASK = """你在无人值守流水线的返修环节（第 {round} / {max_rounds} 轮）。工作目录里已有 out/bank.json，{why}。

只做返修：按下面的报错改 `out/bank.json`（需要时更新 `out/notes.md`），不要重做调研（research/ 里已有材料），不要访问工作目录以外的路径。
{drop_clause}
报错原文：

{errors}

改完后依次运行，两条都要退出码 0；有错就继续改：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
{extra}最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""

REPAIR_WHY = "但结束检查没过"

# 3.13.0（Suda 2026-11-12）：线上生成的题就是售前报告测的全部题，不到 30 道补一轮；补完仍不够照常交付。
TOP_UP_FLOOR = 30
TOP_UP_TASK = """你在无人值守流水线的补题环节。工作目录里的 out/bank.json 已通过检查，但只有 {count} 道题，不到 {floor} 道（选词 selection-rules.md 第 7 步「出几道」）。

只补题，不改已有的题：
1. 先看 `out/notes.md`「没开的格子」和已有矩阵行：我方补充、能写出合理推断的处境，开成业务优先级为中的行（没有买家原话的，`priority_basis` 写「假设：……」），在这些行上出题；
2. 还不够，再在业务优先级为低的行上出题（W64 告警写处理记录：「补足题量」）；
3. 不许用同义改写、调换语序、机械组合条件凑数：门禁 8、W8b、W37 照常拦。找不到真实的新购买决策就停，在 `out/notes.md`「假设」里写一句为什么题少（品类窄、场景少等），照常交付。

规则照 online-runner.md 和 selection-rules.md；约束条件表、需求信号登记照常。合计不超过 60 道。不要重做调研，不要访问工作目录以外的路径。

改完后依次运行，两条都要退出码 0：
`python3 .agents/skills/geo-prompt-selection-builder/scripts/validate_after_sales_set.py out/bank.json`
`python3 .agents/skills/geo-prompt-selection-builder/scripts/export_upload_csv.py out/bank.json --out out/upload`
最后只回复一行：`DONE <validator 输出里的 readiness>`。
"""
REVIEW_REPAIR_WHY = "结束检查已过，但内容审核（[review]，判据见 `.agents/skills/geo-prompt-selection-builder/references/review-rubric.md`）报了阻塞问题"

REVIEW_TASK = """你在无人值守流水线的审核环节，没有人会回答问题。工作目录里的题库已通过 validator 和导出检查，你按固定清单再核对一遍内容。你没有参与生成这份题库，只按清单判断，不要沿用生成时的理由。

读这三个文件：
- `out/bank.json`：题库
- `out/notes.md`：生成记录（可能不存在，不存在就只看题库）
- `.agents/skills/geo-prompt-selection-builder/references/review-rubric.md`：评审清单

{scope}

按清单「九条核对」逐题核对，判据和 blocking 取值照清单，不自己加条目、不建议加题、不重判优先级、不改主题划分。把发现写成一个 JSON 数组存到 `out/review.json`，每条一个对象，键为 `question_id`、`check`（1–9）、`problem`、`suggestion`、`blocking`（true / false），格式见清单「输出格式」；没有发现写 `[]`。

只写 `out/review.json` 这一个文件：不改 `out/bank.json`、不改 `out/notes.md`、不调研、不联网、不访问工作目录以外的路径。
最后只回复一行：`DONE <发现条数>`。
"""

REVIEW_SCOPE_FULL = "范围：题库里的全部题目。"
REVIEW_SCOPE_RECHECK = """范围：这是复核，只看上一轮审核报过阻塞问题的这些题：{ids}。题库已按上一轮意见返修过，看这些题现在还有没有问题；清单外的题不看。清单里的题已经删掉（不在 `questions` 里、记进了 `config.retired`）的跳过。

上一轮的阻塞发现原文：

{findings}"""

REVIEW_NOTES_CLAUSE = """另外，审核还报了下面几条非阻塞意见，不用为它们改题；把它们原样记进 `out/notes.md`「评审意见」一节（没有这一节就新建）：

{items}

"""

DROP_CLAUSE = """这是最后一轮返修，丢题不丢库：报错指向的题能改就改，改不好的直接删掉，不要为凑数新写题。删掉的题号和原因记进 `config.retired`，并写进 `out/notes.md`「删题」一节；空了的主题连主题登记一起删，删题后每个主题仍只放一种意图类型。宁可少交几道题，不要交整库失败。
"""


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def scrapeless_key_present() -> bool:
    """和 shared/scripts/net.py 同一顺序：先环境变量，再 macOS 钥匙串；接平台网关时 key 在网关上，本机不需要。"""
    if os.environ.get("SCRAPELESS_BASE_URL", "").strip():
        return True  # 密钥在平台网关上
    if os.environ.get("SCRAPELESS_API_KEY", "").strip():
        return True
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "SCRAPELESS_API_KEY", "-w"],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def load_normalizer():
    sys.path.insert(0, str(HERE))
    import normalize_case  # noqa: PLC0415
    return normalize_case


def parse_platforms(raw: str) -> tuple[list[str], list[str]]:
    names = [p.strip().removeprefix("scraper.").casefold() for p in raw.split(",") if p.strip()]
    names = list(dict.fromkeys(names))
    return names, [n for n in names if n not in KNOWN_PLATFORMS]


def prepare(case_path: Path, market: str, platforms: str, ws: Path, task_file: Path | None) -> int:
    if ws.exists():
        print(f"工作目录已存在：{ws}（每个品牌 × 市场用一个新目录）", file=sys.stderr)
        return 2
    market = market.strip()
    if not market:
        print("--market 不能为空", file=sys.stderr)
        return 2
    names, unknown = parse_platforms(platforms)
    if not names or unknown:
        print(f"--platforms 要填采集器认识的平台名 {sorted(KNOWN_PLATFORMS)}，收到 {platforms!r}", file=sys.stderr)
        return 2
    ws.mkdir(parents=True)
    for sub in ("inputs", "research", "research/site", "research/precollect", "out", "logs", "logs/net_cache"):
        (ws / sub).mkdir()
    try:
        payload = json.loads(case_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        write_json(ws / "out/result.json", {"status": "input_error", "market": market,
                                             "errors": [{"code": "unreadable_input", "message": str(exc)}]})
        return 2
    result = load_normalizer().normalize(payload)
    write_json(ws / "inputs/case-normalized.json", result)
    if not result["ok"]:
        write_json(ws / "out/result.json", {"status": "input_error", "market": market,
                                             "errors": result["errors"], "warnings": result["warnings"]})
        return 2
    locale = result["normalized"]["locale"]
    for name in SKILL_DIRS:
        src = SKILLS / name
        if src.is_dir():
            shutil.copytree(src, ws / ".agents/skills" / name, symlinks=True, ignore=IGNORE)
    for name, rel in PARTIAL_COPIES:
        src = SKILLS / name / rel
        dst = ws / ".agents/skills" / name / rel
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True, ignore=IGNORE)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    sync_industry_kb(ws)
    task = task_file.read_text(encoding="utf-8") if task_file else TASK.format(market=market, locale=locale, platforms=",".join(names),
                                                                                  reddit_max=os.environ.get("NET_REDDIT_MAX", "10"))
    if domestic() and not task_file:
        task += DOMESTIC_NOTE
    (ws / "TASK.md").write_text(task, encoding="utf-8")
    (ws / "PLAN.md").write_text(PLAN_TASK.format(market=market, gl=market.lower(), lang=locale), encoding="utf-8")
    write_json(ws / "out/result.json", {"status": "prepared", "market": market, "locale": locale,
                                         "platforms": names, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                         "warnings": result["warnings"]})
    return 0


DOMESTIC_NOTE = """
## 境内模式

这台服务器没有海外直连（`GEO_NET_DOMESTIC=1`）：`net.py fetch` 全部经 Scrapeless 代理取，每页付费，缓存命中不付；`net.py reddit` 搜索不发请求、直接回「读不到」，不要重试；`net.py render` 改经 Scrapeless 代理不开 JS 取；Reddit 帖子用 `net.py search` 搜出链接后 `net.py reddit <帖子 URL> --proxy` 取网页版（每帖付费 1 次），Pantip 帖子照常用 `net.py pantip`（经 Scrapeless 渲染，每帖付费 1 次），其余要渲染的站点写进 `notes.md`「未覆盖来源」，注明「境内模式」。`collect_reviews.py`、`collect_keyword_data.py` 走 DataForSEO，报连接失败时同样记进未覆盖来源，不另找办法。
"""




def plan_step(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int) -> dict:
    """先让 agent 判行业、填渠道参数（PLAN.md），检查不过回喂一次；仍不过就退回默认计划，不卡住流水线。"""
    t = min(timeout, PLAN_TIMEOUT)
    rec = run_agent(ws, agent, agent_cmd, t, task_path=ws / "PLAN.md", tag="-plan")
    errors, checked = check_plan(ws)
    if errors:
        (ws / "PLAN-REPAIR.md").write_text(PLAN_REPAIR_TASK.format(errors="\n".join(f"- {e}" for e in errors)),
                                           encoding="utf-8")
        rec = run_agent(ws, agent, agent_cmd, t, task_path=ws / "PLAN-REPAIR.md", tag="-plan-repair")
        errors, checked = check_plan(ws)
    if errors:
        why = "行业判断两次没通过检查：" + "；".join(errors)[:400]
        if rec.get("error"):
            why += f"（agent：{rec['error'][:200]}）"
        checked = fallback_plan(ws, why)
    return checked


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _usage(raw) -> dict:
    """ResultMessage.usage 可能是 dict 也可能是对象；只取四个计费字段，缺的记 0。"""
    get = raw.get if isinstance(raw, dict) else (lambda k, d=None: getattr(raw, k, d))
    return {k: int(get(k, 0) or 0) for k in USAGE_KEYS}


async def _run_sdk(ws: Path, task: str, timeout: int, tag: str = "", model: str = "") -> dict:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query  # noqa: PLC0415
    model = model.strip() or os.environ.get("AGENT_MODEL", "").strip()
    if not os.environ.get("ANTHROPIC_BASE_URL") or not os.environ.get("ANTHROPIC_API_KEY") or not model:
        raise RuntimeError("--agent sdk 需要环境变量 ANTHROPIC_BASE_URL、ANTHROPIC_API_KEY、AGENT_MODEL")
    home = ws / "logs/agent-home"
    home.mkdir(parents=True, exist_ok=True)
    env = {"ANTHROPIC_MODEL": model, "ANTHROPIC_SMALL_FAST_MODEL": model,
           "ANTHROPIC_DEFAULT_HAIKU_MODEL": model, "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
           "ANTHROPIC_DEFAULT_OPUS_MODEL": model, "CLAUDE_CODE_SUBAGENT_MODEL": model,
           "ANTHROPIC_AUTH_TOKEN": "", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
           "CLAUDE_CONFIG_DIR": str(home), **net_env(ws)}
    opts = ClaudeAgentOptions(cwd=str(ws), model=model, env=env, permission_mode="bypassPermissions",
                              disallowed_tools=["WebSearch", "WebFetch"], setting_sources=["project"],
                              max_turns=600)
    record: dict = {"tool_calls": 0}
    with (ws / f"logs/agent{tag}.jsonl").open("w", encoding="utf-8") as log:
        async def consume():
            async for m in query(prompt=task, options=opts):
                if isinstance(m, AssistantMessage):
                    record["tool_calls"] += sum(1 for b in m.content if type(b).__name__ == "ToolUseBlock")
                if isinstance(m, ResultMessage):
                    record.update(finish=getattr(m, "subtype", None), turns=getattr(m, "num_turns", None),
                                  final=getattr(m, "result", None), model=model,
                                  duration_ms=getattr(m, "duration_ms", None),
                                  duration_api_ms=getattr(m, "duration_api_ms", None),
                                  # SDK 按 Anthropic 模型价算的；网关后面是别家模型（如 DeepSeek）时不可信，
                                  # 算钱用 usage × 网关单价（cost_report.py），这个数只原样留存
                                  total_cost_usd_anthropic_price_unreliable=getattr(m, "total_cost_usd", None))
                    if getattr(m, "usage", None) is not None:
                        record["usage"] = _usage(m.usage)
                log.write(json.dumps({"type": type(m).__name__, "repr": repr(m)[:2000]}, ensure_ascii=False) + "\n")
        await asyncio.wait_for(consume(), timeout)
    return record


def run_agent(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int,
              task_path: Path | None = None, tag: str = "", model: str = "") -> dict:
    task_path = task_path or ws / "TASK.md"
    task = task_path.read_text(encoding="utf-8")
    started = time.time()
    record: dict = {"agent": "sdk" if agent == "sdk" else "cmd", "task_file": task_path.name,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        if agent == "sdk":
            record.update(asyncio.run(_run_sdk(ws, task, timeout, tag, model)))
        else:
            env = dict(os.environ, WORKSPACE=str(ws), TASK_FILE=str(task_path), **net_env(ws))
            with (ws / f"logs/agent{tag}.log").open("w", encoding="utf-8") as log:
                proc = subprocess.run(agent_cmd, shell=True, cwd=ws, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=timeout)
            record["exit_code"] = proc.returncode
            if proc.returncode != 0:
                record["error"] = f"agent 命令退出码 {proc.returncode}，输出见 logs/agent{tag}.log"
    except (asyncio.TimeoutError, subprocess.TimeoutExpired):
        record["error"] = f"agent 超时（{timeout} 秒）"
    except Exception as exc:  # noqa: BLE001 - 任何 agent 异常都记成生词失败，不让流水线崩
        record["error"] = f"{type(exc).__name__}: {str(exc)[:2000]}"
    record["wall_secs"] = round(time.time() - started, 1)
    write_json(ws / f"logs/agent-run{tag}.json", record)
    return record


def validator_readiness(stdout: str) -> str:
    """有错时 validator 打印 `READINESS: …` 一行；通过时只打印一段 JSON，readiness 在里面。"""
    for line in stdout.splitlines():
        if line.startswith("READINESS:"):
            return line.split(":", 1)[1].strip()
    for line in reversed(stdout.strip().splitlines()):
        try:
            return str(json.loads(line).get("readiness") or "")
        except (json.JSONDecodeError, AttributeError):
            continue
    return ""


def _tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def finalize(ws: Path, agent_record: dict | None = None, repair_rounds: int | None = None,
             precollect_final: bool = False) -> int:
    """precollect_final=True 表示没有返修轮可用了（最后一轮返修、关闭返修、审核环里）：登记检查缺的只记 warning。"""
    prior = json.loads((ws / "out/result.json").read_text(encoding="utf-8")) if (ws / "out/result.json").exists() else {}
    market, locale = prior.get("market", ""), prior.get("locale", "")
    result = {"status": "failed", "market": market, "locale": locale, "platforms": prior.get("platforms", []), "errors": [],
              "warnings": prior.get("warnings", []), "prepared_at": prior.get("prepared_at", "")}
    block = precollect_block(ws)
    if block is not None:
        result["precollect"] = block
    result["costs"] = collect_costs(ws, market, result["prepared_at"])
    if repair_rounds is not None:
        result["repair_rounds"] = repair_rounds
    if agent_record and agent_record.get("error"):
        result["errors"].append({"stage": "agent", "message": agent_record["error"]})
    bank = ws / "out/bank.json"
    if not bank.exists():
        result["errors"].append({"stage": "agent", "message": "agent 没有写出 out/bank.json"})
        write_json(ws / "out/result.json", result)
        return 1
    tools = ws / ".agents/skills/geo-prompt-selection-builder/scripts"
    upload = ws / "out/upload"
    if upload.exists():
        shutil.rmtree(upload)  # 只认这一次导出的文件
    checks = {
        "validator": [sys.executable, "-I", str(tools / "validate_after_sales_set.py"), str(bank)],
        "export": [sys.executable, "-I", str(tools / "export_upload_csv.py"), str(bank), "--out", str(upload)],
    }
    exits = {}
    for name, cmd in checks.items():
        proc = subprocess.run(cmd, capture_output=True, text=True)
        output = proc.stdout + proc.stderr
        (ws / f"logs/{name}.txt").write_text(output, encoding="utf-8")
        exits[name] = proc.returncode
        if name == "validator":
            result["validator_readiness"] = validator_readiness(proc.stdout)
        if proc.returncode != 0:
            result["errors"].append({"stage": name, "exit_code": proc.returncode, "output": _tail(output)})
    files = sorted(upload.glob("*.upload.csv")) if upload.exists() else []
    result["upload_files"] = [str(p.relative_to(ws)) for p in files]
    try:
        data = json.loads(bank.read_text(encoding="utf-8"))
        regions = sorted({str(q.get("region") or "").strip() for q in data.get("questions") or []})
    except (OSError, json.JSONDecodeError) as exc:
        result["errors"].append({"stage": "bank", "message": f"bank.json 读不了：{exc}"})
        regions = []
    if market and regions and regions != [market]:
        result["errors"].append({"stage": "market", "message": f"题库市场 {regions} 与传入的 --market {market!r} 不一致"})
    # 登记检查（runner 层）：precollect 采到的类别 buyer_quotes 一条没有 → 返修；没有返修轮了只记 warning
    for msg in precollect_registration_errors(ws):
        if precollect_final:
            warn = f"[precollect] 返修轮次已用完仍缺登记，照常交付：{msg}"
            if warn not in result["warnings"]:
                result["warnings"].append(warn)
        else:
            result["errors"].append({"stage": "precollect", "message": msg})
    rows = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows += list(csv.DictReader(f))
    result["prompt_count"] = len(rows)
    result["topics"] = list(dict.fromkeys(r["topic"] for r in rows))
    if not result["errors"] and all(code == 0 for code in exits.values()) and files:
        result["status"] = "success"
    elif not files and not any(e["stage"] == "export" for e in result["errors"]):
        result["errors"].append({"stage": "export", "message": "没有导出任何文件"})
    write_json(ws / "out/result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "market", "prompt_count", "topics", "upload_files")},
                     ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


def _ledger_path() -> Path:
    """和 shared/scripts/collect_keyword_data.py 的 ledger_path 同一规则。"""
    return Path(os.environ.get("DATAFORSEO_LEDGER", "").strip() or Path.home() / ".dataforseo" / "ledger.jsonl")


def dataforseo_case(ws: Path, market: str) -> str:
    """run 给 agent 设的 DATAFORSEO_CASE；没设时同样按「品牌 市场」推。"""
    case = os.environ.get("DATAFORSEO_CASE", "").strip()
    if case:
        return case
    try:
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        brand = ""
    return f"{brand} {market}".strip()


def collect_costs(ws: Path, market: str, since: str) -> dict:
    """本轮记账：只记数量和 usage，不乘单价（单价在 cost_report.py 读本机配置）。

    每次 finalize 都从工作目录重新数一遍，所以返修轮之后的结果包含主跑和全部返修。
    """
    try:
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        brand = ""
    until = time.strftime("%Y-%m-%dT%H:%M:%S")
    # LLM：主跑 logs/agent-run.json，返修 logs/agent-run-repair<n>.json
    llm = {"runs": 0, "runs_with_usage": 0, "turns": 0, "duration_ms": 0, "model": "",
           **{k: 0 for k in USAGE_KEYS}, "total_cost_usd_anthropic_price_unreliable": 0.0, "files": []}
    starts: list[str] = []
    for path in sorted((ws / "logs").glob("agent-run*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        llm["runs"] += 1
        llm["files"].append(path.name)
        if rec.get("started_at"):
            starts.append(rec["started_at"])
        llm["turns"] += int(rec.get("turns") or 0)
        llm["duration_ms"] += int(rec.get("duration_ms") or 0)
        llm["model"] = llm["model"] or rec.get("model") or ""
        llm["total_cost_usd_anthropic_price_unreliable"] += float(rec.get("total_cost_usd_anthropic_price_unreliable") or 0)
        if isinstance(rec.get("usage"), dict):
            llm["runs_with_usage"] += 1
            for k in USAGE_KEYS:
                llm[k] += int(rec["usage"].get(k) or 0)
    if not since and starts:  # 3.1.0 之前 prepare 的目录没有 prepared_at，用最早一次 agent 启动时间
        since = min(starts)
    llm["total_cost_usd_anthropic_price_unreliable"] = round(llm["total_cost_usd_anthropic_price_unreliable"], 6)
    # Scrapeless：预跑尝试（失败重试也算一次）、SERP 原始返回、本轮 net.py 缓存里的代理页和搜索
    prerun = {"attempts": 0, "ok": 0, "files": []}
    for ev in sorted((ws / "research").glob("**/_collector/events.jsonl")):
        prerun["files"].append(str(ev.relative_to(ws)))
        for line in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "attempt":
                prerun["attempts"] += 1
                prerun["ok"] += 1 if e.get("ok") else 0
    serp_raw = list((ws / "research").glob("**/serp*/raw/*.json"))
    # 境内模式的自动补全经 Scrapeless 网页代理取（3.6.3），存成 raw/*.autocomplete.json，按代理页计
    autocomplete = sum(1 for f in serp_raw if f.name.endswith(".autocomplete.json"))
    serp = len(serp_raw) - autocomplete
    cache = ws / "logs/net_cache"
    proxy = search = render = 0
    if cache.is_dir():
        for f in cache.glob("fetch_*.json"):
            try:
                proxy += 1 if "Scrapeless" in json.loads(f.read_text(encoding="utf-8")).get("src", "") else 0
            except (OSError, json.JSONDecodeError):
                continue
        search = sum(1 for f in cache.glob("*.json") if len(f.stem) == 32 and all(c in "0123456789abcdef" for c in f.stem))
        for f in cache.glob("pantip_*.json"):  # 3.6.2：Pantip 经 Scrapeless JS 渲染的帖子
            try:
                render += 1 if "Scrapeless" in json.loads(f.read_text(encoding="utf-8")).get("src", "") else 0
            except (OSError, json.JSONDecodeError):
                continue
    scrapeless = {"prerun_attempts": prerun["attempts"], "prerun_ok": prerun["ok"], "prerun_event_files": prerun["files"],
                  "serp_requests": serp, "net_search_requests": search, "proxy_pages": proxy, "render_pages": render,
                  "autocomplete_proxy": autocomplete,
                  "note": "proxy_pages 只数成功并写进缓存的代理页（Scrapeless 网页代理按成功请求计费）；render_pages 是"
                          "开 JS 渲染的代理页（Pantip），单价可能高于普通代理页；logs/net_cache 不在时记「不可归集」"}
    if not cache.is_dir():
        scrapeless["proxy_pages"] = scrapeless["net_search_requests"] = scrapeless["render_pages"] = "不可归集"
    # DataForSEO：服务端流水按 case 与本轮时间窗过滤，不含沙盒
    case = dataforseo_case(ws, market)
    dfs = {"case": case, "since": since, "until": until, "calls": 0, "cost_usd": 0.0, "ledger": str(_ledger_path())}
    try:
        lines = _ledger_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
        dfs["note"] = "流水文件不存在"
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = str(e.get("time", ""))
        if e.get("sandbox") or (e.get("case") or "").strip() != case or (since and t < since) or t > until:
            continue
        dfs["calls"] += 1
        dfs["cost_usd"] += float(e.get("cost_usd") or 0)
    dfs["cost_usd"] = round(dfs["cost_usd"], 6)
    return {"brand": brand, "market": market, "since": since, "until": until,
            "llm": llm, "scrapeless_requests": scrapeless, "dataforseo": dfs}


def format_errors(errors: list[dict]) -> str:
    """返修任务里的报错格式：每条 `[stage] 原文`，空行分隔。"""
    return "\n\n".join(f"[{e.get('stage', '?')}] {e.get('output') or e.get('message', '')}".strip() for e in errors)


def repair_task(ws: Path, round_no: int, max_rounds: int) -> Path:
    """把上一轮 result.json 的报错写成返修任务，返回任务文件路径。"""
    result = json.loads((ws / "out/result.json").read_text(encoding="utf-8"))
    errors = format_errors(result.get("errors", []))
    drop = DROP_CLAUSE if round_no >= max_rounds else ""
    path = ws / f"REPAIR-{round_no}.md"
    path.write_text(REPAIR_TASK.format(round=round_no, max_rounds=max_rounds, why=REPAIR_WHY, drop_clause=drop,
                                       errors=errors, extra=""),
                    encoding="utf-8")
    return path


# ---- 审核环（3.2.0） ------------------------------------------------------------------

def _finding_ids(finding: dict) -> list[str]:
    """question_id 可能是一个题号、题号列表或空（主题级发现）。"""
    raw = finding.get("question_id")
    items = raw if isinstance(raw, list) else [raw]
    return [str(x).strip() for x in items if str(x or "").strip()]


def finding_message(f: dict) -> str:
    ids = "、".join(_finding_ids(f)) or "（未指明题号）"
    msg = f"{ids} 第 {f.get('check', '?')} 条：{str(f.get('problem') or '').strip()}"
    if str(f.get("suggestion") or "").strip():
        msg += f"（建议：{str(f['suggestion']).strip()}）"
    return msg


def parse_review(path: Path) -> tuple[list[dict] | None, str]:
    """读 out/review.json；返回 (发现列表, 出错说明)。结构不对时发现为 None。"""
    if not path.exists():
        return None, "审核 agent 没有写出 out/review.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"out/review.json 不是合法 JSON：{exc}"
    if isinstance(data, dict) and isinstance(data.get("findings"), list):
        data = data["findings"]  # 宽容：包了一层 {"findings": [...]}
    if not isinstance(data, list):
        return None, f"out/review.json 应是 JSON 数组，收到 {type(data).__name__}"
    for i, f in enumerate(data):
        if not isinstance(f, dict) or not isinstance(f.get("blocking"), bool) or not str(f.get("problem") or "").strip():
            return None, f"out/review.json 第 {i + 1} 条结构不对：要有 problem（非空）和 blocking（true / false）"
    for f in data:
        # 第 9 条（调研缺口）按清单只能是非阻塞、question_id 写 `-`；审核 agent 误标 blocking 也不进返修和删题
        if str(f.get("check")).strip() == "9" and f["blocking"]:
            f["blocking"] = False
    return data, ""


def review_task(ws: Path, run_no: int, recheck: list[dict] | None) -> Path:
    if recheck is None:
        scope = REVIEW_SCOPE_FULL
    else:
        ids = list(dict.fromkeys(i for f in recheck for i in _finding_ids(f)))
        scope = REVIEW_SCOPE_RECHECK.format(ids="、".join(ids) or "（上一轮发现没有指明题号，复核这些发现涉及的题）",
                                            findings="\n".join(f"- {finding_message(f)}" for f in recheck))
    path = ws / ("REVIEW.md" if run_no == 1 else f"REVIEW-{run_no}.md")
    path.write_text(REVIEW_TASK.format(scope=scope), encoding="utf-8")
    return path


def review_repair_task(ws: Path, round_no: int, max_rounds: int, errors: list[dict], notes: list[dict]) -> Path:
    drop = DROP_CLAUSE if round_no >= max_rounds else ""
    extra = REVIEW_NOTES_CLAUSE.format(items="\n".join(f"- {finding_message(f)}" for f in notes)) if notes else ""
    path = ws / f"REVIEW-REPAIR-{round_no}.md"
    path.write_text(REPAIR_TASK.format(round=round_no, max_rounds=max_rounds, why=REVIEW_REPAIR_WHY, drop_clause=drop,
                                       errors=format_errors(errors), extra=extra),
                    encoding="utf-8")
    return path


def write_review_block(ws: Path, market: str, review: dict, fail: str = "") -> None:
    """把审核块写进 result.json；审核 agent 跑在最后一次 finalize 之后，costs 重数一遍才含审核轮。"""
    path = ws / "out/result.json"
    result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    result["review"] = review
    if fail:
        result["status"] = "failed"
        result.setdefault("errors", []).append({"stage": "review", "message": fail})
    result["costs"] = collect_costs(ws, market, result.get("prepared_at", ""))
    write_json(path, result)


def drop_blocked_questions(ws: Path, blocking: list[dict]) -> list[dict]:
    """把阻塞发现指向的题从 out/bank.json 删掉、记进 config.retired；删空的主题连登记一起删，
    挂在它上面的矩阵行去掉 topic_id 并注明本期不出。返回删掉的 [{question_id, reason}]；
    主题级发现（没写题号）删不了，不处理。删前的题库存成 out/bank.before-drop.json。"""
    path = ws / "out/bank.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    config = bank.setdefault("config", {})
    questions = bank.get("questions") or []
    reasons: dict[str, list[str]] = {}
    for f in blocking:
        for qid in _finding_ids(f):
            reasons.setdefault(qid, []).append(f"审核第 {f.get('check', '?')} 条：{str(f.get('problem') or '').strip()}")
    present = {str(q.get("question_id")) for q in questions}
    targets = [qid for qid in reasons if qid in present]
    if not targets:
        return []
    shutil.copy2(path, ws / "out/bank.before-drop.json")
    dropped, kept = [], []
    for q in questions:
        qid = str(q.get("question_id"))
        if qid in targets:
            reason = "审核返修轮次用完仍有阻塞，脚本删除；" + "；".join(reasons[qid])
            config.setdefault("retired", []).append({"question_id": qid, "query": q.get("user_question") or q.get("query", ""), "reason": reason})
            dropped.append({"question_id": qid, "reason": reason})
        else:
            kept.append(q)
    bank["questions"] = kept
    live_topics = {q.get("topic_id") for q in kept}
    empty = {t.get("topic_id") for t in config.get("topics") or []} - live_topics
    if empty:
        config["topics"] = [t for t in config["topics"] if t.get("topic_id") not in empty]
        for s in config.get("slices") or []:
            if s.get("topic_id") in empty:
                s.pop("topic_id")
                s["priority_basis"] = (str(s.get("priority_basis") or "") + "；本期不出：题被审核删光").lstrip("；")
    write_json(path, bank)
    notes = ws / "out/notes.md"
    lines = ["", "## 删题（脚本兜底）", ""] + [f"- {d['question_id']}：{d['reason']}" for d in dropped]
    with notes.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return dropped


def review_loop(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int,
                max_rounds: int, repair_rounds: int, market: str) -> int:
    """首次 finalize 通过后跑：审核 → 阻塞发现回喂返修 → finalize → 只复核报过的题。返回最终退出码。"""
    review = {"rounds": 0, "blocking_found": 0, "nonblocking_found": 0, "status": "skipped", "reason": "",
              "review_repair_rounds": 0, "warnings": [], "nonblocking": [], "blocking_unresolved": []}
    if max_rounds <= 0:
        review["reason"] = "--review-rounds 0，未审核"
        write_review_block(ws, market, review)
        return 0
    model = os.environ.get("AGENT_REVIEW_MODEL", "").strip() or os.environ.get("AGENT_MODEL", "").strip()
    bank = ws / "out/bank.json"
    out = ws / "out/review.json"
    recheck: list[dict] | None = None
    noted: set[str] = set()      # 已经搭车交给返修记进 notes.md 的非阻塞意见
    used = 0
    while True:
        review["rounds"] += 1
        n = review["rounds"]
        if out.exists():
            out.unlink()  # 只认这一轮写的
        before = bank.read_bytes()
        task = review_task(ws, n, recheck)
        record = run_agent(ws, agent, agent_cmd, timeout, task_path=task,
                           tag="-review" if n == 1 else f"-review{n}", model=model if agent == "sdk" else "")
        if bank.read_bytes() != before:
            bank.write_bytes(before)
            review["warnings"].append(f"第 {n} 轮审核 agent 改了 out/bank.json，已恢复审核前的题库")
        if out.exists():
            shutil.copy2(out, ws / f"logs/review-{n}.json")
        findings, err = parse_review(out)
        if findings is None:
            # 审核是增强不是闸门：审核没跑成只记 warning，题库已过检查照常交付
            if record.get("error"):
                err = f"{record['error']}；{err}"
            review.update(status="review_failed", reason="审核没有产出可用结果，按已过检查的题库交付")
            review["warnings"].append(f"第 {n} 轮审核：{err}")
            write_review_block(ws, market, review)
            return 0
        blocking = [f for f in findings if f["blocking"]]
        fresh_notes = []
        for f in findings:
            if f["blocking"]:
                continue
            key = finding_message(f)
            if key not in {finding_message(x) for x in review["nonblocking"]}:
                review["nonblocking"].append(f)
                fresh_notes.append(f)
        review["blocking_found"] += len(blocking)
        review["nonblocking_found"] += len(fresh_notes)
        if not blocking:
            review.update(status="repaired" if used else "passed", blocking_unresolved=[])
            write_review_block(ws, market, review)
            return 0
        pending_errors = [{"stage": "review", "message": finding_message(f)} for f in blocking]
        while True:
            if used >= max_rounds:
                # 丢题不丢库：轮次用完仍有阻塞的题由脚本删掉再查一遍，不靠 agent 自觉删
                dropped = drop_blocked_questions(ws, blocking)
                if dropped and finalize(ws, None, repair_rounds=repair_rounds, precollect_final=True) == 0:
                    review.update(status="dropped", reason=f"审核返修 {max_rounds} 轮后仍有阻塞，脚本删掉 {len(dropped)} 道题后交付",
                                  dropped=dropped, blocking_unresolved=[])
                    write_review_block(ws, market, review)
                    return 0
                review.update(status="review_failed", reason="审核返修轮次用完仍有阻塞发现", blocking_unresolved=blocking,
                              dropped=dropped)
                write_review_block(ws, market, review, fail=f"审核返修 {max_rounds} 轮后仍有 {len(blocking)} 条阻塞发现"
                                   + ("，删题后检查仍没过" if dropped else "，且没有可删的题号") + "："
                                   + "；".join(finding_message(f) for f in blocking))
                return 1
            used += 1
            review["review_repair_rounds"] = used
            notes = [f for f in review["nonblocking"] if finding_message(f) not in noted]
            noted.update(finding_message(f) for f in notes)
            task = review_repair_task(ws, used, max_rounds, pending_errors, notes)
            record = run_agent(ws, agent, agent_cmd, timeout, task_path=task, tag=f"-review-repair{used}")
            code = finalize(ws, record, repair_rounds=repair_rounds, precollect_final=True)
            if code == 0:
                break
            # 返修把检查改坏了：检查报错和没修的阻塞发现一起进下一轮
            result = json.loads((ws / "out/result.json").read_text(encoding="utf-8"))
            pending_errors = list(result.get("errors", [])) + [
                {"stage": "review", "message": finding_message(f)} for f in blocking]
            if used >= max_rounds:
                review.update(status="review_failed", reason="审核返修后检查没过，轮次已用完", blocking_unresolved=blocking)
                write_review_block(ws, market, review)
                return 1
        recheck = blocking


def dataforseo_env(ws: Path, market: str) -> None:
    """DataForSEO 脚本没有调用人就不发调用；线上没传时给一个可见的占位，不让调研静默缺数据。
    precollect 的 collect_reviews.py 和 agent 都从环境变量读 DATAFORSEO_WHO / DATAFORSEO_CASE。"""
    os.environ.setdefault("DATAFORSEO_WHO", "线上选词（未传调用人）")
    if not os.environ.get("DATAFORSEO_CASE", "").strip():
        brand = json.loads((ws / "inputs/case-normalized.json").read_text(encoding="utf-8"))["normalized"]["brand_name"]
        os.environ["DATAFORSEO_CASE"] = f"{brand} {market}".strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "prepare"):
        p = sub.add_parser(name)
        p.add_argument("--case", type=Path, required=True, help="品牌资料 JSON，presales-case-input/v2（见 references/input-contract.md）")
        p.add_argument("--market", required=True, help="市场代码，与采集的 --regions 一致，如 US")
        p.add_argument("--platforms", required=True,
                       help="表单「AI 平台」选中的平台，逗号分隔，如 chatgpt,gemini；研究预跑只跑这些")
        p.add_argument("--out", type=Path, required=True, help="新的工作目录，不能已存在")
        p.add_argument("--task-file", type=Path, help="替换默认任务说明（只用于测试）")
        if name == "run":
            p.add_argument("--agent", choices=["sdk"], help="内置 Claude Agent SDK 适配")
            p.add_argument("--agent-cmd", help="宿主 harness 的命令，在工作目录里执行")
            p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="agent 时间上限（秒），每轮返修同额")
            p.add_argument("--repair-rounds", type=int, default=2,
                           help="检查没过时回喂报错返修的最大轮数（默认 2，0 关闭；最后一轮授权丢题不丢库）")
            p.add_argument("--review-rounds", type=int, default=1,
                           help="审核报阻塞问题时回喂返修的最大轮数（默认 1＝审一轮＋复核一轮，0 关闭审核；"
                                "不占 --repair-rounds 额度）")
    p = sub.add_parser("finalize")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("precollect", help="对已 prepare 的工作目录单独跑 precollect（有 plan.json 先按它判行业，没有按默认渠道）")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("check-plan", help="检查 research/precollect/plan.json（行业判断步骤里 agent 自己跑）")
    p.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ws = a.out.resolve()
    if a.cmd == "finalize":
        return finalize(ws)
    if a.cmd == "check-plan":
        errors, checked = check_plan(ws)
        if errors:
            print("plan.json 没通过：\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
            return 1
        print(json.dumps({"industry": checked["industry"],
                          "channels": [f"{c['category']}:{c['name']}:{c['status']}" for c in checked["channels"]]},
                         ensure_ascii=False))
        return 0
    if a.cmd == "precollect":
        if not (ws / "inputs/case-normalized.json").exists():
            print(f"{ws} 不是 prepare 过的工作目录", file=sys.stderr)
            return 2
        dataforseo_env(ws, json.loads((ws / "out/result.json").read_text(encoding="utf-8")).get("market", ""))
        print(json.dumps(precollect(ws)["categories"], ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "run" and bool(a.agent) == bool(a.agent_cmd):
        print("run 需要 --agent sdk 或 --agent-cmd 二选一", file=sys.stderr)
        return 2
    code = prepare(a.case.resolve(), a.market, a.platforms, ws, a.task_file.resolve() if a.task_file else None)
    if code != 0 or a.cmd == "prepare":
        if code != 0 and (ws / "out/result.json").exists():
            print((ws / "out/result.json").read_text(encoding="utf-8"))
        return code
    if not a.task_file and not scrapeless_key_present():
        # 没有 key 时 agent 采不了研究预跑，会凭空写题；在启动 agent 前就停下
        write_json(ws / "out/result.json", {"status": "env_error", "market": a.market.strip(),
                                             "errors": [{"code": "missing_env", "message": "缺少 SCRAPELESS_API_KEY"}]})
        print("缺少 SCRAPELESS_API_KEY，未启动 agent", file=sys.stderr)
        return 2
    dataforseo_env(ws, a.market.strip())
    # precollect：评价、社区、搜索联想由脚本固定采，在 agent 启动前跑完；--task-file（测试）时只在给了假采集脚本目录时跑
    if not a.task_file or os.environ.get("PRECOLLECT_SCRIPTS_DIR", "").strip():
        plan_step(ws, a.agent, a.agent_cmd, a.timeout)  # 先判行业、定渠道，再按渠道采
        precollect(ws)
    record = run_agent(ws, a.agent, a.agent_cmd, a.timeout)
    code = finalize(ws, record, repair_rounds=0, precollect_final=a.repair_rounds <= 0)
    rounds = 0
    while code != 0 and rounds < max(a.repair_rounds, 0) and (ws / "out/bank.json").exists():
        rounds += 1
        task_path = repair_task(ws, rounds, a.repair_rounds)
        record = run_agent(ws, a.agent, a.agent_cmd, a.timeout, task_path=task_path, tag=f"-repair{rounds}")
        code = finalize(ws, record, repair_rounds=rounds, precollect_final=rounds >= a.repair_rounds)
    if code != 0:
        return code
    if a.repair_rounds > 0 and top_up(ws, a.agent, a.agent_cmd, a.timeout, rounds) != 0:
        return 1
    code = review_loop(ws, a.agent, a.agent_cmd, a.timeout, a.review_rounds, rounds, a.market.strip())
    if code == 0:
        learn_industry(ws, testing=bool(a.task_file))
    return code


def top_up(ws: Path, agent: str | None, agent_cmd: str | None, timeout: int, rounds: int) -> int:
    """题库已过检查但不到 TOP_UP_FLOOR 道时补一轮（3.13.0）。补完没过检查就退回补题前的题库，照常交付。

    结果记在 result.json 的 top_up：{before, after, status: added / unchanged / reverted}。返回 finalize 的退出码（0）。
    """
    result_path = ws / "out/result.json"
    before = json.loads(result_path.read_text(encoding="utf-8")).get("prompt_count") or 0
    if before >= TOP_UP_FLOOR:
        return 0
    saved = {name: (ws / "out" / name).read_bytes() for name in ("bank.json", "notes.md") if (ws / "out" / name).exists()}
    task = ws / "TOPUP.md"
    task.write_text(TOP_UP_TASK.format(count=before, floor=TOP_UP_FLOOR), encoding="utf-8")
    record = run_agent(ws, agent, agent_cmd, timeout, task_path=task, tag="-topup")
    code = finalize(ws, record, repair_rounds=rounds, precollect_final=True)
    status = "added"
    if code != 0:
        for name, data in saved.items():
            (ws / "out" / name).write_bytes(data)
        code = finalize(ws, None, repair_rounds=rounds, precollect_final=True)
        status = "reverted"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    after = result.get("prompt_count") or 0
    if status == "added" and after <= before:
        status = "unchanged"
    result["top_up"] = {"before": before, "after": after, "status": status}
    if after < TOP_UP_FLOOR:
        result["warnings"].append(f"[top_up] 补题后仍只有 {after} 道，不到 {TOP_UP_FLOOR} 道，照常交付；原因见 out/notes.md")
    write_json(result_path, result)
    return code


def sync_industry_kb(ws: Path) -> None:
    """服务器设了 GEO_INDUSTRY_KB（持久化目录）时：目录还空就从随 skill 的档案复制一份，再把这个目录的档案拷进
    工作目录里的 skill，agent 读到的是持续积累的那份，不是随 skill 发布时的那份。出错只打印，不挡运行。"""
    if not os.environ.get("GEO_INDUSTRY_KB", "").strip():
        return
    try:
        import industry_kb  # noqa: PLC0415
        industry_kb.seed_if_empty()
        src = industry_kb.kb_dir()
        dst = ws / ".agents/skills/geo-prompt-selection-builder/references/industry-knowledge"
        dst.mkdir(parents=True, exist_ok=True)
        for f in list(dst.glob("*.md")) + list(dst.glob("*.json")):  # 工作目录里的副本，换成持久化目录的最新档案
            f.unlink()
        for f in src.iterdir():
            if f.is_file() and f.suffix in (".md", ".json"):
                shutil.copy2(f, dst / f.name)
    except Exception as exc:  # noqa: BLE001
        print(f"行业知识档案没拷进工作目录：{type(exc).__name__}: {exc}", file=sys.stderr)


def learn_industry(ws: Path, testing: bool = False) -> None:
    """成功交付后把品类层面的经验并进行业知识档案（3.8.0，industry_kb.py）。测试（--task-file）只在显式设了
    GEO_INDUSTRY_KB 时写，免得假数据进正式档案；出错只记 warning，不影响交付。"""
    if testing and not os.environ.get("GEO_INDUSTRY_KB", "").strip():
        return
    res_path = ws / "out/result.json"
    try:
        sys.path.insert(0, str(HERE))
        import industry_kb  # noqa: PLC0415
        path = industry_kb.add_from_ws(ws)
        note = {"industry_kb": str(path) if path else "没有并入（行业没判出来或缺题库）"}
    except Exception as exc:  # noqa: BLE001
        note = {"industry_kb_warning": f"{type(exc).__name__}: {exc}"[:300]}
    try:
        res = json.loads(res_path.read_text(encoding="utf-8"))
        res.update(note)
        write_json(res_path, res)
    except (OSError, ValueError):
        pass


if __name__ == "__main__":
    sys.exit(main())
