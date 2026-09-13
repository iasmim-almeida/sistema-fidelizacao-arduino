-- =====================================================
-- 1. TABELA USUARIO
-- Clientes e administradores do sistema
-- =====================================================

CREATE TABLE usuario (
    id_usuario INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    telefone VARCHAR(20) UNIQUE,

    nome VARCHAR(100) NOT NULL,

    email VARCHAR(100),

    endereco VARCHAR(255),

    data_cadastro TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    pontos_acumulados INTEGER NOT NULL
        DEFAULT 0,

    login VARCHAR(50) NOT NULL UNIQUE,

    senha_hash VARCHAR(255) NOT NULL,

    nivel_acesso VARCHAR(20) NOT NULL,

    CONSTRAINT chk_usuario_pontos
        CHECK (pontos_acumulados >= 0),

    CONSTRAINT chk_usuario_nivel
        CHECK (nivel_acesso IN ('CLIENTE', 'ADMIN'))
);


-- =====================================================
-- 2. TABELA PRODUTO
-- Cupons/recompensas disponíveis no programa
-- =====================================================

CREATE TABLE produto (
    id_produto INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    nome_cupom VARCHAR(100) NOT NULL,

    descricao VARCHAR(255),

    codigo VARCHAR(50) NOT NULL UNIQUE,

    validade DATE NOT NULL
);


-- =====================================================
-- 3. TABELA HISTORICO
-- Registra compras e resgates
-- =====================================================

CREATE TABLE historico (
    id_historico INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    id_usuario INTEGER NOT NULL,

    id_produto INTEGER,

    tipo_movimentacao VARCHAR(20) NOT NULL,

    data_movimentacao TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    pontos INTEGER NOT NULL,

    descricao VARCHAR(255),

    CONSTRAINT fk_historico_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuario(id_usuario),

    CONSTRAINT fk_historico_produto
        FOREIGN KEY (id_produto)
        REFERENCES produto(id_produto),

    CONSTRAINT chk_historico_tipo
        CHECK (
            tipo_movimentacao IN ('COMPRA', 'RESGATE')
        )
);