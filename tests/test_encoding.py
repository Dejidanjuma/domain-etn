"""Calldata matches the verified Electroneum controller ABI."""

from __future__ import annotations

import unittest

from eth_utils import keccak

from src.domain_etn.ens.encoding import (
    NAME_REGISTERED_TOPIC0,
    NAME_RENEWED_TOPIC0,
    SEL_COMMIT,
    SEL_MAKE_COMMITMENT,
    SEL_REGISTER,
    SEL_RENEW,
    commitment_hash,
    encode_registration,
    labelhash_hex,
    registration_tuple,
    tx_commit,
    tx_register,
    tx_renew,
)


class EncodingTests(unittest.TestCase):
    def test_selectors_match_live_controller(self):
        self.assertEqual(SEL_COMMIT.hex(), "f14fcbc8")
        self.assertEqual(SEL_REGISTER.hex(), "ef9c8805")
        self.assertEqual(SEL_MAKE_COMMITMENT.hex(), "cf7d6e01")
        self.assertEqual(SEL_RENEW.hex(), "18026ad1")

    def test_commitment_is_keccak_of_abi_encode(self):
        reg = registration_tuple(
            label="alice",
            owner="0x1111111111111111111111111111111111111111",
            duration=365 * 24 * 3600,
            secret="0x" + "22" * 32,
            resolver="0xDb4A3Abb6703232e20a118a104e7f4EbB3e2738D",
            reverse_record=1,
        )
        self.assertEqual(
            commitment_hash(reg),
            "0x90f05dc969a48b26211a4b684bccbfb318a05758850a738f5e87511f0699b4c0",
        )
        self.assertEqual("0x" + keccak(encode_registration(reg)).hex(), commitment_hash(reg))

    def test_commit_tx_has_zero_value(self):
        tx = tx_commit("0x" + "11" * 32)
        self.assertEqual(tx["value"], "0")
        self.assertTrue(tx["data"].startswith("0xf14fcbc8"))

    def test_register_tx_value_is_exact_wei_string(self):
        reg = registration_tuple(
            label="alice",
            owner="0x1111111111111111111111111111111111111111",
            duration=28 * 24 * 3600,
            secret="0x" + "22" * 32,
            resolver="0x0000000000000000000000000000000000000000",
            reverse_record=0,
        )
        tx = tx_register(reg, 12345)
        self.assertEqual(tx["value"], "12345")
        self.assertEqual(tx["chain_id"], 52014)

    def test_name_registered_topic0_matches_controller_abi(self):
        self.assertEqual(
            NAME_REGISTERED_TOPIC0,
            "0xc2240194853531f1ae318dcef227de79c6ad0fd9d1b0e4fe08568415be2e08a5",
        )
        self.assertEqual(
            labelhash_hex("alice"),
            "0x9c0257114eb9399a2985f8e75dad7600c5d89fe3824ffa99ec1c3eb8bf3b0501",
        )

    def test_renew_tx_charges_supplied_base_only(self):
        tx = tx_renew("taken", 365 * 24 * 3600, 2 * 10**18)
        self.assertEqual(tx["value"], str(2 * 10**18))
        self.assertTrue(tx["data"].startswith("0x18026ad1"))
        self.assertEqual(
            NAME_RENEWED_TOPIC0,
            "0x" + keccak(b"NameRenewed(string,bytes32,uint256,uint256,bytes32)").hex(),
        )


if __name__ == "__main__":
    unittest.main()
