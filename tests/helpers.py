"""Shared fakes for DOMAIN.etn tests. No live RPC. No wallets."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from src.domain_etn.api.app import create_app
from src.domain_etn.config import Settings
from src.domain_etn.eae.client import EaeClient
from src.domain_etn.registration.service import RegistrationService
from src.domain_etn.renewal.service import RenewalService
from src.domain_etn.rpc import MockRpc

SECRET = "0x" + "22" * 32
REGISTRANT = "0x1111111111111111111111111111111111111111"
YEAR = 365 * 24 * 3600
ALICE = "alice.etn"
TAKEN = "taken.etn"


class DummySettings(Settings):
    def __init__(self):
        super().__init__()
        self.quote_secret = b"test-quote-secret-32-bytes-long!"
        self.quote_ttl_sec = 600
        self.intent_ttl_sec = 86400
        self.eae_url = None
        self.chain_id = 52014


def make_client(
    *,
    available=None,
    prices=None,
    receipts=None,
    chain_id=52014,
    eae=None,
    owners=None,
    expiries=None,
    commitments=None,
):
    rpc = MockRpc(
        chain_id=chain_id,
        available=available if available is not None else {"alice": True, "taken": False, "wallet": False},
        prices=prices or {"alice": (10**18, 0), "taken": (2 * 10**18, 0), "wallet": (10**18, 0)},
        receipts=receipts or {},
        owners=owners if owners is not None else {"taken": REGISTRANT, "wallet": REGISTRANT},
        expiries=expiries if expiries is not None else {"taken": int(time.time()) + YEAR, "wallet": int(time.time()) + YEAR},
        commitments=commitments or {},
    )
    settings = DummySettings()
    service = RegistrationService(rpc, settings=settings)
    renewal = RenewalService(rpc, settings=settings)
    app = create_app(rpc=rpc, service=service, renewal=renewal, eae=eae or EaeClient(None))
    return TestClient(app, raise_server_exceptions=False), rpc, service


def mature_commitment(rpc, commitment, *, now=None):
    ts = int(now if now is not None else time.time()) - 61
    rpc.commitments[str(commitment).lower()] = ts
    return ts
