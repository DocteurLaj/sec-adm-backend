from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MeterCreate(BaseModel):
    meterNumber: str = Field(min_length=3, max_length=80)
    provider: str | None = None
    initialEnergyKwh: Decimal = Decimal("0.000")


class HomeCreate(BaseModel):
    clientId: int
    name: str = Field(min_length=2, max_length=160)
    address: str | None = None
    city: str | None = None
    country: str = "RDC"
    currency: str = "FC"
    energyPricePerKwh: Decimal = Decimal("500.0000")
    meter: MeterCreate


class HomeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str | None = None
    energyPricePerKwh: Decimal | None = None


class MeterOut(BaseModel):
    id: int
    meterNumber: str
    provider: str | None
    energyBalanceKwh: Decimal
    totalLoadedKwh: Decimal
    totalPaidAmount: Decimal
    status: str
    lastLoadedAt: datetime | None

    model_config = {"from_attributes": True}


class HomeOut(BaseModel):
    id: int
    clientId: int
    name: str
    address: str | None
    city: str | None
    country: str
    currency: str
    energyPricePerKwh: Decimal
    meter: MeterOut | None
    createdAt: datetime

    model_config = {"from_attributes": True}
