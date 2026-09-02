"""
Unit & Integration Tests for Quad Production Suite:
- DocGeneratorAgent (Codebase Architecture & Mermaid Generator)
- EphemeralContainerRunner (Container Sandbox Isolation)
"""

import unittest
from saleha.agents.doc_generator import DocGeneratorAgent, CodebaseDocSpec, doc_generator
from saleha.core.ephemeral_container_runner import EphemeralContainerRunner, ContainerExecutionResult, container_runner


class DocGeneratorAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = DocGeneratorAgent()

    def test_scan_and_generate_docs(self):
        spec: CodebaseDocSpec = self.agent.scan_and_generate_docs("saleha/core")
        self.assertTrue(len(spec.modules_found) > 0)
        self.assertGreater(spec.total_classes, 0)
        self.assertGreater(spec.total_functions, 0)
        self.assertIn("```mermaid", spec.architecture_diagram_mermaid)
        self.assertIn("## 📊 Repository Metrics", spec.full_doc_markdown)
        self.assertGreater(spec.generation_time_ms, 0.0)

    def test_execute_agent_response(self):
        resp = self.agent.execute("saleha/agents")
        self.assertTrue(resp.success)
        self.assertIn("Generated documentation", resp.content)


class EphemeralContainerRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = EphemeralContainerRunner()

    def test_run_code_successfully(self):
        code = "print('Container Sandbox Execution Success')"
        res: ContainerExecutionResult = self.runner.run_code(code, timeout_sec=5.0)
        self.assertTrue(res.success)
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Container Sandbox Execution Success", res.output)
        self.assertGreater(res.duration_ms, 0.0)
        self.assertTrue(res.isolation_engine)

    def test_run_code_with_syntax_error(self):
        code = "def broken( { return"
        res: ContainerExecutionResult = self.runner.run_code(code, timeout_sec=5.0)
        self.assertFalse(res.success)
        self.assertNotEqual(res.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
