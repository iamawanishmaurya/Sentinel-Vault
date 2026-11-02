const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const Registry = await hre.ethers.getContractFactory("DocumentRegistry");
  const c = await Registry.deploy();
  await c.waitForDeployment();
  const address = await c.getAddress();
  const artifact = await hre.artifacts.readArtifact("DocumentRegistry");
  const out = {
    address,
    admin: deployer.address,
    chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
    abi: artifact.abi,
  };
  const dir = process.env.DEPLOY_OUT || path.join(__dirname, "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "DocumentRegistry.json"), JSON.stringify(out, null, 2));
  console.log("DocumentRegistry deployed to", address, "->", dir);
}
main().catch((e) => { console.error(e); process.exit(1); });
