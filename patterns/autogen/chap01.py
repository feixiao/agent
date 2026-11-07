"""
基于 Autogen + Ollama 的提示链示例（提取 -> 转换）

说明：这个示例参考了 `langchain/chap01.py` 的两步链逻辑：
1) 提取文本中的技术规格；
2) 将提取到的规格格式化为 JSON（包含 cpu, memory, storage 三个字段）。

使用方法：
- 在根目录 `.env` 中配置 `LLM_BASE_URL` 与 `LLM_MODEL`。
- 确保本地推理服务（LM Studio / Ollama / vLLM）已启动并已加载对应模型。

示例运行：
```bash
uv run python patterns/autogen/chap01.py
```
"""

import os
import sys
from pathlib import Path
import asyncio
from dotenv import find_dotenv, load_dotenv

# 确保根目录在 sys.path 中并加载统一环境变量
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
load_dotenv(find_dotenv(usecwd=True))

from autogen_core.models import UserMessage
from patterns.env import create_autogen_client, get_base_url, get_model

async def run_chain(input_text: str, model_name: str):
    """执行两步提示链：提取 -> 转换。

    返回：最终的 JSON 字符串（模型输出的原始文本）。
    """
    # 根据统一环境变量创建模型客户端（支持 Ollama 与 OpenAI）
    client = create_autogen_client(model_name=model_name)

    # 第一步：提取技术规格
    prompt_extract = (
        "Extract the technical specifications from the following text:\n\n" + input_text
    )
    resp1 = await client.create([UserMessage(content=prompt_extract, source="user")])

    # resp1 的返回格式因版本而异，此处使用最保守的文本化方式提取
    extracted = None
    try:
        # 如果是字典或对象，尝试按常见结构提取
        if hasattr(resp1, "choices"):
            # OpenAI-like shape
            extracted = resp1.choices[0].message.content
        elif isinstance(resp1, dict) and "choices" in resp1:
            extracted = resp1["choices"][0]["message"]["content"]
        else:
            extracted = str(resp1)
    except Exception:
        extracted = str(resp1)

    print("\n--- 提取到的规格（原始模型输出）---")
    print(extracted)

    # 第二步：将提取到的规格转换为 JSON
    prompt_transform = (
        "Transform the following specifications into a JSON object with 'cpu', 'memory', and 'storage' as keys:\n\n"
        + extracted
    )
    resp2 = await client.create([UserMessage(content=prompt_transform, source="user")])

    final = None
    try:
        if hasattr(resp2, "choices"):
            final = resp2.choices[0].message.content
        elif isinstance(resp2, dict) and "choices" in resp2:
            final = resp2["choices"][0]["message"]["content"]
        else:
            final = str(resp2)
    except Exception:
        final = str(resp2)

    print("\n--- 最终 JSON 输出（模型原始输出）---")
    print(final)

    await client.close()
    return final


async def main():
    # 待处理的示例文本（与 langchain 示例一致）
    input_text = "The new laptop model features a 3.5 GHz octa-core processor, 16GB of RAM, and a 1TB NVMe SSD."
    model_name = get_model()
    print(f"使用模型: {model_name} (Endpoint: {get_base_url()})")
    await run_chain(input_text, model_name)


if __name__ == "__main__":
    asyncio.run(main())
