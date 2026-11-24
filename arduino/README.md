# Firmware ESP8266 do IT Clube

## Estado do material versionado

O arquivo `esp8266/fidelizacao_esp8266.ino` é um protótipo de conectividade: envia um telefone para `POST /api/compras/` e sinaliza respostas de sucesso no LED D2. Ele não implementa o terminal descrito no TCC.

Foram pesquisadas todas as branches locais, remotas e versões históricas disponíveis. Nenhuma contém código para teclado matricial ou LCD. O firmware acadêmico esperado utiliza ESP8266 NodeMCU, teclado de 12 teclas, LCD 16×2 I2C, entrada de telefone e retorno pelo display, mas suas pinagens e seu código-fonte precisam ser fornecidos pela equipe. Não se deve inferir ou inventar essas ligações.

## Contrato da API

- Endpoint: `POST /api/compras/`
- Headers: `Content-Type`, `X-Device-Key` e, para proteção contra duplicidade, `X-Idempotency-Key`
- Corpo: `{"telefone":"DDD_NUMERO"}`
- `201 Created`: compra nova; um ponto creditado
- `200 OK` com `duplicada=true`: operação já processada; nenhum ponto adicional
- `401 Unauthorized`: credencial do dispositivo ausente ou inválida

Uma compra válida corresponde a exatamente um ponto. Não existe valor monetário no contrato.

## Provisionamento sem credenciais versionadas

1. Copie `esp8266/secrets.example.h` para `esp8266/secrets.h`.
2. Preencha Wi-Fi, URL e uma chave IoT nova na estação usada para gravar o dispositivo.
3. Nunca faça commit de `secrets.h`; o arquivo está no `.gitignore`.
4. Configure a mesma chave em `IOT_DEVICE_KEY` no ambiente do backend somente durante uma janela de rotação aprovada.
5. Grave e teste o terminal antes de revogar a chave anterior.

A chave anteriormente presente no firmware está no histórico público e deve ser considerada comprometida. Sua rotação no Render não foi executada.

## HTTPS

O protótipo atual usa `WiFiClient` e é adequado apenas para uma rede local descartável de demonstração. Para acesso ao Render ou a qualquer rede não confiável, o firmware real deve usar `BearSSL::WiFiClientSecure`, URL HTTPS e uma CA raiz ou cadeia de certificados validada. Não usar `setInsecure()`.

O certificado deve ser obtido do hostname definitivo e atualizado de forma coordenada. Como o hostname e o firmware real não estão disponíveis, o material de CA não foi inventado nem incluído.

## Prevenção de duplicidade

O backend aceita `X-Idempotency-Key` de 8 a 128 caracteres. Repetir a mesma chave devolve o resultado anterior sem creditar novo ponto. O protótipo gera uma chave por envio; o firmware definitivo deve persistir um contador ou identificador de operação para evitar repetição também após reinicialização.

## Compilação do protótipo

1. Instale o pacote ESP8266 na Arduino IDE.
2. Selecione `NodeMCU 1.0 (ESP-12E Module)`.
3. Crie `secrets.h` conforme as instruções acima.
4. Compile o sketch antes de conectar a placa.
5. A gravação no hardware exige autorização e coordenação com a equipe.
