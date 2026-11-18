from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status

from app.models import Tournament
from app.store import Store, get_store

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(store: Annotated[Store, Depends(get_store)]) -> dict[str, str]:
    """Readiness: the app can reach its database."""
    try:
        store.get(Tournament, 1)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable") from exc
    return {"status": "ready"}
