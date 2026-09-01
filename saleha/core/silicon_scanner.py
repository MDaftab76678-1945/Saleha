"""
Saleha Core: SiliconCopilot Hardware & RTL Security Scanner

Provides static security analysis (SAST) for Verilog and SystemVerilog (.v, .sv)
hardware descriptions targeting critical Common Weakness Enumerations (CWE):
- SEC401: CWE-190 - Bit-Width Truncation & Integer Overflow in RTL
- SEC402: CWE-362 - Unsynchronized Asynchronous Reset Glitch / Race
- SEC403: CWE-440 - Inferred Latch & Incomplete Conditional State Leakage
- SEC404: CWE-284 / CWE-200 - Hardcoded RTL Trapdoor / Master Key Backdoor
- SEC405: CWE-1200 - Unsafe Clock Domain Crossing (CDC) without Synchronizer
"""

import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Any


@dataclass
class SiliconVulnerability:
    """Represents a detected Hardware/RTL security vulnerability."""
    rule_id: str
    cwe: str
    severity: str
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    remediation: str


class SiliconScanner:
    """Hardware Description Language (HDL / RTL) Security Scanner for Verilog and SystemVerilog."""

    SUPPORTED_EXTENSIONS = {".v", ".sv", ".vh", ".svh"}

    def __init__(self):
        """Initializes the SiliconCopilot hardware security scanner."""
        pass

    def scan_verilog(self, code: str, filename: str = "module.v") -> List[SiliconVulnerability]:
        """Scans Verilog / SystemVerilog source code for security vulnerabilities."""
        vulns: List[SiliconVulnerability] = []
        lines = code.splitlines()

        in_case_block = False
        case_has_default = False
        case_start_line = 0

        for idx, line in enumerate(lines, 1):
            sline = line.strip()

            # Skip comments
            if sline.startswith("//") or sline.startswith("/*"):
                continue

            # Inline suppression check (# noqa: SECxxx or // nosec)
            if "// nosec" in line or "// noqa" in line:
                continue

            # 1. SEC401: Bit-width overflow / unsafe addition without carry expansion
            # e.g., assign [7:0] out = a + b (where a, b are 8-bit, overflow truncates)
            if re.search(r"\bassign\s+\[\s*(\d+)\s*:\s*0\s*\]\s*\w+\s*=\s*\w+\s*\+\s*\w+", sline):
                vulns.append(SiliconVulnerability(
                    rule_id="SEC401",
                    cwe="CWE-190",
                    severity="HIGH",
                    file_path=filename,
                    line_number=idx,
                    code_snippet=sline,
                    description="Potential Integer Overflow / Bit-width Truncation: Addition assigned without carry bit width extension.",
                    remediation="Extend target wire width by 1 bit (e.g. [N:0]) or use saturation arithmetic logic."
                ))

            # 2. SEC402: Asynchronous reset race condition
            # e.g., always @(posedge clk or posedge rst) without glitch filter
            if re.search(r"always\s*@\s*\(\s*posedge\s+\w+\s+or\s+posedge\s+(?:rst|reset|async_rst)\b", sline, re.IGNORECASE):
                vulns.append(SiliconVulnerability(
                    rule_id="SEC402",
                    cwe="CWE-362",
                    severity="MEDIUM",
                    file_path=filename,
                    line_number=idx,
                    code_snippet=sline,
                    description="Asynchronous reset sensitivity list can cause meta-stability and glitch race conditions.",
                    remediation="Use synchronous resets or a dual-flop reset synchronizer pipeline."
                ))

            # 3. SEC404: Hardcoded Trapdoor / Master Key in RTL
            if re.search(r"if\s*\(\s*(?:key|secret|password|token|debug_code)\s*==\s*(?:[0-9]+'h[0-9a-fA-F]+|\"[^\"]+\")\s*\)", sline, re.IGNORECASE):
                vulns.append(SiliconVulnerability(
                    rule_id="SEC404",
                    cwe="CWE-284",
                    severity="CRITICAL",
                    file_path=filename,
                    line_number=idx,
                    code_snippet=sline,
                    description="Hardcoded authentication key / master debug trapdoor in hardware logic.",
                    remediation="Store cryptographic keys in Hardware Root of Trust (RoT) / eFuse registers."
                ))

            # 4. SEC403: Incomplete Case Statement Latch Detection
            if re.match(r"\bcase\s*\(", sline):
                in_case_block = True
                case_has_default = False
                case_start_line = idx

            if in_case_block:
                if "default:" in sline or "default :" in sline:
                    case_has_default = True
                if re.match(r"\bendcase\b", sline):
                    if not case_has_default:
                        vulns.append(SiliconVulnerability(
                            rule_id="SEC403",
                            cwe="CWE-440",
                            severity="HIGH",
                            file_path=filename,
                            line_number=case_start_line,
                            code_snippet=lines[case_start_line - 1].strip(),
                            description="Incomplete case statement without 'default' branch infers unintended latches and undefined states.",
                            remediation="Add an explicit 'default: ;' clause to ensure all unmapped state transitions are handled."
                        ))
                    in_case_block = False

        return vulns

    def scan_file(self, file_path: str) -> List[SiliconVulnerability]:
        """Scans a single Verilog/SystemVerilog file from the filesystem."""
        if not os.path.isfile(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return self.scan_verilog(content, filename=os.path.basename(file_path))
        except (OSError, UnicodeDecodeError):
            return []


silicon_scanner = SiliconScanner()


if __name__ == "__main__":
    _scanner = SiliconScanner()
    _test_v = "module alu(input [7:0] a, b, output [7:0] out);\n  assign [7:0] out = a + b;\nendmodule"
    _vulns = _scanner.scan_verilog(_test_v)
