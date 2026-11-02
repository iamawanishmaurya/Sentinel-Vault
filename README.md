# Sentinel Vault

Blockchain-based secure document vault with explainable fraud analytics.

Authorised issuers (e.g. universities) upload documents that are **encrypted (AES-256-GCM)**, **fingerprinted (SHA-256)** and **registered on an Ethereum smart contract**. Anyone with a verifier account can upload a file and get **Verified / Modified / Unknown / Revoked**, plus a **Low / Medium / High fraud risk report** that explains itself.

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, Lucide |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, web3.py |
| Database | PostgreSQL 16 |
| Blockchain | Solidity 0.8.24, Hardhat (local network, chain id 31337) |
| Crypto | AES-256-GCM envelope encryption (per-file keys wrapped by a master key), SHA-256 |
| Storage | Encrypted local storage; optional IPFS pinning of the *encrypted* blob |
| Fraud / ML | scikit-learn (Random Forest, Isolation Forest), OpenCV, Tesseract OCR, PyMuPDF |

## Quick start (Docker)

```bash
cp .env.example .env        # change secrets for anything beyond a local demo
docker compose up --build   # first build trains the ML models (~2-4 min)
```

Open <http://localhost:3000> · API docs <http://localhost:8000/docs> · RPC `http://localhost:8545`.
Default admin: `admin@sentinel-vault.dev` / `ChangeMe!Admin123` (set `ADMIN_EMAIL` / `ADMIN_PASSWORD`).

> The Hardhat chain is ephemeral. If you restart only the `hardhat` container, the contract is re-deployed at the same address but on-chain records are lost while the database keeps its rows — use `docker compose down -v` for a clean reset.
> Optional IPFS: `docker compose --profile ipfs up` and set `IPFS_API_URL=http://ipfs:5001`.

## Local development

```bash
# 1. PostgreSQL
docker run -d --name sentinel-pg -e POSTGRES_USER=sentinel -e POSTGRES_PASSWORD=sentinel -e POSTGRES_DB=sentinel -p 5432:5432 postgres:16-alpine

# 2. Blockchain
cd contracts && npm install
npx hardhat test                 # contract tests
npx hardhat node &               # local chain
npm run deploy                   # writes contracts/deployments/DocumentRegistry.json

# 3. Backend (needs tesseract-ocr installed)
cd ../backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head   # migrations
.venv/bin/python -m app.fraud.train   # trains models on synthetic data (auto-runs on first start if missing)
.venv/bin/uvicorn app.main:app --port 8000

# 4. Frontend
cd ../frontend && npm install && npm run dev      # http://localhost:3000 (proxies /api -> :8000)
```

Run the full automated workflow against a live stack: `backend/.venv/bin/python backend/scripts/e2e_demo.py`.
Unit tests: `cd backend && .venv/bin/python -m pytest tests`.

## The demo workflow

1. Register an **Issuer** account ("university"), sign in as admin → **Administration → Approve**. The backend creates an Ethereum wallet for the issuer (private key stored AES-GCM-wrapped), funds it from the Hardhat deployer and calls `addIssuer` on-chain.
2. Issuer uploads a certificate with *Register on blockchain* → encrypted, SHA-256 hashed, `registerDocument(hash)` tx mined; fraud report generated.
3. Register a **Verifier** account (employer) → **Verify** → upload the certificate → **Verified** (issuer, timestamp, tx shown).
4. Upload an edited copy → hash mismatch + content similarity to the registered document → **Modified**, High risk with reasons.
5. Issuer revokes → re-verify → **Revoked**.
6. **Dashboard** and **Blockchain Explorer** show results, transactions, blocks and issuer addresses.

## How it works

**Verification statuses**
- *Verified* — hash is registered on-chain, issuer currently authorised, not revoked.
- *Revoked* — registered but revoked by the issuer/admin.
- *Modified* — hash not on-chain, but the file matches a registered document by content (privacy-preserving MinHash of OCR/PDF text ≥ 0.45, or 64-bit dHash image similarity ≥ 0.88), or the verifier supplied a *claimed document ID* whose hash differs.
- *Unknown* — no record and no similar registered document (or the issuer is no longer authorised).

Similarity fingerprints are stored instead of plaintext, so the database never contains document text.

**Security**
- JWT auth, bcrypt (cost 12), login throttling, role-based access (admin / issuer / owner / verifier), issuer accounts require admin approval.
- Files are magic-byte checked (PDF/JPG/PNG only), size-limited, encrypted before they touch disk; GCM AAD binds ciphertext to its hash; downloads re-verify the hash.
- Only authorised issuers can register; only the issuing authority (or admin) can revoke — enforced in the contract (`onlyIssuer`, `NotAuthorizedToRevoke`).
- On-chain records are immutable, so registered documents cannot be deleted, only revoked.
- Sharing is per-user with an expiry.

**Fraud analytics** (no random or hard-coded scores)
- *Random Forest* on real forensic features: JPEG Error Level Analysis, block-wise noise/sharpness/brightness consistency, OCR confidence and text-height statistics, editor metadata, PDF incremental updates / date mismatch.
- *Isolation Forest* on verification behaviour: bursts, distinct documents, failure ratio, time of day, new IP.
- *Transparent rules* (editor metadata, repeated failures, bursts …) and the verification status. Final score = max of the components; Low < 0.35 ≤ Medium < 0.65 ≤ High. Every report lists the contributing reasons (feature deviations in σ, rule text).
- **Synthetic data notice:** both models are trained on **synthetic** data (programmatically rendered certificates with simulated tampering; simulated normal activity — see `backend/app/fraud/synth.py`). The model card (`/api/analytics/model-card`, shown in the UI) reports holdout and cross-validated ROC-AUC on that synthetic data. These are demonstration-grade; retrain on real labelled documents before relying on them.

## Layout

```
contracts/   Solidity DocumentRegistry, Hardhat tests & deploy script
backend/     FastAPI app (app/), Alembic migrations, ML (app/fraud), tests, e2e demo script
frontend/    Next.js app (landing, auth, dashboard, documents, verify, analytics, explorer, admin)
docker-compose.yml
```

## Production notes

Set strong `JWT_SECRET` and `MASTER_KEY` (losing the master key makes stored documents unrecoverable), replace the Hardhat dev deployer key (`DEPLOYER_PRIVATE_KEY`) and point `RPC_URL` at a real network/node, terminate TLS in front of the app, and keep the master key in a KMS/HSM. Issuer wallets are custodial in this design (server-held, encrypted); a production deployment may prefer issuer-held keys (e.g. MetaMask signing).
