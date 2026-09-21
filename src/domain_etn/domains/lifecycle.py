"""Domain lifecycle labels from live ENS reads.

Presentation only. `expiring_soon` is a product threshold, not an on-chain
constant. Grace is `nameExpires <= now` while `available()` is still false
(90-day BaseRegistrar grace). After grace the name is simply available.
"""

from __future__ import annotations

from src.domain_etn.ens.addresses import GRACE_PERIOD_SEC

# Product UI threshold. Not encoded in the controller.
EXPIRING_SOON_SEC = 30 * 24 * 3600


def classify(*, available: bool, expires_at: int | None, now: int, grace_period_sec: int = GRACE_PERIOD_SEC) -> dict:
    expires = int(expires_at or 0)
    in_grace = bool(expires and now >= expires and not available)
    remaining = (expires - now) if expires else None
    if available:
        state = "available"
        label = "Available"
    elif in_grace:
        state = "grace"
        label = "Grace period"
    elif remaining is not None and 0 < remaining <= EXPIRING_SOON_SEC:
        state = "expiring_soon"
        label = "Expiring soon"
    else:
        state = "active"
        label = "Registered"
    return {
        "state": state,
        "label": label,
        "available": bool(available),
        "in_grace": in_grace,
        "renewable": not bool(available),
        "expires_at": expires or None,
        "seconds_remaining": remaining,
        "expiring_soon": state == "expiring_soon",
        "grace_period_sec": int(grace_period_sec),
        "expiring_soon_threshold_sec": EXPIRING_SOON_SEC,
        "expiring_soon_is_on_chain": False,
        "source": "ens_controller.available + base_registrar.nameExpires",
    }
