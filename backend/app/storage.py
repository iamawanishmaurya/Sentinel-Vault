import uuid
from pathlib import Path

import httpx

from .config import settings


def save_blob(blob: bytes) -> str:
    name = f"{uuid.uuid4().hex}.enc"
    (Path(settings.storage_dir) / name).write_bytes(blob)
    return name


def load_blob(name: str) -> bytes:
    return (Path(settings.storage_dir) / name).read_bytes()


def delete_blob(name: str) -> None:
    (Path(settings.storage_dir) / name).unlink(missing_ok=True)


def ipfs_add(blob: bytes) -> str | None:
    """Optionally pin the *already encrypted* blob to IPFS. Returns CID or None if disabled/unavailable."""
    if not settings.ipfs_api_url:
        return None
    try:
        r = httpx.post(f"{settings.ipfs_api_url}/api/v0/add", files={"file": ("doc.enc", blob)}, timeout=30)
        r.raise_for_status()
        return r.json()["Hash"]
    except Exception:
        return None
