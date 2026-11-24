# db_connection.py

import os

from sqlalchemy import create_engine

from app.utils.env_loader import load_env
import infra.tenant_licensing.tenant_env  # noqa: F401  (os.environ isolado por requisição)

load_env()


class _EngineHolder:
    """Um engine (pool) por DATABASE_URL; a URL vem do tenant da requisição atual."""

    def __init__(self) -> None:
        self._engines: dict = {}

    def _database_url(self) -> str:
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            raise ValueError(
                "DATABASE_URL não definida. Configure no arquivo .env do projeto."
            )
        return url

    def _ensure(self):
        url = self._database_url()
        eng = self._engines.get(url)
        if eng is None:
            eng = create_engine(
                url,
                pool_pre_ping=True,
                connect_args={
                    "client_encoding": "utf8",
                    "options": "-c client_encoding=UTF8",
                },
            )
            eng = self._engines.setdefault(url, eng)
        return eng

    def connect(self, *args, **kwargs):
        return self._ensure().connect(*args, **kwargs)

    def begin(self, *args, **kwargs):
        return self._ensure().begin(*args, **kwargs)

    def raw_connection(self, *args, **kwargs):
        return self._ensure().raw_connection(*args, **kwargs)

    def dispose(self) -> None:
        """Fecha o pool do tenant atual (os demais tenants seguem com o seu)."""
        url = os.getenv("DATABASE_URL", "").strip()
        eng = self._engines.pop(url, None)
        if eng is not None:
            eng.dispose()

    def __getattr__(self, name):
        return getattr(self._ensure(), name)


engine = _EngineHolder()


def reset_engine() -> None:
    engine.dispose()
