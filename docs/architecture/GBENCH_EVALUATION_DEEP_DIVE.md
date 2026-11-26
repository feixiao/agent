# Google DeepMind `gbench` 架构深解与 Agent 评估工程落地

> **文档定位**：针对仓库当前在系统化评测基准、Serving 性能与能力联合度量、Scaffold 版本控制及模板隔离诊断上的缺口，深度拆解开源项目 [`google-deepmind/gbench`](https://github.com/google-deepmind/gbench)（Apache-2.0，`v0.5.0.post1`）的工程架构，并给出其与本仓库 [`evals/`](../../evals/README.md) 及 [`experiments/chapter7/`](../../experiments/chapter7/README.md) 的完整映射。  
> **核心公式**：$$\text{Agent} = \text{Model（概率模型引擎）} + \text{Harness（确定性工程底座）}$$  
> **评测第一公理**：不同时锁定 **Subject（权重/量化）** 与 **Scaffold（提示/模板/解码/服务环境/负载形态）** 的评测分数，无法分辨是模型进步还是测量尺子发生了漂移。

---

## 一、 为什么已有 `lm-eval` / `tau2-bench` 仍需要 `gbench`？

传统评测工具长期存在三处结构性割裂（见 `gbench/docs/GOSPEL.md`）：

1. **Serving 性能与模型能力割裂**：压测工具（如吞吐/TTFT 脚本）只管 tokens/s，能力评测（如 `lm-eval`）只管静态准确率。生产上线最关键的问题——*“在高并发、长上下文、开启 Thinking 与量化后，Agent 还能不能答对？”*——往往需要人工拼凑工具。
2. **绑定特定推理引擎**：脚本硬编码 vLLM/Ollama/厂商 SDK，切换推理后端或端云端点就要重写整套评测胶水。
3. **非对齐资源条件与“静默假零分”**：不同 GPU 卡数与上下文上限跑出来的数字混为一谈；或者基础设施挂掉、容器缺权限时直接输出 `0.0`，让一次环境故障看起来像模型能力全面崩盘。

`gbench` 的解法是：**全部评测支柱统一走标准 OpenAI 兼容 `/v1` HTTP 接口**（通过 `--remote-endpoint <URL>/v1` 对接任意 vLLM / Ollama / 云端网关，或由 CLI 自动拉起与销毁本地 vLLM 服务），在同一份 run manifest 下联合输出性能曲线与三层能力分数。

---

## 二、 `gbench` 四大核心工程支柱

```text
                       ┌───────────────────────────────────────────────┐
                       │         gbench CLI & Unified /v1 Runner       │
                       │  (Subject ID + Scaffold ID 双轴版本锁定输出)    │
                       └───────────────────────┬───────────────────────┘
                                               │
       ┌───────────────────┬───────────────────┼───────────────────┬───────────────────┐
       ▼                   ▼                   ▼                   ▼                   │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│ Serving Perf│     │ Tier 1:     │     │ Tier 2:     │     │ Tier 3:     │            │
│ TTFT / TPOT │     │ Academic &  │     │ Golden Set  │     │ Agentic     │            │
│ ITL / Knee  │     │ Agentic (86)│     │ Smoke (16)  │     │ Quality (60)│            │
│ --campaign  │     │ --evals     │     │ --golden-   │     │ --quality-  │            │
│ agentic/... │     │ (6 Pillars) │     │ only        │     │ only        │            │
└─────────────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘            │
                           │                   │                   │                   │
                           ▼                   ▼                   ▼                   │
                    [Endpoint Relay]   [Chat Template       [gbench-quality            │
                    进度超时/Token注入   Twin 成对隔离]       Docker 沙盒]              │
```

### 1. Tier 1：学术与 Agent 综合基准（`--evals`）
- **覆盖规模**：`--evals all` 内置 **86 个规范化 Python 套件**（另有 `ui_control_osworld` 与 `swe_lancer` 需显式点名运行），横跨 6 大能力支柱（见 `gbench/docs/eval-suites.md`）：
  1. **General Knowledge & Scientific Reasoning**：`gpqa`、`gpqa_diamond`、`mmlu`、`mmlu_pro`、`arc_agi`、`ifeval`、`simpleqa`、`frames`、`wildbench`、`cyberseceval`、`healthbench` 等。
  2. **Mathematics & Proofs**：`aime`、`hmmt`、`gsm8k`、`putnam`、`putnam_formal`、`imo_answer_bench` 等。
  3. **Coding & Algorithmic Design**：`bigcodebench`、`lcb`、`multipl_e`、`aider_polyglot`、`ojbench`、`scicode` 等。
  4. **Long Context & Retrieval**：`ruler`、`mrcr`、`longbench_v2_code`、`beam_128k`、`aa_lcr`、`loft_scifact` 等。
  5. **Tool Use & Agentic Workflows**（Agent 工程最核心支柱）：
     - 工具与函数调用：`bfcl`、`bfcl_live`、`bfcl_v4_agentic`、`complexfuncbench`、`nestful`、`seal_tools`、`api_bank`、`toolbench`、`gorilla_apibench`。
     - 多轮交互与终端/代码 Agent：`tau2`、`tau3`、`gaia`、`gaia2`、`terminal_bench`、`skillsbench`、`swe_bench_live`、`swe_bench_pro`、`swe_bench_multilingual`、`copilot_bench_swe`、`multi_swe_bench`、`mcp_atlas`、`mcp_bench`、`agent_dojo`、`wildclawbench`、`spider2`。
  6. **Multimodal Vision & Grounding**：`mmmu_pro`、`chartqa`、`charxiv`、`docvqa`、`infographicvqa`、`omnidocbench`、`screenspot`、`screenspot_pointing`、`mobilegym`、`mobilegym_pp`。
- **关键工程特性**：
  - 原生支持推理模式（`--eval-thinking`）、自定义 JSONL（`--eval-custom-jsonl`）与外部插件目录（`--eval-plugins-dir`）。
  - 图片保留数据集原始字节（不做有损重编码）；每套基准通过 `--eval-provenance` 声明上游对齐日期、revision 或校验和。
  - 支持分片执行与事后无损合并（`--merge`）及严格的缓存复用（`--skip-existing` 仅在 `canonical_sync`、`run_shape` 与 `scaffold_id` 完全一致时复用）。

### 2. Tier 2：Golden Set 确定性冒烟与模板隔离（`--golden-only`）
对应源码 `gbench/runners/golden.py` 与文档 `docs/golden-set.md`。它不是测“模型上限”，而是测“部署出来的模型 + 模板 + 解析器是否是一个健康可用的运行体”：
- **三态结果绝对隔离**：每个用例只输出 `passed`、`failed` 或 `error`（模态不支持时记 `not_applicable` 并移出分母）。**端点报错、Tokenizer 无法加载、沙盒缺失一律记为 `error`，绝不混入 `failed` 拉低模型分数**。
- **双边存在性断言（Two-sided Presence Matching）**：同时检查 `expected_outputs` 必须出现与 `expected_not_contains` 严禁出现，防止模型“碰巧输出关键词”或泄漏标签蒙混过关。
- **`python_exec` 隔离单元测试**：对代码生成用例（如 `code_canonical`）提取代码块并在隔离命名空间中运行 `assert` 断言。
- **Chat Template Sensitivity Pairs（模板敏感性成对诊断）**：
  - 将带结构化历史/工具消息的敏感用例与内容完全等价的单轮纯文本 Twin 对照组配对（`template_tool_response` vs `template_tool_response_twin`；`template_multi_turn` vs `template_multi_turn_twin`），并启用 `forbid_chat_template_tokens`（运行时读取模型 Tokenizer 的特殊/模板 Token，检测模板脚手架是否泄漏到可见输出）：

| Sensitive 用例 | Plain Twin 对照 | 归因结论 | 排查方向 |
| :--- | :--- | :--- | :--- |
| `passed` | `passed` | 序列化健康 | 模板与基础指令遵循正常 |
| `failed` | `passed` | **Chat Template 故障** | 模型能读懂纯文本，说明 `tool_calls`/`tool` turn 序列化或 parser 截断了消息 |
| `failed` | `failed` | **模型基础能力不足** | 即使单轮纯文本也答不出，故障不在模板 |

### 3. Tier 3：Agentic Quality Suite（`--quality-only`）
对应源码 `gbench/runners/quality.py` 与文档 `docs/quality.md`：
- 在本地隔离容器 `gbench-quality`（`docker/quality.Dockerfile`）中运行 **GemmaClaw / OpenClaw QA 套件**（固定 commit `d8bc6989` 下包含 60 个多轮工具调用、会话记忆与插件路由场景）。
- **前置基础设施自检**：在运行前核验 `/v1/models` 返回的 `max_model_len`（或配置的上下文长度）必须严格大于 GemmaClaw 的默认输出上限 `SELF_HOSTED_DEFAULT_MAX_TOKENS`（8192）；不足时直接返回 `infra_required` 并将 `pass_rate` 置为 `null`（绝不输出虚假 `0`）。

### 4. Serving 性能与工作负载战役（`--campaign`）
对应 `docs/performance.md`：
- 从模型 `config.json` 自动读取参数规模（`total_params_b`）、MoE 结构（`num_local_experts`、`num_experts_per_tok`）、多模态支持（`vision_config`）与最大上下文（`max_position_embeddings`），并用 `validate_gpu_config` / `get_num_gpus()` 校验显存与标准卡数档位（1 / 2 / 4 / 8 / 16 卡）。
- 提供贴近真实 Agent 流量的预设工作负载（如 `--campaign agentic` 长上下文 Agent 工作负载、`chat-like`、`--batch-sizes` 并发拐点扫描），联测 **TTFT、TPOT、ITL（Inter-Token Latency）与吞吐拐点**。

---

## 三、 三个极易被普通评估框架忽略的深层工程机制

### 机制 A：Subject vs. Scaffold 双轴版本锁定（`gbench/core/scaffold.py`）
`gbench` 把一次运行的实验条件严格拆分为两条独立正交轴（共 11 个 `ContractField`）：

| 轴 | 字段 | 工程含义 |
| :--- | :--- | :--- |
| **Subject（受测对象）** | `model_checkpoint`, `quantization` | 被测模型权重或量化版本 |
| **Scaffold（评测脚手架）** | `prompt_version`, `schema_version`, `scoring_version`, `tool_permissions`, `attempts`, `decode`, `dataset_snapshot`, `serving_environment`, `load_shape` | 如何提问、解码、约束、服务与评分（注意：**批量扫并发定义 `load_shape` 属于 Scaffold**，单点文件名属于数据点，这样同一条并发-延迟曲线才共享同一个 `scaffold_id`） |

核心对比规则：
- **仅 Subject 变化**：合法对比（模型迭代或量化精度消融）。
- **仅 Scaffold 变化**：新实验条件，**必须断开历史折线**并做 condition diff。
- **两者同时变化**：结果**不可解释**，严禁画在同一条对比曲线上。
- **诚实覆盖（`covers` / `unpinned`）**：未建模或未锁定的字段直接从 `ContractField` 推导写入 `unpinned`；若无任何字段被锁定，则 `scaffold_id = null`，绝不用假版本号营造虚假严谨性。

### 机制 B：Progress-Based Endpoint Relay（`docs/relay.md` & `swebench_common.py`）
许多第三方 Agent 评测框架（`SWE-agent`、`tau2`/`tau3`、`terminal_bench`、`skillsbench`、`gaia2`、`mcp_bench`、`toolbench`、`bfcl_v4_agentic` 等）内置了固定 HTTP 客户端超时（例如 `litellm` 默认 600s），一旦推理/长思考超过 600s，客户端静默断连并重采样，**测试结果里完全看不出样本曾因客户端超时被悄悄丢弃重写**。

`gbench` 在 Agent Harness 与 `/v1` 模型服务端之间插入了一个轻量 HTTP Relay，强制执行五项护栏：
1. **进度超时替代墙钟超时**：只要模型仍在持续流式吐出进度就不切断；只有真正停滞（stall）时才判定超时失败。
2. **请求形态校验**：拒绝非模型路由请求，记录 `root_paths`（如 `toolbench` 的 `/tokenize`）。
3. **Smoke Episode 截断**：冒烟模式下在首次有效回复后截断 episode，避免整套 Agent 跑空预算。
4. **Client-Side Abandon Age 记录**：记录客户端主动断开时的请求已耗时，防止静默重采样掩盖真实延迟问题。
5. **运行级 `max_tokens` 注入**：对本身不传输出预算的 Agent 套件（`AGENT_MAX_TOKENS_SUITES`），自动补齐 `--max-output-tokens`。

### 机制 C：统计学尾延迟校验与块自举（`gbench/analysis/statistics.py`）
- **单点不伪造离散度**：样本数 $n < 2$ 时 `std` 返回 `None`，绝不返回看似“零抖动”的 `0.0`。
- **尾部样本量审计（`tail_validity`）**：若要报告稳定的上分位延迟 $P_p$ 且保证尾部至少有 `min_tail=10` 个样本，则最小样本数满足：
  $$n \ge \left\lceil \frac{10}{1 - p/100} \right\rceil$$
  因此 **P95 至少需要 200 条请求、P99 至少需要 1,000 条请求、P99.9 至少需要 10,000 条请求**；样本不足时必须配置信区间上报，严禁当硬指标对比。
- **块自举置信区间（`block_bootstrap_percentile_ci`）**：单次解码内的逐 Token 延迟（ITL）或单条轨迹内的多步延迟存在强时间自相关，直接对单点做 iid bootstrap 会系统性低估置信区间宽度；必须按完整请求/完整轨迹（block）做重采样。

---

## 四、 与本仓库的工程映射关系

| `gbench` 原生模块/理念 | 本仓库对应落地点 | 角色与职责 |
| :--- | :--- | :--- |
| `gbench/core/scaffold.py` | [`evals/scaffold.py`](../../evals/scaffold.py) | 零依赖 `SubjectSpec` / `ScaffoldSpec` / `RunCondition` 与 `compare_conditions()` |
| `gbench/runners/golden.py` + `docs/golden-set.md` | [`evals/benchmarks/golden_set.py`](../../evals/benchmarks/golden_set.py) | Golden Set 三态/四态分离、`python_exec`、双边断言、Chat Template 成对诊断与 `/v1` 接入 |
| `gbench/analysis/statistics.py` + `docs/results.md` | [`evals/metrics/statistics.py`](../../evals/metrics/statistics.py) & [`evals/metrics/reliability.py`](../../evals/metrics/reliability.py) | `tail_validity`、块自举、`Pass^k` / `Pass@k`、`infra_required` 诚实上报 |
| 故障定位与回归飞轮 | [`evals/prefix_regression/locator.py`](../../evals/prefix_regression/locator.py) | 多步轨迹 First Mistake 二分定位与前缀回归用例冻结 |
| 端到端评测实战（第 7 章） | [`experiments/chapter7/gbench-eval/`](../../experiments/chapter7/gbench-eval/README.md) | 官方 `gbench` CLI 对接指南 + 离线 `--mock` / 在线 `/v1` 一体化脚本 |
| 核心测试守卫 | [`tests/unit/test_evals_gbench.py`](../../tests/unit/test_evals_gbench.py) | 覆盖 `evals/` 全模块与 `7-15` 离线冒烟路径的高频单元测试 |
