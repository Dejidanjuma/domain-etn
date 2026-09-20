"""Product UI is served from the same origin. No keys. No fake success."""

from __future__ import annotations

import pathlib
import unittest

from tests.helpers import make_client

WEB = pathlib.Path(__file__).resolve().parents[1] / "web"


class UiTests(unittest.TestCase):
    def test_home_is_html(self):
        client, _, _ = make_client()
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Find your", res.text)
        self.assertIn("satoshi.etn", res.text)
        self.assertNotIn("seed phrase", res.text.lower())
        self.assertNotIn("private key", res.text.lower())

    def test_spa_fallback_for_domain_path(self):
        client, _, _ = make_client()
        res = client.get("/d/alice.etn")
        self.assertEqual(res.status_code, 200)
        self.assertIn("DOMAIN.etn", res.text)

    def test_me_route_is_html(self):
        client, _, _ = make_client()
        self.assertEqual(client.get("/me").status_code, 200)

    def test_js_state_machine_exists(self):
        flow = (WEB / "js" / "flow.js").read_text()
        self.assertIn("REGISTERED_SUCCESSFULLY", flow)
        self.assertIn("WAITING_FOR_COMMITMENT", flow)
        self.assertIn("function isSuccess", flow)

    def test_frontend_never_asks_for_keys(self):
        blob = ""
        for path in WEB.rglob("*"):
            if path.suffix in {".js", ".html", ".css"}:
                blob += path.read_text()
        for token in ("privateKey", "mnemonic", "seed phrase", "Account.from_key"):
            self.assertNotIn(token, blob)

    def test_api_still_json(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/contract")
        self.assertEqual(res.json()["flows"]["renewal"], "implemented_prepare_only")
        self.assertFalse(res.json()["broadcasts"])


if __name__ == "__main__":
    unittest.main()
