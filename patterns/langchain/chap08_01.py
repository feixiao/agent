import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import find_dotenv, load_dotenv

from langchain_core.tools import tool  # 定义/注册可被 LC 使用的 Python 工具
from langchain_core.prompts import PromptTemplate
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables import RunnableSequence
from langchain_core.runnables.history import RunnableWithMessageHistory

# 确保根目录在 sys.path 中并加载统一环境变量
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
load_dotenv(find_dotenv(usecwd=True))

from patterns.env import create_langchain_model

def build_model(provider: Optional[str] = None, model_name: Optional[str] = None):
	return create_langchain_model(provider=provider, model_name=model_name)

try:
    # 需要一个具有函数/工具调用功能的模型。
    llm = build_model()
    print(f"✅ 语言模型已初始化: {getattr(llm, 'model', 'unknown')}")
except Exception as e:
    print(f"初始化语言模型时出错: {e}")
    llm = None


template = """You are a helpful travel agent.

Previous conversation:
{history}

New question: {question}
Response:"""

prompt = PromptTemplate.from_template(template)

# 2. 配置消息历史存储（按 session_id 隔离，方便并发对话）
store = {}

def get_history(session_id: str):
  return store.setdefault(session_id, InMemoryChatMessageHistory())


# 3. 构建链：格式化历史 -> 提示 -> LLM，由 RunnableWithMessageHistory 自动追加消息历史
def _format_history(inputs: dict):
  msgs = inputs.get("history", []) or []
  # 将 Message 对象列表压平成字符串，供 PromptTemplate 渲染
  history_text = "\n".join(f"{m.type}: {m.content}" for m in msgs)
  return {"question": inputs["question"], "history": history_text}

base_chain = RunnableSequence(_format_history, prompt, llm)

# RunnableWithMessageHistory 会在调用前后自动读写消息历史
conversation = RunnableWithMessageHistory(
  base_chain,
  get_history,
  input_messages_key="question",
  history_messages_key="history",
)


# 4. 运行对话
def ask(question: str, session_id: str = "demo-session"):
  result = conversation.invoke(
    {"question": question},
    config={"configurable": {"session_id": session_id}},
  )
  print(result)
  return result


if __name__ == "__main__":
    ask("I want to book a flight.")
    ask("My name is Sam, by theway.")
    ask("What was my name again?")