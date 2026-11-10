# 第 8 章 本地测试报告（模型后训练）

环境：LM Studio qwen3.8-27b-splash @ http://localhost:1234/v1，venv=/Users/fx/wk/github/agent/.venv

**本章特殊性**：18 个实验目录（任务单称 16，实际 `ls` 确认 18 个）全部是 **GPU 训练**（SFT/DPO/GRPO/继续预训练/VLA/语音 LoRA），本机无 GPU，完整训练一律未启动（需 A100/H100/RTX PRO 等）。按任务要求：每个训练实验**不启动训练**，改为真实运行其**离线可验证部分**（数据构建/清洗、质量审计、评估逻辑、pytest、preflight/smoke），训练启动命令记录于下。

**venv 事实（实测）**：torch 2.15.0、transformers 4.52.3、peft 0.21.2、trl 0.19.1、datasets 5.0.1、accelerate 1.15.0 可导入；**unsloth、snac 缺失**（未安装，协议禁止装依赖）。HF Hub 下载可用（免费）。

| 实验 | 命令 | 状态 | 已加注释文件 | 关键输出/说明 |
|---|---|---|---|---|
| AWorld-train | 无本地代码（外部 bojieli/AWorld+verl 未 clone） | BLOCKED(外部源码缺失+GPU) | 无（仅 README） | 训练命令见详录 |
| AdaptThink | 无本地代码（外部 bojieli/AdaptThink 未 clone） | BLOCKED(外部源码缺失+GPU) | 无（仅 README/训练报告） | 8×H100 历史 W&B 运行 |
| Intuitor | `pytest tests/ test_normalize_negative_currency.py`；`evaluate_from_cache.py <parquet>` | PARTIAL(训练需 GPU) | 已有中文注释（evaluate_from_cache.py 等） | 20 测试过；GSM8K 抽取管线 6/8=75% |
| MiniMind-pretrain | `validation/validate_evidence.py`（只读） | BLOCKED(外部源码缺失+GPU) | 无（py 全在 validation/ 内，不可改） | 验证器报预存 README 哈希漂移 |
| MultilingualReasoning | `evaluate_multilingual.py`（评估器，纯逻辑） | PARTIAL(训练需 GPU+20B) | evaluate_multilingual.py | 保真度/准确率逻辑跑通 |
| RLVP | 无本地代码（外部 19PINE-AI/rlvp 未 clone） | BLOCKED(外部源码缺失+GPU) | 无（仅 README） | 训练命令见详录 |
| SimpleVLA-RL | 无本地代码（外部 PRIME-RL 未 clone） | BLOCKED(外部源码缺失+GPU+仿真器) | 无（仅 README+mp4） | LIBERO/RoboTwin 训练 |
| SpatialReasoning | 无本地代码（外部 bojieli/SFTvsRL 未 clone） | BLOCKED(外部源码缺失+GPU) | 无（仅 README） | V-IRL PPO 导航 |
| continued-pretraining | 三脚本 `--help`（语法验证） | PARTIAL(unsloth 缺失+GPU) | evaluate_model.py | 训练入口不可 import(unsloth) |
| cot-distillation | `pytest`；`analyze_data.py`；`sft_data_auditor.py`；`train_student.py --preflight` | PARTIAL(采集需付费 API+训练需 GPU) | sft_data_auditor.py、train_student.py、evaluate_student.py | 14 测试过；审计 score 1.0；preflight ready:false(无 CUDA) |
| curly-quote-sft | `generate_data.py`；`quality_audit.py`；`pytest` | PARTIAL(训练需 GPU+Qwen3-8B) | quality_audit.py、evaluate.py | 数据可复现(哈希一致)；审计 1536 行 0 错 |
| exact-copy-sft | `generate_data.py`；`pytest`；tokenizer 审计(内存复现) | PARTIAL(训练需 GPU+Qwen3-8B) | tokenizer_audit.py、evaluate.py | 512 探针：Qwen 系往返 80.08%，Mistral 100% |
| orpheus | `pytest`（依赖打桩） | PARTIAL(unsloth 缺失+GPU) | inference.py、orpheus_sft_unsloth.py | 17 测试过（stub 模式） |
| premature-completion-dpo | `demo.py`；`build_preference_data.py`；`evaluate.py --mock`；`train_dpo.py --smoke`；`pytest` | PARTIAL(训练需 GPU) | 已有中文注释（6 个脚本均有中文 docstring） | 离线全链路+真实 0.5B 前向 smoke 通过；21 测试过 |
| prompt-distillation | `pytest`；`compare.py`；135M 学生 CPU 评估 | PARTIAL(教师 API 付费+训练需 GPU) | run_experiment_8_8.py | token -97.5%；留出 75/80=93.75% |
| retool | 无本地代码（外部 bojieli/verl+SandboxFusion 未 clone） | BLOCKED(外部源码缺失+GPU) | 无（仅 README） | SFT 暖启+PPO |
| sesame | `pytest`（依赖打桩） | PARTIAL(unsloth 缺失+GPU) | inference.py、batch_inference.py、sesame_csm_sft_unsloth.py | 4 测试过（stub 模式） |
| speech-sft-experiment | `pytest`；`analyze_campaign.py --help` | PARTIAL(snac 缺失+GPU+禁写 validation) | analyze_campaign.py、run_orpheus.py、run_sesame.py | 3 过 1 败(snac 缺)；历史验收包已存 |

## 各实验详细记录

### AWorld-train（8-15）
- 命令（训练，未启动）：`cd chapter8/AWorld/env && bash run-local.sh`（GAIA MCP 沙盒）；数据准备后 `cd chapter8/AWorld/train/examples/train_gaia_with_aworld_verl && bash run.sh`（veRL 训练 Qwen3-4B）。
- 输出片段：无本地代码可运行（目录仅 README.md；外部 AWorld/verl checkout 缺失）。
- 已注释文件：无（无 .py）。
- 备注：BLOCKED(外部源码缺失 + GPU 训练)。README 为复现指南（2479 行），入口/契约已固定到 SHA a52d61d。

### AdaptThink（8-10）
- 命令（训练，未启动）：`bash scripts/preprocess_dataset.sh` → `bash scripts/run_adapt_think_1.5b_deepscaler_16k_delta0.05_btz128_lr2e-6.sh` → `bash scripts/run_eval_verl_hf.sh`（需 8×H100；注意 README 指出评估脚本硬编码 `-fl4096` 路径需手工修正）。
- 输出片段：目录仅 README + TRAINING_REPORT.md（8×H100 公开 W&B `wubbn5tj` 历史记录：step 300 响应长度 -67.9%/-53.4%/-47.2%，AIME mean@16 -0.42pp）。
- 已注释文件：无（无 .py）。
- 备注：BLOCKED(外部源码缺失 + GPU)。

### Intuitor（直觉/内部反馈 RL）
- 命令：`python -m pytest tests/ test_normalize_negative_currency.py -q`；`python evaluate_from_cache.py <lighteval parquet>`（GSM8K 评测管线）。
- 输出片段：
  ```
  20 passed in 0.18s
  # 合成 8 条 lighteval 风格预测（6 对 2 错）+ 真实 GSM8K 金标：
  📊 总样本数: 8
  ✅ 加载了 1319 个金标答案
  总样本数: 8   正确数量: 6   错误数量: 2   准确率: 75.00%
  ```
- 已注释文件：evaluate_from_cache.py 等已含完整中文注释（71 行中文，模块/函数/关键行齐全），无需再加。
- 备注：训练为 GRPO 式内部反馈 RL（论文 sunblaze-ucb/intuitor 实现，本地无训练脚本）→ BLOCKED(GPU)。抽取/归一化/判对管线真实跑通。

### MiniMind-pretrain（8-3/8-4）
- 命令（训练，未启动）：`trainer/train_pretrain_muon.py` → `trainer/train_full_sft_muon.py` → `trainer/train_dpo.py`；评估 `python eval_model.py --load 0 --model 0/1/2`（外部 bojieli/minimind，8bdc5d9 固定）。
- 输出片段（本地 validation 只读验证器）：
  ```
  $ python validation/validate_evidence.py
  AssertionError: byte count mismatch: .../MiniMind-pretrain/README.md
  $ python validation/validate_vlm_evidence.py
  {"error": "input hash mismatch: chapter8/MiniMind-pretrain/README.md", "status": "failed"}
  ```
- 已注释文件：无（6 个 .py 全在 `validation/` 内，协议禁止修改该目录）。
- 备注：**预存文档漂移**——密封于 2026-07-31 的 evidence manifest 记录 README 155255 字节，而 git HEAD 中 README 为 157786 字节（我未改动该文件，git status 干净）；README 在 evidence 密封后被更新过、未重新密封。训练本身 BLOCKED(外部源码缺失 + GPU)。

### MultilingualReasoning（8-7）
- 命令（训练，未启动）：`python gpt_oss_20b_sft.py --mode {train,inference,full}`（gpt-oss-20b，需 GPU + 20B 下载）。
- 输出片段（评估器纯逻辑离线验证）：
  ```
  西班牙语 CoT 保真度: 1.0
  英语污染西班牙语 CoT: 0.2
  中文 CoT 保真度: 1.0
  准确率(一致): 1.0   准确率(不一致): 0.0
  # 编辑后复核：fidelity(en)= 1.0  acc= 1.0
  ```
- 已注释文件：evaluate_multilingual.py（模块 docstring 转中文 + 5 处方法注释）；gpt_oss_20b_sft.py 已有 198 行中文注释。
- 备注：训练 BLOCKED(GPU + 20B 模型)。语言保真度/准确率/token/迁移效率四套指标逻辑跑通。

### RLVP（8-16）
- 命令（训练，未启动）：`python3 tests/test_rules.py && python3 tests/test_credit.py` → `python3 scripts/phase0_baseline.py` → `bash scripts/run_all.sh` → `python3 scripts/eval_checkpoint.py results/run_c3/final c3_norules`（需 CUDA，外部 19PINE-AI/rlvp@1ad30bc）。
- 输出片段：目录仅 README.md；无本地代码。
- 已注释文件：无。
- 备注：BLOCKED(外部源码缺失 + GPU)。

### SimpleVLA-RL（8-13）
- 命令（训练，未启动）：`cd chapter8/SimpleVLA-RL/SimpleVLA-RL && bash examples/run_openvla_oft_rl_libero.sh`；RoboTwin2 用 `bash examples/run_openvla_oft_rl_twin2.sh`（`SFT_MODEL_PATH` 仍是占位符；需 OpenVLA-OFT + 仿真器 + CUDA）。
- 输出片段：无本地代码（README + 3 篇过程文档 + 历史 rollout mp4，如 `step=56--...--success=True--ran=7247.mp4`）。
- 已注释文件：无。
- 备注：BLOCKED(外部源码缺失 + GPU + 机器人仿真器)。

### SpatialReasoning（8-12）
- 命令（训练，未启动）：`cd chapter8/SFTvsRL && bash scripts/virl_training/vl_train.sh`；评估 `bash scripts/virl_evaluation/vl_indist_eval.sh` / `vl_rule_ood_eval.sh` / `vl_visual_ood_eval.sh`（外部 bojieli/SFTvsRL@fef0a4a，未 clone）。
- 输出片段：目录仅 README.md（5034 行指南）。
- 已注释文件：无。
- 备注：BLOCKED(外部源码缺失 + GPU)。

### continued-pretraining（8-5）
- 命令（训练，未启动）：`python continued-pretrain.py --base_model unsloth/mistral-7b-v0.3 ...`（韩语继续预训练）→ SFT；评估 `python evaluate_model.py`、对比 `python compare_models.py`。
- 输出片段：
  ```
  $ python continued-pretrain.py --help   # OK（argparse 先于 unsloth 导入）
  usage: continued-pretrain.py [-h] [--base_model BASE_MODEL] ...
  $ python -c "import ..."  # FAIL: ModuleNotFoundError: No module named 'unsloth'
  $ python evaluate_model.py --help / compare_models.py --help  # 均 OK
  ```
- 已注释文件：evaluate_model.py（模块 docstring 转中文）；continued-pretrain.py/compare_models.py 已有中文注释。
- 备注：训练 BLOCKED(缺依赖: unsloth + GPU)；本目录无历史 checkpoint（lora_model* 不存在），评估脚本缺模型可跑对象；历史 RTX-4090 报告在 validation/。

### cot-distillation（8-9）
- 命令：`pytest -q`；`python analyze_data.py`；`python sft_data_auditor.py data/sft_cot_distill_aime.jsonl`；`python train_student.py --preflight --preflight-output output/preflight_local.json`。
- 输出片段：
  ```
  14 passed in 0.25s
  SFT 样本数：24 | 思考链长度：均值 1255，中位 418，最大 13740 | 含反思/验算：6/24
  examples=24 issues=0 score=1.0
  {"preflight": "output/preflight_local.json", "ready": false}
  blockers: ['no CUDA device available']   samples: 23（kimi_k3 臂）
  ```
- 已注释文件：sft_data_auditor.py（docstring 转中文 + 7 处方法注释）、train_student.py（docstring + 3 处）、evaluate_student.py（docstring 转中文）；generate_data.py/analyze_data.py 已有中文注释。注释后全部重跑/复核通过。
- 备注：`generate_data.py` 走 OpenRouter 教师 API（付费，禁止）→ 数据用仓库已存的 24 条 Kimi K3 轨迹；`train_student.py`/`evaluate_student.py` 需 CUDA + 1.5B 下载（未启动）；checkpoints/ 目录只含 tokenizer.json，**adapter 权重未随书分发**，学生臂无法评估。

### curly-quote-sft（8-18）
- 命令：`python generate_data.py`；`python quality_audit.py`；`pytest -q`。
- 输出片段：
  ```
  {"train": "9e27158265ab...", "eval": "7c54b2bf1f14...", "boundary": "e342edf5d282..."}
  {"total_rows": 1536, "total_errors": 0, "status": "pass"}   # train 1024 / eval 256 / boundary 256
  7 passed in 0.03s
  ```
- 已注释文件：quality_audit.py（docstring 转中文 + check_row 注释）、evaluate.py（新增中文 docstring + score 注释）；generate_data.py 已有 42 行中文。
- 备注：确定性数据重建后哈希与提交版本一致（git 无 diff）。训练 `python train_sft.py`（Qwen3-8B bf16 LoRA，需 GPU）与 `python evaluate.py`（需 16GB 模型下载）未启动 → BLOCKED(GPU+模型规模)。

### exact-copy-sft（8-19）
- 命令：`python generate_data.py`；`pytest -q`；tokenizer 审计以**内存复现**运行（官方脚本会写 `validation/tokenizer_audit.json`，为不碰 validation/ 改为只打印）。
- 输出片段：
  ```
  {"train": "a56d5acc...", "eval": "3ad8d96b...", "boundary": "25a1dab2..."}
  7 passed in 0.03s
  "probe_count": 512,
  "Qwen/Qwen3-8B":            {"roundtrip_rate": 0.8008, "mean_tokens": 34.6}
  "Qwen/Qwen2.5-0.5B-Instruct":{"roundtrip_rate": 0.8008, "mean_tokens": 34.6}
  "mistralai/Mistral-7B-v0.1": {"roundtrip_rate": 1.0,    "mean_tokens": 39.26}
  ```
- 已注释文件：tokenizer_audit.py（docstring 转中文 + main 注释）、evaluate.py（新增中文 docstring）。
- 备注：审计证实 Qwen 系 tokenizer 对约 20% 特殊字符串往返不一致（属 tokenizer 层，非模型能力）——正是本实验要区分的错误来源。训练/评估需 Qwen3-8B + GPU → 未启动。

### orpheus（8-6 Orpheus 轨道）
- 命令（训练/推理，未启动）：`python orpheus_sft_unsloth.py`（Colab 导出训练，需 unsloth+CUDA）；`python inference.py`（需 unsloth/snac + Orpheus-3B 下载）。
- 输出片段：`pytest -q` → `17 passed in 0.46s`（测试以 stub 打桩 unsloth/torchaudio/snac，真实验证 collator/掩码等纯逻辑）。
- 已注释文件：inference.py（docstring 转中文 + 6 处方法注释）、orpheus_sft_unsloth.py（中文说明块 + 5 处）。
- 备注：venv 缺 **unsloth/snac** → 推理/训练脚本不可 import；BLOCKED(缺依赖: unsloth, snac + GPU)。

### premature-completion-dpo（8-17）
- 命令：`python demo.py`；`python build_preference_data.py`；`python evaluate.py --mock`；`python train_dpo.py --smoke`；`pytest -q`。
- 输出片段：
  ```
  [1] 从 24 条 bad case 构造出 24 条 DPO 偏好对
  [base   ] boundary 过早宣称率 100% | retention 正常收尾率 100% | 过度矫正率 0%
  [adapter] boundary 过早宣称率 0%   | retention 正常收尾率 100% | 过度矫正率 0%
  已写出 24 条偏好对 -> output/preference_pairs.jsonl
  数据加载 OK：24 条偏好对 | tokenizer OK：186 tokens | 前向 OK：logits (1,186,151936)
  smoke 检查通过（未训练）。   # 真实下载 Qwen2.5-0.5B，CPU 前向
  21 passed in 0.06s
  ```
- 已注释文件：demo.py/build_preference_data.py/evaluate.py/llm_client.py/train_dpo.py/train_grpo_optional.py 均已有中文模块 docstring（提交自带），未重复添加。
- 备注：真实 DPO 训练 `python train_dpo.py`（7B+LoRA 单卡，需 GPU）与 `python train_grpo_optional.py`（隐藏测试奖励 GRPO）未启动。

### prompt-distillation（8-8）
- 命令：`pytest -q`；`python compare.py`；学生评估用本地驱动复用其解析逻辑在 CPU 跑 135M（官方 `evaluate.py` 用 transformers 5.x 的 `dtype=` API，与 venv 4.52.3 不匹配，直接运行会 TypeError，故未改代码、改在驱动侧兼容）。
- 输出片段：
  ```
  13 passed in 0.02s
  → 输入 token 降低 97.5%（教师是学生的 39.8 倍）
  教师(基准): 100.00%   学生(蒸馏后): 95.19% (1999/2100)
  # 本地 CPU 评估（campaign 真实 student_adapter + SmolLM2-135M，80 条留出，9.8s）：
  "heldout_rows": 80, "trained_gold_accuracy": 0.9375   # 75/80，与 campaign 报告 95% 相近
  ```
- 已注释文件：run_experiment_8_8.py（新增中文说明块）；create_data.py/evaluate.py/compare.py/train_sft_trl.py 已有中文注释。
- 备注：`create_data.py` 需 vLLM 教师或 Moonshot API（付费/外部，禁止）；`train_sft_trl.py`/`run_experiment_8_8.py` 需训练设备 → 未启动。

### retool（8-14）
- 命令（训练，未启动）：`cd chapter8/SandboxFusion && make run-online`（实时代码执行服务）；`cd chapter8/verl && bash recipe/retool/run_qwen2-32b_dapo.sh`（Qwen2-32B DAPO；SFT 暖启 `bash run_qwen2-32b_sft.sh`）。
- 输出片段：目录仅 README.md；外部 verl@1593fc3 / SandboxFusion@4a0d573 未 clone。
- 已注释文件：无。
- 备注：BLOCKED(外部源码缺失 + GPU)。

### sesame（8-6 Sesame 轨道）
- 命令（训练/推理，未启动）：`python sesame_csm_sft_unsloth.py`（Colab 导出，unsloth/csm-1b + Elise 数据集，需 CUDA）；`python inference.py` / `python batch_inference.py`。
- 输出片段：`pytest -q` → `4 passed in 0.02s`（stub 打桩 torch/unsloth/datasets，真实验证 JSON 解析/文件名回退逻辑）。
- 已注释文件：inference.py、batch_inference.py（docstring 转中文 + 方法注释）、sesame_csm_sft_unsloth.py（中文说明块 + 4 处）。
- 备注：venv 缺 **unsloth** → 脚本不可 import；BLOCKED(缺依赖: unsloth + GPU)。

### speech-sft-experiment（8-6 验收）
- 命令：`pytest -q`；`python analyze_campaign.py --help`（完整运行需 CUDA 且会**覆盖 validation/exp8-6-20260804-v1/** 文件，故只验证入口）。
- 输出片段：
  ```
  1 failed, 3 passed in 2.72s   # 失败项: run_orpheus 导入需 snac（venv 缺失）
  usage: analyze_campaign.py [-h] --run RUN
  ```
- 已注释文件：analyze_campaign.py（docstring 转中文 + 5 处）、run_orpheus.py、run_sesame.py（docstring 转中文）。
- 备注：训练 `python run_orpheus.py` / `python run_sesame.py`（各 60 次 LoRA 更新，需 CUDA + unsloth/snac）未启动；历史验收包 `validation/exp8-6-20260804-v1/`（REPORT.md/analysis.json/40 WAV）完整在档，未改动。

## 注释工作汇总

- **新增中文注释 18 个文件**：cot-distillation×3（sft_data_auditor、train_student、evaluate_student）、curly-quote-sft×2、exact-copy-sft×2、orpheus×2、sesame×3、speech-sft-experiment×3、prompt-distillation×1、MultilingualReasoning×1、continued-pretraining×1。
- **已有中文注释（保留，未重复添加）**：Intuitor/evaluate_from_cache.py、premature-completion-dpo 全部 6 脚本、cot-distillation/generate_data.py、curly-quote-sft/generate_data.py、prompt-distillation×4、MultilingualReasoning/gpt_oss_20b_sft.py、continued-pretraining/continued-pretrain.py 等。
- 全部 18 个被编辑文件 `ast.parse` 通过（编辑中曾出现 7 处 docstring 漏闭合/重复行，已逐一修复并复核）；编辑后重跑脚本/测试复核（pytest 全量复跑、analyze_data/sft_data_auditor/quality_audit/evaluator/各 `--help`），输出与编辑前一致。
- 7 个 README-only 实验（AWorld-train、AdaptThink、RLVP、SimpleVLA-RL、SpatialReasoning、retool）+ MiniMind-pretrain（py 全在 validation/ 内）无可注释代码。

## 合规检查

- `validation/` 目录：git status 零改动（curly-quote quality_audit 重跑生成字节一致文件，无 diff）。
- 未改任何 `*.json` 证据、EXPERIMENT_LEDGER.md、其他章节、.env、pyproject/uv.lock；未 git commit/push；未安装依赖；未调用任何付费 API（OpenRouter/Moonshot/ARK 路径全部未触发）；未启动任何训练。
- 新增未跟踪产物仅 3 个实验自己的 `output/` 运行回执（非 validation/）。

## 本章统计

18 个实验 = **0 PASS + 11 PARTIAL + 7 BLOCKED**

- PARTIAL（11）：Intuitor、MultilingualReasoning、continued-pretraining、cot-distillation、curly-quote-sft、exact-copy-sft、orpheus、premature-completion-dpo、prompt-distillation、sesame、speech-sft-experiment —— 离线可验证部分（数据/审计/评估逻辑/pytest/preflight/smoke）真实跑通，训练环节因**无 GPU**（部分叠加 unsloth/snac 缺依赖、付费教师 API）未启动。
- BLOCKED（7）：AWorld-train、AdaptThink、MiniMind-pretrain、RLVP、SimpleVLA-RL、SpatialReasoning、retool —— 本地无代码（外部仓库未 clone，仅 README 指南），无可运行离线部分。

**待用户手动完成**（若需完整跑通）：GPU 机器上按各详录命令启动训练；MiniMind-pretrain 的 README 哈希漂移需重新密封 validation evidence（在 GPU 训练机上操作）。
