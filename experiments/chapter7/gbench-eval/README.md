# 实验 7-15：gBench 端到端评估与 Golden Set / Scaffold 版本锁定实战

本实验将 Google DeepMind 开源的 [`google-deepmind/gbench`](https://github.com/google-deepmind/gbench) 引入第 7 章「Agent 的评估」，提供两条互补路径：

1. **轻量白盒路径（零外部重依赖，立即可跑）**：通过 [`run_gbench_local_smoke.py`](run_gbench_local_smoke.py) 串联本仓库 [`evals/`](../../../evals/README.md) 的 `Subject/Scaffold` 双轴版本锁定、Golden Set 确定性冒烟、`Chat Template` 成对故障隔离、`tail_validity` 尾延迟审计与 `Pass^k` 可靠性聚合（支持 `--mock` 离线演示与 `--endpoint` 对接任意 OpenAI 兼容 `/v1` 服务）。
2. **官方完整 `gbench` 路径（对接真实 GPU 服务与 86 个基准套件）**：直接安装并驱动官方 `gbench` CLI，对本地 vLLM / Ollama 或远程 `/v1` 端点执行 Serving 性能、Golden Set、学术与 Agent 基准及 GemmaClaw Agentic QA 套件。

← [返回第 7 章目录](../README.md) · 📖 [深度架构白皮书](../../../docs/architecture/GBENCH_EVALUATION_DEEP_DIVE.md) · 🛠️ [评测底座 `evals/`](../../../evals/README.md)

---

## 一、 轻量白盒实战：运行 `run_gbench_local_smoke.py`

### 1. 离线演示三种典型故障模式（无需 API Key / GPU）

```bash
# 运行全部 mock 场景：健康模型 vs Chat Template 损坏 vs 模型能力不足 vs 基础设施阻断
uv run python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py --mock

# 只演练某一种场景（healthy | broken_template | weak_model | infra_error）
uv run python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py --mock --scenario broken_template
```

重点观察输出中的三类信号：
- **`pair_diagnostics`**：当 `template_tool_response` 失败而纯文本对照组 `template_tool_response_twin` 通过时，明确输出 `diagnosis = template_broken`（把模板序列化 Bug 与模型能力退化隔离开）。
- **`condition_comparison`**：当固定 `scaffold_id` 仅切换模型权重/量化时判定 `valid_subject_delta`；一旦更改提示词/解码/负载定义，`scaffold_id` 立即变化并拒绝直接混线比较。
- **`tail_validity`**：校验样本量是否足以支撑 P95（$\ge 200$）与 P99（$\ge 1000$），避免在小样本下误报尾延迟结论。

### 2. 对接真实 OpenAI 兼容 `/v1` 端点（Ollama / vLLM / OpenRouter）

```bash
# 例 1：对接本地 Ollama
uv run python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py \
  --endpoint http://127.0.0.1:11434/v1 \
  --model qwen2.5:7b \
  --output experiments/chapter7/gbench-eval/output/local_smoke.json

# 例 2：对接本地 vLLM（或云端 OpenAI 兼容接口）
OPENAI_API_KEY=... uv run python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py \
  --endpoint http://127.0.0.1:8000/v1 \
  --model google/gemma-4-E4B-it
```

---

## 二、 官方 `google-deepmind/gbench` 安装与标准命令

### 1. 安装（Python 3.11+）

```bash
# 基础包（适配本地笔记本与远程 Ollama/vLLM/OpenAI-compatible /v1 端点）
pip install gbench

# 若需在远程模式下用 tokenizer 做提示长度估算、Golden Set 模板 Token 检测或 mmlu/ruler 套件：
pip install "gbench[evals]" transformers
```

### 2. 常用评估命令速查（按推荐排查顺序）

```bash
# Step 0: Dry run 校验执行计划、GPU 档位与端到端参数（不实际启动模型）
gbench --models google/gemma-4-12B-it --num-gpus 1 --preset default --dry-run

# Step 1: Tier 2 Golden Set 冒烟（先排除 chat template / tool-call parser / JSON 格式故障）
gbench --golden-only --models google/gemma-4-E4B-it \
  --remote-endpoint http://127.0.0.1:11434/v1 \
  --tokenizer google/gemma-4-E4B-it

# Step 2: Serving 性能基准（Agentic 长上下文工作负载，联测 TTFT/TPOT/吞吐拐点）
gbench --models google/gemma-4-12B-it --num-gpus 1 --campaign agentic

# Step 3: Tier 1 Agentic & Reasoning 学术评测（开启思维链 + 限制样本快速验证）
gbench --evals-only --remote-endpoint http://127.0.0.1:8000/v1 \
  --tokenizer google/gemma-4-E4B-it \
  --evals bfcl_v4_agentic tau2 terminal_bench gpqa \
  --eval-thinking --max-output-tokens 16384 --eval-limit 20

# Step 4: Tier 3 GemmaClaw 多轮 Agentic QA 套件（需本地 Docker）
gbench --quality-only --models google/gemma-4-12B-it \
  --remote-endpoint http://127.0.0.1:8000/v1 \
  --tokenizer google/gemma-4-12B-it

# 查看各套件与上游 benchmark 的对齐版本（Canonical Sync Provenance）
gbench --eval-provenance
```

---

## 三、 工程检查清单

1. 任何正式对比实验前，先跑 `--golden-only`（或本实验的 Golden Set），确认 `chat_template` 成对诊断全绿再解释上层能力分。
2. 比较两个模型或量化版本时，核对输出中的 `scaffold_id` 是否一致；若不匹配，禁止直接比较分数。
3. 当服务不可用或上下文窗口不满足套件要求时，保持 `infra_required` 与 `score = null`，绝不用 `0` 填充失败格。
