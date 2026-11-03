"""Fixtures de teste (R18).

Usa SQLite em memoria no lugar do Postgres e substitui o cliente MQTT por um
fake, de modo que os testes rodem sem banco externo nem broker.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Variaveis minimas para o Settings carregar sem um .env real.
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")

# Torna o pacote app/ importavel por nome (config, database, ...).
APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))


@pytest.fixture()
def client():
    import database

    # Engine SQLite em memoria compartilhada entre conexoes.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    # Redireciona o engine/sessao globais para o SQLite de teste.
    database.engine = test_engine
    database.SessionLocal = TestingSessionLocal

    import models  # noqa: F401

    database.Base.metadata.create_all(bind=test_engine)

    # Fake do cliente MQTT: conectado e com publish que grava o ultimo comando.
    import mqtt as mqtt_module

    class FakeMQTT:
        def __init__(self):
            self.published = []

        def is_connected(self):
            return True

        def publish(self, topic, payload):
            self.published.append((topic, payload))

    fake = FakeMQTT()
    mqtt_module.mqtt_client = fake
    mqtt_module.publicar_comando_bomba = lambda comando: fake.publish(
        "command/pump", comando
    )

    # Nao inicia loop MQTT real nem a thread de sol durante os testes.
    mqtt_module.start_mqtt = lambda: None
    mqtt_module.stop_mqtt = lambda: None

    import importlib

    import main

    importlib.reload(main)

    # get_db usa database.SessionLocal (ja redirecionado).
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = override_get_db

    with TestClient(main.app) as c:
        c._fake_mqtt = fake  # type: ignore[attr-defined]
        yield c

    main.app.dependency_overrides.clear()
    database.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def auth_headers(client):
    """Registra e autentica um usuario, devolvendo o header Authorization."""
    email = "tester@example.com"
    password = "senha123"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
