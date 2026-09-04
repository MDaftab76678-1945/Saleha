const hre = require("hardhat");
const fs = require("fs");

// हर chain के लिए token address (पहले से deployed MKT token)
const CHAIN_CONFIG = {
  ethereum: {
    tokenAddress: process.env.ETH_MKT_TOKEN,
    treasuryAddress: process.env.ETH_TREASURY,
    collectorRole: process.env.ETH_COLLECTOR_ADDRESS,
    governorRole: process.env.ETH_GOVERNOR_ADDRESS,
    explorer: "https://etherscan.io",
  },
  bsc: {
    tokenAddress: process.env.BSC_MKT_TOKEN,
    treasuryAddress: process.env.BSC_TREASURY,
    collectorRole: process.env.BSC_COLLECTOR_ADDRESS,
    governorRole: process.env.BSC_GOVERNOR_ADDRESS,
    explorer: "https://bscscan.com",
  },
  polygon: {
    tokenAddress: process.env.POLYGON_MKT_TOKEN,
    treasuryAddress: process.env.POLYGON_TREASURY,
    collectorRole: process.env.POLYGON_COLLECTOR_ADDRESS,
    governorRole: process.env.POLYGON_GOVERNOR_ADDRESS,
    explorer: "https://polygonscan.com",
  },
};

async function main() {
  const networkName = hre.network.name;
  const config = CHAIN_CONFIG[networkName];

  if (!config) {
    throw new Error(`No config for network: ${networkName}`);
  }

  console.log(`
============================================`);
  console.log(`Deploying FeeCollector on: ${networkName}`);
  console.log(`============================================
`);

  // 1. Deploy Treasury first
  console.log("1️⃣ Deploying Treasury...");
  const Treasury = await hre.ethers.getContractFactory("Treasury");
  const treasury = await Treasury.deploy(config.tokenAddress);
  await treasury.waitForDeployment();
  const treasuryAddress = await treasury.getAddress();
  console.log(`   ✅ Treasury: ${treasuryAddress}`);

  // 2. Deploy FeeCollector
  console.log("2️⃣ Deploying FeeCollector...");
  const FeeCollector = await hre.ethers.getContractFactory("FeeCollector");
  const feeCollector = await FeeCollector.deploy(config.tokenAddress);
  await feeCollector.waitForDeployment();
  const feeCollectorAddress = await feeCollector.getAddress();
  console.log(`   ✅ FeeCollector: ${feeCollectorAddress}`);

  // 3. Grant COLLECTOR_ROLE (bridge/agent contracts जो fees collect करेंगे)
  console.log("3️⃣ Granting COLLECTOR_ROLE...");
  const COLLECTOR_ROLE = await feeCollector.COLLECTOR_ROLE();
  await feeCollector.grantRole(COLLECTOR_ROLE, config.collectorRole);
  console.log(`   ✅ COLLECTOR_ROLE granted to: ${config.collectorRole}`);

  // 4. Grant GOVERNOR_ROLE (DAO जो fund distribution decide करेगा)
  console.log("4️⃣ Granting GOVERNOR_ROLE...");
  const GOVERNOR_ROLE = await feeCollector.GOVERNOR_ROLE();
  await feeCollector.grantRole(GOVERNOR_ROLE, config.governorRole);
  console.log(`   ✅ GOVERNOR_ROLE granted to: ${config.governorRole}`);

  // 5. Verify roles
  console.log("5️⃣ Verifying roles...");
  const hasCollector = await feeCollector.hasRole(COLLECTOR_ROLE, config.collectorRole);
  const hasGovernor = await feeCollector.hasRole(GOVERNOR_ROLE, config.governorRole);
  console.log(`   Collector role: ${hasCollector}`);
  console.log(`   Governor role: ${hasGovernor}`);

  // 6. Save deployment artifacts
  const deploymentInfo = {
    network: networkName,
    chainId: hre.network.config.chainId,
    treasury: treasuryAddress,
    feeCollector: feeCollectorAddress,
    token: config.tokenAddress,
    roles: {
      collector: config.collectorRole,
      governor: config.governorRole,
    },
    deployedAt: new Date().toISOString(),
  };

  const filename = `deployments/feeCollector.${networkName}.json`;
  fs.mkdirSync("deployments", { recursive: true });
  fs.writeFileSync(filename, JSON.stringify(deploymentInfo, null, 2));
  console.log(`
💾 Saved: ${filename}`);

  console.log(`
🔍 Verify on: ${config.explorer}/address/${feeCollectorAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
