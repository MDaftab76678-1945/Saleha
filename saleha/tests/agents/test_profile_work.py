"""The 37 markdown persona agents: their answers' code and config blocks are checked by program."""

from __future__ import annotations

import unittest

from saleha.agents import artifact_check as ac
from saleha.core.platform.agent_profile_loader import ProfileAgent, profile_registry
from saleha.tests.agents.test_checked_agents import F, Scripted


def persona(answers: list) -> ProfileAgent:
    profile = profile_registry.get("agent_programmer") or profile_registry.list_profiles()[0]
    a = ProfileAgent(profile, model="scripted")
    a.provider = Scripted(answers)
    return a


class CheckAnswerTests(unittest.TestCase):
    def test_each_block_is_checked_by_its_language(self) -> None:
        answer = (f"Here:\n{F}python\ndef f(:\n{F}\n{F}json\n{{\"a\": 1}}\n{F}\n"
                  f"{F}sql\nSELEC * FROM t;\n{F}")
        s = {c.name: c.status for c in ac.check_answer(answer)}
        self.assertEqual(s, {"block 1 (python)": ac.FAIL, "block 2 (json)": ac.PASS, "block 3 (sql)": ac.FAIL})

    def test_a_placeholder_in_code_fails(self) -> None:
        code = f"{F}python\ndef pay(order):\n    raise NotImplementedError\n{F}"
        self.assertIn(ac.FAIL, [c.status for c in ac.check_answer(code)])

    def test_prose_is_left_alone(self) -> None:
        self.assertEqual([c.status for c in ac.check_answer("Use a queue, then retry.")], [ac.PASS])
        self.assertEqual([c.status for c in ac.check_answer("")], [ac.FAIL])


class ProfileWorkTests(unittest.TestCase):
    def test_a_broken_block_goes_back_once_and_a_fixed_answer_is_verified(self) -> None:
        bad = f"{F}python\ndef add(a, b)\n    return a + b\n{F}"
        good = f"{F}python\ndef add(a, b):\n    return a + b\n{F}"
        a = persona([bad, good])
        work = a.work("write add")
        self.assertTrue(work.verified, work.checks)
        self.assertEqual(work.repair_rounds, 1)
        self.assertIn("failed these checks", a.provider.prompts[1])
        self.assertIn("AGENT ROLE", a.provider.prompts[0], "the persona prompt is still used")

    def test_prose_only_is_never_called_verified(self) -> None:
        work = persona(["Split the service in two."]).work("advise")
        self.assertTrue(work.success)
        self.assertIsNone(work.verified)

    def test_no_answer_is_a_failure(self) -> None:
        work = persona([None]).work("advise")
        self.assertFalse(work.success)
        self.assertIsNone(work.verified)

    def test_workflow_nodes_carry_the_checks(self) -> None:
        from saleha.core.workflow.dag_engine import TaskDAG, TaskNode
        good = f"{F}python\ndef add(a, b):\n    return a + b\n{F}"
        dag = TaskDAG("math", model="scripted")
        dag._get_agent_for_node = lambda _pid: persona([good])  # type: ignore[method-assign]
        node = dag._execute_node(TaskNode("n1", "add", "agent_programmer", "write add"), {})
        self.assertEqual((node.status, node.verified), ("COMPLETED", True))
        self.assertTrue(node.checks)


if __name__ == "__main__":
    unittest.main()
