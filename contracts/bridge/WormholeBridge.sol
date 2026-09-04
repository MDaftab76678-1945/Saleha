// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "./interfaces/IWormholeTokenBridge.sol";

/**
 * @title WormholeBridge
 * @notice MUKTI's cross-chain bridge using Wormhole Token Bridge
 *
 * @dev Architecture:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │                    ETHEREUM SIDE                         │
 *   │                                                         │
 *   │  User locks MKT → WormholeBridge → Wormhole Core       │
 *   │       │                              │                  │
 *   │       │                              ▼                  │
 *   │       │                     Guardians sign (13/19)      │
 *   │       │                              │                  │
 *   │       │                              ▼                  │
 *   │       │                     VAA generated               │
 *   │       │                              │                  │
 *   └───────┼──────────────────────────────┼──────────────────┘
 *           │                              │
 *           ▼                              ▼
 *   ┌─────────────────────────────────────────────────────────┐
 *   │                    SOLANA SIDE                           │
 *   │                                                         │
 *   │  Relayer submits VAA → Anchor Program → Mint wMKT      │
 *   │                                                         │
 *   └─────────────────────────────────────────────────────────┘
 *
 * Security features:
 * - Pausable (emergency stop)
 * - ReentrancyGuard
 * - Role-based access (RELAYER_ROLE)
 * - Daily transfer limits
 * - Event emission for off-chain tracking
 */
contract WormholeBridge is ReentrancyGuard, AccessControl, Pausable {
    using SafeERC20 for IERC20;

    // ========================================================================
    // Constants & Roles
    // ========================================================================
    bytes32 public constant RELAYER_ROLE = keccak256("RELAYER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    // Wormhole chain IDs
    uint16 public constant ETH_CHAIN_ID = 2;
    uint16 public constant SOLANA_CHAIN_ID = 1;

    // ========================================================================
    // State
    // ========================================================================
    IWormholeTokenBridge public immutable wormholeTokenBridge;
    IERC20 public immutable mktToken;

    // Daily limits
    uint256 public dailyLimit;
    uint256 public amountTransferredToday;
    uint256 public lastResetTimestamp;

    // Transfer tracking
    uint256 public transferNonce;
    mapping(uint64 => bool) public processedTransfers;

    // Fee configuration (in basis points)
    uint256 public bridgeFeeBps = 10; // 0.1%
    uint256 public constant BPS_DENOMINATOR = 10_000;

    // Fee recipient
    address public feeRecipient;

    // ========================================================================
    // Events
    // ========================================================================
    event TokensLocked(
        uint256 indexed transferId,
        address indexed sender,
        uint256 amount,
        uint256 fee,
        uint16 destinationChain,
        bytes32 destinationAddress,
        uint64 wormholeSequence,
        uint256 timestamp
    );

    event TokensReleased(
        uint256 indexed transferId,
        address indexed recipient,
        uint256 amount,
        uint16 sourceChain,
        uint256 timestamp
    );

    event DailyLimitUpdated(uint256 oldLimit, uint256 newLimit);
    event BridgeFeeUpdated(uint256 oldFeeBps, uint256 newFeeBps);
    event EmergencyPaused(string reason);

    // ========================================================================
    // Errors
    // ========================================================================
    error DailyLimitExceeded(uint256 requested, uint256 remaining);
    error ZeroAmount();
    error InvalidDestinationChain(uint16 chain);
    error InvalidRecipient();
    error TransferAlreadyProcessed(uint64 sequence);
    error WormholeTransferFailed();

    // ========================================================================
    // Constructor
    // ========================================================================
    /**
     * @param _wormholeTokenBridge Wormhole Token Bridge contract address
     * @param _mktToken MKT token address on Ethereum
     * @param _dailyLimit Maximum daily transfer amount (in wei)
     * @param _feeRecipient Address to receive bridge fees
     */
    constructor(
        address _wormholeTokenBridge,
        address _mktToken,
        uint256 _dailyLimit,
        address _feeRecipient
    ) {
        require(_wormholeTokenBridge != address(0), "Invalid bridge address");
        require(_mktToken != address(0), "Invalid token address");
        require(_feeRecipient != address(0), "Invalid fee recipient");

        wormholeTokenBridge = IWormholeTokenBridge(_wormholeTokenBridge);
        mktToken = IERC20(_mktToken);
        dailyLimit = _dailyLimit;
        feeRecipient = _feeRecipient;
        lastResetTimestamp = block.timestamp;

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);
    }

    // ========================================================================
    // Core Functions
    // ========================================================================

    /**
     * @notice Lock MKT tokens and initiate cross-chain transfer to Solana
     * @param amount Amount of MKT to bridge (in wei)
     * @param solanaRecipient Base58-encoded Solana address (as bytes32)
     * @return transferId Unique identifier for this transfer
     */
    function bridgeToSolana(
        uint256 amount,
        bytes32 solanaRecipient
    )
        external
        nonReentrant
        whenNotPaused
        returns (uint256 transferId)
    {
        if (amount == 0) revert ZeroAmount();
        if (solanaRecipient == bytes32(0)) revert InvalidRecipient();

        _checkAndUpdateDailyLimit(amount);

        transferId = transferNonce++;

        // Calculate fee
        uint256 fee = (amount * bridgeFeeBps) / BPS_DENOMINATOR;
        uint256 netAmount = amount - fee;

        // Transfer tokens from sender
        mktToken.safeTransferFrom(msg.sender, address(this), amount);

        // Send fee to recipient
        if (fee > 0) {
            mktToken.safeTransfer(feeRecipient, fee);
        }

        // Approve Wormhole bridge to spend net amount
        mktToken.safeApprove(address(wormholeTokenBridge), netAmount);

        // Execute Wormhole transfer
        uint64 sequence = wormholeTokenBridge.transferTokens(
            address(mktToken),     // token
            netAmount,             // amount
            SOLANA_CHAIN_ID,       // recipient chain
            solanaRecipient,       // recipient address
            0,                     // arbiter fee
            uint32(transferId)     // nonce
        );

        emit TokensLocked(
            transferId,
            msg.sender,
            amount,
            fee,
            SOLANA_CHAIN_ID,
            solanaRecipient,
            sequence,
            block.timestamp
        );
    }

    /**
     * @notice Release MKT tokens from Wormhole VAA (called by relayer)
     * @param encodedVm Encoded Wormhole VAA (Verified Action Approval)
     */
    function releaseFromWormhole(bytes memory encodedVm)
        external
        nonReentrant
        whenNotPaused
        onlyRole(RELAYER_ROLE)
    {
        // Extract sequence from VAA for replay protection
        uint64 sequence = _extractSequenceFromVaa(encodedVm);

        if (processedTransfers[sequence]) {
            revert TransferAlreadyProcessed(sequence);
        }

        processedTransfers[sequence] = true;

        // Complete transfer via Wormhole
        wormholeTokenBridge.completeTransfer(encodedVm);

        // Note: The actual amount is determined by Wormhole
        // We emit event for tracking purposes
        emit TokensReleased(
            sequence,
            address(0), // Recipient is encoded in VAA
            0,          // Amount is encoded in VAA
            SOLANA_CHAIN_ID,
            block.timestamp
        );
    }

    /**
     * @notice Lock MKT and bridge to any Wormhole-supported chain
     * @param amount Amount of MKT (in wei)
     * @param destinationChain Wormhole chain ID
     * @param recipient Recipient address on destination chain
     */
    function bridgeToChain(
        uint256 amount,
        uint16 destinationChain,
        bytes32 recipient
    )
        external
        nonReentrant
        whenNotPaused
        returns (uint256 transferId)
    {
        if (amount == 0) revert ZeroAmount();
        if (destinationChain == ETH_CHAIN_ID) {
            revert InvalidDestinationChain(destinationChain);
        }
        if (recipient == bytes32(0)) revert InvalidRecipient();

        _checkAndUpdateDailyLimit(amount);

        transferId = transferNonce++;

        uint256 fee = (amount * bridgeFeeBps) / BPS_DENOMINATOR;
        uint256 netAmount = amount - fee;

        mktToken.safeTransferFrom(msg.sender, address(this), amount);

        if (fee > 0) {
            mktToken.safeTransfer(feeRecipient, fee);
        }

        mktToken.safeApprove(address(wormholeTokenBridge), netAmount);

        uint64 sequence = wormholeTokenBridge.transferTokens(
            address(mktToken),
            netAmount,
            destinationChain,
            recipient,
            0,
            uint32(transferId)
        );

        emit TokensLocked(
            transferId,
            msg.sender,
            amount,
            fee,
            destinationChain,
            recipient,
            sequence,
            block.timestamp
        );
    }

    // ========================================================================
    // Admin Functions
    // ========================================================================

    function setDailyLimit(uint256 newLimit) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit DailyLimitUpdated(dailyLimit, newLimit);
        dailyLimit = newLimit;
    }

    function setBridgeFee(uint256 newFeeBps) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newFeeBps <= 100, "Fee too high"); // Max 1%
        emit BridgeFeeUpdated(bridgeFeeBps, newFeeBps);
        bridgeFeeBps = newFeeBps;
    }

    function addRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _grantRole(RELAYER_ROLE, relayer);
    }

    function removeRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(RELAYER_ROLE, relayer);
    }

    function pause(string calldata reason) external onlyRole(PAUSER_ROLE) {
        _pause();
        emit EmergencyPaused(reason);
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ========================================================================
    // View Functions
    // ========================================================================

    function getRemainingDailyLimit() external view returns (uint256) {
        if (block.timestamp >= lastResetTimestamp + 24 hours) {
            return dailyLimit;
        }
        return dailyLimit > amountTransferredToday
            ? dailyLimit - amountTransferredToday
            : 0;
    }

    function isTransferProcessed(uint64 sequence) external view returns (bool) {
        return processedTransfers[sequence];
    }

    // ========================================================================
    // Internal Functions
    // ========================================================================

    function _checkAndUpdateDailyLimit(uint256 amount) internal {
        // Reset daily counter if 24 hours have passed
        if (block.timestamp >= lastResetTimestamp + 24 hours) {
            lastResetTimestamp = block.timestamp;
            amountTransferredToday = 0;
        }

        uint256 remaining = dailyLimit > amountTransferredToday
            ? dailyLimit - amountTransferredToday
            : 0;

        if (amount > remaining) {
            revert DailyLimitExceeded(amount, remaining);
        }

        amountTransferredToday += amount;
    }

    function _extractSequenceFromVaa(bytes memory encodedVm)
        internal
        pure
        returns (uint64)
    {
        // VAA format: version(1) + timestamp(4) + nonce(4) + ...
        // The sequence is embedded in the payload
        // Simplified extraction – in production, parse full VAA
        require(encodedVm.length > 9, "Invalid VAA length");

        uint64 sequence;
        assembly {
            sequence := shr(192, mload(add(encodedVm, 41)))
        }
        return sequence;
    }
}
