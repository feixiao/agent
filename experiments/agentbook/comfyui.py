"""ComfyUI 本地图像生成集成模块 (Qwen Image 2.1 等本地模型)。

支持通过 ComfyUI REST API (/prompt -> /history -> /view) 或兼容的
/v1/images/generations 接口，在本地完成高质量图像生成，并返回调用留证。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

DEFAULT_COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
DEFAULT_COMFYUI_MODEL = os.getenv("COMFYUI_IMAGE_MODEL", "qwen_image_2.1")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_comfyui_running(base_url: str = DEFAULT_COMFYUI_BASE_URL) -> bool:
    """检查 ComfyUI 服务是否可访问。"""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/system_stats", timeout=3)
        return r.status_code == 200
    except Exception:
        try:
            r = requests.get(f"{base_url.rstrip('/')}/", timeout=3)
            # 部分环境如 Comfy Desktop 可能返回 200 或 401 (需要 auth header)
            return r.status_code in (200, 401, 403)
        except Exception:
            return False


def build_default_qwen_workflow(
    prompt: str,
    negative_prompt: str = "",
    model_name: str = DEFAULT_COMFYUI_MODEL,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 6.0,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """生成适用于 Qwen Image 2.1 / 经典扩散模型的标准 ComfyUI API 提示词工作流图。"""
    actual_seed = seed if seed is not None else int(time.time() * 1000) % (2**31)
    ckpt = model_name
    if not (ckpt.endswith(".safetensors") or ckpt.endswith(".ckpt")):
        ckpt = f"{model_name}.safetensors"

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": 1.0,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": actual_seed,
                "steps": steps,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": ckpt,
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": height,
                "width": width,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": prompt,
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": negative_prompt or "low quality, bad anatomy, blurry, worst quality",
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "QwenImage",
                "images": ["8", 0],
            },
        },
    }


def load_custom_workflow_template(
    workflow_path: str | Path,
    prompt: str,
    negative_prompt: str = "",
) -> Dict[str, Any]:
    """读取用户自定义 ComfyUI API 工作流 JSON，并将提示词注入到 CLIPTextEncode 节点中。"""
    path = Path(workflow_path)
    if not path.is_file():
        raise FileNotFoundError(f"未找到指定的 ComfyUI 工作流模板文件: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    workflow = data.get("prompt", data)  # 兼容带外层 prompt 包装或纯图格式

    # 寻找 CLIPTextEncode 节点并注入
    replaced_positive = False
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
            inputs = node.get("inputs", {})
            title = node.get("_meta", {}).get("title", "").lower()
            if not replaced_positive or "positive" in title:
                inputs["text"] = prompt
                replaced_positive = True
            elif negative_prompt and ("negative" in title or replaced_positive):
                inputs["text"] = negative_prompt

    return workflow


def generate_image_comfyui(
    prompt: str,
    negative_prompt: str = "",
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 6.0,
    workflow_file: Optional[str] = None,
    timeout: float = 180.0,
) -> Tuple[bytes, str, Dict[str, Any]]:
    """调用本地 ComfyUI (Qwen Image 2.1) 生成图像。

    返回:
        (image_bytes, mime_type, call_record)
    """
    url = (base_url or os.getenv("COMFYUI_BASE_URL") or DEFAULT_COMFYUI_BASE_URL).rstrip("/")
    model_name = model or os.getenv("COMFYUI_IMAGE_MODEL") or DEFAULT_COMFYUI_MODEL
    workflow_path = workflow_file or os.getenv("COMFYUI_WORKFLOW")

    call_record: Dict[str, Any] = {
        "call_id": uuid.uuid4().hex[:12],
        "provider": "comfyui",
        "model": model_name,
        "endpoint": f"{url}/prompt",
        "started_at": _utc_now(),
        "finished_at": None,
        "latency_ms": None,
        "status": "ok",
        "request": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "model": model_name,
            "width": width,
            "height": height,
        },
        "response_id": None,
        "usage": {},
        "error": None,
    }

    t0 = time.monotonic()

    # 1. 优先尝试 OpenAI 兼容图像生成接口（如部署了 ComfyUI-OpenAI 插件或本地网关）
    v1_url = f"{url}/v1/images/generations"
    try:
        r_v1 = requests.post(
            v1_url,
            json={
                "model": model_name,
                "prompt": prompt,
                "size": f"{width}x{height}",
                "n": 1,
            },
            timeout=10,
        )
        if r_v1.status_code == 200:
            res = r_v1.json()
            call_record["endpoint"] = v1_url
            call_record["response_id"] = str(res.get("created", ""))
            data = res.get("data", [])[0]
            if "b64_json" in data:
                img_bytes = base64.b64decode(data["b64_json"])
            elif "url" in data:
                img_bytes = requests.get(data["url"], timeout=30).content
            else:
                raise ValueError("响应中未找到图片数据")
            call_record["finished_at"] = _utc_now()
            call_record["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
            return img_bytes, "image/png", call_record
    except Exception:
        # 回退至 ComfyUI 原生 WebSocket / REST API
        pass

    # 2. 构建工作流提示词图
    if workflow_path and os.path.isfile(workflow_path):
        workflow = load_custom_workflow_template(workflow_path, prompt, negative_prompt)
    else:
        workflow = build_default_qwen_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=model_name,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
        )

    # 3. 提交任务 /prompt
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    try:
        r = requests.post(f"{url}/prompt", json=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(
                f"ComfyUI 任务提交失败 (HTTP {r.status_code}): {r.text}\n"
                f"请检查 ComfyUI 是否已在 {url} 启动，并确认已加载 {model_name} 模型。"
            )
        resp_data = r.json()
        prompt_id = resp_data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 返回未包含 prompt_id: {resp_data}")
        call_record["response_id"] = prompt_id
    except requests.exceptions.ConnectionError as e:
        call_record["status"] = "error"
        err_msg = (
            f"无法连接到本地 ComfyUI ({url})。\n"
            f"请先启动 ComfyUI，或在 .env 中设置 COMFYUI_BASE_URL (当前: {url})"
        )
        call_record["error"] = err_msg
        call_record["finished_at"] = _utc_now()
        call_record["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        raise ConnectionError(err_msg) from e
    except Exception as e:
        call_record["status"] = "error"
        call_record["error"] = f"{type(e).__name__}: {e}"
        call_record["finished_at"] = _utc_now()
        call_record["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        raise

    # 4. 轮询 /history/{prompt_id}
    deadline = time.monotonic() + timeout
    output_image_info: Optional[Dict[str, str]] = None

    while time.monotonic() < deadline:
        time.sleep(1.0)
        try:
            h_res = requests.get(f"{url}/history/{prompt_id}", timeout=10)
            if h_res.status_code == 200:
                history = h_res.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        images = node_output.get("images", [])
                        if images:
                            output_image_info = images[0]
                            break
                    if output_image_info:
                        break
                    # 如果执行已完成但没有输出图片
                    status = history[prompt_id].get("status", {})
                    if status.get("completed", False) and not output_image_info:
                        raise RuntimeError(f"ComfyUI 任务完成但无图片输出: {history[prompt_id]}")
        except Exception as e:
            logger.debug(f"轮询 ComfyUI history 异常: {e}")

    if not output_image_info:
        raise TimeoutError(f"等待 ComfyUI 出图超时 ({timeout}s), prompt_id: {prompt_id}")

    # 5. 下载图片 /view
    filename = output_image_info.get("filename", "")
    subfolder = output_image_info.get("subfolder", "")
    folder_type = output_image_info.get("type", "output")

    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    view_url = f"{url}/view?{urllib.parse.urlencode(params)}"
    view_resp = requests.get(view_url, timeout=30)
    view_resp.raise_for_status()

    img_bytes = view_resp.content
    mime = view_resp.headers.get("Content-Type", "image/png").split(";")[0]

    call_record["finished_at"] = _utc_now()
    call_record["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
    call_record["output"] = {
        "filename": filename,
        "bytes": len(img_bytes),
        "mime": mime,
    }
    return img_bytes, mime, call_record
