from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("homes.id"), index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10), default="FC")
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    payment_method: Mapped[str] = mapped_column(String(80))
    provider_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payment_provider: Mapped[str] = mapped_column(String(80), default="manual")
    provider_deposit_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        index=True,
    )
    provider_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    callback_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    home: Mapped["Home"] = relationship("Home", back_populates="transactions")
