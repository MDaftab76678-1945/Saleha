"""Importing a module must not touch the user's working directory.

Every module here was built at import time by a module-level singleton whose
__init__ created directories -- or, in plugin_loader's case, executed Python
found in the caller's cwd. A user standing in their own repository and
running any saleha command had `.saleha/` written into it, and any
`.saleha/plugins/*.py` sitting there was executed with no opt-in.

These run each import in a subprocess with a temporary cwd, because the
side effect happens once per process at import time and cannot be observed
from within a session that has already imported the package.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).resolve().parents[2])

# Singletons whose construction used to create directories relative to cwd.
CWD_SENSITIVE_MODULES = [
    "saleha.core.swarm_checkpoint_store",
    "saleha.core.tot_orchestrator",
    "saleha.core.plugin_loader",
    "saleha.core.plugin_manifest",
    "saleha.core.dpo_dataset_engine",
]


def _run_in_clean_cwd(code: str, cwd: str, env_extra: dict | None = None
                      ) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd, capture_output=True, text=True, timeout=180, env=env,
    )


@pytest.mark.parametrize("module", CWD_SENSITIVE_MODULES)
def test_import_creates_nothing_in_cwd(module: str) -> None:
    """Importing must leave the working directory byte-for-byte untouched."""
    with tempfile.TemporaryDirectory() as td:
        code = "import sys; sys.path.insert(0, %r); __import__(%r)" % (REPO_ROOT, module)
        proc = _run_in_clean_cwd(code, td)
        assert proc.returncode == 0, f"import failed: {proc.stderr[-400:]}"
        leftover = sorted(os.listdir(td))
        assert leftover == [], (
            f"importing {module} created {leftover} in the caller's cwd"
        )


def test_import_does_not_execute_plugins_from_cwd() -> None:
    """The severe case: `_load_plugin_file` calls `exec_module`, so treating
    the cwd as a plugin directory meant importing the module ran whatever
    Python was sitting in `.saleha/plugins/` -- no prompt, no opt-in. A
    cloned repository could execute code just by being the current
    directory."""
    with tempfile.TemporaryDirectory() as td:
        pdir = Path(td) / ".saleha" / "plugins"
        pdir.mkdir(parents=True)
        (pdir / "evil.py").write_text(
            "import pathlib\n"
            "pathlib.Path('EXECUTED.txt').write_text('ran', encoding='utf-8')\n",
            encoding="utf-8",
        )

        code = ("import sys; sys.path.insert(0, %r); "
                "import saleha.core.plugin_loader" % REPO_ROOT)
        proc = _run_in_clean_cwd(code, td)

        assert proc.returncode == 0, proc.stderr[-400:]
        assert not (Path(td) / "EXECUTED.txt").exists(), (
            "importing plugin_loader executed a .py file from the cwd"
        )


def test_plugins_still_load_when_explicitly_requested() -> None:
    """The ambient path is gone; the feature is not. An explicitly passed
    directory must still be discovered and its hooks still fire."""
    with tempfile.TemporaryDirectory() as td:
        pdir = Path(td) / "myplugins"
        pdir.mkdir()
        (pdir / "demo.py").write_text(
            "PLUGIN_NAME = 'demo'\n"
            "PLUGIN_VERSION = '2.1.0'\n"
            "def on_task_start(**kw):\n"
            "    return 'hook-ran'\n",
            encoding="utf-8",
        )

        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "from saleha.core.plugin_loader import PluginLoader\n"
            "pl = PluginLoader(plugin_dirs=[%r])\n"
            "print([p.name + '|' + p.version for p in pl.list_plugins()])\n"
            "print(pl.trigger_event('on_task_start'))\n"
        ) % (REPO_ROOT, str(pdir))
        proc = _run_in_clean_cwd(code, td)

        assert proc.returncode == 0, proc.stderr[-400:]
        assert "demo|2.1.0" in proc.stdout, proc.stdout
        assert "hook-ran" in proc.stdout, proc.stdout


def test_plugin_dirs_env_var_opts_a_directory_back_in() -> None:
    """SALEHA_PLUGIN_DIRS is the documented way to opt a project directory
    back in, replacing the implicit cwd behaviour."""
    with tempfile.TemporaryDirectory() as td:
        pdir = Path(td) / "envplugins"
        pdir.mkdir()
        (pdir / "demo.py").write_text(
            "PLUGIN_NAME = 'env_demo'\n"
            "def on_task_start(**kw):\n"
            "    return 'env-hook'\n",
            encoding="utf-8",
        )

        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "from saleha.core.plugin_loader import plugin_loader\n"
            "print([p.name for p in plugin_loader.list_plugins()])\n"
            "print(plugin_loader.trigger_event('on_task_start'))\n"
        ) % REPO_ROOT
        proc = _run_in_clean_cwd(code, td, {"SALEHA_PLUGIN_DIRS": str(pdir)})

        assert proc.returncode == 0, proc.stderr[-400:]
        assert "env_demo" in proc.stdout, proc.stdout
        assert "env-hook" in proc.stdout, proc.stdout


def test_checkpoint_store_still_persists_when_used() -> None:
    """Moving the mkdir out of __init__ must not break real saving."""
    from saleha.core.swarm_checkpoint_store import (
        SwarmCheckpoint, SwarmCheckpointStore,
    )

    with tempfile.TemporaryDirectory() as td:
        store = SwarmCheckpointStore(storage_dir=os.path.join(td, "cp"))
        assert not os.path.exists(os.path.join(td, "cp")), (
            "construction created the directory again"
        )

        store.save_checkpoint(SwarmCheckpoint(
            execution_id="exec-1", goal="demo", role_sequence=["a", "b"],
        ))
        loaded = store.get_checkpoint("exec-1")
        assert loaded is not None
        assert loaded.goal == "demo"
        assert loaded.role_sequence == ["a", "b"]
