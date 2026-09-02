from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TelemetryRead(BaseModel):
    id: int
    umidade: float
    estado_bomba: str
    modo: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class AlertRead(BaseModel):
    id: int
    mensagem: str
    timestamp: datetime

    class Config:
        from_attributes = True

class PumpCommand(BaseModel):
    comando: str  # "on" or "off"