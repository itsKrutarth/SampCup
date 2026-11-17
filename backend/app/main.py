from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.api import admin, auth, judge, public, registration
from app.api.routes import router
from app.core.config import get_settings
from app.services.errors import ServiceError

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


def create_app() -> FastAPI:
    settings = get_settings()
    public_docs = settings.app_env != "production"
    app = FastAPI(
        title=settings.app_name,
        docs_url="/api/docs" if public_docs else None,
        openapi_url="/api/openapi.json" if public_docs else None,
        redoc_url=None,
    )
    for module in (
        router,
        public.router,
        registration.router,
        auth.router,
        judge.router,
        admin.router,
    ):
        app.include_router(module, prefix="/api")

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if not request.url.path.startswith("/api/docs"):
            for name, value in SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
        return response

    if settings.static_dir:
        serve_frontend(app, Path(settings.static_dir))
    return app


def serve_frontend(app: FastAPI, root: Path) -> None:
    """Serve the built single-page app; unknown paths get index.html (client routing)."""
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            cache = (
                "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            )
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
