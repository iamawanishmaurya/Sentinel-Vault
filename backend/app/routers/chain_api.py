from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import chain
from ..db import get_db
from ..models import ChainTransaction, Document, Issuer, User
from ..security import current_user

router = APIRouter(prefix="/chain", tags=["blockchain explorer"])


@router.get("/info")
def info(u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        i = chain.chain_info()
    except Exception as e:
        raise HTTPException(502, f"Blockchain unavailable: {e}")
    i["issuers"] = [{"name": x.name, "address": x.eth_address, "authorized": x.authorized} for x in db.scalars(select(Issuer))]
    return i


@router.get("/transactions")
def transactions(limit: int = 50, offset: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(ChainTransaction).order_by(ChainTransaction.id.desc()).limit(min(limit, 200)).offset(offset)
    rows = db.scalars(q).all()
    total = db.scalar(select(func.count()).select_from(ChainTransaction))
    names = {i.eth_address.lower(): i.name for i in db.scalars(select(Issuer))}
    titles = {}
    ids = [r.document_id for r in rows if r.document_id]
    if ids:
        titles = {d.id: d.title for d in db.scalars(select(Document).where(Document.id.in_(ids)))}
    return {"total": total, "items": [{
        "tx_hash": r.tx_hash, "kind": r.kind, "block_number": r.block_number, "timestamp": r.block_timestamp,
        "from": r.from_address, "from_name": names.get(r.from_address.lower()), "to": r.to_address, "doc_hash": r.doc_hash,
        "document_title": titles.get(r.document_id), "gas_used": r.gas_used, "status": r.status} for r in rows]}


@router.get("/blocks")
def blocks(count: int = 10, u: User = Depends(current_user)):
    try:
        latest = chain.w3().eth.block_number
        return [chain.block_summary(n) for n in range(latest, max(-1, latest - min(count, 50)), -1)]
    except Exception as e:
        raise HTTPException(502, f"Blockchain unavailable: {e}")


@router.get("/tx/{tx_hash}")
def tx(tx_hash: str, u: User = Depends(current_user)):
    try:
        return chain.tx_detail(tx_hash)
    except Exception as e:
        raise HTTPException(404, f"Transaction not found: {e}")
