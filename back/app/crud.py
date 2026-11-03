"""Operacoes de acesso a dados reutilizadas por rotas e MQTT."""

from sqlalchemy.orm import Session

from config import settings
from models import SystemConfig, SystemLog


def get_or_create_config(db: Session) -> SystemConfig:
    """Garante a linha unica de configuracao (id=1)."""
    cfg = db.query(SystemConfig).first()
    if cfg is None:
        cfg = SystemConfig(
            limite_umidade_min=settings.LIMITE_UMIDADE_MIN,
            limite_umidade_max=settings.LIMITE_UMIDADE_MAX,
            dias_sem_sol_alerta=settings.DIAS_SEM_SOL_ALERTA,
            limiar_luminosidade=settings.LIMIAR_LUMINOSIDADE,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def registrar_log(
    db: Session, tipo: str, descricao: str, origem: str | None = None
) -> SystemLog:
    """Grava um evento em system_logs."""
    entry = SystemLog(tipo=tipo, descricao=descricao[:500], origem=origem)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
