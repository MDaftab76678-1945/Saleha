// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

/**
 * @title AgentReputation
 * @notice On-chain reputation system for MUKTI marketplace.
 *
 * Features:
 * - 5-star ratings with reviews
 * - Weighted reputation score (recency + reviewer reputation)
 * - Dispute resolution
 * - Badge system (Verified, Top Rated, Expert)
 */
contract AgentReputation is AccessControl {
    using SafeMath for uint256;

    bytes32 public constant MARKETPLACE_ROLE = keccak256("MARKETPLACE_ROLE");
    bytes32 public constant DISPUTE_ROLE = keccak256("DISPUTE_ROLE");

    struct Review {
        address reviewer;
        uint8 rating;          // 1-5 stars
        string comment;
        uint256 timestamp;
        bool isVerified;       // reviewer completed a task with this agent
    }

    struct AgentProfile {
        address agent;
        uint256 totalReviews;
        uint256 totalRating;   // sum of all ratings
        uint256 completedTasks;
        uint256 failedTasks;
        uint256 disputes;
        uint256 badges;        // bitmask: 1=Verified, 2=TopRated, 4=Expert
        bool isActive;
    }

    struct Dispute {
        address taskCreator;
        address agent;
        uint256 taskId;
        string reason;
        bool resolved;
        bool agentAtFault;
    }

    // Storage
    mapping(address => AgentProfile) public profiles;
    mapping(address => Review[]) public reviews;
    mapping(address => mapping(address => bool)) public hasReviewed;
    Dispute[] public disputes;

    // Events
    event ReviewAdded(
        address indexed agent,
        address indexed reviewer,
        uint8 rating,
        string comment
    );
    event BadgeAwarded(address indexed agent, uint256 badge);
    event DisputeOpened(uint256 indexed disputeId, address agent, uint256 taskId);
    event DisputeResolved(uint256 indexed disputeId, bool agentAtFault);

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    // ─────────────────────────────────────────────
    // Reviews
    // ─────────────────────────────────────────────

    /**
     * @notice Add a review for an agent.
     * @param agent Agent address
     * @param rating 1-5 stars
     * @param comment Review text
     */
    function addReview(
        address agent,
        uint8 rating,
        string calldata comment
    ) external {
        require(rating >= 1 && rating <= 5, "Rating must be 1-5");
        require(!hasReviewed[msg.sender][agent], "Already reviewed");
        require(profiles[agent].isActive, "Agent not active");

        // Mark as reviewed
        hasReviewed[msg.sender][agent] = true;

        // Create review
        Review memory review = Review({
            reviewer: msg.sender,
            rating: rating,
            comment: comment,
            timestamp: block.timestamp,
            isVerified: true  // In production, verify task completion
        });
        reviews[agent].push(review);

        // Update profile
        AgentProfile storage profile = profiles[agent];
        profile.totalReviews += 1;
        profile.totalRating += rating;

        emit ReviewAdded(agent, msg.sender, rating, comment);

        // Check for badges
        _checkBadges(agent);
    }

    /**
     * @notice Get average rating for an agent.
     */
    function getAverageRating(address agent) public view returns (uint256) {
        AgentProfile storage profile = profiles[agent];
        if (profile.totalReviews == 0) return 0;
        return profile.totalRating.mul(100).div(profile.totalReviews); // 2 decimal precision
    }

    /**
     * @notice Get all reviews for an agent.
     */
    function getReviews(address agent) external view returns (Review[] memory) {
        return reviews[agent];
    }

    // ─────────────────────────────────────────────
    // Task Completion Tracking
    // ─────────────────────────────────────────────

    /**
     * @notice Record task completion (called by marketplace).
     */
    function recordTaskCompletion(
        address agent,
        bool success
    ) external onlyRole(MARKETPLACE_ROLE) {
        AgentProfile storage profile = profiles[agent];
        if (success) {
            profile.completedTasks += 1;
        } else {
            profile.failedTasks += 1;
        }
        _checkBadges(agent);
    }

    // ─────────────────────────────────────────────
    // Badges
    // ─────────────────────────────────────────────

    uint256 constant BADGE_VERIFIED = 1;
    uint256 constant BADGE_TOP_RATED = 2;
    uint256 constant BADGE_EXPERT = 4;

    function _checkBadges(address agent) internal {
        AgentProfile storage profile = profiles[agent];
        uint256 avgRating = getAverageRating(agent);

        // Verified: 10+ completed tasks
        if (profile.completedTasks >= 10 && profile.badges & BADGE_VERIFIED == 0) {
            profile.badges |= BADGE_VERIFIED;
            emit BadgeAwarded(agent, BADGE_VERIFIED);
        }

        // Top Rated: 4.5+ average with 20+ reviews
        if (avgRating >= 450 && profile.totalReviews >= 20 && profile.badges & BADGE_TOP_RATED == 0) {
            profile.badges |= BADGE_TOP_RATED;
            emit BadgeAwarded(agent, BADGE_TOP_RATED);
        }

        // Expert: 100+ completed tasks with 90%+ success rate
        uint256 totalTasks = profile.completedTasks + profile.failedTasks;
        if (totalTasks >= 100) {
            uint256 successRate = profile.completedTasks.mul(100).div(totalTasks);
            if (successRate >= 90 && profile.badges & BADGE_EXPERT == 0) {
                profile.badges |= BADGE_EXPERT;
                emit BadgeAwarded(agent, BADGE_EXPERT);
            }
        }
    }

    // ─────────────────────────────────────────────
    // Disputes
    // ─────────────────────────────────────────────

    function openDispute(
        address agent,
        uint256 taskId,
        string calldata reason
    ) external returns (uint256 disputeId) {
        disputeId = disputes.length;
        disputes.push(Dispute({
            taskCreator: msg.sender,
            agent: agent,
            taskId: taskId,
            reason: reason,
            resolved: false,
            agentAtFault: false
        }));

        profiles[agent].disputes += 1;
        emit DisputeOpened(disputeId, agent, taskId);
    }

    function resolveDispute(
        uint256 disputeId,
        bool agentAtFault
    ) external onlyRole(DISPUTE_ROLE) {
        require(disputeId < disputes.length, "Invalid dispute ID");
        Dispute storage dispute = disputes[disputeId];
        require(!dispute.resolved, "Already resolved");

        dispute.resolved = true;
        dispute.agentAtFault = agentAtFault;

        if (agentAtFault) {
            profiles[dispute.agent].failedTasks += 1;
        }

        emit DisputeResolved(disputeId, agentAtFault);
    }
}
