# Modo leve (legado) — não usar se o SAT é só web/AWS

> **Se o SAT está na Amazon:** use PostgreSQL **local** (`BIWEB_DB_MODE=installed` ou `embedded`).
> Veja `docs/BANCO_SAT_WEB_POSTGRES_LOCAL.md`.

# Modo leve — sem PostgreSQL embutido no BIWEB

## Por que o backup do SATI ainda usa PostgreSQL?

O site SATI envia um arquivo `.zip` com dump **PostgreSQL** (`pg_restore`).  
Isso não vira SQLite automaticamente. Porém **não é preciso o BIWEB instalar outro PostgreSQL**:

| O quê | Onde fica | Peso no PC |
|-------|-----------|------------|
| Dados operacionais (viagens, despesas, c3332) | PostgreSQL **do SATI** (já instalado com o sistema) | Já existia com o SATI |
| Usuários, senhas, configs, logs do BIWEB | Arquivo **SQLite** (~1–5 MB) | Mínimo |
| BIWEB.exe | Só aplicação + Chrome | Leve |

## Comparativo

| Modo | BIWEB instala PG? | Desempenho | Quando usar |
|------|-------------------|------------|-------------|
| **sqlite** (padrão do .exe) | Não | Melhor para o PC | SATI já instalado (porta 5433) |
| **external** | Não | Igual ao sqlite | Mesmo banco PG para app e SATI |
| **embedded** | Sim (portátil ~150 MB) | Mais RAM/disco | PC sem SATI/PostgreSQL |

## Configurar no `.env` (desenvolvimento)

Exemplo igual ao seu ambiente atual:

```env
BIWEB_DB_MODE=sqlite
DATABASE_URL=sqlite:///C:/Users/SEU_USUARIO/AppData/Local/BIWEB/biweb_app.db
SATI_DATABASE_URL=postgresql://postgres:masterkey@localhost:5433/sat1_sati_is
SATI_PG_RESTORE=C:\Program Files\PostgreSQL\17\bin\pg_restore.exe
USE_SATI_SOURCE=true
SATI_SCHEMA=c3332
EXECUTION_MODE=sync
```

Não precisa de `dashboard_db` na porta 5432 — só o banco do SATI na **5433**.

## Robô

Continua igual: login no SATI → baixa ZIP → `pg_restore` no banco da `SATI_DATABASE_URL`.  
O `pg_restore` usa o PostgreSQL **já instalado** (pasta do SATI ou `Program Files\PostgreSQL`).

## SQLite puro (sem nenhum PostgreSQL)?

Só com **reescrita grande** do projeto (importar milhões de linhas para SQLite/DuckDB com outro formato).  
Hoje **não é suportado** porque o SATI só entrega dump PostgreSQL.

## Nuvem (PC ainda mais leve)

`SATI_DATABASE_URL` pode apontar para PostgreSQL na nuvem (Render, etc.).  
O PC só roda BIWEB + Chrome; o banco fica no servidor.
