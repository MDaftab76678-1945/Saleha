const hre = require("hardhat");
const fs = require("fs");

async function main() {
  const networkName = hre.network.name;

  console.log(`Deploying Bridge on: ${networkName}`);

  // Load MKT token address for this chain
  const tokenDeployment = JSON.parse(
    fs.readFileSync(`deployments/token.${networkName}.json`, "utf-8")
  );

  // Deploy Bridge
  const Bridge = await hre.ethers.getContractFactory("AgentMarketplace");
  const bridge = await Bridge.deploy();
  await bridge.waitForDeployment();
  const bridgeAddress = await bridge.getAddress();

  console.log(`✅ Bridge deployed: ${bridgeAddress}`);

  // Save
  const deploymentInfo = {
    network: networkName,
    bridge: bridgeAddress,
    token: tokenDeployment.address,
    deployedAt: new Date().toISOString(),
  };

  fs.writeFileSync(
    `deployments/bridge.${networkName}.json`,
    JSON.stringify(deploymentInfo, null, 2)
  );
}

main().catch(console.error);
