from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import current_admin
from app.core.email import send_email_verification
from app.core.security import hash_password, hash_token, new_opaque_token, utc_now
from app.db.session import get_db
from app.models.admin import Admin
from app.models.auth import EmailVerificationToken
from datetime import timedelta

router = APIRouter(prefix="/admins", tags=["admins"])


class AdminCreate(BaseModel):
    email: str
    fullName: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role: str = "admin"


def admin_out(admin: Admin) -> dict:
    return {
        "id": admin.id,
        "email": admin.email,
        "fullName": admin.full_name,
        "role": admin.role,
        "isActive": admin.is_active,
        "emailVerified": admin.email_verified,
        "createdAt": admin.created_at,
    }


def _send_admin_verification(db: Session, admin: Admin) -> None:
    settings = get_settings()
    token = new_opaque_token()
    db.add(
        EmailVerificationToken(
            actor_type="admin",
            actor_id=admin.id,
            token_hash=hash_token(token),
            expires_at=utc_now()
            + timedelta(hours=settings.email_verification_token_expire_hours),
        )
    )
    db.commit()
    send_email_verification(
        admin.email,
        f"{settings.frontend_url}/verify-email?actorType=admin&token={token}",
    )


@router.get("")
def list_admins(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return [admin_out(admin) for admin in db.query(Admin).order_by(Admin.id.desc()).all()]


@router.post("", status_code=201)
def create_admin(
    payload: AdminCreate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    if db.query(Admin).filter(Admin.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Admin email already exists")
    admin = Admin(
        email=payload.email,
        full_name=payload.fullName,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    _send_admin_verification(db, admin)
    return admin_out(admin)
