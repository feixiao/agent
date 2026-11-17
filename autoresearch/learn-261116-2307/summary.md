# Autoresearch Summary: AI Agent Harness (and Harmness) Knowledge Base

## Research Overview
- **Goal**: 创建专门研究 Harness 通用组件和作用的目录，对比端侧与云端 Harness 的区别及联系，并提供优质开源项目代码精读指南。
- **Term Clarification**: 标准行业学术及工业界术语为 **Harness**（线束/底座/运行底盘），常见误拼为 `harmness`（混淆 hardness 或 harmlessness）。根目录已建立符号链接 `harmness -> harness` 确保双路径无缝访问。
- **Generated Modules**:
  1. `harness/README.md`: 导读全景、本质公式、知识库架构与学习路线。
  2. `harness/01_core_concepts_and_components.md`: 7 大核心子系统（状态机循环、上下文治理、工具沙箱、动态提示词、模型路由与语法约束、安全护栏、可观测性与评测）。
  3. `harness/02_edge_vs_cloud_harness.md`: 端侧与云端深度对比矩阵，端云协同双环（Dual-Loop）架构设计。
  4. `harness/03_open_source_projects_guide.md`: 8 大顶级开源项目（OpenHands, SWE-agent, LangGraph, PalmClaw, llama.cpp 等）核心源码定位与精读指南。
  5. `harness/examples/minimal_harness.py`: 零重依赖纯 Python 白盒可运行 Harness 原型。
  6. `harness/examples/edge_rule_arbiter.py`: 端侧毫秒级规则短路与本地隐私脱敏原型。
