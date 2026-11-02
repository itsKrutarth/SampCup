from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    public_docs = settings.app_env != "production"
    app = FastAPI(
        title=settings.app_name,
        docs_url="/api/docs" if public_docs else None,
        openapi_url="/api/openapi.json" if public_docs else None,
        redoc_url=None,
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
