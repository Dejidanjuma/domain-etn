"""Read-only marketplace observation. Never prepares settlement transactions."""

from __future__ import annotations

from copy import deepcopy

from src.domain_etn.eae.client import normalize_listings
from src.domain_etn.marketplace.boundary import NOT_IMPLEMENTED


def descriptor(*, eae=None) -> dict:
    payload = deepcopy(NOT_IMPLEMENTED)
    payload["eae_configured"] = bool(eae is not None and getattr(eae, "enabled", lambda: False)())
    payload["indexed"] = None
    if payload["eae_configured"]:
        listings_fn = getattr(eae, "marketplace_listings", None)
        activity_fn = getattr(eae, "marketplace_activity", None)
        listings = listings_fn() if callable(listings_fn) else None
        activity = activity_fn() if callable(activity_fn) else None
        payload["indexed"] = {
            "authority": "eae_indexed_facts",
            "not_live_availability": True,
            "not_authorization": True,
            "listings": normalize_listings(listings),
            "activity": activity,
            "note": "Indexed observation only. Not a catalog of names you can buy here.",
        }
    return payload


def listings(*, eae=None, status: str | None = None) -> dict:
    base = descriptor(eae=eae)
    rows = []
    authority = "not_queried"
    raw = None
    if base["eae_configured"]:
        listings_fn = getattr(eae, "marketplace_listings", None)
        raw = listings_fn(status) if callable(listings_fn) else None
        rows = normalize_listings(raw)
        authority = "eae_indexed_facts" if raw is not None else "eae_unavailable"
    return {
        "type": "marketplace_listings",
        "flow": "secondary_marketplace",
        "settlement": "not_implemented",
        "deployed": False,
        "buy_now": "not_implemented",
        "authority": authority,
        "not_live_availability": True,
        "not_authorization": True,
        "purchasable": False,
        "status_filter": status,
        "listings": rows,
        "matched_count": len(rows),
        "eae": raw,
        "marketplace": NOT_IMPLEMENTED,
        "note": (
            "DOMAIN.etn does not invent marketplace inventory. "
            "Settlement is not deployed on Electroneum. "
            "Indexed rows are not live sellability and cannot be purchased here."
        ),
    }


def activity(*, eae=None) -> dict:
    raw = None
    authority = "not_queried"
    if eae is not None and getattr(eae, "enabled", lambda: False)():
        activity_fn = getattr(eae, "marketplace_activity", None)
        raw = activity_fn() if callable(activity_fn) else None
        authority = "eae_indexed_facts" if raw is not None else "eae_unavailable"
    items = []
    if isinstance(raw, dict):
        items = raw.get("results") or raw.get("items") or []
    return {
        "type": "marketplace_activity",
        "flow": "secondary_marketplace",
        "settlement": "not_implemented",
        "deployed": False,
        "authority": authority,
        "not_authorization": True,
        "sale_proof": "ListingPurchased event only",
        "activity": items if isinstance(items, list) else [],
        "eae": raw,
        "marketplace": NOT_IMPLEMENTED,
        "note": "Canonical marketplace events only, when EAE has indexed them. Transfer is not a sale.",
    }
