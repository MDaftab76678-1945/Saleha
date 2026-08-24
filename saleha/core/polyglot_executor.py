"""
Saleha Core: Polyglot Multi-Language Code Execution Sandbox

Executes generated code across multiple programming languages with pre-execution
AST SAST security auditing, timeout protection, temp directory isolation, and audit logging.

Supported Languages:
- Python (`.py`) -> `python` / `python3`
- JavaScript (`.js`, `.mjs`) -> `node`
- TypeScript (`.ts`) -> `ts-node` / `tsx` / `node`
- Go (`.go`) -> `go run`
- Java (`.java`) -> `javac` + `java`
- Rust (`.rs`) -> `rustc` + binary execution
"""

import os
import shutil
import tempfile
import time
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Any

from saleha.core.security_scanner import ASTSecurityScanner
from saleha.core.audit_log import AuditLog

MAX_POLYGLOT_OUTPUT_CHARS = 50_000


@dataclass
class PolyglotExecutionResult:
    success: bool
    language: str
    output: str = ""
    error: str = ""
    exit_code: int = 0
    blocked: bool = False
    block_reason: str = ""
    execution_time: float = 0.0


class PolyglotExecutor:
    """Executes multi-language code in an isolated sandbox with security gates."""

    LANG_EXTENSIONS = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "go": ".go",
        "java": ".java",
        "rust": ".rs",
    }

    EXT_TO_LANG = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.scanner = ASTSecurityScanner()
        self.audit = AuditLog()

    def detect_language(self, filename_or_ext: str) -> str:
        ext = os.path.splitext(filename_or_ext)[1].lower()
        if not ext and filename_or_ext.lower() in self.LANG_EXTENSIONS:
            return filename_or_ext.lower()
        return self.EXT_TO_LANG.get(ext, "python")

    def _find_compiler(self, tool_name: str) -> Optional[str]:
        return shutil.which(tool_name)

    def execute(self, code: str, language: Optional[str] = None, filename: Optional[str] = None) -> PolyglotExecutionResult:
        """Runs the provided code through SAST security checks and executes it in sandbox."""
        lang = language or (self.detect_language(filename) if filename else "python")
        ext = self.LANG_EXTENSIONS.get(lang, ".py")
        temp_fname = filename or f"solution{ext}"
        start_time = time.time()

        # 1. Pre-execution AST SAST Security Scan
        vulns = self.scanner.scan_code(code, filename=temp_fname)
        high_vulns = [v for v in vulns if v.severity == "HIGH"]
        if high_vulns:
            reason = f"Blocked by SAST: {high_vulns[0].rule_id} - {high_vulns[0].description}"
            self.audit.record(
                code=code,
                allowed=False,
                reason=reason
            )
            return PolyglotExecutionResult(
                success=False,
                language=lang,
                blocked=True,
                block_reason=reason,
                error=reason
            )

        # 2. Prepare Sandboxed Execution Directory
        temp_dir = tempfile.mkdtemp(prefix=f"saleha_exec_{lang}_")
        temp_file = os.path.join(temp_dir, temp_fname)

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(code)

            exec_res = self._dispatch_execution(temp_dir, temp_file, lang)
            exec_time = round(time.time() - start_time, 3)
            exec_res.execution_time = exec_time

            self.audit.record(
                code=code,
                allowed=True,
                executed=True,
                success=exec_res.success,
                exit_code=exec_res.exit_code
            )
            return exec_res
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _dispatch_execution(self, temp_dir: str, temp_file: str, lang: str) -> PolyglotExecutionResult:
        # Python
        if lang == "python":
            python_bin = shutil.which("python3") or shutil.which("python") or "python"
            return self._run_proc([python_bin, temp_file], temp_dir, lang)

        # JavaScript (Node.js)
        if lang == "javascript":
            node_bin = self._find_compiler("node")
            if not node_bin:
                return PolyglotExecutionResult(success=False, language=lang, error="'node' not found on system PATH.")
            return self._run_proc([node_bin, temp_file], temp_dir, lang)

        # TypeScript
        if lang == "typescript":
            ts_bin = self._find_compiler("tsx") or self._find_compiler("ts-node")
            if ts_bin:
                return self._run_proc([ts_bin, temp_file], temp_dir, lang)
            node_bin = self._find_compiler("node")
            if node_bin:
                return self._run_proc([node_bin, temp_file], temp_dir, lang)
            return PolyglotExecutionResult(success=False, language=lang, error="'tsx', 'ts-node', or 'node' not found.")

        # Go
        if lang == "go":
            go_bin = self._find_compiler("go")
            if not go_bin:
                return PolyglotExecutionResult(success=False, language=lang, error="'go' compiler not found on PATH.")
            return self._run_proc([go_bin, "run", temp_file], temp_dir, lang)

        # Java
        if lang == "java":
            javac_bin = self._find_compiler("javac")
            java_bin = self._find_compiler("java")
            if not javac_bin or not java_bin:
                return PolyglotExecutionResult(success=False, language=lang, error="'javac'/'java' JDK not found on PATH.")
            compile_res = subprocess.run([javac_bin, temp_file], cwd=temp_dir, capture_output=True, text=True)
            if compile_res.returncode != 0:
                return PolyglotExecutionResult(success=False, language=lang, error=compile_res.stderr, exit_code=compile_res.returncode)
            class_name = os.path.splitext(os.path.basename(temp_file))[0]
            return self._run_proc([java_bin, class_name], temp_dir, lang)

        # Rust
        if lang == "rust":
            rustc_bin = self._find_compiler("rustc")
            if not rustc_bin:
                return PolyglotExecutionResult(success=False, language=lang, error="'rustc' compiler not found on PATH.")
            bin_name = os.path.join(temp_dir, "out_bin.exe" if os.name == "nt" else "out_bin")
            compile_res = subprocess.run([rustc_bin, temp_file, "-o", bin_name], cwd=temp_dir, capture_output=True, text=True)
            if compile_res.returncode != 0:
                return PolyglotExecutionResult(success=False, language=lang, error=compile_res.stderr, exit_code=compile_res.returncode)
            return self._run_proc([bin_name], temp_dir, lang)

        return PolyglotExecutionResult(success=False, language=lang, error=f"Unsupported execution runtime: {lang}")

    def _run_proc(self, cmd: list, cwd: str, lang: str) -> PolyglotExecutionResult:
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=""
            )
            out = proc.stdout[:MAX_POLYGLOT_OUTPUT_CHARS]
            err = proc.stderr[:MAX_POLYGLOT_OUTPUT_CHARS]
            return PolyglotExecutionResult(
                success=(proc.returncode == 0),
                language=lang,
                output=out,
                error=err,
                exit_code=proc.returncode
            )
        except subprocess.TimeoutExpired:
            return PolyglotExecutionResult(
                success=False,
                language=lang,
                error=f"Execution timed out after {self.timeout}s."
            )
        except Exception as e:
            return PolyglotExecutionResult(
                success=False,
                language=lang,
                error=f"Process execution error: {str(e)}"
            )


# Global instance
polyglot_executor = PolyglotExecutor()
