from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from config import settings
from app.logger import log
from app.routers.topology import router as topology_router
from app.routers.plan import router as plan_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Startup / shutdown lifecycle."""
    log.info("SDN Control Platform starting up")
    log.debug(
        "ODL northbound: {}  |  southbound: {}:{}",
        settings.odl_north_base_url,
        settings.odl_south_ip,
        settings.odl_south_port,
    )
    yield
    log.info("Shutting down")


app = FastAPI(title="SDN Control Platform", version="0.1.0", lifespan=lifespan)
app.include_router(topology_router)
app.include_router(plan_router)


@app.get("/health")
def health() -> dict[str, str]:
    log.debug("Health check called")
    return {"status": "ok"}


def main() -> None:
    host = settings.base_url or "0.0.0.0"
    port = settings.base_port
    log.info("Listening on {}:{}", host, port)
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=settings.log_level.lower() if settings.log_level else "info",
        reload=True,
    )


if __name__ == "__main__":
    main()
