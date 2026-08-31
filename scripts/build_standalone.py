"""
Saleha Standalone Binary Packager (PyInstaller / Nuitka Engine)

Freezes the complete Saleha multi-agent AI framework into a single, zero-dependency
standalone binary (saleha.exe / saleha) so users can run it without Python or pip.
"""

import os
import sys
import shutil
import subprocess
import argparse


def build_binary(clean: bool = False, use_nuitka: bool = False):
    print("=" * 60)
    print("📦 Saleha Standalone Binary Packager")
    print("=" * 60)

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dist_dir = os.path.join(root_dir, "dist")
    build_dir = os.path.join(root_dir, "build")
    entrypoint = os.path.join(root_dir, "saleha", "cli", "commands.py")

    if clean:
        print("🧹 Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(build_dir, ignore_errors=True)

    if use_nuitka:
        print("🚀 Compiling with Nuitka C++ Native Compiler...")
        cmd = [
            sys.executable, "-m", "nuitka",
            "--onefile",
            "--assume-yes-for-downloads",
            f"--output-dir={dist_dir}",
            "--output-filename=saleha",
            entrypoint
        ]
    else:
        print("⚡ Compiling with PyInstaller Bundler...")
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name=saleha",
            f"--distpath={dist_dir}",
            f"--workpath={build_dir}",
            "--hidden-import=rich",
            "--hidden-import=click",
            "--hidden-import=pydantic",
            "--hidden-import=anyio",
            "--hidden-import=saleha",
            entrypoint
        ]

    print(f"Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=root_dir, check=False)
        if res.returncode == 0:
            print("\n✅ Standalone binary successfully compiled in ./dist/saleha")
        else:
            print(f"\n⚠️ Compilation finished with exit code {res.returncode}")
    except FileNotFoundError:
        print("\n⚠️ PyInstaller / Nuitka not installed. Run: pip install pyinstaller")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Saleha Standalone Binary")
    parser.add_argument("--clean", action="store_true", help="Clean build directories before build")
    parser.add_argument("--nuitka", action="store_true", help="Use Nuitka native compiler instead of PyInstaller")
    args = parser.parse_args()

    build_binary(clean=args.clean, use_nuitka=args.nuitka)

