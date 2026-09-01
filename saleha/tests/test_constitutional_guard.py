"""Unit tests for Constitutional AI Alignment Guard."""

import unittest
from saleha.core.constitutional_guard import ConstitutionalGuard, ConstitutionalAuditReport


class TestConstitutionalGuard(unittest.TestCase):
    """Test suite for ConstitutionalGuard safety and alignment verification."""

    def setUp(self):
        self.guard = ConstitutionalGuard()

    def test_clean_code_is_compliant(self):
        code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        rep = self.guard.audit_code(code, "add.py")
        self.assertIsInstance(rep, ConstitutionalAuditReport)
        self.assertTrue(rep.is_compliant)
        self.assertEqual(len(rep.violations), 0)

    def test_detects_destructive_os_command_violation(self):
        destructive_code = "import os\nos.system('rm -rf /')\n"
        rep = self.guard.audit_code(destructive_code, "wipe.py")
        self.assertFalse(rep.is_compliant)
        self.assertTrue(any(v.clause_id == "CONST_01" for v in rep.violations))

    def test_detects_unsafe_pickle_loads_violation(self):
        pickle_code = "import pickle\npickle.loads(user_payload)\n"
        rep = self.guard.audit_code(pickle_code, "deser.py")
        self.assertFalse(rep.is_compliant)
        self.assertTrue(any(v.clause_id == "CONST_02" for v in rep.violations))


if __name__ == "__main__":
    unittest.main()
