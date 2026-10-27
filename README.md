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
| Tópico | Direção | Conteúdo |
| :--- | :--- | :--- |
| `irrigation/v1/telemetry/soil` | ESP32 → Broker | JSON com umidade do solo, estado e modo |
| `irrigation/v1/telemetry/sunlight` | ESP32 → Broker | JSON com dados de incidência de calor/luz |
| `irrigation/v1/command/pump` | Backend → ESP32 | Comandos para a bomba (`on`, `off`) |
| `irrigation/v1/status/pump` | ESP32 → Broker | Confirmação de estado da bomba |

## Riscos Técnicos e Mitigação
- **Risco 1**: Corrosão rápida do sensor resistivo pelo contato constante com o solo.
  - *Mitigação*: Utilização de sensor capacitivo e leitura periódica espaçada.
- **Risco 2**: Desconexão constante de rede Wi-Fi ou queda do Broker.
  - *Mitigação*: Implementação de lógica de reconexão não-bloqueante no ESP32 mantendo as regras locais ativas.

## Como Executar?
### 1. Firmware (ESP32)
* **Pré-requisitos**:
  * Arduino IDE 2.x com suporte a ESP32.
  * Bibliotecas `PubSubClient` e `ArduinoJson`.
* **Passos**:
  * Abrir o código na IDE do Arduino.
  * Configurar as credenciais de rede (`WIFI_SSID` e `WIFI_PASSWORD`).
  * Selecionar a placa `ESP32 Dev Module` e fazer o upload.

### 2. Orquestração e Backend (Docker Compose)
* **Pré-requisitos**: Docker e Docker Compose instalados.
* **Passos**:
  * Na raiz do projeto, executar o comando:
    ```bash
    docker-compose up --build
    ```

## Estrutura do Repositório
irrigacao-iot/
├── back/               # API Backend e regras de negócio
├── firmware/           # Código principal do ESP32 e bibliotecas
├── front/              # Painel web de monitoramento e controle
├── docs/               # Documentação, diagramas e esquemas elétricos
├── docker-compose.yml  # Orquestração de containers
└── README.md

## Segurança
* Operação em baixa tensão (3.3V / 5V do ESP32 e fontes dedicadas).
* Isolamento de cargas indutivas através de módulos de relé com optoacoplador.
* Credenciais sensíveis protegidas por variáveis de ambiente.

## Gestão de Atividades
* [Trello do Projeto](https://trello.com/b/UaGTBRzA/iotirrigation)
