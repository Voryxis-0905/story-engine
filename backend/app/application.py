"""Application assembly. Domain logic belongs in story/, world/ and services."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.security import allowed_origins_for_cors, local_origin_guard

logger = logging.getLogger(__name__)


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
    from app.routes import world_routes, builder_routes, chapter_routes, creator_routes, studio_routes

    application = FastAPI(lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins_for_cors(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )
    application.middleware("http")(local_origin_guard)
    for router in (world_routes.router, builder_routes.router, chapter_routes.router,
                   creator_routes.router, studio_routes.router):
        application.include_router(router)

    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.is_dir():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return application
