"""Resume a previously suspended training process (OS-level SIGCONT / NtResumeProcess).

This does NOT resume from a training checkpoint -- train_sovereign_ultra_gpu.py does
that automatically via get_last_checkpoint(). Use this only when you manually
suspended the python training process and want to un-suspend it.

Usage:
    python scripts/resume_training.py <PID>
"""

import sys

import psutil


def resume(pid: int) -> None:
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[x] Process {pid} not found.")
        sys.exit(1)

    cmdline = " ".join(p.cmdline()).lower()
    if "python" not in p.name().lower() and "python" not in cmdline:
        print(f"[x] Refusing: PID {pid} is {p.name()!r} ({cmdline!r}), not a python process.")
        sys.exit(1)
    if "train" not in cmdline:
        print(f"[!] Warning: PID {pid} cmdline has no 'train' -- {cmdline!r}")
        if input("    Resume anyway? [y/N] ").strip().lower() != "y":
            sys.exit(1)

    try:
        p.resume()
        print(f"[ok] Process {pid} resumed. Status: {p.status()}")
    except Exception as e:  # noqa: BLE001
        print(f"[x] Error resuming {pid}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    resume(int(sys.argv[1]))
