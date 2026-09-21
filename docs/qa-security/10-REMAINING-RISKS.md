# 10 — Riscos Remanescentes e Recomendações Operacionais

Conforme as diretrizes de segurança da informação, nenhuma aplicação pode ser considerada 100% livre de riscos. Este documento cataloga os riscos residuais inerentes à operação do sistema e as recomendações de mitigação para ambiente produtivo.

---

## 1. Riscos Residuais Identificados

### 1.1 Vetor de Ataque Físico ao Hardware IoT (ESP8266)
- **Descrição**: O terminal IoT físico armazena em firmware o token `IOT_DEVICE_KEY` para pontuação automática no caixa.
- **Risco**: Caso o hardware seja fisicamente roubado ou tenha sua memória flash extraída via interface serial/JTAG, o atacante poderá obter a chave e forjar pontuações.
- **Mitigação Recomendada**:
  1. Utilizar firmware protegido contra leitura de memória (Read-Out Protection);
  2. Implementar rotação periódica da chave `IOT_DEVICE_KEY` através de variáveis de ambiente no servidor e atualização OTA (*Over-The-Air*) no dispositivo;
  3. Manter o limite de 1 ponto por transação e monitorar picos anômalos de pontuação na auditoria.

### 1.2 Rate Limiting Baseado em IP sob Proxies Reversos
- **Descrição**: O rate limiting é gerenciado por IP remoto via Flask-Limiter. Caso o proxy reverso (ex: Nginx, Cloudflare ou Render) não propague corretamente o cabeçalho `X-Forwarded-For`, todas as requisições podem compartilhar o mesmo contador de IP ou contornar limites.
- **Mitigação Recomendada**:
  - Garantir o uso do middleware `ProxyFix(app.wsgi_app, x_for=1, x_proto=1)` (já configurado em `ProductionConfig`) e restringir o tráfego da aplicação estritamente à rede do proxy reverso de borda.

### 1.3 Sessões Armazenadas em Cookie do Cliente (Client-side Session)
- **Descrição**: As sessões do Flask utilizam cookies criptograficamente assinados pelo `SECRET_KEY`. Embora protegidos contra adulteração e leitura indevida (`HttpOnly`, `SameSite=Lax`), revogações instantâneas de tokens individuais (ex: forçar logout de todos os dispositivos de uma só vez) exigem invalidação centralizada.
- **Mitigação Recomendada**:
  - Para alta escala, considerar a migração futura do armazenamento de sessões para um cache em memória (ex: Redis com Flask-Session), permitindo revogação remota granular por usuário.

---

## 2. Recomendações Operacionais de Produção (Checklist de Deploy)

1. **Gestão de Segredos e Variáveis de Ambiente**:
   - Nunca comitar o arquivo `.env` no GitHub;
   - Gerar `SECRET_KEY` criptograficamente aleatório e forte em produção (`python -c "import secrets; print(secrets.token_hex(32))"`);
   - Definir `FLASK_ENV=production` e `SESSION_COOKIE_SECURE=True`.
2. **Conexão com Banco de Dados na Nuvem (Neon PostgreSQL)**:
   - Forçar sempre o parâmetro `sslmode=require` e `channel_binding=require` na URL do banco;
   - Manter backups automatizados e logs de transação habilitados na plataforma de nuvem.
3. **WAF e Proteção de Borda (Web Application Firewall)**:
   - Posicionar a aplicação atrás de um WAF (ex: Cloudflare) com regras de mitigação de DDoS e bloqueio de varreduras automatizadas.
4. **Monitoramento e Alertas Ativos**:
   - Configurar alertas de notificação em canais de operação para eventos de `LOGIN_FALHA` consecutivos ou tentativas de injeção registradas pelo log do Flask/Gunicorn.
