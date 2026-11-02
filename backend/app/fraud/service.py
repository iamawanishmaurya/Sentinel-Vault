"""Fraud scoring: genuine model predictions (Random Forest, Isolation Forest) + transparent rules.
No random or hard-coded scores. Models are trained on SYNTHETIC data (see model_card.json)."""
import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from .. import models
from . import features as F

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # tesseract

LOW, HIGH = 0.35, 0.65
_lock = threading.Lock()
_doc = _act = None


def models_ready() -> bool:
    d = Path(settings.models_dir)
    return all((d / n).exists() for n in ("doc_rf.joblib", "activity_if.joblib", "model_card.json"))


def ensure_models():
    global _doc, _act
    with _lock:
        if not models_ready():
            from .train import train
            train()
        if _doc is None:
            _doc = joblib.load(f"{settings.models_dir}/doc_rf.joblib")
            _act = joblib.load(f"{settings.models_dir}/activity_if.joblib")


def model_card() -> dict:
    ensure_models()
    return json.loads(Path(f"{settings.models_dir}/model_card.json").read_text())


def level(score: float) -> str:
    return "High" if score >= HIGH else "Medium" if score >= LOW else "Low"


def _fmt(name: str, val: float) -> str:
    if name.endswith("_flag"):
        return "yes" if val >= 0.5 else "no"
    return f"{val:.2f}"


def score_document(analysis: dict, doc_type: str = "other") -> dict:
    """Random Forest probability that the file shows tampering signatures + explanations."""
    ensure_models()
    f = analysis["features"]
    x = F.vector(f).reshape(1, -1)
    p = float(_doc["model"].predict_proba(x)[0, 1])
    # Explanation: features that deviate from the authentic-class distribution, weighted by importance.
    z = (x[0] - _doc["benign_mean"]) / _doc["benign_std"]
    contrib = _doc["importances"] * np.abs(z)
    reasons, rules = [], []
    if p >= LOW:
        for i in np.argsort(-contrib)[:3]:
            n = F.FEATURE_NAMES[i]
            if abs(z[i]) >= 1.5:
                reasons.append({"source": "random_forest", "feature": n, "value": round(float(x[0, i]), 4), "z": round(float(z[i]), 2),
                                "text": f"{F.FEATURE_DESC[n].capitalize()} is {_fmt(n, x[0, i])} ({z[i]:+.1f}σ from authentic documents)"})
    # transparent rules
    if f["editor_meta_flag"]:
        rules.append(("rule_editor_metadata", 0.45, "File metadata names an image/PDF editing application"))
    if f["date_mismatch_flag"]:
        rules.append(("rule_date_mismatch", 0.4, "PDF modification date differs from its creation date"))
    if f["incremental_updates"] > 0:
        rules.append(("rule_incremental_update", 0.4, f"PDF contains {int(f['incremental_updates'])} incremental update section(s), meaning it was edited after creation"))
    words = analysis["words"]
    if len(words) < 5:
        rules.append(("rule_no_text", 0.4, "Little or no readable text could be extracted by OCR"))
    elif doc_type == "certificate" and not ({"certificate", "certify", "certified", "degree", "diploma", "awarded", "completed", "completion", "achievement", "university", "college", "institute"} & set(words)):
        rules.append(("rule_missing_keywords", 0.4, "Document is typed as a certificate but contains no certificate-related wording"))
    for rid, s, t in rules:
        reasons.append({"source": "rule", "rule": rid, "text": t, "score": s})
    return {"probability": p, "rule_score": max([s for _, s, _ in rules], default=0.0), "reasons": reasons}


def activity_features(db: Session, user_id: int, ip: str | None, now: datetime | None = None, current_doc_hash: str | None = None) -> dict:
    """Features describing this user's verification behaviour (computed from the DB, includes current event)."""
    now = now or datetime.now(timezone.utc)
    V = models.Verification
    since = lambda td: now - td  # noqa
    rows = db.execute(select(V.created_at, V.status, V.file_sha256, V.ip).where(V.verifier_id == user_id, V.created_at >= since(timedelta(hours=24)))).all()
    r10 = [r for r in rows if r.created_at >= since(timedelta(minutes=10))]
    r1h = [r for r in rows if r.created_at >= since(timedelta(hours=1))]
    bad = lambda rs: sum(1 for r in rs if r.status != "Verified")  # noqa
    known_ips = {r.ip for r in rows if r.ip}
    prior_ips = set(db.execute(select(V.ip).where(V.verifier_id == user_id, V.created_at < since(timedelta(hours=24))).distinct()).scalars())
    ang = 2 * math.pi * (now.hour + now.minute / 60) / 24
    return {
        "count_10m": len(r10), "count_1h": len(r1h), "distinct_docs_1h": len({r.file_sha256 for r in r1h}),
        "bad_ratio_24h": bad(rows) / len(rows) if rows else 0.0, "bad_count_1h": bad(r1h),
        "hour_sin": math.sin(ang), "hour_cos": math.cos(ang),
        "new_ip": float(bool(prior_ips) and ip not in prior_ips and ip not in (known_ips - {ip})),
        "same_file_1h": max([sum(1 for r in r1h if r.file_sha256 == h) for h in {r.file_sha256 for r in r1h}] or [0]),
    }


ACT_TEXT = {
    "count_10m": "verification requests in the last 10 minutes", "count_1h": "verification requests in the last hour",
    "distinct_docs_1h": "distinct documents checked in the last hour", "bad_ratio_24h": "share of failed verifications in 24h",
    "bad_count_1h": "failed verifications in the last hour",
}


def score_activity(af: dict) -> dict:
    """Isolation Forest anomaly percentile vs. synthetic normal behaviour, plus rules."""
    ensure_models()
    x = np.array([[af[c] for c in _act["cols"]]])
    s = float(_act["model"].score_samples(x)[0])
    ts = _act["train_scores"]  # ascending
    abnormal_pct = float(np.mean(ts >= s))  # share of normal training windows that look MORE normal than this event
    score = max(0.0, (abnormal_pct - 0.9) / 0.1)
    reasons, rules = [], []
    if score >= LOW:
        for k in ("count_10m", "count_1h", "distinct_docs_1h", "bad_count_1h", "bad_ratio_24h"):
            if af[k] > _normal_cap(k):
                txt = f"{af[k] * 100:.0f}% {ACT_TEXT[k]}" if k == "bad_ratio_24h" else f"{af[k]:.0f} {ACT_TEXT[k]}"
                reasons.append({"source": "isolation_forest", "feature": k, "value": round(af[k], 2), "text": txt})
        if not reasons:
            reasons.append({"source": "isolation_forest", "text": "Combination of timing/volume features is unusual compared to normal activity"})
    if af["count_10m"] >= 10:
        rules.append(("rule_burst", 0.85, f"{af['count_10m']} verifications within 10 minutes (burst pattern)"))
    if af["bad_count_1h"] >= 5:
        rules.append(("rule_many_failures", 0.7, f"{af['bad_count_1h']} failed verifications within an hour (possible forgery probing)"))
    elif af["bad_count_1h"] >= 3:
        rules.append(("rule_repeated_failures", 0.5, f"{af['bad_count_1h']} failed verifications within an hour"))
    if af["same_file_1h"] >= 5:
        rules.append(("rule_repeat_file", 0.5, f"Same file submitted {af['same_file_1h']} times within an hour"))
    for rid, sc, t in rules:
        reasons.append({"source": "rule", "rule": rid, "text": t, "score": sc})
    return {"anomaly_score": score, "iforest_raw": s, "rule_score": max([r[1] for r in rules], default=0.0), "reasons": reasons}


def _normal_cap(k):
    return {"count_10m": 4, "count_1h": 8, "distinct_docs_1h": 7, "bad_count_1h": 2, "bad_ratio_24h": 0.3}[k]


STATUS_SCORE = {"Verified": 0.05, "Unknown": 0.5, "Modified": 0.9, "Revoked": 0.85}


def build_report(*, doc_analysis: dict | None, doc_type: str = "other", activity: dict | None = None, status: str | None = None,
                 issuer_authorized: bool | None = None, similarity: float | None = None) -> dict:
    """Combine components transparently: final score = max(component scores)."""
    comps, reasons = {}, []
    info = {"synthetic_training_data": True, "combination": "final risk score = max(document model, activity model, rules, verification status)"}
    doc_score = act_score = None
    if doc_analysis is not None:
        d = score_document(doc_analysis, doc_type)
        doc_score = d["probability"]
        weight = 0.5 if status == "Verified" else 1.0  # exact on-chain hash match => content identical to issuer's file
        comps["document_model"] = doc_score * weight
        comps["document_rules"] = d["rule_score"]
        reasons += d["reasons"]
        info["document_model"] = "RandomForest probability of tampering signatures" + (" (weighted x0.5: hash matches blockchain record)" if weight < 1 else "")
    if activity is not None:
        a = score_activity(activity)
        act_score = a["anomaly_score"]
        comps["activity_model"] = act_score
        comps["activity_rules"] = a["rule_score"]
        reasons += a["reasons"]
    if status:
        comps["verification_status"] = STATUS_SCORE[status]
        txt = {"Verified": "Hash matches an on-chain record issued by an authorised issuer",
               "Unknown": "No blockchain record exists for this file and it does not resemble any registered document",
               "Modified": "File hash does not match the blockchain record" + (f"; content is {similarity*100:.0f}% similar to a registered document, indicating alteration" if similarity else ""),
               "Revoked": "The issuer revoked this document on-chain"}[status]
        if status != "Verified":
            reasons.append({"source": "rule", "rule": "rule_status_" + status.lower(), "text": txt, "score": STATUS_SCORE[status]})
        else:
            reasons.append({"source": "info", "text": txt})
    if issuer_authorized is False:
        comps["issuer"] = 0.8
        reasons.append({"source": "rule", "rule": "rule_issuer_unauthorized", "text": "The issuing address is no longer an authorised issuer", "score": 0.8})
    score = max(comps.values(), default=0.0)
    if not [r for r in reasons if r["source"] != "info"] and level(score) == "Low":
        reasons.append({"source": "info", "text": "No suspicious characteristics detected by the models or rules"})
    return {"risk_score": round(score, 4), "risk_level": level(score), "document_score": doc_score, "activity_score": act_score,
            "components": {k: round(v, 4) for k, v in comps.items()}, "reasons": reasons, "model_info": info}
