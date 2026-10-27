# PROJETO DE IRRIGAÇÃO - IoT
- **Integrantes**: Ana Julia Castelo Branco, Graziela Torres, Henrique Xavier Klappoth, Marina Rosa Oliveira, Rodrigo Xavier Klappoth e Sophia Eggert Freire da Rocha
- **Disciplina**: Internet das Coisas
- **Professor**: Edson Vaz Lopes
- **Avaliação**: N2 - Entrega parcial do Projeto Completo

## Família Temática
- Grupo 2 - Irrigação de vaso
- Evolução para N2/N3: Irrigação remota/automática + monitoramento de umidade e recebimento de calor

## Problema
Plantas em vasos são frequentemente prejudicadas por irrigação incorreta, tanto por excesso quanto por falta de água. Sem monitoramento, o cuidador depende de rotinas manuais que podem falhar por esquecimento ou outras eventualidades. O objetivo do projeto é permitir a irrigação de forma remota, monitorando a umidade do solo para determinar a necessidade (ou não) de irrigação. Além disso, nosso sistema se propõe a monitorar a quantidade de calor que a planta recebe e identificar se ela tem recebido menos do que o necessário (se não receber calor por alguns dias, um alerta é emitido ao usuário para que a planta seja movido para um lugar ensolarado).

## Usuário/Contexto de Uso
Pessoas que cuidam de plantas e desejam monitorar remotamente a umidade do solo/incidência de luz solar na planta e controlar a irrigação via painel web, sem precisar estar presente.

## Objetivo da N1
Construir um projeto com ESP32 que:
- Leia a umidade do solo em tempo real
- Publique os dados via MQTT com telemetria
- Permita acionar a bomba de irrigação por comando remoto
- Reconecte automaticamente em caso de falha de rede ou broker

## Objetivo N2
Complementar projeto da N1, incluindo um ESP32 que:
- Leia a incidência de calor sobre a planta;
- Publique os dados de calor via MQTT com telemetria;
- Envie uma notificação ao usuário caso muitos dias se passem sem luz solar;

Além disso, deve ser implementado:
- Sistema de login na interface gráfica;
- Segurança nos endpoints do backend que fazem a comunicação com o Broker/ESP32.

## Arquitetura
```
Sensor de Umidade → ESP32 → Firmware → Wi-Fi → MQTT Broker (HiveMQ) 
↓ 
Painel Web (dashboard/) 
↓ 
Comando → Bomba de irrigação

Sensor de Calor  → ESP32 → Firmware → Wi-Fi → MQTT Broker (HiveMQ) 
↓ 
Painel Web (dashboard/)
```

## Tópicos MQTT
|Tópico|Direção|Conteúdo|
|---|---|---|
|irrigacao/umidade|ESP32 → WEB|JSON com umidade, estado e modo|
|irrigacao/status|ESP32 → WEB|Confirmação de estado da bomba|
|irrigacao/alerta|ESP32 → WEB|Alertas (solo seco, segurança, sensor)|
|irrigacao/bomba|ESP32 → WEB|Comandos: `on`, `off`|

## Primeiro risco técnico
- **Risco**: Sensor resistivo pode corroer rapidamente devido ao contato constante com solo úmido, comprometendo a leitura.

## Como executar?
### 1. Firmware (ESP32)
* **Pré-requisitos**:
  * Arduino IDE 2.x com suporte a ESP32
  * Bibliotecas `PubSubClient` e `ArduinoJson` (instalar via Gerenciar Bibliotecas)
* **Passos**:
  * Abrir `firmware\irrigacao.ino` na IDE do Arduino
  * Editar linhas:
    ```
    const char* WIFI_SSID = "wifi";
    const char* WIFI_PASSWORD = "senha";
    ```
  * Selecionar placa `ESP32 Dev Module`
  * Selecionar porta COM correta
  * Fazer upload do código (`Ctrl + U`)
  * Abrir *monitor serial* (115200 baud) para acompanhar logs

### 2. Painel Web
* Abrir arquivo `dashboard\index.html` diretamente no navegador
  * O painel conecta automaticamente ao broker público HiveMQ via WebSocket

### 3. Testar fluxo completo
* ESP32 ligado e conectado → Logs aparecem no monitor serial
* Abrir `dashboard\index.html` → Painel conecta ao MQTT
* Aguardar leituras chegarem (de 5 em 5 segundos)
* Testar botões (irrigar agora, parar)
* Verificar confirmações de estado no painel

## Broker MQTT
* Broker público utilizado: [broker.hivemq.com](broker.hivemq.com)
* Firmware porta: 1883 TCP
* Painel web: 8000 (WebSocket)

## Estrutura do Repositório
```
irrigacao-iot/
├── back /
│ └── server.js 
├── firmware/
│ ├── irrigacao.ino # Código principal do ESP32
│ └── libraries.txt # Bibliotecas necessárias
├── front/
│ └── index.html # Painel web de monitoramento e controle
├── docs/
│ └── esquema_conexoes.md # Diagrama de pinos e conexões
└── README.md
```

## Segurança
* Usar apenas baixa tensão (3,3V do ESP32)
* Nunca conectar à rede elétrica residencial
* Manter água distante da placa e do cabo USB

## Gestão de atividades
* [Trello](https://trello.com/b/UaGTBRzA/iotirrigation)
