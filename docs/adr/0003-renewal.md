# ADR 0003 — Prepare-only .etn renewal

## Status
Accepted.

## Verified mechanism (chain 52014)

Source: `ETHRegistrarController.sol` `renew(string label, uint256 duration, bytes32 referrer)`
payable on live controller `0x3CFa6D6E7e1216393C2cb9393Bc0f411492E33e9`.

Selector `18026ad1`.

Payment is `rentPrice.base` in native ETN. Premium is not collected.
Excess is refunded. Commit/reveal is **not** used. Anyone may pay to extend
a name that is still registered or in the 90-day grace period
(`controller.available` is false). After grace, the name is available for
primary registration instead.

Success event:

`NameRenewed(string label, bytes32 indexed labelhash, uint256 cost, uint256 expires, bytes32 referrer)`

DOMAIN.etn confirms only when that log is on the live controller and
topic1 matches the intent labelhash.

## Decision
Renewal is a prepare-only product API, same security model as registration:
allowlisted controller, live `rentPrice`, HMAC quote, wallet signs, backend
never broadcasts, success is the chain event.

## Not this ADR
Marketplace settlement. Subdomains. Wrapping.
