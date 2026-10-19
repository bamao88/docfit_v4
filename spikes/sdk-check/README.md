# SDK 验证：Claude Agent SDK 0.2.128 + MiniMax

日期：2026-10-10。极小输入（三个对象的分类），不含论文内容；结果见 `results.json`、`results2.json`（不含密钥）。
脚本：`spike.py`、`spike2.py`。运行：`/Volumes/ExtSSD2601/Docfit/.venv/bin/python -I spike.py`。

## 已验证

| 问题 | 结论 |
|---|---|
| 结构化输出（`output_format` JSON schema） | **MiniMax 下可用**。输出符合 schema，枚举值被约束；约 7 秒；开启时工具列表只剩内部的 `StructuredOutput` |
| 完全无工具 | `tools=[]` **有效** |
| 同一会话追加反馈（`ClaudeSDKClient`） | **有效**。第二轮只改 c，a、b 与上一轮完全相同，说明上下文被保留 |
| 隔离无关配置 | `setting_sources=[]` **不够**：内置的 14 个技能、37 个斜杠命令、自动记忆目录仍然存在。`skills=[]` 也无效。**有效组合**：`extra_args={"disable-slash-commands": None}`（技能与斜杠命令归零）加环境变量 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`（记忆关闭） |

## 未验证（后续实验）

- 输出违反 schema 时 SDK 的自动重试行为，以及 MiniMax 下的表现。
- 会话中途增加工具（E3）：文档未写，未测。
- 大输入、长输出下的耗时。旧项目发现思考耗时占 86%，`effort` 参数疑似不被 MiniMax 执行，未测。
- 多个单元并行调用时的速率限制。
- 同样输入多次调用的结果稳定性（简单例子里出现过 c 的判断在两次运行间不同）。
