# 智能体设计模式实现 (Agentic Design Patterns)

> 本目录下的设计模式代码实现对应开源项目：**[xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns)**。  
> 离线电子书阅读：中英双语 EPUB 版位于 [`docs/books/agentic-design-patterns-cn.epub`](../docs/books/agentic-design-patterns-cn.epub) 与 [`docs/books/agentic-design-patterns-en.epub`](../docs/books/agentic-design-patterns-en.epub)。  
> 深入理论、底层 Harness 与排雷地图请参阅：[`docs/books/AI-Agents-in-Depth-QuickStart.md`](../docs/books/AI-Agents-in-Depth-QuickStart.md)。

---

## 模式清单与对应关系

基于 Anthropic《Building effective agents》与行业实践，覆盖 8 大核心设计模式：

| 章节 | 模式名称 (Pattern) | 核心机制与场景 | LangChain 实现 | AutoGen 实现 |
| :--- | :--- | :--- | :--- | :--- |
| **chap01** | **Prompt Chaining（提示链模式）** | 任务线性分解，前一步输出作为下一步输入 | [`langchain/chap01.py`](langchain/chap01.py) | [`autogen/chap01.py`](autogen/chap01.py) |
| **chap02** | **Routing（路由模式）** | 根据用户意图/输入特征动态分流到专门的处理分支 | [`langchain/chap02.py`](langchain/chap02.py) | [`autogen/chap02.py`](autogen/chap02.py) |
| **chap03** | **Parallelization（并行化模式）** | Sectioning（并行独立子任务）或 Voting（多样本投票） | [`langchain/chap03.py`](langchain/chap03.py) | [`autogen/chap03.py`](autogen/chap03.py) |
| **chap04** | **Reflection（反思模式）** | 生成者-评估者循环，通过自我批评与多轮迭代提升质量 | [`langchain/chap04.py`](langchain/chap04.py) | [`autogen/chap04.py`](autogen/chap04.py) |
| **chap05** | **Tool Calling（工具调用模式）** | 借助函数调用/外部 API 扩展 Agent 手脚（含本地模型兼容） | [`langchain/chap05.py`](langchain/chap05.py) | [`autogen/chap05.py`](autogen/chap05.py) |
| **chap06** | **Planning（规划模式）** | 复杂目标分解、动态执行步排序与基于反馈的重规划 | [`langchain/chap06.py`](langchain/chap06.py) | [`autogen/chap06.py`](autogen/chap06.py) |
| **chap07** | **Multi-Agent Collaboration（多智能体协作）** | 多角色分工、群聊协调与复杂流水线协作 | [`langchain/chap07.py`](langchain/chap07.py) | [`autogen/chap07.py`](autogen/chap07.py) |
| **chap08** | **Memory Management（记忆管理模式）** | 短期会话缓冲、长期个性化记忆池与检索注入 | [`langchain/chap08_01.py`](langchain/chap08_01.py) | [`autogen/chap08.py`](autogen/chap08.py) |

---

## 目录结构

- **`langchain/`**：基于 LangChain 0.2+ 的 8 大设计模式 Python 实现及 requirements 依赖。
- **`autogen/`**：基于 AutoGen 的 8 大设计模式实现；`quickstart/` 提供 AutoGen 0.4+ AgentChat 与 Teams 快速上手用例。
