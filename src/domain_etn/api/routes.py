"""HTTP routes. No generic execution endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.domain_etn import PRODUCT, __version__
from src.domain_etn.eae.client import refuse_registration_via_eae
from src.domain_etn.ens.addresses import (
    BASE_REGISTRAR,
    CHAIN_ID,
    CONTROLLER,
    DEFAULT_REVERSE_REGISTRAR,
    GRACE_PERIOD_SEC,
    MAX_COMMITMENT_AGE_SEC,
    MIN_COMMITMENT_AGE_SEC,
    MIN_REGISTRATION_DURATION_SEC,
    NAME_WRAPPER,
    PUBLIC_RESOLVER,
    REGISTRY,
    REVERSE_REGISTRAR,
    UNUSED_CONTROLLER,
)
from src.domain_etn.marketplace.boundary import NOT_IMPLEMENTED as MARKETPLACE
from src.domain_etn.registration.service import RegistrationService

router = APIRouter()


def _svc(request: Request) -> RegistrationService:
    return request.app.state.registration


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
            "secondary_marketplace": "not_implemented",
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
        "ai_interpretation": "not_implemented",
    }


@router.get("/api/v1/domains/availability")
def availability(request: Request, name: str):
    return _svc(request).availability(name)


@router.get("/api/v1/domains/quote")
def quote(request: Request, name: str, duration: int):
    return _svc(request).quote(name, duration)


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


@router.post("/api/v1/registration/{intent_id}/submitted")
async def submitted(request: Request, intent_id: str):
    body = await request.json()
    return _svc(request).mark_submitted(intent_id, body.get("tx_hash") or "", kind=str(body.get("kind") or "commit"))


@router.post("/api/v1/registration/{intent_id}/confirm")
def confirm(request: Request, intent_id: str):
    return _svc(request).confirm(intent_id)


@router.get("/api/v1/owners/{address}/domains")
def owner_domains(request: Request, address: str):
    eae = request.app.state.eae
    facts = eae.investigate(address) if eae.enabled() else None
    return {
        "type": "user_domains",
        "address": address,
        "authority": "eae_indexed_facts" if facts is not None else "not_queried",
        "not_ownership_source": True,
        "eae": facts,
        "note": (
            "DOMAIN.etn does not keep a local ownership table. "
            "Indexed facts come from EAE after the chain event exists."
        ),
    }


@router.get("/api/v1/marketplace")
def marketplace():
    return MARKETPLACE
