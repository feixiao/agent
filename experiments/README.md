# 《深入理解 AI Agent》全书 10 章配套实验库 (Experiments)

本目录收录了《深入理解 AI Agent：设计原理与工程实践》全书 10 章共 **109 个工业级配套实战实验**、**共享 Provider 基础设施 (`agentbook/`)** 以及 **22 个生产级 Agent 技能包 (`skills/`)**。全部代码采用纯 Python 编写，开箱即用。

---

## 📑 章节实验全景

| 章节 | 主题 | 核心实验与工程亮点 | 快速入口 |
| :--: | :--- | :--- | :--: |
| **01** | 🚀 **AI Agent 入门** | 5 组上下文关键作用消融实验、多轮搜索与代码执行闭环、离线经验自学习 | [`chapter1/`](chapter1/README.md) |
| **02** | 🎯 **上下文工程** | GPU KV Cache 命中率分析、提示词注入与结构化防御、上下文压缩、注意力可视化 | [`chapter2/`](chapter2/README.md) |
| **03** | 📚 **用户记忆与知识库** | Agentic-RAG、BM25 稀疏检索与向量密集检索、长期画像演进、知识图谱与结构化索引 | [`chapter3/`](chapter3/README.md) |
| **04** | 🛠️ **工具工程** | Model Context Protocol (MCP) 协议实战、海量工具动态发现与语义路由、人机协同审批 | [`chapter4/`](chapter4/README.md) |
| **05** | 💻 **Coding Agent 与通用智能体** | 代码生成与 AST 原位替换、安全执行沙箱风控审计、跨模型服务商热备容灾切换 | [`chapter5/`](chapter5/README.md) |
| **06** | 🎙️ **交互：观察与动作空间扩展** | 异步事件流驱动 Agent、端到端实时语音交互流 (TTS/STT)、Computer Use (GUI 自动化) | [`chapter6/`](chapter6/README.md) |
| **07** | 🎯 **Agent 的评估** | Tau-Bench 对齐评测、Elo 胜率天梯系统、Token 成本收益分析、统计显著性校验 | [`chapter7/`](chapter7/README.md) |
| **08** | 🧠 **模型后训练** | 思考链 (CoT) 蒸馏、SFT 训练数据质量审计、强化学习 (RL) 奖励函数与协议固化 | [`chapter8/`](chapter8/README.md) |
| **09** | 🔄 **Agent 的持续进化** | 工具自进化闭环、多步执行轨迹校验器、故障规避机制与经验反思注入 | [`chapter9/`](chapter9/README.md) |
| **10** | 🤝 **多 Agent 协作** | 分布式多角色长文档协作翻译、狼人杀博弈社会模拟、群体组织拓扑治理 | [`chapter10/`](chapter10/README.md) |

---

## 🛠️ 核心共享基础设施 (`agentbook/`)

位于 [`agentbook/`](agentbook/)，为所有章节实验提供统一的底层模型适配能力：
- **统一 OpenAI 协议支持**：兼容所有标准 OpenAI 格式接口（本地 LM Studio、Ollama、vLLM、各云端 API）。
- **国内/海外大厂一站式路由**：统一管理 Moonshot/Kimi、字节火山方舟 Ark、阿里百炼 DashScope、深度求索 DeepSeek、智谱 GLM、SiliconFlow、Krill AI、Atlas Cloud、OpenRouter 等厂商的基础端点与默认模型。
- **免 Key / 零成本方案**：支持 `--provider ollama`（本地运行）与 OpenRouter 免费模型快速验证。

---

## ⚡ 快速上手与运行

使用 `uv` 按章节安装运行：

```bash
# 1. 复制并配置环境变量
cp .env.example .env

# 2. 安装指定章节依赖（以第 1 章为例，可替换为 ch2 ~ ch10）
uv sync --extra ch1

# 3. 运行第一章实验（上下文消融实验）
uv run python experiments/chapter1/context/main.py --help
```

---

## 🧰 22 个生产级 Agent Skills (`skills/`)

位于 [`skills/`](skills/README.md)，将全书 10 章方法论蒸馏为 22 个开箱即用的开发技能包，可直接被 Claude Code、Cursor、Windsurf 等开发助手按需检索与加载。
