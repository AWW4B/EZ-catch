from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_dep
from src.models.database import CapturedEvent

router = APIRouter(prefix="/api/v1", tags=["logs"])


def _row_to_dict(row: CapturedEvent) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(row.raw_json)
    except Exception:
        data = {}
    data.setdefault("id", row.id)
    return data


@router.get(
    "/logs",
    summary="Return captured events for the admin dashboard",
)
def list_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, description="Filter by event_type"),
    db: Session = Depends(get_db_dep),
) -> list[dict[str, Any]]:
    query = db.query(CapturedEvent).order_by(desc(CapturedEvent.id))
    if event_type:
        query = query.filter(CapturedEvent.event_type == event_type)
    rows = query.offset(offset).limit(limit).all()
    return [_row_to_dict(r) for r in rows]


@router.get(
    "/logs/{event_id}",
    summary="Return a single captured event by its database ID",
)
def get_log(
    event_id: int,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    row = db.query(CapturedEvent).filter(CapturedEvent.id == event_id).first()
    if row is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return _row_to_dict(row)
