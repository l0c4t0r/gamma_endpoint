from fastapi import FastAPI
from fastapi import Request
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from fastapi.middleware.cors import CORSMiddleware
from endpoint.config.cache import CHARTS_CACHE_TIMEOUT

from sources.mongo.endpoint.routers import build_routers


def create_app(
    title: str,
    version="0.0.1",
):
    app = FastAPI(
        title=title,
        swagger_ui_parameters={"docExpansion": "none"},
        version=version,
    )

    # Add subgraph routes to app
    for route_builder in build_routers():
        app.include_router(route_builder.router(), tags=route_builder.tags)

    # Allow CORS
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.on_event("startup")
    async def startup():
        FastAPICache.init(InMemoryBackend())

    @app.middleware("http")
    async def add_database_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-database"] = "true"
        return response

    return app
