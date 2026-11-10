# 第 5 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1（单槽位，期间与其他会话共享、排队延迟 1~40s 不等），venv=/Users/fx/wk/github/agent/.venv（Python 3.12），macOS，node v24 / ffmpeg 可用；postgres:5432 未运行，ComfyUI:8188 未运行。

通用说明（harness 级补丁，**均只存在于 /tmp 驱动脚本，仓库实验代码零改动**）：
- `/tmp/lm_longtimeout.py`：monkeypatch `OpenAI.__init__` timeout→600s，兼容 LM Studio 排队。
- LM Studio 不支持 `response_format={"type":"json_object"}`（400），`/tmp/run_logd.py` 从请求中摘除该参数（实验提示词本就要求 JSON 且解析有兜底）。
- LM Studio 不支持 function 级 `tool_choice` 对象（400 "Invalid tool_choice type: 'object'"），`/tmp/run_cui.py` 映射为 `"required"`（工具白名单仅 1 个，语义等价）。
- venv 未安装：`cadquery`、`trimesh`、`bs4`(beautifulsoup4)、`fitz`(PyMuPDF)、`playwright`、`psycopg2`、`anthropic`（coding-agent 驱动中给空模块 stub）。按协议不安装。
- 本地模型对**图像输入**返回空/不支持，`tool_choice` 对象与 `json_object` 响应格式不支持（实测）。

实验编号按 `EXPERIMENT_LEDGER.md`（部分文件 docstring 里是旧书稿编号，如 agent-creator 文件内写 5-13、ledger 为 5-16）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| adaptive-log-parser (5-10) | `demo.py --quick --offline` / `--quick`(真实LLM) | PASS | 已含中文注释，未重复添加 | 离线全闭环 OK；真实 LLM 自愈竖线格式成功，解析器持久化到 `parsers/pipe_parser.py` |
| agent-creator (5-16) | `pytest test_creator.py` / `demo.py --no-live`(+`--resume`×3，`AGENT_CREATOR_REQUEST_TIMEOUT=3600`) | PARTIAL | demo.py, validator.py, creator.py | pytest 17 过；template 臂 1 次调用 78s 全部闸门通过；scratch 臂 9 文件全部由本地模型生成（checkpoint status=generated），编译 OK + 契约/领域测试 21/21；仅「CLI 标志须在 main.py」静态闸未过（标志实际在 agent.py 内），自动修复通道受本地模型 JSON 截断限制 |
| cad-vs-diffusion (5-9) | 离线自检（/tmp 驱动，ast 抽取绘图函数） | BLOCKED(缺依赖: cadquery, trimesh；`llm.py` 预存语法错误；视觉绘图需 ComfyUI/Gemini 未运行) | 已含中文注释，未重复添加 | `validate_manifest` 门控 + `flange_spec` + 程序化 matplotlib 绘图均通过 |
| code-for-logic (5-4) | `demo.py --limit 1 --mode both` / `pytest` / `build_puzzles.py --generate 5` | PASS | 已含中文注释，未重复添加 | 求解器 12/12；LLM 两臂均正确(kk01)；合并跑有 1 个预存跨文件 `sys.modules` 污染问题（已记录） |
| code-for-math (5-3) | `demo.py --selfcheck` / `--limit 1 --mode both` / `pytest` / `build_aime_2024.py` | PASS | build_aime_2024.py | selfcheck 11/11；LLM 两臂均 925 ✓；AIME 2024 基准下载构建 30 题成功（revision 锁定） |
| coding-agent（ledger 未编号） | 驱动：本地端点跑「写 hello.py 并运行」 | PASS | agent.py, config.py, hello_world.py | 本地模型 Write+Bash 完成 hello.py 并输出 `Hello, Agent`，done |
| conversational-ui (5-14) | `demo.py --quick --no-build`（tool_choice 补丁）/ `pytest` | PARTIAL(vite 构建未验证: 无 node_modules；浏览器 campaign 需 playwright) | 已含中文注释，未重复添加 | LLM 将主色改为 `#2563eb` 写回 theme.css，断言通过；pytest 8 过 |
| dynamic-form (5-12) | 无（模块级 import bs4 即失败） | BLOCKED(缺依赖: bs4/beautifulsoup4；campaign 需 playwright) | 已含中文注释，未重复添加 | demo 与 pytest 均无法收集（bs4 缺失） |
| erp-agent (5-13) | `demo.py gold` / `demo.py run --only 1 --model qwen3.8-27b-splash` / `pytest` | PASS | 已含中文注释，未重复添加 | gold 10/10；LLM 生成 SQL 与参考一致（886.20 天）；pytest 4 过 |
| log-diagnosis (5-11) | `demo.py --smoke` / 全流程（response_format 补丁）/ `pytest` | PASS | 已含中文注释，未重复添加 | smoke 3/3+3/3；全流程 2 次真实 LLM 调用：3 问题→3 用例→重放复现 3/3、修复后 2/3（RT-002 为模型生成的断言与内置修复不匹配，属模型输出质量）→mock GitHub 3 Issue；pytest 6 过 |
| paper-to-ppt (5-6) | 驱动：make_figures + Proposer 本地 LLM | PARTIAL(Slidev 渲染/Vision 审查 BLOCKED: 缺 fitz/playwright；本地模型无视觉) | paper_source.py | 本地 LLM 2 次调用生成 20 页 slides.md（峰值 prompt 3532 tokens） |
| paper-to-video (5-7) | `demo.py --offline --limit 1` / 讲解词 LLM 驱动 / `pytest` | PARTIAL(TTS 为付费 OpenAI tts-1) | 已含中文注释，未重复添加 | ffmpeg 全流水线 OK（19.6s lecture.mp4）；本地 LLM 讲解词正常；pytest 9 过 |
| permission-embedded-data-objects (5-15) | `pedo.core.models` 冒烟 | BLOCKED(缺依赖: psycopg2；无本地 PostgreSQL) | demo.py, pedo/core/models.py, pedo/core/store.py | models 纯数据模块冒烟 OK（规则 matches 命中）；demo/tests 需数据库无法运行 |
| provider-failover (5-1/5-2) | `pytest tests` / `run_handoff.py --pairs kimi:anthropic --arms neutral`（KIMI 指向本地） | PASS | 已含中文注释，未重复添加 | pytest 23 过；本地 kimi 臂真实执行 3 次工具调用，切换到死端点干净记录「缺少 ANTHROPIC_API_KEY」，重复调用 0 |
| small-model-codified-rules (5-5) | `demo.py --selftest` / `--task TB009 --mode both` / `pytest` | PASS | 已含中文注释，未重复添加 | selftest OK；LLM 两臂 TB009 均正确拒绝（1/1，违规 0）；pytest 4 过 |
| video-edit (5-8) | `demo.py --smoke` / `--quick`(LLM) / `pytest` | PARTIAL(视觉定位 BLOCKED: 本地模型对图像输入返回空) | 已含中文注释，未重复添加 | smoke 剪辑链路+bpy 脚本 OK；文本解析 OK（目标=冲浪场景），vision 步骤返回空；pytest 18 过 |

**汇总：16 = 8 PASS + 5 PARTIAL + 3 BLOCKED**

## 各实验详细记录

### adaptive-log-parser (5-10)
- 命令：`demo.py --quick --offline`；`OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 demo.py --quick`（/tmp 驱动）
- 输出片段：
```
（--offline 离线模式：用预置解析器代替 OpenAI，无需 API Key，机制完全一致）
当前已注册解析器：['builtin_json']
...
演示结束
新格式 A（竖线分隔）自愈结果：成功
新格式 B（嵌套括号）：--quick 模式已跳过
持久化复用（混合格式全部解析）：成功
已学会并持久化的解析器目录: .../adaptive-log-parser/parsers
```
- 已注释文件：demo.py / agent.py / engine.py / tester.py 均已含完整中文注释，未重复添加。
- 备注：真实 LLM 运行生成的解析器持久化为 `parsers/pipe_parser.py`（demo 设计内的产物）；离线与真实 LLM 两条路径均跑通，判 PASS。

### agent-creator (5-16)
- 命令：`pytest test_creator.py -q`；`AGENT_CREATOR_PROVIDER=openai AGENT_CREATOR_MODEL=qwen3.8-27b-splash OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 [AGENT_CREATOR_REQUEST_TIMEOUT=3600] demo.py --no-live --output /tmp/agent_creator_local`（+`--resume` 补跑 ×3；超时值用实验自带环境变量上调，代码零改动）
- 输出片段：
```
template 臂: generation 1 次调用, 78.1s, 466/887 tokens
  validation: structural_ok=true compile_ok=true tests_ok=true ok=true errors=[]
scratch 臂(第1~3次运行): 600s 客户端超时下逐文件推进，分别止步于 tests/test_contract.py、
                     tests/test_domain_tools.py（本地模型生成慢 + 共享服务排队）
scratch 臂(第4次运行, 超时上调 3600s): 全部 9 个文件生成完毕，checkpoint status=generated
  随后修复调用 3/3 次返回被 7000 token 上限截断的 JSON（Unterminated string ~char 13.5k）
  -> official_complete=false, result_claim=inconclusive_incomplete_campaign
独立核验（实验自带 validator + 直接 pytest，均离线）:
  structural_ok=False（main.py 为 4 行薄封装；--task/--model/--history-json 实际在 agent.py，静态闸只查 main.py）
  compile_ok=True  tests_ok=True（tests/ 直接 pytest: 21 passed）
```
- 已注释文件：demo.py（入口）、creator.py（核心）、validator.py（核心）；test_creator.py 未加（非入口/核心）。文件内保留旧书稿编号 5-13（原样字符串常量）。
- 备注：pytest 17 过。template 臂完整验证通过（1 次调用生成 domain_spec，结构/编译/测试闸门全绿，0 修复尝试）。scratch 臂经多次断点续跑由本地模型**完整生成全部 9 个文件**（7 个文件组：agent.py/domain_tools.py/main.py/tools.json/system_prompt.md/requirements.txt/README.md/tests 两个测试文件）：全部 Python 编译通过，契约+领域测试 21/21 通过；唯一未过闸门是「CLI 标志必须出现在 main.py」的静态检查——模型按生成提示词把 main.py 写成 4 行薄封装（标志在 agent.py，功能等价），属静态闸的形态要求而非功能缺陷。自动修复通道无法完成：修复提示要求「只返回需修改文件」的 JSON 信封，但本地 27B 模型 3/3 次把全部文件重发、在 7000 token 上限处截断。demo 诚实记录 `official_complete=false` 非零退出。判 PARTIAL：两臂生成/验证核心机制（协议冻结+哈希、验证→修复循环、逐调用留证、断点 resume）均已真实验证；未达 official_complete 的原因是 live 冻结用例未跑（`--no-live`，本地共享服务排队成本过高）+ 上述修复通道受本地模型输出长度行为限制。

### cad-vs-diffusion (5-9)
- 命令：`/tmp/run_cadvs_offline.py`（ast 抽取 `draw_procedural_plant`，产物写 /tmp）
- 输出片段：
```
SPEC_M5: {'outer_diameter_mm': 80.0, 'thickness_mm': 10.0, 'hole_count': 4, ...}
validate_manifest: 最小合法 manifest 通过
validate_manifest: 缺 gate 正确拦截 → gates 缺 receipts_complete
procedural plant drawn: .../cadvs_*/plant_procedural.png 42861 bytes
```
- 已注释文件：该实验全部文件已含中文注释，未重复添加。
- 备注（阻塞原因）：① venv 缺 `cadquery`、`trimesh`，CAD 路径无法构建；② **预存 bug**：`llm.py` 约 52-64 行 `try:` 块只有裸 `raise` 而**没有 except 子句**（SyntaxError，import 即失败；提交 3e05b43 原样带入）。按「只加注释不改逻辑」规则不修复，已在报告中记录；③ 图像分支需 ComfyUI(8188 未运行) 或付费 Gemini。离线可验证部分（manifest 门控、规格常量、程序化绘图）全部通过，判 BLOCKED。

### code-for-logic (5-4)
- 命令：`demo.py --limit 1 --mode both --model qwen3.8-27b-splash --provider openai --output /tmp/last_run_cfl.json`；`pytest`（逐文件）；`build_puzzles.py --generate 5`
- 输出片段：
```
== 纯思考(pure) ==  [pure ] kk01 (2人) ✓  预测={'A': 'knight', 'B': 'knave'}
== 代码辅助(code) == [code ] kk01 (2人) ✓  预测={'A': 'knight', 'B': 'knave'}
准确率  纯思考 100.0% (1/1)   代码辅助 100.0% (1/1)
```
- 已注释文件：demo.py / csp_solver.py / sandbox.py / build_puzzles.py 均已含中文注释，未重复添加。
- 备注：求解器自洽 12/12；`build_puzzles --generate 5` 唯一解校验通过。合并跑全部 test 文件时有 1 个失败，系**预存**跨文件 `sys.modules` 污染（某测试注入假 `csp_solver` 模块影响后续文件），逐文件跑全部通过，判 PASS。

### code-for-math (5-3)
- 命令：`demo.py --selfcheck`；`demo.py --limit 1 --mode both`（本地 LLM）；`pytest`；`build_aime_2024.py --output /tmp/aime_2024.json`
- 输出片段：
```
[ 1] number theory (inclusion-exclusion)  (真值=925)
  执行结果: answer: 925  brute force: 925
  纯CoT 预测=925 ✓ | 代码辅助 预测=925 ✓ (工具调用 1 次)
参考解命中真值：11/11  全部通过：沙箱可用，题库真值自洽
```
- 已注释文件：build_aime_2024.py（新增模块 docstring + 关键函数注释）；demo.py / sandbox.py 已含中文注释。
- 备注：pytest 6 过。`build_aime_2024.py` 实测从 HuggingFace 下载锁定 revision 的官方数据，30 题构建 + 清单 sha256 成功：`{"problems": 30, "revision": "2fe88a2f..."}`。判 PASS。

### coding-agent（ledger 未编号）
- 命令：`/tmp/run_coding_agent.py`（驱动：openai provider + base_url=本地端点 + anthropic 空模块 stub，任务=写 hello.py 并 Bash 运行验证）
- 输出片段：
```
[tool_call] Write {'file_path': '.../hello.py', 'content': 'def greet...
[tool_done] Write -> ''
[tool_call] Bash {'command': 'python3 hello.py', ...}
[tool_done] Bash -> 'Hello, Agent'
[done] agent finished
```
- 已注释文件：agent.py（模块 docstring + 主循环/流式块处理/格式转换注释）、config.py（resolve 兜底逻辑注释）、hello_world.py（模块 docstring）。
- 备注：注释后重跑一次（run2）验证：Agent 再次创建 hello.py、Bash 运行输出 `Hello, Agent`、`greet(name)` 定义正确、done 正常结束。判 PASS。

### conversational-ui (5-14)
- 命令：`MODEL=qwen3.8-27b-splash` + `/tmp/run_cui.py`（`demo.py --quick --no-build` + tool_choice 补丁）；`pytest test_customize_*.py`
- 输出片段：
```
第 1 轮 NL 定制需求：把发送按钮和用户消息气泡的主题色从绿色改成蓝色，用 #2563eb 这个蓝。
[改动文件] src/theme.css
  -  --color-primary: #16a34a;  +  --color-primary: #2563eb;
断言：源码中出现蓝色值 #2563eb -> 通过 ✅
多轮定制总结：全部通过 ✅
```
- 已注释文件：demo.py / agent.py / campaign_browser.py 均已含中文注释，未重复添加；`frontend/src` 运行后已从 `baseline/` 还原。
- 备注：pytest 8 过。vite build 无法验证（`frontend/` 无 node_modules，协议不允许安装依赖）；`campaign_browser` 需 playwright（未装）。核心「NL→代码修改→断言」闭环用真实本地 LLM 跑通，判 PARTIAL。

### dynamic-form (5-12)
- 命令：无（`demo.py` 模块级 `from bs4 import BeautifulSoup` 即 ModuleNotFoundError；pytest 收集同样失败）
- 已注释文件：demo.py / campaign.py 等均已含中文注释，未重复添加。
- 备注（阻塞原因）：venv 缺 `bs4`/`beautifulsoup4`（协议禁止安装）；campaign 还需 playwright。离线模式也因 import 失败无法运行，判 BLOCKED(缺依赖)。

### erp-agent (5-13)
- 命令：`demo.py gold`；`demo.py run --only 1 --model qwen3.8-27b-splash`；`pytest test_parse_only.py`
- 输出片段：
```
【问题 1】平均每个员工在职多久？
  生成的 SQL： SELECT AVG(julianday(COALESCE(leave_date, date('now'))) - julianday(hire_date)) ...
  查询结果： | 886.20 |  校验：通过 ✓（结果一致）
  总通过率：1/1 (100%)
（gold：总通过率 10/10）
```
- 已注释文件：demo.py / agent.py / gold.py / questions.py 均已含中文注释，未重复添加。
- 备注：pytest 4 过。`campaign_postgres`（docker）仅记录未运行。判 PASS。

### log-diagnosis (5-11)
- 命令：`demo.py --smoke`；`/tmp/run_logd.py`（全流程，摘除 json_object response_format）；`pytest`
- 输出片段：
```
步骤 1｜Agent 诊断（真实调用 OpenAI）
  [问题 1] 退款流程跳过强制前置校验 verify_refund_eligibility (P0, R1)
  [问题 2] 支付网关重试无退避且最终失败被误报为成功
  [问题 3] check_stock 延迟 8300ms 超阈值未触发降级
步骤 3｜重放：(A) 复现 bug 3/3；(B) 修复后通过 2/3（RT-002 例外）
步骤 4｜(mock) 已将 3 个 Issue 写入 output/github_issues.json
```
- 已注释文件：demo.py / diagnoser.py / replay.py / github_mcp.py 均已含中文注释，未重复添加。
- 备注：smoke 3/3+3/3；pytest 6 过。RT-002 在「修复后」重放仍 FAIL：本地模型生成的断言（期望 final_status=failed）与该实验内置修复（修复后成功）语义不符，属模型输出质量差异而非流水线缺陷——流水线机制（诊断→用例→双向重放→GitHub mock）完整跑通，判 PASS。harness 补丁见文首说明。

### paper-to-ppt (5-6)
- 命令：`/tmp/run_ppt.py`（make_figures 程序化图表 + `agents.Proposer` 本地 LLM 生成 slides.md；绕过缺 fitz 的 paper_source/demo 顶层导入）
- 输出片段：
```
figures: {'/speedup_bar.png': '...加速比柱状图', '/memory_hierarchy.png': '...内存层次带宽对比'}
paper chars: 4569
slides.md length: 5918   pages ≈ 20
LLM calls: 2  total_tokens: 12697  peak_prompt_tokens: 3532
```
- 已注释文件：paper_source.py（新增模块 docstring + 关键函数注释）；demo.py / agents.py / make_figures.py / renderer.py 已含中文注释。
- 备注（阻塞原因）：Slidev 渲染链需 `npx slidev`（playwright/chromium，未装）与 fitz（未装）；Reviewer 视觉审查需支持图像的模型（本地模型不支持，且协议禁止请求其他模型 id）。提议者-审核者循环中 LLM 提议侧验证通过；注释后重跑一次（run2）仍正常（2 次调用、~19 页）。判 PARTIAL。

### paper-to-video (5-7)
- 命令：`demo.py --offline --limit 1`；`/tmp/run_ptv_llm.py`（本地 LLM 生成 1 页讲解词）；`pytest`
- 输出片段：
```
[1/1] Attention Is All You Need
  幻灯片: output/slides/slide_01.png   音频: output/audio/audio_01.mp3 时长 19.56s
最终视频时长: 19.61s  输出文件: output/lecture.mp4
narration: 大家好，今天咱们来聊一篇真正改变游戏规则的文章。2017年，Vaswani...
```
- 已注释文件：demo.py / campaign.py 等均已含中文注释，未重复添加。
- 备注：pytest 9 过。ffmpeg 全流水线（渲染→估时→合成→concat→ffprobe 校验）OK；真实 TTS 为付费 OpenAI tts-1（不调用），判 PARTIAL。

### permission-embedded-data-objects (5-15)
- 命令：`python -c` 冒烟 `pedo.core.models`（AccessContext/DataObject/PermissionRule.matches）
- 输出片段：
```
models smoke OK: recruiter1 position True
```
- 已注释文件：demo.py、pedo/core/models.py、pedo/core/store.py（模块 docstring + 三层流水线/权限过滤器链注释）。
- 备注（阻塞原因）：`pedo.core.store` 依赖 `psycopg2`（未安装），demo 与 tests 均需可达 PostgreSQL（5432 未运行，协议不允许安装/起 docker）。纯数据层 models 冒烟通过（规则匹配命中），判 BLOCKED(缺依赖: psycopg2；无本地 PostgreSQL)。

### provider-failover (5-1/5-2)
- 命令：`pytest tests -q`；`KIMI_BASE_URL=http://localhost:1234/v1 KIMI_MODEL=qwen3.8-27b-splash MOONSHOT_API_KEY=not-needed run_handoff.py --pairs kimi:anthropic --arms neutral --out /tmp/pf_handoff_local`
- 输出片段：
```
[kimi -> anthropic] neutral ...
  切换后首个请求 None | 数据齐备 False | 总额正确 False | 重复调用 0 | 切换后 0 轮 / 0 token
（证据 JSON：本地 kimi 臂真实执行 3 次工具调用；切换后因无 ANTHROPIC_API_KEY 干净终止）
```
- 已注释文件：run_handoff.py / run_continuation.py / providers.py / neutral_trace.py / renderers.py / streaming.py 均已含中文注释，未重复添加。
- 备注：pytest 23 过（离线格式转换/渲染全覆盖）。本地端点扮演 kimi 臂真实产生 3 次工具调用，故障切换语义（中立臂、0 重复调用）验证通过，判 PASS。`run_continuation` 需三家真实付费端点，未运行。

### small-model-codified-rules (5-5)
- 命令：`demo.py --selftest`；`OPENAI_API_KEY=not-needed OPENAI_BASE_URL=http://localhost:1234/v1 demo.py --task TB009 --mode both --small-model qwen3.8-27b-splash --provider openai --output /tmp/smcr_result.json`；`pytest test_campaign.py`
- 输出片段：
```
✅ TB009-basic_economy-h24p1-scheduled 应退=False 实退=False 无效调用=0（两臂各 1/1）
指标：任务成功率 100% vs 100%  政策违规 0/0  无效工具调用 0/0
```
- 已注释文件：demo.py / agent.py / airline_env.py / tasks.py 均已含中文注释，未重复添加。
- 备注：selftest 离线三层守卫 OK；pytest 4 过。判 PASS。

### video-edit (5-8)
- 命令：`demo.py --smoke`；`demo.py --quick --backend ffmpeg`（本地 LLM 双模型）；`pytest`
- 输出片段：
```
已生成 .../output/source.mp4  场景真值: {'hiking':(0,15),'surfing':(15,30),...} 时长 54.0s
步骤 1 | 解析结果：目标场景='the surfing scene'  特效=[]
步骤 2 | 视频分析子 Agent：两步 Vision 定位 ...
  ValueError: 未能从回复中解析 JSON：（本地模型对图像输入返回空）
```
- 已注释文件：demo.py / agents.py / video_editor.py / blender_editor.py / ffmpeg_utils.py 等均已含中文注释，未重复添加。
- 备注：smoke 剪辑链路（ffmpeg 回退）+ bpy 脚本生成 OK；pytest 18 过。文本需求解析正确（目标=冲浪 15-30s 段），但两步 Vision 定位依赖视觉能力，本地模型对图像输入返回空 → 后续剪辑/审查无法进行，判 PARTIAL(视觉定位 BLOCKED: 本地模型无视觉能力)。

## 预存问题记录（非本次引入，未修改）
1. `cad-vs-diffusion/llm.py`：约 52-64 行 `try:` 块含裸 `raise` 且无 `except` 子句 → import 即 SyntaxError（提交 3e05b43 原样带入）。按「只加注释」规则不修复。
2. `code-for-logic`：合并跑全部 test 文件时 1 个失败，系跨文件 `sys.modules` 注入污染（假 `csp_solver`），逐文件运行全部通过。
3. LM Studio 兼容性：不支持 `json_object` response_format、function 级 `tool_choice`、图像输入 → 均由 /tmp 驱动 harness 级兼容，仓库零改动。
