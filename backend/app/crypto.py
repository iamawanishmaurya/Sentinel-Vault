"""AES-256-GCM envelope encryption + SHA-256 hashing."""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import MASTER_KEY


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def wrap(plaintext: bytes, aad: bytes = b"") -> str:
    """Encrypt small secrets (data keys, wallet keys) under the master key."""
    nonce = os.urandom(12)
    return _b64(nonce + AESGCM(MASTER_KEY).encrypt(nonce, plaintext, aad))


def unwrap(blob: str, aad: bytes = b"") -> bytes:
    raw = base64.b64decode(blob)
    return AESGCM(MASTER_KEY).decrypt(raw[:12], raw[12:], aad)


def encrypt_file(data: bytes, sha256: str) -> tuple[bytes, str]:
    """Returns (nonce||ciphertext||tag, wrapped data key). Each file gets its own random 256-bit key;
    the file hash is bound as AAD so ciphertext cannot be swapped between records."""
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    blob = nonce + AESGCM(key).encrypt(nonce, data, sha256.encode())
    return blob, wrap(key, sha256.encode())


def decrypt_file(blob: bytes, wrapped_key: str, sha256: str) -> bytes:
    key = unwrap(wrapped_key, sha256.encode())
    return AESGCM(key).decrypt(blob[:12], blob[12:], sha256.encode())
