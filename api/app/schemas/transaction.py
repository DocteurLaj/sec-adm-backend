from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class EnergyRechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    paymentMethod: str = Field(min_length=2, max_length=80)
    providerReference: str | None = None


class PawaPayRechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payerPhone: str = Field(min_length=8, max_length=40)
    correspondent: str | None = Field(default=None, max_length=80)


class TransactionOut(BaseModel):
    id: int
    reference: str
    clientId: int
    homeId: int
    meterId: int
    amount: Decimal
    currency: str
    energyKwh: Decimal
    paymentMethod: str
    providerReference: str | None
    paymentProvider: str
    providerDepositId: str | None
    providerStatus: str | None
    payerPhone: str | None
    failureReason: str | None
    status: str
    createdAt: datetime
    paidAt: datetime | None

    model_config = {"from_attributes": True}
