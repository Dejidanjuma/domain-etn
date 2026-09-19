# ADR 0002 — Primary .etn registration (prepare-only)

## Status
Accepted.

## Verified mechanism (chain 52014)

Source: `electroneum/ens-contracts` `deployments/electroneum/ETHRegistrarController.json`
plus live `eth_call` on 2026-09-19 and controller source
`contracts/ethregistrar/ETHRegistrarController.sol`.

Live controller: `0x3CFa6D6E7e1216393C2cb9393Bc0f411492E33e9`.
Unused controller `0x5cD5CEFDc5925cA6A9A38D2AA810d5aeD360b21C` is never a target.

Flow (commit/reveal **is used**):

1. `available(label)` — valid (`strlen >= 3`) and `base.available(tokenId)`.
2. `rentPrice(label, duration)` → `(base, premium)` native ETN wei.
3. `makeCommitment(Registration)` = `keccak256(abi.encode(registration))`.
4. `commit(commitment)` — no value. Wait `minCommitmentAge` (60s).
5. `register(Registration)` payable with `msg.value >= base+premium`.
6. Excess ETN is refunded by the contract.
7. NFT is minted on Base Registrar. Wrapper is **not** invoked by register.
8. Optional reverse record bits: `1` = addr.reverse, `2` = default.reverse.

Registration tuple:

`(string label, address owner, uint256 duration, bytes32 secret,
  address resolver, bytes[] data, uint8 reverseRecord, bytes32 referrer)`

`MIN_REGISTRATION_DURATION` = 28 days. `maxCommitmentAge` = 24h.
`GRACE_PERIOD` on the base registrar = 90 days.

## Decision
DOMAIN.etn prepares unsigned `commit` and `register` transactions for the
allowlisted controller only. It does not broadcast. Quotes are HMAC-signed
snapshots; prepare always re-reads `rentPrice`. A prepared or submitted
intent is not success. Success requires a `NameRegistered` log on the
live controller for the intent's label **and** registrant.


v1 refuses client-supplied resolver addresses other than public/none,
refuses resolver `data` (multicall), and refuses mixing marketplace ids
into this flow.

## Unverified / not implemented
Exact gas. Live USD oracle magnitude (always read `rentPrice` instead).
Renewal prepare (ABI is known; product API not shipped). Wrapper path
for already-wrapped names. Marketplace settlement.
