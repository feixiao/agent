# Agent 评测与数据飞轮底座 (`evals/`)

> **定位**：补齐 `README.md` 与 `AGENT.md` 规划的顶层 `evals/` 评测底座，融合 [`google-deepmind/gbench`](https://github.com/google-deepmind/gbench)、[`UKGovernmentBEIS/inspect_ai`](https://github.com/UKGovernmentBEIS/inspect_ai) 与 [`laude-institute/harbor`](https://github.com/laude-institute/harbor) 的核心工程设计并保持**零第三方重依赖（纯 Python 标准库）**，与 `core/` Harness 运行时及 `experiments/chapter7/` 配套实验形成闭环。

---

## 目录结构

```text
evals/
├── scaffold.py                 # Subject vs Scaffold 双轴版本锁定与可比性仲裁
├── frameworks/
│   ├── inspect_ai.py           # Inspect AI Task/Solver/Scorer/Sandbox 与 Expected vs Unexpected 错误隔离
│   └── harbor.py               # Harbor task.toml 检查、ErrorPolicy/reward_valid 聚合与 ATIF-v1.8 校验
├── benchmarks/
│   └── golden_set.py           # 确定性 Golden Set 冒烟集 + Chat Template 成对诊断 + /v1 端点接入
├── metrics/
│   ├── reliability.py          # Pass^k / Pass@k / Cache 命中率 / infra_required 诚实上报
│   └── statistics.py           # compute_statistics / tail_validity / iid & block bootstrap CI
└── prefix_regression/
    └── locator.py              # 多步轨迹 First Mistake 二分/线性定位与前缀回归用例冻结
```

---

## 四大核心能力（对齐 `gbench` 与 `AGENT.md`）

1. **Subject vs Scaffold 双轴版本锁定 (`evals.scaffold`)**
   - 将受测对象（`SubjectSpec`：`model_checkpoint`、`quantization`）与评测脚手架（`ScaffoldSpec`：`prompt_version`、`schema_version`、`scoring_version`、`tool_permissions`、`attempts`、`decode`、`dataset_snapshot`、`serving_environment`、`load_shape`）拆分为两条独立哈希轴。
   - 显式输出 `covers` 与 `unpinned` 字段，绝不虚标覆盖率；`compare_conditions()` 自动判定两组实验是有效模型对比（`valid_subject_delta`）、需断轴拆分的脚手架变更（`scaffold_changed_break_series`），还是不可解释混杂变更（`both_changed_uninterpretable`）。

2. **确定性 Golden Set 与模板成对隔离 (`evals.benchmarks.golden_set`)**
   - 严格区分四类互不混淆的结果：`passed`、`failed`、`error`（端点/Harness 故障绝不算作模型退化）、`not_applicable`（缺失模态自动移出分母）。
   - 支持双边断言（`expected_outputs` + `expected_not_contains` + `forbid_chat_template_tokens`）、隔离 `python_exec` 单元测试执行、严格 JSON 与 `tool_call` 参数校验。
   - **Chat Template Sensitivity Pairs**：通过 `(sensitive, twin)` 成对测试（如 `template_tool_response` 与纯文本对照组 `template_tool_response_twin`）自动诊断故障归属：`healthy`、`template_broken`（纯文本能过但工具/多轮结构失败）、`model_weak`（两侧均失败）。

3. **可靠性与统计严谨性 (`evals.metrics`)**
   - `reliability.py`：提供 $Pass^k = p^k$ 与 $Pass@k = 1-(1-p)^k$、KV Cache 命中率聚合，以及 `gbench` 式的**诚实上报契约**（`infra_required=True` 时 `score=None` 而非伪造 `0`；偏离标准协议时强制标记 `leaderboard_comparable=False`）。
   - `statistics.py`：提供 `tail_validity(n, p, min_tail=10)` 样本量审计（例如 P99 需 $\ge 1000$ 样本才具备统计稳定性），以及针对单请求内部自相关序列（如逐 Token / 逐步骤延迟）的 `block_bootstrap_percentile_ci`。

4. **多步轨迹前缀回归定位 (`evals.prefix_regression`)**
   - 实现 `AGENT.md` 第 6 准则（First Mistake Identification）：支持通过单调前缀谓词做 $O(\log N)$ 二分定位或线性扫描，精准捕获最早偏离正确意图的步序号与故障层（`harness_template` / `tool_contract` / `model_reasoning` / `env_infra`），并导出可固化的 `PrefixRegressionCase`。


5. **Inspect AI 与 Harbor 契约适配器 (`evals.frameworks`)**
   - `inspect_ai.py`：实现 `Task(dataset, solver, scorer, sandbox)` 组合流水线、`LocalTempSandbox`、Expected 工具异常（回灌模型自愈）vs Unexpected 沙盒异常（触发 `error` / `infra_required`）隔离，以及 `EvalLog` → `TrajectoryStep` 首错定位桥接。
   - `harbor.py`：实现 Harbor 任务目录解析与 Lint（`task.toml` + `instruction.md` + `tests/test.sh`）、5 组 `ErrorPolicy(should_retry, should_grade, has_valid_reward)` 与 `reward_valid` 均值聚合（无效奖赏同时移出分子与分母），以及 `ATIF-v1.8` (`trajectory.json`) 校验与首错定位桥接。
---

## 快速验证

```bash
# 运行 evals/ 全套单元测试（零外部依赖）
uv run python -m unittest tests/unit/test_evals_gbench.py tests/unit/test_evals_inspect_harbor.py -v

# 运行第 7 章配套实验 7-15 / 7-16 / 7-17（离线 mock 或真实 /v1 端点）
uv run python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py --mock
uv run python experiments/chapter7/inspect-ai-eval/run_inspect_eval_demo.py --mock
uv run python experiments/chapter7/harbor-eval/run_harbor_eval_demo.py --mock
```

深度架构解析与选型对比见：
- [`docs/architecture/EVAL_FRAMEWORKS_COMPARISON.md`](../docs/architecture/EVAL_FRAMEWORKS_COMPARISON.md)（`gbench` × `Inspect AI` × `Harbor` × `Promptfoo`/`DeepEval` 选型决策指南）
- [`docs/architecture/GBENCH_EVALUATION_DEEP_DIVE.md`](../docs/architecture/GBENCH_EVALUATION_DEEP_DIVE.md)（`gbench` 联合评估深度白皮书）
