# ADR 0005 — EAE intelligence in DOMAIN.etn

## Status
Accepted.

## Context
EAE already exposes product APIs for domain profiles, history, discovery,
owner associations, and observational marketplace facts. DOMAIN.etn must
not become a second indexer.

## Decision

DOMAIN.etn consumes EAE over HTTP when `DOMAIN_ETN_EAE_URL` is set.

Layers stay distinct:

| Layer | Source | Authority |
| --- | --- | --- |
| Fact | Live ENS `eth_call` / receipt logs | Yes, for registration, renewal, owner, expiry |
| Indexed fact | EAE catalog / events | Observational only |
| Derived / signal | EAE deterministic measurements | Not ownership, not valuation |
| Presentation | DOMAIN.etn UI labels | Not on-chain truth |

`expiring_soon` is a 30-day **presentation** threshold, not an ENS constant.
Grace is `nameExpires <= now` while `available()` is still false.

Absence from EAE is not absence on-chain. Transfer is not a sale. AI
interpretation is not implemented.

## Consequences
My names, Discover, History, and related-address views are empty and honest
when EAE is unset. Search for availability always hits the official
controller, never the catalog.
