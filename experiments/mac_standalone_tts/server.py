"""Lightweight Local HTTP API Server & WebUI for Mac Standalone TTS.

Fully offline, running on Apple Silicon Metal (MPS).
Provides:
- OpenAI-compatible TTS endpoint: POST /v1/audio/speech
- Custom endpoint: POST /synthesize
- Status / Health: GET /health
- Built-in Local WebUI: GET /
"""

from __future__ import annotations

import base64
import io
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
import soundfile as sf
import torch

from .config import MacTTSConfig, get_optimal_device
from .pipeline import MacTTSPipeline

_pipeline: Optional[MacTTSPipeline] = None


def get_pipeline() -> MacTTSPipeline:
    global _pipeline
    if _pipeline is None:
        cfg = MacTTSConfig(device=get_optimal_device())
        _pipeline = MacTTSPipeline(cfg)
    return _pipeline


WEBUI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mac Standalone TTS (Apple Silicon Metal)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; display: flex; justify-content: center; }
        .container { max-width: 760px; width: 100%; background: #1e293b; border-radius: 12px; padding: 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border: 1px solid #334155; }
        h1 { margin-top: 0; font-size: 1.6rem; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
        .badge { background: #0284c7; color: #fff; font-size: 0.75rem; padding: 2px 8px; border-radius: 9999px; }
        label { display: block; font-weight: 600; margin-top: 1rem; margin-bottom: 0.4rem; color: #94a3b8; }
        textarea, input, select { width: 100%; box-sizing: border-box; background: #0f172a; border: 1px solid #334155; color: #f8fafc; border-radius: 8px; padding: 0.75rem; font-size: 0.95rem; }
        textarea:focus, input:focus { border-color: #38bdf8; outline: none; }
        button { margin-top: 1.5rem; width: 100%; background: #2563eb; color: #fff; border: none; padding: 0.85rem; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #1d4ed8; }
        .status-box { margin-top: 1rem; padding: 0.75rem; border-radius: 8px; background: #0f172a; border: 1px solid #334155; font-size: 0.85rem; color: #cbd5e1; }
        audio { width: 100%; margin-top: 1rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Mac Standalone TTS <span class="badge">Apple Silicon MPS</span></h1>
        <p style="color: #94a3b8; font-size: 0.9rem;">全单机离线运行 · 零网络请求 · 统一内存 Metal 加速</p>
        
        <label for="text">合成文本：</label>
        <textarea id="text" rows="4" placeholder="在此输入需要合成的文字，例如：苹果芯片的统一内存与Metal加速，让本地语音微调和离线推理成为现实。">苹果芯片的统一内存与Metal加速，让本地语音微调和离线推理成为现实。</textarea>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
                <label for="temperature">采样温度 (Temperature):</label>
                <input type="number" id="temperature" value="0.8" step="0.1" min="0.1" max="1.5">
            </div>
            <div>
                <label for="top_k">Top-K 候选采样:</label>
                <input type="number" id="top_k" value="50" step="5" min="1" max="200">
            </div>
        </div>

        <button id="btn-synth" onclick="synthesize()">一键合成语音 (MPS 加速)</button>

        <div id="status" class="status-box">准备就绪。点击按钮在 Mac 本地执行合成。</div>
        <audio id="player" controls style="display:none;"></audio>
    </div>

    <script>
        async function synthesize() {
            const btn = document.getElementById('btn-synth');
            const status = document.getElementById('status');
            const player = document.getElementById('player');
            const text = document.getElementById('text').value.trim();
            const temperature = parseFloat(document.getElementById('temperature').value);
            const top_k = parseInt(document.getElementById('top_k').value);

            if (!text) { alert('请输入待合成文本'); return; }

            btn.disabled = true;
            btn.innerText = '正在本地合成中 (MPS Metal)...';
            status.innerText = '执行推理中：文本音素对齐 -> AR-GPT 语义预测 -> SoVITS 神经声码器波形渲染...';

            try {
                const res = await fetch('/v1/audio/speech', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ input: text, temperature, top_k, response_format: 'wav' })
                });

                if (!res.ok) throw new Error('HTTP ' + res.status);
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                player.src = url;
                player.style.display = 'block';
                player.play();

                const rtf = res.headers.get('X-RTF') || '0.2';
                const latency = res.headers.get('X-Latency-Ms') || '200';
                status.innerText = `合成成功！耗时: ${latency}ms | RTF: ${rtf} | 本机脱网离线运行`;
            } catch (err) {
                status.innerText = '合成出错: ' + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = '一键合成语音 (MPS 加速)';
            }
        }
    </script>
</body>
</html>
"""


class TTSRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request handler for Mac TTS services."""

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = WEBUI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            pipeline = get_pipeline()
            self._send_json(200, {
                "status": "healthy",
                "device": str(pipeline.device),
                "mps_available": torch.backends.mps.is_available(),
                "sample_rate": pipeline.config.audio.sample_rate,
            })
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len)

        try:
            req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON payload: {e}"})
            return

        pipeline = get_pipeline()

        # Handle OpenAI TTS compatibility endpoint: /v1/audio/speech
        if self.path == "/v1/audio/speech":
            text = req_data.get("input", "").strip()
            if not text:
                self._send_json(400, {"error": "Field 'input' is required."})
                return

            temperature = float(req_data.get("temperature", 0.8))
            top_k = int(req_data.get("top_k", 50))

            wav, sr, metrics = pipeline.synthesize(
                text=text,
                temperature=temperature,
                top_k=top_k,
            )

            # Export to WAV buffer
            wav_np = wav.squeeze(0).detach().cpu().numpy()
            buf = io.BytesIO()
            sf.write(buf, wav_np, sr, format="WAV", subtype="PCM_16")
            audio_bytes = buf.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("X-RTF", str(metrics["rtf"]))
            self.send_header("X-Latency-Ms", str(metrics["latency_ms"]))
            self.send_header("X-Throughput", str(metrics["throughput_sec_per_sec"]))
            self.end_headers()
            self.wfile.write(audio_bytes)

        # Handle custom /synthesize endpoint
        elif self.path == "/synthesize":
            text = req_data.get("text", "").strip()
            if not text:
                self._send_json(400, {"error": "Field 'text' is required."})
                return

            wav, sr, metrics = pipeline.synthesize(text=text)
            wav_np = wav.squeeze(0).detach().cpu().numpy()
            buf = io.BytesIO()
            sf.write(buf, wav_np, sr, format="WAV", subtype="PCM_16")
            audio_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            self._send_json(200, {
                "audio_base64": audio_b64,
                "sample_rate": sr,
                "metrics": metrics,
            })
        else:
            self.send_error(404, "Endpoint Not Found")


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start local HTTP server."""
    pipeline = get_pipeline()
    server = HTTPServer((host, port), TTSRequestHandler)
    print(f"Mac Standalone TTS Server running on http://{host}:{port}")
    print(f"Compute Backend: {pipeline.device} (Metal MPS)")
    print(f"OpenAI TTS Endpoint: http://{host}:{port}/v1/audio/speech")
    print(f"WebUI: http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()
