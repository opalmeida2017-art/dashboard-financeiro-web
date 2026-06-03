# BIWEB Desktop — gerar .exe e instalador

## O que o pacote faz

1. Instala `BIWEB.exe` + PostgreSQL portátil (pasta `runtime/postgresql`).
2. Na primeira execução: cria banco local em `%LOCALAPPDATA%\BIWEB\`.
3. Abre o assistente **Configuração inicial** (URL, usuário e senha do SATI).
4. Opcionalmente baixa o ZIP do SATI e restaura com `pg_restore`.
5. O painel passa a ler tudo do PostgreSQL (sem planilhas).

## Pré-requisitos para **compilar**

- Windows 10/11
- Python 3.11+ com venv no projeto
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- Google Chrome no PC do **usuário final** (robô Selenium)

## Passo a passo

### 1. PostgreSQL portátil

Siga `runtime/postgresql/README.md` e coloque os binários em `runtime/postgresql/bin/`.

### 2. Dependências

```powershell
cd C:\python\BIWEB
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-desktop.txt
```

### 3. Gerar o executável

```powershell
.\build_desktop.ps1
```

Saída: `dist\BIWEB-pacote\` (contém `BIWEB.exe`).

### 4. Gerar o instalador (.exe Setup)

Abra o Inno Setup e compile `installer\biweb.iss`, ou:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\biweb.iss
```

Saída: `dist\BIWEB-Setup.exe`

## Testar sem instalador

```powershell
$env:BIWEB_DESKTOP="1"
.\.venv\Scripts\python.exe biweb_launcher.py
```

## Variáveis úteis (.env em %LOCALAPPDATA%\BIWEB)

| Variável | Descrição |
|----------|-----------|
| `URL_LOGIN` | Link do SATI |
| `USUARIO_ROBO` / `SENHA_ROBO` | Credenciais do robô |
| `SATI_SCHEMA` | Schema (ex. `c3332`) |
| `ROBO_HEADLESS` | `true` = Chrome invisível |
| `BIWEB_PORT` | Porta do painel (padrão 5000) |

## Observações

- **WeasyPrint** no PyInstaller pode exigir DLLs GTK no PATH; se PDF falhar, o restante do sistema funciona.
- Atualizações do banco: botão **Atualizar banco SATI** ou assistente na instalação.
- Não inclua senhas reais no repositório Git.
