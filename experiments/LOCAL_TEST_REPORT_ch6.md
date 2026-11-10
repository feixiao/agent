# 第 6 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv
（torch 2.13.0 / transformers 5.17.0，Apple Silicon MPS 可用；每次 LLM 实验前已按协议 curl 探测，
探测期间服务一度变慢至 26~85s/次，已按「30s 重试」规则处理；LLM 请求全部锁死 qwen3.8-27b-splash，
付费 API 一律未调用）

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| agent-with-event-trigger | `python event_loop_demo.py --mock --duration 10`；`LLM_PROVIDER=dashscope DASHSCOPE_BASE_URL=http://localhost:1234/v1` 最小 harness（1 个 timer 事件） | PARTIAL | quickstart.py, agent.py, event_types.py（event_loop_demo.py 原已全中文） | 离线触发→唤醒→处理闭环 3 事件 OK；本地 LLM 真实循环 6 轮 13 次工具调用，但未收敛到 FINAL ANSWER（模型行为，非环境）；quickstart key 门禁正常 |
| astra-async-steering | `python test_judging.py`；`python experiment.py --replay validation/runs/exp6-14-20260905-formal`；`python summarize.py …formal` | BLOCKED(付费 OpenAI Astra API) | experiment.py, summarize.py, test_judging.py | 10 证伪测试全过；正式运行回放 15/15 验证通过、汇总可离线重算；实跑需硬编码 wss://api.openai.com 的 gpt-6-astra（付费）；`_local_smoke.py` 证实本地 LM Studio 不支持 Responses WebSocket |
| async-agent | `python demo.py`（离线三演示）；`python demo.py scenarios --scenario 1`（本地 LLM）；`pytest test_*.py` | PARTIAL | tasks.py, run_real_experiment.py（demo.py/async_demos.py/runtime.py 原已全中文） | 并行 3.00x 加速比；场景 1 本地 LLM 跑通（真实子进程 T1 + 插问应答 + 最终报告）；打断/状态演示与 2 个测试因仓库缺 `book/chapter4.md` 输入文件而失败（既有缺口） |
| claude-computer-use-native | `python validate_weather_run.py <run 目录副本>`（副本在临时目录） | BLOCKED(付费 Anthropic API + Docker 容器) | run_weather_task.py, validate_weather_run.py | 验证器在留存运行上全部 18 道门禁 passed=True（16 次 API 调用/15 动作/15 截图，33 文件哈希）；实跑需 ANTHROPIC key + 钉住 Demo 容器，本地不可行 |
| computer-use-open-model | `python main.py --dry-run`；`python validate_run.py <run 目录副本>` | PARTIAL | main.py, config.py, validate_run.py | dry-run 可打印脱敏端点配置（OPEN_MODEL_* 指向本地）；验证器 8 项内容检查全过，但 manifest 完整性门禁失败——归档 history.json/summary.json 与其自身 manifest 哈希漂移（既有问题，验证器 fail-closed 如实报告）；实跑需视觉模型 key |
| controllable-tts | `python markup.py`；`pytest test_fish_s1.py`；`python demo.py`（key 门禁） | BLOCKED(付费 Fish Audio S1) | tts.py, demo.py, test_fish_s1.py（markup.py 原已全中文） | 标记映射表 OK；8 测试全过（原生非语言标记/拼接鲁棒性/24 笛卡尔积/盲评聚合）；demo 在无 FISH_API_KEY 时正确报错退出 |
| end-to-end-speech | `python prepare_fixtures.py`；`python demo.py`；`python validate_evidence.py <evidence 副本>` | BLOCKED(需 NVIDIA CUDA GPU + MiniCPM-o 权重下载) | demo.py, speech_model.py, prepare_fixtures.py, validate_evidence.py | espeak 重生成 4 条 WAV 用例 OK（随后已 git 还原避免噪音）；demo 在无 CUDA 的 Mac 上按设计立即报错；验证器 9/10 过，implementation_hashes_match 失败（归档时实现文件已漂移，既有问题） |
| gemini-xlerobot-navigation | `python desktop_planner.py --output-dir <临时>`（3 种子×3 失败档×128 回合=3456 回合，MPS，8.5s）；`python validate_evidence.py <新证据>`；`pytest test_validator.py` | PASS（本地 GPU 桌面规划臂） | desktop_planner.py, validate_evidence.py | 证据 VALID：0.5 失败档开环 0.53 / 闭环 1.0 / 预测式 1.0，确定性重放 True，世界模型 MSE 达标；preflight 因上游 lerobot 仓库未检出按预期 blocked；真 Gemini/机械臂为 README 门禁化扩展，本地验收不含 |
| live-audio | `node backend/check-setup.js` | BLOCKED(需 npm 安装 + 付费 ASR/LLM/TTS + 浏览器麦克风) | backend/check-setup.js（无 py 文件，入口为 JS） | 预检通过：Node v24 / ffmpeg / silero_vad.onnx(2.2MB) / config 可加载；ASR/LLM/TTS 三家付费 key 缺失（预期）；完整运行需 npm install（协议禁止装依赖） |
| phone-agent | `pytest test_agent.py test_speech.py test_verify_acceptance.py test_webrtc_app.py`；/tmp 驱动跑 ReAct LLM 臂（经 /tmp 透明代理 8650） | PARTIAL | agent.py, speech.py, demo.py | 14 测试全过（规划契约/真实 TTS-ASR 收据/webrtc 应用）；补跑：json_object 400 由 /tmp 代理剥离后解除 → 对话轮（conversation_turn）真实 LLM 调用完整跑通（确认契约/边界句全对）；规划器（react_plan）请求被接受但 700 token 预算被推理模型耗尽（3/3 截断）；浏览器电话链路需麦克风+手机仍 BLOCKED(设备) |
| rgb-sim2real-grasping | `python pipeline.py --output-dir <临时>`（MPS，55s）；`python validate_evidence.py <新证据>`；`python preflight.py`；`pytest test_validator.py` | PASS | pipeline.py, preflight.py（robotics_lab_common.py 共享文件已加中文 docstring） | 证据 VALID：source_clean 源域 0.93；域随机化(full) 把目标域精度从 0.62→0.75（realistic）、0.61→0.78（bright）；数据重放一致；preflight 因上游仓库未检出按预期 blocked |
| streaming-speech | `pytest test_streaming.py test_whisper_baseline.py test_official_experiment.py`；`python prepare_scenarios.py <源 wav> <临时>` | BLOCKED(Qwen2-Audio-7B / Whisper 权重未下载本地) | demo.py, qwen2_streaming.py, whisper_baseline.py, run_official_experiment.py, prepare_scenarios.py | 6 过 1 败：官方 manifest 测试要求仓库内 `audio/sentence.wav`（未提交，既有缺口）；ffmpeg 三场景生成 OK；实跑需 6.5GB 模型下载，未执行 |
| xlerobot-teleoperation | `python teleop.py --output-dir <临时>`（5 种子×4 物体数×512 回合，MPS，1.6s）；`python validate_evidence.py <新证据>`；`python preflight.py`；`pytest test_validator.py` | PASS | teleop.py, preflight.py | 证据 VALID：20 格全 100% 成功（聚合 1.0 / 最差 1.0），确定性重放 True，2 工件哈希匹配；preflight 因上游 XLeRobot 未检出按预期 blocked |

## 各实验详细记录

### 1. agent-with-event-trigger（事件触发 Agent）
- 命令：`python event_loop_demo.py --mock --duration 10`；`env -u KIMI_API_KEY -u OPENROUTER_API_KEY LLM_PROVIDER=kimi python quickstart.py`；LLM 最小 harness（见下）
- 输出片段：
  ```
  ⏱️  [OneShotTimer(daily_backup_check)] 已注册：3 秒后触发
  🔁 [RecurringTimer(health_check)] 已注册：每 4 秒触发一次
  🟢 事件循环启动，将运行 10 秒，等待事件唤醒 Agent...
  ⚡ [OneShotTimer(daily_backup_check)] 触发事件 -> timer_trigger: 一次性定时器到期：…
  📥 事件循环取出第 1 个事件 -> 唤醒 Agent
  🤖 Agent 被唤醒，收到消息: [Timer daily_backup_check triggered] …
  🛠️  [模拟动作] 读取定时任务上下文 -> 执行例行检查 -> 汇报结果
  ✅ Agent 处理完成: 已响应 timer_trigger 事件
  ```
  LLM 最小运行（agent.py 的 provider 集合不含 openai，借 dashscope 分支的 `DASHSCOPE_BASE_URL` 覆盖指向本地 LM Studio，模型 qwen3.8-27b-splash，temperature=1）：
  ```
  agent model: qwen3.8-27b-splash
  Iteration 1..6  每次返回真实工具调用（ls / find 备份 / 读文件…）
  Tool Calls: 13   SUCCESS: False   FINAL_ANSWER: None
  ```
- 已注释文件：quickstart.py、agent.py、event_types.py（event_loop_demo.py 原本已全中文注释，未再动）
- 备注：LLM 循环、工具执行、系统提示全部真实运转；27B 模型在 6 轮预算内持续调用工具而未产出最终答案（模型收敛行为，非环境故障）。quickstart.py 的 server 全链路（8000 端口长驻）未做无界运行，仅验证 key 门禁分支。状态 PARTIAL。

### 2. astra-async-steering（Astra 异步转向）
- 命令：`python test_judging.py`；`python experiment.py --replay validation/runs/exp6-14-20260905-formal`；`python summarize.py validation/runs/exp6-14-20260905-formal`；`LOCAL_WS=ws://localhost:1234/v1/responses python _local_smoke.py`
- 输出片段：
  ```
  Ran 10 tests in 0.005s — OK
  { "replay_verified": true, "cases": 15, "all_passed": true }   (formal)
  summary: passed 15/15；async 组 independent_output_before_tool_ready=3
  [plain] EXCEPTION: InvalidStatus: server rejected WebSocket connection: HTTP 200
  ```
- 已注释文件：experiment.py、summarize.py、test_judging.py（_local_smoke.py 原有英文说明，保留）
- 备注：实跑臂需付费 gpt-6-astra + 硬编码 OpenAI 端点 → BLOCKED。另注意 `--replay pilot-20260905-v2` 会报 “Judgment changed: 01-sync”：pilot 归档时使用的 judge 比现行版本宽松（现行 judge 更严格、检查项更多），fail-closed 复核如实拒绝旧证据——属代码演进后的预期行为，非本次改动引起。

### 3. async-agent（异步运行时）
- 命令：`python demo.py`（parallel/interrupt/state）；`python demo.py scenarios --scenario 1`（LLM_MODEL=qwen3.8-27b-splash，OPENAI_BASE_URL 指向本地）；`pytest test_real_experiment.py test_real_tasks.py test_checkpoint_robustness.py`
- 输出片段（场景 1，本地 LLM + 真实子进程）：
  ```
  [  0.00s] USER | (immediate) 请运行终端命令 `python analyze_logs.py`（耗时日志分析）…
  [  2.20s] USER | (immediate) 现在几点了？
  [ 25.79s] TASK | 启动真实子进程任务 T1: `python analyze_logs.py` (速度 4%/逻辑秒)
  [ 28.02s] TASK | T1 … 进度 63% (pid=28879)   [29.43s] 进度 100%
  [ 29.44s] TASK | T1 完成 ✅ (pid=28879, returncode=0)
  [ 35.72s] AGENT | 日志分析任务已在后台启动（task_id=T1）。…请稍等。
  [ 54.75s] AGENT | 现在是 **2026年11月10日 07:06:24**。
  …最终输出 Markdown 分析表（行数/标题数/错误关键词/异步提及 + SHA-256）
  ```
- 离线 demo：`串行 4.51s / 并行 1.50s / 加速比 3.00x`；`python demo.py parallel` 重跑一致。
- 已注释文件：tasks.py、run_real_experiment.py（demo.py、async_demos.py、runtime.py、events.py 原已全中文）
- 备注：仓库根缺 `book/chapter4.md`（tasks.DEFAULT_INPUT 硬编码指向它），导致 demo 的 interrupt/state 演示与 `test_real_tasks.py` 2 个真实子进程测试 FileNotFoundError（既有缺口，14 过 2 败）；场景 1 的 LLM 运行是用临时替代文件在 harness 内注入后跑通的（未改实验代码）。状态 PARTIAL。

### 4. claude-computer-use-native（原生 Computer Use）
- 命令：`python validate_weather_run.py <validation/runs/exp6-7-…-v2 的临时副本>`（不动 validation/ 原件）
- 输出片段：
  ```
  "passed": true,  "failed gates": []
  "counts": {"api_calls": 16, "actions": 15, "screenshots": 15, "files_hashed": 33}
  ```
- 已注释文件：run_weather_task.py、validate_weather_run.py
- 备注：实跑需 ANTHROPIC_API_KEY + 钉住版本 Demo 容器（Docker）→ BLOCKED(付费+容器)。验证器对留存证据的全部门禁（模型身份/动作上限/收据/截图哈希/无凭证）通过。

### 5. computer-use-open-model（Qwen3-VL 开放模型臂）
- 命令：`OPEN_MODEL_API_KEY=local OPEN_MODEL_BASE_URL=http://localhost:1234/v1 python main.py --dry-run`；`python validate_run.py <临时副本>`
- 输出片段：
  ```
  dry-run: {"api_protocol": "openai-compatible-chat-completions", "base_url": "http://localhost:1234/v1",
            "requested_model": "qwen/qwen3-vl-32b-instruct", "schema_mode": "native", …}
  validate: status=failed（仅 existing_manifest_integrity=False）
            open_model_identity/real_api_receipts/bounded_read_only_actions/
            completed_within_limit/answer_grounded/step_screenshots/credential_scan 全部 True
  ```
- 已注释文件：main.py、config.py、validate_run.py
- 备注：manifest 完整性失败是因为归档的 history.json/summary.json 内容与归档 manifest 的哈希不一致（既有漂移，非本次运行产生；已直接对仓库原件核算哈希证实）。实跑需视觉模型 key（OpenRouter 或自部署）→ 该臂 BLOCKED，整体记 PARTIAL。

### 6. controllable-tts（Fish S1 可控 TTS）
- 命令：`python markup.py`；`pytest test_fish_s1.py`；`env -u FISH_API_KEY python demo.py`
- 输出片段：
  ```
  控制标记 -> 动作 映射表：[EMO:…] 切换情绪维度… [THINKING] 切到「思考/慢速/正式」+停顿…
  8 passed in 0.62s
  demo.py: error: Set FISH_API_KEY; this experiment has no substitute provider
  ```
- 已注释文件：tts.py、demo.py、test_fish_s1.py（markup.py 原已全中文）
- 备注：合成臂需付费 Fish Audio S1 → BLOCKED(付费 TTS)；解析/拼接/评审聚合等离线部分全部通过。

### 7. end-to-end-speech（MiniCPM-o 端到端语音）
- 命令：`python prepare_fixtures.py`；`timeout 90 python demo.py`；`python validate_evidence.py <临时副本>`
- 输出片段：
  ```
  fixtures: boxes-79.wav / tickets-42.wav / pace-fast.wav / pace-slow.wav（espeak 重生成 OK）
  demo: RuntimeError: MiniCPM-o 4.5 local precision run requires an NVIDIA CUDA GPU
  validate: passed=false —— 9/10 过，implementation_hashes_match=false（归档时实现文件已漂移，既有问题）
  ```
- 已注释文件：demo.py、speech_model.py、prepare_fixtures.py、validate_evidence.py
- 备注：本地为 Mac MPS 且未缓存模型权重 → BLOCKED(需 NVIDIA CUDA + 权重下载)；重生成的 WAV 已 `git checkout` 还原，避免污染仓库。

### 8. gemini-xlerobot-navigation（桌面操作规划 / 闭环策略比较）
- 命令：`python desktop_planner.py --output-dir <临时>`（默认协议：3 种子×0/0.25/0.5 失败档×128 回合）；`python validate_evidence.py <新证据>`；`pytest test_validator.py`
- 输出片段：
  ```
  "device": "mps" (Apple Metal, torch 2.13.0)   wall_time_ms ≈ 7~9s
  0.5 失败档: open_loop≈0.53 / closed_loop=1.0 / predictive=1.0（×3 种子）  deterministic_replay=True
  VALID: experiment 6-12 local GPU evidence    pytest: 3 passed
  ```
- 已注释文件：desktop_planner.py、validate_evidence.py（另给共享 robotics_lab_common.py 加了中文 docstring）
- 备注：本实验的本地验收臂是确定性桌面模拟 + 小型世界模型（README 明确不调用 Gemini API/不开串口），完整跑通并通过全部门禁 → PASS。preflight 因上游仓库未检出按预期 blocked；真实 Gemini+机械臂是单独门禁化扩展。

### 9. live-audio（级联语音聊天 Node 应用）
- 命令：`node backend/check-setup.js`
- 输出片段：
  ```
  ✅ Node v24.14.0  ✅ ffmpeg 8.1.2  ✅ silero_vad.onnx present (2273 KB)  ✅ config.js loaded
  ⚠️ ASR/LLM/TTS 三家付费 key 缺失  →  Prerequisites OK（退出码 0）
  ```
- 已注释文件：backend/check-setup.js（该实验无 py 文件，入口为 JS；README 为纯设计文档）
- 备注：完整运行需 npm install（协议禁止安装依赖）+ 付费 ASR/LLM/TTS + 浏览器麦克风 → BLOCKED。

### 10. phone-agent（浏览器外呼插件）
- 命令：`pytest test_agent.py test_speech.py test_verify_acceptance.py test_webrtc_app.py`；LLM 最小运行 harness（PHONE_MODEL_PROVIDER=openai + 本地端点）
- 输出片段：
  ```
  14 passed（规划契约 / 真实 say-ffmpeg TTS 收据 / Whisper ASR / webrtc 应用 23s）
  LLM: openai.BadRequestError 400 - {'error': "'response_format.type' must be 'json_schema' or 'text'"}
  ```
- 已注释文件：agent.py、speech.py、demo.py
- 备注：ReAct 臂硬编码 `response_format={"type":"json_object"}`，本地 LM Studio 端点不支持 → 该 LLM 臂 BLOCKED（不能改代码）；浏览器电话链路需麦克风+手机设备 → demo 记 BLOCKED(设备)；其余（测试、本地 TTS/ASR）通过 → 整体 PARTIAL。

### 11. rgb-sim2real-grasping（RGB 域迁移基准）
- 命令：`python pipeline.py --output-dir <临时>`（3 种子×4 随机化变体×4096 样本×10 epoch，MPS，55s）；`python validate_evidence.py <新证据>`；`python preflight.py --upstream /nonexistent`；`pytest test_validator.py`
- 输出片段：
  ```
  source_clean 源域精度 0.93
  目标域（无随机化 → 全随机化）: realistic 0.62 → 0.75   bright 0.61 → 0.78
  dataset_replay_match=True   VALID: experiment 6-13 local GPU evidence   2 passed
  preflight: status=blocked（上游 lerobot-sim2real 未检出，5 阶段全 blocked，符合预期）
  ```
- 已注释文件：pipeline.py、preflight.py（robotics_lab_common.py 共享文件已加中文 docstring）
- 备注：本地 GPU 基准完整跑通、域随机化改善迁移的结论复现 → PASS；SO-100 真机为门禁化扩展。

### 12. streaming-speech（Qwen2-Audio 增量感知 vs VAD+Whisper）
- 命令：`pytest test_streaming.py test_whisper_baseline.py test_official_experiment.py`；`python prepare_scenarios.py validation/scenarios/normal.wav <临时>`
- 输出片段：
  ```
  6 passed, 1 failed —— 失败项要求仓库内 audio/sentence.wav（未提交，FileNotFoundError，既有缺口）
  prepare_scenarios: normal.wav / long_pause.wav / background_noise.wav（ffmpeg 生成 OK）
  ```
- 已注释文件：demo.py、qwen2_streaming.py、whisper_baseline.py、run_official_experiment.py、prepare_scenarios.py
- 备注：实跑需 Qwen2-Audio-7B（6.5GB 快照）+ Whisper 检查点，本地缓存均无 → BLOCKED(模型权重未下载)；解析/VAD 单测与场景制备通过。

### 13. xlerobot-teleoperation（遥操作专家上界基准）
- 命令：`python teleop.py --output-dir <临时>`（5 种子×1-4 物体×512 回合，MPS，1.6s）；`python validate_evidence.py <新证据>`；`python preflight.py --upstream /nonexistent`；`pytest test_validator.py`
- 输出片段：
  ```
  20 cells  aggregate_success_rate=1.0  worst_cell=1.0  deterministic_replay=True
  VALID: experiment 6-10 local GPU evidence   3 passed
  preflight: status=blocked（上游 XLeRobot 未检出，符合预期）
  ```
- 已注释文件：teleop.py、preflight.py
- 备注：本地 GPU 基准完整跑通 → PASS；真实 XLeRobot 遥操作为 README 门禁化扩展（需硬件+授权+安全清单）。

## 合规说明

- 模型锁死：全部 LLM 请求仅使用 qwen3.8-27b-splash（本地 LM Studio）；付费 API（OpenAI/Astra、Anthropic、Gemini、Fish、OpenRouter、ARK 等）一律未调用。
- 未修改：`validation/` 目录（所有 validate 类脚本均在临时目录副本上运行）、任何 `*.json` 证据、`EXPERIMENT_LEDGER.md`、`pyproject.toml`、`uv.lock`、`.env`、其他章节。
- 未安装依赖、未 `git commit`。
- 注释只增/替换 docstring 与注释，无任何逻辑改动；每个实验注释后均重跑验证（其中 xlerobot 一处测试因 docstring 译掉 "local GPU" 一度失败，已在中文 docstring 中保留该英文词并复测 3 passed）。
- venv 状态：任务开始时 `uv sync --all-extras` 的后台进程已不在（transformers 已升至 5.17.0，其余同步包就位），未再触发「venv 同步中」阻塞；chapter6 无实验依赖缺失的 mem0ai。

## 本章统计

13 个实验 = 3 PASS（gemini-xlerobot-navigation、rgb-sim2real-grasping、xlerobot-teleoperation）
+ 4 PARTIAL（agent-with-event-trigger、async-agent、computer-use-open-model、phone-agent）
+ 6 BLOCKED（astra-async-steering:付费 Astra、claude-computer-use-native:付费 Anthropic+容器、
controllable-tts:付费 Fish S1、end-to-end-speech:需 CUDA GPU+权重、live-audio:npm 依赖+付费 API+浏览器、
streaming-speech:多 GB 模型权重未下载）

## 补跑记录（venv 同步后）

补跑时间：2026-11-10。任务：phone-agent 的 ReAct LLM 臂（此前被本地端点 `400 'response_format.type' must be
'json_schema' or 'text'` 拒绝，代码硬编码 `response_format={"type":"json_object"}`，不可改）。

### 解法（harness 级，仓库零改动）

`/tmp/jsonfmt_proxy.py`：透明反向代理 `127.0.0.1:8650 → 127.0.0.1:1234`，仅在转发时剥离请求 JSON 中的
`response_format` 参数（LM Studio 只收 json_schema/text；实验提示词本身要求 JSON，代码解析有兜底），
其余（头/体/SSE）原样透传。实验以 `OPENAI_BASE_URL=http://127.0.0.1:8650/v1` 指向它，
`PHONE_MODEL_PROVIDER=openai`、`OPENAI_API_KEY=not-needed`、`PHONE_PLANNER_MODEL=PHONE_DIALOGUE_MODEL=qwen3.8-27b-splash`
（模型锁死）。代理先经 curl 双测（普通请求 200；带 json_object 请求 200 而非 400）验证后投入。

### 命令与结果（/tmp/run_phone_react.py 驱动，最小规模 = 1 规划 + 1 对话轮；浏览器/麦克风链路未起）

```
$ python /tmp/run_phone_react.py
== react_plan（规划器，真实 LLM 经代理）==
  400 已消失（请求被接受、真实生成）；但 max_tokens=700（代码硬编码）被推理模型耗尽：
  3 次尝试 finish 均为 length（completion=700，reasoning 1480 字符 + content 1699 字符），
  content 为截断 JSON → json.JSONDecodeError: Unterminated string（char 1659）
== conversation_turn（模拟 ASR 后对话轮，真实 LLM 经代理）==
  { "assistant_message": "Got it. You've confirmed the dental checkup for Thursday at 3 PM
      with confirmation code 742. I've recorded both details locally.",
    "explicit_confirmation_observed": true, "should_complete": true,
    "completion": { "appointment_time": "Thursday 3 PM", "confirmation_number": "742",
                    "notes": "No external organization was contacted or booking made.",
                    "result": "Local confirmation recorded." },
    "dialogue_model": "openai:qwen3.8-27b-splash" }
  provider=openai | requested/provider_model=qwen3.8-27b-splash | finish=stop
  usage={completion:307(含 reasoning 222), prompt:242, total:549} | latency=9.46s
```
- 对话轮通过 agent.py 全部严格契约校验（should_complete 必须有显式确认 + 两关键字段 + 逐字边界句），
  且 `7 4 2` 正确归一化为 `742`——**ReAct 对话臂真实闭环**。
- 规划器（react_plan）400 解除但受代码硬编码 `max_tokens=700` 限制：qwen3.8-27b-splash 为推理模型，
  reasoning+content 合计必超 700 → 3/3 次 content 截断，无法解析。属「推理模型 × 硬编码 token 预算」
  环境/代码约束（不可改代码），该步记 BLOCKED(700 token 预算对推理模型不足)。
- 状态：整体维持 PARTIAL（浏览器电话链路仍需麦克风+手机设备）；其中 ReAct LLM 臂由
  「400 全拒」推进为「对话臂真实跑通 + 规划臂受 token 预算阻塞」。
