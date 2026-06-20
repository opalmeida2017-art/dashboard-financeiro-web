import os, sys
from pathlib import Path
os.chdir('/home/oitamar/dashboard-financeiro-web')
for line in open('.env'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ['BI_TENANT_SLUG'] = 'w-carlos'
from infra.tenant_licensing.bi_tenant_context import set_tenant
from app.data.database import switch_engine_for_request
set_tenant('w-carlos')
switch_engine_for_request()
from sati_integration.robos from sati_integration.robos import sati_db_restore as s
zip_p = Path('/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip')
if not zip_p.is_file():
    z = sorted(Path('/home/oitamar/dashboard-financeiro-web').glob('downloads/**/*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    zip_p = z[0] if z else None
if not zip_p or not zip_p.is_file():
    print('ERRO: nenhum ZIP SATI encontrado')
    sys.exit(1)
print('ZIP:', zip_p)
s.processar_arquivo_zip_sati(zip_p, apartamento_id=1)
print('Restore OK')
