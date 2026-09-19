"""Read-only JSON-RPC. No eth_sendTransaction. No accounts."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from src.domain_etn.errors import ProductError

BANNED_METHODS = frozenset(
    {
        "eth_sendTransaction",
        "eth_sendRawTransaction",
        "eth_sign",
        "eth_signTransaction",
        "personal_sign",
        "personal_sendTransaction",
    }
)


class Rpc(Protocol):
    def call(self, to: str, data: str) -> str: ...
    def chain_id(self) -> int: ...
    def get_transaction_receipt(self, tx_hash: str) -> dict | None: ...
    def get_code(self, address: str) -> str: ...


class HttpRpc:
    def __init__(self, url: str, *, timeout: float = 20.0):
        self.url = url
        self.timeout = timeout

    def _request(self, method: str, params: list) -> Any:
        if method in BANNED_METHODS:
            raise ProductError("forbidden_rpc", "Broadcast and signing RPC methods are disabled.", {"method": method}, 500)
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self.url, json=payload)
            res.raise_for_status()
            body = res.json()
        if body.get("error"):
            raise ProductError("rpc_error", "Read-only RPC call failed.", {"error": body["error"]}, 502)
        return body.get("result")

    def call(self, to: str, data: str) -> str:
        result = self._request("eth_call", [{"to": to, "data": data}, "latest"])
        return str(result or "0x")

    def chain_id(self) -> int:
        return int(self._request("eth_chainId", []), 16)

    def get_transaction_receipt(self, tx_hash: str) -> dict | None:
        result = self._request("eth_getTransactionReceipt", [tx_hash])
        return result

    def get_code(self, address: str) -> str:
        return str(self._request("eth_getCode", [address, "latest"]) or "0x")


class MockRpc:
    """In-process fake. Tests only."""

    def __init__(
        self,
        *,
        chain_id: int = 52014,
        available: dict[str, bool] | None = None,
        prices: dict[str, tuple[int, int]] | None = None,
        receipts: dict[str, dict] | None = None,
        commitments: dict[str, int] | None = None,
        code: str = "0x6000",
    ):
        self._chain_id = chain_id
        self.available_map = available or {}
        self.prices = prices or {}
        self.receipts = receipts or {}
        self.commitments = commitments or {}
        self.code = code
        self.calls: list[tuple[str, str]] = []

    def call(self, to: str, data: str) -> str:
        self.calls.append((to, data))
        sel = (data or "")[:10].lower()
        payload = data[10:] if data.startswith("0x") else data
        if sel == "0xaeb8ce9b":  # available(string)
            label = _decode_string(payload)
            flag = bool(self.available_map.get(label, True))
            return "0x" + ("1" if flag else "0").zfill(64)
        if sel == "0x83e7f6ff":  # rentPrice(string,uint256)
            label = _decode_string(payload)
            base, prem = self.prices.get(label, (10**18, 0))
            return "0x" + format(base, "064x") + format(prem, "064x")
        if sel == "0xcf7d6e01":  # makeCommitment — tests should use local keccak
            return "0x" + "00" * 32
        if sel == "0x339f540a":  # commitments(bytes32) actual selector computed later
            return "0x" + format(0, "064x")
        return "0x" + "00" * 32

    def chain_id(self) -> int:
        return int(self._chain_id)

    def get_transaction_receipt(self, tx_hash: str) -> dict | None:
        return self.receipts.get(tx_hash.lower())

    def get_code(self, address: str) -> str:
        return self.code


def _decode_string(payload_hex: str) -> str:
    raw = bytes.fromhex(payload_hex)
    if len(raw) < 64:
        return ""
    # dynamic string: offset, length, bytes
    offset = int.from_bytes(raw[0:32], "big")
    length = int.from_bytes(raw[offset : offset + 32], "big")
    return raw[offset + 32 : offset + 32 + length].decode("utf-8")
