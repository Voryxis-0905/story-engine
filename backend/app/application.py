"""Application assembly. Domain logic belongs in story/, world/ and services."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    from app.routes import world_routes, builder_routes, chapter_routes, creator_routes, studio_routes

    application = FastAPI()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )
    for router in (world_routes.router, builder_routes.router, chapter_routes.router,
                   creator_routes.router, studio_routes.router):
        application.include_router(router)

    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.is_dir():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return application
