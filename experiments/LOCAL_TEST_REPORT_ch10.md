# 第 10 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

说明：本地 LM Studio 的 qwen3.8 端点只接受 `response_format.type ∈ {json_schema, text}`，而多个实验代码请求 `json_object` 会 400。为不改实验代码，使用本地透明代理 `127.0.0.1:8650`（仅剥离 json_object 参数，其余透传，模型仍为 qwen3.8-27b-splash）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| autonomous-phone-registration (10-3) | `python demo.py --headless --url http://127.0.0.1:8642/form.html --known-json ... --scripted-json ...`（+`pytest -q`） | PARTIAL | demo.py, orchestration.py, decision.py, bus.py | 真实 Chromium+真实 LLM 自主工具调用+问填并发全通过；语音媒体链路未跑（需付费 TTS/ASR 或 whisper 环境） |
| book-translation (10-2) | `python demo.py --sample-dir <1 章> --no-proofreading --skip-single`；`python run_official_experiment.py --provider openai --source sample_book/chapter3.md` | PARTIAL | demo.py, run_official_experiment.py, consistency_auditor.py | demo 1 章×2 Agent 跑通；official 双臂翻译完成、裁判环节 BLOCKED(付费 ARK/MISTRAL) |
| generative-agents (10-5) | `python validate_campaign.py <runs 副本>`；`python analyze_campaign.py <副本>`；`python launch_campaigns.py`（拒绝） | BLOCKED(缺上游克隆/无 embedding 服务/需付费 DASHSCOPE) | launch_campaigns.py, judge_plausibility.py, analyze_campaign.py | 群模拟本体不可本地跑；离线验证器 13/14 门禁（manifest 门禁为既有失败）；analyze 因 storage/ 未提交无法跑 |
| multi-role-transfer (10-1) | `python demo.py --scenario coding --max-steps 12`（+`--list-roles`） | PARTIAL | demo.py, orchestrator.py, roles.py, evaluation.py | triage→coding 真实移交链跑通；web_search 需付费 Tavily（coding 场景未触发）；--output 保存路径有潜在 bug |
| parallel-web-research (10-4) | `python demo.py --agents 2 --no-compare --timeout 90`（+`pytest -q`） | 待运行 | demo.py, sources.py, llm.py | 真实浏览器×免费 Stanford 站点×本地 LLM |
| staged-system-prompt (10-1 附加) | `python demo.py --max-revisions 1`（+`--list-stages`、`run_official_experiment.py`） | 待运行 | demo.py, run_official_experiment.py, simulated_user.py | 三阶段本地 LLM 最小运行；official 需付费 Moonshot |
| talkact-reproduction (10-3 基线) | `python validate_campaign.py validation/runs/exp10-3-talkact-anthropic-caller-20260803-v2` | PASS | validate_campaign.py | 16 局证据独立重算，passed=true（注意：验证器会写回 run 目录，复跑用副本） |
| voice-werewolf (10-6) | `python demo.py --ai-only ...`（+`pytest -q`） | 待运行 | demo.py | 文本/LLM 路径；语音 TTS/STT 需付费端点 |

## 各实验详细记录

### 1. autonomous-phone-registration（10-3）
- 命令：
  ```
  cd experiments/chapter10/autonomous-phone-registration
  OPENAI_BASE_URL=http://127.0.0.1:8650/v1 OPENAI_MODEL=qwen3.8-27b-splash OPENAI_API_KEY=*** \
    python demo.py --headless --url http://127.0.0.1:8642/form.html \
      --known-json '{"first_name":"Wei","last_name":"Li"}' \
      --scripted-json '{"email":"my email is wei dot li at example dot com","phone":"my phone number is 138 0013 8000","department":"Engineering","address":"my address is 500 spark avenue san francisco","birthday":"my birthday is january fifteenth 2000","company":""}'
  ```
  （本地 http 服务提供 8 字段测试表单；`--scripted-json` 为免音频的自动化通道）
- 输出片段：
  ```
  [Computer Agent] 已打开真实页面：Local Registration (ch10 test form) (http://127.0.0.1:8642/form.html)
  [Computer Agent] 发现 8 个可填写字段，其中 7 个必填
  [自主决策] tool_called=initiate_phone_call_agent; ...
  "filled": ["first_name","last_name","email","phone","birthday","department","address"]
  overlap_checks: 5/5 next_question_before_fill_completed=true
  gates: autonomy=pass, concurrency=pass, privacy=pass, cleanup=pass; webrtc/audio=not_run
  [资源清理] browser/context/page closed=True
  ```
  决策回执：model=qwen3.8-27b-splash, provider=OpenAI(本地), usage prompt=829/completion=346；
  模型自主选择 6 项缺失字段经「电话」收集，浏览器真实填写 7 字段、零错误。
- 已注释文件：demo.py（模块中文 docstring）、orchestration.py、decision.py、bus.py（模块+关键函数中文注释）。
- 备注：
  - 注释前 pytest 23/23 通过；注释后 4 个失败全部是「源码 hash 绑定 manifest」类验证器测试（manifest 绑定注释前源码字节，属注释副作用，非逻辑回归）。
  - 第一次运行（5 字段表单）模型自主决定「不打电话」（缺 3 项太少），exit 2 正常退出——这正是 tool_choice=auto 的自主性边界演示。
  - 完整语音验收（WebRTC+TTS/ASR）需付费 OpenAI/Gemini 语音端点或独立 whisper 环境，本地 BLOCKED(语音)；scripted 通道验证了编排/并发/脱敏全链路。

### 2. book-translation（10-2）
- 命令：
  ```
  python demo.py --sample-dir <temp:仅 chapter3.md> --out-dir <temp> --no-proofreading --skip-single
  python run_official_experiment.py --provider openai --source sample_book/chapter3.md --output-dir <temp>
  python -c "from consistency_auditor import audit_translation; ..."  # 审计 demo 真实译文
  ```
- 输出片段：
  ```
  Manager → Glossary Agent：读全书（1 章）抽取共享术语表
  Glossary Agent ✓：确定 9 个术语 → glossary.json（Manager 只记路径，术语表正文留在文件系统）
  Translation Agent ✓：chapter3_zh.md（上下文 499 tok，译文落盘不回传 Manager）
  Manager 上下文峰值（只存任务/计划/调用记录/文件索引）：511 tokens
  术语表：latency→时延, throughput→吞吐量, KV cache→KV缓存, token→词元, ...（9 项）
  ```
  official 最小版：双臂（4-角色 Manager 工作流 + 单 Agent）各 1 章 1 单元翻译完成并落盘后，
  `RuntimeError: Official translation quality judging requires ARK_API_KEY or MISTRAL_API_KEY`（裁判需付费端点）。
  consistency_auditor 对 demo 真实译文：terminology/code_blocks/latex_formulas/link_targets 全 1.0，is_consistent=true。
- 已注释文件：demo.py（原已有中文注释，模块级补充）、run_official_experiment.py（模块+make_judge+main 中文注释）、consistency_auditor.py（模块+入口中文 docstring）。
- 备注：注释后 pytest 22/23，唯一失败 `test_canonical_evidence_latest_pointer_and_all_declared_hashes_match` 是「源码 hash 绑定既有验收证据」类断言（注释改变源码字节所致，注释前 23/23）。--dry-run 离线预演（模型自动取 qwen3.8-27b-splash）通过。

### 3. generative-agents（10-5）
- 命令：
  ```
  python validate_campaign.py <validation/runs/exp10-5-qwen37flash-20260804-v1 的临时副本>
  python analyze_campaign.py <副本>
  python launch_campaigns.py --upstream <不存在> --output <空>   # 预期拒绝
  ```
- 输出/结果：
  - validate_campaign：14 门禁中 13 通过；`manifest_complete_and_valid=false`（既有问题：run 目录多个文件 hash 与 manifest.json 不符，如 environment.json 实际 510d1e… vs 声明 c9cdb0…，在未改动的干净副本上同样复现，非本次操作所致）。
  - analyze_campaign：`FileNotFoundError: .../storage/exp10_5_history_seed/personas`——提交的 run 目录不含 storage/（被 gitignore，只有压缩 states/），无法对提交证据重算。
  - launch_campaigns：`prepare the shared history seed before launching arms`（拒绝）。
- 已注释文件：launch_campaigns.py、judge_plausibility.py、analyze_campaign.py（模块+关键函数中文 docstring）。
- 备注：群模拟本体（run_campaign.py）要求 pin 到 fe05a71 的外部 generative_agents 克隆（仓库不存在该克隆），且 provider 需付费 DASHSCOPE（chat+embedding，本地无 embedding 服务、模型锁死单槽位）；judge_plausibility 固定调用付费 Anthropic Messages API。三入口均无本地可跑路径 → 整体 BLOCKED(无上游克隆/无 embedding 服务/需付费 API)；离线验证器部分已运行。

### 4. multi-role-transfer（10-1）
- 命令：
  ```
  python demo.py --list-roles        # 离线自检
  python demo.py --scenario coding --max-steps 12    # 最小 LLM 运行（本地无付费 Tavily，选纯代码场景）
  ```
- 输出片段：
  ```
  自主移交链: triage → coding
  移交次数: 1
  各角色分工: triage（仅路由/移交）; coding: execute_python ⇒ 产出最终回复
  最终成果: 斐波那契前 20 项 0,1,1,2,...,4181；和=10945（execute_python 真实执行）
  ```
- 已注释文件：demo.py、orchestrator.py、roles.py（原已有大量中文注释）、evaluation.py（模块中文 docstring）。
- 备注：
  - 首次带 `--output` 的运行在 save_evidence 崩溃：coding 场景的移交链不含 research，`chain.index("research")` 抛 ValueError（该验收门禁按 cagr 场景假设编写）——属代码潜在缺陷，与本地环境无关；不带 --output 的运行正常退出。
  - 默认 cagr/solar 场景的 web_search 工具硬性要求付费 TAVILY_API_KEY（代码注释明确「no mock fallback」），本地 BLOCKED(付费搜索)；coding 场景完全本地可跑。

### 5. parallel-web-research（10-4）
- 待补

### 6. staged-system-prompt（10-1 附加）
- 待补

### 7. talkact-reproduction（10-3 基线臂）
- 命令：`python validate_campaign.py validation/runs/exp10-3-talkact-anthropic-caller-20260803-v2`（离线，无 LLM）
- 输出：`"passed": true`（16 局 = 4 任务 × duplex/strawman × 2 种子；模型/回执/延迟统计等门禁全通过）
- 已注释文件：validate_campaign.py（模块+门禁段中文注释）
- 备注：⚠️ 该验证器会把重算后的 acceptance.json/manifest.json 写回传入的 run 目录（首次运行曾改写仓库 validation/ 下文件，已用 git checkout 恢复原状）；因此「注释后复跑」改为对临时副本执行，结果同样 passed=true。

### 8. voice-werewolf（10-6）
- 待补

## 本章统计

（运行结束后填写）
