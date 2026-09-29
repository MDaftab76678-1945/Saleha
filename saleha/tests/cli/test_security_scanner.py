import json
import os
import tempfile
import unittest

from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.core.verification.security_scanner import ASTSecurityScanner


class SecurityScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scanner = ASTSecurityScanner()

    def test_detect_sql_injection(self) -> None:
        code = '''
def get_user(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC001" for v in vulns))

    def test_detect_dangerous_eval_and_pickle(self) -> None:
        code = '''
import pickle
def load_data(raw):
    data = pickle.loads(raw)
    result = eval("data + 1")
    return result
'''
        vulns = self.scanner.scan_code(code)
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC002", rule_ids)

    def test_detect_hardcoded_secrets(self) -> None:
        code = '''
API_KEY = "mock_sk_key_983748293478923487"
JWT_SECRET = "super_secret_jwt_token_key"
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC003" for v in vulns))

    def test_detect_subprocess_shell_true(self) -> None:
        code = '''
import subprocess
def run_cmd(user_cmd):
    subprocess.run(user_cmd, shell=True)
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC004" for v in vulns))

    def test_detect_subprocess_shell_true_through_alias(self) -> None:
        # The check matched only the literal "subprocess." prefix, so an
        # aliased or from-imported call with shell=True was missed.
        for code in (
            'import subprocess as sp\nsp.run(cmd, shell=True)\n',
            'from subprocess import run\nrun(cmd, shell=True)\n',
        ):
            with self.subTest(code=code):
                vulns = self.scanner.scan_code(code)
                self.assertTrue(any(v.rule_id == "SEC004" for v in vulns))

    def test_noqa_suppresses_matching_rule_only(self) -> None:
        code = 'eval(x)  # noqa: SEC002\n'
        vulns = self.scanner.scan_code(code)
        self.assertEqual(vulns, [])

    def test_js_detects_eval_and_camelcase_secrets(self) -> None:
        """Real bug found while auditing: the secrets regex matched only
        snake_case names (api_key, jwt_secret), missing the camelCase
        convention (apiKey, jwtSecret) that is standard in real JS/TS code.
        Confirmed by direct probe before fixing: apiKey/jwtSecret/secretKey/
        authToken all scored 0 vulnerabilities pre-fix."""
        code = (
            'eval(userInput);\n'
            'const apiKey = "sk-1234567890abcdef";\n'
            'const jwtSecret = "abcdef1234567890xy";\n'
        )
        vulns = self.scanner.scan_code(code, filename="app.js")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC101", rule_ids)
        self.assertEqual(rule_ids.count("SEC003"), 2)

    def test_js_snake_case_secrets_still_detected(self) -> None:
        code = 'const api_key = "sk-1234567890abcdef";\n'
        vulns = self.scanner.scan_code(code, filename="app.js")
        self.assertTrue(any(v.rule_id == "SEC003" for v in vulns))

    def test_go_detects_sql_injection(self) -> None:
        code = 'db.Query(fmt.Sprintf("SELECT * FROM t WHERE id=%s", id))\n'
        vulns = self.scanner.scan_code(code, filename="main.go")
        self.assertTrue(any(v.rule_id == "SEC201" for v in vulns))

    def test_rust_detects_unsafe_block_and_secret(self) -> None:
        code = (
            'unsafe { let x = *ptr; }\n'
            'let secret = "abcdef1234567890xy";\n'
        )
        vulns = self.scanner.scan_code(code, filename="main.rs")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC301", rule_ids)
        self.assertIn("SEC003", rule_ids)

    def test_clean_code_reports_no_vulnerabilities(self) -> None:
        code = "def add(a, b):\n    return a + b\n"
        vulns = self.scanner.scan_code(code)
        self.assertEqual(vulns, [])

    def test_cli_audit_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "vulnerable.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write('eval("2 + 2")\n')

            res = CliRunner().invoke(cli, ["sast", tmpdir, "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertEqual(payload["high"], 1)
            self.assertEqual(payload["vulnerabilities"][0]["rule_id"], "SEC002")


    def test_detect_weak_hash_sec005(self) -> None:
        code = "import hashlib\ndigest = hashlib.md5(b'data').hexdigest()\n"
        vulns = self.scanner.scan_code(code)
        weak = [v for v in vulns if v.rule_id == "SEC005"]
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0].severity, "LOW")
        self.assertEqual(weak[0].line_number, 2)
        self.assertEqual(self.scanner.scan_code("import hashlib\nhashlib.sha256(b'x')\n"), [])

    def test_detect_child_process_exec_sec103(self) -> None:
        code = "const cp = require('child_process');\nchild_process.exec(userCmd);\n"
        vulns = self.scanner.scan_code(code, filename="tool.js")
        hits = [v for v in vulns if v.rule_id == "SEC103"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].severity, "MEDIUM")
        self.assertEqual(hits[0].line_number, 2)
        safe = "child_process.execFile('ls', ['-l']);\n"
        self.assertEqual([v for v in self.scanner.scan_code(safe, filename="tool.js")
                          if v.rule_id == "SEC103"], [])

    def test_every_emitted_rule_is_catalogued(self) -> None:
        from pathlib import Path

        from saleha.core.governance.controls import ControlContext, _catalog_control
        root = Path(__file__).resolve().parents[3]
        res = _catalog_control(ControlContext(root=root, baseline={}))
        self.assertEqual(res.status, "PASS", res.items)


if __name__ == "__main__":
    unittest.main()
