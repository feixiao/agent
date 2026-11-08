"""Google Gemini 原生文生图封装，带留证。

密钥只从环境变量 GEMINI_API_KEY 读取。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from receipts import ReceiptBook, utc_now

IMAGE_MODEL = "gemini-2.5-flash-image"


def generate_image(prompt: str, out_path: Path, book: ReceiptBook, name: str) -> Path:
    """生成图片并保存为 PNG，返回路径。优先支持本地 ComfyUI (Qwen Image 2.1)，未配置时回退至 Gemini。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    t0 = time.time()
    status = "ok"
    resp_summary = {}

    comfy_base = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
    use_comfy = ("GEMINI_API_KEY" not in os.environ) or (os.getenv("IMAGE_PROVIDER") == "comfyui")

    if use_comfy:
        comfy_model = os.getenv("COMFYUI_IMAGE_MODEL", "qwen_image_2.1")
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from agentbook.comfyui import generate_image_comfyui

            image_bytes, mime, call_rec = generate_image_comfyui(
                prompt=prompt,
                base_url=comfy_base,
                model=comfy_model,
            )
            out_path.write_bytes(image_bytes)
            resp_summary["mime_type"] = mime
            resp_summary["image_bytes"] = len(image_bytes)
            resp_summary["saved_to"] = str(out_path)
        except Exception as e:
            status = "error"
            resp_summary["error"] = repr(e)
            raise
        finally:
            ended = utc_now()
            book.record(name, provider="comfyui",
                        endpoint=f"{comfy_base}/prompt",
                        model=comfy_model,
                        request={"model": comfy_model, "contents": prompt},
                        response=resp_summary,
                        started_utc=started, ended_utc=ended,
                        latency_ms=int((time.time() - t0) * 1000), status=status)
        return out_path

    from google import genai
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(model=IMAGE_MODEL, contents=prompt)
        image_bytes = None
        for part in resp.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                resp_summary["mime_type"] = part.inline_data.mime_type
                break
        if image_bytes is None:
            status = "error"
            resp_summary["error"] = "响应中无图像数据"
            raise RuntimeError("Gemini 响应中无图像数据")
        out_path.write_bytes(image_bytes)
        resp_summary["image_bytes"] = len(image_bytes)
        resp_summary["saved_to"] = str(out_path)
        ended = utc_now()
        book.record(name, provider="google-gemini",
                    endpoint="google-genai:models/generate_content",
                    model=IMAGE_MODEL,
                    request={"model": IMAGE_MODEL, "contents": prompt},
                    response=resp_summary,
                    started_utc=started, ended_utc=ended,
                    latency_ms=int((time.time() - t0) * 1000), status=status)
    return out_path
