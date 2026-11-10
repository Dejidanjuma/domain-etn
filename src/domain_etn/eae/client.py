"""Optional EAE HTTP consumer. Read-only. Never asks EAE to register."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from src.domain_etn.errors import ProductError


class EaeClient:
    def __init__(self, base_url: str | None):
        self.base_url = (base_url or "").rstrip("/") or None

    def enabled(self) -> bool:
        return bool(self.base_url)

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any] | None:
        if not self.base_url:
            return None
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, params=params)
                if res.status_code >= 400:
                    return None
                return res.json()
        except httpx.HTTPError:
            return None

    def investigate(self, address: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/investigate/{quote(address)}")

    def owner_domains(self, address: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/owners/{quote(address)}/domains")

    def owner_intelligence(self, address: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/owners/{quote(address)}")

    def domain_search(self, name: str) -> dict[str, Any] | None:
        return self._get("/api/v1/product/search", params={"q": name})

    def catalog_search(self, q: str | None = None, prefix: str | None = None) -> dict[str, Any] | None:
        params: dict[str, str] = {}
        if q:
            params["q"] = q
        if prefix:
            params["prefix"] = prefix
        return self._get("/api/v1/product/domains", params=params or None)

    def domain_profile(self, name: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/domains/{quote(name)}")

    def domain_history(self, name: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/domains/{quote(name)}/history")

    def domain_marketplace(self, name: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/domains/{quote(name)}/marketplace")

    def discovery(self) -> dict[str, Any] | None:
        return self._get("/api/v1/product/domains/discovery")

    def marketplace_listings(self, status: str | None = None) -> dict[str, Any] | None:
        params = {"status": status} if status else None
        return self._get("/api/v1/product/marketplace/listings", params=params)

    def marketplace_activity(self) -> dict[str, Any] | None:
        return self._get("/api/v1/product/marketplace/activity")


def refuse_registration_via_eae(body: dict) -> None:
    if body.get("via") == "eae" or body.get("eae_register"):
        raise ProductError(
            "wrong_layer",
            "EAE cannot register names. Primary registration targets the official ENS controller.",
        )


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    return []


def normalize_owner_domains(address: str, eae_payload: dict | None) -> list[dict]:
    """Extract a display list from EAE without treating it as ownership authority."""
    if not eae_payload or not isinstance(eae_payload, dict):
        return []
    rows = (
        eae_payload.get("domains")
        or eae_payload.get("results")
        or ((eae_payload.get("eae") or {}).get("domains") if isinstance(eae_payload.get("eae"), dict) else None)
        or []
    )
    out = []
    for item in rows:
        rec = _normalize_name_row(item)
        if rec:
            rec["source"] = "eae_indexed_facts"
            out.append(rec)
    return out


def _normalize_name_row(item: Any) -> dict | None:
    if isinstance(item, str):
        name = item
        rec: dict[str, Any] = {"name": name}
    elif isinstance(item, dict):
        name = item.get("normalized_name") or item.get("name")
        rec = {
            "name": name,
            "label": item.get("label"),
            "nft_owner": item.get("nft_owner"),
            "expires": item.get("event_expires") or item.get("expires"),
            "event_type": item.get("event_type") or item.get("label"),
        }
    else:
        return None
    if not name:
        return None
    rec["name"] = name
    return rec


def normalize_history(eae_payload: dict | None) -> list[dict]:
    if not eae_payload or not isinstance(eae_payload, dict):
        return []
    events = eae_payload.get("events") or ((eae_payload.get("history") or {}).get("events") if isinstance(eae_payload.get("history"), dict) else None) or []
    out = []
    for item in _as_list(events):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "event_type": item.get("event_type"),
                "label": item.get("label") or item.get("event_type"),
                "block_number": item.get("block_number"),
                "tx_hash": item.get("tx_hash"),
                "entity": item.get("entity") or item.get("to") or item.get("from"),
                "from": item.get("from"),
                "to": item.get("to"),
                "sale": "not_inferred",
                "source": "eae_indexed_facts",
            }
        )
    return out


def normalize_listings(eae_payload: dict | None) -> list[dict]:
    if not eae_payload or not isinstance(eae_payload, dict):
        return []
    rows = eae_payload.get("results") or eae_payload.get("items") or eae_payload.get("listings") or []
    out = []
    for item in _as_list(rows):
        if isinstance(item, str):
            out.append({"name": item, "source": "eae_indexed_facts", "purchasable": False})
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("normalized_name") or item.get("name")
        out.append(
            {
                "name": name,
                "listing_id": item.get("listing_id"),
                "seller": item.get("seller"),
                "price_wei": item.get("price_wei") or item.get("price"),
                "status": item.get("status"),
                "deadline": item.get("deadline"),
                "source": "eae_indexed_facts",
                "purchasable": False,
                "live_availability": "not_inferred",
                "authorization": "not_authorization",
            }
        )
    return out


def intelligence_from_eae(eae_payload: dict | None) -> dict[str, Any]:
    """Stable product layers. Absence is honest, not fabricated."""
    if not eae_payload or not isinstance(eae_payload, dict):
        return {
            "configured": False,
            "indexed": False,
            "history": [],
            "related_addresses": [],
            "marketplace_facts": None,
            "derived": None,
            "layers": {
                "facts": "live_ens_reads",
                "indexed_facts": "not_queried",
                "derived": "not_queried",
                "signals": "not_implemented",
                "presentation": "domain_etn_ui",
            },
            "note": "EAE is not configured. Live ENS reads remain the ownership source.",
        }
    history = eae_payload.get("history") if isinstance(eae_payload.get("history"), dict) else None
    related = eae_payload.get("related_addresses")
    marketplace = eae_payload.get("marketplace")
    derived = eae_payload.get("intelligence") if isinstance(eae_payload.get("intelligence"), dict) else None
    return {
        "configured": True,
        "indexed": bool(eae_payload.get("indexed") or eae_payload.get("status") == "indexed"),
        "kind": eae_payload.get("kind"),
        "history": normalize_history(history or eae_payload),
        "related_addresses": _as_list(related),
        "marketplace_facts": marketplace if isinstance(marketplace, dict) else None,
        "derived": derived,
        "empty_reason": eae_payload.get("empty_reason"),
        "layers": eae_payload.get("layers")
        or {
            "facts": "live_ens_reads",
            "indexed_facts": "eae_catalog",
            "derived": "deterministic_eae_measurements",
            "signals": "deterministic_eae_signals",
            "presentation": "domain_etn_ui",
        },
        "note": (
            "EAE facts are indexed intelligence, not registration authority. "
            "Transfer is not a sale. Absence from EAE is not absence on-chain."
        ),
    }
