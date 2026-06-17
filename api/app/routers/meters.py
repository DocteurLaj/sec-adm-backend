from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.home import Meter

router = APIRouter(prefix="/meters", tags=["meters"])


class MeterUpdate(BaseModel):
    provider: str | None = None
    status: str | None = None


def meter_out(meter: Meter) -> dict:
    return {
        "id": meter.id,
        "homeId": meter.home_id,
        "meterNumber": meter.meter_number,
        "provider": meter.provider,
        "energyBalanceKwh": meter.energy_balance_kwh,
        "totalLoadedKwh": meter.total_loaded_kwh,
        "totalPaidAmount": meter.total_paid_amount,
        "status": meter.status,
        "lastLoadedAt": meter.last_loaded_at,
        "createdAt": meter.created_at,
    }


@router.get("")
def list_meters(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    meters = db.query(Meter).order_by(Meter.id.desc()).all()
    return [meter_out(meter) for meter in meters]


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
