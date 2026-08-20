-- Schema PostgreSQL (migracao) - gerado a partir dos models SQLAlchemy
CREATE TABLE IF NOT EXISTS usuario (
    id_usuario    SERIAL PRIMARY KEY,
    nome          VARCHAR(120) NOT NULL,
    login         VARCHAR(80)  NOT NULL UNIQUE,
    email         VARCHAR(120) UNIQUE,
    senha_hash    VARCHAR(255) NOT NULL,
    nivel_acesso  VARCHAR(20)  NOT NULL DEFAULT 'gestor'
);
CREATE TABLE IF NOT EXISTS cliente (
    id_cliente        SERIAL PRIMARY KEY,
    nome              VARCHAR(120) NOT NULL,
    telefone          VARCHAR(20)  NOT NULL UNIQUE,
    email             VARCHAR(120) UNIQUE,
    endereco          VARCHAR(200),
    data_cadastro     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pontos_acumulados INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS compra (
    id_compra      SERIAL PRIMARY KEY,
    id_cliente     INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
    data           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor          NUMERIC(10,2) NOT NULL,
    pontos_gerados INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS resgate (
    id_resgate           SERIAL PRIMARY KEY,
    id_cliente           INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
    data                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pontos_utilizados    INTEGER NOT NULL,
    descricao_recompensa VARCHAR(200) NOT NULL
);
