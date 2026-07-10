# Desenvolvimento Windows (base) + deploy Debian

Fluxo: **sync do Debian → setup local → testar → deploy quando aprovar**.

## Pré-requisitos

1. **PostgreSQL 17** (ou 16) instalado, porta **5433**
2. `.env` na raiz (copie de `.env.example` e ajuste senha `postgres`)
3. Python venv com dependências: `pip install -r requirements.txt`

Exemplo mínimo no `.env`:

```env
DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5433/dashboard_db
SATI_DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5433/sat1_sati_is
SATI_PG_RESTORE=C:\Program Files\PostgreSQL\17\bin\pg_restore.exe
SATI_RESTORE_USE_SUDO_POSTGRES=0
USE_SATI_SOURCE=true
BIWEB_LOCAL_DEV=1
BIWEB_REQUIRE_TENANT_LINK=0
BIWEB_SKIP_LOGIN=true
```

## 1. Trazer dados do Debian (Windows ← servidor)

```powershell
cd c:\python\BIWEB
python scripts/sync_from_debian.py --tenant transporte-brasil
```

Baixa:
- `tenant.env` do tenant → `dev/debian_mirror/tenants/`
- `SATI-c3332-atual.zip` → `downloads/3/`

Tenants disponíveis: `transporte-brasil`, `jeremias`, `rio-bonito`, `wcarlos`, `all`

Opcional — sobrescrever código local com o do servidor:

```powershell
python scripts/sync_from_debian.py --tenant transporte-brasil --code
```

## 2. Criar bancos, schema app e restaurar SATI

```powershell
python scripts/setup_dev_windows.py --tenant transporte-brasil
```

Faz automaticamente:
| Passo | Ação |
|-------|------|
| 1 | Cria `dashboard_db` e `sat1_sati_is` (se não existirem) |
| 2 | Aplica `migrations/sql_scripts/criar_tabelas_biweb_apartamento.sql` |
| 3 | Insere apartamento (ex. id=3 Transporte Brasil) |
| 4 | Ajusta `.env` para modo dev Windows |
| 5 | `pg_restore` do ZIP SATI no schema `c3332` |

Tudo de uma vez (sync + setup):

```powershell
python scripts/setup_dev_windows.py --tenant transporte-brasil --sync-first
```

Só schema app, sem restore:

```powershell
python scripts/setup_dev_windows.py --tenant transporte-brasil --skip-restore
```

Forçar novo restore (apaga/recria schema via sati_db_restore):

```powershell
python scripts/setup_dev_windows.py --tenant transporte-brasil --force-restore
```

## 3. Subir o painel local

```powershell
python run_dev.py
```

Abre em **http://127.0.0.1:5000** — sem link `/biweb/slug/`.

## 4. Depois de testar → Debian (só quando você pedir)

```powershell
python scripts/deploy_debian.py --confirmar-deploy
```

O deploy **não** envia `.env`, `downloads/` nem `venv/`.

## Schemas no PostgreSQL local

| Banco | Conteúdo |
|-------|----------|
| `dashboard_db` | Tabelas app (`apartamentos`, `usuarios`, configs…) |
| `sat1_sati_is` | Dados SATI — schemas `c2910`, `c3219`, `c3332` |

Cada restore SATI preenche um schema (`c3332` = Transporte Brasil / Jeremias, etc.).

## Servidor Debian (referência)

| Item | Valor |
|------|--------|
| Host | `192.168.100.12` |
| App | `/home/oitamar/dashboard-financeiro-web` |
| Tenants | `/opt/biweb/tenants` |
| SATI compartilhado | DB `sat1_sati_is` |

## Troubleshooting

- **psql pede senha**: confira `DATABASE_URL` no `.env`
- **Restore falha (versão PG)**: dump SATI exige PostgreSQL **16+**
- **Lista vazia no fluxo**: confira `SATI_SCHEMA` e datas no filtro
- **ZIP grande**: primeiro sync pode demorar vários minutos
