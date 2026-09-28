---
name: geo-presales-eval-case-builder
description: Use when creating, completing, normalizing, auditing, or maintaining a single-product-line brand Case and its customer confirmation document in the overseas GEO presales diagnostic input evaluation set, including generating or revising two to three monitoring Topics, splitting different product lines into separate Cases, writing results to the project Feishu Base, and delegating missing competitor discovery to overseas-geo-competitor-research. Also use for Topic-only maintenance of an existing Case. Do not use for competitor-only research, Prompt generation, answer collection, metric calculation, or report writing.
metadata:
  author: 海外 GEO 项目
  version: "1.8.0"
---

# GEO 售前诊断输入评测集 Case 生成器

把品牌资料整理为一个完整 Case，并默认创建或更新到项目指定的飞书多维表格。每个 Case 对应一条 Record；以业务字段识别记录，不生成 Case 序号。

只审计、建议或预览且未明确要求创建 / 维护的请求保持只读，不写入 Base 或客户文档；客户文档默认创建 / 更新仅适用于获授权的完整 Case，或已有客户文档的维护。

## 开始前

- 读取 [字段合同](references/field-contract.md)。
- 读取 [飞书目标与写入合同](references/lark-base-target.md)，并使用 `lark-base` Skill 执行 Base 操作。
- 读取 [主题生成规则](references/topic-generation-reference.md)；只有拆分存在歧义时再看 [主题拆分示例](references/topic-examples.md)。
- 读取 [客户确认文档规则](references/customer-confirmation-doc.md)。完整 Case 默认同时准备预填的 Feishu 客户确认 / 补全文档；涉及已有文档或 Topic-only 更新时，先按该文件定位并复用原文档身份。
- 读取 [竞品研究交接规则](references/competitor-handoff.md)。竞品名称或官网不足 3 组时，调用 `overseas-geo-competitor-research`；完全未提供竞品时也必须从零研究，不把缺失竞品退回给用户补填。
- 读取 [跨 skill 规范映射](../shared/canonical-intent-mapping.md)；字段别名与词表以本文件为准。
- 从已有执行上下文读取目标市场、语言和 AI 平台；客户可以在确认文档中纠正这些上下文，但它们不新增为 Case 字段。

## 执行

1. 归一化公司、业务 / 产品、品牌、官网、业务模式及输入证据，保留来源冲突和待人工确认项。先锁定单一产品线：一条 Case 只能服务一个购买集合、一组核心客户和一套可共用的竞品。输入包含多条不同产品线时，按产品线分别创建 Case，不得用多个 Topic 把不同产品线塞进同一条 Case（拆分实例见 [主题拆分示例](references/topic-examples.md)）。公司名保留可识别主体名，按字段合同省略无区分度的法律实体后缀。业务模式按当前 Case 的主要购买路径选择 `B2B` 或 `B2C`；只有企业和个人均为核心买方，且购买标准、场景和竞品基本重合时才使用 `B2B / B2C`。两类购买决策差异明显时拆分 Case。
2. 先做 Discovery-first 研究：从公开买方需求、搜索 / 选型语言、场景问题、替代方案和可观察购买标准出发，再用官网和品牌资料核对产品事实与边界。不能只从品牌 USP 反推主题或痛点。提取品类、目标企业画像、目标客户、2–5 条痛点、2–5 条使用场景、2–5 条产品特性、1–5 条差异化优势、适用边界，以及 B2B 专属的购买标准（1–5 条）、集成、兼容或对接要求（1–3 条）和信任与合规（1–5 条），地理与市场有值时才写（1–3 条）；逐项标记为已知证据、研究假设或待客户确认。纯 `B2C` Case 的“目标企业画像”“购买标准”“集成与兼容”和“信任与合规”保持为空，Markdown 中省略整行；只有 `B2B` 和 `B2B / B2C` 填写。目标客户只写会改变购买判断的核心角色或人群，不写“关注什么”；关注点分别归入痛点、使用场景、产品特性或主题。同一字段的多个值合并为一行，值之间用 `，` 分隔；单个值内部尽量用“和”“或”或“；”连接并列要素。适用边界用一句话写清主要适用条件或排除范围，不罗列产品卖点。不得用空泛营销话术补齐。
3. 从第 2 步字段生成主题候选，先按 [主题、属性与标签边界](references/topic-generation-reference.md#主题属性与标签边界) 判断候选是否足以成为 Prompt 集合的主组织单元，再按 `目标客户 × 核心任务 × 评价标准 × 候选品牌 × 优化动作` 合并或拆分。每条 Case 默认生成 3 个正式中文主题：1 个当前产品线的核心品类 Coverage Topic + 2 个彼此明显不同、仍属于同一购买集合的买方场景 Depth Topic；证据不足以支持第二个独立场景时生成 2 个主题（1+1）。不得为了凑数拆同一场景、补另一产品线或制造题量。每个保留的 Topic 必须能形成至少 5 个互不重复的发现型购买意图；不足时合并、记录证据缺口或退回待确认，不造题。主题合并写入同一个“主题”字段并用 `，` 分隔，最多 3 个。所有 Depth Topic 必须与 Coverage Topic 共用目标品牌、产品边界和已冻结正式竞品；若候选实际属于另一条产品线，必须另建 Case，不得作为 Depth Topic。Topic 名通常使用 2–5 个词，优先 2–4 个词，只表达一个核心主题；Coverage Topic 应更短，Depth Topic 仅增加一个必要限定。将横跨 Topic 的能力、特征和评价标准保留在原 Case 字段，供下游派生 Attribute；将诊断意图、品牌范围和其他横向分类留给下游 Tags。只写主题名称，不输出宽泛或细分标签，也不在 Case 或客户文档中分配具体 Prompt / Attribute 配额；下游首阶段只做 Discovery，要求每 Topic 至少 5 条、售前整批不超过 50 条，竞品评价后补且不设固定配额。
4. 处理竞品：已有 3 组经过同一购买集合核验的名称与官网时直接使用；只有 0–2 组、官网缺失或尚未核验购买集合时，调用 `overseas-geo-competitor-research`。已提供项作为优先核验候选，未通过时记录淘汰并自动替换；只将 3 个通过硬门槛的 `formal_competitors` 写回 Case。研究无法冻结时保留错误与证据缺口，不用相邻产品凑数。
5. 起草客户确认文档内容：完整 Case 默认按 [客户确认文档规则](references/customer-confirmation-doc.md) 形成预填草稿，内容包括研究范围、B2B 的目标企业画像与目标客户（persona）或 B2C 的目标客户（audience）、市场与语言执行上下文、优先级、差异化与证据、不能服务 / 可赢边界、独有资产、建议主题及其来源假设，以及要求客户补充的真实买方意图和内部销售 / 客服 / win-loss / GSC 等材料。本步骤不创建或更新文档。AI 预填内容必须标为研究假设或待确认，不能伪装成客户原话；沉默、文档创建或未编辑不等于批准。客户可先纠正已知上下文，但必须补充内部现实，可用访谈或现有材料替代空白长表。若用户明确要求离线交付，仅输出本地材料，不调用 Feishu 文档流程。
6. “补充内容”默认留空。只有当信息无法归入其他字段，且能明确说明会改变哪类问题设计时才填写；与品类、目标企业画像、目标客户、痛点、使用场景、产品特性、差异化优势、适用边界、购买标准、集成与兼容、信任与合规或地理与市场重复时保持为空。补充内容不得替代必填字段。
7. 按 [飞书目标与写入合同](references/lark-base-target.md) 定位目标表，先读取真实 Field schema，再读取现有 Records。以 `品牌名称 + 业务 / 产品名称` 识别单一产品线 Case，用“主题”确认和维护该 Case 的 2–3 个监测视角：同一产品线的补全或维护更新已有 Record；新品牌或新产品线创建新 Record。随后按 [客户确认文档规则](references/customer-confirmation-doc.md) 从现有 Record、handoff 和品牌 + 业务 / 产品名称定位已有客户文档并读回原文。Topic-only 模式只更新“主题”及确需同步的 Topic 边界说明，并在已有客户文档中更新对应章节；没有既有文档时不强制完整 onboarding。
8. 创建使用 `record-batch-create`，维护使用 `record-batch-update`。新增 Record 按飞书默认位置自然追加，不置顶、不倒序，也不移动已有记录。只提交真实 schema 中存在的业务字段，不写 `Case序号`，不维护编号；客户文档 URL 如需交接且 Base 没有现成列，只在交付说明或 handoff 中保留，不扩展 Base schema。认证或权限失败时按 `lark-shared` 以原身份修复，不静默切换 Bot 身份或改交 Markdown。
9. 写入后读回目标 Record，至少核对品牌名称、主题、官方域名、三组竞品及官网、补充内容；确认记录存在且本轮提交字段一致后交付。除离线请求外，仅对完整 Case，或对已有客户文档的 Topic-only 维护，在本步骤使用既有身份通过 `lark-doc` / `lark-cli` 创建或更新预填客户文档；无既有文档的 Topic-only 请求保持不创建。更新必须保留已确认答案和原文档身份，不重复创建客户文档。创建或更新后必须读回文档正文，核对预填草稿已写入且已有确认内容仍在，并返回实际文档 URL / token。文档创建、更新、读回或核对失败时，明确交付为 Base 已完成但客户文档部分失败，或整体阻塞；不得把草稿、计划或待授权说明报告为已成功。不得自动公开分享、改权限或发送消息。

## 本地 Markdown 分支

仅当用户明确要求本地 Markdown、离线交付或评测集导出时，读取 [输出模板](references/output-template.md) 生成无序号标题的两列表，并运行：

```bash
python3 scripts/validate_case.py <case.md>
```

校验失败先修复再交付。该分支不自动追加项目历史 Markdown 评测集，也不重排旧 Case。

## 输出

- 默认输出飞书目标 Record 的创建或更新结果，以及必填项完整性结论和必要的待人工确认项。
- 除离线或明确失败外，完整 Case 输出客户确认 / 补全文档的实际 URL / token、创建或更新结果和回读核对结果；不把 AI 预填内容写成客户语言，不把沉默视为确认。
- 提供使用过的资料来源简表；若调用竞品研究，同时保留竞品选择证据和可比性限制。来源只支撑输入假设，不把厂商自述写成报告结论。
- Topic-only 模式附候选合并或淘汰原因，并报告已有客户文档对应章节的实际更新与回读结果；没有既有文档时不强制创建完整确认流程。

不在本 Skill 内复制竞品研究逻辑；竞品不足时委托专用 Skill。也不生成 Prompt、AI 回答、可见度或情绪指标，不撰写售前报告。
