"""Compatibilidade: python app.py → servidor local de desenvolvimento."""
import os
import sys

# Evita conflito entre este arquivo (app.py) e o pacote app/
os.environ.setdefault("BIWEB_LOCAL_DEV", "1")

if __name__ == "__main__":
    # Executa run_dev como script para não importar o pacote app/ via este módulo
    import runpy

    runpy.run_path(os.path.join(os.path.dirname(__file__), "run_dev.py"), run_name="__main__")
else:
    from run_dev import app  # noqa: F401
