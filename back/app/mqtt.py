"""Cliente MQTT: consome a arvore do contrato v1, persiste telemetrias,
registra logs/alertas e dispara notificacoes por e-mail (R4, R5, R15, R16).

Inclui tambem a rotina periodica que avalia falta de luz solar.
"""

import json
import logging
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
from sqlalchemy import func

from config import settings
from database import SessionLocal
from models import TelemetrySoil, TelemetrySunlight
from crud import get_or_create_config, registrar_log
from services import notifier

log = logging.getLogger("mqtt")

# Ultimo status publicado pelo ESP32, para a API responder sem consultar o banco.
ultimo_status: dict = {"bomba": "off", "modo": "auto", "online": False}

_sun_thread: threading.Thread | None = None
_stop_event = threading.Event()


# --------------------------------------------------------------------------- #
# Callbacks MQTT
# --------------------------------------------------------------------------- #
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        log.error("Falha ao conectar no broker MQTT: %s", reason_code)
        return
    log.info("Conectado ao broker %s:%s", settings.MQTT_BROKER, settings.MQTT_PORT)
    # Subscricao na arvore inteira do contrato v1.
    client.subscribe(settings.TOPICO_WILDCARD, qos=0)
    log.info("Inscrito em %s", settings.TOPICO_WILDCARD)


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    ultimo_status["online"] = False
    log.warning("Desconectado do broker (%s); paho vai reconectar sozinho.", reason_code)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    try:
        dados = json.loads(payload)
    except json.JSONDecodeError:
        dados = None

    topic = msg.topic

    # status/pump nao precisa de banco para o /health; mas registramos mudanca.
    if topic == settings.TOPICO_STATUS:
        _handle_status(payload, dados)
        return

    db = SessionLocal()
    try:
        if topic == settings.TOPICO_SOIL:
            _handle_soil(db, payload, dados)
        elif topic == settings.TOPICO_SUNLIGHT:
            _handle_sunlight(db, payload, dados)
        elif topic == settings.TOPICO_ALERTA:
            _handle_alert(db, payload, dados)
        else:
            log.debug("Topico sem handler: %s", topic)
    except Exception:
        db.rollback()
        log.exception("Erro ao processar mensagem MQTT do topico %s", topic)
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
def _handle_status(payload: str, dados) -> None:
    if isinstance(dados, dict):
        anterior = dict(ultimo_status)
        ultimo_status.update(dados)
        # Loga mudanca de estado da bomba em system_logs.
        if dados.get("bomba") and dados.get("bomba") != anterior.get("bomba"):
            db = SessionLocal()
            try:
                registrar_log(
                    db,
                    tipo="STATUS",
                    descricao=f"Bomba {dados.get('bomba')} (modo {dados.get('modo', '?')})",
                    origem=dados.get("origem", "esp32"),
                )
            except Exception:
                db.rollback()
                log.exception("Erro ao registrar log de status")
            finally:
                db.close()


def _handle_soil(db, payload: str, dados) -> None:
    if not isinstance(dados, dict):
        log.warning("Telemetria de solo ignorada, payload nao e JSON: %s", payload)
        return
    db.add(
        TelemetrySoil(
            umidade=float(dados.get("umidade", 0)),
            raw=_as_int(dados.get("raw")),
            estado_bomba=str(dados.get("estado", "off")),
            modo=dados.get("modo", "auto"),
        )
    )
    db.commit()


def _handle_sunlight(db, payload: str, dados) -> None:
    if not isinstance(dados, dict):
        log.warning("Telemetria de luz ignorada, payload nao e JSON: %s", payload)
        return
    db.add(
        TelemetrySunlight(
            luminosidade=float(dados.get("luminosidade", 0)),
            raw=_as_int(dados.get("raw")),
        )
    )
    db.commit()


def _handle_alert(db, payload: str, dados) -> None:
    if isinstance(dados, dict):
        tipo = str(dados.get("tipo", "geral"))
        mensagem = str(dados.get("mensagem", ""))
    else:
        tipo = "geral"
        mensagem = payload

    registrar_log(db, tipo="ALERT", descricao=f"[{tipo}] {mensagem}", origem="esp32")

    # Notificacao externa imediata (sincrona; estamos em thread do paho).
    corpo = notifier.alerta_generico(tipo, mensagem)
    notifier.enviar_email(f"[Irrigacao IoT] Alerta: {tipo}", corpo)


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Rotina periodica: falta de luz solar (R4, R15)
# --------------------------------------------------------------------------- #
def _avaliar_falta_sol() -> None:
    db = SessionLocal()
    try:
        cfg = get_or_create_config(db)
        dias = cfg.dias_sem_sol_alerta
        limiar = cfg.limiar_luminosidade

        inicio = datetime.now(timezone.utc) - timedelta(days=dias)
        # Media diaria por dia nos ultimos `dias`.
        por_dia = (
            db.query(
                func.date(TelemetrySunlight.created_at).label("dia"),
                func.avg(TelemetrySunlight.luminosidade).label("media"),
            )
            .filter(TelemetrySunlight.created_at >= inicio)
            .group_by(func.date(TelemetrySunlight.created_at))
            .all()
        )

        if not por_dia:
            return  # sem dados de luz ainda

        dias_sem_sol = [row for row in por_dia if (row.media or 0) < limiar]
        if len(dias_sem_sol) >= dias:
            media_geral = sum((row.media or 0) for row in por_dia) / len(por_dia)
            registrar_log(
                db,
                tipo="SUNLIGHT",
                descricao=(
                    f"Falta de sol: {len(dias_sem_sol)} dia(s) abaixo de {limiar}% "
                    f"(media {media_geral:.1f}%)"
                ),
                origem="scheduler",
            )
            corpo = notifier.alerta_falta_sol(len(dias_sem_sol), media_geral, limiar)
            notifier.enviar_email("[Irrigacao IoT] Falta de luz solar", corpo)
    except Exception:
        db.rollback()
        log.exception("Erro na rotina de avaliacao de falta de sol")
    finally:
        db.close()


def _sun_loop() -> None:
    # Espera inicial curta para a app subir antes da primeira avaliacao.
    if _stop_event.wait(10):
        return
    while not _stop_event.is_set():
        _avaliar_falta_sol()
        if _stop_event.wait(settings.SUNLIGHT_CHECK_INTERVAL):
            break


# --------------------------------------------------------------------------- #
# Cliente e ciclo de vida
# --------------------------------------------------------------------------- #
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


def start_mqtt() -> None:
    """Conecta sem bloquear: se o broker estiver fora, a API sobe mesmo assim."""
    global _sun_thread

    if settings.MQTT_USERNAME:
        mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.use_tls:
        mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        log.info("TLS habilitado para a conexao MQTT")

    mqtt_client.connect_async(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()

    _stop_event.clear()
    _sun_thread = threading.Thread(target=_sun_loop, name="sunlight-check", daemon=True)
    _sun_thread.start()


def stop_mqtt() -> None:
    _stop_event.set()
    mqtt_client.loop_stop()
    try:
        mqtt_client.disconnect()
    except Exception:
        pass


def publicar_comando_bomba(comando: str) -> None:
    """Publica um comando no topico de comando da bomba (R8)."""
    mqtt_client.publish(settings.TOPICO_BOMBA, comando)
