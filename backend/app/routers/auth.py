from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import clear_throttle, client_ip, create_token, current_user, hash_password, throttle_login, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(pattern="^(owner|verifier|issuer)$")
    organization: str | None = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "status": u.status,
            "organization": u.organization, "created_at": u.created_at}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    # Issuer accounts need admin approval (which provisions the on-chain issuer identity).
    status = "pending" if body.role == "issuer" else "active"
    u = User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password),
             role=body.role, status=status, organization=body.organization)
    db.add(u); db.commit()
    return {"user": user_out(u), "message": "Awaiting administrator approval" if status == "pending" else "Registered"}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{body.email.lower()}|{client_ip(request)}"
    throttle_login(key)
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if u.status == "pending":
        raise HTTPException(403, "Account is awaiting administrator approval")
    if u.status != "active":
        raise HTTPException(403, "Account disabled")
    clear_throttle(key)
    return {"access_token": create_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
