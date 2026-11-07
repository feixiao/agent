# AI Agent 开发指南与工程规范 (AGENT.md)

> 本文件是本仓库专用的 **AI Agent 开发与协作规范**。无论是人类开发者、Codex、Cursor、Claude 还是自动化 Agent 在本仓库进行开发、重构或新增模块时，均必须严格遵守本文件定义的架构心智模型与工程约束。

---

## 一、 核心心智模型与设计哲学

1. **Agent 核心公式**：
   $$\text{Agent} = \text{Model（概率模型引擎）} + \text{Harness（确定性工程底座与控制外围）}$$
   - 大模型负责概率决策与语义泛化；
   - Harness 负责上下文装配、格式校验、工具沙箱、状态机流转、死循环熔断与安全护栏。
2. **复合概率法则（Compounding Error）**：
   $$Pass^k = p^k$$
   - 单步成功率 $p=95\%$，连续执行 10 步端到端成功率仅剩 **59.8%**。
   - **商业级 Agent 的本质，就是用确定性的 Harness 工程对抗模型单步不确定性的复合放大。**
   - 衡量标准必须盯紧连续可靠性指标 $Pass^k$，而非单点演示的 $Pass@k$。

---

## 二、 仓库分层架构与目录规范

所有新增代码与文件必须按职责严格归入对应目录，**严禁向根目录随意添加孤立脚本或文档**：

```
agent/
├── docs/                      # 知识库与规范文档
│   ├── books/                 # 经典理论与电子书：《深入理解 AI Agent》全本、《智能体设计模式》中英版 (EPUB/PDF)
│   ├── design_patterns/       # 设计模式白皮书（对应 xindoo/agentic-design-patterns）
│   ├── architecture/          # Harness 架构白皮书与 C++/Go 工业级框架实战指南
│   └── multimodal/            # 音视频端侧指南 (AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)
│
├── core/                      # 【核心底座】Harness 运行时框架（自主可控，零外部大框架强依赖）
│   ├── context/               # 上下文工程：Prompt Cache 前缀对齐、Token 预算
│   ├── loop/                  # 运行时状态机、步数计数器、死循环熔断器
│   ├── memory/                # 短期工作记忆与长期检索管理
│   ├── planning/              # DAG 任务分解与动态重规划
│   ├── reflection/            # 校验器、Self-Correction 与 Critic 反思
│   └── sandbox/               # 工具执行沙箱与幂等控制器
│
├── tools/                     # 工具协议与注册网关
│   ├── builtin/               # 内置核心工具
│   └── mcp_servers/           # Model Context Protocol (MCP) 服务实现
│
├── patterns/                  # 【模式工程实战】源自 xindoo/agentic-design-patterns 的多框架对照实现
│   ├── langchain/             # LangChain 实现版本
│   └── autogen/               # AutoGen 0.4+ 实现版本及 quickstart/
├── apps/                      # 垂直场景端到端工程落地
│   ├── cockpit_agent/         # 智能座舱 Agent（MasterAgent + 垂类 Sub-Agents）
│   ├── coding_agent/          # 代码智能体
│   └── multimodal_edge/       # 端侧智能巡检
│
├── perception/                # 感知与边缘算力层
│   ├── edge_platforms/        # Mac Studio / Android Pixel 10 / Jetson 硬件规范
│   └── labs/                  # VLM / Whisper / LoRA 多模态实践套件
│
├── evals/                     # 评测与数据飞轮
│   ├── benchmarks/            # 评测基准用例
│   ├── metrics/               # 指标计算（Pass^k、首错率）
│   └── prefix_regression/     # 轨迹前缀回归定位器
│
└── tests/                     # 单元测试与集成测试
    └── unit/                  # 单元测试（保持零第三方依赖高频可运行）
```

---

## 三、 Agent 开发六大硬性工程准则

在本仓库编写或重构 Agent 代码时，必须落实以下 6 项防坑机制：

### 1. 上下文工程准则 (Context Engineering)
- **前缀字节绝对静止**：System Prompt、Role 描述与基础工具 Schema 必须放在最前缀，严禁在开头插入时间戳、动态计数等易变字段，确保底层 KV Cache 最大化命中。
- **动态状态后置注入**：动态变量（如 `<status_bar>` 状态栏、当前重试轮次）必须追加在最新一轮用户消息尾部。
- **Token 预算裁剪**：必须为生成内容预留足够的 Output Tokens，超出上下文滑动窗口时采用渐进式摘要或代词保留剪枝。

### 2. 状态机与防死循环准则 (Loop & Circuit Breaker)
- **显式状态机**：Agent 必须具备明确的生命周期状态（`IDLE` $\rightarrow$ `PLANNING` $\rightarrow$ `EXECUTING` $\rightarrow$ `REFLECTING` $\rightarrow$ `COMPLETED`/`FAILED`）。
- **硬熔断与步数限制**：单任务必须设死最大执行步数（默认 30 步）；连续遭遇 3 次错误必须熔断；连续 2 次发起完全相同参数的调用必须立刻判定死循环熔断并降级。

### 3. 工具交互与幂等性准则 (Tools & Idempotency)
- **渐进式披露 (Progressive Disclosure)**：避免将全量深层工具 Schema 一次性塞入 Context。遵循 L0（紧凑列表） $\rightarrow$ L1（详细参数 Schema） $\rightarrow$ L2（示例与反例边界）三级按需暴露机制。
- **写操作幂等键**：涉及转账、发信、车控物理动作、文件原位修改等有外部副作用的工具，客户端必须强制注入 `idempotency_key`，防止网络抖动或模型幻觉重复执行。

### 4. 记忆治理准则 (Memory Governance)
- **禁止在线直写长期记忆**：会话过程中产生的信息仅写入 `WorkingMemory`；
- 长期记忆必须通过候选提议（Proposal）$\rightarrow$ 离线清洗/冲突仲裁 $\rightarrow$ 审核合并的治理闭环，防止提示词注入篡改或闲聊污染画像。

### 5. 代码与文件编辑准则 (Coding Agent)
- **禁止依赖盲目行号定位**：严禁仅靠行号进行替换（容易发生行号漂移 Line Drift）；
- **原位特征定位**：采用基于上下文锚点（Search-and-Replace）、AST 语法分析或 Hashline 机制进行精确原位更新。

### 6. 评测与故障归因准则 (Evals & Debugging)
- **首错定位 (First Mistake Identification)**：排查长长轨迹的 Agent 故障时，严禁仅看末端报错（如数据库连接超时）；必须使用前缀回归（Prefix Regression）截断排查，锁定首次偏离正确意图的关键步。

---
### 7. 端云多技术栈分工准则 (Multi-Language Engineering Stack)
- **端云分水岭**：
  - **端侧/车载/机器人 (C++ / Rust)**：以 `llama.cpp`、`MNN-LLM`、`TensorRT-LLM` 为主流底座，强制使用 GBNF 语法树约束输出，杜绝 Python 依赖与 GC 停顿；
  - **云端高并发微服务 (Go)**：以 `cloudwego/eino`、`Genkit (Go)` 为主流调度编排底座，支撑百万并发与全链路 Tracing；
  - **原型与算法基线 (Python)**：本仓库 `core/` 充当跨端状态机与排雷逻辑的 Reference Implementation，保持零第三方依赖以便 1:1 直译或绑定。
  - 详细框架选型与落地参考：[`docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md`](docs/architecture/AGENT_FRAMEWORKS_CPP_GO.md)；
  - 终端智能体 (CLI Coding Agent) 对比白皮书：[`docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md`](docs/architecture/OMP_VS_CLAUDE_CODE_COMPARISON.md)（深度解析 OMP 与 Claude Code 在上下文工程、Prewalk 阶梯模型编排与 Harness 控制底座的设计哲学）。


## 四、 常用开发与测试指令 (uv 管理)

工程使用 `uv` 统一管理 Python 环境、虚拟环境与依赖版本：

### 1. 运行核心底座单元测试
测试用例保持轻量无外部大包依赖，修改 `core/` 或 `tools/` 后必须立即执行：
```bash
uv run python -m unittest discover tests
```

### 2. 运行多模态与感知层套件
针对 Mac Studio / 本地环境的多模态实验：
```bash
cd perception/labs
bash run_all_labs.sh
```

### 3. 运行设计模式示例
模式依赖与统一环境变量均通过 `uv` 管理：
```bash
# 安装设计模式依赖（可包含 langchain 与 autogen）
uv sync --extra patterns

# 运行 LangChain 模式示例
uv run python patterns/langchain/chap01.py

# 运行 AutoGen 模式示例
uv run python patterns/autogen/chap01.py
```
---

## 五、 代码贡献与变更检查清单 (Checklist)

在提交任何 Pull Request 或完成代码生成任务前，逐项检查：

- [ ] 新建文件放置于符合分层架构的目录中，未在根目录新增无关文件。
- [ ] 代码具备完整的 Type Hints 与清晰的 Docstring。
- [ ] 涉及循环与工具调用处接入了 `core.loop.CircuitBreaker` 或步数保护。
- [ ] 关键外部修改工具实现了唯一幂等键或状态核验。
- [ ] 对应模块在 `tests/unit/` 中编写或补充了单元测试。
- [ ] 执行 `python3 -m unittest discover tests` 全部通过。
- [ ] 更新了相关的 `README.md` 引用或说明文档。
