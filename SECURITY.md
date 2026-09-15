# Política de Segurança — IT Clube

Este documento descreve as políticas de segurança, diretrizes de relato de vulnerabilidades e arquitetura de proteção implementadas no sistema **IT Clube**.

---

## 1. Versões Suportadas

As seguintes versões do software recebem ativamente atualizações e patches de segurança:

| Versão | Suportada | Notas |
| :--- | :---: | :--- |
| `2.0.x` (IT Clube) | :white_check_mark: | Versão atual com arquitetura endurecida e RBAC segregado |
| `< 2.0.0` (FideliZa Legado) | :x: | Descontinuada; migração imediata recomendada |

---

## 2. Relatando uma Vulnerabilidade

A equipe de engenharia do IT Clube leva a segurança a sério. Se você identificar uma falha ou vulnerabilidade em nossa aplicação:

1. **Não divulgue publicamente** a falha até que ela tenha sido devidamente analisada e mitigada.
2. Envie um e-mail com os detalhes técnicos, passos de reprodução (PoC) e impacto potencial para: **`seguranca@itclube.com.br`**.
3. Nossa equipe responderá em até 48 horas úteis confirmando o recebimento e o plano de mitigação.

---

## 3. Controles e Práticas de Segurança Implementadas

O sistema foi submetido a um processo de hardening rigoroso, cobrindo:

- **Autenticação Segura:**
  - Armazenamento de credenciais exclusivamente com PBKDF2-HMAC-SHA256 e sal aleatório criptográfico.
  - Eliminação de qualquer mecanismo ou senha de emergência *hardcoded*.
  - Deserialização de sessão estrita (`u_<id>` e `c_<id>`), impedindo colisão e escalação vertical de privilégio.
- **Proteção de API & BOLA/IDOR:**
  - Controle de acesso granular em 100% dos endpoints REST via `@login_required` e `@permissao_requerida`.
  - Clientes finais restritos estritamente aos seus próprios dados através da rota `/api/clientes/me`.
- **Integridade Contábil de Pontos:**
  - Ledger transacional imutável (`movimentacao_pontos`) que audita todas as emissões e débitos.
  - Bloqueio completo de auto-resgate: clientes finais recebem `403 Forbidden` ao tentar forçar resgates diretamente; a baixa é prerrogativa do caixa.
- **Proteção contra CSRF e XSS:**
  - Validação de tokens CSRF em todas as requisições com mutação de estado (`POST`, `PUT`, `DELETE`).
  - Sanitização rigorosa de inputs e auto-escaping de templates HTML.
- **Isolamento de Contêineres:**
  - Imagem Docker baseada em `python:3.12-slim` com execução sob usuário de privilégios mínimos (`appuser`, UID 10001).
  - Nenhum arquivo `.env` ou segredo persistido dentro das camadas da imagem.
- **Trilha de Auditoria Sanitizada:**
  - Logs de auditoria gravam eventos administrativos e sensíveis sem jamais expor senhas, tokens ou dados pessoais protegidos.
