"""
Saleha Core: Micro-Kernel Plugin Manifest Engine

Enables dynamic discovery and runtime registration of third-party plugins,
custom agent roles, and external tools via declarative manifest files (saleha.plugin.json / yaml).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class PluginAgentSpec:
    name: str
    role: str
    description: str
    entrypoint: str
    version: str = "1.0.0"


@dataclass
class SalehaPluginManifest:
    plugin_id: str
    name: str
    version: str
    author: str
    description: str = ""
    agents: List[PluginAgentSpec] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    enabled: bool = True


class PluginManifestEngine:
    """Micro-Kernel Dynamic Plugin Discovery & Loader."""

    def __init__(self, plugins_dir: Optional[str] = None):
        self.plugins_dir = plugins_dir or os.path.join(".saleha", "plugins")
        self._plugins: Dict[str, SalehaPluginManifest] = {}
        os.makedirs(self.plugins_dir, exist_ok=True)
        self.discover_plugins()

    def discover_plugins(self) -> List[SalehaPluginManifest]:
        """Scans plugins directory for declarative plugin manifests."""
        self._plugins.clear()
        if not os.path.isdir(self.plugins_dir):
            return []

        for item in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, item)
            manifest_file = os.path.join(plugin_path, "manifest.json")
            if os.path.isfile(manifest_file):
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        agents = [
                            PluginAgentSpec(
                                name=a.get("name", ""),
                                role=a.get("role", ""),
                                description=a.get("description", ""),
                                entrypoint=a.get("entrypoint", ""),
                                version=a.get("version", "1.0.0"),
                            )
                            for a in data.get("agents", [])
                        ]
                        manifest = SalehaPluginManifest(
                            plugin_id=data.get("plugin_id", item),
                            name=data.get("name", item),
                            version=data.get("version", "1.0.0"),
                            author=data.get("author", "Community"),
                            description=data.get("description", ""),
                            agents=agents,
                            tools=data.get("tools", []),
                            enabled=data.get("enabled", True),
                        )
                        self._plugins[manifest.plugin_id] = manifest
                except Exception:
                    pass

        return list(self._plugins.values())

    def register_plugin_manifest(self, manifest: SalehaPluginManifest) -> None:
        """Manually registers an in-memory or dynamically synthesised plugin manifest."""
        self._plugins[manifest.plugin_id] = manifest

    def get_plugin(self, plugin_id: str) -> Optional[SalehaPluginManifest]:
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> List[SalehaPluginManifest]:
        return list(self._plugins.values())


# Global Singleton Instance
plugin_engine = PluginManifestEngine()
