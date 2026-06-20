#!/usr/bin/env python3
import sys

sys.path.insert(0, "/opt/nfe-web")

from deploy.provision_bi_tenant import criar_instancia_bi, remover_instancia_bi

SLUG = "w-carlos"
RAZAO = "W CARLOS"
SATI_URL = "https://sat3.intersite.com.br/c2910"

if __name__ == "__main__":
    action = (sys.argv[1] if len(sys.argv) > 1 else "recriar").lower()
    if action in ("remover", "recriar"):
        try:
            r = remover_instancia_bi(SLUG, drop_database=True)
            print("removido", r.get("pg_database"))
        except Exception as exc:
            print("remover:", exc)
    if action in ("criar", "recriar"):
        r = criar_instancia_bi(RAZAO, SLUG, SATI_URL)
        print("slug", r.get("slug"))
        print("db", r.get("pg_database"))
        print("sati_db", r.get("sati_database"))
        print("url", r.get("url"))
