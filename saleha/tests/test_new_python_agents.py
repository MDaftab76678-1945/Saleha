"""
Unit tests for the 6 new first-class Python agents in saleha.agents
"""

import unittest
from saleha.agents import (
    ArchitectAgent,
    SecurityGuardAgent,
    QALeadAgent,
    SREIncidentAgent,
    FinOpsOptimizerAgent,
    RefactorSpecialistAgent,
)


class NewPythonAgentsTests(unittest.TestCase):

    def setUp(self):
        self.architect = ArchitectAgent(model="mock")
        self.security = SecurityGuardAgent(model="mock")
        self.qa = QALeadAgent(model="mock")
        self.sre = SREIncidentAgent(model="mock")
        self.finops = FinOpsOptimizerAgent(model="mock")
        self.refactor = RefactorSpecialistAgent(model="mock")

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


if __name__ == "__main__":
    unittest.main()
