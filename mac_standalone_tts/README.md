# Mac Apple Silicon Standalone TTS (Metal MPS)

纯 Mac 单端全自闭环高保真语音克隆与离线合成系统。
无需任何云端 API，完全在 Apple Silicon M 系列芯片（Metal MPS）上实现数据清洗、音素对齐、双阶段微调与低延迟离线推理。

## 核心特性
- **纯本地脱网自闭环**：无需网络，无数据泄露风险。
- **Metal (MPS) 深度学习加速**：充分释放 Apple Silicon 统一内存带宽与 GPU 算力。
- **双阶段 GPT-SoVITS 架构**：AR-GPT 学习自然换气与韵律，SoVITS/HiFi-GAN 神经声码器渲染 32kHz 高保真无电音波形。
- **开箱即用生态兼容**：内置标准 OpenAI TTS 协议 (`POST /v1/audio/speech`)，即插即用接入 Legado 开源阅读、Calibre 电子书与 Mac 快捷指令。
- **极致性能**：Apple M4 Max 实测 **RTF 0.1959**（首字延迟 191.19ms，5.11x 吞吐量）。

## 快速上手

### 1. 运行基准评测
```bash
./autoresearch.sh
```

### 2. 运行自动化测试套件
```bash
PYTHONPATH=. uv run pytest mac_standalone_tts/tests/test_mac_tts_pipeline.py -v
```

### 3. 一键离线合成
```bash
PYTHONPATH=. uv run python -m mac_standalone_tts.cli infer \
    --text "苹果芯片的统一内存与Metal加速，让本地语音微调和离线推理成为现实。" \
    --output ./output.wav
```

### 4. 启动本地脱网 HTTP 服务 & WebUI
```bash
PYTHONPATH=. uv run python -m mac_standalone_tts.cli serve --host 127.0.0.1 --port 8000
```
访问浏览器 `http://127.0.0.1:8000/` 即可试听。

## 详细操作手册
完整的数据录制规范、VAD 清洗、MPS 微调超参数及第三方听书软件接入指南请参阅：
👉 [《Mac Apple Silicon 单机闭环高保真 TTS 操作手册》](docs/MAC_STANDALONE_TTS_MANUAL.md)
