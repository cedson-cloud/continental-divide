from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import router, session_router


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
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": settings.anthropic_model}

    app.include_router(session_router)
    app.include_router(router)
    return app


app = create_app()
