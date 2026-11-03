"""Listagem paginada e filtrada de logs/alertas do sistema (R6)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import SystemLog
from schemas import LogPage

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("", response_model=LogPage)
def list_logs(
    tipo: Optional[str] = Query(default=None, description="COMMAND|ALERT|STATUS|SAFETY|SUNLIGHT"),
    inicio: Optional[datetime] = Query(default=None),
    fim: Optional[datetime] = Query(default=None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(SystemLog)
    if tipo:
        q = q.filter(SystemLog.tipo == tipo.upper())
    if inicio:
        q = q.filter(SystemLog.created_at >= inicio)
    if fim:
        q = q.filter(SystemLog.created_at <= fim)

    total = q.count()
    items = (
        q.order_by(SystemLog.created_at.desc()).offset(offset).limit(limit).all()
    )
    return LogPage(total=total, limit=limit, offset=offset, items=items)
