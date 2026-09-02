"""
Unit tests for the complete suite of first-class Python agents in saleha.agents
"""

import unittest
from saleha.agents import (
    ArchitectAgent,
    SecurityGuardAgent,
    QALeadAgent,
    SREIncidentAgent,
    FinOpsOptimizerAgent,
    RefactorSpecialistAgent,
    DesignerAgent,
    DeveloperAgent,
    NewSkillCreatorAgent,
    WebDevAgent,
    DevOpsAgent,
    DataEngineerAgent,
)


class NewPythonAgentsTests(unittest.TestCase):

    def setUp(self):
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

    def test_architect_agent_design_system(self):
        design = self.architect.design_system("Real-time distributed chat engine", tech_stack="FastAPI + WebSockets")
        self.assertEqual(design.goal, "Real-time distributed chat engine")
        self.assertIn("ADR:", design.adr_title)
        self.assertGreaterEqual(len(design.components), 2)
        self.assertGreaterEqual(len(design.api_contracts), 1)

    def test_security_guard_agent_clean_code(self):
        clean_code = "def calculate_sum(a: int, b: int) -> int:\n    return a + b"
        res = self.security.audit_and_harden("sum function", clean_code)
        self.assertTrue(res.is_secure)
        self.assertEqual(len(res.vulnerabilities_found), 0)

    def test_security_guard_agent_detects_sqli_and_fixes(self):
        insecure_code = 'query = f"SELECT * FROM users WHERE username=\'{user}\'"'
        res = self.security.audit_and_harden("fetch user", insecure_code)
        self.assertFalse(res.is_secure)
        self.assertIn("CWE-89", res.cwe_identifiers)
        self.assertIn(":param", res.hardened_code)

    def test_qa_lead_agent_generate_test_suite(self):
        code = "def multiply(x, y): return x * y"
        suite = self.qa.generate_test_suite("multiply numbers", code, framework="pytest")
        self.assertEqual(suite.framework, "pytest")
        self.assertIn("def test_", suite.test_code)
        self.assertGreaterEqual(len(suite.edge_cases_covered), 2)

    def test_sre_incident_agent_diagnose_incident(self):
        logs = "[ERROR] Database connection pool OOM panic: max limit reached"
        rca = self.sre.diagnose_incident(logs)
        self.assertEqual(rca.severity, "SEV-1")
        self.assertGreaterEqual(len(rca.mitigation_steps), 1)
        self.assertIn("Runbook", rca.runbook_md)

    def test_finops_optimizer_agent_compress(self):
        verbose_prompt = """
        # TODO: clean this up
        

        def process_items(items):
            # TODO: optimize
            return [x * 2 for x in items]
        """
        res = self.finops.compress_and_optimize(verbose_prompt)
        self.assertLessEqual(res.optimized_tokens_est, res.original_tokens_est)
        self.assertGreaterEqual(len(res.techniques_applied), 1)

    def test_refactor_specialist_agent(self):
        legacy_code = "from typing import List, Dict, Union\ndef process(data: List[str], flag: bool) -> Union[int, str]:\n    if flag == True:\n        return len(data)\n    return 'empty'"
        res = self.refactor.refactor_code("modernize types", legacy_code)
        self.assertTrue(res.ast_valid)
        self.assertTrue(res.complexity_reduced)
        self.assertIn("list[str]", res.refactored_code)
        self.assertIn("int | str", res.refactored_code)

    def test_designer_agent_create_design_system(self):
        spec = self.designer.create_design_system("E-Commerce Storefront", theme_style="glassmorphism")
        self.assertIn("accent_primary", spec.color_palette)
        self.assertIn(".glass-card", spec.components_css)
        self.assertIn("theme", spec.design_tokens_json)

    def test_developer_agent_develop_feature(self):
        output = self.developer.develop_feature("Create user registration endpoint", language="python")
        self.assertEqual(output.language, "python")
        self.assertTrue(len(output.source_code) > 0)
        self.assertIn(".py", output.files_created[0])

    def test_skill_creator_agent_create_and_register_skill(self):
        res = self.skill_creator.create_and_register_skill(
            name="Quantum Key Distribution Simulator",
            domain="quantum_cryptography",
            description="Simulates BB84 protocol photon polarization states"
        )
        self.assertTrue(res.registered_in_catalog)
        self.assertEqual(res.domain, "quantum_cryptography")
        self.assertIn("def execute_skill", res.python_handler_snippet)

    def test_web_dev_agent_build_web_application(self):
        output = self.web_dev.build_web_application("Real-Time Analytics Dashboard", framework="html5_css3")
        self.assertIn("<!DOCTYPE html>", output.html_markup)
        self.assertIn(".glass-card", output.css_styles)
        self.assertIn("document.addEventListener", output.js_logic)

    def test_devops_agent_generate_pipeline(self):
        spec = self.devops.generate_devops_pipeline("saleha-backend", runtime="python:3.12-slim")
        self.assertIn("FROM python:3.12-slim", spec.dockerfile)
        self.assertIn("version: '3.8'", spec.docker_compose)
        self.assertIn("name: CI/CD Pipeline", spec.github_actions_workflow)

    def test_data_engineer_agent_build_data_pipeline(self):
        spec = self.data_engineer.build_data_pipeline("user_activity_stream", source_format="json")
        self.assertIn("CREATE TABLE IF NOT EXISTS", spec.sql_schema)
        self.assertIn("import polars as pl", spec.etl_script_py)
        self.assertEqual(len(spec.target_tables), 1)


if __name__ == "__main__":
    unittest.main()
