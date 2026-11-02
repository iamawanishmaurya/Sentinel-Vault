"""Seed demo data through the REAL pipeline (API -> encryption -> blockchain -> fraud models).
Documents are synthetic certificates (see app/fraud/synth.py). After creation, record timestamps are spread
over the last 14 days (database only) so dashboard charts have a history. Usage: python scripts/seed_demo.py [api_url]"""
import io
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx
from PIL import ImageDraw

sys.path.insert(0, ".")
from app.fraud import synth  # noqa: E402

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000") + "/api"
PW = "Demo!Passw0rd123"
c = httpx.Client(timeout=180)
rng = random.Random(2026)
H = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731


def login(e, p=PW):
    r = c.post(f"{API}/auth/login", json={"email": e, "password": p}); r.raise_for_status(); return r.json()["access_token"]


def jpeg(img, q=92):
    b = io.BytesIO(); img.save(b, "JPEG", quality=q); return b.getvalue()


def ensure(email, name, role, org):
    r = c.post(f"{API}/auth/register", json={"email": email, "name": name, "password": PW, "role": role, "organization": org})
    if r.status_code not in (201, 409):
        r.raise_for_status()
    return r.json()["user"]["id"] if r.status_code == 201 else None


admin = login("admin@sentinel-vault.dev", "ChangeMe!Admin123")
issuers = [("registrar@northbridge.example.edu", "Northbridge University"), ("records@eastgate.example.edu", "Eastgate Institute of Technology"), ("office@crestview.example.edu", "Crestview College")]
for email, org in issuers:
    uid = ensure(email, f"{org} Registrar", "issuer", org)
    if uid:
        c.post(f"{API}/admin/users/{uid}/approve-issuer", json={"issuer_name": org}, headers=H(admin)).raise_for_status()
for email, name in [("maya.owner@example.com", "Maya Chen"), ("omar.owner@example.com", "Omar Haddad")]:
    ensure(email, name, "owner", None)
for email, name, org in [("hr@acme.example.com", "Acme HR", "Acme Corp"), ("talent@globex.example.com", "Globex Talent", "Globex")]:
    ensure(email, name, "verifier", org)
iss_tok = [login(e) for e, _ in issuers]
owner_tok = [login("maya.owner@example.com"), login("omar.owner@example.com")]
ver_tok = [login("hr@acme.example.com"), login("talent@globex.example.com")]

people = ["Aarav Mehta", "Sofia Alvarez", "Liam O'Connor", "Mei Tanaka", "Noah Becker", "Amara Okafor", "Elena Petrova", "Daniel Kim", "Priya Nair", "Lucas Moreau"]
grades = ["First Class", "Distinction", "A", "B+", "Merit"]
docs = []
for i, who in enumerate(people):
    img = synth.render(random.Random(500 + i), name=who, grade=rng.choice(grades))
    data = jpeg(img)
    tok = iss_tok[i % 3]
    r = c.post(f"{API}/documents", headers=H(tok), files={"file": (f"{who.replace(' ', '_')}_certificate.jpg", data, "image/jpeg")},
               data={"title": f"Certificate – {who}", "doc_type": "certificate", "register_on_chain": "true"})
    r.raise_for_status(); docs.append((r.json(), img, data, tok))
    print("registered", who, r.json()["transactions"][0]["tx_hash"][:14])
# a few unregistered documents held by owners
for i, tok in enumerate(owner_tok):
    img = synth.render(random.Random(900 + i), name=["Maya Chen", "Omar Haddad"][i])
    c.post(f"{API}/documents", headers=H(tok), files={"file": ("personal_copy.jpg", jpeg(img), "image/jpeg")},
           data={"title": "Personal degree copy", "doc_type": "certificate"}).raise_for_status()
# share one with a verifier
c.post(f"{API}/documents/{docs[0][0]['id']}/share", headers=H(iss_tok[0]), json={"email": "hr@acme.example.com", "expires_days": 14})


def verify(tok, name, data):
    r = c.post(f"{API}/verify", headers=H(tok), files={"file": (name, data, "image/jpeg")}); r.raise_for_status(); return r.json()


def forge(img, text):
    f = img.copy(); d = ImageDraw.Draw(f)
    d.rectangle((300, 420, 600, 462), fill=f.getpixel((310, 425))); d.text((450, 440), text, fill=(10, 10, 10), anchor="mm"); return jpeg(f, 88)


for i, (doc, img, data, tok) in enumerate(docs):
    v = ver_tok[i % 2]
    verify(v, doc["filename"], data)                       # genuine
    if i % 3 == 0:
        verify(ver_tok[(i + 1) % 2], "scan.jpg", data)    # second employer
    if i % 2 == 1:
        verify(v, "edited.jpg", forge(img, "Grade: First Class"))   # forged grade
for k in range(3):
    verify(ver_tok[k % 2], "random.jpg", jpeg(synth.render(random.Random(7000 + k), name="Unregistered Person")))
# revoke two
for doc, img, data, tok in (docs[2], docs[6]):
    c.post(f"{API}/documents/{doc['id']}/revoke", headers=H(tok), json={"reason": "Degree rescinded after academic misconduct review"}).raise_for_status()
    verify(ver_tok[0], "cert.jpg", data)
# a burst of probing from one verifier to exercise the Isolation Forest
for k in range(7):
    verify(ver_tok[1], f"probe{k}.jpg", forge(docs[1][1], f"Grade: A{k}"))

# --- spread timestamps over the last 14 days (DB only) ---
from sqlalchemy import select, text  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app import models  # noqa: E402

with SessionLocal() as db:
    now = datetime.now(timezone.utc)
    vs = db.scalars(select(models.Verification).order_by(models.Verification.id)).all()
    probe_start = len(vs) - 7
    for n, v in enumerate(vs):
        if n >= probe_start:
            continue  # keep the probing burst "now"
        v.created_at = now - timedelta(days=rng.uniform(0.2, 13.5), hours=rng.uniform(0, 6))
    db.flush()
    for r in db.scalars(select(models.FraudReport)):
        src = db.get(models.Verification, r.verification_id) if r.verification_id else db.get(models.Document, r.document_id)
        if src is not None:
            r.created_at = src.created_at
    for d in db.scalars(select(models.Document)):
        d.created_at = now - timedelta(days=rng.uniform(13.6, 14.5)) if d.status != "stored" else d.created_at
    db.commit()
print("seed complete")
