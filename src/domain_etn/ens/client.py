"""Read-only Electroneum ENS calls. Never broadcasts."""

from __future__ import annotations

from eth_abi import decode
from eth_utils import to_checksum_address

from src.domain_etn.ens.addresses import BASE_REGISTRAR, CHAIN_ID, CONTROLLER, ZERO
from src.domain_etn.ens.encoding import (
    call_available,
    call_commitments,
    call_name_expires,
    call_owner_of,
    call_rent_price,
    call_valid,
    token_id,
)
from src.domain_etn.errors import ProductError
from src.domain_etn.rpc import Rpc


def _decode_bool(raw: str) -> bool:
    if not raw or raw == "0x":
        return False
    return int(raw, 16) != 0


def _decode_uint(raw: str) -> int:
    if not raw or raw == "0x":
        return 0
    blob = bytes.fromhex(raw[2:] if raw.startswith("0x") else raw)
    if not blob:
        return 0
    return int.from_bytes(blob[-32:] if len(blob) >= 32 else blob, "big")


def _decode_price(raw: str) -> tuple[int, int]:
    blob = bytes.fromhex(raw[2:] if raw.startswith("0x") else raw)
    if len(blob) < 64:
        raise ProductError("rpc_error", "rentPrice returned a short payload.", http_status=502)
    base, premium = decode(["uint256", "uint256"], blob[:64])
    return int(base), int(premium)


def _decode_address(raw: str) -> str | None:
    if not raw or raw == "0x":
        return None
    blob = bytes.fromhex(raw[2:] if raw.startswith("0x") else raw)
    if len(blob) < 20:
        return None
    addr = "0x" + blob[-20:].hex()
    if int(addr, 16) == 0:
        return None
    return to_checksum_address(addr)


class EnsReader:
    def __init__(self, rpc: Rpc):
        self.rpc = rpc

    def require_chain(self) -> int:
        try:
            live = int(self.rpc.chain_id())
        except ProductError:
            raise
        except Exception as exc:
            raise ProductError("rpc_error", "Could not read chain id.", http_status=502) from exc
        if live != CHAIN_ID:
            raise ProductError(
                "wrong_network",
                f"RPC chain_id {live} is not Electroneum ({CHAIN_ID}).",
                {"expected": CHAIN_ID, "actual": live},
            )
        return live

    def available(self, label: str) -> bool:
        self.require_chain()
        raw = self.rpc.call(CONTROLLER, call_available(label))
        return _decode_bool(raw)

    def valid_onchain(self, label: str) -> bool:
        raw = self.rpc.call(CONTROLLER, call_valid(label))
        return _decode_bool(raw)

    def rent_price(self, label: str, duration: int) -> dict:
        self.require_chain()
        raw = self.rpc.call(CONTROLLER, call_rent_price(label, duration))
        base, premium = _decode_price(raw)
        return {
            "base": str(base),
            "premium": str(premium),
            "total": str(base + premium),
            "currency": "ETN",
            "unit": "wei",
        }

    def owner_of(self, label: str) -> str | None:
        self.require_chain()
        raw = self.rpc.try_call(BASE_REGISTRAR, call_owner_of(token_id(label)))
        return _decode_address(raw or "")

    def name_expires(self, label: str) -> int:
        self.require_chain()
        raw = self.rpc.try_call(BASE_REGISTRAR, call_name_expires(token_id(label)))
        return _decode_uint(raw or "0x")

    def commitment_timestamp(self, commitment: str) -> int:
        self.require_chain()
        raw = self.rpc.call(CONTROLLER, call_commitments(commitment))
        return _decode_uint(raw)


def checksum_wallet(addr: str) -> str:
    try:
        if not addr or not str(addr).strip():
            raise ValueError
        out = to_checksum_address(addr)
    except Exception as exc:
        raise ProductError("invalid_wallet", "registrant must be a 20-byte address.") from exc
    if int(out, 16) == 0 or out.lower() == ZERO.lower():
        raise ProductError("invalid_wallet", "registrant cannot be the zero address.")
    return out
