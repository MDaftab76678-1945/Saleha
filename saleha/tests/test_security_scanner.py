import unittest
import os
import tempfile
import json
from click.testing import CliRunner

from saleha.core.security_scanner import ASTSecurityScanner, SecurityVulnerability
from saleha.cli.commands import cli


class SecurityScannerTests(unittest.TestCase):
    def setUp(self):
        self.scanner = ASTSecurityScanner()

    def test_detect_sql_injection(self):
        code = '''
def get_user(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC001" for v in vulns))

    def test_detect_dangerous_eval_and_pickle(self):
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

    def test_detect_hardcoded_secrets(self):
        code = '''
API_KEY = "mock_sk_key_983748293478923487"
JWT_SECRET = "super_secret_jwt_token_key"
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC003" for v in vulns))

    def test_detect_subprocess_shell_true(self):
        code = '''
import subprocess
def run_cmd(user_cmd):
    subprocess.run(user_cmd, shell=True)
'''
        vulns = self.scanner.scan_code(code)
        self.assertTrue(any(v.rule_id == "SEC004" for v in vulns))

    def test_cli_audit_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "vulnerable.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write('eval("2 + 2")\n')

            res = CliRunner().invoke(cli, ["sast", tmpdir, "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertEqual(payload["high"], 1)
            self.assertEqual(payload["vulnerabilities"][0]["rule_id"], "SEC002")


if __name__ == "__main__":
    unittest.main()
