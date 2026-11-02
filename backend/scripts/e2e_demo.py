"""End-to-end demonstration of the Sentinel Vault workflow against a running API.
Usage: python scripts/e2e_demo.py [http://localhost:8000]"""
import io
import random
import sys
import uuid

import httpx
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, ".")
from app.fraud import synth  # noqa: E402

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000") + "/api"
ADMIN = ("admin@sentinel-vault.dev", "ChangeMe!Admin123")
PW = "Str0ng!Passw0rd"
tag = uuid.uuid4().hex[:6]
c = httpx.Client(timeout=120)


def step(n, msg): print(f"\n[{n}] {msg}")


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(email, pw):
    r = c.post(f"{API}/auth/login", json={"email": email, "password": pw}); r.raise_for_status()
    return r.json()["access_token"]


def jpeg(img, q=92):
    b = io.BytesIO(); img.save(b, "JPEG", quality=q); return b.getvalue()


def main():
    admin = login(*ADMIN)
    step(1, "University registers as issuer; admin approves (wallet provisioned + authorised on-chain)")
    uni_email, emp_email = f"uni-{tag}@example.edu", f"hr-{tag}@example.com"
    r = c.post(f"{API}/auth/register", json={"email": uni_email, "name": "Registrar", "password": PW, "role": "issuer", "organization": "Northbridge University"}); r.raise_for_status()
    uid = r.json()["user"]["id"]
    r = c.post(f"{API}/admin/users/{uid}/approve-issuer", json={"issuer_name": "Northbridge University"}, headers=auth(admin)); r.raise_for_status()
    print("   issuer address:", r.json()["issuer_address"], "tx:", r.json()["tx_hash"])
    c.post(f"{API}/auth/register", json={"email": emp_email, "name": "Employer HR", "password": PW, "role": "verifier"}).raise_for_status()
    uni, emp = login(uni_email, PW), login(emp_email, PW)

    step(2, "University uploads certificate (encrypted AES-256-GCM, SHA-256, registered on blockchain)")
    rng = random.Random(int(tag, 16))
    cert = synth.render(rng, name="Jordan Rivers", grade="First Class")
    original = jpeg(cert)
    r = c.post(f"{API}/documents", headers=auth(uni), files={"file": ("certificate.jpg", original, "image/jpeg")},
               data={"title": f"BSc Certificate {tag}", "doc_type": "certificate", "register_on_chain": "true"}); r.raise_for_status()
    doc = r.json()
    print("   sha256:", doc["sha256"], "| status:", doc["status"], "| tx:", doc["transactions"][0]["tx_hash"], "block", doc["transactions"][0]["block_number"])
    print("   upload fraud report:", doc["fraud_report"]["risk_level"], round(doc["fraud_report"]["risk_score"], 3))

    step(3, "Employer verifies the ORIGINAL certificate")
    r = c.post(f"{API}/verify", headers=auth(emp), files={"file": ("cert.jpg", original, "image/jpeg")}); r.raise_for_status()
    v = r.json(); print("   result:", v["status"], "| risk:", v["fraud_report"]["risk_level"], "|", v["details"]["notes"])
    assert v["status"] == "Verified", v

    step(4, "Employer verifies a MODIFIED certificate (grade forged)")
    forged = cert.copy(); d = ImageDraw.Draw(forged)
    d.rectangle((300, 420, 600, 462), fill=(255, 255, 255)); d.text((450, 440), "Grade: Distinction", fill=(10, 10, 10), anchor="mm")
    r = c.post(f"{API}/verify", headers=auth(emp), files={"file": ("cert-edited.jpg", jpeg(forged, 88), "image/jpeg")}); r.raise_for_status()
    v = r.json(); print("   result:", v["status"], "| similarity:", v["similarity"], "|", v["details"]["notes"])
    print("   risk:", v["fraud_report"]["risk_level"], round(v["fraud_report"]["risk_score"], 3))
    for x in v["fraud_report"]["reasons"]: print("     -", x["source"], ":", x["text"])
    assert v["status"] == "Modified", v

    step(5, "Unrelated document")
    other = synth.render(random.Random(999), name="Nobody Else")
    r = c.post(f"{API}/verify", headers=auth(emp), files={"file": ("x.jpg", jpeg(other), "image/jpeg")}); r.raise_for_status()
    print("   result:", r.json()["status"])

    step(6, "Issuer revokes the certificate; re-verification")
    c.post(f"{API}/documents/{doc['id']}/revoke", headers=auth(uni), json={"reason": "Degree rescinded"}).raise_for_status()
    r = c.post(f"{API}/verify", headers=auth(emp), files={"file": ("cert.jpg", original, "image/jpeg")}); r.raise_for_status()
    print("   result:", r.json()["status"], "| risk:", r.json()["fraud_report"]["risk_level"])
    assert r.json()["status"] == "Revoked"

    step(7, "Decrypt round-trip + dashboard")
    r = c.get(f"{API}/documents/{doc['id']}/download", headers=auth(uni)); assert r.content == original; print("   downloaded file matches original bytes")
    r = c.get(f"{API}/dashboard", headers=auth(admin)); print("   totals:", r.json()["totals"])
    r = c.get(f"{API}/chain/transactions", headers=auth(admin)); print("   chain tx:", r.json()["total"])
    print("\nALL CHECKS PASSED")


main()
