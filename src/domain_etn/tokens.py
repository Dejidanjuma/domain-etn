"""HMAC-signed quote tokens. No database. No client-trusted price."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from src.domain_etn.errors import ProductError


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_payload(payload: dict, secret: bytes) -> str:
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    mac = hmac.new(secret, blob, hashlib.sha256).digest()
    return _b64(blob) + "." + _b64(mac)


def verify_token(token: str, secret: bytes, *, now: int | None = None) -> dict:
    if not token or "." not in token:
        raise ProductError("invalid_quote", "Quote token is malformed.")
    body, mac = token.rsplit(".", 1)
    try:
        blob = _unb64(body)
        expected = hmac.new(secret, blob, hashlib.sha256).digest()
        given = _unb64(mac)
    except Exception as exc:
        raise ProductError("invalid_quote", "Quote token is malformed.") from exc
    if not hmac.compare_digest(expected, given):
        raise ProductError("invalid_quote", "Quote token signature is invalid.")
    try:
        payload = json.loads(blob.decode())
    except json.JSONDecodeError as exc:
        raise ProductError("invalid_quote", "Quote token is malformed.") from exc
    ts = int(now if now is not None else time.time())
    expires = int(payload.get("expires_at") or 0)
    if expires <= ts:
        raise ProductError("stale_quote", "Quote has expired. Request a new quote.", {"expires_at": expires})
    return payload
