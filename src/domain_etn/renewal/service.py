"""Prepare-only renewal against the live ETHRegistrarController.

Verified Electroneum ABI (ETHRegistrarController.sol):

    function renew(string label, uint256 duration, bytes32 referrer) external payable

Payment is native ETN equal to rentPrice.base (premium is not charged).
Excess is refunded by the contract. Anyone may pay to extend a name.
"""

from __future__ import annotations

import time
import uuid

from src.domain_etn.config import Settings, settings as default_settings
from src.domain_etn.ens.addresses import CHAIN_ID, CONTROLLER, UNUSED_CONTROLLER
from src.domain_etn.ens.client import EnsReader, checksum_wallet
from src.domain_etn.ens.encoding import NAME_RENEWED_TOPIC0, labelhash_hex, tx_renew
from src.domain_etn.errors import ProductError
from src.domain_etn.names import parse_registration_name, require_duration
from src.domain_etn.registration.models import (
    FLOW_RENEWAL,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_PREPARED,
    STATUS_SUBMITTED,
    STATUS_WALLET_SIGNING,
    IntentStore,
    RenewalIntent,
)
from src.domain_etn.rpc import Rpc
from src.domain_etn.tokens import sign_payload, verify_token


class RenewalService:
    def __init__(self, rpc: Rpc, *, settings: Settings | None = None, store: IntentStore | None = None):
        self.rpc = rpc
        self.ens = EnsReader(rpc)
        self.settings = settings or default_settings
        self.store = store or IntentStore()

    def quote(self, name: str, duration: int, *, now: int | None = None) -> dict:
        parsed = parse_registration_name(name)
        duration = require_duration(duration)
        if self.ens.available(parsed["label"]):
            raise ProductError(
                "not_renewable",
                "Name is available for primary registration, not renewal.",
                {"name": parsed["name"]},
            )
        price = self.ens.rent_price(parsed["label"], duration)
        ts = int(now if now is not None else time.time())
        quote_id = uuid.uuid4().hex
        payload = {
            "v": 1,
            "kind": "renewal",
            "quote_id": quote_id,
            "name": parsed["name"],
            "label": parsed["label"],
            "duration": duration,
            "chain_id": CHAIN_ID,
            "controller": CONTROLLER.lower(),
            "price_base": price["base"],
            "price_premium": price["premium"],
            "price_total": price["base"],  # controller charges base only
            "issued_at": ts,
            "expires_at": ts + int(self.settings.quote_ttl_sec),
        }
        token = sign_payload(payload, self.settings.quote_secret)
        return {
            "type": "renewal_quote",
            "quote_id": quote_id,
            "quote_token": token,
            "name": parsed["name"],
            "label": parsed["label"],
            "duration": duration,
            "price": {
                "base": price["base"],
                "premium": price["premium"],
                "total": price["base"],
                "currency": "ETN",
                "unit": "wei",
                "charged": "base",
            },
            "controller": CONTROLLER,
            "chain_id": CHAIN_ID,
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
            "flow": FLOW_RENEWAL,
            "note": (
                "Electroneum controller.renew charges rentPrice.base in native ETN. "
                "Premium is not collected on renewal. Quote is not a reservation."
            ),
        }

    def prepare(self, body: dict, *, now: int | None = None) -> dict:
        _reject_marketplace_mix(body)
        _reject_client_contract(body)
        parsed = parse_registration_name(body.get("name") or "")
        quote = verify_token(str(body.get("quote_token") or ""), self.settings.quote_secret, now=now)
        if quote.get("kind") != "renewal":
            raise ProductError("wrong_flow", "This quote is not a renewal quote.")
        if quote.get("label") != parsed["label"]:
            raise ProductError("invalid_quote", "Name does not match the quote.")
        duration = require_duration(quote["duration"])
        if body.get("duration") not in (None, "", duration) and int(body.get("duration") or duration) != duration:
            raise ProductError("invalid_quote", "Duration does not match the quote.")
        payer = checksum_wallet(body.get("payer") or body.get("registrant") or "")
        if self.ens.available(parsed["label"]):
            raise ProductError("not_renewable", "Name is no longer renewable.", {"name": parsed["name"]})
        live = self.ens.rent_price(parsed["label"], duration)
        if int(live["base"]) > int(quote["price_total"]):
            raise ProductError(
                "stale_quote",
                "On-chain renewal rent is higher than the quote. Request a new quote.",
                {"quoted": quote["price_total"], "live": live["base"]},
            )
        unsigned = tx_renew(parsed["label"], duration, int(live["base"]), body.get("referrer"))
        unsigned["from"] = payer
        ts = int(now if now is not None else time.time())
        intent = RenewalIntent(
            intent_id=uuid.uuid4().hex,
            status=STATUS_PREPARED,
            name=parsed["name"],
            label=parsed["label"],
            payer=payer,
            duration=duration,
            controller=CONTROLLER,
            chain_id=CHAIN_ID,
            quote_id=str(quote.get("quote_id") or ""),
            price_base=live["base"],
            price_premium=live["premium"],
            price_total=live["base"],
            renew_tx=unsigned,
            created_at=ts,
            expires_at=ts + int(self.settings.intent_ttl_sec),
            note="Unsigned renew transaction. Pays native ETN to the allowlisted controller. This is not renewal success.",
        )
        self.store.put(intent)
        doc = intent.public()
        doc["client_phase"] = STATUS_WALLET_SIGNING
        return doc

    def mark_submitted(self, intent_id: str, tx_hash: str) -> dict:
        intent = self._require(intent_id)
        intent.tx_hash = _txh(tx_hash)
        intent.status = STATUS_SUBMITTED
        intent.note = "Transaction hash recorded. Not confirmed. Not a successful renewal."
        self.store.put(intent)
        return intent.public()

    def confirm(self, intent_id: str) -> dict:
        intent = self._require(intent_id)
        if not intent.tx_hash:
            raise ProductError("invalid_status", "No renewal transaction hash has been submitted.")
        receipt = self.rpc.get_transaction_receipt(intent.tx_hash)
        if receipt is None:
            intent.status = STATUS_SUBMITTED
            intent.note = "Renewal transaction not yet mined."
            return intent.public()
        status = receipt.get("status")
        ok = status in (1, "0x1", "1")
        if not ok:
            intent.status = STATUS_FAILED
            intent.note = "Renewal transaction reverted. Name was not renewed."
            self.store.put(intent)
            return intent.public()
        if not _has_name_renewed(receipt, intent.label):
            intent.status = STATUS_SUBMITTED
            intent.note = (
                "Receipt succeeded but NameRenewed for this label was not observed. "
                "Not treated as a DOMAIN.etn renewal success."
            )
            self.store.put(intent)
            return intent.public()
        intent.status = STATUS_CONFIRMED
        intent.note = (
            "NameRenewed observed on the official controller for this label. "
            "Expiry truth is the chain. EAE may index this fact later."
        )
        self.store.put(intent)
        return intent.public()

    def get(self, intent_id: str) -> dict:
        return self._require(intent_id).public()

    def _require(self, intent_id) -> RenewalIntent:
        rec = self.store.get(str(intent_id or "").strip())
        if rec is None or not isinstance(rec, RenewalIntent):
            raise ProductError("unknown_intent", "Unknown renewal intent.", http_status=404)
        return rec


def _reject_client_contract(body: dict) -> None:
    for key in ("controller", "contract", "to", "target"):
        raw = body.get(key)
        if not raw:
            continue
        text = str(raw).strip().lower()
        if text == UNUSED_CONTROLLER.lower():
            raise ProductError("wrong_contract", "Unused registrar controller is not a renewal target.")
        if text != CONTROLLER.lower():
            raise ProductError("wrong_contract", "Client-supplied contract addresses are not trusted.")


def _reject_marketplace_mix(body: dict) -> None:
    for key in ("listing_id", "marketplace", "offer_id", "auction_id", "buy_now"):
        if body.get(key):
            raise ProductError(
                "wrong_flow",
                "Renewal is not a marketplace purchase.",
                {"flow": FLOW_RENEWAL},
            )


def _txh(value: str) -> str:
    text = (value or "").strip().lower()
    if text.startswith("0x"):
        hexpart = text[2:]
    else:
        hexpart = text
        text = "0x" + hexpart
    if len(hexpart) != 64 or any(c not in "0123456789abcdef" for c in hexpart):
        raise ProductError("invalid_tx_hash", "tx_hash must be 32 bytes hex.")
    return text


def _has_name_renewed(receipt: dict, label: str) -> bool:
    logs = receipt.get("logs") or []
    want_ctrl = CONTROLLER.lower()
    want_topic0 = NAME_RENEWED_TOPIC0.lower()
    want_label = labelhash_hex(label).lower()
    for log in logs:
        addr = str(log.get("address") or "").lower()
        topics = [str(t).lower() for t in (log.get("topics") or [])]
        if addr != want_ctrl or len(topics) < 2:
            continue
        if topics[0] != want_topic0:
            continue
        if topics[1] != want_label:
            continue
        return True
    return False
