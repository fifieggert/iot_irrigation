import json
import logging

import paho.mqtt.client as mqtt

from app.config import settings
from app.database import SessionLocal
from app.models import TelemetryLog, AlertLog

log = logging.getLogger("mqtt")

# Ultimo status publicado pelo ESP32, para a API responder sem consultar o banco.
ultimo_status: dict = {"bomba": "off", "modo": "auto", "online": False}


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        log.error("Falha ao conectar no broker MQTT: %s", reason_code)
        return
    log.info("Conectado ao broker %s:%s", settings.MQTT_BROKER, settings.MQTT_PORT)
    client.subscribe(
        [(settings.TOPICO_UMIDADE, 0), (settings.TOPICO_ALERTA, 0), (settings.TOPICO_STATUS, 0)]
    )


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    ultimo_status["online"] = False
    log.warning("Desconectado do broker (%s); paho vai reconectar sozinho.", reason_code)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")

    try:
        dados = json.loads(payload)
    except json.JSONDecodeError:
        dados = None

    if msg.topic == settings.TOPICO_STATUS:
        if isinstance(dados, dict):
            ultimo_status.update(dados)
        return

    db = SessionLocal()
    try:
        if msg.topic == settings.TOPICO_UMIDADE:
            if not isinstance(dados, dict):
                log.warning("Telemetria ignorada, payload nao e JSON: %s", payload)
                return
            db.add(
                TelemetryLog(
                    umidade=float(dados.get("umidade", 0)),
                    estado_bomba=str(dados.get("estado", "off")),
                    modo=dados.get("modo", "manual"),
                )
            )
            db.commit()

        elif msg.topic == settings.TOPICO_ALERTA:
            # O firmware publica {"tipo":..., "mensagem":..., "umidade":...}
            if isinstance(dados, dict):
                mensagem = f"[{dados.get('tipo', 'geral')}] {dados.get('mensagem', '')}"
            else:
                mensagem = payload
            db.add(AlertLog(mensagem=mensagem[:255]))
            db.commit()

    except Exception:
        db.rollback()
        log.exception("Erro ao gravar mensagem MQTT do topico %s", msg.topic)
    finally:
        db.close()


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


def start_mqtt() -> None:
    """Conecta sem bloquear: se o broker estiver fora, a API sobe mesmo assim."""
    mqtt_client.connect_async(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()


def stop_mqtt() -> None:
    mqtt_client.loop_stop()
    try:
        mqtt_client.disconnect()
    except Exception:
        pass
