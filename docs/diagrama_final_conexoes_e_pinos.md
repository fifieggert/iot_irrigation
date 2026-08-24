# Esquema de Conexões

**Projeto:** Irrigação de Vaso IoT
**Disciplina:** Internet das Coisas — Católica SC
**Professor:** Edson Vaz Lopes
**Grupo:** 2 — Irrigação de vaso
**Placa:** ESP32 DevKit v1 (30 pinos)

---

## Componentes

| Qtd | Componente | Especificação | Função |
|-----|------------|---------------|--------|
| 1 | ESP32 DevKit v1 | 30 pinos, USB micro-B | Microcontrolador e Wi-Fi |
| 1 | Sensor de umidade do solo | Saída analógica, 3,3 V | Leitura da umidade |
| 1 | LED | 5 mm | Indica o acionamento nos testes |
| 1 | Resistor | 220 Ω | Limita a corrente do LED |
| 1 | Módulo relé | 1 canal, bobina 5 V | Aciona a bomba |
| 1 | Bomba d'água | 12 V DC | Irrigação |
| 1 | Fonte externa | 12 V DC, ≥ 2 A | Alimenta a bomba |
| 1 | Diodo | 1N4007 | Protege o relé do pico da bomba |
| 1 | Protoboard | 400 ou 830 furos | Montagem |
| — | Jumpers | macho-macho e macho-fêmea | Ligações |
| 1 | Cabo USB | micro-B | Gravação e alimentação do ESP32 |

Nos testes iniciais e no simulador, o sensor pode ser substituído por um
potenciômetro de 10 kΩ, que gera a mesma faixa de tensão analógica.

---

## Conexões — controle (3,3 V e 5 V)

| # | Cor do fio | De | Para |
|---|-----------|----|----- |
| 1 | Vermelho | ESP32 `3V3` | Sensor `VCC` |
| 2 | Preto | ESP32 `GND` | Sensor `GND` |
| 3 | Verde | ESP32 `GPIO34` | Sensor `AOUT` (sinal) |
| 4 | Azul | ESP32 `GPIO23` | Resistor 220 Ω, terminal 1 |
| 5 | Azul | Resistor 220 Ω, terminal 2 | LED, anodo (perna longa) |
| 6 | Preto | LED, catodo (perna curta) | ESP32 `GND` |
| 7 | Verde | ESP32 `GPIO23` | Módulo relé, `IN` |
| 8 | Vermelho | ESP32 `VIN` (5 V) | Módulo relé, `VCC` |
| 9 | Preto | ESP32 `GND` | Módulo relé, `GND` |

O LED e o relé ficam no mesmo `GPIO23`: o LED serve como indicação visual do
comando, e o relé faz o acionamento real da bomba.

## Conexões — bomba (12 V)

| # | De | Para |
|---|----|----- |
| 10 | Fonte 12 V (+) | Relé, `COM` |
| 11 | Relé, `NO` | Bomba (+) |
| 12 | Bomba (−) | Fonte 12 V (−) |
| 13 | Fonte 12 V (−) | ESP32 `GND` |
| 14 | Diodo 1N4007, catodo (faixa) | Bomba (+) |
| 15 | Diodo 1N4007, anodo | Bomba (−) |

A bomba **não** é ligada direto no GPIO nem alimentada pelo ESP32. A corrente vem
da fonte de 12 V, e o ESP32 apenas fecha o contato do relé.

---

## Pinos utilizados

| Pino | Direção | Ligado a | Observação |
|------|---------|----------|------------|
| `3V3` | Alimentação | Sensor | Nunca alimentar o sensor em 5 V |
| `GND` | Referência | Sensor, LED, relé e fonte 12 V | Terra comum de todo o circuito |
| `GPIO34` | Entrada analógica | Sensor | ADC1; somente entrada |
| `GPIO23` | Saída digital | LED e `IN` do relé | Comando de acionamento |
| `VIN` | Alimentação | Relé `VCC` | Fornece 5 V com o USB conectado |
| `GPIO2` | Saída digital | LED onboard | Já embutido na placa; status Wi-Fi |

**Por que `GPIO34`:** o ADC2 do ESP32 para de funcionar quando o Wi-Fi está
ativo. Como o projeto usa Wi-Fi o tempo todo, o sensor precisa estar em um pino
do ADC1 (`GPIO32` a `GPIO39`).

**Por que `GPIO23`:** é uma saída digital comum, que não interfere no boot da
placa. Evitar como saída: `GPIO0`, `GPIO2`, `GPIO12`, `GPIO15` e `GPIO6` a
`GPIO11`.

---

## Parâmetros do firmware

Definidos em `firmware/irrigacao.ino`:

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `PINO_SENSOR` | `34` | Entrada do sensor |
| `PINO_BOMBA` | `23` | Saída de acionamento |
| `TOPICO_BASE` | `irrigacao/g2fifi` | Prefixo MQTT do grupo |
| `LIMIAR_LIGA` | `30` | Abaixo disso, o modo automático liga |
| `LIMIAR_DESLIGA` | `60` | Acima disso, o modo automático desliga |
| `INTERVALO_LEITURA` | `5000 ms` | Período da telemetria |
| `TEMPO_MAX_BOMBA` | `30000 ms` | Trava de segurança por acionamento |

O `TOPICO_BASE` precisa ser idêntico ao usado em `dashboard/index.html`, senão o
painel não recebe nada.

A diferença entre `LIMIAR_LIGA` e `LIMIAR_DESLIGA` é proposital: sem essa faixa
morta, a bomba ligaria e desligaria em ciclos rápidos toda vez que a umidade
oscilasse em torno de um valor único.

---

## Montagem

1. Montar as conexões de controle com o USB desconectado e a fonte 12 V fora da
   tomada.
2. Conferir a polaridade do LED: perna longa no lado do resistor.
3. Conectar o USB, gravar o firmware e abrir o monitor serial a 115200 baud.
4. Testar com a bomba ainda desconectada: o LED acende e o relé clica a cada
   comando.
5. Montar as conexões de 12 V, conferindo a polaridade do diodo.
6. Unir o negativo da fonte ao `GND` do ESP32.
7. Energizar a fonte e testar um ciclo curto com a bomba fora da água.
8. Submergir a bomba e testar pelo painel `dashboard/index.html`.

---

## Cuidados

- Alimentar o sensor apenas em `3V3`. Em 5 V, a tensão excede o limite do ADC e
  pode danificar o `GPIO34`.
- `GPIO34` é somente entrada: não configurar como saída.
- Nunca ligar o LED sem o resistor de 220 Ω em série.
- O `GND` da fonte de 12 V precisa estar unido ao `GND` do ESP32, senão o relé
  não chaveia de forma confiável.
- Usar o contato `NO` do relé, não o `NC`: assim a bomba fica desligada quando a
  placa está sem energia.
- A maioria dos módulos relé liga em nível baixo. Se a bomba ligar sozinha ao
  ligar a placa, inverter `HIGH` e `LOW` no `setBomba()` do firmware.
- A bomba não pode funcionar a seco: conferir se há água no reservatório.
- Manter água e o vaso afastados da protoboard, da placa e do cabo USB.
- Desligar a fonte de 12 V da tomada antes de mexer no circuito.
