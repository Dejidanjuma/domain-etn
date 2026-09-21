"""Lifecycle labels come from live ENS reads, not invention."""

from __future__ import annotations

import time
import unittest

from src.domain_etn.domains.lifecycle import EXPIRING_SOON_SEC, classify
from tests.helpers import make_client


class LifecycleTests(unittest.TestCase):
    def test_available(self):
        now = 1_700_000_000
        life = classify(available=True, expires_at=0, now=now)
        self.assertEqual(life["state"], "available")
        self.assertFalse(life["renewable"])
        self.assertFalse(life["in_grace"])

    def test_active(self):
        now = 1_700_000_000
        life = classify(available=False, expires_at=now + 400 * 24 * 3600, now=now)
        self.assertEqual(life["state"], "active")
        self.assertTrue(life["renewable"])

    def test_expiring_soon_is_presentation_only(self):
        now = 1_700_000_000
        life = classify(available=False, expires_at=now + 10 * 24 * 3600, now=now)
        self.assertEqual(life["state"], "expiring_soon")
        self.assertTrue(life["expiring_soon"])
        self.assertFalse(life["expiring_soon_is_on_chain"])
        self.assertEqual(life["expiring_soon_threshold_sec"], EXPIRING_SOON_SEC)

    def test_grace(self):
        now = 1_700_000_000
        life = classify(available=False, expires_at=now - 60, now=now)
        self.assertEqual(life["state"], "grace")
        self.assertTrue(life["in_grace"])
        self.assertTrue(life["renewable"])

    def test_profile_embeds_lifecycle(self):
        client, _, _ = make_client()
        available = client.get("/api/v1/domains/profile", params={"name": "alice.etn"}).json()
        self.assertEqual(available["lifecycle"]["state"], "available")
        taken = client.get("/api/v1/domains/profile", params={"name": "taken.etn"}).json()
        self.assertEqual(taken["status"], "registered")
        self.assertIn(taken["lifecycle"]["state"], {"active", "expiring_soon"})

    def test_profile_grace_lifecycle(self):
        now = int(time.time())
        client, _, _ = make_client(owners={}, expiries={"taken": now - 60})
        body = client.get("/api/v1/domains/profile", params={"name": "taken.etn"}).json()
        self.assertEqual(body["lifecycle"]["state"], "grace")
        self.assertTrue(body["in_grace"])
