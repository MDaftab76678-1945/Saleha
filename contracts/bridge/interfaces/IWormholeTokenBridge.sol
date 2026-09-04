// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IWormholeTokenBridge
 * @notice Interface for Wormhole Token Bridge contract
 * @dev Based on Wormhole's official token bridge interface
 */
interface IWormholeTokenBridge {
    struct Transfer {
        uint8 payloadID;
        uint256 amount;
        bytes32 tokenAddress;
        uint8 tokenChain;
        bytes32 to;
        uint16 toChain;
        uint256 fee;
    }

    function transferTokens(
        address token,
        uint256 amount,
        uint16 recipientChain,
        bytes32 recipient,
        uint256 arbiterFee,
        uint32 nonce
    ) external payable returns (uint64 sequence);

    function completeTransfer(bytes memory encodedVm) external;

    function wrappedAsset(uint16 tokenChainId, bytes32 tokenAddress)
        external
        view
        returns (address);

    function isWrappedAsset(address token) external view returns (bool);

    function bridgeContracts(uint16 chainId) external view returns (bytes32);

    function chainId() external view returns (uint16);
}
