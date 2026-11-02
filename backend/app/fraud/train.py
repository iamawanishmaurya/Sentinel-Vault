"""Train the Random Forest (document forensics) and Isolation Forest (activity) models on SYNTHETIC data."""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import roc_auc_score

from ..config import settings
from . import features, synth

ACTIVITY_COLS = ["count_10m", "count_1h", "distinct_docs_1h", "bad_ratio_24h", "bad_count_1h", "hour_sin", "hour_cos", "new_ip"]


def _job(args):
    seed, label = args
    data = synth.make_sample(seed, bool(label))
    return features.vector(features.analyze(data, "image/jpeg")["features"]), label


def train(n_docs: int = 320) -> dict:
    jobs = [(1000 + i, i % 2) for i in range(n_docs)]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_job, jobs, chunksize=8))
    X = np.vstack([r[0] for r in rows]); y = np.array([r[1] for r in rows])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced", random_state=0, n_jobs=-1)
    rf.fit(Xtr, ytr)
    auc = float(roc_auc_score(yte, rf.predict_proba(Xte)[:, 1]))
    cv = float(np.mean(cross_val_score(RandomForestClassifier(n_estimators=150, random_state=0, n_jobs=-1), X, y, cv=5, scoring="roc_auc")))
    rf.fit(X, y)  # final model on all synthetic data
    benign = X[y == 0]
    joblib.dump({"model": rf, "benign_mean": benign.mean(0), "benign_std": benign.std(0) + 1e-6,
                 "importances": rf.feature_importances_, "names": features.FEATURE_NAMES}, f"{settings.models_dir}/doc_rf.joblib")

    A = synth.make_activity(8000)
    iso = IsolationForest(n_estimators=300, contamination="auto", random_state=0).fit(A)
    scores = np.sort(iso.score_samples(A))  # ascending (lower = more anomalous)
    joblib.dump({"model": iso, "train_scores": scores, "cols": ACTIVITY_COLS}, f"{settings.models_dir}/activity_if.joblib")

    card = {
        "synthetic_training_data": True,
        "notice": "Both models were trained on SYNTHETIC data (programmatically rendered certificates with simulated tampering, and simulated normal verification activity). Re-train on real labelled data before production use.",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "document_model": {"type": "RandomForestClassifier", "n_estimators": 300, "samples": int(len(y)), "features": features.FEATURE_NAMES,
                            "holdout_roc_auc": round(auc, 4), "cv5_roc_auc": round(cv, 4)},
        "activity_model": {"type": "IsolationForest", "n_estimators": 300, "samples": 8000, "features": ACTIVITY_COLS},
    }
    with open(f"{settings.models_dir}/model_card.json", "w") as f:
        json.dump(card, f, indent=2)
    return card


if __name__ == "__main__":
    print(json.dumps(train(int(sys.argv[1]) if len(sys.argv) > 1 else 320), indent=2))
