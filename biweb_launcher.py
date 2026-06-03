"""
Ponto de entrada do BIWEB Desktop (.exe).
Inicia PostgreSQL embutido, cria .env e abre o painel no navegador.
"""

from __future__ import annotations

import atexit
import os
import sys
import threading
import time
import webbrowser


def main() -> None:
    os.environ.setdefault("BIWEB_DESKTOP", "1")
    os.environ.setdefault("EXECUTION_MODE", "sync")
    os.environ.setdefault("BIWEB_SKIP_LOGIN", "1")
    os.environ.setdefault("ROBO_HEADLESS", "true")
    # PostgreSQL local (portátil). Em dev com PG instalado: BIWEB_DB_MODE=installed no .env
    os.environ.setdefault("BIWEB_DB_MODE", "embedded")

    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))

    from biweb_env import init_desktop_environment

    init_desktop_environment()

    from app import create_app

    app = create_app()
    host, port = "127.0.0.1", int(os.getenv("BIWEB_PORT", "5000"))

    def _open_browser():
        time.sleep(1.8)
        from biweb_env import setup_completed

        path = "/instalacao" if not setup_completed() else "/"
        webbrowser.open(f"http://{host}:{port}{path}")

    threading.Thread(target=_open_browser, daemon=True).start()

    from biweb_env import get_db_mode

    if get_db_mode() == "embedded":
        try:
            from embedded_pg import stop_server

            atexit.register(stop_server)
        except Exception:
            pass

    print(f"BIWEB em http://{host}:{port}  (Ctrl+C para encerrar)")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
