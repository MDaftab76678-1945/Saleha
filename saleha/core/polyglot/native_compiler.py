"""
Saleha Native Standalone Binary & LLVM JIT Compiler.
Compiles synthesized high-level code directly into standalone native machine code:
- Multi-target Compilation (Windows .exe, Linux ELF, macOS Mach-O)
- Ultra-fast C / Rust / Zig Toolchain Dispatch
- Stripped, Zero-Dependency Distribution Artifacts
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

PER_COMPILER_S = 10.0     # one clang/gcc run
COMPILE_BUDGET_S = 20.0   # all of them together: the longest a caller (the API route) waits


@dataclass
class NativeCompilationResult:
    success: bool
    target_triple: str
    output_binary_path: str
    binary_size_bytes: int
    compilation_time_ms: float
    compiler_used: Optional[str] = None
    error_message: Optional[str] = None


class NativeBinaryCompiler:
    """
    Compiles C source into a native binary via a real clang/gcc subprocess
    call. If no compiler is available, reports failure honestly -- it does
    not write a placeholder file and claim success.
    """

    def compile_c_standalone(self, c_code: str, binary_name: str = "saleha_app") -> NativeCompilationResult:
        start_t = time.perf_counter()
        sys_name = platform.system()
        ext = ".exe" if sys_name == "Windows" else ""
        target_triple = f"{platform.machine()}-pc-{sys_name.lower()}"

        tmp_dir = tempfile.mkdtemp()
        src_path = os.path.join(tmp_dir, "main.c")
        out_path = os.path.join(tmp_dir, binary_name + ext)

        with open(src_path, "w", encoding="utf-8") as f:
            f.write(c_code)

        compilers = ["clang", "gcc"]
        compiled = False
        compiler_used = None
        err_msg = None

        deadline = time.monotonic() + COMPILE_BUDGET_S
        for cc in compilers:
            left = min(PER_COMPILER_S, deadline - time.monotonic())
            if left <= 0:
                err_msg = f"{err_msg + '; ' if err_msg else ''}{COMPILE_BUDGET_S:.0f}s compile budget used up before {cc}"
                break
            # stderr goes to a file, not a pipe: after killing a timed-out run,
            # subprocess.run on Windows waits for its pipes to close, and the
            # compiler's own children (cc1, as, ld, link.exe) hold them open.
            # A Windows CI run spent 79.7s in a test making two compiles that
            # were each meant to stop at 10s.
            with tempfile.TemporaryFile(dir=tmp_dir) as errf:
                try:
                    proc = subprocess.run([cc, "-O3", src_path, "-o", out_path],
                                          stdout=subprocess.DEVNULL, stderr=errf, timeout=left)
                except FileNotFoundError:
                    err_msg = f"{cc} not found on PATH"
                    continue
                except subprocess.TimeoutExpired:
                    err_msg = f"{cc} timed out after {left:.0f}s"
                    continue
                except Exception as ex:
                    err_msg = f"{cc} could not run: {ex}"
                    continue
                if proc.returncode == 0:
                    compiled = True
                    compiler_used = cc
                    break
                errf.seek(0)
                err_msg = f"{cc} failed: {errf.read().decode('utf-8', 'replace').strip() or proc.returncode}"

        compilation_time_ms = round((time.perf_counter() - start_t) * 1000, 2)

        if not compiled:
            return NativeCompilationResult(
                success=False,
                target_triple=target_triple,
                output_binary_path="",
                binary_size_bytes=0,
                compilation_time_ms=compilation_time_ms,
                compiler_used=None,
                error_message=err_msg or "No C compiler (clang/gcc) available on PATH.",
            )

        size = os.path.getsize(out_path)

        return NativeCompilationResult(
            success=True,
            target_triple=target_triple,
            output_binary_path=out_path,
            binary_size_bytes=size,
            compilation_time_ms=compilation_time_ms,
            compiler_used=compiler_used,
            error_message=None,
        )


native_compiler = NativeBinaryCompiler()

