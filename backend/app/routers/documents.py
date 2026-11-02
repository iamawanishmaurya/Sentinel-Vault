from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import chain, crypto, models, storage
from ..config import settings
from ..db import get_db
from ..fraud import features as F, service as fraud
from ..models import ChainTransaction, Document, DocumentShare, FraudReport, Issuer, User
from ..security import current_user

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED = {"application/pdf": b"%PDF-", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}


def sniff_mime(data: bytes) -> str | None:
    for m, magic in ALLOWED.items():
        if data.startswith(magic):
            return m
    return None


def doc_out(d: Document, me: User, db: Session | None = None) -> dict:
    out = {
        "id": d.id, "title": d.title, "doc_type": d.doc_type, "filename": d.filename, "mime_type": d.mime_type,
        "size_bytes": d.size_bytes, "sha256": d.sha256, "status": d.status, "ipfs_cid": d.ipfs_cid,
        "created_at": d.created_at, "owner": {"id": d.owner_id, "name": d.owner.name},
        "issuer": {"name": d.issuer.name, "address": d.issuer.eth_address} if d.issuer else None,
        "is_owner": d.owner_id == me.id,
    }
    if db is not None:
        tx = db.scalars(select(ChainTransaction).where(ChainTransaction.document_id == d.id).order_by(ChainTransaction.id)).all()
        out["transactions"] = [{"tx_hash": t.tx_hash, "kind": t.kind, "block_number": t.block_number, "timestamp": t.block_timestamp, "status": t.status} for t in tx]
        rep = db.scalar(select(FraudReport).where(FraudReport.document_id == d.id, FraudReport.subject_type == "document").order_by(FraudReport.id.desc()))
        out["fraud_report"] = report_out(rep) if rep else None
    return out


def report_out(r: FraudReport) -> dict:
    return {"id": r.id, "risk_level": r.risk_level, "risk_score": r.risk_score, "document_score": r.document_score,
            "activity_score": r.activity_score, "reasons": r.reasons, "features": r.features, "model_info": r.model_info, "created_at": r.created_at}


def can_view(d: Document, u: User, db: Session) -> bool:
    if u.role == "admin" or d.owner_id == u.id:
        return True
    s = db.scalar(select(DocumentShare).where(DocumentShare.document_id == d.id, DocumentShare.user_id == u.id))
    return bool(s and (s.expires_at is None or s.expires_at > datetime.now(timezone.utc)))


def get_doc(doc_id: int, u: User, db: Session) -> Document:
    d = db.get(Document, doc_id)
    if not d or not can_view(d, u, db):
        raise HTTPException(404, "Document not found")
    return d


def record_tx(db: Session, r: dict, kind: str, doc_hash: str | None, document_id: int | None):
    db.add(ChainTransaction(kind=kind, doc_hash=doc_hash, document_id=document_id, **r))


def issuer_of(u: User, db: Session) -> Issuer:
    iss = db.scalar(select(Issuer).where(Issuer.user_id == u.id))
    if not iss or not iss.authorized:
        raise HTTPException(403, "Only authorised issuers can register official documents")
    return iss


def _register(d: Document, u: User, db: Session):
    iss = issuer_of(u, db)
    try:
        if chain.lookup(d.sha256)["exists"]:
            raise HTTPException(409, "This exact file is already registered on-chain")
        r = chain.register_document(d.sha256, d.ipfs_cid and f"ipfs://{d.ipfs_cid}" or f"sentinel:{d.id}",
                                    crypto.unwrap(iss.wrapped_private_key).decode())
    except chain.ChainError as e:
        raise HTTPException(502, f"Blockchain error: {e}")
    d.status, d.issuer_id = "registered", iss.id
    record_tx(db, r, "register", d.sha256, d.id)


@router.post("", status_code=201)
def upload(file: UploadFile = File(...), title: str = Form(""), doc_type: str = Form("other"), register_on_chain: bool = Form(False),
           u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "verifier":
        raise HTTPException(403, "Verifiers cannot store documents; use the Verify page")
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    mime = sniff_mime(data)
    if not mime:
        raise HTTPException(415, "Only PDF, JPG and PNG files are accepted")
    if register_on_chain:
        issuer_of(u, db)  # fail fast before storing anything
    h = crypto.sha256_hex(data)
    try:
        an = F.analyze(data, mime)
    except Exception as e:
        raise HTTPException(422, f"Could not read document: {e}")
    blob, wrapped = crypto.encrypt_file(data, h)
    d = Document(owner_id=u.id, title=title.strip() or file.filename or "Untitled", doc_type=doc_type[:50], filename=(file.filename or "file")[:255],
                 mime_type=mime, size_bytes=len(data), sha256=h, storage_path=storage.save_blob(blob), wrapped_key=wrapped,
                 ipfs_cid=storage.ipfs_add(blob), minhash=an["minhash"], phash=an["phash"])
    db.add(d); db.flush()
    rep = fraud.build_report(doc_analysis=an, doc_type=doc_type)
    db.add(FraudReport(subject_type="document", document_id=d.id, user_id=u.id, risk_level=rep["risk_level"], risk_score=rep["risk_score"],
                       document_score=rep["document_score"], activity_score=None, reasons=rep["reasons"],
                       features={k: round(v, 4) for k, v in an["features"].items()}, model_info=rep["model_info"]))
    try:
        if register_on_chain:
            _register(d, u, db)
    except HTTPException:
        storage.delete_blob(d.storage_path); db.rollback(); raise
    db.commit()
    return doc_out(d, u, db)


@router.get("")
def list_docs(q: str = "", status: str = "", scope: str = "all", u: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    shared_ids = select(DocumentShare.document_id).where(DocumentShare.user_id == u.id, or_(DocumentShare.expires_at.is_(None), DocumentShare.expires_at > now))
    stmt = select(Document)
    if u.role != "admin":
        stmt = stmt.where(Document.owner_id == u.id) if scope == "mine" else stmt.where(or_(Document.owner_id == u.id, Document.id.in_(shared_ids)))
    elif scope == "mine":
        stmt = stmt.where(Document.owner_id == u.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Document.title.ilike(like), Document.filename.ilike(like), Document.sha256.ilike(like)))
    if status:
        stmt = stmt.where(Document.status == status)
    docs = db.scalars(stmt.order_by(Document.id.desc()).limit(200)).all()
    risk = {r.document_id: r.risk_level for r in db.scalars(select(FraudReport).where(FraudReport.document_id.in_([d.id for d in docs]), FraudReport.subject_type == "document"))}
    return [{**doc_out(d, u), "risk_level": risk.get(d.id)} for d in docs]


@router.get("/{doc_id}")
def detail(doc_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    out = doc_out(d, u, db)
    if d.owner_id == u.id or u.role == "admin":
        out["shares"] = [{"id": s.id, "user": {"id": s.user.id, "name": s.user.name, "email": s.user.email}, "expires_at": s.expires_at}
                         for s in db.scalars(select(DocumentShare).where(DocumentShare.document_id == d.id))]
    return out


@router.get("/{doc_id}/download")
def download(doc_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    try:
        data = crypto.decrypt_file(storage.load_blob(d.storage_path), d.wrapped_key, d.sha256)
    except Exception:
        raise HTTPException(500, "Integrity failure: stored ciphertext failed authentication")
    if crypto.sha256_hex(data) != d.sha256:
        raise HTTPException(500, "Integrity failure: hash mismatch")
    safe = d.filename.replace('"', "")
    return Response(data, media_type=d.mime_type, headers={"Content-Disposition": f'inline; filename="{safe}"', "X-Content-Type-Options": "nosniff"})


@router.post("/{doc_id}/register")
def register(doc_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    if d.owner_id != u.id:
        raise HTTPException(403, "Only the owner can register this document")
    if d.status != "stored":
        raise HTTPException(409, f"Document is already {d.status}")
    _register(d, u, db); db.commit()
    return doc_out(d, u, db)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{doc_id}/revoke")
def revoke(doc_id: int, body: RevokeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    if d.status != "registered":
        raise HTTPException(409, "Only registered documents can be revoked")
    if u.role == "admin":
        key = settings.deployer_private_key
    else:
        iss = issuer_of(u, db)
        if d.issuer_id != iss.id:
            raise HTTPException(403, "Only the issuing authority can revoke this document")
        key = crypto.unwrap(iss.wrapped_private_key).decode()
    try:
        r = chain.revoke_document(d.sha256, body.reason, key)
    except chain.ChainError as e:
        raise HTTPException(502, f"Blockchain error: {e}")
    d.status = "revoked"
    record_tx(db, r, "revoke", d.sha256, d.id); db.commit()
    return doc_out(d, u, db)


class ShareIn(BaseModel):
    email: EmailStr
    expires_days: int | None = Field(default=7, ge=1, le=365)


@router.post("/{doc_id}/share", status_code=201)
def share(doc_id: int, body: ShareIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    if d.owner_id != u.id and u.role != "admin":
        raise HTTPException(403, "Only the owner can share")
    target = db.scalar(select(User).where(User.email == body.email.lower(), User.status == "active"))
    if not target or target.id == d.owner_id:
        raise HTTPException(404, "No active user with that email")
    exp = datetime.now(timezone.utc) + timedelta(days=body.expires_days) if body.expires_days else None
    s = db.scalar(select(DocumentShare).where(DocumentShare.document_id == d.id, DocumentShare.user_id == target.id))
    if s:
        s.expires_at = exp
    else:
        db.add(DocumentShare(document_id=d.id, user_id=target.id, created_by=u.id, expires_at=exp))
    db.commit()
    return {"ok": True}


@router.delete("/{doc_id}/share/{share_id}")
def unshare(doc_id: int, share_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    if d.owner_id != u.id and u.role != "admin":
        raise HTTPException(403, "Only the owner can manage shares")
    s = db.get(DocumentShare, share_id)
    if s and s.document_id == d.id:
        db.delete(s); db.commit()
    return {"ok": True}


@router.delete("/{doc_id}")
def delete(doc_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_doc(doc_id, u, db)
    if d.owner_id != u.id and u.role != "admin":
        raise HTTPException(403, "Only the owner can delete")
    if d.status != "stored":
        raise HTTPException(409, "On-chain records are immutable: revoke the document instead of deleting it")
    storage.delete_blob(d.storage_path)
    db.query(DocumentShare).filter_by(document_id=d.id).delete()
    db.query(FraudReport).filter_by(document_id=d.id).delete()
    db.delete(d); db.commit()
    return {"ok": True}
