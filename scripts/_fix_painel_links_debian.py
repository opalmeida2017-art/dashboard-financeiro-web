"""Corrige links externos no painel de licenças no Debian (/opt/nfe-web)."""
import paramiko
import textwrap

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/opt/nfe-web"

PATCHES = {
    f"{APP}/painel_store.py": [
        (
            'def normalize_tenant_urls():\n    """Atualiza URLs LAN dos tenants web no painel."""',
            'def normalize_tenant_urls():\n    """Atualiza URLs externas dos tenants web no painel."""',
        ),
        (
            "            correto = reg.public_url(slug)",
            "            correto = reg.external_url(slug)",
        ),
    ],
    f"{APP}/bi_store.py": [
        (
            'def normalize_bi_urls():\n    """Corrige URLs com barra final (Flask BI usa /acesso/<slug> sem /)."""',
            'def normalize_bi_urls():\n    """Atualiza URLs externas dos tenants BI no painel."""',
        ),
        (
            """            url = str(item.get("url") or "").strip()
            correto = reg.public_url(slug)
            try:
                import public_urls as pu
                correto = pu.bi_url_lan(slug)
            except ImportError:
                pass""",
            """            razao = str(item.get("razao_social") or "").strip()
            try:
                import public_urls as pu
                correto = pu.bi_url_externo(razao, slug)
            except ImportError:
                correto = reg.external_url(slug)""",
        ),
    ],
    f"{APP}/backend/app/routers/painel.py": [
        (
            """        "painel_url": (
            os.getenv("PAINEL_WEB_URL", "").rstrip("/")
            or f"http://{os.getenv('NFE_PUBLIC_HOST', '192.168.100.12')}:{os.getenv('NFE_WEB_PORT', '8090')}"
        ) + "/painel/",
        "painel_external_url": os.getenv(
            "PAINEL_WEB_EXTERNAL_URL", "https://dadosfrete.duckdns.org/painel_licenca/"
        ).strip(),""",
            """        "painel_url": os.getenv(
            "PAINEL_WEB_EXTERNAL_URL", "https://dadosfrete.duckdns.org/painel_licenca/"
        ).strip(),
        "painel_external_url": os.getenv(
            "PAINEL_WEB_EXTERNAL_URL", "https://dadosfrete.duckdns.org/painel_licenca/"
        ).strip(),
        "painel_lan_url": (
            os.getenv("PAINEL_WEB_URL", "").rstrip("/")
            or f"http://{os.getenv('NFE_PUBLIC_HOST', '192.168.100.12')}:{os.getenv('NFE_WEB_PORT', '8090')}"
        ) + "/painel/",""",
        ),
        (
            """        item = criar_instancia(body.razao_social, body.slug or None)
        import painel_store as ps
        ps.export_json_backup()
        return {"ok": True, "tenant": item}""",
            """        item = criar_instancia(body.razao_social, body.slug or None)
        import painel_store as ps
        import web_tenant_registry as registry
        ps.export_json_backup()
        return {"ok": True, "tenant": registry.enrich_tenant(item)}""",
        ),
    ],
}

PAINEL_JS_OLD = textwrap.dedent(
    """
          <div class="url">LAN: ${t.url} | slug: ${t.slug}</div>
          ${urlExt ? `<div class="url" style="color:#b8f5c3">Externo: ${urlExt}</div>` : ""}
"""
).strip()

PAINEL_JS_NEW = textwrap.dedent(
    """
          <div class="url" style="color:#b8f5c3">Externo: ${urlExt || "—"}</div>
          <div class="url hint">LAN: ${t.url} | slug: ${t.slug}</div>
"""
).strip()

PAINEL_JS_BTNS_OLD = textwrap.dedent(
    """
      ac.appendChild(btn("Copiar LAN", "primary small", () => copiarTexto(t.url)));
      if (urlExt) ac.appendChild(btn("Copiar externo", "primary small", () => copiarTexto(urlExt)));
"""
).strip()

PAINEL_JS_BTNS_NEW = textwrap.dedent(
    """
      if (urlExt) ac.appendChild(btn("Copiar link", "primary small", () => copiarTexto(urlExt)));
      ac.appendChild(btn("Copiar LAN", "secondary small", () => copiarTexto(t.url)));
"""
).strip()

PAINEL_JS_CREATE_OLD = '    alert(`Instância criada!\\n\\nLink: ${r.tenant.url}`);'
PAINEL_JS_CREATE_NEW = (
    "    const ext = r.tenant.url_externa || r.tenant.url;\n"
    "    alert(`Instância criada!\\n\\nLink externo: ${ext}\\nLAN: ${r.tenant.url}`);"
)

PAINEL_JS_BI_OLD = textwrap.dedent(
    """
          <div class="url">LAN: ${t.url} | slug: ${t.slug}</div>
          ${urlExt ? `<div class="url" style="color:#b8f5c3">Externo: ${urlExt} — ${biPath}</div>` : ""}
"""
).strip()

PAINEL_JS_BI_NEW = textwrap.dedent(
    """
          <div class="url" style="color:#b8f5c3">Externo: ${urlExt || "—"}</div>
          <div class="url hint">LAN: ${t.url} | slug: ${t.slug} | path: ${biPath}</div>
"""
).strip()

PAINEL_JS_BI_BTNS_OLD = textwrap.dedent(
    """
      ac.appendChild(btn("Copiar LAN", "primary small", () => copiarTexto(t.url)));
      if (urlExt) {
        ac.appendChild(btn("Copiar externo", "primary small", () => copiarTexto(urlExt)));
      }
"""
).strip()

PAINEL_JS_BI_BTNS_NEW = textwrap.dedent(
    """
      if (urlExt) ac.appendChild(btn("Copiar link", "primary small", () => copiarTexto(urlExt)));
      ac.appendChild(btn("Copiar LAN", "secondary small", () => copiarTexto(t.url)));
"""
).strip()

RUN_FIX = r'''
import os, json
from pathlib import Path
for line in Path('/opt/nfe-web/.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
import sys
sys.path.insert(0, '/opt/nfe-web')
import painel_store as ps
import bi_store as bs
import web_tenant_registry as wr
import bi_tenant_registry as br

ext = os.getenv('NFE_PUBLIC_EXTERNAL_URL', 'https://dadosfrete.duckdns.org').rstrip('/')
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


def apply_replace(path, old, new, skip=False):
    if skip:
        return False
    return old, new


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()

    for path, replacements in PATCHES.items():
        with sftp.open(path, "r") as f:
            content = f.read().decode("utf-8")
        original = content
        for item in replacements:
            if len(item) == 3:
                old, new, skip = item
                if skip:
                    continue
            else:
                old, new = item
            if old not in content:
                print(f"AVISO: trecho não encontrado em {path}")
                continue
            content = content.replace(old, new, 1)
        if content != original:
            with sftp.open(path, "w") as f:
                f.write(content.encode("utf-8"))
            print(f"PATCH OK: {path}")

    painel_js_path = f"{APP}/frontend/painel/painel.js"
    with sftp.open(painel_js_path, "r") as f:
        js = f.read().decode("utf-8")
    js_orig = js
    for old, new in [
        (PAINEL_JS_OLD, PAINEL_JS_NEW),
        (PAINEL_JS_BTNS_OLD, PAINEL_JS_BTNS_NEW),
        (PAINEL_JS_CREATE_OLD, PAINEL_JS_CREATE_NEW),
        (PAINEL_JS_BI_OLD, PAINEL_JS_BI_NEW),
        (PAINEL_JS_BI_BTNS_OLD, PAINEL_JS_BI_BTNS_NEW),
    ]:
        if old in js:
            js = js.replace(old, new, 1)
        else:
            print(f"AVISO: trecho painel.js não encontrado")
    if js != js_orig:
        with sftp.open(painel_js_path, "w") as f:
            f.write(js.encode("utf-8"))
        print("PATCH OK: painel.js")

    with sftp.open("/tmp/_fix_painel_links_run.py", "w") as f:
        f.write(RUN_FIX)
    sftp.close()

    print(run(c, f"cd {APP} && ./venv/bin/python /tmp/_fix_painel_links_run.py"))
    print(run(c, "pkill -f 'uvicorn backend.app.main:app' || true; sleep 2; "
                 f"cd {APP} && nohup ./venv/bin/python -m uvicorn backend.app.main:app "
                 "--host 0.0.0.0 --port 8090 >> /opt/nfe-web/uvicorn.log 2>&1 & sleep 2; "
                 "pgrep -af 'uvicorn backend.app.main' | head -2"))
    c.close()
    print("Concluído.")


if __name__ == "__main__":
    main()
