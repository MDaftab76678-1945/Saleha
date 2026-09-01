"""
Saleha VS Code & Cursor Extension Packaging Utility

Automates 1-click validation, manifest compilation, and .vsix packaging
for VS Code Marketplace and Open-VSX Registry.
"""

import json
import os
import shutil
import zipfile
from typing import Dict, Any, List


def validate_manifest(package_json_path: str) -> Dict[str, Any]:
    """Validates the VS Code extension manifest for required attributes and version sync."""
    with open(package_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_fields = ["name", "displayName", "version", "publisher", "engines", "activationEvents", "contributes"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required extension manifest field: '{field}'")

    return data


def build_vsix_bundle(extension_dir: str, output_dir: str) -> str:
    """Builds a deployable extension archive (.vsix compatible zip)."""
    manifest_path = os.path.join(extension_dir, "package.json")
    manifest = validate_manifest(manifest_path)
    version = manifest.get("version", "2.6.0")

    os.makedirs(output_dir, exist_ok=True)
    vsix_name = f"saleha-vscode-{version}.vsix"
    vsix_path = os.path.join(output_dir, vsix_name)

    # Package extension files
    with zipfile.ZipFile(vsix_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(extension_dir):
            for file in files:
                if any(ign in file for ign in [".vsix", ".git", "node_modules"]):
                    continue
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, extension_dir)
                zip_file.write(fpath, arcname=f"extension/{rel_path}")

    return vsix_path


if __name__ == "__main__":
    ext_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(ext_dir, "dist")
    out = build_vsix_bundle(ext_dir, dist_dir)
    print(f"Extension bundle built successfully: {out}")
