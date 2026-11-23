# Contrato MQTT v1

Contrato de mensagens entre o firmware (ESP32), o backend (FastAPI) e os painéis.
Qualquer mudança de tópico ou de campo precisa ser feita **nos três lados ao mesmo tempo**:

| Lado | Onde o contrato está |
| :--- | :--- |
| Firmware | `firmware/irrigacao/irrigacao.ino` (`TOPICO_BASE` e `TOPICO_*`) |
| Backend | `back/app/config.py` (`MQTT_TOPIC_BASE` e propriedades `TOPICO_*`) |
| Simulador | `back/simulador_esp32.py` |
| Painel MQTT (legado) | `dashboard/index.html` |

- **Broker:** `broker.hivemq.com`, porta `1883` (TCP) ou `8883` (TLS); painel web via WebSocket `8000` (ws) / `8884` (wss).
- **Prefixo:** `g2fifi/irrigation/v1`
- **QoS:** 0 em todos os tópicos. Nenhuma mensagem é *retained*.
- **Formato:** JSON UTF-8, exceto `command/pump`, que é texto puro.

## Tópicos

| Tópico | Direção | Frequência |
| :--- | :--- | :--- |
| `g2fifi/irrigation/v1/telemetry/soil` | ESP32 → Broker | a cada 5 s |
| `g2fifi/irrigation/v1/telemetry/sunlight` | ESP32 → Broker | a cada 15 s |
| `g2fifi/irrigation/v1/status/pump` | ESP32 → Broker | em cada mudança de estado + LWT |
| `g2fifi/irrigation/v1/alert` | ESP32 → Broker | na transição do evento |
| `g2fifi/irrigation/v1/command/pump` | Backend/Painel → ESP32 | sob demanda |

### `telemetry/soil`

```json
{ "umidade": 42, "raw": 2375, "estado": "off", "modo": "auto" }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `umidade` | int 0–100 | Umidade do solo em % (calibrada) |
| `raw` | int 0–4095 | Leitura bruta do ADC (GPIO34) |
| `estado` | `"on"` \| `"off"` | Estado da bomba |
| `modo` | `"auto"` \| `"manual"` | Modo de operação |

### `telemetry/sunlight`

```json
{ "luminosidade": 65, "raw": 1433 }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `luminosidade` | int 0–100 | Luminosidade em % (0 = escuro, 100 = luz plena) |
| `raw` | int 0–4095 | Leitura bruta do ADC (GPIO35) |

O alerta de "dias sem sol" **não** é gerado no ESP32: o backend calcula a média
diária e compara com `limiar_luminosidade` e `dias_sem_sol_alerta` (`/api/v1/config`).

### `status/pump`

```json
{ "bomba": "on", "modo": "manual", "origem": "manual", "bloqueado": false, "online": true }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `bomba` | `"on"` \| `"off"` | Estado da bomba |
| `modo` | `"auto"` \| `"manual"` | Modo de operação |
| `origem` | string | O que causou a publicação: `boot`, `auto`, `manual`, `seguranca`, `sensor`, `timeout`, `recusado` |
| `bloqueado` | bool | `true` durante o bloqueio de 60 s após a trava de segurança |
| `online` | bool | `true` nas publicações normais |

**LWT (Last Will):** se o ESP32 cair sem desconectar, o broker publica `{"online": false}` neste tópico.

### `alert`

```json
{ "tipo": "solo_seco", "mensagem": "Umidade abaixo do limiar minimo", "umidade": 28 }
```

| `tipo` | Quando |
| :--- | :--- |
| `solo_seco` | Umidade cai para ≤ 30% (só na transição) |
| `seguranca` | Bomba excedeu 30 s ligada **ou** comando `on` recusado durante o bloqueio |
| `sensor` | Sensor de umidade com leitura inválida (bomba forçada para desligada) **ou** `on` recusado por isso |
| `comando` | Comando desconhecido recebido |

O backend grava cada alerta em `system_logs` (tipo `ALERT`, descrição `[tipo] mensagem`) e envia e-mail se o SMTP estiver configurado.

### `command/pump`

Texto puro, sem JSON: `on`, `off` ou `auto` (sem diferenciar maiúsculas de minúsculas).

| Comando | Efeito |
| :--- | :--- |
| `on` | Modo manual + liga a bomba. **Recusado** durante o bloqueio de segurança ou com o sensor de umidade inválido |
| `off` | Modo manual + desliga a bomba |
| `auto` | Volta ao modo automático (histerese 30% / 60%) |

Pela API, o comando é enviado com `POST /api/v1/command/pump` (exige JWT).

## Regras locais do firmware

Valem mesmo sem Wi-Fi ou broker:

1. Relé desligado antes de qualquer outra coisa no boot.
2. Modo automático com histerese: liga com umidade ≤ 30%, desliga com umidade ≥ 60%.
3. Trava de segurança: bomba ligada por 30 s seguidos → desliga e bloqueia por 60 s.
4. Sensor de umidade inválido (ADC < 10 por 6 leituras seguidas) → bomba desligada até a leitura normalizar.
5. Modo manual volta sozinho para automático após 10 min.
6. Reconexão Wi-Fi/MQTT não bloqueante, com backoff exponencial de 1 s a 60 s.
