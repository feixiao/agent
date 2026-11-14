# 经典理论与电子书知识库 (Docs / Books)

本目录汇总了本项目核心理论依托的经典著作、电子书资源及快速导读，为底层 Harness 架构设计与 8 大经典设计模式提供理论与心智模型支撑。

---

## 收录书籍与资源清单

### 1. 《Agentic Design Patterns 智能体设计模式》
对应开源项目 **[xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns)**，系统性总结了构建高可靠 Agent 的 8 大核心设计模式（提示链、路由、并行化、反思、工具调用、规划、多智能体协同、记忆管理）。

* **中文版电子书**：[`agentic-design-patterns-cn.epub`](agentic-design-patterns-cn.epub)
* **英文版电子书**：[`agentic-design-patterns-en.epub`](agentic-design-patterns-en.epub)
* **配套实战代码**：
  * [8 大模式总览与对照清单](../../patterns/README.md)
  * [LangChain 实现目录](../../patterns/langchain/ReadMe.md)
  * [AutoGen 0.4+ 实现目录](../../patterns/autogen/ReadMe.md)
* **设计模式白皮书**：[`docs/design_patterns/README.md`](../design_patterns/README.md)

---

### 2. 《深入理解 AI Agent》(AI Agents in Depth) — 李博杰
系统阐述 Agent 的本质、心智模型、外围底座（Harness）以及工业级排雷归因。

* **PDF 全本 (中文)**：[`AI-Agents-in-Depth-zh-CN.pdf`](AI-Agents-in-Depth-zh-CN.pdf)
* **EPUB 电子书 (中文)**：[`AI-Agents-in-Depth-zh-CN.epub`](AI-Agents-in-Depth-zh-CN.epub)
* **核心速查与排雷指南**：[`AI-Agents-in-Depth-QuickStart.md`](AI-Agents-in-Depth-QuickStart.md)
  * 涵盖核心公式 $\text{Agent} = \text{Model} + \text{Harness}$ 与复合概率法则 $Pass^k = p^k$
  * 工业级 12 大排雷归因地图（上下文膨胀、死循环、工具幻觉、并发竞争等）
* **全书 10 章配套实战代码 (109 个实验)**：详见 [实验库总览](../../experiments/README.md)
  * [第 1 章 · AI Agent 入门](../../experiments/chapter1/README.md)
  * [第 2 章 · 上下文工程](../../experiments/chapter2/README.md)
  * [第 3 章 · 用户记忆和知识库](../../experiments/chapter3/README.md)
  * [第 4 章 · 工具](../../experiments/chapter4/README.md)
  * [第 5 章 · Coding Agent 与通用 Agent](../../experiments/chapter5/README.md)
  * [第 6 章 · 交互：观察与动作空间的扩展](../../experiments/chapter6/README.md)
  * [第 7 章 · Agent 的评估](../../experiments/chapter7/README.md)
  * [第 8 章 · 模型后训练](../../experiments/chapter8/README.md)
  * [第 9 章 · Agent 的持续进化](../../experiments/chapter9/README.md)
  * [第 10 章 · 多 Agent 协作](../../experiments/chapter10/README.md)
* **核心共享 Provider 基础设施**：[`experiments/agentbook/`](../../experiments/agentbook/)（统一模型路由、厂商密钥与后端适配）
* **22 个实战 Agent 技能包**：[`experiments/skills/`](../../experiments/skills/README.md)（涵盖上下文工程、KV-Cache、记忆系统、工具设计、评测与自进化闭环）

---

### 3. 《AI Agent 开发实战：从基础原理到企业级应用》 — 郑天民
聚焦企业级应用落地的技术体系，涵盖私有化运行时（Ollama）、链路追踪（LangSmith / Phoenix）、Streamlit 前后端流式交互、Web API 标准服务化（Flask / LangServe）、混合数据持久化（PostgreSQL / pgvector），以及三大主流多 Agent 框架（LlamaIndex Workflows、AutoGen、LangGraph）的架构设计与端到端实战研报系统。

* **企业应用篇核心指南**：[`../../AI-Agent-Application-Development-Guide.md`](../../AI-Agent-Application-Development-Guide.md)
  * 深度提炼第 6~8 章企业应用篇精髓（工程化底座、事件/会话/状态图三大多 Agent 范式、Supervisor 研报落地）
  * 提供三大框架（LlamaIndex vs AutoGen vs LangGraph）架构选型矩阵与生产落地五大铁律
* **官方开源仓库**：[tianminzheng/agent-application-development](https://github.com/tianminzheng/agent-application-development)
---

## 阅读建议

```text
[入门心智模型]
  └─► 阅读 AI-Agents-in-Depth-QuickStart.md 掌握 Harness 哲学与排雷法则
       │
       ├─► [设计模式理论]
       │     └─► 阅读 agentic-design-patterns-cn.epub (或 en.epub)
       │           └─► 运行并对照 patterns/langchain/ 与 patterns/autogen/ 代码
       │
       └─► [系统底座进阶]
             └─► 结合 docs/architecture/ai-agent-harness-architecture.md
                   └─► 深入 core/ (loop, context, memory, reflection, sandbox) 源码
```
