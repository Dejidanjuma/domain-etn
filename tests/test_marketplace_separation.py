"""Primary registration is not a marketplace purchase."""

from __future__ import annotations

import unittest

from tests.helpers import ALICE, REGISTRANT, SECRET, YEAR, make_client


class MarketplaceSeparationTests(unittest.TestCase):
    def test_marketplace_route_is_not_implemented(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/marketplace")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["flow"], "secondary_marketplace")
        self.assertEqual(body["status"], "not_implemented")

    def test_listing_id_cannot_enter_primary_flow(self):
        client, _, service = make_client()
        quote = service.quote(ALICE, YEAR)
        res = client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
                "listing_id": "sale-1",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "wrong_flow")

    def test_contract_separates_flows(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/contract").json()
        self.assertEqual(body["flows"]["primary_registration"], "implemented_prepare_only")
        self.assertEqual(body["flows"]["secondary_marketplace"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
