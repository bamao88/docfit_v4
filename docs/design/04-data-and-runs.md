# 数据表、产物、运行目录与评测

> 状态：草案。遵守 `00-product.md` §5.3、§5.7；`02-architecture.md` §2.4（优先改数据）。
> 本文回答：数据表放在哪、长什么样；产物的通用头；任务目录和资产库的结构；评测与守卫放在哪。
> **不回答**：各交接物的字段（`contracts/`）。

## 1. 数据表（`data/`）

```
data/
  version.yaml                 数据表整体版本（含字段注册表版本）
  registry/fields.yaml         字段：论文题目、中文摘要、关键词……（contracts/field-registry.md）
  registry/roles.yaml          结构角色：各级标题、段落、图、表、公式、题注……，每个带"是否启用"
  unit-types.yaml              模板单元类型 → 处理方式（原样保留 / 填写）
  regions.yaml                 学生文档区域类型 → 对应字段、是否做区域内判定
  skeletons/<单元类型>.yaml     填写类单元的骨架（contracts/unit-skeleton.md）
  prompts/<模块>/<步骤>/        core.md、<类型>.md、view.yaml
  models.yaml                  每一步的模型、轮数、并发、批大小
  policies.yaml                C 的缺失与多余处理策略（Q1、Q9、Q10 定了之后填）
  presets/general-style.yaml   通用样式预设（取值来自旧项目已验收版本）
```

S0 时这些文件都存在，只是内容少：`unit-types.yaml` 里只有"正文"是填写；`roles.yaml` 只启用标题和段落；`regions.yaml` 只有"正文"做区域内判定。

## 2. 产物的通用头

所有 JSON 产物都有同样的头：

| 项 | 用途 |
|---|---|
| `artifact`、`schema_version` | 是什么产物、哪一版格式 |
| `step`、`code_version` | 哪个步骤、哪个代码版本产出 |
| `inputs` | 每个输入产物的名字和哈希 |
| `datatables_version` | 用的哪一版数据表（含字段注册表） |
| `created_at` | 时间 |

下游步骤读输入时核对哈希；不一致说明上游重跑过，下游需要重跑。

## 3. 任务目录（`runs/`）

```
runs/<任务 id>/
  job.json                     任务类型（建资产 / 转换）、输入、所用资产版本
  inputs/                      输入的只读副本，附哈希
  steps/<步骤>/                该步骤的产物、log.json、agent/（本步骤的调用记录）
  final/                       只在转换任务里存在：最终 Word、界面提示
  eval/                        评测结果（只在评测时生成）
```

## 4. 模板资产库（`assets/`）

```
assets/<学校 id>/<版本>/
  clean-template.docx          干净模板
  fill-contract.json           填写合同
  unit-table.json              单元表（入库审核用）
  manifest.json                原件哈希、数据表版本、代码版本、产出任务 id
  review.json                  审核状态：待审 / 通过 / 驳回；审核人、日期、样式冲突的人工选择
```

- 转换任务只接受 `review.json` 为"通过"的资产（`00-product.md` §2）。
- 资产只增不改；重新提取就是新版本。

## 5. Evals

Evals 由 Skill `.claude/skills/docfit-evals/` 承载（`design/06-quality.md`）。与本文相关的只有两个位置：

- `runs/<任务 id>/report/`：该任务的 `report.json`、`index.html` 和对照页图片；
- `runs/baseline/`：产品负责人最近一次接受时的产物。

黄金标准在 Skill 的 `standards/gold/`，绝不进入 `runs/<任务>/inputs/`（`00-product.md` §5.7）。

## 6. 测试与守卫

| 位置 | 内容 | 何时运行 |
|---|---|---|
| `tests/unit/` | Tool 原语、id 确定性、校验器；用很小的合成 docx | 每次提交 |
| `tests/replay/` | 真实样本整条链，Agent 用 replay 模式（与 Skill 的重放共用样本） | 每次提交 |
| `tests/live/` | 真实调用模型 | 手动 |
| `checks/` | 文件行数、依赖方向、代码中不出现学校 ID 或名称 | 每次提交 |

每个阶段结束时，把该阶段的样本加入 `tests/replay/`。之后任何改动都必须让之前阶段的样本继续通过。
