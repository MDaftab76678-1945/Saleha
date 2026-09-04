// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title M2MEscrow
 * @dev Escrow contract for Machine-to-Machine transactions
 * Enables autonomous AI agents to securely transact with each other
 */
contract M2MEscrow {
    struct EscrowContract {
        address buyer;
        address seller;
        uint256 amount;
        EscrowStatus status;
        uint256 createdAt;
        uint256 completedAt;
        string serviceDescription;
    }

    enum EscrowStatus {
        Pending,
        Released,
        Refunded,
        Disputed
    }

    mapping(string => EscrowContract) public escrows;
    mapping(address => uint256) public agentReputation;
    
    address public owner;
    uint256 public platformFeeBps = 300; // 3% platform fee
    
    event EscrowCreated(string indexed escrowId, address buyer, address seller, uint256 amount);
    event EscrowReleased(string indexed escrowId, uint256 amount);
    event EscrowRefunded(string indexed escrowId, uint256 amount);
    event ReputationUpdated(address indexed agent, uint256 newReputation);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Create a new escrow contract between two AI agents
     * @param escrowId Unique identifier for the escrow
     * @param seller Address of the seller agent
     * @param serviceDescription Description of the service being purchased
     */
    function createEscrow(
        string memory escrowId,
        address seller,
        string memory serviceDescription
    ) external payable {
        require(msg.value > 0, "Amount must be > 0");
        require(seller != address(0), "Invalid seller");
        require(escrows[escrowId].createdAt == 0, "Escrow ID exists");

        escrows[escrowId] = EscrowContract({
            buyer: msg.sender,
            seller: seller,
            amount: msg.value,
            status: EscrowStatus.Pending,
            createdAt: block.timestamp,
            completedAt: 0,
            serviceDescription: serviceDescription
        });

        emit EscrowCreated(escrowId, msg.sender, seller, msg.value);
    }

    /**
     * @dev Release escrow funds to seller after service completion
     * Only the buyer can release funds
     * Platform fee is deducted automatically
     */
    function releaseEscrow(string memory escrowId) external {
        EscrowContract storage escrow = escrows[escrowId];
        require(escrow.buyer == msg.sender, "Only buyer can release");
        require(escrow.status == EscrowStatus.Pending, "Not pending");

        uint256 platformFee = (escrow.amount * platformFeeBps) / 10000;
        uint256 sellerAmount = escrow.amount - platformFee;

        escrow.status = EscrowStatus.Released;
        escrow.completedAt = block.timestamp;

        // Transfer to seller
        payable(escrow.seller).transfer(sellerAmount);
        // Transfer platform fee to owner
        payable(owner).transfer(platformFee);

        // Update seller reputation
        agentReputation[escrow.seller] += 10;
        emit ReputationUpdated(escrow.seller, agentReputation[escrow.seller]);

        emit EscrowReleased(escrowId, sellerAmount);
    }

    /**
     * @dev Refund escrow to buyer if service not delivered
     * Can be called by buyer after timeout or by owner in dispute
     */
    function refundEscrow(string memory escrowId) external {
        EscrowContract storage escrow = escrows[escrowId];
        require(
            msg.sender == escrow.buyer || msg.sender == owner,
            "Not authorized"
        );
        require(escrow.status == EscrowStatus.Pending, "Not pending");

        // Check timeout (24 hours)
        if (msg.sender == escrow.buyer) {
            require(block.timestamp > escrow.createdAt + 24 hours, "Timeout not reached");
        }

        escrow.status = EscrowStatus.Refunded;
        escrow.completedAt = block.timestamp;

        payable(escrow.buyer).transfer(escrow.amount);

        emit EscrowRefunded(escrowId, escrow.amount);
    }

    /**
     * @dev Update platform fee (only owner)
     */
    function updatePlatformFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 1000, "Fee too high"); // Max 10%
        platformFeeBps = newFeeBps;
    }

    /**
     * @dev Get escrow details
     */
    function getEscrow(string memory escrowId) external view returns (
        address buyer,
        address seller,
        uint256 amount,
        EscrowStatus status,
        string memory serviceDescription
    ) {
        EscrowContract storage escrow = escrows[escrowId];
        return (
            escrow.buyer,
            escrow.seller,
            escrow.amount,
            escrow.status,
            escrow.serviceDescription
        );
    }
}
