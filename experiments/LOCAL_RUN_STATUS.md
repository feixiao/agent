# 本地跑通总台账 (Local Run Status)

本台账记录 2026-11-09 ~ 11-10 在本地（Mac，LM Studio `qwen3.8-27b-splash` @ `http://localhost:1234/v1`，仓库 `.venv`）对 `experiments/` 全部 **110 个实验目录** 的跑通结果（首轮 + venv 同步/`OPENAI_TIMEOUT=600`/jsonfmt 透明代理补跑轮，共解锁 11 个环节）。

**状态定义**（章级状态由该章各实验最终状态汇总：全 PASS→✅；存在 PARTIAL/BLOCKED→🟡；核心路径均不可运行→⛔）
- ✅ **跑通**：该实验自带的离线入口（demo / quickstart / --dry-run / 离线 fixture / 单元测试）在本机以退出码 0 完成，并产生文档所述产物。
- 🟡 **部分跑通**：核心离线路径跑通，但正式实验路径（真实 LLM 长跑 / 外部 API / GPU / 硬件）未完整执行，原因已注明。
- ⛔ **阻塞**：无法在本机跑通，注明具体阻塞（需外部仓库 / 硬件 / GPU / 云端 key）。

每章详情见 `LOCAL_TEST_REPORT_ch1.md` ~ `LOCAL_TEST_REPORT_ch10.md`（逐步命令、输出片段、阻塞原因、注释文件清单）；总报告见 `LOCAL_TEST_REPORT.md`。代码中文导读见各入口脚本 docstring（只注释未改逻辑，均已 git 提交）。

| 章 | 状态 | 统计 (PASS/PARTIAL/BLOCKED) | 备注 |
| :--: | :--: | :--: | --- |
| 01 | 🟡 部分跑通 | 2 / 1 / 2 | context 消融双臂真实复现「丢工具结果→捏造数字」；learning-from-experience Q-learning 全离线；search-codegen/image-gen 需外部 API |
| 02 | 🟡 部分跑通 | 1 / 5 / 2 | prompt-engineering PASS；context-compression 补跑后入口解锁（全链路可运行，mock 语料压缩收益待真实模型验证）；attention_visualization/local_llm_serving 阻塞 |
| 03 | 🟡 部分跑通 | 3 / 10 / 1 | BM25 稀疏检索 recall@5=0.80、retrieval-pipeline 全 5 阶段离线评测 PASS；向量路径走本地 MiniLM（BGE-M3 超下载上限）；HTTP 服务补跑解锁 |
| 04 | 🟡 部分跑通 | 0 / 6 / 0 | 六个实验核心离线路径全部可运行、无一完整闭环（真实工具调用/MCP 远端/多模态链路受环境限）；multimodal 视觉调用实测成功 |
| 05 | 🟡 部分跑通 | 9 / 5 / 2 | coding-agent 本地写 hello.py 并运行、ERP 生成 SQL 与参考一致、dynamic-form 真实 Chromium campaign 11/11 门全过（补跑升级） |
| 06 | 🟡 部分跑通 | 3 / 4 / 6 | 遥操作/桌面规划/域迁移三个离线基准全 PASS（MPS 55s）；phone-agent ReAct 对话臂真实闭环（规划臂受 700 token 预算限）；语音/硬件 6 项阻塞 |
| 07 | 🟡 部分跑通 | 4 / 1 / 7 | agent-cost --live 补跑 16/16 轮零超时、model-benchmark/行动阈值/公卫评估真实跑通；设备/GPU/付费 API/外部仓库 7 项阻塞 |
| 08 | 🟡 部分跑通 | 0 / 11 / 7 | 11 个后训练实验的数据/奖励/评估离线部分全部跑通（CoT 蒸馏、DPO、curly-quote 等）；训练本体需 GPU 训练机（命令已逐一记入 ch8 报告） |
| 09 | 🟡 部分跑通 | 0 / 9 / 1 | 9 个进化实验离线门/单测全通，补跑后 prompt-auto-optimization 与另一实验全链最小闭环真实执行；hermes 全 LLM 路径需外部付费 API |
| 10 | 🟡 部分跑通 | 2 / 5 / 1 | 狼人杀完整一局（5 人 2 狼、信息隔离 4/4）、电话注册真实 Chromium 填表 5/5、parallel-web-research/talkact 验证器 passed=true；generative-agents 需上游克隆+embedding 服务 |

**合计**：110 个实验 = **24 PASS + 57 PARTIAL + 29 BLOCKED**。29 个 BLOCKED 均为环境硬限制（外部付费 API / GPU 训练 / 机器人·手机·Android 硬件 / Docker / 6.5GB 权重），各自离线可验证部分已跑通，明细见各章报告「阻塞汇总」。

**全局环境说明**（详见 `LOCAL_TEST_REPORT.md`）：
1. 27B 单轮 10~130s；书中以特定云端模型得出的定量结论不能由本地模型复现，本地验证的是「代码可运行 + 流程正确 + 现象定性一致」。
2. LM Studio 单槽位：embedding/视觉端点不可用，向量检索走代码离线路径或本地 MiniLM。
3. 本地端点拒 `response_format=json_object`（400）：以 /tmp 透明代理剥离该参数（仓库零改动）；60s 写死客户端超时以 `OPENAI_TIMEOUT=600` 规避。
4. 推理模型 token 预算陷阱：`reasoning_content` 与 `content` 共享 `max_tokens`，硬编码小预算的 3 处环节（phone-agent 700 / harness-safety-gate 2400 / self-evolution-eval 160）需提至 8000+（代码改动，未执行）。
5. 既有问题（非本次造成，git 干净副本可复现）：ch7 human-benchmark manifest 哈希不符、ch8 MiniMind 密封哈希与 README 不符、voice-werewolf 1 项等，均已记入各章报告，待上游核实。
