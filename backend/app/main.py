from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routes import router, session_router
from .storage import RequestQuotaReached


def _too_large() -> HTTPException:
    return HTTPException(status_code=413, detail="request body is too large")


class BodySizeLimit:
    """Refuses a body over MAX_REQUEST_BYTES before any route reads it, whether or not the
    request declares its length. Read per request, so the limit follows configuration."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().max_request_bytes
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            response = JSONResponse({"detail": _too_large().detail}, status_code=413)
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # An HTTPException, because FastAPI turns any other error raised
                    # while reading a body into a 400.
                    raise _too_large()
            return message

        await self.app(scope, limited_receive, send)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Continental Divide",
        description="Event-tracking request intake, validation, approval, and publish.",
        version="0.1.0",
    )

    app.add_middleware(BodySizeLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestQuotaReached)
    def quota_reached(request: Request, exc: RequestQuotaReached) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=429)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": settings.anthropic_model}

    app.include_router(session_router)
    app.include_router(router)
    return app


app = create_app()
