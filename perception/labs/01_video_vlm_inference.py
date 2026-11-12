#!/usr/bin/env python3
"""
实操练习 1：Mac Studio 视频帧抽取与视觉多模态大模型 (VLM) 调用
演示：
1. 纯 Python / 零外部依赖生成合成测试测试帧（或调用 OpenCV）。
2. 构建符合 OpenAI / MLX-VLM / Ollama 标准的视觉多模态 Payload。
3. 模拟与真实本地端点（Ollama / LM Studio / MLX Server）交互。

运行方式：
    python3 01_video_vlm_inference.py
    # 或指定本地视觉模型与提示词
    python3 01_video_vlm_inference.py --model qwen3-vl-8b-instruct --prompt "画面中有何内容？"
"""
import argparse
import base64
import json
import os
import struct
import sys
import urllib.request
from pathlib import Path

# 优先加载根目录 .env
try:
    from dotenv import find_dotenv, load_dotenv
    _env_path = find_dotenv(usecwd=True)
    if not _env_path:
        _root = Path(__file__).resolve().parent.parent.parent / ".env"
        if _root.exists():
            _env_path = str(_root)
    if _env_path:
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

def detect_local_vlm_model(endpoint_url: str) -> str:
    """自动探测本地 LM Studio / Ollama 中已就绪/已加载的多模态/视觉模型"""
    host_base = endpoint_url.split("/v1")[0].rstrip("/")
    # 1. 尝试 LM Studio 原生 /api/v0/models (能精准拿到 state=="loaded")
    try:
        req = urllib.request.Request(f"{host_base}/api/v0/models", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data", [])
            # 优先挑已经在内存中 loaded 且包含 vl/vision 的多模态视觉模型
            loaded_vl = [
                m["id"] for m in data 
                if m.get("state") == "loaded" and (m.get("type") == "vlm" or any(k in m.get("id", "").lower() for k in ("vl", "vision", "visual")))
            ]
            # 优先选择名称明确带有 vl 的视觉专精模型
            explicit_vl = [m for m in loaded_vl if "vl" in m.lower()]
            if explicit_vl:
                return explicit_vl[0]
            if loaded_vl:
                return loaded_vl[0]
    except Exception:
        pass

    # 2. 尝试标准 /v1/models
    try:
        v1_base = endpoint_url.split("/chat/completions")[0].rstrip("/")
        req = urllib.request.Request(f"{v1_base}/models", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            model_list = [m.get("id", "") for m in data.get("data", [])]
            vl_models = [m for m in model_list if any(k in m.lower() for k in ("-vl-", "vl", "vision", "visual"))]
            if vl_models:
                return vl_models[0]
            if model_list:
                return model_list[0]
    except Exception:
        pass
    return "qwen3-vl-8b-instruct"
def create_synthetic_bmp_frame(width: int = 128, height: int = 128, color: tuple = (30, 144, 255)) -> bytes:
    """纯 Python 生成一张无第三方依赖的 BMP 格式测试图像 (24-bit RGB)"""
    r, g, b = color
    row_bytes = width * 3
    padding = (4 - (row_bytes % 4)) % 4
    image_size = (row_bytes + padding) * height
    file_size = 54 + image_size

    # BMP Header (14 bytes) + DIB Header (40 bytes)
    header = struct.pack(
        "<2sIHHI", b"BM", file_size, 0, 0, 54
    )
    dib = struct.pack(
        "<IIIHHIIIIII", 40, width, height, 1, 24, 0, image_size, 2835, 2835, 0, 0
    )
    
    # Pixel data (bottom-up, BGR format)
    pixel_data = bytearray()
    pad = b"\x00" * padding
    for _ in range(height):
        for _ in range(width):
            pixel_data.extend(bytes([b, g, r]))
        pixel_data.extend(pad)

    return bytes(header + dib + pixel_data)

def simulate_video_frames(num_frames: int = 4) -> list:
    """模拟从视频时间轴抽取的关键帧集合"""
    colors = [
        (30, 144, 255),  # 蓝色 (第 0 秒：工人进入通道)
        (255, 165, 0),   # 橙色 (第 2 秒：工人靠近设备)
        (220, 20, 60),   # 红色 (第 4 秒：检测到设备报警灯闪烁)
        (50, 205, 50),   # 绿色 (第 6 秒：工人按下安全切断开关)
    ]
    frames = []
    for i in range(num_frames):
        color = colors[i % len(colors)]
        bmp_bytes = create_synthetic_bmp_frame(color=color)
        b64_str = base64.b64encode(bmp_bytes).decode("utf-8")
        frames.append({
            "frame_id": i,
            "timestamp_sec": i * 2.0,
            "base64_data": b64_str,
            "simulated_scene": f"时间轴 {i*2.0}s: 场景特征状态值 {color}"
        })
    return frames

def load_or_simulate_video_frames(sample_dir: str = None, num_frames: int = 4) -> tuple:
    """
    优先从 sample_data/frames/ 加载真实预置的 BMP 关键帧图片；
    若目录不存在或为空，则无缝回退到纯 Python 动态生成测试帧。
    返回: (frames, source_description)
    """
    if sample_dir is None:
        default_dir = Path(__file__).resolve().parent / "sample_data" / "frames"
        if default_dir.exists():
            sample_dir = str(default_dir)

    if sample_dir and os.path.isdir(sample_dir):
        img_files = sorted([p for p in Path(sample_dir).iterdir() if p.suffix.lower() in (".bmp", ".jpg", ".jpeg", ".png")])
        if img_files:
            frames = []
            for i, p in enumerate(img_files[:num_frames]):
                raw_bytes = p.read_bytes()
                mime_type = "image/jpeg"
                # 尝试用 PIL 转为标准的真实 JPEG，避免部分引擎解码 BMP 失败
                try:
                    from PIL import Image
                    import io
                    im = Image.open(p)
                    buf = io.BytesIO()
                    im.convert("RGB").save(buf, format="JPEG")
                    raw_bytes = buf.getvalue()
                except Exception:
                    if p.suffix.lower() == ".png":
                        mime_type = "image/png"
                
                b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                frames.append({
                    "frame_id": i,
                    "timestamp_sec": i * 2.0,
                    "mime_type": mime_type,
                    "base64_data": b64_str,
                    "file_path": str(p),
                    "simulated_scene": f"从预置样例加载: {p.name}"
                })
            return frames, f"预置样本目录 ({sample_dir})"

    frames = simulate_video_frames(num_frames)
    return frames, "纯 Python 动态生成测试帧"

def build_vlm_request(frames: list, user_prompt: str, model: str = "qwen2.5-vl:7b") -> dict:
    """构建标准多模态交互消息格式"""
    content = []
    for frame in frames:
        # 兼容主流本地推理端点（LM Studio / Ollama / vLLM / OpenAI），使用标准 image/jpeg MIME
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{frame.get('mime_type', 'image/jpeg')};base64,{frame['base64_data']}"
            }
        })
    content.append({
        "type": "text",
        "text": f"你是一个工业边缘视觉安全分析专家。请根据这 {len(frames)} 张连续视频抽帧分析：{user_prompt}"
    })
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 1024
    }

def call_local_vlm_mock_or_live(payload: dict, endpoint_url: str = None) -> dict:
    """向本地 LM Studio / Ollama 发起真实多模态 HTTP 推理调用"""
    if not endpoint_url:
        raise RuntimeError("未配置本地大模型端点 (endpoint_url 为空)，请确保 LM Studio 已启动并在 .env 中配置 LLM_BASE_URL。")

    try:
        req = urllib.request.Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            msg = raw.get("choices", [{}])[0].get("message", {})
            content = msg.get("content") or raw.get("message", {}).get("content") or ""
            reasoning = msg.get("reasoning_content")
            if not content and reasoning:
                content = "(模型主要完成了深度思维链推理，请参见下方思考过程)"
            elif not content:
                content = str(raw)
            usage = raw.get("usage", {})
            res = {
                "status": "success",
                "inference_engine": "LM Studio (OpenAI Compatible Live HTTP)",
                "model": raw.get("model", payload["model"]),
                "analysis_report": {
                    "summary": content,
                },
                "usage": usage,
                "raw_response": raw
            }
            if reasoning:
                res["analysis_report"]["reasoning"] = reasoning
            return res
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LM Studio 请求返回错误 [{e.code}]: {err_body}") from e
    except Exception as e:
        raise RuntimeError(f"连接本地 LM Studio ({endpoint_url}) 失败: {str(e)}") from e

def save_frames_to_disk(frames: list, output_dir: str):
    """将提取的关键帧保存到本地目录供开发者核对"""
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    for f in frames:
        file_path = p / f"frame_{f['frame_id']:02d}_{f['timestamp_sec']}s.bmp"
        data = base64.b64decode(f["base64_data"])
        file_path.write_bytes(data)
    print(f"  - 抽帧图像已保存至本地: {p.resolve()} (共 {len(frames)} 帧)")

def main():
    parser = argparse.ArgumentParser(description="实操 1：Mac Studio 视频帧抽取与本地 LM Studio 视觉大模型调用")
    env_base = os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    default_endpoint = f"{env_base}/chat/completions"
    
    parser.add_argument("--demo", action="store_true", help="兼容历史参数（直接执行真实本地大模型端到端调用）")
    parser.add_argument("--endpoint", type=str, default=default_endpoint, help=f"LM Studio 接口端点 (默认: {default_endpoint})")
    parser.add_argument("--model", type=str, default=None, help="模型标识 (默认自动探测本地 LM Studio 中加载的视觉模型，或使用 LLM_MODEL)")
    parser.add_argument("--dump-frames", type=str, default=None, help="将抽取的关键帧图像保存到指定目录")
    parser.add_argument("--prompt", type=str, default="请根据这组视频时序关键帧，分析画面中的主要色彩、内容特征以及是否存在异常情况", help="提问提示词")
    args = parser.parse_args()

    endpoint = args.endpoint
    # 自动获取或探测多模态模型
    model = args.model
    if not model:
        env_model = os.getenv("LLM_MODEL", "")
        if any(k in env_model.lower() for k in ("vl", "vision", "visual")):
            model = env_model
        else:
            model = detect_local_vlm_model(endpoint)

    print("===============================================================")
    print(" 🎬 实操 1：Mac Studio 视频多模态 ➔ LM Studio 本地大模型实时调用")
    print("===============================================================")
    print(f"🔗 本地服务地址: {endpoint}")
    print(f"🤖 目标视觉模型: {model}")
    
    frames, source_desc = load_or_simulate_video_frames(num_frames=4)
    print(f"\n[步骤 1] 正在加载视频时序关键帧 (数据源: {source_desc})...")
    for f in frames:
        print(f"  - 提取帧 #{f['frame_id']} | 时间戳: {f['timestamp_sec']}s | 编码大小: {len(f['base64_data'])} 字符")
    if args.dump_frames:
        save_frames_to_disk(frames, args.dump_frames)

    print(f"\n[步骤 2] 正在构建符合 LM Studio / OpenAI 标准的多模态 Payload...")
    payload = build_vlm_request(frames, args.prompt, model=model)
    print(f"  - 模型标识: {payload['model']}")
    print(f"  - 挂载图像: {len(frames)} 帧时序图片")
    print(f"  - 用户提问: {args.prompt}")

    print(f"\n[步骤 3] 发送请求至本地 LM Studio 执行真实多模态推理...")
    result = call_local_vlm_mock_or_live(payload, endpoint)
    
    print("\n[步骤 4] LM Studio 真实推理分析响应：")
    print(f"  - 状态: {result['status']}")
    print(f"  - 引擎: {result['inference_engine']}")
    print(f"  - 模型: {result['model']}")
    print(f"  - Token 统计: {result.get('usage', {})}")
    print("\n--- [模型回复内容] ---")
    print(result["analysis_report"]["summary"])
    if "reasoning" in result["analysis_report"]:
        print("\n--- [模型思考过程] ---")
        print(result["analysis_report"]["reasoning"])
    print("----------------------")
    print("\n✅ 实操 1 验证成功：本地 LM Studio 视觉大模型多模态调用端到端跑通！\n")

if __name__ == "__main__":
    main()
