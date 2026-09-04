"""
Saleha Soul Engine - SoulSpec v1.0 Persona & Cognitive Archetype Manager
Compliant with https://soulspec.org standard.

Provides dynamic discovery, loading, activation, and prompt injection for
agent souls defined in the souls/ directory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class SoulPackage:
    """SoulSpec v1.0 Compliant Persona Package."""
    name: str
    display_name: str
    version: str
    archetype: str
    description: str
    tags: List[str] = field(default_factory=list)
    cognitive_params: Dict[str, Any] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    soul_md: str = ""
    identity_md: str = ""
    style_md: str = ""
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "archetype": self.archetype,
            "description": self.description,
            "tags": self.tags,
            "cognitive_params": self.cognitive_params,
            "allowed_tools": self.allowed_tools,
            "path": self.path,
        }

    def render_system_prompt(self) -> str:
        """Render the complete cognitive identity prompt for LLM system context."""
        parts = [
            f"# Active Persona: {self.display_name} ({self.archetype})",
            f"Version: {self.version}",
            f"Description: {self.description}",
            "",
            "## Core Invariants & Boundaries",
            self.soul_md.strip(),
        ]
        if self.style_md.strip():
            parts.extend([
                "",
                "## Communication Style",
                self.style_md.strip(),
            ])
        if self.identity_md.strip():
            parts.extend([
                "",
                "## Persona Identity",
                self.identity_md.strip(),
            ])
        return "\n".join(parts)


class SoulEngine:
    """Central engine managing discovering, switching, and validating agent souls."""

    DEFAULT_SOUL = "sovereign"

    def __init__(self, souls_dir: Optional[Union[str, Path]] = None, config_dir: Optional[Union[str, Path]] = None):
        if souls_dir:
            self.souls_dir = Path(souls_dir)
        else:
            # Look in repo root or current directory
            candidates = [
                Path.cwd() / "souls",
                Path(__file__).resolve().parent.parent.parent / "souls",
            ]
            self.souls_dir = next((c for c in candidates if c.exists() and c.is_dir()), candidates[0])

        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".saleha"
        
        self._active_file = self.config_dir / "active_soul.json"
        self._cache: Dict[str, SoulPackage] = {}
        self.reload()

    def reload(self) -> None:
        """Scan and load all souls from the souls/ directory."""
        self._cache.clear()
        if not self.souls_dir.exists():
            return

        for item in self.souls_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "soul.json"
                soul_md_path = item / "SOUL.md"
                if manifest_path.exists() and soul_md_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)

                        with open(soul_md_path, "r", encoding="utf-8") as f:
                            soul_content = f.read()

                        ident_content = ""
                        ident_path = item / "IDENTITY.md"
                        if ident_path.exists():
                            with open(ident_path, "r", encoding="utf-8") as f:
                                ident_content = f.read()

                        style_content = ""
                        style_path = item / "STYLE.md"
                        if style_path.exists():
                            with open(style_path, "r", encoding="utf-8") as f:
                                style_content = f.read()

                        package = SoulPackage(
                            name=meta.get("name", item.name),
                            display_name=meta.get("displayName", meta.get("name", item.name)),
                            version=meta.get("version", "1.0.0"),
                            archetype=meta.get("archetype", "General Intelligence"),
                            description=meta.get("description", ""),
                            tags=meta.get("tags", []),
                            cognitive_params=meta.get("cognitive_params", {}),
                            allowed_tools=meta.get("allowed_tools", []),
                            soul_md=soul_content,
                            identity_md=ident_content,
                            style_md=style_content,
                            path=str(item),
                        )
                        self._cache[package.name] = package
                    except Exception as e:
                        # Log error but don't crash
                        pass

    def list_souls(self) -> List[SoulPackage]:
        """Return all registered souls sorted by name."""
        return sorted(self._cache.values(), key=lambda s: s.name)

    def get_soul(self, name: str) -> Optional[SoulPackage]:
        """Retrieve a specific soul by name or alias."""
        norm = name.strip().lower()
        if norm in self._cache:
            return self._cache[norm]
        # Match by partial tag or name
        for s in self._cache.values():
            if norm in s.name.lower() or norm in s.display_name.lower():
                return s
        return None

    def get_active_soul_name(self) -> str:
        """Get the identifier of the currently active soul."""
        if self._active_file.exists():
            try:
                with open(self._active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = data.get("active_soul")
                    if name and name in self._cache:
                        return name
            except Exception:
                pass
        
        # Fallback to default
        if self.DEFAULT_SOUL in self._cache:
            return self.DEFAULT_SOUL
        if self._cache:
            return next(iter(self._cache.keys()))
        return "default"

    def get_active_soul(self) -> Optional[SoulPackage]:
        """Retrieve the currently active SoulPackage."""
        name = self.get_active_soul_name()
        return self._cache.get(name)

    def set_active_soul(self, name: str) -> SoulPackage:
        """Set the active soul and persist preference to disk."""
        target = self.get_soul(name)
        if not target:
            raise KeyError(f"Soul '{name}' not found. Available: {list(self._cache.keys())}")

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._active_file, "w", encoding="utf-8") as f:
                json.dump({"active_soul": target.name, "version": target.version}, f, indent=2)
        except Exception:
            pass

        return target

    def validate_all(self) -> Dict[str, Any]:
        """Validate all souls against SoulSpec v1.0 integrity rules."""
        results = {
            "total_souls": len(self._cache),
            "valid_souls": 0,
            "invalid_souls": 0,
            "errors": {},
        }
        for name, soul in self._cache.items():
            errs = []
            if not soul.display_name:
                errs.append("Missing displayName")
            if not soul.archetype:
                errs.append("Missing archetype")
            if not soul.soul_md or len(soul.soul_md.strip()) < 50:
                errs.append("SOUL.md is empty or too short (<50 chars)")
            
            if errs:
                results["invalid_souls"] += 1
                results["errors"][name] = errs
            else:
                results["valid_souls"] += 1

        return results


# Global singleton instance
soul_engine = SoulEngine()
