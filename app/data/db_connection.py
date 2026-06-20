# db_connection.py

import os

from sqlalchemy import create_engine

from app.utils.env_loader import load_env

load_env()


class _EngineHolder:
    """Engine que recria quando DATABASE_URL muda (multi-tenant Debian)."""

    def __init__(self) -> None:
        self._engine = None
        self._url: str | None = None

    def _database_url(self) -> str:
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            raise ValueError(
                "DATABASE_URL não definida. Configure no arquivo .env do projeto."
            )
        return url

    def _ensure(self):
        url = self._database_url()
        if self._engine is None or self._url != url:
            if self._engine is not None:
                self._engine.dispose()
            self._engine = create_engine(url)
            self._url = url
        return self._engine

    def connect(self, *args, **kwargs):
        return self._ensure().connect(*args, **kwargs)

    def begin(self, *args, **kwargs):
        return self._ensure().begin(*args, **kwargs)

    def raw_connection(self, *args, **kwargs):
        return self._ensure().raw_connection(*args, **kwargs)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
        self._url = None

    def __getattr__(self, name):
        return getattr(self._ensure(), name)


engine = _EngineHolder()


def reset_engine() -> None:
    engine.dispose()
