from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from sqlalchemy.sql import func

from database import Base
from config import settings


class User(Base):
    """Usuario do painel (R4, R9)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TelemetrySoil(Base):
    """Telemetria de umidade do solo (R4, R5)."""

    __tablename__ = "telemetry_soil"

    id = Column(Integer, primary_key=True, index=True)
    umidade = Column(Float, nullable=False)
    raw = Column(Integer, nullable=True)
    estado_bomba = Column(String(10), nullable=False, default="off")
    modo = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TelemetrySunlight(Base):
    """Telemetria do sensor de luz/calor (R4, R5)."""

    __tablename__ = "telemetry_sunlight"

    id = Column(Integer, primary_key=True, index=True)
    luminosidade = Column(Float, nullable=False)
    raw = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SystemLog(Base):
    """Logs e alertas do sistema (R4, R6, R15).

    tipo: COMMAND | ALERT | STATUS | SAFETY | SUNLIGHT
    """

    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(20), nullable=False, index=True)
    descricao = Column(String(500), nullable=False)
    origem = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SystemConfig(Base):
    """Parametros operacionais ajustaveis (R4, R6). Linha unica (id=1)."""

    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    limite_umidade_min = Column(Integer, nullable=False, default=settings.LIMITE_UMIDADE_MIN)
    limite_umidade_max = Column(Integer, nullable=False, default=settings.LIMITE_UMIDADE_MAX)
    dias_sem_sol_alerta = Column(Integer, nullable=False, default=settings.DIAS_SEM_SOL_ALERTA)
    limiar_luminosidade = Column(Integer, nullable=False, default=settings.LIMIAR_LUMINOSIDADE)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# indices compostos para consultas de historico por periodo
Index("ix_soil_created", TelemetrySoil.created_at.desc())
Index("ix_sunlight_created", TelemetrySunlight.created_at.desc())
Index("ix_logs_tipo_created", SystemLog.tipo, SystemLog.created_at.desc())
