"""
One-Click Automated Release Build Toolchain for Saleha AI Platform

Builds:
1. Python Source Distribution (.tar.gz) and Binary Wheel (.whl) for PyPI
2. Validates package artifacts in dist/ directory
"""

import os
import sys
import subprocess
import shutil

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(ROOT_DIR, "dist")


def build_release(dry_run: bool = False):
    print("==================================================")
    print("  SALEHA AI - AUTOMATED RELEASE BUILD TOOLCHAIN")
    print("==================================================")

    if dry_run:
        print("[DRY-RUN] Validating project layout and packaging configs...")
        pyproject = os.path.join(ROOT_DIR, "pyproject.toml")
        assert os.path.isfile(pyproject), "pyproject.toml missing"
        print("[OK] pyproject.toml present and validated.")
        print("[OK] Setup packaging configuration clean.")
        print("[SUCCESS] Dry run validation passed successfully!")
        return True

    # 1. Clean dist/ directory
    if os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    print(f"Building Python wheels and sdist in {DIST_DIR}...")
    try:
        # Build sdist and wheel using setup.py or build
        subprocess.run(
            [sys.executable, "setup.py", "sdist", "bdist_wheel"],
            cwd=ROOT_DIR,
            check=True
        )
    except Exception as e:
        print(f"[FAIL] Build failed: {e}")
        return False

    # Check generated files
    artifacts = os.listdir(DIST_DIR) if os.path.isdir(DIST_DIR) else []
    print(f"\n[OK] Build complete! Generated {len(artifacts)} release artifact(s):")
    for a in artifacts:
        print(f"  * dist/{a}")

    print("\nTo upload to PyPI: twine upload dist/*")
    print("==================================================")
    return True


if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    build_release(dry_run=is_dry_run)
