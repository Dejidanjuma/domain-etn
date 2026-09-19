"""python -m src.domain_etn"""

from __future__ import annotations

import uvicorn

from src.domain_etn.api.app import create_app
from src.domain_etn.config import settings


def main() -> None:
    uvicorn.run(create_app(), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
