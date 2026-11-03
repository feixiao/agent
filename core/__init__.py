"""
Agent Core Runtime & Harness Framework

Harness 是保障 Agent 商业级可靠性的工程底盘：
- 上下文管理 (context): KV-Cache 前缀字节静止、Token 预算控制、滑动窗口裁剪
- 执行循环 (loop): 显式状态机、死循环检测熔断、状态栏 (status_bar) 反馈
- 记忆管理 (memory): 短期工作区、长期画像、检索增强与治理
- 规划决策 (planning): DAG 任务分解与动态重规划
- 反思评审 (reflection): Self-Correction 与 Critic 双重校验
- 安全沙箱 (sandbox): 工具执行隔离与幂等性保障
"""

__version__ = "0.1.0"
