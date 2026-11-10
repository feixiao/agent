"""Compare the two sub-agent context-passing strategies (实验 4-5「对比效果」).

Spawns a sub-agent under BOTH `minimal` and `llm_generated` strategies on the
SAME task and prints the difference (context tokens handed off, extra
preparation cost, whether private data leaked, and each sub-agent's result).

Run:
    export OPENAI_API_KEY=your-openai-api-key        # or OPENROUTER_API_KEY (default model: gpt-5.6-luna)
    python subagent_comparison.py

【中文说明】实验 4-5 的"对比效果"最小脚本：对同一子任务分别用 minimal 与
llm_generated 两种上下文传递策略各 spawn 一次子 Agent，打印交接上下文
token 数、额外准备开销、隐私是否泄漏、两者结果差异。需要 LLM（.env 指向
本地 LM Studio 即可；27B 单次调用慢时可设 OPENAI_TIMEOUT=600 防客户端超时）。
"""

import asyncio
import os
import sys

# Make the src/ modules importable (they use bare imports, matching quickstart).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from subagent_tools import run_context_strategy_comparison  # noqa: E402


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        print("No LLM key set. Export OPENAI_API_KEY or OPENROUTER_API_KEY "
              "(universal fallback; default model: gpt-5.6-luna).")
        sys.exit(1)
    asyncio.run(run_context_strategy_comparison())
