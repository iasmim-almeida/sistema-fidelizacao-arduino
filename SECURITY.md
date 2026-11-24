# Segurança do IT Clube

## Controles atuais

- Hash de senhas pelo Werkzeug com salt individual.
- Sessões Flask-Login com cookies `HttpOnly`, `Secure` em produção e `SameSite=Lax`.
- CSRF global para operações web autenticadas.
- A rota de compra é isenta no middleware para permitir IoT, mas valida CSRF manualmente quando a origem é uma sessão administrativa.
- Logout somente por `POST` e protegido por CSRF.
- ORM e expressões SQLAlchemy parametrizadas.
- Resgate valida custo, saldo, validade, status e estoque no servidor.
- Setup web exige `INITIAL_SETUP_TOKEN` em produção e falha fechado se ausente.
- Produção exige `SECRET_KEY`, `IOT_DEVICE_KEY` forte e `DATABASE_URL` PostgreSQL.
- Assets web são servidos localmente; a CSP não libera CDNs externas.

## Histórico e logs

O histórico transacional registra tipo, origem, pontos, saldo anterior, saldo posterior e motivo. Ele é parte da regra de negócio e não deve ser removido.

O antigo módulo de auditoria operacional foi descontinuado por requisito. Eventos técnicos relevantes usam o logging da aplicação sem persistir senhas, tokens ou payloads sensíveis.

## IoT

- A chave antes versionada deve ser considerada comprometida.
- Credenciais são provisionadas por `secrets.h`, que é ignorado pelo Git.
- `X-Idempotency-Key` evita crédito duplicado quando enviado pelo terminal.
- O protótipo HTTP é apenas para rede local descartável. Comunicação externa requer HTTPS com validação da cadeia de certificados.
- A rotação da chave real depende de autorização e não foi executada.

## Limitações conhecidas

- O rate limiting usa memória de processo e não é global entre workers.
- Scripts e estilos inline ainda exigem `'unsafe-inline'` na CSP.
- Idempotência é compatível e opcional para clientes legados; o firmware definitivo deve sempre enviar a chave.
- A concorrência real precisa ser validada em PostgreSQL descartável antes do deploy.

## Segredos

Nunca versionar `.env`, `secrets.h`, URLs Neon, chaves do Render ou credenciais reais. Em caso de exposição, revogar o segredo no provedor, provisionar um novo valor e só então atualizar os consumidores autorizados.
