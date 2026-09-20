"""On-chain facts vs transaction intent vs transaction state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STATUS_PREPARED = "prepared"
STATUS_WALLET_SIGNING = "wallet_signing"
STATUS_SUBMITTED = "submitted"
STATUS_CONFIRMED = "confirmed"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"
STATUS_EXPIRED = "expired"

FLOW_PRIMARY = "primary_registration"
FLOW_RENEWAL = "renewal"
FLOW_MARKETPLACE = "secondary_marketplace"


@dataclass
class RegistrationIntent:
    intent_id: str
    status: str
    flow: str = FLOW_PRIMARY
    name: str = ""
    label: str = ""
    registrant: str = ""
    duration: int = 0
    controller: str = ""
    chain_id: int = 52014
    resolver: str = ""
    reverse_record: int = 0
    referrer: str = "0x" + "00" * 32
    commitment: str = ""
    quote_id: str = ""
    price_base: str = "0"
    price_premium: str = "0"
    price_total: str = "0"
    commit_tx: dict | None = None
    register_tx: dict | None = None
    commit_tx_hash: str | None = None
    register_tx_hash: str | None = None
    created_at: int = 0
    expires_at: int = 0
    note: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "type": "registration_intent",
            "intent_id": self.intent_id,
            "status": self.status,
            "flow": self.flow,
            "name": self.name,
            "label": self.label,
            "registrant": self.registrant,
            "duration": self.duration,
            "chain_id": self.chain_id,
            "controller": self.controller,
            "resolver": self.resolver,
            "reverse_record": self.reverse_record,
            "commitment": self.commitment,
            "quote_id": self.quote_id,
            "price": {
                "base": self.price_base,
                "premium": self.price_premium,
                "total": self.price_total,
                "currency": "ETN",
                "unit": "wei",
            },
            "commit_tx": self.commit_tx,
            "register_tx": self.register_tx,
            "commit_tx_hash": self.commit_tx_hash,
            "register_tx_hash": self.register_tx_hash,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "success": self.status == STATUS_CONFIRMED,
            "note": self.note
            or "Prepared/signed/submitted is not registration success. Only a confirmed NameRegistered log is.",
        }


@dataclass
class RenewalIntent:
    intent_id: str
    status: str
    flow: str = FLOW_RENEWAL
    name: str = ""
    label: str = ""
    payer: str = ""
    duration: int = 0
    controller: str = ""
    chain_id: int = 52014
    quote_id: str = ""
    price_base: str = "0"
    price_premium: str = "0"
    price_total: str = "0"
    renew_tx: dict | None = None
    tx_hash: str | None = None
    created_at: int = 0
    expires_at: int = 0
    note: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "type": "renewal_intent",
            "intent_id": self.intent_id,
            "status": self.status,
            "flow": self.flow,
            "name": self.name,
            "label": self.label,
            "payer": self.payer,
            "duration": self.duration,
            "chain_id": self.chain_id,
            "controller": self.controller,
            "quote_id": self.quote_id,
            "price": {
                "base": self.price_base,
                "premium": self.price_premium,
                "total": self.price_total,
                "currency": "ETN",
                "unit": "wei",
                "charged": "base",
            },
            "renew_tx": self.renew_tx,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "success": self.status == STATUS_CONFIRMED,
            "note": self.note
            or "Prepared/signed/submitted is not renewal success. Only a confirmed NameRenewed log is.",
        }


class IntentStore:
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def put(self, intent) -> None:
        self._items[intent.intent_id] = intent

    def get(self, intent_id: str):
        return self._items.get(intent_id)
