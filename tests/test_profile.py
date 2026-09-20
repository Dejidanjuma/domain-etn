"""Live domain profile from base registrar + controller."""

from __future__ import annotations

import time
import unittest

from tests.helpers import ALICE, REGISTRANT, YEAR, make_client


class ProfileTests(unittest.TestCase):
    def test_available_profile(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/domains/profile", params={"name": ALICE})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["available"])
        self.assertEqual(body["status"], "available")
        self.assertIsNone(body["owner"])
        self.assertFalse(body["renewable"])
        self.assertTrue(body["eae_is_not_ownership_source"])

    def test_registered_profile(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/domains/profile", params={"name": "taken.etn"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["status"], "registered")
        self.assertEqual(body["owner"].lower(), REGISTRANT.lower())
        self.assertTrue(body["renewable"])
        self.assertTrue(body["expires_at"] > int(time.time()))
        self.assertEqual(body["marketplace"]["status"], "not_implemented")

    def test_invalid_name(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/domains/profile", params={"name": "ab.etn"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "invalid_domain")

    def test_grace_period_hides_owner_if_ownerOf_reverts(self):
        now = int(time.time())
        client, _, _ = make_client(owners={}, expiries={"taken": now - 60})
        res = client.get("/api/v1/domains/profile", params={"name": "taken.etn"})
        body = res.json()
        self.assertFalse(body["available"])
        self.assertIsNone(body["owner"])
        self.assertTrue(body["in_grace"])
        self.assertTrue(body["renewable"])


if __name__ == "__main__":
    unittest.main()
