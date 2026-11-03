"""Historico de telemetrias de solo e luminosidade (R5, R14)."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import TelemetrySoil, TelemetrySunlight
from schemas import SoilRead, SunlightRead

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/soil/history", response_model=List[SoilRead])
def soil_history(
    inicio: Optional[datetime] = Query(default=None, description="Data/hora inicial (ISO)"),
    fim: Optional[datetime] = Query(default=None, description="Data/hora final (ISO)"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(TelemetrySoil)
    if inicio:
        q = q.filter(TelemetrySoil.created_at >= inicio)
    if fim:
        q = q.filter(TelemetrySoil.created_at <= fim)
    return q.order_by(TelemetrySoil.created_at.desc()).limit(limit).all()


@router.get("/soil/latest", response_model=Optional[SoilRead])
def soil_latest(db: Session = Depends(get_db)):
    return db.query(TelemetrySoil).order_by(TelemetrySoil.created_at.desc()).first()


@router.get("/sunlight/history", response_model=List[SunlightRead])
def sunlight_history(
    inicio: Optional[datetime] = Query(default=None, description="Data/hora inicial (ISO)"),
    fim: Optional[datetime] = Query(default=None, description="Data/hora final (ISO)"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(TelemetrySunlight)
    if inicio:
        q = q.filter(TelemetrySunlight.created_at >= inicio)
    if fim:
        q = q.filter(TelemetrySunlight.created_at <= fim)
    return q.order_by(TelemetrySunlight.created_at.desc()).limit(limit).all()


@router.get("/sunlight/latest", response_model=Optional[SunlightRead])
def sunlight_latest(db: Session = Depends(get_db)):
    return db.query(TelemetrySunlight).order_by(TelemetrySunlight.created_at.desc()).first()
