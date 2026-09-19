"""Allowlisted Electroneum ENS addresses.

Verified against electroneum/ens-contracts deployments/electroneum
and live eth_getCode / constructor args / eth_call on chain 52014.

The unused controller is listed so it can be refused, never targeted.
"""

from __future__ import annotations

from eth_utils import to_checksum_address

CHAIN_ID = 52014
CHAIN_NAME = "electroneum"

# Live ETHRegistrarController — only canonical registration target.
CONTROLLER = to_checksum_address("0x3CFa6D6E7e1216393C2cb9393Bc0f411492E33e9")
UNUSED_CONTROLLER = to_checksum_address("0x5cD5CEFDc5925cA6A9A38D2AA810d5aeD360b21C")
BASE_REGISTRAR = to_checksum_address("0x5207496C1248BbD2AeeDd57Bde44dd9d4E9F1b59")
REGISTRY = to_checksum_address("0x6F311F2212593165988Dff84977e24C1005dBb85")
PUBLIC_RESOLVER = to_checksum_address("0xDb4A3Abb6703232e20a118a104e7f4EbB3e2738D")
REVERSE_REGISTRAR = to_checksum_address("0xFBB14eDBD8D3f6E7BB240bFA388f6582df0d8E7A")
DEFAULT_REVERSE_REGISTRAR = to_checksum_address("0x3bED61fE4d7d3Bc79E46912Ee7ACce2c231aA0a6")
NAME_WRAPPER = to_checksum_address("0xd8F4B1A91469B05d9E0b15Cac4917Ee47b2A6f64")
PRICE_ORACLE = to_checksum_address("0x1F5A4178f3B1088e76eB82dC7A3Cb861E3864dE5")
USD_ORACLE = to_checksum_address("0xDB70711Ce7682DB0c0098D8eE3c3856a749D7C37")
ZERO = "0x0000000000000000000000000000000000000000"

# Constructor-immutables / live eth_call (2026-09-19, Ankr public RPC).
MIN_COMMITMENT_AGE_SEC = 60
MAX_COMMITMENT_AGE_SEC = 86_400
MIN_REGISTRATION_DURATION_SEC = 2_419_200  # 28 days
GRACE_PERIOD_SEC = 7_776_000  # 90 days

REVERSE_RECORD_ETHEREUM_BIT = 1
REVERSE_RECORD_DEFAULT_BIT = 2

ALLOWLIST = frozenset(
    {
        CONTROLLER.lower(),
        BASE_REGISTRAR.lower(),
        REGISTRY.lower(),
        PUBLIC_RESOLVER.lower(),
        REVERSE_REGISTRAR.lower(),
        DEFAULT_REVERSE_REGISTRAR.lower(),
        NAME_WRAPPER.lower(),
        PRICE_ORACLE.lower(),
        USD_ORACLE.lower(),
        ZERO,
    }
)


def checksum(addr: str) -> str:
    return to_checksum_address(addr)


def is_allowlisted(addr: str) -> bool:
    try:
        return checksum(addr).lower() in ALLOWLIST
    except Exception:
        return False


def is_forbidden_controller(addr: str) -> bool:
    try:
        return checksum(addr).lower() == UNUSED_CONTROLLER.lower()
    except Exception:
        return False
