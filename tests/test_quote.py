"""Quotes, duration, stale tokens, wrong network."""

from __future__ import annotations

import unittest

from src.domain_etn.ens.addresses import MIN_REGISTRATION_DURATION_SEC
from tests.helpers import YEAR, make_client


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.client, self.rpc, self.service = make_client()

    def test_valid_quote(self):
        res = self.client.get("/api/v1/domains/quote", params={"name": "alice.etn", "duration": YEAR})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["price"]["total"], str(10**18))
        self.assertEqual(body["price"]["unit"], "wei")
        self.assertIn("quote_token", body)
        self.assertEqual(body["controller"][:2], "0x")

    def test_quote_unavailable(self):
        res = self.client.get("/api/v1/domains/quote", params={"name": "taken.etn", "duration": YEAR})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "unavailable_domain")

    def test_invalid_duration(self):
        res = self.client.get(
            "/api/v1/domains/quote",
            params={"name": "alice.etn", "duration": MIN_REGISTRATION_DURATION_SEC - 1},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "invalid_duration")

    def test_stale_quote(self):
        quote = self.service.quote("alice.etn", YEAR, now=100)
        with self.assertRaises(Exception) as ctx:
            self.service.prepare_commit(
                {
                    "name": "alice.etn",
                    "quote_token": quote["quote_token"],
                    "registrant": "0x1111111111111111111111111111111111111111",
                    "secret": "0x" + "22" * 32,
                },
                now=10_000,
            )
        self.assertEqual(ctx.exception.code, "stale_quote")

    def test_wrong_network(self):
        client, _, _ = make_client(chain_id=1)
        res = client.get("/api/v1/domains/availability", params={"name": "alice.etn"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "wrong_network")


if __name__ == "__main__":
    unittest.main()
