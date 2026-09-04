#!/bin/bash
set -e

echo "🚀 Deploying MUKTI on all EVM chains..."

# Testnets first (safe testing)
echo "
📍 Testnets:"
npx hardhat run scripts/deployFeeCollectorMultiChain.js --network sepolia
npx hardhat run scripts/deployFeeCollectorMultiChain.js --network bscTestnet
npx hardhat run scripts/deployFeeCollectorMultiChain.js --network mumbai

# Verify testnet deployments
echo "
✅ Verifying testnets..."
# Add verification commands here

# Mainnets (after testnet success)
read -p "Testnets successful? Deploy mainnets? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "
📍 Mainnets:"
  npx hardhat run scripts/deployFeeCollectorMultiChain.js --network ethereum
  npx hardhat run scripts/deployFeeCollectorMultiChain.js --network bsc
  npx hardhat run scripts/deployFeeCollectorMultiChain.js --network polygon
fi

echo "
🎉 All deployments complete!"
