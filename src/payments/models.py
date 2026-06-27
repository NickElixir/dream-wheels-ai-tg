"""Provider-neutral payment models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

PaymentProviderName = Literal["robokassa", "telegram_stars"]
PaymentCurrency = Literal["RUB", "XTR"]
PaymentDeliveryChannel = Literal["website", "mini_app", "bot"]
PaymentStatus = Literal["pending", "paid", "failed", "refunded"]


@dataclass(frozen=True, slots=True)
class PaymentAmount:
    currency: PaymentCurrency
    provider_units: int
    display_amount: Decimal | None = None
