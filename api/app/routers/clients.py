from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import current_admin, current_client
from app.core.email import send_email_verification
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.models.admin import Admin
from app.models.auth import EmailVerificationToken
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.core.security import hash_token, new_opaque_token, utc_now
from datetime import timedelta

router = APIRouter(prefix="/clients", tags=["clients"])


def client_out(client: Client) -> dict:
    return {
        "id": client.id,
        "email": client.email,
        "phone": client.phone,
        "fullName": client.full_name,
        "isActive": client.is_active,
        "emailVerified": client.email_verified,
        "createdAt": client.created_at,
    }


def _send_client_verification(db: Session, client: Client) -> None:
    settings = get_settings()
    token = new_opaque_token()
    db.add(
        EmailVerificationToken(
            actor_type="client",
            actor_id=client.id,
            token_hash=hash_token(token),
            expires_at=utc_now()
            + timedelta(hours=settings.email_verification_token_expire_hours),
        )
    )
    db.commit()
    send_email_verification(
        client.email,
        f"{settings.frontend_url}/verify-email?actorType=client&token={token}",
    )


@router.get("")
def list_clients(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return [client_out(client) for client in db.query(Client).order_by(Client.id.desc())]


@router.post("", status_code=201)
def create_client(
    payload: ClientCreate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    if db.query(Client).filter(Client.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Client email already exists")
    if payload.phone and db.query(Client).filter(Client.phone == payload.phone).first():
        raise HTTPException(status_code=409, detail="Client phone already exists")
    client = Client(
        email=payload.email,
        phone=payload.phone,
        full_name=payload.fullName,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    _send_client_verification(db, client)
    return client_out(client)


@router.get("/me")
def my_client_profile(client: Annotated[Client, Depends(current_client)]):
    return client_out(client)


@router.get("/{client_id}")
def get_client(
    client_id: int,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_out(client)


@router.patch("/{client_id}")
def update_client(
    client_id: int,
    payload: ClientUpdate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    changes = payload.model_dump(exclude_unset=True)
    if "phone" in changes:
        client.phone = changes["phone"]
    if "fullName" in changes:
        client.full_name = changes["fullName"]
    if "isActive" in changes:
        client.is_active = changes["isActive"]
    db.commit()
    db.refresh(client)
    return client_out(client)
