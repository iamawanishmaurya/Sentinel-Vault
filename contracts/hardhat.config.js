require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: { version: "0.8.24", settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "paris" } },
  networks: {
    hardhat: { chainId: 31337, mining: { auto: true, interval: 0 } },
    localhost: { url: process.env.HARDHAT_URL || "http://127.0.0.1:8545", chainId: 31337 },
  },
};
