# 实验 7-17：Harbor 容器化 Agent 评测与 ATIF 轨迹契约 (`laude-institute/harbor`)

本实验将 Terminal-Bench 团队开源的 [`laude-institute/harbor`](https://github.com/laude-institute/harbor)（Apache-2.0）引入第 7 章「Agent 的评估」，提供两条互补路径：

1. **轻量白盒路径（零外部依赖，立即可跑）**：通过 [`sample_task/`](sample_task/task.toml) 与 [`run_harbor_eval_demo.py`](run_harbor_eval_demo.py) 演示 Harbor 的三大核心工程契约：
   - **自包含任务包（Task Bundle）**：`instruction.md` + `task.toml` + `environment/Dockerfile` + `solution/solve.sh` + `tests/test.sh`（向 `/logs/verifier/reward.txt` 写入奖赏）；
   - **`ErrorPolicy` 与 `reward_valid` 聚合**：精确区分 Agent 自身原因（如 `AgentTimeoutError` → `reward_valid=True`，计为 `0` 分）与限流/容器启动故障（`ApiRateLimitError` / `EnvironmentStartTimeoutError` → `reward_valid=False`，**同时移出分子与分母**）；
   - **`ATIF-v1.8`（Agent Trajectory Interchange Format）**：标准 `trajectory.json` 结构校验，并直接桥接到 `evals.prefix_regression.locate_first_mistake`。
2. **官方完整 `harbor` 路径（Docker / Daytona / Modal 并发评测外部 CLI Agent）**：直接用 `harbor run` 评测 Claude Code、Codex CLI、OpenHands 等完整 Agent 产品。

← [返回第 7 章目录](../README.md) · 📖 [评测框架选型对比白皮书](../../../docs/architecture/EVAL_FRAMEWORKS_COMPARISON.md) · 🛠️ [评测底座 `evals/`](../../../evals/README.md)

---

## 一、 轻量白盒实战：校验 Harbor 任务包与错误策略

```bash
# 解析 sample_task/、审计四类 Trial 错误的 reward_valid 口径，并校验 ATIF-v1.8 轨迹
uv run python experiments/chapter7/harbor-eval/run_harbor_eval_demo.py --mock
```

重点观察输出中的 `aggregation`：
- 4 条 Trial 中：`trial-01-pass`（reward `1.0`, valid）、`trial-02-agent-timeout`（reward `0.0`, valid）、`trial-03-rate-limit`（`reward_valid=False`）、`trial-04-env-start-timeout`（`reward_valid=False`）。
- 最终 `mean_reward = (1.0 + 0.0) / 2 = 0.5`，限流与容器启动异常绝不污染模型均分或 RL rollout 数据。

---

## 二、 官方 `laude-institute/harbor` 安装与标准命令

### 1. 安装

```bash
uv tool install harbor
# 或
pip install harbor
```

### 2. 常用评估与任务开发命令速查

```bash
# 查看 Harbor 支持的第三方基准（如 Terminal-Bench 2.0、SWE-bench、Aider Polyglot 等）
harbor datasets list

# 本地 Docker 并发评测完整 Agent 产品（如 Claude Code）
export ANTHROPIC_API_KEY=<YOUR-KEY>
harbor run --dataset terminal-bench@2.0 \
  --agent claude-code \
  --model anthropic/claude-sonnet-5-5 \
  --n-concurrent 4

# 云端沙盒高并发评测（如 Daytona）
export DAYTONA_API_KEY=<YOUR-KEY>
harbor run --dataset terminal-bench@2.0 \
  --agent claude-code \
  --model anthropic/claude-sonnet-5-5 \
  --n-concurrent 100 \
  --env daytona

# 运行本实验自带的 sample_task（需本地 Docker）
harbor run --path experiments/chapter7/harbor-eval/sample_task \
  --agent oracle

# 校验 ATIF trajectory.json 格式合法性
uv run python -m harbor.utils.trajectory_validator path/to/trajectory.json
```

---

## 三、 工程检查清单

1. 涉及防作弊要求时，在 `task.toml` 的 `[verifier]` 中设置 `environment_mode = "separate"`，避免 Agent 修改测试脚本（reward hacking）。
2. 为生产/RL 收集数据时，只保留 `result.reward_valid == True` 的轨迹，并在 `JobConfig` 中按需配置 `override_error_policy`。
3. 所有自定义 Agent 仅在完整写出合规 `trajectory.json` 后再声明 `AgentCapabilities(atif=True)`。
