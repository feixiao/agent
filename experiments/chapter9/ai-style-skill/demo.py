#!/usr/bin/env python3
"""兼容入口：运行真实的开放式提炼与 LLM-as-a-judge 完整流程。

本文件是 ai-style-skill 实验的命令行入口，本身不实现任何逻辑，
只是转发到 run_ai_style_skill.main()：
全量反馈 → LLM 开放式提炼规则 → 独立人工金标校准 LLM judge
→ 生成 Skill → boundary/retention 评估 → 改写演示，
并把证据回执写入 validation/<时间戳>/evidence.json。
"""

from run_ai_style_skill import main


if __name__ == "__main__":
    # 直接调用真实 LLM 的完整管道（需要配置对应 provider 的 API Key）
    raise SystemExit(main())
