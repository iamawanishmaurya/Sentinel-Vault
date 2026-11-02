from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..fraud import service as fraud
from ..models import ChainTransaction, Document, FraudReport, User, Verification
from ..security import current_user
from .verify import verification_out

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(u: User = Depends(current_user), db: Session = Depends(get_db)):
    admin = u.role == "admin"
    my_docs = select(Document.id).where(Document.owner_id == u.id)
    doc_q = select(func.count()).select_from(Document)
    ver = select(Verification)
    rep = select(FraudReport)
    if not admin:
        doc_q = doc_q.where(Document.owner_id == u.id)
        if u.role == "verifier":
            ver = ver.where(Verification.verifier_id == u.id)
            rep = rep.where(FraudReport.user_id == u.id)
        else:
            ver = ver.where(or_(Verification.verifier_id == u.id, Verification.document_id.in_(my_docs)))
            rep = rep.where(or_(FraudReport.user_id == u.id, FraudReport.document_id.in_(my_docs)))
    vsub, rsub = ver.subquery(), rep.subquery()
    count = lambda s, col, val: db.scalar(select(func.count()).select_from(s).where(col == val))  # noqa
    status_counts = dict(db.execute(select(vsub.c.status, func.count()).group_by(vsub.c.status)).all())
    if admin:
        tx_total = db.scalar(select(func.count()).select_from(ChainTransaction))
    else:
        tx_total = db.scalar(select(func.count()).select_from(ChainTransaction).where(ChainTransaction.document_id.in_(my_docs)))
    risk_counts = dict(db.execute(select(rsub.c.risk_level, func.count()).group_by(rsub.c.risk_level)).all())
    suspicious = db.scalar(select(func.count()).select_from(rsub).where(rsub.c.risk_level.in_(["Medium", "High"]), rsub.c.subject_type == "verification"))
    since = datetime.now(timezone.utc) - timedelta(days=13)
    daily = {}
    for d, st, n in db.execute(select(func.date(vsub.c.created_at), vsub.c.status, func.count()).where(vsub.c.created_at >= since).group_by(func.date(vsub.c.created_at), vsub.c.status)):
        daily.setdefault(str(d), {})[st] = n
    timeline = []
    for i in range(14):
        day = (since + timedelta(days=i)).date().isoformat()
        row = daily.get(day, {})
        timeline.append({"date": day, **{k: row.get(k, 0) for k in ("Verified", "Modified", "Unknown", "Revoked")}})
    risk_daily = {}
    for d, lv, n in db.execute(select(func.date(rsub.c.created_at), rsub.c.risk_level, func.count()).where(rsub.c.created_at >= since).group_by(func.date(rsub.c.created_at), rsub.c.risk_level)):
        risk_daily.setdefault(str(d), {})[lv] = n
    risk_timeline = [{"date": (since + timedelta(days=i)).date().isoformat(),
                      **{k: risk_daily.get((since + timedelta(days=i)).date().isoformat(), {}).get(k, 0) for k in ("Low", "Medium", "High")}} for i in range(14)]
    recent = db.scalars(ver.order_by(Verification.id.desc()).limit(8)).all()
    return {
        "totals": {
            "documents": db.scalar(doc_q),
            "verified": status_counts.get("Verified", 0), "modified": status_counts.get("Modified", 0),
            "unknown": status_counts.get("Unknown", 0), "revoked": status_counts.get("Revoked", 0),
            "revoked_documents": db.scalar(doc_q.where(Document.status == "revoked")),
            "blockchain_transactions": tx_total, "suspicious_activities": suspicious,
            "verifications": sum(status_counts.values()),
        },
        "risk_distribution": {k: risk_counts.get(k, 0) for k in ("Low", "Medium", "High")},
        "verification_timeline": timeline, "risk_timeline": risk_timeline,
        "recent_verifications": [verification_out(v, db) for v in recent],
    }


@router.get("/analytics/reports")
def reports(level: str = "", subject: str = "", limit: int = 100, u: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(FraudReport).order_by(FraudReport.id.desc()).limit(min(limit, 300))
    if u.role != "admin":
        mine = select(Document.id).where(Document.owner_id == u.id)
        stmt = stmt.where(or_(FraudReport.user_id == u.id, FraudReport.document_id.in_(mine)))
    if level:
        stmt = stmt.where(FraudReport.risk_level == level)
    if subject:
        stmt = stmt.where(FraudReport.subject_type == subject)
    out = []
    for r in db.scalars(stmt):
        d = db.get(Document, r.document_id) if r.document_id else None
        v = db.get(Verification, r.verification_id) if r.verification_id else None
        out.append({"id": r.id, "subject_type": r.subject_type, "risk_level": r.risk_level, "risk_score": r.risk_score,
                    "document_score": r.document_score, "activity_score": r.activity_score, "reasons": r.reasons,
                    "created_at": r.created_at, "document_title": d.title if d else None, "document_id": r.document_id,
                    "verification_id": r.verification_id, "verification_status": v.status if v else None,
                    "filename": v.filename if v else (d.filename if d else None), "components": (r.features or {}).get("components")})
    return out


@router.get("/analytics/model-card")
def model_card(u: User = Depends(current_user)):
    return fraud.model_card()
