from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_dep
from src.models.database import CapturedEvent

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get(
    "/stats",
    summary="Aggregate statistics for the admin dashboard",
)
def get_stats(db: Session = Depends(get_db_dep)) -> dict[str, Any]:
    total = db.query(func.count(CapturedEvent.id)).scalar() or 0
    network = (
        db.query(func.count(CapturedEvent.id))
        .filter(CapturedEvent.event_type == "network_intercept")
        .scalar()
        or 0
    )
    terminal = (
        db.query(func.count(CapturedEvent.id))
        .filter(CapturedEvent.event_type == "terminal_action")
        .scalar()
        or 0
    )
    return {
        "total_events": total,
        "network_intercepts": network,
        "terminal_actions": terminal,
        "other": total - network - terminal,
    }


@router.delete(
    "/logs",
    summary="Purge all captured events from the database",
    status_code=status.HTTP_200_OK,
)
def purge_logs(db: Session = Depends(get_db_dep)) -> dict[str, Any]:
    deleted = db.query(CapturedEvent).delete()
    db.commit()
    return {"deleted": deleted}


@router.delete(
    "/logs/{event_id}",
    summary="Delete a single captured event by ID",
    status_code=status.HTTP_200_OK,
)
def delete_log(event_id: int, db: Session = Depends(get_db_dep)) -> dict[str, Any]:
    row = db.query(CapturedEvent).filter(CapturedEvent.id == event_id).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found."
        )
    db.delete(row)
    db.commit()
    return {"deleted": event_id}


@router.get(
    "/logs",
    summary="Admin: paginated log list with richer metadata",
)
def admin_list_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = None,
    source_process: str | None = None,
    db: Session = Depends(get_db_dep),
) -> list[dict[str, Any]]:
    query = db.query(CapturedEvent).order_by(desc(CapturedEvent.id))
    if event_type:
        query = query.filter(CapturedEvent.event_type == event_type)
    if source_process:
        query = query.filter(CapturedEvent.source_process == source_process)
    rows = query.offset(offset).limit(limit).all()
    result = []
    for row in rows:
        try:
            data: dict[str, Any] = json.loads(row.raw_json)
        except Exception:
            data = {}
        data["id"] = row.id
        data["_db_timestamp"] = row.timestamp.isoformat() if row.timestamp else None
        result.append(data)
    return result
