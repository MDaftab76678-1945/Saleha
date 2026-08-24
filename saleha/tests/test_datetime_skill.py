import unittest
from saleha.skills.datetime_skill import DateTimeSkill


class DateTimeSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = DateTimeSkill()

    def test_current_date(self):
        self.assertTrue(self.skill.can_handle("What is today's date?"))
        result = self.skill.execute("What is today's date?")
        self.assertTrue(result.success)
        self.assertIn("Today is", result.output)

    def test_days_between_dates(self):
        task = "days between 2026-01-01 and 2026-01-11"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("10 days", result.output)

    def test_day_of_week(self):
        task = "what day is 2026-01-01"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("Thursday", result.output)

    def test_rejects_coding_requests(self):
        self.assertFalse(self.skill.can_handle("Write a script to get current datetime"))


if __name__ == "__main__":
    unittest.main()

