# 第 10 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

说明：本地 LM Studio 的 qwen3.8 端点只接受 `response_format.type ∈ {json_schema, text}`，而多个实验代码请求 `json_object` 会 400。为不改实验代码，使用本地透明代理 `127.0.0.1:8650`（仅剥离 json_object 参数，其余透传，模型仍为 qwen3.8-27b-splash）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| autonomous-phone-registration (10-3) | `python demo.py --headless --url http://127.0.0.1:8642/form.html --known-json ... --scripted-json ...`（+`pytest -q`） | PARTIAL | demo.py, orchestration.py, decision.py, bus.py | 真实 Chromium+真实 LLM 自主工具调用+5/5 问填并发+脱敏全通过；语音媒体链路未跑（需付费 TTS/ASR 或 whisper 环境） |
| book-translation (10-2) | `python demo.py --sample-dir <1 章> --no-proofreading --skip-single`；`python run_official_experiment.py --provider openai --source sample_book/chapter3.md` | PARTIAL | demo.py, run_official_experiment.py, consistency_auditor.py | demo 1 章×2 Agent 跑通；official 双臂翻译完成、裁判环节 BLOCKED(付费 ARK/MISTRAL) |
| generative-agents (10-5) | `python validate_campaign.py <runs 副本>`；`python analyze_campaign.py <副本>`；`python launch_campaigns.py`（拒绝） | BLOCKED(缺上游克隆/无 embedding 服务/需付费 DASHSCOPE) | launch_campaigns.py, judge_plausibility.py, analyze_campaign.py | 群模拟本体不可本地跑；离线验证器 13/14 门禁（manifest 门禁为既有失败）；analyze 因 storage/ 未提交无法跑 |
| multi-role-transfer (10-1) | `python demo.py --scenario coding --max-steps 12`（+`--list-roles`） | PARTIAL | demo.py, orchestrator.py, roles.py, evaluation.py | triage→coding 真实移交链+execute_python 跑通 exit 0；web_search 需付费 Tavily（coding 场景未触发）；--output 保存路径有潜在 bug |
| parallel-web-research (10-4) | `python demo.py ...`（3 轮：真实 Stanford 站×2 + 本地双页×1；+`pytest -q`） | PASS | demo.py, sources.py, llm.py | 真实浏览器×本地 LLM 证据型抽取×级联终止(1 次广播)×ack 齐全×资源审计 2/2 关闭 |
| staged-system-prompt (10-1 附加) | `python demo.py --max-revisions 1 --start-stage implementation`（+`--list-stages`、`run_official_experiment.py`、`pytest`） | PARTIAL | demo.py, run_official_experiment.py, simulated_user.py | 实现阶段(228 行代码+3 项自测)+审查 3 项客观检查全过；最终批准轮超时间预算 kill；official 需付费 Moonshot |
| talkact-reproduction (10-3 基线) | `python validate_campaign.py validation/runs/exp10-3-talkact-anthropic-caller-20260803-v2` | PASS | validate_campaign.py | 16 局证据独立重算 passed=true（注意：验证器会写回 run 目录，复跑用副本） |
| voice-werewolf (10-6) | `python demo.py --ai-only --players 5 --wolves 2 --max-rounds 2`（+`pytest -q`） | PARTIAL | demo.py | 文本/LLM 完整一局（狼人胜）+信息隔离 4/4 通过；语音 TTS/STT 需付费端点 → BLOCKED(付费语音) |

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
- 命令：
  ```
  python demo.py --agents 2 --no-compare --timeout 90 --output <temp>          # 默认真实 Stanford 站点
  python demo.py --sites-json <含目标姓名站点> --agents 3 --no-compare --timeout 90
  python demo.py --sites-json <本地双页: ng.html 含姓名 / nobody.html 不含> --agents 2
  ```
  （+`pytest -q`）
- 输出片段：
  ```
  run1(默认2站):  并行 4.5s；resource_audit created=2 closed=2；
                  not_found: medicine-profiles / law-faculty（渲染页不含目标姓名，确定性门禁正确拦截）
                  资源清理：PASS; 单次级联广播：PASS   EXIT 0
  run2(3个真实站): profiles.stanford.edu 站点加载超 105s 工作时限（站点慢）→ 该 worker 超时关闭；
                  其余 2 站 not_found；3 上下文全部关闭   EXIT 0
  run3(本地双页, --timeout 300):
      outcome=found; winner=agent-00(local-profile)
      profile: found=true, name=Andrew Ng, position=Professor of Computer Science (Emeritus),
               research=machine learning, deep learning, ..., evidence=页面逐字摘录
               provider=openai(本地), url=http://127.0.0.1:8642/ng.html
      agent-01(local-directory): 确定性门禁「页面不含姓名」→ not_found（未触发 LLM）
      terminate_broadcasts=1（向落败方广播终止）; missing_acks=[]; errors={}
      parallel_seconds=149.6（其中 LLM 抽取 ≈140s，本地 27B 推理慢）
      资源清理：PASS; 单次级联广播：PASS   EXIT 0
  ```
- 已注释文件：demo.py、sources.py、llm.py（模块+入口中文 docstring）。
- 备注：
  - 真实免费 Stanford 站点两轮实测中：页面或加载超 105s（站点慢，worker 超时机制按设计关闭会话）、
    或目标姓名靠客户端渲染注入（初始 DOM 无姓名）→ 确定性「姓名存在门禁」使 LLM 抽取未触发
    （这正是该门禁的设计行为，防模型用参数化记忆编造画像）。
  - 完整链路（真实 Chromium 双上下文 + 本地 LLM 证据型抽取 + 级联终止 + ack + 资源审计）
    由本地双页（含姓名/不含姓名）补跑验证，全部通过。

### 6. staged-system-prompt（10-1 附加）
- 命令：
  ```
  python demo.py --list-stages                  # 离线（通过）
  python run_official_experiment.py             # 预期：MOONSHOT_API_KEY is required（付费，立即退出）
  python demo.py --max-revisions 1              # 全程三阶段（第一次尝试，超 20 分钟未结束，kill）
  python demo.py --max-revisions 1 --start-stage implementation   # 最小规模验证
  ```
  （+`pytest -q` 11/11 通过）
- 输出片段（最小规模运行）：
  ```
  进入阶段：implementation | 角色：软件工程师 | 可用工具：['write_file','read_file','execute_code','submit_for_review']
  [软件工程师] 写文件: organize_downloads.py（5186 字符，228 行）
  [软件工程师] 执行代码自测: …… 14 个文件全部正确归类 / 冲突加 _1 / move 后原文件消失 …… 全部通过
  [软件工程师] 提交审查 -> 转交审查: organize_downloads.py
  进入阶段：review | 角色：代码审查员
  [代码审查员] run_linter: 通过；run_tests: PASS；analyze_complexity: 函数=6 分支=13 最大嵌套=2
  [代码审查员] 读文件: organize_downloads.py   ← 其后最终 approve 轮在时间预算内未完成，按协议 kill
  ```
- 已注释文件：demo.py、run_official_experiment.py（模块中文 docstring）、simulated_user.py（原已全中文）。
- 备注：
  - 共享对话历史跨阶段保留、阶段切换（提示词+工具集随阶段更换）在日志中清晰可辨；
    实现阶段产物与三项客观审查全部真实执行（linter/冒烟测试/复杂度）。
  - 本地 27B 推理模型单轮耗时过长（长推理链），完整三阶段 + 最终批准超出时间预算 → 记 PARTIAL（已完成：实现+自测+提交+审查三项客观检查；未完成：最终 approve 决策轮）。
  - official 入口写死 Moonshot 付费后端，本地 BLOCKED(付费 API)。

### 7. talkact-reproduction（10-3 基线臂）
- 命令：`python validate_campaign.py validation/runs/exp10-3-talkact-anthropic-caller-20260803-v2`（离线，无 LLM）
- 输出：`"passed": true`（16 局 = 4 任务 × duplex/strawman × 2 种子；模型/回执/延迟统计等门禁全通过）
- 已注释文件：validate_campaign.py（模块+门禁段中文注释）
- 备注：⚠️ 该验证器会把重算后的 acceptance.json/manifest.json 写回传入的 run 目录（首次运行曾改写仓库 validation/ 下文件，已用 git checkout 恢复原状）；因此「注释后复跑」改为对临时副本执行，结果同样 passed=true。

### 8. voice-werewolf（10-6）
- 命令：
  ```
  python demo.py --ai-only --players 5 --wolves 2 --max-rounds 2 --report <temp>
  python -m pytest -q        # 5 个测试文件
  ```
- 输出片段（独立重跑，`--ai-only --players 5 --wolves 2 --max-rounds 2`，EXIT 0）：
  ```
  模式：在线全 AI 补充诊断 | 模型：qwen3.8-27b-splash | 音频输入：关
  真实身份表: P1 女巫 / P2 狼人 / P3 预言家 / P4 村民 / P5 狼人
  【第 1 回合 · 夜晚】…（全部 LLM 决策真实走本地端点）
  [校验1] 『狼人队友身份』只进狼人上下文：通过 ✓
  [校验2] 『预言家查验结果』只进预言家本人上下文：通过 ✓
  [校验3] 审计日志中狼人专属信息可见集合 == 狼人集合：通过 ✓
  [校验4] 所有『公开-*』信息可见集合 == 全体玩家：通过 ✓
  信息隔离总校验：全部通过 ✓✓✓
  最终结果：狼人阵营 获胜。  验收报告: …/exp8_report.json | SUPPLEMENTAL_ONLY
  ```
  报告关键字段：information_isolation=pass、winner 由游戏规则判定=pass；
  语音/真人相关门禁=not_run（补充诊断路径，符合预期）；strategy_audit 在 2 回合最小局未达标（记录在案）。
- 已注释文件：demo.py（模块+run_game 中文注释；原文件已含大量中文注释）。
- 备注：
  - 首次运行与 staged 并发争用 LM Studio，首个 LLM 调用触发 45s 客户端超时（env WEREWOLF_LLM_TIMEOUT）崩溃；
    独立重跑（超时放宽至 300s）完整跑通。
  - 语音回环（--voice / --simulate-user / 真人麦克风，TTS/ASR）依赖 OpenAI/Gemini/OpenRouter 付费端点
    → BLOCKED(付费语音)；文本/LLM 路径与 pytest 按协议照常运行（33 通过 / 1 既有失败，见下）。
  - pytest 唯一失败 `test_exp106…::test_latest_formal_run_passes_every_gate_in_one_report` 为**既有**失败：
    提交的 independent_validation.json 记录的 source_report_sha256（655b4e…）与提交的 acceptance_report.json
    实际 hash（190a26…）不一致（在未改动的 git 干净副本上复现，与本次注释/运行无关）。

## 本章统计

8 个实验 = **2 PASS**（parallel-web-research、talkact-reproduction）
+ **5 PARTIAL**（autonomous-phone-registration、book-translation、multi-role-transfer、staged-system-prompt、voice-werewolf）
+ **1 BLOCKED**（generative-agents：缺上游克隆/无 embedding 服务/需付费 API，离线验证部分已跑）。

### 通用说明

1. **模型锁死**：所有 LLM 请求仅发往本地 `qwen3.8-27b-splash`；每次 LLM 实验前先 curl 探测
   （一次探测发现 LM Studio 对 `response_format.type=json_object` 返回 400，用 127.0.0.1:8650
   透明代理剥离该参数解决，模型/端点不变）。未请求任何其他模型 id。
2. **时间预算**：本地 27B 推理模型单轮可达 2~5 分钟（长推理链），个别实验实际耗时超过
   8 分钟阈值；超预算者按协议 kill 并记 PARTIAL（staged 最终批准轮、werewolf 首次并发超时）。
3. **注释副作用（重要）**：若干实验的测试/验证器把「源码文件 SHA-256」绑定在既有验收
   manifest/证据中。按任务要求添加中文注释后源码字节改变，以下测试随之失败（注释前全绿，
   属预期副作用而非逻辑回归）：
   - autonomous-phone-registration：`test_exp103_validation_evidence.py`、`test_validate_acceptance.py` 共 4 项（注释前 23/23）；
   - parallel-web-research：`test_official_experiment.py::test_official_manifest_binds_artifacts_and_runtime_sources`（注释前 13/13）；
   - book-translation：`test_official_experiment.py::test_canonical_evidence_latest_pointer_and_all_declared_hashes_match`（注释前 23/23）。
4. **既有失败（与本次操作无关，在未改动的 git 干净副本上复现）**：
   - voice-werewolf `test_exp106_…` 1 项：提交的 independent_validation.json 所记 hash 与提交的
     acceptance_report.json 实际 hash 不一致（33 通过 / 1 失败）；
   - generative-agents validate_campaign 的 `manifest_complete_and_valid` 门禁：run 目录多个文件
     hash 与 manifest.json 声明不符（13/14 门禁，passed=false）。
5. **validation/ 目录保全**：generative 与 talkact 的验证器会把重算结果写回传入的 run 目录
   （首次运行曾改写仓库 validation/ 下 2 个文件，已 `git checkout` 恢复原状）；「注释后复跑」
   一律对 /var/folders 下临时副本执行，仓库 validation/ 保持零改动（git status 已复核）。
   所有实验运行产物（trace/report/证据 JSON）均输出到 /var/folders/.../ch10/ 临时目录，未污染仓库。
6. 禁止事项遵守：未改 validation/、*.json 证据、EXPERIMENT_LEDGER.md、.env、pyproject/lock；
   未装新依赖（仅下载 Playwright chromium 浏览器二进制，任务明确允许）；未调用任何付费 API；
   未 git commit。
