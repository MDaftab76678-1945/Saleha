"""
Builds the standalone `saleha` binary (via scripts/build_standalone.py) and copies
it into apps/desktop/src-tauri/binaries/ using the Rust target-triple naming
convention Tauri's `externalBin` sidecar loader expects
(saleha-<target-triple>[.exe]). Run this before `tauri dev` / `tauri build`.
"""

import os
import shutil
import subprocess
import sys

if sys.stdout.encoding is not None and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BINARIES_DIR = os.path.join(ROOT_DIR, "apps", "desktop", "src-tauri", "binaries")


def find_rustc() -> str:
    candidate = shutil.which("rustc")
    if candidate:
        return candidate
    cargo_bin_rustc = os.path.join(os.path.expanduser("~"), ".cargo", "bin", "rustc.exe" if os.name == "nt" else "rustc")
    if os.path.exists(cargo_bin_rustc):
        return cargo_bin_rustc
    raise RuntimeError("rustc not found on PATH or in ~/.cargo/bin — install the Rust toolchain (rustup) first")


def host_target_triple() -> str:
    out = subprocess.check_output([find_rustc(), "-vV"], text=True)
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Could not determine host target triple from `rustc -vV`")


def main():
    from build_standalone import build_binary

    build_binary(clean=False, use_nuitka=False)

    triple = host_target_triple()
    is_windows = "windows" in triple
    src = os.path.join(ROOT_DIR, "dist", "saleha.exe" if is_windows else "saleha")
    if not os.path.exists(src):
        print(f"⚠️ Expected built binary at {src} but it was not found.")
        sys.exit(1)

    os.makedirs(BINARIES_DIR, exist_ok=True)
    dest = os.path.join(BINARIES_DIR, f"saleha-{triple}{'.exe' if is_windows else ''}")
    shutil.copyfile(src, dest)
    print(f"✅ Sidecar binary ready at {dest}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main()
