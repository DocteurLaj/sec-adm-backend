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
    transaction_columns = {
        "payment_provider": "ALTER TABLE transactions ADD COLUMN payment_provider VARCHAR(80) NOT NULL DEFAULT 'manual'",
        "provider_deposit_id": "ALTER TABLE transactions ADD COLUMN provider_deposit_id VARCHAR(160) NULL",
        "provider_status": "ALTER TABLE transactions ADD COLUMN provider_status VARCHAR(80) NULL",
        "payer_phone": "ALTER TABLE transactions ADD COLUMN payer_phone VARCHAR(40) NULL",
        "failure_reason": "ALTER TABLE transactions ADD COLUMN failure_reason VARCHAR(255) NULL",
        "callback_payload": "ALTER TABLE transactions ADD COLUMN callback_payload TEXT NULL",
    }
    for column, statement in transaction_columns.items():
        result = db.execute(text(f"SHOW COLUMNS FROM transactions LIKE '{column}'"))
        if result.fetchone() is None:
            db.execute(text(statement))
    result = db.execute(text("SHOW INDEX FROM transactions WHERE Key_name = 'ix_transactions_provider_deposit_id'"))
    if result.fetchone() is None:
        db.execute(
            text(
                "CREATE INDEX ix_transactions_provider_deposit_id "
                "ON transactions (provider_deposit_id)"
            )
        )
    meter_columns = {
        "total_consumed_kwh": "ALTER TABLE meters ADD COLUMN total_consumed_kwh DECIMAL(14, 3) NOT NULL DEFAULT 0.000",
        "last_consumed_at": "ALTER TABLE meters ADD COLUMN last_consumed_at DATETIME NULL",
    }
    for column, statement in meter_columns.items():
        result = db.execute(text(f"SHOW COLUMNS FROM meters LIKE '{column}'"))
        if result.fetchone() is None:
            db.execute(text(statement))
    db.execute(text("ALTER TABLE meters MODIFY energy_balance_kwh DECIMAL(16, 6) NOT NULL DEFAULT 0.000000"))
    db.execute(text("ALTER TABLE meters MODIFY total_loaded_kwh DECIMAL(16, 6) NOT NULL DEFAULT 0.000000"))
    db.execute(text("ALTER TABLE meters MODIFY total_consumed_kwh DECIMAL(16, 6) NOT NULL DEFAULT 0.000000"))
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
