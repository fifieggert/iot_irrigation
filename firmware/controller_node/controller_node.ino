/* ============================================================
   PROJETO DE IRRIGACAO - IoT  |  Avaliacao N3
   Grupo 2 - Irrigacao de vaso

   NO CONTROLADOR (ESP32 #2)
   -------------------------
   Responsabilidade unica: RECEBER a telemetria do no sensor,
   aplicar as regras de seguranca e ACIONAR a bomba. Esta placa
   nao tem sensor nenhum ligado nela.

   Rele da bomba ..... GPIO23 (IN) + LED externo de teste
   LED onboard ....... GPIO2  (segue o estado da bomba)

   Fluxo: ESP32 #1 -> MQTT -> ESP32 #2 -> rele -> bomba
          Backend  -> MQTT -> ESP32 #2 (comando manual)

   Contrato MQTT v1 (ver CONTRATOS.md).
   ============================================================ */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------------- CREDENCIAIS ----------------
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #define WIFI_SSID     "Wokwi-GUEST"
  #define WIFI_PASSWORD ""
#endif

// ---------------- MQTT / CONTRATO v1 ----------------

const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;

#define TOPICO_BASE "g2fifi/irrigation/v1"

const char* TOPICO_SOLO    = TOPICO_BASE "/telemetry/soil";   // assina (do no sensor)
const char* TOPICO_STATUS  = TOPICO_BASE "/status/pump";      // publica (+ LWT)
const char* TOPICO_ALERTA  = TOPICO_BASE "/alert";            // publica
const char* TOPICO_COMANDO = TOPICO_BASE "/command/pump";     // assina (do backend)

// ---------------- PINOS ----------------

const int PINO_BOMBA = 23;  // IN do modulo rele
const int PINO_LED   = 2;   // LED onboard

// A maioria dos modulos rele aciona em nivel BAIXO. Se a bomba ligar
// sozinha ao energizar a placa, troque para false.
const bool RELE_ATIVO_BAIXO = true;

// ---------------- PARAMETROS ----------------

const int LIMIAR_LIGA    = 30;  // umidade <= 30%: modo auto liga a bomba
const int LIMIAR_DESLIGA = 60;  // umidade >= 60%: modo auto desliga

const unsigned long TEMPO_MAX_BOMBA    = 30000;    // bomba no max. 30 s seguidos
const unsigned long BLOQUEIO_SEGURANCA = 60000;    // apos a trava, 60 s sem religar
const unsigned long TIMEOUT_MANUAL     = 600000;   // manual volta para auto em 10 min

// Sistema distribuido: se a telemetria do no sensor parar de chegar,
// o controlador entra em estado seguro.
const unsigned long TIMEOUT_TELEMETRIA = 30000;    // 6 x o intervalo de 5 s

const unsigned long BACKOFF_MIN    = 1000;
const unsigned long BACKOFF_MAX    = 60000;
const unsigned long TENTATIVA_WIFI = 8000;

// Sensor de solo invalido: ADC colado no zero por N leituras seguidas.
const int ADC_SUSPEITO        = 10;
const int LEITURAS_PARA_FALHA = 6;

// ---------------- ESTADO ----------------

WiFiClient espClient;
PubSubClient mqtt(espClient);
String clientId;

bool bombaLigada = false;
bool modoAuto    = true;

int umidadeAtual = 0;
int adcSoloAtual = 0;

unsigned long bombaLigadaEm = 0;
unsigned long manualDesde   = 0;

bool bloqueadoPorSeguranca = false;
unsigned long bloqueioInicio = 0;

bool sensorSoloFalhou    = false;
int  leiturasSuspeitas   = 0;
bool alertaSoloSecoAtivo = false;

// Comunicacao com o no sensor.
bool recebeuTelemetria = false;
bool semTelemetria     = false;
unsigned long ultimaTelemetria = 0;

unsigned long ultimaTentativaWifi = 0;
unsigned long esperaWifi = BACKOFF_MIN;
unsigned long ultimaTentativaMqtt = 0;
unsigned long esperaMqtt = BACKOFF_MIN;

// ---------------- PUBLICACOES ----------------

void publicarJson(const char* topico, JsonDocument& doc, const char* rotulo) {
  char buf[256];
  serializeJson(doc, buf, sizeof(buf));
  if (mqtt.connected()) mqtt.publish(topico, buf);
  Serial.print(rotulo);
  Serial.println(buf);
}

void publicarStatus(const char* origem) {
  JsonDocument doc;
  doc["bomba"]     = bombaLigada ? "on" : "off";
  doc["modo"]      = modoAuto ? "auto" : "manual";
  doc["origem"]    = origem;
  doc["bloqueado"] = bloqueadoPorSeguranca;
  doc["online"]    = true;
  publicarJson(TOPICO_STATUS, doc, "[STATUS] ");
}

void publicarAlerta(const char* tipo, const char* mensagem) {
  JsonDocument doc;
  doc["tipo"]     = tipo;
  doc["mensagem"] = mensagem;
  doc["umidade"]  = umidadeAtual;
  publicarJson(TOPICO_ALERTA, doc, "[ALERTA] ");
}

// ---------------- BOMBA ----------------

void setBomba(bool ligar, const char* origem) {
  if (ligar == bombaLigada) return;

  bombaLigada = ligar;
  bool nivel = RELE_ATIVO_BAIXO ? !ligar : ligar;
  digitalWrite(PINO_BOMBA, nivel ? HIGH : LOW);
  digitalWrite(PINO_LED, ligar ? HIGH : LOW);
  if (ligar) bombaLigadaEm = millis();

  publicarStatus(origem);
}

void entrarModoManual() {
  modoAuto = false;
  manualDesde = millis();
}

// ---------------- REGRAS ----------------

void avaliarSensorSolo() {
  if (adcSoloAtual < ADC_SUSPEITO) leiturasSuspeitas++;
  else leiturasSuspeitas = 0;

  if (leiturasSuspeitas >= LEITURAS_PARA_FALHA && !sensorSoloFalhou) {
    sensorSoloFalhou = true;
    setBomba(false, "sensor");
    publicarAlerta("sensor",
      "Leitura invalida do sensor de umidade: bomba mantida desligada");
  } else if (leiturasSuspeitas == 0 && sensorSoloFalhou) {
    sensorSoloFalhou = false;
    Serial.println("[SENSOR] Leitura de umidade normalizada.");
  }
}

void avaliarSoloSeco() {
  if (sensorSoloFalhou) return;

  if (umidadeAtual <= LIMIAR_LIGA && !alertaSoloSecoAtivo) {
    alertaSoloSecoAtivo = true;
    publicarAlerta("solo_seco", "Umidade abaixo do limiar minimo");
  } else if (umidadeAtual > LIMIAR_DESLIGA && alertaSoloSecoAtivo) {
    alertaSoloSecoAtivo = false;
  }
}

void controleAutomatico() {
  if (!modoAuto || bloqueadoPorSeguranca || sensorSoloFalhou || semTelemetria) return;
  if (!recebeuTelemetria) return;  // sem dado nenhum ainda: nao decide nada

  // Histerese: liga em <= 30%, desliga em >= 60%.
  if (!bombaLigada && umidadeAtual <= LIMIAR_LIGA) {
    setBomba(true, "auto");
  } else if (bombaLigada && umidadeAtual >= LIMIAR_DESLIGA) {
    setBomba(false, "auto");
  }
}

void verificarSeguranca() {
  // Trava: a bomba nunca fica ligada mais que TEMPO_MAX_BOMBA seguidos.
  if (bombaLigada && millis() - bombaLigadaEm >= TEMPO_MAX_BOMBA) {
    bloqueadoPorSeguranca = true;
    bloqueioInicio = millis();
    setBomba(false, "seguranca");
    publicarAlerta("seguranca",
      "Bomba excedeu o tempo maximo e foi desligada automaticamente");
  }

  if (bloqueadoPorSeguranca && millis() - bloqueioInicio >= BLOQUEIO_SEGURANCA) {
    bloqueadoPorSeguranca = false;
    Serial.println("[SEGURANCA] Bloqueio liberado.");
    publicarStatus("seguranca");
  }

  // Modo manual nao fica esquecido: volta para automatico apos 10 min.
  if (!modoAuto && millis() - manualDesde >= TIMEOUT_MANUAL) {
    modoAuto = true;
    Serial.println("[MODO] Timeout do modo manual, voltando para automatico.");
    publicarStatus("timeout");
  }
}

void verificarComunicacao() {
  if (!recebeuTelemetria) return;

  bool parou = (millis() - ultimaTelemetria >= TIMEOUT_TELEMETRIA);

  if (parou && !semTelemetria) {
    semTelemetria = true;
    setBomba(false, "comunicacao");
    publicarAlerta("comunicacao",
      "Telemetria do no sensor parou de chegar: bomba mantida desligada");
  } else if (!parou && semTelemetria) {
    semTelemetria = false;
    Serial.println("[COMUNICACAO] Telemetria do no sensor restabelecida.");
    publicarStatus("comunicacao");
  }
}

// ---------------- MENSAGENS RECEBIDAS ----------------

void tratarTelemetriaSolo(byte* payload, unsigned int tamanho) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, tamanho)) {
    Serial.println("[SOLO] Payload invalido, ignorado.");
    return;
  }

  umidadeAtual = doc["umidade"] | 0;
  adcSoloAtual = doc["raw"] | 0;

  ultimaTelemetria  = millis();
  recebeuTelemetria = true;

  Serial.print("[SOLO] recebido do no sensor: umidade=");
  Serial.print(umidadeAtual);
  Serial.print("% raw=");
  Serial.println(adcSoloAtual);

  avaliarSensorSolo();
  avaliarSoloSeco();
  controleAutomatico();
}

void tratarComando(byte* payload, unsigned int tamanho) {
  String comando;
  for (unsigned int i = 0; i < tamanho; i++) comando += (char)payload[i];
  comando.trim();
  comando.toLowerCase();

  Serial.print("[COMANDO] ");
  Serial.println(comando);

  if (comando == "on") {
    // Regras locais de seguranca tem prioridade sobre o comando remoto.
    if (bloqueadoPorSeguranca) {
      publicarAlerta("seguranca",
        "Comando on recusado: bomba em bloqueio de seguranca");
      publicarStatus("recusado");
      return;
    }
    if (sensorSoloFalhou) {
      publicarAlerta("sensor",
        "Comando on recusado: sensor de umidade com leitura invalida");
      publicarStatus("recusado");
      return;
    }
    if (semTelemetria || !recebeuTelemetria) {
      publicarAlerta("comunicacao",
        "Comando on recusado: sem telemetria do no sensor");
      publicarStatus("recusado");
      return;
    }
    entrarModoManual();
    if (bombaLigada) publicarStatus("manual");
    else setBomba(true, "manual");
  }
  else if (comando == "off") {
    entrarModoManual();
    if (!bombaLigada) publicarStatus("manual");
    else setBomba(false, "manual");
  }
  else if (comando == "auto") {
    modoAuto = true;
    publicarStatus("auto");
  }
  else {
    publicarAlerta("comando", "Comando desconhecido recebido");
  }
}

void aoReceberMensagem(char* topico, byte* payload, unsigned int tamanho) {
  if (strcmp(topico, TOPICO_SOLO) == 0)         tratarTelemetriaSolo(payload, tamanho);
  else if (strcmp(topico, TOPICO_COMANDO) == 0) tratarComando(payload, tamanho);
}

// ---------------- CONEXAO ----------------

void garantirWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    esperaWifi = BACKOFF_MIN;
    return;
  }
  if (millis() - ultimaTentativaWifi >= max(esperaWifi, TENTATIVA_WIFI)) {
    ultimaTentativaWifi = millis();
    Serial.println("[WIFI] Reconectando...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    esperaWifi = min(esperaWifi * 2, BACKOFF_MAX);
  }
}

void garantirMqtt() {
  if (mqtt.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  if (millis() - ultimaTentativaMqtt >= esperaMqtt) {
    ultimaTentativaMqtt = millis();
    Serial.print("[MQTT] Conectando ao broker... ");

    const char* lastWill = "{\"online\":false}";

    if (mqtt.connect(clientId.c_str(), NULL, NULL,
                     TOPICO_STATUS, 0, false, lastWill)) {
      Serial.println("conectado!");
      esperaMqtt = BACKOFF_MIN;
      mqtt.subscribe(TOPICO_SOLO);
      mqtt.subscribe(TOPICO_COMANDO);
      Serial.println("[MQTT] Assinado: telemetry/soil e command/pump");
      publicarStatus("boot");
    } else {
      Serial.print("falhou, rc=");
      Serial.print(mqtt.state());
      Serial.print(". Nova tentativa em ");
      Serial.print(esperaMqtt / 1000);
      Serial.println(" s");
      esperaMqtt = min(esperaMqtt * 2, BACKOFF_MAX);
    }
  }
}

// ---------------- SETUP ----------------

void setup() {
  // Rele desligado ANTES de qualquer outra coisa no boot.
  pinMode(PINO_BOMBA, OUTPUT);
  digitalWrite(PINO_BOMBA, RELE_ATIVO_BAIXO ? HIGH : LOW);
  pinMode(PINO_LED, OUTPUT);
  digitalWrite(PINO_LED, LOW);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Irrigacao IoT - NO CONTROLADOR (ESP32 #2) ===");

  clientId = "esp32-ctrl-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.print("Client ID: ");
  Serial.println(clientId);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  ultimaTentativaWifi = millis();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(aoReceberMensagem);
  mqtt.setKeepAlive(30);
  mqtt.setBufferSize(512);
}

// ---------------- LOOP ----------------

void loop() {
  garantirWifi();
  garantirMqtt();
  mqtt.loop();

  verificarComunicacao();
  verificarSeguranca();
}
