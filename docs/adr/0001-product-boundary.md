# ADR 0001 — DOMAIN.etn product boundary

## Status
Accepted.

## Context
EAE already indexes Electroneum `.etn` facts and exposes investigation APIs.
DOMAIN.etn is the product people will use to search, register, and later
buy/sell names. Mixing those jobs in EAE would make the fact engine a
commerce system.

## Decision

```
Official Electroneum ENS contracts
        ↓
   ┌────┴─────┐
   ↓          ↓
  EAE      DOMAIN.etn
   ↓          ↓
facts &    product /
intelligence commerce UX
```

1. DOMAIN.etn is the product/commerce layer.
2. EAE is the intelligence/data layer. Optional HTTP consumer only.
3. Official Electroneum ENS contracts are the registration source of truth.
4. DOMAIN.etn is not a registrar and does not assign ownership.
5. DOMAIN.etn does not custody user funds or private keys.
6. Wallet signing stays with the user's wallet.
7. Primary registration and secondary marketplace are different flows.
8. After on-chain success, EAE may index the resulting fact. DOMAIN.etn
   may then display it. DOMAIN.etn never becomes a second ownership table.
9. Future listings, Buy Now, offers, auctions, CLUB mechanisms, renewals,
   and primary-name UX must preserve this split.

## Consequences
Registration APIs live in this repository. EAE is not modified to execute
or prepare registrations.
