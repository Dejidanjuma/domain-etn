# ADR 0004 — Marketplace settlement is not live

## Status
Accepted.

## Context
EAE already contains `DomainMarketplace.sol` (fixed-price, native ETN,
unwrapped ERC-721 2LDs, non-custodial approval). Offers and auctions are
declared in the interface as deferred events and are **not implemented**.

EAE's M5 deployment gate reports:

- `PRODUCTION_DEPLOY_ENABLED = false`
- `deployed = false`
- production pause owner (governance) = `undecided`
- no production marketplace address is configured

DOMAIN.etn must not invent a competing marketplace, must not deploy the
contract, and must not prepare listing or purchase transactions against an
address that does not exist on Electroneum.

## Decision

1. Secondary marketplace remains a **different flow** from primary
   registration and renewal.
2. Settlement status is `not_implemented` until a human deployment gate
   enables a live marketplace contract on chain 52014.
3. DOMAIN.etn may **observe** EAE indexed marketplace facts when EAE is
   configured. Those rows are not live sellability and are not authorization.
4. DOMAIN.etn will not expose `prepare-listing`, `prepare-buy`, or
   `prepare-cancel` endpoints while `deployed` is false.
5. Offers and auctions stay documented extension points. They are not
   implemented by the current contract and must not be faked in the product.
6. EAE is not modified by this product milestone.

## Consequences
The `/market` UI and `/api/v1/marketplace*` routes tell the truth: nothing
is for sale here yet. Indexed listings, if any, cannot be purchased through
DOMAIN.etn.
