from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.admin import Admin
from app.models.client import Client

bearer_scheme = HTTPBearer(auto_error=True)


def current_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    try:
        return decode_token(credentials.credentials)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from error


def current_admin(
    token: Annotated[dict, Depends(current_token)],
    db: Annotated[Session, Depends(get_db)],
) -> Admin:
    if token.get("role") not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    admin = db.get(Admin, int(token["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin


def current_client(
    token: Annotated[dict, Depends(current_token)],
    db: Annotated[Session, Depends(get_db)],
) -> Client:
    if token.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.get(Client, int(token["sub"]))
    if client is None or not client.is_active:
        raise HTTPException(status_code=401, detail="Client not found")
    return client
