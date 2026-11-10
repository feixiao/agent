# 第 7 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

执行时间：2026-11-10。协议遵守说明：
- **模型锁死**：全部 LLM 请求只用 `qwen3.8-27b-splash`；每个 LLM 实验前按协议 curl 探测。探测时曾遇 1 次 40s 无返回，等 30s 重试后成功（之后正常，单次小请求 ~6s）。
- **venv 同步**：开始时后台 `uv sync --all-extras` 已完成（transformers 5.17.0 已生效），全程未遇 import 报错，无 BLOCKED(venv)。
- 未修改 `validation/`、`*.json` 证据、`EXPERIMENT_LEDGER.md`、`.env`、`pyproject.toml`；未装依赖；未 git commit；未调用外部付费 API。
- 注释原则：只加注释不改逻辑。**例外说明**：`user-memory-policy-eval/runner.py` 被 `results/manifest.json` 以 SHA-256 绑定（离线测试校验该绑定），加注释会破坏已保存证据的完整性，故该文件保持原字节不动（已验证还原后 4/4 测试通过），中文注释加在同目录 `test_runner.py`。
- 并发负载说明：本次执行期间仓库内其他章节的子代理同时在压 LM Studio，本地 27B 单轮耗时在 12s（空闲）~129s（高峰）间波动，直接影响了依赖 60s 客户端超时的在线实验（见 agent-cost-analysis）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| agent-cost-analysis | `demo.py --offline --scenario ab`（在线 `--live` 尝试 3 次） | PARTIAL | demo.py, agent.py（tracer.py/config.py 原已全中文注释） | 离线 A/B 表完整跑通：B 优化较 A 朴素总成本 -30.0%（$0.003776→$0.002643），A 是 B 的 1.43 倍；在线路径被 60s 硬编码客户端超时阻塞 |
| android-world | `pytest test_experiment.py` | BLOCKED(设备) | experiment_core.py, run_controlled_experiment.py, test_experiment.py | 19 passed；主入口 `run_controlled_experiment.py` 需真实 Android emulator + 外部 android_world checkout（本地未克隆） |
| elo-leaderboard | `cli.py pipeline --source simulate --models alpha beta --num-battles 40 --method bradley-terry --bootstrap 20` | PARTIAL | battle_simulator.py, bradley_terry.py（cli.py 原已中文注释） | 离线模拟 2 模型×40 场 → BT 评分+95%CI → 排行榜；online-elo 与 42 条 pytest 全过；LLM 评判路径需付费 Anthropic/OpenRouter |
| experiment-7-2-human-benchmark | 离线校验 results/manifest JSON | BLOCKED(设备+人工+外部checkout) | run_android_human.py | 18/18 记录完整、13 通过；发现 selection_manifest.json 实际哈希与预登记哈希不一致（见详细记录） |
| model-action-threshold | `experiment.py --models qwen3.8-27b-splash --tasks localized_timeout --trials 1 --max-turns 8 --base-url http://localhost:1234/v1` | PASS | experiment.py | 本地 LLM 真实跑通 2 次：`pre-edit files=2 tools=3 final_pass=True` / `files=3 tools=4 final_pass=True`，6 条 pytest 过 |
| model-benchmark | `demo.py --base-url http://localhost:1234/v1 --model qwen3.8-27b-splash --num-requests 4 --serial --max-tokens 32 --timeout 300` | PASS | benchmark.py, campaign.py, rate_ramp_benchmark.py（demo.py 原已中文注释） | 本地实测 4/4 成功（TTFT 均值 17.9s、端到端 p95 42.2s、15.4 t/s）；`--mock`、rate_ramp 最小模拟、15 条 pytest 全过；campaign 长期实验需付费端点未跑 |
| openvla-robotwin2-eval | `pytest test_experiment.py`；`annotate_timeouts.py --run-dir validation/runs/...` | BLOCKED(GPU+上游仓库) | experiment.py, annotate_timeouts.py, test_experiment.py | 6 passed；超时标注助手对已保存证据运行，按设计拒绝缺失败视频的 episode |
| public-health-reporting-eval | `demo.py` | PASS | demo.py, agent.py, evaluator.py, reporting_tools.py | 纯确定性（无 LLM）：5 任务 30/30 满分；19 条 pytest 过 |
| tau2-bench-eval | 无本地 py 入口 | BLOCKED(外部仓库) | —（目录内无代码，仅 README+validation 证据） | 上游 tau2-bench 未克隆且禁止装依赖；已有 4/5 验收证据保留于 validation/ |
| tts-quality-eval | `demo.py`（全链路，OPENAI_BASE_URL 锁本地）；`--list-providers`/`--dump-rubric`；`pytest tests` | BLOCKED(付费TTS/本地无合成端点) | 三文件（demo.py/config.py/pipeline.py）原已全中文注释，未新增改动 | 流水线 24 格端到端跑通但全在合成阶段失败（本地 LM Studio 无 /audio/speech，1.0s 完成）；ffprobe 对 ch6 现成 mp3 得 4.62s；Whisper 回译与 json_object 评审本地不可用；10 条 pytest 过 |
| user-memory-policy-eval | `pytest test_runner.py` | BLOCKED(付费API/本地端点不支持json_object) | test_runner.py（runner.py 受 SHA-256 绑定不可改） | 4 passed；在线 runner 硬编码 OpenRouter 且需 response_format=json_object（本地 LM Studio 返回 400，已实测） |
| user-memory-system-evaluation | `pytest test_experiment.py test_run_full.py` | BLOCKED(付费API+本地无embedding) | experiment.py, run_full.py | 16 passed；实验需付费 chat(kimi/doubao/openai)+4 个付费 embedding 端点+json_object，本地均不满足 |

## 各实验详细记录

### agent-cost-analysis（7-10 成本分析）
- 命令：
  - 在线：`OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 python demo.py --live --scenario ab --model qwen3.8-27b-splash --no-warmup`（共尝试 3 次，含 1 次 `--scenario naive`）
  - 离线：`python demo.py --offline --scenario ab`
- 输出片段（离线 A/B，真实注释后重跑）：
```
===== A/B 成本对比（同一个 8 轮客服退款任务）=====
方案                             总输入tok      缓存tok      缓存率    输出tok       总成本($)       vs基线
A 朴素(无缓存/无压缩)                   20700          0     0.0%     1118     0.003776         基线
B 优化(KV缓存+压缩)                    16035       6144    38.3%     1164     0.002643     -30.0%
重点对比：A → B  总 token: A=21818 → B=17199 减少 4619 (21.2%)；成本倍率 A 是 B 的 1.43 倍
```
- 已注释文件：demo.py（主流程）、agent.py（8 轮主循环）。tracer.py、config.py 交付时已含完整中文注释，未重复改动。
- 备注：在线路径阻塞原因——`config.make_client_and_model` 硬编码 `timeout=60.0, max_retries=2`（不可改）。实测单轮耗时：空闲 42s、并发高峰 129s（1.1k prompt + 160 reasoning tokens），60s 超时在高峰下必失败，3 次尝试全部 APITimeout 于 naive 首轮。LM Studio 不返回 `prompt_tokens_details.cached_tokens`，即便在线跑通，KV-cache 命中也会显示 0%（该观测属环境限制）。离线路径（canned trace 重算）完整覆盖两份交付物，故记 PARTIAL。

### android-world（7-12 T3A 受控实验）
- 命令：`python -m pytest test_experiment.py -q`
- 输出片段：`19 passed in 0.03s`
- 已注释文件：experiment_core.py（模块概括、redact_text、choose_decision、enforce_scope_claims）、run_controlled_experiment.py（模块概括）、test_experiment.py（模块概括）。
- 备注：主入口 `run_controlled_experiment.py` 需要真实 Android emulator（Pixel 6/API-33）+ 未克隆的外部 `android_world` checkout + 本地 vLLM Qwen，本地均不满足 → BLOCKED(设备)。离线证据/报告核心（脱敏、截断、配对比较、范围门禁、resume 校验）19 条测试全过。

### elo-leaderboard（7-7 排行榜）
- 命令：`python cli.py pipeline --source simulate --models alpha beta --num-battles 40 --seed 7 --method bradley-terry --bootstrap 20 --top-n 5`；另跑 `cli.py elo --method online-elo` 与 `pytest tests`
- 输出片段：
```
排名    模型                           Elo   95% 置信区间                 场数       胜率
1     alpha                     1028.5   [978, 1071]              40    61.3%
2     beta                       971.5   [929, 1022]              40    38.8%
```
（online-elo：alpha 1015.2 / beta 984.8；`42 passed`）
- 已注释文件：battle_simulator.py、bradley_terry.py。cli.py 原已中文注释。
- 备注：默认 simulate 来源即「离线 seed 模式」，按任务要求跑极小档（2 模型×40 场）。LLM 评判路径（`--source llm`）只支持 Anthropic/OpenRouter 付费后端 → 该分支 BLOCKED(付费API)，核心流水线离线全通，故记 PARTIAL。

### experiment-7-2-human-benchmark（7-2 人工基准）
- 命令：离线校验脚本（json 解析 + SHA-256 复核 + 18 题逐基准汇总）
- 输出片段：
```
results.json 内登记的 manifest 哈希: 0fa3f6f890e69c0e51db6ea50d46186af999c5ad0a24284055bbebd667fa15b7
当前文件实际哈希: 66fd3ff14f9a0842d77a17e6b69db002deea258a3dc5d3f44d07d70ccc477aae
18 题记录完整: True | 摘要: 13 / 18 通过
 GAIA 2/3  AndroidWorld 2/3  SWE-bench Verified 2/3  tau2-bench 2/3  Terminal-Bench 2/3  OSWorld-Verified 3/3
```
- 已注释文件：run_android_human.py（模块概括）。
- 备注：入口需 `--checkout`（外部 android_world 未克隆）+ Android emulator + 人工操作员 → BLOCKED(设备+人工+外部checkout)。⚠️ 完整性发现：`selection_manifest.json` 当前哈希与 README/results.json 预登记的 `0fa3f6f8...` 不一致——文件在预登记后被改动过（内容仍完整可读、18 题齐全）。按协议未改动该 JSON，请用户核实是否需要以版本库历史版本恢复。

### model-action-threshold（7-8 行动阈值）
- 命令：`python experiment.py --models qwen3.8-27b-splash --tasks localized_timeout --trials 1 --max-turns 8 --base-url http://localhost:1234/v1 --api-key-env OPENAI_API_KEY`（注释前 1 次 + 注释后重跑 1 次）
- 输出片段：
```
[1] model=qwen3.8-27b-splash task=localized_timeout trial=1
    pre-edit files=2 tools=3 final_pass=True error=None      （注释前）
    pre-edit files=3 tools=4 final_pass=True error=None      （注释后重跑）
```
- 已注释文件：experiment.py（模块概括 + run_cell 主循环）。
- 备注：本地 LLM（LM Studio 工具调用）真实跑通两次，harness 独立跑 unittest 判定通过；6 条 pytest 亦全过。1 模型×1 任务×1 试验即最小规模。

### model-benchmark（7-10 性能基准）
- 命令：
  - 本地 LLM 最小档：`python demo.py --base-url http://localhost:1234/v1 --model qwen3.8-27b-splash --api-key-env OPENAI_API_KEY --num-requests 4 --serial --max-tokens 32 --timeout 300`
  - 离线：`python demo.py --mock --concurrency-sweep 1,2`；`run_benchmark({"start_rate":1,"end_rate":2,"step_rate":1,"requests_per_step":5,...})`（rate_ramp 模拟）；`pytest test_campaign.py`
- 输出片段：
```
custom/qwen3.8-27b-splash | 4/4 (100%) | TTFT均值 17900ms | TTFT_p95 38475ms | 端到端均值 20.67s | 端到端p95 42.21s | 吞吐 15.4 t/s | 输出tok 32
```
（rate_ramp 模拟：10 请求 0 错误，ttft_p95≈0.096s；`15 passed`）
- 已注释文件：benchmark.py（模块概括）、campaign.py（模块概括、CampaignStore、run_workloads 主循环）、rate_ramp_benchmark.py（模块概括）。demo.py 原已中文注释。
- 备注：本地 LM Studio 流式端点实测可用（含 TTFT）。`campaign.py` 的 168h 可用性/负载矩阵配置（campaign_config.json）指向 OpenAI/Anthropic 等付费端点，未跑（禁止付费 API）；其 15 条 pytest 全过，`--smoke` 亦会被付费端点卡住。任务要求的「压测最小档」以 rate_ramp 内置模拟 + 4 请求本地实测覆盖。

### openvla-robotwin2-eval（7-13 OpenVLA×RoboTwin2）
- 命令：`python -m pytest test_experiment.py -q`；`python annotate_timeouts.py --run-dir validation/runs/exp7-13-localgpu-20260803-v1`
- 输出片段：
```
6 passed in 0.02s
RuntimeError: expected one exact failure video for chunk_1|robotwin2_move_can_pot_train_iid|100007, found 0
```
- 已注释文件：experiment.py、annotate_timeouts.py、test_experiment.py。
- 备注：主实验需 GPU + 上游 RoboTwin2/OpenVLA checkout + 失败视频产物（均在原 GPU 主机上，本仓库只存 episodes.jsonl 等 JSON）→ BLOCKED(GPU)。超时标注助手对已保存证据运行，按其「拒绝缺视频、不猜机制」的设计正确报错退出；6 条离线测试（val-only 命令精确性、证据门禁、preflight 诚实性等）全过。

### public-health-reporting-eval（公共卫生报告评估）
- 命令：`python demo.py`；`python -m pytest tests -q`
- 输出片段：
```
positivity-alpha-jan           6/6
...
TOTAL                          30/30
19 passed in 0.02s
```
- 已注释文件：demo.py、agent.py、evaluator.py、reporting_tools.py（模块概括）。
- 备注：纯确定性合成 DHIS2 数据 + 客观评分器，完全不依赖 LLM，一次跑通全部 5 任务满分。

### tau2-bench-eval（7-1 τ²-bench telecom）
- 命令：无（目录内无 Python 代码，仅 README 与 validation 证据）
- 输出片段：无
- 已注释文件：无（没有可注释的代码）
- 备注：运行主体在外部 `sierra-research/tau2-bench` 仓库（README 要求 `git clone` + `uv pip install -e`，本地未克隆且禁止装依赖）→ BLOCKED(外部仓库)。已有 5 任务 4/5 的验收证据（evidence.json/manifest.json/trajectories.json）保留在 validation/runs/ 未动。

### tts-quality-eval（7-6 TTS 质量评估）
- 命令：`OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 python demo.py --output <tmp>`（全链路 24 格）；`demo.py --list-providers` / `--dump-rubric`；`pytest tests`；pipeline 函数直接调用（ffprobe/Whisper/Rubric 分段验证）
- 输出片段：
```
完成：0/24 条成功，耗时 1.0s。   （24 格全部在 synthesis 阶段失败：本地 LM Studio 无 /v1/audio/speech）
[tts1-alloy-1.0 | digits] ... !! 失败: RuntimeError: ffprobe 失败 ... Invalid data
probe_duration(ffprobe, 离线): neutral_normal_formal.mp3 -> 4.62s   （ch6 现成 mp3）
transcribe 失败(本地LM Studio无Whisper端点, 预期内): APIStatusError
judge_rubric: response_format=json_object 本地返回 400 -> 不可用
10 passed in 0.22s
```
- 已注释文件：demo.py、config.py、pipeline.py 交付时已全部为中文注释，未新增改动（避免无谓 diff）；已重跑验证仍可运行。
- 备注：核心（TTS 合成 + 音频评审）必须走 OpenAI/ElevenLabs/Fish/Minimax/豆包等付费外部 API，本地无合成端点 → BLOCKED(付费TTS)。离线可验证部分全部跑通：流水线端到端（失败如实记录、整表不中断、results.json 落盘）、provider 状态表、Rubric 定义、ffprobe 对 ch6 现成 mp3 的时长探测、10 条 pytest。

### user-memory-policy-eval（7-7 记忆政策使用）
- 命令：`python -m pytest test_runner.py -q`
- 输出片段：`4 passed in 0.21s`（含 runner 文件哈希绑定校验）
- 已注释文件：test_runner.py。⚠️ `runner.py` 不可加注释——`results/manifest.json` 绑定其 SHA-256 且测试会校验，曾尝试加注释导致 1 条测试失败，已逐字节还原（`git checkout`）。
- 备注：在线 runner 的 `APIClient` 硬编码 `https://openrouter.ai/api/v1` 且要求 `response_format={"type":"json_object"}`（本地 LM Studio 实测返回 400）→ BLOCKED(付费API+本地端点不支持json_object)。离线测试（三种记忆编码、JSON 解析兜底、确定性评分器、哈希绑定）全过。

### user-memory-system-evaluation（7-4/7-11 记忆系统评估）
- 命令：`python -m pytest test_experiment.py test_run_full.py -q`
- 输出片段：`16 passed in 1.87s`
- 已注释文件：experiment.py（模块概括）、run_full.py（模块概括 + valid_checkpoint）。
- 备注：实验需付费 chat 端点（kimi/doubao/openai-mini）+ 4 个付费 embedding 端点 + 付费评审，且多处调用 `response_format=json_object`（本地 400）；本地无 embedding 服务 → BLOCKED(付费API+本地无embedding)。参考了 ch3 user-memory-evaluation 的 env 覆写方式（读 `OPENAI_BASE_URL`），但本实验端点全部硬编码于 YAML（`EndpointSpec` 甚至拒绝未解析的 `${}` 占位符），且 embedding/json_object 两个硬依赖本地无法满足，故不做本地强行改造。断点续跑/611 格矩阵/就绪探测等离线逻辑 16 条测试全过。

## 本章统计

12 个实验目录 = **3 PASS**（model-action-threshold、model-benchmark、public-health-reporting-eval）+ **2 PARTIAL**（agent-cost-analysis、elo-leaderboard）+ **7 BLOCKED**（android-world(设备)、experiment-7-2-human-benchmark(设备+人工)、openvla-robotwin2-eval(GPU)、tau2-bench-eval(外部仓库)、tts-quality-eval(付费TTS)、user-memory-policy-eval(付费API)、user-memory-system-evaluation(付费API+embedding)）。

所有可离线验证部分（pytest 合计 137 条全过：android-world 19、elo 42、openvla 6、public-health 19、model-benchmark 15、tts 10、action-threshold 6、memory-policy 4、memory-system 16；另有确定性/模拟/本地 LLM 运行）均已执行；全部 LLM 调用仅请求 `qwen3.8-27b-splash`；未改动任何证据文件。
