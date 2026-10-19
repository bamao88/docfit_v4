# 填写合同（Fill Contract）

> 状态：草案 v0。遵守 `00-product.md` §3.2、§3.4、§4.7；骨架见 `contracts/unit-skeleton.md`。
> 本文只回答：填写合同里有什么。**不回答**：A 怎么产出它（`modules/A-template-extraction.md`）、C 怎么用（`modules/C-assembly.md`）。
> 生产者：A⑧。消费者：C、入库审核。与干净模板 Word 一起构成模板资产。

## 1. 整体

| 项 | 含义 |
|---|---|
| 通用头 | 见 `design/04-data-and-runs.md` §2 |
| `school_id`、`asset_version` | 哪所学校、哪一版资产 |
| `source_sha256` | 学校原件哈希 |
| `units` | 单元列表，按文档顺序 |
| `roles` | 角色 → 样式来源 |
| `generated` | 生成对象（目录域、页码域）的位置 |

## 2. 单元

| 字段 | 含义 |
|---|---|
| `unit_id` | 合同内唯一 |
| `type` | 单元类型（取自 `data/unit-types.yaml`） |
| `handling` | 原样保留 / 填写 |
| `range` | 起止对象 id（原件 id 空间） |
| `display_name` | 给界面提示用的名字，如"封面" |
| `slots` | 仅填写单元有 |

## 3. 槽位

| 字段 | 含义 |
|---|---|
| `slot_id` | 合同内唯一；内容控件标签为 `docfit:slot:<slot_id>` |
| `skeleton_slot` | 对应骨架里的槽位名 |
| `kind` | 字段 / 结构 / 标签 / 生成（与骨架一致） |
| `ref` | 字段名或结构角色名（字段注册表） |
| `optional` | 来自骨架的"可选"。**不等于"必填"**："必填"的来源未定，见 Q9 |
| `region` | 仅"结构"类：可重复区域的起止，C 在此插入内容 |
| `prototypes` | 仅"结构"类：角色 → 原型槽位 |
| `repeat_break` | 仅"结构"类：重复时是否带分页（A §5.6） |

## 4. 角色

| 字段 | 含义 |
|---|---|
| `role` | 结构角色名 |
| `source` | school（来自本校原型）/ preset（来自通用样式预设） |
| `prototype` | 原型的位置：本校槽位 id；或预设版本 + 预设角色 id |
| `fingerprint` | 选定原型的格式指纹 |
| `conflicts` | 同一角色出现的其他指纹（R4），供入库审核 |

一个角色只能有一个来源（`00-product.md` §3.4）。

## 5. 规则

1. 合同只说"哪里放什么"，不写格式数值；格式就在干净模板的原型里。
2. 合同里出现的字段名、角色名、槽位名，都必须在字段注册表和骨架中存在。
3. 原样保留的单元也列出，`slots` 为空，供界面提示（D5）。
