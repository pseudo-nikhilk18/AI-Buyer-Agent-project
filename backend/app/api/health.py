import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import check_database_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class ServiceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "unavailable"]
    latency_ms: int


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "degraded"]
    environment: str
    checked_at: datetime
    services: dict[str, ServiceHealth]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def health(response: Response) -> HealthResponse:
    started_at = perf_counter()
    database_status: Literal["ready", "unavailable"] = "ready"

    try:
        check_database_connection()
    except SQLAlchemyError:
        database_status = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.exception("Database health check failed")

    latency_ms = round((perf_counter() - started_at) * 1_000)
    overall_status: Literal["ready", "degraded"] = (
        "ready" if database_status == "ready" else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        environment=get_settings().app_env,
        checked_at=datetime.now(UTC),
        services={
            "api": ServiceHealth(status="ready", latency_ms=0),
            "database": ServiceHealth(status=database_status, latency_ms=latency_ms),
        },
    )
