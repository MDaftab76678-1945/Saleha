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

if sys.stdout.encoding is not None and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def build_binary(clean: bool = False, use_nuitka: bool = False):
    print("=" * 60)
    print("📦 Saleha Standalone Binary Packager")
    print("=" * 60)

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dist_dir = os.path.join(root_dir, "dist")
    build_dir = os.path.join(root_dir, "build")
    # `saleha/cli/commands` used to be a single commands.py module and is now a
    # package. This path still pointed at the old file, so every sidecar build
    # failed with "Script file ... commands.py does not exist" -- and because
    # nothing checked the exit code, `turbo run build` carried on regardless.
    entrypoint = os.path.join(root_dir, "saleha", "cli", "commands", "__init__.py")
    if not os.path.isfile(entrypoint):
        raise SystemExit(
            f"CLI entrypoint not found: {entrypoint}\n"
            f"pyproject.toml declares `saleha = \"saleha.cli.commands:cli\"`; "
            f"this build must point at the same module."
        )

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
    # A failed compile used to print a warning and return normally, so callers
    # (build_desktop_sidecar.py, and `turbo run build` above it) carried on as
    # if a binary had been produced. Raise instead: a build that did not build
    # must not report as one.
    try:
        res = subprocess.run(cmd, cwd=root_dir, check=False)
    except FileNotFoundError as exc:
        raise SystemExit(
            "PyInstaller / Nuitka not installed. Run: pip install pyinstaller"
        ) from exc

    if res.returncode != 0:
        raise SystemExit(f"Compilation failed with exit code {res.returncode}")
    print("\nStandalone binary successfully compiled in ./dist/saleha")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Saleha Standalone Binary")
    parser.add_argument("--clean", action="store_true", help="Clean build directories before build")
    parser.add_argument("--nuitka", action="store_true", help="Use Nuitka native compiler instead of PyInstaller")
    args = parser.parse_args()

    build_binary(clean=args.clean, use_nuitka=args.nuitka)

