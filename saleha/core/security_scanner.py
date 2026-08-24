"""
Saleha Core: Deep AST Security SAST & Vulnerability Scanner

Performs static analysis on Python codebases using Abstract Syntax Trees (AST):
1. SEC001 - SQL Injection (f-strings / format formatting inside query execution)
2. SEC002 - Unsafe Code Execution & Deserialization (eval, exec, pickle.loads)
3. SEC003 - Hardcoded Secrets & High-Entropy API Keys
4. SEC004 - Insecure Subprocess with shell=True
5. SEC005 - Weak Cryptography (MD5, SHA1)
"""

import ast
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from saleha.core.path_utils import safe_relpath


@dataclass
class SecurityVulnerability:
    rule_id: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    remediation: str


@dataclass
class ScanReport:
    total_files_scanned: int = 0
    total_vulnerabilities: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    clean_files: List[str] = field(default_factory=list)


class ASTSecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, lines: List[str]):
        self.filename = filename
        self.lines = lines
        self.vulnerabilities: List[SecurityVulnerability] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_Call(self, node: ast.Call):
        # 1. Check eval / exec / pickle / yaml
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"

        if func_name in ("eval", "exec"):
            self.vulnerabilities.append(SecurityVulnerability(
                rule_id="SEC002",
                severity="HIGH",
                file_path=self.filename,
                line_number=node.lineno,
                code_snippet=self._get_snippet(node.lineno),
                description=f"Use of dangerous dynamic execution function '{func_name}'.",
                remediation="Avoid eval/exec. Use ast.literal_eval or structured parsers."
            ))

        if func_name in ("pickle.loads", "pickle.load", "marshal.loads", "yaml.unsafe_load"):
            self.vulnerabilities.append(SecurityVulnerability(
                rule_id="SEC002",
                severity="HIGH",
                file_path=self.filename,
                line_number=node.lineno,
                code_snippet=self._get_snippet(node.lineno),
                description=f"Unsafe deserialization function '{func_name}' can lead to arbitrary remote code execution.",
                remediation="Use json, protobuf, or safe yaml loaders."
            ))

        # 2. Check SQL Injection in execute/executemany
        if func_name.endswith("execute") or func_name.endswith("raw_sql") or func_name.endswith("select"):
            if node.args:
                first_arg = node.args[0]
                # Formatted value (f-string)
                if isinstance(first_arg, ast.JoinedStr):
                    self.vulnerabilities.append(SecurityVulnerability(
                        rule_id="SEC001",
                        severity="HIGH",
                        file_path=self.filename,
                        line_number=node.lineno,
                        code_snippet=self._get_snippet(node.lineno),
                        description="Potential SQL Injection: f-string interpolation detected in database query.",
                        remediation="Use parameterized queries with bind variables (e.g. `cursor.execute('SELECT * FROM t WHERE id = ?', (id,))`)."
                    ))
                # Binary operation (e.g. "SELECT * FROM " + user_input or % formatting)
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Add, ast.Mod)):
                    self.vulnerabilities.append(SecurityVulnerability(
                        rule_id="SEC001",
                        severity="HIGH",
                        file_path=self.filename,
                        line_number=node.lineno,
                        code_snippet=self._get_snippet(node.lineno),
                        description="Potential SQL Injection: String concatenation or %-formatting detected in query.",
                        remediation="Use parameterized queries with bind parameters."
                    ))

        # 3. Check Subprocess shell=True
        if func_name.startswith("subprocess."):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.vulnerabilities.append(SecurityVulnerability(
                        rule_id="SEC004",
                        severity="MEDIUM",
                        file_path=self.filename,
                        line_number=node.lineno,
                        code_snippet=self._get_snippet(node.lineno),
                        description="Subprocess invocation with shell=True can allow command injection.",
                        remediation="Pass command as a list with shell=False (e.g. `['ls', '-l']`)."
                    ))

        # 4. Check Weak Cryptography (MD5, SHA1)
        if func_name in ("hashlib.md5", "hashlib.sha1", "md5", "sha1"):
            self.vulnerabilities.append(SecurityVulnerability(
                rule_id="SEC005",
                severity="LOW",
                file_path=self.filename,
                line_number=node.lineno,
                code_snippet=self._get_snippet(node.lineno),
                description=f"Use of weak hash algorithm '{func_name}'.",
                remediation="Use secure hashing algorithms like hashlib.sha256, bcrypt, or argon2."
            ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # 5. Check hardcoded secrets
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                secret_keywords = ("password", "passwd", "secret_key", "api_key", "auth_token", "jwt_secret", "private_key")
                if any(k in var_name for k in secret_keywords):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        val = node.value.value.strip()
                        # Ignore placeholders
                        if len(val) >= 8 and not val.startswith("your_") and not val.startswith("my_") and val not in ("password", "secret"):
                            self.vulnerabilities.append(SecurityVulnerability(
                                rule_id="SEC003",
                                severity="HIGH",
                                file_path=self.filename,
                                line_number=node.lineno,
                                code_snippet=self._get_snippet(node.lineno),
                                description=f"Hardcoded credential/secret assigned to variable '{target.id}'.",
                                remediation="Store credentials in environment variables or a secure key management service."
                            ))
        self.generic_visit(node)


class ASTSecurityScanner:
    """Polyglot SAST Scanner for Python (AST) and JS/TS/Go/Java/Rust."""

    POLYGLOT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rs"}

    def scan_code(self, code: str, filename: str = "snippet.py") -> List[SecurityVulnerability]:
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".js", ".jsx", ".ts", ".tsx"):
            return self._scan_js_ts(code, filename)
        elif ext == ".go":
            return self._scan_go(code, filename)
        elif ext == ".java":
            return self._scan_java(code, filename)
        elif ext == ".rs":
            return self._scan_rust(code, filename)
        else:
            return self._scan_python(code, filename)

    def _scan_python(self, code: str, filename: str) -> List[SecurityVulnerability]:
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError:
            return []
        lines = code.splitlines()
        visitor = ASTSecurityVisitor(filename=filename, lines=lines)
        visitor.visit(tree)
        return visitor.vulnerabilities

    def _scan_js_ts(self, code: str, filename: str) -> List[SecurityVulnerability]:
        vulns = []
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            # SEC101: eval or Function constructor
            if re.search(r"\beval\s*\(", sline) or re.search(r"new\s+Function\s*\(", sline):
                vulns.append(SecurityVulnerability(
                    rule_id="SEC101", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Unsafe dynamic JavaScript execution (eval/Function).",
                    remediation="Avoid eval() or new Function(). Use JSON.parse or safe expression parsers."
                ))
            # SEC102: XSS
            if "dangerouslySetInnerHTML" in sline or "document.write(" in sline:
                vulns.append(SecurityVulnerability(
                    rule_id="SEC102", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Potential Cross-Site Scripting (XSS) via unescaped HTML injection.",
                    remediation="Sanitize HTML using DOMPurify or use standard textContent rendering."
                ))
            # SEC103: child_process.exec
            if "child_process.exec(" in sline or "execSync(" in sline:
                vulns.append(SecurityVulnerability(
                    rule_id="SEC103", severity="MEDIUM", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Insecure child_process.exec command execution.",
                    remediation="Use child_process.execFile() or spawn() with argument arrays."
                ))
            # Secrets
            if re.search(r"(?:api_key|jwt_secret|password|secret_key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", sline, re.IGNORECASE):
                vulns.append(SecurityVulnerability(
                    rule_id="SEC003", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Hardcoded API key or secret token detected.",
                    remediation="Store credentials in environment variables or secret manager."
                ))
        return vulns

    def _scan_go(self, code: str, filename: str) -> List[SecurityVulnerability]:
        vulns = []
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if re.search(r"db\.(?:Query|Exec)\s*\(\s*fmt\.Sprintf", sline) or re.search(r"db\.(?:Query|Exec)\s*\(\s*\"SELECT.*\"\s*\+", sline):
                vulns.append(SecurityVulnerability(
                    rule_id="SEC201", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Potential SQL Injection via string formatting in Go database query.",
                    remediation="Use parameterized queries with placeholder variables `db.Query('SELECT ... WHERE id = ?', id)`."
                ))
        return vulns

    def _scan_java(self, code: str, filename: str) -> List[SecurityVulnerability]:
        vulns = []
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if "ObjectInputStream" in sline or "readObject" in sline:
                vulns.append(SecurityVulnerability(
                    rule_id="SEC202", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Unsafe Java deserialization via ObjectInputStream / readObject.",
                    remediation="Use safe serialization formats like Jackson JSON or Protocol Buffers."
                ))
        return vulns

    def _scan_rust(self, code: str, filename: str) -> List[SecurityVulnerability]:
        vulns = []
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if re.search(r"\bunsafe\s*\{", sline):
                vulns.append(SecurityVulnerability(
                    rule_id="SEC301", severity="MEDIUM", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Unchecked 'unsafe' block in Rust code.",
                    remediation="Minimize unsafe blocks and wrap with safe abstractions."
                ))
            if re.search(r"(?:api_key|secret|password)\s*=\s*\"[A-Za-z0-9_\-]{16,}\"", sline, re.IGNORECASE):
                vulns.append(SecurityVulnerability(
                    rule_id="SEC003", severity="HIGH", file_path=filename, line_number=idx,
                    code_snippet=sline, description="Hardcoded credential or secret detected in Rust code.",
                    remediation="Store secrets in environment variables or configuration files."
                ))
        return vulns

    def scan_file(self, file_path: str) -> List[SecurityVulnerability]:
        if not os.path.isfile(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            return self.scan_code(code, filename=os.path.basename(file_path))
        except (OSError, UnicodeDecodeError):
            return []

    def scan_directory(self, dir_path: str = ".") -> ScanReport:
        report = ScanReport()
        for root, _, files in os.walk(dir_path):
            rel_parts = safe_relpath(root, dir_path).split(os.sep)
            if any((p.startswith(".") and p not in (".", "..")) or p in ("node_modules", "venv", "__pycache__", "build", "dist", ".git", "target", "vendor") for p in rel_parts):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.POLYGLOT_EXTENSIONS:
                    full_path = os.path.join(root, f)
                    report.total_files_scanned += 1
                    vulns = self.scan_file(full_path)
                    if vulns:
                        report.vulnerabilities.extend(vulns)
                    else:
                        report.clean_files.append(full_path)

        report.total_vulnerabilities = len(report.vulnerabilities)
        for v in report.vulnerabilities:
            if v.severity == "HIGH":
                report.high_count += 1
            elif v.severity == "MEDIUM":
                report.medium_count += 1
            else:
                report.low_count += 1

        return report
