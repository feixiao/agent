# https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/memory.html#


import os
import sys
from pathlib import Path
import asyncio
from dotenv import find_dotenv, load_dotenv

# 确保根目录在 sys.path 中并加载统一环境变量
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
load_dotenv(find_dotenv(usecwd=True))

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from patterns.env import create_autogen_client

def _build_client():
	return create_autogen_client(default="qwen3:8b", temperature=0.2)

# Initialize user memory
async def main():
    user_memory = ListMemory()

    # Add user preferences to memory
    await user_memory.add(MemoryContent(content="The weather should be in metric units", mime_type=MemoryMimeType.TEXT))

    await user_memory.add(MemoryContent(content="Meal recipe must be vegan", mime_type=MemoryMimeType.TEXT))


    async def get_weather(city: str, units: str = "imperial") -> str:
        if units == "imperial":
            return f"The weather in {city} is 73 °F and Sunny."
        elif units == "metric":
            return f"The weather in {city} is 23 °C and Sunny."
        else:
            return f"Sorry, I don't know the weather in {city}."


    assistant_agent = AssistantAgent(
        name="assistant_agent",
        model_client=_build_client(),
        tools=[get_weather],
        memory=[user_memory],
    )


    # Run the agent with a task.
    stream = assistant_agent.run_stream(task="What is the weather in New York?")
    await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())

