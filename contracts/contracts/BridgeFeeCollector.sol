// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title BridgeFeeCollector
 * @notice Collects bridge transfer fees and distributes revenue.
 *
 * Fee model:
 *   - Flat % on each cross-chain transfer (default 10 bps = 0.1%)
 *   - Fees accumulate per source-chain
 *   - Periodic sweep to treasury / staking rewards
 */
contract BridgeFeeCollector is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant BRIDGE_ROLE = keccak256("BRIDGE_ROLE");
    bytes32 public constant SWEEPER_ROLE = keccak256("SWEEPER_ROLE");

    uint256 public constant BPS_DENOMINATOR = 10_000;

    // Fee rate in basis points (default 0.1%)
    uint256 public feeBps = 10;

    // Token being bridged
    IERC20 public immutable token;

    // Accumulated fees per source chain (wormhole chainId)
    mapping(uint16 => uint256) public feesByChain;

    // Total lifetime fees
    uint256 public totalFees;

    // Where swept fees go
    address public treasury;

    // Distribution split (bps, must sum to 10000)
    uint256 public treasuryBps = 7000;   // 70% treasury
    uint256 public stakingBps = 3000;    // 30% staking rewards
    address public stakingRewards;

    event FeeCollected(
        uint16 indexed sourceChain,
        address indexed payer,
        uint256 amount,
        uint256 fee
    );
    event FeesSwept(uint256 toTreasury, uint256 toStaking);
    event FeeRateUpdated(uint256 oldBps, uint256 newBps);

    error InsufficientFee();
    error InvalidSplit();

    constructor(address _token, address _treasury, address _stakingRewards) {
        token = IERC20(_token);
        treasury = _treasury;
        stakingRewards = _stakingRewards;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    /**
     * @notice Called by the bridge when a transfer is initiated.
     * @dev Pulls the fee from the payer. Bridge must be approved.
     */
    function collectFee(
        uint16 sourceChain,
        address payer,
        uint256 transferAmount
    ) external onlyRole(BRIDGE_ROLE) returns (uint256 fee) {
        fee = (transferAmount * feeBps) / BPS_DENOMINATOR;
        if (fee > 0) {
            token.safeTransferFrom(payer, address(this), fee);
            feesByChain[sourceChain] += fee;
            totalFees += fee;
        }
        emit FeeCollected(sourceChain, payer, transferAmount, fee);
    }

    /**
     * @notice Sweep accumulated fees to treasury + staking.
     */
    function sweep() external onlyRole(SWEEPER_ROLE) nonReentrant {
        uint256 balance = token.balanceOf(address(this));
        if (balance == 0) return;

        uint256 toTreasury = (balance * treasuryBps) / BPS_DENOMINATOR;
        uint256 toStaking = balance - toTreasury;

        // Reset per-chain accounting
        for (uint16 i = 0; i < 30; i++) {
            feesByChain[i] = 0;
        }

        token.safeTransfer(treasury, toTreasury);
        token.safeTransfer(stakingRewards, toStaking);

        emit FeesSwept(toTreasury, toStaking);
    }

    // ---- Admin ----
    function setFeeRate(uint256 _bps) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_bps <= 100, "Fee too high"); // max 1%
        emit FeeRateUpdated(feeBps, _bps);
        feeBps = _bps;
    }

    function setSplit(uint256 _treasuryBps, uint256 _stakingBps)
        external onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (_treasuryBps + _stakingBps != BPS_DENOMINATOR) revert InvalidSplit();
        treasuryBps = _treasuryBps;
        stakingBps = _stakingBps;
    }

    // ---- Views ----
    function quoteFee(uint256 transferAmount) external view returns (uint256) {
        return (transferAmount * feeBps) / BPS_DENOMINATOR;
    }
}
