"""HTTP routes. No generic execution endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.domain_etn import PRODUCT, __version__
from src.domain_etn.domains.profile import DomainProfile
from src.domain_etn.eae.client import (
    intelligence_from_eae,
    normalize_history,
    normalize_owner_domains,
    refuse_registration_via_eae,
)
from src.domain_etn.ens.addresses import (
    BASE_REGISTRAR,
    CHAIN_ID,
    CHAIN_DISPLAY_NAME,
    CONTROLLER,
    DEFAULT_REVERSE_REGISTRAR,
    EXPLORER_URL,
    GRACE_PERIOD_SEC,
    MAX_COMMITMENT_AGE_SEC,
    MIN_COMMITMENT_AGE_SEC,
    MIN_REGISTRATION_DURATION_SEC,
    NAME_WRAPPER,
    NATIVE_DECIMALS,
    NATIVE_SYMBOL,
    PUBLIC_RESOLVER,
    PUBLIC_RPC_URL,
    REGISTRY,
    REVERSE_REGISTRAR,
    UNUSED_CONTROLLER,
)
from src.domain_etn.marketplace import observe as marketplace_observe
from src.domain_etn.marketplace.boundary import NOT_IMPLEMENTED as MARKETPLACE
from src.domain_etn.names import parse_address, parse_registration_name
from src.domain_etn.registration.service import RegistrationService
from src.domain_etn.renewal.service import RenewalService

router = APIRouter()


def _svc(request: Request) -> RegistrationService:
    return request.app.state.registration


def _renew(request: Request) -> RenewalService:
    return request.app.state.renewal


def _profile(request: Request) -> DomainProfile:
    return request.app.state.profile


def _eae(request: Request):
    return request.app.state.eae


def _eae_call(eae, method: str, *args, **kwargs):
    if eae is None or not getattr(eae, "enabled", lambda: False)():
        return None
    fn = getattr(eae, method, None)
    if not callable(fn):
        return None
    return fn(*args, **kwargs)


@router.get("/health")
def health():
    return {"status": "ok", "product": PRODUCT, "version": __version__}


@router.get("/ready")
def ready(request: Request):
    rpc = request.app.state.rpc
    chain = rpc.chain_id()
    return {
        "status": "ok" if chain == CHAIN_ID else "wrong_network",
        "chain_id": chain,
        "expected_chain_id": CHAIN_ID,
        "broadcast": False,
        "custody": False,
    }


@router.get("/api/v1/contract")
def contract():
    return {
        "type": "domain_etn_product_contract",
        "product": PRODUCT,
        "version": __version__,
        "role": "commerce_layer",
        "registrar": False,
        "custodial": False,
        "broadcasts": False,
        "private_keys": False,
        "eae": "optional_intelligence_dependency",
        "source_of_truth": "official_electroneum_ens_contracts",
        "flows": {
            "primary_registration": "implemented_prepare_only",
            "renewal": "implemented_prepare_only",
            "secondary_marketplace": "not_implemented",
            "marketplace_indexed_facts": "optional_eae_observation",
        },
        "chain": {
            "chain_id": CHAIN_ID,
            "name": CHAIN_DISPLAY_NAME,
            "native_symbol": NATIVE_SYMBOL,
            "native_decimals": NATIVE_DECIMALS,
            "explorer": EXPLORER_URL,
            "public_rpc": PUBLIC_RPC_URL,
        },
        "chain_id": CHAIN_ID,
        "contracts": {
            "controller": CONTROLLER,
            "unused_controller": UNUSED_CONTROLLER,
            "base_registrar": BASE_REGISTRAR,
            "registry": REGISTRY,
            "public_resolver": PUBLIC_RESOLVER,
            "reverse_registrar": REVERSE_REGISTRAR,
            "default_reverse_registrar": DEFAULT_REVERSE_REGISTRAR,
            "name_wrapper": NAME_WRAPPER,
            "wrapper_used_by_primary_register": False,
            "marketplace": None,
        },
        "registration": {
            "commit_reveal": True,
            "min_commitment_age_sec": MIN_COMMITMENT_AGE_SEC,
            "max_commitment_age_sec": MAX_COMMITMENT_AGE_SEC,
            "min_duration_sec": MIN_REGISTRATION_DURATION_SEC,
            "grace_period_sec": GRACE_PERIOD_SEC,
            "payment": "native_ETN",
            "approvals_required": False,
        },
        "renewal": {
            "method": "renew(string,uint256,bytes32)",
            "selector": "18026ad1",
            "payment": "native_ETN",
            "charged": "rentPrice.base",
            "commit_reveal": False,
            "anyone_may_pay": True,
        },
        "marketplace": MARKETPLACE,
        "ai_interpretation": "not_implemented",
    }


@router.get("/api/v1/domains/availability")
def availability(request: Request, name: str):
    return _svc(request).availability(name)


@router.get("/api/v1/domains/quote")
def quote(request: Request, name: str, duration: int):
    return _svc(request).quote(name, duration)


@router.get("/api/v1/domains/profile")
def domain_profile(request: Request, name: str):
    return _profile(request).get(name)


@router.get("/api/v1/domains/history")
def domain_history(request: Request, name: str):
    parsed = parse_registration_name(name)
    eae = _eae(request)
    raw = _eae_call(eae, "domain_history", parsed["name"])
    events = normalize_history(raw)
    return {
        "type": "domain_history",
        "name": parsed["name"],
        "authority": "eae_indexed_facts" if raw is not None else "not_queried",
        "not_ownership_source": True,
        "sale": "not_inferred",
        "events": events,
        "eae": raw,
        "note": (
            "Indexed domain events from EAE, when configured. "
            "Not a trace. Transfer is not a sale. Absence is not absence on-chain."
        ),
    }


@router.get("/api/v1/domains/discovery")
def domain_discovery(request: Request):
    eae = _eae(request)
    raw = _eae_call(eae, "discovery")
    categories = {}
    if isinstance(raw, dict):
        categories = raw.get("categories") or {
            "recently_seen": raw.get("recent") or raw.get("recently_seen") or [],
            "recently_registered": raw.get("recent_registrations") or raw.get("recently_registered") or [],
        }
    return {
        "type": "domain_discovery",
        "authority": "eae_indexed_facts" if raw is not None else "not_queried",
        "not_availability": True,
        "not_ranking": True,
        "categories": categories,
        "eae": raw,
        "note": (
            "Indexed catalog recency from EAE. Not live availability. "
            "Not a popularity ranking. DOMAIN.etn does not invent names."
        ),
    }


@router.get("/api/v1/domains/search")
def domain_search(request: Request, q: str | None = None, prefix: str | None = None):
    eae = _eae(request)
    raw = _eae_call(eae, "catalog_search", q, prefix) or _eae_call(eae, "domain_search", q or prefix or "")
    results = []
    if isinstance(raw, dict):
        results = raw.get("results") or raw.get("domains") or []
    return {
        "type": "indexed_search",
        "q": q,
        "prefix": prefix,
        "authority": "eae_indexed_facts" if raw is not None else "not_queried",
        "not_availability": True,
        "results": results if isinstance(results, list) else [],
        "eae": raw,
        "note": (
            "Indexed catalog search. This is not availability and not a marketplace. "
            "Use /api/v1/domains/availability for live controller.available."
        ),
    }


@router.post("/api/v1/registration/prepare-commit")
async def prepare_commit(request: Request):
    body = await request.json()
    refuse_registration_via_eae(body)
    return _svc(request).prepare_commit(body)


@router.post("/api/v1/registration/prepare-register")
async def prepare_register(request: Request):
    body = await request.json()
    refuse_registration_via_eae(body)
    return _svc(request).prepare_register(body)


@router.get("/api/v1/registration/{intent_id}")
def get_intent(request: Request, intent_id: str):
    return _svc(request).get(intent_id)


@router.get("/api/v1/registration/{intent_id}/commitment")
def commitment_status(request: Request, intent_id: str):
    return _svc(request).commitment_status(intent_id)


@router.post("/api/v1/registration/{intent_id}/submitted")
async def submitted(request: Request, intent_id: str):
    body = await request.json()
    return _svc(request).mark_submitted(intent_id, body.get("tx_hash") or "", kind=str(body.get("kind") or "commit"))


@router.post("/api/v1/registration/{intent_id}/confirm")
def confirm(request: Request, intent_id: str):
    return _svc(request).confirm(intent_id)


@router.get("/api/v1/renewal/quote")
def renewal_quote(request: Request, name: str, duration: int):
    return _renew(request).quote(name, duration)


@router.post("/api/v1/renewal/prepare")
async def renewal_prepare(request: Request):
    body = await request.json()
    refuse_registration_via_eae(body)
    return _renew(request).prepare(body)


@router.get("/api/v1/renewal/{intent_id}")
def get_renewal(request: Request, intent_id: str):
    return _renew(request).get(intent_id)


@router.post("/api/v1/renewal/{intent_id}/submitted")
async def renewal_submitted(request: Request, intent_id: str):
    body = await request.json()
    return _renew(request).mark_submitted(intent_id, body.get("tx_hash") or "")


@router.post("/api/v1/renewal/{intent_id}/confirm")
def renewal_confirm(request: Request, intent_id: str):
    return _renew(request).confirm(intent_id)


@router.get("/api/v1/owners/{address}")
def owner_intelligence(request: Request, address: str):
    parsed = parse_address(address)
    eae = _eae(request)
    facts = _eae_call(eae, "owner_intelligence", parsed) or _eae_call(eae, "investigate", parsed)
    domains = []
    owner_fn = _eae_call(eae, "owner_domains", parsed)
    if owner_fn is not None:
        domains = normalize_owner_domains(parsed, owner_fn)
    elif facts is not None:
        domains = normalize_owner_domains(parsed, facts)
    return {
        "type": "owner_intelligence",
        "address": parsed,
        "authority": "eae_indexed_facts" if facts is not None or owner_fn is not None else "not_queried",
        "not_ownership_source": True,
        "not_identity": True,
        "domains": domains,
        "intelligence": intelligence_from_eae(facts),
        "eae": facts,
        "note": (
            "Indexed associations for this address. Not a person label. "
            "Not a marketplace counterparty. Live ownership is on the base registrar."
        ),
    }


@router.get("/api/v1/owners/{address}/domains")
def owner_domains(request: Request, address: str):
    parsed = parse_address(address)
    eae = _eae(request)
    facts = None
    if eae.enabled():
        owner_fn = getattr(eae, "owner_domains", None)
        if callable(owner_fn):
            facts = owner_fn(parsed)
        if facts is None and hasattr(eae, "investigate"):
            facts = eae.investigate(parsed)
    domains = normalize_owner_domains(parsed, facts)
    return {
        "type": "user_domains",
        "address": parsed,
        "authority": "eae_indexed_facts" if facts is not None else "not_queried",
        "not_ownership_source": True,
        "domains": domains,
        "eae": facts,
        "note": (
            "DOMAIN.etn does not keep a local ownership table. "
            "Indexed facts come from EAE after the chain event exists. "
            "Search a name for a live on-chain profile."
        ),
    }


@router.get("/api/v1/marketplace")
def marketplace(request: Request):
    return marketplace_observe.descriptor(eae=_eae(request))


@router.get("/api/v1/marketplace/listings")
def marketplace_listings(request: Request, status: str | None = None):
    return marketplace_observe.listings(eae=_eae(request), status=status)


@router.get("/api/v1/marketplace/activity")
def marketplace_activity(request: Request):
    return marketplace_observe.activity(eae=_eae(request))
