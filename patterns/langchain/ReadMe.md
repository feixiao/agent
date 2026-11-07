### 智能体设计模式 (LangChain 实现)

> 本实现对应开源项目 [xindoo/agentic-design-patterns](https://github.com/xindoo/agentic-design-patterns) 的 LangChain 分支。配套电子书请参阅 [`docs/books/agentic-design-patterns-cn.epub`](../../docs/books/agentic-design-patterns-cn.epub)（[英文版](../../docs/books/agentic-design-patterns-en.epub)）。
#### 环境与依赖管理 (uv)
```shell
# 1. 同步安装 LangChain 模式依赖
uv sync --extra patterns-langchain

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

基于 LangChain 0.2+ / LangGraph / CrewAI 覆盖的 8 大核心设计模式实现：

| 章节与文件 | 模式名称 | LangChain 核心机制与场景说明 |
| :--- | :--- | :--- |
| **[`chap01.py`](chap01.py)** | **Prompt Chaining（提示链模式）** | **LCEL 链式组合**：利用 LangChain 表达式语言（LCEL `|` 管道操作符）将提取链与格式化转换链串联成单一可运行单元。 |
| **[`chap02.py`](chap02.py)** | **Routing（路由模式）** | **RunnableBranch 条件分流**：使用 `RunnableBranch` 根据分类模型的输出条件动态路由到预订处理、问答检索或未明兜底链路。 |
| **[`chap03.py`](chap03.py)** | **Parallelization（并行化模式）** | **RunnableParallel 并发编排**：利用 `RunnableParallel` 并行执行摘要提炼、问题生成与术语抽取三路独立子任务，大幅压低整体时延。 |
| **[`chap04.py`](chap04.py)** | **Reflection（反思模式）** | **反思与自我纠错循环**：构建生成者-评估者循环，通过多次自我评估生成代码的阶乘逻辑与异常处理，并完成自我修正。 |
| **[`chap05.py`](chap05.py)** | **Tool Calling（工具调用模式）** | **轻量工具扩展与模型兼容**：面向端侧模型实现“轻量 ReAct 决策 -> 本地 `@tool` 执行 -> 汇总回答”，无需强依赖模型原生函数调用。 |
| **[`chap06.py`](chap06.py)** | **Planning（规划模式）** | **CrewAI 规划与撰写流水线**：利用 CrewAI 编排文章规划师（Planner）与撰写人，先制定要点规划再展开为结构化摘要。 |
| **[`chap07.py`](chap07.py)** | **Multi-Agent Collaboration（多智能体协作）** | **专业角色分工与交接**：通过 CrewAI 组织高级研究分析师与科技内容撰写人顺序交接协作，产出多维度 AI 行业洞察报告。 |
| **[`chap08_01.py`](chap08_01.py)**<br>**[`chap08_02.py`](chap08_02.py)** | **Memory Management（记忆管理模式）** | **短期对话缓冲与语义检索**：`chap08_01` 演示基于 Session ID 的对话上下文滚动缓冲；`chap08_02` 演示基于 LangGraph Store 的向量语义记忆检索与持久化。 |
## 关于 chap05.py：在“不支持 Tools”的模型上实现工具增强

某些本地模型（例如 `registry.ollama.ai/library/deepseek-r1:14b`）当前不支持原生的 function/tool calling。
为兼容此类模型，`chap05.py` 采用了“轻量 ReAct 决策 -> 可选调用 Python 工具 -> 汇总回答”的流程，无需模型原生工具能力也能实现“带工具”的效果。

### 思路概览
- 决策链：让 LLM 只输出一个 JSON，包含 `decision`（`use_tool` 或 `answer`）与 `tool_input`（若用工具则给出英文查询）。
- 工具：使用 LangChain 的 `@tool` 装饰器定义本地 Python 工具（示例为 `search_information`）。
- 汇总链：结合工具结果与原问题，生成最终回答。

该流程的优点是“通用、可移植”，即使模型不支持 tools，也可通过普通对话能力完成“要不要用工具”的判断与调用。

### 运行
```bash
python chap05.py
```

你应能看到三条并发查询的输出：
- “伦敦天气怎么样？”与“法国的首都是什么？”会触发工具（或兜底）并给出答案；
- “告诉我一些关于狗的事情。”则直接由模型作答。

### 依赖说明
- 本目录的 `requirements.txt` 已包含所需依赖（`langchain`, `langchain-core`, `langchain-ollama`, `nest_asyncio` 等）。
- 你可以通过环境变量 `LLM_MODEL` 指定模型名称；默认使用 `deepseek-r1:14b`（Ollama）。

### 与原生 Agents 的区别
- 原生 Agents（如 `create_tool_calling_agent`、`AgentExecutor`、`initialize_agent`）依赖模型的函数/工具调用能力或特定版本的库结构。
- `chap05.py` 不再依赖这些接口，避免了版本差异与工具能力缺失带来的报错。

### 常见问题与排查
1) NameError/ImportError（如 `create_tool_calling_agent` 未定义或不可导入）
	- 说明：依赖的 Agents API 或版本不一致；`chap05.py` 已移除这些强依赖。
2) `StructuredTool object is not callable`
	- 解决：使用 `tool.invoke({"query": ...})` 或回退 `tool.run(...)`。
3) INVALID_PROMPT_INPUT（花括号被当作变量）
	- 解决：在 `ChatPromptTemplate` 中对示例 JSON 使用双花括号转义，如 `{{"decision": ...}}`。

### 如何切换到“支持 Tools”的模型
- 若切换到支持工具调用的模型（如部分 OpenAI 模型），可以改回原生 Agents 流程（`create_tool_calling_agent`/`initialize_agent` 等）。
- 但推荐先验证当前库版本的导入路径与 API 是否匹配，避免再次出现导入错误。


