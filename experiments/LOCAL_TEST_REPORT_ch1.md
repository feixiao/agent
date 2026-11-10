# 第 1 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv
日期：2026-11-09 晚 ~ 2026-11-10（接续执行）。前序执行者已为 context / image-gen-workflow / search-codegen 的核心模块加好中文注释并完成 context full 首跑（崩溃退出）；本次接续完成全部 5 个实验的运行与报告，并为缺失导读的入口脚本补齐中文注释（只加注释、零逻辑改动，改后全部重跑验证）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| 1-1 context | `python main.py --mode single --provider openai --model qwen3.8-27b-splash --task "把 100 欧元换算成美元,再换算回欧元,告诉我两步的结果" --context-mode full`（另同任务 `--context-mode no_tool_results` 对照） | PASS | agent.py, config.py, main.py | full：3 轮迭代 / 2 次 convert_currency，108.70 USD→100.00 EUR 往返无损；no_tool_results：同样 3 轮/2 次调用，但看不到工具结果，改用自行捏造的汇率 1.1642（116.42→99.99 EUR）作答——消融目标现象 |
| 1-2 web-search-agent | `python main.py --provider offline-demo` + 本地 LLM 最小探测（WebSearchAgent→LM Studio，Formula 声明以标准 web_search function 模拟）+ pytest | PARTIAL | agent.py, run_experiment_1_2.py | 离线 ReAct 轨迹回放正常；本地 LLM chat 真实跑通（finish_reason=stop）；Formula 托管 web_search 为 Moonshot 专有能力，本地无 /formulas 端点 → 真实搜索环节 BLOCKED(外部付费 API)；44/44 测试通过 |
| 1-3 search-codegen | `python main.py --backend openai --dry-run --request "东盟 10 国首都之间最近的一对是哪两个？请搜索并用 Python 计算" --reasoning high --verbosity high` + pytest + py_compile | BLOCKED(服务端托管 web_search/code_interpreter 依赖外部付费 API，本地无 OpenAI/DashScope Key) | agent.py, run_experiment_1_3.py, main.py, config.py, example_request.py, quickstart.py | dry-run 离线打印完整 Responses API 请求体（含托管工具定义）；12/12 测试、py_compile 通过 |
| 1-4 image-gen-workflow | 改写节点直调（`pipeline.rewrite_prompt`，本地 LLM）1 条需求 + pytest | BLOCKED(生图依赖外部付费 API 通义万相/Gemini/GPT-Image，或本地 ComfyUI 127.0.0.1:8188，两者本机均不可用) | pipeline.py | 改写节点自动走本地 qwen3.8-27b-splash，windowsill-plant 一条改写成功（SD 风格 prompt + 负面词 + style_notes，耗时 229s）；25/25 测试通过 |
| 7-1/7-2 learning-from-experience | `python experiment.py --mode qlearning --rl-episodes 10000 --eval-episodes 100 --seed 42` + pytest | PASS（Q-learning 纯离线完整跑通；LLM 对照部分需 Moonshot Key，未跑） | experiment.py, game_environment.py, rl_agent.py, llm_agent.py, demo.py, quick_demo.py, run_experiment_8_2.py | 10,000 局训练 1.38s，100 局贪婪评估胜率 100.0%（平均奖励 243.0 / 平均 12 步）；16/16 测试通过 |

## 各实验详细记录

### 1-1 context（上下文消融）

- 命令：
  ```bash
  cd experiments/chapter1/context
  python main.py --mode single --provider openai --model qwen3.8-27b-splash \
    --task "把 100 欧元换算成美元,再换算回欧元,告诉我两步的结果" \
    --context-mode full --output local_test/task_result_full_local.json
  python main.py --mode single --provider openai --model qwen3.8-27b-splash \
    --task "把 100 欧元换算成美元,再换算回欧元,告诉我两步的结果" \
    --context-mode no_tool_results --output local_test/task_result_no_tool_results_local.json
  ```
  （输出文件用新路径，避免覆盖 git 已跟踪的 task_result_full.json 历史证据；两次均退出码 0。）
- 输出片段：
  ```
  [full]  Context Mode: full | Iterations: 3 | Tool Calls: 2
          Final Answer: 100 EUR → 108.70 USD（汇率 1.087）→ 100.00 EUR（汇率 0.92）
                     往返换算回到 100 欧元，无损失
  [no_tool_results]  Iterations: 3 | Tool Calls: 2（调了 convert_currency 但看不到返回）
          Final Answer: 100 EUR = 116.42 USD → 99.99 EUR
                     “相差 0.01 是四舍五入误差”（汇率 1.1642 为模型自行捏造）
  ```
- 已注释文件：agent.py（模块导读 + ContextMode/ContextAwareAgent/主循环）、config.py、main.py（三种模式入口 + run_single_task/run_ablation_study）。
- 备注：no_tool_results 组看不到工具结果后改用自报汇率作答，正是本消融要展示的行为变化（与 EXPERIMENT_LEDGER 记载的 2026-08-25 Kimi K3 探针对照一致：隐藏工具结果后模型会编造数字）。52/52 测试通过（注释后重跑验证）。

### 1-2 web-search-agent（Kimi 搜索 Agent）

- 命令：
  ```bash
  cd experiments/chapter1/web-search-agent
  python main.py --provider offline-demo --output local_test/demo.json     # 无需 Key
  python main.py "什么是 Q-learning？" --provider kimi --base-url http://localhost:1234/v1 \
    --api-key not-needed --model qwen3.8-27b-splash --max-steps 1 \
    --output local_test/llm_local_probe.json                               # 指向本地端点
  ```
  另用一次性脚本直接调用 `WebSearchAgent._chat`（预置标准 web_search function 声明模拟 Formula 回执），证据存 `local_test/llm_local_chat_probe.json`；`pytest -q` 全量。
- 输出片段：
  ```
  [offline-demo] 💭[1] 思考 → 🔧[1] 调用 web_search → 👀[1] 观察(示例结果)
                 💭[2] 思考 → 🔧[2] 调用 web_search → ✅[3] 最终答案（Context Caching 解释）
  [本地端点]     答案: 搜索过程中出现错误: Formula declaration response has no tools
                 （LM Studio 的 /formulas 端点无该回执 → 真实搜索不可用，已留证）
  [本地 LLM]     HTTP 200 | finish_reason: stop
                 content: Q-learning 是一种无模型(model-free)强化学习算法，核心更新
                 Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',a') − Q(s,a)] …（正常成文回答）
  ```
- 已注释文件：agent.py（WebSearchAgent/_get_tools/_execute_formula/ReAct 主循环，前序已加）、run_experiment_1_2.py（本次补模块导读：正式验收需 Moonshot Key，离线路径用 offline-demo）。
- 备注：离线轨迹、单元测试（44/44）、本地 LLM chat 三条路径均验证通过；但实验的验收核心——Kimi Formula 托管 web_search 真实执行——是 Moonshot 专有能力（本地 LM Studio 无 /formulas 端点，Moonshot Key 属外部付费 API 被禁），故整体记 PARTIAL。

### 1-3 search-codegen（Deep Research：托管搜索 + 代码执行）

- 命令：
  ```bash
  cd experiments/chapter1/search-codegen
  python main.py --backend openai --dry-run \
    --request "东盟 10 国首都之间最近的一对是哪两个？请搜索并用 Python 计算" \
    --reasoning high --verbosity high
  python -m pytest -q test_responses_agent.py test_config_and_usage.py
  python -m py_compile agent.py config.py main.py run_experiment_1_3.py
  ```
- 输出片段：
  ```
  🧪 Dry-run：以下是发送给 GPT-5 的请求体（未联网）
  Model: gpt-5.6-sol   "model": "gpt-5.6-sol", "store": true,
    "tools": [{"type": "web_search", "search_context_size": "medium"},
              {"type": "code_interpreter", "container": {...}}], "tool_choice": "auto"
  12 passed in 0.25s | py_compile OK
  ```
- 已注释文件：agent.py（前序）、run_experiment_1_3.py（前序）、main.py / config.py / example_request.py / quickstart.py（本次补模块导读）。
- 备注：`--dry-run` 确认请求体协议正确（Responses API + 两个服务端托管工具）；单任务真实运行需 OpenAI/DashScope 付费 Key（Responses API 的 web_search/code_interpreter 均为服务端托管，本地 LM Studio 不提供，且禁止调用外部付费 API）→ 实验本体 BLOCKED，离线/测试部分全部通过。

### 1-4 image-gen-workflow（文生图工作流 vs 原生）

- 命令：
  ```bash
  cd experiments/chapter1/image-gen-workflow
  python -m pytest -q
  python -c "from pipeline import rewrite_prompt; rewrite_prompt('帮我画一盆放在窗台上的绿植，早晨的阳光刚好照进来')"
  ```
  （未跑 main.py 全量：其 validate() 要求 4 个付费 Key；直调 rewrite_prompt 走代码内置的本地端点开关。）
- 输出片段：
  ```
  25 passed in 0.64s
  provider: local | model: qwen3.8-27b-splash
  endpoint: http://localhost:1234/v1/chat/completions   status: ok | latency_ms: 229369.3
  prompt: masterpiece, best quality, highly detailed, a lush potted green plant
          on a wooden windowsill, terracotta pot, morning sunlight streaming …
  style_notes: 将口语描述拆解为写实摄影 tag，补充陶土花盆、光中浮尘、散景虚化…
  ```
- 已注释文件：pipeline.py（前序：三条路线编排 + 本地端点开关说明）；main.py / config.py 原有中文 docstring。
- 备注：生图环节 BLOCKED——通义万相/Gemini/GPT-Image 均为外部付费 API，本地 ComfyUI（127.0.0.1:8188）探测不可达；`main.py` 还会覆写 `validation/latest.json`（受保护证据文件），故未整体运行。离线可验证部分（25/25 测试 + 改写节点本地 LLM 实测 1 条）通过，改写产物存 `local_test/rewrite_node_local_llm.json`。

### 7-1/7-2 learning-from-experience（Q-learning vs LLM 上下文学习）

- 命令：
  ```bash
  cd experiments/chapter1/learning-from-experience
  python experiment.py --mode qlearning --rl-episodes 10000 --eval-episodes 100 --seed 42 \
    --output local_test/results
  python -m pytest -q
  ```
- 输出片段：
  ```
  LEARNING CURVE (最近 1000 局滑动窗口)
        1000 |   0.3% | Q-table 123 | ε 0.606
        5000 |   0.1% | Q-table 128 | ε 0.100
        6000 |  55.9% | Q-table 137 | ε 0.100
       10000 |  98.1% | Q-table 142 | ε 0.100
  RL Training Summary: 训练 1.37s | Q 表 142 状态 | 训练胜率 45.10% | 评估胜率 100.00%
  Results saved to: local_test/results/20261110_004208（16 passed in 0.41s）
  ```
- 已注释文件：experiment.py / game_environment.py / rl_agent.py（前序已加）、llm_agent.py / demo.py / quick_demo.py / run_experiment_8_2.py（本次补模块导读）。
- 备注：纯离线 Q-learning 完整跑通（训练 + 评估，seed 42 可复现；注释后重跑一致）。LLM 对照部分（kimi-k3，20 局）需 Moonshot 付费 Key，按任务范围未跑——该部分若后续要跑属 BLOCKED(外部付费 API)。

## 服务状态备注

- 每个 LLM 实验运行前均按协议探测（curl /v1/chat/completions, max_tokens=5）；本次会话内所有 LLM 调用（context×2、web-search×1、image-gen 改写×1）均在服务正常时完成，单调用耗时 32s~229s，未超 8 分钟阈值，无 kill。
- 全部实验完成后收尾探测发现 chat 端点再次挂起（3 次 >40s 无响应；/v1/models 正常、qwen3.8-27b-splash 仍在加载列表）——与任务描述的“之前崩溃过”同一故障模式。因 LLM 工作已全部完成，不影响本报告结论；**建议重启 LM Studio 后再安排后续章节的 LLM 实验**。

## 统计

5 个实验 = 2 PASS（1-1 context、7-1/7-2 learning-from-experience）+ 1 PARTIAL（1-2 web-search-agent）+ 2 BLOCKED（1-3 search-codegen、1-4 image-gen-workflow）。
共运行 pytest 149 项全部通过（52+44+12+25+16）；LLM 真实调用 4 次全部 qwen3.8-27b-splash；全程未改任何逻辑、未动 validation/ 与受保护文件、未 commit、未装依赖。
