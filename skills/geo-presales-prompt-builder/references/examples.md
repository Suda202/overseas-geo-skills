# v8 Edgelight 生问正反例

以下为不同题型的写法示例，不是每轮必须生成的清单。默认 `generation_stage=discovery` 只产出发现型，每 Topic 至少 5 条、整批最多 50；其余题型在用户要求时补充。`attribute_plan` 从 Case 派生，不要求客户填写完整属性库。目录事实不应作为购买属性。

| 默认 Intent Tag | 合格英文示例 | 其他 Tags 与关键要求 |
|---|---|---|
| `Intent: Discovery` | `Which LED display manufacturers are strong options for commercial AV integrators that need both display products and project support?` | `Brand Scope: Non-Branded`；按实际条件挂 `Attribute: Project Support` 等 Tag；不出现 Edgelight 或竞品。 |
| `Intent: Competitor` | `Should commercial AV integrators choose Edgelight or SANSI LED for a fixed-installation LED display project requiring project support?` | `Brand Scope: Branded`；只出现目标品牌与竞品 1；Attribute Tags 对应比较维度。 |
| `Intent: Competitor` | `Should commercial AV integrators choose Edgelight or Unilumin for a fixed-installation LED display project requiring project support?` | 除竞品名外与上一题的题面和 Attribute Tags 完全同构。 |
| `Intent: Evaluation` | `Evaluate the LED display manufacturer and commercial display solution provider company Edgelight on LED display manufacturers and commercial display solution providers` | `Brand Scope: Branded`；固定模板，不出现独立单词 `topic`。 |
| `Intent: Category Awareness` | `What is a LED display manufacturer and commercial display solution provider, and how should I evaluate one for LED display manufacturers and commercial display solution providers?` | `Brand Scope: Non-Branded`；固定品类优先模板，不出现任何品牌。 |

Category Awareness 的退化情形：当 `category_label` 与 Topic 归一后相同（忽略大小写、标点与复数），范围从句只是在复述品类，改用短式。例如 Coverage Topic 就是核心品类时：

`What is a Chinese-language video streaming platform, and how should I evaluate one?`

Edgelight 的 Topic 比品类多出 `manufacturers and` 等限定，不构成复读，仍用完整模板。

如果需要第三条 Competitor，只替换竞品名，保持比较条件；不因 Case 有三个竞品就强制生成三题。

历史 Topic 局部竞品例子：Botslab 行车记录仪仅适用 70mai，家庭安防仅适用 Reolink / aosu。读取历史混合 Case 时保留边界；新 Case 应按不同产品线拆分。补题按实际需要，不跨 Topic 使用竞品。

兼容特例：若某个 Topic 的实际配额被规划为 Discovery 17、Competitor 3、Verification 0、Accuracy 0、Evaluation 4、Category Awareness 1，则该 Topic 合计 25 题，仍是合法 v8 产物；这不要求其他 Topic 也为 25 题，整批仍不得超过 50。

反例：

- `What should buyers look for in an LED display?`：若标为 Discovery，只给标准清单，不要求具体候选；应使用品类优先 Category Awareness 模板，或改问制造商候选。
- `Its product portfolio includes LED displays as a separate product category.`：只验证官网目录分类，不改变采购入围或选型判断。
- `A listed product specifies 12 V, 8 A, and 96 W output.`：宽泛 LED 驱动电源 Topic 下不应以单款 SKU 的孤立精确参数代替品类级选型能力；精确值核对属于具体型号或 Accuracy 合同。
- 默认不生成 Verification 与 Accuracy 题，也不要求上游事实包；如用户明确要求，先单独确认合同。
- 发现型阶段默认生成一整套竞品 Evaluation：超出当前阶段；用户明确要求补充时可另进入 `diagnostic`，不用重写 Discovery。
- `Why is Edgelight better than Unilumin?`：预设胜者。
- `How do Edgelight, Unilumin and LianTronics compare?`：破坏一对一控制变量。
- 为 SANSI LED 问产品范围、为 Unilumin 问刷新率：即使各题合理，也破坏同一 Topic 竞品题“仅竞品名不同”的合同。
- 在 Case 中新增“AI 已把 Edgelight 与项目支持强关联”：这是采集后的 `observed_associations`，不得作为 Builder 输入或预写结论。
- 给不出现任何品牌的 Discovery 写 `Brand Scope: Branded`：品牌范围必须由题面实际提及确定。
- 给“智能行车记录仪”Topic 的问题挂只存在于“家庭安防摄像头”规划中的 Attribute：Attribute Tag 必须回指当前 Topic；若 `Night Vision` 在两个 Topic 都有规划，可在两边使用同名 Tag 跨 Topic 聚合。
