import base64
import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel"
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    master_key: str = ""  # base64 32 bytes; auto-generated into storage dir for dev if empty
    storage_dir: str = "./storage"
    models_dir: str = "./models"
    rpc_url: str = "http://127.0.0.1:8545"
    contract_file: str = "../contracts/deployments/DocumentRegistry.json"
    # Hardhat account #0 (public dev key, only valid on the local Hardhat network)
    deployer_private_key: str = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    issuer_funding_eth: float = 5.0
    ipfs_api_url: str = ""  # e.g. http://ipfs:5001 ; empty disables IPFS
    admin_email: str = "admin@sentinel-vault.dev"
    admin_password: str = "ChangeMe!Admin123"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 15


settings = Settings()

Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
Path(settings.models_dir).mkdir(parents=True, exist_ok=True)


def _persisted_secret(name: str, value: str, nbytes: int = 32) -> bytes:
    """Use configured secret or persist a generated one (dev convenience; set env vars in prod)."""
    if value:
        return base64.b64decode(value) if name == "master.key" else value.encode()
    p = Path(settings.storage_dir) / f".{name}"
    if not p.exists():
        p.write_bytes(base64.b64encode(secrets.token_bytes(nbytes)))
        os.chmod(p, 0o600)
    raw = base64.b64decode(p.read_bytes())
    return raw


MASTER_KEY: bytes = _persisted_secret("master.key", settings.master_key)
assert len(MASTER_KEY) == 32, "MASTER_KEY must be 32 bytes (base64 encoded)"
JWT_SECRET: str = settings.jwt_secret or base64.b64encode(_persisted_secret("jwt.key", "")).decode()
