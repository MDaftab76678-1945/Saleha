"""
Saleha Core: Dynamic Plugin & Sidecar Hook System

Discovers, loads, and executes custom user plugins, event hooks, and dynamic agent profiles
from ~/.saleha/plugins/ and .saleha/plugins/ without modifying core source code.
"""

import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    file_path: str
    hooks_registered: List[str]


class PluginLoader:
    """Discovers and orchestrates lifecycle hooks and custom third-party plugins."""

    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        # The working directory is deliberately NOT a default plugin source.
        # `_load_plugin_file` calls `exec_module`, so including it meant that
        # standing in any directory containing `.saleha/plugins/*.py` and
        # importing this module executed that code -- no prompt, no opt-in.
        # A cloned repository could therefore run code merely by being the
        # cwd. The user's own home directory stays, since it is theirs.
        # Set SALEHA_PLUGIN_DIRS (os.pathsep-separated) to opt a project
        # directory back in explicitly.
        if plugin_dirs is None:
            plugin_dirs = [os.path.join(os.path.expanduser("~"), ".saleha", "plugins")]
            env_dirs = os.environ.get("SALEHA_PLUGIN_DIRS", "").strip()
            if env_dirs:
                plugin_dirs.extend(
                    d for d in (p.strip() for p in env_dirs.split(os.pathsep)) if d
                )
        self.plugin_dirs = plugin_dirs
        self.plugins: Dict[str, PluginInfo] = {}
        self.hooks: Dict[str, List[Callable]] = {
            "on_task_start": [],
            "on_code_generated": [],
            "on_test_complete": [],
            "on_commit": []
        }
        self.load_all_plugins()

    def load_all_plugins(self):
        """Scans plugin directories and loads Python modules dynamically."""
        for pdir in self.plugin_dirs:
            if not os.path.isdir(pdir):
                continue
            for f in os.listdir(pdir):
                if f.endswith(".py") and not f.startswith("__"):
                    full_path = os.path.join(pdir, f)
                    self._load_plugin_file(full_path, f[:-3])

    def _load_plugin_file(self, file_path: str, module_name: str):
        try:
            spec = importlib.util.spec_from_file_location(f"saleha_plugin_{module_name}", file_path)
            if not spec or not spec.loader:
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            registered = []
            for event_name in self.hooks:
                hook_fn = getattr(mod, event_name, None)
                if callable(hook_fn):
                    self.hooks[event_name].append(hook_fn)
                    registered.append(event_name)

            self.plugins[module_name] = PluginInfo(
                name=getattr(mod, "PLUGIN_NAME", module_name),
                version=getattr(mod, "PLUGIN_VERSION", "1.0.0"),
                description=getattr(mod, "PLUGIN_DESCRIPTION", "Custom Saleha Plugin"),
                file_path=file_path,
                hooks_registered=registered
            )
        except Exception:
            pass

    def trigger_event(self, event_name: str, **kwargs) -> List[Any]:
        """Dispatches an event to all registered plugin hook functions."""
        results = []
        for hook_fn in self.hooks.get(event_name, []):
            try:
                res = hook_fn(**kwargs)
                results.append(res)
            except Exception:
                pass
        return results

    def list_plugins(self) -> List[PluginInfo]:
        """Returns all currently loaded plugins."""
        return list(self.plugins.values())


class _LazyPluginLoader:
    """Defers plugin discovery until the loader is actually used.

    Constructing it at import time ran `load_all_plugins()` -- and therefore
    `exec_module` on every discovered file -- as a side effect of importing
    this module.
    """

    __slots__ = ("_impl",)

    def __init__(self) -> None:
        self._impl: Optional[PluginLoader] = None

    def _get(self) -> PluginLoader:
        if self._impl is None:
            self._impl = PluginLoader()
        return self._impl

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


# Global instance
plugin_loader = _LazyPluginLoader()

