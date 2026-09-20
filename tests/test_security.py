"""No keys, no broadcast, no arbitrary execution."""

from __future__ import annotations

import pathlib
import unittest

from src.domain_etn.rpc import BANNED_METHODS, HttpRpc
from tests.helpers import make_client

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"


class SecurityTests(unittest.TestCase):
    def test_source_has_no_keys_or_signing(self):
        blob = ""
        for path in ROOT.rglob("*.py"):
            blob += path.read_text()
        for token in ("Account.from_key", "privateKey", "mnemonic", "eth_account"):
            self.assertNotIn(token, blob)

    def test_web_has_no_key_prompts(self):
        web = pathlib.Path(__file__).resolve().parents[1] / "web"
        blob = ""
        for path in web.rglob("*"):
            if path.suffix in {".js", ".html"}:
                blob += path.read_text()
        for token in ("Account.from_key", "privateKey", "mnemonic", "seed phrase"):
            self.assertNotIn(token, blob)

    def test_broadcast_methods_are_hard_refused(self):
        self.assertIn("eth_sendRawTransaction", BANNED_METHODS)
        self.assertIn("eth_sendTransaction", BANNED_METHODS)
        rpc = HttpRpc("http://127.0.0.1:1")
        with self.assertRaises(Exception) as ctx:
            rpc._request("eth_sendRawTransaction", ["0x"])
        self.assertEqual(ctx.exception.code, "forbidden_rpc")

    def test_no_execute_endpoint(self):
        client, _, _ = make_client()
        for path in ("/api/v1/execute", "/api/v1/tx", "/api/v1/send", "/api/v1/broadcast"):
            res = client.post(path, json={"data": "0x"})
            self.assertEqual(res.status_code, 404)

    def test_contract_descriptor_security_flags(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/contract").json()
        self.assertFalse(body["custodial"])
        self.assertFalse(body["broadcasts"])
        self.assertFalse(body["private_keys"])
        self.assertFalse(body["registrar"])
        self.assertEqual(body["registration"]["payment"], "native_ETN")


if __name__ == "__main__":
    unittest.main()
