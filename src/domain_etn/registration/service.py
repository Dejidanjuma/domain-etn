"""Primary registration use-cases. Prepares unsigned txs. Never sends them."""

from __future__ import annotations

import time
import uuid

from eth_utils import keccak as _keccak

from src.domain_etn.config import Settings, settings as default_settings
from src.domain_etn.ens.addresses import (
    CHAIN_ID,
    CONTROLLER,
    MIN_REGISTRATION_DURATION_SEC,
    PUBLIC_RESOLVER,
    REVERSE_RECORD_ETHEREUM_BIT,
    UNUSED_CONTROLLER,
    ZERO,
)
from src.domain_etn.ens.client import EnsReader, checksum_wallet
from src.domain_etn.ens.encoding import commitment_hash, registration_tuple, tx_commit, tx_register
from src.domain_etn.errors import ProductError
from src.domain_etn.names import parse_registration_name
from src.domain_etn.registration.models import (
    FLOW_PRIMARY,
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PREPARED,
    STATUS_STALE,
    STATUS_SUBMITTED,
    STATUS_WALLET_SIGNING,
    IntentStore,
    RegistrationIntent,
)
from src.domain_etn.rpc import Rpc
from src.domain_etn.tokens import sign_payload, verify_token

# Live controller ABI: NameRegistered(string,bytes32,address,uint256,uint256,uint256,bytes32)
# Indexed: labelhash (topic1), owner (topic2). referrer is NOT indexed.
NAME_REGISTERED_TOPIC0 = "0x" + _keccak(
    b"NameRegistered(string,bytes32,address,uint256,uint256,uint256,bytes32)"
).hex()


class RegistrationService:
    def __init__(self, rpc: Rpc, *, settings: Settings | None = None, store: IntentStore | None = None):
        self.rpc = rpc
        self.ens = EnsReader(rpc)
        self.settings = settings or default_settings
        self.store = store or IntentStore()

    def availability(self, name: str) -> dict:
        parsed = parse_registration_name(name)
        available = self.ens.available(parsed["label"])
        return {
            "type": "domain_availability",
            "name": parsed["name"],
            "label": parsed["label"],
            "available": available,
            "status": "available" if available else "unavailable",
            "source": "ens_controller.available",
            "controller": CONTROLLER,
            "chain_id": CHAIN_ID,
            "flow": FLOW_PRIMARY,
            "note": (
                "Availability is the live controller view, including grace period. "
                "It is not an EAE index and not a reservation."
            ),
        }

    def quote(self, name: str, duration: int, *, now: int | None = None) -> dict:
        parsed = parse_registration_name(name)
        duration = _require_duration(duration)
        avail = self.ens.available(parsed["label"])
        if not avail:
            raise ProductError(
                "unavailable_domain",
                "Name is not available for primary registration.",
                {"name": parsed["name"]},
            )
        price = self.ens.rent_price(parsed["label"], duration)
        ts = int(now if now is not None else time.time())
        quote_id = uuid.uuid4().hex
        payload = {
            "v": 1,
            "quote_id": quote_id,
            "name": parsed["name"],
            "label": parsed["label"],
            "duration": duration,
            "chain_id": CHAIN_ID,
            "controller": CONTROLLER.lower(),
            "price_base": price["base"],
            "price_premium": price["premium"],
            "price_total": price["total"],
            "issued_at": ts,
            "expires_at": ts + int(self.settings.quote_ttl_sec),
        }
        token = sign_payload(payload, self.settings.quote_secret)
        return {
            "type": "registration_quote",
            "quote_id": quote_id,
            "quote_token": token,
            "name": parsed["name"],
            "label": parsed["label"],
            "duration": duration,
            "available": True,
            "price": price,
            "controller": CONTROLLER,
            "chain_id": CHAIN_ID,
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
            "flow": FLOW_PRIMARY,
            "note": (
                "Quote is a signed price snapshot. Registration still requires "
                "commit/reveal and on-chain payment. Quote is not a reservation."
            ),
        }

    def prepare_commit(self, body: dict, *, now: int | None = None) -> dict:
        _reject_marketplace_mix(body)
        _reject_client_contract(body)
        parsed = parse_registration_name(body.get("name") or "")
        quote = verify_token(str(body.get("quote_token") or ""), self.settings.quote_secret, now=now)
        requested_duration = int(body.get("duration") or quote["duration"])
        if quote.get("label") != parsed["label"]:
            raise ProductError("invalid_quote", "Name does not match the quote.")
        if requested_duration != int(quote["duration"]):
            raise ProductError("invalid_quote", "Duration does not match the quote.")
        duration = int(quote["duration"])
        _require_duration(duration)
        registrant = checksum_wallet(body.get("registrant") or "")
        secret = str(body.get("secret") or "")
        resolver, reverse = _resolver_and_reverse(body)
        if not self.ens.available(parsed["label"]):
            raise ProductError("unavailable_domain", "Name is no longer available.", {"name": parsed["name"]})
        live_price = self.ens.rent_price(parsed["label"], duration)
        if int(live_price["total"]) > int(quote["price_total"]):
            raise ProductError(
                "stale_quote",
                "On-chain rent is higher than the quote. Request a new quote.",
                {"quoted": quote["price_total"], "live": live_price["total"]},
            )
        reg = registration_tuple(
            label=parsed["label"],
            owner=registrant,
            duration=duration,
            secret=secret,
            resolver=resolver,
            reverse_record=reverse,
            referrer=body.get("referrer"),
        )
        commitment = commitment_hash(reg)
        unsigned = tx_commit(commitment)
        unsigned["from"] = registrant
        ts = int(now if now is not None else time.time())
        intent = RegistrationIntent(
            intent_id=uuid.uuid4().hex,
            status=STATUS_PREPARED,
            name=parsed["name"],
            label=parsed["label"],
            registrant=registrant,
            duration=duration,
            controller=CONTROLLER,
            chain_id=CHAIN_ID,
            resolver=resolver,
            reverse_record=reverse,
            commitment=commitment,
            quote_id=str(quote.get("quote_id") or ""),
            price_base=live_price["base"],
            price_premium=live_price["premium"],
            price_total=live_price["total"],
            commit_tx=unsigned,
            created_at=ts,
            expires_at=ts + int(self.settings.intent_ttl_sec),
            note="Unsigned commit transaction. Wallet must sign. This is not registration success.",
        )
        self.store.put(intent)
        doc = intent.public()
        doc["client_phase"] = STATUS_WALLET_SIGNING
        doc["min_commitment_age_sec"] = 60
        doc["max_commitment_age_sec"] = 86400
        return doc

    def prepare_register(self, body: dict, *, now: int | None = None) -> dict:
        _reject_marketplace_mix(body)
        _reject_client_contract(body)
        intent = self._require_intent(body.get("intent_id"))
        ts = int(now if now is not None else time.time())
        if ts >= intent.expires_at:
            intent.status = STATUS_EXPIRED
            raise ProductError("expired_intent", "Registration intent has expired.")
        secret = str(body.get("secret") or "")
        resolver = intent.resolver or ZERO
        reg = registration_tuple(
            label=intent.label,
            owner=intent.registrant,
            duration=intent.duration,
            secret=secret,
            resolver=resolver,
            reverse_record=intent.reverse_record,
            referrer=intent.referrer,
        )
        if commitment_hash(reg) != intent.commitment:
            raise ProductError("invalid_secret", "secret does not match the prepared commitment.")
        if not self.ens.available(intent.label):
            intent.status = STATUS_STALE
            raise ProductError("unavailable_domain", "Name is no longer available.")
        live_price = self.ens.rent_price(intent.label, intent.duration)
        if int(live_price["total"]) > int(intent.price_total):
            intent.status = STATUS_STALE
            raise ProductError(
                "stale_quote",
                "On-chain rent is higher than the prepared total. Request a new quote.",
                {"prepared": intent.price_total, "live": live_price["total"]},
            )
        intent.price_base = live_price["base"]
        intent.price_premium = live_price["premium"]
        intent.price_total = live_price["total"]
        unsigned = tx_register(reg, int(live_price["total"]))
        unsigned["from"] = intent.registrant
        intent.register_tx = unsigned
        intent.status = STATUS_PREPARED
        intent.note = (
            "Unsigned register transaction. Pays native ETN to the allowlisted controller. "
            "Wait minCommitmentAge after the commit is mined. Excess ETN is refunded by the contract. "
            "This is not registration success."
        )
        self.store.put(intent)
        doc = intent.public()
        doc["client_phase"] = STATUS_WALLET_SIGNING
        return doc

    def mark_submitted(self, intent_id: str, tx_hash: str, *, kind: str) -> dict:
        intent = self._require_intent(intent_id)
        hx = _txh(tx_hash)
        if kind not in {"commit", "register"}:
            raise ProductError("invalid_status", "kind must be commit or register.")
        if kind == "commit":
            intent.commit_tx_hash = hx
        else:
            intent.register_tx_hash = hx
        intent.status = STATUS_SUBMITTED
        intent.note = "Transaction hash recorded. Not confirmed. Not a successful registration."
        self.store.put(intent)
        return intent.public()

    def confirm(self, intent_id: str) -> dict:
        intent = self._require_intent(intent_id)
        txh = intent.register_tx_hash
        if not txh:
            raise ProductError("invalid_status", "No register transaction hash has been submitted.")
        receipt = self.rpc.get_transaction_receipt(txh)
        if receipt is None:
            intent.status = STATUS_SUBMITTED
            intent.note = "Register transaction not yet mined."
            return intent.public()
        status = receipt.get("status")
        ok = status in (1, "0x1", "1")
        if not ok:
            intent.status = STATUS_FAILED
            intent.note = "Register transaction reverted. Name was not registered."
            self.store.put(intent)
            return intent.public()
        if not _has_name_registered(receipt, intent.label, intent.registrant):
            intent.status = STATUS_SUBMITTED
            intent.note = (
                "Receipt succeeded but NameRegistered for this label and owner was not observed. "
                "Not treated as a DOMAIN.etn registration success."
            )
            self.store.put(intent)
            return intent.public()
        intent.status = STATUS_CONFIRMED
        intent.note = (
            "NameRegistered observed on the official controller for this label and owner. "
            "Ownership truth is the chain. EAE may index this fact later."
        )
        self.store.put(intent)
        return intent.public()

    def get(self, intent_id: str) -> dict:
        return self._require_intent(intent_id).public()

    def _require_intent(self, intent_id) -> RegistrationIntent:
        rec = self.store.get(str(intent_id or "").strip())
        if rec is None:
            raise ProductError("unknown_intent", "Unknown registration intent.", http_status=404)
        return rec


def _require_duration(duration) -> int:
    try:
        value = int(duration)
    except (TypeError, ValueError) as exc:
        raise ProductError("invalid_duration", "duration must be an integer number of seconds.") from exc
    if value < MIN_REGISTRATION_DURATION_SEC:
        raise ProductError(
            "invalid_duration",
            f"duration must be >= {MIN_REGISTRATION_DURATION_SEC} seconds (28 days).",
            {"min": MIN_REGISTRATION_DURATION_SEC},
        )
    return value


def _resolver_and_reverse(body: dict) -> tuple[str, int]:
    mode = str(body.get("resolver") or "public").strip().lower()
    if mode in {"", "public", "public_resolver"}:
        resolver = PUBLIC_RESOLVER
    elif mode in {"none", "zero", ZERO.lower()}:
        resolver = ZERO
    else:
        raise ProductError("wrong_contract", "resolver must be 'public' or 'none'. Arbitrary resolvers are refused.")
    if "reverse_record" in body and body["reverse_record"] is not None:
        reverse = int(body["reverse_record"])
        if reverse not in {0, 1, 2, 3}:
            raise ProductError("invalid_reverse_record", "reverse_record must be 0..3.")
    else:
        set_rev = body.get("set_reverse_record")
        reverse = REVERSE_RECORD_ETHEREUM_BIT if set_rev in (None, True, "true", "1", 1) else 0
    if reverse and resolver == ZERO:
        raise ProductError("invalid_reverse_record", "Reverse record requires the public resolver.")
    return resolver, reverse


def _reject_client_contract(body: dict) -> None:
    for key in ("controller", "contract", "to", "target"):
        raw = body.get(key)
        if not raw:
            continue
        text = str(raw).strip().lower()
        if text == UNUSED_CONTROLLER.lower():
            raise ProductError("wrong_contract", "Unused registrar controller is not a registration target.")
        if text != CONTROLLER.lower():
            raise ProductError("wrong_contract", "Client-supplied contract addresses are not trusted.")


def _reject_marketplace_mix(body: dict) -> None:
    for key in ("listing_id", "marketplace", "offer_id", "auction_id", "buy_now"):
        if body.get(key):
            raise ProductError(
                "wrong_flow",
                "Primary registration is not a marketplace purchase.",
                {"flow": FLOW_PRIMARY},
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


def labelhash_hex(label: str) -> str:
    """ENS labelhash: keccak256(bytes(label))."""
    return "0x" + _keccak(text=label).hex()


def _topic_address(addr: str) -> str:
    hexpart = str(addr).lower().replace("0x", "")
    return "0x" + hexpart.rjust(64, "0")


def _has_name_registered(receipt: dict, label: str, owner: str) -> bool:
    """Success = NameRegistered on the live controller for THIS label and owner.

    A NameRegistered log for a different name, or a different owner of the same
    name, is not this intent's success. topic0 alone is not enough.
    """
    logs = receipt.get("logs") or []
    want_ctrl = CONTROLLER.lower()
    want_topic0 = NAME_REGISTERED_TOPIC0.lower()
    want_label = labelhash_hex(label).lower()
    want_owner = _topic_address(owner)
    for log in logs:
        addr = str(log.get("address") or "").lower()
        topics = [str(t).lower() for t in (log.get("topics") or [])]
        if addr != want_ctrl or len(topics) < 3:
            continue
        if topics[0] != want_topic0:
            continue
        if topics[1] != want_label:
            continue
        if topics[2] != want_owner:
            continue
        return True
    return False
