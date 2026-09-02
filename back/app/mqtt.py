import json
import paho.mqtt.client as mqtt
from app.config import settings
from app.database import SessionLocal
from app.models import TelemetryLog, AlertLog

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe("irrigacao/umidade")
    client.subscribe("irrigacao/alerta")

def on_message(client, userdata, msg):
    db = SessionLocal()
    try:
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        
        if topic == "irrigacao/umidade":
            data = json.loads(payload)
            log = TelemetryLog(
                umidade=float(data.get("umidade", 0)),
                estado_bomba=str(data.get("estado", "off")),
                modo=data.get("modo", "manual")
            )
            db.add(log)
            db.commit()

        elif topic == "irrigacao/alerta":
            log = AlertLog(mensagem=payload)
            db.add(log)
            db.commit()

    except Exception as e:
        print(f"Error processing MQTT message: {e}")
        db.rollback()
    finally:
        db.close()

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def start_mqtt():
    mqtt_client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, 60)
    mqtt_client.loop_start()