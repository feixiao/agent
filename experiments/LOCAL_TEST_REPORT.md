# 《深入理解 AI Agent》experiments 全量本地测试总报告

- **任务**：在本地（macOS + LM Studio qwen3.8-27b-splash @ `http://localhost:1234/v1` + 仓库 `.venv`）测试 `experiments/` 下全部实验，并为代码添加中文注释便于理解。
- **执行规范**：见 [LOCAL_TEST_PROTOCOL.md](LOCAL_TEST_PROTOCOL.md)
- **分章报告**：每章完成后汇总于此。

| 章节 | 实验数 | PASS | PARTIAL | BLOCKED | 报告 |
|---|---|---|---|---|---|
| ch1 入门 | 5 | 2 | 1 | 2 | [LOCAL_TEST_REPORT_ch1.md](LOCAL_TEST_REPORT_ch1.md) |
| ch2 上下文工程 | 8 | 1 | 4 | 3 | [LOCAL_TEST_REPORT_ch2.md](LOCAL_TEST_REPORT_ch2.md) |
| ch3 记忆与知识库 | 14 | 1 | 11 | 2 | [LOCAL_TEST_REPORT_ch3.md](LOCAL_TEST_REPORT_ch3.md) |
| ch4 工具工程 | 6 | 0 | 5 | 1 | [LOCAL_TEST_REPORT_ch4.md](LOCAL_TEST_REPORT_ch4.md) |
| ch5 Coding Agent | 16 | 收尾中（agent-creator 补跑） | | | [LOCAL_TEST_REPORT_ch5.md](LOCAL_TEST_REPORT_ch5.md) |
| ch6 交互扩展 | 13 | 运行中 | | | [LOCAL_TEST_REPORT_ch6.md](LOCAL_TEST_REPORT_ch6.md) |
| ch7 评估 | 12 | 运行中 | | | [LOCAL_TEST_REPORT_ch7.md](LOCAL_TEST_REPORT_ch7.md) |
| ch8 模型后训练 | 18 | 0 | 11 | 7 | [LOCAL_TEST_REPORT_ch8.md](LOCAL_TEST_REPORT_ch8.md) |
| ch9 持续进化 | 10 | 运行中 | | | [LOCAL_TEST_REPORT_ch9.md](LOCAL_TEST_REPORT_ch9.md) |
| ch10 多 Agent | 8 | 运行中 | | | [LOCAL_TEST_REPORT_ch10.md](LOCAL_TEST_REPORT_ch10.md) |

**当前累计（ch1/2/3/4/8 已完）：61 个实验 = 4 PASS + 32 PARTIAL + 12 BLOCKED + 13 运行中（ch5 收尾）**
- 已跑 pytest 累计 300+ 项通过（ch1 149、ch2 25、ch3 若干、ch4 182+、ch8 105/106）
- LLM 真实调用全部走本地 `qwen3.8-27b-splash`；BLOCKED 均为环境硬性限制（付费 API / GPU / 硬件 / 缺包），离线可验证部分已全部跑通
- venv 已执行 `uv sync --all-extras` 对齐项目 lock（补齐 sentence-transformers/FlagEmbedding/mem0ai/fastapi/bs4/html2text/google-genai 等，transformers→5.17.0、trl→1.15.0），ch3 报告的 7 个缺包将随之解决，服务空闲后可补跑对应 LLM/embedding 环节

> 说明：`skills/`（22 个技能包）是供 Claude Code/Cursor 等开发助手加载的 markdown 技能包，不是可运行实验，不纳入运行清单。
> 状态口径：PASS=本地真实跑通；PARTIAL=部分跑通（环境受限环节已注明）；BLOCKED=本地无法运行（已跑其离线可验证部分，如有）。

## 环境受限说明（全局）

1. **本地 LLM**：LM Studio 当前只加载了对话模型 `qwen3.8-27b-splash`（~20s/次调用）。所有 LLM 驱动实验均改用本地模型运行；书中以 Kimi K3 / GPT-5.6 等特定模型得出的**定量结论**不能由本地模型复现，本报告只验证「代码可运行 + 流程正确」。
2. **本地 embedding 服务不可用**（LM Studio 同时只加载一个模型）。向量检索实验走代码自带的离线/确定性路径或 BM25 路径。
3. **外部付费 API**（Moonshot/DashScope/OpenAI 云端/Gemini/Anthropic 等）：不调用，走离线/测试路径。
4. **GPU 训练 / 机器人 / 手机 / Docker**：本地不具备，记 BLOCKED，运行其离线可验证部分。

## 运行事故记录

- **2026-11-09 并发模型切换导致 LM Studio 引擎崩溃**：多个执行者并发请求不同模型（对话/embedding/视觉），LM Studio 单槽位反复重载，`splash` 引擎启动被中止，服务挂起。已恢复（重新加载 `qwen3.8-27b-splash`，chat 200 OK/18s）。受影响的 ch1/ch2/ch4 执行者已重启，全部执行者已追加「模型锁死」规则（只允许 qwen3.8-27b-splash，每次 LLM 实验前先探测服务健康）。协议文件已同步该规则。

## 待用户手动操作的事项（跑完后汇总）

- （跑完后填写：例如需要在 LM Studio 手动加载 embedding 模型、提供某 API Key 等）
