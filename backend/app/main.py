import hmac
import json
import logging
import sys
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.api import admin, auth, judge, public, registration
from app.api.routes import router
from app.core.config import get_settings
from app.services.errors import ServiceError

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# Public pages are the same for everyone: CloudFront may serve them for 3 seconds.
# CloudFront keeps a page 3s; it may serve the last copy while it fetches a new one, or for a
# minute if the server is failing, so a busy moment never blanks the public pages.
PUBLIC_CACHE = "public, max-age=0, s-maxage=3, stale-while-revalidate=10, stale-if-error=60"

logger = logging.getLogger("sampcup")


def log(level: int, **fields: Any) -> None:
    """One JSON line per event; CloudWatch Logs Insights reads the fields directly."""
    logger.log(level, json.dumps(fields, default=str))


def _setup_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def create_app() -> FastAPI:
    settings = get_settings()
    _setup_logging()
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
    async def edge(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        secret = settings.origin_secret
        if secret and not hmac.compare_digest(request.headers.get("x-origin-verify", ""), secret):
            response: Response = JSONResponse({"detail": "Forbidden"}, status_code=403)
        else:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(json.dumps({"event": "unhandled", "path": request.url.path}))
                response = JSONResponse(
                    {"detail": "Something went wrong. Please try again."}, status_code=500
                )
        path = request.url.path
        if (
            request.method == "GET"
            and path.startswith("/api/public/")
            and response.status_code == 200
        ):
            response.headers["Cache-Control"] = PUBLIC_CACHE
        else:
            response.headers.setdefault("Cache-Control", "no-store")
        if not path.startswith("/api/docs"):
            for name, value in SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
        context = request.scope.get("aws.context")
        log(
            logging.ERROR if response.status_code >= 500 else logging.INFO,
            method=request.method,
            path=path,
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000),
            request_id=getattr(context, "aws_request_id", None),
        )
        return response

    return app


app = create_app()
