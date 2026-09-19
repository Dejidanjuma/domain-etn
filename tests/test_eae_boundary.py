"""EAE cannot register. Owner lists are not a local ownership table."""

from __future__ import annotations

import unittest

from tests.helpers import ALICE, REGISTRANT, SECRET, YEAR, make_client


class FakeEae:
    def enabled(self):
        return True

    def investigate(self, address):
        return {"type": "investigation", "address": address, "source": "eae"}

    def domain_search(self, name):
        return {"q": name}


class EaeBoundaryTests(unittest.TestCase):
    def test_prepare_rejects_via_eae(self):
        client, _, service = make_client()
        quote = service.quote(ALICE, YEAR)
        res = client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
                "via": "eae",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "wrong_layer")

    def test_owner_domains_are_not_local_authority(self):
        client, _, _ = make_client(eae=FakeEae())
        res = client.get(f"/api/v1/owners/{REGISTRANT}/domains")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["not_ownership_source"])
        self.assertEqual(body["eae"]["source"], "eae")


if __name__ == "__main__":
    unittest.main()
