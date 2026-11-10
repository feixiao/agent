"""
事件驱动 Agent 快速启动脚本（Quick Start）
=========================================

用最简单的方式演示本实验的基本功能：
  1. 检查 LLM 提供商的 API Key 是否可用（server 侧有 OpenRouter 兜底逻辑）；
  2. 若 8000 端口的服务器已在运行则直接提示可用；
  3. 否则以子进程方式启动 server.py，轮询 /health 直到就绪；
  4. 把服务器输出转发到当前终端，并提示后续如何用 client.py / curl 发事件。

用法：python quickstart.py   （在 agent-with-event-trigger 目录下）
"""

import os
import sys
import time
import subprocess
import signal
from event_types import EventType

# 检查是否配置了 API Key（server 端还有通用的 OpenRouter 兜底）。
from agent import resolve_provider_and_key

provider = os.getenv("LLM_PROVIDER", "kimi").lower()
resolved_provider, api_key = resolve_provider_and_key(provider)

if not api_key:
    print(f"❌ Error: no API key for provider '{provider}', and no OPENROUTER_API_KEY fallback")
    print(f"\nPlease set one of:")
    print(f"  export DASHSCOPE_API_KEY='...'    # for dashscope/qwen/bailian")
    print(f"  export KIMI_API_KEY='...'         # or SILICONFLOW/DOUBAO/OPENROUTER per provider")
    print(f"  export OPENROUTER_API_KEY='...'   # universal fallback")
    print(f"\nOr change provider:")
    print(f"  export LLM_PROVIDER=dashscope  # or qwen, bailian, siliconflow, doubao, kimi, openrouter")
    sys.exit(1)

if resolved_provider != provider:
    print(f"ℹ️  provider '{provider}' has no key; the server will fall back to OpenRouter.")

print("\n" + "="*80)
print("🚀 EVENT-TRIGGERED AGENT QUICK START")
print("="*80)
print()

# 检查服务器是否已经在运行
import requests
try:
    response = requests.get("http://localhost:8000/health", timeout=2)
    print("✅ Server is already running!")
    print("\n💡 You can now use the client to send events:")
    print("   python client.py --mode test")
    print("   python client.py --mode interactive")
    sys.exit(0)
except Exception:
    pass

print("📦 Starting the event-triggered agent server...")
print("\n⏳ This may take a moment to initialize...\n")

# 以子进程方式启动服务器
try:
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Wait for server to start
    print("⏰ Waiting for server to start...")
    max_wait = 30
    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8000/health", timeout=1)
            if response.status_code == 200:
                print("✅ Server is running!\n")
                break
        except Exception:
            pass
        time.sleep(1)
        if i % 5 == 0:
            print(f"   Still waiting... ({i}/{max_wait}s)")
    else:
        print("❌ Server failed to start in time")
        server_process.terminate()
        sys.exit(1)
    
    print("="*80)
    print("🎉 QUICK START READY!")
    print("="*80)
    print()
    print("The event-triggered agent server is now running on port 8000.")
    print()
    print("📋 What you can do now:")
    print()
    print("1. Send test events (in another terminal):")
    print("   python client.py --mode test")
    print()
    print("2. Use interactive mode:")
    print("   python client.py --mode interactive")
    print()
    print("3. Send individual events via API:")
    print("   curl -X POST http://localhost:8000/event \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"event_type\": \"web_message\", \"content\": \"Hello!\"}'")
    print()
    print("4. Check agent status:")
    print("   curl http://localhost:8000/agent/status")
    print()
    print("="*80)
    print("📺 Server output will appear below:")
    print("="*80)
    print()
    
    # Stream server output
    try:
        while True:
            line = server_process.stdout.readline()
            if not line:
                break
            print(line, end='')
    except KeyboardInterrupt:
        print("\n\n⚠️ Shutting down server...")
        server_process.send_signal(signal.SIGINT)
        server_process.wait(timeout=5)
        print("✅ Server stopped")
        
except FileNotFoundError:
    print("❌ Error: Could not find server.py")
    print("Make sure you're in the agent-with-event-trigger directory")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
