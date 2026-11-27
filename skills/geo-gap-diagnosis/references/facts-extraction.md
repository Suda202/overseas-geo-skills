# 事实抽取判据（facts_draft.py 的模型步骤）

给模型的说明。每个批次是一个 JSONL，一行是官网某一页的一段正文（`chunk_id`、`url`、`brand`、`text`）。模型逐段抽取，每段交回一行：

```json
{"chunk_id": "…", "facts": [
  {"subject": "W702S Plus", "attribute": "screen brightness", "value": "1000 nits",
   "quote": "1000 nits high brightness IPS screen", "volatile": false}
]}
```

## 抽什么

只抽**关于本品牌和它自己产品的、能判对错的硬事实**：

- 公司：全称、成立年份、总部或联系地址、电话、邮箱、服务的国家地区、资质认证。
- 产品：型号、系统版本、尺寸、规格数字、接口、兼容范围、随箱配件、适用条件和限制。
- 政策：保修期、退货期限、运费门槛、发货地。
- 价格：标价、套餐（`volatile: true`）。库存、促销、销量、评价数同样标 `volatile: true`。

不抽：营销形容词（"best-in-class"、"ultra clear"）、观点、客户评价原文、博客里的行业知识、**页面上竞品的参数**（对比表里的竞品列一律不抽）。

## 怎么写

- `subject`：公司写品牌名；产品写型号原样（大小写照页面），整个系列写系列名。
- `attribute`：用简短的英文小写名词，同一类属性前后写法一致（`price`、`screen size`、`android version`、`warranty`、`headquarters address`）。脚本按对象 + 属性找冲突，写法不一致会漏掉冲突。
- `value`：只写值，必须原样出现在 `quote` 里。
- `quote`：**从这一段里逐字复制**，包含这个值的一句或一个短语，不改写、不拼接、不跨行。脚本逐字校验，对不上的整条退回。
- 一段里同一个事实出现多次只抽一次；没有可抽的事实交回 `"facts": []`，不要跳过这一行。

## 脚本之后做什么

`merge` 校验原文、去重、把同一对象同一属性的不同值标成「冲突」，生成 `facts-draft.csv` 交品牌方逐条确认（通过 / 改 / 删 / 新增）。冲突的那几行要品牌方定哪个是对的，另一个通常就是官网需要改的那页。只有确认过的行进 `facts.md`。
