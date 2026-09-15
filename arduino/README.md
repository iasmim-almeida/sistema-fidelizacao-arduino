# Módulo IoT e Terminal Físico — IT Clube

Este diretório contém os códigos de firmware, especificações de montagem eletrônica e documentação da integração de hardware do sistema **IT Clube** via microcontrolador **ESP8266 NodeMCU**.

---

## 1. Visão Geral da Integração

O terminal físico de balcão permite registrar pontuações de clientes diretamente no momento da compra. O microcontrolador conecta-se à rede Wi-Fi local da loja e despacha requisições HTTP autenticadas para o backend do IT Clube.

Ao receber a confirmação de pontuação computada com sucesso (`HTTP 201 Created`), o terminal físico aciona um sinalizador luminoso (LED Verde).

> **Regra de Pontuação IT Clube:** Cada requisição de compra computada adiciona rigorosamente **1 ponto** à conta do cliente no sistema.

---

## 2. Componentes de Hardware Utilizados

| Componente | Quantidade | Descrição / Função |
| :--- | :---: | :--- |
| **ESP8266 NodeMCU (ESP-12E)** | 1 | Microcontrolador Wi-Fi principal de comunicação |
| **LED Difuso Verde (5mm)** | 1 | Sinalizador visual de sucesso de pontuação |
| **Resistor de 220Ω (1/4W)** | 1 | Limitador de corrente para o LED Verde |
| **Protoboard (830 ou 400 pontos)** | 1 | Plataforma de prototipagem |
| **Cabos Jumper Macho-Macho** | 4 | Conexões de sinal e terra (GND) |
| **Fonte / Cabo Micro-USB 5V/1A** | 1 | Alimentação estável para a placa NodeMCU |

---

## 3. Pinagem e Esquemático de Ligação

```
  +---------------------------------------------------+
  |                 ESP8266 NodeMCU                   |
  |                                                   |
  |   [ D2 / GPIO4 ] ------[ Resistor 220Ω ]----+---->| (Ânodo LED Verde)
  |                                                    |
  |   [ GND ] -----------------------------------------> (Cátodo LED Verde)
  +---------------------------------------------------+
```

### Detalhamento das Conexões:
1. **Pino D2 (GPIO4)** do NodeMCU conectado a um terminal do **Resistor de 220Ω**.
2. O outro terminal do resistor conectado ao **terminal longo (Ânodo, +)** do **LED Verde**.
3. O **terminal curto (Cátodo, -)** do LED Verde conectado diretamente ao pino **GND** do NodeMCU.

---

## 4. Protocolo de Comunicação & Segurança (PSK)

Para impedir injeção não autorizada de compras ou pontos por terceiros na rede local, o ESP8266 utiliza **chave de dispositivo pré-compartilhada (Pre-Shared Key - PSK)**:

- **Endpoint de Destino:** `POST /api/compras/`
- **Cabeçalho Obrigatório:** `X-Device-Key: <CHAVE_CONFIGURADA_NO_ENV>`
- **Content-Type:** `application/json`
- **Corpo da Mensagem:**
  ```json
  {
    "telefone": "11999991111",
    "valor": 50.00
  }
  ```

### Tratamento de Respostas pelo Firmware:
- **`HTTP 201 Created`**: Compra registrada e 1 ponto adicionado. O pino `D2` entra em nível alto (`HIGH`) por 1.500 ms (1,5 segundos), piscando o LED verde.
- **`HTTP 401 Unauthorized`**: Chave de dispositivo incorreta ou ausente. O LED permanece desligado e o erro é logado na porta Serial (115200 bps).
- **`HTTP 404 / 400`**: Telefone não encontrado ou dados inválidos.

---

## 5. Instruções de Compilação e Gravação

1. Abra a **Arduino IDE** (versão 2.0 ou superior).
2. Certifique-se de que o pacote de placas ESP8266 está instalado (`Gerenciador de Placas -> esp8266 by ESP8266 Community`).
3. Selecione a placa: **NodeMCU 1.0 (ESP-12E Module)**.
4. Abra o arquivo [`arduino/esp8266/fidelizacao_esp8266.ino`](file:///C:/dev/Projetotc/FideliZa-integrado/sistema-fidelizacao-integrado/arduino/esp8266/fidelizacao_esp8266.ino).
5. Configure suas credenciais de Wi-Fi e endereço do backend:
   ```cpp
   const char* SSID     = "SUA_REDE_WIFI";
   const char* SENHA    = "SUA_SENHA_WIFI";
   const char* SERVIDOR = "http://<IP_DO_SERVIDOR>:5000/api/compras/";
   ```
6. Conecte o cabo USB ao computador, selecione a porta COM correspondente e clique em **Upload**.
7. Abra o Monitor Serial a **115200 baud** para acompanhar o status da conexão Wi-Fi e das chamadas HTTP.
