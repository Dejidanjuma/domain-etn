"""EAE intelligence is optional, observational, and never registers."""

from __future__ import annotations

import unittest

from tests.helpers import REGISTRANT, make_client


class FakeIntelEae:
    def enabled(self):
        return True

    def investigate(self, address):
        return {"kind": "investigation", "address": address}

    def owner_domains(self, address):
        return {"domains": [{"name": "taken.etn", "nft_owner": address}]}

    def owner_intelligence(self, address):
        return {"kind": "owner", "address": address, "indexed": True, "related_addresses": []}

    def domain_search(self, name):
        return {"q": name, "results": [{"name": "taken.etn"}]}

    def catalog_search(self, q=None, prefix=None):
        return {"results": [{"normalized_name": "taken.etn", "name": "taken.etn"}], "q": q, "prefix": prefix}

    def domain_profile(self, name):
        return {
            "kind": "profile",
            "indexed": True,
            "status": "indexed",
            "history": {
                "events": [
                    {
                        "event_type": "NameRegistered",
                        "label": "Registered",
                        "block_number": 1,
                        "tx_hash": "0xabc",
                        "sale": "not_inferred",
                    }
                ]
            },
            "related_addresses": [{"role": "nft_owner", "address": REGISTRANT}],
            "marketplace": {"status": "no_indexed_marketplace_facts"},
            "layers": {"indexed_facts": "catalog rows"},
        }

    def domain_history(self, name):
        return {
            "events": [
                {"event_type": "NameRegistered", "label": "Registered", "block_number": 1, "tx_hash": "0xabc"}
            ]
        }

    def domain_marketplace(self, name):
        return {"status": "no_indexed_marketplace_facts"}

    def discovery(self):
        return {
            "categories": {"recently_registered": [{"name": "taken.etn"}], "recently_seen": [{"name": "taken.etn"}]},
            "recent_registrations": [{"name": "taken.etn"}],
        }

    def marketplace_listings(self, status=None):
        return {"results": [], "matched_count": 0, "status": status}

    def marketplace_activity(self):
        return {"results": [], "matched_count": 0}


class IntelligenceTests(unittest.TestCase):
    def test_profile_without_eae_is_honest(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/domains/profile", params={"name": "taken.etn"}).json()
        self.assertTrue(body["eae_is_not_ownership_source"])
        self.assertFalse(body["intelligence"]["configured"])
        self.assertEqual(body["intelligence"]["history"], [])

    def test_profile_with_eae_keeps_layers(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/domains/profile", params={"name": "taken.etn"}).json()
        self.assertTrue(body["intelligence"]["configured"])
        self.assertEqual(body["intelligence"]["history"][0]["event_type"], "NameRegistered")
        self.assertEqual(body["intelligence"]["history"][0]["sale"], "not_inferred")
        self.assertEqual(body["owner"].lower(), REGISTRANT.lower())
        self.assertTrue(body["eae_is_not_ownership_source"])

    def test_history_route(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/domains/history", params={"name": "taken.etn"}).json()
        self.assertEqual(body["authority"], "eae_indexed_facts")
        self.assertEqual(body["sale"], "not_inferred")
        self.assertEqual(body["events"][0]["event_type"], "NameRegistered")

    def test_transfer_sale_claim_is_not_repeated(self):
        class Hostile(FakeIntelEae):
            def domain_history(self, name):
                return {
                    "events": [
                        {
                            "event_type": "Transfer",
                            "sale": True,
                            "tx_hash": "0xabc",
                            "from": REGISTRANT,
                            "to": "0x0000000000000000000000000000000000000001",
                        }
                    ]
                }

            def domain_profile(self, name):
                payload = super().domain_profile(name)
                payload["history"]["events"][0]["event_type"] = "Transfer"
                payload["history"]["events"][0]["sale"] = True
                return payload

        client, _, _ = make_client(eae=Hostile())
        history = client.get("/api/v1/domains/history", params={"name": "taken.etn"}).json()
        self.assertEqual(history["events"][0]["event_type"], "Transfer")
        self.assertEqual(history["events"][0]["sale"], "not_inferred")
        profile = client.get("/api/v1/domains/profile", params={"name": "taken.etn"}).json()
        self.assertEqual(profile["intelligence"]["history"][0]["sale"], "not_inferred")

    def test_history_without_eae(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/domains/history", params={"name": "taken.etn"}).json()
        self.assertEqual(body["authority"], "not_queried")
        self.assertEqual(body["events"], [])

    def test_discovery_without_eae(self):
        client, _, _ = make_client()
        body = client.get("/api/v1/domains/discovery").json()
        self.assertEqual(body["authority"], "not_queried")
        self.assertTrue(body["not_availability"])
        self.assertTrue(body["not_ranking"])

    def test_discovery_with_eae(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/domains/discovery").json()
        self.assertEqual(body["authority"], "eae_indexed_facts")
        self.assertEqual(body["categories"]["recently_registered"][0]["name"], "taken.etn")

    def test_indexed_search_is_not_availability(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get("/api/v1/domains/search", params={"prefix": "tak"}).json()
        self.assertTrue(body["not_availability"])
        self.assertEqual(body["results"][0]["name"], "taken.etn")

    def test_owner_intelligence(self):
        client, _, _ = make_client(eae=FakeIntelEae())
        body = client.get(f"/api/v1/owners/{REGISTRANT}").json()
        self.assertTrue(body["not_ownership_source"])
        self.assertTrue(body["not_identity"])
        self.assertEqual(body["domains"][0]["name"], "taken.etn")
