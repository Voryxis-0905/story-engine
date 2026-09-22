"""Application assembly. Domain logic belongs in story/, world/ and services."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.security import allowed_origins_for_cors, local_origin_guard
from app.storage import WorldFileUnreadable

logger = logging.getLogger(__name__)


async def _unreadable_world_file_handler(request: Request, exc: WorldFileUnreadable) -> JSONResponse:
    """Answer corrupt world state with 409 rather than a bare 500.

    The world cannot be served, but the client can act on it: restore a save or
    re-import the world. A stack trace would say none of that.
    """
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                f"World file '{exc.filename}' exists but cannot be read ({exc.reason}). "
                "The world state is corrupt; restore it from a save or re-import the world."
            )
        },
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    from app.storage import WORLDS_DIR
    from app.world.schema import migrate_all_worlds

    result = migrate_all_worlds(WORLDS_DIR, logger)
    if result["migrated"]:
        logger.info("Migrated worlds to current schema: %s", result["migrated"])
    for failure in result["errors"]:
        logger.error("World schema migration error for %s: %s", failure["world"], failure["error"])
    yield


def create_app() -> FastAPI:
    from app.routes import (
        world_routes, builder_routes, chapter_routes, creator_routes, studio_routes,
        discovery_routes, demo_routes, runtime_routes,
    )

    application = FastAPI(lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins_for_cors(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )
    application.middleware("http")(local_origin_guard)
    application.add_exception_handler(WorldFileUnreadable, _unreadable_world_file_handler)
    for router in (world_routes.router, builder_routes.router, chapter_routes.router,
                   creator_routes.router, studio_routes.router, discovery_routes.router,
                   demo_routes.router, runtime_routes.router):
        application.include_router(router)

    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.is_dir():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return application
