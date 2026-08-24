import unittest

from saleha.agents.debugger import DebuggerAgent
from saleha.core.model_provider import ProviderResponse


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, model, prompt, options=None):
        self.prompts.append(prompt)
        return self.response

    def is_available(self):
        return True


class DebuggerAgentTests(unittest.TestCase):
    def test_debug_code_returns_diagnosis_and_fixed_code(self):
        provider = FakeProvider(ProviderResponse(
            success=True,
            content=(
                "DIAGNOSIS: The variable is used before it is defined.\n"
                "FIXED_CODE:\n```python\n"
                "def greet(name):\n    return f'Hello {name}'\n```"
            ),
            response_time=0.01,
        ))

        result = DebuggerAgent(model="test-model", provider=provider).debug_code(
            "Create a greeting function",
            "def greet(name):\n    return f'Hello {username}'",
            "NameError: name 'username' is not defined",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.diagnosis, "The variable is used before it is defined.")
        self.assertEqual(result.fixed_code, "def greet(name):\n    return f'Hello {name}'")
        self.assertEqual(result.model_used, "test-model")
        self.assertIn("NameError", provider.prompts[0])

    def test_debug_code_rejects_missing_inputs(self):
        agent = DebuggerAgent(model="test-model", provider=FakeProvider(ProviderResponse(True, "")))

        empty_code = agent.debug_code("task", "", "NameError: missing")
        empty_error = agent.debug_code("task", "print('ok')", "")

        self.assertFalse(empty_code.success)
        self.assertEqual(empty_code.error, "Code is empty.")
        self.assertFalse(empty_error.success)
        self.assertEqual(empty_error.error, "Error log is empty.")

    def test_debug_code_propagates_provider_failure(self):
        provider = FakeProvider(ProviderResponse(
            success=False,
            content="",
            error_message="provider unavailable",
        ))

        result = DebuggerAgent(model="test-model", provider=provider).debug_code(
            "task", "print('ok')", "SyntaxError: invalid syntax"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "provider unavailable")


if __name__ == "__main__":
    unittest.main()
