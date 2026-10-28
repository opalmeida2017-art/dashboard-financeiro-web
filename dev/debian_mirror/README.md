# Espelho Debian (dev Windows)

Arquivos baixados do Debian `192.168.100.15` para desenvolvimento local.
Gerado por `python scripts/sync_from_debian.py` — **não versionar** (gitignore).

Estrutura:
- `tenants/<slug>/tenant.env` — config do tenant
- `manifest.json` — último sync (data, arquivos, schemas)

ZIPs SATI ficam em `downloads/<apt_id>/` na raiz do projeto.
