# 通用 AI Agent Harness 架构与工程实现深度解析（以 Nous Research Hermes Agent 为参考范本）

## 一、 什么是 AI Agent Harness：核心边界与“单核窄腰”范式

### 1.1 Model 与 Harness 的本质分野

在现代自主智能体（Autonomous Agent）工程中，**大语言模型（LLM）本身并不是一个完整的 Agent，而是一个无状态的概率推理内核（Stateless Reasoning Kernel）**。模型只负责在给定 Token 序列的条件下预测下一段文本或结构化工具调用请求；而将这一推理内核封装为具备持久记忆、长程规划、环境感知、工具执行、故障自愈与安全边界的运行时底座，即为 **AI Agent Harness（智能体运行时框架/控制底座）**（参考 [Hermes Agent – The Open-Source AI Harness by Nous Research](https://innfactory.ai/en/ai-harness/hermes-agent/)）。

如果用操作系统作类比，LLM 相当于 CPU 的算术逻辑单元（ALU），而 **Harness 则是完整的操作系统内核（OS Kernel）**：

| 操作系统概念 | AI Agent Harness 对应子系统 | 解决的核心工程问题 | 参考实现（[NousResearch/hermes-agent](https://github.com/nousresearch/hermes-agent)） | 
| ----- | ----- | ----- | ----- | 
| **进程调度器（Scheduler）** | **编排控制回路（Orchestration Loop）** | 管理“思考 $\rightarrow$ 动作 $\rightarrow$ 观察”的回合状态机、流式中断、重试退避与预算熔断 | `AIAgent.run_conversation()` 与 `agent/turn_*.py`（[Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)） | 
| **L1/L2 高速缓存控制器** | **提示词组装与前缀缓存引擎（Prompt & Prefix Cache Engine）** | 防止动态状态（时间戳、目录、新工具）击穿服务商 KV Cache，降低首字延迟（TTFT）与推理成本 | 三层静态组装 + 单次用户消息旁路通道（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)） | 
| **虚拟内存与分页管理（MMU）** | **上下文窗口治理引擎（Context Governance & Compaction）** | 在有限上下文窗口内平衡历史保真度与信噪比，避免“中间迷失（Lost-in-the-Middle）”与窗口溢出 | 锚点计量 + 4 阶段压缩 + 增量微压缩（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)） | 
| **系统调用与设备驱动（Syscalls）** | **工具运行时与认知卸载（Tool Runtime & Cognitive Offloading）** | 上百个工具的按需披露、并发/串行屏障调度、多步循环逻辑向沙箱脚本卸载 | 渐进式披露 `tool_search` + 本地 RPC `execute_code`（[Tools Runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime)） | 
| **多进程派生与 IPC（Fork/Wait）** | **子智能体并发编排（Subagent Orchestration）** | 将复杂任务拆解给隔离上下文的子智能体，处理并发冲突、死锁检测与带外干预 | `delegate_task` + 心跳停滞检测器 + Worktree 隔离（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)） | 
| **文件系统与持久化存储（VFS）** | **多层记忆与自演进闭环（Multi-Tier Memory & Self-Improvement）** | 区分常驻核心画像、跨会话情景检索与可复用操作规程（SOP），实现经验沉淀与防膨胀治理 | L1 双文件快照 + L2 SQLite FTS5 + L3 Skills 闭环（[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)） | 
| **分布式锁与事务日志（WAL）** | **单一会话权威与状态恢复（Single-Writer Session Authority）** | 多终端（CLI/桌面/移动端/IM）附着同一会话时的并发写仲裁、崩溃防重放与损坏降级 | `gateway.sock` 单写者 + `runtime_epoch` 栅栏 + WAL（[Gateway local sessions](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-local-sessions)） | 
| **内核安全模块（LSM / SELinux）** | **纵深防御与权限审批（Defense-in-Depth Security）** | 拦截毁灭性命令、防范提示词注入（Prompt Injection）、隔离沙箱与过滤敏感凭据输出 | 8 层纵深防御 + 不可绕过 `HARDLINE_PATTERNS`（[Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)） | 

### 1.2 通用 Harness 的“单核窄腰（Narrow Waist）”架构模式

#### （1）通用工程痛点：多入口状态分裂与维护灾难

一个生产级 Agent 往往需要同时服务于本地终端（CLI/TUI）、桌面 GUI、IDE 插件、多平台即时通讯网关（Telegram、Discord、Slack、微信等）、定时任务（Cron）以及离线评测管线（Batch Evaluation）。初级架构常见的反模式是为不同交互端各自编写一套 Agent 胶水逻辑，这会导致提示词拼装不一致、工具权限逻辑分叉、会话历史无法跨端接续。

#### （2）通用设计原则：Narrow Waist（窄腰收敛）

成熟的 Harness 架构严格遵循网络协议栈式的 **“窄腰（Narrow Waist）”模型**：

1. **上层入口彻底薄化（Thin Surfaces）**：所有前端入口仅负责**协议收发、界面渲染与用户交互阻塞确认**，严禁包含任何 Prompt 拼接、上下文裁剪或工具编排逻辑。

2. **中层单一编排权威（Single Orchestrator Core）**：所有入口最终收敛到同一个与平台无关的同步状态机内核，统一接管推理、工具分发与记忆持久化。

3. **底层资源插件化（Pluggable Backends）**：模型路由（Providers）、终端执行沙箱（Environments）、上下文压缩器（Context Engine）与外部记忆库（Memory Providers）全部通过抽象基类（ABC）解耦。

#### （3）Hermes Agent 的工程映射与六大设计公理

在 [NousResearch/hermes-agent](https://github.com/nousresearch/hermes-agent) 的架构设计（[Architecture | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) 與 [Codebase Ownership Map | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/codebase-ownership)）中，所有入口（交互式 CLI `cli.py`、基于 Ink 的 `ui-tui/`、桌面端 `apps/desktop/`、支持 25+ 平台的 `gateway/run.py`、IDE 适配器 `acp_adapter/`、定时调度器与离线批处理 `batch_runner.py`）全部汇入单一核心编排器 `AIAgent`（由外观层 `run_agent.py` 委托给 `agent/conversation_loop.py`）。其确立的**六大核心工程公理**具有极高的通用参考价值：

1. **提示词绝对稳定（Prompt Stability）**：系统提示词在会话启动时一次性构建并冻结，中途绝不原地修改，确保服务商 Prompt Cache 100% 命中。

2. **执行过程全可观测（Observable Execution）**：通过结构化钩子与无副作用回调暴露内部状态，核心循环不依赖任何 UI 库。

3. **任意时刻安全可中断（Interruptible）**：无论处于流式生成还是并发工具执行阶段，用户或网关均可随时发起中断，且保证底层消息序列不留脏状态。

4. **核心彻底平台无关（Platform-Agnostic Core）**：编排内核不知道自己运行在本地终端还是云端 IM 机器人中，仅通过环境变量与能力元数据调整输出格式。

5. **通过注册表松耦合（Loose Coupling）**：工具、插件、记忆提供方与上下文引擎均通过注册表自发现；核心准则规定：**“如果一个插件需要修改核心文件才能工作，那就是架构异味（Code Smell）”**（[Codebase Ownership Map](https://hermes-agent.nousresearch.com/docs/developer-guide/codebase-ownership)）。

6. **配置与状态全隔离（Profile Isolation）**：所有配置、认证凭据、SQLite 数据库、技能库与网关套接字均封装在单一 `$HERMES_HOME` 目录下，支持多实例零冲突并行。

## 二、 编排控制回路（Orchestration Loop）：从简单 ReAct 到生产级回合状态机

### 2.1 通用 Harness 面临的四大控制回路挑战

教科书中的 ReAct 循环仅仅是一个 `while True` 加上 LLM 调用与工具执行，但在生产环境中，这种朴素实现会迅速崩溃于以下四个工程边界：

1. **多模型协议异构性（Wire Protocol Divergence）**：OpenAI Chat Completions、OpenAI Responses API（如 Codex 推理流）、Anthropic Messages API 在工具调用格式、思维链（Reasoning/Thinking blocks）回传要求以及完成状态码上截然不同。

2. **流式中断引发的角色交替污染（Role Alternation Corruption）**：当用户在模型生成到一半或正在输出 `tool_calls` 时按下中断键，若将半截 Assistant 消息写入历史，下一轮追加新的 User 消息就会产生连续两条同角色消息或悬挂的未闭合 `tool_call`，直接触发各大模型 API 的 `400 Bad Request` 协议校验错误。

3. **长程任务失控与死循环（Runaway Loops）**：模型在遇到顽固报错时可能陷入无限重试，或者在推理模型中出现只输出思维链不输出正文的“空转现象”。

4. **单点供应商故障（Provider Fragility）**：长耗时任务执行到第 30 轮时若遭遇 API 限流（429）、余额耗尽（402）或上游宕机（5xx），缺乏无缝故障转移会导致整条任务链前功尽弃。

### 2.2 通用设计模式与工程权衡

#### 模式一：单一内部中间表示（Canonical IR）+ 边界线协议延迟转换

Harness 内部的消息历史、压缩器与数据库**只维护一套规范化的内部消息列表（Canonical Message List）**，并严格强制执行两条**角色交替不变量（Role Alternation Invariants）**：

* 纯对话流必须满足：`User` $\rightarrow$ `Assistant` $\rightarrow$ `User` $\rightarrow$ `Assistant`（严禁出现连续两个 `user` 或连续两个 `assistant`）。

* 工具调用流必须满足：`Assistant (含 tool_calls)` $\rightarrow$ `Tool (按原始请求顺序一一对应的结果)` $\rightarrow$ `Assistant`。

* **协议适配下沉至最后一公里**：仅在真正发起 HTTP 请求的前一刻，才将内部 IR 转换为目标模型的线协议（Wire Format）；收到响应后立即归一化回内部 IR。

#### 模式二：后台守护线程 API 调用 + 中断即丢弃（Discard-on-Interrupt）

为了实现毫秒级中断响应且不破坏消息历史：

* 主控制线程不直接阻塞在网络 I/O 上，而是将流式 HTTP 请求派发至后台守护线程，主线程循环轮询**中断事件（Interrupt Event）**。

* 一旦在流式生成中途捕获中断信号，Harness **立即丢弃当前尚未完成的 Assistant 残缺响应**，绝不将其写入对话历史；若中断发生在工具执行阶段，则对所有尚未完成的 `tool_call` 自动合成结构化的中断占位结果，确保 `tool_call` 与 `tool_result` 严格配对闭合。

#### 模式三：两级迭代预算（Iteration Budget）与有界宽限故障转移（Bounded Grace Fallback）

* 通过原子计数器维护单次任务的推理预算（区分主智能体预算与子智能体预算）。

* 当主供应商发生不可恢复错误或连续空转时，状态机自动切换至备用供应商链（Fallback Chain）；即便此时迭代预算已耗尽，也应授予**单次有界宽限调用（1 Bounded Grace Call）**，让备用模型有机会汇总当前进展并体面收尾，而不是直接硬崩溃。

### 2.3 Hermes Agent 的具体实现机制

在 [Agent Loop Internals | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop) 与 [Provider Runtime Resolution | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime) 中，`AIAgent.run_conversation()` 将单回合生命周期拆解为 `agent/turn_*.py` 系列正交模块，形成了一套严密的 **9 步回合状态机**：

| 阶段序号 | 阶段名称与核心职责 | 关键工程实现细节与负责模块 | 
| ----- | ----- | ----- | 
| **Step 1** | **任务初始化与中断重置** | 生成唯一 `task_id`，重置中断事件标志，初始化共享或独立的 `IterationBudget`（主 Agent 默认 `agent.max_turns = 500`，子 Agent 默认 `delegation.max_iterations = 250`），并将用户输入追加至规范化 `messages` 列表（[Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)）。 | 
| **Step 2** | **系统提示词构建或缓存复用** | 检查 `_cached_system_prompt`。若首次运行或刚经历完整压缩重建，则调用 `_build_system_prompt()` 组装并冻结，后续所有内层工具循环直接零开销复用（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。 | 
| **Step 3** | **Preflight 上下文水位预检** | 在发起网络请求前检查当前上下文 Token 是否越过压缩阈值；若越过，先执行压缩并在压缩后重建缓存的系统提示词（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。 | 
| **Step 4** | **插件 Pre-LLM 钩子与窗口投影** | 触发 `pre_llm_call` 钩子（仅在首个内层迭代触发），允许插件向首条用户消息追加临时上下文或动态收窄本轮可见工具集；随后调用 `context_engine.select_context()` 获取本轮投影视图（[Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)）。 | 
| **Step 5** | **请求预备与三套线协议适配** | `agent/turn_api_request.py` 将内部消息转换为三种 API 模式之一：`chat_completions`（OpenAI 及 18+ 兼容服务商）、`codex_responses`（OpenAI Responses API）或 `anthropic_messages`（原生 Claude 协议）（[Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)）。 | 
| **Step 6** | **API 调用期临时覆盖层注入** | 调用 `_apply_ephemeral_Context()` 将 `ephemeral_system_prompt` 或插件返回的动态提示注入**仅存在于本次 HTTP 载荷中的副本**，绝不落盘到持久化 `messages` 历史（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。 | 
| **Step 7** | **服务商缓存断点打标** | 对 Anthropic 或 OpenRouter Claude 模型，由 `agent/prompt_caching.py` 自动执行 `system_and_3` 策略（放置 4 个 `cache_control` 断点），节省约 75% 的输入 Token 成本（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。 | 
| **Step 8** | **可中断流式调用与异常恢复** | `_interruptible_api_call()` 在后台线程运行 HTTP 流；`agent/turn_response_intake.py` 归一化响应。若遇到 `incomplete_response`（如 `codex_responses` 仅返回推理块而无正文），最多自动续写 3 次，仍无进展则触发 `_try_activate_fallback` 切换备用模型与 `CredentialPool`（支持 `fill_first`、`round_robin`、`random`、`least_used` 四种凭据池轮转策略）（[Provider Runtime Resolution](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime)）。 | 
| **Step 9** | **工具分发或回合终结分支** | **分支 A（含 `tool_calls`）**：通过 `ThreadPoolExecutor` 并发或按屏障串行执行工具，按原始调用顺序写回 `role: "tool"` 消息，跳回 Step 5 继续内层循环。  **分支 B（纯文本最终回答）**：经 `turn_stop_gates.py` 执行 `pre_verify` 完成度校验 $\rightarrow$ `transform_llm_output` 转换 $\rightarrow$ 写入 SQLite `state.db` $\rightarrow$ `turn_finalizer.py` 执行增量微压缩 $\rightarrow$ 异步拉起后台复盘线程（[Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)）。 | 

## 三、 提示词工程与前缀缓存经济学（Prompt Assembly & Prefix Cache Economy）

### 3.1 通用痛点：动态系统提示词引发的“缓存雪崩”

在长程任务中，单次会话往往包含 20～100 次连续的 LLM 调用，其中系统提示词（System Prompt）加上工具 Schema 动辄占用 10,000～30,000 Tokens。

* **现代 LLM 推理服务的计费与延迟规律**：无论是云端 API（Anthropic、OpenAI、DeepSeek）还是本地推理引擎（`llama.cpp` / `vLLM` 的 KV Cache 复用），只要新请求的**前缀 Token 序列与上一轮完全一致（Byte-for-Byte Identical）**，即可跳过 Prefill 阶段，享受 75%～90% 的输入成本折扣以及数倍的首字延迟（TTFT）加速。

* **朴素 Harness 的致命错误**：许多框架习惯在每一轮调用前动态刷新 System Prompt（例如：将当前精确时间戳、当前工作目录 `pwd`、最新 Git 分支状态、或者刚刚安装的技能列表直接拼接到 System Prompt 头部或中部）。**哪怕 System Prompt 第 100 个 Token 处变了一个字符，其后数万 Token 的 System Prompt、Tool Schemas 以及全部多轮对话历史的 KV Cache 将瞬间全部失效！**

### 3.2 通用设计模式：按易变性分层排序 + 旁路增量通知

为了最大化前缀缓存命中率，通用 Harness 在提示词工程上必须遵循三条核心法则：

1. **按信息熵与变动频率从低到高严格分层（`Stable → Context → Volatile`）**：

   * 越稳定、跨会话越通用的内容（人格设定、核心行为准则）必须放在最前面；

   * 项目级静态共享上下文（项目规范文档）次之，且**必须排在任何与具体工作树路径（CWD）相关的信息之前**，从而让同一代码仓库下不同分支/工作树的并发 Agent 也能共享前缀缓存；

   * 会话级可变快照（记忆快照、环境元数据）放在 System Prompt 的最末尾。

2. **会话期内冻结（Freeze-per-Session）与调用期临时覆盖（Ephemeral Overlay）**：

   * System Prompt 一旦在 Turn 1 构建完成，在发生完整上下文压缩重建之前**严禁修改**。

   * 确实需要每轮注入的瞬态控制信号（如临时状态提醒），只能在 HTTP 请求组装阶段附加到消息列表末尾的临时副本中，请求结束后立即销毁。

3. **单次用户消息旁路通道（One-Shot User-Message Note Channel）**：

   * 当会话中途发生环境跳变（例如：用户从桌面端切换到手机端 IM 导致交互表面改变，或中途新增/卸载了某个技能）时，**绝不回头修改 System Prompt**，而是将这一增量变更封装为一段简短的 `[System Note]`，一次性附加在**下一条 `user` 消息**中通知模型。这样既完成了状态同步，又完好保全了此前所有轮次的 Prompt Cache 前缀。

### 3.3 Hermes Agent 的三层组装与缓存防击穿实践

根据 [Prompt Assembly | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)，Hermes 将 `_build_system_prompt()` 精确划分为三大有序层级，并在工程细节上做到了极致：

| 层级 | 包含的上下文块（按拼接先后顺序） | 工程防呆与防缓存击穿设计细节 | 
| ----- | ----- | ----- | 
| 第一层：`stable`  （跨会话静态层） | 1\. Agent 核心身份（读取 `$HERMES_HOME/SOUL.md` 或回退 `DEFAULT_AGENT_IDENTITY`）  2\. 工具与模型特定行为指南（如 `execute_code` 卸载准则）  3\. 编码执行简报与平台排版提示（Markdown / 终端渲染约束） | 完全不依赖当前目录或会话状态，确保同一用户的所有会话在最前端拥有 100% 相同的 Token 序列（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。 | 
| 第二层：`context`  （项目共享层） | 1\. 显式传入的 `system_message`  2\. 项目级上下文文件（按优先级**首个命中即胜出**：向上递归至 Git 根目录查找 `.hermes.md`/`HERMES.md` $\succ$ `AGENTS.md` $\succ$ `CLAUDE.md` $\succ$ `.cursorrules`）  3\. Git 工作区快照 | **关键排序技巧**：共享的项目上下文文件被严格排在任何包含当前工作目录（CWD）或 Worktree 路径的行之前，使得多个 Git Worktree 下的主/子智能体能够共享完整的项目上下文缓存前缀。  **防撑爆与防注入**：所有注入文件均经过威胁扫描拦截 Prompt 注入；单文件超过 20,000 字符（约 5,000 Tokens）时自动执行**头部保留 70% + 尾部保留 20%** 的保首尾截断（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。 | 
| 第三层：`volatile`  （会话启动快照层） | 1\. `<available_skills>` 技能目录索引  2\. `MEMORY.md` 与 `USER.md` 的会话启动冻结快照  3\. 外部 Memory Provider 静态块  4\. 会话时间戳、模型名称与位于最末尾的 `# Hermes runtime environment` 边界标记 | 哪怕会话中途调用 `memory` 工具修改了磁盘上的 `MEMORY.md`，或者安装了新技能，第三层在当前会话内也**保持冻结不刷新**。中场跨端切换（`agent/surface_switch.py`，PR #104414）与技能目录增删（`agent/skills_index_delta.py`）全部走**单次用户消息旁路通道**（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。 | 

此外，为了防止研发团队在迭代代码时无意间膨胀了基础 Prompt 或工具 Schema，Hermes 引入了 **Prompt Surface CI 快照机制**（`scripts/ci/prompt_surface.py render`），将 9 种典型配置组合下的完整 System Prompt 与 Tool Schemas 渲染为基准快照（保存在 `tests/fixtures/prompt_surface/`），在每次 Pull Request 中自动对比 Token 增减量（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)）。

## 四、 上下文窗口治理：计量锚点、多阶段压缩与增量微压缩（Context Governance）

### 4.1 通用痛点：为什么大窗口无法替代上下文治理？

即便现代模型声称支持 200K 甚至 1M 上下文窗口，生产级 Harness 依然必须将上下文治理视为生命线，原因在于四大物理与认知瓶颈：

1. **本地分词器估算漂移（Tokenizer Estimation Drift）**：不同模型家族（Claude、GPT、Qwen、DeepSeek）使用不同的分词器，且多模态图片与复杂 JSON Schema 的真实 Token 消耗与本地 `tiktoken` 粗算常常相差 20%～50%，极易导致“以为没满但请求直接报 400 Context Length Exceeded”或“过早误触发压缩”。

2. **工具输出噪音淹没（Tool Output Bloat）**：一次文件搜索、网页抓取或终端编译日志就可能灌入数万 Token 的一次性原始文本，迅速稀释历史中的核心决策信号。

3. **摘要失忆症（Summary Amnesia）**：传统的“一刀切 LLM 摘要”在经过 2～3 次迭代压缩后，往往会把用户的初始硬性约束、精确的文件路径、Git Commit SHA 或报错码概括成模糊的套话，且如果在 `tool_call` 与 `tool_result` 中间切一刀，会直接破坏 API 协议合法性。

4. **锯齿状延迟尖峰（Sawtooth Latency Spikes）**：等到上下文塞满 85% 再同步调用大模型生成全量摘要，会让用户遭遇长达 15～40 秒的交互卡顿。

### 4.2 通用设计模式与工程权衡

针对上述四大痛点，现代 Harness 演化出了五项标准治理模式：

| 治理维度 | 通用设计模式 | 核心权衡与解决机制 | 
| ----- | ----- | ----- | 
| **Token 计量** | **API 真实回执锚定法（Usage-Anchored Accounting）** | 摒弃纯本地全量重算。以最近一次 API 响应返回的真实 `prompt_tokens + completion_tokens` 为绝对基准锚点（Anchor），仅对锚点之后新增的少量消息做本地增量估算；在尚无真实回执的首轮或刚切换模型时，遵循“等待真实证据（Wait-for-Provider-Evidence）”原则推迟预检。 | 
| **多模态计费** | **在线残差自学习（Adaptive Image Token Learning）** | 首次发送图片前采用保守默认值；收到包含图片的首次 API 真实 Token 回执后，用真实消耗减去文本估算值，动态反推出当前 `model@host` 的单图实际 Token 开销并缓存复用。 | 
| **全量压缩（Macro-Compaction）** | **四阶段无损边界对齐压缩（Prune** $\rightarrow$ **Align** $\rightarrow$ **Structured Summary** $\rightarrow$ **In-Place Commit）** | 1\. **零成本修剪**：先清理历史中大体积工具输出，不调 LLM。  2\. **协议安全切分**：保护头部初始指令，从尾部向前对齐切分点，严禁拆散 `tool_call/tool_result` 对。  3\. **结构化模板 + 正则机械锚点**：强制固定章节摘要，并用正则硬提取路径/SHA/PR 号 + 原样保留真实用户消息。  4\. **原地提交**：保持同一 `session_id` 不断裂。 | 
| **延迟隐藏** | **后台预备压缩（Prepared Compaction）+ 阶梯退避** | 当水位接近阈值（如距离阈值还有 10%～12%）时，在回合结束后的空闲期拉起后台线程预先算好摘要；下轮一旦真正越界直接毫秒级替换。若后台 LLM 超时，则按指数阶梯冷却并在多次失败后自动降级为确定性无 LLM 摘要。 | 
| **增量平滑（Micro-Compaction）** | **非对称回合末微压缩（Asymmetric Rolling Micro-Compaction）** | 每回合结束时仅将最老的一组 **Assistant 动作与工具交互**吸收进滚动摘要标记，而**永久跳过并原样保留所有 User 消息**。这使上下文水位始终维持在约 20%～25% 的平坦直线，彻底消灭锯齿状停顿（代价是每轮重写摘要标记会使该位置之后的缓存失效，适用于注重低水位的场景）。 | 

### 4.3 Hermes Agent 的上下文引擎与压缩管线实现

Hermes 在 [Context Compression and Caching | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)、[Micro-compaction | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/micro-compaction) 与 [Context Engine Plugins | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/context-engine-plugin) 中构建了可插拔的 `ContextEngine` 抽象基类（`agent/context_engine.py`），其默认实现 `ContextCompressor`（`agent/context_compressor.py`）包含以下精密设计：

1. **双层水位防线（Dual Compression Defense）**：

   * **外层网关卫生预检（Gateway Session Hygiene）**：`gateway/run_turn_hygiene.py` 在实例化 `AIAgent` 之前按固定 **85% 阈值**做兜底拦截。

   * **内层引擎自适应阈值**：默认在上下文窗口达到 **50%** 时触发压缩；对于上下文上限被锁死在 272K 的特定高阶模型（如 Codex OAuth 下的 `gpt-5.4/5.5/5.6` 与 `Astra`），自动将阈值上调至 **85%（约 231K Tokens）** 以充分利用有效窗口（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。

2. **精准计量与视觉自适应**：

   * `agent/usage_anchor.py` 实现真实回执锚定，并通过 `should_defer_preflight_to_real_usage()` 防止在回滚（Rewind）或换模型后的第一轮因锚点缺失而误判。

   * `agent/image_token_cost.py` 在未获知真实消耗前按每张图 `1,500 Tokens` 预估，首轮视觉调用后自动学习每个 `model@host` 的真实单图 Token 残差（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。

3. **四阶段压缩算法（4-Phase Compression Algorithm）**：

   * **Phase 1（零成本工具修剪）**：扫描受保护尾部之外的历史，将所有超过 200 字符的旧 `tool` 输出替换为 `[Old tool output cleared to save context space]`，并将已加载的技能正文替换为 `[SKILL_PRUNED: <name> — reload with skill_view if needed]`。若修剪后水位已降至阈值以下，直接跳过 LLM 摘要！

   * **Phase 2（协议安全边界对齐与精简尾部 `tail_mode: lean`）**：默认保护头部前 `protect_first_n = 3` 条消息；尾部采用 `lean` 模式，仅保留窗口的 2.5%（钳制在 `10,000`～`25,000 Tokens` 之间，且至少包含 `min_tail_user_messages = 1` 条真实用户消息——在 500K 窗口下仅保留约 49K Tokens，而传统模式会保留 162K）。调用 `_align_boundary_backward()` 向回滑动切分点，确保绝不把 `Assistant(tool_calls)` 与对应的 `Tool(tool_result)` 切在边界两侧。

   * **Phase 3（带机械锚点的结构化摘要）**：调用摘要模型生成固定七大章节（`## Goal`、`## Constraints & Preferences`、`## Progress`、`## Key Decisions`、`## Relevant Files`、`## Next Steps`、`## Critical Context`），同时通过**确定性正则表达式**提取所有 PR 编号、Commit SHA、文件路径与错误码组成**机械锚点索引（Mechanical Anchor Index）**，并将被压缩区段内的真实用户消息（排除系统旁路通知）原样附在摘要中。迭代重压缩时直接在此结构上原地演进。

   * **Phase 4（原地会话提交 `in_place: true`）**：保持原 `session_id` 不变，在 SQLite 中将旧消息标记为 `active=0, compacted=1`，写入新摘要行，使 CLI 与 IM 网关状态无缝延续（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。

4. **后台预备压缩（Prepared Compaction）与微压缩（Micro-Compaction）**：

   * `agent/prepared_compaction.py`（`prepare_ahead: true`）在水位进入阈值下方 12% 区间时启动后台线程预计算摘要；若遭遇超时失败，执行 `60s → 300s → 900s` 三级冷却退避，连续 2 次超时后直接回退至确定性无 LLM 摘要（PR #112420）（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)）。

   * `agent/micro_compactor.py`（`compression.micro_compact: true`）在每回合 `finalize_turn` 阶段吸收最老的一轮 Assistant 交互至滚动摘要标记（`display_metadata.micro_compacted = True`），当滚动摘要超过 `micro_compact_defrag_threshold_tokens = 2000` 时自动碎片整理，使长会话水位稳定在 **\~22%**（[Micro-compaction](https://hermes-agent.nousresearch.com/docs/developer-guide/micro-compaction)）。

5. **跨压缩身份追踪（Persistent `message_uid`）**：

   * `ContextEngine` 为每条消息分配持久化 32 位十六进制 `message_uid`，并在压缩摘要上维护 `absorbed_message_uids` 与 `_tool_call_uids`，使得外部知识图谱或树状记忆插件（如将对话组织为有向无环图 DAG 的 `lossless-claw` 插件）在经历多轮压缩后仍能精确追溯任意结论的原始消息出处（[Context Engine Plugins](https://hermes-agent.nousresearch.com/docs/developer-guide/context-engine-plugin)）。

## 五、 工具运行时与认知卸载（Tool Runtime, Progressive Disclosure & Cognitive Offloading）

### 5.1 通用痛点：工具 Schema 爆炸与多步机械调用陷阱

随着 Agent 接入外部生态（如 MCP 协议服务器、浏览器自动化、本地系统工具），工具层会引发三大严重瓶颈：

1. **工具 Schema 塞满上下文并拉低准确率（Schema Bloat & Selection Degradation）**：当可用工具超过 50～100 个时，仅将所有工具的 JSON Schema 塞入请求就会消耗 20,000～50,000 Tokens；更糟糕的是，工具数量过多会显著干扰模型的注意力分布，导致选错工具或填错参数。

2. **多步机械推理拉长回路（Multi-Turn Ping-Pong Latency）**：如果一个任务需要先搜索 10 个文件、逐个读取内容、过滤出特定配置再汇总，传统 Tool Calling 需要与云端 LLM 往返交互 15～20 个回合，不仅每次都要把庞大的中间文件内容塞进上下文窗口，还会消耗数十秒的网络往返延迟。

3. **后台长耗时进程死等轮询（Busy-Polling Burn）**：模型启动一个耗时 3 分钟的编译或测试任务后，往往会每隔几秒调用一次 `process(action="poll")` 或 `wait`，白白烧掉几十个推理回合与大量 Token。

### 5.2 通用设计模式与工程权衡

#### 模式一：渐进式工具披露（Progressive Tool Disclosure / Tool Search）

不要在初始请求中一次性暴露所有工具的完整 JSON Schema，而是模仿人类查阅手册的过程，将工具集划分为**常驻热工具（Eager Core Tools）**与**按需延迟加载工具（Deferred Tools）**：

* 初始上下文中只挂载高频核心工具的完整 Schema，外加一部极简的“一句话工具目录（Manifest）”以及三个元桥接工具：**搜索工具（Search）**、**查看参数定义（Describe）**、**间接调用（Call）**。

* 当模型需要冷门或外部 MCP 工具时，先按关键词检索并拉取该工具的 Schema，随后即可直接调用。Anthropic 基准测试表明，当挂载约 50 个 MCP 工具时，渐进式工具检索可将 Opus 4 的工具调用准确率从 **49% 大幅提升至 74%**，同时节省数万固定 Token 开销（[Tool Search | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search)）。

#### 模式二：编程式工具调用与认知卸载（Programmatic Tool Calling / Cognitive Offloading）

对于包含循环、条件分支、批量过滤或多步管道的数据处理任务，Harness 应提供一个**受控的本地代码执行沙箱（如 `execute_code`）**，并在沙箱内通过本地进程间通信（IPC/RPC）暴露核心工具库：

* 模型只需编写一段数十行的 Python 编排脚本，在脚本内部循环调用文件读写、网页提取或 Shell 工具，并使用标准 Python 代码完成正则过滤与聚合，最后仅通过 `print()` 输出几百字的最终结论。

* **核心收益**：原本需要 15 轮 LLM 往返、消耗 50,000 Tokens 中间上下文的操作，被**折叠为单次 LLM 回合**，且海量中间工具原始输出完全留在子进程内存中，**零字节进入 LLM 上下文窗口**。

#### 模式三：并发屏障调度与空轮询自动转异步事件（Auto-Notify on Quiet Poll）

* **工具并发分类**：纯读/独立工具通过线程池并发执行，但涉及**用户交互提问（如 `clarify`）**或**长耗时外部状态变更**的工具必须设为**串行屏障（Sequential Barrier）**，独占执行。

* **防死等轮询干预**：当 Harness 检测到模型对同一后台进程连续发起 2 次无新输出的轮询（Empty Poll/Wait）时，自动将该进程转为**完成时异步回调通知模式（Notify-on-Complete）**，并在工具返回中明确命令模型停止轮询、立即结束当前回合并等待系统唤醒。

### 5.3 Hermes Agent 的工具运行时与沙箱实现

在 [Tools Runtime | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime)、[Tool Search | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search) 与 [Code Execution (Programmatic Tool Calling) | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution) 中，Hermes 的工具子系统展现了极高的工程完成度：

1. **导入期自注册与核心循环拦截（Import-Time Self-Registration & Intercepted Tools）**：

   * 所有内置工具在 `model_tools.py` 导入 `tools/*.py` 时自动向全局单例 `tools/registry.py` 注册 Schema、处理函数与环境可用性检查器，无需维护集中式枚举表。

   * 绝大多数工具由 `registry.dispatch()` 分发并在 `ThreadPoolExecutor` 中并发执行（完成后严格按模型请求的原始顺序写回结果）；但 **`todo`、`memory`、`session_search`、`delegate_task` 四个核心有状态工具由 `AIAgent` 主循环直接拦截执行**，以便安全地读写会话内部状态。交互式工具 `clarify` 与长耗时 MCP 调用则作为串行屏障执行（[Tools Runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime)）。

2. **三级渐进式工具披露（3-Tier Progressive Tool Search）**：

   * 针对 MCP 工具、插件工具以及 `computer_use`、`session_search` 等低频大 Schema 内置工具，Hermes 提供三个元桥接工具：`tool_search`、`tool_describe`（加载完整 Schema 并将其提升至本会话热工具集）与 `tool_call`。

   * **透明解包机制（Transparent Unwrapping）**：当模型通过 `tool_call(name="...", arguments={...})` 发起调用时，运行时在执行前会将其**解包还原为真实目标工具名称**，确保下游的插件钩子、危险命令审批与并发策略与直接调用完全一致。

   * 根据延迟工具规模自动切换三级暴露策略：小规模直接全量暴露（Tier 1: Eager）$\rightarrow$ 中等规模暴露桥接工具 + 单行目录清单（Tier 2: Bridge + Manifest）$\rightarrow$ 超大规模仅暴露纯桥接工具（Tier 3: Bare Bridge）（[Tool Search](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search)）。

3. **基于 Unix Domain Socket RPC 的编程式工具卸载（`execute_code`）**：

   * 模型在 `execute_code` 中编写 Python 脚本并直接 `from hermes_tools import web_search, web_extract, read_file, write_file, search_files, patch, terminal`。

   * 运行时为每次执行自动生成临时 `hermes_tools.py` 桩模块，子进程通过 **Unix Domain Socket**（Windows 下回退至本地回环 TCP，远程沙箱通过文件 RPC）回调父进程的真实工具运行时。

   * **安全边界**：单脚本硬超时 300 秒、嵌套工具调用上限 50 次、严禁在沙箱内递归调用 `delegate_task` 或 `execute_code`，且自动剥离所有 API Key 环境变量；最终仅有截断至 50KB 以内的 `stdout` 进入模型上下文（[Code Execution](https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution)）。

4. **七大可插拔执行沙箱与后台进程防轮询**：

   * 终端工具支持 7 种后端无缝切换：`local`、`docker`（单容器跨回合与跨子智能体持久化复用，强制 `--read-only` 根文件系统、`--cap-drop ALL`、`--pids-limit 256` 及 `tmpfs` 隔离）、`ssh`、`modal`、`daytona`、`vercel_sandbox`（支持退出时自动拍摄文件系统快照并在下次会话恢复），以及插件后端 `singularity` 和 `sprites`（[Tools & Toolsets | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)）。

   * 开启 `process_wait_auto_notify` 后，对同一后台进程连续 2 次空轮询会自动注册 `notify_on_complete` 异步监听，彻底杜绝无意义的轮询回合消耗（[Tools & Toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)）。

## 六、 多智能体派生与并发编排（Subagent Delegation & Swarm Control）

### 6.1 通用痛点：多智能体协作的四大工程陷阱

当主智能体（Parent Planner）将复杂任务拆解并派生给多个子智能体（Subagents）并发执行时，天真的实现往往会陷入四个深坑：

1. **上下文交叉污染 vs 缓存失效的两难**：如果把父智能体的完整历史传给子智能体，子智能体会受到无关上下文干扰且浪费海量 Token；但如果为子智能体构造全新的 System Prompt，并发启动 5 个子智能体就会导致 5 次昂贵的冷启动 Prefill，无法复用父智能体的 Prompt Cache。

2. **并发写同一代码库引发的踩踏（Workspace Race Conditions）**：多个编码子智能体在同一目录下同时修改代码、切换分支或运行构建，会直接把工作区改乱。

3. **固定总耗时超时（Wall-Clock Timeout）误杀正常慢任务**：如果简单给子智能体设一个“最长运行 10 分钟”的死限，一个正在持续推进 50 个文件重构的正常子智能体会被无情强杀；而另一个真正卡死在死循环或挂起请求上的子智能体却要白白浪费 10 分钟才报错。

4. **递归派生风暴与越权副作用**：子智能体自己又派生孙智能体导致指数级算力爆炸，或者子智能体擅自向最终用户发消息、篡改全局核心记忆。

### 6.2 通用设计模式与工程权衡

1. **零对话历史隔离 + 共享系统提示词前缀（Clean-Slate History with Shared Cache Prefix）**：

   * 子智能体以**空白对话历史**启动，仅接收父智能体明确下发的任务描述（Task Prompt）与返回格式契约（Output Schema）。

   * 但子智能体的 System Prompt 必须**复用与父智能体完全相同的项目上下文前缀顺序**，使所有并发子智能体直接命中父智能体已经预热好的服务商 KV Cache。

2. **扁平化单层树（Flat 1-Level Tree）与叶子能力剥离**：

   * 严禁嵌套派生（子智能体不可再调用派生工具），将多智能体拓扑严格收敛为深度为 1 的星型结构。

   * 剥离子智能体的用户交互权（不可向用户提问或发外部通知）与全局状态写权限（不可修改全局长期记忆或定时任务）。

3. **基于心跳进度的停滞检测（Progress-Based Stall Monitor）替代固定总超时**：

   * 不限制子智能体的总运行时间，而是监控其**最后一次产生实质进展（完成一次 API 响应或工具调用）的时间间隔**。只要子智能体在持续干活，就允许其一直运行；仅当其在规定时间内毫无进展时才判定为卡死（Stall），且在强杀前先注入一次带外警告提示促其收尾。

4. **Git Worktree 物理隔离与实时带外引导（Out-of-Band Steer）**：

   * 对需要并行改代码的子智能体，自动为其创建独立的 `git worktree` 临时分支目录；在父智能体运行期间支持向活跃子智能体动态注入引导消息（Steer），修正其执行方向而无需销毁重来。

### 6.3 Hermes Agent 的 `delegate_task` 并发编排实现

根据 [Subagent Delegation | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)，Hermes 在 `tools/delegate_tool.py` 中实现了兼具同步批处理与异步后台派生的子智能体编排器：

| 核心机制 | 具体工程实现与参数配置 | 解决的实战问题 | 
| ----- | ----- | ----- | 
| **缓存友好的上下文隔离** | 子 `AIAgent` 实例仅接收独立 `goal` 与 `context`，但其 System Prompt 内嵌相同的项目上下文文件前缀，直接共享父会话 Prompt Cache。 | 兼顾子任务高信噪比与并发启动时的极低 Prefill 成本（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 
| **叶子工具硬封禁** | 默认强制在子智能体中禁用：`delegate_task`（防无限递归）、`clarify`（防阻塞交互）、`memory`（防污染全局 `MEMORY.md`）、`send_message`（防外部副作用）与 `cronjob`。 | 确保所有对外交互与持久状态变更收口于主智能体（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 
| **结构化输出契约（`output_schema`）** | 父智能体可传入 JSON Schema 契约。子智能体完成时若输出不符合 Schema，运行时自动执行 **1 次有界修正重试（1 Bounded Validation Retry）**，并返回 `structured_output` 与 `schema_valid` 标志。 | 让主智能体可以像调用强类型函数一样可靠地消费子智能体的分析结果（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 
| **进度停滞监控器（Stall Monitor）** | 摒弃总时长硬超时，改为双状态空闲监控：  • **思考空闲（Idle between tools）**：默认 `450s`（达到 80% 即 `360s` 时自动注入警告引导消息提醒收尾）。  • **工具执行中（In-tool）**：默认 `1200s`。  • 触发停滞后给予 `120s` 宽限期（Grace Period）汇总部分结果，超时后再终止。 | 既允许复杂长任务运行数小时，又能精准识别并优雅回收挂起的死任务（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 
| **Git Worktree 隔离与实时控制** | 开启 `worktree_isolation: true` 时自动在 `.worktrees/subagent-<id>` 下创建独立工作树并在结束后清理未修改分支。  支持异步模式下的四类实时操作：`steer`（注入新指令，若子智能体恰在注入前结束则标记 `missed_steer`）、`interrupt`、`status` 与 `handoff`（将子智能体创建的最多 3 个后台进程移交父智能体管理）。 | 彻底解决多编码 Agent 并发改文件冲突，支持运行时动态纠偏与后台服务移交（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 
| **独立完成唤醒与五级崩溃恢复** | 多任务异步派生支持 `independent_completions` 与按 `group` 分组聚合唤醒。  持久化的子任务若遇进程崩溃，恢复时按五种策略自动分类处置：`AUTO_AT`、`AUTO_ON_BOOT`、`ON_FIX`、`REPAIR_THEN_CONTINUE` 与 `HANDOFF`。 | 避免“一个慢子任务拖住整批快子任务回报”，保障网关重启后子任务不丢失（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)）。 | 

## 七、 跨会话记忆分层与自演进闭环（Multi-Tier Memory & Self-Improving Loop）

### 7.1 通用痛点：为什么 RAG 向量库解决不了 Agent 记忆问题？

许多早期 Agent 框架将“长期记忆”简单等同于“把所有历史对话切块扔进向量数据库（Vector RAG）”，这在实际使用中存在三个结构性缺陷：

1. **核心偏好漏召回与噪音召回**：用户的全局身份、语言习惯、硬件环境或架构文档偏好需要在**每一轮对话中无条件生效**；如果依赖语义检索，当用户问一个具体技术问题时，向量检索往往召回不了“不要输出代码片段”这类元偏好。反之，如果无脑往常驻记忆文件里追加内容，几个月后常驻记忆就会膨胀成数万 Token 的垃圾场。

2. **陈述性事实（Declarative Facts）与程序性技能（Procedural Skills）混为一谈**：“用户有一台 128GB 内存的 Mac Studio”是一条简短的**陈述性事实**；而“如何排查某特定框架的编译报错并打补丁”是一套包含脚本、参考文档与多步检查清单的**程序性操作规程（SOP）**。把长篇排障指南塞进常驻记忆会严重浪费上下文。

3. **同步反思阻塞主流程**：如果让 Agent 在每次回答完用户后同步调用工具去整理记忆或总结技能，会显著拉长用户的等待时间；而在本地部署大模型（如单机运行 `llama-server`）时，后台异步复盘线程又会与用户下一轮正常提问争抢宝贵的 GPU 算力。

### 7.2 通用设计模式：认知科学启发的三层记忆架构与异步自演进

成熟的 Agent Harness 借鉴人类认知科学的记忆分类，构建**三层解耦的记忆金字塔（3-Tier Memory Architecture）**，并配以后台异步自省 + 生命周期淘汰（Curator）闭环：

| 记忆层级 | 认知科学映射 | 存储内容与形态 | 注入时机与固定 Token 成本 | 容量治理与防膨胀机制 | 
| ----- | ----- | ----- | ----- | ----- | 
| Tier 1：核心工作记忆  （Core Bounded Memory） | **语义记忆 / 自我图式** | 极高密度的环境关键事实与用户核心画像/偏好（Markdown 文本块） | 会话启动时作为**冻结快照**全量注入 System Prompt（固定开销极小，约 **1,000～1,500 Tokens**） | **硬性字符上限（Hard Character Cap）+ 溢出强制原子合并**：一旦写操作超限，直接拒绝简单追加，强制模型在同一调用中合并冗余、删除过时条目。 | 
| Tier 2：情景历史检索  （Episodic Session Recall） | **情景记忆** | 过去所有会话的完整消息记录与工具交互流水（SQLite 全文索引库） | 按需通过检索工具查询并生成高密度摘要（**0 常驻 Token 成本**） | 基于 **FTS5（BM25 词法）+ Trigram（子串/代码标识符）** 双索引毫秒级检索，支持命中位置前后滑动窗口浏览。 | 
| Tier 3：程序性技能库  （Procedural Skill Library） | **程序性记忆 / 肌肉记忆** | 复杂任务的标准作业程序（SOP）、排障手册、领域知识库与配套脚本（目录树） | **三级渐进式披露**：仅在 System Prompt 注入技能名称与单行描述索引（约 **3,000 Tokens**），正文与参考文件按需加载 | 后台自省复盘（Background Review）自动沉淀新技能 + **静态规范检查（Linter）** + 馆长归档机制（Curator）自动淘汰陈旧技能。 | 

### 7.3 Hermes Agent 的三层记忆与自演进实现细节

在 [Persistent Memory | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)、[Skills System | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)、[Creating Skills | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills)、[Curator | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator) 与 [Memory Providers | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers) 中，Hermes 的实现展现了严密的工程闭环：

1. **Tier 1：硬性定长双文件与原子批处理整理（`MEMORY.md` & `USER.md`）**：

   * `MEMORY.md`（存储环境事实、项目约定）被严格限制在 **2,200 字符（约 800 Tokens）** 以内；`USER.md`（存储用户画像与沟通偏好）被严格限制在 **1,375 字符（约 500 Tokens）** 以内。

   * **溢出强制整理（Overflow Consolidation）**：当模型调用 `memory(action="add")` 导致文件超出上限时，工具直接拒绝写入，并返回当前全部记忆条目及字符占比，要求模型立即使用 `operations` 批量原子操作（在单次工具调用中组合多条 `remove` 与 `replace`）对现有记忆进行去重提炼。

   * **双层安全防护**：任何写入 `MEMORY.md` 的内容首先经过正则注入扫描（拦截伪造系统指令与越狱载荷），并在工具输出给模型前自动脱敏 API 密钥与 Token（[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)）。

2. **Tier 2：毫秒级零常驻成本的跨会话检索（`session_search`）**：

   * 所有历史会话实时同步至 SQLite `~/.hermes/state.db`，同时构建 **FTS5 全文索引**（针对自然语言做 Porter 词干分词 + BM25 排序）与 **Trigram 三元语法索引**（专门应对骆驼拼写函数名、报错码、文件路径等精确子串匹配）。

   * 检索耗时仅约 **20ms**，召回相关会话后通过便宜的辅助模型将长对话浓缩为 **500 字高密度摘要**返回给主模型；若需查看原始上下文，主模型可通过 `scroll` 操作以约 **1ms** 的延迟在命中位置前后滑动查看，全程不污染主上下文窗口（[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)）。

3. **Tier 3：三级渐进式技能库（`~/.hermes/skills/`）与 `/learn` 知识蒸馏**：

   * 遵循开放的 `agentskills.io` 规范，每个技能目录包含带 YAML Frontmatter 的 `SKILL.md` 及可选的 `references/`、`templates/`、`scripts/`、`assets/` 子目录。

   * **三级按需加载**：Level 0 在系统提示词中仅列出 `skills_list` 摘要（约 3k Tokens） $\rightarrow$ Level 1 调用 `skill_view(name)` 加载 `SKILL.md` 正文与关联文件清单 $\rightarrow$ Level 2 调用 `skill_view(name, path)` 读取具体参考章节或脚本（[Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)）。

   * **结构化知识蒸馏（`/learn`）**：支持直接将整本电子书（EPUB/PDF）、文档站点或 GitHub 仓库蒸馏为结构化技能包（顶层 `SKILL.md` 作为总目录索引，`references/` 下存放按章节拆分的精炼文档，并在 `sources.json` 中记录源文件路径或 Git Commit SHA 以便增量更新）。

   * **防退化静态检查器（Advisory Skill Linter）**：每次创建或修补技能时自动运行三大健康检查：`incident-log-shape`（防止模型把技能文档写成流水账式的排错日记）、`references-sprawl`（警告 `references/` 下文件超过 60 个）与 `oversized-body`（警告 `SKILL.md` 正文超过 24,000 字符）（[Creating Skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills)）。

4. **后台自省复盘分支（Background Review Fork）与馆长（Curator）生命周期治理**：

   * 每经过设定轮次，主回合结束（`finalize_turn`）后会在后台派生一个只读复盘分支（仅授予 `memory`、`skill_manage`、`skill_view`、`session_search` 权限），自动提炼本轮新发现的用户偏好或通用排障规程。

   * **三种成本与本地算力优化技巧**：

     1. **复用父会话热缓存**：若后台复盘使用与主会话相同的模型，直接克隆父会话完整历史并在末尾追加复盘指令，100% 命中刚生成的服务商 Prompt Cache；

     2. **轻量摘要投喂**：若配置了廉价辅助模型（`auxiliary.background_review`），则自动将长历史压缩为精简摘要（上限控制在模型窗口的 75% 且不超过 600K Tokens）再发送；

     3. **本地 GPU 空闲让行（`defer: auto`）**：当检测到本地推理服务（如 `llama-server`）时，自动推迟后台复盘直至主对话空闲，避免与用户的下一次实时提问争抢本地显存与算力（[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)）。

   * **馆长归档机制（`agent/curator.py`）**：定期审计所有由 Agent 自主创建的技能，根据使用频率与近期采纳率将其划分为 `active → stale → archived` 三个状态，自动将长期未使用的陈旧技能移入 `.archive/` 目录（人工创建的技能永久豁免），确保 `<available_skills>` 索引永不膨胀（[Curator](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)）。

5. **可插拔外部记忆引擎（`MemoryProvider` ABC）**：

   * 除了内置记忆外，还提供 `agent/memory_provider.py` 抽象接口，支持挂载 RetainDB、ByteRover、Honcho、OpenViking、Mem0、Hindsight、Holographic、Supermemory、Memori 等第三方图谱或向量记忆系统，且规定静态块走 System Prompt、动态检索结果走 API 调用期临时层以保护缓存（[Memory Providers](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers)）。

## 八、 单一会话权威与分布式状态一致性（Session Authority & Durable State）

### 8.1 通用痛点：多端并发附着下的脑裂、重放与库损坏

当一个 Agent Harness 支持多端协同（例如：用户在电脑 CLI 上启动了一个任务，出门后在手机 Telegram 或车载语音端继续接入同一个会话，同时后台还有定时任务在推送消息）时，底层状态管理会面临分布式系统的典型难题：

1. **双写脑裂（Split-Brain Concurrent Mutation）**：如果 CLI 进程和后台 Gateway 进程各自实例化一个 Agent 并同时读写同一个 SQLite 会话，必然导致上下文覆盖、消息序号错乱以及 SQLite `SQLITE_BUSY` 锁死。

2. **崩溃恢复引发的副作用重复执行（Side-Effect Replay on Crash）**：如果用户在会话中下达了“帮我发送邮件/执行转账/删除分支”的指令，Gateway 在工具已经执行完毕但尚未完成回合收尾时突然断电或崩溃，重启后若简单重放队列中的未完成输入，就会导致外部副作用被**重复执行两次**。

3. **全文索引损坏拖垮主库（Index Corruption Cascading Failure）**：SQLite 的 FTS5 虚拟表在非正常关机或磁盘满时比普通 B-Tree 表更容易出现索引页损坏（`SQLITE_CORRUPT`）。如果检索索引报错直接抛异常，会导致整个 Agent 无法保存新消息而彻底瘫痪。

### 8.2 通用设计模式与工程权衡

1. **单一会话写权威（Single-Writer Session Authority）+ 本地客户端薄代理化**：

   * 同一时刻，针对同一个会话或状态目录，**只允许一个长驻网关守护进程（Gateway Daemon）拥有会话的直接执行权与数据库主写权**。

   * 当本地网关在线时，任何新启动的本地 CLI、TUI、桌面端或远程 Web 端都不再自行运行编排循环，而是自动退化为一个**薄客户端（Thin Attach Client）**，通过本地 IPC 套接字或 WebSocket 附着（Attach）到网关上订阅事件流并提交输入。

2. **持久化运行纪元栅栏（Runtime Epoch Fencing）**：

   * 数据库维护一个单调递增的 `runtime_epoch` 版本号。任何旧进程或僵尸线程在写库前必须校验自身持有的 Epoch 是否与当前库一致，一旦失配立即自我中止（Fence Off），杜绝新老实例双写。

3. **三态持久化准入队列（Durable Admission FIFO）与 `unknown` 熔断态**：

   * 所有进入会话的外部输入先持久化写入准入队列表，状态流转为：`queued`（排队中） $\rightarrow$ `started`（已开始执行） $\rightarrow$ `completed`（已完成）。

   * **核心防重放法则**：如果网关在启动恢复时发现某条记录处于 `queued` 状态，说明尚未执行，可以安全自动唤醒；但如果发现记录处于 **`started` 状态**，说明崩溃发生在工具可能已经产生外部副作用的中途——此时**严禁自动重放**，必须将其标记为 `unknown`（未知结果态）并**挂起该会话的后续队列**，等待人工确认或显式恢复。

4. **派生索引热降级（Derived Index Detachment）与损坏库隔离（Quarantine）**：

   * 将全文检索索引视为可随时丢弃重建的**派生数据（Derived Data）**：一旦检测到 FTS 虚拟表损坏，立即在运行时解耦 FTS 触发器并回退至普通 `LIKE` 扫描，保证核心消息写入不受丝毫影响，再由后台空闲任务异步重建索引。

   * 若主 B-Tree 表本身发生不可逆物理损坏，则立即冻结旧连接（禁止 Checkpoint 覆盖残留 WAL），将损坏文件重命名隔离，并在毫秒内原地初始化新库（同时将内存中的当轮未落盘消息刷入 `.jsonl` 应急日志），实现零停机自愈。

### 8.3 Hermes Agent 的多路复用网关与 SQLite 31 版容灾实现

在 [Gateway Internals | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals)、[Gateway local sessions | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-local-sessions)、[Multiplexing Gateway](https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/multiplexing-gateway)、[Session Storage | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage) 与 [State DB Recovery | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/state-db-recovery) 中，Hermes 实现了一套金融级稳健度的本地状态底座：

1. **基于 Unix Socket 内核凭据校验的多路复用网关（`$HERMES_HOME/gateway.sock`）**：

   * 网关在 `$HERMES_HOME/gateway.sock`（权限严格锁死为 `0600`）暴露本地控制面。当用户运行 `hermes` CLI 时，CLI 先探测该 Socket：若网关在线，内核通过 `SO_PEERCRED`（Linux）或 `getpeereid`（macOS/BSD）在操作系统层面校验调用方进程的 `UID` 是否与网关一致。

   * 校验通过后，网关签发一张 **30 秒有效、单次使用（Single-Use）的随机票据（Ticket）**，CLI 凭此票据升级至 `/api/ws` WebSocket 双工流，实现 CLI、TUI、Web 与 25+ IM 平台对同一会话的实时多端同屏同步与协同控制（[Gateway local sessions](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-local-sessions)）。

2. **`state.db`（Schema v31）并发控制与准入队列**：

   * 启用 SQLite WAL 模式（`synchronous=NORMAL`、`mmap_size=64MB`），所有写事务包裹在应用层锁与抖动指数退避重试中（常规写入最大容忍等待 `3s`，回合终结批量刷盘 `flush_messages` 最大容忍等待 **60s**，确保高并发子智能体同时写库时绝不丢失最终结果）（[Session Storage](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage)）。

   * 通过 `runtime_State` 表的 `runtime_epoch` 实施写栅栏，并通过 `session_admissions` 表严格执行 `queued → started → completed / unknown` 状态机，防止崩溃后重复触发工具副作用（[Gateway local sessions](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-local-sessions)）。

3. **两级数据库损坏自愈（Two-Tier Corruption Recovery）**：

   * **Tier 1（FTS5 索引局部损坏）**：一旦捕获 FTS 损坏异常，自动删除同步触发器与虚拟表，置位 `fts_stale` 标志，将 `session_search` 无缝降级为 `LIKE` 查询，并在会话结束后后台静默重建索引。

   * **Tier 2（主库物理损坏隔离）**：抛出 `StateDbCorruptError`，对所有旧连接句柄设置 `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE`（防止关闭旧句柄时把坏页刷入 WAL），将原库連同 `-wal`/`-shm` 原子重命名为 `.corrupt.<timestamp>.<pid>` 进行现场保全，同时将内存消息转储至 `~/.hermes/sessions/corrupt_recovery_<session_id>.jsonl` 应急文件，随即无缝建立新库继续服务（[State DB Recovery](https://hermes-agent.nousresearch.com/docs/developer-guide/state-db-recovery)）。

## 九、 插件扩展契约、流式多模态管线与纵深安全（Extensibility, Streaming & Defense-in-Depth）

### 9.1 插件扩展契约：观察者钩子与洋葱圈中间件分离

一个可扩展的 Harness 必须允许开发者在不侵入核心代码的前提下注入自定义监控、审计、路由与上下文增强逻辑，但同时必须防止劣质插件卡死主循环或撑爆上下文。

在 [Build a Hermes Plugin | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) 中，Hermes 将扩展能力清晰地划分为两套正交机制：

1. **20+ 生命周期钩子（Lifecycle Hooks，以直通观察为主）**：

   * 涵盖会话与网关启停、回合开始与结束、压缩前后、子智能体派生、内存写入与技能加载等全链路节点。

   * **严格的控制权收口**：在全部 20 多个钩子中，**仅有 `pre_llm_call`（可注入本轮临时上下文或动态过滤可用工具集）与 `pre_tool_call`（可拦截并拒绝工具执行 `{"block": True, "reason": "..."}`）具备干预控制流的能力**；其余所有钩子均为纯观察性质（Fire-and-Forget），且任何插件异常均被捕获隔离，绝不中断主回路。

   * **输出防撑爆溢写（Output Spill Cap）**：插件注入的文本若超过 `10,000 字符`，超出部分会自动溢写至磁盘临时文件并在上下文中仅保留文件路径引用。

2. **四类洋葱圈中间件链（4 Middleware Chains，支持包裹与改写）**：

   * 针对需要修改请求载荷、缓存结果或统计耗时的切面需求，提供 `tool_request`、`llm_request`、`tool_execution`、`llm_execution` 四条可组合的 `next()` 中间件管道（[Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)）。

### 9.2 流式语音合成管线（Streaming TTS Pipeline）

对于跨端语音助手或实时交互场景，等待大模型生成完整篇回答后再调用 TTS 会带来数秒的静默等待。

根据 [Streaming TTS Internals | Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/streaming-tts)，通用低延迟语音管线的核心在于**流式子句切分与异步预取（Sentence Chunking & Prefetching）**：

1. **跨 Token Delta 的思维链剥离**：`SentenceChunker` 在接收流式文本块时，实时维护状态机以剥离 `<think>...</think>` 推理块（哪怕标签被切分在两个相邻的 Token Delta 中也能准确识别拦截），确保绝不把内部推理过程念出来。

2. **自然韵律切分与 3 句并发预取**：按句末标点、换行及逗号子句边界切分文本，并在后台并发预取最多 **3 个句子的音频流**，将合成好的原始 PCM 音频帧实时推入播放队列（原生支持 `elevenlabs`、`openai`、`gemini`、`xai` 流式接口，并对 Edge TTS 等非流式接口提供自动分片降级）（[Streaming TTS Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/streaming-tts)）。

### 9.3 八层纵深安全防御体系（8-Layer Defense-in-Depth Security）

由于 Agent 拥有执行 Shell 命令、读写本地文件与访问内网的能力，安全边界是生产级 Harness 不可妥协的底线。在 [Security | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/security) 中，Hermes 构建了从底层命令拦截到顶层输出脱敏的 **8 层纵深防御体系**，其中针对工具与命令执行的三道核心闸门尤为关键：

| 防御层级 | 执行机制与拦截策略 | 为什么不可或缺 | 
| ----- | ----- | ----- | 
| 第一道闸门：不可绕过的硬阻断黑名单  （`HARDLINE_PATTERNS`） | 针对销毁根文件系统、格式化磁盘块设备、直接写内核伪文件、Fork 炸弹等毁灭性命令，在最底层硬编码拦截。  • **不可绕过性**：哪怕用户显式开启了全自动免批模式（`--yolo` 或 `HERMES_YOLO_MODE`），硬阻断黑名单依然强制生效。  • **语法错误默认拒绝（Fail-Closed）**：在解析 Shell 命令时若遇到未闭合引号等畸形语法（常见于攻击者试图用引号逃逸绕过正则检测），解析器直接按最高风险拒绝执行。 | 防止模型幻觉或恶意网页中的间接提示词注入（Indirect Prompt Injection）造成不可逆的系统损毁（[Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)）。 | 
| 第二道闸门：用户自定义策略与语义风险审批  （Approval Modes） | 1\. 先匹配 `config.yaml` 中的 `approvals.deny` 拒绝通配符。  2\. 对敏感操作（如 `rm -rf`、修改 Git 历史、携带变量的动态命令），支持三种审批模式：`manual`（逐条人工确认）、`smart`（调用轻量辅助 LLM 评估当前命令在上下文中的真实意图与风险等级，安全则放行、高危则弹窗）、`off`。 | 在日常高频开发效率与高危动作确认之间取得平衡，避免用户因频繁弹窗产生“审批疲劳”（[Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)）。 | 
| **第三道闸门：文件系统、网络 SSRF 与凭据最小权限隔离** | • **文件读写不对称保护**：拦截对 `~/.ssh/`、`~/.aws/`、系统目录及 `SOUL.md` 的越权修改；对 `.env` 环境变量文件采取“允许写入配置模板，但严禁读取明文内容”的单向策略。  • **SSRF 防护**：网页抓取工具强制校验 DNS 解析结果，拦截指向私有网段（`127.0.0.0/8`、`10.0.0.0/8`、`169.254.169.254` 云元数据端点等）的请求与重定向跳板。  • **凭据沙箱剥离与输出脱敏**：子进程执行前自动清空环境变量中的敏感 API Keys（仅按插件声明的 `env_passthrough` 白名单放行），并在所有日志与工具返回进入上下文前做正则密钥脱敏。 | 彻底斩断“通过读取本地 `.env` 或云主机 Metadata 窃取密钥并外发”的攻击链条（[Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)）。 | 

## 十、 通用 AI Agent Harness 架构设计全景检查清单（Checklist）

在设计或评估一套跨端、长程 AI Agent Harness 时，可直接对照以下 **9 大维度、27 项核心工程指标** 进行架构走查：

| 架构分层 | 核心检验问题（Pass / Fail 判据） | Hermes Agent 对标方案参考 | 
| ----- | ----- | ----- | 
| **1. 总体拓扑** | 是否所有交互端（CLI/GUI/移动端/IM/定时任务）均收敛至单一无 UI 依赖的编排内核，而非各自维护一套胶水循环？ | `AIAgent` 单核窄腰架构（[Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)） | 
| **2. 控制回路** | 内部消息列表是否与具体模型厂商线协议解耦？流式生成中途按下中断键时，是否能彻底丢弃半截响应以保证 `User/Assistant` 与 `tool_call/tool_result` 严格配对？ | 9 步状态机 + `_interruptible_api_call` 后台流（[Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)） | 
| **3. 缓存经济学** | System Prompt 是否按 `Stable → Context → Volatile` 排序并在会话期内冻结？中途切换终端或增删技能时，是否通过用户消息旁路通知而非原地篡改 System Prompt？ | 三层组装 + 单次用户消息旁路通道 + CI 快照（[Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)） | 
| **4. 上下文计量** | 是否以 API 真实返回的 `usage` 为计量锚点（而非纯本地重算）？是否具备针对多模态图片的在线 Token 残差学习能力？ | `usage_anchor.py` + `image_token_cost.py`（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)） | 
| **5. 压缩与保真** | 压缩前是否先做零成本旧工具输出修剪？切分点是否向后对齐以避免劈开工具调用对？摘要是否包含正则提取的精确标识符索引并原样保留用户指令？是否支持后台预备压缩与非对称微压缩？ | 4 阶段压缩 + `prepared_compaction` + `micro_compactor`（[Micro-compaction](https://hermes-agent.nousresearch.com/docs/developer-guide/micro-compaction)） | 
| **6. 工具与卸载** | 面对上百个外部工具是否提供 `search/describe/call` 渐进式披露？面对多步机械数据处理是否提供基于本地 RPC 的代码执行沙箱以防中间输出塞满窗口？是否能自动拦截空轮询并转为完成时通知？ | 3 级 `tool_search` + Unix Socket `execute_code` + `process_wait_auto_notify`（[Code Execution](https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution)） | 
| **7. 子智能体编排** | 派生的子智能体在隔离对话历史的同时能否复用父会话的 Prompt Cache 前缀？是否用基于心跳进度的停滞检测（Stall Monitor）替代了僵化的固定总超时？是否支持 Git Worktree 物理隔离与运行时 `steer` 引导？ | `delegate_task` + 双阈值 Stall Monitor + Worktree 隔离（[Subagent Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)） | 
| **8. 记忆与演进** | 常驻核心记忆是否有硬性字符上限与溢出强制原子合并机制？历史检索是否做到零常驻 Token 开销？后台自省复盘是否复用了热缓存并在本地推理繁忙时自动让行？是否有自动归档陈旧技能的馆长机制？ | 定长 `MEMORY.md` + FTS5/Trigram `session_search` + `Curator`（[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)） | 
| **9. 状态与安全** | 多端并发接入同一会话时是否有单写者权威与 Epoch 栅栏？网关崩溃恢复时能否将执行中途的回合标记为 `unknown` 以防重复触发外部副作用？底层是否具备连 `--yolo` 都无法绕过的硬阻断安全防线？ | `gateway.sock` 单写者 + `session_admissions` + 8 层安全防线（[Gateway local sessions](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-local-sessions)、[Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)） | 
