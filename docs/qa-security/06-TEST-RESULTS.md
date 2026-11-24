# 06 — Resultados da Execução Inicial de Testes

> **Resultado histórico:** não apresentar estas contagens como execução ou cobertura atual.

Relatório dos testes automatizados existentes executados no início do ciclo de QA e Segurança.

---

## 1. Resumo da Execução de Linha de Base (Baseline)

- **Comando**: `python3 -m unittest discover -s tests`
- **Ambiente**: Local / Linux / Python 3.12 / SQLite in-memory isolado para testes
- **Configuração de Teste**: `TestingConfig` (CSRF desabilitado nos testes unitários legados onde aplicável, limiter desabilitado para não poluir os testes de unidade, timeouts de conexão seguros).

```text
TOTAL DE TESTES: 114
PASS: 114
FAIL: 0
ERROR: 0
SKIPPED: 0
TEMPO DE EXECUÇÃO: 29.917s
RESULTADO GERAL: OK
```

---

## 2. Distribuição por Arquivo de Teste

| Arquivo de Teste | Quantidade | Status | Escopo Avaliado |
| :--- | :---: | :---: | :--- |
| [`test_pontos_ledger.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_pontos_ledger.py) | 12 | PASS | Atomicidade do saldo, integridade contábil, saldo não-negativo, histórico imutável. |
| [`test_setup_seguro.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_setup_seguro.py) | 14 | PASS | Provisionamento seguro `/setup`, bloqueio de re-execução, proteção CSRF, validação de senha. |
| [`test_itclube_regras.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_itclube_regras.py) | 18 | PASS | Regra 1 compra = 1 ponto, integração de compras com histórico, auditoria sem vazamento de senhas. |
| [`test_clientes_gestao.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_clientes_gestao.py) | 11 | PASS | CRUD de clientes, busca por telefone e texto, ativação/desativação, ajuste manual de saldo. |
| [`test_rbac.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_rbac.py) | 6 | PASS | Permissões granulares da vendedora, bloqueio de cliente em áreas restritas, rejeição de inativos. |
| [`test_troca_senha.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_troca_senha.py) | 14 | PASS | Redefinição de senha de administrador, blacklist, complexidade, CSRF obrigatório. |
| [`test_funcionarios.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_funcionarios.py) | 11 | PASS | Gestão de equipe interna, criação e edição de colaboradoras, proteção contra auto-desativação. |
| [`test_recompensas.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_recompensas.py) | 10 | PASS | Catálogo de prêmios, controle de estoque atômico, expiração por data e pausa de recompensas. |
| [`test_auditoria.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_auditoria.py) | 5 | PASS | Trilha de auditoria administrativa, mascaramento de campos confidenciais, paginação de logs. |
| [`test_cadastro.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_cadastro.py) | 8 | PASS | Auto-cadastro público web de clientes via formulário com CSRF ativo e regras de duplicidade. |
| [`test_cliente_primeiro_acesso.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_cliente_primeiro_acesso.py) | 5 | PASS | Cadastro por vendedora com senha inicial, identificação no login e bloqueio até a troca de senha. |

---

## 3. Diagnóstico e Oportunidades Identificadas

Apesar de a suíte inicial ter obtido 100% de aprovação funcional, a análise de segurança estática e dinâmica identificou as seguintes lacunas a serem corrigidas e validadas:

1. Ausência de validação estrita do perfil no endpoint de login de vendedoras (`/auth/login`), permitindo que clientes autenticassem no portal errado;
2. Ausência de validação estrita do perfil no endpoint de login de clientes (`/auth/cliente/login`), permitindo que vendedoras autenticassem no portal do cliente;
3. Falta de validação de tamanho mínimo e regex de e-mail no endpoint de cadastro direto de clientes (`POST /api/clientes/`);
4. Falta de validação estrita de tipo para `id_cliente` no endpoint de compras;
5. Ausência dos cabeçalhos modernos `Permissions-Policy` e `Cross-Origin-Opener-Policy`.
