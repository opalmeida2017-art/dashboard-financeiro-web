"""Variáveis de ambiente do tenant isoladas por requisição/greenlet.

O gunicorn roda workers gevent: várias requisições de transportadoras diferentes
dividem o mesmo processo. Gravar DATABASE_URL etc. só em os.environ fazia uma
requisição enxergar o banco de outra. Aqui os.environ passa a consultar primeiro
os valores do tenant ativos no contexto atual (ContextVar, isolado por greenlet).
"""
from __future__ import annotations

import os
from contextvars import ContextVar

_AUSENTE = object()
_overrides: ContextVar[dict | None] = ContextVar("bi_tenant_env", default=None)


class _TenantEnviron(type(os.environ)):
    def __getitem__(self, key):
        ov = _overrides.get()
        if ov is not None and key in ov:
            val = ov[key]
            if val is _AUSENTE:
                raise KeyError(key)
            return val
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        ov = _overrides.get()
        if ov is not None and key in ov:
            ov[key] = value

    def __delitem__(self, key):
        ov = _overrides.get()
        if ov is not None and key in ov:
            ov[key] = _AUSENTE
        try:
            super().__delitem__(key)
        except KeyError:
            if ov is None or key not in ov:
                raise


def instalar() -> None:
    if isinstance(os.environ, _TenantEnviron):
        return
    base = os.environ
    os.environ = _TenantEnviron(
        base._data, base.encodekey, base.decodekey, base.encodevalue, base.decodevalue
    )


def definir(valores: dict[str, str | None], chaves: tuple[str, ...]) -> None:
    """Ativa as variáveis do tenant no contexto atual; chaves sem valor ficam ausentes."""
    instalar()
    ov = {k: _AUSENTE for k in chaves}
    for k, v in valores.items():
        ov[k] = _AUSENTE if v is None else str(v)
    _overrides.set(ov)


def limpar() -> None:
    _overrides.set(None)


instalar()
