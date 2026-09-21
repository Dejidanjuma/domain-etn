"""Marketplace settlement stays off. Indexed rows are not purchases."""

from __future__ import annotations

import unittest

from tests.helpers import make_client
from tests.test_intelligence import FakeIntelEae


class MarketplaceObserveTests(unittest.TestCase):
    def test_descriptor_still_not_implemented(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/marketplace").json()
        self.assertEqual(body["status"], "not_implemented")
        self.assertEqual(body["settlement"], "not_implemented")
        self.assertFalse(body["deployed"])
        self.assertFalse(body["production_deploy_enabled"])
        self.assertIsNone(body["marketplace_contract_address"])
        self.assertEqual(body["capabilities"]["buy_now"], "not_implemented")
        self.assertEqual(body["capabilities"]["offers"], "not_implemented")
        self.assertEqual(body["capabilities"]["auctions"], "not_implemented")
        self.assertIn("offers", body["deferred"])

    def test_listings_without_eae_are_empty(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/marketplace/listings").json()
        self.assertEqual(body["settlement"], "not_implemented")
        self.assertFalse(body["purchasable"])
        self.assertEqual(body["authority"], "not_queried")
        self.assertEqual(body["listings"], [])

    def test_listings_with_eae_are_not_purchasable(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/marketplace/listings").json()
        self.assertEqual(body["buy_now"], "not_implemented")
        self.assertFalse(body["purchasable"])
        self.assertTrue(body["not_authorization"])
        self.assertEqual(body["listings"], [])

    def test_activity_does_not_infer_sales(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/marketplace/activity").json()
        self.assertEqual(body["sale_proof"], "ListingPurchased event only")
        self.assertEqual(body["settlement"], "not_implemented")

    def test_no_prepare_purchase_endpoint(self):
        client, _, _ = make_client()
        for path in (
            "/api/v1/marketplace/buy",
            "/api/v1/marketplace/prepare-buy",
            "/api/v1/marketplace/prepare-listing",
            "/api/v1/marketplace/prepare-cancel",
        ):
            res = client.post(path, json={"listing_id": "0x1"})
            self.assertEqual(res.status_code, 404)

    def test_contract_marketplace_address_is_null(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/contract").json()
        self.assertEqual(body["flows"]["secondary_marketplace"], "not_implemented")
        self.assertIsNone(body["contracts"]["marketplace"])
        self.assertEqual(body["marketplace"]["status"], "not_implemented")
