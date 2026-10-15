from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_server_settings
from .routers import admin_router, builds_router, deployments_router, sandboxes_router


def create_app() -> FastAPI:
    settings = get_server_settings()
    app = FastAPI(
        title="sandebox",
        description="Self-hosted execution substrate for running untrusted code on Kubernetes with gVisor isolation",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["health"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def readyz():
        return {
            "status": "ready",
            "namespace": settings.sandbox_config.namespace,
            "runtime_class": settings.sandbox_config.runtime_class,
        }

    app.include_router(sandboxes_router)
    app.include_router(builds_router)
    app.include_router(deployments_router)
    app.include_router(admin_router)

    return app


app = create_app()
