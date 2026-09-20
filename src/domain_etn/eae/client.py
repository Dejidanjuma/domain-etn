"""Optional EAE HTTP consumer. Read-only. Never asks EAE to register."""

from __future__ import annotations

from typing import Any

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
        return self._get(f"/api/v1/product/investigate/{address}")

    def owner_domains(self, address: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/owners/{address}/domains")

    def domain_search(self, name: str) -> dict[str, Any] | None:
        return self._get("/api/v1/product/search", params={"q": name})

    def domain_profile(self, name: str) -> dict[str, Any] | None:
        return self._get(f"/api/v1/product/domains/{name}")


def refuse_registration_via_eae(body: dict) -> None:
    if body.get("via") == "eae" or body.get("eae_register"):
        raise ProductError(
            "wrong_layer",
            "EAE cannot register names. Primary registration targets the official ENS controller.",
        )


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
        if isinstance(item, str):
            name = item
            rec = {"name": name}
        elif isinstance(item, dict):
            name = item.get("normalized_name") or item.get("name")
            rec = {
                "name": name,
                "label": item.get("label"),
                "nft_owner": item.get("nft_owner"),
                "expires": item.get("event_expires") or item.get("expires"),
            }
        else:
            continue
        if name:
            rec["name"] = name
            rec["source"] = "eae_indexed_facts"
            out.append(rec)
    return out
