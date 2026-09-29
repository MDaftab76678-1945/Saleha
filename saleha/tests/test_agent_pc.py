"""Unit tests for Saleha Agent Personal Computer (AgentPC), Sandbox & Blackbox.

Tests:
1. WorkspaceFS jailed filesystem and path traversal defense.
2. WorkspaceFS checkpoints and time-travel state rollback.
3. AgentSandbox hardware/AST security audit and execution containment.
4. AgentBlackbox SHA-256 cryptographic hash-chaining and tamper verification.
5. AgentPersonalComputer safe mutation with auto-rollback on test failure.
6. Hinton-Amodei verified artifact export gate.
7. BaseAgent and specialized agents automatic PC inheritance.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from saleha.agents.base_agent import BaseAgent
from saleha.agents.coder import CoderAgent
from saleha.core.sandbox.agent_pc import (
    AgentPersonalComputer,
    clear_agent_pc_registry,
    get_agent_pc,
    list_active_agent_pcs,
)


class TestAgentPCSubsystem(unittest.TestCase):
    def setUp(self) -> None:
        clear_agent_pc_registry()
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_pc_test_")
        self.workspace_path = Path(self.temp_dir) / "workspace"
        self.pc = AgentPersonalComputer(
            agent_role="test_coder",
            base_dir=self.workspace_path,
            memory_limit_mb=50,
            timeout_sec=3.0,
        )

    def tearDown(self) -> None:
        clear_agent_pc_registry()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_workspace_fs_jail_and_path_traversal(self) -> None:
        fs = self.pc.workspace

        # Valid file write & read inside workspace
        p = fs.write_file("nested/module.py", "x = 42\n")
        self.assertTrue(p.exists())
        self.assertEqual(fs.read_file("nested/module.py"), "x = 42\n")

        # Path traversal attack must be blocked
        with self.assertRaises(PermissionError):
            fs.write_file("../../../escaped.txt", "hacked")

        with self.assertRaises(PermissionError):
            fs.read_file("../../secret.txt")

    def test_workspace_fs_crud_and_scratchpad(self) -> None:
        fs = self.pc.workspace

        fs.write_file("file_a.py", "a = 1")
        fs.write_file("file_b.txt", "hello")
        self.assertTrue(fs.file_exists("file_a.py"))
        self.assertTrue(fs.file_exists("file_b.txt"))

        files = fs.list_files()
        self.assertIn("file_a.py", files)
        self.assertIn("file_b.txt", files)

        # Scratchpad
        fs.set_scratchpad("counter", 100)
        self.assertEqual(fs.get_scratchpad("counter"), 100)
        self.assertIsNone(fs.get_scratchpad("nonexistent"))

        # Delete
        self.assertTrue(fs.delete_file("file_b.txt"))
        self.assertFalse(fs.file_exists("file_b.txt"))

    def test_workspace_fs_checkpoints_and_restore(self) -> None:
        fs = self.pc.workspace

        # Step 1: Initial state
        fs.write_file("app.py", "version = 1.0")
        fs.set_scratchpad("state", "v1")
        chk1 = fs.create_checkpoint("v1")

        # Step 2: Mutate state
        fs.write_file("app.py", "version = 2.0")
        fs.write_file("extra.py", "junk = True")
        fs.set_scratchpad("state", "v2")

        self.assertEqual(fs.read_file("app.py"), "version = 2.0")
        self.assertTrue(fs.file_exists("extra.py"))

        # Step 3: Restore checkpoint v1
        restored = fs.restore_checkpoint(chk1.checkpoint_id)
        self.assertTrue(restored)
        self.assertEqual(fs.read_file("app.py"), "version = 1.0")
        self.assertFalse(fs.file_exists("extra.py"))
        self.assertEqual(fs.get_scratchpad("state"), "v1")

    def test_sandbox_run_python_success(self) -> None:
        code = "print('Hello from Agent PC Sandbox!')"
        res = self.pc.execute_code(code=code, filename="test_run.py")

        self.assertTrue(res.passed)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.output, "Hello from Agent PC Sandbox!")
        self.assertFalse(res.timed_out)

    def test_sandbox_ast_security_blocking(self) -> None:
        # Banned call: eval()
        dangerous_code = "eval('1 + 1')"
        res = self.pc.execute_code(code=dangerous_code, filename="eval_attack.py", verify_ast=True)

        self.assertFalse(res.passed)
        self.assertEqual(res.exit_code, 126)
        self.assertIn("SECURITY_AUDIT_VIOLATION", res.error)

    def test_sandbox_timeout_handling(self) -> None:
        infinite_loop = "import time\nwhile True:\n    time.sleep(0.1)"
        res = self.pc.execute_code(code=infinite_loop, filename="hang.py", timeout_sec=0.5)

        self.assertFalse(res.passed)
        self.assertTrue(res.timed_out)
        self.assertIn("TIMEOUT", res.error)

    def test_blackbox_cryptographic_hash_chain(self) -> None:
        bb = self.pc.blackbox

        # Record events
        bb.record("EVENT_A", "STAGE_1", {"key": "value_a"})
        bb.record("EVENT_B", "STAGE_2", {"key": "value_b"})
        bb.record("EVENT_C", "STAGE_3", {"key": "value_c"})

        # Chain must be intact
        integrity = bb.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["status"], "INTACT")
        self.assertGreaterEqual(integrity["total_events"], 4)  # Includes BOOT

        # Replay must match
        trace = bb.replay()
        self.assertGreaterEqual(len(trace), 4)

        # Artificially tamper with one line in log
        with open(bb.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        tampered = json.loads(lines[-1])
        tampered["payload"]["key"] = "hacked_value"
        lines[-1] = json.dumps(tampered) + "\n"

        with open(bb.log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        tampered_integrity = bb.verify_integrity()
        self.assertFalse(tampered_integrity["valid"])
        self.assertIn(tampered_integrity["status"], ("COMPROMISED", "HASH_MISMATCH"))

    def test_agent_pc_safe_mutate_success(self) -> None:
        # Mutate with valid code and passing test
        code = "def multiply(x, y):\n    return x * y\n"
        test = "from math_mod import multiply\nassert multiply(3, 4) == 12\n"

        ok, msg = self.pc.safe_mutate(
            filename="math_mod.py",
            new_code=code,
            test_code=test,
        )
        self.assertTrue(ok)
        self.assertIn("verified", msg)
        self.assertEqual(self.pc.workspace.read_file("math_mod.py"), code)

    def test_agent_pc_safe_mutate_rollback_on_failure(self) -> None:
        # Pre-populate working file
        initial_code = "def divide(x, y):\n    return x / y\n"
        self.pc.workspace.write_file("calc.py", initial_code)

        # Attempt bad mutation
        broken_code = "def divide(x, y):\n    return x + y\n"
        failing_test = "from calc import divide\nassert divide(10, 2) == 5\n"

        ok, msg = self.pc.safe_mutate(
            filename="calc.py",
            new_code=broken_code,
            test_code=failing_test,
        )

        self.assertFalse(ok)
        self.assertIn("rolled back", msg)
        # Verify file rolled back to initial code!
        self.assertEqual(self.pc.workspace.read_file("calc.py"), initial_code)

    def test_agent_pc_verified_artifact_export_gate(self) -> None:
        # 1. Unverified file export is blocked by Hinton-Amodei gate
        self.pc.workspace.write_file("unverified.py", "x = 100")
        export_dest = Path(self.temp_dir) / "exported" / "output.py"

        blocked = self.pc.export_verified_artifact("unverified.py", export_dest, require_green_run=True)
        self.assertFalse(blocked)
        self.assertFalse(export_dest.exists())

        # 2. Once verified by sandbox execution, export succeeds
        self.pc.execute_code(code="x = 100\nassert x == 100", filename="verified.py")
        exported = self.pc.export_verified_artifact("verified.py", export_dest, require_green_run=True)
        self.assertTrue(exported)
        self.assertTrue(export_dest.exists())
        self.assertEqual(export_dest.read_text(encoding="utf-8"), "x = 100\nassert x == 100")

    def test_export_gate_blocks_content_changed_after_green_run(self) -> None:
        self.pc.execute_code(code="x = 1\nassert x == 1", filename="art.py")
        self.pc.write_in_pc("art.py", "raise SystemExit('never executed')\n")
        export_dest = Path(self.temp_dir) / "exported" / "art.py"

        exported = self.pc.export_verified_artifact("art.py", export_dest, require_green_run=True)

        self.assertFalse(exported)
        self.assertFalse(export_dest.exists())
        blocked = self.pc.blackbox.get_events(limit=1, event_type="EXPORT_BLOCKED")
        self.assertIn("exact content", blocked[0]["payload"]["reason"])

    @unittest.skipUnless(sys.platform == "win32", "job-object memory limit is Windows-only")
    def test_sandbox_enforces_memory_limit(self) -> None:
        res = self.pc.execute_code(code="x = bytearray(300 * 1024 * 1024)", filename="mem.py")

        self.assertFalse(res.passed)
        self.assertTrue(res.memory_limit_hit)

    def test_sandbox_non_ascii_output_passes(self) -> None:
        res = self.pc.execute_code(code="print('\\u0101')", filename="uni.py")

        self.assertTrue(res.passed, res.error)
        self.assertEqual(res.output, "\u0101")

    def test_run_command_captures_non_ascii_output(self) -> None:
        res = self.pc.sandbox.run_command([sys.executable, "-c", "print('\\u0101')"])

        self.assertTrue(res.passed, res.error)
        self.assertEqual(res.output, "\u0101")

    def test_checkpoints_with_same_tag_do_not_collide(self) -> None:
        self.pc.write_in_pc("a.py", "v1")
        first = self.pc.checkpoint_pc("snap")
        self.pc.write_in_pc("a.py", "v2")
        second = self.pc.checkpoint_pc("snap")
        self.pc.write_in_pc("a.py", "v3")

        self.assertNotEqual(first, second)
        self.assertTrue(self.pc.restore_pc(first))
        self.assertEqual(self.pc.workspace.read_file("a.py"), "v1")
        self.assertTrue(self.pc.restore_pc("snap"))
        self.assertEqual(self.pc.workspace.read_file("a.py"), "v2")

    def test_get_agent_pc_rejects_path_traversal_role(self) -> None:
        from saleha.core import agent_pc as agent_pc_module

        root = agent_pc_module.DEFAULT_AGENT_PC_ROOT.resolve()
        for role in ("../..", "..\\..", "a/../../b", "C:/Windows"):
            pc = AgentPersonalComputer(agent_role=role)
            self.assertEqual(pc.workspace_root.resolve().parent, root, role)
        clear_agent_pc_registry()

    def test_base_agent_pc_integration(self) -> None:
        agent = BaseAgent(role="test_architect", model="mock", pc_workspace_dir=str(self.workspace_path))
        self.assertIsNotNone(agent.pc)

        # File write and read via agent helper
        agent.write_in_pc("notes.md", "# Architecture Draft")
        self.assertEqual(agent.read_from_pc("notes.md"), "# Architecture Draft")

        # Run code inside PC
        res = agent.run_in_pc("y = 10 * 10\nprint(y)")
        self.assertTrue(res.passed)
        self.assertEqual(res.output, "100")

        # Checkpoints via agent
        chk_id = agent.checkpoint_pc("draft_v1")
        self.assertTrue(chk_id.startswith("chk_"))

    def test_specialized_agents_inherit_pc(self) -> None:
        coder = CoderAgent(model="mock", pc_workspace_dir=str(self.workspace_path))
        self.assertIsNotNone(coder.pc)

        coder.write_in_pc("solution.py", "def solution(): return 42")
        self.assertEqual(coder.read_from_pc("solution.py"), "def solution(): return 42")

        summary = coder.pc.get_pc_summary()
        self.assertEqual(summary["agent_role"], "coder")
        self.assertIn("solution.py", summary["files"])

    def test_global_pc_registry_and_listing(self) -> None:
        pc1 = get_agent_pc("designer", base_dir=self.workspace_path / "designer")
        self.assertEqual(pc1.agent_role, "designer")

        active_pcs = list_active_agent_pcs()
        roles = [p["agent_role"] for p in active_pcs]
        self.assertIn("designer", roles)


if __name__ == "__main__":
    unittest.main()
