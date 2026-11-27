"""售前报告流水线驾驶脚本:一条命令跑到下一个暂停点。

把「题库 → 采集目录 → HTML」的确定性步骤按序串起来;遇到需要语义工作或人工
决定的环节(付费采集、词表冻结、情感判读、翻译)时停下,打印该暂停点
缺什么文件、按什么格式补,补齐后重跑本命令自动续跑。译文是必做环节,
不跑等于把英文原文交给中文客户。

本脚本只调度、不实现:每一步都 subprocess 调用各 skill 既有脚本,口径
和校验完全以被调脚本为准。步骤定义的权威说明仍是 SKILL.md 执行流程。

用法(最少参数):
    python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
        --case <Case.json 或 v8 题库.json> --lexicon <词表.json> --out-dir <输出目录> \
        [--brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌>] \
        [--regions US] [--platforms chatgpt,gemini,aimode,overview] [--dry-run]

采集目录不存在时停在阶段 -1,打印 collect_answers.py 的采集命令(付费,不代跑)。
不带 --brands/--target 时跳过情感环节:报告不出情感模块,问题明细与抽屉也不出情感列。
商品卡默认不出:未传 --shopping-cards 开时,不出购物商品卡模块、核心洞察的商品卡提及率和回答详情里的
商品卡;本次采集一张带目录的商品卡都没有时,写了开也不出(见 render-spec「模块显隐」)。
翻译环节按 translation-batches 目录是否就绪自动接入,缺席不阻塞主链。
售前诊断报告必须带 --diagnosis:缺了停在阶段 5d,按 geo-gap-diagnosis 的写法补 diagnosis.json;
售后基线要出「诊断与行动」时在 config 的 extra_modules 写 diagnosis。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
MONITORING = SKILLS / "geo-monitoring" / "scripts"
CRAWL_INTEGRITY = MONITORING / "audit_crawl_integrity.py"
COLLECTOR = MONITORING / "collect_answers.py"
JUDGE = SKILLS / "geo-metrics" / "scripts" / "sentiment_sentences.py"


class Pause(Exception):
    """流水线在暂停点停下:message 告诉使用者补什么。"""


def run(cmd: list, dry: bool, label: str) -> None:
    printable = " ".join(str(c) for c in cmd)
    print(f"→ [{label}] {printable}")
    if dry:
        return
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode != 0:
        raise SystemExit(f"[{label}] 失败(退出码 {result.returncode}),流水线停止:{printable}")


def stage_collect(args) -> None:
    """阶段 -1：采集目录是否齐全。采集要付费，驾驶脚本只检查、不代跑。"""
    manifest = args.collect / "collect-manifest.json"
    if args.collect.exists() and not manifest.exists():
        print(f"○ [-1 采集] {args.collect} 不是 collect_answers.py 产出的目录(无 manifest),跳过采集检查")
        return
    if not args.regions:
        raise SystemExit("[-1 采集] 采集目录还没建好，必须传 --regions(如 US 或 SG,MY)")
    base = [sys.executable, COLLECTOR, "--questions", args.questions,
            "--out", args.collect, "--regions", args.regions, "--platforms", args.platforms]
    printable = " ".join(str(c) for c in base)
    print(f"→ [-1 采集检查] {printable} --check-only")
    if args.dry_run and not args.collect.exists():
        return
    result = subprocess.run([str(c) for c in base + ["--check-only"]])
    if result.returncode == 3:
        raise Pause(
            f"采集目录未齐(Scrapeless 付费调用,驾驶脚本不代跑)。先看调用量:\n    {printable} --dry-run\n"
            f"确认后 export SCRAPELESS_API_KEY 再执行:\n    {printable}\n"
            f"补采后仍无效的格会移出分母并登记在 {manifest}。")
    if result.returncode != 0:
        raise SystemExit(f"[-1 采集检查] 失败(退出码 {result.returncode})")


def case_from_bank_config(config: dict) -> dict:
    """本地手写的 v8 题库常常没有 config.case_fields（只有线上 normalize_case 会写）：
    这时按 config 顶层的品牌、官网、别名、竞品、主题拼一份报告用 Case，
    免得 load_case 报「缺少品牌或官方域名」（Zhiqinghe 2026-11-26）。"""
    fields = {"品牌": config["brand_name"], "官方域名": config["official_domain"]}
    if config.get("brand_aliases"):
        fields["品牌别名"] = config["brand_aliases"]
    category = config.get("category_label") or config.get("product_line")
    if category:
        fields["品类"] = category
    topics = [t.get("topic") for t in config.get("topics") or [] if isinstance(t, dict) and t.get("topic")]
    if topics:
        fields["主题"] = ",".join(topics)
    for index, comp in enumerate(config.get("competitors") or [], 1):
        if isinstance(comp, dict) and comp.get("name") and comp.get("domain"):
            fields[f"竞品 {index}"] = comp["name"]
            fields[f"竞品 {index} 官网域名"] = comp["domain"]
    return fields


def resolve_case(args) -> None:
    """--case 可以直接给 v8 题库 JSON：取其中 config.case_fields 作为报告用 Case。"""
    raw = json.loads(args.case.read_text(encoding="utf-8"))
    config = (raw.get("config") or {}) if isinstance(raw, dict) else {}
    fields = config.get("case_fields")
    if not fields and config.get("brand_name") and config.get("official_domain"):
        fields = case_from_bank_config(config)
    if not fields:
        return
    # Case 输入合同 v2 不收品类，选词把推出来的品类名写在 config.category_label
    if config.get("category_label") and not fields.get("品类"):
        fields = {**fields, "category_label": config["category_label"]}
    derived = args.out_dir / "case.json"
    derived.write_text(json.dumps(fields, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ [Case] 从 v8 题库取 Case 字段（config.case_fields，缺时用 config 顶层字段）→ {derived}")
    args.case = derived


def stage_crawl_integrity(args, out: Path) -> None:
    audit = out / "crawl-integrity.json"
    if audit.exists():
        print(f"✓ [0 采集校验] 已存在 {audit}(重跑请先删除)")
        return
    cmd = [sys.executable, CRAWL_INTEGRITY, "--collect-dir", args.collect,
           "--target", args.target or "-", "--out", audit]
    printable = " ".join(str(c) for c in cmd)
    print(f"→ [0 采集校验] {printable}")
    if args.dry_run:
        return
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode == 2:
        raise SystemExit(
            f"[0 采集校验] 有阻断缺陷(退出码 2),按 geo-monitoring/references/crawl-integrity.md 的缺陷分派"
            f"修采集或显式降级口径后再继续。报告:{audit}")
    if result.returncode == 1:
        print(f"⚠ [0 采集校验] 有警告(退出码 1),按缺陷目录补齐口径后再采信指标。报告:{audit}")


def stage_lexicon(args) -> None:
    candidates = args.out_dir / "brand-candidates.csv"
    if args.lexicon.exists():
        print(f"✓ [1 品牌词表] {args.lexicon}")
        # 词表已有也要查漏：品类词表跨客户复用时，新采集里的长尾同类厂商常不在表里（2026-11-20）。
        cmd = [sys.executable, SKILLS / "geo-metrics" / "scripts" / "mine_brand_lexicon.py",
               "--collect-dir", args.collect, "--lexicon", args.lexicon, "--case", args.case,
               "--out", candidates, "--check", "--show-unknown", "0"]
        print(f"→ [1 词表查漏] {' '.join(str(c) for c in cmd)}")
        if not args.dry_run and subprocess.run([str(c) for c in cmd]).returncode == 1:
            message = (f"[1 词表查漏] 有 A 档候选没进词表，或有疑似同一品牌拆成两条(见上方清单与 {candidates} 的 tier 列):"
                       f"同类厂商收进 brands 并写 same_category,不是品牌的写进 stopwords;同一家合并成一条,"
                       f"确是两家写进 distinct_brands,再重跑。不处理会让声量份额分母偏小、竞品漏判或被拆低。")
            if args.allow_lexicon_gaps:
                print(f"⚠ {message} 已按 --allow-lexicon-gaps 放行:{args.allow_lexicon_gaps}")
            else:
                raise Pause(message + "确实不处理时加 --allow-lexicon-gaps \"<理由>\"。")
        return
    run([sys.executable, SKILLS / "geo-metrics" / "scripts" / "mine_brand_lexicon.py",
         "--collect-dir", args.collect, "--out", candidates], args.dry_run, "1 词表挖掘")
    raise Pause(
        f"词表 {args.lexicon} 不存在。已挖掘候选到 {candidates},"
        f"请人工过一遍冻结成 brands[].name/aliases/type 结构后重跑。"
        f"机器无法可靠区分品牌名与品类词,这一步不能自动化。")


def stage_build(args, out: Path) -> None:
    report = out / "report-data.json"
    cmd = [sys.executable, HERE / "build_report_data.py",
           "--collect", args.collect, "--questions", args.questions,
           "--case", args.case, "--lexicon", args.lexicon,
           "--domain-cache", SKILLS / "geo-metrics" / "assets" / "domain-categories.json",
           "--out", report]
    if args.regions:
        cmd += ["--regions", args.regions]
    if args.brand_suffixes:
        cmd += ["--brand-suffixes", args.brand_suffixes]
    if args.shopping_cards:
        cmd += ["--shopping-cards", args.shopping_cards]
    if args.sku_map:
        cmd += ["--sku-map", args.sku_map]
    if args.source_limit is not None:
        cmd += ["--source-limit", str(args.source_limit)]
    if args.allow_unjudged_domains:
        cmd += ["--allow-unjudged-domains", args.allow_unjudged_domains]
    printable = " ".join(str(c) for c in cmd)
    print(f"→ [2 数据生成] {printable}")
    if args.dry_run:
        return
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode == 3:
        # 引用来源门禁（geo-metrics core sources.enforce_judged）：域名判读是语义活，不能自动化。
        raise Pause(
            f"引用来源有超过 5% 的引用来自没判读过的域名，待判清单已写到 "
            f"{report.with_name(report.stem + '.domain-candidates.json')}。逐条读域名和页面标题，"
            f"判成 media_review/ugc/institutional/press_release/other，写回 "
            f"{SKILLS / 'geo-metrics' / 'assets' / 'domain-categories.json'} 后重跑；品牌官网改 Case 或词表，不写缓存。"
            f"确实不判时加 --allow-unjudged-domains \"<理由>\"。")
    if result.returncode != 0:
        raise SystemExit(f"[2 数据生成] 失败(退出码 {result.returncode}),流水线停止:{printable}")


def stage_sentiment(args, out: Path) -> None:
    if not (args.brands and args.target):
        print("○ [3 情感] 未提供 --brands/--target,跳过(报告不出情感模块)")
        return
    units = out / "sentiment-units.json"

    if not units.exists():
        run([sys.executable, JUDGE, "extract", "--bank", args.questions,
             "--crawl-dir", args.collect, "--lexicon", args.lexicon,
             "--output", units], args.dry_run, "3a 情感抽取")
    else:
        print(f"✓ [3a 情感抽取] {units}")

    # 3b 抽取只出 claim；3d/3f 是两趟聚类（语义暂停点）；3c/3e 生成待聚类的去重清单（确定性）；
    # 3g 回装（确定性）。三层各由一趟工序产出——聚类的输入是去重后的清单，因此同一
    # claim 只判一次、同一 attribute 只有一个 theme，不会各片各拍。
    claims_raw = out / "claims-raw.json"
    unique_claims = out / "cluster-claims.json"
    claim_attr = out / "claim-attributes.json"
    unique_attrs = out / "cluster-attributes.json"
    attr_theme = out / "attribute-themes.json"
    claims_file = out / "claims.json"

    if not claims_raw.exists():
        raise Pause(
            f"请抽取 Claim：读 {units}，按 geo-metrics/references/claim-layer-contract.md 逐单元拆出**原子 Claim**，"
            f"每条只给 unit_index / brand / claim / sentiment。"
            f"claim 是**标准化后的语义判断**（例：价格高、未公开定价页），不是原文摘抄；"
            f"一句话含多个观点就拆多条；品牌未提及或无明确倾向的不生成 Claim。"
            f"本环节**不产出 attribute / theme**——它们由随后两趟聚类产出。"
            f"写 {claims_raw}。拿不准的记入 {out}/review-queue.md 交 Suda 裁决，禁止关键词自动打标。")
    else:
        print(f"✓ [3b Claim 抽取] {claims_raw}")

    run([sys.executable, JUDGE, "claims-cluster-list", "--input", claims_raw,
         "--key", "claim", "--output", unique_claims], args.dry_run, "3c 聚类1 输入清单")
    if not claim_attr.exists():
        raise Pause(
            f"请做聚类 1（claim → attribute）：读 {unique_claims} 的去重 claim 清单，"
            f"把**相近的 claim 归到同一 attribute**（例：价格高 / 收费贵 / 定价偏贵 → Pricing > Expensive；"
            f"未公开定价页 / 要联系销售报价 → Pricing > Opaque）。"
            f"attribute 用「维度 > 极性」形式且**跨品牌通用**；每个 claim 只能归一个 attribute。"
            f'写 {claim_attr}（{{"claim": "attribute"}} 或 [{{"claim": ..., "attribute": ...}}]）。')
    else:
        print(f"✓ [3d 聚类1 claim→attribute] {claim_attr}")

    run([sys.executable, JUDGE, "claims-cluster-list", "--input", claim_attr,
         "--key", "attribute", "--output", unique_attrs], args.dry_run, "3e 聚类2 输入清单")
    if not attr_theme.exists():
        raise Pause(
            f"请做聚类 2（attribute → theme）：读 {unique_attrs} 的去重 attribute 清单，"
            f"把 attribute 再聚成**高层中性主题**（例：Pricing > Expensive 与 Pricing > Opaque → Pricing）。"
            f"theme 必须中性（是「价格」不是「价格贵」）；每个 attribute 只能归一个 theme。"
            f'写 {attr_theme}（{{"attribute": "theme"}}）。')
    else:
        print(f"✓ [3f 聚类2 attribute→theme] {attr_theme}")

    run([sys.executable, JUDGE, "claims-assemble", "--units", units,
         "--claims", claims_raw, "--claim-attributes", claim_attr,
         "--attribute-themes", attr_theme, "--output", claims_file], args.dry_run, "3g Claim 回装")

    metrics_file = out / "claims-metrics.json"
    run([sys.executable, JUDGE, "claims-metrics", "--claims", claims_file,
         "--brands", args.brands, "--out-metrics", metrics_file], args.dry_run, "3h Claim 统计")

    run([sys.executable, HERE / "attach_sentiment.py",
         "--report", out / "report-data.json", "--units", units,
         "--labels-dir", out / "sentiment-batches", "--brands", args.brands,
         "--target", args.target, "--claims", claims_file,
         *(["--theme-keywords", args.theme_keywords] if args.theme_keywords else []),
         "--out", out / "report-data.json"], args.dry_run, "3i 情感接入")


def stage_translations(args, out: Path) -> None:
    """译文是必选环节：报告是给中文读者看的，抽屉里必须是中文。"""
    batches = out / "translation-batches"
    if not batches.exists():
        run([sys.executable, HERE / "export_translations.py", "--collect", args.collect,
             "--out-dir", batches, *(["--regions", args.regions] if args.regions else [])],
            args.dry_run, "4a 导出待翻译回答")
        if args.dry_run:
            return
    pending = [p.name for p in sorted(batches.glob("*.json"))
               if not p.name.endswith("-zh.json") and not (batches / f"{p.stem}-zh.json").exists()]
    if pending:
        raise Pause(
            f"译文未齐:{len(pending)} 个批次缺 <批次>-zh.json(如 {pending[:3]})。"
            f"按 SKILL.md 第 6 步的翻译要求逐批翻译,每翻完一条立即落盘,"
            f"补齐后重跑本命令。翻译要求:保留 markdown 结构、品牌名与型号保留英文、"
            f"URL 与数值原样、商品表格照原样、不增删信息。")
    run([sys.executable, HERE / "attach_translations.py",
         "--report", out / "report-data.json", "--batches", batches,
         "--out", out / "report-data.json"], args.dry_run, "4b 译文回填")


def case_report_kind(case: Path) -> str:
    """Case 里的「报告类型」；缺省按售前诊断。"""
    try:
        return json.loads(case.read_text(encoding="utf-8")).get("报告类型") or "售前诊断"
    except (OSError, ValueError, AttributeError):
        return "售前诊断"


def stage_verify_render(args, out: Path) -> None:
    run([sys.executable, HERE / "verify_report_data.py",
         "--report", out / "report-data.json", "--collect", args.collect],
        args.dry_run, "5 独立校验")
    # 页面多选筛选由 report-engine.js 从 facts 现算；每个预算切片对应的单选组合必须与引擎逐项一致
    run(["node", HERE / "check_engine_parity.js", out / "report-data.json"], args.dry_run, "5b 引擎对账")
    if args.difficulty:
        # 竞争难度与优化难度：geo-gap-diagnosis 的 difficulty.py 判，这里只接入并写成对客说法
        run([sys.executable, HERE / "attach_difficulty.py", "--report", out / "report-data.json",
             "--difficulty", args.difficulty, "--out", out / "report-data.json"], args.dry_run, "5c 难度接入")
    # 售后基线也走这条流水线（prepare_baseline.py 在 Case 里写「报告类型」），文件名跟着类型走
    kind = case_report_kind(args.case)
    if args.diagnosis:
        # 诊断与行动：分析师读报告后写成 diagnosis.json，这里只接入，内容原样渲染
        run([sys.executable, HERE / "attach_diagnosis.py", "--report", out / "report-data.json",
             "--diagnosis", args.diagnosis, "--out", out / "report-data.json"], args.dry_run, "5d 诊断接入")
    elif kind == "售前诊断" and not args.dry_run:
        if args.allow_missing_diagnosis:
            print(f"⚠ 售前诊断报告缺诊断，已按 --allow-missing-diagnosis 放行:{args.allow_missing_diagnosis}")
        else:
            raise Pause(
                "售前诊断报告的「诊断与行动」是必选模块，缺 diagnosis.json。"
                "按 geo-gap-diagnosis/references/diagnosis-writing.md 写好后重跑，加 --diagnosis <diagnosis.json>；"
                "确实不出时加 --allow-missing-diagnosis \"<理由>\"。")
    html = out / f"{args.brand_name or 'report'}-{kind}报告.html"
    run([sys.executable, HERE / "render_report.py",
         "--data", out / "report-data.json", "--out", html], args.dry_run, "6 渲染")
    print(f"完成:{html}\n最后一步是人工/代理浏览器验证:逐个切国家/平台/主题,确认各模块有数、无空白、无变形。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collect", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--brands", help="展示品牌(含目标),与词表标准名一致;缺省跳过情感环节")
    parser.add_argument("--target", help="目标品牌标准名")
    parser.add_argument("--theme-keywords", type=Path,
                        help="主题关键词表 JSON;换品类必传,否则主题矩阵落空")
    parser.add_argument("--sku-map", help="本品 SKU 归并表 JSON（见 build_report_data --sku-map）")
    parser.add_argument("--shopping-cards", choices=["开", "关", ""], default="",
                        help="商品卡开关;留空默认关,传开才出(且本次采集至少有一张带目录的商品卡)")
    parser.add_argument("--brand-suffixes",
                        help="逗号分隔的品类/产品线后缀,展示时从品牌名剥掉(如 LED,Display);"
                             "留空用内置净水器词表兜底")
    parser.add_argument("--allow-lexicon-gaps", default="", metavar="理由",
                        help="词表查漏不通过时仍继续(写明理由);缺省暂停")
    parser.add_argument("--difficulty", type=Path,
                        help="geo-gap-diagnosis difficulty.py 的输出目录或 difficulty.json;给了才出「竞争与优化难度」模块")
    parser.add_argument("--diagnosis", type=Path,
                        help="分析师写的 diagnosis.json;售前诊断报告必带,给了才出「诊断与行动」模块")
    parser.add_argument("--allow-missing-diagnosis", default="", metavar="理由",
                        help="售前诊断报告确实不出「诊断与行动」时写理由放行")
    parser.add_argument("--allow-unjudged-domains", default="", metavar="理由",
                        help="引用来源未判读超过 5%% 时流水线默认暂停等补判；写明理由才放行")
    parser.add_argument("--source-limit", type=int,
                        help="引用域名/页面榜单条数,透传给 build_report_data;缺省售前 Top 20,0 为全量(售后)")
    parser.add_argument("--regions", help="逗号分隔区域:新采集时必填(决定采哪些国家),同时透传给 build_report_data")
    parser.add_argument("--platforms", default="chatgpt,gemini,aimode,overview",
                        help="新采集时的平台,默认售前四平台 ChatGPT/Gemini/AI Mode/AIO")
    parser.add_argument("--brand-name", help="输出 HTML 文件名用的品牌名,缺省 report")
    parser.add_argument("--dry-run", action="store_true", help="只打印步骤计划,不执行")
    args = parser.parse_args()

    for path, label in ((args.questions, "题库"), (args.case, "Case")):
        if not path.exists():
            raise SystemExit(f"{label}不存在:{path}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        resolve_case(args)
        stage_collect(args)
        if not args.collect.exists():
            raise Pause(f"采集目录 {args.collect} 不存在(dry-run 到此为止)")
        stage_crawl_integrity(args, args.out_dir)
        stage_lexicon(args)
        stage_build(args, args.out_dir)
        stage_sentiment(args, args.out_dir)
        stage_translations(args, args.out_dir)
        stage_verify_render(args, args.out_dir)
    except Pause as pause:
        print(f"\n⏸ 暂停点:{pause}\n补齐后重跑同一命令即可续跑。")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
