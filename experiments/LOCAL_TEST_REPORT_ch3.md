# 第 3 章 本地测试报告

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

> 执行说明（含任务追加指令的落实）：
> - 每个 LLM 实验运行前均按追加指令用 `curl` 快请求探测 LM Studio 健康（30s 窗口，失败等 30s 重试，最多 3 次）。
> - 执行中 LM Studio 多次被**我自身被 5 分钟规则 kill 的残留服务端推理**占住（客户端断开不会取消 27B 推理模型仍在生成的长 CoT 响应），队列消化需要数分钟；最终一轮 3 次探测全部失败，故除 user-memory 外，其余实验的**实时 LLM 环节统一记 `BLOCKED(LLM服务暂不可用)`**，离线部分全部验证完毕。
> - 全程仅请求 `qwen3.8-27b-splash` 一个模型 id；未安装依赖、未动 validation/、*.json 证据、EXPERIMENT_LEDGER.md、.env，未 git commit。
> - 本地 embedding 端点不可用（协议既定事实），向量环节优先走代码自带离线/确定性/BM25 路径。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| sparse-embedding (3-5) | `python cli.py --eval`、`python -m pytest`；HTTP：`python server.py 4241` + `python demo.py` | **PASS**（venv 同步后补跑） | bm25_engine.py, quickstart.py（cli.py 原已中文） | 核心 BM25 全通：pytest 8 passed；eval 宏平均 recall@5=0.800/MRR=0.800；fastapi 补装后 HTTP 服务补跑全通（启动→10 篇索引→统计→检索→停止，demo + 手工 curl），原 HTTP BLOCKED(缺 fastapi) 环节解锁，见「补跑记录」 |
| log-sanitization (3-3) | `python main.py --demo`、`python -m pytest tests/` | PARTIAL | main.py, test_loader.py, metrics.py, agent.py（regex_sanitizer.py 原已中文） | 离线 regex 引擎：16 处脱敏/13 类别；pytest 26 passed；LLM 路径 BLOCKED（Ollama 服务未运行、无 OpenRouter 回退 Key） |
| dense-embedding (3-4) | `python -m pytest` + 临时 ANN 验证脚本；服务补跑：临时脚本（已缓存 MiniLM 87MB，8000 端口）+ `python test_client.py` | PARTIAL(venv 同步后补跑；BGE-M3 仍超下载上限) | config.py, document_store.py, embedding_service.py, main.py, indexing.py | FlagEmbedding/colorlog 补装后：服务全部环节（初始化→索引 10 篇→检索→删除→列表）用已缓存 all-MiniLM-L6-v2 真实跑通（384 维/HNSW）；默认 BGE-M3(~2.3GB) 仍超 200MB 下载上限 → 该模型本体 BLOCKED(模型下载超限)；ANNOY 库仍损坏，ANN 走 HNSW；见「补跑记录」 |
| retrieval-pipeline (3-6) | `python evaluate.py --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2` | **PASS** | config.py, reranker.py, retrieval_pipeline.py, document_store.py（evaluate.py/fusion.py 原已中文） | 全 5 阶段单进程离线评测跑通：BM25 R@3=0.833 → Dense 1.000 → Hybrid-RRF 1.000 → Weighted 0.958 → +Rerank 0.903；pytest 4 passed；稠密用已缓存 MiniLM，重排模型下载后跑通 |
| structured-index (3-7) | `python structured_vs_flat_demo.py`、`python -m pytest test_*.py`；补跑：`python main.py build/query`（小 txt + 已缓存 MiniLM + 本地 LLM） | PARTIAL(venv 同步后补跑：缺依赖阻塞解除，RAPTOR 构建/查询全通，GraphRAG 实体抽取受 27B 推理预算限制) | raptor_indexer.py, graphrag_indexer.py, hybrid_retriever.py, document_processor.py（main.py 原已中文） | 离线演示全通；pytest 12 passed；loguru/sentence-transformers/umap 补装后索引构建解锁：RAPTOR 树（本地 27B 摘要）+ query 正常，GraphRAG 管线跑通但 0 实体（27B reasoning 占满写死的 max_tokens=1000 → JSON 解析失败）；见「补跑记录」 |
| user-memory (3-1/3-2) | `python main.py --mode demo --memory-mode notes --provider dashscope --model qwen3.8-27b-splash`（env 覆写 DASHSCOPE_BASE_URL 指向本地）；补跑同命令 + `OPENAI_TIMEOUT=600` | **PASS**（venv 同步后补跑：后台记忆闭环完整） | main.py, conversational_agent.py, background_memory_processor.py, memory_manager.py | 补跑完整闭环：对话 3/3 轮 → 后台记忆提取 3 条（add_memory×3 + STOP，"Memory update task completed: True"）→ Session 2 跨会话召回正确复述全部偏好 → 正常退出；原 PARTIAL 缺口（5 分钟 kill 于后台处理前）已补齐；pytest 17 passed；见「补跑记录」 |
| user-memory-evaluation (3-1) | `python main.py --mode compare --metric keyword-recall`、`python -m pytest` | PARTIAL | main.py, framework.py, evaluator.py, models.py（metrics.py 原已中文） | 离线 4 系统对比表：full_context 1.000 / json_cards 1.000 / simple_notes 0.323 / no_memory 0.000 (n=8)；pytest 6 passed；llm-judge BLOCKED（kimi 无 Key；openai 本地路由在但服务被占） |
| mem0 (3-2) | `python -m pytest test_simple.py test_agent_v3.py`；demo：`python main.py --mode demo`（KIMI_* 指向本地） | BLOCKED(mem0 cloud：embedder 强制 openai，本地无 embeddings 端点) | main.py, agent.py | mem0ai 2.2.1 补装后 import 解锁：pytest 9 passed（test_simple + test_agent_v3 全部收集通过，原 4 passed+收集报错）；Memory 本地 chroma 初始化 OK、LLM 路由本地 OK；但 embedder 写死 openai 云配置 → 首次 memory.add 即 `POST /v1/embeddings 400`（本地无 embedding 模型）→ 记忆闭环 BLOCKED；见「补跑记录」 |
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

14 个实验 = **3 PASS**（retrieval-pipeline、sparse-embedding※、user-memory※）+ **10 PARTIAL**（log-sanitization、structured-index※、dense-embedding※、user-memory-evaluation、memobase、agentic-rag、agentic-rag-for-user-memory、contextual-retrieval、contextual-retrieval-for-user-memory、structured-knowledge-extraction）+ **1 BLOCKED**（mem0※）

（※ = venv 同步补跑后状态变化，见「补跑记录」小节。原口径：1 PASS + 11 PARTIAL + 2 BLOCKED。其中 sparse-embedding 由 PARTIAL→PASS，user-memory 由 PARTIAL→PASS，dense-embedding 由 BLOCKED→PARTIAL（BGE-M3 本体仍超下载上限、ANNOY 仍损坏，故非 PASS）；structured-index 保持 PARTIAL（缺依赖阻塞解除，GraphRAG 实体抽取受 27B 预算限制）；mem0 保持 BLOCKED（原因收窄为 mem0 cloud embedder，pytest 由 4 passed 提升至 9 passed）。）

## 补跑记录（venv 同步后）

> 背景：`uv sync --all-extras` 后 venv 补装/升级 fastapi 0.136.3、FlagEmbedding 1.4.2、colorlog 6.12.0、loguru 0.7.3、sentence-transformers 6.2.0、mem0ai 2.2.1、umap-learn 0.5.12、beautifulsoup4、html2text 等（transformers 5.17.0 / trl 1.15.0）。
> 模型锁死规则全程遵守：LLM 仅请求 `qwen3.8-27b-splash`（每个 LLM 实验前 curl 探测通过）；HF 只用 `~/.cache` 已缓存的 all-MiniLM-L6-v2(87MB)/cross-encoder(88MB)，无新下载；未装依赖、未改代码/validation/*.json/LEDGER/.env，未 git commit。

### 1. sparse-embedding (3-5)：HTTP 检索服务（原 BLOCKED：缺 fastapi）→ **PASS**

- 命令：`python server.py 4241`（后台启动）→ `python demo.py` → `curl -X POST http://localhost:4241/search` → kill 服务。
- 输出片段：
```
INFO:     Uvicorn running on http://0.0.0.0:4241 (Press CTRL+C to quit)
   Successfully indexed 10 documents
   Total documents: 10   Unique terms: 162   Total terms: 242
   Query: 'machine learning algorithms' (top 3 results)
   Rank 1:  Score: 2.3624   Title: Introduction to Machine Learning
   Matched terms: ['machine', 'learning', 'algorithms']
（手工 curl "how do I learn machine learning"：#1 Machine learning 2.987 / #2 Deep learning 0.838）
```
- 结论：启动→清空→索引→统计→结构→检索 全环节经 HTTP 真实跑通，服务正常停止；原「HTTP 服务部分 BLOCKED（缺 fastapi）」环节解锁 → 实验整体 **PASS**。

### 2. dense-embedding (3-4)：索引+检索（原 BLOCKED：缺 FlagEmbedding/colorlog + 无本地 embedding 服务）→ **PARTIAL**

- 模型选择：默认 `BAAI/bge-m3`（~2.3GB）超 200MB 下载上限，且 `main.py` 无 `--model` 参数、`ServiceConfig.from_env()`（`DENSE_MODEL` 变量）在 `main()` 中未被调用 → 按「不得改代码」用临时脚本 `/tmp/dense_service_mini.py`：import 仓库 `main` 模块后注入 `model_name="sentence-transformers/all-MiniLM-L6-v2"`（87MB，HF 缓存已有，`HF_HUB_OFFLINE=1` 禁网）、`use_fp16=False`（macOS CPU），8000 端口起服务（test_client 默认端口）。
- 输出片段（`python test_client.py`）：
```
✅ Service is running   - Index type: hnsw   - Model: sentence-transformers/all-MiniLM-L6-v2
✅ Indexed 10 documents   - embedding_dimension: 384
  Query: 'What is deep learning and neural networks?'  (top1 Score: 0.9413)
  Deleting document: bcf102da-...  Result: ... deleted successfully
✅ Demo completed successfully!
```
  另：`EmbeddingService` 直接初始化验证 dim=384、encode 正常；`pytest -q` 1 passed（与注释期一致）。
- 结论：嵌入（BGEM3FlagModel 包装小模型）+ HNSW 索引 + 服务全部环节真实跑通；残留限制：① BGE-M3 本体仍 BLOCKED(模型下载超限)；② ANNOY 库在 numpy 2.x 下损坏（原阻塞汇总第 3 条，未变），ANN 验证走 HNSW。整体 **BLOCKED→PARTIAL**。

### 3. structured-index (3-7)：索引构建（原 BLOCKED：缺 loguru/sentence-transformers/umap）→ 保持 **PARTIAL**（阻塞解除，GraphRAG 受模型预算限制）

- 代码中嵌入模型硬编码 `sentence-transformers/all-MiniLM-L6-v2`（87MB，缓存已有）→ 符合小模型规则；LLM 经 `OPENAI_BASE_URL`(.env 本地) + `RAPTOR_MODEL/GRAPHRAG_MODEL=qwen3.8-27b-splash` 指向本地。
- 命令：`HF_HUB_OFFLINE=1 ... python main.py build /tmp/si_x86_docs.txt --type both`（2 篇 SSE/AVX 小文档），随后 `python main.py query "What registers does AVX use?" --type both --top-k 3`。
- 输出片段：
```
Initialized RAPTOR indexer with model: qwen3.8-27b-splash
  Created 1 text chunks
  RAPTOR tree built with 1 nodes and 1 root nodes
  RAPTOR index built: {'total_nodes': 1, 'root_nodes': 1, 'levels': 1, ...}
  Extracting entities: 100%|██| 1/1 [00:45<00:00]
  WARNING Could not parse JSON from LLM response
  GraphRAG index built: {'total_entities': 0, 'total_relationships': 0, ...}
  Indexing complete!
（query） RAPTOR returned 1 results   1. Score: 0.539   Summary: ...   Level: 0
（query） GraphRAG returned 0 results   ← 退出码 0
```
- 结论：loguru 日志、SentenceTransformer 加载（offline 6s）、RAPTOR 构建（本地 27B 摘要 16s）+ 查询全通——「索引构建 BLOCKED(缺依赖)」已解除。GraphRAG 实体抽取：LLM 调用真实发出（45s），但 27B 为推理模型，思考耗掉写死的 `max_tokens=1000` 预算 → content 空/非 JSON → 解析失败 0 实体（两次、中英文文档一致复现，属模型预算而非代码/依赖问题，不得改码）→ 图谱为空。整体保持 **PARTIAL**（原缺依赖缺口补齐，新增模型预算缺口）。
- 备注：运行副产物 `structured-index/indexes/{raptor,graphrag}/*_index.pkl`（实验代码默认写盘路径，未提交）。

### 4. mem0 (3-2)：demo/pytest（原 BLOCKED：缺 mem0ai）→ 保持 **BLOCKED**（原因收窄：mem0 cloud embedder）

- 命令：`python -m pytest test_simple.py test_agent_v3.py`；`KIMI_API_KEY=local KIMI_API_BASE=http://localhost:1234/v1 MODEL_NAME=qwen3.8-27b-splash OPENAI_TIMEOUT=600 python main.py --mode demo --user-id rerun_user`。
- 输出片段：
```
pytest: 9 passed, 2 warnings（mem0ai 2.2.1 装好后 test_agent_v3 亦可收集）
agent - INFO - Initialized Mem0 memory system with local backend（chroma ./data/chroma_db）
  Agent initialized successfully
  Session 1 —— 首次对话，建立用户画像
  httpx - HTTP Request: POST http://localhost:1234/v1/embeddings "HTTP/1.1 400 Bad Request"
  → memory.add 首次嵌入即失败（LM Studio 无 embeddings 模型，/v1/embeddings 返回 "No models loaded"）
```
- 结论：mem0ai 补装后框架 import/pytest 全通；但 `agent.py` 中 embedder 写死 `{"provider": "openai", "model": text-embedding-3-small}`（cloud 配置，无本地替代开关）；即便借 `.env` 的 `OPENAI_BASE_URL` 把请求路由到本地，本地单槽位是 27B 对话模型、embeddings 端点不可用（协议既定事实）→ 记忆 add/search 闭环 **BLOCKED(mem0 cloud/无本地 embedding 端点)**，按任务口径记录。

### 5. user-memory (3-1/3-2)：后台记忆闭环重试（原 PARTIAL：5 分钟规则 kill 于后台记忆处理前）→ **PASS**

- 超时规避核查：本实验 `ConversationalAgent`/`BackgroundMemoryProcessor` 的 `OpenAI(...)` 均未写死 timeout（SDK 默认 600s；`conversation_history.py` 的 `timeout=30` 是其自有 REST 接口），代码不读取 `OPENAI_TIMEOUT`——仍按任务指令显式携带 `OPENAI_TIMEOUT=600`（无害），未出现 APITimeoutError。
- 命令：`DASHSCOPE_BASE_URL=http://localhost:1234/v1 DASHSCOPE_API_KEY=local OPENAI_TIMEOUT=600 python main.py --mode demo --memory-mode notes --provider dashscope --model qwen3.8-27b-splash`（退出码 0，约 5 分钟）。
- 输出片段：
```
👤 User: I'm currently working on a new mobile app project for our company.
🔄 Processing conversation for memory updates...
   Memory update task completed: True
📝 Memory Operations (3 total):
1. ➕ ADD: Alice is a Product Manager at TechCorp.
2. ➕ ADD: Alice is currently working on a new mobile app project for TechCorp.
3. ➕ ADD: Alice prefers Python for scripting, uses VS Code as her IDE, and likes dark themes.
✅ Summary: 3 added, 0 updated, 0 deleted
📝 Session 2: Testing memory persistence
👤 User: What do you know about me and my work?
🤖 Assistant: Hi Alice! ... Product Manager at TechCorp ... mobile app project ... Python/VS Code/dark themes（全部正确召回）
👋 Thank you for using User Memory Agent!
```
- 结论：对话 3/3 轮 → 后台记忆提取/持久化 → 跨会话（Session 2）召回 正确复述全部 3 条记忆 → 正常收尾。**PARTIAL→PASS**（原缺口补齐）。

### 6. 阻塞汇总补跑覆盖说明

- 阻塞汇总第 2 条（venv 缺包）中**仅因缺依赖**的 LLM 环节按「性价比」挑 2 个补跑：structured-index 构建/查询的 LLM 环节（loguru/sentence-transformers/umap → 已补跑，RAPTOR 全通、GraphRAG 受 27B 预算限制）与 mem0 的 LLM 环节（mem0ai → 已补跑，LLM 路由通、embedder 仍 BLOCKED）。其余缺依赖环节（fastapi/FlagEmbedding/colorlog）分别由第 1/2 条覆盖。
- 阻塞汇总第 1 条（LM Studio 被占）中的 LLM 环节（agentic-rag 生成、3-9/3-11 评审、3-10/3-11 前缀生成、3-12 阶段 1-2、log-sanitization）**保持 BLOCKED 不动**（按任务要求不补跑；本次服务健康、可后续由用户择机重试）。
- 补跑期间新增未跟踪文件（实验代码正常写盘，非证据篡改，不删除）：`chapter2/context-compression/logs/strategy_{run,results}_*.log/json`、`chapter3/structured-index/indexes/{raptor,graphrag}/*_index.pkl`。
- 本次补跑 LLM 请求全部且仅发往 `qwen3.8-27b-splash`（每次实验前 curl 探测；mem0 的 400 为 embeddings 端点、非模型切换）；未下载任何 >200MB 模型；未调用任何付费/外部 API。
