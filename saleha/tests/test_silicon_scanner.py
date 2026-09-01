"""Unit tests for SiliconCopilot Hardware / Verilog SAST Scanner."""

import unittest
from saleha.core.silicon_scanner import SiliconScanner, silicon_scanner
from saleha.core.security_scanner import ASTSecurityScanner


class TestSiliconScanner(unittest.TestCase):
    """Test suite for Verilog and SystemVerilog security vulnerability checks."""

    def setUp(self):
        self.scanner = SiliconScanner()
        self.polyglot = ASTSecurityScanner()

    def test_detects_cwe_190_integer_overflow_in_verilog(self):
        verilog_code = """
        module adder(input [7:0] a, input [7:0] b, output [7:0] sum);
            assign [7:0] sum = a + b;
        endmodule
        """
        vulns = self.scanner.scan_verilog(verilog_code, filename="adder.v")
        self.assertTrue(any(v.rule_id == "SEC401" for v in vulns))
        self.assertTrue(any(v.cwe == "CWE-190" for v in vulns))

    def test_detects_async_reset_race_condition(self):
        verilog_code = """
        module dff(input clk, input async_rst, input d, output reg q);
            always @(posedge clk or posedge async_rst) begin
                if (async_rst) q <= 0;
                else q <= d;
            end
        endmodule
        """
        vulns = self.scanner.scan_verilog(verilog_code, filename="dff.v")
        self.assertTrue(any(v.rule_id == "SEC402" for v in vulns))

    def test_detects_hardcoded_trapdoor_backdoor_in_rtl(self):
        verilog_code = """
        module auth(input [31:0] key, output reg unlocked);
            always @(*) begin
                if (key == 32'hDEADBEEF) unlocked = 1;
                else unlocked = 0;
            end
        endmodule
        """
        vulns = self.scanner.scan_verilog(verilog_code, filename="auth.v")
        self.assertTrue(any(v.rule_id == "SEC404" for v in vulns))
        self.assertTrue(any(v.severity == "CRITICAL" for v in vulns))

    def test_detects_incomplete_case_statement_latch(self):
        verilog_code = """
        module mux(input [1:0] sel, input a, b, output reg out);
            always @(*) begin
                case (sel)
                    2'b00: out = a;
                    2'b01: out = b;
                endcase
            end
        endmodule
        """
        vulns = self.scanner.scan_verilog(verilog_code, filename="mux.v")
        self.assertTrue(any(v.rule_id == "SEC403" for v in vulns))

    def test_polyglot_scanner_routes_verilog_files(self):
        verilog_code = """
        module top(input [7:0] a, b, output [7:0] c);
            assign [7:0] c = a + b;
        endmodule
        """
        vulns = self.polyglot.scan_code(verilog_code, filename="top.sv")
        self.assertTrue(len(vulns) > 0)
        self.assertEqual(vulns[0].rule_id, "SEC401")


if __name__ == "__main__":
    unittest.main()
