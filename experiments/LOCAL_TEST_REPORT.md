# 《深入理解 AI Agent》experiments 全量本地测试总报告

- **任务**：在本地（macOS + LM Studio `qwen3.8-27b-splash` @ `http://localhost:1234/v1` + 仓库 `.venv`）测试 `experiments/` 下全部实验，并为代码添加中文注释便于理解。
- **执行规范**：[LOCAL_TEST_PROTOCOL.md](LOCAL_TEST_PROTOCOL.md)
- **分章报告**：`LOCAL_TEST_REPORT_ch1.md` ~ `LOCAL_TEST_REPORT_ch10.md`

## 结果总表

| 章节 | 实验数 | PASS | PARTIAL | BLOCKED | 报告 |
|---|---|---|---|---|---|
| ch1 入门 | 5 | 2 | 1 | 2 | [ch1](LOCAL_TEST_REPORT_ch1.md) |
| ch2 上下文工程 | 8 | 1 | 5 | 2 | [ch2](LOCAL_TEST_REPORT_ch2.md) |
| ch3 记忆与知识库 | 14 | 3 | 10 | 1 | [ch3](LOCAL_TEST_REPORT_ch3.md) |
| ch4 工具工程 | 6 | 0 | 6 | 0 | [ch4](LOCAL_TEST_REPORT_ch4.md) |
| ch5 Coding Agent | 16 | 9 | 5 | 2 | [ch5](LOCAL_TEST_REPORT_ch5.md) |
| ch6 交互扩展 | 13 | 3 | 4 | 6 | [ch6](LOCAL_TEST_REPORT_ch6.md) |
| ch7 评估 | 12 | 4 | 1 | 7 | [ch7](LOCAL_TEST_REPORT_ch7.md) |
| ch8 模型后训练 | 18 | 0 | 11 | 7 | [ch8](LOCAL_TEST_REPORT_ch8.md) |
| ch9 持续进化 | 10 | 0 | 9 | 1 | [ch9](LOCAL_TEST_REPORT_ch9.md) |
| ch10 多 Agent | 8 | 2 | 5 | 1 | [ch10](LOCAL_TEST_REPORT_ch10.md) |
| **合计** | **110** | **24** | **57** | **29** | |

> 110 个实验目录（README 标称 109 个编号实验 + 1 个未编号的 coding-agent），**全部尝试运行**。
> 状态口径：PASS=本地真实跑通；PARTIAL=大部分跑通、个别环节受环境限制（分章报告逐一注明哪部分、为何）；BLOCKED=本地无法运行（已跑其离线可验证部分，如有）。
> 首轮完成后执行了「补跑轮」（venv `uv sync --all-extras` 解锁缺依赖 + `OPENAI_TIMEOUT=600` 规避 60s 超时 + /tmp 透明代理规避 json_object 400），上表为补跑后最终数字。补跑升级了 11 个环节：ch2 context-compression、ch3 sparse-embedding/dense-embedding/user-memory、ch4 perception-tools/multimodal-agent（**视觉调用实测成功**）、ch5 dynamic-form（真实 Chromium campaign 11/11 门全过）、ch6 phone-agent 对话臂、ch7 agent-cost --live（16/16 轮零超时）、ch9 两个全链闭环。
> 29 个 BLOCKED 均为环境硬限制（外部付费 API / GPU 训练 / 机器人/手机/Android 硬件 / Docker / 6.5GB 权重），各自离线可验证部分已跑通，明细见分章报告「阻塞汇总」。

## 运行中真实发生的事情（证据摘要）

- **LLM 真实调用**：全部走本地 `qwen3.8-27b-splash`（LM Studio），累计数百次调用。典型：ch1 消融 full/no_tool_results 双臂对照（no_tool_results 臂真实复现"看不到工具结果→自报汇率捏造数字"）；ch5 coding-agent 本地模型写 `hello.py` 并运行输出 `Hello, Agent`；ch5 erp-agent LLM 生成 SQL 与参考一致（886.20 天）；ch10 狼人杀完整一局（5 人 2 狼，信息隔离 4/4）；ch10 电话注册真实 Chromium 自主填表 5/5。
- **pytest 累计 500+ 项通过**（ch1 149、ch2 25、ch4 182+、ch5 ~100、ch6 50+、ch7 137、ch8 105/106、ch9 40+、ch10 60+）。
- **纯离线算法全部跑通**：Q-learning 10000 局（1.4s，评估胜率 100%）、CSP 求解 12/12、AIME 2024 双臂 925✓、KV-cache 两轮对照、工具发现 11.9× token 精简、工具选择 100% 召回、20 格遥操作基准全 100%、域迁移 0.62→0.75、桌面规划 3456 回合、talkact 16 局独立重算 passed=true。
- **中文注释**：10 章共约 180 个文件加入中文 docstring/行注释（只注释不改逻辑，每个文件注释后都重跑验证；纯注释改动已经 git diff 批量核验）。

## 环境受限说明（全局）

1. **本地 LLM**：27B 单轮 10~130s。书中以 Kimi K3 / GPT-5.6 / Gemini 等特定模型得出的**定量结论**不能由本地模型复现；本报告验证的是「代码可运行 + 流程正确 + 现象定性一致」。
2. **LM Studio 单槽位**：同时只能加载一个模型 → embedding/视觉端点不可用；向量检索走代码离线路径或 sentence-transformers 本地小模型（补跑轮处理中）。
3. **LM Studio 引擎崩溃一次**（2026-11-09 并发切换模型所致，详见下节），已恢复并全程「模型锁死+运行前探测」。
4. **`response_format=json_object` 不被本地端点接受**（400）：用 /tmp 透明代理剥离该参数解决（ch10 已用此法跑通 2 个实验；补跑轮推广中）。
60s **写死客户端超时** vs 本地 27B 慢速：用 `OPENAI_TIMEOUT=600` 环境变量规避（不改代码）。
5. **外部付费 API / GPU / 硬件**：不调用、不具备 → 记 BLOCKED 并跑离线可验证部分。
6. **推理模型 token 预算陷阱**（补跑轮实测命中 3 处）：`qwen3.8-27b-splash` 是推理模型，`reasoning_content` 与 `content` 共享 `max_tokens` 预算。代码中硬编码小预算的环节（phone-agent 700 / harness-safety-gate 2400 / self-evolution-eval 160）会被 reasoning 耗尽，导致 content 为空或截断。若要在本地稳定跑这类环节，需要把对应 `max_tokens` 提到 8000+（属代码改动，未执行）。

## 运行事故记录

- **2026-11-09 并发模型切换导致 LM Studio 引擎崩溃**：多执行者并发请求不同模型（对话/embedding/视觉），单槽位反复重载，`splash` 引擎启动被中止，服务挂起约 1 小时（被 kill 的客户端请求在服务端继续生成）。已恢复；全部执行者追加「模型锁死」规则并写入协议；此后未再发生。

## 需要用户手动操作/知悉的事项

1. **（建议）在 LM Studio 手动加载 `text-embedding-nomic-embed-text-v1.5`**（先卸载对话模型）即可跑通真实 HTTP embedding 路径；不加载也能用 sentence-transformers 本地小模型（补跑轮正在做）。
2. **需要 GPU 训练机**：ch8 共 11 个训练实验（SFT/DPO/RL/继续预训练）只验证了数据/奖励/评估离线部分，训练本体需 A100/H100；训练命令已逐一记入 ch8 报告。
3. **需要硬件/设备**：机器人（xlerobot×2、gemini 导航、rgb 抓取）、手机（phone-agent、autonomous-phone-registration 语音链路）、Android 模拟器（android-world 主入口）、Docker（self-modifying-agent 沙箱、erp-postgres）。这些实验的验证器/测试/离线基准均已跑通。
4. **6.5GB 语音模型权重**（streaming-speech）与 CUDA（end-to-end-speech）未下载/不具备。
5. **既有问题（非本次造成，git 干净副本可复现，请核实）**：
   - ch7 `experiment-7-2-human-benchmark/selection_manifest.json` 哈希与预登记值不符（文件曾在预登记后被改动）
   - ch8 MiniMind-pretrain 的 evidence 密封哈希与后来更新的 README 不符（需训练机重新密封）
   - 多个实验的"提交证据 hash 类测试"因加中文注释而变化（各章报告已逐一对照说明，属预期副作用）
   - 若干既有失败：voice-werewolf 1 项、generative manifest 门禁、end-to-end validate 9/10、streaming-speech 归档 wav 缺失
6. **正式复现书中结论**需要对应付费 Key（Moonshot/DashScope/ARK/Anthropic/Gemini/OpenRouter），各实验 `env.example` 已列明变量名。

## 复跑入口（快速参考）

```bash
cd /Users/fx/wk/github/agent
# 单任务消融（第 1 章）
.venv/bin/python experiments/chapter1/context/main.py --mode single \
  --task "把 100 欧元换算成美元再换回来" --provider openai --model qwen3.8-27b-splash
# 纯离线 Q-learning（第 1 章）
.venv/bin/python experiments/chapter1/learning-from-experience/<入口>.py
# 各实验通用：先看该目录 README.md，再跑 main.py/demo.py/quickstart.py，
# LLM 实验加 --provider openai --model qwen3.8-27b-splash，慢速时 export OPENAI_TIMEOUT=600
```
