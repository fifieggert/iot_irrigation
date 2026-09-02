from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True)
    umidade = Column(Float, nullable=False)
    estado_bomba = Column(String(10), nullable=False)
    modo = Column(String(20), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    mensagem = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())