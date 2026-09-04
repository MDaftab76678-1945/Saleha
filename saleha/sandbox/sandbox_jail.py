import os
import sys
import subprocess
import tempfile
import resource
from typing import Dict, Any

class HardenedSandbox:
    """POSIX isolated worker process with strict memory, CPU, and process count ceilings."""

    def __init__(self, max_mem_mb: int = 128, max_cpu_sec: int = 3, max_procs: int = 4):
        self.max_mem_bytes = max_mem_mb * 1024 * 1024
        self.max_cpu_sec = max_cpu_sec
        self.max_procs = max_procs

    def _set_security_rlimits(self):
        # 1. Virtual memory limit
        resource.setrlimit(resource.RLIMIT_AS, (self.max_mem_bytes, self.max_mem_bytes))
        # 2. CPU execution time limit
        resource.setrlimit(resource.RLIMIT_CPU, (self.max_cpu_sec, self.max_cpu_sec))
        # 3. Prevent fork bombs (Process limit)
        resource.setrlimit(resource.RLIMIT_NPROC, (self.max_procs, self.max_procs))
        # 4. Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # 5. Limit file creation size (1MB max output)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        # 6. Limit open file descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))

    def run_isolated(self, python_code: str) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as jail_dir:
            file_path = os.path.join(jail_dir, "jailed_workload.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(python_code)

            clean_env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONUNBUFFERED": "1",
                "LANG": "C.UTF-8"
            }

            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.max_cpu_sec + 1,
                    preexec_fn=self._set_security_rlimits,
                    cwd=jail_dir,
                    env=clean_env
                )
                return {
                    "passed": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip()
                }
            except subprocess.TimeoutExpired:
                return {"passed": False, "exit_code": -1, "stdout": "", "stderr": "SIGKILL: Execution timed out."}
            except Exception as ex:
                return {"passed": False, "exit_code": -2, "stdout": "", "stderr": f"Sandbox Exception: {ex}"}
