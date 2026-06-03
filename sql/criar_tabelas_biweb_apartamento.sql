-- Tabelas/colunas do BIWEB (schema public) que NÃO existem no dump SATI (c3332).
-- Execute no banco sat1_sati_is (PG 17, porta 5433):
--   psql -U postgres -h localhost -p 5433 -d sat1_sati_is -f sql/criar_tabelas_biweb_apartamento.sql

-- ========== MULTI-TENANT (apartamento_id) ==========

CREATE TABLE IF NOT EXISTS apartamentos (
    id SERIAL PRIMARY KEY,
    nome_empresa TEXT NOT NULL,
    slug TEXT UNIQUE,
    status TEXT DEFAULT 'ativo',
    data_criacao TEXT NOT NULL,
    data_vencimento TEXT,
    notas_admin TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nome TEXT,
    role TEXT DEFAULT 'usuario'
);

CREATE TABLE IF NOT EXISTS static_expense_groups (
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    group_name TEXT NOT NULL,
    is_despesa TEXT DEFAULT 'S',
    is_custo_viagem TEXT DEFAULT 'N',
    PRIMARY KEY (apartamento_id, group_name)
);

ALTER TABLE static_expense_groups
    ADD COLUMN IF NOT EXISTS incluir_em_tipo_d BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS configuracoes_robo (
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    chave TEXT NOT NULL,
    valor TEXT,
    PRIMARY KEY (apartamento_id, chave)
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id SERIAL PRIMARY KEY,
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    mensagem TEXT NOT NULL,
    lida BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ========== AUXILIARES (apartamento_id) ==========

CREATE TABLE IF NOT EXISTS tb_logs_robo (
    id SERIAL PRIMARY KEY,
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mensagem TEXT
);

CREATE INDEX IF NOT EXISTS idx_tb_logs_robo_apt_ts
    ON tb_logs_robo (apartamento_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS tb_user_activity (
    apartamento_id INTEGER PRIMARY KEY REFERENCES apartamentos(id),
    last_seen_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS despesas_viagem_associadas (
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    numero INTEGER NOT NULL,
    coditemnota INTEGER NOT NULL,
    PRIMARY KEY (apartamento_id, numero, coditemnota)
);

CREATE TABLE IF NOT EXISTS despesas_viagem_excluidas (
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    numero INTEGER NOT NULL,
    coditemnota INTEGER NOT NULL,
    PRIMARY KEY (apartamento_id, numero, coditemnota)
);

-- ========== Exemplo: apartamento ligado ao schema SATI c3332 ==========
-- INSERT INTO apartamentos (nome_empresa, slug, status, data_criacao)
-- VALUES ('SATI C3332', 'c3332', 'ativo', to_char(now(), 'YYYY-MM-DD'))
-- ON CONFLICT (slug) DO NOTHING;
--
-- INSERT INTO configuracoes_robo (apartamento_id, chave, valor)
-- SELECT id, 'SATI_COD_FILIAL', '1' FROM apartamentos WHERE slug = 'c3332'
-- ON CONFLICT (apartamento_id, chave) DO NOTHING;
