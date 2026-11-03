"""Testes de insercao e leitura de telemetrias (R5, R18)."""

import json


def _inserir_soil(db_session_factory, **kwargs):
    import models

    db = db_session_factory()
    try:
        reg = models.TelemetrySoil(**kwargs)
        db.add(reg)
        db.commit()
    finally:
        db.close()


def test_soil_history_empty(client):
    resp = client.get("/api/v1/telemetry/soil/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_mqtt_soil_handler_persiste(client):
    """O handler MQTT de solo deve gravar na tabela telemetry_soil."""
    import mqtt as mqtt_module
    import database

    db = database.SessionLocal()
    try:
        payload = json.dumps(
            {"umidade": 42, "raw": 2310, "estado": "off", "modo": "auto"}
        )
        mqtt_module._handle_soil(db, payload, json.loads(payload))
    finally:
        db.close()

    resp = client.get("/api/v1/telemetry/soil/history")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["umidade"] == 42
    assert dados[0]["raw"] == 2310
    assert dados[0]["estado_bomba"] == "off"


def test_mqtt_sunlight_handler_persiste(client):
    import mqtt as mqtt_module
    import database

    db = database.SessionLocal()
    try:
        payload = json.dumps({"luminosidade": 78, "raw": 3200})
        mqtt_module._handle_sunlight(db, payload, json.loads(payload))
    finally:
        db.close()

    resp = client.get("/api/v1/telemetry/sunlight/history")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["luminosidade"] == 78
    assert dados[0]["raw"] == 3200
