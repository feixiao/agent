# 深入 AI Agent 开发体系 (Agent in Depth)

> 核心公式：$$\text{Agent} = \text{Model（概率模型引擎）} + \text{Harness（确定性工程底盘）}$$
> 
> 商业级 Agent 的本质，是用确定性的 Harness 工程对抗模型单步不确定性的复合放大（$Pass^k = p^k$）。本项目聚焦从理论原理、外围底盘设计、经典协同模式，到多模态端侧感知与垂直行业（智能座舱、代码生成）的完整深入落地。

---

## 目录全景导航
├── docs/                          # 统一文档中心与理论知识库
│   ├── books/                     # 经典理论：《深入理解 AI Agent》全本与速查指南
│   ├── design_patterns/           # 8 大设计模式原理与架构白皮书
│   ├── architecture/              # Harness 架构通用白皮书 (ai-agent-harness-architecture.md)
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
├── patterns/                      # 【模式工程实战】8 大经典 Agent 设计模式对照实现
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

## 快速上手

### 1. 环境准备
```bash
# 基础运行时
pip install -e .

# 安装特定能力扩展
pip install -e ".[patterns-langchain]"   # 安装 LangChain 模式依赖
pip install -e ".[patterns-autogen]"     # 安装 AutoGen 模式依赖
pip install -e ".[evals]"                # 安装评测套件
```

### 2. 探索路径建议

1. **理论与心智模型**：
   - 必读：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](docs/books/AI-Agents-in-Depth-QuickStart.md)（掌握 12 大排雷归因地图与 $Pass^k$ 法则）。
2. **经典模式工程**：
   - 查看 LangChain 8 大模式：[`patterns/langchain/ReadMe.md`](patterns/langchain/ReadMe.md)
   - 查看 AutoGen 0.4+ 模式与上手：[`patterns/autogen/ReadMe.md`](patterns/autogen/ReadMe.md)
3. **垂直行业架构**：
   - 车载智能座舱 Agent：[`apps/cockpit_agent/ReadMe.md`](apps/cockpit_agent/ReadMe.md)
4. **端侧多模态实践**：
   - 音视频与边缘节点手册：[`docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md`](docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
   - 本地实操套件：[`perception/labs/README.md`](perception/labs/README.md)
