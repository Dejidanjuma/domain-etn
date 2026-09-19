"""Availability and invalid names."""

from __future__ import annotations

import unittest

from tests.helpers import make_client


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.client, _, _ = make_client()

    def test_available_domain(self):
        res = self.client.get("/api/v1/domains/availability", params={"name": "alice.etn"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["available"])
        self.assertEqual(body["status"], "available")
        self.assertEqual(body["label"], "alice")
        self.assertEqual(body["flow"], "primary_registration")

    def test_unavailable_domain(self):
        res = self.client.get("/api/v1/domains/availability", params={"name": "taken.etn"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["available"])
        self.assertEqual(res.json()["status"], "unavailable")

    def test_invalid_domain_short(self):
        res = self.client.get("/api/v1/domains/availability", params={"name": "ab.etn"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "invalid_domain")

    def test_invalid_subdomain(self):
        res = self.client.get("/api/v1/domains/availability", params={"name": "a.b.etn"})
        self.assertEqual(res.status_code, 400)

    def test_non_etn(self):
        res = self.client.get("/api/v1/domains/availability", params={"name": "alice.eth"})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
