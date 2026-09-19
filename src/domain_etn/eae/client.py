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

    def investigate(self, address: str) -> dict[str, Any] | None:
        if not self.base_url:
            return None
        url = f"{self.base_url}/api/v1/product/investigate/{address}"
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url)
                if res.status_code >= 400:
                    return None
                return res.json()
        except httpx.HTTPError:
            return None

    def domain_search(self, name: str) -> dict[str, Any] | None:
        if not self.base_url:
            return None
        url = f"{self.base_url}/api/v1/product/search"
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, params={"q": name})
                if res.status_code >= 400:
                    return None
                return res.json()
        except httpx.HTTPError:
            return None


def refuse_registration_via_eae(body: dict) -> None:
    if body.get("via") == "eae" or body.get("eae_register"):
        raise ProductError(
            "wrong_layer",
            "EAE cannot register names. Primary registration targets the official ENS controller.",
        )
