# AI Agent 深度开发闯关实战清单 (todolist.md)

> **核心心法**：$$\text{Agent} = \text{Model（概率模型引擎）} + \text{Harness（确定性工程底盘）}$$
> 本仓库已沉淀完整的理论书稿、原生 C++ 底盘、8 大设计模式代码库、多模态端侧感知实验以及从评测到自演化的 Chapter 4~9 真实实验代码。
> 本清单作为**现存代码与文档的索引导航地图**，带你由浅入深逐一研读、运行、验证与掌握。

---

## 🚀 小白通关专区：四阶段“倒金字塔”成长路线（防劝退指南）

> **写给初学者**：不要从第一行代码硬啃到最后一行！请采用**“先建心智（防忽悠） $\to$ 跑通微循环（见活物） $\to$ 拆解生产底盘（学架构） $\to$ 掌握评测与演进（成专家）”**的节奏通关。

```text
[Day 1] 认知破迷 (建立直觉，不写代码)
  ├─ [ ] 1. 核心公式与本质: README.md (为什么 Agent = Model + Harness? 为什么 Pass^k 会暴跌?)
  ├─ [ ] 2. 12 大排雷地图: docs/books/AI-Agents-in-Depth-QuickStart.md (防死循环、防 Token 飞逝)
  └─ [ ] 3. 产品与商业心智: AI-Agent-Product-Manager-Guide.md (产品五步法、三态权限闸门 Allow/Confirm/Block)

[Day 2-3] 破冰动手 (跑通最简 ReAct 循环)
  ├─ [ ] 1. 极速环境装配: cp .env.example .env && uv sync --extra patterns
  ├─ [ ] 2. 看清手脚怎么动: 运行 patterns/langchain/chap05.py & chap06.py (观察 ReAct 思考与工具分发)
  └─ [ ] 3. 多角色协作体验: 运行 patterns/autogen/chap01.py (观察 UserProxyAgent 与 Assistant 对话)

[Week 2] 进阶专家底盘 (从调包侠走向架构师)
  ├─ [ ] 1. 五层底座与内存段: docs/architecture/01_general_agent_harness_architecture_specification.md (KV Cache 对齐)
  ├─ [ ] 2. 顶级终端智能体拆解: docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md (Claude Code vs OMP)
  ├─ [ ] 3. 端云语音与硬实时: docs/architecture/02_personal_voice_assistant_harness_architecture.md (Barge-in ≤50ms 打断)
  └─ [ ] 4. 工业级 C++ 底座感知: core/native_cpp/include/harness/ (circuit_breaker 熔断器与 token_budget)

[Week 3-4] 商业级落地与专家分水岭 (评测、安全与自演化)
  ├─ [ ] 1. 真实 Coding Agent: experiments/chapter5/coding-agent/ (代码沙箱与 Traceback 自动修复)
  ├─ [ ] 2. 科学客观打分体系: experiments/chapter7/ (Rubric 四档量表、Elo 对战天梯、首错归因 First Mistake)
  ├─ [ ] 3. 商业成本精细核算: experiments/chapter7/agent-cost-analysis/ (Token 消耗、缓存命中与美元账单)
  └─ [ ] 4. 安全策略与自演进: experiments/chapter9/harness-safety-gate/ & self-modifying-agent/ (上线准出检查)
```

## 阶段零：理论基石与心智模型对齐
**目标**：建立“以确定性 Harness 对抗概率模型不确定性（$Pass^k = p^k$）”的工业级认知。

- [ ] **1. 入门破迷与架构概览**
  - [x] 索引文件：[`README.md`](README.md)
  - 🔍 **关注重点**：
    - 理解极简本质公式：$\text{Agent} = \text{Model} + \text{Harness}$。
    - 为什么多步 Agent 会发生死循环和级联衰减（$Pass^k = p^k$，如 $0.95^{10} \approx 59.8\%$）。
    - 浏览仓库快速上手与全局模块索引。
- [ ] **2. 12 大踩坑避险指南**
  - [ ] 索引文件：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md)
  - 🔍 **关注重点**：
    - 认真对照“12 大排雷地图”：防死循环、Token 飞逝、JSON 格式幻觉、无边界重试。
    - 明确 Agent 项目立项与设计时的反模式（Anti-patterns）。
- [ ] **3. 产品经理实战与设计方法论**
  - [ ] 索引文件：[`AI-Agent-Product-Manager-Guide.md`](AI-Agent-Product-Manager-Guide.md)
  - 🔍 **关注重点**：
    - 商业化落地 $Pass^k$ 生死线。
    - Agent 产品设计标准五步法与三态权限闸门（Allow/Confirm/Block）。
    - 8 项 PRD 交付物自查清单。
- [ ] **4. 系统化电子书与理论全景**
  - [ ] 索引文件：[`AI-Agent-Application-Development-Guide.md`](AI-Agent-Application-Development-Guide.md)
  - [ ] 附带电子书资源：[`docs/books/agentic-design-patterns-cn.epub`](docs/books/agentic-design-patterns-cn.epub) / [`AI-Agents-in-Depth-zh-CN.epub`](docs/books/AI-Agents-in-Depth-zh-CN.epub)
  - 🔍 **关注重点**：
    - Agent 认知循环的本质（Perception $\to$ Planning $\to$ Action $\to$ Memory）。
    - 评测体系（Eval）为何先于 Prompt 编写。
---

## 阶段一：经典 8 大设计模式实操运行 (`patterns/`)
**目标**：通过 LangChain 与 AutoGen 实例，吃透经典编排模式与多智能体交互逻辑。

- [ ] **1. 基础编排与链式模式 (LangChain 视角)**
  - [ ] 索引目录：[`patterns/langchain/`](patterns/langchain/)
  - [ ] 重点脚本：
    - [`patterns/langchain/chap01.py`](patterns/langchain/chap01.py) ~ [`chap03.py`](patterns/langchain/chap03.py)：基础提示、链与工具挂载。
    - [`patterns/langchain/chap04.py`](patterns/langchain/chap04.py)：Router 动态路由分发模式。
    - [`patterns/langchain/chap05.py`](patterns/langchain/chap05.py) ~ [`chap06.py`](patterns/langchain/chap06.py)：ReAct 决策与 Tool-Calling 闭环。
    - [`patterns/langchain/chap07.py`](patterns/langchain/chap07.py) & [`chap11.py`](patterns/langchain/chap11.py)：反思检查 (Reflection) 与人机介入确认 (Human-in-the-Loop)。
  - 🔍 **关注重点**：
    - 工具参数模式校验（Pydantic Schema）。
    - 如何用代码拦截并修正模型工具调用的格式错误。
- [ ] **2. 多智能体协作与对话状态机 (AutoGen 视角)**
  - [ ] 索引目录：[`patterns/autogen/`](patterns/autogen/) 与 [`patterns/autogen/quickstart/`](patterns/autogen/quickstart/)
  - [ ] 重点脚本：
    - [`patterns/autogen/chap01.py`](patterns/autogen/chap01.py)：UserProxyAgent 与 AssistantAgent 基础双角色对话。
    - [`patterns/autogen/chap03.py`](patterns/autogen/chap03.py) ~ [`chap05.py`](patterns/autogen/chap05.py)：代码执行沙箱与外部 API 集成。
    - [`patterns/autogen/chap07.py`](patterns/autogen/chap07.py) ~ [`chap08.py`](patterns/autogen/chap08.py)：群聊管理器 (GroupChatManager) 状态流转机制。
  - 🔍 **关注重点**：
    - 多 Agent 对话中的发言权判定（Next Speaker Selection）。
    - 会话终止条件（Termination Trigger）的设计。

---

## 阶段二：硬核 C++ 原生底盘剖析 (`core/native_cpp/`)
**目标**：跳出 Python 脚本胶水层，学习工业级高性能、微秒级响应与强内存安全的 Harness 实现。

- [ ] **1. 核心架构设计文档研读**
  - [ ] 索引文档：
    - [`docs/architecture/01_general_agent_harness_architecture_specification.md`](docs/architecture/01_general_agent_harness_architecture_specification.md)（通用 Agent Harness 五层架构标准与 OpenHarness/AgentBench/SWE-bench/OpenCode 深度剖析）
    - [`docs/architecture/02_personal_voice_assistant_harness_architecture.md`](docs/architecture/02_personal_voice_assistant_harness_architecture.md)（个人语音助手与端云协同架构：FastAvatar 工业范式）
    - [`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)（Claude Code 垂直共生与 OMP Prewalk 阶梯降模）
    - [`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)（C++ 端侧运行时与 Go 云端微服务架构选型）
  - 🔍 **关注重点**：
    - 为什么生产级关键路径需要 C++/Go 级别的 Harness。
    - 了解低线束税（Low Harness Tax）、KV Cache 字节级静态对齐与无拷贝状态传递。
- [ ] **2. C++ 关键防护与引擎头文件精读**
  - [ ] 索引目录：[`core/native_cpp/include/harness/`](core/native_cpp/include/harness/)
  - [ ] 重点组件：
    - [`circuit_breaker.hpp`](core/native_cpp/include/harness/circuit_breaker.hpp)：**熔断器**，防止单 Agent 陷入死循环及级联故障。
    - [`token_budget.hpp`](core/native_cpp/include/harness/token_budget.hpp)：**Token 预算控制器**，前置预扣与硬限额。
    - [`context_engine.hpp`](core/native_cpp/include/harness/context_engine.hpp)：**上下文引擎**，KV-Cache 前缀静止与窗口无损管理。
    - [`tool_registry.hpp`](core/native_cpp/include/harness/tool_registry.hpp)：**工具注册中心**，类型安全的入参与返回值绑定。
    - [`pii_sanitizer.hpp`](core/native_cpp/include/harness/pii_sanitizer.hpp)：**PII 隐私脱敏网关**。
    - [`harness_engine.hpp`](core/native_cpp/include/harness/harness_engine.hpp) & [`agent_state.hpp`](core/native_cpp/include/harness/agent_state.hpp)：状态机主循环。
- [ ] **3. 本地编译、单元测试与基准性能测试**
  - [ ] 索引工程：[`core/native_cpp/CMakeLists.txt`](core/native_cpp/CMakeLists.txt)
  - [ ] 运行验证：
    - 单元测试：[`core/native_cpp/tests/test_main.cpp`](core/native_cpp/tests/test_main.cpp)
    - 性能压测：[`core/native_cpp/benchmark/benchmark_main.cpp`](core/native_cpp/benchmark/benchmark_main.cpp)
  - 🔍 **关注重点**：
    - 观察微秒级状态路由耗时与内存分配情况。

---

## 阶段三：垂直领域 Agent 实战——自动化与代码生成 (`experiments/chapter5/` & `chapter6/`)
**目标**：通过真实应用场景（代码生成、GUI/Web 自动化、异步事件驱动），理解落地边界。

- [ ] **1. 代码生成与执行 Agent (Coding Agent)**
  - [ ] 索引目录：[`experiments/chapter5/coding-agent/`](experiments/chapter5/coding-agent/)
  - [ ] 重点脚本：[`agent.py`](experiments/chapter5/coding-agent/agent.py)、[`config.py`](experiments/chapter5/coding-agent/config.py)
  - 🔍 **关注重点**：
    - 代码执行沙箱（Sandbox）隔离设计与安全防护。
    - 自纠错循环：语法报错 $\to$ 注入 traceback $\to$ 生成补丁 $\to$ 重新回归。
- [ ] **2. 权限内嵌数据对象 (PEDO 安全架构)**
  - [ ] 索引目录：[`experiments/chapter5/permission-embedded-data-objects/`](experiments/chapter5/permission-embedded-data-objects/)
  - [ ] 重点脚本：[`demo.py`](experiments/chapter5/permission-embedded-data-objects/demo.py)、`core/models.py`
  - 🔍 **关注重点**：
    - 细粒度数据权限管控，防止 Agent 跨权限窃取或污染敏感上下文。
- [ ] **3. 计算机与浏览器操控 (Computer-Use / RPA)**
  - [ ] 索引目录：[`experiments/chapter6/claude-computer-use-native/`](experiments/chapter6/claude-computer-use-native/) 与 [`experiments/chapter9/browser-use-rpa/`](experiments/chapter9/browser-use-rpa/)
  - [ ] 重点脚本：[`browser-use-rpa/quickstart.py`](experiments/chapter9/browser-use-rpa/quickstart.py)、[`demo_email.py`](experiments/chapter9/browser-use-rpa/demo_email.py)
  - 🔍 **关注重点**：
    - 视觉坐标反算与网页 DOM 树动态注入裁剪。
    - 异步事件流机制：参考 [`experiments/chapter6/agent-with-event-trigger/`](experiments/chapter6/agent-with-event-trigger/)。

---

## 阶段四：端侧多模态感知与具身计算 (`perception/` & `docs/multimodal/`)
**目标**：掌握视频、音频、TTS 与端侧小模型（Android/Mac Studio）联合驱动的感知闭环。

- [ ] **1. 多模态技术手册**
  - [ ] 索引文档：[`docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md`](docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md) 与 [`docs/architecture/ON_DEVICE_HARNESS_DESIGN.md`](docs/architecture/ON_DEVICE_HARNESS_DESIGN.md)
  - 🔍 **关注重点**：
    - 端侧 4096 极小上下文约束下的多模态帧压缩方案。
    - 端云协同路由策略（端侧小模型感知意图，云端大模型做复杂决策）。
- [ ] **2. 运行 Perception Labs 实操套件**
  - [ ] 索引目录：[`perception/labs/`](perception/labs/)
  - [ ] 重点脚本：
    - [`01_video_vlm_inference.py`](perception/labs/01_video_vlm_inference.py)：视频流关键帧抽取与 VLM 视觉理解。
    - [`02_audio_whisper_tts.py`](perception/labs/02_audio_whisper_tts.py)：端到端流式语音听觉与合成链路。
    - [`03_vlm_lora_dataset_and_train.py`](perception/labs/03_vlm_lora_dataset_and_train.py)：视觉 LoRA 数据集组装与训练。
    - [`04_export_to_pixel10.py`](perception/labs/04_export_to_pixel10.py)：端侧部署与模型量化导出。
    - [`05_local_multimodal_server.py`](perception/labs/05_local_multimodal_server.py)：本地多模态服务调度。
  - 🔍 **关注重点**：
    - 运行 `bash perception/labs/run_all_labs.sh`，掌握多模态信号如何转换为 Agent 的感知输入。

---

## 阶段五：记忆系统与模型基准评测 (`experiments/chapter7/`)
**目标**：建立完整的 Agent 记忆生命周期评测与工业级 Leaderboard 裁判体系。

- [ ] **1. 用户分层记忆系统评估**
  - [ ] 索引目录：[`experiments/chapter7/user-memory-system-evaluation/`](experiments/chapter7/user-memory-system-evaluation/) 与 [`user-memory-policy-eval/`](experiments/chapter7/user-memory-policy-eval/)
  - [ ] 重点脚本：[`experiment.py`](experiments/chapter7/user-memory-system-evaluation/experiment.py)、[`run_full.py`](experiments/chapter7/user-memory-system-evaluation/run_full.py)
  - 🔍 **关注重点**：
    - 记忆召回率（Recall）、精确度与过时记忆遗忘（Decay）策略。
    - 测量长会话中记忆注入对最终决策成功率的影响。
- [ ] **2. 成本、延迟与模型动作阈值调优**
  - [ ] 索引目录：[`experiments/chapter7/agent-cost-analysis/`](experiments/chapter7/agent-cost-analysis/) 与 [`model-action-threshold/`](experiments/chapter7/model-action-threshold/)
  - [ ] 重点脚本：[`agent-cost-analysis/agent.py`](experiments/chapter7/agent-cost-analysis/agent.py)、[`model-action-threshold/experiment.py`](experiments/chapter7/model-action-threshold/experiment.py)
  - 🔍 **关注重点**：
    - 动作置信度阈值：何时模型应该直接回答？何时必须调用外部工具？
- [ ] **3. 自动化天梯赛评测 (ELO Leaderboard)**
  - [ ] 索引目录：[`experiments/chapter7/elo-leaderboard/`](experiments/chapter7/elo-leaderboard/)
  - [ ] 重点脚本：[`battle_simulator.py`](experiments/chapter7/elo-leaderboard/battle_simulator.py)、[`bradley_terry.py`](experiments/chapter7/elo-leaderboard/bradley_terry.py)
  - 🔍 **关注重点**：
    - 基于 Bradley-Terry 模型构建双盲对战与 Elo 评分体系。

---

## 阶段六：模型专项蒸馏与偏好对齐 (`experiments/chapter8/`)
**目标**：当通用模型太贵太慢、或频繁出现格式幻觉时，训练 Agent 专项小模型。

- [ ] **1. 思维链数据蒸馏 (CoT Distillation)**
  - [ ] 索引目录：[`experiments/chapter8/cot-distillation/`](experiments/chapter8/cot-distillation/)
  - [ ] 重点脚本：[`sft_data_auditor.py`](experiments/chapter8/cot-distillation/sft_data_auditor.py)、[`train_student.py`](experiments/chapter8/cot-distillation/train_student.py)、[`evaluate_student.py`](experiments/chapter8/cot-distillation/evaluate_student.py)
  - 🔍 **关注重点**：
    - 教师模型优质轨迹的审核、清洗与过滤规则。
    - 小学生模型（Student Model）对复杂推理轨迹的学习与保真度。
- [ ] **2. 消除“提前完成任务”恶习 (Premature Completion DPO)**
  - [ ] 索引目录：[`experiments/chapter8/premature-completion-dpo/`](experiments/chapter8/premature-completion-dpo/)
  - [ ] 重点文件：[`output/preference_pairs.jsonl`](experiments/chapter8/premature-completion-dpo/output/preference_pairs.jsonl)、[`output/eval_report.json`](experiments/chapter8/premature-completion-dpo/output/eval_report.json)
  - 🔍 **关注重点**：
    - 偏好对齐（DPO）：将“假装完成实际未执行”标记为 Rejected，将“认真检查验证”标记为 Chosen。
- [ ] **3. 复杂 System Prompt 蒸馏至模型权重**
  - [ ] 索引目录：[`experiments/chapter8/prompt-distillation/`](experiments/chapter8/prompt-distillation/)
  - [ ] 重点脚本：[`run_experiment_8_8.py`](experiments/chapter8/prompt-distillation/run_experiment_8_8.py)
  - 🔍 **关注重点**：
    - 将 2k~4k Token 的 System Prompt 固化到模型参数中，减少推理延迟与首字延迟（TTFT）。

---

## 阶段七：安全闸门、轨迹校验与自演化智能体 (`experiments/chapter9/`)
**目标**：掌握商业级 Agent 的终极壁垒——安全拦截、自动裁判与自我代码演变。

- [ ] **1. 确定性安全策略闸门 (Harness Safety Gate)**
  - [ ] 索引目录：[`experiments/chapter9/harness-safety-gate/`](experiments/chapter9/harness-safety-gate/)
  - [ ] 重点脚本：[`safety_policy_gate.py`](experiments/chapter9/harness-safety-gate/safety_policy_gate.py)、[`output/release_manifest.json`](experiments/chapter9/harness-safety-gate/output/release_manifest.json)
  - 🔍 **关注重点**：
    - 确定性拦截清单与准出放行机制（Release Manifest）。
- [ ] **2. 轨迹验证器与 LLM 裁判 (Trajectory Verifier & LLM Judge)**
  - [ ] 索引目录：[`experiments/chapter9/trajectory-verifier/`](experiments/chapter9/trajectory-verifier/)
  - [ ] 重点脚本：[`verifier.py`](experiments/chapter9/trajectory-verifier/verifier.py)、[`llm_judge.py`](experiments/chapter9/trajectory-verifier/llm_judge.py)、[`run_experiment_9_1.py`](experiments/chapter9/trajectory-verifier/run_experiment_9_1.py)
  - 🔍 **关注重点**：
    - 多维度评估指标校验：任务达成度、调用冗余率、证据链闭环。
- [ ] **3. 自我演进与工具自动合成 (Self-Evolution & Tool Creation)**
  - [ ] 索引目录：[`experiments/chapter9/self-evolving-tools/`](experiments/chapter9/self-evolving-tools/) 与 [`self-modifying-agent/`](experiments/chapter9/self-modifying-agent/)
  - [ ] 重点脚本：[`self-modifying-agent/evolution.py`](experiments/chapter9/self-modifying-agent/evolution.py)、[`candidate_sandbox.py`](experiments/chapter9/self-modifying-agent/candidate_sandbox.py)
  - 🔍 **关注重点**：
    - Agent 在沙箱中为自身编写新 Python 工具代码。
    - 自动化单元测试与安全校验通过后，热加载进 Tool Registry 的闭环。

---

## 快速导航索引表

| 学习阶段 | 核心目录 / 文件 | 关键考察点 / 关注重点 |
| :--- | :--- | :--- |
| **0. 理论认知** | [`docs/books/`](docs/books/) / [`README.md`](README.md) | $Pass^k = p^k$ 级联失效模型、Harness 确定性底盘原理 |
| **1. 经典模式** | [`patterns/langchain/`](patterns/langchain/) & [`patterns/autogen/`](patterns/autogen/) | ReAct、动态路由、多智能体协同、Human-in-the-Loop |
| **2. 原生底盘** | [`core/native_cpp/`](core/native_cpp/) | C++ 熔断器、Token 预算控制、无拷贝上下文引擎 |
| **3. 业务落地** | [`experiments/chapter5/`](experiments/chapter5/) & [`chapter6/`](experiments/chapter6/) | Coding Agent 代码沙箱、PEDO 数据权限、Browser-use RPA |
| **4. 感知计算** | [`perception/labs/`](perception/labs/) | 视听流式处理、端侧 4096 极小窗口上下文装配与量化 |
| **5. 记忆与评测** | [`experiments/chapter7/`](experiments/chapter7/) | 分层记忆衰减、成本阈值、Elo 双盲 Leaderboard 机制 |
| **6. 专项微调** | [`experiments/chapter8/`](experiments/chapter8/) | CoT 蒸馏、Premature Completion DPO 偏好对齐、Prompt 蒸馏 |
| **7. 安全与演进** | [`experiments/chapter9/`](experiments/chapter9/) | 安全策略闸门、Trajectory 轨迹裁判、自生成工具沙箱热加载 |
