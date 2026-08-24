"""Profile quality gate: ye tests kabhi fail hone chahiye agar koi profile
wapas 'thin' ho gayi (goals/constraints/tools/routing missing)."""
import unittest

from saleha.core.agent_profile_loader import profile_registry


class ProfileQualityGateTests(unittest.TestCase):
    def test_all_20_profiles_load(self):
        profiles = profile_registry.list_profiles()
        self.assertEqual(len(profiles), 20)

    def test_every_profile_meets_richness_bar(self):
        failures = []
        for p in profile_registry.list_profiles():
            problems = []
            if len(p.goals) < 3:
                problems.append(f"goals={len(p.goals)} (<3)")
            if len(p.constraints) < 2:
                problems.append(f"constraints={len(p.constraints)} (<2)")
            if not p.allowed_tools:
                problems.append("allowed_tools empty")
            temp = p.llm_routing.get("temperature")
            if temp is None:
                problems.append("llm_routing.temperature missing")
            elif not (0 < float(temp) <= 1):
                problems.append(f"temperature out of range: {temp}")
            if problems:
                failures.append(f"{p.id}: {'; '.join(problems)}")
        self.assertEqual(failures, [], "Thin profiles detected:\n" + "\n".join(failures))

    def test_temperature_values_clamped_range(self):
        for p in profile_registry.list_profiles():
            t = p.llm_routing.get("temperature")
            if t is not None:
                self.assertLessEqual(float(t), 1.0, p.id)
                self.assertGreater(float(t), 0.0, p.id)

    def test_allowed_tools_are_known_names(self):
        known = {"list_dir", "read_file", "search_repo", "run_code", "write_file",
                 "web_fetch", "file_search", "sqlite_inspect", "shell_exec"}
        bad = []
        for p in profile_registry.list_profiles():
            for t in p.allowed_tools:
                if t not in known:
                    bad.append(f"{p.id}:{t}")
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
