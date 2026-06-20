from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.push import PushToken


class PushUnavailable(Exception):
    pass


@lru_cache
def _firebase_messaging():
    settings = get_settings()
    if not settings.firebase_credentials_path:
        raise PushUnavailable("Firebase credentials are not configured")
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError as exc:
        raise PushUnavailable("firebase-admin is not installed") from exc

    if not firebase_admin._apps:
        credential = credentials.Certificate(settings.firebase_credentials_path)
        options = (
            {"projectId": settings.firebase_project_id}
            if settings.firebase_project_id
            else None
        )
        firebase_admin.initialize_app(credential, options=options)
    return messaging


def send_to_client(
    db: Session,
    client_id: int,
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    tokens = (
        db.query(PushToken)
        .filter(PushToken.client_id == client_id, PushToken.is_active.is_(True))
        .all()
    )
    if not tokens:
        return 0
    messaging = _firebase_messaging()
    sent = 0
    payload_data = data or {}
    for token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=payload_data,
            token=token.token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="sec_alerts",
                    sound="default",
                ),
            ),
        )
        try:
            messaging.send(message)
            sent += 1
        except Exception:
            token.is_active = False
    db.commit()
    return sent


def try_send_to_client(
    db: Session,
    client_id: int,
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    try:
        return send_to_client(db, client_id, title=title, body=body, data=data)
    except PushUnavailable:
        return 0
