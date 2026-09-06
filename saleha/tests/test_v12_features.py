"""v1.2: token accounting, stream forwarding, SWE-bench prediction format."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from saleha.core.model_provider import ProviderResponse
from saleha.agents.base_agent import BaseAgent
from saleha.agents.coder import CoderAgent
from saleha.core.swe_bench_runner import (
    build_prompt,
    iter_instances,
    real_diff_from_repo,
    run_benchmark,
    synth_newfile_patch,
    write_predictions,
)


class TokenAccountingTests(unittest.TestCase):
    def test_provider_captures_eval_count(self):
        from saleha.core.model_provider import OllamaProvider
        prov = OllamaProvider()

        class R:
            status = 200
            def raise_for_status(self): pass
            def json(self): return {"response": "ok", "eval_count": 123}

        with patch("requests.post", return_value=R()):
            res = prov.generate("m", "p")
        self.assertEqual(res.tokens_used, 123)

    def test_agent_accumulates_session_tokens(self):
        prov = MagicMock()
        prov.generate.return_value = ProviderResponse(success=True, content="x",
                                                      tokens_used=40)
        agent = BaseAgent(role="T", model="fixed", provider=prov)
        r1 = agent.think("a")
        r2 = agent.think("b")
        self.assertEqual((r1.tokens_used, r2.tokens_used), (40, 40))
        self.assertEqual(agent.total_tokens_used, 80)

    def test_stream_path_counts_tokens(self):
        prov = MagicMock()
        def fake_stream(model, prompt, callback=None, options=None):
            if callback:
                callback("a"); callback("b")
            return ProviderResponse(success=True, content="ab", tokens_used=7)
        prov.stream_generate = fake_stream
        agent = BaseAgent(role="T", model="m", provider=prov)
        resp = agent.think_stream("hi", on_token=lambda t: None)
        self.assertEqual(resp.tokens_used, 7)
        self.assertEqual(agent.total_tokens_used, 7)


class StreamForwardingTests(unittest.TestCase):
    def test_generate_code_forwards_on_token(self):
        coder = CoderAgent(model="fixed-model")
        seen = {}

        def fake_think_stream(prompt, on_token=None, complexity_score=0.0):
            seen["called"] = True
            if on_token:
                on_token("tok")
            return MagicMock(success=True, content="```python\nx=1\n```",
                             error_message="", model_used="m", tokens_used=5)

        with patch.object(coder, "think_stream", side_effect=fake_think_stream):
            res = coder.generate_code("do it", on_token=lambda t: None)
        self.assertTrue(res.success)
        self.assertTrue(seen.get("called"))

    def test_no_callback_uses_plain_think(self):
        coder = CoderAgent(model="fixed-model")
        coder.think = MagicMock(return_value=MagicMock(
            success=True, content="```python\nx=1\n```", error_message="", model_used="m"))
        coder.think_stream = MagicMock(side_effect=AssertionError("stream must not run"))
        res = coder.generate_code("plain")
        self.assertTrue(res.success)


class SWEBenchRunnerTests(unittest.TestCase):
    def test_build_prompt_includes_problem_and_hints(self):
        p = build_prompt("Fix the off-by-one in parser", hints_text="look at line 42")
        self.assertIn("off-by-one", p)
        self.assertIn("line 42", p)

    def test_synth_newfile_patch_is_valid_unified_diff(self):
        patch = synth_newfile_patch("def a():\n    return 1\n")
        self.assertIn("--- /dev/null", patch)
        self.assertIn("+def a():", patch)

    def test_real_diff_from_repo_uses_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "mod.py"), "w") as f:
                f.write("value = 1\n")
            patch = real_diff_from_repo(tmp, {"mod.py": "value = 2\n"})
        self.assertIn("-value = 1", patch)
        self.assertIn("+value = 2", patch)

    def test_iter_instances_skips_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "inst.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"instance_id": "a__1", "problem_statement": "fix"}\n')
                f.write("not-json\n")
                f.write('{"no_id": true}\n')
            ids = [i["instance_id"] for i in iter_instances(path)]
        self.assertEqual(ids, ["a__1"])

    def test_run_benchmark_no_local_repo_is_honest_empty_patch(self):
        """No real repo checkout -> no real fix is possible; must record an
        honest empty patch, not a fabricated new-file diff."""
        with tempfile.TemporaryDirectory() as tmp:
            inst_path = os.path.join(tmp, "inst.jsonl")
            with open(inst_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "instance_id": "repo__issue-1",
                    "problem_statement": "Fix the bug",
                }) + "\n")
            out_path = os.path.join(tmp, "preds.jsonl")
            report = run_benchmark(inst_path, out_path, model="fixed-model")
            self.assertEqual(report["empty_patches"], 1)
            preds = [json.loads(l) for l in open(out_path, encoding="utf-8")]
            self.assertEqual(preds[0]["model_patch"], "")

    def test_run_benchmark_real_repo_produces_real_git_diff(self):
        """Real bug fixed here: run_benchmark() used to hardcode the changed
        filename as 'saleha_solution.py' even with a real repo, so a good
        model response could never produce a patch that actually fixes the
        real buggy file. Now it uses AgentLoop + a real `git diff` of
        whatever the agent actually changed."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = os.path.join(tmp, "repo")
            os.makedirs(repo_dir)
            buggy_path = os.path.join(repo_dir, "buggy.py")
            with open(buggy_path, "w") as f:
                f.write("def add(a, b):\n    return a - b\n")
            subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
            subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)

            inst_path = os.path.join(tmp, "inst.jsonl")
            with open(inst_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "instance_id": "repo__issue-1",
                    "problem_statement": "add() uses - instead of +",
                    "local_repo_dir": repo_dir,
                }) + "\n")
            out_path = os.path.join(tmp, "preds.jsonl")

            fake_agent = MagicMock()
            fake_agent.think.side_effect = [
                MagicMock(success=True, content=(
                    '```tool_call\n{"tool": "patch_file", '
                    '"args": {"path": "buggy.py", "search": "a - b", "replace": "a + b"}}\n```'
                )),
                MagicMock(success=True, content='```json\n{"finish": "fixed"}\n```'),
            ]
            # SALEHA_APPROVAL defaults to "off" (auto-approve) so patch_file
            # works without a human confirmer in this test environment.
            with patch("saleha.agents.base_agent.BaseAgent", return_value=fake_agent):
                report = run_benchmark(inst_path, out_path, model="fixed-model")

            self.assertEqual(report["empty_patches"], 0)
            with open(buggy_path) as f:
                self.assertIn("a + b", f.read())  # the real file was actually changed
            preds = [json.loads(l) for l in open(out_path, encoding="utf-8")]
            patch_text = preds[0]["model_patch"]
            self.assertIn("buggy.py", patch_text)  # real file, not "saleha_solution.py"
            self.assertIn("+    return a + b", patch_text)
            self.assertIn("-    return a - b", patch_text)

    def test_write_predictions_official_format(self):
        from saleha.core.swe_bench_runner import SWEBenchPrediction
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "preds.jsonl")
            n = write_predictions([
                SWEBenchPrediction("repo__issue-1", "saleha-model", "diff --git x"),
                SWEBenchPrediction("repo__issue-2", "saleha-model", ""),
            ], out)
            self.assertEqual(n, 2)
            lines = [json.loads(l) for l in open(out, encoding="utf-8")]
            self.assertEqual(set(lines[0].keys()),
                             {"instance_id", "model_name_or_path", "model_patch"})


if __name__ == "__main__":
    unittest.main()
