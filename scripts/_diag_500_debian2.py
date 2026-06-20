import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")

print(run(
    f"cd {BI} && ./venv/bin/python - <<'PY'\n"
    "import traceback\n"
    "from app import app\n"
    "c = app.test_client()\n"
    "for path in ['/', '/biweb/wcarlos/', '/biweb/wcarlos']:\n"
    "    try:\n"
    "        r = c.get(path, headers={'Host': 'dadosfrete.duckdns.org'})\n"
    "        print(path, r.status_code, len(r.data))\n"
    "    except Exception:\n"
    "        traceback.print_exc()\n"
    "try:\n"
    "    from app.data from app.data import data_manager as dm\n"
    "    v = dm._total_investimento_estoque(1)\n"
    "    print('investimento_estoque', v)\n"
    "except Exception:\n"
    "    traceback.print_exc()\n"
    "PY"
))

print("--- nginx error ---")
print(run("sudo tail -20 /var/log/nginx/error.log 2>/dev/null", t=30))

c.close()
