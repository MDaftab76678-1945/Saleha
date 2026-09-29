import unittest

from saleha.skills.git_skill import GitSkill


class GitSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = GitSkill()

    def test_handles_gitignore_request(self):
        task = "generate a .gitignore for python"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("__pycache__/", result.output)
        self.assertIn(".venv", result.output)

    def test_handles_conventional_commit_formatting(self):
        task = "create a git commit message for adding ttl cache feature"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("feat:", result.output)

    def test_handles_fix_commit_formatting(self):
        task = "generate a git commit for fixing memory leak in websocket connection"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("fix:", result.output)

    def test_handles_changelog_generation(self):
        task = "generate changelog for release"
        self.assertTrue(self.skill.can_handle(task))
        result = self.skill.execute(task)
        self.assertTrue(result.success)
        self.assertIn("# CHANGELOG", result.output)

    def test_rejects_unrelated_coding_task(self):
        self.assertFalse(self.skill.can_handle("Write a python script to download a webpage"))


if __name__ == "__main__":
    unittest.main()

