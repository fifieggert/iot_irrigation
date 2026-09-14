"""
Simulador do ESP32 - permite testar backend e painel sem o hardware montado.

Publica nos mesmos topicos do firmware e responde aos comandos da bomba,
com a mesma logica de histerese e trava de seguranca.

Uso:  .venv/Scripts/python.exe simulador_esp32.py
"""

import json
import random
import signal
import sys
import time

import paho.mqtt.client as mqtt

TOPICO_BASE = "irrigacao/g2fifi"
BROKER = "broker.hivemq.com"
PORTA = 1883

T_UMIDADE = f"{TOPICO_BASE}/umidade"
T_STATUS = f"{TOPICO_BASE}/status"
T_ALERTA = f"{TOPICO_BASE}/alerta"
T_BOMBA = f"{TOPICO_BASE}/bomba"

# Mesmos parametros do firmware
LIMIAR_LIGA = 30
LIMIAR_DESLIGA = 60
INTERVALO_LEITURA = 5.0
TEMPO_MAX_BOMBA = 30.0

umidade = 45.0
bomba_ligada = False
modo_auto = True
bomba_ligada_em = 0.0
alerta_solo_seco = False
rodando = True


def agora() -> float:
    return time.monotonic()


def publicar_status(client, origem: str) -> None:
    payload = {
        "bomba": "on" if bomba_ligada else "off",
        "modo": "auto" if modo_auto else "manual",
        "origem": origem,
        "online": True,
    }
    client.publish(T_STATUS, json.dumps(payload))
    print(f"[STATUS] {payload}")


def publicar_alerta(client, tipo: str, mensagem: str) -> None:
    payload = {"tipo": tipo, "mensagem": mensagem, "umidade": round(umidade)}
    client.publish(T_ALERTA, json.dumps(payload))
    print(f"[ALERTA] {payload}")


def set_bomba(client, ligar: bool, origem: str) -> None:
    global bomba_ligada, bomba_ligada_em
    if ligar == bomba_ligada:
        return
    bomba_ligada = ligar
    if ligar:
        bomba_ligada_em = agora()
    publicar_status(client, origem)


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Conectado ao broker ({reason_code}). Topico base: {TOPICO_BASE}")
    client.subscribe(T_BOMBA)
    publicar_status(client, "boot")


def on_message(client, userdata, msg):
    global modo_auto
    comando = msg.payload.decode("utf-8", errors="replace").strip().lower()
    print(f"[COMANDO] {comando}")

    if comando == "on":
        modo_auto = False
        set_bomba(client, True, "manual")
    elif comando == "off":
        modo_auto = False
        set_bomba(client, False, "manual")
    elif comando == "auto":
        modo_auto = True
        publicar_status(client, "auto")
    else:
        publicar_alerta(client, "comando", "Comando desconhecido recebido")


def encerrar(signum, frame):
    global rodando
    rodando = False


def main() -> None:
    global umidade, alerta_solo_seco

    signal.signal(signal.SIGINT, encerrar)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(T_STATUS, json.dumps({"online": False}))
    client.connect(BROKER, PORTA, 60)
    client.loop_start()

    print("Simulador rodando. Ctrl+C para parar.\n")
    proxima_leitura = 0.0

    while rodando:
        t = agora()

        # Trava de seguranca, igual ao firmware
        if bomba_ligada and t - bomba_ligada_em >= TEMPO_MAX_BOMBA:
            set_bomba(client, False, "seguranca")
            publicar_alerta(
                client, "seguranca",
                "Bomba excedeu o tempo maximo e foi desligada automaticamente"
            )

        if t >= proxima_leitura:
            proxima_leitura = t + INTERVALO_LEITURA

            # Solo encharca com a bomba ligada e seca devagar com ela desligada.
            umidade += 6.0 if bomba_ligada else -1.5
            umidade += random.uniform(-0.4, 0.4)
            umidade = max(0.0, min(100.0, umidade))

            if umidade <= LIMIAR_LIGA and not alerta_solo_seco:
                alerta_solo_seco = True
                publicar_alerta(client, "solo_seco", "Umidade abaixo do limiar minimo")
            elif umidade > LIMIAR_DESLIGA and alerta_solo_seco:
                alerta_solo_seco = False

            if modo_auto:
                if not bomba_ligada and umidade <= LIMIAR_LIGA:
                    set_bomba(client, True, "auto")
                elif bomba_ligada and umidade >= LIMIAR_DESLIGA:
                    set_bomba(client, False, "auto")

            leitura = {
                "umidade": round(umidade),
                "raw": round(4095 - (umidade / 100) * 4095),
                "estado": "on" if bomba_ligada else "off",
                "modo": "auto" if modo_auto else "manual",
            }
            client.publish(T_UMIDADE, json.dumps(leitura))
            print(f"[TELEMETRIA] {leitura}")

        time.sleep(0.2)

    print("\nEncerrando simulador...")
    client.publish(T_STATUS, json.dumps({"online": False}))
    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
