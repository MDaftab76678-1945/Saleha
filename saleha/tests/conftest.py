"""
Pytest session-wide configuration.

Sets SALEHA_TEST_MODE=1 for the entire test run. Several modules
(swarm_pipeline_engine.py, swebench_runner.py, persona_debate.py, and now
ttc_solver.py) check this variable to route model calls through a fast,
deterministic mock instead of a real Ollama request -- but nothing set it
automatically before this file existed. A test that imports one of those
modules and does not itself export the variable would silently make a real
network call to a local LLM.

This was not a hypothetical: `test_repl_slash_ttc`
(test_cli_quality_ttc_trace.py) hung the full suite for 15+ minutes because
`saleha.core.ttc_solver`'s module-level singleton called the real
qwen2.5-coder:3b model -- the test's `SalehaREPL(model="mock")` fixture never
reached it, since the REPL imports the global `ttc_solver` instance rather
than constructing its own. Found and fixed in pass 30
(NOTEBOOK_IMPORT.md, "Thirtieth pass").

Setting this here does not silence a bug the way a blanket mock would --
each module's own SALEHA_TEST_MODE branch is real code, exercised by tests
that assert on its (deterministic, inspectable) output, same as before this
file existed for the three modules that already checked it. This just makes
that branch reliably reached instead of reachable only by accident.
"""

import os

os.environ.setdefault("SALEHA_TEST_MODE", "1")
