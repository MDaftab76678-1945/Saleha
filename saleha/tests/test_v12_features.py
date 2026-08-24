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
