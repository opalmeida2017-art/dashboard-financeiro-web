"""Ponto de entrada do worker RQ (compatibilidade com deploy legado)."""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

runpy.run_path(os.path.join(ROOT, "infra", "cloud", "worker.py"), run_name="__main__")
