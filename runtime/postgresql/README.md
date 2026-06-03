# PostgreSQL portátil para o BIWEB Desktop

O instalador precisa do motor PostgreSQL na pasta `runtime/postgresql` (ao lado do `BIWEB.exe`).

## Como obter (Windows 64 bits)

1. Baixe binários portáteis compatíveis (ex.: PostgreSQL 16 ZIP oficial em https://www.postgresql.org/download/windows/ — opção *zip archive*), ou use uma build *portable* confiável.
2. Extraia para esta pasta de forma que exista:
   - `runtime/postgresql/bin/pg_ctl.exe`
   - `runtime/postgresql/bin/initdb.exe`
   - `runtime/postgresql/bin/psql.exe`
   - `runtime/postgresql/bin/pg_restore.exe`

## Dados do usuário

O banco de dados **não** fica em Program Files. Na primeira execução o BIWEB cria:

- `%LOCALAPPDATA%\BIWEB\.env` — conexões e credenciais SAT
- `%LOCALAPPDATA%\BIWEB\pgdata` — cluster PostgreSQL (porta **5433**)

## Tamanho

O pacote completo (exe + PostgreSQL) costuma ter **150–250 MB**. Isso é normal.
