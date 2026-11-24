# Checklist Pré-PR — IT Clube

> **Registro histórico:** os comandos e contagens abaixo pertencem a uma versão anterior. Consulte `TESTES_LOCAL.md`.

Este checklist é obrigatório para desenvolvedores, tech leads e revisores antes de mesclar qualquer alteração para as branches principais (`main`, `staging` ou `feat/*`).

---

## 1. Verificações Estáticas & Compilação
- [ ] **Sintaxe Python íntegra:**
  ```bash
  python -m compileall backend run.py
  ```
- [ ] **Sem dependências conflitantes:**
  ```bash
  pip check
  ```
- [ ] **Nenhum arquivo `.env` ou arquivo de credenciais adicionado ao Git:**
  ```bash
  git status --ignored
  ```
- [ ] **Sem `print()`, debuggers (`breakpoint()`, `pdb`) ou senhas hardcoded.**

---

## 2. Bateria de Testes Automatizados
- [ ] **Suíte Unitária e Integração (100% de Aprovação):**
  ```bash
  python -m unittest discover backend/tests
  ```
  *Total esperado: 100 testes aprovados (0 falhas, 0 erros).*
- [ ] **Auditoria de Segurança SAST / DAST Local:**
  ```bash
  python test_security_audit.py
  ```
  *Total esperado: 7 testes aprovados (OWASP, Anti-CSRF, PBKDF2, RBAC, Bypass IoT).*
- [ ] **Testes de Hardening e Concorrência:**
  ```bash
  python -m unittest backend.tests.test_production_hardening
  ```

---

## 3. Banco de Dados & Migrações
- [ ] **Migrações executam do zero sem erro:**
  ```bash
  flask db upgrade
  ```
- [ ] **Nenhuma migração duplicada ou com `down_revision` conflitante.**
- [ ] **Restrições de integridade ativas:** Check constraints de pontos não-negativos e validação de `nivel_acesso`.

---

## 4. Regras Fundamentais de Negócio
- [ ] **Regra de Pontuação Unificada:** Cada compra registrada gera rigorosamente **+1 ponto**, sem campo financeiro.
- [ ] **Bloqueio de Auto-Resgate:** Clientes finais são terminantemente impedidos de realizar auto-resgate (`POST /api/resgates/` retorna 403).
- [ ] **Autoatendimento Restrito:** Cliente só altera dados do próprio perfil (`/perfil`) e visualiza extrato pessoal.
- [ ] **Anti Role-Injection:** Tentativas de injeção de cargo no cadastro público são neutralizadas.

---

## 5. Simulação de Produção Local
- [ ] **A aplicação inicializa em modo produção sob Gunicorn com headers de segurança:**
  ```bash
  FLASK_ENV=production SECRET_KEY="chave-de-teste-32-chars-longa" gunicorn --bind 127.0.0.1:5000 --workers 2 --threads 2 --timeout 30 --no-control-socket run:app
  ```
- [ ] **Endpoint `/health` responde 200 OK com HSTS e CSP.**

---

**Critério de Aprovação do Gate:**
Somente abra o Pull Request quando **TODOS** os itens acima estiverem marcados como `[x]`.
