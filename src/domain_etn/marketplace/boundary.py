"""Keep secondary commerce out of the primary registration flow."""

from __future__ import annotations

NOT_IMPLEMENTED = {
    "type": "marketplace",
    "flow": "secondary_marketplace",
    "status": "not_implemented",
    "capabilities": {
        "listings": "not_implemented",
        "buy_now": "not_implemented",
        "offers": "not_implemented",
        "auctions": "not_implemented",
    },
    "note": (
        "Secondary marketplace purchase is a different transaction flow from "
        "primary registration. Buyer → marketplace mechanism → seller/domain "
        "transfer. Official ENS controller registration is not a sale."
    ),
}
