from decimal import Decimal
from uuid import uuid4

import httpx

from app.core.config import get_settings


class PawaPayError(RuntimeError):
    pass


def new_deposit_id() -> str:
    return str(uuid4())


def normalize_currency(value: str | None) -> str:
    if not value or value.upper() == "FC":
        return get_settings().pawapay_default_currency
    return value.upper()


def format_amount(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def provider_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.pawapay_api_token:
        raise PawaPayError("PAWAPAY_API_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {settings.pawapay_api_token}",
        "Content-Type": "application/json",
    }


def initiate_deposit(
    *,
    deposit_id: str,
    amount: Decimal,
    currency: str,
    payer_phone: str,
    correspondent: str | None,
    statement_description: str,
) -> dict:
    settings = get_settings()
    provider = correspondent or settings.pawapay_default_correspondent
    if not provider:
        raise PawaPayError("PAWAPAY_DEFAULT_CORRESPONDENT is not configured")
    payload = {
        "depositId": deposit_id,
        "amount": format_amount(amount),
        "currency": normalize_currency(currency),
        "payer": {
            "type": "MMO",
            "accountDetails": {
                "phoneNumber": payer_phone.lstrip("+"),
                "provider": provider,
            },
        },
        "customerMessage": statement_description[:22],
    }
    if settings.pawapay_callback_url:
        payload["callbackUrl"] = settings.pawapay_callback_url

    try:
        response = httpx.post(
            f"{settings.pawapay_base_url.rstrip('/')}/v2/deposits",
            headers=provider_headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:220] if exc.response is not None else str(exc)
        raise PawaPayError(f"pawaPay deposit initiation failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise PawaPayError(f"pawaPay deposit initiation failed: {exc}") from exc
    return response.json() if response.content else {}


def get_deposit_status(deposit_id: str) -> dict:
    settings = get_settings()
    try:
        response = httpx.get(
            f"{settings.pawapay_base_url.rstrip('/')}/v2/deposits/{deposit_id}",
            headers=provider_headers(),
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PawaPayError(f"pawaPay status check failed: {exc}") from exc
    return response.json() if response.content else {}


def extract_deposit_id(payload: dict) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict):
        nested = extract_deposit_id(data)
        if nested:
            return nested
    for key in ("depositId", "deposit_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def extract_provider_status(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        nested_status = extract_provider_status(data)
        if nested_status != "PENDING":
            return nested_status
    for key in ("status", "depositStatus", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.upper()
    return "PENDING"


def map_status(provider_status: str) -> str:
    normalized = provider_status.upper()
    if normalized in {"COMPLETED", "SUCCESS", "SUCCESSFUL", "PAID"}:
        return "paid"
    if normalized in {"FAILED", "REJECTED", "CANCELLED", "CANCELED", "DUPLICATE_IGNORED"}:
        return "failed"
    return "pending"
