# Verified Electroneum ENS registration

Network: Electroneum mainnet, chain id **52014**.

Deployment records: [electroneum/ens-contracts `deployments/electroneum`](https://github.com/electroneum/ens-contracts/tree/staging/deployments/electroneum).

## Addresses (checksummed)

| Role | Address | Notes |
|---|---|---|
| ETHRegistrarController (live) | `0x3CFa6D6E7e1216393C2cb9393Bc0f411492E33e9` | Only registration target |
| Unused controller | `0x5cD5CEFDc5925cA6A9A38D2AA810d5aeD360b21C` | Refused |
| BaseRegistrarImplementation | `0x5207496C1248BbD2AeeDd57Bde44dd9d4E9F1b59` | ERC-721 2LD |
| ENSRegistry | `0x6F311F2212593165988Dff84977e24C1005dBb85` | |
| PublicResolver | `0xDb4A3Abb6703232e20a118a104e7f4EbB3e2738D` | |
| ReverseRegistrar | `0xFBB14eDBD8D3f6E7BB240bFA388f6582df0d8E7A` | |
| DefaultReverseRegistrar | `0x3bED61fE4d7d3Bc79E46912Ee7ACce2c231aA0a6` | Constructor arg |
| NameWrapper | `0xd8F4B1A91469B05d9E0b15Cac4917Ee47b2A6f64` | Optional; **not** used by `register` |
| ExponentialPremiumPriceOracle | `0x1F5A4178f3B1088e76eB82dC7A3Cb861E3864dE5` | `prices()` |
| OwnedUsdOracle | `0xDB70711Ce7682DB0c0098D8eE3c3856a749D7C37` | Manual ETN/USD |

## Live eth_call (2026-09-19, Ankr public RPC)

- `minCommitmentAge` = 60
- `maxCommitmentAge` = 86400
- `MIN_REGISTRATION_DURATION` = 2419200 (28 days)
- `GRACE_PERIOD` (base registrar) = 7776000 (90 days)
- `available("wallet"|"pay"|"resolver")` = false (reserved)
- `available("thisnamedoesnotexistzzzzz")` = true
- `valid("ab")` = false; `valid("abc")` = true
- `makeCommitment` local keccak matched on-chain

## ETN-specific differences vs Ethereum ENS

- TLD is `.etn` (`ETN_NODE` in the controller).
- No `NameWrapper` constructor argument. `register` calls `base.register`, not `registerAndWrapETH2LD`.
- `register` / `makeCommitment` take a `Registration` tuple with `uint8 reverseRecord` and `bytes32 referrer` (newer ENS controller), not the older 4-argument `register(string,address,uint256,bytes32)`.
- Pricing uses `OwnedUsdOracle` (no Chainlink ETN/USD). README states USD tiers $5 / $160 / $640 per year; runtime always reads `rentPrice`.
- Native payment is ETN, not ETH.
- No legacy registrar controller on this network.

## Unverified

- Exact gas for commit/register (wallet estimates).
- Current `OwnedUsdOracle.latestAnswer()` at any future time.
- Whether operators later enable wrapping as a separate user action.

## Success event (verified)

`NameRegistered(string label, bytes32 indexed labelhash, address indexed owner, uint256 baseCost, uint256 premium, uint256 expires, bytes32 referrer)`

- topic0 = keccak of the signature above (`0xc2240194853531f1ae318dcef227de79c6ad0fd9d1b0e4fe08568415be2e08a5`)
- topic1 = `keccak256(bytes(label))`
- topic2 = owner (left-padded address)
- referrer is **not** indexed
- DOMAIN.etn treats an intent as confirmed only when this log is on the live controller **and** topic1/topic2 match the intent's label and registrant

## Reverse-record nuance

If `reverseRecord` bits are set, the controller calls reverse registrars with `msg.sender`, not `registration.owner`. Paying for someone else's name does not set *their* reverse record. Product default is bit 1 (addr.reverse) when `set_reverse_record` is omitted.

