from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    
    load_dotenv()
    
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_SSLMODE: str = "require"

    MQTT_BROKER: str
    MQTT_PORT: int
    # Precisa ser identico ao TOPICO_BASE do firmware e do dashboard.
    MQTT_TOPIC_BASE: str = "irrigacao/g2fifi"

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
    def TOPICO_UMIDADE(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/umidade"

    @property
    def TOPICO_ALERTA(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/alerta"

    @property
    def TOPICO_STATUS(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/status"

    @property
    def TOPICO_BOMBA(self) -> str:
        return f"{self.MQTT_TOPIC_BASE}/bomba"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
