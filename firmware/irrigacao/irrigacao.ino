/* ============================================================
   PROJETO DE IRRIGAÇÃO - IoT  |  Avaliação N3
   Grupo 2 - Irrigação de vaso
   ESP32 DevKit v1 + sensor de umidade do solo (GPIO34)
                   + sensor de luminosidade LDR (GPIO35)
                   + relé da bomba (GPIO23) + LED onboard (GPIO2)

   Fluxo: Sensores -> ESP32 -> Wi-Fi -> MQTT (HiveMQ)
          -> Backend FastAPI -> PostgreSQL (Supabase) -> Painel Web

   Contrato MQTT v1 (ver CONTRATOS.md). O TOPICO_BASE precisa ser
   IDÊNTICO ao MQTT_TOPIC_BASE do backend (back/.env).
   ============================================================ */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------------- CREDENCIAIS ----------------
// Copie secrets.h.example para secrets.h e preencha (secrets.h não vai
// para o Git). Sem secrets.h, usa a rede do simulador Wokwi.
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #define WIFI_SSID     "Wokwi-GUEST"
  #define WIFI_PASSWORD ""
#endif

// ---------------- MQTT / CONTRATO v1 ----------------

const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;

// Prefixo exclusivo do grupo: o broker HiveMQ é público.
#define TOPICO_BASE "g2fifi/irrigation/v1"

const char* TOPICO_SOLO    = TOPICO_BASE "/telemetry/soil";      // ESP32 -> Broker
const char* TOPICO_LUZ     = TOPICO_BASE "/telemetry/sunlight";  // ESP32 -> Broker
const char* TOPICO_STATUS  = TOPICO_BASE "/status/pump";         // ESP32 -> Broker (+ LWT)
const char* TOPICO_ALERTA  = TOPICO_BASE "/alert";               // ESP32 -> Broker
const char* TOPICO_COMANDO = TOPICO_BASE "/command/pump";        // Backend -> ESP32

// ---------------- PINOS ----------------

// Sensores SEMPRE no ADC1 (GPIO32-39): o ADC2 para de funcionar com o Wi-Fi ligado.
const int PINO_SENSOR_SOLO = 34;  // AOUT do sensor capacitivo de umidade
const int PINO_SENSOR_LUZ  = 35;  // AO do módulo LDR (fotoresistor)
const int PINO_BOMBA       = 23;  // IN do módulo relé (+ LED externo de teste)
const int PINO_LED         = 2;   // LED onboard: segue o estado da bomba

// A maioria dos módulos relé aciona em nível BAIXO. Se a bomba ligar
// sozinha ao energizar a placa, troque para false.
const bool RELE_ATIVO_BAIXO = true;

// ---------------- CALIBRAÇÃO ----------------

// Solo (sensor capacitivo): seco = ADC ALTO, molhado = ADC BAIXO.
// No Wokwi, potenciômetro no mínimo = solo encharcado.
const int ADC_SOLO_SECO    = 4095;
const int ADC_SOLO_MOLHADO = 0;

// Luz (módulo LDR com divisor): muita luz = ADC BAIXO, escuro = ADC ALTO.
// É o comportamento do wokwi-photoresistor-sensor e dos módulos comuns.
// Se no seu módulo for o contrário, troque os dois valores.
const int ADC_LUZ_ESCURO = 4095;
const int ADC_LUZ_CLARO  = 0;

// ---------------- PARÂMETROS ----------------

const int LIMIAR_LIGA    = 30;  // umidade <= 30%: modo auto liga a bomba
const int LIMIAR_DESLIGA = 60;  // umidade >= 60%: modo auto desliga

const unsigned long INTERVALO_LEITURA  = 5000;     // telemetria de solo: 5 s
const unsigned long INTERVALO_LUZ      = 15000;    // telemetria de luz: 15 s
const unsigned long TEMPO_MAX_BOMBA    = 30000;    // trava: bomba no máx. 30 s seguidos
const unsigned long BLOQUEIO_SEGURANCA = 60000;    // após a trava, 60 s sem religar
const unsigned long TIMEOUT_MANUAL     = 600000;   // manual volta para auto após 10 min

const unsigned long BACKOFF_MIN = 1000;    // reconexão: começa em 1 s...
const unsigned long BACKOFF_MAX = 60000;   // ...e dobra até 60 s

// Sensor de solo inválido: ADC colado no zero por N leituras seguidas.
const int ADC_SUSPEITO          = 10;
const int LEITURAS_PARA_FALHA   = 6;   // 6 x 5 s = 30 s

// ---------------- ESTADO ----------------

WiFiClient espClient;
PubSubClient mqtt(espClient);
String clientId;

bool bombaLigada = false;
bool modoAuto    = true;

int umidadeAtual = 0;
int adcSoloAtual = 0;
int luzAtual     = 0;
int adcLuzAtual  = 0;

unsigned long bombaLigadaEm = 0;
unsigned long manualDesde   = 0;
unsigned long ultimaLeitura = 0;
unsigned long ultimaLeituraLuz = 0;

bool bloqueadoPorSeguranca = false;
unsigned long bloqueioInicio = 0;

bool sensorSoloFalhou    = false;
int  leiturasSuspeitas   = 0;
bool alertaSoloSecoAtivo = false;

// Backoff exponencial independente para Wi-Fi e MQTT.
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

// ---------------- PUBLICAÇÕES ----------------

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

void publicarTelemetriaSolo() {
  JsonDocument doc;
  doc["umidade"] = umidadeAtual;
  doc["raw"]     = adcSoloAtual;
  doc["estado"]  = bombaLigada ? "on" : "off";
  doc["modo"]    = modoAuto ? "auto" : "manual";
  publicarJson(TOPICO_SOLO, doc, "[SOLO] ");
}

void publicarTelemetriaLuz() {
  JsonDocument doc;
  doc["luminosidade"] = luzAtual;
  doc["raw"]          = adcLuzAtual;
  publicarJson(TOPICO_LUZ, doc, "[LUZ] ");
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

// ---------------- COMANDOS ----------------

void aoReceberMensagem(char* topico, byte* payload, unsigned int tamanho) {
  String comando;
  for (unsigned int i = 0; i < tamanho; i++) comando += (char)payload[i];
  comando.trim();
  comando.toLowerCase();

  Serial.print("[COMANDO] ");
  Serial.println(comando);

  if (comando == "on") {
    // Regras locais de segurança têm prioridade sobre o comando remoto.
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

// ---------------- CONEXÃO (backoff exponencial, não bloqueante) ----------------

void garantirWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    esperaWifi = BACKOFF_MIN;
    return;
  }

  if (millis() - ultimaTentativaWifi >= esperaWifi) {
    ultimaTentativaWifi = millis();
    Serial.print("[WIFI] Reconectando (proxima tentativa em ");
    Serial.print(esperaWifi / 1000);
    Serial.println(" s)...");
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
      mqtt.subscribe(TOPICO_COMANDO);
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

// ---------------- REGRAS LOCAIS ----------------

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

  // Modo manual não fica esquecido: volta para automático após 10 min.
  if (!modoAuto && millis() - manualDesde >= TIMEOUT_MANUAL) {
    modoAuto = true;
    Serial.println("[MODO] Timeout do modo manual, voltando para automatico.");
    publicarStatus("timeout");
  }
}

void avaliarSensorSolo() {
  if (adcSoloAtual < ADC_SUSPEITO) leiturasSuspeitas++;
  else leiturasSuspeitas = 0;

  if (leiturasSuspeitas >= LEITURAS_PARA_FALHA && !sensorSoloFalhou) {
    sensorSoloFalhou = true;
    // Estado seguro: sem leitura confiável, a bomba fica desligada.
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

  // Alerta só na transição, não a cada leitura.
  if (umidadeAtual <= LIMIAR_LIGA && !alertaSoloSecoAtivo) {
    alertaSoloSecoAtivo = true;
    publicarAlerta("solo_seco", "Umidade abaixo do limiar minimo");
  } else if (umidadeAtual > LIMIAR_DESLIGA && alertaSoloSecoAtivo) {
    alertaSoloSecoAtivo = false;
  }
}

void controleAutomatico() {
  if (!modoAuto || bloqueadoPorSeguranca || sensorSoloFalhou) return;

  // Histerese: liga em <= 30%, desliga em >= 60%.
  if (!bombaLigada && umidadeAtual <= LIMIAR_LIGA) {
    setBomba(true, "auto");
  } else if (bombaLigada && umidadeAtual >= LIMIAR_DESLIGA) {
    setBomba(false, "auto");
  }
}

// ---------------- SETUP ----------------

void setup() {
  // Relé desligado ANTES de qualquer outra coisa no boot.
  pinMode(PINO_BOMBA, OUTPUT);
  digitalWrite(PINO_BOMBA, RELE_ATIVO_BAIXO ? HIGH : LOW);
  pinMode(PINO_LED, OUTPUT);
  digitalWrite(PINO_LED, LOW);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Irrigacao IoT - ESP32 (N3: solo + luz) ===");

  analogReadResolution(12);   // 0 a 4095
  pinMode(PINO_SENSOR_SOLO, INPUT);
  pinMode(PINO_SENSOR_LUZ, INPUT);

  clientId = "esp32-irrig-" + String((uint32_t)ESP.getEfuseMac(), HEX);
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

  verificarSeguranca();

  // --- Solo: leitura, regras locais e telemetria (5 s) ---
  if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
    ultimaLeitura = millis();

    adcSoloAtual = lerAdcMedio(PINO_SENSOR_SOLO);
    umidadeAtual = adcParaPercentual(adcSoloAtual, ADC_SOLO_SECO, ADC_SOLO_MOLHADO);

    avaliarSensorSolo();
    avaliarSoloSeco();
    controleAutomatico();
    publicarTelemetriaSolo();
  }

  // --- Luz: leitura e telemetria (15 s) ---
  // O alerta de "dias sem sol" é calculado no backend (média diária).
  if (millis() - ultimaLeituraLuz >= INTERVALO_LUZ) {
    ultimaLeituraLuz = millis();

    adcLuzAtual = lerAdcMedio(PINO_SENSOR_LUZ);
    luzAtual = adcParaPercentual(adcLuzAtual, ADC_LUZ_ESCURO, ADC_LUZ_CLARO);

    publicarTelemetriaLuz();
  }
}
