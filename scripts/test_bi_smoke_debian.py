"""Smoke test do BIWEB no Debian — páginas, APIs e gráficos."""
import json
import sys
import textwrap

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
PREFIX = "/biweb/transporte-brasil"
BASE = f"https://127.0.0.1:8443{PREFIX}"

REMOTE_PY = textwrap.dedent(
    r"""
import json, re, ssl
from http.cookiejar import CookieJar
from urllib import error, request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HOST = "https://127.0.0.1:8443"
PREFIX = "/biweb/transporte-brasil"

jar = CookieJar()
opener = request.build_opener(
    request.HTTPSHandler(context=ctx), request.HTTPCookieProcessor(jar)
)
request.install_opener(opener)


def fetch(path, timeout=90):
    url = HOST + path
    req = request.Request(url, headers={"User-Agent": "BIWEB-smoke"})
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return 0, str(exc)


report = []

st, body = fetch(PREFIX + "/", timeout=30)
report.append(
    {
        "test": "home",
        "status": st,
        "navbar": "biweb-navbar" in body,
        "dash": "dash-page" in body,
        "chart_js": bool(re.search(r"chart(\.umd)?\.js", body, re.I)),
        "auto_login": "Administrador" in body,
    }
)

apis = [
    ("dashboard_body", PREFIX + "/api/dashboard_body?start_date=2026-06-01&end_date=2026-06-23", 90),
    ("monthly_summary", PREFIX + "/api/monthly_summary?start_date=2026-06-01&end_date=2026-06-23", 90),
    (
        "gestao_comercial",
        PREFIX + "/api/gestao_comercial_data?analise=1&start_date=2026-06-01&end_date=2026-06-23",
        120,
    ),
    (
        "visao_bi",
        PREFIX + "/api/visao_bi_data?visao=volume&analise=1&start_date=2026-06-01&end_date=2026-06-23",
        120,
    ),
    ("fluxo_body", PREFIX + "/api/fluxo_viagem_body?start_date=2026-06-01&end_date=2026-06-23", 120),
]
for name, path, tmo in apis:
    st, body = fetch(path, timeout=tmo)
    item = {"test": f"api_{name}", "status": st, "bytes": len(body)}
    if st == 200:
        try:
            data = json.loads(body)
            item["json"] = True
            if isinstance(data, dict):
                item["keys"] = list(data.keys())[:8]
                chart = data.get("chart")
                item["has_chart"] = bool(chart)
                if chart and isinstance(chart, dict):
                    item["chart_labels"] = len(chart.get("labels") or [])
        except json.JSONDecodeError:
            item["html"] = True
            item["has_canvas"] = "canvas" in body
            item["has_kpi"] = "dash-kpi" in body or "kpi" in body.lower()
    else:
        item["snippet"] = body[:200]
    report.append(item)

pages = [
    ("visao_comercial", PREFIX + "/visao_comercial"),
    ("visao_volume", PREFIX + "/visao/volume"),
    ("fluxo_viagem", PREFIX + "/fluxo_viagem"),
    ("configuracao", PREFIX + "/configuracao"),
]
for name, path in pages:
    st, body = fetch(path, timeout=60)
    report.append(
        {
            "test": f"page_{name}",
            "status": st,
            "buttons": body.lower().count("btn") + body.lower().count("button"),
            "chart_js": bool(re.search(r"chart(\.umd)?\.js", body, re.I)),
            "canvas": "canvas" in body.lower(),
        }
    )

ok = sum(1 for r in report if r.get("status") == 200)
failed = [r for r in report if r.get("status") != 200]
print(json.dumps({"ok": ok, "total": len(report), "failed": failed, "all": report}, ensure_ascii=False))
"""
)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_biweb_smoke3.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    _, o, e = c.exec_command(
        "/home/oitamar/dashboard-financeiro-web/venv/bin/python /tmp/_biweb_smoke3.py",
        timeout=600,
    )
    out = (o.read() + e.read()).decode("utf-8", "replace")
    c.close()
    print(out)
    data = json.loads(out.strip().splitlines()[-1] if "\n" in out else out)
    return 0 if not data.get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
