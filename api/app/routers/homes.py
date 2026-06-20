from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.deps import current_admin, current_client
from app.db.session import get_db
from app.models.admin import Admin
from app.models.client import Client
from app.models.home import Home, Meter
from app.schemas.home import HomeCreate, HomeUpdate

router = APIRouter(prefix="/homes", tags=["homes"])


def meter_out(meter: Meter | None) -> dict | None:
    if meter is None:
        return None
    return {
        "id": meter.id,
        "meterNumber": meter.meter_number,
        "provider": meter.provider,
        "energyBalanceKwh": meter.energy_balance_kwh,
        "totalLoadedKwh": meter.total_loaded_kwh,
        "totalPaidAmount": meter.total_paid_amount,
        "totalConsumedKwh": meter.total_consumed_kwh,
        "status": meter.status,
        "lastLoadedAt": meter.last_loaded_at,
        "lastConsumedAt": meter.last_consumed_at,
    }


def home_out(home: Home) -> dict:
    return {
        "id": home.id,
        "clientId": home.client_id,
        "name": home.name,
        "address": home.address,
        "city": home.city,
        "country": home.country,
        "currency": home.currency,
        "energyPricePerKwh": home.energy_price_per_kwh,
        "meter": meter_out(home.meter),
        "createdAt": home.created_at,
    }


@router.get("")
def list_homes(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    homes = (
        db.query(Home)
        .options(joinedload(Home.meter))
        .order_by(Home.id.desc())
        .all()
    )
    return [home_out(home) for home in homes]


@router.post("", status_code=201)
def create_home(
    payload: HomeCreate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    client = db.get(Client, payload.clientId)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if db.query(Meter).filter(Meter.meter_number == payload.meter.meterNumber).first():
        raise HTTPException(status_code=409, detail="Meter number already exists")
    home = Home(
        client_id=payload.clientId,
        name=payload.name,
        address=payload.address,
        city=payload.city,
        country=payload.country,
        currency=payload.currency,
        energy_price_per_kwh=payload.energyPricePerKwh,
    )
    home.meter = Meter(
        meter_number=payload.meter.meterNumber,
        provider=payload.meter.provider,
        energy_balance_kwh=payload.meter.initialEnergyKwh,
        total_loaded_kwh=payload.meter.initialEnergyKwh,
    )
    db.add(home)
    db.commit()
    db.refresh(home)
    return home_out(home)


@router.get("/me")
def my_homes(
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    homes = (
        db.query(Home)
        .options(joinedload(Home.meter))
        .filter(Home.client_id == client.id)
        .order_by(Home.id.desc())
        .all()
    )
    return [home_out(home) for home in homes]


@router.get("/{home_id}")
def get_home(
    home_id: int,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    home = db.query(Home).options(joinedload(Home.meter)).filter(Home.id == home_id).first()
    if home is None:
        raise HTTPException(status_code=404, detail="Home not found")
    return home_out(home)


@router.patch("/{home_id}")
def update_home(
    home_id: int,
    payload: HomeUpdate,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    home = db.query(Home).options(joinedload(Home.meter)).filter(Home.id == home_id).first()
    if home is None:
        raise HTTPException(status_code=404, detail="Home not found")
    changes = payload.model_dump(exclude_unset=True)
    mapping = {
        "name": "name",
        "address": "address",
        "city": "city",
        "country": "country",
        "currency": "currency",
        "energyPricePerKwh": "energy_price_per_kwh",
    }
    for key, value in changes.items():
        setattr(home, mapping[key], value)
    db.commit()
    db.refresh(home)
    return home_out(home)


@router.delete("/{home_id}", status_code=204)
def delete_home(
    home_id: int,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    home = db.get(Home, home_id)
    if home is None:
        raise HTTPException(status_code=404, detail="Home not found")
    db.delete(home)
    db.commit()
