# 2026 音视频多模态大模型实操练习套件 (Hands-on Practice Labs)

> 针对 **Mac Studio（桌面边缘中心）** 与 **Google Pixel 10（移动端边缘节点）** 打造的 5 套端到端、零门槛、零外部三方依赖的音视频大模型实操练习与客户端套件。  
> 理论与完整指南请参阅：[`docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md`](../../docs/multimodal/AUDIO_VIDEO_MULTIMODAL_HANDBOOK.md)。


---

## 系统架构拓扑全景 (Architecture Topology)

```
                            ┌──────────────────────────────────────────────────────────┐
                            │     Mac Studio (Apple Silicon UMA 400~800GB/s MEC)       │
                            │                                                          │
                            │  ┌────────────────────────────────────────────────────┐  │
                            │  │ 05_local_multimodal_server.py (HTTP API Gateway)   │  │
                            │  │  - GET  /health        (Metal/ANE Accelerator Info)│  │
                            │  │  - GET  /v1/models     (Loaded Models Registry)    │  │
                            │  │  - POST /v1/chat/completions  (Multimodal VLM)     │  │
                            │  │  - POST /v1/audio/transcriptions (Whisper ASR)     │  │
                            │  └────────▲───────────────────────────────▲───────────┘  │
                            │           │                               │              │
     本地调用与客户端演练   │           │                               │              │
┌───────────────────────────┤           │                               │              │
│ 01_video_vlm_inference.py ┼───────────┘                               │              │
│ 02_audio_whisper_tts.py   ┼───────────────────────────────────────────┘              │
│ 03_vlm_lora_train.py      │ (LoRA W + (alpha/r)*BA 原生数学梯度下降仿真)              │
│ client_example.py         │ (零依赖原生 Python SDK 参考实现)                         │
└───────────────────────────┴───────────────────────────┬──────────────────────────────┘
                                                        │
                                                        │ 量化导出 (04_export_to_pixel10.py)
                                                        │ W4A16 INT4 权重 (1.8GB) + ADB Push
                                                        │
                                                        ▼
                            ┌──────────────────────────────────────────────────────────┐
                            │     Google Pixel 10 (Tensor G5 Edge Sensor Node)         │
                            │                                                          │
                            │  - 硬件边界: 可用物理内存 <= 4.5GB, 被动散热功耗 < 2W     │
                            │  - 移动运行时: Google LiteRT / MediaPipe GenAI Task      │
                            │  - 零拷贝管线: CameraX HardwareBuffer 直通 Edge TPU      │
                            │  - 本地常驻: Qwen2.5-VL-3B-INT4 + Whisper-Tiny (离线感知) │
                            │  - 协同上报: 遇复杂疑难切片 ➔ 局域网请求 Mac Studio 网关  │
                            └──────────────────────────────────────────────────────────┘
```

---

## 核心 Demo 重点速览 (Key Highlights)

| 编号与模块 | 对应脚本 | 核心功能与亮点 | 解决的技术痛点 / 关键价值 |
| :--- | :--- | :--- | :--- |
| **Lab 01: 视觉时序推理** | `01_video_vlm_inference.py` | • 时序抽帧并编码为标准 JPEG Data URI<br>• 直连本地 LM Studio（自动探测 loaded 状态模型）<br>• 捕获思考链（`reasoning_content`）与图像落盘 | 验证多帧时序图像在本地 VLM 下的端到端调用与结构化研判链路 |
| **Lab 02: 语音交互闭环** | `02_audio_whisper_tts.py` | • 纯 Python 生成/加载 16kHz PCM 单声道音频<br>• 端侧低功耗 VAD 静音切除<br>• Whisper ASR 语音转写 + 本地 TTS 朗读（`--play`） | 建立轻量级、低延迟、零云端依赖的端到端双向语音交互闭环 |
| **Lab 03: VLM LoRA 训练** | `03_vlm_lora_dataset_and_train.py` | • 自动化生成 ShareGPT 图文数据集与 JSON Schema 校验<br>• 输出 MLX LoRA 生产级微调命令<br>• **原生数学级 LoRA 梯度下降仿真**（$W + \frac{\alpha}{r}BA$） | 在无需 GPU 算力集群前提下透彻理解低秩适配器（Loss 降低 87%）与微调原理 |
| **Lab 04: 端侧量化与部署** | `04_export_to_pixel10.py` | • 测算 3.0B 模型从 FP16 (6GB) 到 INT4 (1.8GB) 的压缩比与显存预算<br>• 针对 Pixel 10 硬件约束（$\le 4.5\text{GB}$ 内存、$< 2\text{W}$ 功耗）安全校验<br>• 生成 LiteRT/GGUF/ExecuTorch 转换矩阵与 CameraX 零拷贝代码 | 解决多模态大模型落地移动边缘端算力、显存与零拷贝直通核心工程难点 |
| **Lab 05: 本地 HTTP 网关** | `05_local_multimodal_server.py` | • 纯 Python 标准库构建零依赖 OpenAI 兼容 HTTP 网关（端口 8000）<br>• 提供 `/health`、`/v1/models`、`/v1/chat/completions`、`/v1/audio/transcriptions` | 充当桌面边缘中枢，打通局域网 Pixel 10、Web 客户端与本地模型的统一接入与联调 |
---

## 快速开始

### 方式一：一键运行全部 6 阶段端到端流水线
```bash
bash run_all_labs.sh
```
*自动完成环境探测（Apple Silicon 芯片检测、统一内存 UMA 探测、可选工具检查），并依次执行 6 阶段实操练习与客户端联调流水线。*

### 方式二：交互式终端控制台菜单
```bash
bash run_all_labs.sh --menu
# 或直接运行
python3 interactive_menu.py
```
*提供 TUI 数字菜单，支持按需单选练习 1~4、环境探测或算力预算估算器。*

### 方式三：真机环境就绪检查与 Pixel 10 ADB 模型推送
```bash
# 检查 Mac Studio 与 Pixel 10 工具链 (Python, Metal, FFmpeg, ADB 在线设备)
bash setup_environment.sh --check

# 一键安装 Apple Silicon 原生 MLX 多模态组件
bash setup_environment.sh --install-mac-mlx

# 将量化导出的模型通过 ADB 推送至在线的 Pixel 10 手机端
bash setup_environment.sh --push-pixel10 /path/to/qwen2.5_vl_3b_w4a16.task
```

### 方式四：Developer Makefile 快捷指令
```bash
make demo    # 运行全量 6 阶段流水线
make menu    # 打开交互式终端控制台
make test    # 运行 26 项单元测试
make check   # 探测硬件与 ADB 设备
make report  # 查看技术雷达与基准看板
make server  # 启动本地多模态网关服务 (8000端口)
```

---

## 5 套实操练习详解

### 练习 1：Mac Studio 视频抽帧与本地 LM Studio 视觉大模型 (VLM) 实时调用
* **脚本文件**：`01_video_vlm_inference.py`
* **功能**：
  1. 读取预置测试时序抽帧图片或动态生成测试帧；
  2. 自动读取 `.env` 中 `LLM_BASE_URL` 配置（如 `http://localhost:1234/v1`），直连本地真实运行的 **LM Studio**；
  3. 自动探测并匹配 LM Studio 中处于 `loaded` 状态的视觉模型（如 `qwen3.8-27b-splash`、`qwen3-vl-8b-instruct`）；
  4. 自动以标准 JPEG Data URI 封装图像帧，完全兼容本地多模态校验；
  5. 支持展示模型的深度思考链（`reasoning_content`）与结构化研判；
  6. 支持指定 `--dump-frames /path` 将抽帧图片保存到本地硬盘查看。
* **命令示例**：
  ```bash
  # 默认一键直连本地 LM Studio
  python3 01_video_vlm_inference.py

  # 指定特定已加载的模型与提示词
  python3 01_video_vlm_inference.py --model qwen3-vl-8b-instruct --prompt "分析时序画面是否存在设备故障"

  # 导出抽帧图像到本地目录
  python3 01_video_vlm_inference.py --dump-frames /tmp/vlm_frames
  ```

---

### 练习 2：Mac Studio 音频大模型 (Whisper ASR + TTS) 语音交互闭环
* **脚本文件**：`02_audio_whisper_tts.py`
* **功能**：
  1. 纯 Python 原生生成 16kHz PCM 单声道测试音频波形；
  2. 模拟端侧低功耗语音活动检测 (VAD)，滤除静音区间；
  3. 模拟 ANE 硬件加速的 Whisper-large-v3-turbo 极速语音转写；
  4. 触发本地语音合成 (TTS) 反馈（在 macOS 上加 `--play` 可调用系统语音合成引擎直接发音朗读）。
* **命令示例**：
  ```bash
  # 默认运行（自动调用本地 Whisper 模型进行音频转写）
  python3 02_audio_whisper_tts.py

  # 在 Mac 扬声器中播放合成的回复语音
  python3 02_audio_whisper_tts.py --play

  # 传入自己录制的真实 WAV 音频文件
  python3 02_audio_whisper_tts.py --audio /path/to/my_record.wav --play
  ```
---

### 练习 3：Mac Studio 多模态大模型 LoRA 微调与数学梯度下降
* **脚本文件**：`03_vlm_lora_dataset_and_train.py`
* **功能**：
  1. 自动生成标准 ShareGPT 多模态图文对数据集（`train.jsonl` 与 `valid.jsonl`）；
  2. 严格校验助手输出是否 100% 满足工业级 JSON Schema；
  3. 规划并输出真实的 MLX LoRA 训练命令；
  4. **原生数学级 LoRA 仿真**：使用原生 Python 完整计算 $W + \frac{\alpha}{r}BA$ 的前向传播与反向传播，演示在冻结基座权重前提下仅更新低秩适配器使 Loss 降低 87% 的过程。
* **命令示例**：
  ```bash
  python3 03_vlm_lora_dataset_and_train.py
  ```
---

### 练习 4：W4A16 4-bit 量化导出与 Pixel 10 端侧部署
* **脚本文件**：`04_export_to_pixel10.py`
* **功能**：
  1. 精确测算 3.0B 视觉模型从 FP16 (6.0GB) 到 W4A16 INT4 (1.8GB) 的压缩比与显存开销；
  2. 对标 Google Pixel 10 硬件约束（<= 4.5GB 可用内存上限），校验部署安全性；
  3. 自动生成包含 LiteRT、llama.cpp GGUF、ExecuTorch 三大端侧运行时的标准转换命令矩阵；
  4. 生成直接可贴入 Android Studio 的 CameraX 零拷贝 HardwareBuffer 调用模板代码。
* **命令示例**：
  ```bash
  python3 04_export_to_pixel10.py
  ```
---

### 练习 5：Mac Studio 本地 OpenAI 兼容多模态 HTTP API 网关服务
* **脚本文件**：`05_local_multimodal_server.py`
* **功能**：
  1. 纯 Python 标准库构建零依赖 OpenAI 兼容 HTTP 网关；
  2. 提供 `GET /health`（硬件/加速器状态）、`GET /v1/models`（模型枚举）；
  3. 提供 `POST /v1/chat/completions`（多模态视觉问答）、`POST /v1/audio/transcriptions`（语音转写）；
  4. 允许局域网内的 Pixel 10、Web 客户端或 Agent 框架跨端调用。
* **命令示例**：
  ```bash
  # 在前台启动正式网关服务供局域网 / 手机调用 (端口 8000)
  python3 05_local_multimodal_server.py --port 8000 --host 0.0.0.0

  # 执行自动化全路由联调自测
  python3 05_local_multimodal_server.py --test
  ```
#### 客户端与网关服务联动联调命令：
```bash
# 终端 A：在 Mac Studio 上启动本地多模态网关服务
python3 05_local_multimodal_server.py --port 8000

# 终端 B：实操 1 客户端直连网关发送视频抽帧
python3 01_video_vlm_inference.py --endpoint http://localhost:8000/v1/chat/completions

# 终端 B：实操 2 客户端直连网关发送音频执行 Whisper 转写
python3 02_audio_whisper_tts.py --endpoint http://localhost:8000/v1/audio/transcriptions
```

---

## 样例数据与真机测试资源 (`sample_data/`)

套件内置了可直接查看与训练验证的静态真实样例资源：
* `sample_data/train.jsonl`：包含 4 条真实多模态标注的 ShareGPT 格式训练数据（含 `<image>` 占位与结构化 JSON 输出契约）；
* `sample_data/valid.jsonl`：验证集样例；
* `sample_data/video_inspection_metadata.json`：工业监控切片元数据定义（包含摄像头编号、分辨率、采样步长与目标 ROI 坐标）；
* `sample_data/frames/`：预先生成的 4 张 BMP 关键帧图片（可直接在 Finder / 系统看图器中查看）。
* `sample_data/audio/sample_inspection_16k.wav`：标准 16kHz PCM 单声道测试音频（包含多频段语音特征与静音段，供 Whisper 与 VAD 练习无缝读取）。
