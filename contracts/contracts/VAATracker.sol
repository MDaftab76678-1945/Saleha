// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";

contract VAATracker is Ownable {
    enum VAAStatus { Pending, Verifying, Verified, Rejected, Expired }

    struct VAA {
        bytes32 vaaHash;
        bytes32 payloadHash;
        address submitter;
        uint256 submittedAt;
        uint256 verifiedAt;
        VAAStatus status;
        uint8 guardianSignatures;
        uint8 requiredSignatures;
        bytes32[] guardianAddresses;
    }

    mapping(bytes32 => VAA) public vaas;
    bytes32[] public vaaList;

    uint8 public constant REQUIRED_GUARDIANS = 13; // 13 of 19
    uint256 public constant VAA_EXPIRY = 24 hours;

    event VAASubmitted(bytes32 indexed vaaHash, address indexed submitter);
    event VAAVerified(bytes32 indexed vaaHash);
    event VAARejected(bytes32 indexed vaaHash, string reason);

    function submitVAA(
        bytes32 vaaHash,
        bytes32 payloadHash,
        bytes32[] calldata guardians
    ) external {
        require(vaas[vaaHash].submittedAt == 0, "VAA already submitted");
        require(guardians.length >= REQUIRED_GUARDIANS, "Insufficient signatures");

        vaas[vaaHash] = VAA({
            vaaHash: vaaHash,
            payloadHash: payloadHash,
            submitter: msg.sender,
            submittedAt: block.timestamp,
            verifiedAt: 0,
            status: VAAStatus.Verifying,
            guardianSignatures: uint8(guardians.length),
            requiredSignatures: REQUIRED_GUARDIANS,
            guardianAddresses: guardians
        });

        vaaList.push(vaaHash);

        emit VAASubmitted(vaaHash, msg.sender);
    }

    function verifyVAA(bytes32 vaaHash) external onlyOwner {
        VAA storage vaa = vaas[vaaHash];
        require(vaa.submittedAt > 0, "VAA not found");
        require(vaa.status == VAAStatus.Verifying, "Invalid status");

        // Check expiry
        if (block.timestamp > vaa.submittedAt + VAA_EXPIRY) {
            vaa.status = VAAStatus.Expired;
            emit VAARejected(vaaHash, "Expired");
            return;
        }

        vaa.status = VAAStatus.Verified;
        vaa.verifiedAt = block.timestamp;

        emit VAAVerified(vaaHash);
    }

    function rejectVAA(bytes32 vaaHash, string calldata reason) external onlyOwner {
        VAA storage vaa = vaas[vaaHash];
        require(vaa.submittedAt > 0, "VAA not found");

        vaa.status = VAAStatus.Rejected;
        emit VAARejected(vaaHash, reason);
    }

    function getVAA(bytes32 vaaHash) external view returns (VAA memory) {
        return vaas[vaaHash];
    }

    function getVAAStatus(bytes32 vaaHash) external view returns (VAAStatus) {
        return vaas[vaaHash].status;
    }

    function getTotalVAAs() external view returns (uint256) {
        return vaaList.length;
    }
}
