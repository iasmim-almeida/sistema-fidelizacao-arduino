# Guia de Rollback e Recuperação de Desastres — FideliZa / IT Clube

Este documento define os procedimentos de emergência para contingência, reversão de deploy (*application rollback*), recuperação de banco de dados (*database recovery*) e contenção de vazamento de segredos na plataforma Render e PostgreSQL Neon.

---

## 1. Cenários de Rollback

| Cenário | Gravidade | Tempo Alvo (RTO) | Ação Recomendada |
| :--- | :--- | :--- | :--- |
| **Falha de Código pós-deploy** (Erro 500, quebra de rota) | Alta | < 5 minutos | Instant Rollback no Render para o último deploy funcional |
| **Corrupção de Dados / Falha de Migração** | Crítica | < 15 minutos | Restauração de Branch / PITR no Neon + Rollback no Render |
| **Comprometimento de Segredos (`SECRET_KEY`, Senha do Banco)** | Crítica | < 10 minutos | Rotação imediata das variáveis de ambiente e reinicialização |
| **Indisponibilidade do Provedor de Nuvem** | Alta | < 30 minutos | Ativação de réplica ou ambiente secundário |

---

## 2. Procedimento de Rollback de Aplicação (Render Web Service)

### Opção A: Rollback Imediato via Dashboard Render (Recomendado - 60 segundos)
1. Acesse o painel do serviço no Render: `https://dashboard.render.com/web/<service-id>`.
2. Clique na aba **Events** ou **Deploys**.
3. Localize o último deploy que estava com status **Live** e funcionando perfeitamente antes da falha.
4. Clique nos três pontos (`...`) ao lado do deploy anterior e selecione **Rollback to this deploy**.
5. O Render ativará imediatamente a imagem anterior sem necessidade de rebuild completo.
6. Acompanhe a inicialização dos workers e confirme o retorno do status `200 OK` no endpoint `/health`.

### Opção B: Rollback via Git Revert (Controle de Versão)
Caso seja necessário reverter a alteração no histórico do repositório:
```bash
# 1. Certifique-se de estar na branch principal
git checkout feat/banco-nuvem   # ou main

# 2. Crie um commit de reversão do commit problemático
git revert <HASH_DO_COMMIT_COM_ERRO> -m 1  # se for merge commit, ou direto git revert <HASH>

# 3. Empurre a reversão para o repositório remoto
git push origin feat/banco-nuvem

# 4. O Render detectará o novo commit e iniciará o build automaticamente
```

---

## 3. Estratégia de Rollback de Banco de Dados (PostgreSQL Neon)

### 3.1 Entendendo o Comportamento das Migrações Alembic (`0005` e `0006`)
> [!IMPORTANT]
> As migrações `0005_fix_foreign_keys_and_enums.py` e `0006_unified_schema_consolidation.py` realizam consolidação definitiva de dados das tabelas legadas (`cliente`, `recompensa`, `resgate`, `compra`) para o modelo unificado (`usuario`, `produto`, `historico`).
> 
> Por razões de **integridade e segurança da informação**, as funções `downgrade()` dessas migrações foram propositalmente configuradas para disparar um `RuntimeError("Downgrade automático bloqueado...")`.
> 
> **NÃO force a execução de `flask db downgrade` em produção.** Uma tentativa de desmontar tabelas consolidadas via script causará perda irreversível de integridade referencial.

### 3.2 Procedimento Seguro: Point-in-Time Recovery (PITR) e Branching no Neon
A arquitetura *serverless* e baseada em *Copy-on-Write* do PostgreSQL Neon permite restaurar o banco para qualquer segundo no passado:

1. **Acessar o Console Neon**:
   - Faça login em `https://console.neon.tech/app/projects/<seu-project-id>`.
2. **Criar um Novo Branch a partir de um Momento no Passado (PITR)**:
   - Navegue até a aba **Branches**.
   - Clique em **New Branch**.
   - Selecione a branch `main` como pai.
   - Escolha **Point in time** e informe o timestamp exato anterior ao deploy com falha (ex.: 10 minutos atrás).
   - Nomeie o branch, ex.: `recovery-2026-09-20`.
3. **Obter a Nova Connection String**:
   - O Neon criará instantaneamente uma cópia isolada do banco naquele segundo.
   - Copie a connection string fornecida:
     `postgresql+psycopg2://user:pass@ep-recovery-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`
4. **Atualizar a Variável `DATABASE_URL` no Render**:
   - Vá em **Render Dashboard > Environment**.
   - Atualize `DATABASE_URL` com a URI do branch recuperado.
   - Clique em **Save Changes**. O Render reiniciará a aplicação apontando para os dados íntegros.
5. **Pós-Recuperação e Consolidação**:
   - Após a estabilização do incidente, promova a branch `recovery-...` para branch primária no console do Neon ou sincronize os registros faltantes.

---

## 4. Plano de Emergência: Comprometimento de Segredos

Se houver suspeita ou confirmação de que chaves de API, senhas do banco ou a `SECRET_KEY` foram expostas:

### Passo 1: Rotação da `SECRET_KEY` (Sessões e Cookies)
1. Gere imediatamente uma nova chave criptográfica no terminal seguro:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. No painel do Render, atualize a variável `SECRET_KEY`.
3. Salve as alterações. Todos os cookies e sessões ativas serão instantaneamente invalidados, deslogando potenciais invasores.

### Passo 2: Rotação da Senha do Banco PostgreSQL Neon
1. No console do Neon (`https://console.neon.tech`), vá em **Roles**.
2. Localize o usuário de produção (ex.: `neondb_owner`) e clique em **Reset Password**.
3. O Neon gerará uma nova senha e atualizará a connection string.
4. No painel do Render, atualize a variável `DATABASE_URL` com a nova connection string.
5. Salve e force o deploy (`Manual Deploy > Clear build cache & deploy`).

### Passo 3: Rotação de Credenciais de Administrador
1. Conecte-se ao banco ou via Render Shell e execute a atualização de hash da senha dos administradores:
   ```bash
   flask create-owner --email "admin@itclube.com.br" ... # Ou utilize script de redefinição
   ```

---

## 5. Checklist Pós-Rollback

Após a execução de qualquer procedimento de reversão:

- [ ] Endpoint `/health` responde com status `200 OK`.
- [ ] Logs no dashboard do Render não apresentam erros de inicialização de workers ou banco.
- [ ] Login de usuário administrador efetuado com sucesso.
- [ ] Consulta de saldo e catálogo de recompensas de um cliente validada.
- [ ] Comunicação com a equipe e stakeholders informando a normalização do serviço.
- [ ] Abertura de ticket/issue de *Post-Mortem* para análise da causa raiz da falha.
