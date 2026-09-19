"""Calldata encoding for the verified Electroneum ETHRegistrarController.

Selectors and tuple layout were checked against the staging deployment ABI
and a live makeCommitment eth_call on chain 52014.
"""

from __future__ import annotations

from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, keccak, to_checksum_address

from src.domain_etn.ens.addresses import CONTROLLER, ZERO
from src.domain_etn.errors import ProductError

REGISTRATION_TUPLE = "(string,address,uint256,bytes32,address,bytes[],uint8,bytes32)"
COMMIT_SIG = "commit(bytes32)"
REGISTER_SIG = f"register({REGISTRATION_TUPLE})"
MAKE_COMMITMENT_SIG = f"makeCommitment({REGISTRATION_TUPLE})"
AVAILABLE_SIG = "available(string)"
VALID_SIG = "valid(string)"
RENT_PRICE_SIG = "rentPrice(string,uint256)"
COMMITMENTS_SIG = "commitments(bytes32)"
CHAIN_ID_SIG = "eth_chainId"

SEL_COMMIT = function_signature_to_4byte_selector(COMMIT_SIG)
SEL_REGISTER = function_signature_to_4byte_selector(REGISTER_SIG)
SEL_MAKE_COMMITMENT = function_signature_to_4byte_selector(MAKE_COMMITMENT_SIG)
SEL_AVAILABLE = function_signature_to_4byte_selector(AVAILABLE_SIG)
SEL_VALID = function_signature_to_4byte_selector(VALID_SIG)
SEL_RENT_PRICE = function_signature_to_4byte_selector(RENT_PRICE_SIG)
SEL_COMMITMENTS = function_signature_to_4byte_selector(COMMITMENTS_SIG)

# Live-verified 2026-09-19
assert SEL_AVAILABLE.hex() == "aeb8ce9b"
assert SEL_RENT_PRICE.hex() == "83e7f6ff"
assert SEL_COMMIT.hex() == "f14fcbc8"
assert SEL_REGISTER.hex() == "ef9c8805"
assert SEL_MAKE_COMMITMENT.hex() == "cf7d6e01"


def _addr(value: str) -> str:
    return to_checksum_address(value)


def _secret(raw: str) -> bytes:
    text = (raw or "").strip()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) != 64:
        raise ProductError("invalid_secret", "secret must be 32 bytes hex.")
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise ProductError("invalid_secret", "secret must be 32 bytes hex.") from exc


def _referrer(raw: str | None) -> bytes:
    if not raw:
        return b"\x00" * 32
    text = raw.strip()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) != 64:
        raise ProductError("invalid_referrer", "referrer must be bytes32 hex.")
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise ProductError("invalid_referrer", "referrer must be bytes32 hex.") from exc


def registration_tuple(
    *,
    label: str,
    owner: str,
    duration: int,
    secret: str,
    resolver: str,
    reverse_record: int,
    referrer: str | None = None,
) -> tuple:
    if reverse_record not in {0, 1, 2, 3}:
        raise ProductError("invalid_reverse_record", "reverse_record must be a 0..3 bitmask.")
    return (
        label,
        _addr(owner),
        int(duration),
        _secret(secret),
        _addr(resolver) if resolver and resolver != ZERO else ZERO,
        [],  # v1: never client-supplied resolver data
        int(reverse_record),
        _referrer(referrer),
    )


def encode_registration(reg: tuple) -> bytes:
    return encode([REGISTRATION_TUPLE], [reg])


def commitment_hash(reg: tuple) -> str:
    """Matches controller.makeCommitment: keccak256(abi.encode(registration))."""
    return "0x" + keccak(encode_registration(reg)).hex()


def call_available(label: str) -> str:
    return "0x" + SEL_AVAILABLE.hex() + encode(["string"], [label]).hex()


def call_valid(label: str) -> str:
    return "0x" + SEL_VALID.hex() + encode(["string"], [label]).hex()


def call_rent_price(label: str, duration: int) -> str:
    return "0x" + SEL_RENT_PRICE.hex() + encode(["string", "uint256"], [label, int(duration)]).hex()


def call_commitments(commitment: str) -> str:
    raw = commitment[2:] if commitment.startswith("0x") else commitment
    return "0x" + SEL_COMMITMENTS.hex() + encode(["bytes32"], [bytes.fromhex(raw)]).hex()


def tx_commit(commitment: str) -> dict:
    raw = commitment[2:] if commitment.startswith("0x") else commitment
    data = "0x" + SEL_COMMIT.hex() + encode(["bytes32"], [bytes.fromhex(raw)]).hex()
    return {
        "to": CONTROLLER,
        "value": "0",
        "data": data,
        "chain_id": 52014,
    }


def tx_register(reg: tuple, value_wei: int) -> dict:
    data = "0x" + SEL_REGISTER.hex() + encode_registration(reg).hex()
    return {
        "to": CONTROLLER,
        "value": str(int(value_wei)),
        "data": data,
        "chain_id": 52014,
    }
