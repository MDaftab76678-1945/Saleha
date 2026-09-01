"""
Saleha Desktop: Packaging and Distribution Script

Generates executable launcher configurations, desktop shortcuts, and
distribution metadata for Windows, macOS, and Linux desktop environments.
"""

from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path


def generate_desktop_manifest(output_dir: str = "dist/desktop") -> str:
    """Generates desktop application manifest and packaging metadata."""
    os.makedirs(output_dir, exist_ok=True)
    manifest = {
        "name": "Saleha AI Desktop",
        "version": "2.0.0",
        "description": "Autonomous AI Software Engineering Desktop Studio",
        "main_entry": "saleha.desktop.app:SalehaDesktopApp",
        "window": {
            "title": "Saleha AI Desktop v2.0",
            "width": 1280,
            "height": 820,
            "min_width": 1024,
            "min_height": 700,
            "resizable": True,
            "icon": "assets/icon.png"
        },
        "features": {
            "local_llm_manager": True,
            "system_tray": True,
            "voice_hud": True,
            "dag_visualizer": True,
            "memory_explorer": True
        }
    }

    manifest_path = os.path.join(output_dir, "app_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Generate quick launch scripts
    if sys.platform == "win32":
        bat_path = os.path.join(output_dir, "Launch-Saleha-Desktop.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("@echo off\ntitle Saleha AI Desktop\npython -m saleha.cli.commands desktop %*\npause\n")
    else:
        sh_path = os.path.join(output_dir, "launch-saleha-desktop.sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env bash\npython3 -m saleha.cli.commands desktop \"$@\"\n")
        os.chmod(sh_path, 0o755)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(f"[OK] Desktop distribution bundle generated in: {output_dir}")
    return manifest_path


if __name__ == "__main__":
    generate_desktop_manifest()
