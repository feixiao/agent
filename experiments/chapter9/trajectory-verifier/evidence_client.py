"""实验 9-1 的「无凭据」真实调用捕获客户端。

每次 chat/completions 调用都把原始请求/响应（不含 key 值）、耗时、
用量记入 api_turns，供证据落盘。注意：各 provider 的 base_url 在
BACKENDS 中显式写死（含 api.openai.com），不随 OPENAI_BASE_URL 环境变量
变化——因此它无法指向本地 LM Studio，本地只适合跑离线/启发式路径。
"""

from __future__ import annotations

import os
import time
from typing import Any

from openai import OpenAI


BACKENDS = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "moonshot": ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "kimi-k3"),
    "ark": ("ARK_API_KEY", "https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-1-6-250615"),
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
}


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _dump(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    return value


class EvidenceChatClient:
    """OpenAI-compatible client that records requests and responses, never keys."""

    def __init__(self, provider: str = "openrouter", model: str | None = None):
        if provider not in BACKENDS:
            raise ValueError(f"unsupported provider: {provider}")
        key_env, base_url, default_model = BACKENDS[provider]
        key = os.getenv(key_env)
        if not key:
            raise RuntimeError(f"{key_env} is required for provider={provider}")
        self.provider = provider
        self.model = model or default_model
        self.base_url = base_url
        self.credential_source_env = key_env
        self.client = OpenAI(api_key=key, base_url=base_url)
        self.api_turns: list[dict[str, Any]] = []

    def complete(self, *, kind: str, **kwargs: Any) -> Any:
        request = {"model": self.model, **kwargs}
        started = time.time()
        response = self.client.chat.completions.create(**request)
        elapsed = time.time() - started
        self.api_turns.append({
            "kind": kind,
            "endpoint": f"{self.base_url}/chat/completions",
            "provider": self.provider,
            "request": _dump(request),
            "response": _dump(response),
            "elapsed_seconds": round(elapsed, 6),
        })
        return response

    def usage_summary(self) -> dict[str, Any]:
        prompt = completion = total = 0
        native_cost = 0.0
        cost_observations = 0
        for turn in self.api_turns:
            usage = turn.get("response", {}).get("usage") or {}
            prompt += int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            completion += int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
            total += int(usage.get("total_tokens") or 0)
            if usage.get("cost") is not None:
                native_cost += float(usage["cost"])
                cost_observations += 1
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total or prompt + completion,
            "provider_reported_cost_usd": round(native_cost, 9) if cost_observations else None,
            "provider_reported_cost_observations": cost_observations,
            "cost_qualification": (
                "provider-native usage.cost summed across all calls"
                if cost_observations
                else "provider did not expose monetary cost; no price was guessed"
            ),
        }
