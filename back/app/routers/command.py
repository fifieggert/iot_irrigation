"""Envio de comandos para a bomba (R8). Rota protegida por JWT."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from config import settings
from crud import registrar_log
from database import get_db
from models import User
import mqtt
from schemas import CommandPumpRequest

router = APIRouter(prefix="/api/v1/command", tags=["command"])


@router.post("/pump")
def command_pump(
    cmd: CommandPumpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not mqtt.mqtt_client.is_connected():
        raise HTTPException(
            status_code=503, detail="Backend nao esta conectado ao broker MQTT"
        )

    mqtt.publicar_comando_bomba(cmd.comando)
    registrar_log(
        db,
        tipo="COMMAND",
        descricao=f"Comando '{cmd.comando}' enviado a bomba",
        origem=user.email,
    )
    return {
        "status": "success",
        "topico": settings.TOPICO_BOMBA,
        "command_sent": cmd.comando,
    }
