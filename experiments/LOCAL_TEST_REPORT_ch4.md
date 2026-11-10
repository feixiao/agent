# 第 4 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

> 全程环境备注：
> 1. LM Studio 服务**间歇性可用**：任务开始时连续 3 次探测超时；中途恢复（协作/执行/对比实验的真实 LLM 部分借此跑通）；任务尾声再次连续 3 次探测超时。按硬性规则，探测失败时该实验 LLM 部分记 BLOCKED(LLM服务暂不可用)。
> 2. 27B 模型单次调用 20 秒~2.5 分钟，协作工具客户端默认 60 秒超时会报 `Request timed out`，运行时以 `OPENAI_TIMEOUT=600 OPENAI_MAX_RETRIES=1` 规避（环境变量覆盖，未改代码）。
> 3. venv 装的是 mcp SDK 2.3.0：按 1.x API（FastMCP）写的 collaboration-tools 服务器与 execution-tools 的 server.py 在本机 import 即失败；perception-tools 已适配 2.x（MCPServer）但缺 bs4 等依赖。
> 4. 禁止改 validation/：perception `run_experiment_4_2.py` 崩溃运行产生的部分 campaign 目录、execution-tools pytest 产生的 `test_edit.py`/`test_output.py`/`.test-runtime-tmp/` 等**运行产物已清理**，恢复初始状态。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| active-tool-discovery | `python demo.py --offline`；`pytest test_exact_experiment.py`；`python run_exact_experiment.py` | PARTIAL | run_exact_experiment.py（demo/agent/discovery/offline_backend/tools_library 原代码即全中文，未重复加） | 离线三策略对比 8/8 任务全部跑通；`run_exact_experiment.py` 需本地 Ollama qwen3:4b（11434 端口拒连）BLOCKED(本地无 Ollama)；在线 LLM 路径 BLOCKED(探测超时 + 在线路径需 OpenAI embeddings 端点，本地不可用) |
| active-tool-selection | `python demo_comparison.py --offline`；`pytest tests`；`python quickstart.py` | PARTIAL | agent.py, semantic_router.py, tool_knowledge_base.py, config.py, quickstart.py, demo_comparison.py, benchmark.py | 离线对比 10 任务 100% 召回、token -86.6%、35→400 扩展曲线全部输出；端到端/quickstart BLOCKED(LLM服务暂不可用，探测 3 次超时) |
| collaboration-tools | `python main.py demo`；`python subagent_comparison.py`；`pytest`；`python quickstart.py` | PARTIAL | src/subagent_tools.py, src/hitl_tools.py, src/notification_tools.py, src/llm_fallback.py, src/config.py, src/main.py, quickstart.py, run_experiment_4_5.py, subagent_comparison.py（main.py 原代码即中文） | 端到端演示真实跑通（minimal 86 tok / llm_generated 258+854 tok，均无隐私泄漏；HITL 两场景）；pytest 48 passed+6 subtests；quickstart/run_experiment_4_5 BLOCKED(缺依赖: mcp 2.x 与代码 1.x FastMCP API 不兼容；正式实验另需 Moonshot 付费 Key) |
| execution-tools | `python cli.py demo`；`cli.py code/shell/write/edit`；`pytest` | PARTIAL | server.py, execution_tools.py, file_tools.py, llm_helper.py, config.py（cli.py 原代码即中文） | 离线演示 4 项安全机制全过；code_interpreter/virtual_terminal/file_write/file_edit 单独调用全过；LLM 审批/总结路径 BLOCKED(代码 provider 解析无 openai 分支，仅支持付费 provider，无法指向本地 LM Studio)；calendar/PR BLOCKED(缺 github/googleapiclient 库)；pytest 76 passed 1 failed(既有) |
| multimodal-agent | `python create_sample.py`；`python demo.py`/`main.py` | BLOCKED(缺依赖: google-genai) | agent.py, config.py, main.py, demo.py, quickstart.py, campaign.py（create_sample.py 原代码即中文） | agent.py 顶部 `from google import genai` import 失败（venv 缺包，禁止安装）→ demo/main/quickstart/campaign/pytest 全部 BLOCKED；离线可验证部分 create_sample.py PASS（生成 sample_chart.png + sample_report.pdf）；且模型注册表硬编码 gemini/gpt-5/doubao，无本地 qwen 路由，视觉模型未加载 |
| perception-tools | `pytest`（逐文件）；`python run_experiment_4_2.py`；`python smoke_test_mcp_v2.py` | PARTIAL | run_experiment_4_2.py, smoke_test_mcp_v2.py, quickstart.py, src/main.py, src/search_tools.py | 8 个可导入测试文件 48 passed（+1 既有 failed）；13 个测试文件 import 失败 BLOCKED(缺依赖: bs4/cv2/wikipedia/yfinance/duckduckgo_search)；MCP stdio 入口（正式实验/冒烟）因服务器缺 bs4 崩溃 BLOCKED(缺依赖: bs4 等) |

## 各实验详细记录

### active-tool-discovery

- 命令与输出：
```
$ python demo.py --offline          # 本地哈希嵌入 + mock 模型，无需 key
模型: mock-offline  |  嵌入: local-hash-512  |  工具库: 126 个  |  任务数: 8  |  策略: ['全量注入', '检索预筛选', '主动发现']
[主动发现] 注入   1019 tokens （暴露 11 个工具）  延迟  0.01s
           [discover_tools] need='查询某股票的实时价格与涨跌幅' -> ['get_crypto_price', 'get_stock_price', ...]
           判定: ✅ 精确选对（2/2 能力槽位命中）
策略                  精确选对      任务完成       平均注入token      总注入token     平均延迟(s)
全量注入               8/8       8/8           11630         93040       0.004
检索预筛选              4/8       4/8            1030          8236       0.004
主动发现               8/8       8/8             974          7796       0.007
注入 token：全量注入 93040 vs 主动发现 7796，平均每任务精简约 11.9 倍。
$ pytest test_exact_experiment.py -q   → 10 passed in 0.27s
```
- 已注释文件：run_exact_experiment.py（模块 docstring + ollama_chat/run_agent_task/run_group/run 关键函数）。其余 5 文件（demo.py/agent.py/discovery.py/offline_backend.py/tools_library.py）原代码即全中文注释，按"已加不重复"原则未改。
- 备注：`run_exact_experiment.py` BLOCKED——需本地 Ollama `qwen3:4b`（127.0.0.1:11434 连接拒绝），且其拉起的 perception MCP 服务器缺 bs4。在线 `demo.py`（非 --offline）需要 OpenAI embeddings 端点（text-embedding-3-small），本地无该端点且不允许请求其他模型 → LLM 部分 BLOCKED(本地无 embedding 服务)。注释后重跑 pytest（10 passed）+ demo --offline 验证通过。

### active-tool-selection

- 命令与输出：
```
$ python demo_comparison.py --offline
Benchmark tasks: 10   Catalog size: 35 tools   Retrieval top-k: 5
| all-tools (dump everything) | 35 |  3,857 | 100% |
| retrieval (top-5)           |  5 |   517 | 100% |
=> Retrieval keeps 100% recall while cutting tool-schema tokens by 86.6% (3,857 -> 517).
Scaling: 35→50→100→200→400 工具，retrieval token 稳定 517~522，all-tools 线性增长至 40,258
$ pytest tests -q   → 8 passed in 0.89s
```
- 已注释文件：agent.py（模块 docstring + execute_task 主循环）、semantic_router.py（模块 + route_request 两级打分 0.3/0.7）、tool_knowledge_base.py、config.py、quickstart.py、demo_comparison.py、benchmark.py。
- 备注：端到端评测（quickstart.py / demo_comparison 在线部分）BLOCKED(LLM服务暂不可用)——尝试前探测 3 次全部超时（该服务间歇性故障）。离线核心（TF-IDF 语义路由 + 基准）完全跑通，语义路由走 sklearn 离线路径，不依赖 embedding 服务。注释后重跑 --offline + pytest + 三 Agent 构造/检索验证全部通过。

### collaboration-tools

- 命令与输出：
```
$ OPENAI_TIMEOUT=600 OPENAI_MAX_RETRIES=1 python main.py demo
策略: minimal    上下文 86 tok | 额外准备 0 tok | 泄漏隐私: 否
  子 Agent 结果: {"status": "need_info", ...缺少退款申请信息，请求补充…}
策略: llm_generated  上下文 258 tok | 额外准备 854 tok | 泄漏隐私: 否
  子 Agent 结果: {"status":"done","result":"该笔退款满足全部三项自动批准条件…①7天内②<500元③Gold…"}
→ 场景 A（超时前批准）: "approved": true, "admin_notes": "核对无误，同意退款"
→ 场景 B（超时保守默认）: "approved": false, "timeout": true
  [email/slack/telegram] 未发送（No email service configured / webhook not configured…）
$ python subagent_comparison.py   → 同任务双策略对比，结论与 demo 一致
$ pytest -q（排除 2 个缺 chess 包的文件 + 1 个 27B 慢速 LLM 文件）→ 48 passed, 6 subtests passed
```
- 已注释文件：src/subagent_tools.py（两策略说明）、src/hitl_tools.py、src/notification_tools.py、src/llm_fallback.py、src/config.py、src/main.py（含 mcp 2.x 不兼容说明）、quickstart.py、run_experiment_4_5.py、subagent_comparison.py。main.py 原代码即全中文，未改。
- 备注：quickstart.py（MCP stdio 客户端）BLOCKED——服务器进程 import `mcp.server.fastmcp` 失败（venv 为 mcp 2.3.0，FastMCP 已改名 MCPServer）。run_experiment_4_5.py 正式 campaign 同样 BLOCKED（同 mcp 不兼容 + 服务器子进程被契约强制 COLLAB_PROVIDER=moonshot/kimi-k3 付费 API，无 Key）。test_intelligence_tools.py（5 次真实 LLM 调用）在 480 秒内完成 3 个、其余受 27B 速度限制未跑完，记 PARTIAL。test_chess_tools.py 与 src/test_excel_max_rows_all_sheets.py 缺 `chess` 包，BLOCKED(缺依赖: chess)。注释后 import 全模块 + main.py list + 48 pytest 重跑通过。

### execution-tools

- 命令与输出：
```
$ python cli.py demo        # 端到端离线演示（无需 API key）
1. file_write 语法校验 → success=True, verification=passed
2. 写坏代码 → success=False（Syntax error at line 1: invalid syntax，linter 拦截）
4. code_interpreter → apple: 4 / banana: 3 / cherry: 2
6. 长输出截断：上下文保留 102 行（原始 1000 行），完整输出落盘 + 尾部片段
7. 危险命令审批 → success=False（无 KIMI key 时 fail-safe 拒绝、未执行）
$ cli.py code --language python --code "print(sum(range(10)))"  → "45", returncode=0
$ cli.py shell "ls <workspace>"（--no-approval）→ 正常回包
$ cli.py write / edit → success=True，edit 输出 diff 预览 "line one" → "LINE ONE"
$ pytest -q  → 1 failed, 76 passed   # 失败为既有的 test_github_idempotency（缺 github 库）
```
- 已注释文件：server.py（含 mcp 2.x 不兼容说明）、execution_tools.py、file_tools.py、llm_helper.py、config.py（明确"无 openai 分支"）。cli.py 原代码即全中文，未改。
- 备注：LLM 审批/总结/非 Python 语法检查路径 BLOCKED——`config.get_llm_config` 只支持 dashscope/siliconflow/doubao/kimi/moonshot/openrouter（均为付费/聚合端点），没有 openai 分支，无法指向本地 LM Studio，按规则不请求付费 API。google_calendar/github_create_pr BLOCKED(缺依赖: googleapiclient/github 库)，返回明确的"库未安装"错误。演示中 file_write 存在将相对路径写向 CWD 的既有怪癖（demo 产物 wordcount.py/data.txt 已清理）。注释后 demo + shell 调用 + pytest 重跑一致。

### multimodal-agent

- 命令与输出：
```
$ python create_sample.py    # 完全离线
已生成图表: test_files/sample_chart.png
已生成报告: test_files/sample_report.pdf
$ python demo.py / main.py / pytest
ImportError: cannot import name 'genai' from 'google'   # agent.py:19，venv 缺 google-genai
```
- 已注释文件：agent.py（三范式 + 本机阻塞说明）、config.py（注册表无本地 qwen 路由）、main.py、demo.py、quickstart.py、campaign.py（含写入 validation/ 说明）。create_sample.py 原代码即中文，未改。
- 备注：整个实验 BLOCKED(缺依赖: google-genai，禁止安装)——agent.py 顶层 import 失败，连带 demo/main/quickstart/campaign/pytest 全部无法运行。即使装上，模型注册表硬编码 gemini-3.5-flash/gpt-5/gpt-5.6-luna/doubao-1.6（付费/视觉模型，本地未加载，不允许请求），LLM 路径也无本地路由。图像理解 BLOCKED(视觉模型未加载)。离线可验证部分 = create_sample.py PASS。注释后 py_compile 全过、create_sample 重跑正常、pytest 错误状态与注释前一致（既有缺包）。

### perception-tools

- 命令与输出（逐文件单独跑，规避既有的同会话 sys.modules 污染问题）：
```
test_filesystem_mutations.py        → 6 passed
test_parse_page_range_trailing_comma.py → 5 passed
test_wiki_article_history_date.py   → 1 passed
test_xquik_tools.py                 → 9 passed
test_pubchem_tools.py               → 14 passed（14s，含真实 PubChem 免费 API）
test_pubchem_async.py               → 1 passed
test_document_tools.py              → 5 passed
test_experiment_4_2.py              → 6 passed（离线验收检查）
test_real_experiment_4_2_evidence.py→ 5 passed, 1 failed（既有：回执字节数 136 vs 28 不符）
$ python run_experiment_4_2.py  → 服务器子进程缺 bs4 崩溃 + credential_preflight 的
                                  find_spec("google.oauth2.credentials") 抛 ModuleNotFoundError
$ python smoke_test_mcp_v2.py   → MCPError: Connection closed（服务器 import 崩溃）
```
- 已注释文件：run_experiment_4_2.py、smoke_test_mcp_v2.py、quickstart.py、src/main.py、src/search_tools.py。
- 备注：13 个测试文件 import 失败（缺 bs4 / cv2 / wikipedia / yfinance / duckduckgo_search，requirements.txt 未装入 venv，禁止安装）→ BLOCKED(缺依赖)。MCP stdio 两个入口因此同样 BLOCKED(缺依赖: bs4 等)（非 docker 问题：代码走 stdio 而非容器）。崩溃运行产生的部分 campaign 目录（validation/ 下）已清理。注释后 py_compile 全过，8 文件 pytest 重跑结果与注释前完全一致。

## 本章统计

6 个实验 = 0 PASS + 5 PARTIAL + 1 BLOCKED

- PARTIAL（5）：active-tool-discovery、active-tool-selection、collaboration-tools、execution-tools、perception-tools
  （离线核心/安全机制/pytest 全部真实跑通，受阻环节均为环境限制：LLM 服务间歇性故障、缺依赖、代码不支持本地 provider 路由）
- BLOCKED（1）：multimodal-agent（缺依赖: google-genai，连带全部 LLM 路径；离线部分 create_sample.py 已跑通）
