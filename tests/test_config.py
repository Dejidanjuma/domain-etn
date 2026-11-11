"""Production quote signing must use a stable operator-provided secret."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.domain_etn.config import Settings


class QuoteSecretConfigurationTests(unittest.TestCase):
    def test_default_loopback_development_keeps_ephemeral_secret_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(len(Settings().quote_secret), 32)

    def test_explicit_local_container_mode_keeps_development_fallback(self):
        with patch.dict(
            os.environ,
            {"DOMAIN_ETN_ENV": "development", "DOMAIN_ETN_HOST": "0.0.0.0"},
            clear=True,
        ):
            self.assertEqual(len(Settings().quote_secret), 32)

    def test_production_requires_explicit_quote_secret(self):
        with patch.dict(
            os.environ,
            {"DOMAIN_ETN_ENV": "production", "DOMAIN_ETN_HOST": "127.0.0.1"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "DOMAIN_ETN_QUOTE_SECRET"):
                Settings()

    def test_explicit_host_binding_requires_secret_even_behind_loopback_proxy(self):
        with patch.dict(os.environ, {"DOMAIN_ETN_HOST": "127.0.0.1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DOMAIN_ETN_QUOTE_SECRET"):
                Settings()

    def test_hosted_runtime_requires_explicit_quote_secret(self):
        with patch.dict(os.environ, {"RENDER": "true"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DOMAIN_ETN_QUOTE_SECRET"):
                Settings()

    def test_explicit_secret_is_used_in_production(self):
        with patch.dict(
            os.environ,
            {
                "DOMAIN_ETN_ENV": "production",
                "DOMAIN_ETN_HOST": "127.0.0.1",
                "DOMAIN_ETN_QUOTE_SECRET": "a-stable-test-secret-for-domain-etn",
            },
            clear=True,
        ):
            self.assertEqual(Settings().quote_secret, b"a-stable-test-secret-for-domain-etn")


if __name__ == "__main__":
    unittest.main()
