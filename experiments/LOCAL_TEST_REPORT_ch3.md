# 第 3 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

> 执行说明（含任务追加指令的落实）：
> - 每个 LLM 实验运行前均按追加指令用 `curl` 快请求探测 LM Studio 健康（30s 窗口，失败等 30s 重试，最多 3 次）。
> - 执行中 LM Studio 多次被**我自身被 5 分钟规则 kill 的残留服务端推理**占住（客户端断开不会取消 27B 推理模型仍在生成的长 CoT 响应），队列消化需要数分钟；最终一轮 3 次探测全部失败，故除 user-memory 外，其余实验的**实时 LLM 环节统一记 `BLOCKED(LLM服务暂不可用)`**，离线部分全部验证完毕。
> - 全程仅请求 `qwen3.8-27b-splash` 一个模型 id；未安装依赖、未动 validation/、*.json 证据、EXPERIMENT_LEDGER.md、.env，未 git commit。
> - 本地 embedding 端点不可用（协议既定事实），向量环节优先走代码自带离线/确定性/BM25 路径。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| sparse-embedding (3-5) | `python cli.py --eval`、`python -m pytest` | PARTIAL | bm25_engine.py, quickstart.py（cli.py 原已中文） | 核心 BM25 全通：pytest 8 passed；eval 宏平均 recall@5=0.800/MRR=0.800，"cat" 同义词漏召回=0（设计预期）；HTTP 服务部分 BLOCKED（缺 fastapi，server.py/demo.py 依赖它） |
| log-sanitization (3-3) | `python main.py --demo`、`python -m pytest tests/` | PARTIAL | main.py, test_loader.py, metrics.py, agent.py（regex_sanitizer.py 原已中文） | 离线 regex 引擎：16 处脱敏/13 类别；pytest 26 passed；LLM 路径 BLOCKED（Ollama 服务未运行、无 OpenRouter 回退 Key） |
| dense-embedding (3-4) | `python -m pytest` + 临时 ANN 验证脚本 | BLOCKED(缺依赖 FlagEmbedding/colorlog + 无本地 embedding 服务) | config.py, document_store.py, embedding_service.py, main.py, indexing.py | 嵌入模型不可用；ANN 层验证：HNSW recall@5=1.000（500 向量/10 查询，与 numpy 精确 top-k 一致）；ANNOY 在 venv 中库级损坏（裸 annoy 单热向量也只返回 1 个邻居，recall 0.02） |
| retrieval-pipeline (3-6) | `python evaluate.py --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2` | **PASS** | config.py, reranker.py, retrieval_pipeline.py, document_store.py（evaluate.py/fusion.py 原已中文） | 全 5 阶段单进程离线评测跑通：BM25 R@3=0.833 → Dense 1.000 → Hybrid-RRF 1.000 → Weighted 0.958 → +Rerank 0.903；pytest 4 passed；稠密用已缓存 MiniLM，重排模型下载后跑通 |
| structured-index (3-7) | `python structured_vs_flat_demo.py`、`python -m pytest test_*.py` | PARTIAL | raptor_indexer.py, graphrag_indexer.py, hybrid_retriever.py, document_processor.py（main.py 原已中文） | 离线对比演示全通（图谱多跳/层次树 vs 扁平检索）；pytest 12 passed；索引构建 BLOCKED（缺 loguru/sentence-transformers/umap，main.py 连 `--help` 都起不来；LLM 当时亦不可用） |
| user-memory (3-1/3-2) | `python main.py --mode demo --memory-mode notes --provider dashscope --model qwen3.8-27b-splash`（env 覆写 DASHSCOPE_BASE_URL 指向本地） | PARTIAL | main.py, conversational_agent.py, background_memory_processor.py, memory_manager.py | 本地 LLM 真实跑通对话 9/10 轮（日志留存）：记忆检索注入、偏好记住/更新均正常；单轮 1–2 分钟，5 分钟规则 kill 于后台记忆处理前；pytest 17 passed |
| user-memory-evaluation (3-1) | `python main.py --mode compare --metric keyword-recall`、`python -m pytest` | PARTIAL | main.py, framework.py, evaluator.py, models.py（metrics.py 原已中文） | 离线 4 系统对比表：full_context 1.000 / json_cards 1.000 / simple_notes 0.323 / no_memory 0.000 (n=8)；pytest 6 passed；llm-judge BLOCKED（kimi 无 Key；openai 本地路由在但服务被占） |
| mem0 (3-2) | `python -m pytest test_simple.py` | BLOCKED(缺依赖 mem0ai + 外部 LLM/embedding) | main.py, agent.py | 框架包未安装，agent 无法 import；test_simple 4 passed（不依赖该包的部分）；test_agent_v3 收集报错 |
| memobase (3-2) | `python -m pytest` | PARTIAL | main.py, agent.py | 自研实现、无外部框架依赖：pytest 7 passed；LLM 记忆更新 BLOCKED（默认 kimi 外部付费；本地路由 LLM_PROVIDER=dashscope+env 覆写存在，但 LLM 服务当时不可用） |
| agentic-rag (3-8) | `python compare_offline.py`、`python -m pytest` | PARTIAL | main.py, agent.py（compare_offline.py/offline_retriever.py 原已中文） | 离线司法检索对比：21372 法条块/288 文档；单次检索证据召回 76% vs 分解式 100%（复杂题 58%→100%）；pytest 7 passed 3 skipped；LLM ReAct 环节 BLOCKED(LLM服务暂不可用) |
| agentic-rag-for-user-memory (3-9) | `python offline_demo.py`、`python -m pytest` | PARTIAL | main.py, agent.py, indexer.py（offline_demo.py 原已中文） | 离线演示：朴素单次检索决定性证据召回 50% → 智能体 5 轮追查 100%（本田预约+特斯拉双车都取回）；pytest 10 passed；LLM 评审 BLOCKED |
| contextual-retrieval (3-10) | `python -m pytest`（compare_retrieval.py 因语料缺失不可跑） | PARTIAL | main.py, agent.py, contextual_chunking.py, contextual_agent.py, contextual_tools.py（compare_retrieval.py 原已中文） | pytest 4 passed；BM25 对比脚本可用但仓库自带 document_store.json 仅 2 条测试残留、无分块；真实前缀索引需 LLM 逐块生成（服务不可用）→ 前缀生成环节 BLOCKED |
| contextual-retrieval-for-user-memory (3-11) | `python contextual_compare.py`、`python -m pytest <各文件>` | PARTIAL | main.py, agent.py, indexer.py, contextual_chunking.py, contextual_indexer.py, contextual_evaluator.py（contextual_compare.py 原已中文） | 离线双层对比：Plain Recall@1=0.625 → Contextual 0.750、MRR 0.792→0.875（12 块/8 查询）；pytest 15 passed（逐文件；3 个文件模块级 sys.exit 无法并入套件）；LLM 前缀/卡片生成 BLOCKED |
| structured-knowledge-extraction (3-12) | `python -m pytest` | PARTIAL | campaign.py（discovery/extractor/advisor_agent/demo/archetypes 原已中文） | pytest 11 passed（合成小样本 66 案，15.8s）；demo 四阶段需 LLM（阶段 1 约 7 次调用起步，无 schema 缓存）BLOCKED；官方 CAIL2018 路径需外部 API 不尝试 |

## 各实验详细记录

### sparse-embedding (3-5)
- 命令：`python cli.py`、`python cli.py --explain`、`python cli.py --eval`、`python -m pytest`
- 输出片段：
```
查询: 'model distillation'  (BM25, top-5)
  #1  doc_3  score=3.1216  Model Distillation
         └ 'model': TF=3, 文档长度=13词, IDF=1.2238, BM25贡献=1.9705
  #2  doc_4  score=2.2197  Knowledge Distillation

查询 'cat'  相关文档=['doc_7', 'doc_8']
  召回排序: []
  recall@5=0.00  ...  <- 漏召回(同义词短板)
宏平均  recall@5=0.800  precision@5=0.700  MRR=0.800  漏召回率=0.200
```
- 已注释文件：bm25_engine.py（TextProcessor/InvertedIndex/BM25/SparseSearchEngine 模块+类中文 docstring）、quickstart.py（模块 docstring）。cli.py 原已中文。
- 备注：pytest 8 passed。`server.py` 依赖 fastapi（venv 未装，禁止安装）→ HTTP 服务与 `demo.py`（依赖该服务）不可运行；`quickstart.py` 为 stdin 交互循环，非交互下按 5 分钟规则 kill。引擎核心（分词/倒排/BM25/评测）全部真实跑通。

### log-sanitization (3-3)
- 命令：`python -m pytest tests/`、`python main.py --demo`
- 输出片段：
```
脱敏类别汇总 (across all samples)
   口令/密钥赋值 2 处 · 邮箱 2 · 手机号 2 · API Key 1 · 信用卡 1 · SSN 1
   连接串凭据 1 · AWS 访问密钥 1 · IP 1 · GitHub 令牌 1 · Slack 1 · JWT 1 · 私钥/证书 1
   合计脱敏 16 处敏感信息，覆盖 13 个类别
```
- 已注释文件：main.py、test_loader.py、metrics.py、agent.py。regex_sanitizer.py 原已完整中文。
- 备注：pytest 26 passed；离线 regex 引擎完全跑通。LLM 路径 BLOCKED：agent 只认 Ollama（`localhost:11434` 连接拒绝，服务未运行）或 OpenRouter（.env 无 Key，外部付费禁止）。

### dense-embedding (3-4)
- 命令：`python -m pytest`；ANN 验证用临时脚本（运行时 stub 缺失的 colorlog，不改仓库代码）
- 输出片段：
```
pytest: 1 passed
ANNOY: size=500 build=2.7ms query10=0.05ms avg_results=1.9 recall@5=0.020 sample=['doc_0']
HNSW:  size=500 build=20.4ms query10=0.36ms avg_results=5.0 recall@5=1.000 sample=['doc_107','doc_396','doc_409','doc_60','doc_499']
```
- 已注释文件：config.py、document_store.py、embedding_service.py、main.py、indexing.py
- 备注：嵌入模型环节 BLOCKED——FlagEmbedding 未安装、无本地 embedding 端点（协议事实）、HF 缓存无 BGE-M3 权重；indexing.py 依赖 chain 上的 colorlog 也未装。ANN 层：HNSW 与 numpy 精确 top-k 完全一致（recall 1.0）；ANNOY 结果异常系 **annoy 库在本 venv（numpy 2.x）下损坏**——不经实验代码、裸 annoy 对 2D/64 维单热向量同样只返回 1 个邻居，可复现，属环境问题而非实验代码问题。

### retrieval-pipeline (3-6)
- 命令：`python evaluate.py --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2`（默认稠密 MiniLM 已在 HF 缓存）、`python -m pytest`、`python evaluate.py --no-dense`
- 输出片段：
```
语料: 20 篇文档 → 22 个 chunk   查询: 12 条   耗时: 3.45s
Stage / Method            Recall@3    MRR     nDCG@3
BM25 (sparse)               0.8333    0.7917  0.8026
Dense                       1.0000    0.9167  0.9385
Hybrid-RRF                  1.0000    1.0000  1.0000
Hybrid-Weighted             1.0000    0.9583  0.9692
Hybrid-RRF+Rerank           1.0000    0.9028  0.9276
```
- 已注释文件：config.py、reranker.py、retrieval_pipeline.py、document_store.py。evaluate.py、fusion.py 原已中文/详尽。
- 备注：**本章唯一全量 PASS**——单进程离线评测把 分块→嵌入→检索→融合→重排 五阶段全部真实跑通（本地 MiniLM 嵌入 + 交叉编码器重排，均为免费模型下载，非付费 API）。首次全量尝试因首次下载 1.1GB 重排模型超 5 分钟被 kill，换 90MB 轻量重排模型后 3.45s 完成。pytest 4 passed。微服务版（main.py 需 fastapi）未验证。

### structured-index (3-7)
- 命令：`python structured_vs_flat_demo.py`、`python -m pytest test_graphrag_search_top_k.py test_hybrid_retriever.py test_raptor_chunk_step.py`
- 输出片段：
```
【查询 2】SSE 与 AVX 使用的向量寄存器有什么区别？
-- 扁平检索 --  召回 YMM/XMM/MOVAPS 零散片段，不会对齐成对比表
-- 结构化图检索 --  SSE→XMM(128位) / AVX→YMM(256位,低128位共享)  直接综合出对比
【查询 3】概述一下 x86 的 SIMD 指令集
-- 结构化树检索 -- 返回父节点摘要「SIMD 指令集综述」，可下钻细节
结论：扁平检索擅长「找到含某信息的片段」…关系推理/多层次综合必须依赖结构化索引（图/层次树）
```
- 已注释文件：raptor_indexer.py、graphrag_indexer.py、hybrid_retriever.py、document_processor.py。main.py 原已中文。
- 备注：pytest 12 passed（test_indexing.py 因缺 loguru 无法收集）；`main.py` 模块级 import loguru 失败，build/query（需 sentence-transformers/umap + LLM）BLOCKED(缺依赖+无本地 embedding)。

### user-memory (3-1/3-2)
- 命令：`DASHSCOPE_BASE_URL=http://localhost:1234/v1 DASHSCOPE_API_KEY=local python main.py --mode demo --memory-mode notes --provider dashscope --model qwen3.8-27b-splash`（该实验 provider 均为外部，借 DASHSCOPE_BASE_URL 环境覆写路由到本地 LM Studio，未改代码）
- 输出片段（两次运行日志，均本地 qwen3.8-27b-splash）：
```
[Session: session-dd2424df, Turn 7]  User: Hi! My name is Alice ... product manager at TechCorp.
[Session: session-5a9b9db1, Turn 9]  User: I prefer Python for scripting and use VS Code ... dark themes.
Assistant: Noted, Alice! 🐍🖥️🌑 ...（正确复述并确认偏好）
HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
```
- 已注释文件：main.py、conversational_agent.py、background_memory_processor.py、memory_manager.py
- 备注：pytest 17 passed。本地 LLM 对话真实跑通 9/10 轮（记忆检索注入、自我介绍、偏好记录均正常）；本地 27B 每轮 1–2 分钟，10 轮+后台记忆处理超 5 分钟规则被 kill，**后台记忆提取/持久化闭环未完成**（PARTIAL 的具体缺口）。该实验的残留服务端请求随后长期占满 LM Studio，是后续实验 LLM 环节 BLOCKED 的直接原因。

### user-memory-evaluation (3-1)
- 命令：`DEFAULT_EVALUATOR=openai python main.py --mode compare --metric keyword-recall`、`python -m pytest`
- 输出片段：
```
Memory System Comparison (Keyword Recall, 0.000-1.000)
Layer 1 · Basic Recall          full_ctx 1.000  json_cards 1.000  simple_notes 0.417  no_memory 0.000
Layer 2 · Disambiguation        full_ctx 1.000  json_cards 1.000  simple_notes 0.333  no_memory 0.000
Layer 3 · Proactive Synthesis   full_ctx 1.000  json_cards 1.000  simple_notes 0.125  no_memory 0.000
Overall (n=8)                   1.000 / 1.000 / 0.323 / 0.000   对比报告已保存至 evaluation_report.txt
```
- 已注释文件：main.py、framework.py、evaluator.py、models.py。metrics.py 原已中文。
- 备注：pytest 6 passed。离线 keyword-recall 对比全通。发现一个代码缺陷（未修改，仅记录）：`--mode batch --metric keyword-recall` 在 fixtures 示例（按系统分组、与用例 id 不重合）下 results 为空，`generate_report` 的 `100*total_passed/total_tests` 无零除保护，抛 ZeroDivisionError。llm-judge BLOCKED（kimi 无 Key；openai 本地路由存在但服务被占）。

### mem0 (3-2)
- 命令：`python -m pytest test_simple.py`
- 输出片段：`4 passed, 2 warnings in 0.01s`（test_agent_v3.py 收集期 import mem0ai 失败）
- 已注释文件：main.py、agent.py
- 备注：BLOCKED——`mem0ai` 未安装（禁止安装依赖），Mem0 框架无法 import；且其记忆嵌入用 OpenAI 云 text-embedding-3-small（外部+embedding 不可用）。

### memobase (3-2)
- 命令：`python -m pytest`
- 输出片段：`7 passed, 4 warnings in 0.37s`
- 已注释文件：main.py、agent.py
- 备注：本实现自研（不依赖 memobase 框架包），离线单测全通。LLM 记忆更新/画像环节 BLOCKED：默认 kimi（外部付费禁止）；存在本地路由（`LLM_PROVIDER=dashscope` + `DASHSCOPE_BASE_URL` 覆写 + `MODEL_NAME=qwen3.8-27b-splash`），但执行时 LLM 服务不可用。另注意其 MODEL_TEMPERATURE=0.7，推理模型要求 temperature=1，即便服务恢复也可能被拒，未改代码。

### agentic-rag (3-8)
- 命令：`python compare_offline.py`、`python -m pytest`
- 输出片段：
```
[离线对比] 索引完成：21372 个法条分块 / 288 篇文档，用时 1.1s
故意伤害致人重伤…  easy   100%  100%   1→1
诈骗罪量刑标准      hard    0%    100%  1→1
醉酒过失致人重伤且有盗窃前… hard  33%  100%  1→3
聚合: 全部 76% → 100%（+24%）；复杂题 58% → 100%
结论：分解式多轮检索将整体证据召回率从 76% 提升到 100%，代价是平均检索次数 1.0→1.3
```
- 已注释文件：main.py、agent.py。compare_offline.py、offline_retriever.py 原已中文。
- 备注：pytest 7 passed 3 skipped。真实法规模语料（21372 块）上的离线检索对比完整跑通；LLM ReAct/non-agentic 生成环节 BLOCKED(LLM服务暂不可用)。

### agentic-rag-for-user-memory (3-9)
- 命令：`python offline_demo.py`、`python -m pytest --ignore=test_enhanced_logging.py --ignore=verify_test_loading.py`
- 输出片段：
```
[追查] 查询: Tesla service appointment scheduled → 命中 3 块
[追查] 查询: Honda Accord service appointment scheduled → 命中 3 块
指标                          朴素单次检索   智能体化多轮检索
检索查询次数                    1             5
覆盖: 本田已确认预约(FS-447291)  ✗             ✓
覆盖: 特斯拉 Model 3 存在        ✓             ✓
决定性证据召回率                50%           100%
能否完整消歧作答                不能           能
```
- 已注释文件：main.py、agent.py、indexer.py。offline_demo.py 原已中文。
- 备注：pytest 10 passed（test_enhanced_logging/verify_test_loading 模块级 sys.exit 无法收集）。本地 BM25 后端 + 离线演示全通；LLM 评审环节 BLOCKED。

### contextual-retrieval (3-10)
- 命令：`python -m pytest`；`python compare_retrieval.py`（尝试）
- 输出片段：`4 passed`；`compare_retrieval.py` → `[错误] 语料中没有可用分块（缺少 *_chunk_* 条目）: document_store.json`
- 已注释文件：main.py、agent.py、contextual_chunking.py、contextual_agent.py、contextual_tools.py。compare_retrieval.py 原已中文。
- 备注：仓库自带 document_store.json 仅 2 条测试残留（无 `_chunk_` 条目）；构建真实前缀索引（288 篇法律文档逐块 LLM 前缀）需大量 LLM 调用且服务不可用 → 前缀生成 BLOCKED；embedding/hybrid 方法 BLOCKED(无 embedding 服务)。BM25 对比脚本本身可跑（代码完好，缺输入语料）。

### contextual-retrieval-for-user-memory (3-11)
- 命令：`python contextual_compare.py`、`python -m pytest <逐文件>`
- 输出片段：
```
数据集: memory_qa_eval.json   记忆块: 12  查询: 8
方法                          Recall@1   Recall@3   MRR
Plain（直接索引原始块）          0.625      1.000      0.792
Contextual（上下文化后索引）     0.750      1.000      0.875
提升（Δ）                      +0.125     +0.000     +0.083
（最受益：『西雅图酒店确认了吗，是哪家？』Plain 第 3 位 → Ctx 第 1 位）
```
- 已注释文件：main.py、agent.py、indexer.py、contextual_chunking.py、contextual_indexer.py、contextual_evaluator.py。contextual_compare.py 原已中文。
- 备注：pytest 15 passed（逐文件；test_quick/test_enhanced_logging/test_memory_card_generation 模块级 sys.exit 无法并入套件）。离线对比（预生成上下文化数据）全通；LLM 前缀/卡片实时生成 BLOCKED。

### structured-knowledge-extraction (3-12)
- 命令：`python -m pytest`；`python demo.py`（评估后未实际启动：阶段 1 起需 7+ 次 LLM 调用）
- 输出片段：`11 passed in 15.81s`
- 已注释文件：campaign.py。discovery.py、extractor.py、advisor_agent.py、demo.py、archetypes.py 原已完整中文。
- 备注：合成小样本（66 案）单测全通（含归一化/覆盖度/原型/追问等）；demo 四阶段与官方 CAIL2018 campaign 均 BLOCKED（LLM 服务暂不可用 + 官方数据需外部 API）。

## 阻塞汇总（需要用户手动处理 / 待服务恢复后重试）

1. **LM Studio 服务被占用**：多次 5 分钟 kill 的 LLM 运行在服务端继续生成（客户端断开不取消推理），队列消化需 10 分钟级。服务恢复后可补跑：user-memory demo 完整 10 轮+后台记忆闭环、各实验 LLM 环节（agentic-rag 生成、3-9/3-11 评审、3-10/3-11 前缀生成、3-12 阶段 1-2、log-sanitization 需另起 Ollama）。
2. **venv 缺包**（禁止安装）：fastapi（sparse-embedding 服务、dense-embedding 服务）、FlagEmbedding、sentence-transformers、colorlog、loguru、umap、mem0ai、memobase 包（后者代码自研不受影响）→ 对应环节记 BLOCKED(缺依赖:xxx)。
3. **annoy 库损坏**（numpy 2.x 不兼容，裸库即可复现）：dense-embedding 的 ANNOY 后端在本地不可用，HNSW 后端正常。
4. **user-memory-evaluation 代码缺陷**（未修改）：batch+keyword-recall 空结果时 generate_report 零除崩溃。

## 未跟踪文件说明（运行副产物，非证据篡改）

本次运行新增了 4 个未跟踪数据文件，均为实验代码自身的正常写盘行为（测试/对比默认输出路径），不属于 validation/ 证据：`agentic-rag/document_store.json` 与 `contextual-retrieval/document_store.json`（pytest 用例 save_document_store 写回，内容与原有 2 条测试数据一致）、`memobase/memory_store/memories.pkl`（单测本地存储后端）、`user-memory-evaluation/evaluation_report.txt`（compare 模式默认报告）。未删除以免丢失原有数据。

## 统计

14 个实验 = **1 PASS**（retrieval-pipeline）+ **11 PARTIAL**（sparse-embedding、log-sanitization、structured-index、user-memory、user-memory-evaluation、memobase、agentic-rag、agentic-rag-for-user-memory、contextual-retrieval、contextual-retrieval-for-user-memory、structured-knowledge-extraction）+ **2 BLOCKED**（dense-embedding、mem0）
