# 对象清单（Object List）

> 状态：草案 v0。遵守 `00-product.md` §4.5；设计见 `design/02-tool.md` §1–§3。
> 本文只回答：对象清单里有什么。**不回答**：怎么生成（`design/02-tool.md`）。
> 生产者：`tool/read`（A② 与 B② 共用）。消费者：A、B 的所有后续步骤，以及校验与评测。

## 1. 整体

| 项 | 含义 |
|---|---|
| 通用头 | 见 `design/04-data-and-runs.md` §2 |
| `doc` | `T`（模板）或 `S`（学生论文） |
| `doc_sha256` | 原件哈希 |
| `objects` | 按部件、按文档顺序排列的对象 |
| `groups` | 复合关系 |
| `boundaries` | 候选分界点（对象 id + 原因） |

## 2. 对象

| 字段 | 含义 | S0 |
|---|---|---|
| `id` | `T:body:0042` | 是 |
| `part` | body / header1 / footer2 / footnotes …… | 是 |
| `kind` | paragraph / table / sdt | 是 |
| `text` | 可见文字；表格为各单元格文字按行拼接 | 是 |
| `label` | 自动编号显示出来的文字，如"1.1"；没有则为空 | 是 |
| `style_name` | 段落样式名（线索，不是格式依据） | 是 |
| `fmt` | 规范化的生效格式（`design/02-tool.md` §3） | 是 |
| `fingerprint` | 格式指纹 | 是 |
| `breaks` | 前有分页、后有分页、分节结尾 | 是 |
| `inline` | 含图片、含公式、含域起止、含文本框、含批注锚点、含修订 | 是 |
| `empty` | 是否为真正的空对象（视图中折叠） | 是 |
| `table` | 行数、列数、合并单元格（只描述结构） | S1 |

## 3. 组

| 字段 | 含义 |
|---|---|
| `id` | 组 id |
| `kind` | field_toc / numbering_list / sdt / figure_caption …… |
| `members` | 对象 id 列表 |

判定、编辑、校验都必须覆盖整个组（P13）。

## 4. 规则

1. 同一文件读两次，输出完全一致（除通用头时间）。
2. 只描述原件，不含任何判断。
3. 新增字段可以，改名或改含义需要升 `schema_version`。
