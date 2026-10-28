<!-- wisharness:start -->

## WisHarness

`.wisharness/config.json` 中 `enabled` 为 `true` 时：开发前先读基础规范，再读全部匹配专项（可多项）。链接相对项目根目录；必读规范缺失须报告并修复路径，不得跳过。

- 所有开发任务：[基础研发规范](.wisharness/rules/core.md)
- 行为变更、并行协作或跨会话交接：[团队协作](.wisharness/rules/team-collaboration.md)
- UI 修改，尤其是有设计资料或对标产品时：[UI 视觉验收](.wisharness/rules/ui-visual-contract.md)
- 分支、提交、评审、合并或热修复：[Git 分支协作](.wisharness/rules/git-collaboration.md)
- 影响路径、进程、权限、原生模块或平台能力：[跨平台兼容](.wisharness/rules/cross-platform.md)

填写、修改或使用配置前读[配置说明](.wisharness/rules/config-reference.md)。

<!-- wisharness:end -->
