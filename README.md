# PROJETO DE IRRIGAÇÃO - IoT

- **Integrantes**: Ana Julia Castelo Branco, Graziela Torres, Henrique Xavier Klappoth, Marina Rosa Oliveira, Rodrigo Xavier Klappoth e Sophia Eggert Freire da Rocha
- **Disciplina**: Internet das Coisas
- **Professor**: Edson Vaz Lopes
- **Avaliação**: N2/N3 - Proposta de Upgrade e Projeto Completo

## Família Temática
- Grupo 2 - Irrigação de vaso
- Evolução para N2/N3: Irrigação remota/automática + monitoramento de umidade e sensor de calor/luminosidade.

## Problema
Plantas em vasos são frequentemente prejudicadas por irrigação incorreta, tanto por excesso quanto por falta de água. Sem monitoramento, o cuidador depende de rotinas manuais que podem falhar por esquecimento ou outras eventualidades. O objetivo do projeto é permitir a irrigação de forma remota, monitorando a umidade do solo para determinar a necessidade (ou não) de irrigação. Além disso, o sistema monitora a incidência de calor/luz solar na planta, emitindo um alerta caso passe muitos dias sem receber luz adequada.

## Usuário/Contexto de Uso
Pessoas que cuidam de plantas e desejam monitorar remotamente a umidade do solo e a incidência de luz solar, controlando a irrigação via painel web, sem precisar estar presentes.

## Estado Atual (Herdado da N1)
- Leitura de umidade do solo em tempo real.
- Publicação de dados via MQTT com telemetria.
- Acionamento da bomba de irrigação por comando remoto.
- Reconexão automática em caso de falha de rede/broker.

## Direção do Upgrade (N3)
- Adição de sensor de calor/luminosidade para alerta de luz solar.
- Backend estruturado (Python/FastAPI) integrado com banco de dados PostgreSQL hospedado no Supabase.
- Sistema de login e segurança nos endpoints (com autenticação).
- Orquestração completa utilizando Docker Compose.
- Regras locais de segurança e tratamento de falhas testadas.

## Arquitetura-Alvo
- **Sensor de Umidade / Calor** → ESP32 → Firmware → Wi-Fi → MQTT Broker (HiveMQ) → Backend (API + Regras) → Banco de Dados (PostgreSQL / Supabase) → Painel Web (Dashboard).

## Tópicos MQTT (Contrato v1)
Prefixo: `g2fifi/irrigation/v1`. Contrato completo em [`CONTRATOS.md`](CONTRATOS.md).

| Tópico | Direção | Conteúdo |
| :--- | :--- | :--- |
| `g2fifi/irrigation/v1/telemetry/soil` | ESP32 → Broker | JSON com umidade do solo, estado e modo |
| `g2fifi/irrigation/v1/telemetry/sunlight` | ESP32 → Broker | JSON com luminosidade (proposta N3) |
| `g2fifi/irrigation/v1/command/pump` | Backend → ESP32 | Comandos para a bomba (`on`, `off`, `auto`) |
| `g2fifi/irrigation/v1/status/pump` | ESP32 → Broker | Estado da bomba, modo e origem; LWT `online:false` |
| `g2fifi/irrigation/v1/alert` | ESP32 → Broker | Alertas (solo seco, segurança, sensor) |

## Diagramas
- [Arquitetura](docs/diagramas/arquitetura.png)
- [Fluxograma do firmware](docs/diagramas/firmware_fluxograma.png)
- [Esquema elétrico](docs/diagramas/esquema_eletrico.png) e [mapa de pinos](docs/hardware/pinout_map.md)

## Riscos Técnicos e Mitigação
- **Risco 1**: Corrosão rápida do sensor resistivo pelo contato constante com o solo.
  - *Mitigação*: Utilização de sensor capacitivo e leitura periódica espaçada.
- **Risco 2**: Desconexão constante de rede Wi-Fi ou queda do Broker.
  - *Mitigação*: Reconexão não-bloqueante com backoff exponencial (1 s a 60 s) no ESP32, mantendo a regra local da bomba ativa mesmo offline.
- **Risco 3**: Bomba ligada por tempo excessivo ou funcionando a seco.
  - *Mitigação*: Trava no firmware: desliga após 30 s de acionamento contínuo e bloqueia novo acionamento por 60 s.
- **Risco 4**: Broker HiveMQ público e aberto: outro grupo pode publicar nos mesmos tópicos.
  - *Mitigação*: Prefixo exclusivo do grupo (`g2fifi`) nos tópicos e, na N3, TLS e autenticação no broker.

## Como Executar?
### 1. Firmware (ESP32)
* **Pré-requisitos**:
  * Arduino IDE 2.x com suporte a ESP32.
  * Bibliotecas `PubSubClient` e `ArduinoJson`.
* **Passos**:
  * Abrir o código na IDE do Arduino.
  * Copiar `firmware/irrigacao/secrets.h.example` para `secrets.h` e preencher `WIFI_SSID` e `WIFI_PASSWORD` (o arquivo não vai para o Git).
  * Selecionar a placa `ESP32 Dev Module` e fazer o upload.

### 2. Orquestração e Backend (Docker Compose)
* **Pré-requisitos**: Docker e Docker Compose instalados.
* **Passos**:
  * Copiar `back/.env.example` para `back/.env` e preencher (Supabase, broker, SMTP opcional).
  * Na raiz do projeto, executar o comando:
    ```bash
    docker compose up --build
    ```
  * API em `http://localhost:8000/api/health`; painel em `http://localhost:5500`.

## Estrutura do Repositório
```
irrigacao-iot/
├── back/               # API Backend e regras de negócio
├── firmware/           # Código principal do ESP32 e bibliotecas
├── front/              # Painel web de monitoramento e controle
├── dashboard/          # Painel MQTT direto (legado da N1)
├── docs/               # diagramas/ (arquitetura, fluxograma, esquema), hardware/pinout_map.md
├── CONTRATOS.md        # Contrato MQTT v1
├── docker-compose.yml  # Orquestração de containers
└── README.md
```

## Divisão de Responsabilidades
| Integrante | Responsabilidade principal |
| :--- | :--- |
| Ana Julia Castelo Branco | A definir |
| Graziela Torres | Front-end: painel web em TypeScript |
| Henrique Xavier Klappoth | Simulação no Wokwi, firmware inicial e painel web MQTT |
| Marina Rosa Oliveira | Backend FastAPI, modelagem do banco (MER) e documentação |
| Rodrigo Xavier Klappoth | Correções do backend e documentação de hardware |
| Sophia Eggert | Integração backend e firmware, ambiente e organização do README |

## Cronograma
| Data | Marco |
| :--- | :--- |
| 27/10 | CP12 completo + contrato MQTT v1 congelado |
| 03/11 | N2: documentação do projeto e prova individual |
| 10/11 a 24/11 | Implementação: sensor de luz, login, logs, configurações, TLS, testes e CI |
| 01/12 | N3: defesa do produto funcionando |

## Segurança
* Operação em baixa tensão (3.3V / 5V do ESP32 e fontes dedicadas).
* Isolamento de cargas indutivas através de módulos de relé com optoacoplador.
* Credenciais sensíveis fora do Git: `back/.env` e `firmware/irrigacao/secrets.h` (modelos `.env.example` e `secrets.h.example`).
* Firmware: relé desligado antes de tudo no boot, trava de 30 s com bloqueio de 60 s que recusa o comando `on`, estado seguro (bomba desligada) com sensor inválido e timeout de 10 min no modo manual.
* Reconexão Wi-Fi/MQTT com backoff exponencial (1 s a 60 s).
* Pendente (N3): autenticação nos endpoints da API e firmware do sensor de luz (GPIO35).

## Gestão de Atividades
* [Trello do Projeto](https://trello.com/b/UaGTBRzA/iotirrigation)