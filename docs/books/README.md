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
