"""Testes de autenticacao (R9, R18)."""


def test_register_and_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "novo@example.com", "password": "senha123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "novo@example.com"
    assert "id" in body

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "novo@example.com", "password": "senha123"},
    )
    assert resp.status_code == 200
    token = resp.json()
    assert token["token_type"] == "bearer"
    assert token["access_token"]


def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "senha123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "senha123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "x@example.com", "password": "errada"},
    )
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    # Sem token -> 401.
    resp = client.post("/api/v1/command/pump", json={"comando": "on"})
    assert resp.status_code == 401
