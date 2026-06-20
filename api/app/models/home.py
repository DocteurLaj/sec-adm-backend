from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Home(Base):
    __tablename__ = "homes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="RDC")
    currency: Mapped[str] = mapped_column(String(10), default="FC")
    energy_price_per_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        default=Decimal("500.0000"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    client: Mapped["Client"] = relationship("Client", back_populates="homes")
    meter: Mapped["Meter"] = relationship(
        "Meter",
        back_populates="home",
        uselist=False,
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="home",
        cascade="all, delete-orphan",
    )


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("homes.id"), unique=True, index=True)
    meter_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    energy_balance_kwh: Mapped[Decimal] = mapped_column(
        Numeric(16, 6),
        default=Decimal("0.000000"),
    )
    total_loaded_kwh: Mapped[Decimal] = mapped_column(
        Numeric(16, 6),
        default=Decimal("0.000000"),
    )
    total_paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
    )
    total_consumed_kwh: Mapped[Decimal] = mapped_column(
        Numeric(16, 6),
        default=Decimal("0.000000"),
    )
    last_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), default="active")
    last_loaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    home: Mapped["Home"] = relationship("Home", back_populates="meter")
