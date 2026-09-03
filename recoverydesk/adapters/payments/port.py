"""PaymentRailPort / NotificationPort — the ONLY rails core may call.
Dialect lives below the port (adapters); core imports this module only
(boundary tests enforce)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AttemptResult:
    attempt_ref: str
    success: bool
    failure_class: str | None      # canonical taxonomy on failure
    psp_reason_code: str | None    # raw dialect code (mapped upstream via code map)
    latency_ms: int


@dataclass(slots=True)
class DeliveryResult:
    delivery_ref: str
    accepted: bool
    channel: str


class PaymentRailPort(Protocol):
    def charge_retry(self, *, mandate_ref: str, amount_inr: float, idem_key: str,
                     window_code: str, at) -> AttemptResult: ...


class NotificationPort(Protocol):
    def send(self, *, channel: str, template_id: str, locale: str, slots: dict,
             idem_key: str, at) -> DeliveryResult: ...
