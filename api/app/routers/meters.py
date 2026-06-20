from typing import Annotated
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.home import Meter

router = APIRouter(prefix="/meters", tags=["meters"])


class MeterUpdate(BaseModel):
    provider: str | None = None
    status: str | None = None


class MeterConsumptionSync(BaseModel):
    meterNumber: str = Field(min_length=1, max_length=80)
    consumedKwh: Decimal = Field(gt=Decimal("0.000"))
    measuredAt: datetime | None = None


def meter_out(meter: Meter) -> dict:
    return {
        "id": meter.id,
        "homeId": meter.home_id,
        "meterNumber": meter.meter_number,
        "provider": meter.provider,
        "energyBalanceKwh": meter.energy_balance_kwh,
        "totalLoadedKwh": meter.total_loaded_kwh,
        "totalPaidAmount": meter.total_paid_amount,
        "totalConsumedKwh": meter.total_consumed_kwh,
        "status": meter.status,
        "lastLoadedAt": meter.last_loaded_at,
        "lastConsumedAt": meter.last_consumed_at,
        "createdAt": meter.created_at,
    }


@router.get("")
def list_meters(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    meters = db.query(Meter).order_by(Meter.id.desc()).all()
    return [meter_out(meter) for meter in meters]


@router.post("/consume")
def consume_meter_energy(
    payload: MeterConsumptionSync,
    db: Annotated[Session, Depends(get_db)],
    x_sec_meter_sync_secret: Annotated[str | None, Header()] = None,
):
    settings = get_settings()
    if settings.meter_sync_secret and x_sec_meter_sync_secret != settings.meter_sync_secret:
        raise HTTPException(status_code=403, detail="Invalid meter sync secret")
    meter = (
        db.query(Meter)
        .filter(Meter.meter_number == payload.meterNumber)
        .first()
    )
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    consumed = payload.consumedKwh.quantize(Decimal("0.000001"))
    meter.energy_balance_kwh = max(
        Decimal("0.000000"),
        meter.energy_balance_kwh - consumed,
    )
    meter.total_consumed_kwh += consumed
    meter.last_consumed_at = payload.measuredAt or datetime.now(timezone.utc)
    db.commit()
    db.refresh(meter)
    return meter_out(meter)


@router.get("/{meter_id}")
def get_meter(
    meter_id: int,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    return meter_out(meter)


@router.patch("/{meter_id}")
def update_meter(
    meter_id: int,
    payload: MeterUpdate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    changes = payload.model_dump(exclude_unset=True)
    if "provider" in changes:
        meter.provider = changes["provider"]
    if "status" in changes:
        meter.status = changes["status"]
    db.commit()
    db.refresh(meter)
    return meter_out(meter)
