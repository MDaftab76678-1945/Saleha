"""
Saleha Distribution: PyPI Package Builder & Validator

Builds source distribution (.tar.gz) and binary wheel (.whl) packages
using standard build tools and validates package metadata.
"""

from __future__ import annotations

import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_package(clean: bool = True) -> bool:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root_dir = Path(__file__).resolve().parent.parent
    dist_dir = root_dir / "dist"
    
    print(f"=== Building Saleha Distribution in: {root_dir} ===")
    
    if clean and dist_dir.exists():
        print(f"Cleaning existing dist directory: {dist_dir}")
        shutil.rmtree(dist_dir)
        
    # Ensure build is installed
    try:
        import build
    except ImportError:
        print("Installing build frontend...")
        subprocess.run([sys.executable, "-m", "pip", "install", "build", "twine"], check=True)
        
    cmd = [sys.executable, "-m", "build", str(root_dir), "--outdir", str(dist_dir)]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
        
    if res.returncode != 0:
        print(f"❌ Build failed with exit code {res.returncode}")
        return False
        
    built_files = list(dist_dir.glob("*"))
    print(f"✅ Built {len(built_files)} distribution artifacts:")
    for f in built_files:
        print(f"  • {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        
    # Validate with twine if available
    try:
        twine_res = subprocess.run([sys.executable, "-m", "twine", "check", str(dist_dir / "*")], capture_output=True, text=True)
        print("\nTwine Check Output:\n" + twine_res.stdout)
    except Exception:
        pass
        
    return True


if __name__ == "__main__":
    success = build_package()
    sys.exit(0 if success else 1)
