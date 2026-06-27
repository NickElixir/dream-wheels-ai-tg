"""Base contracts for payment provider adapters."""

from dataclasses import dataclass
from typing import Any, Protocol

from src.payments.models import PaymentProviderName


@dataclass(frozen=True, slots=True)
class ProviderInvoice:
    provider: PaymentProviderName
    provider_invoice_payload: str
    confirmation_url: str | None
    metadata: dict[str, Any]


class PaymentProvider(Protocol):
    """Provider adapter boundary used by payment service orchestration."""

    provider: PaymentProviderName

    def verify_result_signature(self, **kwargs: Any) -> bool:
        """Verify provider server-side callback/update authenticity."""
