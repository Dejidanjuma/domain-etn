# DOMAIN.etn architecture

DOMAIN.etn is the **product and commerce** backend for `.etn` names.

EAE is an **external intelligence** dependency. Official Electroneum ENS
contracts are the **registration source of truth**.

This service:

- answers availability from `ETHRegistrarController.available`
- quotes native ETN rent from `rentPrice`
- prepares unsigned `commit` then `register` calldata
- tracks intent state (`prepared` → `submitted` → `confirmed`/`failed`)
- reads live owner/expiry from the base registrar for domain profiles
- classifies lifecycle from those live reads (`available` / `active` /
  `expiring_soon` / `grace`)
- prepares unsigned `renew` calldata (base rent only)
- serves the product UI (search, profile, my names, discover, marketplace status)
- may display EAE facts after the chain event exists

This service does **not**:

- hold private keys
- custody ETN
- broadcast transactions
- treat prepare/submit as success
- trust client-supplied prices or contract addresses
- execute arbitrary calldata
- implement secondary marketplace settlement
- register names through EAE
- invent marketplace inventory, offers, or auctions

## API (v1)

- `GET /health`
- `GET /ready`
- `GET /api/v1/contract`
- `GET /api/v1/domains/availability?name=`
- `GET /api/v1/domains/quote?name=&duration=`
- `POST /api/v1/registration/prepare-commit`
- `POST /api/v1/registration/prepare-register`
- `GET /api/v1/registration/{intent_id}`
- `POST /api/v1/registration/{intent_id}/submitted`
- `POST /api/v1/registration/{intent_id}/confirm` (read receipt only)
- `GET /api/v1/domains/profile?name=`
- `GET /api/v1/domains/history?name=` (EAE indexed events, optional)
- `GET /api/v1/domains/discovery` (EAE indexed catalog, optional)
- `GET /api/v1/domains/search?q=&prefix=` (indexed catalog, not availability)
- `GET /api/v1/registration/{intent_id}/commitment`
- `GET /api/v1/renewal/quote`
- `POST /api/v1/renewal/prepare`
- `GET /api/v1/renewal/{intent_id}`
- `POST /api/v1/renewal/{intent_id}/submitted`
- `POST /api/v1/renewal/{intent_id}/confirm`
- `GET /api/v1/owners/{address}` (EAE intelligence, not identity)
- `GET /api/v1/owners/{address}/domains` (EAE facts, not local authority)
- `GET /api/v1/marketplace` (`not_implemented` settlement)
- `GET /api/v1/marketplace/listings` (optional EAE observation)
- `GET /api/v1/marketplace/activity` (optional EAE observation)

There is no `prepare-buy` / `prepare-listing` endpoint.

Frontend contract:

SEARCH → availability → quote → prepare commit → wallet signs → wait 60s →
prepare register → wallet signs and pays ETN → confirm NameRegistered →
EAE indexes the fact.

A prepared or submitted intent is **not** success. Confirm reads the receipt
and requires a `NameRegistered` log on the live controller whose indexed
labelhash and owner match the intent. A log for a different name, or a
different owner of the same name, is not confirmation.

## Layers

- On-chain facts: owner, expiry, NameRegistered, NameRenewed, receipt
- Transaction intent: name, duration, registrant, quoted price, calldata
- Transaction state: prepared / wallet_signing / submitted / confirmed / failed / stale / expired
- Indexed facts: EAE catalog / events (optional)
- Presentation: lifecycle labels, product copy

## Marketplace

See [adr/0004-marketplace.md](adr/0004-marketplace.md). The EAE
DomainMarketplace bytecode is local/test only. DOMAIN.etn does not deploy it
and does not settle against it.
