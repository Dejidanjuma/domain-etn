"""Intent lifecycle: submitted, failed, confirmed. Never success from prepare."""

from __future__ import annotations

import unittest

from src.domain_etn.ens.addresses import CONTROLLER
from src.domain_etn.registration.service import NAME_REGISTERED_TOPIC0, labelhash_hex
from tests.helpers import ALICE, REGISTRANT, SECRET, YEAR, make_client

TX = "0x" + "ab" * 32
OTHER_OWNER = "0x2222222222222222222222222222222222222222"


def _owner_topic(addr: str) -> str:
    return "0x" + addr.lower().replace("0x", "").rjust(64, "0")


def _name_registered_log(label: str, owner: str) -> dict:
    return {
        "address": CONTROLLER,
        "topics": [NAME_REGISTERED_TOPIC0, labelhash_hex(label), _owner_topic(owner)],
        "data": "0x",
    }


class StatusTests(unittest.TestCase):
    def _prepared(self, receipts=None):
        client, rpc, service = make_client(receipts=receipts)
        quote = service.quote(ALICE, YEAR)
        commit = service.prepare_commit(
            {
                "name": ALICE,
                "quote_token": quote["quote_token"],
                "registrant": REGISTRANT,
                "secret": SECRET,
            }
        )
        service.prepare_register({"intent_id": commit["intent_id"], "secret": SECRET})
        return client, commit["intent_id"]

    def test_prepare_is_not_success(self):
        client, intent_id = self._prepared()
        body = client.get(f"/api/v1/registration/{intent_id}").json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "prepared")

    def test_submitted_is_not_confirmed(self):
        client, intent_id = self._prepared()
        res = client.post(
            f"/api/v1/registration/{intent_id}/submitted",
            json={"kind": "register", "tx_hash": TX},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "submitted")
        self.assertFalse(res.json()["success"])

    def test_failed_receipt(self):
        client, intent_id = self._prepared(receipts={TX: {"status": "0x0", "logs": []}})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertEqual(res.json()["status"], "failed")
        self.assertFalse(res.json()["success"])

    def test_confirmed_name_registered(self):
        receipt = {"status": "0x1", "logs": [_name_registered_log("alice", REGISTRANT)]}
        client, intent_id = self._prepared(receipts={TX: receipt})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertEqual(res.json()["status"], "confirmed")
        self.assertTrue(res.json()["success"])

    def test_name_registered_wrong_label_is_not_success(self):
        receipt = {"status": "0x1", "logs": [_name_registered_log("bob", REGISTRANT)]}
        client, intent_id = self._prepared(receipts={TX: receipt})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertNotEqual(res.json()["status"], "confirmed")
        self.assertFalse(res.json()["success"])

    def test_name_registered_wrong_owner_is_not_success(self):
        receipt = {"status": "0x1", "logs": [_name_registered_log("alice", OTHER_OWNER)]}
        client, intent_id = self._prepared(receipts={TX: receipt})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertNotEqual(res.json()["status"], "confirmed")
        self.assertFalse(res.json()["success"])

    def test_topic0_alone_is_not_success(self):
        receipt = {
            "status": "0x1",
            "logs": [{"address": CONTROLLER, "topics": [NAME_REGISTERED_TOPIC0], "data": "0x"}],
        }
        client, intent_id = self._prepared(receipts={TX: receipt})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertNotEqual(res.json()["status"], "confirmed")
        self.assertFalse(res.json()["success"])

    def test_success_without_event_is_not_confirmed(self):
        client, intent_id = self._prepared(receipts={TX: {"status": "0x1", "logs": []}})
        client.post(f"/api/v1/registration/{intent_id}/submitted", json={"kind": "register", "tx_hash": TX})
        res = client.post(f"/api/v1/registration/{intent_id}/confirm")
        self.assertNotEqual(res.json()["status"], "confirmed")
        self.assertFalse(res.json()["success"])


if __name__ == "__main__":
    unittest.main()
