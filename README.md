# DOMAIN.etn

Product/commerce layer for Electroneum `.etn` names.

Repository: [github.com/Dejidanjuma/domain-etn](https://github.com/Dejidanjuma/domain-etn)

- **Not** the Electroneum Analytics Engine (EAE)
- **Not** a registrar
- **Not** a custodian

Official ENS contracts on Electroneum (chain 52014) are the source of truth
for registration and renewal. This process prepares unsigned transactions
for the user's wallet and serves the product UI. See
[docs/architecture.md](docs/architecture.md), [docs/ui.md](docs/ui.md),
and [docs/verified-ens.md](docs/verified-ens.md).

## Run

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
node --test tests/js/test_flow.mjs
PYTHONPATH=. python3 -m src.domain_etn
```

Defaults: `127.0.0.1:8081`. Copy `.env.example`. Set `DOMAIN_ETN_QUOTE_SECRET`
in any durable process. Never put a wallet key in env.

Open `/` for search. Registration: availability → quote → commit → 60s wait
→ pay native ETN → backend confirms `NameRegistered`. Renewal is prepare-only
and charges `rentPrice.base`.

## Boundary

Primary registration: user → official `ETHRegistrarController`.
Renewal: user → official `ETHRegistrarController.renew`.
Secondary marketplace: not implemented; different flow, do not mix.
