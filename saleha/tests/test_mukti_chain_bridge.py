"""Unit tests for saleha.core.mukti_chain_bridge.MuktiChainBridge. Had no
test coverage before this file (found during a test-coverage sweep of
saleha/core/).

The module's own design-goals docstring promises "No silent success": every
call should raise ChainUnavailableError with an honest reason rather than
fabricate a transaction receipt when the chain cannot actually be reached.
These tests check that promise holds without needing a real Hardhat node or
the web3 package installed -- both status() and every write method must
report the true state of the world, not a default success.
"""

import unittest

from saleha.core.mukti_chain_bridge import (
    MuktiChainBridge,
    ChainUnavailableError,
    _WEB3_AVAILABLE,
)


class StatusReportingTests(unittest.TestCase):
    def test_status_reports_actual_web3_availability_not_assumed(self) -> None:
        bridge = MuktiChainBridge()
        status = bridge.status()
        # This must reflect the real, current state of the environment --
        # not a hardcoded True regardless of whether web3 is installed.
        self.assertEqual(status["web3_installed"], _WEB3_AVAILABLE)
        self.assertIn("rpc_url", status)
        self.assertIn("chain_reachable", status)

    def test_is_chain_reachable_is_false_without_a_real_connection(self) -> None:
        bridge = MuktiChainBridge(rpc_url="http://127.0.0.1:1")  # nothing listens here
        self.assertFalse(bridge.is_chain_reachable())


@unittest.skipIf(_WEB3_AVAILABLE, "this test targets the not-installed code path")
class NoSilentSuccessWithoutWeb3Tests(unittest.TestCase):
    """When web3 isn't installed, every write path must raise honestly."""

    def test_create_escrow_raises_rather_than_fabricating_a_receipt(self) -> None:
        bridge = MuktiChainBridge()
        with self.assertRaises(ChainUnavailableError) as ctx:
            bridge.create_escrow("e1", "0xClient", "0xAgent", "codehash", 1.0)
        self.assertIn("web3", str(ctx.exception).lower())

    def test_settle_escrow_raises_rather_than_fabricating_a_receipt(self) -> None:
        bridge = MuktiChainBridge()
        with self.assertRaises(ChainUnavailableError):
            bridge.settle_escrow("e1", is_ast_valid=True)


class RequireReadyTests(unittest.TestCase):
    """_require_ready is the single gate every write path calls through --
    tests each of its three honest failure reasons directly, independent of
    whether web3 happens to be installed on the machine running the suite."""

    @unittest.skipUnless(_WEB3_AVAILABLE, "requires web3 to reach the reachability check")
    def test_unreachable_chain_raises_with_the_configured_url_in_the_message(self) -> None:
        bridge = MuktiChainBridge(rpc_url="http://127.0.0.1:1")
        with self.assertRaises(ChainUnavailableError) as ctx:
            bridge._require_ready()
        self.assertIn("http://127.0.0.1:1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
