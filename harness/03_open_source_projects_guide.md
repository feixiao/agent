# 优质开源 Agent Harness 项目精读与源码学习指南

> **文档定位**：本指南专为开发者深入学习工业级 Agent Harness 源码而设计。精选了全球最具代表性的云端、端侧、自主研发与评测底座项目，详细拆解其核心目录、关键源码文件与精读切入点，帮助你以“透视底层架构”的视角最高效地阅读代码。

---

## 一、 精选开源项目矩阵总览

| 项目名称 | 开源仓库与许可 | 领域分类 | 最值得学习的核心工程设计 | 推荐精读等级 |
|:---|:---|:---|:---|:---:|
| **OpenHands** (原 OpenDevin) | [All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands) <br/> `MIT` | 云端全能型 | 事件驱动流（EventStream）、多环境 Docker 沙箱运行时、Controller 状态机 | ⭐⭐⭐⭐⭐ (云端必读) |
| **SWE-agent** | [princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent) <br/> `MIT` | 代码解决型 | ACI（Agent-Computer Interface）人机终端交互设计、专用文件浏览与编辑工具底座 | ⭐⭐⭐⭐⭐ (编码必读) |
| **LangGraph** | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) <br/> `MIT` | 编排运行时 | 基于 Pregel 计算模型的图状态机、持久化检查点（Checkpointer）、人机协同中断 | ⭐⭐⭐⭐⭐ (架构必读) |
| **PalmClaw** | [ModalityDance/PalmClaw](https://github.com/ModalityDance/PalmClaw) <br/> `AGPL-3.0` | 端侧/Android | 完整的 Android 端侧 Harness：上下文装配、记忆固化、原生权限闸门、MCP 支持 | ⭐⭐⭐⭐⭐ (移动端必读) |
| **Foundation Models Utilities** | [apple/foundation-models-utilities](https://github.com/apple/foundation-models-utilities) <br/> `Apache-2.0` | 端侧/Apple | Apple 官方开源的端侧 Harness 抽象：Skills、滚动窗口裁剪、`DropCompletedToolCalls` | ⭐⭐⭐⭐ (iOS必读) |
| **llama.cpp** | [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp) <br/> `MIT` | 算力与推理底座 | C/C++ 极简无依赖推理、GBNF 语法树约束解码（物理消除 JSON 格式错误） | ⭐⭐⭐⭐⭐ (底层必读) |
| **OpenManus** | [mannaandpoem/OpenManus](https://github.com/mannaandpoem/OpenManus) <br/> `Apache-2.0` | 极简微内核 | 不依赖庞大框架的白盒纯 Python 原生 Agent Loop 与工具链，适合新手快速通关 | ⭐⭐⭐⭐ (入门首选) |
| **lm-evaluation-harness** | [EleutherAI/lm-eval](https://github.com/EleutherAI/lm-evaluation-harness) <br/> `MIT` | 评测基准底座 | 行业事实标准的模型自动化评测 Harness、Task Registry、动态批处理与指标聚合 | ⭐⭐⭐⭐ (评测必读) |

---

## 二、 云端生产级 Harness 源码精读

### 1. OpenHands (All-Hands-AI/OpenHands)
> **代码定位**：开源界目前最成熟、代码工程化程度最高的云端自主 Agent 平台。

#### 核心目录结构
```text
openhands/
├── controller/            # 核心控制器（Agent Loop 与状态调度）
│   ├── agent.py           # Agent 基类定义
│   └── state/             # 状态机管理与事件状态
├── events/                # 事件流（Event Stream）核心定义
│   ├── action/            # 动作事件 (CmdRunAction, FileWriteAction 等)
│   └── observation/       # 观察事件 (CmdOutputObservation, FileReadObservation)
├── runtime/               # 运行时沙箱（核心底盘！）
│   ├── client/            # 客户端与沙箱通信 RPC
│   └── plugins/           # 插件系统（Jupyter, agent-skills 等）
└── storage/               # 检查点与文件持久化
```

#### 推荐精读切入点
1. **事件流架构**：精读 `openhands/events/stream.py` 与 `openhands/controller/agent_controller.py`。
   * **学习重点**：看 OpenHands 如何彻底抛弃传统字符串拼装，将每次思考转化为 `Action` 事件，将工具和沙箱的执行结果转化为 `Observation` 事件。理解单向事件驱动流（Event-driven）如何让 Agent 支持实时流式输出、取消与重放。
2. **Docker 沙箱隔离**：精读 `openhands/runtime/impl/docker/docker_runtime.py`。
   * **学习重点**：学习如何在后台为每个任务动态启动轻量 Docker 容器，如何通过 Unix Domain Socket 安全地向容器下发命令并收集输出。

---

### 2. SWE-agent (princeton-nlp/SWE-agent)
> **代码定位**：在代码生成与修复领域（SWE-bench）开创了 ACI（Agent-Computer Interface）标准的奠基之作。

#### 核心目录结构
```text
sweagent/
├── agent/
│   ├── agents.py          # 主循环驱动与每步 Prompt 装配
│   └── models.py          # 模型调用接口与 Token 计数
├── environment/
│   └── swe_env.py         # Docker 执行环境与交互终端
└── tools/
    └── commands.py        # 专为大模型定制的高效终端命令（ACI）
```

#### 推荐精读切入点
1. **专为 Agent 定制的操作命令（ACI）**：精读 `sweagent/tools/commands.py`。
   * **学习重点**：普通开发者直接给模型丢一个原生 `bash`，模型很容易 `cat` 一个几万行的大文件导致上下文爆炸。SWE-agent 专门设计了分页查看命令 `open <file> <line>`、`scroll_up`、`scroll_down`，以及精确匹配替换命令 `edit <start_line>:<end_line>`。看它如何通过工程手段降低模型的认知负荷。
2. **环境重置与结果提取**：精读 `sweagent/environment/swe_env.py`，看它如何用 Python 封装长链接 bash 会话与解析 Exit Code。

---

### 3. LangGraph (langchain-ai/langgraph)
> **代码定位**：企业级生产环境最主流的图编排与状态持久化底盘。

#### 核心目录结构
```text
langgraph/
├── graph/
│   ├── state.py           # 状态图（StateGraph）定义与 Schema
│   └── message.py         # 消息聚合机制 (add_messages 增量合并)
├── checkpoint/            # 状态检查点持久化（Durable Execution）
│   ├── base.py            # Checkpointer 接口
│   └── memory.py          # 内存与 DB 存储实现
└── pregel/                # 底层计算调度引擎（基于 Google Pregel 论文）
    └── loop.py            # 节点并发调度与通道同步
```

#### 推荐精读切入点
1. **状态检查点机制（Checkpointer）**：精读 `langgraph/checkpoint/base.py`。
   * **学习重点**：看 LangGraph 如何在每个节点（Node）执行完毕后，自动给整个系统的 Memory 拍摄版本快照。这就是实现 **Human-in-the-Loop（人机审批挂起）** 和 **Time-Travel（时间旅行回退调试）** 的工程奥秘。

---

## 三、 端侧与移动端轻量 Harness 源码精读

### 1. PalmClaw (ModalityDance/PalmClaw)
> **代码定位**：EMNLP 2026 最新开源的完整 Android 端侧 Agent Harness 系统（纯 Kotlin 实现）。

#### 核心目录结构
```text
palmclaw/
├── app/src/main/java/com/palmclaw/
│   ├── agent/
│   │   ├── AgentLoop.kt            # 端侧主执行循环与步数熔断
│   │   ├── ContextBuilder.kt       # 上下文装配与严格 Token 预算治理
│   │   └── MemoryConsolidator.kt   # 本地短期与长期记忆固化
│   ├── tools/                      # 丰富的 Android 原生系统工具封装
│   │   ├── calendar/               # 日历读写
│   │   ├── contacts/               # 通讯录访问（含权限检查）
│   │   └── shell/                  # 本地 Termux / Shell 交互
│   └── mcp/                        # Model Context Protocol 本地客户端
```

#### 推荐精读切入点
1. **端侧循环驱动与权限检查**：精读 `AgentLoop.kt`。
   * **学习重点**：看它如何在 Android 主线程之外安全驱动后台协程，如何将系统权限申请（Runtime Permissions）无缝嵌入到 Agent 的工具调用流程中。
2. **上下文极致压缩**：精读 `ContextBuilder.kt`，看它如何在手机端面对小上下文时，剔除无用 tool call 结果并控制最大 Token 预算。

---

### 2. Apple Foundation Models Utilities (apple/foundation-models-utilities)
> **代码定位**：Apple 官方开源的 Swift 端侧 Harness 实用抽象库。

#### 核心精读点
* **精读文件**：`Sources/FoundationModelsUtilities/HistoryPruning/`
* **学习重点**：
  * `DropCompletedToolCalls`：如何在不破坏多轮语义的前提下，动态移除已经完成历史任务的工具冗余输出；
  * `RollingWindow`：端侧极简滑动窗口实现；
  * `Skill` 协议抽象：如何将端侧原生能力模块化包装并动态下发。

---

### 3. llama.cpp (ggerganov/llama.cpp)
> **代码定位**：C/C++ 跨平台本地模型推理引擎，端侧自下载模型的绝对基石。

#### 推荐精读切入点
* **语法约束解码引擎（GBNF Grammar）**：精读 `common/grammar-parser.cpp` 与 `grammar-parser.h`。
* **学习重点**：
  * 普通云端调用经常会遇到模型吐出非合法的 JSON（如缺少闭合引号、逗号多余）。
  * llama.cpp 的 GBNF 会根据你给出的 BNF 语法树，在模型自回归预测下一个 Token 的 Logits 分布时，**直接将所有不符合语法规则的 Token Logits 掩码（置为 $-\infty$）**。
  * 彻底搞懂“为什么从采样底层约束可以 100% 保证结构化输出合规”。

---

## 四、 极简微内核与教学项目

### OpenManus (mannaandpoem/OpenManus)
> **代码定位**：完全不依赖 LangChain 或 AutoGen 等三方重型框架的纯原生 Python 白盒实现。代码结构极度扁平、直观。

#### 核心精读文件与学习路径
1. `app/agent/base.py`：观察最基础的 `BaseAgent` 抽象，看 `step()` 方法如何接收环境观察并产生动作；
2. `app/agent/toolcall.py`：理解大模型原生 Function Calling 的解析、执行、异常捕获与格式重整；
3. `app/tool/base.py`：工具注册中心的极简实现，学习如何用 Python 函数的类型注解（Type Hint）自动生成标准的 JSON Schema。

---

## 五、 新手源码精读路线图建议

如果你准备深入代码学习，建议按照以下**四步渐进法**展开：

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  第 1 步：阅读 OpenManus (用半天时间看通纯 Python 白盒 ReAct 循环)        │
│  重点理解：Prompt 怎么拼、ToolCall 怎么派发、结果怎么塞回。                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第 2 步：精读 OpenHands 的 Controller 与 EventStream (掌握企业级云端 Harness)│
│  重点理解：为什么要抛弃单向字符串，改用 Action/Observation 双向事件流。       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第 3 步：深入 PalmClaw 与 llama.cpp GBNF (掌握端侧严苛物理约束)           │
│  重点理解：端侧如何做权限闸门、如何用 GBNF 做底层语法掩码、如何做上下文裁剪。  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第 4 步：研究 LangGraph 的 Checkpointer 机制 (掌握任务中断、持久化与恢复)    │
│  重点理解：复杂多步长任务在服务重启或网络抖动时，如何从断点精确自愈。         │
└─────────────────────────────────────────────────────────────────────────┘
```
