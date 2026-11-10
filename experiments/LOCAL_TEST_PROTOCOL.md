# 本地测试协议（LOCAL_TEST_PROTOCOL）

本文件是「在本地跑通 experiments 下全部实验 + 为代码添加中文注释」任务的统一执行规范。
每位执行者（subagent）负责一章（chapterN），必须遵守以下规则。

## 环境事实（已预先验证，不要重新探测）

- 仓库根目录：`/Users/fx/wk/github/agent`
- Python 解释器（依赖已全部装好，含 torch/langchain/autogen/chromadb/sklearn/audio 等 435 个包）：
  `/Users/fx/wk/github/agent/.venv/bin/python`
  **一律用这个解释器**，不要用系统 python3。
- 本地 LLM：LM Studio，OpenAI 兼容端点 `http://localhost:1234/v1`，已加载模型 `qwen3.8-27b-splash`（27B 推理模型）。
  - 仓库根目录 `.env` 已配置：`LLM_PROVIDER=openai`、`OPENAI_BASE_URL=http://localhost:1234/v1`、`OPENAI_MODEL=qwen3.8-27b-splash`、`OPENAI_API_KEY`（本地占位）。
  - 实验 CLI 若提供 `--provider` 选项：用 `openai`（会读取 .env 的 OPENAI_BASE_URL 打到本地 LM Studio）。
  - 若需要显式 `--model`：用 `qwen3.8-27b-splash`。
  - 该模型是**推理模型**：temperature 必须为 1（多数实验代码已内置兼容处理，无需改动）。
  - 本地推理速度：每次 LLM 调用约 10~40 秒。
- **【硬性规则：模型锁死】** 所有 LLM 请求只允许 `qwen3.8-27b-splash`。
  绝不请求任何其他模型 id（embedding/视觉/gemma/kimi 等）——LM Studio 单槽位切换模型
  会触发引擎重载，曾导致整个服务崩溃（2026-11-09 实际发生过一次）。
  每运行一个 LLM 实验前先探测服务：
  `curl -s --max-time 40 http://localhost:1234/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"qwen3.8-27b-splash","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'`
  30 秒无返回→等 30 秒重试，最多 3 次；仍失败→该实验 LLM 部分记 `BLOCKED(LLM服务暂不可用)`，继续离线部分。
- 本地 **embedding 端点不可用**（LM Studio 同时只加载一个模型，当前加载的是对话模型）。
  依赖向量检索的实验：优先用代码自带的离线/确定性/mock 检索路径（如 BM25、hash 向量）；
  若代码没有离线路径，则运行不依赖 embedding 的部分（如 BM25 稀疏检索、构建索引、评估脚本），
  并在报告中把语义向量部分标记为 `BLOCKED(本地无 embedding 服务)`。
- 需要**外部付费 API**（Moonshot/DashScope/OpenAI 云端/Gemini/Anthropic/SiliconFlow 等）或
  **GPU 训练 / 机器人硬件 / 手机设备 / Docker** 的实验：不要尝试联网调用付费 API，
  改为运行该实验的离线/测试/mock 路径（如有 pytest 就跑 pytest），报告中标记 `BLOCKED(原因)`。

## 每个实验的标准动作

对负责的章节下的**每个实验目录**（不含 `agentbook/`、`skills/`）：

1. **找入口**：`README.md`、`main.py`、`demo.py`、`run_*.py`、`test_*.py`。
2. **本地运行**（能跑就跑）：
   - 纯离线实验：直接跑完整流程。
   - 依赖 LLM 的实验：跑**一次最小规模**运行（1 个任务/1 份文档/2~3 轮迭代，
     用 CLI 参数把规模压到最小；若无法压缩就默认跑一次）。
   - 每次运行捕获输出，报告里粘贴**关键片段**（前/中/后各几行，总长 ≤ 40 行）。
   - 运行卡住超过 5 分钟或明显跑飞：`kill` 掉，按 `PARTIAL` 记录已完成部分。
3. **添加中文注释**（这是用户明确要求的重点）：
   - 对该实验的**入口脚本 + 1~3 个核心模块**添加中文注释：
     模块级 docstring 概括「这个文件是干什么的」；关键函数/类的 docstring 用中文说明
     「做什么、为什么」；主循环/关键分支处加 `# 中文注释`。
   - **只加注释，绝不改动任何逻辑**（不重命名、不改行为、不动字符串常量）。
   - 注释完后**重跑一次**该实验验证仍可运行。
4. 记录到本章报告。

## 禁止事项

- 不得修改：`validation/` 目录、任何 `*.json` 证据文件、`EXPERIMENT_LEDGER.md`、
  `pyproject.toml`、`uv.lock`、其他章节目录、`.env`。
- 不得 `git commit` / `git push`。
- 不得安装新依赖（venv 已齐全；若某实验缺包，记录 `BLOCKED(缺依赖:xxx)` 即可）。
- 不得调用外部付费 API。

## 报告格式（写入 `/Users/fx/wk/github/agent/experiments/LOCAL_TEST_REPORT_ch<N>.md`）

```markdown
# 第 N 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| xxx | `python main.py ...` | PASS / PARTIAL / BLOCKED(原因) | a.py, b.py | 输出片段或原因 |

## 各实验详细记录
### <实验名>
- 命令：...
- 输出片段：```（粘贴）```
- 已注释文件：...
- 备注（阻塞原因 / 需要用户手动做的事）：...
```

状态口径：
- `PASS`：本地真实跑通，输出正常。
- `PARTIAL`：大部分跑通，个别环节受环境限制（说明是哪部分）。
- `BLOCKED(原因)`：本地无法运行（硬件/付费 API/GPU/缺包），已运行其离线可验证部分（如有）。

最后给出本章统计：X 个实验 = a PASS + b PARTIAL + c BLOCKED。
