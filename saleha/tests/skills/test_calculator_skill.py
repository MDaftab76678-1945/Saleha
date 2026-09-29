import unittest

from saleha.skills.calculator_skill import CalculatorSkill


class CalculatorSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = CalculatorSkill()

    def test_handles_arithmetic_without_llm(self):
        result = self.skill.execute("What is 12 * 8?")

        self.assertTrue(self.skill.can_handle("What is 12 * 8?"))
        self.assertTrue(result.success)
        self.assertEqual(result.output, "12 * 8 = 96")

    def test_supports_power_operator(self):
        result = self.skill.execute("Calculate 2 ^ 3")

        self.assertTrue(result.success)
        self.assertEqual(result.output, "2 ** 3 = 8")

    def test_does_not_claim_coding_requests(self):
        self.assertFalse(self.skill.can_handle("Write a function that returns 2 + 2"))

    def test_rejects_expression_without_operator(self):
        self.assertFalse(self.skill.can_handle("What is 42?"))
        result = self.skill.execute("What is 42?")

        self.assertFalse(result.success)
        self.assertIn("No arithmetic expression", result.error)


if __name__ == "__main__":
    unittest.main()
