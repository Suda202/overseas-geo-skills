#!/usr/bin/env python3
"""独立审计：从原始采集 JSON 复算售前报告的全部指标，**不 import 任何项目模块**。

为什么要独立一份：`verify_report_data.py` 复算时复用生产的 `discover_sample_files` 映射，
「文件 → 题目」归属错了它跟着错，对账永远平。这个脚本自己重建映射，所以能查出归属错误
（Obrand 2026-11-11 就是靠它确认 303 个文件 0 错位，同时挖出运行次数排序和裸词别名两个 bug）。

用法：
    python3 -I audit_independent.py --case-dir <含 build/ 与 collect/ 的任务目录>
                                    [--out-dir <输出目录，默认 build/audit>]
                                    [--variant recon|spec] [--seed 20261111]

variant：
    recon（默认）= 按报告的识别口径（剔除图片标签、链接文字与裸 URL，Nothing 区分大小写）
    spec        = 严格按文档口径，不剔除上面这些

退出码：0 = 与报告一致；1 = 有差异（逐条列出）。
"""
import argparse, json, re, csv, glob, os, random, sys
from urllib.parse import urlparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--case-dir", required=True, help="任务目录（下面的 build/、collect/ 由它拼）")
_ap.add_argument("--out-dir", default="", help="输出目录，默认 <case-dir>/build/audit")
_ap.add_argument("--variant", default="recon", choices=["recon", "spec"])
_ap.add_argument("--seed", type=int, default=20261111)
_args = _ap.parse_args()
BASE = _args.case_dir.rstrip("/")
OUT = _args.out_dir or (BASE + "/build/audit")
os.makedirs(OUT, exist_ok=True)
SEED = _args.seed
VARIANT = _args.variant
SUFFIX = '' if VARIANT == 'spec' else '-' + VARIANT

# ---------- 输入 ----------
qs = []
with open(BASE + '/build/questions.csv', encoding='utf-8-sig', newline='') as f:
    for i, row in enumerate(csv.DictReader(f), 1):
        qs.append(dict(qid=i, query=row['query'], topic=row['topic'], regions=[x.strip() for x in row['region'].split(',')]))
case = json.load(open(BASE + '/build/case.json'))
lex = json.load(open(BASE + '/build/brand_lexicon.brand_o.json'))
report = json.load(open(BASE + '/build/report-data.json'))
TARGET = case['品牌']
OFFICIAL = re.sub(r'^www\.', '', urlparse(case['官方域名']).netloc or case['官方域名'])
brands = [dict(name=TARGET, aliases=[TARGET], domains=[OFFICIAL])] + [dict(name=b['name'], aliases=b['aliases'], domains=b['domains']) for b in lex['brands']]
names = [b['name'] for b in brands]

def pat(aliases, cs=False):
    return re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')(?![A-Za-z0-9])', 0 if cs else re.I)
PAT = {b['name']: pat(b['aliases'], VARIANT == 'recon' and b['name'] == 'Nothing') for b in brands}
PAT_CS = {b['name']: pat(b['aliases'], True) for b in brands}  # 变体B：区分大小写

# AI 反问用户的追问块不算品牌提及（生产侧 de_cite_crawl.strip_follow_up_form + strip_choice_lists，
# 2026-11-11 Suda 定）。审计独立实现一遍，避免 import 项目模块：
#   1. ChatGPT 表单：用 follow_up_form 字段定位（第一个问题标题的最后一段 → 提交按钮那一行）整段删；
#   2. 普通追问：向用户提问的句子（非 Markdown 标题）后紧跟 2 条以上短列表项，连问句一起删。
LIST_ITEM = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+(.+?)\s*$")
ASKS_USER = re.compile(r"\byou\b|\byour\b|\bwhich\b|\bwhat\b|你|您|哪", re.I)


def _is_short_item(text: str) -> bool:
    text = text.replace("*", "").strip()
    if re.search(r"[\u4e00-\u9fff]", text):
        return len(text) <= 12
    return len(text.split()) <= 5


def drop_form(text: str, form) -> str:
    if not isinstance(form, dict) or not form.get("questions") or not (form.get("submit_label") or "").strip():
        return text
    paras = [x.strip() for x in re.split(r"\n\s*\n", form["questions"][0].get("label") or "") if x.strip()]
    end = text.rfind(form["submit_label"].strip())
    if not paras or end < 0:
        return text
    hits = [m.start() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(paras[-1]) + r"[ \t]*$", text[:end])]
    start = hits[-1] if hits else text.rfind(paras[-1], 0, end)
    if start < 0:
        return text
    stop = text.find("\n", end)
    return text[:start] + ("" if stop < 0 else text[stop:])


def strip_choice_lists(text: str) -> str:
    lines = text.split("\n")
    drop = set()
    i = 0
    while i < len(lines):
        q = lines[i].replace("*", "").strip()
        if (q.endswith(("?", "\uff1f")) and ASKS_USER.search(q) and not LIST_ITEM.match(lines[i])
                and not lines[i].lstrip().startswith("#")):
            j, items = i + 1, []
            while j < len(lines):
                m = LIST_ITEM.match(lines[j])
                if m and _is_short_item(m.group(1)):
                    items.append(j)
                    j += 1
                elif not lines[j].strip() and not items:
                    j += 1
                else:
                    break
            if len(items) >= 2:
                drop.update([i, *items])
            i = max(j, i + 1)
            continue
        i += 1
    return "\n".join(l for k, l in enumerate(lines) if k not in drop)


FOOT = re.compile(r'^\s*\[(\d+)\]:\s*(\S+).*$', re.M)
CITE = re.compile(r'\[([^\]\n]+)\]\[(\d+)\]')

def host(u):
    h = (urlparse(u).netloc or '').lower().split(':')[0]
    return re.sub(r'^www\.', '', h)

def is_official(h):
    return h == OFFICIAL or h.endswith('.' + OFFICIAL)

# ---------- 题目归属核对 ----------
answers, mismatches, region_bad, nfiles = [], [], [], 0
for reg in ('KE', 'NG'):
    for fp in sorted(glob.glob(f'{BASE}/collect/scraper.chatgpt/{reg}/*.json')):
        nfiles += 1
        fn = os.path.basename(fp)
        m = re.fullmatch(r'(\d{4})(?:-r(\d+))?\.json', fn)
        qid, n = int(m.group(1)), int(m.group(2) or 1)
        d = json.load(open(fp))
        tr = d['task_result']
        q = qs[qid - 1]
        if (tr.get('prompt') or '').strip().lower() != q['query'].strip().lower():
            mismatches.append(dict(file=f'{reg}/{fn}', prompt=tr.get('prompt'), expected=q['query']))
        if reg not in q['regions']:
            region_bad.append(dict(file=f'{reg}/{fn}', qid=qid, regions=q['regions']))
        text = strip_choice_lists(drop_form(tr.get('result_text') or '', tr.get('follow_up_form')))
        answers.append(dict(reg=reg, qid=qid, n=n, file=f'{reg}/{fn}', text=text, valid=bool(text.strip()), products=tr.get('products') or []))

cover_missing = [dict(qid=q['qid'], region=r) for q in qs for r in q['regions'] if not any(a['qid'] == q['qid'] and a['reg'] == r for a in answers)]

# ---------- 单条回答分析 ----------
def analyse(a, P):
    body = FOOT.sub('', a['text'])
    if VARIANT == 'recon':
        body = re.sub(r'<img[^>]*>', '', body)
        body = re.sub(r'\(?\[[^\]\n]*\]\[\d+\]\)?', '', body)
        # markdown 链接/图片整体(含链接文字)；方括号文字里允许转义的 \[ \]（图片 alt 常见）
        body = re.sub(r'!?\[(?:\\.|[^\]\\\n])*\]\(<?https?://[^)>\s]*>?\)', '', body)
        body = re.sub(r'https?://[^\s)>\]]+', '', body)
    foot = {m.group(1): m.group(2) for m in FOOT.finditer(a['text'])}
    first = {}
    for nm in names:
        m = P[nm].search(body)
        if m: first[nm] = m.start()
    order = sorted(first, key=lambda k: first[k])
    a['order'] = order
    a['rank'] = {nm: i + 1 for i, nm in enumerate(order)}
    cites = []
    for m in CITE.finditer(a['text']):
        u = foot.get(m.group(2))
        cites.append(host(u) if u else None)
    if VARIANT == 'recon':
        cites = [h for h in cites if not (h and (h == 'google.com' or h.endswith('.google.com')))]  # 报告 facts.domains 不含 google.com
    a['cites'] = cites
    # 只认带商品目录的购物卡：有 id / cite / offers / price 之一（2026-11-11）
    titles = [(p.get('title') or '').strip() for p in a['products']
              if p.get('id') or p.get('cite') or p.get('offers') or p.get('price')]
    a['cards'] = [t for t in titles if t]
for a in answers:
    analyse(a, PAT)
    a['rank_cs'] = None
# 变体B
def variantB():
    res = {}
    for a in answers:
        body = FOOT.sub('', a['text'])
        first = {nm: PAT_CS[nm].search(body).start() for nm in names if PAT_CS[nm].search(body)}
        res[a['file']] = sorted(first, key=lambda k: first[k])
    return res
VB = variantB()

# ---------- 切片复算 ----------
def metrics(sub, P_rank=None):
    v = [a for a in sub if a['valid']]
    N = len(v)
    cnt = {nm: sum(1 for a in v if nm in a['rank']) for nm in names}
    tot = sum(cnt.values())
    out = dict(valid=N, brands={})
    for nm in names:
        rk = [a['rank'][nm] for a in v if nm in a['rank']]
        out['brands'][nm] = dict(count=cnt[nm], rate=cnt[nm] / N if N else None, sov=cnt[nm] / tot if tot else None, avg_rank=sum(rk) / len(rk) if rk else None)
    allc = [h for a in v for h in a['cites']]
    out['citations'] = len(allc)
    out['official_cites'] = sum(1 for h in allc if h and is_official(h))
    out['official_share'] = out['official_cites'] / len(allc) if allc else None
    carded = [a for a in v if a['cards']]
    out['shopping_answers'] = len(carded)
    out['shopping_rate'] = len(carded) / N if N else None
    tp = PAT[TARGET]
    tc = sum(1 for a in carded if any(tp.search(t) for t in a['cards']))
    out['target_card_hits'] = tc
    out['target_card_rate'] = tc / len(carded) if carded else None
    return out

def sel(reg, topic):
    return [a for a in answers if (not reg or a['reg'] == reg) and (not topic or qs[a['qid'] - 1]['topic'] == topic)]

topics = report['meta']['topics']
slice_keys = [(r, t) for r in ('', 'KE', 'NG') for t in [''] + topics]
recomputed = {f'{r}||{t}': metrics(sel(r, t)) for r, t in slice_keys}

# ---------- 对比 ----------
def pct(s):
    if s in (None, '—', ''): return None
    return float(str(s).rstrip('%')) / 100
TOP = ['Obrand', 'RivalO2', 'Apple', 'Samsung', 'RivalO4', 'RivalO1']
rows, diffs = [], []
def cmp(slice_, metric, rep, mine, tol=0.0006):
    if rep is None and mine is None: ok = True
    elif rep is None or mine is None: ok = False
    else: ok = abs(rep - mine) <= tol
    rows.append(dict(slice=slice_, metric=metric, report=rep, recomputed=mine, ok=ok))
    if not ok: diffs.append(rows[-1])
for key, rc in recomputed.items():
    s = report['slices'][key]
    cmp(key, '有效回答数', s['_counts']['valid_answers'], rc['valid'], 0)
    cmp(key, '提及率[Obrand]/kpis', pct(s['kpis']['mention_rate']), rc['brands'][TARGET]['rate'])
    cmp(key, 'SOV[Obrand]/kpis', pct(s['kpis']['share_of_voice']), rc['brands'][TARGET]['sov'])
    ca = {b['name']: b for b in s['competition_all']}
    for nm in names:
        b = ca.get(nm)
        if b is None:
            rows.append(dict(slice=key, metric=f'{nm}:不在competition_all', report=None, recomputed=rc['brands'][nm]['rate'], ok=rc['brands'][nm]['count'] == 0)); 
            if rc['brands'][nm]['count']: diffs.append(rows[-1])
            continue
        cmp(key, f'提及率[{nm}]', b['mention_rate'], rc['brands'][nm]['rate'])
        cmp(key, f'声量份额[{nm}]', b['share_of_voice'], rc['brands'][nm]['sov'])
        cmp(key, f'平均位置[{nm}]', b['average_rank'], rc['brands'][nm]['avg_rank'], 0.0006)
    cmp(key, '引用总次数', s['sources']['total_citations'], rc['citations'], 0)
    cmp(key, '目标品牌引用份额', pct(s['sources']['official_share']), rc['official_share'])
    sh = s['shopping']['by_platform'].get('chatgpt')
    if sh is None:
        rows.append(dict(slice=key, metric='空切片(无商品卡数据)', report=0, recomputed=rc['valid'], ok=rc['valid']==0))
        if rc['valid']: diffs.append(rows[-1])
        continue
    cmp(key, '商品卡:valid', sh['valid_answers'], rc['valid'], 0)
    cmp(key, '商品卡:出卡回答数', sh['shopping_answers'], rc['shopping_answers'], 0)
    cmp(key, '商品卡触发率', sh['shopping_mode_rate']['raw'], rc['shopping_rate'])
    tgt = sh['target']['shopping_visibility']
    cmp(key, '目标品牌商品卡命中回答数', tgt['numerator'], rc['target_card_hits'], 0)
# 逐题 records 对比（全部切片）
rec_rows = 0
for key in recomputed:
    r, t = key.split('||')
    for rec in report['slices'][key]['records']:
        sub = [a for a in sel(r, t) if a['qid'] == rec['qid'] and a['valid']]
        mm = metrics(sub)
        for b in rec['brands']:
            rec_rows += 1
            mine = mm['brands'][b['name']]
            if b['mention_count'] != mine['count'] or (b['average_rank'] is None) != (mine['avg_rank'] is None) or (b['average_rank'] is not None and abs(b['average_rank'] - mine['avg_rank']) > 1e-6):
                diffs.append(dict(slice=key, metric=f"record q{rec['qid']} {b['name']}", report=dict(count=b['mention_count'], avg_rank=b['average_rank']), recomputed=dict(count=mine['count'], avg_rank=mine['avg_rank']), ok=False))

# ---------- facts.answers 逐条对比 ----------
F = report['facts']; objs = [o['name'] for o in F['objects']]
# facts.n 就是文件名里的 -rN（生产侧 2026-11-11 起按 _run_number 排，不再按字符串排）
idx = {(a['reg'], a['qid'], a['n']): a for a in answers}
idx_literal = idx
n_label_mismatch = 0
fact_diff, fact_n = [], 0
for fa in F['answers']:
    a = idx.get((fa['r'], fa['q'], fa['n']))
    fact_n += 1
    if a is None:
        fact_diff.append(dict(r=fa['r'], q=fa['q'], n=fa['n'], issue='无对应文件')); continue
    rep = {objs[i]: p for i, p in fa['m']}
    if rep != a['rank']:
        fact_diff.append(dict(file=a['file'], facts=sorted(rep.items(), key=lambda x: x[1]), mine=a['order']))
missing_in_facts = [a['file'] for a in answers if (a['reg'], a['qid'], a['n']) not in {(f['r'], f['q'], f['n']) for f in F['answers']}]
# facts 官网引用归属 c 的数量对比
cit_fact = sum(len(fa['c']) for fa in F['answers'])
cit_mine = sum(len(a['cites']) for a in answers)

# ---------- brand_o 出现 ----------
ora = []
for a in answers:
    for m in re.finditer('brand_o', a['text'], re.I):
        s = max(0, m.start() - 120); e = min(len(a['text']), m.end() + 120)
        ora.append(dict(file=a['file'], pos=m.start(), in_footnote=bool(FOOT.search(a['text'][max(0,a['text'].rfind('\n',0,m.start())):m.end()+200]) and a['text'][a['text'].rfind('\n',0,m.start())+1:].lstrip().startswith('[')), context=a['text'][s:e].replace('\n', ' ')))

prod_terms = [dict(file=a['file'], term=m.group(0)) for a in answers for m in re.finditer(r'spacebuds|freepods|airbuds|brand_o|orabuds|powermini', a['text'] + ' '.join(a['cards']), re.I)]
# ---------- 抽样 ----------
random.seed(SEED)
sample = random.sample(F['answers'], 10)
samp = [dict(file=idx[(f['r'], f['q'], f['n'])]['file'], facts_m=[(objs[i], p) for i, p in f['m']], script_order=idx[(f['r'], f['q'], f['n'])]['order']) for f in sample]

# 变体：区分大小写（口径歧义探查）
vb_diff = [dict(file=a['file'], insensitive=a['order'], sensitive=VB[a['file']]) for a in answers if a['order'] != VB[a['file']]]

result = dict(
    seed=SEED, files_checked=nfiles, valid_total=sum(a['valid'] for a in answers),
    prompt_mismatch=mismatches, region_not_allowed=region_bad, coverage_missing=cover_missing,
    comparisons_total=len(rows), record_brand_rows=rec_rows, diffs=diffs,
    facts=dict(n_label_mismatch_vs_filename=n_label_mismatch, answers=fact_n, mismatches=len(fact_diff), mismatch_detail=fact_diff[:60], not_in_facts=missing_in_facts, citations_in_facts_c=cit_fact, citations_mine=cit_mine),
    brand_o_product_terms=prod_terms, brand_o_total=len(ora), brand_o_files=sorted({o['file'] for o in ora}), brand_o_hits=ora,
    sample=samp, casesensitive_variant_diff_count=len(vb_diff), casesensitive_variant_diff=vb_diff[:80],
    all_rows=rows,
)
json.dump(result, open(OUT + f'/recompute{SUFFIX}.json', 'w'), ensure_ascii=False, indent=1, default=str)
print('files', nfiles, 'valid', result['valid_total'], 'prompt_mismatch', len(mismatches), 'region_bad', len(region_bad), 'coverage_missing', len(cover_missing))
print('comparisons', len(rows), 'record rows', rec_rows, 'diffs', len(diffs))
print('facts answers', fact_n, 'facts mismatch', len(fact_diff), 'not_in_facts', len(missing_in_facts), 'cites facts/mine', cit_fact, cit_mine)
print('brand_o product-line terms', len(prod_terms)); print('brand_o total', len(ora), 'files', result['brand_o_files'])
print('casesensitive variant answers differing', len(vb_diff))
