"""跨主题切片标签：按 config.tag_dimensions 从矩阵行派生每道题的 tags（Suda 2026-11-03）。

导出脚本（export_upload_csv.py）和 validator（W62、W63）共用这里的口径，两边算出来的标签一致。只认现行结构的题库。

- 维度：目标客户 / 使用场景（取题所在矩阵行的 audience / scene）、
  属性（维度名沿用，值是约束条件：取 attribute_ref，只出 values 里登记的「差异化优势」对应的约束条件）、
  自定义（营销活动、季节节点这类矩阵里没有的方向，题目自己的 tags 里写，values 必须登记）。
- 一个值要同时落在至少 2 个主题、至少 5 道题上才出标签；只落在 1 个主题、或和主题名相同的值和主题重复，不出。
- 计数只算会上传的题：停测、需修改、问题解决不算。
"""

DIMENSION_FIELDS = {"目标客户": "audience", "使用场景": "scene"}
DIMENSIONS = (*DIMENSION_FIELDS, "属性", "约束条件", "自定义")  # 属性、约束条件是同一维度的两个叫法
MIN_TOPICS = 2
MIN_PROMPTS = 5
SKIP_STATUS = {"停测", "需修改"}
TYPE_ZH = {"Discovery": "发现", "Competitor": "对比", "Alternatives": "替代", "Evaluation": "评估",
           "Information": "问题解决", "Trust": "验证", "Transactional": "交易", "Support": "售后"}  # 八类意图类型


def _text(value):
    return str(value or "").strip()


def _items(value):
    items = value if isinstance(value, (list, tuple)) else [value]
    return [_text(v) for v in items if _text(v)]


def counted(q):
    """会进上传 CSV 的题才计数。"""
    return _text(q.get("status")) not in SKIP_STATUS and _text(q.get("prompt_type")) != "Information"


def handwritten(q):
    """题目自己写的 tags，去掉重复的类型中文名。"""
    return [t for t in _items(q.get("tags")) if t not in TYPE_ZH.values()]


def _entries(config):
    raw = config.get("tag_dimensions")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def _slices(config):
    rows = config.get("slices")
    if not isinstance(rows, list):
        return {}
    return {_text(r.get("slice_id")): r for r in rows if isinstance(r, dict) and _text(r.get("slice_id"))}


def _values(entry, q, slices):
    dim = _text(entry.get("dimension"))
    listed = _items(entry.get("values"))
    if dim in DIMENSION_FIELDS:
        found = _items((slices.get(_text(q.get("slice_ref"))) or {}).get(DIMENSION_FIELDS[dim]))
        return [v for v in found if not listed or v in listed]
    if dim in ("属性", "约束条件"):
        attr = _text(q.get("attribute_ref"))
        return [attr] if attr and attr in listed else []
    if dim == "自定义":
        return [t for t in handwritten(q) if t in listed]
    return []


def tag_plan(config, questions):
    """返回 (每道题的派生标签 {id(q): [..]}, 问题清单, 没登记的手写标签 {题号: [..]})。"""
    entries = _entries(config)
    slices = _slices(config)
    topic_names = {_text(t.get("topic") or t.get("name")) for t in config.get("topics") or [] if isinstance(t, dict)}
    topic_names |= {_text(q.get("topic")) for q in questions}
    topic_names.discard("")
    rows = [q for q in questions if counted(q)]
    problems, passing = [], {}
    custom = set()
    for entry in entries:
        dim = _text(entry.get("dimension"))
        if dim not in DIMENSIONS:
            problems.append(f"维度「{dim or '（空）'}」不是 {' / '.join(DIMENSIONS)} 之一")
            continue
        if not _text(entry.get("basis")):
            problems.append(f"{dim}：没写 basis（跨哪些主题、切完谁拿去做什么）")
        if dim == "自定义":
            if not _items(entry.get("values")):
                problems.append("自定义：要在 values 里登记标签值")
            custom |= set(_items(entry.get("values")))
        spread = {}
        for q in rows:
            for v in dict.fromkeys(_values(entry, q, slices)):
                topics, n = spread.setdefault(v, (set(), 0))
                topics.add(_text(q.get("topic_id") or q.get("topic")))
                spread[v] = (topics, n + 1)
        if len(spread) >= 2 and all(len(t) == 1 for t, _ in spread.values()):
            problems.append(f"{dim}：每个值都只落在一个主题里，这个维度就是主题的切分轴，和主题重复，不做标签")
            continue
        for v, (topics, n) in spread.items():
            if v in topic_names:
                problems.append(f"{dim}「{v}」和主题名相同，和主题重复")
            elif len(topics) < MIN_TOPICS:
                problems.append(f"{dim}「{v}」只落在 1 个主题（{next(iter(topics))}），和主题重复，按主题筛即可")
            elif n < MIN_PROMPTS:
                problems.append(f"{dim}「{v}」只有 {n} 道题，切出来读数不稳（至少 {MIN_PROMPTS} 道）")
            else:
                passing.setdefault(dim, set()).add(v)
    tags = {}
    for q in questions:
        out = []
        for entry in entries:
            ok = passing.get(_text(entry.get("dimension")), set())
            out += [v for v in _values(entry, q, slices) if v in ok and v not in out]
        tags[id(q)] = out
    unregistered = {}
    for q in rows:
        extra = [t for t in handwritten(q) if t not in custom]
        if extra:
            unregistered[_text(q.get("question_id"))] = extra
    return tags, problems, unregistered
