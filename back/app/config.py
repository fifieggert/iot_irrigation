from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # Banco de dados (Supabase / PostgreSQL via pooler)
    # ------------------------------------------------------------------ #
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_SSLMODE: str = "require"

    # ------------------------------------------------------------------ #
    # MQTT (HiveMQ)
    # ------------------------------------------------------------------ #
    MQTT_BROKER: str
    MQTT_PORT: int = 1883
    # Prefixo do contrato v1. Precisa ser identico ao firmware/dashboard.
    MQTT_TOPIC_BASE: str = "g2fifi/irrigation/v1"
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    # Ativa TLS automaticamente quando a porta e a de TLS (8883) ou quando
    # MQTT_TLS=true e informado explicitamente.
    MQTT_TLS: bool = False

    # ------------------------------------------------------------------ #
    # Autenticacao / JWT (R9)
    # ------------------------------------------------------------------ #
    JWT_SECRET: str = "troque-este-segredo-em-producao"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # ------------------------------------------------------------------ #
    # Notificacao por e-mail / SMTP (R15)
    # ------------------------------------------------------------------ #
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_TLS: bool = True
    ALERT_EMAIL_TO: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Regras de negocio (defaults; podem ser sobrescritos em system_config)
    # ------------------------------------------------------------------ #
    LIMITE_UMIDADE_MIN: int = 30
    LIMITE_UMIDADE_MAX: int = 60
    DIAS_SEM_SOL_ALERTA: int = 3
    # Limiar de luminosidade (0-100) abaixo do qual o dia conta como "sem sol".
    LIMIAR_LUMINOSIDADE: int = 20
    # Intervalo (segundos) da rotina periodica que avalia falta de sol.
    SUNLIGHT_CHECK_INTERVAL: int = 60 * 60  # 1h

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus

        senha = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{senha}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={self.POSTGRES_SSLMODE}"
        )

    @property
    def use_tls(self) -> bool:
        return self.MQTT_TLS or self.MQTT_PORT == 8883

    # --- Topicos do contrato v1 ------------------------------------------ #
    @property
    def TOPICO_SOIL(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/telemetry/soil"

    @property
    def TOPICO_SUNLIGHT(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/telemetry/sunlight"

    @property
    def TOPICO_STATUS(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/status/pump"

    @property
    def TOPICO_ALERTA(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/alert"

    @property
    def TOPICO_BOMBA(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/command/pump"

    @property
    def TOPICO_WILDCARD(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/#"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
