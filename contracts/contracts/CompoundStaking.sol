// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract CompoundStaking is ReentrancyGuard, Ownable {
    IERC20 public stakingToken;
    IERC20 public rewardToken;

    uint256 public constant COMPOUND_INTERVAL = 1 days;
    uint256 public constant MAX_APR = 10000; // 100% in basis points

    struct Stake {
        uint256 amount;
        uint256 rewardDebt;
        uint256 lastCompoundTime;
        uint256 totalCompounded;
    }

    mapping(address => Stake) public stakes;
    uint256 public totalStaked;
    uint256 public rewardRate; // rewards per second
    uint256 public lastRewardTime;
    uint256 public accRewardPerShare; // accumulated rewards per share (1e12 precision)

    bool public autoCompoundEnabled = true;

    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event Compounded(address indexed user, uint256 reward);
    event RewardRateUpdated(uint256 newRate);

    constructor(address _stakingToken, address _rewardToken, uint256 _rewardRate) {
        stakingToken = IERC20(_stakingToken);
        rewardToken = IERC20(_rewardToken);
        rewardRate = _rewardRate;
        lastRewardTime = block.timestamp;
    }

    modifier updateRewards() {
        _updateRewards();
        _;
    }

    function _updateRewards() internal {
        if (block.timestamp > lastRewardTime && totalStaked > 0) {
            uint256 elapsed = block.timestamp - lastRewardTime;
            uint256 reward = elapsed * rewardRate;
            accRewardPerShare += (reward * 1e12) / totalStaked;
            lastRewardTime = block.timestamp;
        }
    }

    function stake(uint256 amount) external nonReentrant updateRewards {
        require(amount > 0, "Cannot stake 0");

        Stake storage userStake = stakes[msg.sender];

        // Harvest pending rewards first
        if (userStake.amount > 0) {
            uint256 pending = pendingReward(msg.sender);
            if (pending > 0 && autoCompoundEnabled) {
                _compound(msg.sender, pending);
            }
        }

        userStake.amount += amount;
        userStake.rewardDebt = (userStake.amount * accRewardPerShare) / 1e12;
        totalStaked += amount;

        stakingToken.transferFrom(msg.sender, address(this), amount);

        emit Staked(msg.sender, amount);
    }

    function withdraw(uint256 amount) external nonReentrant updateRewards {
        Stake storage userStake = stakes[msg.sender];
        require(userStake.amount >= amount, "Insufficient stake");

        uint256 pending = pendingReward(msg.sender);
        if (pending > 0) {
            rewardToken.transfer(msg.sender, pending);
        }

        userStake.amount -= amount;
        userStake.rewardDebt = (userStake.amount * accRewardPerShare) / 1e12;
        totalStaked -= amount;

        stakingToken.transfer(msg.sender, amount);

        emit Withdrawn(msg.sender, amount);
    }

    function compound() external nonReentrant updateRewards {
        uint256 pending = pendingReward(msg.sender);
        require(pending > 0, "No rewards to compound");
        _compound(msg.sender, pending);
    }

    function _compound(address user, uint256 reward) internal {
        Stake storage userStake = stakes[user];

        // Convert reward to stake tokens (assuming 1:1 for simplicity)
        // In production, use oracle price
        uint256 stakeEquivalent = reward;

        userStake.amount += stakeEquivalent;
        userStake.totalCompounded += stakeEquivalent;
        userStake.lastCompoundTime = block.timestamp;
        userStake.rewardDebt = (userStake.amount * accRewardPerShare) / 1e12;
        totalStaked += stakeEquivalent;

        emit Compounded(user, stakeEquivalent);
    }

    function pendingReward(address user) public view returns (uint256) {
        Stake storage userStake = stakes[user];
        uint256 accReward = accRewardPerShare;

        if (block.timestamp > lastRewardTime && totalStaked > 0) {
            uint256 elapsed = block.timestamp - lastRewardTime;
            uint256 reward = elapsed * rewardRate;
            accReward += (reward * 1e12) / totalStaked;
        }

        return ((userStake.amount * accReward) / 1e12) - userStake.rewardDebt;
    }

    function estimateAPR() external view returns (uint256) {
        if (totalStaked == 0) return 0;
        uint256 annualRewards = rewardRate * 365 days;
        uint256 apr = (annualRewards * 10000) / totalStaked;
        return apr > MAX_APR ? MAX_APR : apr;
    }

    function setRewardRate(uint256 _newRate) external onlyOwner {
        _updateRewards();
        rewardRate = _newRate;
        emit RewardRateUpdated(_newRate);
    }

    function setAutoCompound(bool _enabled) external onlyOwner {
        autoCompoundEnabled = _enabled;
    }
}
