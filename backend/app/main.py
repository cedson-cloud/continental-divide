from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Continental Divide",
        description="Event-tracking request intake, validation, approval, and publish.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": settings.anthropic_model}

    # Routes for intake, decision, and queries are added in step 4.
    return app


app = create_app()
