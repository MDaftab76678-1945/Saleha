// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title Bridge
 * @notice Cross-chain bridge for MKT token (Ethereum <-> Solana <-> XRP)
 * @dev Lock-and-mint pattern with multi-sig relayer verification
 *
 * Security features:
 * - Multi-sig relayer verification (m of n signatures required)
 * - Nonce-based replay protection
 * - Daily transfer limits
 * - Emergency pause capability
 * - Merkle proof verification for batch transfers
 */
contract Bridge is ReentrancyGuard, AccessControl {
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;

    // ========================================================================
    // Constants & Roles
    // ========================================================================
    bytes32 public constant RELAYER_ROLE = keccak256("RELAYER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint8 public constant CHAIN_ETHEREUM = 1;
    uint8 public constant CHAIN_SOLANA = 2;
    uint8 public constant CHAIN_XRP = 3;

    // ========================================================================
    // State Variables
    // ========================================================================
    IERC20 public immutable token;              // MKT token
    uint8 public immutable chainId;             // This chain's ID

    uint64 public nonce;                        // Prevents replay attacks
    uint256 public dailyLimit;                  // Max transfer per day
    uint256 public lastResetTime;               // Last daily limit reset
    uint256 public amountUsedToday;             // Amount used today

    uint8 public requiredSignatures;            // m of n multi-sig
    bool public paused;

    // Transfer tracking
    mapping(bytes32 => bool) public processedTransfers;  // transferId => processed
    mapping(address => uint256) public lockedBalances;   // user => locked amount

    // Relayer management
    address[] public relayers;
    mapping(address => bool) public isRelayer;

    // ========================================================================
    // Events
    // ========================================================================
    event TokensLocked(
        bytes32 indexed transferId,
        address indexed sender,
        uint256 amount,
        uint8 destinationChain,
        string destinationAddress,
        uint64 nonce,
        uint256 timestamp
    );

    event TokensReleased(
        bytes32 indexed transferId,
        address indexed recipient,
        uint256 amount,
        uint8 sourceChain
    );

    event TokensBurned(
        bytes32 indexed transferId,
        address indexed sender,
        uint256 amount,
        uint8 destinationChain,
        string destinationAddress
    );

    event TokensMinted(
        bytes32 indexed transferId,
        address indexed recipient,
        uint256 amount,
        uint8 sourceChain
    );

    event RelayerAdded(address indexed relayer);
    event RelayerRemoved(address indexed relayer);
    event DailyLimitUpdated(uint256 newLimit);
    event EmergencyPaused(bool paused);

    // ========================================================================
    // Errors
    // ========================================================================
    error BridgePaused();
    error DailyLimitExceeded();
    error InvalidDestinationChain();
    error TransferAlreadyProcessed();
    error InsufficientSignatures();
    error InvalidSignature();
    error ZeroAmount();
    error InvalidDestinationAddress();

    // ========================================================================
    // Constructor
    // ========================================================================
    constructor(
        address _token,
        uint8 _chainId,
        uint256 _dailyLimit,
        uint8 _requiredSignatures,
        address[] memory _relayers
    ) {
        require(_token != address(0), "Invalid token");
        require(_requiredSignatures > 0, "Need at least 1 signature");
        require(_relayers.length >= _requiredSignatures, "Not enough relayers");

        token = IERC20(_token);
        chainId = _chainId;
        dailyLimit = _dailyLimit;
        requiredSignatures = _requiredSignatures;
        lastResetTime = block.timestamp;

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);

        for (uint i = 0; i < _relayers.length; i++) {
            _addRelayer(_relayers[i]);
        }
    }

    // ========================================================================
    // Modifiers
    // ========================================================================
    modifier whenNotPaused() {
        if (paused) revert BridgePaused();
        _;
    }

    // ========================================================================
    // Core Functions - Lock & Mint Pattern
    // ========================================================================

    /**
     * @notice Lock MKT tokens to bridge to another chain
     * @param amount Amount of MKT to bridge
     * @param destinationChain Target chain ID (2=Solana, 3=XRP)
     * @param destinationAddress Recipient address on destination chain
     */
    function lockTokens(
        uint256 amount,
        uint8 destinationChain,
        string calldata destinationAddress
    ) external nonReentrant whenNotPaused returns (bytes32 transferId) {
        if (amount == 0) revert ZeroAmount();
        if (destinationChain == chainId) revert InvalidDestinationChain();
        if (bytes(destinationAddress).length == 0) revert InvalidDestinationAddress();

        _checkAndUpdateDailyLimit(amount);

        // Generate unique transfer ID
        transferId = keccak256(abi.encodePacked(
            chainId,
            destinationChain,
            msg.sender,
            destinationAddress,
            amount,
            nonce
        ));

        // Lock tokens in contract
        token.safeTransferFrom(msg.sender, address(this), amount);
        lockedBalances[msg.sender] += amount;

        emit TokensLocked(
            transferId,
            msg.sender,
            amount,
            destinationChain,
            destinationAddress,
            nonce,
            block.timestamp
        );

        nonce++;
    }

    /**
     * @notice Release locked MKT tokens (called by relayers with multi-sig)
     * @dev Called when tokens are burned on source chain
     */
    function releaseTokens(
        bytes32 transferId,
        address recipient,
        uint256 amount,
        uint8 sourceChain,
        bytes[] calldata signatures
    ) external nonReentrant whenNotPaused onlyRole(RELAYER_ROLE) {
        if (processedTransfers[transferId]) revert TransferAlreadyProcessed();

        _verifyMultiSig(transferId, recipient, amount, sourceChain, signatures);

        processedTransfers[transferId] = true;
        token.safeTransfer(recipient, amount);

        emit TokensReleased(transferId, recipient, amount, sourceChain);
    }

    /**
     * @notice Burn wrapped tokens to release original MKT on source chain
     * @dev For wrapped MKT (wMKT) coming back to Ethereum
     */
    function burnWrappedTokens(
        uint256 amount,
        uint8 destinationChain,
        string calldata destinationAddress
    ) external nonReentrant whenNotPaused returns (bytes32 transferId) {
        if (amount == 0) revert ZeroAmount();
        if (destinationChain == chainId) revert InvalidDestinationChain();

        transferId = keccak256(abi.encodePacked(
            chainId,
            destinationChain,
            msg.sender,
            destinationAddress,
            amount,
            nonce,
            "burn"
        ));

        // Burn tokens (transfer to dead address or use burn function)
        token.safeTransferFrom(msg.sender, address(0xdead), amount);

        emit TokensBurned(
            transferId,
            msg.sender,
            amount,
            destinationChain,
            destinationAddress
        );

        nonce++;
    }

    /**
     * @notice Mint wrapped MKT (called by relayers with multi-sig)
     * @dev Called when tokens are locked on source chain
     */
    function mintWrappedTokens(
        bytes32 transferId,
        address recipient,
        uint256 amount,
        uint8 sourceChain,
        bytes[] calldata signatures
    ) external nonReentrant whenNotPaused onlyRole(RELAYER_ROLE) {
        if (processedTransfers[transferId]) revert TransferAlreadyProcessed();

        _verifyMultiSig(transferId, recipient, amount, sourceChain, signatures);

        processedTransfers[transferId] = true;

        // For wrapped tokens, we release from locked pool
        // In production, this would mint new wrapped tokens
        token.safeTransfer(recipient, amount);

        emit TokensMinted(transferId, recipient, amount, sourceChain);
    }

    // ========================================================================
    // Batch Transfer with Merkle Proof
    // ========================================================================

    /**
     * @notice Process batch transfers using Merkle proof
     * @dev More gas-efficient for multiple transfers
     */
    function processBatchTransfers(
        bytes32 merkleRoot,
        bytes32[] calldata transferIds,
        address[] calldata recipients,
        uint256[] calldata amounts,
        bytes32[][] calldata proofs
    ) external onlyRole(RELAYER_ROLE) whenNotPaused {
        require(
            transferIds.length == recipients.length &&
            recipients.length == amounts.length &&
            amounts.length == proofs.length,
            "Length mismatch"
        );

        for (uint i = 0; i < transferIds.length; i++) {
            if (processedTransfers[transferIds[i]]) continue;

            bytes32 leaf = keccak256(abi.encodePacked(
                transferIds[i],
                recipients[i],
                amounts[i]
            ));

            if (MerkleProof.verify(proofs[i], merkleRoot, leaf)) {
                processedTransfers[transferIds[i]] = true;
                token.safeTransfer(recipients[i], amounts[i]);
                emit TokensReleased(transferIds[i], recipients[i], amounts[i], chainId);
            }
        }
    }

    // ========================================================================
    // Internal Functions
    // ========================================================================

    function _checkAndUpdateDailyLimit(uint256 amount) internal {
        // Reset daily limit if 24 hours passed
        if (block.timestamp >= lastResetTime + 24 hours) {
            lastResetTime = block.timestamp;
            amountUsedToday = 0;
        }

        if (amountUsedToday + amount > dailyLimit) {
            revert DailyLimitExceeded();
        }

        amountUsedToday += amount;
    }

    function _verifyMultiSig(
        bytes32 transferId,
        address recipient,
        uint256 amount,
        uint8 sourceChain,
        bytes[] calldata signatures
    ) internal view {
        if (signatures.length < requiredSignatures) {
            revert InsufficientSignatures();
        }

        bytes32 messageHash = keccak256(abi.encodePacked(
            transferId,
            recipient,
            amount,
            sourceChain,
            chainId,
            "release"
        ));
        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();

        address lastSigner = address(0);
        uint8 validSignatures = 0;

        for (uint i = 0; i < signatures.length; i++) {
            address signer = ethSignedHash.recover(signatures[i]);

            // Ensure signers are unique and sorted (prevent duplicates)
            if (signer <= lastSigner) revert InvalidSignature();
            if (!isRelayer[signer]) revert InvalidSignature();

            lastSigner = signer;
            validSignatures++;
        }

        if (validSignatures < requiredSignatures) {
            revert InsufficientSignatures();
        }
    }

    // ========================================================================
    // Admin Functions
    // ========================================================================

    function addRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _addRelayer(relayer);
    }

    function removeRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(isRelayer[relayer], "Not a relayer");
        isRelayer[relayer] = false;
        _revokeRole(RELAYER_ROLE, relayer);

        for (uint i = 0; i < relayers.length; i++) {
            if (relayers[i] == relayer) {
                relayers[i] = relayers[relayers.length - 1];
                relayers.pop();
                break;
            }
        }

        emit RelayerRemoved(relayer);
    }

    function _addRelayer(address relayer) internal {
        require(!isRelayer[relayer], "Already a relayer");
        isRelayer[relayer] = true;
        relayers.push(relayer);
        _grantRole(RELAYER_ROLE, relayer);
        emit RelayerAdded(relayer);
    }

    function setDailyLimit(uint256 newLimit) external onlyRole(DEFAULT_ADMIN_ROLE) {
        dailyLimit = newLimit;
        emit DailyLimitUpdated(newLimit);
    }

    function setRequiredSignatures(uint8 newRequired) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newRequired > 0 && newRequired <= relayers.length, "Invalid value");
        requiredSignatures = newRequired;
    }

    function setPaused(bool _paused) external onlyRole(PAUSER_ROLE) {
        paused = _paused;
        emit EmergencyPaused(_paused);
    }

    // ========================================================================
    // View Functions
    // ========================================================================

    function getRelayers() external view returns (address[] memory) {
        return relayers;
    }

    function getLockedAmount(address user) external view returns (uint256) {
        return lockedBalances[user];
    }

    function isTransferProcessed(bytes32 transferId) external view returns (bool) {
        return processedTransfers[transferId];
    }

    function getRemainingDailyLimit() external view returns (uint256) {
        if (block.timestamp >= lastResetTime + 24 hours) {
            return dailyLimit;
        }
        return dailyLimit > amountUsedToday ? dailyLimit - amountUsedToday : 0;
    }
}
