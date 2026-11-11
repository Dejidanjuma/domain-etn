"""Process configuration. No private keys. Safe localhost defaults."""

from __future__ import annotations

import os
import secrets


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


class Settings:
    host: str
    port: int
    rpc_url: str
    quote_secret: bytes
    eae_url: str | None
    chain_id: int
    quote_ttl_sec: int
    intent_ttl_sec: int

    def __init__(self) -> None:
        self.host = os.getenv("DOMAIN_ETN_HOST", "127.0.0.1").strip() or "127.0.0.1"
        self.port = _int("DOMAIN_ETN_PORT", 8081)
        self.rpc_url = (
            os.getenv("DOMAIN_ETN_RPC_URL", "https://rpc.ankr.com/electroneum").strip()
            or "https://rpc.ankr.com/electroneum"
        )
        secret = os.getenv("DOMAIN_ETN_QUOTE_SECRET", "").strip()
        deployment_env = os.getenv("DOMAIN_ETN_ENV", "").strip().lower()
        hosted_runtime = any(
            os.getenv(name, "").strip()
            for name in ("RENDER", "RENDER_SERVICE_ID", "VERCEL", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME")
        )
        loopback_bind = self.host in {"127.0.0.1", "localhost", "::1"}
        explicit_local_mode = deployment_env in {"development", "test", "local"}
        implicit_local_default = not deployment_env and "DOMAIN_ETN_HOST" not in os.environ and loopback_bind and not hosted_runtime
        production = hosted_runtime or deployment_env == "production" or not (
            explicit_local_mode or implicit_local_default
        )
        if not secret and production:
            raise RuntimeError(
                "DOMAIN_ETN_QUOTE_SECRET must be configured in hosted/production environments"
            )
        self.quote_secret = secret.encode() if secret else secrets.token_bytes(32)
        eae = os.getenv("DOMAIN_ETN_EAE_URL", "").strip().rstrip("/")
        self.eae_url = eae or None
        self.chain_id = _int("DOMAIN_ETN_CHAIN_ID", 52014)
        self.quote_ttl_sec = _int("DOMAIN_ETN_QUOTE_TTL_SEC", 600)
        # Commitments expire after maxCommitmentAge (24h). Intent follows that bound.
        self.intent_ttl_sec = _int("DOMAIN_ETN_INTENT_TTL_SEC", 86400)


settings = Settings()
