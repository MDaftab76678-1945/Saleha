"""`saleha doctor` must report the number of models Ollama actually has.

`get_installed_ollama_models()` deliberately returns a bare base name beside
every tagged one ("qwen3.5" as well as "qwen3.5:9b") so the router can match
an untagged request. That set is a matching index, not an inventory --
counting it reported **15 models on a box with 8**, and `doctor` is the first
command a new user runs, so its numbers are the project's first impression.

There was no test for `doctor` at all, which is why this went unnoticed.
"""

import unittest
from unittest import mock

from saleha.cli.commands import cli
from click.testing import CliRunner


# What Ollama's /api/tags actually lists, and what the router's alias
# expansion turns it into.
_REAL_TAGS = [
    "qwen2.5-coder:3b",
    "qwen3:8b",
    "qwen3.5:4b",
    "nomic-embed-text:latest",
]
_WITH_ALIASES = set(_REAL_TAGS) | {
    "qwen2.5-coder", "qwen3", "qwen3.5", "nomic-embed-text",
}


class DoctorModelCountTests(unittest.TestCase):

    def _run_doctor(self) -> str:
        with mock.patch(
            "saleha.core.platform.smart_router.get_installed_ollama_models",
            return_value=set(_WITH_ALIASES),
        ):
            result = CliRunner().invoke(cli, ["doctor"])
        return result.output

    def test_reports_the_tagged_model_count_not_the_alias_expanded_one(self) -> None:
        """8 real models were reported as 15 because each base-name alias was
        counted as a separate model."""
        output = self._run_doctor()
        self.assertIn(f"{len(_REAL_TAGS)} models", output)
        self.assertNotIn(f"{len(_WITH_ALIASES)} models", output)

    def test_the_sample_names_it_prints_are_real_tagged_models(self) -> None:
        """A bare "qwen3.5" is not something the user can run; every name
        shown should be one they could pass to `ollama run`."""
        output = self._run_doctor()
        # The table wraps, so strip whitespace/newlines before matching.
        flat = "".join(output.split())
        shown = [m for m in _REAL_TAGS if m.replace(" ", "") in flat]
        self.assertTrue(shown, f"no tagged model name appeared in:\n{output}")
        for bare in ("qwen3.5,", "qwen3,"):
            self.assertNotIn(bare, flat)


if __name__ == "__main__":
    unittest.main()
