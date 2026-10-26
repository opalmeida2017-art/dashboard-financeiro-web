# BIWEB — teste Windows + versão pelo GitHub

**Pasta de teste:** `C:\python\BIWEB`  
**Repositório:** `https://github.com/opalmeida2017-art/dashboard-financeiro-web.git`  
**Produção:** `192.168.100.12` (`/home/oitamar/dashboard-financeiro-web`) — DuckDNS continua lá até pedido de troca.

## Fluxo

```
produzir / corrigir em C:\python\BIWEB
        ↓
publicar_versao.bat   →  git push origin main
        ↓
GitHub (fonte da versão)
        ↓
atualizar_do_github.bat  (ou Actions no runner self-hosted)
        ↓
reinicia http://127.0.0.1:5000
```

O GitHub recebe **só a aplicação**. Não versionar: `.env`, `venv/`, `downloads/`, dumps, logs, `scripts/_*`, `deploy/`.

## 1. Subir o teste local

Pré-requisitos: PostgreSQL 17 (porta **5433**), `.env` (copie de `.env.example`), venv com `pip install -r requirements.txt`.

```powershell
cd C:\python\BIWEB
python run_dev.py
```

Abre em **http://127.0.0.1:5000** (sem `/biweb/slug/`).

Primeira vez (bancos + SATI de um tenant):

```powershell
python scripts/sync_from_debian.py --tenant transporte-brasil
python scripts/setup_dev_windows.py --tenant transporte-brasil
```

## 2. Enviar versão → GitHub

```bat
publicar_versao.bat
```

Ou: `git add` / `git commit` / `git push origin main`.

## 3. Reiniciar o teste pela versão do GitHub

```bat
atualizar_do_github.bat
```

Isso faz `git pull --ff-only origin main`, atualiza o venv e reinicia **somente** o `run_dev.py` desta pasta (não mexe no CTe).

No GitHub: **Actions → Atualizar teste Windows → Run workflow** (precisa de runner self-hosted com labels `self-hosted`, `windows`, `biweb-win` nesta máquina).

## 4. Produção .12

O `.12` **não** atualiza sozinho. Quando quiser mandar a mesma versão do GitHub para a produção:

```powershell
python scripts/deploy_debian.py --confirmar-deploy
```

Não envia `.env`, `downloads/` nem `venv/`.

## O que não vai para o GitHub

| Fica só no Windows / servidor | Motivo |
|-------------------------------|--------|
| `.env` | senhas |
| `venv/`, `.venv/` | ambiente local |
| `downloads/`, `*.dump`, logs | dados |
| `scripts/_*`, `deploy/` | diagnóstico e ops |
| `frontend/static/uploads/` | logos de cliente |

## Troubleshooting

- **psql pede senha:** confira `DATABASE_URL` no `.env`
- **Restore falha (versão PG):** dump SATI exige PostgreSQL **16+**
- **pull recusado:** há commit local; faça commit ou `git status` antes de `atualizar_do_github.bat`
