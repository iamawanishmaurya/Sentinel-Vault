import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("STORAGE_DIR", "/tmp/sv-test-storage")
from cryptography.exceptions import InvalidTag  # noqa: E402

from app import crypto  # noqa: E402
from app.fraud import features as F, service as fraud, synth  # noqa: E402


def test_sha256_known_vector():
    assert crypto.sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_encrypt_roundtrip_and_tamper_detection():
    data = os.urandom(5000)
    h = crypto.sha256_hex(data)
    blob, wrapped = crypto.encrypt_file(data, h)
    assert data not in blob
    assert crypto.decrypt_file(blob, wrapped, h) == data
    bad = bytearray(blob); bad[20] ^= 1
    with pytest.raises(InvalidTag):
        crypto.decrypt_file(bytes(bad), wrapped, h)
    with pytest.raises(InvalidTag):  # AAD binding: cannot be swapped to another record
        crypto.decrypt_file(blob, wrapped, "0" * 64)


def test_unique_keys_and_nonces_per_file():
    b1, w1 = crypto.encrypt_file(b"x", "a"); b2, w2 = crypto.encrypt_file(b"x", "a")
    assert b1 != b2 and w1 != w2


def test_minhash_detects_edit_but_not_unrelated():
    a = F.minhash("this is to certify that jordan rivers has completed the bachelor of computer science with first class".split())
    b = F.minhash("this is to certify that jordan rivers has completed the bachelor of computer science with distinction".split())
    c = F.minhash("quarterly invoice number 4471 payable within thirty days to the supplier account".split())
    assert F.minhash_similarity(a, a) == 1.0
    assert F.minhash_similarity(a, b) > 0.5 > F.minhash_similarity(a, c)


def test_document_model_runs_on_real_image():
    img = synth.make_sample(5, tampered=False)
    an = F.analyze(img, "image/jpeg")
    r = fraud.score_document(an, "certificate")
    assert 0.0 <= r["probability"] <= 1.0


def test_activity_burst_flagged_and_normal_not():
    normal = dict(count_10m=1, count_1h=2, distinct_docs_1h=2, bad_ratio_24h=0.0, bad_count_1h=0, hour_sin=0.0, hour_cos=-1.0, new_ip=0.0, same_file_1h=1)
    burst = dict(count_10m=30, count_1h=60, distinct_docs_1h=55, bad_ratio_24h=0.8, bad_count_1h=40, hour_sin=0.0, hour_cos=1.0, new_ip=1.0, same_file_1h=1)
    assert fraud.score_activity(normal)["anomaly_score"] < fraud.LOW
    b = fraud.score_activity(burst)
    assert b["anomaly_score"] >= fraud.HIGH and b["reasons"]


def test_report_status_floors():
    assert fraud.build_report(doc_analysis=None, status="Modified")["risk_level"] == "High"
    assert fraud.build_report(doc_analysis=None, status="Unknown")["risk_level"] == "Medium"
    assert fraud.build_report(doc_analysis=None, status="Verified")["risk_level"] == "Low"
