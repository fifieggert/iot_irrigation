Com base nos requisitos da **N3** e no contrato formalizado no **CP12** do projeto **IOT_Irrigation**, o backend em FastAPI precisa evoluir de uma API simples de telemetria de solo herdada da N1 para um serviço robusto com suporte a múltiplos sensores (luminosidade/sol), autenticação JWT, regras de negócio de automação/alerta por e-mail, gerenciamento de limites operacionais e Docker Compose.

Abaixo está o conteúdo estruturado para você salvar como `PLAN.md` na raiz do seu projeto ou fornecer diretamente para o agente/IA da sua IDE.

---

# PLAN.md: Upgrade do Backend IoT Irrigation (N3)

## 1. Visão Geral e Contexto

O objetivo deste plano é guiar a refatoração e implementação das funcionalidades do **Backend (FastAPI + SQLAlchemy + PostgreSQL/Supabase)** para atender integralmente aos requisitos **R4, R5, R8, R9, R12, R15, R16 e R18** estabelecidos na especificação da N3.

O backend atua como orquestrador central: consome telemetrias MQTT do HiveMQ, persiste em banco relacional, avalia regras de alertas/notificações (falta de sol), expõe API REST autenticada para o frontend TypeScript e despacha comandos para o ESP32.

---

## 2. Mapa de Tópicos MQTT (Contrato v1)

Prefix: `g2fifi/irrigation/v1/`

| Tópico | Direção (Perspectiva Backend) | Formato Payload / Conteúdo |
| --- | --- | --- |
| `g2fifi/irrigation/v1/telemetry/soil`

 | Subscrição (Inbound) | `{"umidade": 42, "raw": 2310, "estado": "off", "modo": "auto"}`

 |
| `g2fifi/irrigation/v1/telemetry/sunlight`

 | Subscrição (Inbound) | `{"luminosidade": 78, "raw": 3200}`

 |
| `g2fifi/irrigation/v1/status/pump`

 | Subscrição (Inbound) | `{"bomba": "on", "modo": "manual", "origem": "manual", "online": true}`

 |
| `g2fifi/irrigation/v1/alert`

 | Subscrição (Inbound) | `{"tipo": "solo_seco", "mensagem": "...", "timestamp": "..."}`

 |
| `g2fifi/irrigation/v1/command/pump`

 | Publicação (Outbound) | Texto simples: `"on"`, `"off"` ou `"auto"`

 |

---

## 3. Tarefas de Implementação por Camada

### Etapa 1: Modelagem e Banco de Dados (`app/models.py`)

* [ ] **Tabela `users` (R4, R9):**


* `id` (UUID/Integer, PK)
* `email` (String, unique, index)
* `hashed_password` (String)
* `created_at` (DateTime)


* [ ] **Tabela `telemetry_soil` (R4, R5):**


* `id` (PK), `umidade` (Float/Int), `raw` (Int), `estado_bomba` (String), `modo` (String), `created_at` (DateTime indexado)




* [ ] **Tabela `telemetry_sunlight` (R4, R5):**


* `id` (PK), `luminosidade` (Float/Int), `raw` (Int), `created_at` (DateTime indexado)




* [ ] **Tabela `system_logs` / `alerts` (R4, R6, R15):**


* `id` (PK), `tipo` (`COMMAND`, `ALERT`, `STATUS`, `SAFETY`), `descricao` (String), `origem` (String), `created_at` (DateTime)




* [ ] **Tabela `system_config` (R4, R6):**


* `id` (PK), `limite_umidade_min` (padrão 30), `limite_umidade_max` (padrão 60), `dias_sem_sol_alerta` (padrão 3), `updated_at` (DateTime)





### Etapa 2: Schemas Pydantic (`app/schemas.py`)

* [ ] Modelos de entrada/saída para autenticação: `UserCreate`, `UserLogin`, `Token`, `UserResponse`.
* [ ] Schemas para telemetria de solo e luminosidade (inbound MQTT e outbound REST).


* [ ] Schemas para logs e alertas com paginação e filtro por período.


* [ ] Schemas de payload para configuração dos thresholds (`ConfigUpdate`, `ConfigResponse`).


* [ ] Schema para envio de comando da bomba (`CommandPumpRequest` com valor literal `"on" | "off" | "auto"`).



### Etapa 3: Autenticação e Segurança Básica (`app/auth.py` / `app/security.py` - R9)

* [ ] Implementar hashing de senhas com `passlib[bcrypt]` ou `bcrypt`.


* [ ] Implementar geração e decodificação de tokens JWT (`python-jose` ou `PyJWT`) com expiração configurável.
* [ ] Criar dependência `get_current_user` para proteção de rotas privadas via OAuth2 Bearer Token.



### Etapa 4: Integração MQTT e Regras de Negócio (`app/mqtt.py`)

* [ ] Atualizar cliente MQTT para conectar no Broker HiveMQ (com suporte a credenciais e TLS se porta 8883 - R16).


* [ ] Subscrição automática na inicialização para a árvore `g2fifi/irrigation/v1/#`.


* [ ] **Handler `telemetry/soil`:** Inserir registro em `telemetry_soil`.


* [ ] **Handler `telemetry/sunlight`:** Inserir registro em `telemetry_sunlight`.


* [ ] **Handler `status/pump`:** Salvar log de mudança de estado da bomba em `system_logs`.


* [ ] **Handler `alert`:** Gravar alerta no banco e disparar notificação externa imediata.


* [ ] **Verificação periódica de falta de luz solar (R4, R15):**


* Executar rotina (cron/background task com `apscheduler` ou `asyncio.sleep`) calculando a incidência de sol nos últimos $X$ dias configurados.


* Caso a média diária fique abaixo do threshold configurado por mais de 3 dias, disparar e-mail de alerta e registrar em log.





### Etapa 5: Serviço de Notificação Externa (`app/services/notifier.py` - R15)

* [ ] Implementar envio de e-mails assíncronos via SMTP (`aiosmtplib` ou `smtplib` em executor).


* [ ] Utilizar variáveis de ambiente configuráveis: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`.


* [ ] Formatar template do alerta: horário, leitura atual, recomendação de reposicionamento da planta ao sol.

### Etapa 6: Rotas da API REST (`app/routers/`)

* [ ] **`POST /api/v1/auth/register`** e **`POST /api/v1/auth/login`**: Criação de conta e emissão de JWT.


* [ ] **`GET /api/v1/telemetry/soil/history`**: Filtros por data inicial/final e limite para gráfico analítico (R14).


* [ ] **`GET /api/v1/telemetry/sunlight/history`**: Histórico de luminosidade e calor.


* [ ] **`POST /api/v1/command/pump`**: Endpoint protegido que valida comando (`on`, `off`, `auto`) e publica via MQTT (R8).


* [ ] **`GET /api/v1/logs`**: Listagem paginada e filtrada por tipo de evento (`COMMAND`, `ALERT`, etc.) (R6).


* [ ] **`GET /api/v1/config`** e **`PUT /api/v1/config`**: Consulta e atualização dos parâmetros de acionamento e tolerância (R4).


* [ ] **`GET /health`**: Verificação do status da API, banco e conexão MQTT.

### Etapa 7: Configuração, Testes e Docker (R11, R12, R18)

* [ ] **`back/.env.example` (R9):** Mapear todas as novas variáveis (`DATABASE_URL`, `MQTT_BROKER`, `MQTT_PORT`, `JWT_SECRET`, `SMTP_*`, etc.).


* [ ] **`requirements.txt`:** Adicionar dependências (`paho-mqtt`, `python-jose`, `passlib[bcrypt]`, `aiosmtplib`, `pytest`, `httpx`).
* [ ] **Docker Compose (R12):** Criar `docker-compose.yml` na raiz ou no backend definindo serviços de backend e dependências.


* [ ] **Testes Automatizados (R18):** Criar `tests/` com testes unitários e de integração (autenticação, inserção de telemetrias e endpoint de comando) integrados em pipeline de CI.



---

## 4. Ordem Recomendada de Execução

1. **Config & Models:** Ajustar `config.py` e expandir `models.py` com as novas tabelas (usuários, luminosidade, logs e configurações).
2. **Database Migration / Setup:** Inicializar tabelas no Supabase/PostgreSQL.


3. **Módulo Auth:** Criar endpoints de registro e login com hash seguro e autenticação JWT.


4. **MQTT & Background Consumer:** Implementar subscrições nos tópicos de solo, luz e alerta.


5. **Serviço de Alertas & SMTP:** Montar a rotina de envio de e-mails para alertas e sol ausente (R15).


6. **Endpoints REST:** Desenvolver endpoints para o frontend consumir histórico, logs e enviar comandos.


7. **Testes & Dockerfile:** Escrever testes de integração e validar inicialização via Docker.