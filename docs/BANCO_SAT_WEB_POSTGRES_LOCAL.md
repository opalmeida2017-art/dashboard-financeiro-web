# SAT na web (Amazon) + PostgreSQL local

## Como funciona

| Onde | O quê |
|------|--------|
| **SAT / Amazon** | Sistema web; banco na nuvem — **sem acesso direto** pelo BIWEB |
| **Seu PC** | PostgreSQL instalado (ou portátil do instalador) |
| **Robô** | Login no site SAT → baixa `SATI-c3332-atual.zip` → `pg_restore` no Postgres **local** |
| **Painel** | Lê o schema `c3332` dessa cópia local |

## Modos no `.env`

### 1. PostgreSQL instalado no Windows (desenvolvimento)

```env
BIWEB_DB_MODE=installed
DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5433/biweb_sati
SATI_DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5433/biweb_sati
SATI_PG_RESTORE=C:\Program Files\PostgreSQL\17\bin\pg_restore.exe
USE_SATI_SOURCE=true
SATI_SCHEMA=c3332
EXECUTION_MODE=sync
```

Crie o banco vazio antes (ex. `biweb_sati` ou `sat1_sati_is`). O robô preenche com o restore.

### 2. PostgreSQL portátil (instalador .exe)

```env
BIWEB_DB_MODE=embedded
```

O BIWEB sobe o Postgres em `%LOCALAPPDATA%\BIWEB\pgdata` (porta 5433).

## O que NÃO usar

- `SATI_DATABASE_URL` apontando para RDS/Amazon do SAT — o BIWEB **não** conecta lá.
- Modo `sqlite` só para configs — **não** substitui os dados do SAT.

## Fluxo resumido

1. Instalar PostgreSQL no Windows **ou** usar o pacote com `runtime/postgresql`.
2. Configurar URL/senha do site SAT em **Configurações do Robô**.
3. **Atualizar banco SATI** — download + restore local.
4. Abrir o painel (dados vêm do Postgres local).
