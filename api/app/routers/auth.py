from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import current_admin, current_client, current_token
from app.core.email import send_email_verification, send_password_reset_email
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_email_code,
    new_opaque_token,
    utc_now,
    verify_password,
)
from app.db.session import get_db
from app.models.admin import Admin
from app.models.auth import (
    AuthAuditLog,
    EmailVerificationToken,
    PasswordResetToken,
    RefreshSession,
)
from app.models.client import Client
from app.models.home import Home, Meter
from app.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ClientRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _find_actor(db: Session, actor_type: str, email: str | None = None, actor_id: int | None = None):
    model = Admin if actor_type == "admin" else Client if actor_type == "client" else None
    if model is None:
        raise HTTPException(status_code=400, detail="actorType must be admin or client")
    if email is not None:
        return db.query(model).filter(model.email == email).first()
    if actor_id is not None:
        return db.get(model, actor_id)
    return None


def _audit(
    db: Session,
    request: Request,
    event_type: str,
    actor_type: str | None = None,
    actor_id: int | None = None,
    email: str | None = None,
) -> None:
    db.add(
        AuthAuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            email=email,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()


def _create_refresh_session(db: Session, actor_type: str, actor_id: int) -> str:
    settings = get_settings()
    refresh_token = new_opaque_token()
    db.add(
        RefreshSession(
            actor_type=actor_type,
            actor_id=actor_id,
            token_hash=hash_token(refresh_token),
            expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.commit()
    return refresh_token


def _token_response(db: Session, actor, actor_type: str) -> dict:
    role = actor.role if actor_type == "admin" else "client"
    return {
        "accessToken": create_access_token(str(actor.id), role),
        "refreshToken": _create_refresh_session(db, actor_type, actor.id),
        "role": role,
        "userId": actor.id,
        "email": actor.email,
    }


def _create_reset_token(db: Session, actor_type: str, actor_id: int) -> str:
    settings = get_settings()
    token = new_opaque_token()
    db.add(
        PasswordResetToken(
            actor_type=actor_type,
            actor_id=actor_id,
            token_hash=hash_token(token),
            expires_at=utc_now()
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
    )
    db.commit()
    return token


def _create_verification_token(
    db: Session,
    actor_type: str,
    actor_id: int,
    target_email: str,
) -> tuple[str, str]:
    settings = get_settings()
    token = new_opaque_token()
    code = new_email_code()
    db.add(
        EmailVerificationToken(
            actor_type=actor_type,
            actor_id=actor_id,
            token_hash=hash_token(token),
            code_hash=hash_token(code),
            target_email=target_email,
            expires_at=utc_now()
            + timedelta(hours=settings.email_verification_token_expire_hours),
        )
    )
    db.commit()
    return token, code


def _send_verification_for_actor(
    db: Session,
    actor,
    actor_type: str,
    target_email: str | None = None,
) -> None:
    email = (target_email or actor.email).strip().lower()
    token, code = _create_verification_token(db, actor_type, actor.id, email)
    verification_url = (
        f"{get_settings().frontend_url}/verify-email"
        f"?actorType={actor_type}&token={token}"
    )
    send_email_verification(email, verification_url, code)


@router.post("/client/register", response_model=TokenResponse, status_code=201)
def client_register(
    payload: ClientRegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    email = payload.email.strip().lower()
    phone = payload.phone.strip() if payload.phone else None
    full_name = payload.fullName.strip()
    if len(full_name) < 2:
        raise HTTPException(status_code=422, detail="fullName is too short")
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="password must contain at least 8 characters")
    if db.query(Client).filter(Client.email == email).first():
        raise HTTPException(status_code=409, detail="Client email already exists")
    if phone and db.query(Client).filter(Client.phone == phone).first():
        raise HTTPException(status_code=409, detail="Client phone already exists")
    meter_number = payload.meterNumber.strip() if payload.meterNumber else None
    if meter_number and db.query(Meter).filter(Meter.meter_number == meter_number).first():
        raise HTTPException(status_code=409, detail="Meter number already exists")

    client = Client(
        email=email,
        phone=phone,
        full_name=full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
        email_verified=False,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    if meter_number:
        home = Home(
            client_id=client.id,
            name="Maison principale",
            address=payload.address,
            city=None,
            country="RDC",
            currency="FC",
            energy_price_per_kwh=Decimal("500.0000"),
        )
        home.meter = Meter(
            meter_number=meter_number,
            provider=payload.contractType or "SEC",
            energy_balance_kwh=Decimal("0.000"),
            total_loaded_kwh=Decimal("0.000"),
        )
        db.add(home)
        db.commit()
    _send_verification_for_actor(db, client, "client")
    _audit(db, request, "client_registered", "client", client.id, client.email)
    return _token_response(db, client, "client")


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    admin = db.query(Admin).filter(Admin.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        _audit(db, request, "admin_login_failed", "admin", email=payload.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Admin disabled")
    _audit(db, request, "admin_login_success", "admin", admin.id, admin.email)
    return _token_response(db, admin, "admin")


@router.post("/client/login", response_model=TokenResponse)
def client_login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    client = db.query(Client).filter(Client.email == payload.email).first()
    if client is None or not verify_password(payload.password, client.password_hash):
        _audit(db, request, "client_login_failed", "client", email=payload.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not client.is_active:
        raise HTTPException(status_code=403, detail="Client disabled")
    _audit(db, request, "client_login_success", "client", client.id, client.email)
    return _token_response(db, client, "client")


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == hash_token(payload.refreshToken))
        .first()
    )
    if session is None or session.revoked_at is not None or session.expires_at <= utc_now():
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    actor = _find_actor(db, session.actor_type, actor_id=session.actor_id)
    if actor is None or not actor.is_active:
        raise HTTPException(status_code=401, detail="Account not found")
    return _token_response(db, actor, session.actor_type)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Annotated[Session, Depends(get_db)]):
    if payload.refreshToken:
        session = (
            db.query(RefreshSession)
            .filter(RefreshSession.token_hash == hash_token(payload.refreshToken))
            .first()
        )
        if session and session.revoked_at is None:
            session.revoked_at = utc_now()
            db.commit()
    return {"message": "Logged out"}


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    actor = _find_actor(db, payload.actorType, email=payload.email)
    if actor is not None and actor.is_active:
        token = _create_reset_token(db, payload.actorType, actor.id)
        reset_url = (
            f"{get_settings().frontend_url}/reset-password"
            f"?actorType={payload.actorType}&token={token}"
        )
        send_password_reset_email(actor.email, reset_url)
        _audit(db, request, "password_reset_requested", payload.actorType, actor.id, actor.email)
    else:
        _audit(db, request, "password_reset_requested_unknown", payload.actorType, email=payload.email)
    return {"message": "If the account exists, a reset email has been sent"}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_token(payload.token))
        .first()
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    actor = _find_actor(db, reset.actor_type, actor_id=reset.actor_id)
    if actor is None:
        raise HTTPException(status_code=400, detail="Account not found")
    actor.password_hash = hash_password(payload.newPassword)
    reset.used_at = utc_now()
    db.query(RefreshSession).filter(
        RefreshSession.actor_type == reset.actor_type,
        RefreshSession.actor_id == reset.actor_id,
        RefreshSession.revoked_at.is_(None),
    ).update({"revoked_at": utc_now()})
    db.commit()
    _audit(db, request, "password_reset_completed", reset.actor_type, actor.id, actor.email)
    return {"message": "Password updated"}


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    token: Annotated[dict, Depends(current_token)],
    db: Annotated[Session, Depends(get_db)],
):
    actor_type = "client" if token.get("role") == "client" else "admin"
    actor = _find_actor(db, actor_type, actor_id=int(token["sub"]))
    if actor is None or not verify_password(payload.currentPassword, actor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid current password")
    actor.password_hash = hash_password(payload.newPassword)
    db.commit()
    _audit(db, request, "password_changed", actor_type, actor.id, actor.email)
    return {"message": "Password changed"}


@router.post("/change-email", response_model=MessageResponse)
def change_email(
    payload: ChangeEmailRequest,
    request: Request,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    new_email = payload.newEmail.strip().lower()
    if "@" not in new_email or "." not in new_email:
        raise HTTPException(status_code=422, detail="Invalid email")
    if not verify_password(payload.currentPassword, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid current password")
    existing = db.query(Client).filter(Client.email == new_email).first()
    if existing and existing.id != client.id:
        raise HTTPException(status_code=409, detail="Email already exists")
    if new_email == client.email:
        raise HTTPException(status_code=422, detail="New email must be different")

    client.pending_email = new_email
    db.commit()
    _send_verification_for_actor(db, client, "client", target_email=new_email)
    _audit(db, request, "email_change_requested", "client", client.id, new_email)
    return {"message": "Verification code sent to the new email"}


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    query = db.query(EmailVerificationToken)
    if payload.token:
        verification = query.filter(
            EmailVerificationToken.token_hash == hash_token(payload.token)
        ).first()
    elif payload.email and payload.code:
        verification = (
            query.filter(
                EmailVerificationToken.actor_type == payload.actorType,
                EmailVerificationToken.target_email == payload.email.strip().lower(),
                EmailVerificationToken.code_hash == hash_token(payload.code.strip()),
            )
            .order_by(EmailVerificationToken.id.desc())
            .first()
        )
    else:
        raise HTTPException(status_code=422, detail="token or email/code is required")
    if (
        verification is None
        or verification.used_at is not None
        or verification.expires_at <= utc_now()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    actor = _find_actor(db, verification.actor_type, actor_id=verification.actor_id)
    if actor is None:
        raise HTTPException(status_code=400, detail="Account not found")
    if (
        verification.actor_type == "client"
        and isinstance(actor, Client)
        and actor.pending_email
        and verification.target_email == actor.pending_email
    ):
        actor.email = actor.pending_email
        actor.pending_email = None
    actor.email_verified = True
    verification.used_at = utc_now()
    db.commit()
    _audit(db, request, "email_verified", verification.actor_type, actor.id, actor.email)
    return {"message": "Email verified"}


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    email = payload.email.strip().lower()
    actor = _find_actor(db, payload.actorType, email=email)
    if actor is None and payload.actorType == "client":
        actor = db.query(Client).filter(Client.pending_email == email).first()
    is_pending_email = (
        payload.actorType == "client"
        and isinstance(actor, Client)
        and actor.pending_email == email
    )
    if actor is not None and actor.is_active and (is_pending_email or not actor.email_verified):
        _send_verification_for_actor(db, actor, payload.actorType, target_email=email)
        _audit(db, request, "email_verification_sent", payload.actorType, actor.id, email)
    return {"message": "If verification is required, an email has been sent"}


@router.get("/admin/me")
def admin_me(admin: Annotated[Admin, Depends(current_admin)]):
    return {
        "id": admin.id,
        "email": admin.email,
        "fullName": admin.full_name,
        "role": admin.role,
        "isActive": admin.is_active,
        "emailVerified": admin.email_verified,
    }


@router.get("/client/me")
def client_me(client: Annotated[Client, Depends(current_client)]):
    return {
        "id": client.id,
        "email": client.email,
        "pendingEmail": client.pending_email,
        "phone": client.phone,
        "fullName": client.full_name,
        "isActive": client.is_active,
        "emailVerified": client.email_verified,
    }
