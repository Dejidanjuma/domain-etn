"""Commit/register preparation, value, wallet, contract allowlist."""

from __future__ import annotations

import unittest

from src.domain_etn.ens.addresses import CONTROLLER, UNUSED_CONTROLLER
from tests.helpers import ALICE, REGISTRANT, SECRET, YEAR, make_client, mature_commitment


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.client, self.rpc, self.service = make_client()

    def _quote(self):
        return self.service.quote(ALICE, YEAR)

    def test_prepare_commit(self):
        quote = self._quote()
        res = self.client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "prepared")
        self.assertFalse(body["success"])
        self.assertEqual(body["commit_tx"]["to"], CONTROLLER)
        self.assertEqual(body["commit_tx"]["from"], REGISTRANT)
        self.assertEqual(body["commit_tx"]["value"], "0")
        self.assertTrue(body["commit_tx"]["data"].startswith("0xf14fcbc8"))
        self.assertEqual(body["commit_tx"]["chain_id"], 52014)
        self.assertIsNone(body["register_tx"])

    def test_prepare_register_native_value(self):
        quote = self._quote()
        commit = self.service.prepare_commit(
            {
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
            }
        )
        mature_commitment(self.rpc, commit["commitment"])
        res = self.client.post(
            "/api/v1/registration/prepare-register",
            json={"intent_id": commit["intent_id"], "secret": SECRET},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["register_tx"]["to"], CONTROLLER)
        self.assertEqual(body["register_tx"]["from"], REGISTRANT)
        self.assertEqual(body["register_tx"]["value"], str(10**18))
        self.assertTrue(body["register_tx"]["data"].startswith("0xef9c8805"))
        self.assertFalse(body["success"])

    def test_immature_commitment_is_refused(self):
        quote = self._quote()
        commit = self.service.prepare_commit(
            {
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
            }
        )
        res = self.client.post(
            "/api/v1/registration/prepare-register",
            json={"intent_id": commit["intent_id"], "secret": SECRET},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(res.json()["error"], {"commitment_not_found", "commitment_not_mature"})

    def test_wrong_secret_rejected(self):
        quote = self._quote()
        commit = self.service.prepare_commit(
            {
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
            }
        )
        res = self.client.post(
            "/api/v1/registration/prepare-register",
            json={"intent_id": commit["intent_id"], "secret": "0x" + "33" * 32},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "invalid_secret")

    def test_invalid_wallet(self):
        quote = self._quote()
        res = self.client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": "not-an-address",
                "secret": SECRET,
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "invalid_wallet")

    def test_wrong_contract_refused(self):
        quote = self._quote()
        res = self.client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
                "controller": UNUSED_CONTROLLER,
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "wrong_contract")

    def test_client_price_is_not_trusted(self):
        quote = self._quote()
        res = self.client.post(
            "/api/v1/registration/prepare-commit",
            json={
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
                "price_total": "1",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["price"]["total"], str(10**18))


if __name__ == "__main__":
    unittest.main()
