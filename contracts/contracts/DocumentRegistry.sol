// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title DocumentRegistry
/// @notice Registry of SHA-256 document fingerprints issued by authorised issuers.
contract DocumentRegistry {
    struct Record {
        address issuer;
        uint64 registeredAt;
        uint64 revokedAt;      // 0 when not revoked
        string metadataURI;    // e.g. issuer reference / IPFS CID (never plaintext content)
        string revocationReason;
        bool exists;
    }

    address public admin;
    mapping(address => bool) public isIssuer;
    mapping(address => string) public issuerName;
    mapping(bytes32 => Record) private records;
    uint256 public documentCount;

    event IssuerAdded(address indexed issuer, string name);
    event IssuerRemoved(address indexed issuer);
    event DocumentRegistered(bytes32 indexed docHash, address indexed issuer, uint64 timestamp, string metadataURI);
    event DocumentRevoked(bytes32 indexed docHash, address indexed revoker, uint64 timestamp, string reason);
    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);

    error NotAdmin();
    error NotIssuer();
    error AlreadyRegistered();
    error NotFound();
    error AlreadyRevoked();
    error NotAuthorizedToRevoke();
    error ZeroAddress();

    modifier onlyAdmin() { if (msg.sender != admin) revert NotAdmin(); _; }
    modifier onlyIssuer() { if (!isIssuer[msg.sender]) revert NotIssuer(); _; }

    constructor() { admin = msg.sender; emit AdminTransferred(address(0), msg.sender); }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroAddress();
        emit AdminTransferred(admin, newAdmin);
        admin = newAdmin;
    }

    function addIssuer(address issuer, string calldata name) external onlyAdmin {
        if (issuer == address(0)) revert ZeroAddress();
        isIssuer[issuer] = true;
        issuerName[issuer] = name;
        emit IssuerAdded(issuer, name);
    }

    function removeIssuer(address issuer) external onlyAdmin {
        isIssuer[issuer] = false;
        emit IssuerRemoved(issuer);
    }

    function registerDocument(bytes32 docHash, string calldata metadataURI) external onlyIssuer {
        if (records[docHash].exists) revert AlreadyRegistered();
        records[docHash] = Record(msg.sender, uint64(block.timestamp), 0, metadataURI, "", true);
        documentCount++;
        emit DocumentRegistered(docHash, msg.sender, uint64(block.timestamp), metadataURI);
    }

    /// @notice Only the original issuer or the admin may revoke.
    function revokeDocument(bytes32 docHash, string calldata reason) external {
        Record storage r = records[docHash];
        if (!r.exists) revert NotFound();
        if (r.revokedAt != 0) revert AlreadyRevoked();
        if (msg.sender != r.issuer && msg.sender != admin) revert NotAuthorizedToRevoke();
        r.revokedAt = uint64(block.timestamp);
        r.revocationReason = reason;
        emit DocumentRevoked(docHash, msg.sender, uint64(block.timestamp), reason);
    }

    /// @return exists, issuer, registeredAt, revokedAt, metadataURI, revocationReason, issuerAuthorized
    function getDocument(bytes32 docHash)
        external view
        returns (bool, address, uint64, uint64, string memory, string memory, bool)
    {
        Record storage r = records[docHash];
        return (r.exists, r.issuer, r.registeredAt, r.revokedAt, r.metadataURI, r.revocationReason, isIssuer[r.issuer]);
    }
}
