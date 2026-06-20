-- Tabelas do BIWEB (configurações, usuários, logs) — SQLite, arquivo leve local.
-- Os dados operacionais (viagens, despesas) vêm do SATI via SATI_DATABASE_URL (PostgreSQL).

CREATE TABLE IF NOT EXISTS apartamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    slug TEXT UNIQUE,
    status TEXT DEFAULT 'ativo',
    data_criacao TEXT NOT NULL,
    data_vencimento TEXT,
    notas_admin TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    incluir_em_tipo_d INTEGER DEFAULT 0,
    PRIMARY KEY (apartamento_id, group_name)
);

CREATE TABLE IF NOT EXISTS configuracoes_robo (
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    chave TEXT NOT NULL,
    valor TEXT,
    PRIMARY KEY (apartamento_id, chave)
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    mensagem TEXT NOT NULL,
    lida INTEGER DEFAULT 0,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_logs_robo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    mensagem TEXT
);

CREATE INDEX IF NOT EXISTS idx_tb_logs_robo_apt_ts
    ON tb_logs_robo (apartamento_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS tb_user_activity (
    apartamento_id INTEGER PRIMARY KEY REFERENCES apartamentos(id),
    last_seen_timestamp TEXT DEFAULT CURRENT_TIMESTAMP
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
