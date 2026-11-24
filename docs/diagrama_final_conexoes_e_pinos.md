# Esquema de Conexões

**Projeto:** Irrigação de Vaso IoT
**Disciplina:** Internet das Coisas — Católica SC
**Professor:** Edson Vaz Lopes
**Grupo:** 2 — Irrigação de vaso
**Placas:** 2 × ESP32 DevKit v1 (30 pinos)

O sistema usa **duas placas ESP32**, sem nenhum fio de sinal entre elas: toda a
comunicação passa pelo broker MQTT (HiveMQ, prefixo `g2fifi/irrigation/v1`).

| Placa | Sketch | Função |
|-------|--------|--------|
| ESP32 #1 — nó sensor | `firmware/sensor_node/sensor_node.ino` | Lê umidade (GPIO34) e luz (GPIO35) e publica a telemetria. Não aciona nada. |
| ESP32 #2 — nó controlador | `firmware/controller_node/controller_node.ino` | Recebe a telemetria, aplica as regras locais e aciona o relé da bomba (GPIO23). Não tem sensores. |

---

## Componentes

| Qtd | Componente | Especificação | Placa | Função |
|-----|------------|---------------|-------|--------|
| 2 | ESP32 DevKit v1 | 30 pinos, USB micro-B | #1 e #2 | Microcontrolador e Wi-Fi |
| 1 | Sensor de umidade do solo | Capacitivo, saída analógica, 3,3 V | #1 | Leitura da umidade |
| 1 | Módulo sensor de luminosidade (LDR) | Saída analógica `AO`, 3,3 V | #1 | Leitura da luz solar |
| 1 | LED | 5 mm | #2 | Indica o acionamento nos testes |
| 1 | Resistor | 220 Ω | #2 | Limita a corrente do LED |
| 1 | Módulo relé | 1 canal, bobina 5 V | #2 | Aciona a bomba |
| 1 | Bomba d'água | 12 V DC | #2 | Irrigação |
| 1 | Fonte externa | 12 V DC, ≥ 2 A | #2 | Alimenta a bomba |
| 1 | Diodo | 1N4007 | #2 | Protege o relé do pico da bomba |
| 2 | Protoboard | 400 ou 830 furos | #1 e #2 | Montagem |
| — | Jumpers | macho-macho e macho-fêmea | — | Ligações |
| 2 | Cabo USB | micro-B | #1 e #2 | Gravação e alimentação de cada ESP32 |

Nos testes iniciais e no simulador, o sensor de umidade pode ser substituído por
um potenciômetro de 10 kΩ, que gera a mesma faixa de tensão analógica. No Wokwi,
o sensor de luz é o `wokwi-photoresistor-sensor` (diagrama em
`docs/rascunhowokwi.json`, ainda na versão de uma placa).

---

## ESP32 #1 — nó sensor

### Conexões (3,3 V)

| # | Cor do fio | De | Para |
|---|-----------|----|----- |
| 1 | Vermelho | ESP32 #1 `3V3` | Sensor de umidade `VCC` |
| 2 | Preto | ESP32 #1 `GND` | Sensor de umidade `GND` |
| 3 | Verde | ESP32 #1 `GPIO34` | Sensor de umidade `AOUT` (sinal) |
| 4 | Vermelho | ESP32 #1 `3V3` | Módulo LDR `VCC` |
| 5 | Preto | ESP32 #1 `GND` | Módulo LDR `GND` |
| 6 | Laranja | ESP32 #1 `GPIO35` | Módulo LDR `AO` (sinal analógico) |

O pino `DO` do módulo LDR (saída digital do comparador) não é usado: o firmware
lê o valor analógico para calcular a luminosidade de 0 a 100%.

### Pinos utilizados

| Pino | Direção | Ligado a | Observação |
|------|---------|----------|------------|
| `3V3` | Alimentação | Sensor de umidade e módulo LDR | Nunca alimentar os sensores em 5 V |
| `GND` | Referência | Sensor de umidade e módulo LDR | |
| `GPIO34` | Entrada analógica | Sensor de umidade (`AOUT`) | ADC1; somente entrada |
| `GPIO35` | Entrada analógica | Módulo LDR (`AO`) | ADC1; somente entrada |
| `GPIO2` | Saída digital | LED onboard | Já embutido na placa; pisca a cada publicação |

**Por que `GPIO34` e `GPIO35`:** o ADC2 do ESP32 para de funcionar quando o Wi-Fi
está ativo. Como o projeto usa Wi-Fi o tempo todo, os dois sensores precisam estar
em pinos do ADC1 (`GPIO32` a `GPIO39`).

---

## ESP32 #2 — nó controlador

### Conexões — controle (3,3 V e 5 V)

| # | Cor do fio | De | Para |
|---|-----------|----|----- |
| 1 | Verde | ESP32 #2 `GPIO23` | Módulo relé `IN` |
| 2 | Vermelho | ESP32 #2 `VIN` (5 V) | Módulo relé `VCC` |
| 3 | Preto | ESP32 #2 `GND` | Módulo relé `GND` |
| 4 | Azul | ESP32 #2 `GPIO23` | Resistor 220 Ω, terminal 1 (LED de teste, opcional) |
| 5 | Azul | Resistor 220 Ω, terminal 2 | LED, anodo (perna longa) |
| 6 | Preto | LED, catodo (perna curta) | ESP32 #2 `GND` |

O LED externo e o relé ficam no mesmo `GPIO23`: o LED serve como indicação visual
do comando, e o relé faz o acionamento real da bomba.

### Conexões — bomba (12 V)

| # | De | Para |
|---|----|----- |
| 7 | Fonte 12 V (+) | Relé `COM` |
| 8 | Relé `NO` | Bomba (+) |
| 9 | Bomba (−) | Fonte 12 V (−) |
| 10 | Fonte 12 V (−) | ESP32 #2 `GND` (GND comum) |
| 11 | Diodo 1N4007, catodo (faixa) | Bomba (+) |
| 12 | Diodo 1N4007, anodo | Bomba (−) |

A bomba **não** é ligada direto no GPIO nem alimentada pelo ESP32. A corrente vem
da fonte de 12 V, e o ESP32 #2 apenas fecha o contato do relé.

### Pinos utilizados

| Pino | Direção | Ligado a | Observação |
|------|---------|----------|------------|
| `GPIO23` | Saída digital | `IN` do relé e LED de teste | Comando de acionamento |
| `VIN` | Alimentação | Relé `VCC` | Fornece 5 V com o USB conectado |
| `GND` | Referência | Relé, LED e fonte 12 V (−) | Terra comum do circuito da bomba |
| `GPIO2` | Saída digital | LED onboard | Já embutido na placa; segue o estado da bomba |

**Por que `GPIO23`:** é uma saída digital comum, que não interfere no boot da
placa. Evitar como saída: `GPIO0`, `GPIO2`, `GPIO12`, `GPIO15` e `GPIO6` a
`GPIO11`.

---

## Parâmetros do firmware

### `firmware/sensor_node/sensor_node.ino` (ESP32 #1)

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `TOPICO_BASE` | `g2fifi/irrigation/v1` | Prefixo MQTT do grupo (contrato v1) |
| `PINO_SENSOR_SOLO` | `34` | Entrada do sensor de umidade |
| `PINO_SENSOR_LUZ` | `35` | Entrada do sensor de luminosidade |
| `PINO_LED` | `2` | LED onboard, pisca a cada publicação |
| `ADC_SOLO_SECO` / `ADC_SOLO_MOLHADO` | `4095` / `2100` | Calibração do sensor de umidade |
| `ADC_LUZ_ESCURO` / `ADC_LUZ_CLARO` | `4095` / `0` | Calibração do LDR (inverter se o módulo for o contrário) |
| `INTERVALO_LEITURA` | `5000 ms` | Período da telemetria de solo (`telemetry/soil`) |
| `INTERVALO_LUZ` | `15000 ms` | Período da telemetria de luz (`telemetry/sunlight`) |
| `BACKOFF_MIN` / `BACKOFF_MAX` | `1000 ms` / `60000 ms` | Backoff exponencial de reconexão |
| `TENTATIVA_WIFI` | `8000 ms` | Tempo mínimo de cada tentativa de Wi-Fi |

### `firmware/controller_node/controller_node.ino` (ESP32 #2)

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `TOPICO_BASE` | `g2fifi/irrigation/v1` | Prefixo MQTT do grupo (contrato v1) |
| `PINO_BOMBA` | `23` | Saída para o `IN` do relé |
| `PINO_LED` | `2` | LED onboard, segue o estado da bomba |
| `RELE_ATIVO_BAIXO` | `true` | Relé aciona em nível baixo |
| `LIMIAR_LIGA` | `30` | Umidade ≤ 30%: o modo automático liga |
| `LIMIAR_DESLIGA` | `60` | Umidade ≥ 60%: o modo automático desliga |
| `TEMPO_MAX_BOMBA` | `30000 ms` | Trava de segurança por acionamento |
| `BLOQUEIO_SEGURANCA` | `60000 ms` | Bloqueio após a trava (recusa `on`) |
| `TIMEOUT_MANUAL` | `600000 ms` | Modo manual volta para automático |
| `TIMEOUT_TELEMETRIA` | `30000 ms` | Sem telemetria do nó sensor: estado seguro (bomba desligada) |
| `ADC_SUSPEITO` | `10` | `raw` abaixo disso conta como leitura suspeita |
| `LEITURAS_PARA_FALHA` | `6` | Leituras suspeitas seguidas para declarar o sensor inválido |
| `BACKOFF_MIN` / `BACKOFF_MAX` | `1000 ms` / `60000 ms` | Backoff exponencial de reconexão |
| `TENTATIVA_WIFI` | `8000 ms` | Tempo mínimo de cada tentativa de Wi-Fi |

O `TOPICO_BASE` precisa ser idêntico nos dois sketches, no `MQTT_TOPIC_BASE` do
backend e em `dashboard/index.html`, senão ninguém recebe nada. Contrato completo
em `CONTRATOS.md`.

A diferença entre `LIMIAR_LIGA` e `LIMIAR_DESLIGA` é proposital: sem essa faixa
morta, a bomba ligaria e desligaria em ciclos rápidos toda vez que a umidade
oscilasse em torno de um valor único.

---

## Montagem

1. Montar as conexões das duas placas com os USB desconectados e a fonte 12 V
   fora da tomada.
2. Gravar `sensor_node.ino` no ESP32 #1 e `controller_node.ino` no ESP32 #2
   (cada um com seu `secrets.h`) e abrir o monitor serial a 115200 baud.
3. Conferir no serial do ESP32 #1 as mensagens `[SOLO]` e `[LUZ]`, e no serial do
   ESP32 #2 as mensagens `[SOLO] recebido do no sensor`.
4. Conferir a polaridade do LED de teste: perna longa no lado do resistor.
5. Testar com a bomba ainda desconectada: o LED acende e o relé clica a cada
   comando.
6. Desligar o ESP32 #1 e conferir que, após 30 s, o ESP32 #2 publica o alerta
   `comunicacao` e mantém a bomba desligada.
7. Montar as conexões de 12 V, conferindo a polaridade do diodo.
8. Unir o negativo da fonte ao `GND` do ESP32 #2.
9. Energizar a fonte e testar um ciclo curto com a bomba fora da água.
10. Submergir a bomba e testar pelo painel.

---

## Cuidados

- Alimentar os sensores do ESP32 #1 apenas em `3V3`. Em 5 V, a tensão excede o
  limite do ADC e pode danificar o `GPIO34`/`GPIO35`.
- `GPIO34` e `GPIO35` são somente entrada: não configurar como saída.
- O LDR precisa ficar exposto à mesma luz que a planta recebe, fora da sombra das
  folhas e protegido da água da irrigação.
- Nunca ligar o LED sem o resistor de 220 Ω em série.
- O `GND` da fonte de 12 V precisa estar unido ao `GND` do ESP32 #2, senão o relé
  não chaveia de forma confiável.
- Usar o contato `NO` do relé, não o `NC`: assim a bomba fica desligada quando a
  placa está sem energia.
- A maioria dos módulos relé liga em nível baixo. Se a bomba ligar sozinha ao
  ligar a placa, trocar `RELE_ATIVO_BAIXO` para `false` em `controller_node.ino`.
- As duas placas precisam alcançar o broker: se o ESP32 #1 perder o Wi-Fi, o
  ESP32 #2 desliga a bomba por segurança.
- A bomba não pode funcionar a seco: conferir se há água no reservatório.
- Manter água e o vaso afastados das protoboards, das placas e dos cabos USB.
- Desligar a fonte de 12 V da tomada antes de mexer no circuito.
