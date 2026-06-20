import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.core.deps import current_admin, current_client
from app.db.session import get_db
from app.models.admin import Admin
from app.models.client import Client
from app.models.home import Home, Meter
from app.models.transaction import Transaction
from app.schemas.transaction import EnergyRechargeRequest, PawaPayRechargeRequest
from app.services import pawapay
from app.services.push import try_send_to_client

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
        "paymentProvider": transaction.payment_provider,
        "providerDepositId": transaction.provider_deposit_id,
        "providerStatus": transaction.provider_status,
        "payerPhone": transaction.payer_phone,
        "failureReason": transaction.failure_reason,
        "status": transaction.status,
        "createdAt": transaction.created_at,
        "paidAt": transaction.paid_at,
    }


def _energy_for_amount(home: Home, amount: Decimal) -> Decimal:
    if home.energy_price_per_kwh <= 0:
        raise HTTPException(status_code=409, detail="Invalid energy price")
    return (amount / home.energy_price_per_kwh).quantize(Decimal("0.001"))


def _credit_meter_if_paid(transaction: Transaction, meter: Meter) -> None:
    if transaction.status == "paid" and transaction.paid_at is not None:
        return
    now = datetime.now(timezone.utc)
    transaction.status = "paid"
    transaction.paid_at = now
    meter.energy_balance_kwh += transaction.energy_kwh
    meter.total_loaded_kwh += transaction.energy_kwh
    meter.total_paid_amount += transaction.amount
    meter.last_loaded_at = now


def _failure_reason(payload: dict) -> str | None:
    for key in ("failureReason", "failure_reason", "errorMessage", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:255]
    return None


def _apply_provider_payload(transaction: Transaction, payload: dict, db: Session) -> Transaction:
    provider_status = pawapay.extract_provider_status(payload)
    status = pawapay.map_status(provider_status)
    transaction.provider_status = provider_status
    transaction.callback_payload = json.dumps(payload, ensure_ascii=True)
    if status == "paid":
        meter = db.get(Meter, transaction.meter_id)
        if meter is None:
            raise HTTPException(status_code=409, detail="Transaction meter not found")
        _credit_meter_if_paid(transaction, meter)
    elif status == "failed":
        transaction.status = "failed"
        transaction.failure_reason = _failure_reason(payload)
    else:
        transaction.status = "pending"
    return transaction


def _notify_transaction_paid(db: Session, transaction: Transaction) -> None:
    try_send_to_client(
        db,
        transaction.client_id,
        title="Paiement confirme",
        body=f"Votre compteur a ete recharge de {transaction.energy_kwh} kWh.",
        data={
            "id": f"payment-{transaction.reference}",
            "type": "payment",
            "title": "Paiement confirme",
            "message": f"Votre compteur a ete recharge de {transaction.energy_kwh} kWh.",
            "reference": transaction.reference,
            "status": transaction.status,
        },
    )


def _notify_transaction_failed(db: Session, transaction: Transaction) -> None:
    reason = transaction.failure_reason or "Le paiement n'a pas abouti."
    try_send_to_client(
        db,
        transaction.client_id,
        title="Paiement echoue",
        body=reason,
        data={
            "id": f"payment-{transaction.reference}",
            "type": "payment",
            "title": "Paiement echoue",
            "message": reason,
            "reference": transaction.reference,
            "status": transaction.status,
        },
    )


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


@router.get("/{reference}")
def get_transaction(
    reference: str,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.reference == reference, Transaction.client_id == client.id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction_out(transaction)


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

    meter: Meter = home.meter
    energy_kwh = _energy_for_amount(home, payload.amount)
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
        payment_provider="manual",
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
    _notify_transaction_paid(db, transaction)
    return transaction_out(transaction)


@router.post("/homes/{home_id}/pawapay/recharge", status_code=201)
def start_pawapay_recharge(
    home_id: int,
    payload: PawaPayRechargeRequest,
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

    deposit_id = pawapay.new_deposit_id()
    reference = f"SEC-PAWA-{uuid4().hex[:12].upper()}"
    transaction = Transaction(
        reference=reference,
        client_id=client.id,
        home_id=home.id,
        meter_id=home.meter.id,
        amount=payload.amount,
        currency=pawapay.normalize_currency(home.currency),
        energy_kwh=_energy_for_amount(home, payload.amount),
        payment_method="pawaPay Mobile Money",
        provider_reference=deposit_id,
        payment_provider="pawapay",
        provider_deposit_id=deposit_id,
        provider_status="PENDING",
        payer_phone=payload.payerPhone,
        status="pending",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    try:
        provider_payload = pawapay.initiate_deposit(
            deposit_id=deposit_id,
            amount=payload.amount,
            currency=transaction.currency,
            payer_phone=payload.payerPhone,
            correspondent=payload.correspondent,
            statement_description=f"SEC Energie {home.meter.meter_number}",
        )
    except pawapay.PawaPayError as exc:
        transaction.status = "failed"
        transaction.provider_status = "INIT_FAILED"
        transaction.failure_reason = str(exc)[:255]
        db.commit()
        db.refresh(transaction)
        _notify_transaction_failed(db, transaction)
        raise HTTPException(status_code=502, detail="pawaPay sandbox unavailable")

    previous_status = transaction.status
    _apply_provider_payload(transaction, provider_payload, db)
    db.commit()
    db.refresh(transaction)
    if previous_status != "paid" and transaction.status == "paid":
        _notify_transaction_paid(db, transaction)
    elif previous_status != "failed" and transaction.status == "failed":
        _notify_transaction_failed(db, transaction)
    return transaction_out(transaction)


@router.post("/pawapay/callback", status_code=202)
async def pawapay_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    payload = await request.json()
    deposit_id = pawapay.extract_deposit_id(payload)
    if not deposit_id:
        raise HTTPException(status_code=400, detail="Missing depositId")
    transaction = (
        db.query(Transaction)
        .filter(Transaction.provider_deposit_id == deposit_id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    previous_status = transaction.status
    _apply_provider_payload(transaction, payload, db)
    db.commit()
    if previous_status != "paid" and transaction.status == "paid":
        _notify_transaction_paid(db, transaction)
    elif previous_status != "failed" and transaction.status == "failed":
        _notify_transaction_failed(db, transaction)
    return {"status": "accepted"}


@router.post("/{reference}/sync")
def sync_pawapay_transaction(
    reference: str,
    client: Annotated[Client, Depends(current_client)],
    db: Annotated[Session, Depends(get_db)],
):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.reference == reference, Transaction.client_id == client.id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.payment_provider != "pawapay" or not transaction.provider_deposit_id:
        return transaction_out(transaction)
    if transaction.status == "paid":
        return transaction_out(transaction)
    try:
        payload = pawapay.get_deposit_status(transaction.provider_deposit_id)
    except pawapay.PawaPayError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    previous_status = transaction.status
    _apply_provider_payload(transaction, payload, db)
    db.commit()
    db.refresh(transaction)
    if previous_status != "paid" and transaction.status == "paid":
        _notify_transaction_paid(db, transaction)
    elif previous_status != "failed" and transaction.status == "failed":
        _notify_transaction_failed(db, transaction)
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
        payment_provider="manual",
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
    _notify_transaction_paid(db, transaction)
    return transaction_out(transaction)
