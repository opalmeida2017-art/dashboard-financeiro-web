# BIWEB — teste Windows + versão pelo GitHub

**Pasta de teste:** `C:\python\BIWEB`  
**Repositório:** `https://github.com/opalmeida2017-art/dashboard-financeiro-web.git`  
**Debian:** `192.168.100.15` (`/home/oitamar/dashboard-financeiro-web`)

O **192.168.100.12** só serviu para copiar banco e estrutura. Não recebe mais deploy e pode ser desligado.

## Fluxo

```
produzir / corrigir em C:\python\BIWEB
        ↓
publicar_versao.bat   →  git push origin main
        ↓
GitHub Actions (push na main)
  1. cria release  v{VERSION}.{run}   (versiona)
  2. atualiza C:\python\BIWEB e reinicia http://127.0.0.1:5000
  3. git pull no .15 e systemctl restart gunicorn
```

Painel de licenças (Automação CT-e) gera banco + link no **.15** (`/biweb/{slug}/` e `/acesso/{slug}/{usuario}`).

O GitHub recebe **só a aplicação**. Não versionar: `.env`, `venv/`, `downloads/`, dumps, logs, `deploy/`, `tenants/`.

## 1. Subir o teste local

Pré-requisitos: PostgreSQL 17 (porta **5433**), `.env` (copie de `.env.example`), venv com `pip install -r requirements.txt`.

```powershell
cd C:\python\BIWEB
python run_dev.py
```

Abre em **http://127.0.0.1:5000** (sem `/biweb/slug/`).

Primeira vez (bancos + SATI a partir do **.15**):

```powershell
python scripts/sync_from_debian.py --tenant transporte-brasil
python scripts/setup_dev_windows.py --tenant transporte-brasil
```

## 2. Enviar versão → GitHub

```bat
publicar_versao.bat
```

Ou: `git add` / `git commit` / `git push origin main`.

A cada push na `main` o GitHub:

- publica a tag/release `v1.1.0.{número}`
- puxa a main nesta pasta e reinicia o teste
- no **.15**: `git reset --hard origin/main` + `systemctl restart gunicorn`

Runner self-hosted nesta máquina, labels: `self-hosted`, `windows`, `biweb-win`.

## 3. Reiniciar só o teste Windows

```bat
atualizar_do_github.bat
```

Ou no GitHub: **Actions → Atualizar teste Windows (manual) → Run workflow**.

## 4. Debian .15

Automático no push da `main` (passo 2).

Para mandar de novo sem novo commit:

- GitHub **Actions → Versão, teste Windows e Debian .15 → Run workflow**
- ou: `python scripts/_deploy_git_pull.py`

## Banco e link (painel de licenças)

No painel CT-e (`/painel/`):

- **Gerar banco + link BI** — cria `bi_{slug}` no **.15** e o link `http://192.168.100.15/biweb/{slug}/`
- **Criar link do usuário** — mesmo banco, `http://192.168.100.15/acesso/{slug}/{usuario}`

A API admin (`/api/admin/tenants` e `/api/admin/acessos`) usa `NFE_ADMIN_SECRET` / `BIWEB_ADMIN_SECRET`.

## O que não vai para o GitHub

| Fica só no Windows / servidor | Motivo |
|-------------------------------|--------|
| `.env` | senhas |
| `venv/`, `.venv/` | ambiente local |
| `downloads/`, `*.dump`, logs | dados |
| `tenants/`, `data/acessos_bi.json` | instâncias e links de usuário |
| `scripts/_*` (exceto guard/deploy) | diagnóstico e ops |
| `deploy/` | ops local |
| `frontend/static/uploads/` | logos de cliente |

## Troubleshooting

- **psql pede senha:** confira `DATABASE_URL` no `.env`
- **Restore falha (versão PG):** dump SATI exige PostgreSQL **16+**
- **pull recusado:** há commit local; faça commit ou `git status` antes de `atualizar_do_github.bat`
- **Actions não reinicia o .15:** o runner `biweb-win` precisa estar online nesta máquina (rede local)
