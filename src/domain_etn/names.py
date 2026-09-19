"""2LD .etn label rules for primary registration.

Contract `valid(label)` is `strlen >= 3`. This layer additionally refuses
non-ASCII, whitespace, and subdomains. Those refusals are product policy,
not extra on-chain truth.
"""

from __future__ import annotations

import re

from src.domain_etn.errors import ProductError

TLD = "etn"
_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MIN_LABEL_LEN = 3  # ETHRegistrarController.valid
MAX_LABEL_LEN = 63


def parse_registration_name(raw: str) -> dict:
    if raw is None or not isinstance(raw, str) or not raw.strip():
        raise ProductError("invalid_domain", "Name is required.")
    text = raw.strip()
    if text != raw.strip() or any(ch.isspace() for ch in text):
        raise ProductError("invalid_domain", "Name must not contain whitespace.", {"name": raw})
    if any(ord(ch) > 127 for ch in text):
        raise ProductError("invalid_domain", "Non-ASCII labels are not supported.", {"name": raw})
    lowered = text.lower()
    if lowered.endswith("." + TLD):
        labels = lowered.split(".")
        if len(labels) != 2:
            raise ProductError(
                "invalid_domain",
                "Primary registration is 2LD .etn only. Subdomains are not this flow.",
                {"name": raw},
            )
        label, tld = labels
    elif "." in lowered:
        raise ProductError("invalid_domain", "Only .etn names can be registered here.", {"name": raw})
    else:
        label = lowered
    if not _LABEL_RE.fullmatch(label):
        raise ProductError("invalid_domain", "Label must be lowercase ASCII letters, digits, or inner hyphens.", {"name": raw})
    if len(label) < MIN_LABEL_LEN:
        raise ProductError(
            "invalid_domain",
            f"Label must be at least {MIN_LABEL_LEN} characters (controller valid()).",
            {"name": raw, "label": label},
        )
    if len(label) > MAX_LABEL_LEN:
        raise ProductError("invalid_domain", "Label exceeds 63 characters.", {"name": raw})
    return {
        "label": label,
        "name": f"{label}.{TLD}",
        "tld": TLD,
        "normalized": f"{label}.{TLD}",
    }
