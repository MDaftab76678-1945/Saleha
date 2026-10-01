"""The agents that used to return fixed templates now ask the model, check the answer by program, and say how it went."""

from __future__ import annotations

import unittest
from typing import Any, List, Optional

from saleha.agents import artifact_check as ac
from saleha.core.platform.model_provider import ProviderResponse

F = "```"


class Scripted:
    """A model that gives the listed answers in turn; None is a failed call."""

    def __init__(self, answers: List[Optional[str]]) -> None:
        self.answers = list(answers)
        self.prompts: List[str] = []

    def generate(self, model: str, prompt: str, options: Any = None, response_format: Any = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if self.answers else None
        return ProviderResponse(success=answer is not None, content=answer or "",
                                error_message="" if answer is not None else "offline")


def agent(cls: Any, answers: List[Optional[str]]) -> Any:
    a = cls(model="scripted")
    a.provider = Scripted(answers)
    return a


def statuses(checks: List[dict]) -> dict:
    return {c["name"]: c["status"] for c in checks}


GOOD_CODE = (f"{F}python\ndef add(a: int, b: int) -> int:\n    return a + b\n{F}\n"
             f"{F}python\nfrom solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n{F}")


class DeveloperTests(unittest.TestCase):
    def test_code_is_verified_only_by_its_tests_passing(self) -> None:
        from saleha.agents.developer import DeveloperAgent
        out = agent(DeveloperAgent, [GOOD_CODE]).develop_feature("add two ints")
        self.assertTrue(out.verified, out.checks)
        self.assertEqual(statuses(out.checks)["tests pass"], "PASS")
        self.assertIn("1 passed", out.checks[1]["detail"])

    def test_failing_tests_are_shown_to_the_model_and_a_still_wrong_answer_is_not_verified(self) -> None:
        from saleha.agents.developer import DeveloperAgent
        wrong = GOOD_CODE.replace("a + b", "a - b")
        a = agent(DeveloperAgent, [wrong, wrong])
        out = a.develop_feature("add two ints")
        self.assertFalse(out.verified)
        self.assertEqual(len(a.provider.prompts), 2)
        self.assertIn("failed these checks", a.provider.prompts[1])

    def test_dependencies_are_read_from_the_imports(self) -> None:
        from saleha.agents.developer import third_party_imports
        self.assertEqual(third_party_imports("import os\nimport requests\nfrom fastapi import X\n"),
                         ["fastapi", "requests"])


class DevOpsTests(unittest.TestCase):
    def test_a_broken_workflow_fails_its_check(self) -> None:
        from saleha.agents.devops import DevOpsAgent
        ops = (f"{F}dockerfile\nFROM python:3.12\nCMD [\"python\", \"main.py\"]\n{F}\n"
               f"{F}yaml\nservices:\n  app:\n    build: .\n{F}\n{F}yaml\nname: CI\njobs:\n  t:\n    steps: []\n{F}\n"
               f"{F}nginx\nserver {{\n    listen 80;\n}}\n{F}")
        spec = agent(DevOpsAgent, [ops, ops]).generate_devops_pipeline("shop")
        self.assertFalse(spec.is_template)
        self.assertEqual(statuses(spec.checks)["CI workflow"], "FAIL")
        self.assertFalse(spec.verified)

    def test_the_template_starts_the_project_not_saleha(self) -> None:
        import os
        import tempfile

        from saleha.agents.devops import DevOpsAgent
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            open(os.path.join(d, "requirements.txt"), "w").close()
            open(os.path.join(d, "app.py"), "w").close()
            spec = agent(DevOpsAgent, [None]).generate_devops_pipeline("shop", project_dir=d)
        self.assertTrue(spec.is_template)
        self.assertIn('CMD ["python", "app.py"]', spec.dockerfile)
        self.assertEqual(statuses(spec.checks)["model answered"], "NOT_RUN")


class DesignerTests(unittest.TestCase):
    def test_unreadable_text_fails_the_contrast_check(self) -> None:
        from saleha.agents.designer import DesignerAgent
        low = (f'{F}json\n{{"palette": {{"bg": "#ffffff", "text": "#dddddd", "text_muted": "#eeeeee"}}}}\n{F}\n'
               f"{F}css\n:root {{ --bg: #ffffff; }}\nbody {{ background: var(--bg); }}\n{F}")
        spec = agent(DesignerAgent, [low, low]).create_design_system("shop")
        self.assertFalse(spec.verified)
        self.assertEqual(statuses(spec.checks)["text contrast >= 4.5:1"], "FAIL")
        self.assertLess(spec.contrast["text on bg"], 4.5)

    def test_contrast_is_computed(self) -> None:
        self.assertEqual(ac.contrast("#000000", "#ffffff"), 21.0)
        self.assertIsNone(ac.contrast("red", "#ffffff"))


class WebDevTests(unittest.TestCase):
    def test_a_page_missing_its_basics_is_not_verified(self) -> None:
        from saleha.agents.web_dev import WebDevAgent
        page = (f"{F}html\n<html><body><img src='a.png'><div></body></html>\n{F}\n{F}css\nbody {{ margin: 0; }}\n{F}\n"
                f"{F}javascript\nconsole.log(1);\n{F}")
        out = agent(WebDevAgent, [page, page]).build_web_application("shop")
        s = statuses(out.checks)
        self.assertEqual((s["HTML well-formed"], s["page basics"]), ("FAIL", "FAIL"))
        self.assertFalse(out.verified)


class DataEngineerTests(unittest.TestCase):
    def test_the_etl_is_run_on_the_sample_records(self) -> None:
        from saleha.agents.data_engineer import DataEngineerAgent
        answer = (f"{F}sql\nCREATE TABLE orders (id SERIAL PRIMARY KEY, total NUMERIC);\n{F}\n"
                  f"{F}python\ndef transform_batch(raw_data: list) -> list:\n"
                  f"    return [{{'total': float(r['total'])}} for r in raw_data]\n{F}")
        spec = agent(DataEngineerAgent, [answer, answer]).build_data_pipeline("orders", sample_records=[{"x": 1}])
        self.assertEqual(statuses(spec.checks)["ETL runs on the sample"], "FAIL", "KeyError on the sample")
        self.assertFalse(spec.verified)
        good = agent(DataEngineerAgent, [answer]).build_data_pipeline("orders", sample_records=[{"total": "2"}])
        self.assertTrue(good.verified, good.checks)
        self.assertEqual((good.target_tables, good.sample_output), (["orders"], '[{"total": 2.0}]'))


class SkillCreatorTests(unittest.TestCase):
    def test_a_skill_whose_tests_fail_is_never_registered(self) -> None:
        from saleha.agents.skill_creator import NewSkillCreatorAgent
        from saleha.core.skills.skill_catalog import skill_catalog
        before = len(getattr(skill_catalog, "skills", {}) or {})
        bad = (f"{F}python\ndef execute_skill(context: dict) -> dict:\n    return {{'status': 'ok', 'words': 0}}\n{F}\n"
               f"{F}python\nfrom solution import execute_skill\n\ndef test_count():\n"
               f"    assert execute_skill({{'text': 'a b'}})['words'] == 2\n{F}")
        res = agent(NewSkillCreatorAgent, [bad, bad]).create_and_register_skill("wc", "text", "count words",
                                                                                register=True)
        self.assertFalse(res.registered_in_catalog)
        self.assertFalse(res.verified)
        self.assertIn("tests did not pass", res.not_registered_because)
        self.assertEqual(len(getattr(skill_catalog, "skills", {}) or {}), before)


class SlidesAndNotebookTests(unittest.TestCase):
    def test_a_deck_with_a_broken_diagram_is_not_verified(self) -> None:
        from saleha.agents.slides_architect import SlidesArchitectAgent
        deck_json = (f'{F}json\n{{"slides": [{{"title": "A", "bullets": ["x"]}}, {{"title": "B", "bullets": ["y"], '
                     f'"mermaid": "boxes and lines"}}, {{"title": "C", "bullets": ["z"]}}]}}\n{F}')
        deck = agent(SlidesArchitectAgent, [deck_json, deck_json]).synthesize_deck("t")
        self.assertFalse(deck.from_template)
        self.assertFalse(deck.verified)
        self.assertIn("<h2>B</h2>", deck.html5_presentation)

    def test_notebook_cells_run_in_order_and_a_failing_cell_is_marked(self) -> None:
        from saleha.agents.notebook_architect import NotebookArchitectAgent
        nb = f"{F}markdown\n# Sums\n{F}\n{F}python\nxs = [1, 2, 3]\nprint(sum(xs))\n{F}\n{F}python\nprint(xs[10])\n{F}"
        res = agent(NotebookArchitectAgent, [nb, nb]).synthesize_notebook("sums")
        code = [c for c in res.notebook_doc.cells if c.cell_type == "code"]
        self.assertEqual(code[0].output_text.strip(), "6")
        self.assertTrue(code[1].has_error)
        self.assertIn("IndexError", code[1].error_diagnostic)
        self.assertFalse(res.verified)
        self.assertIn('"6\\n"', res.ipynb_json, "the real output is in the exported notebook")


class ChaosAndQATests(unittest.TestCase):
    def test_the_circuit_breaker_template_is_put_through_injected_faults(self) -> None:
        from saleha.agents.chaos_resilience import CIRCUIT_BREAKER_TEMPLATE, verify_breaker
        self.assertTrue(all(c.status == ac.PASS for c in verify_breaker()))
        never_opens = CIRCUIT_BREAKER_TEMPLATE.replace('state = "OPEN"', 'state = "CLOSED"')
        self.assertIn(ac.FAIL, [c.status for c in verify_breaker(never_opens)])

    def test_a_suite_runs_against_the_code_and_a_wrong_function_fails_it(self) -> None:
        from saleha.agents.qa_lead import run_suite
        tests = ("import unittest\nclass T(unittest.TestCase):\n    def test_add(self):\n"
                 "        self.assertEqual(add(1, 2), 3)\n")
        self.assertEqual(run_suite("def add(a, b):\n    return a + b\n", tests).status, ac.PASS)
        self.assertEqual(run_suite("def add(a, b):\n    return a - b\n", tests).status, ac.FAIL)
        self.assertEqual(run_suite("def add(a, b):\n    return a\n", "def test_x():\n    pass\n").status, ac.FAIL)


class ArtifactCheckTests(unittest.TestCase):
    def test_could_not_check_never_reads_as_passed(self) -> None:
        self.assertIsNone(ac.verdict([ac.Check("x", ac.NOT_RUN)]))
        self.assertIsNone(ac.verdict([]))
        self.assertFalse(ac.verdict([ac.Check("x", ac.PASS), ac.Check("y", ac.FAIL)]))
        self.assertTrue(ac.verdict([ac.Check("x", ac.PASS)]))

    def test_sloppy_fences_from_a_small_model_are_still_read(self) -> None:
        # Both shapes measured on qwen2.5-coder:3b answering these agents' prompts.
        unclosed_prose = f"{F}markdown\n# Prices\ntext\n{F}python\nprint(1)\n{F}\n## Results"
        self.assertEqual(ac.fenced_blocks(unclosed_prose), [("markdown", "# Prices\ntext"), ("python", "print(1)")])
        on_the_fence = f'{F}json {{"palette": {{"bg": "#ffffff"}}}}  -- a remark\n{F}css :root {{\n  --bg: #fff;\n}}\n{F}'
        blocks = ac.fenced_blocks(on_the_fence)
        self.assertEqual([info for info, _b in blocks], ["json", "css"])
        check, data = ac.check_json(blocks[0][1])
        self.assertEqual((check.status, data), (ac.PASS, {"palette": {"bg": "#ffffff"}}))
        self.assertTrue(blocks[1][1].startswith(":root {"))

    def test_dangerous_model_code_is_not_run(self) -> None:
        check, _out = ac.run_python("import shutil\nshutil.rmtree('/')\n")
        self.assertEqual(check.status, ac.NOT_RUN)


if __name__ == "__main__":
    unittest.main()
