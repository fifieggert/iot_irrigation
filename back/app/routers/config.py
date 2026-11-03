"""Consulta e atualizacao dos parametros operacionais (R4, R6).

A leitura e publica; a atualizacao exige autenticacao.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from crud import get_or_create_config, registrar_log
from database import get_db
from models import User
from schemas import ConfigResponse, ConfigUpdate

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return get_or_create_config(db)


@router.put("", response_model=ConfigResponse)
def update_config(
    payload: ConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = get_or_create_config(db)
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(cfg, campo, valor)
    db.commit()
    db.refresh(cfg)

    registrar_log(
        db,
        tipo="COMMAND",
        descricao=f"Configuracao atualizada: {dados}",
        origem=user.email,
    )
    return cfg
