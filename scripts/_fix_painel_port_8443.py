"""Ajusta painel nfe-web para gerar links externos com porta :8443."""
import paramiko
import textwrap

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/opt/nfe-web"
EXT = "https://dadosfrete.duckdns.org:8443"
PAINEL_EXT = f"{EXT}/painel_licenca/"

REPLACEMENTS = {
    f"{APP}/public_urls.py": [
        ('or "https://dadosfrete.duckdns.org"', f'or "{EXT}"'),
    ],
    f"{APP}/backend/app/routers/painel.py": [
        ('"https://dadosfrete.duckdns.org").rstrip("/")', f'"{EXT}").rstrip("/")'),
        ('"https://dadosfrete.duckdns.org/painel_licenca/"', f'"{PAINEL_EXT}"'),
    ],
    f"{APP}/frontend/painel/painel.js": [
        ('let biExternalUrl = "https://dadosfrete.duckdns.org";', f'let biExternalUrl = "{EXT}";'),
        ('info.painel_external_url || "https://dadosfrete.duckdns.org/painel_licenca/"',
         f'info.painel_external_url || "{PAINEL_EXT}"'),
        ('info.external_domain || "https://dadosfrete.duckdns.org"', f'info.external_domain || "{EXT}"'),
    ],
    f"{APP}/frontend/painel/index.html": [
        ('<span id="bi-external-url">https://dadosfrete.duckdns.org</span>',
         f'<span id="bi-external-url">{EXT}</span>'),
        ('href="https://dadosfrete.duckdns.org/painel_licenca/"',
         f'href="{PAINEL_EXT}"'),
        ('dadosfrete.duckdns.org/painel_licenca/', 'dadosfrete.duckdns.org:8443/painel_licenca/'),
        ('painel.js?v=2', 'painel.js?v=3'),
    ],
}

PAINEL_JS_PREVIEW = textwrap.dedent(
    f"""
let externalDomain = "{EXT}";

function previewExterno(path) {{
  const base = (externalDomain || "{EXT}").replace(/\\/$/, "");
  return `${{base}}${{path.startsWith("/") ? path : "/" + path}}`;
}}
"""
).strip()

PAINEL_JS_PREVIEW_OLD = 'let biBaseUrl = "http://192.168.100.12";'
PAINEL_JS_PREVIEW_NEW = PAINEL_JS_PREVIEW + '\n\nlet biBaseUrl = "http://192.168.100.12";'

PAINEL_JS_WEB_PREVIEW_OLD = (
    '      document.getElementById("web-preview").textContent = `Prévia: /t/${slugPreview(razao)}/`;'
)
PAINEL_JS_WEB_PREVIEW_NEW = (
    '      document.getElementById("web-preview").textContent = '
    '`Prévia externa: ${previewExterno(`/t/${slugPreview(razao)}/`)}`;'
)

ENV_LINES = {
    "NFE_PUBLIC_EXTERNAL_URL": EXT,
    "BI_PUBLIC_EXTERNAL_URL": EXT,
    "PAINEL_WEB_EXTERNAL_URL": PAINEL_EXT,
}

RUN_FIX = r'''
import os, json
from pathlib import Path
for line in Path('/opt/nfe-web/.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
import sys
sys.path.insert(0, '/opt/nfe-web')
import painel_store as ps
import bi_store as bs
import web_tenant_registry as wr
import bi_tenant_registry as br

ext = os.getenv('NFE_PUBLIC_EXTERNAL_URL', 'https://dadosfrete.duckdns.org:8443').rstrip('/')
conn = ps._connect_central()
conn.autocommit = True
cur = conn.cursor()
cur.execute(
    """
    INSERT INTO painel_meta (chave, valor) VALUES ('external_base_url', %s)
    ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor
    """,
    (ext,),
)
conn.close()
bs.set_external_base_url(ext)
ps.normalize_tenant_urls()
bs.normalize_bi_urls()
ps.export_json_backup()
bs.export_json_backup()
print('external_base_url=', ext)
print('WEB')
for t in wr.list_tenants():
    print(json.dumps(wr.enrich_tenant(t), ensure_ascii=False))
print('BI')
for t in br.list_tenants():
    print(json.dumps(br.enrich_tenant(t), ensure_ascii=False))
'''


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def patch_file(sftp, path, pairs):
    with sftp.open(path, "r") as f:
        content = f.read().decode("utf-8")
    original = content
    for old, new in pairs:
        if old not in content:
            print(f"AVISO: trecho não encontrado em {path}: {old[:60]}...")
            continue
        content = content.replace(old, new)
    if content != original:
        with sftp.open(path, "w") as f:
            f.write(content.encode("utf-8"))
        print(f"PATCH OK: {path}")
    else:
        print(f"SEM MUDANÇA: {path}")


def update_env(sftp):
    path = f"{APP}/.env"
    with sftp.open(path, "r") as f:
        lines = f.read().decode("utf-8").splitlines()
    out = []
    seen = set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else ""
        if key in ENV_LINES:
            out.append(f"{key}={ENV_LINES[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in ENV_LINES.items():
        if key not in seen:
            out.append(f"{key}={val}")
    with sftp.open(path, "w") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print("PATCH OK: .env")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()

    for path, pairs in REPLACEMENTS.items():
        patch_file(sftp, path, pairs)

    # preview externo no painel.js
    with sftp.open(f"{APP}/frontend/painel/painel.js", "r") as f:
        js = f.read().decode("utf-8")
    js_orig = js
    if "function previewExterno" not in js:
        if PAINEL_JS_PREVIEW_OLD in js:
            js = js.replace(PAINEL_JS_PREVIEW_OLD, PAINEL_JS_PREVIEW_NEW, 1)
        else:
            print("AVISO: não inseriu previewExterno")
    if PAINEL_JS_WEB_PREVIEW_OLD in js:
        js = js.replace(PAINEL_JS_WEB_PREVIEW_OLD, PAINEL_JS_WEB_PREVIEW_NEW, 1)
    if 'biExternalUrl = (info.bi_external_base_url || biExternalUrl)' in js:
        js = js.replace(
            'biExternalUrl = (info.bi_external_base_url || biExternalUrl).replace(/\\/$/, "");',
            'biExternalUrl = (info.bi_external_base_url || biExternalUrl).replace(/\\/$/, "");\n'
            '  externalDomain = (info.external_domain || externalDomain || biExternalUrl).replace(/\\/$/, "");',
            1,
        )
    if js != js_orig:
        with sftp.open(f"{APP}/frontend/painel/painel.js", "w") as f:
            f.write(js.encode("utf-8"))
        print("PATCH OK: painel.js (preview)")

    update_env(sftp)

    with sftp.open("/tmp/_fix_painel_port_8443_run.py", "w") as f:
        f.write(RUN_FIX)
    sftp.close()

    print(run(c, f"cd {APP} && ./venv/bin/python /tmp/_fix_painel_port_8443_run.py"))
    print(run(c, f"echo {PASS} | sudo -S systemctl restart nfe-web && sleep 4 && "
                 "systemctl is-active nfe-web"))
    c.close()
    print("Concluído.")


if __name__ == "__main__":
    main()
