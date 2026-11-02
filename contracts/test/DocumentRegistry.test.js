const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DocumentRegistry", () => {
  let reg, admin, issuer, other;
  const h = ethers.sha256(ethers.toUtf8Bytes("certificate"));
  beforeEach(async () => {
    [admin, issuer, other] = await ethers.getSigners();
    reg = await (await ethers.getContractFactory("DocumentRegistry")).deploy();
    await reg.addIssuer(issuer.address, "Uni");
  });
  it("only authorised issuers register", async () => {
    await expect(reg.connect(other).registerDocument(h, "x")).to.be.revertedWithCustomError(reg, "NotIssuer");
    await reg.connect(issuer).registerDocument(h, "x");
    const d = await reg.getDocument(h);
    expect(d[0]).to.equal(true); expect(d[1]).to.equal(issuer.address); expect(d[6]).to.equal(true);
  });
  it("rejects duplicates", async () => {
    await reg.connect(issuer).registerDocument(h, "x");
    await expect(reg.connect(issuer).registerDocument(h, "x")).to.be.revertedWithCustomError(reg, "AlreadyRegistered");
  });
  it("revocation by issuer/admin only", async () => {
    await reg.connect(issuer).registerDocument(h, "x");
    await expect(reg.connect(other).revokeDocument(h, "r")).to.be.revertedWithCustomError(reg, "NotAuthorizedToRevoke");
    await reg.connect(issuer).revokeDocument(h, "fraud");
    expect((await reg.getDocument(h))[3]).to.be.gt(0);
    await expect(reg.revokeDocument(h, "r")).to.be.revertedWithCustomError(reg, "AlreadyRevoked");
  });
  it("only admin manages issuers", async () => {
    await expect(reg.connect(other).addIssuer(other.address, "x")).to.be.revertedWithCustomError(reg, "NotAdmin");
    await reg.removeIssuer(issuer.address);
    await expect(reg.connect(issuer).registerDocument(h, "x")).to.be.revertedWithCustomError(reg, "NotIssuer");
  });
});
