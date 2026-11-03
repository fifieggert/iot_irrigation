from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --------------------------------------------------------------------------- #
# Autenticacao (R9)
# --------------------------------------------------------------------------- #
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------------------------------- #
# Telemetria de solo (R4, R5)
# --------------------------------------------------------------------------- #
class SoilRead(BaseModel):
    id: int
    umidade: float
    raw: Optional[int] = None
    estado_bomba: str
    modo: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Telemetria de luminosidade (R4, R5)
# --------------------------------------------------------------------------- #
class SunlightRead(BaseModel):
    id: int
    luminosidade: float
    raw: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Logs / alertas (R6, R15)
# --------------------------------------------------------------------------- #
class LogRead(BaseModel):
    id: int
    tipo: str
    descricao: str
    origem: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LogPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[LogRead]


# --------------------------------------------------------------------------- #
# Configuracao de thresholds (R4, R6)
# --------------------------------------------------------------------------- #
class ConfigResponse(BaseModel):
    limite_umidade_min: int
    limite_umidade_max: int
    dias_sem_sol_alerta: int
    limiar_luminosidade: int
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdate(BaseModel):
    limite_umidade_min: Optional[int] = Field(default=None, ge=0, le=100)
    limite_umidade_max: Optional[int] = Field(default=None, ge=0, le=100)
    dias_sem_sol_alerta: Optional[int] = Field(default=None, ge=1, le=30)
    limiar_luminosidade: Optional[int] = Field(default=None, ge=0, le=100)


# --------------------------------------------------------------------------- #
# Comando da bomba (R8)
# --------------------------------------------------------------------------- #
class CommandPumpRequest(BaseModel):
    comando: Literal["on", "off", "auto"]
