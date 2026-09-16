import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from models import TelemetryLog, AlertLog
from schemas import TelemetryRead, AlertRead, PumpCommand
from mqtt import start_mqtt, stop_mqtt, mqtt_client, ultimo_status

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        # A API sobe mesmo sem banco; os endpoints de historico e que vao falhar.
        log.exception("Nao foi possivel criar/verificar as tabelas no Postgres")
    start_mqtt()
    yield
    stop_mqtt()


app = FastAPI(title="Irrigacao IoT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "api": "ok",
        "mqtt_conectado": mqtt_client.is_connected(),
        "broker": f"{settings.MQTT_BROKER}:{settings.MQTT_PORT}",
        "topico_base": settings.MQTT_TOPIC_BASE,
        "ultimo_status": ultimo_status,
    }


@app.get("/api/telemetry", response_model=List[TelemetryRead])
def get_telemetry(limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    """Historico de leituras de umidade e estado da bomba."""
    return db.query(TelemetryLog).order_by(TelemetryLog.timestamp.desc()).limit(limit).all()


@app.get("/api/telemetry/latest", response_model=TelemetryRead)
def get_latest_telemetry(db: Session = Depends(get_db)):
    """Leitura mais recente enviada pelo ESP32."""
    latest = db.query(TelemetryLog).order_by(TelemetryLog.timestamp.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="Nenhuma telemetria registrada")
    return latest


@app.get("/api/alerts", response_model=List[AlertRead])
def get_alerts(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    """Historico de alertas do sistema."""
    return db.query(AlertLog).order_by(AlertLog.timestamp.desc()).limit(limit).all()


@app.post("/api/bomba")
def control_pump(cmd: PumpCommand):
    """Publica um comando de acionamento no topico da bomba."""
    comando = cmd.comando.strip().lower()
    if comando not in ("on", "off", "auto"):
        raise HTTPException(status_code=400, detail="Comando invalido. Use 'on', 'off' ou 'auto'.")

    if not mqtt_client.is_connected():
        raise HTTPException(status_code=503, detail="Backend nao esta conectado ao broker MQTT")

    mqtt_client.publish(settings.TOPICO_BOMBA, comando)
    return {"status": "success", "topico": settings.TOPICO_BOMBA, "command_sent": comando}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


