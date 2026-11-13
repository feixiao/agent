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
│  对照原版 pi 极简 4 原语设计，深入精读 core/ (Python) 与 core/native_cpp/ (C++)│
│  目标：搞懂“低线束税”、防死循环熔断、前缀静止与微秒级原生状态机底盘       │
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
│  研究 apps/cockpit_agent (车载座舱) 与 experiments/chapter5/coding-agent   │
│  目标：看懂真实的 Master-SubAgent 硬件控制与防行号漂移的原位精准替换机制 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  第 6 关：工业级跨语言与端云基础设施 (架构师视野)                         │
│  研读 core/native_cpp/、mac_standalone_tts/ 与 docs/architecture/       │
│  目标：掌握端侧原生 C++ (微秒级 Harness/llama.cpp) 与云端高并发 Go 调度底座│
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
   - **最佳学习标杆**：对照开源极简神作原版 `pi`（[pi.dev](https://pi.dev) / `earendil-works/pi`）仅用 4 个原语工具 (`read`, `write`, `edit`, `bash`) 构建出极高成功率的极简心智，并在本项目 [`core/`](core/) 中深入学习白盒实现：
     - **纯 Python 原生参考实现 (`core/`)**：
       - **防死循环熔断 (`core/loop/`)**：看如何用 30 行代码实现熔断器，连续 2 次参数相同或遇到报错立即熔断，防止烧光 Token；
       - **省钱与提速缓存 (`core/context/`)**：看为什么 Prompt 开头绝对不能加动态时间戳，如何保持前缀静止最大化命中 GPU KV Cache；
       - **防重复扣款与操作幂等 (`core/sandbox/`)**：看如何在工具调用中注入唯一幂等键 (`idempotency_key`)，彻底解决弱网重试导致重复扣款。
     - **高性能原生 C++20 Harness 底盘 (`core/native_cpp/`)**：
       - 面向端侧与高吞吐业务，提供零拷贝 JSON 校验、Token 预算硬限额、微秒级状态机与 PII 脱敏网关；实测单步状态机开销低至 **3.83 µs**，吞吐量超 **24 万 turns/s**，RSS 内存仅 **2.5 MB**。
4. **第四关 · 解构现代工业级终端 Agent 双雄：Claude Code 与 OMP**：
   - **必读白皮书**：[`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)
   - **核心收获**：
     - 理解 **Claude Code** 的垂直一体化共生（Co-Design）与 5 分钟 TTL 缓存工程；
     - 理解 **OMP (Oh My Pi)** 的 Prewalk 阶梯降模（慢模型规划 $\to$ 快模型编码）、LSP 零编译语法即时诊断与 ACP 跨进程协议；
     - 掌握 **“双剑合璧”** 实操 SOP：用 Claude Code 规划复杂架构，用 `omp --from-claude --prewalk` 接管批量落地，实现质量不降、Token 成本暴降 80%。

5. **第五关 · 观摩真实产业垂直落地**：
   - 学习车载座舱中枢：[`apps/cockpit_agent/`](apps/cockpit_agent/ReadMe.md)：解析用户一句话，将车控指令安全下发给空调、座椅等硬件子 Agent。
   - 学习完整代码智能体：[`experiments/chapter5/coding-agent/`](experiments/chapter5/coding-agent/) 与设计模式 [`experiments/skills/coding-agent-harness/`](experiments/skills/coding-agent-harness/)：看代码助手为什么不能盲目依赖行号（防止行号漂移），而是采用 AST 语法分析、上下文锚点搜索替换与安全沙箱执行。

6. **第六关 · 拓展工业级跨语言与端云基础设施**：
   - **端侧 C++ 与云端 Go 架构指南**：[`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)（掌握端侧嵌入式/车载设备对零 GC 和低延迟的要求，以及云端高并发微服务网关 `cloudwego/eino` 的设计）。
   - **原生极速 C++ Harness 引擎**：[`core/native_cpp/`](core/native_cpp/)（含 CMake 构建、单测与微基准，支持 C API / FFI 跨语言集成）。
   - **端侧极小上下文装配**：[`docs/architecture/ON_DEVICE_HARNESS_DESIGN.md`](docs/architecture/ON_DEVICE_HARNESS_DESIGN.md) 与 [`docs/architecture/ai-agent-harness-architecture.md`](docs/architecture/ai-agent-harness-architecture.md)（掌握 4096 极小上下文约束下的状态装配与系统模型权限闸门）。
   - **端侧脱网语音克隆与离线合成**：[`mac_standalone_tts/`](mac_standalone_tts/README.md)（Apple Silicon Metal MPS 加速、RTF 0.19、完全本地脱网并兼容 OpenAI 协议）。
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

> 💡 **通关导航推荐**：直接进入 [`todolist.md`](todolist.md) 查看从阶段零到阶段七的完整学习与通关打卡地图。

### 1. Python 环境与实验依赖 (uv 管理)
工程统一使用 `uv` 进行高效依赖隔离与运行时管理，通过 `.env` 集中配置模型端点与 API Key：
```bash
# 1. 配置环境变量 (提供 Ollama / OpenAI / 兼容端点开箱即用模板)
cp .env.example .env

# 2. 使用 uv 安装基础运行时与依赖
uv sync

# 3. 按需安装特定扩展模块
uv sync --extra patterns               # 安装设计模式全部依赖 (LangChain + AutoGen)
uv sync --extra ch1                    # 仅安装第 1 章实验依赖 (支持 ch1 ~ ch10 按章自选)
uv sync --extra evals                  # 评测与自动化测试套件
uv sync --extra all                    # 一键安装全量组件

# 4. 运行第 1 章消融实验示例
uv run python experiments/chapter1/context/main.py --help
```

### 2. 运行自动化测试套件 (Python + C++)
```bash
# 运行全量 Python 单元测试与 10 章回归验证 (765+ 测试全部通过)
uv run pytest

# 运行 Mac Standalone TTS 音频流水线测试
PYTHONPATH=. uv run pytest mac_standalone_tts/tests/
```

### 3. 构建与压测原生 C++20 Harness 底盘
```bash
# 本地编译 C++ 原生引擎、单元测试与基准评测
cmake -B core/native_cpp/build core/native_cpp && cmake --build core/native_cpp/build

# 运行 C++ GoogleTest 单元测试
ctest --test-dir core/native_cpp/build --output-on-failure

# 运行微秒级基准压测 (实测平均单步状态机耗时仅 3.83 µs)
./core/native_cpp/build/harness_benchmark
```
---

## 🗺️ 仓库目录全景导航

```text
agent/
├── todolist.md                    # 【学习路线索引】8 阶段通关实战清单与核心文件索引
├── experiments/                   # 【书籍配套实验库】源自《深入理解 AI Agent》全书 10 章 109 个配套实验与设施
│   ├── agentbook/                 # 【Provider 基础设施】统一厂商适配层、模型解析、多模型路由与 Key 管理
│   ├── chapter1/                  # 第 1 章 · AI Agent 入门（上下文消融、多轮搜索、代码执行、离线自学习）
│   ├── chapter2/                  # 第 2 章 · 上下文工程（KV-Cache、提示注入防御、上下文压缩、注意力可视化）
│   ├── chapter3/                  # 第 3 章 · 用户记忆与知识库（Agentic-RAG、向量/稀疏检索、长期用户画像）
│   ├── chapter4/                  # 第 4 章 · 工具工程（MCP 协议、多工具动态发现与路由、通知调度中心）
│   ├── chapter5/                  # 第 5 章 · Coding Agent 与通用 Agent（代码生成、沙箱隔离、多厂商容灾切换）
│   │   └── coding-agent/          # 完整代码智能体工程落地（AST 语法树定位、原位特征替换、沙箱执行与自纠错）
│   ├── chapter6/                  # 第 6 章 · 交互与空间扩展（异步事件流、端到端语音交互、Computer Use）
│   ├── chapter7/                  # 第 7 章 · Agent 评估套件（Tau-Bench、成本收益分析、Elo 胜率天梯）
│   ├── chapter8/                  # 第 8 章 · 模型后训练（CoT 蒸馏、SFT 数据审计、RL 奖励建模）
│   ├── chapter9/                  # 第 9 章 · Agent 持续进化（自进化工具、轨迹校验器、策略闸门）
│   ├── chapter10/                 # 第 10 章 · 多 Agent 协作（长文档分布式翻译、狼人杀协同、组织治理）
│   ├── skills/                    # 【22 个生产级 Agent 技能包】按需触发的高频开发知识包与实操 SOP
│   └── README.md                  # 实验库快速导航与总览
│
├── core/                          # 【核心底座】自主研发 Agent 运行时与 Harness 引擎
│   ├── native_cpp/                # 原生 C++20 高性能 Harness（微秒级状态机、零拷贝 JSON、熔断与基准测试）
│   ├── context/                   # 上下文工程：Prompt Cache 前缀对齐、Token 预算、窗口修剪
│   ├── loop/                      # 执行循环：显式状态机、死循环检测、熔断机制、计步器
│   ├── memory/                    # 记忆管理：短期工作区 (WorkingMemory) 与长期画像检索
│   ├── planning/                  # 任务规划：DAG 依赖解析与动态重规划
│   ├── reflection/                # 反思机制：Self-Correction 与 Critic 校验器
│   └── sandbox/                   # 安全沙箱：工具执行隔离与写操作幂等键注入
│
├── patterns/                      # 【模式工程实战】源自 xindoo/agentic-design-patterns 的 8 大模式多框架对照实现
│   ├── langchain/                 # LangChain 实现（提示链、路由、并行、反思、工具、规划、多智能体、记忆）
│   └── autogen/                   # AutoGen 0.4+ 实现（模式范例与 quickstart 快速上手）
│
├── apps/                          # 【垂类工程落地】垂直领域生产级 Agent 架构
│   └── cockpit_agent/             # 智能座舱 Agent 架构（MasterAgent + 垂类车控/导航/健康 Sub-Agents）
│
├── perception/                    # 【多模态与端侧底座】传感器流接入与边缘计算
│   ├── edge_platforms/            # 三大边缘节点架构：Mac Studio / Android Pixel 10 / Jetson
│   └── labs/                      # 音视频多模态实战套件（VLM 视频推理、Whisper/TTS、LoRA、Pixel 10 导出）
│
├── mac_standalone_tts/            # 【端侧脱网语音】Mac Apple Silicon (Metal MPS) 本地语音克隆与离线合成
│   ├── audio_processor.py         # 音频预处理与 VAD 降噪
│   ├── server.py / cli.py         # OpenAI 兼容语音 API 服务与 CLI 工具
│   ├── benchmark.py               # MPS 推理性能基准评测 (实测 RTF 0.19)
│   └── tests/                     # 语音流水线自动化测试套件
│
├── tools/                         # 工具协议与注册网关（轻量 ToolRegistry，生态联动 chapter4 MCP）
├── docs/                          # 统一文档中心与理论知识库
│   ├── books/                     # 经典理论与电子书：《深入理解 AI Agent》全本、《智能体设计模式》中英版 (EPUB/PDF)
│   ├── design_patterns/           # 8 大设计模式原理与架构文档（对应 xindoo/agentic-design-patterns）
│   ├── architecture/              # Harness 架构通用白皮书、终端双雄对比与 C++/Go 工业级框架选型指南
│   └── multimodal/                # 音视频多模态与端侧全景指南 (AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
│
├── tests/                         # 自动化测试套件 (包含 765+ 单元与回归测试，全绿保证)
├── pyproject.toml                 # 模块化依赖定义
└── README.md                      # 本文档
```
---

## 📚 探索路径索引与参考

1. **理论基石与心智模型**：
   - 闯关实战清单：[`todolist.md`](todolist.md)（8 大阶段全流程打卡指南与文件索引）
   - 书籍索引中心：[`docs/books/README.md`](docs/books/README.md)（收录两部经典著作全本及速查清单）
   - 核心理论速查：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md)（掌握 12 大排雷归因地图与 $Pass^k$ 法则）
   - 模式电子书：中英双语 EPUB（[`agentic-design-patterns-cn.epub`](docs/books/agentic-design-patterns-cn.epub) / [`agentic-design-patterns-en.epub`](docs/books/agentic-design-patterns-en.epub)）
   - 企业落地实战指南：[`docs/books/AI-Agent-Application-Development-Guide.md`](docs/books/AI-Agent-Application-Development-Guide.md)（《AI Agent 开发实战：从基础原理到企业级应用》第 6~8 章核心工程化、多 Agent 框架选型与研报系统实战）
2. **经典模式工程**：
   - 模式总览：[`patterns/README.md`](patterns/README.md)（对应开源项目 [xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns)）
   - 查看 LangChain 8 大模式实现：[`patterns/langchain/ReadMe.md`](patterns/langchain/ReadMe.md)
   - 查看 AutoGen 0.4+ 模式与上手：[`patterns/autogen/ReadMe.md`](patterns/autogen/ReadMe.md)
3. **深入理解 AI Agent 全套 10 章配套实战 (109 个实验)**：详见 [实验库总览](experiments/README.md)
   - [第 1 章 · AI Agent 入门](experiments/chapter1/README.md)：上下文消融、多轮搜索与代码解释器
   - [第 2 章 · 上下文工程](experiments/chapter2/README.md)：KV Cache 命中率分析、提示注入攻防与上下文压缩
   - [第 3 章 · 用户记忆与知识库](experiments/chapter3/README.md)：Agentic-RAG、结构化知识图谱与混合召回
   - [第 4 章 · 工具工程](experiments/chapter4/README.md)：Model Context Protocol (MCP)、动态工具发现与人机协同审批
   - [第 5 章 · Coding Agent 与通用智能体](experiments/chapter5/README.md)：代码生成、执行沙箱安全审计与跨服务商热备切换
   - [第 6 章 · 观察与动作空间扩展](experiments/chapter6/README.md)：异步事件驱动架构、端到端实时语音与 GUI 自动化
   - [第 7 章 · Agent 的评估](experiments/chapter7/README.md)：多维指标度量、Elo 胜率天梯与成本收益分析
   - [第 8 章 · 模型后训练](experiments/chapter8/README.md)：思考链 (CoT) 蒸馏、SFT 样本数据审计与强化学习对齐
   - [第 9 章 · Agent 的持续进化](experiments/chapter9/README.md)：工具自进化、执行轨迹校验器与错误经验闭环
   - [第 10 章 · 多 Agent 协作](experiments/chapter10/README.md)：分布式多角色协作、长文档编排翻译与群体博弈
   - [22 个生产级 Agent Skills 库](experiments/skills/README.md)：支持 Claude Code 与各类 Coding Agent 的即用技能包
4. **垂直行业与代码智能体落地**：
   - 车载智能座舱 Agent：[`apps/cockpit_agent/ReadMe.md`](apps/cockpit_agent/ReadMe.md)
   - 生产级代码智能体实现：[`experiments/chapter5/coding-agent/`](experiments/chapter5/coding-agent/) 与技能底座 [`experiments/skills/coding-agent-harness/`](experiments/skills/coding-agent-harness/)
5. **端侧多模态与离线语音实践**：
   - 音视频与边缘节点手册：[`docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md`](docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
   - 本地实操套件：[`perception/labs/README.md`](perception/labs/README.md)
   - Mac Apple Silicon 脱网语音合成系统：[`mac_standalone_tts/README.md`](mac_standalone_tts/README.md)
6. **工业级 C++/Go 选型与生产落地**：
   - 原生微秒级 C++ Harness 底盘：[`core/native_cpp/`](core/native_cpp/)（零拷贝、熔断器、Token 预算控制）
   - 端云生产框架实战指南：[`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)（掌握 C++ 端侧运行时 `llama.cpp` / `MNN-LLM` 与 Go 云端微服务框架 `Eino` / `Genkit`）。
   - 终端智能体架构对比白皮书：[`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)（站在 Agent Harness 视角深度剖析 **OMP (Oh My Pi)** 与 **Claude Code**：垂直共生 vs 异构分工、Prewalk 阶梯调度、LSP 诊断与经济学选型）。
   - 端侧 Harness 设计（Android / iOS / Mac 开放助手）：[`docs/architecture/ON_DEVICE_HARNESS_DESIGN.md`](docs/architecture/ON_DEVICE_HARNESS_DESIGN.md)（系统模型 Foundation Models / Gemini Nano 与 LiteRT-LM 选型、端云路由、4096 上下文约束下的上下文装配、工具权限闸门与跨端共享规格）。
   - Harness 总体架构白皮书：[`docs/architecture/ai-agent-harness-architecture.md`](docs/architecture/ai-agent-harness-architecture.md)。
