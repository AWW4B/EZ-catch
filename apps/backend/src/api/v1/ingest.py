from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_dep
from src.models.database import CapturedEvent

router = APIRouter(prefix="/api/v1", tags=["ingest"])


class IngestEventPayload(BaseModel):
    """
    Minimal shape expected from the agent's BufferForwarder.
    Extra fields are passed through so nothing is silently dropped.
    """
    event_type: str = Field(..., description="'network_intercept' or 'terminal_action'")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp",
    )
    source_process: str | None = None

    model_config = {"extra": "allow"}


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a batch of agent events from the local buffer forwarder",
)
def ingest_events(
    payload: list[IngestEventPayload],
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty payload — nothing to ingest.",
        )
    if len(payload) > 500:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Batch too large — maximum 500 events per request.",
        )

    rows: list[CapturedEvent] = []
    for item in payload:
        raw = item.model_dump(mode="json")
        rows.append(
            CapturedEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=item.event_type,
                source_process=item.source_process,
                raw_json=json.dumps(raw),
            )
        )

    db.add_all(rows)
    db.commit()

    return {"accepted": len(rows)}
