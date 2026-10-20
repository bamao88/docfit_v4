# DocFit 2

开始任何工作前，按顺序读：

1. `docs/00-product.md`（产品层）
2. `docs/02-architecture.md`（角色边界与防膨胀规则）
3. `docs/06-workflow.md`（任务怎么执行、怎么对结果负责）和 `docs/status.md`（现在在哪）
4. 你要做的模块在 `docs/modules/` 里的文档

**每件任务收尾必须调用 Skill `docfit-evals`**，生成 Evals 报告（HTML）并通过 Review 审计；没有报告的任务不算完成，不得向产品负责人说"完成"。

文档地图与规则见 `docs/README.md`。下层与上层冲突时，停下并指出，不要自行绕过。
文件和文档都要保持小而单一，不得无限增长。
