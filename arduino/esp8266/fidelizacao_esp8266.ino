/*
 * IT Clube - ESP8266: envia compra por TELEFONE para a API Flask.
 * POST /api/compras/  body {"telefone":"..."}
 * Acende LED verde ao receber HTTP 201 (1 compra = 1 ponto).
 */
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include "secrets.h"

const int   LED_VERDE = D2;
unsigned long sequenciaOperacao = 0;

void setup() {
  Serial.begin(115200);
  pinMode(LED_VERDE, OUTPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi OK: " + WiFi.localIP().toString());
}

void pontuar(String telefone) {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client; HTTPClient http;
  http.begin(client, API_COMPRAS_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", IOT_DEVICE_KEY);
  String idOperacao = "iot-" + String(ESP.getChipId(), HEX) + "-" + String(millis()) + "-" + String(++sequenciaOperacao);
  http.addHeader("X-Idempotency-Key", idOperacao);
  String corpo = "{\"telefone\":\"" + telefone + "\"}";
  int codigo = http.POST(corpo);
  Serial.printf("HTTP %d -> %s\n", codigo, http.getString().c_str());
  if (codigo == 200 || codigo == 201) { digitalWrite(LED_VERDE, HIGH); delay(1500); digitalWrite(LED_VERDE, LOW); }
  http.end();
}

void loop() {
  pontuar("11999991111");
  delay(30000);
}
