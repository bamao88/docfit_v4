# manual-a：手工完成模块 A（模板提取）

> 实验性质（spike），不是产品代码，不进入运行时。遵守 `docs/modules/A-template-extraction.md` 的步骤划分与 D8（只原位编辑）、D15（内容控件作槽位）。

由 AI 手工充当 A③（单元表）和 A⑥（单元内判定），判定写在 `specs/<学校>.yaml`；
`build.py` 按判定执行 A⑧，`verify.py` 独立重读产物做 A⑨ 比对。产物写到 `assets/<学校>/v0-manual/`，`review.json` 为 `pending`，等入库审核（A⑩）。

```bash
python3 build.py specs/*.yaml
python3 verify.py specs/*.yaml
```

| 文件 | 职责 |
|---|---|
| `specs/*.yaml` | 单元表 + 每个对象的判定（格式见 `spec.py` 文件头） |
| `spec.py` | 读判定和 `data/` 数据表；处理方式只按 `data/unit-types.yaml` 查表 |
| `edit.py` | 三种编辑：清空文字、换成槽位、把复合原型包进块级内容控件 |
| `build.py` | 检查完整/唯一，执行编辑，写干净模板与填写合同 |
| `verify.py` | 预期 vs 实际：对象数不变、未动对象 XML 一致、改动对象的属性/分页/分节不变且文字等于预期、槽位标签与合同一致、其他部件逐字节一致 |

合同中对 `contracts/fill-contract.md` 的补充：结构类单元有一条 `<单元>.content` 槽位，带 `region`、`prototypes`（角色→原型槽位）、`repeat_break`（section/none）、`remove_prototypes_after_fill`；每个原型另有一条槽位，`wrap` 为 run（文字原型）或 block（图、表、公式等复合原型，原样保留在块级内容控件中）。
