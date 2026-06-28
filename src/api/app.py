"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_cors_origins
from api.rate_limit import add_rate_limit_middleware
from api.routes.runs import router as runs_router
from api.run_manager import RunManager, get_run_manager
from config import get_settings
from version import get_version


def create_app(*, manager: RunManager | None = None) -> FastAPI:
    app = FastAPI(title="Roast Arena API", version=get_version())

    if manager is not None:
        app.state.run_manager = manager
        app.dependency_overrides[get_run_manager] = lambda: manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_rate_limit_middleware(app, settings=get_settings())

    app.include_router(runs_router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
