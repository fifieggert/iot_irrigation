# Diagrama de Conexões: Irrigação de Vaso IoT

**Internet das Coisas · Católica SC · Prof. Edson Vaz Lopes**
**Placa:** ESP32 DevKit v1 (30 pinos)

---

## Legenda de fios

| Cor | Significado |
|---|---|
| Vermelho | VCC / 3V3 |
| Preto | GND |
| Azul (tracejado) | Sinal analógico (sensor) |
| Verde | Sinal digital (bomba/LED) |
| Roxo | Resistor 220Ω |
| Laranja | LED onboard Wi-Fi |

---

## Componentes

1. **Sensor de Umidade do Solo** (analógico): ponta fica no solo
2. **Resistor 220Ω**
3. **Bomba de irrigação 12V Arduino MJ**
4. **LED onboard Wi-Fi** (já embutido na placa, pino GPIO2)

## Fluxo de dados

```
Solo > Sensor > GPIO34 > ESP32 > Wi-Fi > MQTT > Painel Web > Comando > GPIO26 > LED
```

---

## Atenção

- Nunca conectar o LED sem o resistor (queima o GPIO).
- Usar somente 3,3V para alimentar o sensor (não 5V).
- GPIO34 é somente entrada: não usar como saída.
- Manter água afastada da protoboard e do ESP32.
- O LED onboard (GPIO2) já está na placa: não precisa de componente externo.
