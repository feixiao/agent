

# Models:
# https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tutorial/models.html
# 抽象接口访问各种服务提供的模型


import os
import sys
from pathlib import Path
import asyncio
import logging
from dotenv import find_dotenv, load_dotenv

# 确保根目录在 sys.path 中并加载统一环境变量
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
load_dotenv(find_dotenv(usecwd=True))

from autogen_core.models import UserMessage
from patterns.env import create_autogen_client, get_base_url, get_model
import logging

# AutoGen uses standard Python logging module to log events like model calls and responses
from autogen_core import EVENT_LOGGER_NAME

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(EVENT_LOGGER_NAME)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

async def main():
	model_name = get_model()
	logging.info(f"Using model: {model_name} (Endpoint: {get_base_url()})")
	ollama_model_client = create_autogen_client(model_name=model_name)

	response = await ollama_model_client.create([UserMessage(content="What is the capital of France?", source="user")])
	logging.info(response)
	await ollama_model_client.close()

if __name__ == "__main__":
	asyncio.run(main())
