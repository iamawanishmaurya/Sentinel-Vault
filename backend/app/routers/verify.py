from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import chain, crypto, models
from ..config import settings
from ..db import get_db
from ..fraud import features as F, service as fraud
from ..models import Document, FraudReport, User, Verification
from ..security import client_ip, current_user
from .documents import report_out, sniff_mime

router = APIRouter(prefix="/verify", tags=["verification"])
MODIFIED_TEXT_SIM = 0.45    # MinHash Jaccard estimate on word-bigram shingles
MODIFIED_IMG_SIM = 0.88     # 64-bit dHash similarity


def verification_out(v: Verification, db: Session, with_report=True) -> dict:
    out = {"id": v.id, "filename": v.filename, "file_sha256": v.file_sha256, "status": v.status, "document_id": v.document_id,
           "claimed_document_id": v.claimed_document_id, "similarity": v.similarity, "issuer_address": v.issuer_address,
           "issuer_authorized": v.issuer_authorized, "chain_timestamp": v.chain_timestamp, "details": v.details,
           "created_at": v.created_at, "verifier": {"id": v.verifier_id, "name": v.verifier.name}}
    if with_report:
        r = db.scalar(select(FraudReport).where(FraudReport.verification_id == v.id))
        out["fraud_report"] = report_out(r) if r else None
    return out


@router.post("", status_code=201)
def verify(request: Request, file: UploadFile = File(...), claimed_document_id: int | None = Form(None),
           u: User = Depends(current_user), db: Session = Depends(get_db)):
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")
    mime = sniff_mime(data)
    if not mime:
        raise HTTPException(415, "Only PDF, JPG and PNG files are accepted")
    h = crypto.sha256_hex(data)
    try:
        an = F.analyze(data, mime)
    except Exception as e:
        raise HTTPException(422, f"Could not read document: {e}")
    try:
        rec = chain.lookup(h)
    except Exception as e:
        raise HTTPException(502, f"Blockchain unavailable: {e}")

    status, doc, sim, notes = "Unknown", None, None, []
    if rec["exists"]:
        doc = db.scalar(select(Document).where(Document.sha256 == h, Document.status.in_(["registered", "revoked"])))
        if rec["revoked_at"]:
            status = "Revoked"; notes.append(f"Revoked on-chain: {rec['revocation_reason']}")
        elif not rec["issuer_authorized"]:
            status = "Unknown"; notes.append("A record exists but its issuer is no longer authorised, so it cannot be trusted")
        else:
            status = "Verified"; notes.append("Hash matches the on-chain record and the issuer is authorised")
    else:
        # No exact match: is it an altered copy of something we know? (claimed ID or content similarity)
        candidates = db.scalars(select(Document).where(Document.status.in_(["registered", "revoked"]))).all()
        best, best_sim = None, 0.0
        for c in candidates:
            if claimed_document_id and c.id != claimed_document_id:
                continue
            ts = F.minhash_similarity(an["minhash"], c.minhash)
            isim = F.dhash_similarity(an["phash"], c.phash) if c.phash else 0.0
            s = ts if ts >= MODIFIED_TEXT_SIM else (isim if isim >= MODIFIED_IMG_SIM else max(ts, 0.0))
            if (claimed_document_id or ts >= MODIFIED_TEXT_SIM or isim >= MODIFIED_IMG_SIM) and max(ts, isim if isim >= MODIFIED_IMG_SIM else 0) >= best_sim:
                best, best_sim = c, max(ts, isim if isim >= MODIFIED_IMG_SIM else 0)
        if best:
            status, doc, sim = "Modified", best, best_sim
            notes.append(f"SHA-256 {h[:16]}… does not match the registered hash {best.sha256[:16]}… for \"{best.title}\"")
            notes.append(f"Content similarity to the registered document: {best_sim*100:.0f}%")
            rec = chain.lookup(best.sha256)
        elif claimed_document_id:
            notes.append("The claimed document ID did not match any registered document")
        else:
            notes.append("No blockchain record and no similar registered document")

    v = Verification(verifier_id=u.id, filename=(file.filename or "file")[:255], file_sha256=h, status=status,
                     document_id=doc.id if doc else None, claimed_document_id=claimed_document_id, similarity=sim,
                     issuer_address=rec.get("issuer"), issuer_authorized=rec.get("issuer_authorized") if rec.get("exists") else None,
                     chain_timestamp=rec.get("registered_at"), ip=client_ip(request),
                     details={"notes": notes, "issuer_name": rec.get("issuer_name"), "document_title": doc.title if doc else None,
                              "registered_hash": doc.sha256 if doc else None, "revoked_at": rec.get("revoked_at") and rec["revoked_at"].isoformat(),
                              "revocation_reason": rec.get("revocation_reason") or None})
    db.add(v); db.flush()
    af = fraud.activity_features(db, u.id, v.ip)
    rep = fraud.build_report(doc_analysis=an, doc_type=doc.doc_type if doc else "other", activity=af, status=status,
                             issuer_authorized=(rec["issuer_authorized"] if rec.get("exists") and status != "Verified" and status != "Revoked" else None),
                             similarity=sim)
    db.add(FraudReport(subject_type="verification", verification_id=v.id, document_id=doc.id if doc else None, user_id=u.id,
                       risk_level=rep["risk_level"], risk_score=rep["risk_score"], document_score=rep["document_score"],
                       activity_score=rep["activity_score"], reasons=rep["reasons"],
                       features={"document": {k: round(x, 4) for k, x in an["features"].items()}, "activity": {k: round(x, 4) for k, x in af.items()},
                                 "components": rep["components"]}, model_info=rep["model_info"]))
    db.commit()
    return verification_out(v, db)


@router.get("")
def history(limit: int = 50, u: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Verification).order_by(Verification.id.desc()).limit(min(limit, 200))
    if u.role == "admin":
        pass
    elif u.role in ("issuer", "owner"):
        mine = select(Document.id).where(Document.owner_id == u.id)
        stmt = stmt.where((Verification.verifier_id == u.id) | Verification.document_id.in_(mine))
    else:
        stmt = stmt.where(Verification.verifier_id == u.id)
    return [verification_out(v, db) for v in db.scalars(stmt)]


@router.get("/{vid}")
def get_one(vid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.get(Verification, vid)
    if not v:
        raise HTTPException(404, "Not found")
    mine = v.verifier_id == u.id
    owns = bool(v.document_id and (d := db.get(Document, v.document_id)) and d.owner_id == u.id)
    if not (mine or owns or u.role == "admin"):
        raise HTTPException(404, "Not found")
    return verification_out(v, db)
