"""Live domain profile from official ENS contracts. EAE is optional intelligence."""

from __future__ import annotations

import time

from src.domain_etn.domains.lifecycle import classify
from src.domain_etn.eae.client import intelligence_from_eae
from src.domain_etn.ens.addresses import (
    BASE_REGISTRAR,
    CHAIN_ID,
    CONTROLLER,
    EXPLORER_URL,
    GRACE_PERIOD_SEC,
)
from src.domain_etn.ens.client import EnsReader
from src.domain_etn.ens.encoding import labelhash_hex
from src.domain_etn.marketplace.boundary import NOT_IMPLEMENTED as MARKETPLACE
from src.domain_etn.names import parse_registration_name
from src.domain_etn.rpc import Rpc


class DomainProfile:
    def __init__(self, rpc: Rpc, *, eae=None):
        self.rpc = rpc
        self.ens = EnsReader(rpc)
        self.eae = eae

    def get(self, name: str, *, now: int | None = None) -> dict:
        parsed = parse_registration_name(name)
        available = self.ens.available(parsed["label"])
        expires_at = int(self.ens.name_expires(parsed["label"]) or 0)
        owner = None if available else self.ens.owner_of(parsed["label"])
        ts = int(now if now is not None else time.time())
        lifecycle = classify(available=available, expires_at=expires_at, now=ts, grace_period_sec=GRACE_PERIOD_SEC)
        eae_facts = None
        if self.eae is not None and getattr(self.eae, "enabled", lambda: False)():
            profile_fn = getattr(self.eae, "domain_profile", None)
            search_fn = getattr(self.eae, "domain_search", None)
            if callable(profile_fn):
                eae_facts = profile_fn(parsed["name"])
            if eae_facts is None and callable(search_fn):
                eae_facts = search_fn(parsed["name"])
        intelligence = intelligence_from_eae(eae_facts)
        return {
            "type": "domain_profile",
            "name": parsed["name"],
            "label": parsed["label"],
            "labelhash": labelhash_hex(parsed["label"]),
            "available": available,
            "status": "available" if available else "registered",
            "lifecycle": lifecycle,
            "owner": owner,
            "expires_at": expires_at or None,
            "grace_period_sec": GRACE_PERIOD_SEC,
            "in_grace": lifecycle["in_grace"],
            "renewable": lifecycle["renewable"],
            "chain_id": CHAIN_ID,
            "controller": CONTROLLER,
            "base_registrar": BASE_REGISTRAR,
            "explorer": EXPLORER_URL,
            "source": {
                "availability": "ens_controller.available",
                "owner": "base_registrar.ownerOf",
                "expires": "base_registrar.nameExpires",
                "lifecycle": lifecycle["source"],
            },
            "eae": eae_facts,
            "intelligence": intelligence,
            "eae_is_not_ownership_source": True,
            "marketplace": MARKETPLACE,
            "note": (
                "Owner and expiry are live eth_call reads. "
                "ownerOf reverts after expiry (including grace), so owner may be null while the name is still not available. "
                "EAE facts are indexed intelligence, not registration authority. "
                "Marketplace settlement is not deployed on Electroneum."
            ),
        }
