import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from database import engine, Base, SessionLocal
from crud import get_or_create_config
from mqtt import start_mqtt, stop_mqtt, mqtt_client, ultimo_status
from routers import auth, command, config as config_router, logs, telemetry

# Importa os models para que Base.metadata conheca todas as tabelas.
import models  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        # Garante a linha unica de configuracao.
        db = SessionLocal()
        try:
            get_or_create_config(db)
        finally:
            db.close()
    except Exception:
        # A API sobe mesmo sem banco; so os endpoints que usam o banco falham.
        log.exception("Nao foi possivel criar/verificar as tabelas no Postgres")
    start_mqtt()
    yield
    stop_mqtt()


app = FastAPI(title="Irrigacao IoT API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(telemetry.router)
app.include_router(command.router)
app.include_router(logs.router)
app.include_router(config_router.router)


def _db_ok() -> bool:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception:
        return False


@app.get("/health", tags=["health"])
def health():
    """Status da API, banco e conexao MQTT."""
    return {
        "api": "ok",
        "database": "ok" if _db_ok() else "indisponivel",
        "mqtt_conectado": mqtt_client.is_connected(),
        "broker": f"{settings.MQTT_BROKER}:{settings.MQTT_PORT}",
        "topico_base": settings.MQTT_TOPIC_BASE,
        "ultimo_status": ultimo_status,
    }


# Alias antigo para compatibilidade com clientes existentes.
@app.get("/api/health", include_in_schema=False)
def health_legacy():
    return health()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
