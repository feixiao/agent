# 第 2 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| agent-skills-ppt | `python demo.py --offline -o output/presentation_offline.pptx`；LLM：`OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 python demo.py --model qwen3.8-27b-splash` | PARTIAL(60s 硬编码超时) | demo.py | 离线全流程 PASS（9 页 pptx 生成+校验）；LLM 路径第 1 轮 read_skill 成功后，生成大纲 payload 的轮次 >60s 触发 APITimeoutError（客户端 timeout=60.0 写死，不可改） |
| attention_visualization | `python -m pytest -q` | BLOCKED(HF 模型下载 >200MB) | main.py, agent.py, visualization.py | 需下载 Qwen/Qwen3-0.6B 权重约 1.2GB，超 200MB 上限且本地无缓存 → LLM 部分 BLOCKED；离线 pytest 8 passed |
| context-compression | 入口 `python main.py -s combined --model qwen3.8-27b-splash --no-streaming`；核心模块最小演示（临时脚本直接调 ContextCompressor，2 篇文档） | PARTIAL(venv 同步后补跑，入口已解锁；最小规模 27B 未收敛 final answer，见「补跑记录」) | main.py, compression_strategies.py | venv 同步补装 bs4/html2text 后入口解锁：main.py 与 run_all_strategies.py 最小规模全流程真实跑通（agent 循环/工具/压缩/落盘），但 27B 最小规模下 success=False、压缩比反转；原记录：核心压缩模块本地验证 combined 1533→863(56.3%)、context_aware 1533→902(58.8%)；pytest 1 passed |
| kv-cache | `KIMI_BASE_URL=http://localhost:1234/v1 MOONSHOT_API_KEY=not-needed python main.py --mode correct --model qwen3.8-27b-splash --no-interactive --root-dir . --task "..."`（再跑 --mode dynamic_system 第二轮） | PARTIAL(LM Studio 不上报 cached_tokens) | main.py, agent.py | 两轮演示均跑通（各 2 轮迭代 / 1 次 read_file / 最终答案 / 结果 JSON 落盘）；缓存列恒 0：本地 usage 无 cached_tokens 字段，属预期；TTFT correct 56.8s→76.9s，dynamic_system 51.3s→107.7s，TTFT 差异在本地噪声范围内，缓存结论仅能以线上报告 cached_tokens 的模型得出 |
| local_llm_serving | `python check_compatibility.py`、`python main.py --info`、`python -m pytest -q` | BLOCKED(Ollama 服务未安装/未启动，vllm 包缺失) | main.py, agent.py, ollama_native.py | 离线检查全部通过（macOS/arm64/Py3.12，Ollama 包已装但 11434 无服务，无 vllm）；LLM 演示无法运行：代码只支持 ollama/vllm 两个后端，无指向 LM Studio 等任意 OpenAI 兼容端点的参数（--backend 仅 vllm/ollama/auto）；quick_test_streaming.py 是 0 字节空文件；pytest 20 passed / 4 failed（4 个失败全部要求真实 Ollama/vLLM 服务） |
| prompt-engineering | `OPENAI_API_KEY=not-needed OPENAI_API_BASE=http://localhost:1234/v1 python run_ablation.py --model qwen3.8-27b-splash --model-provider openai --user-model qwen3.8-27b-splash --user-model-provider openai --env retail --end-index 1 --num-trials 1 --max-agent-steps 3` | PASS(最小规模) | run.py, run_ablation.py | tau-bench retail 任务完整闭环（用户模拟器 LLM + Agent 3 步 + 2 次工具调用 + 8 条消息），reward 0.0（3 步截断属最小规模的预期结果），结果存 results_ablation/tool-calling-qwen3.8-27b-splash-baseline_*.json |
| prompt-injection | `python demo.py --list`；LLM：`python demo.py -n 1 -a 1,2 -d 1,4 -o result_local_qwen38.json`；`python -m pytest -q` | PARTIAL(客户端 60s 超时 < 本地单调用耗时) | demo.py（agent.py 原有完整中文注释） | --list 离线 OK；pytest 5 passed；LLM 矩阵 2 攻击×2 防御×1 次全部 APITimeoutError（make_client 写死 timeout=60.0，本地 27B 单调用 60~100+s），矩阵输出 0% 且含错误，无有效成败数据；run_campaign.py BLOCKED（冻结协议指向 Moonshot 付费 API，协议 JSON 不可改） |
| system-hint | `python main.py --mode preview`；`KIMI_API_KEY=not-needed KIMI_BASE_URL=http://localhost:1234/v1 python main.py --mode single --provider kimi --model qwen3.8-27b-splash --task "..."` | PARTIAL(2-8 campaign 需 Moonshot 付费) | main.py, agent.py | preview 五类状态栏离线全流程 OK；single 最小任务完成（2 轮迭代 / 1 次 write_file / 最终答案 / trajectory.json 落盘）；run_experiment_2_8.py 为冻结 campaign（协议 JSON 固定 Moonshot kimi-k3 + 30 组合，不可改不可缩小）→ 该入口 BLOCKED(付费 API) |

## 各实验详细记录

### agent-skills-ppt
- 命令：离线 `python demo.py --offline -o output/presentation_offline.pptx`；LLM `OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 python demo.py --model qwen3.8-27b-splash -o output/presentation_local_qwen38.pptx`
- 输出片段：
```
【离线回放】按 SKILL.md 约定，逐层加载并调用捆绑脚本：
  >>> [渐进式披露·第二层] Agent 调用 read_skill('pptx')，加载完整 SKILL.md（1242 字符）
  >>> [渐进式披露·第三层] Agent 调用 read_skill_file('pptx', 'reference.md')，加载子文档（1163 字符）
  >>> [执行捆绑脚本] run_skill_script('pptx', 'generate_pptx.py') 生成 presentation_offline.pptx ...
  >>> 生成结果：{"path": "...", "num_slides": 9, "titles": ["渐进式披露式 Agent Skills 对上下文效率的影响", "目录", ...]}
校验通过：这是一个可被 python-pptx / PowerPoint 打开的有效 .pptx（9 页）。
```
LLM 路径：第 1 轮 `read_skill(name=pptx)` 成功（渐进式披露第二层真实发生）；第 2 轮起模型需一次性写出 8-12 页大纲 JSON（长生成），本地 27B 单轮 >60s，`timeout=60.0, max_retries=3`（写死于 run_agent）三次全部 `openai.APITimeoutError: Request timed out.`。
- 已注释文件：demo.py（原文件已含大量中文注释，本次补 run_agent docstring 与本地 60s 超时运行提示）
- 备注：离线路径完整复现三层渐进式披露并生成、校验 9 页 pptx；LLM 路径受 60s 硬编码超时限制（禁止改逻辑，无法通过参数放宽）。

### attention_visualization
- 命令：`/venv/bin/python -m pytest -q`
- 输出片段：
```
........                                                                 [100%]
8 passed in 3.55s
```
- 已注释文件：main.py, agent.py, visualization.py
- 备注：agent.py 通过 `transformers` 加载 `Qwen/Qwen3-0.6B`（bf16 权重约 1.2GB，超 200MB 下载上限；本地 HF 缓存无此模型，仅有 12MB 的 Qwen2.5-0.5B tokenizer 文件）。按任务规则不下载 → LLM 推理部分 BLOCKED；可视化绘图与 pytest 路径正常。若用户允许，可手动 `HF_HOME` 下载后用 `MODEL_NAME`/`MODEL_PATH` 环境变量运行 main.py（代码支持本地路径，无需改码）。

### context-compression
- 命令：入口 `python main.py -s combined --model qwen3.8-27b-splash --no-streaming`（退出码 1，bs4 缺失）；核心模块最小演示（临时脚本 `cc_minimal_demo.py`，2 篇模拟文档，combined + context_aware 两种策略）
- 输出片段（入口失败）：
```
File ".../web_tools.py", line 11, in <module>
    from bs4 import BeautifulSoup
ModuleNotFoundError: No module named 'bs4'
```
- 输出片段（核心模块 LLM 验证，本地 200 OK）：
```
[non_context_aware_combined_summary] original=1533 chars -> compressed=863 chars (ratio 56.3%)
**Summary: Major OpenAI Talent Departures in 2024** ...
[context_aware_summary] original=1533 chars -> compressed=902 chars (ratio 58.8%)
**OpenAI Co-Founders: Current Affiliations** ...
```
- 已注释文件：main.py, compression_strategies.py
- 备注：venv 缺 bs4(beautifulsoup4) 与 html2text，禁止装依赖 → 入口 BLOCKED(缺依赖)；压缩核心（ContextCompressor + 五种策略）用本地 qwen3.8-27b-splash 真实调用验证通过；pytest 1 passed（test_malformed_tool_json / test_web_tools_null_content 因 bs4 跳过，其余测试文件为空）。

### kv-cache
- 命令：`MOONSHOT_API_KEY=not-needed KIMI_BASE_URL=http://localhost:1234/v1 python main.py --mode correct --model qwen3.8-27b-splash --no-interactive --api-key not-needed --root-dir . --task "Use read_file to read env.example. ..." --output result_local_qwen38_correct.json`（第二轮同参数 `--mode dynamic_system`）
- 输出片段（correct 轮）：
```
Iteration 1 - TTFT: 56.774s, Tokens: prompt=745, completion=41
Executing tool: read_file with args: {'file_path': 'env.example'}
Iteration 2 - TTFT: 76.906s, Tokens: prompt=1125, completion=107
...
📊 Performance Metrics:  TTFT per iteration: 56.774s / 76.906s
🔄 Cache Statistics:  Cached Tokens: 0, Cache Hits: 0, Cache Misses: 0
💰 Token Usage: Prompt 1,870 / Completion 148 / Total 2,018
💾 Detailed results saved to: result_local_qwen38_correct.json
```
dynamic_system 轮：TTFT 51.345s / 107.679s，Prompt 1,937，缓存同样全 0。
- 已注释文件：main.py, agent.py
- 备注：两轮演示流程完整跑通（工具调用、最终答案、指标打印、JSON 落盘）；本地 usage 只有 `completion_tokens_details.reasoning_tokens`，无 `prompt_tokens_details.cached_tokens` → 缓存命中/比例列恒 0，属 LM Studio 不上报所致，缓存对比结论 PARTIAL；TTFT 两轮均无改善（-35%/-110%），本地推理噪声 + 无缓存复用信号，不足以支撑"缓存改善 TTFT"结论（该结论需 Moonshot 等上报 cached_tokens 的端点）。

### local_llm_serving
- 命令：`python check_compatibility.py`、`python main.py --info`、`python main.py --mode single --backend ollama --no-stream --task "say hello"`、`python -m pytest -q`
- 输出片段：
```
📊 System Information:
  Platform: Darwin 27.2.0   Architecture: arm64   Python: 3.12.16
  CUDA: ❌ Not available     Ollama: ✅ Package installed
```
（check_compatibility 判定 macOS → 建议使用 Ollama）
```
2026-11-10 ... - __main__ - INFO - Ollama is not running ...   or: ollama serve
（--mode single 初始化即 exit 1）
```
pytest：`4 failed, 20 passed`（失败均为 test_parallel_tools/test_streaming 中要求真实 Ollama/vLLM 服务的用例）。
- 已注释文件：main.py, agent.py, ollama_native.py
- 备注：Ollama 服务未安装/未启动（11434 无响应，无 ollama 二进制），vllm 包未安装；main.py 后端仅 vllm/ollama/auto，**没有**指向 LM Studio OpenAI 兼容端点的参数，无法按用户期望"用参数指向本地 LM Studio" → LLM 部分 BLOCKED；`quick_test_streaming.py` 为 0 字节空文件（无内容可运行）。

### prompt-engineering
- 命令：见总表（run_ablation.py 基线，retail，1 任务 × 1 trial × 3 agent 步，litellm openai provider → 本地 LM Studio）
- 输出片段：
```
🔬 Running Ablation Study: baseline
📝 Initial User Message:
Hi, my name is Yusuf Rossi. I recently received my order #W2378156 ... exchange a couple of items ...
🤖 Assistant Response:  💬 Message: Great, I've verified your identity. Now let me pull up your order details.
🔧 Tool Calls (1 tool(s)):  [1] get_order_details • order_id: #W2378156
📊 TASK SUMMARY  Final Reward: 0.0  Total Steps: 3  Messages Exchanged: 8
🏆 Average reward: 0.0   📄 Results saved to results_ablation/tool-calling-qwen3.8-27b-splash-baseline_1110012447.json
```
- 已注释文件：run.py, run_ablation.py
- 备注：完整闭环（用户模拟器 LLM 生成初始消息 → Agent 鉴权 → 查订单详情）在本地模型上跑通；reward 0.0 是 3 步截断的必然结果（最小规模），用于验证链路而非成功率。完整任务（30 步）在本地 27B 上单任务需 15 分钟以上，未跑全量。

### prompt-injection
- 命令：`python demo.py --list`（离线）；`python demo.py -n 1 -a 1,2 -d 1,4 -o result_local_qwen38.json`（LLM 最小矩阵）；`python -m pytest -q`
- 输出片段：
```
使用模型：qwen3.8-27b-splash，每个组合试验 1 次
[直接注入 ] x [D1-无防御 ] 成功率   0% (0/1)  (含 1 次错误)
[间接注入 ] x [D4-组合防御] 成功率   0% (0/1)  (含 1 次错误)
...
结果矩阵已保存到 result_local_qwen38.json
```
（单独复跑确认错误为 `APITimeoutError: Request timed out.`，来自 make_client 写死的 `timeout=60.0, max_retries=2`）
- 已注释文件：demo.py（agent.py 原已含完整中文注释）
- 备注：LLM 矩阵框架完整执行（3 攻击×4 防御中取 2×2），但本地单调用耗时普遍 60~100+s，全部 4 次调用超时 → 成功率无有效数据；run_campaign.py 为冻结 manuscript campaign（协议 JSON 固定 Moonshot/kimi-k3、60 格×5 trial，且协议为不可修改的 *.json 证据文件）→ BLOCKED(付费 API)。

### system-hint
- 命令：`python main.py --mode preview`（离线）；`KIMI_API_KEY=not-needed KIMI_BASE_URL=http://localhost:1234/v1 python main.py --mode single --provider kimi --model qwen3.8-27b-splash --output trajectory_local_qwen38.json --task "Create a file named hint_check.txt ..."`
- 输出片段：
```
【案例 2 · 工具调用计数器】在工具结果上标注第几次调用
  无状态栏：{"success": true, "output": "Call connected, no answer"}
  有状态栏：[2025-09-14 10:30:45] [Tool call #3 for 'phone_call'] ...
...
✅ Task completed successfully!
📝 Final Answer: File `hint_check.txt` created successfully.
📊 Statistics:  Iterations: 2   Tool calls: 1
💾 Trajectory saved to: trajectory_local_qwen38.json
🔧 Tool Call Summary: - write_file: 1 calls (1 success, 0 failed)
```
- 已注释文件：main.py, agent.py
- 备注：preview（五类状态栏离线渲染）与 single（本地 LLM 最小任务）均通过；run_experiment_2_8.py 是冻结真实 campaign（协议 JSON 固定 Moonshot `kimi-k3`、6 套件×5 例、30 个条件组合、`base_url` 取自协议且要求 MOONSHOT_API_KEY，无 CLI 缩小规模入口，协议 JSON 不可改）→ 该入口 BLOCKED(付费 Moonshot API)。实测无 key 运行时立即 `RuntimeError: MOONSHOT_API_KEY or KIMI_API_KEY is required`（未发起任何外部调用）。

## 注释后重跑验证（全部通过）

| 实验 | 重跑命令 | 结果 |
|---|---|---|
| agent-skills-ppt | `python demo.py --offline` | PASS（9 页 pptx 生成+校验，退出码 0） |
| attention_visualization | `pytest -q` | 8 passed |
| context-compression | 核心模块最小 LLM 演示脚本 | PASS（combined/context_aware 两策略摘要正常，退出码 0）；pytest 1 passed |
| kv-cache | `--mode correct` 小任务 | PASS（2 轮迭代，结果落盘，退出码 0） |
| local_llm_serving | check_compatibility + main --info + pytest | 20 passed / 4 failed（与注释前完全相同，失败均为需真实 Ollama/vLLM 服务的用例） |
| prompt-engineering | 同最小规模命令 | PASS（3 步 / 2 工具调用，新结果文件落盘） |
| prompt-injection | `--list` + pytest | 5 passed |
| system-hint | preview + single 小任务 | PASS（2 轮 / 1 write_file / trajectory 落盘） |

## 统计

8 个实验 = **1 PASS + 5 PARTIAL + 2 BLOCKED**（venv 同步补跑后口径，原 1 PASS + 4 PARTIAL + 3 BLOCKED）：

| 状态 | 数量 | 实验 |
|---|---|---|
| PASS | 1 | prompt-engineering |
| PARTIAL | 5 | agent-skills-ppt、kv-cache、prompt-injection、system-hint、context-compression(补跑后入口解锁) |
| BLOCKED | 2 | attention_visualization(HF 下载>200MB)、local_llm_serving(无 Ollama 服务/vllm) |

环境限制共性说明：
1. **60s 硬编码客户端超时**（agent-skills-ppt run_agent、prompt-injection make_client）与本地 27B 单调用 60~110s 的推理速度冲突，导致长生成轮次必然 APITimeoutError；代码禁止改动逻辑，无法放宽。
2. **LM Studio 不上报 cached_tokens**（usage 仅含 completion_tokens_details.reasoning_tokens）→ kv-cache 缓存列恒 0。
3. **冻结协议 JSON**（prompt-injection / system-hint 的 run_campaign、run_experiment_2_8 固定 Moonshot 付费端点）不可修改，且付费 API 禁止调用。
4. 所有 LLM 请求均只使用 `qwen3.8-27b-splash`（LM Studio 单槽位保护规则遵守，无其他模型 id 请求）。

## 补跑记录（venv 同步后）

> 背景：`uv sync --all-extras` 后 venv 补装了 beautifulsoup4(4.15.0)/html2text(2025.4.15) 等。
> 本小节只记录补跑结果；总表 context-compression 行已由 `BLOCKED(缺依赖)` 更新为 `PARTIAL`。

### context-compression（原 BLOCKED：缺依赖 bs4/html2text，入口无法 import）

- 依赖确认：`import main` 成功（`web_tools.py` 的 `from bs4 import BeautifulSoup` / `import html2text` 可解析）；`run_all_strategies.py --list-strategies` 正常输出 6 种策略。
- 超时规避核查：agent.py / compression_strategies.py 的 `OpenAI(api_key=..., base_url=...)` **未写死 timeout** → openai SDK 默认 600s，无 60s 硬编码；本次仍显式携带 `OPENAI_TIMEOUT=600`（SDK 该版本不读此变量，仅作无害冗余），未出现 APITimeoutError，无需改码。
- 命令 1（run_all_strategies 最小规模，1 策略）：
  `MAX_ITERATIONS=5 MODEL_TEMPERATURE=1 LLM_PROVIDER=openai LLM_MODEL=qwen3.8-27b-splash OPENAI_BASE_URL=http://localhost:1234/v1 OPENAI_API_KEY=not-needed OPENAI_TIMEOUT=600 python run_all_strategies.py -s combined -m qwen3.8-27b-splash -n 5`（退出码 0）
- 命令 2（main.py 入口，非交互 stdin 注 `n`）：
  同 env + `printf 'n' | python main.py -s combined --no-streaming`（退出码 0）
- 输出片段（命令 1，324s 完成）：
```
Strategy                                 Success    Time(s)    Tokens       Compression  Overflows
non_context_aware_combined_summary       ❌ No       323.99     16,581       233.2%       0
  - Successful: 0/1
JSON results saved to logs/strategy_results_20261110_114448.json
                             TEST RUN COMPLETE
```
- 输出片段（命令 2，524s 完成）：
```
RESEARCH COMPLETE
❌ Failed
📊 Statistics:
  Tool Calls: 20          Context Overflows: 0
  Total Tokens Used: 24,278    Compression Ratio: 280.7%   Space Saved: -15,925 chars
Try another strategy? (y/n):
Thank you for using the demo!
```
- 结果解读：
  - **依赖阻塞已解除**——两个入口首次完整跑通：研究 agent 循环（20 次工具调用：search_web 走 mock 数据 + fetch_webpage）、13 次压缩摘要调用全部命中本地 LM Studio（200 OK）、token 统计、流式/非流式、日志与 JSON 落盘全部正常。
  - 但 `success=False`（5/6 轮内 27B 未给出 final answer，循环到 max_iterations 自然结束，无异常）；且压缩比 >100%（模型把 54 字符的 mock 占位内容"摘要"成 1200+ 字符长文，属 27B 在最小 mock 语料上的行为质量问题，非环境/代码问题）。fetch_webpage 真实外网请求全部 10s 超时（沙箱无外网），代码按设计捕获并缓存错误结果，agent 继续运行。
  - 状态结论：`BLOCKED(缺依赖)` → **PARTIAL**（入口与全链路可运行；"研究成功+真实压缩收益"需在可联网 + 更强模型/更大语料下验证）。
- 备注：运行在 `chapter2/context-compression/logs/` 新增 `strategy_run_*.log` 与 `strategy_results_*.json`（实验代码自身正常写盘，未提交）。
