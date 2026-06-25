"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import RunRegistry, get_cors_origins, get_run_registry
from api.routes.runs import router as runs_router


def create_app(*, registry: RunRegistry | None = None) -> FastAPI:
    app = FastAPI(title="Roast Arena API", version="0.1.0")

    if registry is not None:
        app.state.run_registry = registry
        app.dependency_overrides[get_run_registry] = lambda: registry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
