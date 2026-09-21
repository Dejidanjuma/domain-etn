"""Keep secondary commerce out of the primary registration flow.

Settlement is not implemented: the EAE DomainMarketplace bytecode is
local/test only, PRODUCTION_DEPLOY_ENABLED is false, pause owner is
undecided, and no production marketplace address exists on chain 52014.

Offers and auctions are deferred in that contract. Do not invent them.
Indexed EAE marketplace facts, when present, are observational only.
"""

from __future__ import annotations

from src.domain_etn.ens.addresses import BASE_REGISTRAR, CHAIN_ID, NAME_WRAPPER

NOT_IMPLEMENTED = {
    "type": "marketplace",
    "flow": "secondary_marketplace",
    "status": "not_implemented",
    "settlement": "not_implemented",
    "deployed": False,
    "production_deploy_enabled": False,
    "marketplace_contract_address": None,
    "pause_owner": None,
    "pause_owner_status": "undecided",
    "chain_id": CHAIN_ID,
    "registrar": BASE_REGISTRAR,
    "wrapper": NAME_WRAPPER,
    "mvp": {
        "standard": "erc721_unwrapped_base_registrar",
        "payment": "native_etn",
        "listing": "on_chain",
        "custody": "non_custodial_approval",
        "rejects_wrapped": True,
        "source": "eae DomainMarketplace.sol local/test bytecode",
    },
    "capabilities": {
        "listings": "not_implemented",
        "buy_now": "not_implemented",
        "offers": "not_implemented",
        "auctions": "not_implemented",
        "prepare_listing": "not_implemented",
        "prepare_purchase": "not_implemented",
        "prepare_cancel": "not_implemented",
    },
    "deferred": ["offers", "auctions", "fees", "royalties", "wrapped_names", "subdomains"],
    "blockers": [
        "DomainMarketplace is local/test bytecode; not deployed on Electroneum",
        "PRODUCTION_DEPLOY_ENABLED remains false in EAE",
        "Production pause owner (governance) is undecided",
        "No production marketplace address is configured",
    ],
    "indexed_facts": "optional_eae_observation",
    "authorization": "not_authorization",
    "note": (
        "Secondary marketplace purchase is a different transaction flow from "
        "primary registration. Buyer → marketplace mechanism → seller/domain "
        "transfer. Official ENS controller registration is not a sale. "
        "DOMAIN.etn will not prepare listing or purchase transactions until a "
        "human deployment gate enables a live marketplace contract. "
        "Offers and auctions are not implemented by the current contract. "
        "Indexed EAE listing rows are observational and are not live sellability."
    ),
}
