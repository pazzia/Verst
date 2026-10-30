"""The FastAPI application (ADR-0020). `uvicorn verst_api.main:app` (container) or `create_app(settings)`."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from verst_api import API_VERSION, errors, store
from verst_api.db import make_pool, migrate_up
from verst_api.deps import Context
from verst_api.engine import Engine
from verst_api.logs import configure
from verst_api.middleware import RequestContext
from verst_api.routes import router
from verst_api.settings import Settings

log = logging.getLogger("verst_api.main")

CLEANUP_EVERY_S = 3600.0


async def _cleanup_loop(ctx: Context) -> None:
    while True:
        try:
            done = await store.cleanup(ctx.pool, ctx.settings.feedback_text_days)
            if any(done.values()):
                log.info("cleanup", extra=done)
        except Exception as e:  # keep the loop alive; the next run retries
            log.warning("cleanup failed: %s", type(e).__name__)
        await asyncio.sleep(CLEANUP_EVERY_S)


def create_app(
    settings: Settings | None = None, engine: Engine | None = None, log_setup: bool = True
) -> FastAPI:
    settings = settings or Settings()
    if log_setup:
        configure(settings.log_level)
    engine = engine or Engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.migrate_on_start:
            applied = await migrate_up(settings.database_url)
            if applied:
                log.info("migrations applied", extra={"versions": applied})
        pool = make_pool(settings.database_url, settings.db_pool_max)
        await pool.open()
        await asyncio.get_running_loop().run_in_executor(None, engine.load)
        ctx = Context(settings, pool, engine)
        app.state.ctx = ctx
        cleaner = asyncio.create_task(_cleanup_loop(ctx))
        log.info("verst-api started", extra={"env": settings.env, "routing": engine.routing_mode})
        try:
            yield
        finally:
            cleaner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleaner
            await pool.close()

    app = FastAPI(
        title="Verst API (beta)",
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.env != "prod" else None,
    )
    errors.install(app)
    app.include_router(router)
    app.add_middleware(RequestContext, max_body_bytes=settings.max_body_bytes)
    return app


def app() -> FastAPI:
    """Factory for `uvicorn --factory verst_api.main:app`."""
    return create_app()
