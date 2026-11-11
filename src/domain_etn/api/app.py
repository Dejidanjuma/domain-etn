"""FastAPI application. Read-only chain access. No broadcasting."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.domain_etn import PRODUCT, __version__
from src.domain_etn.api.routes import router
from src.domain_etn.config import settings
from src.domain_etn.domains.profile import DomainProfile
from src.domain_etn.eae.client import EaeClient
from src.domain_etn.errors import ProductError
from src.domain_etn.registration.service import RegistrationService
from src.domain_etn.renewal.service import RenewalService
from src.domain_etn.rpc import HttpRpc

WEB_DIR = Path(__file__).resolve().parents[3] / "web"

DESCRIPTION = """
DOMAIN.etn product/commerce API.

Official Electroneum ENS contracts are the registration source of truth.
This service prepares unsigned transactions for the user's wallet.
It does not custody funds, hold private keys, or broadcast transactions.
EAE is an optional intelligence dependency, not a registrar.
Primary registration and secondary marketplace are different flows.
Marketplace settlement is not deployed on Electroneum.
"""


def create_app(
    *,
    rpc=None,
    service: RegistrationService | None = None,
    renewal: RenewalService | None = None,
    eae: EaeClient | None = None,
) -> FastAPI:
    app = FastAPI(
        title="DOMAIN.etn API",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.rpc = rpc or HttpRpc(settings.rpc_url)
    app.state.registration = service or RegistrationService(app.state.rpc)
    app.state.renewal = renewal or RenewalService(app.state.rpc)
    app.state.eae = eae if eae is not None else EaeClient(settings.eae_url)
    app.state.profile = DomainProfile(app.state.rpc, eae=app.state.eae)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.pop("X-Powered-By", None)
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

    if WEB_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

        @app.get("/")
        def index():
            return FileResponse(WEB_DIR / "index.html")

        @app.get("/me")
        def my_names():
            return FileResponse(WEB_DIR / "index.html")

        @app.get("/discover")
        def discover_page():
            return FileResponse(WEB_DIR / "index.html")

        @app.get("/market")
        def market_page():
            return FileResponse(WEB_DIR / "index.html")

        @app.get("/d/{name:path}")
        def domain_page(name: str):
            return FileResponse(WEB_DIR / "index.html")

        @app.get("/w/{address}")
        def wallet_page(address: str):
            return FileResponse(WEB_DIR / "index.html")

    return app
