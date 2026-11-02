import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import chain
from .config import settings
from .db import SessionLocal
from .fraud import service as fraud
from .models import User
from .routers import admin, auth, chain_api, dashboard, documents, verify
from .security import hash_password

log = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.role == "admin")):
            db.add(User(email=settings.admin_email.lower(), name="Administrator", role="admin", status="active",
                        password_hash=hash_password(settings.admin_password)))
            db.commit()
            log.warning("Seeded admin account %s", settings.admin_email)
    try:
        fraud.ensure_models()
    except Exception:
        log.exception("Fraud models unavailable")
    yield


app = FastAPI(title="Sentinel Vault API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, documents.router, verify.router, chain_api.router, admin.router, dashboard.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "blockchain": chain.is_connected(), "models": fraud.models_ready()}
