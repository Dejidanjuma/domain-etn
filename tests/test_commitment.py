"""Commitment wait is sourced from controller.commitments, not only the UI clock."""

from __future__ import annotations

import time
import unittest

from tests.helpers import ALICE, REGISTRANT, SECRET, YEAR, make_client, mature_commitment


class CommitmentTests(unittest.TestCase):
    def test_commitment_not_on_chain(self):
        client, _, service = make_client()
        quote = service.quote(ALICE, YEAR)
        commit = service.prepare_commit(
            {"name": ALICE, "quote_token": quote["quote_token"], "registrant": REGISTRANT, "secret": SECRET}
        )
        res = client.get(f"/api/v1/registration/{commit['intent_id']}/commitment")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body["committed"])
        self.assertFalse(body["ready"])

    def test_commitment_ready_after_min_age(self):
        client, rpc, service = make_client()
        quote = service.quote(ALICE, YEAR)
        commit = service.prepare_commit(
            {"name": ALICE, "quote_token": quote["quote_token"], "registrant": REGISTRANT, "secret": SECRET}
        )
        mature_commitment(rpc, commit["commitment"])
        res = client.get(f"/api/v1/registration/{commit['intent_id']}/commitment")
        body = res.json()
        self.assertTrue(body["committed"])
        self.assertTrue(body["ready"])
        self.assertEqual(body["min_commitment_age_sec"], 60)

    def test_unknown_intent_recovery(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/registration/does-not-exist")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"], "unknown_intent")


if __name__ == "__main__":
    unittest.main()
