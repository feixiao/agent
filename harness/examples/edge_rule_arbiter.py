#!/usr/bin/env python3
"""
edge_rule_arbiter.py - 端侧轻量级意图短路与敏感数据脱敏仲裁器原型

演示端侧 Harness 的两大核心低开销底座能力：
  1. 毫秒级意图短路（Fast Intent Arbiter）：高频指令不走大模型，本地规则 1ms 闭环
  2. 敏感隐私脱敏器（PII Redactor）：向云端发起调用前，在端侧将手机号、身份证、邮箱掩码替换
"""

import re
from typing import Dict, Any, Tuple, Optional


class EdgeRuleArbiter:
    """端侧快速仲裁器：用极小算力对抗云端网络延迟与高昂 Token 成本"""
    def __init__(self):
        # 预编译高频短路规则库
        self.fast_rules = [
            (re.compile(r"^(打开|开启|启动)(手电筒|闪光灯)$"), "turn_on_flashlight"),
            (re.compile(r"^(关闭|灭掉)(手电筒|闪光灯)$"), "turn_off_flashlight"),
            (re.compile(r"^音量(调大|增加|升高|大一点)$"), "volume_up"),
            (re.compile(r"^音量(调小|降低|减小|小一点)$"), "volume_down"),
            (re.compile(r"^静音$"), "mute"),
        ]
        # PII 正则探测器
        self.pii_patterns = [
            (re.compile(r"(1[3-9]\d{9})"), "<PHONE_NUMBER>"),
            (re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"), "<EMAIL_ADDRESS>"),
            (re.compile(r"(\d{17}[\dXx])"), "<ID_CARD>"),
        ]

    def try_short_circuit(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """尝试本地短路执行，命中返回 (动作名, 参数)，未命中返回 None"""
        clean_text = text.strip()
        for pattern, action_name in self.fast_rules:
            if pattern.match(clean_text):
                return action_name, {}
        return None

    def redact_pii_for_cloud(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        在本地内存中对敏感数据进行脱敏：
        返回: (脱敏后文本, 原始数据映射表，保留在端侧私有内存中)
        """
        redacted_text = text
        vault = {}
        counter = 1
        
        for pattern, placeholder in self.pii_patterns:
            matches = pattern.findall(redacted_text)
            for m in matches:
                tag = f"{placeholder[:-1]}_{counter}>"
                vault[tag] = m
                redacted_text = redacted_text.replace(m, tag)
                counter += 1
                
        return redacted_text, vault

    def restore_pii_from_cloud_response(self, cloud_response: str, vault: Dict[str, str]) -> str:
        """云端大模型规划返回后，端侧重新将占位符还原为真实数据"""
        restored = cloud_response
        for tag, original in vault.items():
            restored = restored.replace(tag, original)
        return restored


# ============================================================================
# 测试与演示
# ============================================================================

if __name__ == "__main__":
    arbiter = EdgeRuleArbiter()
    print("📱 === 端侧 Harness 快速仲裁与脱敏测试 ===\n")

    # 测试场景 1: 本地高频意图短路 (零模型调用，零延迟)
    queries = ["打开手电筒", "音量调大", "帮我查一下杭州到北京的高铁票"]
    for q in queries:
        short_circuit = arbiter.try_short_circuit(q)
        if short_circuit:
            action, _ = short_circuit
            print(f"[端侧短路 ⚡] 输入: '{q}' -> 直接本地执行系统原生指令: {action}() (耗时 < 1ms)")
        else:
            print(f"[云端路由 ☁️] 输入: '{q}' -> 未命中端侧规则，准备进入脱敏并派发云端")

    # 测试场景 2: 敏感数据端侧脱敏与安全回传
    print("\n🔒 --- 隐私脱敏测试 ---")
    sensitive_user_input = "请帮我给张三（手机号 13812345678，邮箱 test@company.com）发送一份会议通知"
    print(f"用户原生输入: {sensitive_user_input}")

    redacted_input, private_vault = arbiter.redact_pii_for_cloud(sensitive_user_input)
    print(f"发往云端的脱敏 Payload: {redacted_input}")
    print(f"端侧私有内存保险库 (Vault, 不出设备): {private_vault}")

    # 模拟云端推理给出的规划
    mock_cloud_plan = "已生成邮件草稿，收件人设为 <EMAIL_ADDRESS_2>，短信抄送 <PHONE_NUMBER_1>。"
    print(f"\n云端大模型返回规划: {mock_cloud_plan}")

    restored_local_plan = arbiter.restore_pii_from_cloud_response(mock_cloud_plan, private_vault)
    print(f"端侧还原后最终在手机上执行的真实操作: {restored_local_plan}")
