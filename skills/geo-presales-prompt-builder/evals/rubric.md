# Quality Rubric

- **5**：默认显式生成 v8 `generation_stage=discovery`，每 Topic 至少 5 个独立非品牌购买问题，整批最多 50。按真实需求与证据选题，不凑属性或 Journey 配额；已有 P1 有覆盖。客户确认文档、来源与待验证状态可追溯，不冒充真人原话。补题仅按请求切换 `diagnostic`，保留 Discovery，竞品/评价无固定数量；历史无阶段题库仍能正确校验。JSON、CSV、翻译、Tags 与路由均正确，未试跑如实说明。
- **4**：全部硬门通过，但目标客户、场景或评价标准的覆盖分布略弱，或英文表达略显模板化。
- **3**：实际题量记录与六个常用 Intent Tags 基本正确，但 Topic / Attribute 路由、Attribute Tags、品牌范围 Tag、P1 在 Discovery 中的覆盖、竞品同构或固定模板有一项需要人工修订。
- **2**：仍依赖旧 `target_attributes`、固定三个 Topic、JSON 内保留 `diagnosis_intent` 固定字段、单属性 Verification 或 v5 双重指标路由，虽能生成问题但不符合新流程。
- **1**：实际题量、聚合配额与 `expected_total` 不一致，超过 50 题，Discovery 少于 5 条或未覆盖 P1，品牌边界破坏，品类明显漂移，事实被编造，或把检索词直接作为监测 Prompt。
