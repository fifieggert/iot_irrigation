# Contrato MQTT v1

Contrato de mensagens entre o firmware (dois ESP32), o backend (FastAPI) e os painéis.
Qualquer mudança de tópico ou de campo precisa ser feita **em todos os lados ao mesmo tempo**:

| Lado | Onde o contrato está |
| :--- | :--- |
| Firmware — ESP32 #1 (nó sensor) | `firmware/sensor_node/sensor_node.ino` (`TOPICO_BASE` e `TOPICO_*`) |
| Firmware — ESP32 #2 (nó controlador) | `firmware/controller_node/controller_node.ino` (`TOPICO_BASE` e `TOPICO_*`) |
| Backend | `back/app/config.py` (`MQTT_TOPIC_BASE` e propriedades `TOPICO_*`) |
| Simulador | `back/simulador_esp32.py` |
| Painel MQTT (legado) | `dashboard/index.html` |

- **Broker:** `broker.hivemq.com`, porta `1883` (TCP) ou `8883` (TLS); painel web via WebSocket `8000` (ws) / `8884` (wss).
- **Prefixo:** `g2fifi/irrigation/v1`
- **QoS:** 0 em todos os tópicos. Nenhuma mensagem é *retained*.
- **Formato:** JSON UTF-8, exceto `command/pump`, que é texto puro.
- **Placas:** os dois ESP32 não se falam diretamente; toda a comunicação passa pelo broker.

## Tópicos

| Tópico | Publica | Assina | Frequência |
| :--- | :--- | :--- | :--- |
| `g2fifi/irrigation/v1/telemetry/soil` | ESP32 #1 (nó sensor) | ESP32 #2, Backend | a cada 5 s |
| `g2fifi/irrigation/v1/telemetry/sunlight` | ESP32 #1 (nó sensor) | Backend | a cada 15 s |
| `g2fifi/irrigation/v1/status/pump` | ESP32 #2 (nó controlador) | Backend, Painel | em cada mudança de estado + LWT |
| `g2fifi/irrigation/v1/alert` | ESP32 #2 (nó controlador) | Backend, Painel | na transição do evento |
| `g2fifi/irrigation/v1/command/pump` | Backend/Painel | ESP32 #2 (nó controlador) | sob demanda |

### `telemetry/soil`

Publicado pelo nó sensor. É a entrada das regras do nó controlador.

```json
{ "umidade": 42, "raw": 2375 }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `umidade` | int 0–100 | Umidade do solo em % (calibrada) |
| `raw` | int 0–4095 | Leitura bruta do ADC (GPIO34 do nó sensor) |

O estado da bomba e o modo de operação **não** vão neste tópico: ficam em `status/pump`.

### `telemetry/sunlight`

```json
{ "luminosidade": 65, "raw": 1433 }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `luminosidade` | int 0–100 | Luminosidade em % (0 = escuro, 100 = luz plena) |
| `raw` | int 0–4095 | Leitura bruta do ADC (GPIO35 do nó sensor) |

O alerta de "dias sem sol" **não** é gerado nos ESP32: o backend calcula a média
diária e compara com `limiar_luminosidade` e `dias_sem_sol_alerta` (`/api/v1/config`).

### `status/pump`

```json
{ "bomba": "on", "modo": "manual", "origem": "manual", "bloqueado": false, "online": true }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `bomba` | `"on"` \| `"off"` | Estado da bomba |
| `modo` | `"auto"` \| `"manual"` | Modo de operação |
| `origem` | string | O que causou a publicação: `boot`, `auto`, `manual`, `seguranca`, `sensor`, `comunicacao`, `timeout`, `recusado` |
| `bloqueado` | bool | `true` durante o bloqueio de 60 s após a trava de segurança |
| `online` | bool | `true` nas publicações normais |

**LWT (Last Will):** se o nó controlador (ESP32 #2) cair sem desconectar, o broker publica `{"online": false}` neste tópico. O nó sensor não tem LWT.

### `alert`

```json
{ "tipo": "solo_seco", "mensagem": "Umidade abaixo do limiar minimo", "umidade": 28 }
```

| `tipo` | Quando |
| :--- | :--- |
| `solo_seco` | Umidade cai para ≤ 30% (só na transição) |
| `seguranca` | Bomba excedeu 30 s ligada **ou** comando `on` recusado durante o bloqueio |
| `sensor` | Sensor de umidade com leitura inválida (bomba forçada para desligada) **ou** `on` recusado por isso |
| `comunicacao` | Telemetria do nó sensor parou de chegar por 30 s (bomba mantida desligada) **ou** `on` recusado por isso |
| `comando` | Comando desconhecido recebido |

O backend grava cada alerta em `system_logs` (tipo `ALERT`, descrição `[tipo] mensagem`) e envia e-mail se o SMTP estiver configurado.

### `command/pump`

Texto puro, sem JSON: `on`, `off` ou `auto` (sem diferenciar maiúsculas de minúsculas).

| Comando | Efeito |
| :--- | :--- |
| `on` | Modo manual + liga a bomba. **Recusado** durante o bloqueio de segurança, com o sensor de umidade inválido ou sem telemetria do nó sensor |
| `off` | Modo manual + desliga a bomba |
| `auto` | Volta ao modo automático (histerese 30% / 60%) |

Pela API, o comando é enviado com `POST /api/v1/command/pump` (exige JWT).

## Regras locais do firmware

Aplicadas pelo nó controlador (ESP32 #2, `controller_node.ino`). As travas de tempo
valem mesmo sem Wi-Fi ou broker. Sem broker, porém, a umidade não chega, e por isso
entra em ação a regra 6.

1. Relé desligado antes de qualquer outra coisa no boot.
2. Modo automático com histerese: liga com umidade ≤ 30%, desliga com umidade ≥ 60%. Antes da primeira telemetria recebida, não decide nada.
3. Trava de segurança: bomba ligada por 30 s seguidos → desliga e bloqueia por 60 s.
4. Sensor de umidade inválido (`raw` < 10 em 6 telemetrias seguidas) → bomba desligada até a leitura normalizar.
5. Modo manual volta sozinho para automático após 10 min.
6. Estado seguro por falta de telemetria (`TIMEOUT_TELEMETRIA` = 30 s, 6 × o intervalo de 5 s): se `telemetry/soil` do nó sensor parar de chegar, a bomba é desligada, o controle automático é suspenso, o comando `on` é recusado e é publicado o alerta `comunicacao`. Quando a telemetria volta, publica `status/pump` com `origem: "comunicacao"`.
7. Reconexão Wi-Fi/MQTT não bloqueante, com backoff exponencial de 1 s a 60 s (nas duas placas).
