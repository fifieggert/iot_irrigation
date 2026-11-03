"""Testes do endpoint de comando da bomba (R8, R18)."""


def test_command_pump_autenticado(client, auth_headers):
    resp = client.post(
        "/api/v1/command/pump", json={"comando": "on"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["command_sent"] == "on"

    # O fake MQTT deve ter recebido o publish.
    assert client._fake_mqtt.published
    _, comando = client._fake_mqtt.published[-1]
    assert comando == "on"


def test_command_pump_comando_invalido(client, auth_headers):
    resp = client.post(
        "/api/v1/command/pump", json={"comando": "ligar"}, headers=auth_headers
    )
    # Literal["on","off","auto"] -> 422 na validacao do Pydantic.
    assert resp.status_code == 422


def test_command_pump_registra_log(client, auth_headers):
    client.post("/api/v1/command/pump", json={"comando": "auto"}, headers=auth_headers)
    resp = client.get("/api/v1/logs?tipo=COMMAND")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any("auto" in item["descricao"] for item in body["items"])


def test_config_get_e_update(client, auth_headers):
    # GET publico com defaults.
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    assert resp.json()["limite_umidade_min"] == 30

    # PUT autenticado altera o valor.
    resp = client.put(
        "/api/v1/config",
        json={"limite_umidade_min": 25},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["limite_umidade_min"] == 25
