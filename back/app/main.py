from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from app.database import engine, Base, get_db
from app.models import TelemetryLog, AlertLog
from app.schemas import TelemetryRead, AlertRead, PumpCommand
from app.mqtt import start_mqtt, mqtt_client

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Irrigacao IoT API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    start_mqtt()

@app.get("/api/telemetry", response_model=List[TelemetryRead])
def get_telemetry(limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    """Retrieve historical moisture and status logs."""
    return db.query(TelemetryLog).order_by(TelemetryLog.timestamp.desc()).limit(limit).all()

@app.get("/api/telemetry/latest", response_model=TelemetryRead)
def get_latest_telemetry(db: Session = Depends(get_db)):
    """Get the most recent reading from the ESP32."""
    latest = db.query(TelemetryLog).order_by(TelemetryLog.timestamp.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No telemetry logs found")
    return latest

@app.get("/api/alerts", response_model=List[AlertRead])
def get_alerts(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    """Retrieve system alert logs."""
    return db.query(AlertLog).order_by(AlertLog.timestamp.desc()).limit(limit).all()

@app.post("/api/bomba")
def control_pump(cmd: PumpCommand):
    """Publish a command to turn the pump on/off."""
    if cmd.comando not in ["on", "off"]:
        raise HTTPException(status_code=400, detail="Invalid command. Use 'on' or 'off'.")
    
    mqtt_client.publish("irrigacao/bomba", cmd.comando)
    return {"status": "success", "command_sent": cmd.comando}