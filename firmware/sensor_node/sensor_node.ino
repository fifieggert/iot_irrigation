/* ============================================================
   PROJETO DE IRRIGACAO - IoT  |  Avaliacao N3
   Grupo 2 - Irrigacao de vaso

   NO SENSOR (ESP32 #1)
   --------------------
   Responsabilidade unica: LER os dois sensores e PUBLICAR a
   telemetria. Esta placa nao decide nada e nao aciona a bomba.

   Sensor de umidade do solo .... GPIO34 (AOUT)
   Sensor de luminosidade LDR ... GPIO35 (AO)

   Fluxo: Sensores -> ESP32 #1 -> MQTT -> ESP32 #2 (controlador)
                                       -> Backend FastAPI

   Contrato MQTT v1 (ver CONTRATOS.md). O TOPICO_BASE precisa ser
   IDENTICO ao MQTT_TOPIC_BASE do backend (back/.env).
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

const char* TOPICO_SOLO = TOPICO_BASE "/telemetry/soil";      // publica
const char* TOPICO_LUZ  = TOPICO_BASE "/telemetry/sunlight";  // publica

// ---------------- PINOS ----------------

// Sensores SEMPRE no ADC1 (GPIO32-39): o ADC2 para de funcionar com Wi-Fi.
const int PINO_SENSOR_SOLO = 34;
const int PINO_SENSOR_LUZ  = 35;
const int PINO_LED         = 2;   // LED onboard: pisca a cada publicacao

// ---------------- CALIBRACAO ----------------

// Solo (capacitivo): seco = ADC ALTO, molhado = ADC BAIXO.
const int ADC_SOLO_SECO    = 4095;
const int ADC_SOLO_MOLHADO = 2100;

// Luz (modulo LDR): muita luz = ADC BAIXO, escuro = ADC ALTO.
const int ADC_LUZ_ESCURO = 4095;
const int ADC_LUZ_CLARO  = 0;

// ---------------- PARAMETROS ----------------

const unsigned long INTERVALO_LEITURA = 5000;    // solo: 5 s
const unsigned long INTERVALO_LUZ     = 15000;   // luz: 15 s

const unsigned long BACKOFF_MIN     = 1000;
const unsigned long BACKOFF_MAX     = 60000;
const unsigned long TENTATIVA_WIFI  = 8000;   // tempo minimo por tentativa

// ---------------- ESTADO ----------------

WiFiClient espClient;
PubSubClient mqtt(espClient);
String clientId;

int umidadeAtual = 0;
int adcSoloAtual = 0;
int luzAtual     = 0;
int adcLuzAtual  = 0;

unsigned long ultimaLeitura    = 0;
unsigned long ultimaLeituraLuz = 0;

unsigned long ultimaTentativaWifi = 0;
unsigned long esperaWifi = BACKOFF_MIN;
unsigned long ultimaTentativaMqtt = 0;
unsigned long esperaMqtt = BACKOFF_MIN;

// ---------------- SENSORES ----------------

int lerAdcMedio(int pino) {
  long soma = 0;
  for (int i = 0; i < 10; i++) {
    soma += analogRead(pino);
    delay(2);
  }
  return soma / 10;
}

int adcParaPercentual(int raw, int adcZero, int adcCem) {
  long p = map(raw, adcZero, adcCem, 0, 100);
  return constrain(p, 0, 100);
}

// ---------------- PUBLICACOES ----------------

void publicarJson(const char* topico, JsonDocument& doc, const char* rotulo) {
  char buf[256];
  serializeJson(doc, buf, sizeof(buf));
  if (mqtt.connected()) mqtt.publish(topico, buf);
  Serial.print(rotulo);
  Serial.println(buf);

  digitalWrite(PINO_LED, HIGH);
  delay(30);
  digitalWrite(PINO_LED, LOW);
}

void publicarTelemetriaSolo() {
  JsonDocument doc;
  doc["umidade"] = umidadeAtual;
  doc["raw"]     = adcSoloAtual;
  publicarJson(TOPICO_SOLO, doc, "[SOLO] ");
}

void publicarTelemetriaLuz() {
  JsonDocument doc;
  doc["luminosidade"] = luzAtual;
  doc["raw"]          = adcLuzAtual;
  publicarJson(TOPICO_LUZ, doc, "[LUZ] ");
}

// ---------------- CONEXAO (backoff exponencial, nao bloqueante) ----------------

void garantirWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    esperaWifi = BACKOFF_MIN;
    return;
  }
  // Cada tentativa ganha ao menos TENTATIVA_WIFI antes de ser abortada.
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

    if (mqtt.connect(clientId.c_str())) {
      Serial.println("conectado!");
      esperaMqtt = BACKOFF_MIN;
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
  pinMode(PINO_LED, OUTPUT);
  digitalWrite(PINO_LED, LOW);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Irrigacao IoT - NO SENSOR (ESP32 #1) ===");

  analogReadResolution(12);
  pinMode(PINO_SENSOR_SOLO, INPUT);
  pinMode(PINO_SENSOR_LUZ, INPUT);

  clientId = "esp32-sensor-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.print("Client ID: ");
  Serial.println(clientId);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  ultimaTentativaWifi = millis();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(30);
  mqtt.setBufferSize(512);
}

// ---------------- LOOP ----------------

void loop() {
  garantirWifi();
  garantirMqtt();
  mqtt.loop();

  if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
    ultimaLeitura = millis();
    adcSoloAtual = lerAdcMedio(PINO_SENSOR_SOLO);
    umidadeAtual = adcParaPercentual(adcSoloAtual, ADC_SOLO_SECO, ADC_SOLO_MOLHADO);
    publicarTelemetriaSolo();
  }

  if (millis() - ultimaLeituraLuz >= INTERVALO_LUZ) {
    ultimaLeituraLuz = millis();
    adcLuzAtual = lerAdcMedio(PINO_SENSOR_LUZ);
    luzAtual = adcParaPercentual(adcLuzAtual, ADC_LUZ_ESCURO, ADC_LUZ_CLARO);
    publicarTelemetriaLuz();
  }
}
