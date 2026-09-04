"""
Saleha Mukti Chain Bridge.

Real Python <-> Solidity bridge for the "hallucination insurance" flow described
in saleha/core/mukti_economy.py. Until this module existed, create_insurance_policy()
and settle_insurance_claim() were pure in-memory Python dataclass bookkeeping with
no connection whatsoever to contracts/M2MEscrow.sol -- despite the web_server.py
docstring advertising /api/mukti/insurance/create and /api/mukti/insurance/settle
as Web3 endpoints.

This module makes that connection real, using the `web3.py` package to talk to a
JSON-RPC endpoint (by default a local Hardhat node) and to invoke the actual
M2MEscrow contract:

    create_insurance_policy -> M2MEscrow.createEscrow(escrowId, seller, serviceDescription)
    settle_insurance_claim(is_ast_valid=True)  -> M2MEscrow.releaseEscrow(escrowId)   (agent paid)
    settle_insurance_claim(is_ast_valid=False) -> M2MEscrow.refundEscrow(escrowId)    (client refunded)

Design goals (this is a local dev/demo project, not production infra):
- No silent success. If web3 isn't installed, or no chain is reachable at the
  configured RPC URL, or no contract address is configured, callers get a clear
  ChainUnavailableError instead of a fabricated receipt.
- ABI resolution prefers a *real* Hardhat compilation artifact
  (contracts/artifacts/contracts/M2MEscrow.sol/M2MEscrow.json) when present, and
  falls back to a bundled hand-authored ABI mirror
  (saleha/server/web3_contracts/M2MEscrow.abi.json) shipped with the package so the
  bridge still works without ever running `npx hardhat compile`.
- Address handling: the mocked policy addresses used elsewhere in the demo
  ("0xClient", "0xAgent", ...) are not real Ethereum addresses. When a caller
  supplies something that isn't a valid checksummable address, the bridge falls
  back to Hardhat's well-known default dev accounts (accounts[0] as buyer/client,
  accounts[1] as seller/agent) so a local Hardhat node can still be exercised
  end-to-end without requiring the caller to manage real keys.

Environment variables:
    SALEHA_CHAIN_RPC_URL           JSON-RPC endpoint. Default: http://127.0.0.1:8545
    SALEHA_ESCROW_CONTRACT_ADDRESS Deployed M2MEscrow address. Required to send txs.
    SALEHA_CHAIN_STAKE_UNIT        "gwei" (default) or "ether" -- how `stake_amount`
                                    (a MUKTI float) is converted to a wei value sent
                                    as msg.value. gwei keeps demo stakes affordable
                                    against any funded account.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from web3 import Web3
    from web3.exceptions import Web3Exception

    _WEB3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when web3 extra isn't installed
    Web3 = None  # type: ignore
    Web3Exception = Exception  # type: ignore
    _WEB3_AVAILABLE = False

# Hardhat's deterministic default dev-account private keys / addresses
# (well-known, published in Hardhat's docs -- never use these outside local dev).
_HARDHAT_DEFAULT_ACCOUNT_INDEX_BUYER = 0
_HARDHAT_DEFAULT_ACCOUNT_INDEX_SELLER = 1

_DEFAULT_RPC_URL = "http://127.0.0.1:8545"
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # saleha/core/.. -> saleha/.. -> repo root
_BUNDLED_ABI_PATH = _THIS_DIR.parent / "server" / "web3_contracts" / "M2MEscrow.abi.json"
_HARDHAT_ARTIFACT_PATH = (
    _REPO_ROOT / "contracts" / "artifacts" / "contracts" / "M2MEscrow.sol" / "M2MEscrow.json"
)


class ChainUnavailableError(RuntimeError):
    """Raised when an on-chain call cannot be honestly attempted or completed.

    Never caught internally to fabricate a fake success -- callers (the HTTP
    handlers in saleha/server/web_server.py) are expected to surface this as an
    explicit error/status field rather than pretending the chain call worked.
    """


@dataclass
class ChainTxResult:
    escrow_id: str
    tx_hash: str
    block_number: Optional[int]
    contract_address: str
    rpc_url: str
    function: str
    raw_receipt_status: int
    extra: Dict[str, Any] = field(default_factory=dict)


def _load_abi() -> list:
    """Prefer a real Hardhat compilation artifact; fall back to the bundled ABI."""
    if _HARDHAT_ARTIFACT_PATH.exists():
        with open(_HARDHAT_ARTIFACT_PATH, "r", encoding="utf-8") as fh:
            artifact = json.load(fh)
        return artifact["abi"]

    if not _BUNDLED_ABI_PATH.exists():
        raise ChainUnavailableError(
            f"No M2MEscrow ABI found. Looked for a Hardhat build artifact at "
            f"{_HARDHAT_ARTIFACT_PATH} and a bundled fallback at {_BUNDLED_ABI_PATH}, "
            f"neither exists."
        )

    with open(_BUNDLED_ABI_PATH, "r", encoding="utf-8") as fh:
        bundled = json.load(fh)
    return bundled["abi"]


class MuktiChainBridge:
    """Thin, real web3.py bridge to the deployed M2MEscrow contract."""

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
    ):
        self.rpc_url = rpc_url or os.getenv("SALEHA_CHAIN_RPC_URL", _DEFAULT_RPC_URL)
        self.contract_address = contract_address or os.getenv("SALEHA_ESCROW_CONTRACT_ADDRESS")
        self.stake_unit = os.getenv("SALEHA_CHAIN_STAKE_UNIT", "gwei")
        self._w3 = None
        self._contract = None
        self._abi_error: Optional[str] = None

        if _WEB3_AVAILABLE:
            try:
                self._w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 5}))
            except Exception as exc:  # pragma: no cover - defensive
                self._abi_error = str(exc)

    # -- capability checks -------------------------------------------------

    def is_web3_installed(self) -> bool:
        return _WEB3_AVAILABLE

    def is_chain_reachable(self) -> bool:
        if not _WEB3_AVAILABLE or self._w3 is None:
            return False
        try:
            return bool(self._w3.is_connected())
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        """Diagnostic snapshot -- used by handlers to build honest error messages."""
        return {
            "web3_installed": self.is_web3_installed(),
            "rpc_url": self.rpc_url,
            "chain_reachable": self.is_chain_reachable(),
            "contract_address": self.contract_address,
        }

    # -- internals -----------------------------------------------------------

    def _require_ready(self) -> None:
        if not _WEB3_AVAILABLE:
            raise ChainUnavailableError(
                "The 'web3' package is not installed. Install it with `pip install web3` "
                "(or `pip install .[chain]`) to enable real on-chain calls."
            )
        if not self.is_chain_reachable():
            raise ChainUnavailableError(
                f"No JSON-RPC chain reachable at {self.rpc_url}. Start a local Hardhat node "
                f"with `npx hardhat node` (run from contracts/), deploy M2MEscrow to it, "
                f"and set SALEHA_ESCROW_CONTRACT_ADDRESS to the deployed address."
            )
        if not self.contract_address:
            raise ChainUnavailableError(
                "SALEHA_ESCROW_CONTRACT_ADDRESS is not set. Deploy contracts/M2MEscrow.sol "
                "to your local chain and set that env var to the resulting address."
            )

    def _get_contract(self):
        if self._contract is not None:
            return self._contract
        abi = _load_abi()
        checksum_addr = self._w3.to_checksum_address(self.contract_address)
        self._contract = self._w3.eth.contract(address=checksum_addr, abi=abi)
        return self._contract

    def _resolve_address(self, addr: Optional[str], default_account_index: int) -> str:
        """Return a usable checksum address, falling back to a Hardhat dev account.

        The rest of the demo (saleha/core/mukti_economy.py, web_server.py payloads)
        uses placeholder strings like "0xClient" / "0xAgent" that are not valid
        Ethereum addresses. Rather than fail outright on those placeholders, fall
        back to one of Hardhat's well-known default unlocked dev accounts so the
        on-chain path can still be exercised locally.
        """
        if addr and self._w3.is_address(addr):
            return self._w3.to_checksum_address(addr)
        accounts = self._w3.eth.accounts
        if len(accounts) > default_account_index:
            return accounts[default_account_index]
        raise ChainUnavailableError(
            f"No usable address for '{addr}' and the connected node exposes no "
            f"unlocked accounts to fall back to."
        )

    def _stake_to_wei(self, stake_amount: float) -> int:
        if self.stake_unit == "ether":
            return self._w3.to_wei(stake_amount, "ether")
        return self._w3.to_wei(stake_amount, "gwei")

    # -- public API ------------------------------------------------------

    def create_escrow(
        self,
        escrow_id: str,
        client_address: str,
        agent_address: str,
        code_hash: str,
        stake_amount: float,
    ) -> ChainTxResult:
        """Calls M2MEscrow.createEscrow(escrowId, seller, serviceDescription)."""
        self._require_ready()
        contract = self._get_contract()

        buyer = self._resolve_address(client_address, _HARDHAT_DEFAULT_ACCOUNT_INDEX_BUYER)
        seller = self._resolve_address(agent_address, _HARDHAT_DEFAULT_ACCOUNT_INDEX_SELLER)
        value_wei = self._stake_to_wei(stake_amount)

        try:
            tx_hash = contract.functions.createEscrow(
                escrow_id, seller, code_hash
            ).transact({"from": buyer, "value": value_wei})
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        except Web3Exception as exc:
            raise ChainUnavailableError(f"createEscrow transaction failed: {exc}") from exc
        except Exception as exc:
            raise ChainUnavailableError(f"createEscrow transaction failed: {exc}") from exc

        return ChainTxResult(
            escrow_id=escrow_id,
            tx_hash=tx_hash.hex(),
            block_number=receipt.get("blockNumber"),
            contract_address=self.contract_address,
            rpc_url=self.rpc_url,
            function="createEscrow",
            raw_receipt_status=receipt.get("status", 0),
            extra={"buyer": buyer, "seller": seller, "value_wei": value_wei},
        )

    def settle_escrow(
        self,
        escrow_id: str,
        is_ast_valid: bool,
        client_address: Optional[str] = None,
    ) -> ChainTxResult:
        """Valid code -> releaseEscrow (pays agent/seller).
        Invalid/hallucinated code -> refundEscrow (refunds client/buyer).
        """
        self._require_ready()
        contract = self._get_contract()
        buyer = self._resolve_address(client_address, _HARDHAT_DEFAULT_ACCOUNT_INDEX_BUYER)
        fn_name = "releaseEscrow" if is_ast_valid else "refundEscrow"

        try:
            fn = getattr(contract.functions, fn_name)
            tx_hash = fn(escrow_id).transact({"from": buyer})
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        except Web3Exception as exc:
            raise ChainUnavailableError(f"{fn_name} transaction failed: {exc}") from exc
        except Exception as exc:
            raise ChainUnavailableError(f"{fn_name} transaction failed: {exc}") from exc

        return ChainTxResult(
            escrow_id=escrow_id,
            tx_hash=tx_hash.hex(),
            block_number=receipt.get("blockNumber"),
            contract_address=self.contract_address,
            rpc_url=self.rpc_url,
            function=fn_name,
            raw_receipt_status=receipt.get("status", 0),
            extra={"buyer": buyer},
        )


mukti_chain_bridge = MuktiChainBridge()
