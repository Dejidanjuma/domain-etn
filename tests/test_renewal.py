"""Prepare-only renewal. Pays rentPrice.base. Confirms NameRenewed."""

from __future__ import annotations

import unittest

from src.domain_etn.ens.addresses import CONTROLLER, UNUSED_CONTROLLER
from src.domain_etn.ens.encoding import NAME_RENEWED_TOPIC0, labelhash_hex
from tests.helpers import REGISTRANT, YEAR, make_client

TX = "0x" + "cd" * 32


class RenewalTests(unittest.TestCase):
    def test_quote_registered_name(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/renewal/quote", params={"name": "taken.etn", "duration": YEAR})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["flow"], "renewal")
        self.assertEqual(body["price"]["charged"], "base")
        self.assertEqual(body["price"]["total"], str(2 * 10**18))

    def test_cannot_renew_available_name(self):
        client, _, _ = make_client()
        res = client.get("/api/v1/renewal/quote", params={"name": "alice.etn", "duration": YEAR})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "not_renewable")

    def test_prepare_uses_controller_and_base_value(self):
        client, _, _ = make_client()
        quote = client.get("/api/v1/renewal/quote", params={"name": "taken.etn", "duration": YEAR}).json()
        res = client.post(
            "/api/v1/renewal/prepare",
            json={
                "name": "taken.etn",
                "quote_token": quote["quote_token"],
                "payer": REGISTRANT,
                "controller": UNUSED_CONTROLLER,
            },
        )
        self.assertEqual(res.status_code, 400)
        res = client.post(
            "/api/v1/renewal/prepare",
            json={"name": "taken.etn", "quote_token": quote["quote_token"], "payer": REGISTRANT},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["renew_tx"]["to"], CONTROLLER)
        self.assertEqual(body["renew_tx"]["from"], REGISTRANT)
        self.assertEqual(body["renew_tx"]["value"], str(2 * 10**18))
        self.assertTrue(body["renew_tx"]["data"].startswith("0x18026ad1"))

    def test_confirm_requires_name_renewed_for_label(self):
        client, _, _ = make_client(
            receipts={
                TX: {
                    "status": "0x1",
                    "logs": [
                        {
                            "address": CONTROLLER,
                            "topics": [NAME_RENEWED_TOPIC0, labelhash_hex("taken")],
                            "data": "0x",
                        }
                    ],
                }
            }
        )
        quote = client.get("/api/v1/renewal/quote", params={"name": "taken.etn", "duration": YEAR}).json()
        prep = client.post(
            "/api/v1/renewal/prepare",
            json={"name": "taken.etn", "quote_token": quote["quote_token"], "payer": REGISTRANT},
        ).json()
        client.post(f"/api/v1/renewal/{prep['intent_id']}/submitted", json={"tx_hash": TX})
        res = client.post(f"/api/v1/renewal/{prep['intent_id']}/confirm")
        self.assertEqual(res.json()["status"], "confirmed")
        self.assertTrue(res.json()["success"])

    def test_wrong_label_is_not_success(self):
        client, _, _ = make_client(
            receipts={
                TX: {
                    "status": "0x1",
                    "logs": [
                        {
                            "address": CONTROLLER,
                            "topics": [NAME_RENEWED_TOPIC0, labelhash_hex("other")],
                            "data": "0x",
                        }
                    ],
                }
            }
        )
        quote = client.get("/api/v1/renewal/quote", params={"name": "taken.etn", "duration": YEAR}).json()
        prep = client.post(
            "/api/v1/renewal/prepare",
            json={"name": "taken.etn", "quote_token": quote["quote_token"], "payer": REGISTRANT},
        ).json()
        client.post(f"/api/v1/renewal/{prep['intent_id']}/submitted", json={"tx_hash": TX})
        res = client.post(f"/api/v1/renewal/{prep['intent_id']}/confirm")
        self.assertFalse(res.json()["success"])
        self.assertNotEqual(res.json()["status"], "confirmed")

    def test_registration_quote_cannot_enter_renewal(self):
        client, _, service = make_client()
        reg_quote = service.quote("alice.etn", YEAR)
        res = client.post(
            "/api/v1/renewal/prepare",
            json={"name": "taken.etn", "quote_token": reg_quote["quote_token"], "payer": REGISTRANT},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "wrong_flow")


if __name__ == "__main__":
    unittest.main()
