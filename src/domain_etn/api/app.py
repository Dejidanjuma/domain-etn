"""FastAPI application. Read-only chain access. No broadcasting."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain_etn import PRODUCT, __version__
from src.domain_etn.api.routes import router
from src.domain_etn.config import settings
from src.domain_etn.eae.client import EaeClient
from src.domain_etn.errors import ProductError
from src.domain_etn.registration.service import RegistrationService
from src.domain_etn.rpc import HttpRpc


DESCRIPTION = """
DOMAIN.etn product/commerce API.

Official Electroneum ENS contracts are the registration source of truth.
This service prepares unsigned transactions for the user's wallet.
It does not custody funds, hold private keys, or broadcast transactions.
EAE is an optional intelligence dependency, not a registrar.
Primary registration and secondary marketplace are different flows.
"""


def create_app(*, rpc=None, service: RegistrationService | None = None, eae: EaeClient | None = None) -> FastAPI:
    app = FastAPI(
        title="DOMAIN.etn API",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.rpc = rpc or HttpRpc(settings.rpc_url)
    app.state.registration = service or RegistrationService(app.state.rpc)
    app.state.eae = eae if eae is not None else EaeClient(settings.eae_url)

    @app.middleware("http")
    async def _no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ProductError)
    async def _product_error(_, exc: ProductError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
                "product": PRODUCT,
            },
        )

    app.include_router(router)
    return app
