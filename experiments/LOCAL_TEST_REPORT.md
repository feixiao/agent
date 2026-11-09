# 《深入理解 AI Agent》experiments 全量本地测试总报告

- **任务**：在本地（macOS + LM Studio qwen3.8-27b-splash @ `http://localhost:1234/v1` + 仓库 `.venv`）测试 `experiments/` 下全部实验，并为代码添加中文注释便于理解。
- **执行规范**：见 [LOCAL_TEST_PROTOCOL.md](LOCAL_TEST_PROTOCOL.md)
- **分章报告**：每章完成后汇总于此。

| 章节 | 实验数 | PASS | PARTIAL | BLOCKED | 报告 |
|---|---|---|---|---|---|
| ch1 入门 | 5 | 进行中… | | | [LOCAL_TEST_REPORT_ch1.md](LOCAL_TEST_REPORT_ch1.md) |
| ch2 上下文工程 | 8 | 排队中 | | | [LOCAL_TEST_REPORT_ch2.md](LOCAL_TEST_REPORT_ch2.md) |
| ch3 记忆与知识库 | 14 | 进行中… | | | [LOCAL_TEST_REPORT_ch3.md](LOCAL_TEST_REPORT_ch3.md) |
| ch4 工具工程 | 6 | 排队中 | | | [LOCAL_TEST_REPORT_ch4.md](LOCAL_TEST_REPORT_ch4.md) |
| ch5 Coding Agent | 16 | 排队中 | | | [LOCAL_TEST_REPORT_ch5.md](LOCAL_TEST_REPORT_ch5.md) |
| ch6 交互扩展 | 13 | 排队中 | | | [LOCAL_TEST_REPORT_ch6.md](LOCAL_TEST_REPORT_ch6.md) |
| ch7 评估 | 11 | 排队中 | | | [LOCAL_TEST_REPORT_ch7.md](LOCAL_TEST_REPORT_ch7.md) |
| ch8 模型后训练 | 18 | 进行中… | | | [LOCAL_TEST_REPORT_ch8.md](LOCAL_TEST_REPORT_ch8.md) |
| ch9 持续进化 | 10 | 排队中 | | | [LOCAL_TEST_REPORT_ch9.md](LOCAL_TEST_REPORT_ch9.md) |
| ch10 多 Agent | 8 | 排队中 | | | [LOCAL_TEST_REPORT_ch10.md](LOCAL_TEST_REPORT_ch10.md) |

> 说明：`skills/`（22 个技能包）是供 Claude Code/Cursor 等开发助手加载的 markdown 技能包，不是可运行实验，不纳入运行清单。
> 状态口径：PASS=本地真实跑通；PARTIAL=部分跑通（环境受限环节已注明）；BLOCKED=本地无法运行（已跑其离线可验证部分，如有）。

## 环境受限说明（全局）

1. **本地 LLM**：LM Studio 当前只加载了对话模型 `qwen3.8-27b-splash`（~20s/次调用）。所有 LLM 驱动实验均改用本地模型运行；书中以 Kimi K3 / GPT-5.6 等特定模型得出的**定量结论**不能由本地模型复现，本报告只验证「代码可运行 + 流程正确」。
2. **本地 embedding 服务不可用**（LM Studio 同时只加载一个模型）。向量检索实验走代码自带的离线/确定性路径或 BM25 路径。
3. **外部付费 API**（Moonshot/DashScope/OpenAI 云端/Gemini/Anthropic 等）：不调用，走离线/测试路径。
4. **GPU 训练 / 机器人 / 手机 / Docker**：本地不具备，记 BLOCKED，运行其离线可验证部分。

## 待用户手动操作的事项（跑完后汇总）

- （跑完后填写：例如需要在 LM Studio 手动加载 embedding 模型、提供某 API Key 等）
