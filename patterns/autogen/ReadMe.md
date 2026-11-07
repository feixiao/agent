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

#### 例子说明
+ chap01 	提示链模式
+ chap02    路由模式
+ chap03	并行化模式
+ chap04    反思模式
+ chap05    工具模式
+ chap06	规划模式
+ chap07	多智能体协作模式
+ chap08	内存管理

#### 快速上手实战
+ [AutoGen 核心组件快速上手 (AssistantAgent / Teams)](./quickstart/README.md)