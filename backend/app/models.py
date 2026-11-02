from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # admin|issuer|owner|verifier
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|pending|disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Issuer(Base):
    __tablename__ = "issuers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    eth_address: Mapped[str] = mapped_column(String(42), unique=True)
    wrapped_private_key: Mapped[str] = mapped_column(Text)  # AES-256-GCM wrapped with master key
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    issuer_id: Mapped[int | None] = mapped_column(ForeignKey("issuers.id"))
    title: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(50), default="other")
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(255))
    wrapped_key: Mapped[str] = mapped_column(Text)  # per-file data key wrapped by master key
    ipfs_cid: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="stored")  # stored|registered|revoked
    minhash: Mapped[list | None] = mapped_column(JSON)  # privacy-preserving text fingerprint
    phash: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    issuer: Mapped[Issuer | None] = relationship()


class DocumentShare(Base):
    __tablename__ = "document_shares"
    __table_args__ = (UniqueConstraint("document_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class ChainTransaction(Base):
    __tablename__ = "chain_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str] = mapped_column(String(66), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(30))  # register|revoke|add_issuer|remove_issuer
    block_number: Mapped[int] = mapped_column(Integer)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    from_address: Mapped[str] = mapped_column(String(42))
    to_address: Mapped[str] = mapped_column(String(42))
    doc_hash: Mapped[str | None] = mapped_column(String(64))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    gas_used: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))  # success|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    verifier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))  # Verified|Modified|Unknown|Revoked
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    claimed_document_id: Mapped[int | None] = mapped_column(Integer)
    similarity: Mapped[float | None] = mapped_column(Float)
    issuer_address: Mapped[str | None] = mapped_column(String(42))
    issuer_authorized: Mapped[bool | None] = mapped_column(Boolean)
    chain_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    verifier: Mapped[User] = relationship()


class FraudReport(Base):
    __tablename__ = "fraud_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(20))  # document|verification
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    verification_id: Mapped[int | None] = mapped_column(ForeignKey("verifications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    risk_level: Mapped[str] = mapped_column(String(10), index=True)  # Low|Medium|High
    risk_score: Mapped[float] = mapped_column(Float)
    document_score: Mapped[float | None] = mapped_column(Float)  # Random Forest probability
    activity_score: Mapped[float | None] = mapped_column(Float)  # Isolation Forest anomaly percentile
    reasons: Mapped[list] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    model_info: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
