# DOMAIN.etn

Product/commerce backend for Electroneum `.etn` names.

Repository: [github.com/Dejidanjuma/domain-etn](https://github.com/Dejidanjuma/domain-etn)

- **Not** the Electroneum Analytics Engine (EAE)
- **Not** a registrar
- **Not** a custodian

Official ENS contracts on Electroneum (chain 52014) are the source of truth
for registration. This API prepares unsigned commit/reveal transactions for
the user's wallet. See [docs/architecture.md](docs/architecture.md) and
[docs/verified-ens.md](docs/verified-ens.md).

## Run

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 -m src.domain_etn
```

Defaults: `127.0.0.1:8081`. Copy `.env.example`. Set `DOMAIN_ETN_QUOTE_SECRET`
in any durable process (quotes are HMAC-signed; a random secret is generated
only as a last resort). Never put a wallet key in env.

## Boundary

Primary registration: user → official `ETHRegistrarController`.
Secondary marketplace: not implemented; different flow, do not mix.
