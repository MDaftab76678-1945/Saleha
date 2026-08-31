"""
Saleha VS Code Extension Packager

Bundles the `editors/vscode` extension into a `.vsix` package using `@vscode/vsce`
or creates a standard zipped marketplace archive ready for distribution.
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


def package_extension() -> bool:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root_dir = Path(__file__).resolve().parent.parent
    vscode_dir = root_dir / "editors" / "vscode"
    dist_dir = root_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    
    pkg_json_path = vscode_dir / "package.json"
    if not pkg_json_path.exists():
        print(f"❌ package.json not found at {pkg_json_path}")
        return False
        
    with open(pkg_json_path, "r", encoding="utf-8") as f:
        pkg_data = json.load(f)
        
    version = pkg_data.get("version", "2.0.0")
    name = pkg_data.get("name", "saleha-vscode")
    vsix_name = f"{name}-{version}.vsix"
    out_vsix = dist_dir / vsix_name
    
    print(f"=== Packaging VS Code Extension: {name} v{version} ===")
    
    # Try using npx @vscode/vsce if available, else build zip structure
    vsce_cmd = shutil.which("vsce") or shutil.which("npx")
    packaged_via_vsce = False
    
    if vsce_cmd:
        try:
            cmd = ["vsce", "package", "--out", str(out_vsix)] if "vsce" in vsce_cmd else ["npx", "@vscode/vsce", "package", "--out", str(out_vsix)]
            print(f"Attempting vsce package in {vscode_dir}...")
            res = subprocess.run(cmd, cwd=str(vscode_dir), capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and out_vsix.exists():
                print(f"✅ Created VSIX via vsce: {out_vsix}")
                packaged_via_vsce = True
        except Exception as e:
            print(f"Notice: vsce cli package skipped ({e}), falling back to zip bundle builder...")
            
    if not packaged_via_vsce:
        # Build standard VSIX archive zip format
        print(f"Building standalone VSIX bundle archive at: {out_vsix}")
        with zipfile.ZipFile(out_vsix, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in vscode_dir.rglob("*"):
                if file_path.is_file() and not any(part.startswith(".") or part == "node_modules" for part in file_path.parts):
                    arcname = f"extension/{file_path.relative_to(vscode_dir)}"
                    zf.write(file_path, arcname)
                    
            # Add extension manifest
            manifest_content = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Id="{name}" Version="{version}" Publisher="saleha-ai" />
    <DisplayName>{pkg_data.get('displayName', 'Saleha AI')}</DisplayName>
    <Description>{pkg_data.get('description', '')}</Description>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
</PackageManifest>"""
            zf.writestr("extension.vsixmanifest", manifest_content)
            
        print(f"✅ Successfully built VSIX package: {out_vsix} ({out_vsix.stat().st_size / 1024:.1f} KB)")
        
    return True


if __name__ == "__main__":
    success = package_extension()
    sys.exit(0 if success else 1)
