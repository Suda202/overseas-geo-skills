#!/usr/bin/env python3
"""选词 skill 家族的退役说法扫描（Suda 2026-10-27）。只读，不改文件。

每次改口径后跑一遍，扫出 0 条才算改完。扫 SKILL.md 与 references/*.md，
覆盖选词、监测、售前生词三个 skill 和 shared 下引用选词规则的两份文档。

一行里同时出现「历史标记」（退役、改名、取消、before 2026… 这类交代来历的词）
时不算命中：规则里保留旧名是为了说明沿革，不是在用旧口径。标了 strict 的说法
连沿革也不该出现（它本身就是错的现行描述），历史标记不放行。

用法：python3 -I check_skill_terms.py [--json out.json]
退出码：0 无命中；1 有命中。
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
TARGETS = [
    SKILLS / "geo-prompt-selection-builder" / "SKILL.md",
    *sorted((SKILLS / "geo-prompt-selection-builder" / "references").glob("*.md")),
    SKILLS / "geo-monitoring" / "SKILL.md",
    *sorted((SKILLS / "geo-monitoring" / "references").glob("*.md")),
    SKILLS / "geo-presales-prompt-builder" / "SKILL.md",
    *sorted((SKILLS / "geo-presales-prompt-builder" / "references").glob("*.md")),
    SKILLS / "shared" / "canonical-intent-mapping.md",
    SKILLS / "shared" / "prompt-generation-principles.md",
]

# 退役说法 → 现在的说法
RETIRED = [
    (r"候选基线|candidate baseline", "试跑（每平台 3 次）与正式基线（每格 30 次）"),
    (r"Every table in it carries a 客户确认", "Base 里直接改单元格，只有文档版带客户确认列"),
    (r"P1 = decides", "业务重要性只在提示词矩阵行上判"),
    (r"ChatGPT quality trial", "各监测平台的质量试跑"),
    (r"用来分配题量|decides how many Prompts", "优先受众进矩阵行的业务重要性依据"),
    (r"context columns|information columns", "试跑读数放单独的试跑报告"),
    (r"enforced by structure", "防选择偏差靠推荐顺序不读试跑读数"),
    (r"formal set must carry", "验证题是正式基线后的诊断题，不占名额"),
    (r"Accuracy Prompts (are trialled|go through the same trial)|alongside Competitor and Accuracy", "准确性题不进试跑"),
    (r"brand-named Evaluation and Verification", "只写点名评价题，不写点名验证题"),
    (r"Four Stages", "The Stage Chain（六段）"),
    (r"of the 5 runs", "按实际次数写"),
    (r"P1 Attributes land|P1/P2 landing|from the P1 landings|重要性 高 Attributes? (with|land)|where the 重要性 高", "主题从业务重要性为高、中的矩阵行聚出"),
    (r"属性池 优先级|attribute tier|重要性 × 可改变性|importance × changeability", "属性池不出档位；业务重要性只在提示词矩阵行上判"),
    (r"建议优先级", "提示词库只有一列可编辑的提示词优先级，脚本按矩阵行预填"),
    (r"信源壁垒|来源追不上 drop|来源追不上 barrier", "提示词库「可改变性」，按引用前 20 域名判（2026-10-28）"),
    (r"判断冲突", "属性池只判相对竞品，无判断冲突公式（2026-10-28）"),
    (r"「品类基线」|品类基线：|category-baseline row", "不带条件的品类题挂在属性为空的矩阵行（2026-10-28）"),
    (r"买家角色 row|买家角色 行|买家角色行", "受众是否重点只写在业务范围主要受众（优先）（2026-10-28）"),
    (r"category observation Topic|Depth (\(细分\) )?Topics?|Coverage (\(宽泛\) )?Topics?|Coverage and Depth", "主题不分类型（2026-10-28）"),
    (r"Default wording per prompt type|one opening for Discovery|one sentence form|the sentence form is fixed|默认句式", "提示词不限句式和开头，只看该类型题面必须做到什么（2026-10-29）"),
    (r"Default to the report wording", "评价题默认买家问法，Evaluate 命令式只作诊断（2026-10-29）"),
    (r"broad anchor Prompts|low-condition anchor|Every Topic keeps a broad|each candidate Topic has at least one natural no-qualifier", "不写宽泛品类题，品牌方点名大词才写（2026-10-29）"),
    (r"人群只判重要性", "优先受众进矩阵行的业务重要性依据"),
    (r"领先 / 持平 / 劣势|领先 or 持平|领先 before 持平|领先 rows|领先 goes before", "相对竞品取值用 优势 / 持平 / 劣势 / 待确认"),
    (r"What is \[category\] and what should buyers consider", "What should I look for when choosing [category] for [condition]?"),
    (r"「竞品对比」|竞品对比题|点名品牌的竞品对比|类型[^。]{0,6}竞品对比", "提示词类型标签「对比」"),
    (r"购买影响", "属性池的「重要性」"),
    (r"必须给", "优先提供 / 有就提供"),
    (r"at least five independent Prompts|five-Prompt floor|每个候选主题至少 5|每个主题至少 5|Topic recommendation order|推荐顺序（|P1 rows are a Topic's core", "主题不设题数底线（2026-10-30）"),
    (r"主题排序|Topics are not ranked|主题不排优先级", "主题排优先级：高 ＝ 有业务重要性为高的行，中 ＝ 有搜索需求，低 ＝ 都弱（2026-11-01）"),
    (r"tag_search_signals|keyword-profiles|打类型提示", "打标脚本已删，搜索词逐条人工判断（2026-10-30）"),
    (r"adstransparency|广告透明度中心.{0,6}按竞品|竞品搜索广告文案", "广告透明度中心已删（2026-10-30）"),
    (r"reads low mention across its Discovery|read low in the trial|在试跑里读数低就配|试跑读数低就配", "验证题只在试跑后按 selection-rules 第 8 步的两个条件触发（2026-11-02 审核清单）"),
    (r"Written only after the formal baseline|after the formal baseline reads low|正式基线读数低后再写|After the formal baseline, add the diagnostics", "验证题只在试跑后按 selection-rules 第 8 步的两个条件触发（2026-11-02 审核清单）"),
    (r"目标题数|覆盖情况|target_count|planned_prompts|source_slices", "矩阵不设目标题数和覆盖情况，题数由行上的属性推出（2026-10-31）"),
    (r"库分层|看什么指标|group_role", "题的用途由提示词类型推出，不另存字段（2026-11-01）"),
    (r"待确认.{0,12}(封顶|停在 P2)|caps? at P2|normally stays at P2", "待确认不碰行档位（2026-10-31）"),
    (r"业务重点 × 买家证据|business focus × buyer-evidence|证据强.{0,4}证据弱", "行优先级只看业务重要性（2026-10-31）"),
    (r"劣势.{0,8}(不挂|never listed)", "劣势属性可以挂在矩阵行上，写题时剔除（2026-10-31）"),
    (r"标(为|注)?「?品牌自述|labelled \*\*品牌自述|品牌自述」?标签", "品牌取值只写值和出处，不标品牌自述（2026-10-31）"),
    (r"after-sales-rules|representative-library|aleyda-21-step|peec-geobubbles|deep-research-brief|check_matrix_coverage", "规则合并为 selection-rules.md，对照笔记移出 skill（2026-11-01）"),
    (r"从属性关联识别|clustered from 提示词矩阵 rows|共同需求（功能", "主题按核心购买需求聚合矩阵行（2026-10-31）"),
    (r"八段|八个旅程阶段|eight (journey )?stages|eight-stage|解决问题阶段|购后支持阶段", "旅程阶段三段：需求认知 / 方案考虑 / 购买决策（2026-11-02）"),
    (r"中档行?只出 ?1 道|中档出 1 道|a 中 row gets one|中 row gets one", "业务重要性为高、为中的行都按决策差异出题（2026-11-02）"),
    (r"核心层|实验层|监测层|core layer|experimental layer|monitoring layer", "考核按类型认：发现＋替代；三层已取消（2026-11-02）"),
    (r"行优先级|row priority|row tier", "矩阵行叫「业务重要性」（2026-11-02）"),
    (r"高档行|中档行|低档行|a 高 row|a 中 row|高档切片|低档切片", "业务重要性为高 / 中 / 低的行（2026-11-02）"),
    (r"发现至少一半|发现题不到一半|Discovery is at least half|at least half Discovery", "删告警 40；考核题 ＝ 发现＋替代（2026-11-02）"),
    (r"计不计入提及率考核未定|counts toward the KPI is undecided|mention rate .{0,30}undecided", "替代题计入提及率考核（2026-11-02）"),
    (r"准确性题一次只问|准确性题：答案层|验证与准确性题的标准答案", "准确性题不进选词题库（2026-11-02）"),
    (r"购后支持|「评估」(阶段|「)|「解决问题」", "旅程阶段三段：需求认知 / 方案考虑 / 购买决策（2026-11-02）"),
    # strict：这些写法本身就是错的现行描述，出现即命中
    (r"只有发现题算提及率|只有发现题算|only Discovery counts", "考核题 ＝ 发现＋替代（2026-11-02）", True),
    (r"售后生词的权威|售后生词规则.{0,6}权威", "选词规则唯一来源是 selection-rules.md（2026-11-01）", True),
    (r"(提示词)?矩阵的?「约束」列", "矩阵不设约束列，条件取属性的「常见约束」（2026-10-31）", True),
    (r"按「品牌自述」记录", "品牌取值只写值和出处（2026-10-31）", True),
    (r"矩阵行?的?优先级", "矩阵行叫「业务重要性」（2026-11-02）", True),
    (r"Google 月搜索(量)?或 GSC 展示|搜索需求（Google 月搜索量或", "主题优先级中档以 Google 月搜索量为准，GSC 展示只作补充（2026-11-02）", True),
    (r"试跑后用评价题、对比题的回答补判", "待确认用调研预跑的评价答案、试跑的发现题和对比题答案补判（2026-11-02）", True),
    (r"交易场景(的)?发现题?|交易 situations", "「在哪买、价格、库存」不进选词题库；发现题只在方案考虑行（2026-11-02）", True),
    (r"有证据显示买家会拿某个竞品来比才开|对比有证据才出|替代、对比有证据才出", "对比题品牌方要才出（2026-11-02）", True),
    (r"(?<!现状)替代[^。]{0,40}每个主题最多 1 道", "替代题每个有证据的竞品 1 道（2026-11-02）", True),
    (r"声誉 / 信任监测[^。|]{0,20}暂不做|评价[^。|]{0,10}暂不做", "声誉 / 信任已开放：品牌方选了且买家在问可信度才出评价题（2026-11-02）", True),
    (r"对比题要不要建议品牌方加，看行业", "对比题按第 1 步证据表判断，行业只作参考（2026-11-02）", True),
    (r"品牌方勾选|勾选的目标|基础服务，默认包含|默认勾上", "目标题不预选：品牌方写选项名，发现题照常默认出（2026-11-02）", True),
    (r"内容被引用|内容引用（", "问题解决不作为目标选项，仍是品牌方点名才出（2026-11-02）", True),
    (r"必须接入（只读|必须接入，只读", "GSC / Bing 优先提供，默认品牌方导出、取最长历史（2026-11-02 审核清单）", True),
    (r"最优先的问题|问题例子", "不单设：目标那一行按重要性排先后，答错例子写进「品牌方关心的问法」（2026-11-02）", True),
    (r"品牌方的目标归两类", "目标四类：发现型可见度 / 竞争定位 / 品牌呈现监测 / 声誉信任监测（2026-11-02）", True),
    (r"推荐顺序：主题优先级 →", "主题优先级定买哪些主题；主题内按提示词优先级挑题（2026-11-02）", True),
    (r"(?<!不)先剔除品牌词|剔除品牌词，留问句", "GSC 研究阶段全收，按本品牌词 / 竞品词 / 非品牌查询分开用（2026-11-02）", True),
    (r"默认只开方案考虑|购买决策行默认不开|只在品牌方要问题解决题时开", "核心受众 × 核心场景 × 三段全面梳理，组合成立就开行、没证据标假设；题型按目标在第 7 步筛（2026-11-02 审核清单）", True),
    (r"依据与说明", "主题表只留「主题优先级依据」一个依据字段（2026-11-02）"),
    (r"只留在内部(题库|矩阵)|不写进对客(确认)?表|行不进对客表|它们不进对客确认表", "对客表放完整矩阵，本期不出题的行依据末尾写「本期不出：……」（2026-11-02）", True),
    # 2.4.0（Suda 2026-11-02 审核清单拍板）
    (r"(GSC|Bing|Search Console|Webmaster)[^。；]{0,40}必须提供|必须提供[^。|；]{0,20}(GSC|Bing|Search Console)",
     "GSC / Bing 优先提供（默认品牌方导出，取最长历史）（2.4.0）", True),
    (r"只开值得测的行", "核心受众 × 核心场景 × 三段全面梳理，组合成立就开行，没证据标假设（2.4.0）", True),
    (r"有(买家|公开)?证据的阶段才开行|没有证据的阶段不开|有(买家|公开)证据就开行|开行要的证据",
     "组合成立就开行；证据只决定写什么依据、标不标假设，阶段表那一列叫「依据举例」（2.4.0）", True),
    (r"证据决定这一行开不开|证据只决定开不开", "证据只决定写什么依据、要不要标假设；开不开看组合成不成立（2.4.0）", True),
    (r"品牌方选了品牌呈现时，按品牌方见过的答错例子|按「品牌方关心的问法」里他们见过的答错例子|品牌呈现的验证题（第 1 步）|发现题试跑一次都没提到品牌时，我们照常补|诊断用的在试跑后补",
     "验证题写题时不出，只在试跑后按 selection-rules 第 8 步的条件触发（2.4.0）", True),
    (r"(为中的行只在相对竞品为优势时)|劣势、待确认的属性不配",
     "零提及诊断：行为高或中、属性为优势或持平（2.4.0）", True),
    (r"品牌方要几道出几道", "问题解决题每个主题最多 2 道，占正式名额（2.4.0）", True),
    (r"(?<![0-9])告警 8(?![0-9b])|\| 8 \| 两道题措辞", "措辞高度相似的告警编号是 8b，报错 8 是题面完全重复（2.4.0）", True),
    # 2.4.0 D 组与收口（Suda 2026-11-02）
    (r"备注(开头)?写原因|依据、本期不出题的原因", "本期不出的原因写在业务重要性依据末尾「本期不出：……」，不写备注（2.4.0 D1）", True),
    (r"\| — \| 无条件的发现题", "告警都带编号：W53 题没有所在行、W54 无条件发现题、W55 手动改档没写理由（2.4.0 D5）", True),
    (r"发现型过半", "售前专属检查不查发现型占比（2.2.1 已删）", True),
    (r"（Google；韩国用 Naver", "月搜索量取哪家的只在 selection-rules 第 6 节定义，其他地方写指针（2.4.0 C3）", True),
    (r"config\.audience_terms missing|没写 audience_terms[^。]{0,10}告警", "没写 audience_terms 时告警 39 转人工检查（2.4.0 D3）", True),
]
HISTORY = re.compile(
    r"retired|retiring|退役|取消|superseding|superseded|replac|renamed|改名|简化|formerly|former|"
    r"\bwas\b|before 20\d\d|pre-20\d\d|原「|原名|旧|never|removed|已删|删除|不再|legacy|old flow|"
    r"was called|called .+ before|reversing|推翻|拆出|split out|不写|不设|不再写|there is no|\d\d-\d\d 前|之前|以前"
)


def scan():
    hits = []
    for path in TARGETS:
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, now, *strict in RETIRED:
                m = re.search(pattern, line)
                if m and (strict or not HISTORY.search(line)):
                    hits.append({"file": str(path.relative_to(SKILLS)), "line": n, "term": m.group(0), "now": now})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    hits = scan()
    for h in hits:
        print(f"{h['file']}:{h['line']}  「{h['term']}」 → {h['now']}")
    print(f"共 {len(hits)} 处退役说法" if hits else "通过：没有退役说法")
    if a.json:
        Path(a.json).write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
