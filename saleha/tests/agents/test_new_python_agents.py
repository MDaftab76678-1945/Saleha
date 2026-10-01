"""
Unit tests for the complete suite of first-class Python agents in saleha.agents
"""

import unittest

from saleha.agents import (
    ArchitectAgent,
    DataEngineerAgent,
    DesignerAgent,
    DeveloperAgent,
    DevOpsAgent,
    FinOpsOptimizerAgent,
    NewSkillCreatorAgent,
    QALeadAgent,
    RefactorSpecialistAgent,
    SecurityGuardAgent,
    SREIncidentAgent,
    WebDevAgent,
)


class NewPythonAgentsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.architect = ArchitectAgent(model="mock")
        self.security = SecurityGuardAgent(model="mock")
        self.qa = QALeadAgent(model="mock")
        self.sre = SREIncidentAgent(model="mock")
        self.finops = FinOpsOptimizerAgent(model="mock")
        self.refactor = RefactorSpecialistAgent(model="mock")
        self.designer = DesignerAgent(model="mock")
        self.developer = DeveloperAgent(model="mock")
        self.skill_creator = NewSkillCreatorAgent(model="mock")
        self.web_dev = WebDevAgent(model="mock")
        self.devops = DevOpsAgent(model="mock")
        self.data_engineer = DataEngineerAgent(model="mock")

    def test_architect_agent_design_system(self) -> None:
        design = self.architect.design_system("Real-time distributed chat engine", tech_stack="FastAPI + WebSockets")
        self.assertEqual(design.goal, "Real-time distributed chat engine")
        self.assertIn("ADR:", design.adr_title)
        self.assertGreaterEqual(len(design.components), 2)
        self.assertGreaterEqual(len(design.api_contracts), 1)

    def test_security_guard_agent_clean_code(self) -> None:
        clean_code = "def calculate_sum(a: int, b: int) -> int:\n    return a + b"
        res = self.security.audit_and_harden("sum function", clean_code)
        self.assertTrue(res.is_secure)
        self.assertEqual(len(res.vulnerabilities_found), 0)

    def test_security_guard_agent_detects_sqli_and_fixes(self) -> None:
        insecure_code = 'query = f"SELECT * FROM users WHERE username=\'{user}\'"'
        res = self.security.audit_and_harden("fetch user", insecure_code)
        self.assertFalse(res.is_secure)
        self.assertIn("CWE-89", res.cwe_identifiers)
        self.assertIn(":param", res.hardened_code)

    def test_qa_lead_without_a_model_generates_no_tests(self) -> None:
        # model="mock" reaches no model. This test used to assert the
        # fallback: `def test_...(): assert True` functions and a fixed list
        # of "edge cases covered" that no test contained.
        code = "def multiply(x, y): return x * y"
        suite = self.qa.generate_test_suite("multiply numbers", code, framework="pytest")
        self.assertFalse(suite.generated)
        self.assertEqual(suite.test_code, "")
        self.assertEqual(suite.test_case_count, 0)
        self.assertTrue(suite.error)

    def test_qa_prompt_gets_the_api_not_the_source(self) -> None:
        from saleha.agents.qa_lead import api_summary
        code = (
            "import re\n\n"
            "def is_palindrome(s: str) -> bool:\n"
            "    \"\"\"True if s reads the same both ways.\"\"\"\n"
            "    cleaned = re.sub(r'[^a-z0-9]', '', s.lower())\n"
            "    return cleaned == cleaned[::-1]\n\n"
            "class TestOwn:\n    pass\n"
        )
        summary = api_summary(code)
        self.assertIn("def is_palindrome(s: str) -> bool:", summary)
        self.assertIn("True if s reads the same both ways.", summary)
        self.assertNotIn("cleaned", summary)       # no implementation to copy
        self.assertNotIn("TestOwn", summary)       # the solution's own tests are not API
        self.assertEqual(api_summary("def broken(:"), "def broken(:")

    def test_qa_lead_extracts_fenced_tests_and_counts_them(self) -> None:
        from unittest.mock import patch

        from saleha.agents.base_agent import AgentResponse
        reply = "Here you go:\n```python\ndef test_a():\n    assert multiply(2, 3) == 6\n\ndef test_b():\n    assert multiply(0, 3) == 0\n```\n"
        with patch.object(self.qa, "think", return_value=AgentResponse(success=True, content=reply, model_used="m")):
            suite = self.qa.generate_test_suite("multiply numbers", "def multiply(x, y): return x * y")
        self.assertTrue(suite.generated)
        self.assertNotIn("```", suite.test_code)
        self.assertEqual(suite.test_case_count, 2)

    def test_sre_incident_agent_diagnose_incident(self) -> None:
        logs = "[ERROR] Database connection pool OOM panic: max limit reached"
        rca = self.sre.diagnose_incident(logs)
        self.assertEqual(rca.severity, "SEV-1")
        self.assertIn("oom", rca.severity_reason.lower())
        # No model answered ("mock" is no installed model): no steps are invented.
        self.assertTrue(rca.from_template)
        self.assertEqual(rca.mitigation_steps, [])
        self.assertNotIn("ERROR", rca.affected_components, "a log level is not a component")
        self.assertIn("Runbook", rca.runbook_md)

    def test_finops_optimizer_agent_compress(self) -> None:
        verbose_prompt = """
        # TODO: clean this up
        

        def process_items(items):
            # TODO: optimize
            return [x * 2 for x in items]
        """
        res = self.finops.compress_and_optimize(verbose_prompt)
        self.assertLessEqual(res.optimized_tokens_est, res.original_tokens_est)
        self.assertGreaterEqual(len(res.techniques_applied), 1)

    def test_refactor_specialist_agent(self) -> None:
        legacy_code = "from typing import List, Dict, Union\ndef process(data: List[str], flag: bool) -> Union[int, str]:\n    if flag == True:\n        return len(data)\n    return 'empty'"
        res = self.refactor.refactor_code("modernize types", legacy_code)
        self.assertTrue(res.ast_valid)
        # Measured now: modernising type hints removes no branch.
        self.assertEqual((res.complexity_before, res.complexity_after, res.complexity_reduced), (1, 1, False))
        self.assertIn("if flag == True", res.refactored_code, "the behaviour-changing rewrite is gone")
        self.assertIn("list[str]", res.refactored_code)
        self.assertIn("int | str", res.refactored_code)

    def test_designer_agent_create_design_system(self) -> None:
        spec = self.designer.create_design_system("E-Commerce Storefront", theme_style="glassmorphism")
        # No usable model answer ("mock" is no installed model): the template is returned,
        # labelled, with the reason first, and still checked.
        self.assertTrue(spec.is_template)
        self.assertIn(spec.checks[0]["name"], ("model answered", "model answer used"))
        self.assertIn(spec.checks[0]["status"], ("NOT_RUN", "FAIL"))
        self.assertIn("text", spec.color_palette)
        self.assertGreaterEqual(spec.contrast["text on bg"], 4.5)
        self.assertTrue(spec.verified)

    def test_developer_agent_develop_feature(self) -> None:
        output = self.developer.develop_feature("Create user registration endpoint", language="python")
        self.assertEqual(output.language, "python")
        self.assertTrue(len(output.source_code) > 0)
        # Nothing is written to disk by develop_feature: an entry here
        # previously asserted a filename, reading as "file created".
        self.assertEqual(output.files_created, [])

    def test_skill_creator_agent_create_and_register_skill(self) -> None:
        res = self.skill_creator.create_and_register_skill(
            name="Quantum Key Distribution Simulator",
            domain="quantum_cryptography",
            description="Simulates BB84 protocol photon polarization states"
        )
        # An untested draft must not land in the real catalog: the old
        # assertion (registered True) pinned the pollution in place.
        self.assertFalse(res.registered_in_catalog)
        self.assertEqual(res.domain, "quantum_cryptography")
        self.assertIn("def execute_skill", res.python_handler_snippet)
        self.assertIn("NotImplementedError", res.python_handler_snippet)

    def test_web_dev_agent_build_web_application(self) -> None:
        output = self.web_dev.build_web_application("Real-Time Analytics Dashboard", framework="html5_css3")
        self.assertTrue(output.is_template)
        self.assertIn("<!DOCTYPE html>", output.html_markup)
        self.assertEqual(output.seo_meta_tags["title"], "Real-Time Analytics Dashboard")
        statuses = {c["name"]: c["status"] for c in output.checks}
        self.assertEqual(statuses["HTML well-formed"], "PASS")
        self.assertEqual(statuses["page basics"], "PASS")

    def test_devops_agent_generate_pipeline(self) -> None:
        spec = self.devops.generate_devops_pipeline("saleha-backend", runtime="python:3.12-slim")
        self.assertTrue(spec.is_template)
        self.assertIn("FROM python:3.12-slim", spec.dockerfile)
        self.assertNotIn("saleha.server.web_server", spec.dockerfile, "a project is not started as Saleha")
        self.assertTrue(spec.verified, spec.checks)

    def test_data_engineer_agent_build_data_pipeline(self) -> None:
        spec = self.data_engineer.build_data_pipeline("user_activity_stream", source_format="json",
                                                      sample_records=[{"a": 1}, {}])
        self.assertTrue(spec.is_template)
        self.assertIn("CREATE TABLE IF NOT EXISTS", spec.sql_schema)
        self.assertEqual(spec.target_tables, ["user_activity_stream_records"])
        self.assertEqual(spec.sample_output, '[{"a": 1}]', "the template ETL ran on the sample")


if __name__ == "__main__":
    unittest.main()
