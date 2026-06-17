from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.admin import Admin


def run_light_migrations(db: Session) -> None:
    for table in ("admins", "clients"):
        result = db.execute(text(f"SHOW COLUMNS FROM {table} LIKE 'email_verified'"))
        if result.fetchone() is None:
            db.execute(
                text(
                    f"ALTER TABLE {table} "
                    "ADD COLUMN email_verified BOOL NOT NULL DEFAULT FALSE"
                )
            )
    db.commit()


def seed_first_admin(db: Session) -> None:
    settings = get_settings()
    existing = db.query(Admin).filter(Admin.email == settings.first_admin_email).first()
    if existing:
        if not existing.email_verified:
            existing.email_verified = True
            db.commit()
        return
    admin = Admin(
        email=settings.first_admin_email,
        full_name=settings.first_admin_full_name,
        password_hash=hash_password(settings.first_admin_password),
        role="super_admin",
        is_active=True,
        email_verified=True,
    )
    db.add(admin)
    db.commit()
