# 深入 AI Agent 开发体系 (Agent in Depth)

> 核心公式：$$\text{Agent} = \text{Model（概率模型引擎）} + \text{Harness（确定性工程底盘）}$$
> 
> 商业级 Agent 的本质，是用确定性的 Harness 工程对抗模型单步不确定性的复合放大（$Pass^k = p^k$）。本项目聚焦从理论原理、外围底盘设计、经典协同模式，到多模态端侧感知与垂直行业（智能座舱、代码生成）的完整深入落地。

---

## 🎯 小白入门指南：如何靠本项目吃透 AI Agent？

> 如果你是刚接触 Agent 的新手，请把本仓库当作一份**从“会调包”到“懂底盘”的通关路线图**。不需要你懂复杂的深度学习数学，只要有基础 Python 读写能力，就能彻底搞懂真实工业级 Agent 的设计精髓。

### 1. 概念破迷：30 秒搞懂什么是 Agent？
* **普通聊天（ChatGPT）**：你问一句、它回一句，属于**单次开环嘴炮**，没有手脚，无法真正替你办事。
* **AI 智能体（Agent）**：你给它一个目标（例如“帮我订去杭州最便宜的高铁并把行程写入日历”），它能**自我规划任务、主动调用外部工具（查票/写日历）、检查执行结果、报错自动纠错，直到达成目标**。
* **极简本质公式**：
  $$\text{Agent} = \text{大模型（负责概率思考的“脑”）} + \text{Harness（负责确定性控制的“手脚、仪表盘与刹车”）}$$

---

### 2. 六步通关实战路线图 (从极简微内核到工业级落地)

```text
┌────────────────────────────────────────────────────────────────────────┐
│  第 1 关：建立防坑直觉 (30分钟)                                            │
│  阅读 docs/books/AI-Agents-in-Depth-QuickStart.md 中的 12 大排雷地图     │
│  目标：明白为什么大模型做多步任务会死循环、乱扣费、胡言乱语 (Pass^k = p^k)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 2 关：上手经典 8 大模式 (1 ~ 2 天)                                   │
│  阅读 docs/books/ 中的中英双语电子书，运行 patterns/ 示例                 │
│  目标：掌握提示链、路由、反思、工具调用、规划与多智能体 8 种上层编排模式   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 3 关：拆解极简微内核与确定性 Harness (2 ~ 3 天)                       │
│  对照原版 pi (pi.dev) 极简 4 原语设计，深入精读 core/ 纯 Python 白盒源码  │
│  目标：搞懂“低线束税 (Low Harness Tax)”、防死循环熔断、KV-Cache 前缀静止 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 4 关：解构工业级全能终端智能体 (进阶实操)                            │
│  精读 docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md               │
│  目标：拆解 Claude Code (垂直一体化) 与 OMP (Prewalk 阶梯调度 / LSP / ACP)│
│       掌握兼顾顶级确定性与降本 80% 的“双剑合璧”5 步标准化作战 SOP         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 5 关：观摩企业级垂直场景落地 (3 ~ 5 天)                              │
│  研究 apps/cockpit_agent (车载智能座舱) 与 apps/coding_agent (代码助理)  │
│  目标：看懂真实的 Master-SubAgent 硬件控制与防行号漂移的原位精准替换机制 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 6 关：工业级跨语言与端云基础设施 (架构师视野)                         │
│  阅读 docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md                     │
│  目标：掌握端侧嵌入式 C++ (llama.cpp 零 GC) 与云端高并发 Go (Eino) 调度底座│
└────────────────────────────────────────────────────────────────────────┘
```

#### 详细通关指引：

1. **第一关 · 建立防坑直觉（打破“大模型万能”盲目崇拜）**：
   - **必读文件**：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md)
   - **核心收获**：掌握复合概率法则 $Pass^k = p^k$（如果单步成功率是 95%，连续做 10 步端到端成功率仅剩 59.8%）。彻底搞懂为什么 Agent 上线不能靠碰运气，必须依靠工程底盘兜底。

2. **第二关 · 动手跑通经典 8 大模式（体验 Agent 的手和脚）**：
   - **参考书籍**：中英双语 EPUB（[`agentic-design-patterns-cn.epub`](docs/books/agentic-design-patterns-cn.epub)）
   - **动手代码**：进入 [`patterns/`](patterns/README.md)，推荐先看 [`patterns/langchain/`](patterns/langchain/ReadMe.md)：
     - **提示链 (Chaining)**：任务流水线串联；
     - **路由 (Routing)**：按意图分配不同模型或分支；
     - **反思 (Reflection)**：AI 生成内容后自己挑刺检查；
     - **工具使用 (Tool Use)**：让 AI 学会查天气、搜计算器；
     - **多智能体 (Multi-Agent)**：多个 Agent 角色对话协同。

3. **第三关 · 拆开黑盒看底盘：从原版 `pi` 与自主研发的 `core/` 学习极简 Harness**：
   - 现成大框架（如 LangChain/AutoGen）封装过深，注入数千 Token 冗余规则导致“高线束税 (High Harness Tax)”。
   - **最佳学习标杆**：对照开源极简神作原版 `pi`（[pi.dev](https://pi.dev) / `earendil-works/pi`）仅用 4 个原语工具 (`read`, `write`, `edit`, `bash`) 构建出极高成功率的极简心智，并在本项目 [`core/`](core/) 中用纯 Python 深入学习白盒实现：
     - **防死循环熔断 (`core/loop/`)**：看如何用 30 行代码实现熔断器，连续 2 次参数相同或遇到报错立即熔断，防止烧光 Token；
     - **省钱与提速缓存 (`core/context/`)**：看为什么 Prompt 开头绝对不能加动态时间戳，如何保持前缀静止最大化命中 GPU KV Cache；
     - **防重复扣款与操作幂等 (`core/sandbox/`)**：看如何在工具调用中注入唯一幂等键 (`idempotency_key`)，彻底解决弱网重试导致重复扣款。

4. **第四关 · 解构现代工业级终端 Agent 双雄：Claude Code 与 OMP**：
   - **必读白皮书**：[`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)
   - **核心收获**：
     - 理解 **Claude Code** 的垂直一体化共生（Co-Design）与 5 分钟 TTL 缓存工程；
     - 理解 **OMP (Oh My Pi)** 的 Prewalk 阶梯降模（慢模型规划 $\to$ 快模型编码）、LSP 零编译语法即时诊断与 ACP 跨进程协议；
     - 掌握 **“双剑合璧”** 实操 SOP：用 Claude Code 规划复杂架构，用 `omp --from-claude --prewalk` 接管批量落地，实现质量不降、Token 成本暴降 80%。

5. **第五关 · 观摩真实产业垂直落地**：
   - 学习 [`apps/cockpit_agent/`](apps/cockpit_agent/ReadMe.md)：车载座舱中，主中枢 Agent 如何解析用户一句话，将车控指令下发给空调、座椅等硬件子 Agent。
   - 学习 [`apps/coding_agent/`](apps/coding_agent/)：看代码助手为什么不能盲目依赖行号（防止行号漂移），而是采用 AST 语法分析与特征原位替换。

6. **第六关 · 拓展工业级跨语言与端云基础设施**：
   - 学习 [`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)：理解真实业务中，端侧嵌入式/车载设备对零 GC 和低延迟的要求（为什么用 C++ `llama.cpp`），以及云端大并发微服务网关的要求（为什么用 Go `cloudwego/eino`）。
   - 学习 [`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)：理解真实业务中，端侧嵌入式/车载设备对零 GC 和低延迟的要求（为什么用 C++），以及云端大并发微服务网关的要求（为什么用 Go `cloudwego/eino`）。

---

### 3. 小白常见问题答疑 (FAQ)

* **Q: 我没有昂贵的独立显卡（GPU），能跑这个项目吗？**
  * **A: 完全可以！** Agent 的开发重心在**逻辑编排、工具调用与工程状态控制**，不在模型训练。你可以直接配置云端 API（如 DeepSeek、OpenAI、Kimi），或在本地电脑用 CPU 安装 [Ollama](https://ollama.com/)（运行轻量模型如 `qwen2.5:3b` 或 `deepseek-r1:1.5b`），零显卡成本即可跑通全部案例。

* **Q: 我刚学完 Python 基础，能看懂本项目代码吗？**
  * **A: 毫无压力。** 本项目 `core/` 遵循极简微内核哲学，没有任何花哨的黑魔法和臃肿依赖，主要使用标准数据结构、枚举与简单的状态流转，代码注释详尽，非常适合作为入门的第一个工程级开源项目阅读。

* **Q: 我应该先看书还是先动手写代码？**
  * **A: 推荐“两头并进”**：先花 20 分钟翻翻 [`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md) 建立大局观，然后直接进入 `patterns/` 跑一个工具调用的 Demo；当产生疑问（“它怎么会死循环？”）时，再来看 `core/` 的实现原理。

---

## ⚡ 快速上手

### 1. 环境准备
```bash
# 基础运行时
pip install -e .

# 安装特定能力扩展
pip install -e ".[patterns-langchain]"   # 安装 LangChain 模式依赖
pip install -e ".[patterns-autogen]"     # 安装 AutoGen 模式依赖
pip install -e ".[evals]"                # 安装评测套件
```

---

## 🗺️ 仓库目录全景导航

```text
agent/
├── docs/                          # 统一文档中心与理论知识库
│   ├── books/                     # 经典理论与电子书：《深入理解 AI Agent》全本、《智能体设计模式》中英版 (EPUB/PDF)
│   ├── design_patterns/           # 8 大设计模式原理与架构文档（对应 xindoo/agentic-design-patterns）
│   ├── architecture/              # Harness 架构通用白皮书与 C++/Go 工业级框架选型指南
│   └── multimodal/                # 音视频多模态与端侧全景指南 (AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
│
├── core/                          # 【核心底座】自主研发 Agent 运行时与 Harness 引擎
│   ├── context/                   # 上下文工程：Prompt Cache 前缀对齐、Token 预算、窗口修剪
│   ├── loop/                      # 执行循环：显式状态机、死循环检测、熔断机制、计步器
│   ├── memory/                    # 记忆管理：短期工作区 (WorkingMemory) 与长期画像检索
│   ├── planning/                  # 任务规划：DAG 依赖解析与动态重规划
│   ├── reflection/                # 反思机制：Self-Correction 与 Critic 校验器
│   └── sandbox/                   # 安全沙箱：工具执行隔离与写操作幂等键注入
│
├── tools/                         # 工具协议与注册中心
│   ├── registry.py                # 动态工具注册器（渐进式暴露 L0/L1/L2）
│   ├── builtin/                   # 内置高频工具
│   └── mcp_servers/               # Model Context Protocol (MCP) 服务生态
│
├── patterns/                      # 【模式工程实战】源自 xindoo/agentic-design-patterns 的 8 大模式多框架对照实现
│   ├── langchain/                 # LangChain 实现（提示链、路由、并行、反思、工具、规划、多智能体、记忆）
│   └── autogen/                   # AutoGen 0.4+ 实现（模式范例与 quickstart 快速上手）
│
├── apps/                          # 【垂类工程落地】垂直领域生产级 Agent
│   ├── cockpit_agent/             # 智能座舱 Agent（MasterAgent + 垂类车控/导航/健康 Sub-Agents）
│   ├── coding_agent/              # 代码智能体（基于 AST 与原位精准替换）
│   └── multimodal_edge/           # 边缘巡检与具身感知智能体
│
├── perception/                    # 【多模态与端侧底座】传感器流接入与边缘计算
│   ├── edge_platforms/            # 三大边缘节点架构：Mac Studio / Android Pixel 10 / Jetson
│   └── labs/                      # 音视频多模态实战套件（VLM、Whisper、LoRA 仿真、Pixel 10 导出）
│
├── evals/                         # 【评测与数据飞轮】连续可靠性度量与故障归因
│   ├── benchmarks/                # 测试基准集（金标用例、多步长程用例）
│   ├── metrics/                   # 核心指标（Pass^k 连续成功率、单步准确率、Token 成本）
│   └── prefix_regression/         # 故障归因：前缀回归定位首个偏离错误 (First Mistake)
│
├── tests/                         # 单元与集成测试套件
├── pyproject.toml                 # 模块化依赖定义
└── README.md                      # 本文档
```

---

## 📚 探索路径索引与参考

1. **理论与心智模型**：
   - 书籍索引中心：[`docs/books/README.md`](docs/books/README.md)（收录两部经典著作全本及速查清单）
   - 核心理论速查：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md)（掌握 12 大排雷归因地图与 $Pass^k$ 法则）
   - 模式电子书：中英双语 EPUB（[`agentic-design-patterns-cn.epub`](docs/books/agentic-design-patterns-cn.epub) / [`agentic-design-patterns-en.epub`](docs/books/agentic-design-patterns-en.epub)）
2. **经典模式工程**：
   - 模式总览：[`patterns/README.md`](patterns/README.md)（对应开源项目 [xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns)）
   - 查看 LangChain 8 大模式实现：[`patterns/langchain/ReadMe.md`](patterns/langchain/ReadMe.md)
   - 查看 AutoGen 0.4+ 模式与上手：[`patterns/autogen/ReadMe.md`](patterns/autogen/ReadMe.md)
3. **垂直行业架构**：
   - 车载智能座舱 Agent：[`apps/cockpit_agent/ReadMe.md`](apps/cockpit_agent/ReadMe.md)
4. **端侧多模态实践**：
   - 音视频与边缘节点手册：[`docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md`](docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
   - 本地实操套件：[`perception/labs/README.md`](perception/labs/README.md)
5. **工业级 C++/Go 选型与生产落地**：
   - 端云生产框架实战指南：[`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)（掌握 C++ 端侧运行时 `llama.cpp` / `MNN-LLM` 与 Go 云端微服务框架 `Eino` / `Genkit`）。
   - 终端智能体架构对比白皮书：[`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)（站在 Agent Harness 视角深度剖析 **OMP (Oh My Pi)** 与 **Claude Code**：垂直共生 vs 异构分工、Prewalk 阶梯调度、LSP 诊断与经济学选型）。
