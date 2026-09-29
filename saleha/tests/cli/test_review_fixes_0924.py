"""Regression tests for defects found by the 2026-09-24 code review."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from saleha.cli.commands.quality_security import _split_command


class SplitCommandTests(unittest.TestCase):
    def test_quoted_argument_loses_its_quotes(self) -> None:
        self.assertEqual(_split_command('python -m pytest "tests/a b.py" -q'),
                         ["python", "-m", "pytest", "tests/a b.py", "-q"])

    def test_windows_backslashes_survive(self) -> None:
        self.assertEqual(_split_command(r"C:\venv\python.exe -m pytest")[0], r"C:\venv\python.exe")


class PersonaWithoutModelTests(unittest.TestCase):
    def test_no_model_answer_registers_no_persona(self) -> None:
        from saleha.sandbox.local_llm_driver import LocalLLMDriver
        from saleha.sandbox.v5_production_core import SwarmGenesisRegistry

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            registry = SwarmGenesisRegistry(specs_dir=tmp)
            offline = LocalLLMDriver(ollama_url="http://127.0.0.1:9", vllm_url="http://127.0.0.1:9/v1")
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(registry.generate_agent_persona("packets", "parse", offline))
            self.assertIn("not generated", str(ctx.exception))
            self.assertEqual(os.listdir(tmp), [])


if __name__ == "__main__":
    unittest.main()
