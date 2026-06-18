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
    result = db.execute(text("SHOW COLUMNS FROM clients LIKE 'pending_email'"))
    if result.fetchone() is None:
        db.execute(
            text("ALTER TABLE clients ADD COLUMN pending_email VARCHAR(255) NULL")
        )
    result = db.execute(
        text("SHOW COLUMNS FROM email_verification_tokens LIKE 'code_hash'")
    )
    if result.fetchone() is None:
        db.execute(
            text(
                "ALTER TABLE email_verification_tokens "
                "ADD COLUMN code_hash VARCHAR(128) NULL"
            )
        )
    result = db.execute(
        text("SHOW COLUMNS FROM email_verification_tokens LIKE 'target_email'")
    )
    if result.fetchone() is None:
        db.execute(
            text(
                "ALTER TABLE email_verification_tokens "
                "ADD COLUMN target_email VARCHAR(255) NULL"
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
