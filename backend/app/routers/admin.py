from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import chain, crypto
from ..config import settings
from ..db import get_db
from ..models import ChainTransaction, Issuer, User
from ..routers.auth import user_out
from ..security import require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_roles("admin")


@router.get("/users")
def users(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    iss = {i.user_id: i for i in db.scalars(select(Issuer))}
    return [{**user_out(u), "issuer": ({"name": iss[u.id].name, "address": iss[u.id].eth_address, "authorized": iss[u.id].authorized} if u.id in iss else None)}
            for u in db.scalars(select(User).order_by(User.id))]


class ApproveIn(BaseModel):
    issuer_name: str = Field(min_length=2, max_length=120)


@router.post("/users/{uid}/approve-issuer")
def approve_issuer(uid: int, body: ApproveIn, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.role != "issuer":
        raise HTTPException(404, "Issuer applicant not found")
    iss = db.scalar(select(Issuer).where(Issuer.user_id == uid))
    try:
        if not iss:
            addr, pk = chain.new_wallet()
            chain.fund(addr, settings.issuer_funding_eth)
            iss = Issuer(user_id=uid, name=body.issuer_name, eth_address=addr, wrapped_private_key=crypto.wrap(pk.encode()))
            db.add(iss)
        r = chain.add_issuer(iss.eth_address, body.issuer_name)
    except chain.ChainError as e:
        raise HTTPException(502, f"Blockchain error: {e}")
    iss.authorized, iss.name, u.status = True, body.issuer_name, "active"
    db.add(ChainTransaction(kind="add_issuer", doc_hash=None, **r)); db.commit()
    return {"ok": True, "issuer_address": iss.eth_address, "tx_hash": r["tx_hash"]}


@router.post("/users/{uid}/revoke-issuer")
def revoke_issuer(uid: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    iss = db.scalar(select(Issuer).where(Issuer.user_id == uid))
    if not iss:
        raise HTTPException(404, "Not an issuer")
    try:
        r = chain.remove_issuer(iss.eth_address)
    except chain.ChainError as e:
        raise HTTPException(502, f"Blockchain error: {e}")
    iss.authorized = False
    db.add(ChainTransaction(kind="remove_issuer", doc_hash=None, **r)); db.commit()
    return {"ok": True, "tx_hash": r["tx_hash"]}


class StatusIn(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


@router.post("/users/{uid}/status")
def set_status(uid: int, body: StatusIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.id == admin.id:
        raise HTTPException(400, "Invalid target")
    u.status = body.status; db.commit()
    return user_out(u)
