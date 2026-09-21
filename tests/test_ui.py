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

    def test_discover_and_market_and_wallet_routes(self):
        client, _, _ = make_client()
        for path in ("/discover", "/market", "/w/0x1111111111111111111111111111111111111111"):
            res = client.get(path)
            self.assertEqual(res.status_code, 200, path)
            self.assertIn("text/html", res.headers.get("content-type", ""))

    def test_nav_contains_product_surfaces(self):
        html = (WEB / "index.html").read_text()
        for label in ("Search", "Discover", "My names", "Marketplace"):
            self.assertIn(label, html)

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

    def test_esc_uses_html_entities(self):
        app = (WEB / "js" / "app.js").read_text()
        self.assertIn("&", app)
        self.assertIn("<", app)

    def test_api_still_json(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/contract")
        self.assertEqual(res.json()["flows"]["renewal"], "implemented_prepare_only")
        self.assertFalse(res.json()["broadcasts"])

    def test_security_headers(self):
        client, _, _ = make_client()
        res = client.get("/")
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(res.headers.get("x-frame-options"), "DENY")
