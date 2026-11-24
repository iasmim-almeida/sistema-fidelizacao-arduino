-- Schema de referência PostgreSQL do IT Clube.
-- A fonte executável de evolução do banco são as migrações Alembic.

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario           SERIAL PRIMARY KEY,
    nome                 VARCHAR(100) NOT NULL,
    telefone             VARCHAR(20) UNIQUE,
    email                VARCHAR(100) UNIQUE,
    endereco             VARCHAR(255),
    data_cadastro        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pontos_acumulados    INTEGER NOT NULL DEFAULT 0,
    login                VARCHAR(50) NOT NULL UNIQUE,
    senha_hash           VARCHAR(255) NOT NULL,
    nivel_acesso         VARCHAR(20) NOT NULL,
    cargo                VARCHAR(30) NOT NULL DEFAULT 'proprietario',
    ativo                BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_login         TIMESTAMP,
    precisa_trocar_senha BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chk_usuario_pontos CHECK (pontos_acumulados >= 0),
    CONSTRAINT chk_usuario_nivel CHECK (nivel_acesso IN ('CLIENTE', 'ADMIN'))
);

CREATE TABLE IF NOT EXISTS produto (
    id_produto            SERIAL PRIMARY KEY,
    id_usuario            INTEGER REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    nome_cupom            VARCHAR(100) NOT NULL,
    descricao             VARCHAR(255),
    codigo                VARCHAR(50) NOT NULL UNIQUE,
    validade              DATE NOT NULL,
    custo_pontos          INTEGER NOT NULL,
    tipo                  VARCHAR(30) NOT NULL DEFAULT 'produto_fisico',
    valor_beneficio       NUMERIC(10,2),
    quantidade_total      INTEGER,
    quantidade_disponivel INTEGER,
    status                VARCHAR(10) NOT NULL DEFAULT 'ativa',
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_produto_custo CHECK (custo_pontos > 0),
    CONSTRAINT chk_produto_tipo CHECK (
        tipo IN ('produto_fisico', 'desconto_percentual', 'desconto_valor_fixo')
    ),
    CONSTRAINT chk_produto_status CHECK (status IN ('ativa', 'pausada')),
    CONSTRAINT chk_produto_quantidade_total CHECK (
        quantidade_total IS NULL OR quantidade_total >= 0
    ),
    CONSTRAINT chk_produto_quantidade_disponivel CHECK (
        quantidade_disponivel IS NULL OR
        (quantidade_disponivel >= 0 AND
         (quantidade_total IS NULL OR quantidade_disponivel <= quantidade_total))
    ),
    CONSTRAINT chk_produto_valor_beneficio CHECK (
        (tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR
        (tipo = 'desconto_percentual' AND valor_beneficio > 0 AND valor_beneficio <= 100) OR
        (tipo = 'desconto_valor_fixo' AND valor_beneficio > 0)
    )
);

CREATE INDEX IF NOT EXISTS ix_produto_id_usuario ON produto(id_usuario);
CREATE INDEX IF NOT EXISTS ix_produto_validade ON produto(validade);
CREATE INDEX IF NOT EXISTS ix_produto_status ON produto(status);

CREATE TABLE IF NOT EXISTS historico (
    id_historico        SERIAL PRIMARY KEY,
    id_usuario          INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    id_produto          INTEGER REFERENCES produto(id_produto) ON DELETE SET NULL,
    tipo_movimentacao   VARCHAR(20) NOT NULL,
    data_movimentacao   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pontos              INTEGER NOT NULL,
    descricao           VARCHAR(255),
    saldo_anterior      INTEGER,
    saldo_posterior     INTEGER,
    origem              VARCHAR(50),
    chave_idempotencia  VARCHAR(128),
    CONSTRAINT chk_historico_tipo CHECK (
        tipo_movimentacao IN (
            'COMPRA', 'RESGATE', 'AJUSTE_POSITIVO',
            'AJUSTE_NEGATIVO', 'ESTORNO', 'EXPIRACAO'
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_historico_id_usuario ON historico(id_usuario);
CREATE INDEX IF NOT EXISTS ix_historico_id_produto ON historico(id_produto);
CREATE INDEX IF NOT EXISTS ix_historico_tipo_movimentacao ON historico(tipo_movimentacao);
CREATE INDEX IF NOT EXISTS ix_historico_data_movimentacao ON historico(data_movimentacao);
CREATE UNIQUE INDEX IF NOT EXISTS ix_historico_chave_idempotencia
    ON historico(chave_idempotencia);
