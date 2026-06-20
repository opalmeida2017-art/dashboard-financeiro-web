import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
ZIP = "/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c3332-atual.zip"


def sudo(c, cmd):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    return o.read().decode(errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    cmd = (
        f"rm -rf /tmp/sati_t && mkdir /tmp/sati_t && "
        f"unzip -q -o {ZIP} -d /tmp/sati_t && "
        f"ls -la /tmp/sati_t && "
        f"/usr/lib/postgresql/17/bin/pg_restore --list /tmp/sati_t/SATI-c3332.dump 2>&1 | head -25"
    )
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode(errors="replace"))
    print(e.read().decode(errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
