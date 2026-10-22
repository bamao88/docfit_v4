---
name: docfit-evals
description: DocFit Evals（评测）。每件开发任务完成后必须调用：在冻结样本上重放产品全链路，生成记分板、变化对照、产品 AI 思考全链路与链路分析，经独立审计后输出一个本地 HTML 报告交给产品负责人裁决。也用于排查"某次运行哪里出了问题"。没有生成本报告的任务不算完成。
---

# DocFit Evals

设计依据见 `docs/design/06-quality.md`；任务流程见 `docs/06-workflow.md`。本 Skill 只写"怎么做"。

本 Skill 是四部分中的 **Evals**：先在第 0 步运行业务代码的 **Tests**，再读取产品运行时产生的 **Checks** 结果和 **Tracing** 记录，加上 `standards/`，打分、对比基线、分析问题在哪层，输出报告；第 8 步的审计和产品负责人的裁决属于 **Review**。**不重新实现任何 Checks**，只汇总它们的结果。

## 何时调用

- **每件任务收尾时，必须调用。** 报告没生成、或审计没通过，不得向产品负责人说"完成"。
- 排查问题时：对某次运行单独生成链路报告（跳过第 3、4 步）。

## 输入

- 任务卡：`docs/tasks/active/<任务 id>.md`（读"预期影响范围"和"完成条件"）。
- 基线：`runs/baseline/`，即产品负责人最近一次接受时的产物。
- 冻结样本清单与标准：`standards/`。

## 步骤

0. **Tests**：`scripts/tests.py`。运行业务代码的自动化测试（单元、集成、回归重放）和架构守卫（`checks/`：行数、依赖方向、禁用字符串）。**不通过就停下**，回到开发，不往后做。结果写入 `tests.json`，供第 7 步放进报告。
1. **重放**：`scripts/replay.py <任务 id>`。在 `standards/samples.yaml` 列出的全部冻结样本上跑完整产品链路，Agent 用 replay 模式（无缓存的调用才真实调用模型）。产物写到 `runs/<任务 id>/`。
2. **记分板**：`scripts/scoreboard.py`。汇总 Checks 结果（A⑨、B⑧、C⑤）和黄金对比，并与基线比较，标出"第一个出错的步骤"。
3. **变化与范围**：`scripts/diff_scope.py`。逐对象对比本次与基线，找出变化的页面，与任务卡的预期影响范围对比，超出的标红。
4. **对照页**：`scripts/pages.py`。只渲染变化的页面，每页三栏：原件 / 基线 / 本次。
5. **全链路**：`scripts/trace.py`。把每个样本的 Tracing 记录（`contracts/run-trace.md`）汇编成链路数据。
6. **链路分析**：启动一个**新的子代理**，只给它 `prompts/analyst.md` 和第 2–5 步产出的数据路径，只读权限。它写出 `analysis.json`。
7. **生成报告**：`scripts/report.py`，把第 0–6 步的数据合成 `runs/<任务 id>/report/report.json` 和 `index.html`。
8. **审计**：启动另一个**新的子代理**，只给它 `prompts/auditor.md`（保护区）、`report.json` 和任务卡，只读权限。它写出 `audit.json`，然后重新运行第 7 步。
9. **呈现**：
   - 审计不通过：回到开发，不交给产品负责人。
   - 审计通过：在内置浏览器里打开 `index.html`，并给产品负责人四行话：结论、范围外变化有几处、需要决定的事（最多三件）、报告路径。

## 产品负责人接受之后

由产品负责人确认后才运行 `scripts/accept.py <任务 id>`：把本次产物设为新基线，把被退回过的页面加入回归样本。AI 不得自行运行。

## 规则

- **不改 `standards/` 和 `prompts/auditor.md`**。需要改时，写在报告"需要决定的事"里。
- **Tests 只运行、不改写**：Evals 调用业务代码的 Tests，不复制、不重新实现；Tests 失败时修产品代码或测试本身，属于开发工作，与 Evals 无关。
- **不用文字总结代替报告。** 给产品负责人的数字只能来自 `report.json`。
- **事实和推断分开**：记分板、差异、轨迹是机器事实；`analysis.json` 是 AI 推断，报告里用不同颜色区分。
- **报告只留在本地**：里面有学生论文内容，不发布、不上传、不提交到 git（`runs/` 已忽略）。
- 修改 `scripts/` 时，与产品代码的修改分开提交，并让 `tests/` 里的正反样本全部通过。

## 目录

```
standards/        保护区：samples.yaml（冻结样本）、gold/（黄金标准）、checks.yaml（不变量清单与阈值）
prompts/          analyst.md（链路分析，可维护）、auditor.md（审计，保护区）
scripts/          tests、replay、scoreboard、diff_scope、pages、trace、report、accept
templates/        report.html（单文件，无外部依赖）
tests/            每个检查器的正反样本
```

当前状态：只有本说明与提示词草案；脚本在 S0 第 2 步实现（`docs/05-roadmap.md`）。
