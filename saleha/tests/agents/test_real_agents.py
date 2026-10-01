"""Ten more agents that returned empty stubs or fixed text now do the work: fetch, compute, run, re-check."""

from __future__ import annotations

import http.server
import importlib
import threading
import unittest
from typing import Any
from unittest.mock import patch

from saleha.tests.agents.test_checked_agents import F, agent, statuses

PAGE = (b"<html lang='en'><head><title>Bakery</title><meta name='description' content='Fresh bread'></head>"
        b"<body><h1>Breads</h1><a href='/rye'>Rye</a><table><tr><th>Item</th><th>Price</th></tr>"
        b"<tr><td>Rye</td><td>4</td></tr></table><script>var x = 'not text';</script></body></html>")


class _Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body, code = (PAGE, 200) if self.path in ("/", "/bakery") else (b"gone", 404)
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- the base class's name
        return


class ClawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Page)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_a_page_is_really_fetched_and_extracted(self) -> None:
        from saleha.agents.browser_claw import SovereignClawAgent
        r = SovereignClawAgent(model="mock").crawl_and_extract(self.base + "/bakery")
        self.assertTrue(r.fetched)
        self.assertEqual((r.http_status, r.page_title), (200, "Bakery"))
        self.assertEqual(r.extracted_data["headings"], [("h1", "Breads")])
        self.assertEqual(r.extracted_data["links"][0]["href"], self.base + "/rye")
        self.assertEqual(r.extracted_data["tables"], [[["Item", "Price"], ["Rye", "4"]]])
        self.assertNotIn("not text", r.extracted_data["text_excerpt"], "script text is not page text")
        self.assertEqual([a.action_type for a in r.action_trace], ["navigate", "extract"])

    def test_a_missing_page_and_a_non_url_are_not_reported_as_fetched(self) -> None:
        from saleha.agents.browser_claw import SovereignClawAgent
        claw = SovereignClawAgent(model="mock")
        missing = claw.crawl_and_extract(self.base + "/nope")
        self.assertEqual((missing.fetched, missing.http_status), (False, 404))
        task = claw.crawl_and_extract("find bakeries in Patna")
        self.assertFalse(task.fetched)
        self.assertIn("no search backend", task.error)


class SheetsTests(unittest.TestCase):
    CSV = "city,sales\nPatna,10\nDelhi,12\nPune,11\nGoa,13\nAgra,9\nLeh,250\n"

    def test_statistics_and_outliers_are_computed_from_the_data(self) -> None:
        from saleha.agents.sheets_analyst import SheetsAnalystAgent
        r = SheetsAnalystAgent(model="mock").analyze_tabular_query(self.CSV)
        sales = next(c for c in r.columns if c.name == "sales")
        self.assertEqual((r.total_rows, r.total_columns, sales.dtype, sales.max_val), (6, 2, "number", "250"))
        self.assertEqual([(a.column, a.value) for a in r.anomalies], [("sales", "250")])

    def test_a_question_is_answered_by_running_the_models_sql(self) -> None:
        from saleha.agents.sheets_analyst import SheetsAnalystAgent
        wrong = f"{F}sql\nSELECT city FROM sales_table\n{F}"
        right = f"{F}sql\nSELECT city FROM data ORDER BY sales DESC LIMIT 1\n{F}"
        a = agent(SheetsAnalystAgent, [wrong, right])
        r = a.analyze_tabular_query(self.CSV, question="which city sold the most?")
        self.assertEqual(r.answer_rows, [{"city": "Leh"}])
        self.assertIn("no such table", a.provider.prompts[1], "the SQL error went back to the model")

    def test_no_table_is_not_an_analysis(self) -> None:
        from saleha.agents.sheets_analyst import SheetsAnalystAgent
        r = SheetsAnalystAgent(model="mock").analyze_tabular_query("Monthly API token usage and cost")
        self.assertFalse(r.loaded)
        self.assertIn("no table given", r.error)


class ResearchTests(unittest.TestCase):
    def test_every_citation_must_point_at_a_fetched_source(self) -> None:
        dr = importlib.import_module("saleha.agents.deep_researcher")   # the package rebinds the name
        sources = [("Bread", "https://en.wikipedia.org/wiki/Bread", "Bread is a staple food."),
                   ("Rye", "https://en.wikipedia.org/wiki/Rye", "Rye is a grass grown as a grain.")]
        ghost = "## Summary\nBread matters [1].\n## Key findings\n- Rye is used in bread [7].\n"
        good = "## Summary\nBread matters [1].\n## Key findings\n- Rye is a grain [2].\n- Bread is staple [1].\n"
        with patch.object(dr, "wikipedia", lambda q, limit=4: sources), \
                patch.object(dr, "arxiv", lambda q, limit=4: []):
            a = agent(dr.DeepResearcherAgent, [ghost, good])
            report = a.conduct_research("bread")
        self.assertTrue(report.synthesized and report.verified, report.checks)
        self.assertIn("[7]", a.provider.prompts[1])
        self.assertEqual([c.url_or_doi for c in report.citations], [s[1] for s in sources])
        self.assertIn("## Sources", report.full_markdown_report)

    def test_no_network_means_no_report_not_an_invented_one(self) -> None:
        dr = importlib.import_module("saleha.agents.deep_researcher")
        report = dr.DeepResearcherAgent(model="mock").conduct_research("anything at all")
        self.assertEqual(report.citations, [])
        self.assertIn("No sources could be fetched", report.full_markdown_report)


class ScreenTests(unittest.TestCase):
    BAD = ("<html><head><style>.hero { color: #777777; background: #888888; width: 900px; }</style></head>"
           "<body><img src='a.png'></body></html>")

    def test_faults_are_measured_and_a_fix_is_re_inspected(self) -> None:
        from saleha.agents.screen_copilot import ScreenCopilotAgent
        good = ("<html lang='en'><head><meta name='viewport' content='width=device-width'><title>T</title>"
                "<meta name='description' content='d'><style>.hero { color: #111111; background: #ffffff; "
                "max-width: 100%; }</style></head><body><img src='a.png' alt='logo'></body></html>")
        r = agent(ScreenCopilotAgent, [f"{F}html\n{good}\n{F}"]).inspect_screen_and_fix(self.BAD)
        self.assertTrue(any(g.startswith("contrast") for g in r.detected_glitches))
        self.assertTrue(any(g.startswith("fixed width") for g in r.detected_glitches))
        self.assertTrue(r.verified, r.remaining_glitches)
        self.assertIn("+", r.remediation_code_diff)

    def test_a_description_without_markup_is_not_inspected(self) -> None:
        from saleha.agents.screen_copilot import ScreenCopilotAgent
        r = ScreenCopilotAgent(model="mock").inspect_screen_and_fix("Navbar mobile breakpoint")
        self.assertFalse(r.inspected)
        self.assertEqual(r.detected_glitches, [])


class VoiceTests(unittest.TestCase):
    def test_a_script_naming_a_function_the_code_lacks_fails(self) -> None:
        from saleha.agents.voice_architect import VoiceArchitectAgent
        code = "def load(path):\n    return open(path).read()\n"
        words = " ".join(["word"] * 200)
        invented = f"We call load() and then parse_all() to finish. {words}\nPOINTS:\n- a\n- b\n- c"
        r = agent(VoiceArchitectAgent, [invented, invented]).synthesize_voice_commentary(code)
        # Not read aloud: the labelled draft comes back, with the reason.
        self.assertTrue(r.from_template)
        self.assertIsNone(r.verified)
        self.assertEqual(r.checks[0]["status"], "FAIL")
        self.assertIn("parse_all", r.checks[0]["detail"])
        self.assertNotIn("parse_all", r.transcript)
        self.assertEqual(r.audio_path, "", "no audio was asked for")

    def test_a_grounded_script_of_the_right_length_is_verified(self) -> None:
        from saleha.agents.voice_architect import VoiceArchitectAgent
        code = "def load(path):\n    return open(path).read()\n"
        script = "We call load() to read a file. " + " ".join(["word"] * 150) + "\nPOINTS:\n- reads\n- returns"
        r = agent(VoiceArchitectAgent, [script]).synthesize_voice_commentary(code)
        self.assertTrue(r.verified, r.checks)
        self.assertEqual(statuses(r.checks)["names only real functions"], "PASS")


class SRETests(unittest.TestCase):
    LOGS = ("2026-10-01 10:00:01 INFO [checkout] start\n"
            "2026-10-01 10:00:02 ERROR [checkout] ConnectionRefusedError: redis:6379\n"
            'Traceback (most recent call last):\n  File "app/cache.py", line 42, in get_cart\n'
            "2026-10-01 10:00:03 ERROR [payments] TimeoutError after 30s\n")

    def test_components_and_severity_come_from_the_logs(self) -> None:
        from saleha.agents.sre_incident import SREIncidentAgent
        rca_text = ("## Root cause\nConnectionRefusedError from redis in cache.py.\n## Mitigation\n"
                    "1. Restart the redis service on port 6379\n2. Add a timeout and retry to get_cart\n")
        r = agent(SREIncidentAgent, [rca_text]).diagnose_incident(self.LOGS)
        self.assertEqual(r.severity, "SEV-2")
        self.assertIn("checkout", r.affected_components)
        self.assertIn("cache.py", r.affected_components)
        self.assertIn("ConnectionRefusedError", r.evidence["exceptions"])
        self.assertTrue(r.verified, r.checks)
        self.assertEqual(len(r.mitigation_steps), 2)

    def test_an_rca_that_names_no_logged_error_fails(self) -> None:
        from saleha.agents.sre_incident import SREIncidentAgent
        vague = "## Root cause\nSomething broke.\n## Mitigation\n1. Restart everything now please\n2. Monitor it closely\n"
        r = agent(SREIncidentAgent, [vague, vague]).diagnose_incident(self.LOGS)
        self.assertEqual(statuses(r.checks)["names an error from the logs"], "FAIL")


class RefactorTests(unittest.TestCase):
    CODE = "def is_on(x):\n    if x == True:\n        return 1\n    else:\n        return 0\n"
    TESTS = "from solution import is_on\n\ndef test_on():\n    assert is_on(True) == 1\n    assert is_on(2) == 0\n"

    def test_a_refactor_that_changes_behaviour_is_rejected(self) -> None:
        from saleha.agents.refactor_specialist import RefactorSpecialistAgent
        breaking = f"{F}python\ndef is_on(x):\n    return 1 if x else 0\n{F}"     # is_on(2) becomes 1
        r = agent(RefactorSpecialistAgent, [breaking, breaking]).refactor_code("simplify", self.CODE, tests=self.TESTS)
        self.assertEqual(r.refactored_code, self.CODE, "the behaviour-changing refactor was not kept")
        self.assertNotEqual(r.checks[0]["status"], "PASS")

    def test_a_behaviour_preserving_refactor_is_verified_and_complexity_measured(self) -> None:
        from saleha.agents.refactor_specialist import RefactorSpecialistAgent
        keeps = f"{F}python\ndef is_on(x):\n    return 1 if x is True else 0\n{F}"
        r = agent(RefactorSpecialistAgent, [keeps]).refactor_code("simplify", self.CODE, tests=self.TESTS)
        self.assertTrue(r.verified, r.checks)
        self.assertEqual((r.complexity_before, r.complexity_after), (1, 1))


class FinOpsAndSecurityTests(unittest.TestCase):
    def test_only_techniques_that_changed_something_are_listed(self) -> None:
        from saleha.agents.finops_optimizer import FinOpsOptimizerAgent
        r = FinOpsOptimizerAgent(model="mock").compress_and_optimize("import os\nimport sys\n\nprint(sys.argv)\n")
        self.assertEqual(r.techniques_applied, ["unused import removal (os)"])
        self.assertNotIn("import os", r.optimized_payload)
        compile(r.optimized_payload, "x", "exec")
        self.assertEqual(FinOpsOptimizerAgent(model="mock").compress_and_optimize("x = 1").techniques_applied, [])

    def test_the_patch_is_scanned_again_and_a_secret_is_left_for_a_person(self) -> None:
        from saleha.agents.security_guard import SecurityGuardAgent
        code = 'import hashlib\nAPI_KEY = "abcdef123456"\ndef h(s):\n    return hashlib.md5(s).hexdigest()\n'
        r = SecurityGuardAgent(model="mock").audit_and_harden("audit", code)
        self.assertFalse(r.is_secure)
        self.assertIn("sha256", r.hardened_code)
        self.assertFalse(r.patch_verified)
        self.assertTrue(any("CWE-798" in x for x in r.remaining_after_patch))
        self.assertFalse(any("CWE-328" in x for x in r.remaining_after_patch), "the weak hash was fixed")


class DebuggerTests(unittest.TestCase):
    def test_a_fix_is_verified_only_when_the_tests_pass_on_it(self) -> None:
        from saleha.agents.debugger import DebuggerAgent
        tests = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        still = f"DIAGNOSIS: sign\nFIXED_CODE:\n{F}python\ndef add(a, b):\n    return a * b\n{F}"
        fixed = f"DIAGNOSIS: wrong operator\nFIXED_CODE:\n{F}python\ndef add(a, b):\n    return a + b\n{F}"
        a = agent(DebuggerAgent, [still, fixed])
        r = a.debug_code("add numbers", "def add(a, b):\n    return a - b\n", "AssertionError: -1 != 5", tests=tests)
        self.assertTrue(r.success and r.verified, r.checks)
        self.assertEqual(r.diagnosis, "wrong operator")
        self.assertEqual(len(a.provider.prompts), 2)


if __name__ == "__main__":
    unittest.main()
