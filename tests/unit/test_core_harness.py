import unittest
from core.context import ContextEngine, TokenBudget
from core.loop import CircuitBreaker, LoopConfig, AgentState
from core.memory import WorkingMemory
from core.planning import Plan, PlanStep
from core.sandbox import generate_idempotency_key
from tools import ToolRegistry

class TestCoreHarness(unittest.TestCase):
    def test_context_engine_prefix_cache_preservation(self):
        engine = ContextEngine()
        messages = engine.assemble(
            system_prompt="You are an expert agent.",
            history=[{"role": "user", "content": "Hello"}],
            status_bar="Steps: 1/30 | Retries: 0"
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are an expert agent.")
        self.assertIn("<status_bar>", messages[-1]["content"])

    def test_circuit_breaker_duplicate_calls(self):
        config = LoopConfig(max_steps=10, consecutive_error_limit=3, identical_call_limit=2)
        cb = CircuitBreaker(config=config)

        self.assertTrue(cb.record_action("search(query='python')"))
        self.assertTrue(cb.record_action("search(query='python')"))
        # 第三次相同调用触发熔断
        self.assertFalse(cb.record_action("search(query='python')"))

    def test_circuit_breaker_consecutive_errors(self):
        config = LoopConfig(consecutive_error_limit=3)
        cb = CircuitBreaker(config=config)

        self.assertTrue(cb.record_action("action1", is_error=True))
        self.assertTrue(cb.record_action("action2", is_error=True))
        self.assertFalse(cb.record_action("action3", is_error=True))

    def test_working_memory(self):
        mem = WorkingMemory()
        mem.add("user_goal", "deploy cluster")
        records = mem.retrieve("goal")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["key"], "user_goal")
        self.assertEqual(records[0]["data"]["value"], "deploy cluster")

    def test_plan_dag(self):
        step1 = PlanStep(id="s1", description="fetch data", status="COMPLETED")
        step2 = PlanStep(id="s2", description="process data", dependencies=["s1"])
        step3 = PlanStep(id="s3", description="generate report", dependencies=["s2"])
        plan = Plan(goal="analysis", steps=[step1, step2, step3])

        executable = plan.get_executable_steps()
        self.assertEqual(len(executable), 1)
        self.assertEqual(executable[0].id, "s2")

    def test_idempotency_key_generation(self):
        key1 = generate_idempotency_key("refund_payment", "tx_12345")
        key2 = generate_idempotency_key("refund_payment", "tx_12345")
        self.assertTrue(key1.startswith("refund_payment:tx_12345:"))
        self.assertNotEqual(key1, key2)

    def test_tool_registry(self):
        registry = ToolRegistry()

        @registry.register(name="add_numbers", description="Add two integers")
        def add(a: int, b: int) -> int:
            return a + b

        schemas = registry.list_schemas()
        self.assertIn("add_numbers", schemas)
        self.assertEqual(schemas["add_numbers"]["description"], "Add two integers")
        tool_fn = registry.get_tool("add_numbers")
        self.assertIsNotNone(tool_fn)
        self.assertEqual(tool_fn(2, 3), 5)

if __name__ == "__main__":
    unittest.main()
