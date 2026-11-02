"""Real Ethereum integration through web3.py against the Hardhat JSON-RPC node."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from web3 import Web3
from web3.exceptions import ContractLogicError

from .config import settings

_lock = threading.Lock()
_w3: Web3 | None = None
_contract = None
_meta: dict | None = None


class ChainError(Exception):
    pass


def w3() -> Web3:
    global _w3
    if _w3 is None:
        _w3 = Web3(Web3.HTTPProvider(settings.rpc_url, request_kwargs={"timeout": 20}))
    return _w3


def meta() -> dict:
    global _meta
    if _meta is None:
        p = Path(settings.contract_file)
        if not p.exists():
            raise ChainError(f"Contract deployment file not found: {p}. Deploy with `npm run deploy` in /contracts.")
        _meta = json.loads(p.read_text())
    return _meta


def contract():
    global _contract
    if _contract is None:
        _contract = w3().eth.contract(address=Web3.to_checksum_address(meta()["address"]), abi=meta()["abi"])
    return _contract


def reset_cache():
    global _contract, _meta
    _contract = None
    _meta = None


def is_connected() -> bool:
    try:
        return w3().is_connected() and len(w3().eth.get_code(Web3.to_checksum_address(meta()["address"]))) > 0
    except Exception:
        return False


def new_wallet() -> tuple[str, str]:
    acct = w3().eth.account.create()
    return acct.address, acct.key.hex()


def _send(fn, private_key: str):
    """Sign and send a contract call, wait for the receipt. Raises ChainError with the revert reason."""
    acct = w3().eth.account.from_key(private_key)
    with _lock:
        try:
            tx = fn.build_transaction({
                "from": acct.address,
                "nonce": w3().eth.get_transaction_count(acct.address, "pending"),
                "chainId": meta()["chainId"],
            })
            signed = acct.sign_transaction(tx)
            h = w3().eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3().eth.wait_for_transaction_receipt(h, timeout=30)
        except ContractLogicError as e:
            raise ChainError(f"Contract reverted: {e}") from e
        except Exception as e:
            raise ChainError(str(e)) from e
    if receipt["status"] != 1:
        raise ChainError("Transaction failed on-chain")
    block = w3().eth.get_block(receipt["blockNumber"])
    return {
        "tx_hash": h.hex() if h.hex().startswith("0x") else "0x" + h.hex(),
        "block_number": receipt["blockNumber"],
        "block_timestamp": datetime.fromtimestamp(block["timestamp"], tz=timezone.utc),
        "from_address": acct.address,
        "to_address": contract().address,
        "gas_used": receipt["gasUsed"],
        "status": "success",
    }


def fund(address: str, eth: float):
    acct = w3().eth.account.from_key(settings.deployer_private_key)
    with _lock:
        tx = {
            "from": acct.address, "to": Web3.to_checksum_address(address), "value": Web3.to_wei(eth, "ether"),
            "nonce": w3().eth.get_transaction_count(acct.address, "pending"), "chainId": meta()["chainId"],
            "gas": 21000, "maxFeePerGas": w3().eth.gas_price * 2, "maxPriorityFeePerGas": 1,
        }
        h = w3().eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        w3().eth.wait_for_transaction_receipt(h, timeout=30)


def _h32(hex_hash: str) -> bytes:
    return bytes.fromhex(hex_hash)


def add_issuer(address: str, name: str) -> dict:
    return _send(contract().functions.addIssuer(Web3.to_checksum_address(address), name), settings.deployer_private_key)


def remove_issuer(address: str) -> dict:
    return _send(contract().functions.removeIssuer(Web3.to_checksum_address(address)), settings.deployer_private_key)


def register_document(doc_hash: str, metadata_uri: str, issuer_private_key: str) -> dict:
    return _send(contract().functions.registerDocument(_h32(doc_hash), metadata_uri), issuer_private_key)


def revoke_document(doc_hash: str, reason: str, private_key: str) -> dict:
    return _send(contract().functions.revokeDocument(_h32(doc_hash), reason), private_key)


def lookup(doc_hash: str) -> dict:
    exists, issuer, reg_at, rev_at, uri, reason, authorized = contract().functions.getDocument(_h32(doc_hash)).call()
    return {
        "exists": exists, "issuer": issuer if exists else None,
        "registered_at": datetime.fromtimestamp(reg_at, tz=timezone.utc) if exists else None,
        "revoked_at": datetime.fromtimestamp(rev_at, tz=timezone.utc) if rev_at else None,
        "metadata_uri": uri, "revocation_reason": reason, "issuer_authorized": authorized,
        "issuer_name": contract().functions.issuerName(issuer).call() if exists else None,
    }


def chain_info() -> dict:
    w = w3()
    latest = w.eth.get_block("latest")
    return {
        "connected": True, "chain_id": w.eth.chain_id, "latest_block": latest["number"],
        "contract_address": meta()["address"], "admin": contract().functions.admin().call(),
        "document_count": contract().functions.documentCount().call(),
        "client": w.client_version,
    }


def block_summary(n) -> dict:
    b = w3().eth.get_block(n)
    return {"number": b["number"], "hash": b["hash"].hex(), "timestamp": datetime.fromtimestamp(b["timestamp"], tz=timezone.utc),
            "tx_count": len(b["transactions"]), "gas_used": b["gasUsed"], "miner": b.get("miner")}


def tx_detail(tx_hash: str) -> dict:
    w = w3()
    tx = w.eth.get_transaction(tx_hash)
    rc = w.eth.get_transaction_receipt(tx_hash)
    blk = w.eth.get_block(rc["blockNumber"])
    events = []
    for name in ("IssuerAdded", "IssuerRemoved", "DocumentRegistered", "DocumentRevoked"):
        for ev in getattr(contract().events, name)().process_receipt(rc):
            events.append({"event": ev["event"], "args": {k: (v.hex() if isinstance(v, bytes) else v) for k, v in ev["args"].items()}})
    return {
        "tx_hash": tx_hash, "block_number": rc["blockNumber"], "block_hash": blk["hash"].hex(),
        "timestamp": datetime.fromtimestamp(blk["timestamp"], tz=timezone.utc),
        "from": tx["from"], "to": tx["to"], "nonce": tx["nonce"], "gas_used": rc["gasUsed"],
        "status": "success" if rc["status"] == 1 else "failed", "events": events,
        "confirmations": w.eth.block_number - rc["blockNumber"] + 1,
    }
