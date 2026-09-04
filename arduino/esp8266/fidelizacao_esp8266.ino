/*
 * FideliZa - ESP8266: envia compra por TELEFONE para a API Flask.
 * POST /api/compras/  body {"telefone":"...","valor":...}
 * Acende LED verde ao receber HTTP 201.
 */
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

const char* SSID     = "SUA_REDE_WIFI";
const char* SENHA    = "SUA_SENHA_WIFI";
const char* SERVIDOR = "http://192.168.0.10:5000/api/compras/";
const int   LED_VERDE = D2;

void setup() {
  Serial.begin(115200);
  pinMode(LED_VERDE, OUTPUT);
  WiFi.begin(SSID, SENHA);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi OK: " + WiFi.localIP().toString());
}

void pontuar(String telefone, float valor) {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client; HTTPClient http;
  http.begin(client, SERVIDOR);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", "fideliza-iot-key-padrao");
  String corpo = "{\"telefone\":\"" + telefone + "\",\"valor\":" + String(valor, 2) + "}";
  int codigo = http.POST(corpo);
  Serial.printf("HTTP %d -> %s\n", codigo, http.getString().c_str());
  if (codigo == 201) { digitalWrite(LED_VERDE, HIGH); delay(1500); digitalWrite(LED_VERDE, LOW); }
  http.end();
}

void loop() {
  pontuar("11999991111", 50.00);
  delay(30000);
}
