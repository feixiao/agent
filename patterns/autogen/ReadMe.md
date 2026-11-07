### 智能体设计模式 (AutoGen 实现)

> 本实现对应开源项目 [xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns) 的 AutoGen 分支。配套电子书请参阅 [`docs/books/agentic-design-patterns-cn.epub`](../../docs/books/agentic-design-patterns-cn.epub)（[英文版](../../docs/books/agentic-design-patterns-en.epub)）。
#### 环境与依赖管理 (uv)
```shell
# 1. 同步安装 AutoGen 模式依赖
uv sync --extra patterns-autogen

# 2. 配置环境变量 (复制根目录模板)
cp ../../.env.example ../../.env

# 3. 使用 uv 运行示例
uv run python chap01.py
```

所有示例统一支持通过根目录 `.env` 或环境变量配置（无需区分提供商，只需地址与模型）：
- `LLM_BASE_URL`: 服务地址（如 LM Studio: `http://localhost:1234/v1`, Ollama: `http://localhost:11434/v1`）
- `LLM_MODEL`: 模型名称（如 `qwen3.8-27b-splash`）
- `LLM_API_KEY`: API Key（本地推理服务保持默认 `not-needed` 即可）

#### 例子说明与模式介绍

基于 Anthropic《Building effective agents》与业界落地实践，通过 AutoGen 0.4+ AgentChat 体系完整覆盖 8 大核心设计模式：

| 章节与文件 | 模式名称 | AutoGen 核心机制与场景说明 |
| :--- | :--- | :--- |
| **[`chap01.py`](chap01.py)** | **Prompt Chaining（提示链模式）** | **任务线性分解与链式流转**：将复杂任务拆解为两阶段管线，前一步的非结构化提取输出作为后一步的输入，精准转换为标准化 JSON。 |
| **[`chap02.py`](chap02.py)** | **Routing（路由模式）** | **意图识别与动态分流**：使用 `AssistantAgent` 充当决策路由器，分析用户输入语义（机票预订、知识问答等），动态委派给专门的子业务处理器。 |
| **[`chap03.py`](chap03.py)** | **Parallelization（并行化模式）** | **并发独立子任务 (Sectioning)**：针对指定主题同时并发调度 3 个独立 Agent（要点总结、问题挖掘、术语提取），最后由 Synthesizer 综合汇聚输出。 |
| **[`chap04.py`](chap04.py)** | **Reflection（反思模式）** | **生成者-评审者循环 (Generator-Critic)**：创建 Coder 与 Reviewer 双 Agent 闭环，对生成的代码进行多轮自我批评与边界用例校验，直到满足标准自动收敛。 |
| **[`chap05.py`](chap05.py)** | **Tool Calling（工具调用模式）** | **外部函数调用与端侧模型兼容**：采用轻量 ReAct 决策范式（决策 -> 本地 Python 工具执行 -> 汇总回答），即使端侧小模型缺少原生 Function Calling 也能稳健执行工具。 |
| **[`chap06.py`](chap06.py)** | **Planning（规划模式）** | **复杂目标分解与有序执行**：通过 `RoundRobinGroupChat` 编排规划师（Planner）与撰写人（Writer），先生成执行大纲要点再逐项展开，并利用终止条件关键词受控退出。 |
| **[`chap07.py`](chap07.py)** | **Multi-Agent Collaboration（多智能体协作）** | **异构角色协同与团队流水线**：结合群聊调度与终止条件（`TextMentionTermination`），组织研究分析师与科技撰稿人高效协作，完成端到端研究报告生成。 |
| **[`chap08.py`](chap08.py)** | **Memory Management（记忆管理模式）** | **用户偏好记忆池与上下文注入**：利用 AutoGen 的 `ListMemory` 持久化用户偏好（如度量单位、饮食习惯），在智能体执行任务时自动检索并注入上下文。 |
#### 快速上手实战
+ [AutoGen 核心组件快速上手 (AssistantAgent / Teams)](./quickstart/README.md)