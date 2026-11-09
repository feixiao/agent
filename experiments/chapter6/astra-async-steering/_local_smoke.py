"""One-off local smoke test: same wire protocol as experiment.py, pointed at
LM Studio (wss://localhost:1234/v1/responses). NOT part of the formal run.

Call 1: plain text response (no tools) -> validates connect/create/stream/complete.
Call 2: with one function tool -> validates whether the local model emits
function_call items at all (qwen3.8-27b-splash is not expected to support
response.steer / native async tool semantics, so acceptance is NOT expected).
"""
import asyncio
import json
import os
import sys
import time

import websockets
from websockets.asyncio.client import connect

WS = os.environ.get("LOCAL_WS", "wss://localhost:1234/v1/responses")
HTTP = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("LLM_MODEL", "qwen3.8-27b-splash")

import urllib.request

def http_health():
    req = urllib.request.Request(HTTP + "/models")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
            return [m.get("id") for m in body.get("data", [])][:5]
    except Exception as e:
        return f"ERROR: {e!r}"

async def one_request(tools, tag):
    settings = {"model": MODEL, "store": False,
                "instructions": "Answer in one short line.",
                "max_output_tokens": 200, "tools": tools, "parallel_tool_calls": False}
    t0 = time.monotonic()
    types = []
    try:
        async with connect(WS, additional_headers={
                "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "not-needed")},
                open_timeout=15, max_size=16 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"type": "response.create", **settings,
                                      "input": "Say OK."}))
            async for raw in ws:
                ev = json.loads(raw)
                t = ev.get("type")
                types.append(t)
                if t in {"response.completed", "response.failed", "error"}:
                    print(f"[{tag}] got terminal: {t} in {time.monotonic()-t0:.2f}s")
                    out = ev.get("response", ev.get("error")) or {}
                    break
            print(f"[{tag}] event stream: {types}")
    except Exception as e:
        print(f"[{tag}] EXCEPTION after {time.monotonic()-t0:.2f}s: {type(e).__name__}: {e}")
        print(f"[{tag}] events before failure: {types}")

async def main():
    print("http /models:", http_health())
    await one_request([], "plain")
    tools = [{"type": "function", "name": "lookup_venues",
              "description": "Read the venue inventory.",
              "parameters": {"type": "object", "properties": {}, "required": []}}]
    await one_request(tools, "tool")

if __name__ == "__main__":
    asyncio.run(main())
