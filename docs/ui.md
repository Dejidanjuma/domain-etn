# DOMAIN.etn product UI

Same-origin SPA served by the FastAPI process (`web/`).

## Journey

Search → availability/profile → quote → connect wallet (Electroneum 52014)
→ prepare commit → wallet signs (`value = 0`) → submitted → wait until
`controller.commitments` is ≥ 60s old → prepare register → wallet pays
native ETN → submitted → confirm NameRegistered → domain profile.

Registered names open the profile, not Register. Renewal is prepare-only
against `renew(string,uint256,bytes32)` and charges `rentPrice.base`.

## Recovery

The browser stores `intent_id` + client secret in `localStorage`.
Refresh re-reads `GET /api/v1/registration/{id}`. If the in-memory intent
is gone, the UI shows a checking/recovery state. A transaction hash is
never treated as success.

## Wallet

EIP-1193 `window.ethereum` only. The app never asks for keys. The backend
never broadcasts. `eth_sendTransaction` is invoked in the browser against
the user's wallet using backend-prepared `to` / `data` / `value`.
