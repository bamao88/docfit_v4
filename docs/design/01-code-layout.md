# 代码目录与文件职责

> 状态：草案。遵守 `design/00-overview.md`、`02-architecture.md` §2（依赖方向）、§4（防膨胀）。
> 本文回答：仓库里有哪些目录和文件，每个负责什么，谁可以引用谁，步骤脚本长什么样。
> **不回答**：每个文件内部怎么实现；Tool、Harness 的设计细节（见 `02-tool.md`、`03-harness-agent.md`）。

## 1. 目录树

```
pyproject.toml
src/docfit/
  core/                        共享基础，不含任何业务
    ids.py                     source_id 的格式、拆分派生、插入派生
    artifact.py                产物读写：通用头、schema 校验、内容哈希、输入哈希核对
    datatables.py              读取并校验 data/ 下的数据表，带版本
    schemas/                   交接物的 pydantic 模型，一个交接物一个文件
      object_list.py  unit_table.py  decisions.py  fill_contract.py
      content_model.py  match_table.py  verify_report.py
  tool/                        确定性的 Word 能力（Tool 角色）
    package.py                 docx 打开与保存：部件、关系、命名空间保真
    read/objects.py            原件 → 对象清单（正文、页眉页脚、脚注分部件）
    read/groups.py             复合关系：域（目录）、编号列表、内容控件、图文
    read/labels.py             计算自动编号显示出来的文字（如"1.1"）
    read/boundaries.py         候选分界点
    format/resolve.py          生效格式：文档默认 → 样式链 → 编号 → 直接格式
    format/fingerprint.py      格式指纹与比较
    format/preset.py           读取通用样式预设
    format/materialize.py      把一组样式属性写成 Word 格式
    edit/session.py            编辑会话：读取时建 id → 元素映射，按 id 定位，一次保存
    edit/clear_text.py         删除段落内的指定文字
    edit/split.py              在指定句子之后拆分对象
    edit/slot.py               把对象变成占位（内容控件）
    edit/clone.py              克隆原型对象并换成新文字
    edit/remove.py             删除对象（只供 C 删除用完的原型）
    edit/carry.py              （S1）跨文档搬运图片、批注等带关系的对象
    edit/toc.py                （S4 预留）按参数生成目录域
    diff/compare.py            预期对象清单与实际对象清单逐项比对
    render/libreoffice.py      渲染 PDF 和页面图（辅助；旧 Docker 渲染器为候选）
  agent/                       模型调用（不是 Agent 本身）
    client.py                  统一接口：judge(请求) → 结构化结果
    backends/sdk.py            Claude Agent SDK 后端，含隔离配置（D12、D13）
    backends/api.py            （预留）直接调 API 的后端（Q12）
    cache.py                   请求哈希 → 响应落盘，用于重放
  harness/                     通用的裁判与调度
    loop.py                    判定循环：发出、校验、只回发出错项、重试、降级
    validators.py              校验器登记表（数量有上限）
    views.py                   对象清单 → 给 Agent 看的紧凑视图
    prompts.py                 从 data/prompts 组装提示词
    parallel.py                并行调度与限速
  pipelines/
    a_template/                模块 A，每个步骤一个文件（步骤见 modules/A）
      steps.py                 步骤顺序清单（只有清单，没有逻辑）
      a02_read.py  a03_units.py  a04_check_units.py  a05_dispatch.py  a06_judge_unit.py
      a07_check_decisions.py  a08_execute.py  a08_expect.py  a09_verify.py  a10_review_sheet.py
    b_content/                 模块 B（步骤见 modules/B）
      steps.py  b02_read.py  b03_regions.py  b04_check_regions.py  b05_judge_region.py
      b06_check_roles.py  b07_build_model.py  b08_verify.py
    c_assemble/                模块 C（步骤见 modules/C）
      steps.py  c01_match.py  c02_gaps.py  c03_plan.py  c04_execute.py  c04_expect.py  c05_verify.py
      fill/handlers/heading.py  fill/handlers/paragraph.py   （S1 起每个角色一个文件）
  shell/
    cli.py                     docfit asset build | asset approve | convert | step
    jobs.py                    任务目录、输入只读复制、哈希
    assets.py                  模板资产库：版本、审核状态、入库、读取
    publish.py                 最终 Word 与界面提示
data/                          数据表（见 04-data-and-runs.md §1）
.claude/skills/docfit-evals/  Evals Skill：冻结样本与黄金标准、记分板、差异、链路分析、报告、审计（见 design/06-quality.md §4）
checks/                        架构守卫脚本
tests/                         unit/（Tool 原语、校验器）、replay/（真实样本、缓存的 AI 输出）、live/
assets/  runs/                 运行产生，不进版本库
```

## 2. 依赖规则（由 import-linter 强制）

| 包 | 可以引用 | 不可以引用 |
|---|---|---|
| `core` | 无 | 任何内部包 |
| `tool` | `core` | `agent`、`harness`、`pipelines`、`shell` |
| `agent` | `core` | `tool`、`harness`、`pipelines` |
| `harness` | `core`、`agent` | `tool`（Harness 不含 Word 细节）、`pipelines` |
| `pipelines/x` | `core`、`tool`、`harness` | 其他 `pipelines/y`（模块之间只靠产物）、`lxml` |
| `shell` | `core`、`pipelines` | `tool` 内部、`agent` |
| Skill 脚本 | `core`、`tool.read`、产品 CLI | `harness`、`pipelines` 内部；产品代码不得引用 Skill |

第三方库也有边界：`lxml` 只在 `tool/`；`claude_agent_sdk` 只在 `agent/backends/sdk.py`。

## 3. 步骤脚本的统一形态

每个步骤文件只做一件事，形态固定：

```python
INPUTS  = ["object_list", "unit_table"]      # 读哪些产物
OUTPUTS = ["unit_table_checked"]             # 写哪些产物

def run(ctx: StepContext) -> None:
    ...                                       # 读输入 → 计算 → 写输出
```

- `StepContext` 只提供：任务目录、数据表、产物读写、Agent 客户端、日志。
- 步骤之间不互相调用。`steps.py` 只列顺序，没有判断逻辑；不设"总管"（`02-architecture.md` §4.2）。
- 任何步骤可单独重跑：`docfit step a06 --job <任务目录>`。
- 输入产物的哈希写在输出的通用头里；上游重跑后，下游自动知道自己过期。
- `a08_expect.py`、`c04_expect.py` 是纯函数，只根据判定推导"预期对象清单"，供校验步骤使用，不碰 Word。

## 4. 体量

- 每个文件不超过约 400 行（`02-architecture.md` §4.1）。按上面的划分，步骤脚本预计 50–150 行，Tool 原语 50–200 行。
- 某个文件逼近上限，说明它承担了两件事，按职责拆分，不往里加。
- `checks/` 在提交前运行：文件行数、依赖方向、代码中不得出现学校 ID 或学校名称。
