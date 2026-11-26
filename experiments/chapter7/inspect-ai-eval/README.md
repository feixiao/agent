# 实验 7-16：Inspect AI 可编程沙盒评估实战 (`UKGovernmentBEIS/inspect_ai`)

本实验将英国 AI 安全研究所（UK AISI）与 Meridian Labs 开源的 [`UKGovernmentBEIS/inspect_ai`](https://github.com/UKGovernmentBEIS/inspect_ai)（MIT）引入第 7 章「Agent 的评估」，提供两条互补路径：

1. **轻量白盒路径（零外部依赖，立即可跑）**：通过 [`run_inspect_eval_demo.py`](run_inspect_eval_demo.py) 演示 Inspect AI 的三大核心工程机制：
   - **`Task(dataset, solver, scorer, sandbox)` 组合式解耦**：同一套任务与评分器可无缝切换不同 `react_solver` / 模型；
   - **Expected vs. Unexpected 沙盒错误边界**：工具报错（`ExpectedToolError`）回灌给模型促使其自愈重试；基础设施异常（`UnexpectedSandboxError`）直接把样本标为 `error` 并在 `SuiteOutcome` 中触发 `infra_required=True`（`score=None`），绝不压低模型真实分数；
   - **`EvalLog` → `FirstMistake` 归因闭环**：失败轨迹直接桥接到 `evals.prefix_regression.locate_first_mistake`。
2. **官方完整 `inspect_ai` 路径（对接 Docker/K8s 沙盒、200+ 基准与 `sandbox_agent_bridge`）**：直接运行官方 `inspect eval` 与 `inspect view` Web UI。

← [返回第 7 章目录](../README.md) · 📖 [评测框架选型对比白皮书](../../../docs/architecture/EVAL_FRAMEWORKS_COMPARISON.md) · 🛠️ [评测底座 `evals/`](../../../evals/README.md)

---

## 一、 轻量白盒实战：运行 `run_inspect_eval_demo.py`

### 1. 离线演练三种典型沙盒场景（无需 API Key / Docker）

```bash
# 运行全部 mock 场景：工具报错自愈 vs 模型误读归因 vs 沙盒基建故障隔离
uv run python experiments/chapter7/inspect-ai-eval/run_inspect_eval_demo.py --mock

# 单独演练某一种场景（healthy_recovery | model_mistake | sandbox_infra_error）
uv run python experiments/chapter7/inspect-ai-eval/run_inspect_eval_demo.py --mock --scenario healthy_recovery
```

重点观察输出中的三类信号：
- `healthy_recovery`：Turn 1 触发 `ExpectedToolError`（文件不存在）→ Turn 2 模型根据报错改读 `secret_flag.txt` 并通过（`status="passed"`）；
- `model_mistake`：`first_mistake_attribution` 精准锁定 `fault_layer="model_reasoning"` 的首次错误步骤；
- `sandbox_infra_error`：`eval_log.summary.errors=1`、`suite_outcome.infra_required=true`、`suite_outcome.score=null`。

### 2. 对接真实 OpenAI 兼容 `/v1` 端点

```bash
uv run python experiments/chapter7/inspect-ai-eval/run_inspect_eval_demo.py \
  --endpoint http://127.0.0.1:11434/v1 \
  --model qwen2.5:7b
```

---

## 二、 官方 `UKGovernmentBEIS/inspect_ai` 安装与标准命令

### 1. 安装

```bash
# 安装核心框架与常用社区基准包
pip install inspect-ai inspect-evals

# 可选：评估外部 CLI Agent（如 Claude Code / Codex CLI）或 Harbor 移植套件
pip install inspect-swe inspect-harbor
```

### 2. 常用评估命令速查

```bash
# Step 1: 运行单个自定义 Python Task 文件（默认读取同目录 Dockerfile / compose.yaml）
inspect eval my_ctf_task.py --model openai/gpt-4.1-mini --sandbox docker

# Step 2: 接入本地 vLLM / Ollama（OpenAI 兼容服务）
inspect eval inspect_evals/gaia --model vllm/Qwen/Qwen2.5-7B-Instruct --limit 10

# Step 3: 启动可视化 Transcript 与沙盒事件流查看器
inspect view
```

### 3. 桥接已有 Agent（`agent_bridge` 与 `sandbox_agent_bridge`）

当待测对象本身是一套完整 Agent（如 LangChain / OpenAI Agents SDK / Claude Code）时，无需重写其内部逻辑，只需在 `@agent` 中包一层上下文管理器拦截 `/v1` 请求：

```python
from inspect_ai.agent import Agent, AgentState, agent, sandbox_agent_bridge

@agent
def cli_coding_agent() -> Agent:
    async def execute(state: AgentState) -> AgentState:
        async with sandbox_agent_bridge(state) as bridge:
            # 容器内 CLI Agent 把 base_url 指向 bridge 暴露的代理地址即可
            ...
            return bridge.state
    return execute
```

---

## 三、 工程检查清单

1. 自定义工具必须区分 `ToolError`（模型可恢复）与未知基础设施异常（触发样本 `error` 状态）。
2. 使用 `agent_bridge()` 时，仅用于可信模型或沙盒隔离环境；多模型分层调用需配置 `model_aliases`，切勿将 `grader`/`monitor` 角色暴露给被测 Agent。
3. 评测完成后用 `inspect view` 抽检失败轨迹，区分提示/工具契约缺陷与模型推理缺陷。
