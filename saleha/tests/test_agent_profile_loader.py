import unittest
import os
import tempfile
from saleha.core.agent_profile_loader import AgentProfileRegistry, AgentProfile, profile_registry


class AgentProfileLoaderTests(unittest.TestCase):
    def test_registry_loads_default_profiles(self):
        profiles = profile_registry.list_profiles()
        self.assertGreaterEqual(len(profiles), 10)

        sde = profile_registry.get("agent_sde")
        self.assertIsNotNone(sde)
        self.assertEqual(sde.name, "Software Development Engineer (Core Distributed Systems)")
        self.assertTrue(len(sde.goals) > 0)

    def test_get_by_fuzzy_or_short_name(self):
        profile = profile_registry.get("security_engineer")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.id, "agent_security_engineer")

    def test_task_matching(self):
        match = profile_registry.match_profile_for_task("Implement a distributed lock with redis and raft consensus")
        self.assertIsNotNone(match)
        self.assertEqual(match.id, "agent_sde")

        match_sec = profile_registry.match_profile_for_task("Run semgrep to detect hardcoded private key vulnerability")
        self.assertIsNotNone(match_sec)
        self.assertEqual(match_sec.id, "agent_security_engineer")

    def test_persona_formatting(self):
        profile = profile_registry.get("agent_software_engineer")
        self.assertIsNotNone(profile)
        persona = profile.format_persona_prompt()
        self.assertIn("[AGENT ROLE:", persona)
        self.assertIn("[PRIMARY GOALS]:", persona)
        self.assertIn("[CONSTRAINTS & RULES]:", persona)

    def test_custom_profile_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "agent_custom_expert.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("""---
id: "agent_custom_expert"
name: "Custom Domain Expert"
type: "agent_profile"
version: "1.0.0"
goals:
  - Deliver custom domain solutions.
---

# Custom Domain Spec
Details here.
""")
            custom_reg = AgentProfileRegistry(search_dir=tmpdir)
            profile = custom_reg.get("agent_custom_expert")
            self.assertIsNotNone(profile)
            self.assertEqual(profile.name, "Custom Domain Expert")
            self.assertEqual(profile.goals, ["Deliver custom domain solutions."])


if __name__ == "__main__":
    unittest.main()

