# Camada de Banco de Dados — IT Clube

Este diretório centraliza a arquitetura, esquemas relacionais, scripts de migração (Alembic/Flask-Migrate) e rotinas de semeadura (*seeding*) de dados do sistema **IT Clube**.

---

## 1. Estrutura de Diretórios

```
database/
├── migrations/          # Histórico versionado de migrações (Flask-Migrate / Alembic)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/        # Arquivos de migração sequenciais
│       ├── 0001_schema_legado.py
│       ├── 0002_recompensas_persistentes.py
│       ├── 0003_evolucao_completa.py
│       └── 0004_it_clube_regras.py
├── schema/              # Definições conceituais e diagramas DDL
├── scripts/             # Scripts utilitários de manutenção SQL
└── seeds/               # Semeadura de dados com credenciais de demonstração
    └── seed.py
```

---

## 2. Modelagem Relacional

O banco de dados foi estruturado com foco em rastreabilidade, imutabilidade e integridade referencial:

1. **`usuario`**: Funcionários da loja (Proprietária, Gerente, Vendedora) com controle RBAC granular. Senhas armazenadas com hash PBKDF2-SHA256 (`generate_password_hash`).
2. **`cliente`**: Clientes do programa de fidelidade identificados por telefone único e e-mail único. Possuem senha com hash e saldo consolidado de pontos (`pontos_acumulados`).
3. **`compra`**: Registro de transações do PDV. No IT Clube, **1 compra gera exatamente 1 ponto**, desacoplado de valor financeiro.
4. **`recompensa`**: Catálogo persistente de prêmios gerenciado pela proprietária/gerente, contendo custo em pontos, quantidade disponível, validade e tipo.
5. **`resgate`**: Registro de consumo de pontos e validação física de prêmios, executado e confirmado exclusivamente pela vendedora/gestora no balcão da loja.
6. **`movimentacao_pontos`**: Ledger imutável de movimentação atômica de pontos (`COMPRA`, `RESGATE`, `AJUSTE_MANUAL`, `EXPIRACAO`), garantindo auditoria contábil de cada ponto emitido ou debitado.
7. **`auditoria`**: Trilha de auditoria administrativa e de segurança registrando IP, User-Agent, entidade modificada, ação e alterações (sem armazenar senhas ou dados sensíveis em texto plano).

---

## 3. Histórico de Migrações

- **`0001_schema_legado`**: Esquema inicial das entidades `usuario`, `cliente`, `compra` e `resgate`.
- **`0002_recompensas_persistentes`**: Introdução da tabela `recompensa` com controle de estoque e vigência.
- **`0003_evolucao_completa`**: Adição de RBAC nos usuários, soft delete, ledger `movimentacao_pontos` e tabela `auditoria`.
- **`0004_it_clube_regras`**: Unicidade de e-mail do cliente, default de 1 ponto por compra e alinhamento com a marca IT Clube.

---

## 4. Como Executar Migrações e Seeds

### Aplicar Migrações
```bash
flask db upgrade
```

### Reverter Última Migração
```bash
flask db downgrade
```

### Popular Dados Iniciais (Seed)
Para criar usuários padrão e clientes de teste para demonstração:
```bash
python database/seeds/seed.py
```

> **Atenção:** As senhas iniciais geradas pelo script de seed obedecem às políticas de complexidade do sistema (mínimo 8 caracteres, maiúsculas, minúsculas e números).
