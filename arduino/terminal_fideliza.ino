/* =====================================================================
   TERMINAL DE FIDELIZACAO - FideliZa
   TCC - Ciencia da Computacao / UNIP Campinas - 2026

   Terminal de balcao. O cliente digita o telefone, o servidor credita
   os pontos da visita e devolve nome e saldo, exibidos no display.

   -------------------------------------------------------------------
   COMO ELE CONVERSA COM O BANCO

   O terminal NAO acessa o banco de dados. Ele envia uma requisicao
   HTTP para a API do FideliZa, e a API e a unica que le e grava no
   banco. Por isso terminal e portal enxergam sempre os mesmos dados:
   nao existem duas fontes, existe uma so.

       Terminal ---HTTP--> API FideliZa --> Banco
                                ^
       Portal web --------------

   Para apontar para outro servidor basta mudar API_BASE no
   credenciais.h. Nenhuma outra linha deste arquivo muda.

   -------------------------------------------------------------------
   CONTRATO ESPERADO DO SERVIDOR

     POST  {API_BASE}{API_ROTA}
     Header: X-Device-Key: <IOT_DEVICE_KEY do .env do servidor>
     Corpo:  {"telefone":"19998887777","uuid":"<id unico da operacao>"}

     Resposta 200 ou 201, em qualquer um destes formatos:
       {"cliente":{"nome":"Ana"},"compra":{"pontos_gerados":1},
        "saldo_atualizado":42}
       ou
       {"nome":"Ana","pontos_gerados":1,"pontos_total":42}

     O firmware aceita os dois, para nao depender do formato exato que
     o backend vier a adotar. Erros tratados: 400, 401, 404 e 409.

   O uuid identifica a operacao. Se o servidor guardar esse valor com
   restricao de unicidade, um reenvio por falha de rede nao pontua o
   cliente duas vezes. Se ignorar o campo, nada quebra.

   -------------------------------------------------------------------
   LIGACAO

   LCD I2C:  VCC -> VU (5V)   GND -> G   SDA -> D2   SCL -> D1
             Em NodeMCU v3 o 5V sai no VU, nao no Vin.

   TECLADO (7 fios, sem alimentacao):
     linha  1 2 3  -> D5      coluna 1 4 7 *  -> D0
     linha  4 5 6  -> D3      coluna 2 5 8 0  -> RX
     linha  7 8 9  -> D6      coluna 3 6 9 #  -> D4
     linha  * 0 #  -> D7

   O D8 fica livre.

   MONTE SOBRE PROTOBOARD. Jumper encaixado direto no pino solta ao
   menor esbarrao, e o sintoma e sempre o mesmo: uma coluna inteira
   para de responder, mudando de lugar a cada remontagem. A protoboard
   da apoio mecanico a cada fio e foi o que resolveu.

   -------------------------------------------------------------------
   OPERACAO
     digitos  telefone (10 ou 11)
     #        confirma
     *        apaga o ultimo digito

   Bibliotecas: LiquidCrystal_I2C, Keypad, ArduinoJson v7
   ===================================================================== */

// A ORDEM DOS INCLUDES IMPORTA:
// ESP8266WiFi.h antes de Keypad.h. A Keypad define a macro CLOSED, que
// colide com o enum de mesmo nome da pilha de rede do ESP8266.
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>

// Quando o servidor esta na internet, a URL e https e o ESP precisa
// falar TLS. Ligue USAR_HTTPS no credenciais.h nesse caso.
#include "credenciais.h"
#if USAR_HTTPS
  #include <WiFiClientSecure.h>
#endif
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>
#include <ArduinoJson.h>

// =====================================================================
// TIPOS E ESTADO GLOBAL
//
// Declarados aqui, logo apos os includes, de proposito: o Arduino IDE
// gera os prototipos das funcoes e os insere perto do topo do arquivo.
// Se os tipos viessem depois, a compilacao falharia com
// "'Resposta' does not name a type".
// =====================================================================

enum Estado { ST_ENTRADA, ST_RESULTADO };
enum Cor    { COR_OFF, COR_VERDE, COR_VERMELHO };

Estado estado = ST_ENTRADA;

String telefone = "";
unsigned long marcaResultado = 0;

struct Resposta {
  int    codigo = 0;    // HTTP status (0 = falha de rede)
  String nome   = "";
  int    ganhos = 0;
  int    total  = 0;
};

// =====================================================================
// PARAMETROS
// =====================================================================

const uint16_t HTTP_TIMEOUT_MS  = 8000;
const uint16_t TEMPO_RESULTADO  = 4500;
const uint8_t  TAM_MIN_TELEFONE = 10;
const uint8_t  TAM_MAX_TELEFONE = 11;

#define PINO_SDA      4    // D2
#define PINO_SCL      5    // D1
#define ENDERECO_LCD  0x27 // use 0x3F se o display nao responder

LiquidCrystal_I2C lcd(ENDERECO_LCD, 16, 2);

// =====================================================================
// TECLADO 4x3  -- pinagem confirmada em bancada
//
// Duas exigencias desta montagem:
//
//   SERIAL_TX_ONLY, porque o RX (GPIO3) e usado como coluna. Sem ele
//   a UART toma o pino de volta e a coluna 3 6 9 # para de responder.
//
//   O D0 (GPIO16) como coluna nao tem pull-up interno. Em teoria isso
//   o desqualifica; na pratica funciona nesta montagem. Se um dia a
//   coluna 2 5 8 0 falhar, e o primeiro suspeito.
// =====================================================================

const byte LINHAS  = 4;
const byte COLUNAS = 3;

char teclas[LINHAS][COLUNAS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};

// Pinagem determinada empiricamente: os fios deste teclado estao
// INTERCALADOS, nao seguem a sequencia de quatro linhas seguidas de
// tres colunas. A ordem abaixo foi confirmada em bancada, tecla a
// tecla.
byte linhas[LINHAS]   = { 14,  0, 12, 13 };  // D5  D3  D6  D7
byte colunas[COLUNAS] = { 16,  3,  2 };      // D0  RX  D4

Keypad teclado = Keypad(makeKeymap(teclas), linhas, colunas, LINHAS, COLUNAS);

char lerTecla() { return teclado.getKey(); }

// =====================================================================
// SETUP
// =====================================================================

void setup() {

  // SERIAL_TX_ONLY libera o GPIO3 (RX) para o teclado. Os Serial.print
  // continuam saindo no monitor; so nao da para enviar texto do
  // computador para a placa, o que este projeto nao usa.
  Serial.begin(115200, SERIAL_8N1, SERIAL_TX_ONLY);

  Wire.begin(PINO_SDA, PINO_SCL);
  lcd.init();
  lcd.backlight();
  telaSimples("FideliZa", "Iniciando...");

  teclado.setDebounceTime(50);
  randomSeed(RANDOM_REG32);   // TRNG do chip, para o uuid

  conectarWiFi();
  mostrarEntrada();
}

// =====================================================================
// LOOP
// =====================================================================

void loop() {

  // Sai da tela de resultado sem travar o processador com delay()
  if (estado == ST_RESULTADO) {
    if (millis() - marcaResultado >= TEMPO_RESULTADO) {
      corLed(COR_OFF);
      mostrarEntrada();
    }
    return;
  }

  char tecla = teclado.getKey();
  if (!tecla) return;
  if (tecla >= '0' && tecla <= '9') {
    if (telefone.length() < TAM_MAX_TELEFONE) {
      telefone += tecla;
      atualizarLinhaTelefone();
    }
    return;
  }

  if (tecla == '*') {
    if (telefone.length() > 0) {
      telefone.remove(telefone.length() - 1);
      atualizarLinhaTelefone();
    }
    return;
  }

  if (tecla == '#') {
    if (telefone.length() < TAM_MIN_TELEFONE) {
      mostrarResultado("Telefone curto", "Use DDD + numero", false);
      return;
    }
    registrarVisita();
  }
}

// =====================================================================
// ENVIO AO SERVIDOR
// =====================================================================

void registrarVisita() {

  telaSimples("Registrando...", "Aguarde");

  if (WiFi.status() != WL_CONNECTED) conectarWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    mostrarResultado("Sem WiFi", "Chame a gestora", false);
    return;
  }

  Resposta r = chamarAPI();

  switch (r.codigo) {

    case 200:
    case 201: {
      // Mostra o NOME, nunca o telefone: a tela fica virada para a
      // loja, e o numero e dado pessoal.
      String l1 = r.nome.length() ? r.nome : String("Cliente");
      if (l1.length() > 16) l1 = l1.substring(0, 16);

      String l2 = "Pontos: " + String(r.total);
      if (r.ganhos > 0) {
        String alt = "+" + String(r.ganhos) + " pt | Tot " + String(r.total);
        if (alt.length() <= 16) l2 = alt;
      }

      mostrarResultado(l1, l2, true);
      break;
    }

    case 400:
      mostrarResultado("Nao pontuado", "Ver no painel", false);
      break;

    case 401:
      mostrarResultado("Terminal negado", "Chave invalida", false);
      break;

    case 404:
      mostrarResultado("Nao cadastrado", "Cadastre no site", false);
      break;

    case 409:
      mostrarResultado("Ja registrado", "Volte depois", false);
      break;

    case 0:
      mostrarResultado("Erro de conexao", "Tente de novo", false);
      break;

    default:
      mostrarResultado("Erro no servidor", "Cod " + String(r.codigo), false);
      break;
  }
}

Resposta chamarAPI() {

  Resposta r;

#if USAR_HTTPS
  // BearSSL: setInsecure() aceita o certificado sem validar a
  // identidade do servidor. O trafego continua criptografado, mas nao
  // ha garantia de com QUEM se esta falando. E o caminho pratico no
  // ESP8266, que nao tem espaco para a cadeia de certificados nem
  // relogio para checar validade.
  WiFiClientSecure cliente;
  cliente.setInsecure();
#else
  WiFiClient cliente;
#endif

  HTTPClient http;

  String url = String(API_BASE) + String(API_ROTA);

  // TLS consome cerca de 22 KB de heap. Se este numero cair abaixo de
  // uns 25000 em modo HTTPS, a conexao falha por falta de memoria.
  if (!http.begin(cliente, url)) {
    return r;
  }

  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  String payload = "{\"telefone\":\"" + telefone +
                   "\",\"uuid\":\"" + gerarUUID() + "\"}";
  r.codigo = http.POST(payload);

  if (r.codigo > 0) {
    String resposta = http.getString();
    JsonDocument doc;
    if (!deserializeJson(doc, resposta)) {
      // Aceita a resposta aninhada ou plana, para nao depender do
      // formato exato que o backend vier a adotar.
      r.nome   = doc["cliente"]["nome"] | doc["nome"] | "";
      r.ganhos = doc["compra"]["pontos_gerados"] | doc["pontos_gerados"] | 0;
      r.total  = doc["saldo_atualizado"]
               | doc["cliente"]["pontos_acumulados"]
               | doc["pontos_total"] | 0;
    }
  } else {
    r.codigo = 0;
  }

  http.end();
  return r;
}

// Identificador unico da operacao: chip + tempo ligado + aleatorio de
// hardware. Permite ao servidor reconhecer reenvio por falha de rede.
String gerarUUID() {
  char buf[48];
  snprintf(buf, sizeof(buf), "%06x-%08x-%08x",
           (unsigned)ESP.getChipId(),
           (unsigned)millis(),
           (unsigned)RANDOM_REG32);
  return String(buf);
}

void conectarWiFi() {

  if (WiFi.status() == WL_CONNECTED) return;

  telaSimples("Conectando...", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 12000) {
    delay(250);
  }
}

// =====================================================================
// TELAS  (o display tem 16 colunas: nenhuma string passa disso)
// =====================================================================

void mostrarEntrada() {
  estado   = ST_ENTRADA;
  telefone = "";
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Digite o tel:");
  atualizarLinhaTelefone();
}

void atualizarLinhaTelefone() {
  lcd.setCursor(0, 1);
  lcd.print("                ");
  lcd.setCursor(0, 1);
  lcd.print(formatarTelefone(telefone));
}

String formatarTelefone(const String& t) {
  size_t n = t.length();
  if (n == 0) return "_";
  String s = "";
  for (size_t i = 0; i < n; i++) {
    if (i == 0) s += '(';
    if (i == 2) s += ") ";
    if ((n > 10 && i == 7) || (n <= 10 && i == 6)) s += '-';
    s += t[i];
  }
  return s;
}

void mostrarResultado(const String& l1, const String& l2, bool ok) {
  telaSimples(l1, l2);
  corLed(ok ? COR_VERDE : COR_VERMELHO);
  estado = ST_RESULTADO;
  marcaResultado = millis();
}

void telaSimples(const String& l1, const String& l2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(l1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(l2.substring(0, 16));
}

// =====================================================================
// RETORNO VISUAL
//
// Usa o backlight do proprio LCD, sem componente adicional. O que
// distingue sucesso de falha e o RITMO: o backlight SEMPRE termina
// aceso, senao a mensagem de erro ficaria ilegivel na tela escura.
// =====================================================================

void corLed(Cor c) {
  switch (c) {

    case COR_VERDE:                       // 2 piscadas lentas
      for (byte i = 0; i < 2; i++) {
        lcd.noBacklight(); delay(120);
        lcd.backlight();   delay(120);
      }
      break;

    case COR_VERMELHO:                    // 4 piscadas rapidas
      for (byte i = 0; i < 4; i++) {
        lcd.noBacklight(); delay(60);
        lcd.backlight();   delay(60);
      }
      break;

    default:
      lcd.backlight();
      break;
  }
}
