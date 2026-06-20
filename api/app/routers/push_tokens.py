from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import current_client
from app.db.session import get_db
from app.models.client import Client
from app.models.push import PushToken
from app.schemas.common import MessageResponse
from app.schemas.push import PushTokenOut, PushTokenRegister

router = APIRouter(prefix="/push-tokens", tags=["push-tokens"])


def push_token_out(token: PushToken) -> dict:
    return {
        "id": token.id,
        "token": token.token,
        "platform": token.platform,
        "deviceId": token.device_id,
        "isActive": token.is_active,
        "createdAt": token.created_at,
        "updatedAt": token.updated_at,
    }


@router.post("/me", response_model=PushTokenOut, status_code=status.HTTP_201_CREATED)
def register_my_push_token(
    payload: PushTokenRegister,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    existing = db.query(PushToken).filter(PushToken.token == payload.token).first()
    if existing is None:
        existing = PushToken(
            client_id=client.id,
            token=payload.token,
            platform=payload.platform,
            device_id=payload.deviceId,
            is_active=True,
        )
        db.add(existing)
    else:
        existing.client_id = client.id
        existing.platform = payload.platform
        existing.device_id = payload.deviceId
        existing.is_active = True
    db.commit()
    db.refresh(existing)
    return push_token_out(existing)


@router.get("/me", response_model=list[PushTokenOut])
def list_my_push_tokens(
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    tokens = (
        db.query(PushToken)
        .filter(PushToken.client_id == client.id, PushToken.is_active.is_(True))
        .order_by(PushToken.id.desc())
        .all()
    )
    return [push_token_out(token) for token in tokens]


@router.delete("/me/{token_id}", response_model=MessageResponse)
def disable_my_push_token(
    token_id: int,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    token = (
        db.query(PushToken)
        .filter(PushToken.id == token_id, PushToken.client_id == client.id)
        .first()
    )
    if token is not None:
        token.is_active = False
        db.commit()
    return {"message": "Push token disabled"}
