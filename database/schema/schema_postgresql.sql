-- Schema PostgreSQL (migracao) - gerado a partir dos models SQLAlchemy
CREATE TABLE IF NOT EXISTS usuario (
    id_usuario           SERIAL PRIMARY KEY,
    nome                 VARCHAR(120) NOT NULL,
    login                VARCHAR(80)  NOT NULL UNIQUE,
    email                VARCHAR(120) UNIQUE,
    senha_hash           VARCHAR(255) NOT NULL,
    nivel_acesso         VARCHAR(20)  NOT NULL DEFAULT 'gestor',
    cargo                VARCHAR(30)  NOT NULL DEFAULT 'proprietario',
    ativo                BOOLEAN      NOT NULL DEFAULT TRUE,
    data_cadastro        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_login         TIMESTAMP,
    precisa_trocar_senha BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS cliente (
    id_cliente        SERIAL PRIMARY KEY,
    nome              VARCHAR(120) NOT NULL,
    telefone          VARCHAR(20)  NOT NULL UNIQUE,
    email             VARCHAR(120) UNIQUE,
    endereco          VARCHAR(200),
    senha_hash        VARCHAR(255),
    data_cadastro     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    pontos_acumulados INTEGER      NOT NULL DEFAULT 0,
    ativo             BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS compra (
    id_compra      SERIAL PRIMARY KEY,
    id_cliente     INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
    data           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor          NUMERIC(10,2) NOT NULL,
    pontos_gerados INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recompensa (
    id_recompensa         SERIAL PRIMARY KEY,
    id_usuario            INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    nome                  VARCHAR(120) NOT NULL,
    custo_pontos          INTEGER NOT NULL CHECK (custo_pontos > 0),
    tipo                  VARCHAR(30) NOT NULL CHECK (tipo IN ('produto_fisico', 'desconto_percentual', 'desconto_valor_fixo')),
    valor_beneficio       NUMERIC(10,2),
    validade              DATE NOT NULL,
    quantidade_total      INTEGER NOT NULL CHECK (quantidade_total >= 0),
    quantidade_disponivel INTEGER NOT NULL CHECK (quantidade_disponivel >= 0 AND quantidade_disponivel <= quantidade_total),
    status                VARCHAR(10) NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa', 'pausada')),
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_recompensa_valor_beneficio CHECK (
        (tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR
        (tipo = 'desconto_percentual' AND valor_beneficio > 0 AND valor_beneficio <= 100) OR
        (tipo = 'desconto_valor_fixo' AND valor_beneficio > 0)
    )
);

CREATE INDEX IF NOT EXISTS ix_recompensa_id_usuario ON recompensa(id_usuario);
CREATE INDEX IF NOT EXISTS ix_recompensa_status ON recompensa(status);
CREATE INDEX IF NOT EXISTS ix_recompensa_validade ON recompensa(validade);

CREATE TABLE IF NOT EXISTS resgate (
    id_resgate           SERIAL PRIMARY KEY,
    id_cliente           INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
    id_recompensa        INTEGER REFERENCES recompensa(id_recompensa) ON DELETE SET NULL,
    data                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pontos_utilizados    INTEGER NOT NULL,
    descricao_recompensa VARCHAR(200) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_resgate_id_recompensa ON resgate(id_recompensa);

CREATE TABLE IF NOT EXISTS movimentacao_pontos (
    id_movimentacao SERIAL PRIMARY KEY,
    id_cliente      INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
    tipo            VARCHAR(30) NOT NULL,
    quantidade      INTEGER NOT NULL,
    saldo_anterior  INTEGER NOT NULL,
    saldo_posterior INTEGER NOT NULL,
    origem          VARCHAR(50) NOT NULL DEFAULT 'sistema',
    motivo          VARCHAR(255),
    id_usuario      INTEGER REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    id_compra       INTEGER REFERENCES compra(id_compra) ON DELETE SET NULL,
    id_resgate      INTEGER REFERENCES resgate(id_resgate) ON DELETE SET NULL,
    id_recompensa   INTEGER REFERENCES recompensa(id_recompensa) ON DELETE SET NULL,
    data_hora       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_id_cliente ON movimentacao_pontos(id_cliente);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_tipo ON movimentacao_pontos(tipo);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_id_usuario ON movimentacao_pontos(id_usuario);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_id_compra ON movimentacao_pontos(id_compra);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_id_resgate ON movimentacao_pontos(id_resgate);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_id_recompensa ON movimentacao_pontos(id_recompensa);
CREATE INDEX IF NOT EXISTS ix_movimentacao_pontos_data_hora ON movimentacao_pontos(data_hora);

CREATE TABLE IF NOT EXISTS auditoria (
    id_auditoria SERIAL PRIMARY KEY,
    id_usuario   INTEGER REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    acao         VARCHAR(50) NOT NULL,
    entidade     VARCHAR(50) NOT NULL,
    entidade_id  VARCHAR(50),
    detalhes     TEXT,
    ip           VARCHAR(45),
    user_agent   VARCHAR(255),
    data_hora    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_auditoria_id_usuario ON auditoria(id_usuario);
CREATE INDEX IF NOT EXISTS ix_auditoria_acao ON auditoria(acao);
CREATE INDEX IF NOT EXISTS ix_auditoria_entidade ON auditoria(entidade);
CREATE INDEX IF NOT EXISTS ix_auditoria_entidade_id ON auditoria(entidade_id);
CREATE INDEX IF NOT EXISTS ix_auditoria_data_hora ON auditoria(data_hora);
