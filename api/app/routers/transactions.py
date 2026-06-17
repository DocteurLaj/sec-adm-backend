from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.deps import current_admin, current_client
from app.db.session import get_db
from app.models.admin import Admin
from app.models.client import Client
from app.models.home import Home, Meter
from app.models.transaction import Transaction
from app.schemas.transaction import EnergyRechargeRequest

router = APIRouter(prefix="/transactions", tags=["transactions"])


def transaction_out(transaction: Transaction) -> dict:
    return {
        "id": transaction.id,
        "reference": transaction.reference,
        "clientId": transaction.client_id,
        "homeId": transaction.home_id,
        "meterId": transaction.meter_id,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "energyKwh": transaction.energy_kwh,
        "paymentMethod": transaction.payment_method,
        "providerReference": transaction.provider_reference,
        "status": transaction.status,
        "createdAt": transaction.created_at,
        "paidAt": transaction.paid_at,
    }


@router.get("")
def list_transactions(
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    transactions = db.query(Transaction).order_by(Transaction.id.desc()).limit(200).all()
    return [transaction_out(transaction) for transaction in transactions]


@router.get("/me")
def my_transactions(
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.client_id == client.id)
        .order_by(Transaction.id.desc())
        .limit(100)
        .all()
    )
    return [transaction_out(transaction) for transaction in transactions]


@router.post("/homes/{home_id}/recharge", status_code=201)
def recharge_home_energy(
    home_id: int,
    payload: EnergyRechargeRequest,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    home = (
        db.query(Home)
        .options(joinedload(Home.meter))
        .filter(Home.id == home_id, Home.client_id == client.id)
        .first()
    )
    if home is None:
        raise HTTPException(status_code=404, detail="Home not found")
    if home.meter is None:
        raise HTTPException(status_code=409, detail="Home has no meter")
    if home.energy_price_per_kwh <= 0:
        raise HTTPException(status_code=409, detail="Invalid energy price")

    meter: Meter = home.meter
    energy_kwh = (payload.amount / home.energy_price_per_kwh).quantize(
        Decimal("0.001")
    )
    now = datetime.now(timezone.utc)
    transaction = Transaction(
        reference=f"SEC-{uuid4().hex[:16].upper()}",
        client_id=client.id,
        home_id=home.id,
        meter_id=meter.id,
        amount=payload.amount,
        currency=home.currency,
        energy_kwh=energy_kwh,
        payment_method=payload.paymentMethod,
        provider_reference=payload.providerReference,
        status="paid",
        paid_at=now,
    )
    meter.energy_balance_kwh += energy_kwh
    meter.total_loaded_kwh += energy_kwh
    meter.total_paid_amount += payload.amount
    meter.last_loaded_at = now
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction_out(transaction)


@router.post("/admin/homes/{home_id}/recharge", status_code=201)
def admin_recharge_home_energy(
    home_id: int,
    payload: EnergyRechargeRequest,
    _: Annotated[Admin, Depends(current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    home = db.query(Home).options(joinedload(Home.meter)).filter(Home.id == home_id).first()
    if home is None:
        raise HTTPException(status_code=404, detail="Home not found")
    if home.meter is None:
        raise HTTPException(status_code=409, detail="Home has no meter")
    meter: Meter = home.meter
    energy_kwh = (payload.amount / home.energy_price_per_kwh).quantize(
        Decimal("0.001")
    )
    now = datetime.now(timezone.utc)
    transaction = Transaction(
        reference=f"SEC-ADM-{uuid4().hex[:14].upper()}",
        client_id=home.client_id,
        home_id=home.id,
        meter_id=meter.id,
        amount=payload.amount,
        currency=home.currency,
        energy_kwh=energy_kwh,
        payment_method=payload.paymentMethod,
        provider_reference=payload.providerReference,
        status="paid",
        paid_at=now,
    )
    meter.energy_balance_kwh += energy_kwh
    meter.total_loaded_kwh += energy_kwh
    meter.total_paid_amount += payload.amount
    meter.last_loaded_at = now
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction_out(transaction)
