/* ============================================================
   PROJETO DE IRRIGAÇÃO - IoT  |  Avaliação N1
   Grupo 2 - Irrigação de vaso
   ESP32 DevKit v1 + sensor de umidade (potenciômetro) + LED (bomba)

   Fluxo: Sensor -> ESP32 -> Wi-Fi -> MQTT (HiveMQ) -> Painel Web

   ATENÇÃO: o TOPICO_BASE abaixo precisa ser IDÊNTICO ao usado no
   dashboard/index.html, senão o painel não recebe nada.
   ============================================================ */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------------- CONFIGURAÇÃO ----------------

// No Wokwi o Wi-Fi é sempre este. Na placa real, troque pelo seu.
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;

// Prefixo único do grupo. O broker HiveMQ é público e aberto ao mundo:
// se usarem só "irrigacao/", outro grupo pode publicar em cima de vocês.
#define TOPICO_BASE "irrigacao/g2fifi"

const char* TOPICO_UMIDADE = TOPICO_BASE "/umidade";  // ESP32 -> WEB
const char* TOPICO_STATUS  = TOPICO_BASE "/status";   // ESP32 -> WEB
const char* TOPICO_ALERTA  = TOPICO_BASE "/alerta";   // ESP32 -> WEB
const char* TOPICO_BOMBA   = TOPICO_BASE "/bomba";    // WEB -> ESP32

// ---------------- PINOS ----------------

// GPIO 34 é do ADC1. NÃO troque para 0/2/4/12-15/25-27 (ADC2):
// o ADC2 para de funcionar quando o Wi-Fi está ligado.
const int PINO_SENSOR = 34;
const int PINO_BOMBA  = 23;   // LED + resistor 220 ohms

// ---------------- PARÂMETROS ----------------

// Calibração do sensor (sensor capacitivo: seco = valor ALTO).
// No simulador, gire o potenciômetro: mínimo = solo encharcado.
const int ADC_SECO    = 4095;
const int ADC_MOLHADO = 0;

const int LIMIAR_LIGA    = 30;  // abaixo disso, modo auto liga a bomba
const int LIMIAR_DESLIGA = 60;  // acima disso, modo auto desliga

const unsigned long INTERVALO_LEITURA   = 5000;   // telemetria a cada 5 s
const unsigned long TEMPO_MAX_BOMBA     = 30000;  // trava de segurança: 30 s
const unsigned long BLOQUEIO_SEGURANCA  = 60000;  // espera 60 s após a trava
const unsigned long INTERVALO_RECONEXAO = 5000;

// ---------------- ESTADO ----------------

WiFiClient espClient;
PubSubClient mqtt(espClient);
String clientId;

bool bombaLigada = false;
bool modoAuto    = true;
int  umidadeAtual = 0;
int  adcAtual     = 0;

unsigned long bombaLigadaEm     = 0;
unsigned long ultimaLeitura     = 0;
unsigned long ultimaTentativaWifi = 0;
unsigned long ultimaTentativaMqtt = 0;
unsigned long bloqueioInicio    = 0;
bool bloqueadoPorSeguranca = false;

bool alertaSoloSecoAtivo = false;
bool alertaSensorAtivo   = false;
int  leiturasSuspeitas   = 0;

// ---------------- SENSOR ----------------

int lerAdcMedio() {
  long soma = 0;
  for (int i = 0; i < 10; i++) {
    soma += analogRead(PINO_SENSOR);
    delay(5);
  }
  return soma / 10;
}

int adcParaUmidade(int raw) {
  long u = map(raw, ADC_SECO, ADC_MOLHADO, 0, 100);
  return constrain(u, 0, 100);
}

// ---------------- PUBLICAÇÕES ----------------

void publicarStatus(const char* origem) {
  JsonDocument doc;
  doc["bomba"]  = bombaLigada ? "on" : "off";
  doc["modo"]   = modoAuto ? "auto" : "manual";
  doc["origem"] = origem;
  doc["online"] = true;

  char buf[160];
  serializeJson(doc, buf);
  mqtt.publish(TOPICO_STATUS, buf);
  Serial.print("[STATUS] ");
  Serial.println(buf);
}

void publicarTelemetria() {
  JsonDocument doc;
  doc["umidade"] = umidadeAtual;
  doc["raw"]     = adcAtual;
  doc["estado"]  = bombaLigada ? "on" : "off";
  doc["modo"]    = modoAuto ? "auto" : "manual";

  char buf[160];
  serializeJson(doc, buf);
  mqtt.publish(TOPICO_UMIDADE, buf);
  Serial.print("[TELEMETRIA] ");
  Serial.println(buf);
}

void publicarAlerta(const char* tipo, const char* mensagem) {
  JsonDocument doc;
  doc["tipo"]     = tipo;
  doc["mensagem"] = mensagem;
  doc["umidade"]  = umidadeAtual;

  char buf[220];
  serializeJson(doc, buf);
  mqtt.publish(TOPICO_ALERTA, buf);
  Serial.print("[ALERTA] ");
  Serial.println(buf);
}

// ---------------- BOMBA ----------------

void setBomba(bool ligar, const char* origem) {
  if (ligar == bombaLigada) return;

  bombaLigada = ligar;
  digitalWrite(PINO_BOMBA, ligar ? HIGH : LOW);
  if (ligar) bombaLigadaEm = millis();

  publicarStatus(origem);
}


void aoReceberMensagem(char* topico, byte* payload, unsigned int tamanho) {
  String comando;
  for (unsigned int i = 0; i < tamanho; i++) comando += (char)payload[i];
  comando.trim();
  comando.toLowerCase();

  Serial.print("[COMANDO] ");
  Serial.println(comando);

  if (comando == "on") {
    modoAuto = false;
    bloqueadoPorSeguranca = false;
    setBomba(true, "manual");
    publicarStatus("manual");
  }
  else if (comando == "off") {
    modoAuto = false;
    setBomba(false, "manual");
    publicarStatus("manual");
  }
  else if (comando == "auto") {
    modoAuto = true;
    publicarStatus("auto");
  }
  else {
    publicarAlerta("comando", "Comando desconhecido recebido");
  }
}


void garantirWifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  if (millis() - ultimaTentativaWifi >= INTERVALO_RECONEXAO) {
    ultimaTentativaWifi = millis();
    Serial.println("[WIFI] Reconectando...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

void garantirMqtt() {
  if (mqtt.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  if (millis() - ultimaTentativaMqtt >= INTERVALO_RECONEXAO) {
    ultimaTentativaMqtt = millis();
    Serial.print("[MQTT] Conectando ao broker... ");

    const char* lastWill = "{\"online\":false}";

    if (mqtt.connect(clientId.c_str(), NULL, NULL,
                     TOPICO_STATUS, 0, false, lastWill)) {
      Serial.println("conectado!");
      mqtt.subscribe(TOPICO_BOMBA);
      publicarStatus("boot");
    } else {
      Serial.print("falhou, rc=");
      Serial.println(mqtt.state());
    }
  }
}


void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Irrigacao IoT - ESP32 ===");

  pinMode(PINO_BOMBA, OUTPUT);
  digitalWrite(PINO_BOMBA, LOW);
  analogReadResolution(12);   // 0 a 4095

  clientId = "esp32-irrig-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.print("Client ID: ");
  Serial.println(clientId);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(aoReceberMensagem);
  mqtt.setKeepAlive(30);
}

// ---------------- LOOP ----------------

void loop() {
  garantirWifi();
  garantirMqtt();
  mqtt.loop();

  // --- Trava de segurança: bomba nunca fica ligada demais ---
  if (bombaLigada && millis() - bombaLigadaEm >= TEMPO_MAX_BOMBA) {
    setBomba(false, "seguranca");
    bloqueadoPorSeguranca = true;
    bloqueioInicio = millis();
    publicarAlerta("seguranca",
      "Bomba excedeu o tempo maximo e foi desligada automaticamente");
  }

  if (bloqueadoPorSeguranca &&
      millis() - bloqueioInicio >= BLOQUEIO_SEGURANCA) {
    bloqueadoPorSeguranca = false;
    Serial.println("[SEGURANCA] Bloqueio liberado.");
  }

  // --- Ciclo de leitura + telemetria ---
  if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
    ultimaLeitura = millis();

    adcAtual = lerAdcMedio();
    umidadeAtual = adcParaUmidade(adcAtual);

    // Suspeita de sensor desconectado: leitura colada no zero absoluto.
    // Se o potenciômetro no mínimo disparar isso no teste de vocês,
    // é só aumentar o limite de 10 ou o contador de 6.
    if (adcAtual < 10) leiturasSuspeitas++;
    else leiturasSuspeitas = 0;

    if (leiturasSuspeitas >= 6 && !alertaSensorAtivo) {
      alertaSensorAtivo = true;
      publicarAlerta("sensor", "Leitura invalida: verifique o sensor");
    } else if (leiturasSuspeitas == 0 && alertaSensorAtivo) {
      alertaSensorAtivo = false;
    }

    // Alerta de solo seco (só na transição, não a cada 5 s)
    if (umidadeAtual <= LIMIAR_LIGA && !alertaSoloSecoAtivo) {
      alertaSoloSecoAtivo = true;
      publicarAlerta("solo_seco", "Umidade abaixo do limiar minimo");
    } else if (umidadeAtual > LIMIAR_DESLIGA && alertaSoloSecoAtivo) {
      alertaSoloSecoAtivo = false;
    }

    // --- Modo automático com histerese ---
    if (modoAuto && !bloqueadoPorSeguranca) {
      if (!bombaLigada && umidadeAtual <= LIMIAR_LIGA) {
        setBomba(true, "auto");
      } else if (bombaLigada && umidadeAtual >= LIMIAR_DESLIGA) {
        setBomba(false, "auto");
      }
    }

    publicarTelemetria();
  }
}
